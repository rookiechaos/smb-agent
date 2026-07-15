from __future__ import annotations

from dataclasses import replace

from smbagent.observability.alerts import AlertHook
from smbagent.portal import render_monitor
from smbagent.runtime.workflows import WorkflowExecutor, WorkflowKind
from smbagent.workflow_circuit_breaker import (
    read_workflow_circuit_breaker_state,
    reset_workflow_circuit_breaker,
)
from smbagent.workflow_health import build_workflow_health_report
from smbagent.workflow_maintenance import build_maintenance_report


def test_workflow_circuit_breaker_default_disabled(config, workspace):
    executor = WorkflowExecutor(workspace, config=config)
    executor.submit(kind=WorkflowKind.ANALYSIS, title="ok", payload={"summary": "x"})
    result = executor.run_next()
    assert result is not None

    state = read_workflow_circuit_breaker_state(workspace)
    assert state is not None
    assert state.enabled is False
    assert state.open is False
    assert state.status == "disabled"


def test_workflow_circuit_breaker_opens_after_repeated_failures(config, workspace):
    cfg = replace(
        config,
        workflow_circuit_breaker_enabled=True,
        workflow_circuit_breaker_consecutive_failures=2,
        workflow_circuit_breaker_failures_in_window=10,
    )
    alert_hook = AlertHook(None)
    executor = WorkflowExecutor(workspace, config=cfg, alert_hook=alert_hook)

    executor.submit(kind="mystery", title="bad one")
    first = executor.run_next()
    assert first is not None
    assert first.status == "failed"

    executor.submit(kind="mystery", title="bad two")
    second = executor.run_next()
    assert second is not None
    assert second.status == "failed"

    state = read_workflow_circuit_breaker_state(workspace)
    assert state is not None
    assert state.enabled is True
    assert state.open is True
    assert state.status == "open"
    assert state.consecutive_failures >= 2
    assert alert_hook.fired
    assert alert_hook.fired[-1].event == "workflow_circuit_breaker_open"

    executor.submit(kind=WorkflowKind.ANALYSIS, title="would have run", payload={"summary": "x"})
    blocked_by_breaker = executor.run_next()
    assert blocked_by_breaker is None


def test_workflow_circuit_breaker_reset_rearms_future_runs(config, workspace):
    cfg = replace(
        config,
        workflow_circuit_breaker_enabled=True,
        workflow_circuit_breaker_consecutive_failures=1,
        workflow_circuit_breaker_failures_in_window=10,
    )
    executor = WorkflowExecutor(workspace, config=cfg)
    executor.submit(kind="mystery", title="bad one")
    failed = executor.run_next()
    assert failed is not None
    assert failed.status == "failed"

    open_state = read_workflow_circuit_breaker_state(workspace)
    assert open_state is not None and open_state.open is True

    reset_state = reset_workflow_circuit_breaker(workspace, cfg, reason="operator reviewed and fixed payload")
    assert reset_state.open is False

    executor.submit(kind=WorkflowKind.ANALYSIS, title="good one", payload={"summary": "done"})
    result = executor.run_next()
    assert result is not None
    assert result.status == "completed"

    final_state = read_workflow_circuit_breaker_state(workspace)
    assert final_state is not None
    assert final_state.open is False
    assert final_state.status == "closed"


def test_workflow_circuit_breaker_surfaces_in_health_maintenance_and_monitor(config, workspace):
    cfg = replace(
        config,
        workflow_circuit_breaker_enabled=True,
        workflow_circuit_breaker_consecutive_failures=1,
        workflow_circuit_breaker_failures_in_window=10,
    )
    executor = WorkflowExecutor(workspace, config=cfg)
    executor.submit(kind="mystery", title="bad one")
    result = executor.run_next()
    assert result is not None
    assert result.status == "failed"

    maintenance = build_maintenance_report(workspace)
    assert maintenance.status == "needs_attention"
    assert any(item.source == "workflow_circuit_breaker" for item in maintenance.issues)

    health = build_workflow_health_report(workspace, cfg)
    assert health.status == "needs_attention"
    assert health.circuit_breaker_open is True
    assert health.circuit_breaker_status == "open"

    html = render_monitor(workspace)
    assert "paused for safety" in html
    assert "Needs attention" in html
