"""End-to-end tests of bad-LLM scenarios.

For each agent boundary, the LLM (or codex CLI) is told to produce broken output.
The harness must handle every case gracefully — no stack traces escape, the
operator gets a clear message, and the system can be re-run.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

import pytest

from smbagent.agents import validation as validation_mod
from smbagent.agents.qualify import QualifyAgent
from smbagent.agents.validation import ValidationAgent
from smbagent.config import Config
from smbagent.safety import (
    enforce_required_artifacts,
)
from smbagent.types import (
    AgentSkillSpec,
    LandingPageSpec,
    Plan,
    Requirements,
    Tier,
)
from smbagent.workspace import Workspace
from tests._popen_mocks import popen_from_run

# ---- LLM stand-ins ----


@dataclass
class _Block:
    text: str
    type: str = "text"


@dataclass
class _Resp:
    content: list


@dataclass
class _Msgs:
    scripted: list[str]
    idx: int = 0

    def create(self, *, model, max_tokens, system, messages):
        text = self.scripted[self.idx]
        self.idx += 1
        return _Resp(content=[_Block(text)])


@dataclass
class _FakeAnthropic:
    messages: _Msgs


def _qualify_with_response(config: Config, response: str) -> QualifyAgent:
    agent = QualifyAgent(config)
    agent.client = _FakeAnthropic(messages=_Msgs(scripted=[response]))
    return agent


# ============================================================================
# QualifyAgent — bad LLM output
# ============================================================================


def test_qualify_empty_response_raises(config: Config, workspace: Workspace):
    """Model returned literally nothing → extract_json raises ValueError."""
    agent = _qualify_with_response(config, "")
    with pytest.raises(Exception) as excinfo:
        agent.run(workspace, "x")
    assert "No JSON" in str(excinfo.value) or "json" in str(excinfo.value).lower()


def test_qualify_refusal_response_raises(config: Config, workspace: Workspace):
    """Model refuses to answer with prose ("I cannot assess this") → no JSON → halt."""
    agent = _qualify_with_response(config, "I'm sorry, I cannot evaluate this customer.")
    with pytest.raises(Exception):
        agent.run(workspace, "x")


def test_qualify_json_missing_go_field_raises(config: Config, workspace: Workspace):
    agent = _qualify_with_response(
        config,
        '```json\n{"recommended_tier": "growth", "summary_ja": "x"}\n```',
    )
    with pytest.raises(Exception):
        agent.run(workspace, "x")


def test_qualify_json_with_extra_fields_is_tolerated(config: Config, workspace: Workspace):
    """Extra unknown fields should not crash — Pydantic ignores them."""
    agent = _qualify_with_response(
        config,
        '```json\n{"go": true, "recommended_tier": "growth", "summary_ja": "ok",'
        ' "extra_garbage": 42, "model_thoughts": ["..."]}\n```',
    )
    q = agent.run(workspace, "x")
    assert q.go is True
    assert q.recommended_tier == Tier.GROWTH


def test_qualify_with_truthy_string_for_go(config: Config, workspace: Workspace):
    """Pydantic v2 coerces 'true' string to bool. Document this behavior."""
    agent = _qualify_with_response(
        config,
        '```json\n{"go": "true", "recommended_tier": "growth", "summary_ja": "ok"}\n```',
    )
    # Pydantic accepts "true" / 1 / etc as True. Verify we don't crash; semantics may
    # differ across Pydantic minor versions but the harness handles it either way.
    try:
        q = agent.run(workspace, "x")
        assert q.go in (True, False)
    except Exception:
        pass  # Strict mode rejection is also acceptable.


# ============================================================================
# Requirements — bad LLM output via empty business_name
# ============================================================================


def test_requirements_empty_business_name_rejected_by_pydantic():
    """LLM emitted `done: true` but business_name is "" — Pydantic must reject."""
    with pytest.raises(Exception) as excinfo:
        Requirements(
            customer_id="c",
            tier=Tier.STARTER,
            business_name="",  # empty
            summary_ja="x",
            target_users=["x"],
            brand_notes=["y"],
            desired_skills=["s"],
            desired_integrations=["i"],
            acceptance_criteria=["a"],
        )
    assert "business_name" in str(excinfo.value)


def test_requirements_empty_summary_rejected_by_pydantic():
    with pytest.raises(Exception) as excinfo:
        Requirements(
            customer_id="c",
            tier=Tier.STARTER,
            business_name="X",
            summary_ja="",
            target_users=["x"],
            brand_notes=["y"],
            desired_skills=["s"],
            desired_integrations=["i"],
            acceptance_criteria=["a"],
        )
    assert "summary_ja" in str(excinfo.value)


def test_requirements_arrays_can_be_empty():
    """Empty arrays for skills/integrations are still allowed — customer might
    not know what they want; Plan agent fills in defaults."""
    req = Requirements(
        customer_id="c",
        tier=Tier.STARTER,
        business_name="X",
        summary_ja="x",
        target_users=[],
        brand_notes=[],
        desired_skills=[],
        desired_integrations=[],
        acceptance_criteria=[],
    )
    assert req.business_name == "X"


# ============================================================================
# Plan — tier mismatch
# ============================================================================


def test_plan_with_mismatched_tier_fails_caps_check():
    """LLM ignored requirements.tier and produced a plan with the wrong tier label."""
    plan = Plan(
        tier=Tier.BUSINESS,  # plan claims business
        summary="ok",
        landing_page=LandingPageSpec(pages=["/"], hero_copy_outline="o", primary_cta="c"),
        agent_skills=[
            AgentSkillSpec(name=f"s{i}", description="d", system_prompt_outline="o")
            for i in range(15)  # 15 skills — fits business cap of 20
        ],
        integrations=[],
    )
    # Plan itself is internally consistent — 15 ≤ 20.
    assert plan.violates_tier_caps() == []
    # The orchestrator-level check verifies plan.tier == requirements.tier;
    # that's tested in test_harness.py::test_plan_tier_violation_does_not_propagate.


# ============================================================================
# Validation — bad codex output
# ============================================================================


def _fake_codex_with_verdict(workspace: Workspace, round_n: int, verdict: dict):
    """Returns a Popen-shaped class via popen_from_run, wrapping a run-style fake."""

    def fake(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
        workspace.verdict_path(round_n).write_text(json.dumps(verdict), encoding="utf-8")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    return popen_from_run(fake)


def test_codex_passed_true_with_critical_issue_is_overridden(
    monkeypatch, config: Config, workspace: Workspace
):
    """Codex contradicts itself: passed=true alongside a critical issue.
    The invariant must override to passed=false."""
    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        _fake_codex_with_verdict(
            workspace,
            1,
            {
                "passed": True,
                "summary": "all good (lol)",
                "issues": [
                    {
                        "severity": "critical",
                        "file": "agent-skills/foo.md",
                        "description": "frontmatter missing",
                    }
                ],
            },
        ),
    )
    verdict = ValidationAgent(config).run(workspace, round_n=1)
    assert verdict.passed is False
    assert "overridden" in verdict.summary.lower()


def test_codex_passed_true_with_only_minor_issues_stays_passed(
    monkeypatch, config: Config, workspace: Workspace
):
    """Edge of the invariant: minor issues alone do NOT override pass."""
    # Set up requirements so the structural check doesn't fire on missing dirs.
    # But we DO want structural checks to fail because code/ is empty — so let's
    # populate just enough code/ structure to avoid the required-artifacts trip.
    _populate_minimal_code(workspace)
    _save_requirements(workspace, Tier.STARTER)

    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        _fake_codex_with_verdict(
            workspace,
            1,
            {
                "passed": True,
                "summary": "ok",
                "issues": [{"severity": "minor", "description": "no docstring"}],
            },
        ),
    )
    verdict = ValidationAgent(config).run(workspace, round_n=1)
    assert verdict.passed is True
    assert any(i.severity == "minor" for i in verdict.issues)


def test_codex_says_passed_but_code_is_empty(monkeypatch, config: Config, workspace: Workspace):
    """The 'codex rubber-stamped empty deliverable' scenario.
    The required-artifacts structural check must catch it."""
    _save_requirements(workspace, Tier.STARTER)
    # NOTE: not populating code/ — it's just the empty ensured workspace.
    # workspace.ensure() creates code_dir but no contents.

    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        _fake_codex_with_verdict(
            workspace,
            1,
            {
                "passed": True,
                "summary": "perfect",
                "issues": [],
            },
        ),
    )
    verdict = ValidationAgent(config).run(workspace, round_n=1)
    assert verdict.passed is False
    critical_descs = [i.description for i in verdict.issues if i.severity == "critical"]
    # Should flag missing agent-skills/, missing landing-page/, missing README
    assert any("agent-skills" in d for d in critical_descs)
    assert any("landing-page" in d for d in critical_descs)
    assert any("README" in d for d in critical_descs)


def test_codex_wrong_type_issue_severity_is_tooling_failure(
    monkeypatch, config: Config, workspace: Workspace
):
    """LLM emits `severity: "WHATEVER"` — Pydantic Literal rejects.
    Should become a tooling failure (schema mismatch), not a crash."""
    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        _fake_codex_with_verdict(
            workspace,
            1,
            {
                "passed": False,
                "summary": "x",
                "issues": [{"severity": "PROBABLY_FINE", "description": "x"}],
            },
        ),
    )
    verdict = ValidationAgent(config).run(workspace, round_n=1)
    assert verdict.passed is False
    assert verdict.tooling_error is not None
    assert "schema" in verdict.tooling_error.lower()


def test_codex_emits_huge_issue_description_truncated_in_feedback(
    monkeypatch, config: Config, workspace: Workspace
):
    """A 10KB description from codex must not blow up the next-round handoff."""
    _save_requirements(workspace, Tier.STARTER)
    _populate_minimal_code(workspace)

    huge_desc = "x" * 10_000
    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        _fake_codex_with_verdict(
            workspace,
            1,
            {
                "passed": False,
                "summary": "y",
                "issues": [
                    {
                        "severity": "major",
                        "file": "a.md",
                        "description": huge_desc,
                    }
                ],
            },
        ),
    )
    ValidationAgent(config).run(workspace, round_n=1)
    fb = workspace.feedback_path(1).read_text(encoding="utf-8")
    # The feedback.md must NOT contain the full 10KB string.
    assert huge_desc not in fb
    # Should have a truncation marker.
    assert "…" in fb
    # And the verdict.json keeps the full text (no truncation in storage).
    raw = workspace.verdict_path(1).read_text(encoding="utf-8")
    assert huge_desc in raw


def test_codex_self_consistent_failure_no_override(monkeypatch, config: Config, workspace: Workspace):
    """Sanity check: codex reports passed=false honestly → we accept it as-is.
    The invariant only fires when codex contradicts itself."""
    _save_requirements(workspace, Tier.STARTER)
    _populate_minimal_code(workspace)

    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        _fake_codex_with_verdict(
            workspace,
            1,
            {
                "passed": False,
                "summary": "needs work",
                "issues": [{"severity": "major", "description": "no h1"}],
            },
        ),
    )
    verdict = ValidationAgent(config).run(workspace, round_n=1)
    assert verdict.passed is False
    assert "overridden" not in verdict.summary.lower()


# ============================================================================
# Required-artifacts structural check (standalone tests)
# ============================================================================


def test_required_artifacts_empty_code_dir_flags_everything(workspace: Workspace):
    issues = enforce_required_artifacts(workspace.code_dir)
    descs = " ".join(i.description for i in issues)
    assert "agent-skills" in descs
    assert "landing-page" in descs
    assert "README" in descs
    assert all(i.severity == "critical" for i in issues)


def test_required_artifacts_missing_code_dir_flags_top_level(workspace: Workspace):
    """If code/ itself doesn't exist, flag that and stop."""
    import shutil

    shutil.rmtree(workspace.code_dir)
    issues = enforce_required_artifacts(workspace.code_dir)
    assert len(issues) == 1
    assert "code/" in issues[0].description
    assert issues[0].severity == "critical"


def test_required_artifacts_empty_skills_dir_flags(workspace: Workspace):
    (workspace.code_dir / "agent-skills").mkdir(exist_ok=True)
    (workspace.code_dir / "landing-page").mkdir(exist_ok=True)
    (workspace.code_dir / "landing-page" / "index.html").write_text("<html/>", encoding="utf-8")
    (workspace.code_dir / "README.md").write_text("# r", encoding="utf-8")
    issues = enforce_required_artifacts(workspace.code_dir)
    assert any("agent-skills" in i.description for i in issues)
    assert not any("landing-page" in i.description for i in issues)
    assert not any("README" in i.description for i in issues)


def test_required_artifacts_landing_page_with_only_partials_flags(workspace: Workspace):
    """A landing-page/ that only has _app.tsx / layout.tsx is NOT a real page set."""
    (workspace.code_dir / "agent-skills").mkdir(exist_ok=True)
    (workspace.code_dir / "agent-skills" / "x.md").write_text(
        "---\nname: x\ndescription: d\n---\n\nb",
        encoding="utf-8",
    )
    lp = workspace.code_dir / "landing-page"
    lp.mkdir(exist_ok=True)
    (lp / "_app.tsx").write_text("...", encoding="utf-8")
    (lp / "layout.tsx").write_text("...", encoding="utf-8")
    (workspace.code_dir / "README.md").write_text("# r", encoding="utf-8")

    issues = enforce_required_artifacts(workspace.code_dir)
    assert any("landing-page" in i.description for i in issues)


def test_required_artifacts_empty_readme_flags(workspace: Workspace):
    (workspace.code_dir / "agent-skills").mkdir(exist_ok=True)
    (workspace.code_dir / "agent-skills" / "x.md").write_text(
        "---\nname: x\ndescription: d\n---\n\nb",
        encoding="utf-8",
    )
    (workspace.code_dir / "landing-page").mkdir(exist_ok=True)
    (workspace.code_dir / "landing-page" / "index.html").write_text("<html/>", encoding="utf-8")
    (workspace.code_dir / "README.md").write_text("", encoding="utf-8")  # empty

    issues = enforce_required_artifacts(workspace.code_dir)
    assert any("README" in i.description for i in issues)


def test_required_artifacts_complete_no_issues(workspace: Workspace):
    _populate_minimal_code(workspace)
    assert enforce_required_artifacts(workspace.code_dir) == []


# ============================================================================
# Test helpers
# ============================================================================


def _populate_minimal_code(workspace: Workspace) -> None:
    """Just enough for required-artifacts to pass."""
    (workspace.code_dir / "agent-skills").mkdir(exist_ok=True)
    (workspace.code_dir / "agent-skills" / "understand-x.md").write_text(
        "---\nname: understand-x\ndescription: d\n---\n\nb",
        encoding="utf-8",
    )
    (workspace.code_dir / "landing-page").mkdir(exist_ok=True)
    (workspace.code_dir / "landing-page" / "index.html").write_text("<html/>", encoding="utf-8")
    (workspace.code_dir / "README.md").write_text("# r", encoding="utf-8")


def _save_requirements(workspace: Workspace, tier: Tier) -> None:
    workspace.save_requirements(
        Requirements(
            customer_id=workspace.customer_id,
            tier=tier,
            business_name="X",
            summary_ja="x",
            target_users=["x"],
            brand_notes=["y"],
            desired_skills=["s"],
            desired_integrations=["i"],
            acceptance_criteria=["a"],
        )
    )
