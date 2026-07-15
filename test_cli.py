from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from smbagent.cli import app
from smbagent.config import load_config
from smbagent.observability import SLMAdvisoryLogger
from smbagent.workflow_health import WorkflowHealthReport
from smbagent.workspace import Workspace

runner = CliRunner()


@pytest.fixture
def isolated_root(tmp_path: Path, monkeypatch):
    """Run CLI commands in a tmp_path with its own workspaces/ directory.

    load_config() reads the project root and derives workspaces_dir from it.
    We chdir into tmp_path so a fresh workspaces/ folder is used per test.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "smbagent").mkdir()  # placate load_config()'s parent walk
    (tmp_path / "workspaces").mkdir()
    yield tmp_path


def test_help_lists_all_commands(isolated_root):
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in (
        "new",
        "qualify",
        "run",
        "negotiate",
        "plan",
        "validate",
        "tiers",
        "status",
        "context-update",
        # Runtime / deploy / integration / template / portal
        "serve",
        "deploy",
        "send",
        "template",
        "portal",
        "monitor",
        # Auth + serve-http + book
        "auth-issue",
        "auth-show",
        "employee-auth-issue",
        "employee-auth-show",
        "monitor-auth-issue",
        "monitor-auth-show",
        "maintenance",
        "serve-http",
        "book",
        "launch-readiness",
        "deployment-readiness",
        "security-readiness",
        "commercial-readiness",
        "repo-hygiene",
        "pre-release-check",
        "remote-smoke-plan",
        "remote-smoke-record",
        "launch-notes",
        "network-posture",
        "vpn-plan",
        "secret-put",
        "secret-delete",
        "secret-list",
        "remote-benchmark-plan",
        "remote-benchmark-record",
        "slm-runtime-plan",
        "slm-benchmark-plan",
        "slm-benchmark-record",
        "slm-completion-plan",
        "slm-dataset-build",
        "slm-status",
        "slm-customer-policy-show",
        "slm-customer-policy-set",
        "slm-quality-gate",
        "slm-acceptance-checklist",
        "slm-candidate-create",
        "slm-candidate-from-eval",
        "slm-promotion-approve",
        "slm-promotion-reject",
        "slm-rollback",
        "trust-eval",
        "trust-regression-contract",
        "japan-trust-note",
        "customer-legal-review",
        "japan-trust-launch-review",
        "legal-launch-checklist",
        "launch-prep",
        "backup-drill",
        "backup-encrypt-status",
        "coding-benchmarks",
        "harness-profiles",
        "smoke-harness",
        "apple-container-plan",
        "image-contract",
        "loop-engineering",
        "tune",
        "workflow-check",
        "workflow-check-all",
        "memory-analytics",
        "launchd-plist",
        "ikida-gps-analyze",
        "ikida-labor-review",
        "ikida-labor-finalize",
        "ikida-shipment-review",
        "ikida-shipment-finalize",
        "ikida-pricing-review",
        "ikida-pricing-finalize",
        # Operator dashboard
        "dashboard",
    ):
        assert cmd in result.stdout


def test_apple_container_plan_prints_images_and_no_port_posture(isolated_root, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
    monkeypatch.setenv("SMBAGENT_SUBPROCESS_ISOLATION", "apple-container")
    monkeypatch.setenv("SMBAGENT_APPLE_CONTAINER_CODING_IMAGE", "smbagent/claude-code:latest")
    monkeypatch.setenv("SMBAGENT_APPLE_CONTAINER_VALIDATION_IMAGE", "smbagent/codex-validation:latest")

    result = runner.invoke(app, ["apple-container-plan"])

    assert result.exit_code == 0
    assert "Apple container image contract" in result.stdout
    assert "no_published_ports: true" in result.stdout
    assert "smbagent/claude-code:latest" in result.stdout
    assert "smbagent/codex-validation:latest" in result.stdout
    assert "container build --file containers/apple/claude-code/Containerfile" in result.stdout


def test_image_contract_alias_can_write_json(isolated_root, monkeypatch):
    monkeypatch.setenv("SMBAGENT_SUBPROCESS_ISOLATION", "apple-container")
    out = isolated_root / "ops" / "apple_container_plan.json"

    result = runner.invoke(app, ["image-contract", "--json-out", str(out)])

    assert result.exit_code == 0
    assert out.exists()
    body = json.loads(out.read_text(encoding="utf-8"))
    assert body["provider"] == "apple-container"
    assert body["no_published_ports"] is True
    assert len(body["images"]) == 2


def test_trust_regression_contract_cli_writes_reports(isolated_root):
    out_json = isolated_root / "ops" / "trust_regression_contract.json"
    out_md = isolated_root / "ops" / "trust_regression_contract.md"

    result = runner.invoke(
        app,
        [
            "trust-regression-contract",
            "--json-out",
            str(out_json),
            "--md-out",
            str(out_md),
        ],
    )

    assert result.exit_code == 0
    assert "Trust regression contract" in result.stdout
    assert out_json.exists()
    assert out_md.exists()
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["posture"] == "ci_backed_pr_smoke_plus_full_regression_without_outside_ports"


def test_loop_engineering_writes_workspace_contract_and_json_copy(isolated_root):
    customer_id = "loop-co"
    runner.invoke(app, ["new", customer_id])
    out = isolated_root / "ops" / "loop_engineering.json"

    result = runner.invoke(app, ["loop-engineering", customer_id, "--json-out", str(out)])

    assert result.exit_code == 0
    assert "Loop engineering contract" in result.stdout
    assert "bounded_checkpointed_learning_loop" in result.stdout
    assert "one_shot_autonomy: false" in result.stdout
    assert "hard cap at" in result.stdout
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["customer_id"] == customer_id
    assert payload["posture"] == "bounded_checkpointed_learning_loop"
    assert payload["one_shot_autonomy"] is False
    assert "latest_selected_action" in payload
    workspace_copy = isolated_root / "workspaces" / customer_id / "loop_engineering.json"
    assert workspace_copy.exists()


def test_monitor_auth_issue_creates_owner_token(isolated_root, monkeypatch):
    monkeypatch.setenv("SMBAGENT_MONITOR_PUBLIC_BASE_URL", "https://monitor.example.com")
    customer_id = f"monitor-owner-{isolated_root.name}"
    runner.invoke(app, ["new", customer_id])

    result = runner.invoke(app, ["monitor-auth-issue", customer_id, "--force"])

    assert result.exit_code == 0
    assert "owner monitor login URL" in result.stdout
    cfg = load_config()
    assert (cfg.workspaces_dir / customer_id / "monitor_auth.json").exists()


def test_network_posture_cli_prints_tailscale_first_plan(isolated_root):
    out = isolated_root / "ops" / "network_posture.json"
    result = runner.invoke(app, ["network-posture", "--customer-id", "acme-co", "--json-out", str(out)])
    assert result.exit_code == 0
    assert "preferred_remote_stack: tailscale" in result.stdout
    assert "secondary_remote_stack: wireguard" in result.stdout
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["preferred_remote_stack"] == "tailscale"


def test_vpn_plan_cli_prints_delivery_recommendation(isolated_root):
    result = runner.invoke(app, ["vpn-plan", "--customer-id", "beta-co"])
    assert result.exit_code == 0
    assert "VPN delivery plan" in result.stdout
    assert "tailscale" in result.stdout
    assert "/monitor-login/beta-co" in result.stdout


def test_deployment_readiness_cli_fails_when_attestations_missing(isolated_root):
    result = runner.invoke(app, ["deployment-readiness"])
    assert result.exit_code == 1
    assert "Single-customer deployment maturity" in result.stdout
    assert "Local privacy posture" in result.stdout


def test_security_readiness_cli_fails_when_attestations_missing(isolated_root):
    result = runner.invoke(app, ["security-readiness"])
    assert result.exit_code == 1
    assert "Isolation and agent boundaries" in result.stdout
    assert "Auth and token storage" in result.stdout


def test_slm_runtime_plan_prints_qwen_bf16_defaults(isolated_root):
    result = runner.invoke(app, ["slm-runtime-plan"])
    assert result.exit_code == 0
    assert "qwen3.5-2b" in result.stdout
    assert "bfloat16" in result.stdout
    assert "Qwen/Qwen3.5-2B-Instruct" in result.stdout
    assert "Copyable .env block" in result.stdout
    assert "Copyable launch command" in result.stdout
    assert "estimated_working_set_gb" in result.stdout


def test_slm_acceptance_checklist_writes_output(isolated_root):
    result = runner.invoke(app, ["slm-acceptance-checklist"])
    assert result.exit_code == 0
    assert "SLM acceptance checklist" in result.stdout
    assert (isolated_root / "ops" / "slm_acceptance_checklist.json").exists()


def test_slm_customer_policy_set_and_show(isolated_root):
    customer_id = "policy-co"
    runner.invoke(app, ["new", customer_id])
    result = runner.invoke(
        app,
        [
            "slm-customer-policy-set",
            customer_id,
            "--mode",
            "advisory",
            "--operator",
            "human:admin@example.com",
            "--allowed-stage",
            "runtime",
            "--blocked-workflow-family",
            "payroll",
            "--note",
            "sensitive payroll stays blocked",
        ],
    )
    assert result.exit_code == 0
    show = runner.invoke(app, ["slm-customer-policy-show", customer_id])
    assert show.exit_code == 0
    assert "mode: advisory" in show.stdout
    assert "runtime" in show.stdout
    assert "payroll" in show.stdout


def test_slm_quality_gate_command_writes_report(isolated_root):
    source_eval = isolated_root / "weekly_eval.json"
    repo_root = Path(__file__).resolve().parents[1]
    source_eval.write_text(
        (repo_root / "examples" / "slm_registry" / "fixtures" / "sample_eval_report.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["slm-quality-gate", "--eval-report", str(source_eval)])
    assert result.exit_code == 0
    assert "passed: true" in result.stdout
    assert source_eval.with_name("weekly_eval.quality_gate.json").exists()


def test_slm_candidate_create_writes_candidate_and_pending_request(isolated_root):
    result = runner.invoke(
        app,
        [
            "slm-candidate-create",
            "--version",
            "qwen3.5-2b-lora-2026-06-03-r1",
            "--dataset-snapshot-id",
            "weekly-2026-06-03",
            "--train-config-ref",
            "configs/slm_lora_weekly_v1.json",
            "--artifact-path",
            "slm/adapters/qwen3.5-2b-lora-2026-06-03-r1",
            "--eval-report-path",
            "slm/registry/reports/qwen3.5-2b-lora-2026-06-03-r1.eval.json",
            "--note",
            "weekly candidate",
        ],
    )
    assert result.exit_code == 0
    registry_root = isolated_root / "slm" / "registry"
    assert (registry_root / "candidates" / "qwen3.5-2b-lora-2026-06-03-r1.json").exists()
    assert (registry_root / "promotion_requests" / "qwen3.5-2b-lora-2026-06-03-r1.promotion.json").exists()


def test_slm_candidate_from_eval_records_report_and_creates_chain(isolated_root):
    source_eval = isolated_root / "weekly_eval.json"
    repo_root = Path(__file__).resolve().parents[1]
    source_eval.write_text(
        (repo_root / "examples" / "slm_registry" / "fixtures" / "sample_eval_report.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "slm-candidate-from-eval",
            "--eval-report",
            str(source_eval),
            "--dataset-snapshot-id",
            "weekly-2026-06-03",
            "--train-config-ref",
            "configs/slm_lora_weekly_v1.json",
            "--artifact-path",
            "slm/adapters/qwen3.5-2b-lora-2026-06-03-r1",
        ],
    )
    assert result.exit_code == 0
    registry_root = isolated_root / "slm" / "registry"
    assert (registry_root / "reports" / "qwen3.5-2b-lora-2026-06-03-r1.eval.json").exists()
    assert (registry_root / "reports" / "qwen3.5-2b-lora-2026-06-03-r1.quality_gate.json").exists()
    assert (registry_root / "candidates" / "qwen3.5-2b-lora-2026-06-03-r1.json").exists()
    assert (registry_root / "promotion_requests" / "qwen3.5-2b-lora-2026-06-03-r1.promotion.json").exists()


def test_slm_candidate_from_eval_fails_closed_on_bad_quality_gate(isolated_root):
    source_eval = isolated_root / "bad_eval.json"
    source_eval.write_text(
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
    result = runner.invoke(
        app,
        [
            "slm-candidate-from-eval",
            "--eval-report",
            str(source_eval),
            "--dataset-snapshot-id",
            "weekly-bad",
            "--train-config-ref",
            "configs/slm_lora_weekly_v1.json",
            "--artifact-path",
            "slm/adapters/bad-r1",
        ],
    )
    assert result.exit_code != 0
    assert "quality gate failed" in result.stdout.lower()


def test_slm_candidate_create_fails_closed_when_auto_train_enabled(isolated_root, monkeypatch):
    monkeypatch.setenv("SMBAGENT_SLM_AUTO_TRAIN_ENABLED", "true")

    result = runner.invoke(
        app,
        [
            "slm-candidate-create",
            "--version",
            "qwen3.5-2b-lora-2026-06-03-r1",
            "--dataset-snapshot-id",
            "weekly-2026-06-03",
            "--train-config-ref",
            "slm/train_configs/weekly-lora.yaml",
            "--artifact-path",
            "slm/artifacts/qwen3.5-2b-lora-2026-06-03-r1",
            "--eval-report-path",
            "slm/registry/reports/qwen3.5-2b-lora-2026-06-03-r1.eval.json",
        ],
    )

    assert result.exit_code != 0
    assert "automatic specialist training must remain disabled" in result.stdout.lower()


def test_slm_dataset_build_fails_closed_when_raw_log_export_enabled(isolated_root, monkeypatch):
    monkeypatch.setenv("SMBAGENT_SLM_TRAINING_EXPORT_ALLOW_RAW_LOGS", "true")
    customer_id = "gamma-co"
    runner.invoke(app, ["new", customer_id])

    result = runner.invoke(
        app,
        [
            "slm-dataset-build",
            "--dataset-snapshot-id",
            "weekly-2026-06-09",
            "--customer-id",
            customer_id,
        ],
    )

    assert result.exit_code != 0
    assert "customer raw logs are not allowed" in result.stdout.lower()


def test_slm_promotion_approve_requires_human_operator(isolated_root):
    runner.invoke(
        app,
        [
            "slm-candidate-create",
            "--version",
            "qwen3.5-2b-lora-2026-06-03-r1",
            "--dataset-snapshot-id",
            "weekly-2026-06-03",
            "--train-config-ref",
            "slm/train_configs/weekly-lora.yaml",
            "--artifact-path",
            "slm/artifacts/qwen3.5-2b-lora-2026-06-03-r1",
            "--eval-report-path",
            "slm/registry/reports/qwen3.5-2b-lora-2026-06-03-r1.eval.json",
        ],
    )

    result = runner.invoke(
        app,
        [
            "slm-promotion-approve",
            "--version",
            "qwen3.5-2b-lora-2026-06-03-r1",
            "--operator",
            "system:weekly-slm-train",
            "--allow-failed-quality-gate",
        ],
    )

    assert result.exit_code != 0
    assert "requires an explicit human operator identity" in result.stdout.lower()


def test_slm_status_shows_active_pending_and_latest_rollback(isolated_root):
    runner.invoke(
        app,
        [
            "slm-candidate-create",
            "--version",
            "qwen3.5-2b-lora-2026-06-03-r0",
            "--dataset-snapshot-id",
            "weekly-2026-06-03",
            "--train-config-ref",
            "configs/slm_lora_weekly_v1.json",
            "--artifact-path",
            "slm/adapters/qwen3.5-2b-lora-2026-06-03-r0",
            "--eval-report-path",
            "slm/registry/reports/qwen3.5-2b-lora-2026-06-03-r0.eval.json",
        ],
    )
    runner.invoke(
        app,
        [
            "slm-promotion-approve",
            "--version",
            "qwen3.5-2b-lora-2026-06-03-r0",
            "--operator",
            "human:admin@example.com",
        ],
    )
    runner.invoke(
        app,
        [
            "slm-candidate-create",
            "--version",
            "qwen3.5-2b-lora-2026-06-03-r1",
            "--dataset-snapshot-id",
            "weekly-2026-06-10",
            "--train-config-ref",
            "configs/slm_lora_weekly_v1.json",
            "--artifact-path",
            "slm/adapters/qwen3.5-2b-lora-2026-06-03-r1",
            "--eval-report-path",
            "slm/registry/reports/qwen3.5-2b-lora-2026-06-03-r1.eval.json",
        ],
    )
    runner.invoke(
        app,
        [
            "slm-promotion-approve",
            "--version",
            "qwen3.5-2b-lora-2026-06-03-r1",
            "--operator",
            "human:admin@example.com",
        ],
    )
    runner.invoke(
        app,
        [
            "slm-candidate-create",
            "--version",
            "qwen3.5-2b-lora-2026-06-03-r2",
            "--dataset-snapshot-id",
            "weekly-2026-06-17",
            "--train-config-ref",
            "configs/slm_lora_weekly_v1.json",
            "--artifact-path",
            "slm/adapters/qwen3.5-2b-lora-2026-06-03-r2",
            "--eval-report-path",
            "slm/registry/reports/qwen3.5-2b-lora-2026-06-03-r2.eval.json",
        ],
    )
    runner.invoke(
        app,
        [
            "slm-rollback",
            "--operator",
            "human:admin@example.com",
            "--reason",
            "quality regressed",
        ],
    )
    result = runner.invoke(app, ["slm-status"])
    assert result.exit_code == 0
    assert "SLM adapter status" in result.stdout
    assert "active:" in result.stdout
    assert "qwen3.5-2b-lora-2026-06-03-r0" in result.stdout
    assert "pending promotion requests: " in result.stdout
    assert "qwen3.5-2b-lora-2026-06-03-r2" in result.stdout
    assert "latest rollback:" in result.stdout


def test_slm_promotion_approve_updates_active_adapter(isolated_root):
    runner.invoke(
        app,
        [
            "slm-candidate-create",
            "--version",
            "qwen3.5-2b-lora-2026-06-03-r1",
            "--dataset-snapshot-id",
            "weekly-2026-06-03",
            "--train-config-ref",
            "configs/slm_lora_weekly_v1.json",
            "--artifact-path",
            "slm/adapters/qwen3.5-2b-lora-2026-06-03-r1",
            "--eval-report-path",
            "slm/registry/reports/qwen3.5-2b-lora-2026-06-03-r1.eval.json",
        ],
    )
    result = runner.invoke(
        app,
        [
            "slm-promotion-approve",
            "--version",
            "qwen3.5-2b-lora-2026-06-03-r1",
            "--operator",
            "human:admin@example.com",
        ],
    )
    assert result.exit_code == 0
    active_path = isolated_root / "slm" / "registry" / "active_adapter.json"
    assert active_path.exists()
    assert "qwen3.5-2b-lora-2026-06-03-r1" in active_path.read_text(encoding="utf-8")


def test_slm_promotion_reject_marks_request(isolated_root):
    runner.invoke(
        app,
        [
            "slm-candidate-create",
            "--version",
            "qwen3.5-2b-lora-2026-06-03-r2",
            "--dataset-snapshot-id",
            "weekly-2026-06-03",
            "--train-config-ref",
            "configs/slm_lora_weekly_v1.json",
            "--artifact-path",
            "slm/adapters/qwen3.5-2b-lora-2026-06-03-r2",
            "--eval-report-path",
            "slm/registry/reports/qwen3.5-2b-lora-2026-06-03-r2.eval.json",
        ],
    )
    result = runner.invoke(
        app,
        [
            "slm-promotion-reject",
            "--version",
            "qwen3.5-2b-lora-2026-06-03-r2",
            "--operator",
            "human:admin@example.com",
            "--reason",
            "holdout regression",
        ],
    )
    assert result.exit_code == 0
    request_path = (
        isolated_root
        / "slm"
        / "registry"
        / "promotion_requests"
        / "qwen3.5-2b-lora-2026-06-03-r2.promotion.json"
    )
    text = request_path.read_text(encoding="utf-8")
    assert '"status": "rejected"' in text
    assert "holdout regression" in text


def test_slm_rollback_restores_previous_version(isolated_root):
    runner.invoke(
        app,
        [
            "slm-candidate-create",
            "--version",
            "qwen3.5-2b-lora-2026-06-03-r0",
            "--dataset-snapshot-id",
            "weekly-2026-06-03",
            "--train-config-ref",
            "configs/slm_lora_weekly_v1.json",
            "--artifact-path",
            "slm/adapters/qwen3.5-2b-lora-2026-06-03-r0",
            "--eval-report-path",
            "slm/registry/reports/qwen3.5-2b-lora-2026-06-03-r0.eval.json",
        ],
    )
    runner.invoke(
        app,
        [
            "slm-promotion-approve",
            "--version",
            "qwen3.5-2b-lora-2026-06-03-r0",
            "--operator",
            "human:admin@example.com",
        ],
    )
    runner.invoke(
        app,
        [
            "slm-candidate-create",
            "--version",
            "qwen3.5-2b-lora-2026-06-03-r1",
            "--dataset-snapshot-id",
            "weekly-2026-06-10",
            "--train-config-ref",
            "configs/slm_lora_weekly_v1.json",
            "--artifact-path",
            "slm/adapters/qwen3.5-2b-lora-2026-06-03-r1",
            "--eval-report-path",
            "slm/registry/reports/qwen3.5-2b-lora-2026-06-03-r1.eval.json",
        ],
    )
    runner.invoke(
        app,
        [
            "slm-promotion-approve",
            "--version",
            "qwen3.5-2b-lora-2026-06-03-r1",
            "--operator",
            "human:admin@example.com",
        ],
    )
    result = runner.invoke(
        app,
        [
            "slm-rollback",
            "--operator",
            "human:admin@example.com",
            "--reason",
            "quality regressed",
        ],
    )
    assert result.exit_code == 0
    active_path = isolated_root / "slm" / "registry" / "active_adapter.json"
    rollback_path = (
        isolated_root / "slm" / "registry" / "rollbacks" / "qwen3.5-2b-lora-2026-06-03-r1.rollback.json"
    )
    assert rollback_path.exists()
    assert '"active_version": "qwen3.5-2b-lora-2026-06-03-r0"' in active_path.read_text(encoding="utf-8")


def test_employee_auth_issue_creates_employee_token(isolated_root):
    customer_id = f"employee-token-{isolated_root.name}"
    runner.invoke(app, ["new", customer_id])

    result = runner.invoke(app, ["employee-auth-issue", customer_id, "--force"])

    assert result.exit_code == 0
    assert "employee chat + employee skills only" in result.stdout
    cfg = load_config()
    assert (cfg.workspaces_dir / customer_id / "employee_auth.json").exists()


def test_maintenance_command_writes_report(isolated_root):
    customer_id = f"maintenance-{isolated_root.name}"
    runner.invoke(app, ["new", customer_id])

    result = runner.invoke(app, ["maintenance", customer_id])

    assert result.exit_code == 0
    cfg = load_config()
    report_path = cfg.workspaces_dir / customer_id / "maintenance_report.json"
    assert report_path.exists()
    assert "Wrote maintenance report:" in result.stdout


def test_tune_set_records_audit_log(isolated_root):
    result = runner.invoke(
        app,
        [
            "tune",
            "set",
            "--creative",
            "0.55",
            "--operator",
            "alice@example.com",
            "--notes",
            "remote maintainer tune",
        ],
    )

    assert result.exit_code == 0
    cfg = load_config()
    audit_path = cfg.root / "tuning" / "changes.jsonl"
    assert audit_path.exists()
    assert "Recorded tuning audit:" in result.stdout


def test_workflow_check_writes_health_report(isolated_root):
    customer_id = f"health-{isolated_root.name}"
    runner.invoke(app, ["new", customer_id])

    result = runner.invoke(app, ["workflow-check", customer_id])

    assert result.exit_code == 0
    cfg = load_config()
    report_path = cfg.workspaces_dir / customer_id / "workflow_health.json"
    assert report_path.exists()
    assert "Wrote workflow health:" in result.stdout


def test_workflow_check_all_runs_due_workspaces(isolated_root):
    customer_id = f"healthall-{isolated_root.name}"
    runner.invoke(app, ["new", customer_id])

    result = runner.invoke(app, ["workflow-check-all", "--all"])

    assert result.exit_code == 0
    assert customer_id in result.stdout


def test_workflow_check_all_prints_breaker_alert_when_open(isolated_root, monkeypatch):
    customer_id = f"breakerall-{isolated_root.name}"
    report = WorkflowHealthReport(
        customer_id=customer_id,
        status="needs_attention",
        healthy=False,
        checked_at="2026-06-08T02:00:00Z",
        next_check_due_at="2026-06-08T03:00:00Z",
        interval_minutes=60,
        monitor_status="idle",
        maintenance_status="needs_attention",
        issue_count=1,
        issues=[],
        circuit_breaker_status="open",
        circuit_breaker_open=True,
        circuit_breaker_reason="Paused for safety after repeated failed workflow tasks.",
    )

    from smbagent import cli as cli_module

    monkeypatch.setattr(cli_module, "run_due_workflow_checks", lambda cfg, due_only=True: [report])
    result = runner.invoke(
        app,
        ["workflow-check-all", "--all"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "MAINTAINER ALERT" in result.stdout
    assert "workflow circuit breaker open" in result.stdout
    assert customer_id in result.stdout
    assert "workflow-breaker-reset" in result.stdout


def test_launchd_plist_writes_file(isolated_root):
    label = f"com.smbagent.workflow-check-{isolated_root.name}"
    result = runner.invoke(app, ["launchd-plist", "--label", label, "--interval-minutes", "30"])

    assert result.exit_code == 0
    cfg = load_config()
    out = cfg.root / "ops" / "launchd" / f"{label}.plist"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "workflow-check-all" in text
    assert "<integer>1800</integer>" in text


def test_dashboard_command_creates_html(isolated_root):
    result = runner.invoke(app, ["dashboard"])
    assert result.exit_code == 0
    assert "dashboard.html" in result.stdout
    cfg = load_config()
    dash_path = cfg.workspaces_dir / "dashboard.html"
    assert dash_path.exists()
    text = dash_path.read_text(encoding="utf-8")
    assert "Operator dashboard" in text


def test_dashboard_command_with_customers(isolated_root):
    runner.invoke(app, ["new", "alpha-co"])
    runner.invoke(app, ["new", "beta-co"])
    result = runner.invoke(app, ["dashboard"])
    assert result.exit_code == 0
    cfg = load_config()
    text = (cfg.workspaces_dir / "dashboard.html").read_text(encoding="utf-8")
    assert "alpha-co" in text
    assert "beta-co" in text


def test_tiers_prints_three_tiers(isolated_root):
    result = runner.invoke(app, ["tiers"])
    assert result.exit_code == 0
    assert "starter" in result.stdout
    assert "growth" in result.stdout
    assert "business" in result.stdout
    assert "$399" in result.stdout
    assert "$999" in result.stdout


def test_new_creates_workspace(isolated_root, monkeypatch):
    cfg = load_config()
    result = runner.invoke(app, ["new", "alpha-co"])
    assert result.exit_code == 0
    assert (cfg.workspaces_dir / "alpha-co").is_dir()
    assert (cfg.workspaces_dir / "alpha-co" / "code").is_dir()


def test_new_rejects_path_traversal(isolated_root):
    """The CLI must refuse a customer_id that would escape workspaces/."""
    result = runner.invoke(app, ["new", "../../etc/passwd"])
    assert result.exit_code != 0
    assert "invalid customer_id" in (result.stdout + (str(result.exception or "")))


def test_new_rejects_empty_id(isolated_root):
    result = runner.invoke(app, ["new", ""])
    assert result.exit_code != 0


def test_status_on_missing_workspace(isolated_root):
    result = runner.invoke(app, ["status", "ghost-customer"])
    assert result.exit_code != 0
    assert "no workspace" in result.stdout


def test_status_on_empty_workspace(isolated_root):
    runner.invoke(app, ["new", "beta-co"])
    result = runner.invoke(app, ["status", "beta-co"])
    assert result.exit_code == 0
    assert "qualification.json: False" in result.stdout
    assert "requirements.json:  False" in result.stdout
    assert "rounds completed:   0" in result.stdout


def test_plan_command_errors_when_requirements_missing(isolated_root):
    runner.invoke(app, ["new", "gamma-co"])
    result = runner.invoke(app, ["plan", "gamma-co"])
    # Typer BadParameter exits with code 2 and prints to stderr.
    assert result.exit_code != 0


def test_run_with_bad_tier_string_errors(isolated_root):
    runner.invoke(app, ["new", "delta-co"])
    result = runner.invoke(app, ["run", "delta-co", "--brief", "test", "--tier", "bogus"])
    assert result.exit_code != 0


def test_negotiate_errors_when_no_tier_and_no_qualification(isolated_root):
    runner.invoke(app, ["new", "epsilon-co"])
    result = runner.invoke(app, ["negotiate", "epsilon-co"])
    assert result.exit_code != 0


# ---- New commands: serve / deploy / send / template / portal ----


def test_serve_errors_when_workspace_missing(isolated_root):
    result = runner.invoke(app, ["serve", "ghost", "--message", "hi"])
    assert result.exit_code != 0


def test_deploy_errors_when_workspace_missing(isolated_root):
    result = runner.invoke(app, ["deploy", "ghost"])
    assert result.exit_code != 0


def test_deploy_errors_when_landing_page_missing(isolated_root):
    runner.invoke(app, ["new", "zeta-co"])
    # No landing-page/ in code/, so tarball target should refuse.
    result = runner.invoke(app, ["deploy", "zeta-co", "--target", "tarball"])
    assert result.exit_code != 0


def test_deploy_with_unknown_target_errors(isolated_root):
    runner.invoke(app, ["new", "eta-co"])
    result = runner.invoke(app, ["deploy", "eta-co", "--target", "github-pages"])
    assert result.exit_code != 0


def test_send_errors_when_workspace_missing(isolated_root):
    result = runner.invoke(
        app, ["send", "ghost", "--integration", "x", "--to", "a@b", "--subject", "s", "--body", "b"]
    )
    assert result.exit_code != 0


def test_send_errors_when_integration_config_missing(isolated_root):
    runner.invoke(app, ["new", "theta-co"])
    result = runner.invoke(
        app, ["send", "theta-co", "--integration", "ghost", "--to", "a@b", "--subject", "s", "--body", "b"]
    )
    assert result.exit_code != 0


def test_template_list_prints_available_packs(isolated_root):
    result = runner.invoke(app, ["template", "list"])
    assert result.exit_code == 0
    assert "dental" in result.stdout


def test_template_materialize_requires_pack_and_customer(isolated_root):
    result = runner.invoke(app, ["template", "materialize"])
    assert result.exit_code != 0


def test_template_materialize_into_fresh_workspace(isolated_root):
    runner.invoke(app, ["new", "iota-co"])
    result = runner.invoke(app, ["template", "materialize", "dental", "--customer", "iota-co"])
    assert result.exit_code == 0
    assert "Materialized" in result.stdout
    # Verify files actually arrived.
    cfg = load_config()
    assert (cfg.workspaces_dir / "iota-co" / "code" / "agent-skills" / "understand-dental.md").exists()


def test_template_unknown_action_errors(isolated_root):
    runner.invoke(app, ["new", "kappa-co"])
    result = runner.invoke(app, ["template", "wat", "dental", "--customer", "kappa-co"])
    assert result.exit_code != 0


def test_portal_errors_when_workspace_missing(isolated_root):
    result = runner.invoke(app, ["portal", "ghost"])
    assert result.exit_code != 0


def test_portal_generates_html_for_empty_workspace(isolated_root):
    runner.invoke(app, ["new", "lambda-co"])
    result = runner.invoke(app, ["portal", "lambda-co"])
    assert result.exit_code == 0
    assert "portal.html" in result.stdout
    cfg = load_config()
    portal_path = cfg.workspaces_dir / "lambda-co" / "portal.html"
    assert portal_path.exists()
    content = portal_path.read_text(encoding="utf-8")
    assert "<!doctype html>" in content
    assert "lambda-co" in content


def test_monitor_generates_html_for_empty_workspace(isolated_root):
    runner.invoke(app, ["new", "sigma-co"])
    result = runner.invoke(app, ["monitor", "sigma-co"])
    assert result.exit_code == 0
    assert "monitor.html" in result.stdout
    cfg = load_config()
    monitor_path = cfg.workspaces_dir / "sigma-co" / "monitor.html"
    assert monitor_path.exists()
    content = monitor_path.read_text(encoding="utf-8")
    assert "<!doctype html>" in content
    assert "Workflow monitor" in content


# ---- auth-issue / auth-show ----


def test_auth_issue_creates_token(isolated_root):
    customer_id = f"mu-{isolated_root.name}"
    runner.invoke(app, ["new", customer_id])
    result = runner.invoke(app, ["auth-issue", customer_id, "--force"])
    assert result.exit_code == 0
    assert f"Token for {customer_id}:" in result.stdout
    cfg = load_config()
    assert (cfg.workspaces_dir / customer_id / "auth.json").exists()


def test_auth_issue_is_idempotent(isolated_root):
    customer_id = f"nu-{isolated_root.name}"
    runner.invoke(app, ["new", customer_id])
    r1 = runner.invoke(app, ["auth-issue", customer_id, "--force"])
    r2 = runner.invoke(app, ["auth-issue", customer_id])
    assert r1.exit_code == 0 and r2.exit_code == 0
    # Hashed token storage only shows the bearer token at initial issue time.
    import re

    m1 = re.search(rf"Token for {customer_id}:\s*\S+", r1.stdout)
    assert m1
    assert "already exists" in r2.stdout
    assert "not recoverable" in r2.stdout


def test_auth_issue_force_rotates(isolated_root):
    customer_id = f"xi-{isolated_root.name}"
    runner.invoke(app, ["new", customer_id])
    r1 = runner.invoke(app, ["auth-issue", customer_id])
    r2 = runner.invoke(app, ["auth-issue", customer_id, "--force"])
    # Different tokens after --force
    assert r1.stdout != r2.stdout


def test_auth_show_without_prior_issue_errors(isolated_root):
    customer_id = f"omicron-{isolated_root.name}"
    runner.invoke(app, ["new", customer_id])
    result = runner.invoke(app, ["auth-show", customer_id])
    assert result.exit_code != 0


def test_auth_show_after_issue_succeeds(isolated_root):
    customer_id = f"pi-{isolated_root.name}"
    runner.invoke(app, ["new", customer_id])
    runner.invoke(app, ["auth-issue", customer_id])
    result = runner.invoke(app, ["auth-show", customer_id])
    assert result.exit_code == 0
    assert "token:" in result.stdout
    assert "not recoverable" in result.stdout


# ---- book ----


def test_book_errors_when_workspace_missing(isolated_root):
    result = runner.invoke(
        app,
        [
            "book",
            "ghost",
            "--integration",
            "x",
            "--summary",
            "s",
            "--start",
            "2026-06-01T10:00:00+09:00",
            "--end",
            "2026-06-01T11:00:00+09:00",
        ],
    )
    assert result.exit_code != 0


def test_book_errors_on_unparseable_datetime(isolated_root):
    runner.invoke(app, ["new", "rho-co"])
    result = runner.invoke(
        app,
        [
            "book",
            "rho-co",
            "--integration",
            "x",
            "--summary",
            "s",
            "--start",
            "not-a-date",
            "--end",
            "also-not",
        ],
    )
    assert result.exit_code != 0


def test_book_errors_when_integration_config_missing(isolated_root):
    runner.invoke(app, ["new", "sigma-co"])
    result = runner.invoke(
        app,
        [
            "book",
            "sigma-co",
            "--integration",
            "ghost",
            "--summary",
            "s",
            "--start",
            "2026-06-01T10:00:00+09:00",
            "--end",
            "2026-06-01T11:00:00+09:00",
        ],
    )
    assert result.exit_code != 0


def test_slm_dataset_build_writes_snapshot(isolated_root):
    customer_id = "dataset-customer"
    result = runner.invoke(app, ["new", customer_id])
    assert result.exit_code == 0
    ws = Workspace(customer_id, isolated_root / "workspaces")
    ws.ensure()
    SLMAdvisoryLogger(ws).record(
        stage="plan",
        applied=True,
        workflow_family="ikida_shipment",
        task_class="shipment_governance",
        risk_band="medium",
        hitl_recommended=True,
        confidence=0.88,
        notes="shipment advisory",
    )

    result = runner.invoke(
        app,
        [
            "slm-dataset-build",
            "--dataset-snapshot-id",
            "weekly-2026-06-07",
            "--customer-id",
            customer_id,
            "--note",
            "weekly specialist export",
        ],
    )
    assert result.exit_code == 0
    manifest = isolated_root / "slm" / "datasets" / "snapshots" / "weekly-2026-06-07" / "manifest.json"
    examples = isolated_root / "slm" / "datasets" / "snapshots" / "weekly-2026-06-07" / "examples.jsonl"
    review_json = (
        isolated_root / "slm" / "datasets" / "snapshots" / "weekly-2026-06-07" / "weekly_review.json"
    )
    review_md = isolated_root / "slm" / "datasets" / "snapshots" / "weekly-2026-06-07" / "weekly_review.md"
    assert manifest.exists()
    assert examples.exists()
    assert review_json.exists()
    assert review_md.exists()


def test_slm_status_shows_latest_dataset_review(isolated_root):
    customer_id = "review-customer"
    runner.invoke(app, ["new", customer_id])
    ws = Workspace(customer_id, isolated_root / "workspaces")
    ws.ensure()
    SLMAdvisoryLogger(ws).record(
        stage="plan",
        applied=True,
        workflow_family="ikida_gps",
        task_class="gps_analysis",
        risk_band="medium",
        hitl_recommended=True,
        confidence=0.9,
        notes="weekly review candidate",
    )
    runner.invoke(
        app,
        [
            "slm-dataset-build",
            "--dataset-snapshot-id",
            "weekly-2026-06-10",
            "--customer-id",
            customer_id,
        ],
    )

    result = runner.invoke(app, ["slm-status"])

    assert result.exit_code == 0
    assert "latest dataset review:" in result.stdout
    assert "weekly-2026-06-10" in result.stdout
    assert "ready_for_lora_review:" in result.stdout
    assert "maintainer_decision:" in result.stdout
    assert "weekly training summary" in result.stdout
    assert "training_posture:" in result.stdout
    assert "governance revision:" in result.stdout
    assert "governance conflicts:" in result.stdout


def test_slm_dataset_build_updates_governance_state(isolated_root):
    customer_id = "governance-customer"
    runner.invoke(app, ["new", customer_id])
    ws = Workspace(customer_id, isolated_root / "workspaces")
    ws.ensure()
    SLMAdvisoryLogger(ws).record(
        stage="plan",
        applied=True,
        workflow_family="ikida_gps",
        task_class="gps_analysis",
        risk_band="medium",
        hitl_recommended=True,
        confidence=0.9,
        notes="governance state sample",
    )

    result = runner.invoke(
        app,
        [
            "slm-dataset-build",
            "--dataset-snapshot-id",
            "weekly-2026-06-11",
            "--customer-id",
            customer_id,
        ],
    )

    assert result.exit_code == 0
    governance_state = json.loads(
        (isolated_root / "slm" / "registry" / "governance_state.json").read_text(encoding="utf-8")
    )
    assert governance_state["revision"] >= 1
    assert governance_state["sections"]["weekly_review"]["dataset_snapshot_id"] == "weekly-2026-06-11"
    assert governance_state["sections"]["weekly_review"]["decision_label"]
