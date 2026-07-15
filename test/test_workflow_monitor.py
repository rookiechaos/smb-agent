from __future__ import annotations

from smbagent.approvals import OperatorApprovalLog
from smbagent.customer_readiness import write_customer_legal_review, write_japan_trust_launch_review
from smbagent.observability import TransitionLogger, UsageLogger
from smbagent.portal import render_monitor
from smbagent.workflow_health import write_workflow_health_report
from smbagent.workflow_monitor import (
    build_owner_surface,
    build_owner_team_view,
    build_workflow_monitor_view,
    update_workflow_monitor,
)


def test_workflow_monitor_view_renders_runtime_status(workspace):
    update_workflow_monitor(
        workspace,
        status="running",
        active_stage="coding",
        current_round=2,
        detail="Implementing validation feedback.",
    )
    TransitionLogger(workspace).record(
        agent="coding",
        from_state="validating_round_1",
        to_state="coding_round_2",
        input_hash="a",
        output_hash="b",
        latency_ms=123,
        round_n=2,
    )
    UsageLogger(workspace).record(
        provider="anthropic",
        surface="api",
        stage="plan",
        model="claude-opus-4-7",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    view = build_workflow_monitor_view(workspace)
    assert view.status == "running"
    assert view.active_stage == "coding"
    assert view.current_round == 2
    assert view.usage_total_tokens == 2_000_000
    assert view.monthly_api_budget_percent == 15
    assert "本日は現在 Coding round 2 を進めています。" in view.daily_summary_ja
    owner_surface = build_owner_surface(view)
    assert owner_surface.status_label == "Running"
    assert owner_surface.status_tone == "running"
    assert "currently in coding round 2" in owner_surface.boss_summary_en
    assert "5項目中" in owner_surface.loop_summary_ja or "bounded loops" in owner_surface.loop_summary_ja
    team = build_owner_team_view(view)
    by_name = {member.code_name: member for member in team}
    assert by_name["Shin"].status == "running"
    assert by_name["Sora"].status == "waiting"

    html = render_monitor(workspace)
    assert "Workflow monitor" in html
    assert "monitor-logout" in html
    assert "ログアウト" in html
    assert "Running" in html
    assert "AI team is on duty" in html
    assert "Daily summary" in html
    assert "Loop control" in html
    assert "Trust surface" in html
    assert "ループ統制" in html
    assert "currently in coding round 2" in html
    assert "API budget this month" in html
    assert "15%" in html
    assert "本日の AI チーム" in html
    assert "Shin" in html
    assert "Minato" in html


def test_workflow_monitor_defaults_to_idle(workspace):
    view = build_workflow_monitor_view(workspace)
    owner_surface = build_owner_surface(view)
    assert view.status == "idle"
    assert owner_surface.status_label == "Waiting"
    html = render_monitor(workspace)
    assert "Waiting" in html


def test_workflow_monitor_renders_framework_health_check(config, workspace):
    write_workflow_health_report(workspace, config)
    html = render_monitor(workspace)
    assert "Framework check" in html
    assert "Last checked" in html


def test_workflow_monitor_maps_failed_state_to_needs_attention(workspace):
    update_workflow_monitor(
        workspace,
        status="failed_tooling",
        active_stage="validation",
        current_round=4,
        detail="Codex validation needs operator review.",
    )
    view = build_workflow_monitor_view(workspace)
    owner_surface = build_owner_surface(view)
    team = build_owner_team_view(view)
    by_name = {member.code_name: member for member in team}
    assert by_name["Shin"].status == "attention"
    assert by_name["Sora"].status == "attention"
    assert owner_surface.status_label == "Needs attention"
    html = render_monitor(workspace)
    assert "Needs attention" in html
    assert "needs operator attention" in html
    assert "要確認" in html


def test_workflow_monitor_shows_pending_approval_and_budget_alerts(workspace):
    update_workflow_monitor(
        workspace,
        status="running",
        active_stage="validation",
        current_round=1,
        detail="Awaiting approval.",
    )
    UsageLogger(workspace).record(
        provider="anthropic",
        surface="api",
        stage="plan",
        model="claude-opus-4-7",
        input_tokens=8_000_000,
        output_tokens=4_000_000,
    )
    OperatorApprovalLog(workspace).record_decision(
        action="send_email",
        resource="customer=acme",
        decision="approved",
        operator="alice",
        reason="ok",
    )
    view = build_workflow_monitor_view(workspace)
    assert view.pending_approval_count == 1
    assert any(alert.key == "approval_pending" for alert in view.owner_alerts)
    assert any(alert.key == "budget_high" for alert in view.owner_alerts)

    html = render_monitor(workspace)
    assert "Proactive reminders" in html
    assert "承認待ち" in html
    assert "月次 API 利用率が高め" in html


def test_workflow_monitor_shows_loop_search_reason_and_customer_reviews(workspace, config):
    workspace.loop_search_status_path.write_text(
        '{"selected_action":"branch","selected_source_round":2,"selected_reason":"Branch from the strongest public checkpoint after a worse latest round.","cost_guard_status":"watch"}',
        encoding="utf-8",
    )
    write_customer_legal_review(
        workspace,
        operator="human:alice",
        purpose_of_use="gps analysis",
        data_categories=["gps", "employee"],
        retention_summary="30 days",
        access_summary="owner only",
        external_actions_hitl=True,
        approved=True,
        approval_note="ok",
    )
    (workspace.path / "japan_trust_launch_note.md").write_text("note", encoding="utf-8")
    (workspace.path / "customer_ai_use_policy_ja.md").write_text("policy", encoding="utf-8")
    (workspace.path / "employee_data_notice_ja.md").write_text("employee", encoding="utf-8")
    (workspace.path / "gps_analysis_notice_ja.md").write_text("gps", encoding="utf-8")
    write_japan_trust_launch_review(
        workspace,
        operator="human:alice",
        workflow_categories=["gps", "employee"],
        sensitive_mode=config.sensitive_mode,
        human_approval_required=True,
        approved=True,
        approval_note="ok",
    )
    update_workflow_monitor(
        workspace, status="running", active_stage="validation", current_round=3, detail="branching"
    )
    view = build_workflow_monitor_view(workspace)
    assert view.latest_loop_search_action == "branch"
    assert view.legal_review_ready is True
    assert view.trust_launch_ready is True
    owner_surface = build_owner_surface(view)
    assert "理由" in owner_surface.loop_decision_ja
    html = render_monitor(workspace)
    assert "Why this AI loop continued / stopped / branched" in html
    assert "Branch from the strongest public checkpoint" in html
