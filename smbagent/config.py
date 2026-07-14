from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .config_loaders import (
    flatten_config_sections,
    load_deployment_config,
    load_governance_config,
    load_path_config,
    load_pipeline_config,
    load_runtime_config,
    load_slm_config,
    load_voice_config,
)
from .config_sections import (
    DeploymentAttestationConfig,
    GovernanceConfig,
    PathConfig,
    PipelineConfig,
    RuntimeServeConfig,
    SLMConfig,
    VoiceConfig,
)

load_dotenv()


def _split(cmd: str) -> list[str]:
    return shlex.split(cmd)


def _default_root() -> Path:
    cwd = Path.cwd().resolve()
    if (cwd / "smbagent").is_dir():
        return cwd
    return Path(__file__).resolve().parent.parent


@dataclass(frozen=True, kw_only=True)
class Config:
    root: Path
    workspaces_dir: Path
    prompts_dir: Path

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
    # Per-call Anthropic SDK timeout. Default ample for the plan agent's
    # multi-thousand-token response; the runtime's faster chat calls also use this.

    admin_token: str | None
    # When set, server-side /admin/* endpoints become accessible (with
    # Authorization: Bearer <token>). When unset, admin endpoints return 503.

    cors_origins: list[str]
    # Allowed origins for CORS. ["*"] in dev; comma-list in production.
    # Empty list = no CORS headers sent (cross-origin requests will fail).

    pipeline_timeout_s: int
    # Global wall-clock budget for one Pipeline.run() invocation. After this,
    # the orchestrator halts cleanly with whatever it has.

    workspace_size_warn_mb: int
    # Soft warning threshold for per-customer workspace size. Surfaced via
    # admin diagnose, NOT a hard enforcement.

    alert_webhook: str | None
    # When set, the alerting layer POSTs JSON to this URL on important events
    # (tooling-failure halt, pipeline timeout, etc.). Operator-supplied.

    onboard_rate_per_hour: int
    chat_rate_per_minute: int
    monitor_login_rate_per_minute: int
    rate_limit_backend: str = "sqlite-local"
    onboarding_repeat_fingerprint_per_day: int = 2
    onboarding_contact_rate_per_day: int = 3
    onboarding_ip_rate_per_day: int = 20
    onboarding_block_disposable_email: bool = True
    onboarding_honeypot_enabled: bool = True
    # Per-IP rate limit for /onboard; per-token rate limit for /chat.

    token_ttl_days: int
    # Default TTL for newly-minted runtime tokens. 0 = never expires (legacy).

    max_body_bytes: int
    # Hard upper bound on HTTP request body size. Returns 413 above this.

    voice_backend: str  # generic catch-all kept for back-compat; see asr_backend

    asr_backend: str
    # "mlx" | "api" | "none". Default is local mlx-whisper for privacy-first
    # voice intake on Apple Silicon. "api" uses OpenAI Whisper API (cloud).

    asr_model: str
    # Model identifier for the chosen ASR backend.
    # API default: "whisper-1". MLX default: "mlx-community/whisper-large-v3-turbo".

    # Coding ↔ validation iteration: temperature annealing + bridge orchestrator.
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
    slm_advisory_enabled: bool = False
    local_llm_backend: str = "none"
    pipeline_local_llm_enabled: bool = False
    slm_advisory_min_confidence: float = 0.6
    slm_advisory_timeout_s: float = 5.0
    asr_delete_audio_after_transcribe: bool = True
    voice_capture_duration_s: float = 15.0
    voice_capture_sample_rate: int = 16000
    tts_backend: str = "none"
    serve_host: str = "127.0.0.1"
    serve_port: int = 8000
    monitor_public_base_url: str | None = None
    monitor_exposure: str = "local-only"
    remote_access_channel: str = "none"
    allow_lan_monitor_fallback: bool = False
    allow_monitor_query_token_fallback: bool = False
    maintenance_access_channel: str = "ssh-vpn"
    filevault_confirmed: bool = False
    local_workspace_confirmed: bool = False
    no_synced_folders_confirmed: bool = False
    backup_restore_drill_confirmed: bool = False
    launch_acceptance_confirmed: bool = False
    workflow_check_interval_minutes: int = 60
    monthly_api_budget_jpy: int = 30000
    usd_to_jpy_rate: float = 150.0
    workflow_circuit_breaker_enabled: bool = False
    workflow_circuit_breaker_consecutive_failures: int = 3
    workflow_circuit_breaker_failures_in_window: int = 5
    workflow_circuit_breaker_window_minutes: int = 30
    slm_auto_train_enabled: bool = False
    slm_auto_promote_enabled: bool = False
    slm_training_export_allow_raw_logs: bool = False
    slm_training_export_allow_hidden_reasoning: bool = False
    secret_storage_mode: str = "local_env"
    secret_storage_keychain_service: str = "com.smbagent.integrations"
    backup_encryption_mode: str = "none"
    backup_encryption_passphrase_env: str = "SMBAGENT_BACKUP_PASSPHRASE"
    voice_cloud_redaction_enabled: bool = True
    voice_cloud_minimization_mode: str = "balanced"
    consent_record_required: bool = True
    slm_completion_enabled: bool = False
    slm_completion_backend: str = "sglang"
    slm_completion_allowed_stages: tuple[str, ...] = (
        "preplan",
        "employee_route",
        "context_refresh",
        "loop_advice",
    )
    # Soft warning threshold for stale company context. Surfaced via status,
    # portal/dashboard, and admin diagnose; NOT a hard enforcement.

    @property
    def paths(self) -> PathConfig:
        return PathConfig(root=self.root, workspaces_dir=self.workspaces_dir, prompts_dir=self.prompts_dir)

    @property
    def pipeline(self) -> PipelineConfig:
        return PipelineConfig(
            anthropic_api_key=self.anthropic_api_key,
            openai_api_key=self.openai_api_key,
            plan_model=self.plan_model,
            coding_cmd=self.coding_cmd,
            validation_backend=self.validation_backend,
            validation_cmd=self.validation_cmd,
            validation_model=self.validation_model,
            harness_profile=self.harness_profile,
            subprocess_isolation=self.subprocess_isolation,
            subprocess_read_paths=self.subprocess_read_paths,
            apple_container_coding_image=self.apple_container_coding_image,
            apple_container_validation_image=self.apple_container_validation_image,
            apple_container_home_mounts=self.apple_container_home_mounts,
            max_rounds=self.max_rounds,
            coding_timeout_s=self.coding_timeout_s,
            validation_timeout_s=self.validation_timeout_s,
            anthropic_timeout_s=self.anthropic_timeout_s,
            pipeline_timeout_s=self.pipeline_timeout_s,
            workspace_size_warn_mb=self.workspace_size_warn_mb,
            anneal_temp_creative=self.anneal_temp_creative,
            anneal_temp_convergence=self.anneal_temp_convergence,
            anneal_temp_final=self.anneal_temp_final,
            anneal_stale_rounds=self.anneal_stale_rounds,
            bridge_orchestrator_enabled=self.bridge_orchestrator_enabled,
            bridge_orchestrator_model=self.bridge_orchestrator_model,
            bridge_orchestrator_max_tokens=self.bridge_orchestrator_max_tokens,
            bridge_orchestrator_temperature=self.bridge_orchestrator_temperature,
            humanize_enabled=self.humanize_enabled,
            max_humanize_rounds=self.max_humanize_rounds,
            adaptive_loop_enabled=self.adaptive_loop_enabled,
            adaptive_min_rounds=self.adaptive_min_rounds,
            adaptive_max_rounds=self.adaptive_max_rounds,
        )

    @property
    def runtime(self) -> RuntimeServeConfig:
        return RuntimeServeConfig(
            admin_token=self.admin_token,
            cors_origins=self.cors_origins,
            alert_webhook=self.alert_webhook,
            onboard_rate_per_hour=self.onboard_rate_per_hour,
            chat_rate_per_minute=self.chat_rate_per_minute,
            monitor_login_rate_per_minute=self.monitor_login_rate_per_minute,
            rate_limit_backend=self.rate_limit_backend,
            onboarding_repeat_fingerprint_per_day=self.onboarding_repeat_fingerprint_per_day,
            onboarding_contact_rate_per_day=self.onboarding_contact_rate_per_day,
            onboarding_ip_rate_per_day=self.onboarding_ip_rate_per_day,
            onboarding_block_disposable_email=self.onboarding_block_disposable_email,
            onboarding_honeypot_enabled=self.onboarding_honeypot_enabled,
            token_ttl_days=self.token_ttl_days,
            max_body_bytes=self.max_body_bytes,
            serve_host=self.serve_host,
            serve_port=self.serve_port,
            monitor_public_base_url=self.monitor_public_base_url,
            monitor_exposure=self.monitor_exposure,
            remote_access_channel=self.remote_access_channel,
            allow_lan_monitor_fallback=self.allow_lan_monitor_fallback,
            allow_monitor_query_token_fallback=self.allow_monitor_query_token_fallback,
            maintenance_access_channel=self.maintenance_access_channel,
            workflow_check_interval_minutes=self.workflow_check_interval_minutes,
            monthly_api_budget_jpy=self.monthly_api_budget_jpy,
            usd_to_jpy_rate=self.usd_to_jpy_rate,
            workflow_circuit_breaker_enabled=self.workflow_circuit_breaker_enabled,
            workflow_circuit_breaker_consecutive_failures=self.workflow_circuit_breaker_consecutive_failures,
            workflow_circuit_breaker_failures_in_window=self.workflow_circuit_breaker_failures_in_window,
            workflow_circuit_breaker_window_minutes=self.workflow_circuit_breaker_window_minutes,
        )

    @property
    def voice(self) -> VoiceConfig:
        return VoiceConfig(
            voice_backend=self.voice_backend,
            asr_backend=self.asr_backend,
            asr_model=self.asr_model,
            asr_delete_audio_after_transcribe=self.asr_delete_audio_after_transcribe,
            voice_capture_duration_s=self.voice_capture_duration_s,
            voice_capture_sample_rate=self.voice_capture_sample_rate,
            tts_backend=self.tts_backend,
            voice_cloud_redaction_enabled=self.voice_cloud_redaction_enabled,
            voice_cloud_minimization_mode=self.voice_cloud_minimization_mode,
            consent_record_required=self.consent_record_required,
        )

    @property
    def slm(self) -> SLMConfig:
        return SLMConfig(
            slm_advisory_enabled=self.slm_advisory_enabled,
            local_llm_backend=self.local_llm_backend,
            pipeline_local_llm_enabled=self.pipeline_local_llm_enabled,
            slm_advisory_min_confidence=self.slm_advisory_min_confidence,
            slm_advisory_timeout_s=self.slm_advisory_timeout_s,
            slm_auto_train_enabled=self.slm_auto_train_enabled,
            slm_auto_promote_enabled=self.slm_auto_promote_enabled,
            slm_training_export_allow_raw_logs=self.slm_training_export_allow_raw_logs,
            slm_training_export_allow_hidden_reasoning=self.slm_training_export_allow_hidden_reasoning,
            slm_completion_enabled=self.slm_completion_enabled,
            slm_completion_backend=self.slm_completion_backend,
            slm_completion_allowed_stages=self.slm_completion_allowed_stages,
        )

    @property
    def deployment(self) -> DeploymentAttestationConfig:
        return DeploymentAttestationConfig(
            filevault_confirmed=self.filevault_confirmed,
            local_workspace_confirmed=self.local_workspace_confirmed,
            no_synced_folders_confirmed=self.no_synced_folders_confirmed,
            backup_restore_drill_confirmed=self.backup_restore_drill_confirmed,
            launch_acceptance_confirmed=self.launch_acceptance_confirmed,
            secret_storage_mode=self.secret_storage_mode,
            secret_storage_keychain_service=self.secret_storage_keychain_service,
            backup_encryption_mode=self.backup_encryption_mode,
            backup_encryption_passphrase_env=self.backup_encryption_passphrase_env,
        )

    @property
    def governance(self) -> GovernanceConfig:
        return GovernanceConfig(
            trust_principle=self.trust_principle,
            external_execution_policy=self.external_execution_policy,
            allow_unattended_external_writes=self.allow_unattended_external_writes,
            context_refresh_warn_days=self.context_refresh_warn_days,
            data_retention_days=self.data_retention_days,
            runtime_log_retention_days=self.runtime_log_retention_days,
            failure_memory_retention_days=self.failure_memory_retention_days,
            transcript_retention_days=self.transcript_retention_days,
            allow_failure_memory_training_use=self.allow_failure_memory_training_use,
            sensitive_mode=self.sensitive_mode,
            local_only_mode=self.local_only_mode,
        )

    def view_paths(self) -> PathConfig:
        """Read-only path section view."""
        return self.paths

    def view_pipeline(self) -> PipelineConfig:
        """Read-only pipeline section view."""
        return self.pipeline

    def view_runtime(self) -> RuntimeServeConfig:
        """Read-only HTTP/runtime serve section view."""
        return self.runtime

    def view_voice(self) -> VoiceConfig:
        """Read-only voice section view."""
        return self.voice

    def view_slm(self) -> SLMConfig:
        """Read-only SLM section view."""
        return self.slm

    def view_deployment(self) -> DeploymentAttestationConfig:
        """Read-only deployment attestation section view."""
        return self.deployment

    def view_governance(self) -> GovernanceConfig:
        """Read-only governance section view."""
        return self.governance

    def requires_anthropic_api_key(self) -> bool:
        """Anthropic API access is required for the planning side of the pipeline."""
        return True

    def uses_validation_api(self) -> bool:
        return self.validation_backend.lower() == "api"

    def uses_validation_cli(self) -> bool:
        return self.validation_backend.lower() == "cli"

    def uses_openai_api(self) -> bool:
        return self.uses_validation_api() or self.asr_backend.lower() == "api"

    def requires_openai_api_key(self) -> bool:
        return self.uses_openai_api()

    def unattended_external_writes_allowed(self) -> bool:
        return self.allow_unattended_external_writes or self.external_execution_policy.lower() != "hitl"

    def uses_cloud_llm_backend(self) -> bool:
        return self.requires_anthropic_api_key() or self.uses_openai_api()

    def sensitive_voice_ok(self) -> bool:
        return self.asr_backend.lower() in {"mlx", "none"} and self.asr_delete_audio_after_transcribe


def load_config(root: Path | None = None) -> Config:
    root = (root or _default_root()).resolve()
    paths = load_path_config(root)
    pipeline = load_pipeline_config()
    runtime = load_runtime_config()
    voice = load_voice_config()
    slm = load_slm_config()
    deployment = load_deployment_config()
    governance = load_governance_config()
    return Config(
        **flatten_config_sections(
            paths=paths,
            pipeline=pipeline,
            runtime=runtime,
            voice=voice,
            slm=slm,
            deployment=deployment,
            governance=governance,
        )
    )
