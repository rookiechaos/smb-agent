from __future__ import annotations

from dataclasses import replace

from smbagent.adaptive_loop import decide_loop_budget
from smbagent.observability import LoopMemoryLogger
from smbagent.types import Requirements, Tier


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


def test_adaptive_loop_disabled_uses_hard_max(config, workspace):
    _save_req(workspace)
    cfg = replace(config, adaptive_loop_enabled=False, max_rounds=5)
    decision = decide_loop_budget(cfg, workspace)
    assert decision.enabled is False
    assert decision.round_budget == 5
    assert decision.monthly_api_budget_percent >= 0


def test_adaptive_loop_gives_complex_tasks_more_budget(config, workspace):
    _save_req(workspace, tier=Tier.BUSINESS, skills=8, integrations=3, criteria=4)
    cfg = replace(config, adaptive_loop_enabled=True, max_rounds=12, adaptive_max_rounds=12)
    decision = decide_loop_budget(cfg, workspace)
    assert decision.enabled is True
    assert decision.round_budget > cfg.adaptive_min_rounds
    assert decision.round_budget <= 12


def test_adaptive_loop_learns_from_recent_loop_exhaustion(config, workspace):
    _save_req(workspace, skills=1, integrations=0, criteria=1)
    cfg = replace(config, adaptive_loop_enabled=True, max_rounds=8, adaptive_max_rounds=8)
    baseline = decide_loop_budget(cfg, workspace)
    LoopMemoryLogger(workspace).record(
        outcome="failed_max_rounds",
        rounds_used=baseline.round_budget,
        round_budget=baseline.round_budget,
        complexity_score=baseline.complexity_score,
        benchmark_policy_version=baseline.benchmark_policy_version,
        adaptive_reason=baseline.reason,
        tuning={},
    )
    learned = decide_loop_budget(cfg, workspace)
    assert learned.round_budget > baseline.round_budget
    assert "loop exhaustion" in learned.reason


def test_adaptive_loop_cost_pressure_can_reduce_budget(config, workspace):
    _save_req(workspace, skills=4, integrations=1, criteria=2)
    from smbagent.observability import UsageLogger

    UsageLogger(workspace).record(
        provider="anthropic",
        surface="api",
        stage="plan",
        input_tokens=500_000,
        output_tokens=100_000,
        total_tokens=600_000,
    )
    rich_cfg = replace(
        config,
        adaptive_loop_enabled=True,
        max_rounds=10,
        adaptive_max_rounds=10,
        monthly_api_budget_jpy=100,
        usd_to_jpy_rate=100.0,
    )
    decision = decide_loop_budget(rich_cfg, workspace)
    assert decision.cost_guard_status in {"high", "exhausted"}
