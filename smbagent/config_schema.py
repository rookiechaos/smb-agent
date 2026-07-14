from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ConfigEnvVar:
    name: str
    section: str
    field: str
    default: str | None
    secret: bool = False
    description: str = ""


_CONFIG_ENV_VARS: tuple[ConfigEnvVar, ...] = (
    ConfigEnvVar(
        "ANTHROPIC_API_KEY",
        "pipeline",
        "anthropic_api_key",
        None,
        secret=True,
        description="Anthropic API key for Qualify/Negotiate/Plan",
    ),
    ConfigEnvVar(
        "OPENAI_API_KEY",
        "pipeline",
        "openai_api_key",
        None,
        secret=True,
        description="OpenAI API key when validation or ASR uses API backend",
    ),
    ConfigEnvVar("SMBAGENT_PLAN_MODEL", "pipeline", "plan_model", "claude-opus-4-7"),
    ConfigEnvVar(
        "SMBAGENT_CODING_CMD",
        "pipeline",
        "coding_cmd",
        "claude -p --model opus --permission-mode acceptEdits",
    ),
    ConfigEnvVar("SMBAGENT_VALIDATION_BACKEND", "pipeline", "validation_backend", "cli"),
    ConfigEnvVar("SMBAGENT_VALIDATION_CMD", "pipeline", "validation_cmd", "codex exec --skip-git-repo-check"),
    ConfigEnvVar("SMBAGENT_VALIDATION_MODEL", "pipeline", "validation_model", "gpt-5"),
    ConfigEnvVar("SMBAGENT_HARNESS_PROFILE", "pipeline", "harness_profile", "opus-default"),
    ConfigEnvVar("SMBAGENT_SUBPROCESS_ISOLATION", "pipeline", "subprocess_isolation", "none"),
    ConfigEnvVar("SMBAGENT_SUBPROCESS_READ_PATHS", "pipeline", "subprocess_read_paths", ""),
    ConfigEnvVar(
        "SMBAGENT_APPLE_CONTAINER_CODING_IMAGE",
        "pipeline",
        "apple_container_coding_image",
        "smbagent/claude-code:latest",
    ),
    ConfigEnvVar(
        "SMBAGENT_APPLE_CONTAINER_VALIDATION_IMAGE",
        "pipeline",
        "apple_container_validation_image",
        "smbagent/codex-validation:latest",
    ),
    ConfigEnvVar("SMBAGENT_APPLE_CONTAINER_HOME_MOUNTS", "pipeline", "apple_container_home_mounts", "true"),
    ConfigEnvVar("SMBAGENT_MAX_ROUNDS", "pipeline", "max_rounds", "20"),
    ConfigEnvVar("SMBAGENT_CODING_TIMEOUT_S", "pipeline", "coding_timeout_s", "1800"),
    ConfigEnvVar("SMBAGENT_VALIDATION_TIMEOUT_S", "pipeline", "validation_timeout_s", "900"),
    ConfigEnvVar("SMBAGENT_ANTHROPIC_TIMEOUT_S", "pipeline", "anthropic_timeout_s", "300"),
    ConfigEnvVar("SMBAGENT_PIPELINE_TIMEOUT_S", "pipeline", "pipeline_timeout_s", "14400"),
    ConfigEnvVar("SMBAGENT_WORKSPACE_SIZE_WARN_MB", "pipeline", "workspace_size_warn_mb", "500"),
    ConfigEnvVar("SMBAGENT_ANNEAL_TEMP_CREATIVE", "pipeline", "anneal_temp_creative", "0.7"),
    ConfigEnvVar("SMBAGENT_ANNEAL_TEMP_CONVERGENCE", "pipeline", "anneal_temp_convergence", "0.3"),
    ConfigEnvVar("SMBAGENT_ANNEAL_TEMP_FINAL", "pipeline", "anneal_temp_final", "0.0"),
    ConfigEnvVar("SMBAGENT_ANNEAL_STALE_ROUNDS", "pipeline", "anneal_stale_rounds", "2"),
    ConfigEnvVar("SMBAGENT_BRIDGE_ORCHESTRATOR", "pipeline", "bridge_orchestrator_enabled", "true"),
    ConfigEnvVar(
        "SMBAGENT_BRIDGE_ORCHESTRATOR_MODEL", "pipeline", "bridge_orchestrator_model", "claude-opus-4-7"
    ),
    ConfigEnvVar(
        "SMBAGENT_BRIDGE_ORCHESTRATOR_MAX_TOKENS", "pipeline", "bridge_orchestrator_max_tokens", "512"
    ),
    ConfigEnvVar(
        "SMBAGENT_BRIDGE_ORCHESTRATOR_TEMPERATURE", "pipeline", "bridge_orchestrator_temperature", "0.0"
    ),
    ConfigEnvVar("SMBAGENT_HUMANIZE_ENABLED", "pipeline", "humanize_enabled", "true"),
    ConfigEnvVar("SMBAGENT_MAX_HUMANIZE_ROUNDS", "pipeline", "max_humanize_rounds", "3"),
    ConfigEnvVar("SMBAGENT_ADAPTIVE_LOOP_ENABLED", "pipeline", "adaptive_loop_enabled", "true"),
    ConfigEnvVar("SMBAGENT_ADAPTIVE_MIN_ROUNDS", "pipeline", "adaptive_min_rounds", "2"),
    ConfigEnvVar("SMBAGENT_ADAPTIVE_MAX_ROUNDS", "pipeline", "adaptive_max_rounds", "20"),
    ConfigEnvVar("SMBAGENT_ADMIN_TOKEN", "runtime", "admin_token", None, secret=True),
    ConfigEnvVar("SMBAGENT_CORS_ORIGINS", "runtime", "cors_origins", ""),
    ConfigEnvVar("SMBAGENT_ALERT_WEBHOOK", "runtime", "alert_webhook", None),
    ConfigEnvVar("SMBAGENT_ONBOARD_RATE_PER_HOUR", "runtime", "onboard_rate_per_hour", "10"),
    ConfigEnvVar("SMBAGENT_CHAT_RATE_PER_MINUTE", "runtime", "chat_rate_per_minute", "60"),
    ConfigEnvVar("SMBAGENT_MONITOR_LOGIN_RATE_PER_MINUTE", "runtime", "monitor_login_rate_per_minute", "5"),
    ConfigEnvVar("SMBAGENT_RATE_LIMIT_BACKEND", "runtime", "rate_limit_backend", "sqlite-local"),
    ConfigEnvVar(
        "SMBAGENT_ONBOARDING_REPEAT_FINGERPRINT_PER_DAY",
        "runtime",
        "onboarding_repeat_fingerprint_per_day",
        "2",
    ),
    ConfigEnvVar(
        "SMBAGENT_ONBOARDING_CONTACT_RATE_PER_DAY", "runtime", "onboarding_contact_rate_per_day", "3"
    ),
    ConfigEnvVar("SMBAGENT_ONBOARDING_IP_RATE_PER_DAY", "runtime", "onboarding_ip_rate_per_day", "20"),
    ConfigEnvVar(
        "SMBAGENT_ONBOARDING_BLOCK_DISPOSABLE_EMAIL", "runtime", "onboarding_block_disposable_email", "true"
    ),
    ConfigEnvVar("SMBAGENT_ONBOARDING_HONEYPOT_ENABLED", "runtime", "onboarding_honeypot_enabled", "true"),
    ConfigEnvVar("SMBAGENT_TOKEN_TTL_DAYS", "runtime", "token_ttl_days", "365"),
    ConfigEnvVar("SMBAGENT_MAX_BODY_BYTES", "runtime", "max_body_bytes", "1048576"),
    ConfigEnvVar(
        "SMBAGENT_SERVE_HOST",
        "runtime",
        "serve_host",
        "127.0.0.1",
        description="Default localhost bind; no outside port unless explicitly overridden",
    ),
    ConfigEnvVar("SMBAGENT_SERVE_PORT", "runtime", "serve_port", "8000"),
    ConfigEnvVar("SMBAGENT_MONITOR_PUBLIC_BASE_URL", "runtime", "monitor_public_base_url", None),
    ConfigEnvVar("SMBAGENT_MONITOR_EXPOSURE", "runtime", "monitor_exposure", "local-only"),
    ConfigEnvVar("SMBAGENT_REMOTE_ACCESS_CHANNEL", "runtime", "remote_access_channel", "none"),
    ConfigEnvVar("SMBAGENT_ALLOW_LAN_MONITOR_FALLBACK", "runtime", "allow_lan_monitor_fallback", "false"),
    ConfigEnvVar(
        "SMBAGENT_ALLOW_MONITOR_QUERY_TOKEN_FALLBACK",
        "runtime",
        "allow_monitor_query_token_fallback",
        "false",
    ),
    ConfigEnvVar("SMBAGENT_MAINTENANCE_ACCESS_CHANNEL", "runtime", "maintenance_access_channel", "ssh-vpn"),
    ConfigEnvVar(
        "SMBAGENT_WORKFLOW_CHECK_INTERVAL_MINUTES", "runtime", "workflow_check_interval_minutes", "60"
    ),
    ConfigEnvVar("SMBAGENT_MONTHLY_API_BUDGET_JPY", "runtime", "monthly_api_budget_jpy", "30000"),
    ConfigEnvVar("SMBAGENT_USD_TO_JPY_RATE", "runtime", "usd_to_jpy_rate", "150"),
    ConfigEnvVar(
        "SMBAGENT_WORKFLOW_CIRCUIT_BREAKER_ENABLED", "runtime", "workflow_circuit_breaker_enabled", "false"
    ),
    ConfigEnvVar(
        "SMBAGENT_WORKFLOW_CIRCUIT_BREAKER_CONSECUTIVE_FAILURES",
        "runtime",
        "workflow_circuit_breaker_consecutive_failures",
        "3",
    ),
    ConfigEnvVar(
        "SMBAGENT_WORKFLOW_CIRCUIT_BREAKER_FAILURES_IN_WINDOW",
        "runtime",
        "workflow_circuit_breaker_failures_in_window",
        "5",
    ),
    ConfigEnvVar(
        "SMBAGENT_WORKFLOW_CIRCUIT_BREAKER_WINDOW_MINUTES",
        "runtime",
        "workflow_circuit_breaker_window_minutes",
        "30",
    ),
    ConfigEnvVar("SMBAGENT_VOICE_BACKEND", "voice", "voice_backend", "text"),
    ConfigEnvVar("SMBAGENT_ASR_BACKEND", "voice", "asr_backend", "mlx"),
    ConfigEnvVar("SMBAGENT_ASR_MODEL", "voice", "asr_model", ""),
    ConfigEnvVar(
        "SMBAGENT_ASR_DELETE_AUDIO_AFTER_TRANSCRIBE", "voice", "asr_delete_audio_after_transcribe", "true"
    ),
    ConfigEnvVar("SMBAGENT_VOICE_CAPTURE_DURATION_S", "voice", "voice_capture_duration_s", "15"),
    ConfigEnvVar("SMBAGENT_VOICE_CAPTURE_SAMPLE_RATE", "voice", "voice_capture_sample_rate", "16000"),
    ConfigEnvVar("SMBAGENT_TTS_BACKEND", "voice", "tts_backend", "none"),
    ConfigEnvVar("SMBAGENT_VOICE_CLOUD_REDACTION_ENABLED", "voice", "voice_cloud_redaction_enabled", "true"),
    ConfigEnvVar(
        "SMBAGENT_VOICE_CLOUD_MINIMIZATION_MODE", "voice", "voice_cloud_minimization_mode", "balanced"
    ),
    ConfigEnvVar("SMBAGENT_CONSENT_RECORD_REQUIRED", "voice", "consent_record_required", "true"),
    ConfigEnvVar("SMBAGENT_ENABLE_SLM_ADVISORY", "slm", "slm_advisory_enabled", "false"),
    ConfigEnvVar("SMBAGENT_LOCAL_LLM_BACKEND", "slm", "local_llm_backend", "none"),
    ConfigEnvVar("SMBAGENT_PIPELINE_LOCAL_LLM_ENABLED", "slm", "pipeline_local_llm_enabled", "false"),
    ConfigEnvVar("SMBAGENT_SLM_ADVISORY_MIN_CONFIDENCE", "slm", "slm_advisory_min_confidence", "0.6"),
    ConfigEnvVar("SMBAGENT_LOCAL_SLM_TIMEOUT_S", "slm", "slm_advisory_timeout_s", "5.0"),
    ConfigEnvVar("SMBAGENT_SLM_AUTO_TRAIN_ENABLED", "slm", "slm_auto_train_enabled", "false"),
    ConfigEnvVar("SMBAGENT_SLM_AUTO_PROMOTE_ENABLED", "slm", "slm_auto_promote_enabled", "false"),
    ConfigEnvVar(
        "SMBAGENT_SLM_ALLOW_RAW_TRAINING_EXPORT", "slm", "slm_training_export_allow_raw_logs", "false"
    ),
    ConfigEnvVar(
        "SMBAGENT_SLM_ALLOW_HIDDEN_REASONING_TRAINING_EXPORT",
        "slm",
        "slm_training_export_allow_hidden_reasoning",
        "false",
    ),
    ConfigEnvVar("SMBAGENT_SLM_COMPLETION_ENABLED", "slm", "slm_completion_enabled", "false"),
    ConfigEnvVar("SMBAGENT_SLM_COMPLETION_BACKEND", "slm", "slm_completion_backend", "sglang"),
    ConfigEnvVar(
        "SMBAGENT_SLM_COMPLETION_ALLOWED_STAGES",
        "slm",
        "slm_completion_allowed_stages",
        "preplan,employee_route,context_refresh,loop_advice",
    ),
    ConfigEnvVar("SMBAGENT_FILEVAULT_CONFIRMED", "deployment", "filevault_confirmed", "false"),
    ConfigEnvVar("SMBAGENT_LOCAL_WORKSPACE_CONFIRMED", "deployment", "local_workspace_confirmed", "false"),
    ConfigEnvVar(
        "SMBAGENT_NO_SYNCED_FOLDERS_CONFIRMED", "deployment", "no_synced_folders_confirmed", "false"
    ),
    ConfigEnvVar(
        "SMBAGENT_BACKUP_RESTORE_DRILL_CONFIRMED", "deployment", "backup_restore_drill_confirmed", "false"
    ),
    ConfigEnvVar(
        "SMBAGENT_LAUNCH_ACCEPTANCE_CONFIRMED", "deployment", "launch_acceptance_confirmed", "false"
    ),
    ConfigEnvVar("SMBAGENT_SECRET_STORAGE_MODE", "deployment", "secret_storage_mode", "local_env"),
    ConfigEnvVar(
        "SMBAGENT_SECRET_STORAGE_KEYCHAIN_SERVICE",
        "deployment",
        "secret_storage_keychain_service",
        "com.smbagent.integrations",
    ),
    ConfigEnvVar("SMBAGENT_BACKUP_ENCRYPTION_MODE", "deployment", "backup_encryption_mode", "none"),
    ConfigEnvVar(
        "SMBAGENT_BACKUP_ENCRYPTION_PASSPHRASE_ENV",
        "deployment",
        "backup_encryption_passphrase_env",
        "SMBAGENT_BACKUP_PASSPHRASE",
    ),
    ConfigEnvVar("SMBAGENT_TRUST_PRINCIPLE", "governance", "trust_principle", "trustable"),
    ConfigEnvVar("SMBAGENT_EXTERNAL_EXECUTION_POLICY", "governance", "external_execution_policy", "hitl"),
    ConfigEnvVar(
        "SMBAGENT_ALLOW_UNATTENDED_EXTERNAL_WRITES", "governance", "allow_unattended_external_writes", "false"
    ),
    ConfigEnvVar("SMBAGENT_CONTEXT_REFRESH_WARN_DAYS", "governance", "context_refresh_warn_days", "90"),
    ConfigEnvVar("SMBAGENT_DATA_RETENTION_DAYS", "governance", "data_retention_days", "180"),
    ConfigEnvVar("SMBAGENT_RUNTIME_LOG_RETENTION_DAYS", "governance", "runtime_log_retention_days", "90"),
    ConfigEnvVar(
        "SMBAGENT_FAILURE_MEMORY_RETENTION_DAYS", "governance", "failure_memory_retention_days", "365"
    ),
    ConfigEnvVar("SMBAGENT_TRANSCRIPT_RETENTION_DAYS", "governance", "transcript_retention_days", "30"),
    ConfigEnvVar(
        "SMBAGENT_ALLOW_FAILURE_MEMORY_TRAINING_USE",
        "governance",
        "allow_failure_memory_training_use",
        "false",
    ),
    ConfigEnvVar("SMBAGENT_SENSITIVE_MODE", "governance", "sensitive_mode", "false"),
    ConfigEnvVar("SMBAGENT_LOCAL_ONLY_MODE", "governance", "local_only_mode", "false"),
)


def build_config_schema() -> dict[str, Any]:
    sections: dict[str, list[dict[str, Any]]] = {}
    for item in _CONFIG_ENV_VARS:
        sections.setdefault(item.section, []).append(
            {
                "env": item.name,
                "field": item.field,
                "default": item.default,
                "secret": item.secret,
                "description": item.description,
            }
        )
    return {
        "schema_version": 1,
        "sections": [{"name": name, "env_vars": rows} for name, rows in sections.items()],
        "env_var_count": len(_CONFIG_ENV_VARS),
    }


def render_config_schema_json() -> str:
    return json.dumps(build_config_schema(), ensure_ascii=False, indent=2)
