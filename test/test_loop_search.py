from __future__ import annotations

import json
from dataclasses import replace

from smbagent.adaptive_loop import decide_loop_budget
from smbagent.loop_search import build_loop_search_plan, write_loop_branch_handoff, write_loop_search_plan
from smbagent.observability import UsageLogger
from smbagent.types import Issue, Requirements, Tier, Verdict


def _save_req(workspace, *, tier=Tier.STARTER, skills=1, integrations=0, criteria=1):
    workspace.save_requirements(
        Requirements(
            customer_id=workspace.customer_id,
            tier=tier,
            business_name="Acme",
            summary_ja="テスト",
            target_users=["customer"],
            desired_skills=[f"skill-{i}" for i in range(skills)],
            desired_integrations=[f"integration-{i}" for i in range(integrations)],
            acceptance_criteria=[f"criteria-{i}" for i in range(criteria)],
        )
    )


def test_loop_search_prefers_continue_on_first_round(config, workspace):
    _save_req(workspace)
    decision = decide_loop_budget(config, workspace)
    plan = build_loop_search_plan(config, workspace, decision=decision, round_n=1, prior_verdict=None)
    assert plan.selected_action == "continue"
    assert plan.uses_public_artifacts_only is True
    assert plan.commercially_reliable_scaling is True


def test_loop_search_can_branch_from_best_public_checkpoint(config, workspace):
    _save_req(workspace)
    workspace.save_verdict(
        Verdict(
            passed=False,
            round=1,
            summary="ok-ish",
            issues=[Issue(severity="minor", description="a")],
            tooling_error=None,
        )
    )
    workspace.feedback_path(1).write_text("minor issue", encoding="utf-8")
    workspace.save_verdict(
        Verdict(
            passed=False,
            round=2,
            summary="worse",
            issues=[Issue(severity="critical", description="b")],
            tooling_error=None,
        )
    )
    workspace.feedback_path(2).write_text("critical issue", encoding="utf-8")
    decision = decide_loop_budget(config, workspace)
    prior = workspace.load_verdict(2)
    plan = build_loop_search_plan(config, workspace, decision=decision, round_n=3, prior_verdict=prior)
    assert plan.branch_ready is True
    assert plan.selected_action in {"branch", "escalate"}


def test_loop_search_stops_when_monthly_budget_exhausted(config, workspace):
    _save_req(workspace)
    cfg = replace(config, monthly_api_budget_jpy=100, usd_to_jpy_rate=100.0)
    UsageLogger(workspace).record(
        provider="anthropic",
        surface="api",
        stage="plan",
        input_tokens=500_000,
        output_tokens=100_000,
        total_tokens=600_000,
    )
    decision = decide_loop_budget(cfg, workspace)
    plan = build_loop_search_plan(
        cfg,
        workspace,
        decision=decision,
        round_n=2,
        prior_verdict=Verdict(
            passed=False,
            round=1,
            summary="still failing",
            issues=[Issue(severity="major", description="x")],
            tooling_error=None,
        ),
    )
    assert plan.cost_guard_status == "exhausted"
    assert plan.selected_action == "stop"


def test_loop_search_writes_status_and_branch_handoff(config, workspace):
    _save_req(workspace)
    workspace.save_verdict(
        Verdict(
            passed=False,
            round=1,
            summary="retry",
            issues=[Issue(severity="major", description="x")],
            tooling_error=None,
        )
    )
    workspace.feedback_path(1).write_text("needs fix", encoding="utf-8")
    decision = decide_loop_budget(config, workspace)
    prior = workspace.load_verdict(1)
    plan = build_loop_search_plan(config, workspace, decision=decision, round_n=2, prior_verdict=prior)
    write_loop_search_plan(workspace, plan)
    if plan.selected_action in {"replay", "branch"}:
        write_loop_branch_handoff(workspace, plan)
        assert workspace.loop_branch_for_coding_path(2).exists()
    assert workspace.loop_search_status_path.exists()
    payload = json.loads(workspace.loop_search_status_path.read_text(encoding="utf-8"))
    assert payload["selected_action"] == plan.selected_action
