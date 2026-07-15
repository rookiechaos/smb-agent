"""Tests for the ASR backends + factory.

No outside network. The OpenAI SDK call is mocked at the client method level;
the mlx_whisper package is mocked via sys.modules (or absent) so we exercise
both the happy path and the "package not installed" hint.
"""

from __future__ import annotations

import sys
import types
from dataclasses import replace

import pytest

from smbagent.config import Config, load_config
from smbagent.voice import (
    ASRBackendError,
    MLXWhisperBackend,
    WhisperAPIBackend,
    build_asr_backend,
)

# ============================================================================
# WhisperAPIBackend
# ============================================================================


class _FakeWhisperResponse:
    """Stand-in for the openai.AudioTranscription response (modern shape)."""

    def __init__(self, text: str):
        self.text = text


class _FakeTranscriptions:
    def __init__(self, response=None, raises=None):
        self._response = response
        self._raises = raises
        self.calls: list[dict] = []

    def create(self, *, model, file, language):
        self.calls.append(
            {
                "model": model,
                "filename": getattr(file, "name", None),
                "language": language,
            }
        )
        if self._raises:
            raise self._raises
        return self._response


class _FakeAudio:
    def __init__(self, response=None, raises=None):
        self.transcriptions = _FakeTranscriptions(response=response, raises=raises)


class _FakeOpenAI:
    def __init__(self, *, response=None, raises=None):
        self.audio = _FakeAudio(response=response, raises=raises)


def _backend_with_fake_client(client) -> WhisperAPIBackend:
    """Construct a WhisperAPIBackend and pre-load its lazy client field."""
    b = WhisperAPIBackend(api_key="test-key", model="whisper-1")
    b._client = client  # bypass the lazy import in tests
    return b


def test_whisper_api_transcribe_happy_path():
    fake = _FakeOpenAI(response=_FakeWhisperResponse("こんにちは"))
    b = _backend_with_fake_client(fake)
    text = b.transcribe(b"fake-wav-bytes", language="ja")
    assert text == "こんにちは"
    call = fake.audio.transcriptions.calls[0]
    assert call["model"] == "whisper-1"
    assert call["language"] == "ja"
    assert call["filename"] == "audio.wav"


def test_whisper_api_uses_configured_model():
    fake = _FakeOpenAI(response=_FakeWhisperResponse("ok"))
    b = WhisperAPIBackend(api_key="k", model="whisper-large")
    b._client = fake
    b.transcribe(b"audio", language="en")
    assert fake.audio.transcriptions.calls[0]["model"] == "whisper-large"


def test_whisper_api_empty_audio_raises():
    b = _backend_with_fake_client(_FakeOpenAI(response=_FakeWhisperResponse("x")))
    with pytest.raises(ASRBackendError) as excinfo:
        b.transcribe(b"")
    assert "empty audio_bytes" in str(excinfo.value)


def test_whisper_api_wraps_sdk_errors():
    fake = _FakeOpenAI(raises=RuntimeError("network down"))
    b = _backend_with_fake_client(fake)
    with pytest.raises(ASRBackendError) as excinfo:
        b.transcribe(b"audio")
    assert "Whisper API call failed" in str(excinfo.value)
    assert "network down" in str(excinfo.value)


def test_whisper_api_no_text_in_response_raises():
    fake = _FakeOpenAI(response=_FakeWhisperResponse(""))
    b = _backend_with_fake_client(fake)
    with pytest.raises(ASRBackendError) as excinfo:
        b.transcribe(b"audio")
    assert "no text" in str(excinfo.value)


def test_whisper_api_listen_once_uses_local_capture(monkeypatch):
    class FakeCapture:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def capture_once(self):
            return types.SimpleNamespace(audio_bytes=b"audio", audio_path=None, deleted=True)

    fake = _FakeOpenAI(text="聞き取りました")
    b = _backend_with_fake_client(fake)
    monkeypatch.setattr("smbagent.voice.whisper_api.MacOSMicCapture", FakeCapture)
    assert b.listen_once() == "聞き取りました"


def test_whisper_api_backend_name_attribute():
    assert WhisperAPIBackend().name == "whisper-api"


def test_whisper_api_lazy_import_raises_clean_error(monkeypatch):
    """If openai isn't installed, calling transcribe gives a clean error."""
    # Hide the openai module from import resolution
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "openai" or (fromlist and "OpenAI" in fromlist and name == "openai"):
            raise ImportError("simulated missing openai")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)
    b = WhisperAPIBackend()
    with pytest.raises(ASRBackendError) as excinfo:
        b.transcribe(b"audio")
    assert "openai" in str(excinfo.value).lower()


# ============================================================================
# MLXWhisperBackend
# ============================================================================


def test_mlx_backend_raises_when_package_missing(monkeypatch):
    """Without mlx_whisper installed, transcribe raises ASRBackendError cleanly."""
    monkeypatch.delitem(sys.modules, "mlx_whisper", raising=False)

    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def fake_import(name, *args, **kwargs):
        if name == "mlx_whisper":
            raise ImportError("simulated: package not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    b = MLXWhisperBackend()
    with pytest.raises(ASRBackendError) as excinfo:
        b.transcribe(b"audio")
    assert "mlx_whisper not installed" in str(excinfo.value)
    assert "pip install" in str(excinfo.value)


def test_mlx_backend_transcribe_happy_path(monkeypatch, tmp_path):
    """Inject a fake mlx_whisper module that records calls and returns text."""
    fake_module = types.ModuleType("mlx_whisper")
    calls: list[dict] = []

    def fake_transcribe(audio_path, *, path_or_hf_repo, language=None, word_timestamps=False):
        calls.append(
            {
                "audio_path": audio_path,
                "model": path_or_hf_repo,
                "language": language,
                "word_timestamps": word_timestamps,
            }
        )
        return {"text": "  おはようございます  "}

    fake_module.transcribe = fake_transcribe
    monkeypatch.setitem(sys.modules, "mlx_whisper", fake_module)

    b = MLXWhisperBackend(model="some-model")
    text = b.transcribe(b"\x00\x01\x02wav-bytes", language="ja")
    assert text == "おはようございます"  # stripped
    assert calls[0]["model"] == "some-model"
    assert calls[0]["language"] == "ja"


def test_mlx_backend_passes_word_timestamps_flag(monkeypatch):
    fake_module = types.ModuleType("mlx_whisper")
    captured = {}

    def fake_transcribe(audio_path, *, path_or_hf_repo, language=None, word_timestamps=False):
        captured["word_timestamps"] = word_timestamps
        return {"text": "ok"}

    fake_module.transcribe = fake_transcribe
    monkeypatch.setitem(sys.modules, "mlx_whisper", fake_module)
    b = MLXWhisperBackend(word_timestamps=True)
    b.transcribe(b"audio")
    assert captured["word_timestamps"] is True


def test_mlx_backend_empty_audio_raises():
    b = MLXWhisperBackend()
    with pytest.raises(ASRBackendError) as excinfo:
        b.transcribe(b"")
    assert "empty audio_bytes" in str(excinfo.value)


def test_mlx_backend_wraps_transcribe_errors(monkeypatch):
    fake_module = types.ModuleType("mlx_whisper")

    def fake_transcribe(audio_path, **kwargs):
        raise RuntimeError("CUDA OOM (or whatever)")

    fake_module.transcribe = fake_transcribe
    monkeypatch.setitem(sys.modules, "mlx_whisper", fake_module)
    b = MLXWhisperBackend()
    with pytest.raises(ASRBackendError) as excinfo:
        b.transcribe(b"audio")
    assert "mlx-whisper transcribe failed" in str(excinfo.value)
    assert "CUDA OOM" in str(excinfo.value)


def test_mlx_backend_no_text_in_result_raises(monkeypatch):
    fake_module = types.ModuleType("mlx_whisper")

    def fake_transcribe(audio_path, **kwargs):
        return {"segments": []}  # no "text" key

    fake_module.transcribe = fake_transcribe
    monkeypatch.setitem(sys.modules, "mlx_whisper", fake_module)
    b = MLXWhisperBackend()
    with pytest.raises(ASRBackendError) as excinfo:
        b.transcribe(b"audio")
    assert "no text" in str(excinfo.value)


def test_mlx_backend_cleans_up_tempfile(monkeypatch):
    """The tempfile we write should be removed after transcription."""
    fake_module = types.ModuleType("mlx_whisper")
    seen_paths: list[str] = []

    def fake_transcribe(audio_path, **kwargs):
        seen_paths.append(audio_path)
        return {"text": "ok"}

    fake_module.transcribe = fake_transcribe
    monkeypatch.setitem(sys.modules, "mlx_whisper", fake_module)

    b = MLXWhisperBackend()
    b.transcribe(b"audio-bytes")
    assert seen_paths, "transcribe wasn't called"
    from pathlib import Path

    assert not Path(seen_paths[0]).exists(), "tempfile should be cleaned up"


def test_mlx_backend_listen_once_uses_local_capture(monkeypatch):
    fake_module = types.ModuleType("mlx_whisper")
    fake_module.transcribe = lambda *args, **kwargs: {"text": "ローカル音声です"}
    monkeypatch.setitem(sys.modules, "mlx_whisper", fake_module)

    class FakeCapture:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def capture_once(self):
            return types.SimpleNamespace(audio_bytes=b"audio", audio_path=None, deleted=True)

    b = MLXWhisperBackend()
    monkeypatch.setattr("smbagent.voice.mlx_whisper.MacOSMicCapture", FakeCapture)
    assert b.listen_once() == "ローカル音声です"


def test_mlx_backend_default_model():
    """The default points to the community large-v3-turbo port."""
    b = MLXWhisperBackend()
    assert "whisper" in b.model.lower()
    assert b.name == "mlx-whisper"


# ============================================================================
# build_asr_backend factory
# ============================================================================


def test_load_config_defaults_asr_to_mlx(monkeypatch):
    monkeypatch.delenv("SMBAGENT_ASR_BACKEND", raising=False)
    assert load_config().asr_backend == "mlx"


def test_factory_defaults_empty_backend_to_mlx(config: Config):
    cfg = replace(config, asr_backend="")
    backend = build_asr_backend(cfg)
    assert isinstance(backend, MLXWhisperBackend)


def test_factory_returns_none_when_explicit_none(config: Config):
    cfg = replace(config, asr_backend="none")
    assert build_asr_backend(cfg) is None


def test_factory_returns_api_backend(config: Config):
    cfg = replace(config, asr_backend="api")
    backend = build_asr_backend(cfg)
    assert isinstance(backend, WhisperAPIBackend)
    assert backend.model == "whisper-1"  # default
    assert backend.api_key == cfg.openai_api_key


def test_factory_respects_asr_model_for_api(config: Config):
    cfg = replace(config, asr_backend="api", asr_model="whisper-large-v3")
    backend = build_asr_backend(cfg)
    assert backend.model == "whisper-large-v3"


def test_factory_returns_mlx_backend(config: Config):
    cfg = replace(config, asr_backend="mlx")
    backend = build_asr_backend(cfg)
    assert isinstance(backend, MLXWhisperBackend)
    # Default model is the community large-v3-turbo
    assert "whisper" in backend.model.lower()


def test_factory_respects_asr_model_for_mlx(config: Config):
    cfg = replace(config, asr_backend="mlx", asr_model="custom/whisper-small-mlx")
    backend = build_asr_backend(cfg)
    assert backend.model == "custom/whisper-small-mlx"


def test_factory_case_insensitive(config: Config):
    cfg = replace(config, asr_backend="API")
    backend = build_asr_backend(cfg)
    assert isinstance(backend, WhisperAPIBackend)


def test_factory_unknown_backend_raises(config: Config):
    cfg = replace(config, asr_backend="azure")
    with pytest.raises(ASRBackendError) as excinfo:
        build_asr_backend(cfg)
    assert "azure" in str(excinfo.value)
    assert "none, api, mlx" in str(excinfo.value)


# ============================================================================
# Polymorphism — both backends satisfy the ASRBackend protocol
# ============================================================================


def test_both_backends_have_required_methods():
    for backend in (WhisperAPIBackend(), MLXWhisperBackend()):
        assert hasattr(backend, "transcribe")
        assert hasattr(backend, "listen_once")
        assert hasattr(backend, "name")
        assert callable(backend.transcribe)
