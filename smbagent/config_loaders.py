from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path

from .config_sections import (
    DeploymentAttestationConfig,
    GovernanceConfig,
    PathConfig,
    PipelineConfig,
    RuntimeServeConfig,
    SLMConfig,
    VoiceConfig,
)


def _split(cmd: str) -> list[str]:
    import shlex

    return shlex.split(cmd)


def _env_bool(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).lower() in ("1", "true", "yes")


def load_path_config(root: Path) -> PathConfig:
    return PathConfig(
        root=root,
        workspaces_dir=root / "workspaces",
        prompts_dir=Path(__file__).resolve().parent / "prompts",
    )


def load_pipeline_config() -> PipelineConfig:
    return PipelineConfig(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        plan_model=os.environ.get("SMBAGENT_PLAN_MODEL", "claude-opus-4-7"),
        coding_cmd=_split(
            os.environ.get(
                "SMBAGENT_CODING_CMD",
                "claude -p --model opus --permission-mode acceptEdits",
            )
        ),
        validation_backend=os.environ.get("SMBAGENT_VALIDATION_BACKEND", "cli").lower(),
        validation_cmd=_split(
            os.environ.get(
                "SMBAGENT_VALIDATION_CMD",
                "codex exec --skip-git-repo-check",
            )
        ),
        validation_model=os.environ.get("SMBAGENT_VALIDATION_MODEL", "gpt-5"),
        harness_profile=os.environ.get("SMBAGENT_HARNESS_PROFILE", "opus-default"),
        subprocess_isolation=os.environ.get("SMBAGENT_SUBPROCESS_ISOLATION", "none").lower(),
        subprocess_read_paths=[
            p.strip() for p in os.environ.get("SMBAGENT_SUBPROCESS_READ_PATHS", "").split(",") if p.strip()
        ],
        apple_container_coding_image=os.environ.get(
            "SMBAGENT_APPLE_CONTAINER_CODING_IMAGE",
            "smbagent/claude-code:latest",
        ),
        apple_container_validation_image=os.environ.get(
            "SMBAGENT_APPLE_CONTAINER_VALIDATION_IMAGE",
            "smbagent/codex-validation:latest",
        ),
        apple_container_home_mounts=_env_bool("SMBAGENT_APPLE_CONTAINER_HOME_MOUNTS", "true"),
        max_rounds=int(os.environ.get("SMBAGENT_MAX_ROUNDS", "20")),
        coding_timeout_s=int(os.environ.get("SMBAGENT_CODING_TIMEOUT_S", "1800")),
        validation_timeout_s=int(os.environ.get("SMBAGENT_VALIDATION_TIMEOUT_S", "900")),
        anthropic_timeout_s=float(os.environ.get("SMBAGENT_ANTHROPIC_TIMEOUT_S", "300")),
        pipeline_timeout_s=int(os.environ.get("SMBAGENT_PIPELINE_TIMEOUT_S", str(4 * 3600))),
        workspace_size_warn_mb=int(os.environ.get("SMBAGENT_WORKSPACE_SIZE_WARN_MB", "500")),
        anneal_temp_creative=float(os.environ.get("SMBAGENT_ANNEAL_TEMP_CREATIVE", "0.7")),
        anneal_temp_convergence=float(os.environ.get("SMBAGENT_ANNEAL_TEMP_CONVERGENCE", "0.3")),
        anneal_temp_final=float(os.environ.get("SMBAGENT_ANNEAL_TEMP_FINAL", "0.0")),
        anneal_stale_rounds=int(os.environ.get("SMBAGENT_ANNEAL_STALE_ROUNDS", "2")),
        bridge_orchestrator_enabled=_env_bool("SMBAGENT_BRIDGE_ORCHESTRATOR", "true"),
        bridge_orchestrator_model=os.environ.get("SMBAGENT_BRIDGE_ORCHESTRATOR_MODEL", "")
        or os.environ.get("SMBAGENT_PLAN_MODEL", "claude-opus-4-7"),
        bridge_orchestrator_max_tokens=int(os.environ.get("SMBAGENT_BRIDGE_ORCHESTRATOR_MAX_TOKENS", "512")),
        bridge_orchestrator_temperature=float(
            os.environ.get("SMBAGENT_BRIDGE_ORCHESTRATOR_TEMPERATURE", "0.0")
        ),
        humanize_enabled=_env_bool("SMBAGENT_HUMANIZE_ENABLED", "true"),
        max_humanize_rounds=int(os.environ.get("SMBAGENT_MAX_HUMANIZE_ROUNDS", "3")),
        adaptive_loop_enabled=_env_bool("SMBAGENT_ADAPTIVE_LOOP_ENABLED", "true"),
        adaptive_min_rounds=int(os.environ.get("SMBAGENT_ADAPTIVE_MIN_ROUNDS", "2")),
        adaptive_max_rounds=int(
            os.environ.get("SMBAGENT_ADAPTIVE_MAX_ROUNDS", os.environ.get("SMBAGENT_MAX_ROUNDS", "20"))
        ),
    )


def load_runtime_config() -> RuntimeServeConfig:
    return RuntimeServeConfig(
        admin_token=os.environ.get("SMBAGENT_ADMIN_TOKEN") or None,
        cors_origins=[o.strip() for o in os.environ.get("SMBAGENT_CORS_ORIGINS", "").split(",") if o.strip()],
        alert_webhook=os.environ.get("SMBAGENT_ALERT_WEBHOOK") or None,
        onboard_rate_per_hour=int(os.environ.get("SMBAGENT_ONBOARD_RATE_PER_HOUR", "10")),
        chat_rate_per_minute=int(os.environ.get("SMBAGENT_CHAT_RATE_PER_MINUTE", "60")),
        monitor_login_rate_per_minute=int(os.environ.get("SMBAGENT_MONITOR_LOGIN_RATE_PER_MINUTE", "5")),
        rate_limit_backend=os.environ.get("SMBAGENT_RATE_LIMIT_BACKEND", "sqlite-local").lower(),
        onboarding_repeat_fingerprint_per_day=int(
            os.environ.get("SMBAGENT_ONBOARDING_REPEAT_FINGERPRINT_PER_DAY", "2")
        ),
        onboarding_contact_rate_per_day=int(os.environ.get("SMBAGENT_ONBOARDING_CONTACT_RATE_PER_DAY", "3")),
        onboarding_ip_rate_per_day=int(os.environ.get("SMBAGENT_ONBOARDING_IP_RATE_PER_DAY", "20")),
        onboarding_block_disposable_email=_env_bool("SMBAGENT_ONBOARDING_BLOCK_DISPOSABLE_EMAIL", "true"),
        onboarding_honeypot_enabled=_env_bool("SMBAGENT_ONBOARDING_HONEYPOT_ENABLED", "true"),
        token_ttl_days=int(os.environ.get("SMBAGENT_TOKEN_TTL_DAYS", "365")),
        max_body_bytes=int(os.environ.get("SMBAGENT_MAX_BODY_BYTES", str(1024 * 1024))),
        serve_host=os.environ.get("SMBAGENT_SERVE_HOST", "127.0.0.1"),
        serve_port=int(os.environ.get("SMBAGENT_SERVE_PORT", "8000")),
        monitor_public_base_url=os.environ.get("SMBAGENT_MONITOR_PUBLIC_BASE_URL") or None,
        monitor_exposure=os.environ.get("SMBAGENT_MONITOR_EXPOSURE", "local-only").lower(),
        remote_access_channel=os.environ.get("SMBAGENT_REMOTE_ACCESS_CHANNEL", "none").lower(),
        allow_lan_monitor_fallback=_env_bool("SMBAGENT_ALLOW_LAN_MONITOR_FALLBACK"),
        allow_monitor_query_token_fallback=_env_bool("SMBAGENT_ALLOW_MONITOR_QUERY_TOKEN_FALLBACK"),
        maintenance_access_channel=os.environ.get("SMBAGENT_MAINTENANCE_ACCESS_CHANNEL", "ssh-vpn").lower(),
        workflow_check_interval_minutes=int(os.environ.get("SMBAGENT_WORKFLOW_CHECK_INTERVAL_MINUTES", "60")),
        monthly_api_budget_jpy=int(os.environ.get("SMBAGENT_MONTHLY_API_BUDGET_JPY", "30000")),
        usd_to_jpy_rate=float(os.environ.get("SMBAGENT_USD_TO_JPY_RATE", "150")),
        workflow_circuit_breaker_enabled=_env_bool("SMBAGENT_WORKFLOW_CIRCUIT_BREAKER_ENABLED"),
        workflow_circuit_breaker_consecutive_failures=int(
            os.environ.get("SMBAGENT_WORKFLOW_CIRCUIT_BREAKER_CONSECUTIVE_FAILURES", "3")
        ),
        workflow_circuit_breaker_failures_in_window=int(
            os.environ.get("SMBAGENT_WORKFLOW_CIRCUIT_BREAKER_FAILURES_IN_WINDOW", "5")
        ),
        workflow_circuit_breaker_window_minutes=int(
            os.environ.get("SMBAGENT_WORKFLOW_CIRCUIT_BREAKER_WINDOW_MINUTES", "30")
        ),
    )


def load_voice_config() -> VoiceConfig:
    return VoiceConfig(
        voice_backend=os.environ.get("SMBAGENT_VOICE_BACKEND", "text"),
        asr_backend=os.environ.get("SMBAGENT_ASR_BACKEND", "mlx"),
        asr_model=os.environ.get("SMBAGENT_ASR_MODEL", ""),
        asr_delete_audio_after_transcribe=_env_bool("SMBAGENT_ASR_DELETE_AUDIO_AFTER_TRANSCRIBE", "true"),
        voice_capture_duration_s=float(os.environ.get("SMBAGENT_VOICE_CAPTURE_DURATION_S", "15")),
        voice_capture_sample_rate=int(os.environ.get("SMBAGENT_VOICE_CAPTURE_SAMPLE_RATE", "16000")),
        tts_backend=os.environ.get("SMBAGENT_TTS_BACKEND", "none"),
        voice_cloud_redaction_enabled=_env_bool("SMBAGENT_VOICE_CLOUD_REDACTION_ENABLED", "true"),
        voice_cloud_minimization_mode=os.environ.get(
            "SMBAGENT_VOICE_CLOUD_MINIMIZATION_MODE",
            "balanced",
        ).lower(),
        consent_record_required=_env_bool("SMBAGENT_CONSENT_RECORD_REQUIRED", "true"),
    )


def load_slm_config() -> SLMConfig:
    return SLMConfig(
        slm_advisory_enabled=_env_bool("SMBAGENT_ENABLE_SLM_ADVISORY"),
        local_llm_backend=os.environ.get("SMBAGENT_LOCAL_LLM_BACKEND", "none"),
        pipeline_local_llm_enabled=_env_bool("SMBAGENT_PIPELINE_LOCAL_LLM_ENABLED"),
        slm_advisory_min_confidence=float(os.environ.get("SMBAGENT_SLM_ADVISORY_MIN_CONFIDENCE", "0.6")),
        slm_advisory_timeout_s=float(os.environ.get("SMBAGENT_LOCAL_SLM_TIMEOUT_S", "5.0")),
        slm_auto_train_enabled=_env_bool("SMBAGENT_SLM_AUTO_TRAIN_ENABLED"),
        slm_auto_promote_enabled=_env_bool("SMBAGENT_SLM_AUTO_PROMOTE_ENABLED"),
        slm_training_export_allow_raw_logs=_env_bool("SMBAGENT_SLM_ALLOW_RAW_TRAINING_EXPORT"),
        slm_training_export_allow_hidden_reasoning=_env_bool(
            "SMBAGENT_SLM_ALLOW_HIDDEN_REASONING_TRAINING_EXPORT"
        ),
        slm_completion_enabled=_env_bool("SMBAGENT_SLM_COMPLETION_ENABLED"),
        slm_completion_backend=os.environ.get("SMBAGENT_SLM_COMPLETION_BACKEND", "sglang").lower(),
        slm_completion_allowed_stages=tuple(
            stage.strip()
            for stage in os.environ.get(
                "SMBAGENT_SLM_COMPLETION_ALLOWED_STAGES",
                "preplan,employee_route,context_refresh,loop_advice",
            ).split(",")
            if stage.strip()
        ),
    )


def load_deployment_config() -> DeploymentAttestationConfig:
    return DeploymentAttestationConfig(
        filevault_confirmed=_env_bool("SMBAGENT_FILEVAULT_CONFIRMED"),
        local_workspace_confirmed=_env_bool("SMBAGENT_LOCAL_WORKSPACE_CONFIRMED"),
        no_synced_folders_confirmed=_env_bool("SMBAGENT_NO_SYNCED_FOLDERS_CONFIRMED"),
        backup_restore_drill_confirmed=_env_bool("SMBAGENT_BACKUP_RESTORE_DRILL_CONFIRMED"),
        launch_acceptance_confirmed=_env_bool("SMBAGENT_LAUNCH_ACCEPTANCE_CONFIRMED"),
        secret_storage_mode=os.environ.get("SMBAGENT_SECRET_STORAGE_MODE", "local_env").lower(),
        secret_storage_keychain_service=os.environ.get(
            "SMBAGENT_SECRET_STORAGE_KEYCHAIN_SERVICE",
            "com.smbagent.integrations",
        ),
        backup_encryption_mode=os.environ.get("SMBAGENT_BACKUP_ENCRYPTION_MODE", "none").lower(),
        backup_encryption_passphrase_env=os.environ.get(
            "SMBAGENT_BACKUP_ENCRYPTION_PASSPHRASE_ENV",
            "SMBAGENT_BACKUP_PASSPHRASE",
        ),
    )


def load_governance_config() -> GovernanceConfig:
    return GovernanceConfig(
        context_refresh_warn_days=int(os.environ.get("SMBAGENT_CONTEXT_REFRESH_WARN_DAYS", "90")),
        data_retention_days=int(os.environ.get("SMBAGENT_DATA_RETENTION_DAYS", "180")),
        runtime_log_retention_days=int(os.environ.get("SMBAGENT_RUNTIME_LOG_RETENTION_DAYS", "90")),
        failure_memory_retention_days=int(os.environ.get("SMBAGENT_FAILURE_MEMORY_RETENTION_DAYS", "365")),
        transcript_retention_days=int(os.environ.get("SMBAGENT_TRANSCRIPT_RETENTION_DAYS", "30")),
        allow_failure_memory_training_use=_env_bool("SMBAGENT_ALLOW_FAILURE_MEMORY_TRAINING_USE"),
        sensitive_mode=_env_bool("SMBAGENT_SENSITIVE_MODE"),
        local_only_mode=_env_bool("SMBAGENT_LOCAL_ONLY_MODE"),
        trust_principle=os.environ.get("SMBAGENT_TRUST_PRINCIPLE", "trustable"),
        external_execution_policy=os.environ.get("SMBAGENT_EXTERNAL_EXECUTION_POLICY", "hitl"),
        allow_unattended_external_writes=_env_bool("SMBAGENT_ALLOW_UNATTENDED_EXTERNAL_WRITES"),
    )


def flatten_config_sections(
    *,
    paths: PathConfig,
    pipeline: PipelineConfig,
    runtime: RuntimeServeConfig,
    voice: VoiceConfig,
    slm: SLMConfig,
    deployment: DeploymentAttestationConfig,
    governance: GovernanceConfig,
) -> dict[str, object]:
    merged: dict[str, object] = {}
    for section in (paths, pipeline, runtime, voice, slm, deployment, governance):
        merged.update(asdict(section))
    return merged
