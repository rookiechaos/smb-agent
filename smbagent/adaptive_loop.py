"""Adaptive coding-validation loop budget.

The loop should not be hard-coded to "try N times" for every customer. This
module combines current benchmark policy, task complexity, prior local loop
memory, and current cost pressure to choose a conservative per-run budget under
the operator's hard cap.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .coding_benchmarks import BENCHMARK_POLICY_VERSION, PRIMARY_CODING_BENCHMARKS
from .config import Config
from .observability import LoopMemoryLogger, summarize_monthly_api_cost
from .workspace import Workspace


@dataclass(frozen=True)
class AdaptiveLoopDecision:
    enabled: bool
    round_budget: int
    hard_cap: int
    complexity_score: int
    benchmark_policy_version: str
    reason: str
    monthly_api_budget_percent: int
    cost_guard_status: str


def decide_loop_budget(config: Config, workspace: Workspace) -> AdaptiveLoopDecision:
    hard_cap = max(1, min(config.max_rounds, config.adaptive_max_rounds))
    complexity = _complexity_score(workspace)
    cost_summary = summarize_monthly_api_cost(workspace, config)
    budget_percent = cost_summary.monthly_api_budget_percent
    cost_guard_status = _cost_guard_status(budget_percent)
    if not config.adaptive_loop_enabled:
        return AdaptiveLoopDecision(
            enabled=False,
            round_budget=config.max_rounds,
            hard_cap=config.max_rounds,
            complexity_score=complexity,
            benchmark_policy_version=BENCHMARK_POLICY_VERSION,
            reason="adaptive loop disabled; using SMBAGENT_MAX_ROUNDS",
            monthly_api_budget_percent=budget_percent,
            cost_guard_status=cost_guard_status,
        )

    base = 2
    if complexity >= 4:
        base += 1
    if complexity >= 8:
        base += 1
    if complexity >= 14:
        base += 2

    benchmark_adjustment = _benchmark_adjustment()
    history_adjustment, history_reason = _history_adjustment(workspace)
    cost_adjustment, cost_reason = _cost_adjustment(budget_percent)
    raw_budget = base + benchmark_adjustment + history_adjustment + cost_adjustment
    min_rounds = min(max(1, config.adaptive_min_rounds), hard_cap)
    budget = min(hard_cap, max(min_rounds, raw_budget))
    reason = (
        f"complexity={complexity}, base={base}, "
        f"benchmark_adjustment={benchmark_adjustment}, "
        f"history_adjustment={history_adjustment} ({history_reason}), "
        f"cost_adjustment={cost_adjustment} ({cost_reason}), "
        f"bounded=[{min_rounds}, {hard_cap}]"
    )
    return AdaptiveLoopDecision(
        enabled=True,
        round_budget=budget,
        hard_cap=hard_cap,
        complexity_score=complexity,
        benchmark_policy_version=BENCHMARK_POLICY_VERSION,
        reason=reason,
        monthly_api_budget_percent=budget_percent,
        cost_guard_status=cost_guard_status,
    )


def _complexity_score(workspace: Workspace) -> int:
    if not workspace.requirements_path.exists():
        return 3
    try:
        req = workspace.load_requirements()
    except Exception:
        return 3
    tier_weight = {"starter": 0, "growth": 2, "business": 5}.get(req.tier.value, 2)
    return (
        tier_weight
        + len(req.desired_skills)
        + 2 * len(req.desired_integrations)
        + len(req.acceptance_criteria)
        + min(len(req.target_users), 3)
    )


def _benchmark_adjustment() -> int:
    roles = {b.role for b in PRIMARY_CODING_BENCHMARKS}
    adjustment = 0
    if "terminal_agent_execution" in roles:
        adjustment += 1
    if "primary_agentic_software_engineering" in roles:
        adjustment += 1
    return adjustment


def _history_adjustment(workspace: Workspace) -> tuple[int, str]:
    loop_events = LoopMemoryLogger(workspace).read_all()[-20:]
    if not loop_events:
        return _failure_memory_adjustment(workspace)
    exhausted = sum(1 for e in loop_events if e.outcome in {"failed_max_rounds", "budget_exhausted"})
    passed = [e for e in loop_events if e.outcome == "passed" and e.rounds_used is not None]
    high_round_passes = sum(1 for e in passed if (e.rounds_used or 0) >= max(3, e.round_budget - 1))
    low_round_passes = sum(1 for e in passed if (e.rounds_used or 0) <= 2)
    if exhausted:
        return min(3, exhausted), f"{exhausted} recent loop exhaustion event(s)"
    if high_round_passes >= 2:
        return 1, f"{high_round_passes} recent passes used almost full budget"
    if low_round_passes >= 5:
        return -1, f"{low_round_passes} recent passes completed in <=2 rounds"
    return 0, f"{len(loop_events)} loop event(s), no budget pressure"


def _failure_memory_adjustment(workspace: Workspace) -> tuple[int, str]:
    path = workspace.path / "failure_memory.jsonl"
    if not path.exists():
        return 0, "no loop or failure history"
    outcomes: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-20:]:
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        outcome = str(data.get("outcome", ""))
        if outcome:
            outcomes.append(outcome)
    exhausted = sum(1 for o in outcomes if o == "failed_max_rounds")
    failed_verdicts = sum(1 for o in outcomes if o == "failed_verdict")
    if exhausted:
        return min(3, exhausted), f"{exhausted} prior max-round exhaustion event(s)"
    if failed_verdicts >= 3:
        return 1, f"{failed_verdicts} prior failed verdict event(s)"
    return 0, "failure history has no budget pressure"


def _cost_adjustment(budget_percent: int) -> tuple[int, str]:
    if budget_percent >= 100:
        return -2, "monthly API budget exhausted"
    if budget_percent >= 90:
        return -1, "monthly API budget in high-pressure zone"
    if budget_percent <= 30:
        return 0, "cost pressure low"
    return 0, "cost pressure acceptable"


def _cost_guard_status(budget_percent: int) -> str:
    if budget_percent >= 100:
        return "exhausted"
    if budget_percent >= 90:
        return "high"
    if budget_percent >= 70:
        return "watch"
    return "low"
