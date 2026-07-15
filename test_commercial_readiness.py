from __future__ import annotations

import json

from typer.testing import CliRunner

from smbagent.cli import app
from smbagent.commercial_readiness import build_commercial_readiness_report, write_launch_notes_snapshot
from smbagent.config import load_config

runner = CliRunner()


def test_commercial_readiness_report_has_intentional_boundaries(config):
    report = build_commercial_readiness_report(config)
    keys = {gate.key: gate for gate in report.intentional_boundaries}
    assert keys["no_automatic_specialist_training"].status == "ready"
    assert keys["no_auto_promotion_into_active_routing"].status == "ready"
    assert keys["no_hidden_autonomy_path"].status == "ready"
    assert keys["no_raw_logs_or_hidden_reasoning_in_training_export"].status == "ready"


def test_commercial_readiness_report_flags_secret_storage_gap(config):
    report = build_commercial_readiness_report(config)
    gates = {gate.key: gate for gate in report.remaining_gates}
    assert gates["managed_secret_storage"].status == "gap"
    assert "local_env" in gates["managed_secret_storage"].detail


def test_commercial_readiness_prefers_apple_container_runtime(config):
    report = build_commercial_readiness_report(
        type(config)(**{**config.__dict__, "subprocess_isolation": "apple-container"})
    )
    gates = {gate.key: gate for gate in report.remaining_gates}
    assert gates["apple_official_container_runtime"].status == "ready"
    assert "Apple official container runtime" in gates["apple_official_container_runtime"].detail


def test_launch_notes_snapshot_writes_json_and_markdown(config):
    json_path, md_path = write_launch_notes_snapshot(config, operator="human:alice", customer_id="acme-co")
    assert json_path.exists()
    assert md_path.exists()
    body = json.loads(json_path.read_text(encoding="utf-8"))
    assert body["operator"] == "human:alice"
    assert body["customer_id"] == "acme-co"
    assert body["smbagent_version"]
    assert "Launch Notes" in md_path.read_text(encoding="utf-8")
    state = json.loads(
        (config.workspaces_dir / "acme-co" / "workspace_state.json").read_text(encoding="utf-8")
    )
    freshness = state["sections"]["artifact_freshness"]["launch_notes"]
    assert freshness["status"] == "fresh"
    assert "ops/launch_notes/acme-co.launch_notes.json" in freshness["artifact_paths"]
    assert "ops/launch_notes/acme-co.launch_notes.md" in freshness["artifact_paths"]
    assert any(
        path.endswith("/launch_notes/acme-co.launch_notes.json") for path in freshness["artifact_paths"]
    )
    assert any(path.endswith("/launch_notes/acme-co.launch_notes.md") for path in freshness["artifact_paths"])
    assert any(path.endswith("/release_record_manifest.json") for path in freshness["artifact_paths"])


def test_launch_notes_snapshot_writes_release_record_manifest(config):
    json_path, _ = write_launch_notes_snapshot(config, operator="human:alice", customer_id="acme-co")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    release_dir = config.root / "ops" / "release_reviews"
    manifests = sorted(release_dir.glob("*/release_record_manifest.json"))
    assert manifests
    manifest = json.loads(manifests[-1].read_text(encoding="utf-8"))
    by_key = {item["key"]: item for item in manifest["artifacts"]}
    assert by_key["launch_notes"]["status"] == "present"
    assert any(
        path.endswith("launch_notes/acme-co.launch_notes.json")
        for path in by_key["launch_notes"]["artifact_paths"]
    )
    assert any(
        path.endswith("launch_notes/acme-co.launch_notes.md")
        for path in by_key["launch_notes"]["artifact_paths"]
    )
    assert by_key["remote_smoke"]["status"] == "reserved"
    assert payload["smbagent_version"] == manifest["smbagent_version"]


def test_commercial_readiness_cli_can_write_reports(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "smbagent").mkdir()
    (tmp_path / "workspaces").mkdir()
    json_out = tmp_path / "ops" / "commercial.json"
    md_out = tmp_path / "ops" / "commercial.md"
    result = runner.invoke(
        app, ["commercial-readiness", "--json-out", str(json_out), "--md-out", str(md_out)]
    )
    assert json_out.exists()
    assert md_out.exists()
    assert "Commercial readiness" in result.stdout


def test_launch_notes_cli_writes_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "smbagent").mkdir()
    (tmp_path / "workspaces").mkdir()
    out_dir = tmp_path / "notes"
    result = runner.invoke(
        app,
        ["launch-notes", "--operator", "human:bob", "--customer-id", "beta-co", "--out-dir", str(out_dir)],
    )
    assert result.exit_code == 0
    assert (out_dir / "beta-co.launch_notes.json").exists()
    assert (out_dir / "beta-co.launch_notes.md").exists()
    release_root = tmp_path / "ops" / "release_reviews"
    assert release_root.exists()


def test_commercial_readiness_detects_ci_wiring():
    report = build_commercial_readiness_report(load_config())
    gates = {gate.key: gate for gate in report.remaining_gates}
    assert gates["ci_backed_trustworthiness_adversarial_suite"].status == "ready"
    assert "ruff" in gates["ci_backed_trustworthiness_adversarial_suite"].detail


def test_commercial_readiness_flags_voice_hardening_gap_by_default(config):
    cfg = type(config)(**{**config.__dict__, "sensitive_mode": True})
    report = build_commercial_readiness_report(cfg)
    gates = {gate.key: gate for gate in report.remaining_gates}
    assert gates["voice_sensitive_mode_hardening"].status == "gap"


def test_commercial_readiness_accepts_onboarding_abuse_controls(config):
    report = build_commercial_readiness_report(config)
    gates = {gate.key: gate for gate in report.remaining_gates}
    assert gates["production_grade_onboarding_abuse_controls"].status == "ready"


def test_commercial_readiness_ci_quality_gates_ready_on_repo():
    report = build_commercial_readiness_report(load_config())
    gates = {gate.key: gate for gate in report.remaining_gates}
    assert gates["ci_lint_and_dependency_audit"].status == "ready"


def test_commercial_readiness_accepts_governed_local_slm_completion_default_off(config):
    report = build_commercial_readiness_report(config)
    gates = {gate.key: gate for gate in report.remaining_gates}
    assert gates["local_slm_completion_governed"].status == "ready"


def test_commercial_readiness_flags_customer_specific_legal_review_gap(config):
    customer = config.workspaces_dir / "clinic-co"
    customer.mkdir(parents=True)
    (customer / "requirements.json").write_text('{"summary_ja":"クリニック 音声"}', encoding="utf-8")
    report = build_commercial_readiness_report(config)
    gates = {gate.key: gate for gate in report.remaining_gates}
    assert gates["customer_specific_legal_review"].status == "gap"
    assert gates["japan_smb_trust_launch_reviews"].status == "gap"
