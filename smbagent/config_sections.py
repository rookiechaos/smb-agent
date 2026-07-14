from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, kw_only=True)
class PipelineConfig:
    anthropic_api_key: str | None
    openai_api_key: str | None
    plan_model: str
    coding_cmd: list[str]
    validation_backend: str
    validation_cmd: list[str]
    validation_model: str
    harness_profile: str
    subprocess_isolation: str
    subprocess_read_paths: list[str]
    apple_container_coding_image: str
    apple_container_validation_image: str
    apple_container_home_mounts: bool
    max_rounds: int
    coding_timeout_s: int
    validation_timeout_s: int
    anthropic_timeout_s: float
    pipeline_timeout_s: int
    workspace_size_warn_mb: int
    anneal_temp_creative: float
    anneal_temp_convergence: float
    anneal_temp_final: float
    anneal_stale_rounds: int
    bridge_orchestrator_enabled: bool
    bridge_orchestrator_model: str
    bridge_orchestrator_max_tokens: int
    bridge_orchestrator_temperature: float
    humanize_enabled: bool
    max_humanize_rounds: int
    adaptive_loop_enabled: bool = True
    adaptive_min_rounds: int = 2
    adaptive_max_rounds: int = 20


@dataclass(frozen=True, kw_only=True)
class RuntimeServeConfig:
    admin_token: str | None
    cors_origins: list[str]
    alert_webhook: str | None
    onboard_rate_per_hour: int
    chat_rate_per_minute: int
    monitor_login_rate_per_minute: int
    rate_limit_backend: str = "sqlite-local"
    onboarding_repeat_fingerprint_per_day: int = 2
    onboarding_contact_rate_per_day: int = 3
    onboarding_ip_rate_per_day: int = 20
    onboarding_block_disposable_email: bool = True
    onboarding_honeypot_enabled: bool = True
    token_ttl_days: int = 365
    max_body_bytes: int = 1024 * 1024
    serve_host: str = "127.0.0.1"
    serve_port: int = 8000
    monitor_public_base_url: str | None = None
    monitor_exposure: str = "local-only"
    remote_access_channel: str = "none"
    allow_lan_monitor_fallback: bool = False
    allow_monitor_query_token_fallback: bool = False
    maintenance_access_channel: str = "ssh-vpn"
    workflow_check_interval_minutes: int = 60
    monthly_api_budget_jpy: int = 30000
    usd_to_jpy_rate: float = 150.0
    workflow_circuit_breaker_enabled: bool = False
    workflow_circuit_breaker_consecutive_failures: int = 3
    workflow_circuit_breaker_failures_in_window: int = 5
    workflow_circuit_breaker_window_minutes: int = 30


@dataclass(frozen=True, kw_only=True)
class VoiceConfig:
    voice_backend: str
    asr_backend: str
    asr_model: str
    asr_delete_audio_after_transcribe: bool = True
    voice_capture_duration_s: float = 15.0
    voice_capture_sample_rate: int = 16000
    tts_backend: str = "none"
    voice_cloud_redaction_enabled: bool = True
    voice_cloud_minimization_mode: str = "balanced"
    consent_record_required: bool = True


@dataclass(frozen=True, kw_only=True)
class SLMConfig:
    slm_advisory_enabled: bool = False
    local_llm_backend: str = "none"
    pipeline_local_llm_enabled: bool = False
    slm_advisory_min_confidence: float = 0.6
    slm_advisory_timeout_s: float = 5.0
    slm_auto_train_enabled: bool = False
    slm_auto_promote_enabled: bool = False
    slm_training_export_allow_raw_logs: bool = False
    slm_training_export_allow_hidden_reasoning: bool = False
    slm_completion_enabled: bool = False
    slm_completion_backend: str = "sglang"
    slm_completion_allowed_stages: tuple[str, ...] = (
        "preplan",
        "employee_route",
        "context_refresh",
        "loop_advice",
    )


@dataclass(frozen=True, kw_only=True)
class DeploymentAttestationConfig:
    filevault_confirmed: bool = False
    local_workspace_confirmed: bool = False
    no_synced_folders_confirmed: bool = False
    backup_restore_drill_confirmed: bool = False
    launch_acceptance_confirmed: bool = False
    secret_storage_mode: str = "local_env"
    secret_storage_keychain_service: str = "com.smbagent.integrations"
    backup_encryption_mode: str = "none"
    backup_encryption_passphrase_env: str = "SMBAGENT_BACKUP_PASSPHRASE"


@dataclass(frozen=True, kw_only=True)
class GovernanceConfig:
    trust_principle: str = "trustable"
    external_execution_policy: str = "hitl"
    allow_unattended_external_writes: bool = False
    context_refresh_warn_days: int = 90
    data_retention_days: int = 180
    runtime_log_retention_days: int = 90
    failure_memory_retention_days: int = 365
    transcript_retention_days: int = 30
    allow_failure_memory_training_use: bool = False
    sensitive_mode: bool = False
    local_only_mode: bool = False


@dataclass(frozen=True, kw_only=True)
class PathConfig:
    root: Path
    workspaces_dir: Path
    prompts_dir: Path


_CONFIG_SECTIONS = (
    "paths",
    "pipeline",
    "runtime",
    "voice",
    "slm",
    "deployment",
    "governance",
)
