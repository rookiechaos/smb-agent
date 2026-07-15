from __future__ import annotations

from smbagent.annealing import (
    AnnealingPhase,
    AnnealingTemps,
    compute_annealing,
    detect_deadlock,
    issue_fingerprint,
    temperature_prompt_section,
)
from smbagent.types import Issue, Verdict
from smbagent.workspace import Workspace


def test_round_one_is_creative(config, workspace: Workspace):
    state = compute_annealing(
        1,
        max_rounds=5,
        consecutive_failures=0,
        deadlock=False,
        temps=AnnealingTemps(),
    )
    assert state.phase == AnnealingPhase.CREATIVE
    assert state.temperature == 0.7
    assert state.is_final_resolution is False


def test_deadlock_after_two_failures_lowers_temperature(config, workspace: Workspace):
    issue = Issue(severity="critical", file="a.ts", description="same bug")
    for r in (1, 2):
        v = Verdict(passed=False, round=r, summary=f"fail {r}", issues=[issue])
        workspace.save_verdict(v)
        workspace.feedback_path(r).write_text("x", encoding="utf-8")

    assert detect_deadlock(workspace, through_round=2, stale_round_threshold=2)

    state = compute_annealing(
        3,
        max_rounds=5,
        consecutive_failures=2,
        deadlock=True,
        temps=AnnealingTemps(),
        stale_round_threshold=2,
    )
    assert state.phase == AnnealingPhase.CONVERGENCE
    assert state.temperature == 0.3


def test_final_round_forces_zero_temperature(config, workspace: Workspace):
    state = compute_annealing(
        5,
        max_rounds=5,
        consecutive_failures=4,
        deadlock=True,
        temps=AnnealingTemps(),
    )
    assert state.phase == AnnealingPhase.FINAL
    assert state.temperature == 0.0
    assert state.is_final_resolution is True


def test_repeated_summary_triggers_deadlock(config, workspace: Workspace):
    for r in (1, 2):
        workspace.save_verdict(Verdict(passed=False, round=r, summary="identical summary", issues=[]))
    assert detect_deadlock(workspace, through_round=2)


def test_temperature_section_mentions_target(config):
    state = compute_annealing(
        1,
        max_rounds=3,
        consecutive_failures=0,
        deadlock=False,
    )
    section = temperature_prompt_section(state)
    assert "0.7" in section
    assert "creative" in section


def test_issue_fingerprint_stable():
    a = Issue(severity="major", file="x", description="hello world")
    b = Issue(severity="major", file="x", description="hello world")
    assert issue_fingerprint(a) == issue_fingerprint(b)
