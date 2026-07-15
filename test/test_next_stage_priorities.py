from __future__ import annotations

import json

from typer.testing import CliRunner

from smbagent.cli import app
from smbagent.next_stage_priorities import (
    build_next_stage_priorities_summary,
    write_next_stage_priorities_summary,
    write_priority_packs,
)

runner = CliRunner()


def test_build_next_stage_priorities_summary_returns_six_areas(config, workspace):
    summary = build_next_stage_priorities_summary(config)
    assert summary.posture == "single-tenant Mac mini supervised backend"
    assert len(summary.areas) == 6
    assert isinstance(summary.action_queue, list)
    keys = {area.key for area in summary.areas}
    assert keys == {
        "workflow_operating_system",
        "deliverable_system",
        "decision_support",
        "closed_loop_improvement",
        "trust_evidence",
        "service_model",
    }


def test_write_next_stage_priorities_summary_persists_json_and_fleet_freshness(config, workspace):
    out = write_next_stage_priorities_summary(config)
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["posture"] == "single-tenant Mac mini supervised backend"
    assert len(payload["areas"]) == 6
    packs_dir = config.root / "ops" / "priority_packs"
    assert packs_dir.exists()
    pack_files = sorted(p.name for p in packs_dir.glob("*.json"))
    assert len(pack_files) == 7
    assert "loop_maturity.json" in pack_files
    assert "workflow_operating_system.json" in pack_files
    state = json.loads((config.root / "ops" / "fleet_state.json").read_text(encoding="utf-8"))
    freshness = state["sections"]["artifact_freshness"]["next_stage_priorities"]
    assert freshness["status"] == "fresh"
    assert "ops/next_stage_priorities.json" in freshness["artifact_paths"]
    assert "ops/priority_packs/workflow_operating_system.json" in freshness["artifact_paths"]
    assert "ops/priority_packs/loop_maturity.json" in freshness["artifact_paths"]


def test_build_next_stage_priorities_summary_collects_action_queue(config, workspace):
    summary = build_next_stage_priorities_summary(config)
    area_map = {area.key: area for area in summary.areas}
    assert area_map["deliverable_system"].action_queue
    assert any(action.severity == "critical" for action in summary.action_queue)
    assert summary.action_queue[0].title.startswith("Review loop posture for")
    assert summary.action_queue[0].action_family == "loop_posture"
    assert summary.action_queue[0].priority_class == "attention_customer"


def test_closed_loop_improvement_includes_loop_maturity_metrics(config, workspace):
    summary = build_next_stage_priorities_summary(config)
    area = next(area for area in summary.areas if area.key == "closed_loop_improvement")
    assert "loop_mature_customers" in area.metrics
    assert "loop_growing_customers" in area.metrics
    assert "loop_attention_customers" in area.metrics


def test_write_priority_packs_outputs_one_file_per_area(config, workspace):
    summary = build_next_stage_priorities_summary(config)
    written = write_priority_packs(summary, config.root / "ops" / "priority_packs", config=config)
    assert len(written) == 7
    payload = json.loads(written[0].read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["posture"] == "single-tenant Mac mini supervised backend"
    assert payload["area"]["key"]
    assert isinstance(payload["global_action_queue"], list)
    loop_pack = json.loads(
        (config.root / "ops" / "priority_packs" / "loop_maturity.json").read_text(encoding="utf-8")
    )
    assert loop_pack["schema_version"] == 1
    assert isinstance(loop_pack["customers"], list)
    if loop_pack["customers"]:
        first = loop_pack["customers"][0]
        assert first["attention_control_count"] >= 0


def test_next_stage_summary_cli_writes_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "smbagent").mkdir()
    (tmp_path / "workspaces").mkdir()
    out_dir = tmp_path / "ops"
    result = runner.invoke(app, ["next-stage-summary", "--out-dir", str(out_dir)])
    assert result.exit_code == 0
    assert (out_dir / "next_stage_priorities.json").exists()
    assert (out_dir / "priority_packs" / "workflow_operating_system.json").exists()
    assert (out_dir / "priority_packs" / "loop_maturity.json").exists()
    assert "Wrote next-stage priorities" in result.stdout
    assert "Wrote priority packs" in result.stdout


def test_write_priority_packs_uses_config_root_for_loop_pack(config, workspace, tmp_path):
    summary = build_next_stage_priorities_summary(config)
    out_dir = tmp_path / "exports" / "nightly" / "priority_packs"
    written = write_priority_packs(summary, out_dir, config=config)
    assert len(written) == 7
    loop_pack = json.loads((out_dir / "loop_maturity.json").read_text(encoding="utf-8"))
    customer_ids = [item["customer_id"] for item in loop_pack["customers"]]
    assert workspace.customer_id in customer_ids
