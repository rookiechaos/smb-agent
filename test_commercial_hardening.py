from __future__ import annotations

import json

import pytest

from smbagent.cloud_llm_guard import sanitize_cloud_text
from smbagent.onboarding_abuse import (
    build_onboarding_abuse_protector,
    evaluate_onboarding_submission,
    onboarding_abuse_controls_ready,
)
from smbagent.pipeline_llm import PipelineLLMError, complete_pipeline_messages, pipeline_uses_local_llm
from smbagent.server.rate_limit import is_disposable_email


def test_sanitize_cloud_text_redacts_email(config):
    cfg = type(config)(**{**config.__dict__, "voice_cloud_redaction_enabled": True})
    assert "[REDACTED_EMAIL]" in sanitize_cloud_text(cfg, "contact a@example.com")


def test_onboarding_abuse_blocks_disposable_email(config):
    assert is_disposable_email("bot@mailinator.com") is True
    protector = build_onboarding_abuse_protector(config)
    decision = evaluate_onboarding_submission(
        protector,
        business_name="Acme",
        contact_email="bot@mailinator.com",
        brief="Need a trustworthy SMB AI workflow for scheduling and operations.",
        client_ip="127.0.0.1",
    )
    assert decision.allowed is False


def test_onboarding_abuse_blocks_honeypot(config):
    protector = build_onboarding_abuse_protector(config)
    decision = evaluate_onboarding_submission(
        protector,
        business_name="Acme",
        contact_email="owner@example.com",
        brief="Need a trustworthy SMB AI workflow for scheduling and operations.",
        client_ip="127.0.0.1",
        honeypot_value="https://spam.example",
    )
    assert decision.allowed is False


def test_onboarding_abuse_controls_ready_with_defaults(config):
    assert onboarding_abuse_controls_ready(config) is True


def test_pipeline_uses_local_llm_when_local_only(config):
    cfg = type(config)(**{**config.__dict__, "local_only_mode": True, "local_llm_backend": "sglang"})
    assert pipeline_uses_local_llm(cfg) is True


def test_complete_pipeline_messages_uses_local_sglang(config, workspace, monkeypatch):
    cfg = type(config)(
        **{
            **config.__dict__,
            "local_only_mode": True,
            "local_llm_backend": "sglang",
            "anthropic_api_key": None,
        }
    )

    class _Response:
        def read(self):
            return json.dumps(
                {
                    "choices": [{"message": {"content": '{"done": false}'}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                }
            ).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setenv("SMBAGENT_LOCAL_SLM_SGLANG_BASE_URL", "http://127.0.0.1:30000")
    monkeypatch.setattr("smbagent.pipeline_llm.urlopen", lambda *args, **kwargs: _Response())
    completion = complete_pipeline_messages(
        cfg,
        workspace,
        stage="qualify",
        model=cfg.plan_model,
        max_tokens=100,
        system="system",
        messages=[{"role": "user", "content": "brief"}],
    )
    assert completion.provider == "sglang"
    assert completion.text


def test_complete_pipeline_messages_blocks_cloud_when_local_only_without_backend(config, workspace):
    cfg = type(config)(**{**config.__dict__, "local_only_mode": True, "local_llm_backend": "none"})
    with pytest.raises(PipelineLLMError):
        complete_pipeline_messages(
            cfg,
            workspace,
            stage="qualify",
            model=cfg.plan_model,
            max_tokens=100,
            system="system",
            messages=[{"role": "user", "content": "brief"}],
        )
