from __future__ import annotations

import json

import smbagent.runtime.workflows as workflows_module
from smbagent.runtime.workflows import WorkflowExecutor, WorkflowKind


def test_workflow_dispatch_records_slm_advisory_event(config, workspace, monkeypatch):
    monkeypatch.setattr(
        workflows_module,
        "get_workflow_dispatch_slm_advisory",
        lambda cfg, ws, **kwargs: {  # noqa: ARG005
            "workflow_family": "ikida_gps",
            "task_class": "gps_analysis",
            "risk_band": "medium",
            "hitl_recommended": False,
            "loop_action": None,
            "confidence": 0.83,
            "reasons_public": ["queued task matched GPS workflow"],
            "backend": "sglang",
            "model_name": "qwen3.5-2b",
        },
    )
    executor = WorkflowExecutor(workspace, config=config)
    executor.submit(kind=WorkflowKind.ANALYSIS, title="gps summary", payload={"summary": "today"})

    result = executor.run_next()

    assert result is not None
    assert result.status == "completed"
    advisory_log = workspace.path / "slm_advisory.jsonl"
    events = [json.loads(line) for line in advisory_log.read_text(encoding="utf-8").splitlines()]
    event = next(ev for ev in events if ev["stage"] == "workflow_dispatch")
    assert event["applied"] is True
    assert event["workflow_family"] == "ikida_gps"
    assert event["task_class"] == "gps_analysis"
