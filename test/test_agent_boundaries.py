from __future__ import annotations

import json

from smbagent.agent_boundaries import (
    AGENT_BOUNDARIES,
    COMMUNICATION_LANES,
    build_agent_isolation_status,
    validate_agent_boundary_contract,
    write_agent_isolation_status,
)
from smbagent.launch_readiness import evaluate_launch_readiness


def test_agent_boundary_contract_declares_five_stages_in_order():
    assert [b.agent for b in AGENT_BOUNDARIES] == [
        "Qualify",
        "Negotiation",
        "Plan",
        "Coding",
        "Validation",
    ]
    assert validate_agent_boundary_contract() == []


def test_agent_boundaries_allow_public_rules_but_forbid_private_memory():
    for boundary in AGENT_BOUNDARIES:
        shared = " ".join(boundary.allowed_shared_rules).lower()
        forbidden = " ".join(boundary.forbidden_private_channels).lower()
        assert "tier" in shared or "schema" in shared
        assert "memory" in forbidden
        assert "reasoning" in forbidden
        assert "logs" in forbidden


def test_agent_communication_lanes_are_public_only():
    assert COMMUNICATION_LANES
    for lane in COMMUNICATION_LANES:
        assert lane.public_only is True
        forbidden = " ".join(lane.forbidden_payloads).lower()
        assert "memory" in forbidden
        assert "reasoning" in forbidden


def test_agent_isolation_status_reflects_separate_coding_and_validation(config):
    status = build_agent_isolation_status(config)
    assert status.agents_separate is True
    assert status.communication_lane_count >= 4
    assert status.subprocess_isolation_enabled is False
    assert any("subprocess isolation" in item for item in status.warnings)


def test_agent_isolation_status_accepts_apple_container_provider(config):
    cfg = type(config)(**{**config.__dict__, "subprocess_isolation": "apple-container"})
    status = build_agent_isolation_status(cfg)
    assert status.subprocess_isolation_enabled is True
    assert status.subprocess_isolation_provider == "apple-container"
    assert status.subprocess_isolation_official_apple_container is True
    assert "Apple official container runtime" in status.subprocess_isolation_label
    assert not any("legacy-only" in item for item in status.warnings)


def test_launch_readiness_includes_agent_boundary_contract_and_runtime_isolation(config):
    checks = {c.name: c for c in evaluate_launch_readiness(config)}
    assert checks["five_stage_agent_boundary_contract"].passed is True
    assert checks["five_stage_agent_boundary_contract"].severity == "critical"
    assert checks["agent_runtime_isolation_posture"].passed is False
    assert checks["agent_runtime_isolation_posture"].severity == "major"


def test_write_agent_isolation_status_writes_agent_packs(config, workspace):
    workspace.ensure()
    (workspace.path / "plan_harness_manifest.json").write_text("{}", encoding="utf-8")
    snap = workspace.path / "runs" / "round-1" / "validation_snapshot"
    snap.mkdir(parents=True, exist_ok=True)
    (snap / "snapshot_manifest.json").write_text("{}", encoding="utf-8")

    out = write_agent_isolation_status(config)

    assert out.exists()
    packs_dir = config.root / "ops" / "agent_packs"
    assert (packs_dir / "runtime.json").exists()
    assert (packs_dir / "lanes.json").exists()
    assert (packs_dir / "customers.json").exists()
    customers = json.loads((packs_dir / "customers.json").read_text(encoding="utf-8"))
    assert customers["payload"]["customer_count"] >= 1
    assert customers["payload"]["customers"][0]["customer_id"] == workspace.customer_id


def test_agent_packs_publish_customer_isolation_posture(config, workspace):
    workspace.ensure()
    payload = json.loads(write_agent_isolation_status(config).read_text(encoding="utf-8"))
    assert payload["posture"] == "public-artifact-only communication between separated agents"
