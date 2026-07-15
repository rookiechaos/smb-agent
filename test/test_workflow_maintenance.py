from __future__ import annotations

import json

from smbagent.workflow_maintenance import write_maintenance_report


def test_write_maintenance_report_publishes_artifact_freshness(workspace):
    out = write_maintenance_report(workspace)
    assert out.exists()
    state = json.loads(workspace.workspace_state_path.read_text(encoding="utf-8"))
    freshness = state["sections"]["artifact_freshness"]["maintenance_report"]
    assert freshness["artifact_paths"] == ["maintenance_report.json"]
    assert freshness["status"] in {"ok", "needs_attention"}
    assert "maintenance issue" in freshness["detail"]
