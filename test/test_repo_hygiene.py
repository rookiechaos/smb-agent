from __future__ import annotations

import json

from typer.testing import CliRunner

from smbagent.cli import app
from smbagent.config import Config
from smbagent.repo_hygiene import (
    build_pre_release_check_report,
    build_repo_hygiene_report,
    write_pre_release_check_bundle,
)

runner = CliRunner()

_RUNTIME_GITIGNORE = """\
workspaces/*
!workspaces/.gitkeep
!workspaces/README.md
analytics/*
!analytics/.gitkeep
!analytics/README.md
ops/slm_packs/*
!ops/slm_packs/.gitkeep
slm/registry/**
!slm/registry/.gitkeep
"""


def _clean_config(tmp_path, prompts_dir) -> Config:
    (tmp_path / "workspaces").mkdir()
    (tmp_path / "analytics").mkdir()
    (tmp_path / "workspaces" / ".gitkeep").write_text("", encoding="utf-8")
    (tmp_path / "workspaces" / "README.md").write_text("local runtime placeholder", encoding="utf-8")
    (tmp_path / "analytics" / ".gitkeep").write_text("", encoding="utf-8")
    (tmp_path / "analytics" / "README.md").write_text("local analytics placeholder", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(_RUNTIME_GITIGNORE, encoding="utf-8")
    (tmp_path / "README.md").write_text("local generated runtime data only", encoding="utf-8")
    (tmp_path / "DATA_POLICY.md").write_text("Local-only runtime artifacts", encoding="utf-8")
    (tmp_path / "SECURITY.md").write_text("runtime artifacts local-only", encoding="utf-8")
    return Config(
        root=tmp_path,
        workspaces_dir=tmp_path / "workspaces",
        prompts_dir=prompts_dir,
        anthropic_api_key="sk-ant-test",
        openai_api_key="sk-test",
        plan_model="claude-haiku-4-5-20251001",
        coding_cmd=["claude", "-p", "--model", "opus", "--permission-mode", "acceptEdits"],
        validation_backend="cli",
        validation_cmd=["codex", "exec"],
        validation_model="gpt-5",
        harness_profile="opus-default",
        subprocess_isolation="apple-container",
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
        token_ttl_days=0,
        max_body_bytes=1024 * 1024,
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
        allow_monitor_query_token_fallback=False,
        filevault_confirmed=True,
        local_workspace_confirmed=True,
        no_synced_folders_confirmed=True,
        backup_restore_drill_confirmed=True,
        launch_acceptance_confirmed=True,
    )


def test_write_pre_release_check_bundle_updates_release_record_manifest(tmp_path, config):
    cfg = _clean_config(tmp_path, config.prompts_dir)
    report, _, _ = write_pre_release_check_bundle(cfg)
    manifests = sorted((tmp_path / "ops" / "release_reviews").glob("*/release_record_manifest.json"))
    assert manifests
    manifest = json.loads(manifests[-1].read_text(encoding="utf-8"))
    by_key = {item["key"]: item for item in manifest["artifacts"]}
    assert by_key["pre_release_check"]["status"] == "present"
    assert any(
        path.endswith("pre_release_check/pre_release_check.json")
        for path in by_key["pre_release_check"]["artifact_paths"]
    )
    assert any(
        path.endswith("pre_release_check/pre_release_check.md")
        for path in by_key["pre_release_check"]["artifact_paths"]
    )
    assert by_key["remote_smoke"]["status"] == "reserved"
    assert manifest["smbagent_version"] == report.smbagent_version


def test_repo_hygiene_passes_on_placeholder_only_tree(tmp_path, config):
    cfg = _clean_config(tmp_path, config.prompts_dir)
    report = build_repo_hygiene_report(cfg)
    assert report.blocking_issue_count == 0
    assert all(check.passed for check in report.checks)


def test_repo_hygiene_detects_runtime_workspace_entries(tmp_path, config):
    cfg = _clean_config(tmp_path, config.prompts_dir)
    (cfg.workspaces_dir / "acme-co").mkdir()
    report = build_repo_hygiene_report(cfg)
    checks = {check.key: check for check in report.checks}
    assert checks["workspaces_placeholder_only"].passed is False
    assert "acme-co" in checks["workspaces_placeholder_only"].detail


def test_repo_hygiene_detects_stale_root_module_duplicates(tmp_path, config):
    cfg = _clean_config(tmp_path, config.prompts_dir)
    (tmp_path / "backup.py").write_text("# stale duplicate\n", encoding="utf-8")
    report = build_repo_hygiene_report(cfg)
    checks = {check.key: check for check in report.checks}
    assert checks["no_stale_root_module_duplicates"].passed is False
    assert "backup.py" in checks["no_stale_root_module_duplicates"].detail


def test_pre_release_check_prioritizes_expected_queue(tmp_path, config):
    cfg = _clean_config(tmp_path, config.prompts_dir)
    report = build_pre_release_check_report(cfg)
    assert [gate.key for gate in report.prioritized_release_queue] == [
        "full_synthetic_dry_run_real_apis",
        "managed_secret_storage",
        "ci_backed_trustworthiness_adversarial_suite",
        "remote_external_benchmark_runner",
    ]


def test_repo_hygiene_cli_writes_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "smbagent").mkdir()
    (tmp_path / "workspaces").mkdir()
    (tmp_path / "analytics").mkdir()
    (tmp_path / "workspaces" / ".gitkeep").write_text("", encoding="utf-8")
    (tmp_path / "workspaces" / "README.md").write_text("x", encoding="utf-8")
    (tmp_path / "analytics" / ".gitkeep").write_text("", encoding="utf-8")
    (tmp_path / "analytics" / "README.md").write_text("x", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(_RUNTIME_GITIGNORE, encoding="utf-8")
    (tmp_path / "README.md").write_text("local generated runtime data only", encoding="utf-8")
    (tmp_path / "DATA_POLICY.md").write_text("Local-only runtime artifacts", encoding="utf-8")
    (tmp_path / "SECURITY.md").write_text("runtime artifacts local-only", encoding="utf-8")
    out = tmp_path / "ops" / "repo_hygiene.json"

    result = runner.invoke(app, ["repo-hygiene", "--json-out", str(out)])

    assert result.exit_code == 0
    assert out.exists()
    body = json.loads(out.read_text(encoding="utf-8"))
    assert body["blocking_issue_count"] == 0


def test_pre_release_check_cli_writes_reports(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "smbagent").mkdir()
    (tmp_path / "workspaces").mkdir()
    (tmp_path / "analytics").mkdir()
    (tmp_path / "workspaces" / ".gitkeep").write_text("", encoding="utf-8")
    (tmp_path / "workspaces" / "README.md").write_text("x", encoding="utf-8")
    (tmp_path / "analytics" / ".gitkeep").write_text("", encoding="utf-8")
    (tmp_path / "analytics" / "README.md").write_text("x", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(_RUNTIME_GITIGNORE, encoding="utf-8")
    (tmp_path / "README.md").write_text("local generated runtime data only", encoding="utf-8")
    (tmp_path / "DATA_POLICY.md").write_text("Local-only runtime artifacts", encoding="utf-8")
    (tmp_path / "SECURITY.md").write_text("runtime artifacts local-only", encoding="utf-8")
    json_out = tmp_path / "ops" / "pre_release.json"
    md_out = tmp_path / "ops" / "pre_release.md"

    result = runner.invoke(app, ["pre-release-check", "--json-out", str(json_out), "--md-out", str(md_out)])

    assert result.exit_code == 0
    assert json_out.exists()
    assert md_out.exists()
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["smbagent_version"]
    assert payload["schema_version"] == 1
    assert "Pre-release check" in result.stdout


def test_write_pre_release_check_bundle_publishes_fleet_freshness(tmp_path, config):
    cfg = _clean_config(tmp_path, config.prompts_dir)
    report, json_path, md_path = write_pre_release_check_bundle(cfg)
    assert json_path == tmp_path / "ops" / "pre_release_check.json"
    assert md_path == tmp_path / "ops" / "pre_release_check.md"
    release_root = tmp_path / "ops" / "release_reviews"
    assert release_root.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["smbagent_version"]
    assert payload["schema_version"] == 1
    state = json.loads((tmp_path / "ops" / "fleet_state.json").read_text(encoding="utf-8"))
    freshness = state["sections"]["artifact_freshness"]["pre_release_check"]
    assert freshness["status"] == "fresh"
    assert "ops/pre_release_check.json" in freshness["artifact_paths"]
    assert "ops/pre_release_check.md" in freshness["artifact_paths"]
    assert any(
        path.endswith("/pre_release_check/pre_release_check.json") for path in freshness["artifact_paths"]
    )
    assert any(
        path.endswith("/pre_release_check/pre_release_check.md") for path in freshness["artifact_paths"]
    )
    assert any(path.endswith("/release_record_manifest.json") for path in freshness["artifact_paths"])
    assert report.smbagent_version == payload["smbagent_version"]
