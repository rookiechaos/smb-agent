from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from smbagent.workflow_health import (
    build_workflow_health_report,
    read_workflow_health_report,
    run_due_workflow_checks,
    workflow_check_due,
    write_workflow_health_report,
)
from smbagent.workflow_monitor import update_workflow_monitor


def test_workflow_health_report_is_idle_for_clean_workspace(config, workspace):
    report = build_workflow_health_report(workspace, config)
    assert report.customer_id == workspace.customer_id
    assert report.status == "idle"
    assert report.healthy is True
    assert report.issue_count == 0


def test_workflow_health_report_needs_attention_when_monitor_failed(config, workspace):
    update_workflow_monitor(
        workspace,
        status="failed_tooling",
        active_stage="validation",
        current_round=3,
        detail="Validation failed.",
    )
    report = build_workflow_health_report(workspace, config)
    assert report.status == "needs_attention"
    assert report.healthy is False
    assert report.issue_count >= 1


def test_workflow_check_due_after_interval(config, workspace):
    cfg = replace(config, workflow_check_interval_minutes=10)
    base = datetime.now(UTC)
    write_workflow_health_report(workspace, cfg)
    assert workflow_check_due(workspace, cfg, now=base + timedelta(minutes=11)) is True


def test_run_due_workflow_checks_writes_report(config, workspace):
    reports = run_due_workflow_checks(config, due_only=True)
    assert len(reports) == 1
    saved = read_workflow_health_report(workspace)
    assert saved is not None
    assert saved.customer_id == workspace.customer_id
