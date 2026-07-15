"""Tests for the `smbagent doctor` self-diagnostic command + checks."""

from __future__ import annotations

import sys
from pathlib import Path

from typer.testing import CliRunner

from smbagent import __version__
from smbagent.cli import app as cli_app
from smbagent.config import Config
from smbagent.doctor import (
    check_anthropic_api_key,
    check_asr_backend,
    check_claude_on_path,
    check_codex_on_path,
    check_config_loads,
    check_deployment_modes,
    check_mac_audio_io,
    check_openai_api_key,
    check_prompts_dir,
    check_python_deps,
    check_python_version,
    check_smbagent_version,
    check_workspaces_writable,
    run_doctor_checks,
)

# ---- check_python_version ----


def test_python_version_passes_on_311_plus():
    c = check_python_version()
    # We're running on 3.11+; should always pass in CI
    assert c.ok is True
    assert "." in c.detail


def test_python_version_fails_simulated_old(monkeypatch):
    """Simulate Python 3.10 — should fail the check."""

    class _FakeVersion:
        major = 3
        minor = 10
        micro = 0

        def __getitem__(self, i):
            return [self.major, self.minor, self.micro][i]

    monkeypatch.setattr(sys, "version_info", _FakeVersion())
    c = check_python_version()
    assert c.ok is False
    assert c.hint != ""


# ---- check_claude_on_path / check_codex_on_path ----


def test_claude_on_path_found(monkeypatch):
    monkeypatch.setattr("smbagent.doctor.shutil.which", lambda name: "/usr/bin/claude")
    c = check_claude_on_path()
    assert c.ok is True
    assert c.detail == "/usr/bin/claude"


def test_claude_not_found(monkeypatch):
    monkeypatch.setattr("smbagent.doctor.shutil.which", lambda name: None)
    c = check_claude_on_path()
    assert c.ok is False
    assert "not found" in c.detail
    assert "npm install" in c.hint


def test_codex_on_path_found(monkeypatch):
    monkeypatch.setattr("smbagent.doctor.shutil.which", lambda name: "/usr/local/bin/codex")
    c = check_codex_on_path()
    assert c.ok is True


def test_codex_not_required_for_api_validation(config: Config):
    api_cfg = Config(**{**config.__dict__, "validation_backend": "api"})
    c = check_codex_on_path(api_cfg)
    assert c.ok is True
    assert "not required" in c.detail


def test_codex_not_found(monkeypatch):
    monkeypatch.setattr("smbagent.doctor.shutil.which", lambda name: None)
    c = check_codex_on_path()
    assert c.ok is False
    assert "https://github.com/openai/codex" in c.hint


# ---- API key checks ----


def test_anthropic_key_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-real-key-here")
    c = check_anthropic_api_key()
    assert c.ok is True


def test_anthropic_key_missing(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    c = check_anthropic_api_key()
    assert c.ok is False
    assert "missing" in c.detail or "placeholder" in c.detail


def test_anthropic_key_still_placeholder(monkeypatch):
    """Operator copied .env.example but didn't fill in — should fail."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-...")
    c = check_anthropic_api_key()
    assert c.ok is False


def test_openai_key_set(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-openai-key")
    c = check_openai_api_key()
    assert c.ok is True


def test_openai_key_not_required_for_default_cli_setup(config: Config, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    c = check_openai_api_key(config)
    assert c.ok is True
    assert "not required" in c.detail


def test_openai_key_required_for_api_validation(config: Config, monkeypatch):
    api_cfg = Config(**{**config.__dict__, "validation_backend": "api"})
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    c = check_openai_api_key(api_cfg)
    assert c.ok is False
    assert "missing" in c.detail or "placeholder" in c.detail


def test_openai_key_still_placeholder(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-...")
    c = check_openai_api_key()
    assert c.ok is False


# ---- Python deps ----


def test_python_deps_all_present(monkeypatch):
    import importlib

    real_import = importlib.import_module

    def fake_import(name, package=None):
        if name == "anthropic":
            return object()
        return real_import(name, package=package)

    monkeypatch.setattr("smbagent.doctor.importlib.import_module", fake_import)
    c = check_python_deps()
    assert c.ok is True
    assert "importable" in c.detail


def test_python_deps_simulated_missing(monkeypatch):
    """Simulate a missing dep by patching importlib.import_module."""
    import importlib

    real_import = importlib.import_module

    def fake_import(name, package=None):
        if name == "anthropic":
            raise ImportError("simulated missing")
        return real_import(name, package=package)

    monkeypatch.setattr("smbagent.doctor.importlib.import_module", fake_import)
    c = check_python_deps()
    assert c.ok is False
    assert "anthropic" in c.detail
    assert "pip install" in c.hint


# ---- ASR backend ----


def test_asr_backend_none_is_ok(config: Config):
    cfg = Config(**{**config.__dict__, "asr_backend": "none"})
    c = check_asr_backend(cfg)
    assert c.ok is True
    assert "disabled" in c.detail


def test_asr_backend_api_is_ok(config: Config):
    cfg = Config(**{**config.__dict__, "asr_backend": "api"})
    c = check_asr_backend(cfg)
    assert c.ok is True
    assert "OpenAI Whisper API" in c.detail


def test_asr_backend_mlx_importable(config: Config, monkeypatch):
    def fake_import(name, package=None):
        if name == "mlx_whisper":
            return object()
        raise AssertionError(f"unexpected import: {name}")

    cfg = Config(**{**config.__dict__, "asr_backend": "mlx"})
    monkeypatch.setattr("smbagent.doctor.importlib.import_module", fake_import)
    c = check_asr_backend(cfg)
    assert c.ok is True
    assert "mlx_whisper importable" in c.detail


def test_asr_backend_mlx_missing(config: Config, monkeypatch):
    def fake_import(name, package=None):
        if name == "mlx_whisper":
            raise ImportError("simulated missing")
        raise AssertionError(f"unexpected import: {name}")

    cfg = Config(**{**config.__dict__, "asr_backend": "mlx"})
    monkeypatch.setattr("smbagent.doctor.importlib.import_module", fake_import)
    c = check_asr_backend(cfg)
    assert c.ok is False
    assert "mlx_whisper" in c.detail
    assert "SMBAGENT_ASR_BACKEND=none" in c.hint


def test_asr_backend_unknown(config: Config):
    cfg = Config(**{**config.__dict__, "asr_backend": "azure"})
    c = check_asr_backend(cfg)
    assert c.ok is False
    assert "unknown" in c.detail


def test_mac_audio_io_not_required_when_voice_disabled(config: Config):
    cfg = Config(**{**config.__dict__, "asr_backend": "none", "tts_backend": "none"})
    c = check_mac_audio_io(cfg)
    assert c.ok is True
    assert "not required" in c.detail


def test_mac_audio_io_uses_macos_selected_devices(config: Config, monkeypatch):
    cfg = Config(**{**config.__dict__, "asr_backend": "mlx", "tts_backend": "macos"})
    monkeypatch.setattr("smbagent.doctor.platform.system", lambda: "Darwin")
    monkeypatch.setattr("smbagent.doctor.shutil.which", lambda name: f"/usr/bin/{name}")
    c = check_mac_audio_io(cfg)
    assert c.ok is True
    assert "selected input device" in c.detail
    assert "selected output device" in c.detail


def test_mac_audio_io_fails_when_voice_enabled_off_macos(config: Config, monkeypatch):
    cfg = Config(**{**config.__dict__, "asr_backend": "mlx"})
    monkeypatch.setattr("smbagent.doctor.platform.system", lambda: "Linux")
    c = check_mac_audio_io(cfg)
    assert c.ok is False
    assert "requires macOS" in c.detail


def test_mac_audio_io_reports_missing_afrecord(config: Config, monkeypatch):
    cfg = Config(**{**config.__dict__, "asr_backend": "mlx", "tts_backend": "none"})
    monkeypatch.setattr("smbagent.doctor.platform.system", lambda: "Darwin")
    monkeypatch.setattr("smbagent.doctor.shutil.which", lambda name: None)
    c = check_mac_audio_io(cfg)
    assert c.ok is False
    assert "afrecord" in c.detail


def test_deployment_modes_sensitive_rejects_cloud_asr(config: Config):
    cfg = Config(**{**config.__dict__, "sensitive_mode": True, "asr_backend": "api"})
    c = check_deployment_modes(cfg)
    assert c.ok is False
    assert "sensitive_asr_local_or_text" in c.detail


def test_deployment_modes_local_only_fails_closed(config: Config):
    cfg = Config(**{**config.__dict__, "local_only_mode": True})
    c = check_deployment_modes(cfg)
    assert c.ok is False
    assert "local_only" in c.detail


# ---- Prompts dir ----


def test_prompts_dir_real_one_passes():
    """The actual prompts dir in the repo should pass."""
    from smbagent.config import load_config

    cfg = load_config()
    c = check_prompts_dir(cfg.prompts_dir)
    assert c.ok is True


def test_prompts_dir_missing(tmp_path: Path):
    c = check_prompts_dir(tmp_path / "nope")
    assert c.ok is False
    assert "does not exist" in c.detail


def test_prompts_dir_incomplete(tmp_path: Path):
    """Dir exists but is missing some required prompt files."""
    pd = tmp_path / "prompts"
    pd.mkdir()
    (pd / "qualify_ja.md").write_text("...", encoding="utf-8")  # only 1 of 5
    c = check_prompts_dir(pd)
    assert c.ok is False
    assert "missing" in c.detail


# ---- Workspaces dir ----


def test_workspaces_dir_writable(tmp_path: Path):
    c = check_workspaces_writable(tmp_path / "workspaces")
    assert c.ok is True


def test_workspaces_dir_creates_if_missing(tmp_path: Path):
    d = tmp_path / "new" / "deep" / "workspaces"
    c = check_workspaces_writable(d)
    assert c.ok is True
    assert d.exists()


def test_workspaces_dir_not_writable(tmp_path: Path, monkeypatch):
    """Simulate a write failure by monkeypatching Path.write_text."""
    d = tmp_path / "ws"
    d.mkdir()

    real_write = Path.write_text

    def fake_write(self, *a, **kw):
        if self.name == ".doctor_probe":
            raise OSError("simulated permission denied")
        return real_write(self, *a, **kw)

    monkeypatch.setattr(Path, "write_text", fake_write)
    c = check_workspaces_writable(d)
    assert c.ok is False
    assert "write probe failed" in c.detail


# ---- config_loads ----


def test_config_loads_succeeds():
    c = check_config_loads()
    assert c.ok is True


# ---- smbagent_version ----


def test_smbagent_version_reports_current():
    c = check_smbagent_version()
    assert c.ok is True
    assert c.detail == __version__


# ---- run_doctor_checks ----


def test_run_doctor_checks_returns_list():
    checks = run_doctor_checks()
    assert isinstance(checks, list)
    assert len(checks) >= 8
    # Every check has the right shape
    for c in checks:
        assert hasattr(c, "ok") and hasattr(c, "name") and hasattr(c, "detail")


def test_run_doctor_checks_includes_all_expected():
    names = {c.name for c in run_doctor_checks()}
    for expected in (
        "smbagent version",
        "Python version",
        "Python dependencies",
        "ASR backend",
        "Mac audio I/O",
        "Deployment modes",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "claude CLI on PATH",
        "codex CLI on PATH",
        "Prompts directory",
        "Workspaces directory writable",
        "Configuration loads",
    ):
        assert expected in names, f"missing: {expected}"


# ---- CLI integration ----


def test_doctor_cli_command_exits_zero_when_all_pass(monkeypatch):
    """Force every check to pass by patching the runner."""
    from smbagent.doctor import DoctorCheck

    def fake_runner():
        return [
            DoctorCheck(name="thing-1", ok=True, detail="ok"),
            DoctorCheck(name="thing-2", ok=True, detail="ok"),
        ]

    monkeypatch.setattr("smbagent.cli.run_doctor_checks", fake_runner)
    runner = CliRunner()
    result = runner.invoke(cli_app, ["doctor"])
    assert result.exit_code == 0
    assert "All checks passed" in result.stdout


def test_doctor_cli_command_exits_nonzero_when_anything_fails(monkeypatch):
    from smbagent.doctor import DoctorCheck

    def fake_runner():
        return [
            DoctorCheck(name="thing-1", ok=True, detail="ok"),
            DoctorCheck(name="thing-2", ok=False, detail="bad", hint="do X"),
        ]

    monkeypatch.setattr("smbagent.cli.run_doctor_checks", fake_runner)
    runner = CliRunner()
    result = runner.invoke(cli_app, ["doctor"])
    assert result.exit_code != 0
    assert "1 check(s) failed" in result.stdout


def test_doctor_cli_command_listed_in_help(monkeypatch, tmp_path: Path):
    """Cosmetic but important: `smbagent --help` must surface `doctor`."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspaces").mkdir()
    runner = CliRunner()
    result = runner.invoke(cli_app, ["--help"])
    assert result.exit_code == 0
    assert "doctor" in result.stdout
