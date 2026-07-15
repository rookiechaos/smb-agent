from __future__ import annotations

from pathlib import Path

import pytest

from smbagent.config import Config
from smbagent.workspace import Workspace

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "smbagent" / "prompts"


@pytest.fixture
def config(tmp_path: Path) -> Config:
    """A Config pointing at a fresh tmp_path. No real API keys, no network."""
    return Config(
        root=tmp_path,
        workspaces_dir=tmp_path / "workspaces",
        prompts_dir=PROMPTS_DIR,
        anthropic_api_key="sk-ant-test",
        openai_api_key="sk-test",
        plan_model="claude-haiku-4-5-20251001",
        coding_cmd=["claude", "-p", "--model", "opus", "--permission-mode", "acceptEdits"],
        validation_backend="cli",
        validation_cmd=["codex", "exec"],
        validation_model="gpt-5",
        harness_profile="opus-default",
        subprocess_isolation="none",
        subprocess_read_paths=[],
        apple_container_coding_image="smbagent/claude-code:latest",
        apple_container_validation_image="smbagent/codex-validation:latest",
        apple_container_home_mounts=True,
        max_rounds=5,
        coding_timeout_s=10,
        validation_timeout_s=10,
        anthropic_timeout_s=30.0,
        admin_token=None,
        cors_origins=[],
        pipeline_timeout_s=60,
        workspace_size_warn_mb=500,
        alert_webhook=None,
        onboard_rate_per_hour=100,
        chat_rate_per_minute=1000,
        monitor_login_rate_per_minute=100,
        rate_limit_backend="sqlite-local",
        onboarding_repeat_fingerprint_per_day=2,
        onboarding_contact_rate_per_day=3,
        onboarding_ip_rate_per_day=20,
        onboarding_block_disposable_email=True,
        onboarding_honeypot_enabled=True,
        token_ttl_days=0,  # never expires by default; TTL tests override
        max_body_bytes=1024 * 1024,  # 1 MB
        voice_backend="text",
        asr_backend="none",
        asr_model="",
        anneal_temp_creative=0.7,
        anneal_temp_convergence=0.3,
        anneal_temp_final=0.0,
        anneal_stale_rounds=2,
        bridge_orchestrator_enabled=False,
        bridge_orchestrator_model="claude-haiku-4-5-20251001",
        bridge_orchestrator_max_tokens=512,
        bridge_orchestrator_temperature=0.0,
        humanize_enabled=True,
        max_humanize_rounds=3,
        adaptive_loop_enabled=False,
        adaptive_min_rounds=2,
        adaptive_max_rounds=5,
        data_retention_days=180,
        runtime_log_retention_days=90,
        failure_memory_retention_days=365,
        transcript_retention_days=30,
        allow_failure_memory_training_use=False,
        remote_access_channel="none",
        allow_lan_monitor_fallback=False,
        allow_monitor_query_token_fallback=False,
        maintenance_access_channel="ssh-vpn",
    )


@pytest.fixture
def workspace(config: Config) -> Workspace:
    ws = Workspace("test-customer", config.workspaces_dir)
    ws.ensure()
    return ws
