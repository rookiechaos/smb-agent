from __future__ import annotations

import json

from typer.testing import CliRunner

from smbagent.cli import app as cli_app
from smbagent.customer_readiness import write_customer_legal_review, write_japan_trust_launch_review
from smbagent.launch_readiness import (
    LaunchCheck,
    evaluate_launch_readiness,
    summarize_deployment_readiness,
    summarize_security_readiness,
    validate_monitor_start_posture,
)


def test_launch_readiness_marks_real_e2e_as_remote_only(config):
    checks = evaluate_launch_readiness(config)
    by_name = {c.name: c for c in checks}
    assert by_name["remote_real_api_e2e_smoke"].remote_only is True
    assert by_name["remote_real_api_e2e_smoke"].severity == "remote"


def test_launch_readiness_detects_plaintext_legacy_tokens(config):
    customer = config.workspaces_dir / "legacy-co"
    customer.mkdir(parents=True)
    (customer / "auth.json").write_text(
        json.dumps(
            {
                "customer_id": "legacy-co",
                "token": "plaintext",
                "created_at": "2026-01-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    checks = evaluate_launch_readiness(config)
    token_check = {c.name: c for c in checks}["no_plaintext_runtime_tokens"]
    assert token_check.passed is False
    assert "legacy-co/auth.json" in token_check.detail


def test_launch_readiness_accepts_hash_only_tokens(config):
    customer = config.workspaces_dir / "hash-co"
    customer.mkdir(parents=True)
    (customer / "auth.json").write_text(
        json.dumps(
            {
                "customer_id": "hash-co",
                "token_hash": "pbkdf2_sha256$1$c2FsdA==$ZGlnZXN0",
                "created_at": "2026-01-01T00:00:00Z",
                "revoked": False,
            }
        ),
        encoding="utf-8",
    )

    checks = evaluate_launch_readiness(config)
    token_check = {c.name: c for c in checks}["no_plaintext_runtime_tokens"]
    assert token_check.passed is True


def test_launch_readiness_requires_claude_opus_coding_alias(config):
    checks = evaluate_launch_readiness(config)
    coding_check = {c.name: c for c in checks}["coding_uses_claude_opus_alias"]
    assert coding_check.passed is True


def test_launch_readiness_checks_five_stage_agent_boundary_contract(config):
    checks = evaluate_launch_readiness(config)
    boundary_check = {c.name: c for c in checks}["five_stage_agent_boundary_contract"]
    assert boundary_check.passed is True
    assert boundary_check.severity == "critical"


def test_launch_readiness_flags_agent_runtime_isolation_when_subprocess_is_off(config):
    checks = evaluate_launch_readiness(config)
    isolation_check = {c.name: c for c in checks}["agent_runtime_isolation_posture"]
    assert isolation_check.passed is False
    assert "subprocess isolation" in isolation_check.detail


def test_launch_readiness_accepts_apple_official_container_runtime(config):
    cfg = type(config)(**{**config.__dict__, "subprocess_isolation": "apple-container"})
    checks = evaluate_launch_readiness(cfg)
    by_name = {c.name: c for c in checks}
    assert by_name["subprocess_isolation_enabled"].passed is True
    assert by_name["apple_official_container_runtime"].passed is True


def test_launch_readiness_keeps_slm_guardrails_fail_closed_by_default(config):
    checks = evaluate_launch_readiness(config)
    by_name = {c.name: c for c in checks}
    assert by_name["slm_auto_train_disabled"].passed is True
    assert by_name["slm_auto_promote_disabled"].passed is True
    assert by_name["slm_training_export_public_only"].passed is True
    assert by_name["slm_customer_policy_contract_present"].passed is True
    assert by_name["slm_runtime_acceptance_checklist"].passed is True
    assert by_name["slm_quality_gate_posture"].passed is True


def test_launch_readiness_requires_single_tenant_operator_attestations(config):
    checks = evaluate_launch_readiness(config)
    by_name = {c.name: c for c in checks}
    assert by_name["filevault_confirmed"].passed is False
    assert by_name["local_workspace_storage_confirmed"].passed is False
    assert by_name["no_synced_folders_confirmed"].passed is False
    assert by_name["backup_restore_drill_confirmed"].passed is False
    assert by_name["launch_acceptance_confirmed"].passed is False


def test_launch_readiness_accepts_operator_attestations(config):
    cfg = type(config)(
        **{
            **config.__dict__,
            "filevault_confirmed": True,
            "local_workspace_confirmed": True,
            "no_synced_folders_confirmed": True,
            "backup_restore_drill_confirmed": True,
            "launch_acceptance_confirmed": True,
        }
    )
    checks = evaluate_launch_readiness(cfg)
    by_name = {c.name: c for c in checks}
    assert by_name["filevault_confirmed"].passed is True
    assert by_name["local_workspace_storage_confirmed"].passed is True
    assert by_name["no_synced_folders_confirmed"].passed is True
    assert by_name["backup_restore_drill_confirmed"].passed is True
    assert by_name["launch_acceptance_confirmed"].passed is True


def test_launch_readiness_rejects_public_bind_when_monitor_is_local_only(config):
    cfg = type(config)(
        **{
            **config.__dict__,
            "serve_host": "0.0.0.0",
            "monitor_exposure": "local-only",
        }
    )
    checks = evaluate_launch_readiness(cfg)
    monitor_check = {c.name: c for c in checks}["monitor_exposure_posture"]
    assert monitor_check.passed is False
    assert monitor_check.severity == "critical"


def test_launch_readiness_rejects_wildcard_cors_on_public_bind(config):
    cfg = type(config)(
        **{
            **config.__dict__,
            "serve_host": "0.0.0.0",
            "cors_origins": ["*"],
        }
    )
    checks = evaluate_launch_readiness(cfg)
    cors_check = {c.name: c for c in checks}["cors_exposure_posture"]
    assert cors_check.passed is False
    assert cors_check.severity == "critical"


def test_launch_readiness_accepts_lan_only_monitor_posture(config):
    cfg = type(config)(
        **{
            **config.__dict__,
            "serve_host": "0.0.0.0",
            "monitor_exposure": "lan-only",
        }
    )
    checks = evaluate_launch_readiness(cfg)
    monitor_check = {c.name: c for c in checks}["monitor_exposure_posture"]
    assert monitor_check.passed is True


def test_launch_readiness_prefers_vpn_over_bare_lan(config):
    cfg = type(config)(
        **{
            **config.__dict__,
            "serve_host": "0.0.0.0",
            "monitor_exposure": "lan-only",
            "allow_lan_monitor_fallback": False,
        }
    )
    checks = evaluate_launch_readiness(cfg)
    vpn_check = {c.name: c for c in checks}["remote_access_vpn_posture"]
    assert vpn_check.passed is False
    assert vpn_check.severity == "major"


def test_launch_readiness_accepts_overlay_vpn_remote_access(config):
    cfg = type(config)(
        **{
            **config.__dict__,
            "serve_host": "0.0.0.0",
            "monitor_exposure": "public-approved",
            "monitor_public_base_url": "https://100.64.0.10:8000",
            "remote_access_channel": "tailscale",
            "maintenance_access_channel": "ssh-vpn",
        }
    )
    checks = evaluate_launch_readiness(cfg)
    by_name = {c.name: c for c in checks}
    assert by_name["remote_access_vpn_posture"].passed is True
    assert by_name["maintenance_access_posture"].passed is True


def test_launch_readiness_flags_non_vpn_remote_maintenance(config):
    cfg = type(config)(
        **{
            **config.__dict__,
            "maintenance_access_channel": "ssh-local-only",
        }
    )
    checks = evaluate_launch_readiness(cfg)
    maint_check = {c.name: c for c in checks}["maintenance_access_posture"]
    assert maint_check.passed is False
    assert maint_check.severity == "major"


def test_validate_monitor_start_blocks_non_local_bind_without_vpn(config):
    cfg = type(config)(
        **{
            **config.__dict__,
            "serve_host": "0.0.0.0",
            "monitor_exposure": "lan-only",
            "allow_lan_monitor_fallback": False,
        }
    )
    check = validate_monitor_start_posture(cfg, host="0.0.0.0")
    assert check.passed is False


def test_validate_monitor_start_accepts_tailscale_path(config):
    cfg = type(config)(
        **{
            **config.__dict__,
            "serve_host": "100.64.0.10",
            "monitor_exposure": "public-approved",
            "remote_access_channel": "tailscale",
            "maintenance_access_channel": "ssh-vpn",
            "monitor_public_base_url": "https://100.64.0.10:8000",
        }
    )
    check = validate_monitor_start_posture(cfg, host="100.64.0.10")
    assert check.passed is True


def test_launch_readiness_flags_monitor_query_token_fallback(config):
    cfg = type(config)(
        **{
            **config.__dict__,
            "allow_monitor_query_token_fallback": True,
        }
    )
    checks = evaluate_launch_readiness(cfg)
    token_check = {c.name: c for c in checks}["monitor_query_token_posture"]
    assert token_check.passed is False
    assert token_check.severity == "major"


def test_launch_readiness_flags_lan_monitor_fallback_enabled(config):
    cfg = type(config)(
        **{
            **config.__dict__,
            "allow_lan_monitor_fallback": True,
        }
    )
    checks = evaluate_launch_readiness(cfg)
    lan_check = {c.name: c for c in checks}["monitor_lan_fallback_posture"]
    assert lan_check.passed is False
    assert lan_check.severity == "major"


def test_launch_readiness_flags_non_https_monitor_base_url(config):
    cfg = type(config)(
        **{
            **config.__dict__,
            "monitor_public_base_url": "http://192.168.1.50:8000",
        }
    )
    checks = evaluate_launch_readiness(cfg)
    https_check = {c.name: c for c in checks}["monitor_base_url_https_posture"]
    assert https_check.passed is False
    assert https_check.severity == "major"


def test_launch_readiness_accepts_https_monitor_base_url(config):
    cfg = type(config)(
        **{
            **config.__dict__,
            "monitor_public_base_url": "https://100.64.0.10:8000",
        }
    )
    checks = evaluate_launch_readiness(cfg)
    https_check = {c.name: c for c in checks}["monitor_base_url_https_posture"]
    assert https_check.passed is True


def test_launch_readiness_detects_plaintext_employee_or_monitor_tokens(config):
    customer = config.workspaces_dir / "multi-lane-co"
    customer.mkdir(parents=True)
    for name in ("employee_auth.json", "monitor_auth.json"):
        (customer / name).write_text(
            json.dumps(
                {
                    "customer_id": "multi-lane-co",
                    "token": "plaintext",
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ),
            encoding="utf-8",
        )

    checks = evaluate_launch_readiness(config)
    token_check = {c.name: c for c in checks}["no_plaintext_runtime_tokens"]
    assert token_check.passed is False
    assert "employee_auth.json" in token_check.detail or "monitor_auth.json" in token_check.detail


def test_launch_readiness_detects_broad_auth_file_permissions(config):
    customer = config.workspaces_dir / "perm-co"
    customer.mkdir(parents=True)
    path = customer / "monitor_auth.json"
    path.write_text(
        json.dumps(
            {
                "customer_id": "perm-co",
                "token_hash": "pbkdf2_sha256$1$c2FsdA==$ZGlnZXN0",
                "created_at": "2026-01-01T00:00:00Z",
                "revoked": False,
            }
        ),
        encoding="utf-8",
    )
    path.chmod(0o644)

    checks = evaluate_launch_readiness(config)
    perm_check = {c.name: c for c in checks}["auth_file_permissions_strict"]
    assert perm_check.passed is False
    assert "monitor_auth.json" in perm_check.detail


def test_deployment_readiness_summary_contains_four_pillars(config):
    pillars = summarize_deployment_readiness(config)
    assert [pillar.key for pillar in pillars] == [
        "deployment_maturity",
        "local_privacy",
        "approval_governance",
        "recoverability",
    ]
    assert all(pillar.checks for pillar in pillars)


def test_security_readiness_summary_contains_four_domains(config):
    domains = summarize_security_readiness(config)
    assert [domain.key for domain in domains] == [
        "isolation_and_boundaries",
        "auth_and_token_storage",
        "local_privacy_and_data_minimization",
        "approval_and_recovery",
    ]
    assert all(domain.checks for domain in domains)


def test_launch_readiness_flags_old_claude_coding_cmd(config):
    old_cfg = type(config)(**{**config.__dict__, "coding_cmd": ["claude", "-p"]})
    checks = evaluate_launch_readiness(old_cfg)
    coding_check = {c.name: c for c in checks}["coding_uses_claude_opus_alias"]
    assert coding_check.passed is False
    assert coding_check.severity == "major"


def test_launch_readiness_flags_slm_guardrail_regressions(config):
    cfg = type(config)(
        **{
            **config.__dict__,
            "slm_auto_train_enabled": True,
            "slm_auto_promote_enabled": True,
            "slm_training_export_allow_raw_logs": True,
        }
    )
    checks = evaluate_launch_readiness(cfg)
    by_name = {c.name: c for c in checks}
    assert by_name["slm_auto_train_disabled"].passed is False
    assert by_name["slm_auto_promote_disabled"].passed is False
    assert by_name["slm_training_export_public_only"].passed is False
    assert by_name["slm_training_export_public_only"].severity == "critical"


def test_launch_readiness_requires_customer_policies_when_slm_enabled(config):
    cfg = type(config)(
        **{
            **config.__dict__,
            "slm_advisory_enabled": True,
            "local_llm_backend": "sglang",
        }
    )
    customer = cfg.workspaces_dir / "slm-enabled-co"
    customer.mkdir(parents=True)
    checks = evaluate_launch_readiness(cfg)
    by_name = {c.name: c for c in checks}
    assert by_name["slm_customer_policy_contract_present"].passed is False
    assert "slm_policy.json" in by_name["slm_customer_policy_contract_present"].detail


def test_launch_readiness_accepts_customer_policies_when_slm_enabled(config):
    cfg = type(config)(
        **{
            **config.__dict__,
            "slm_advisory_enabled": True,
            "local_llm_backend": "sglang",
        }
    )
    customer = cfg.workspaces_dir / "slm-allowed-co"
    customer.mkdir(parents=True)
    (customer / "slm_policy.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "customer_id": "slm-allowed-co",
                "mode": "advisory",
                "allowed_stages": ["runtime"],
                "blocked_workflow_families": ["payroll"],
                "notes": ["local advisory only"],
                "updated_by": "human:admin@example.com",
                "updated_at": "2026-06-11T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    checks = evaluate_launch_readiness(cfg)
    by_name = {c.name: c for c in checks}
    assert by_name["slm_customer_policy_contract_present"].passed is True


def test_launch_readiness_flags_failed_quality_gate_reports(config):
    reports_dir = config.root / "slm" / "registry" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "bad-r1.eval.json").write_text(
        json.dumps(
            {
                "candidate_version": "bad-r1",
                "compared_to_version": "prev-r0",
                "generated_at": "2026-06-11T00:00:00+00:00",
                "routing_accuracy": 0.62,
                "employee_routing_accuracy": 0.61,
                "loop_advice_usefulness": 0.40,
                "context_refresh_precision": 0.50,
                "false_confidence_rate": 0.22,
                "missed_escalation_rate": 0.21,
                "better_than_current": False,
                "summary": "regressed",
                "holdout_dataset_snapshot_id": "holdout-bad",
            }
        ),
        encoding="utf-8",
    )
    checks = evaluate_launch_readiness(config)
    by_name = {c.name: c for c in checks}
    assert by_name["slm_quality_gate_posture"].passed is False
    assert "bad-r1" in by_name["slm_quality_gate_posture"].detail


def test_launch_readiness_cli_fails_on_local_major_check(monkeypatch):
    monkeypatch.setattr(
        "smbagent.cli.evaluate_launch_readiness",
        lambda _cfg: [
            LaunchCheck(
                name="subprocess_isolation_enabled",
                passed=False,
                severity="major",
                detail="SMBAGENT_SUBPROCESS_ISOLATION=none",
            ),
            LaunchCheck(
                name="remote_real_api_e2e_smoke",
                passed=False,
                severity="remote",
                detail="deferred",
                remote_only=True,
            ),
        ],
    )
    result = CliRunner().invoke(cli_app, ["launch-readiness"])
    assert result.exit_code == 1
    assert "major/critical" in result.output


def test_launch_readiness_flags_missing_managed_secret_storage(config):
    checks = evaluate_launch_readiness(config)
    gate = {c.name: c for c in checks}["managed_secret_storage_posture"]
    assert gate.passed is False


def test_launch_readiness_accepts_sensitive_voice_hardening_bundle(config):
    cfg = type(config)(
        **{
            **config.__dict__,
            "sensitive_mode": True,
            "voice_cloud_redaction_enabled": True,
            "backup_encryption_mode": "openssl-aes256",
            "consent_record_required": True,
        }
    )
    checks = evaluate_launch_readiness(cfg)
    by_name = {c.name: c for c in checks}
    assert by_name["voice_cloud_redaction_posture"].passed is True
    assert by_name["encrypted_backup_posture"].passed is True
    assert by_name["consent_record_posture"].passed is True


def test_launch_readiness_flags_unbounded_slm_completion(config):
    cfg = type(config)(
        **{
            **config.__dict__,
            "slm_completion_enabled": True,
            "slm_completion_allowed_stages": ("preplan", "deploy"),
        }
    )
    checks = evaluate_launch_readiness(cfg)
    gate = {c.name: c for c in checks}["slm_completion_governance_posture"]
    assert gate.passed is False


def test_launch_readiness_requires_customer_legal_review_for_sensitive_workspaces(config):
    customer = config.workspaces_dir / "gps-co"
    customer.mkdir(parents=True)
    (customer / "requirements.json").write_text('{"summary_ja":"GPS と 従業員 勤怠"}', encoding="utf-8")
    checks = evaluate_launch_readiness(config)
    by_name = {c.name: c for c in checks}
    assert by_name["customer_legal_review_records_present"].passed is False
    assert by_name["japan_trust_launch_reviews_present"].passed is False


def test_launch_readiness_accepts_customer_legal_review_and_japan_trust_records(config):
    from smbagent.workspace import Workspace

    ws = Workspace("gps-ok", config.workspaces_dir)
    ws.ensure()
    ws.requirements_path.write_text('{"summary_ja":"GPS と 従業員 勤怠"}', encoding="utf-8")
    write_customer_legal_review(
        ws,
        operator="human:alice",
        purpose_of_use="gps analysis",
        data_categories=["gps", "employee"],
        retention_summary="30 days",
        access_summary="owner only",
        external_actions_hitl=True,
        approved=True,
        approval_note="ok",
    )
    (ws.path / "japan_trust_launch_note.md").write_text("note", encoding="utf-8")
    (ws.path / "customer_ai_use_policy_ja.md").write_text("policy", encoding="utf-8")
    (ws.path / "employee_data_notice_ja.md").write_text("employee", encoding="utf-8")
    (ws.path / "gps_analysis_notice_ja.md").write_text("gps", encoding="utf-8")
    write_japan_trust_launch_review(
        ws,
        operator="human:alice",
        workflow_categories=["gps", "employee"],
        sensitive_mode=config.sensitive_mode,
        human_approval_required=True,
        approved=True,
        approval_note="ok",
    )
    checks = evaluate_launch_readiness(config)
    by_name = {c.name: c for c in checks}
    assert by_name["customer_legal_review_records_present"].passed is True
    assert by_name["japan_trust_launch_reviews_present"].passed is True


def test_launch_readiness_prefers_hardened_isolation_beyond_legacy_macos(config):
    checks = evaluate_launch_readiness(config)
    by_name = {c.name: c for c in checks}
    assert by_name["hardened_subprocess_isolation_posture"].passed is False
    cfg = type(config)(**{**config.__dict__, "subprocess_isolation": "apple-container"})
    checks2 = evaluate_launch_readiness(cfg)
    by_name2 = {c.name: c for c in checks2}
    assert by_name2["hardened_subprocess_isolation_posture"].passed is True
