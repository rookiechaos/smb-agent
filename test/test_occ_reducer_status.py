from __future__ import annotations

import json

from smbagent.occ_reducer_status import build_occ_reducer_status, write_occ_reducer_status
from smbagent.slm.governance_state import SLMGovernanceStateStore
from smbagent.slm.training_registry import default_training_registry_paths
from smbagent.types import Qualification, Tier


def test_write_occ_reducer_status_reports_workspace_fleet_and_slm(config, workspace):
    workspace.save_qualification(
        Qualification(
            customer_id=workspace.customer_id,
            go=True,
            recommended_tier=Tier.GROWTH,
            summary_ja="ok",
        )
    )
    SLMGovernanceStateStore(default_training_registry_paths(config.root / "slm")).reduce_update(
        section="weekly_review",
        patch={"decision_label": "READY"},
        writer="test.weekly_review",
    )
    out = write_occ_reducer_status(config)
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["overall_status"] in {"strong", "growing"}
    keys = {layer["key"] for layer in payload["layers"]}
    assert keys == {"workspace", "fleet", "slm"}
    packs_dir = config.root / "ops" / "occ_packs"
    assert (packs_dir / "workspace.json").exists()
    assert (packs_dir / "fleet.json").exists()
    assert (packs_dir / "slm.json").exists()
    fleet_state = json.loads((config.root / "ops" / "fleet_state.json").read_text(encoding="utf-8"))
    assert fleet_state["sections"]["artifact_freshness"]["occ_reducer_status"]["status"] == "fresh"
    assert (
        "ops/occ_packs/workspace.json"
        in fleet_state["sections"]["artifact_freshness"]["occ_reducer_status"]["artifact_paths"]
    )


def test_build_occ_reducer_status_counts_section_meta(config):
    store = SLMGovernanceStateStore(default_training_registry_paths(config.root / "slm"))
    store.reduce_update(
        section="promotion_lifecycle",
        patch={"status": "pending_review"},
        writer="test.lifecycle",
    )
    status = build_occ_reducer_status(config)
    layer_map = {layer.key: layer for layer in status.layers}
    assert layer_map["slm"].sections_with_meta >= 1
