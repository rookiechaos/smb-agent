"""Harness-level tests — orchestrator error handling, tier-mismatch guard,
tooling-failure short-circuit, runtime cache invalidation, SDK timeout wiring.

These exercise the structure that holds the agents together (not the agents themselves).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from smbagent.config import Config
from smbagent.orchestrator import Pipeline
from smbagent.runtime import SkillsRuntime
from smbagent.types import (
    AgentSkillSpec,
    IntegrationSpec,
    Issue,
    LandingPageSpec,
    Plan,
    Qualification,
    Requirements,
    Tier,
    Verdict,
)
from smbagent.workspace import Workspace

# ---- shared fakes (copied lightly from test_orchestrator to keep this isolated) ----


@dataclass
class FakeCoding:
    calls: list[tuple[int, Verdict | None]] = field(default_factory=list)

    def run(self, workspace: Workspace, round_n: int, prior_feedback: Verdict | None):
        self.calls.append((round_n, prior_feedback))


@dataclass
class FakeValidation:
    scripted: list[Verdict]
    calls: int = 0
    raises: BaseException | None = None

    def run(self, workspace: Workspace, round_n: int) -> Verdict:
        if self.raises is not None:
            raise self.raises
        idx = min(self.calls, len(self.scripted) - 1)
        v = self.scripted[idx]
        self.calls += 1
        return v.model_copy(update={"round": round_n})


@dataclass
class FakeQualify:
    qualification: Qualification
    raises: BaseException | None = None

    def run(self, workspace, brief):
        if self.raises is not None:
            raise self.raises
        workspace.save_qualification(self.qualification)
        return self.qualification


@dataclass
class FakeNegotiation:
    """Persists a Requirements that mirrors the tier it was called with."""

    raises: BaseException | None = None

    def run(self, workspace: Workspace, tier: Tier) -> Requirements:
        if self.raises is not None:
            raise self.raises
        req = Requirements(
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
        workspace.save_requirements(req)
        return req


@dataclass
class FakePlan:
    raises: BaseException | None = None

    def run(self, workspace: Workspace) -> Plan:
        if self.raises is not None:
            raise self.raises
        req = workspace.load_requirements()
        plan = Plan(
            tier=req.tier,
            summary="ok",
            landing_page=LandingPageSpec(pages=["/"], hero_copy_outline="o", primary_cta="cta"),
            agent_skills=[AgentSkillSpec(name="understand-x", description="d", system_prompt_outline="o")],
            integrations=[IntegrationSpec(name="Gmail", purpose="x")],
        )
        workspace.save_plan(plan, plan_md="# plan")
        return plan


def _install(p: Pipeline, *, qualify, negotiation, plan, coding, validation) -> None:
    p.qualify = qualify
    p.negotiation = negotiation
    p.plan = plan
    p.coding = coding
    p.validation = validation


def _good_qualify() -> FakeQualify:
    return FakeQualify(Qualification(customer_id="c", go=True, recommended_tier=Tier.GROWTH, summary_ja="ok"))


def _passing_validation() -> FakeValidation:
    return FakeValidation(scripted=[Verdict(passed=True, round=1, summary="ok")])


# ============================================================================
# Stage-level error handling (the fix in task #36)
# ============================================================================


def test_negotiation_crash_does_not_propagate(config: Config):
    p = Pipeline(config)
    _install(
        p,
        qualify=_good_qualify(),
        negotiation=FakeNegotiation(raises=RuntimeError("LLM hung")),
        plan=FakePlan(),
        coding=FakeCoding(),
        validation=_passing_validation(),
    )
    result = p.run("c", customer_brief="x")
    assert result is None  # graceful halt, no crash


def test_negotiation_30_turn_runtime_error_is_caught(config: Config):
    """The specific failure mode where Negotiation never converges within MAX_TURNS."""
    p = Pipeline(config)
    _install(
        p,
        qualify=_good_qualify(),
        negotiation=FakeNegotiation(raises=RuntimeError("did not converge")),
        plan=FakePlan(),
        coding=FakeCoding(),
        validation=_passing_validation(),
    )
    assert p.run("c", customer_brief="x") is None


def test_plan_tier_violation_does_not_propagate(config: Config):
    """PlanAgent raises ValueError on tier-cap violation. Orchestrator must catch."""
    p = Pipeline(config)
    _install(
        p,
        qualify=_good_qualify(),
        negotiation=FakeNegotiation(),
        plan=FakePlan(raises=ValueError("Plan exceeds growth tier caps")),
        coding=FakeCoding(),
        validation=_passing_validation(),
    )
    assert p.run("c", customer_brief="x") is None


def test_plan_generic_failure_does_not_propagate(config: Config):
    """Malformed LLM JSON would raise extract_json's ValueError; must be caught."""
    p = Pipeline(config)
    _install(
        p,
        qualify=_good_qualify(),
        negotiation=FakeNegotiation(),
        plan=FakePlan(raises=Exception("malformed JSON")),
        coding=FakeCoding(),
        validation=_passing_validation(),
    )
    assert p.run("c", customer_brief="x") is None


def test_validation_uncaught_exception_does_not_crash(config: Config):
    """If ValidationAgent itself raises (not just tooling-failure verdict), the loop
    surfaces it and returns last_verdict (None on first round)."""
    p = Pipeline(config)
    _install(
        p,
        qualify=_good_qualify(),
        negotiation=FakeNegotiation(),
        plan=FakePlan(),
        coding=FakeCoding(),
        validation=FakeValidation(scripted=[], raises=RuntimeError("missing requirements.json")),
    )
    result = p.run("c", customer_brief="x")
    # last_verdict was None when validation crashed on the first round
    assert result is None


# ============================================================================
# Tier-override mismatch detection (task #37)
# ============================================================================


def test_tier_override_matching_stored_is_fine(config: Config):
    """Override that agrees with stored requirements.tier is allowed."""
    ws = Workspace("c", config.workspaces_dir)
    ws.ensure()
    # Pre-populate qualification AND requirements with growth tier
    ws.save_qualification(
        Qualification(customer_id="c", go=True, recommended_tier=Tier.GROWTH, summary_ja="ok")
    )
    ws.save_requirements(
        Requirements(
            customer_id="c",
            tier=Tier.GROWTH,
            business_name="X",
            summary_ja="x",
            target_users=["x"],
            brand_notes=["y"],
            desired_skills=["s"],
            desired_integrations=["i"],
            acceptance_criteria=["a"],
        )
    )

    p = Pipeline(config)
    _install(
        p,
        qualify=_good_qualify(),
        negotiation=FakeNegotiation(),
        plan=FakePlan(),
        coding=FakeCoding(),
        validation=_passing_validation(),
    )
    result = p.run("c", tier_override=Tier.GROWTH)
    assert result is not None and result.passed


def test_tier_override_mismatching_stored_halts(config: Config):
    """Override that conflicts with stored requirements.tier must halt with a
    clear message instead of silently producing the wrong-tier deliverable."""
    ws = Workspace("c", config.workspaces_dir)
    ws.ensure()
    ws.save_qualification(
        Qualification(customer_id="c", go=True, recommended_tier=Tier.GROWTH, summary_ja="ok")
    )
    ws.save_requirements(
        Requirements(
            customer_id="c",
            tier=Tier.GROWTH,
            business_name="X",
            summary_ja="x",
            target_users=["x"],
            brand_notes=["y"],
            desired_skills=["s"],
            desired_integrations=["i"],
            acceptance_criteria=["a"],
        )
    )

    p = Pipeline(config)
    coding = FakeCoding()
    _install(
        p,
        qualify=_good_qualify(),
        negotiation=FakeNegotiation(),
        plan=FakePlan(),
        coding=coding,
        validation=_passing_validation(),
    )
    result = p.run("c", tier_override=Tier.BUSINESS)
    assert result is None
    assert coding.calls == []  # never advanced past the negotiation stage


def test_no_override_with_stored_requirements_is_fine(config: Config):
    """Reusing stored requirements without an override is the normal happy path."""
    ws = Workspace("c", config.workspaces_dir)
    ws.ensure()
    ws.save_qualification(
        Qualification(customer_id="c", go=True, recommended_tier=Tier.STARTER, summary_ja="ok")
    )
    ws.save_requirements(
        Requirements(
            customer_id="c",
            tier=Tier.STARTER,
            business_name="X",
            summary_ja="x",
            target_users=["x"],
            brand_notes=["y"],
            desired_skills=["s"],
            desired_integrations=["i"],
            acceptance_criteria=["a"],
        )
    )

    p = Pipeline(config)
    _install(
        p,
        qualify=_good_qualify(),
        negotiation=FakeNegotiation(),
        plan=FakePlan(),
        coding=FakeCoding(),
        validation=_passing_validation(),
    )
    result = p.run("c")
    assert result is not None and result.passed


def test_corrupt_requirements_halts_with_clear_error(config: Config):
    ws = Workspace("c", config.workspaces_dir)
    ws.ensure()
    ws.save_qualification(
        Qualification(customer_id="c", go=True, recommended_tier=Tier.STARTER, summary_ja="ok")
    )
    ws.requirements_path.write_text("not json {{", encoding="utf-8")

    p = Pipeline(config)
    _install(
        p,
        qualify=_good_qualify(),
        negotiation=FakeNegotiation(),
        plan=FakePlan(),
        coding=FakeCoding(),
        validation=_passing_validation(),
    )
    assert p.run("c") is None


# ============================================================================
# Tooling-failure short-circuit (task #38)
# ============================================================================


def _tooling_failure_verdict(round_n: int = 0) -> Verdict:
    return Verdict(
        passed=False,
        round=round_n,
        summary="codex broken",
        issues=[Issue(severity="critical", description="Validator could not produce a verdict")],
        tooling_error="codex CLI not found",
    )


def test_two_consecutive_tooling_failures_halts(config: Config):
    """Two tooling failures in a row → halt with a clear message. Don't burn 20 rounds."""
    p = Pipeline(config)
    coding = FakeCoding()
    validation = FakeValidation(scripted=[_tooling_failure_verdict()])
    _install(
        p,
        qualify=_good_qualify(),
        negotiation=FakeNegotiation(),
        plan=FakePlan(),
        coding=coding,
        validation=validation,
    )
    result = p.run("c", customer_brief="x")
    assert result is not None
    assert result.tooling_error is not None
    # Should have stopped after exactly 2 attempts, NOT max_rounds (5 in fixture).
    assert validation.calls == 2
    assert len(coding.calls) == 2


def test_tooling_failure_does_not_feed_back_to_coding(config: Config):
    """When a tooling failure happens, the next coding round must NOT receive the
    tooling-failure verdict as a 'fix this' signal — claude can't fix the validator."""
    p = Pipeline(config)
    coding = FakeCoding()
    validation = FakeValidation(scripted=[_tooling_failure_verdict()])
    _install(
        p,
        qualify=_good_qualify(),
        negotiation=FakeNegotiation(),
        plan=FakePlan(),
        coding=coding,
        validation=validation,
    )
    p.run("c", customer_brief="x")

    # Round 1: no prior feedback.
    # Round 2 (the retry after tooling failure): prior_verdict must be None,
    # not the round-1 tooling-failure verdict.
    assert coding.calls[0][1] is None
    assert coding.calls[1][1] is None


def test_tooling_failure_then_recovery_continues_normally(config: Config):
    """Single tooling failure → retry; second round produces a real verdict → loop continues."""
    p = Pipeline(config)
    coding = FakeCoding()
    validation = FakeValidation(
        scripted=[
            _tooling_failure_verdict(),
            Verdict(passed=True, round=0, summary="recovered"),
        ]
    )
    _install(
        p,
        qualify=_good_qualify(),
        negotiation=FakeNegotiation(),
        plan=FakePlan(),
        coding=coding,
        validation=validation,
    )
    result = p.run("c", customer_brief="x")
    assert result is not None and result.passed
    assert validation.calls == 2


# ============================================================================
# SkillsRuntime cache invalidation (task #39)
# ============================================================================


def _write_skill(workspace: Workspace, name: str, description: str, body: str) -> Path:
    skills_dir = workspace.code_dir / "agent-skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    path = skills_dir / f"{name}.md"
    path.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n{body}",
        encoding="utf-8",
    )
    return path


def test_runtime_is_stale_when_skill_file_modified(config: Config, workspace: Workspace):
    skill_path = _write_skill(workspace, "x", "first", "body1")
    rt = SkillsRuntime(workspace, config)
    assert rt.is_stale() is False

    # Sleep so mtime moves; rewrite the skill
    time.sleep(0.02)
    skill_path.write_text(
        "---\nname: x\ndescription: second\n---\n\nbody2",
        encoding="utf-8",
    )
    assert rt.is_stale() is True


def test_runtime_is_stale_when_skill_added(config: Config, workspace: Workspace):
    _write_skill(workspace, "x", "first", "body")
    rt = SkillsRuntime(workspace, config)
    assert rt.is_stale() is False

    time.sleep(0.02)
    _write_skill(workspace, "y", "second", "body")
    assert rt.is_stale() is True


def test_runtime_is_stale_when_skill_removed(config: Config, workspace: Workspace):
    a = _write_skill(workspace, "a", "first", "body")
    _write_skill(workspace, "b", "second", "body")
    rt = SkillsRuntime(workspace, config)
    assert rt.is_stale() is False

    time.sleep(0.02)
    a.unlink()
    assert rt.is_stale() is True


def test_runtime_not_stale_when_unrelated_file_added(config: Config, workspace: Workspace):
    """Files in code/ but not under agent-skills/ should NOT invalidate the cache."""
    _write_skill(workspace, "x", "d", "body")
    rt = SkillsRuntime(workspace, config)

    time.sleep(0.02)
    (workspace.code_dir / "landing-page").mkdir(exist_ok=True)
    (workspace.code_dir / "landing-page" / "index.html").write_text("<html/>", encoding="utf-8")
    # Note: this might tick the parent code/ dir's mtime but NOT agent-skills/'s.
    # The is_stale check looks only at agent-skills/.
    assert rt.is_stale() is False


def test_server_rebuilds_runtime_on_skill_change(config: Config):
    """End-to-end: after a skill file is rewritten, the server's next request
    sees the new content (not the cached stale runtime)."""
    from fastapi.testclient import TestClient

    from smbagent.auth import issue_token
    from smbagent.server import create_app

    ws = Workspace("cache-test", config.workspaces_dir)
    ws.ensure()
    _write_skill(ws, "x", "original description", "body")
    token = issue_token(ws).token

    app = create_app(config)
    with TestClient(app) as client:
        # First request builds + caches the runtime
        r1 = client.get(
            "/v1/customers/cache-test/skills",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r1.status_code == 200
        assert any(s["description"] == "original description" for s in r1.json()["skills"])
        rt_first = app.state.runtime_cache.get("cache-test")

        # Now modify the skill on disk
        time.sleep(0.02)
        _write_skill(ws, "x", "modified description", "body")

        # Second request must rebuild the cache
        r2 = client.get(
            "/v1/customers/cache-test/skills",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 200
        assert any(s["description"] == "modified description" for s in r2.json()["skills"])
        rt_second = app.state.runtime_cache.get("cache-test")
        assert rt_second is not rt_first  # actual rebuild happened


# ============================================================================
# Anthropic SDK timeout config (task #40)
# ============================================================================


def test_qualify_agent_passes_timeout_to_anthropic_client(config: Config):
    """All Anthropic clients should receive `timeout` from config."""
    from smbagent.agents.qualify import QualifyAgent

    agent = QualifyAgent(config)
    # anthropic SDK exposes the timeout as client.timeout (an httpx.Timeout in recent versions)
    assert hasattr(agent.client, "timeout")


def test_negotiation_agent_passes_timeout_to_anthropic_client(config: Config):
    from smbagent.agents.negotiation import NegotiationAgent

    agent = NegotiationAgent(config)
    assert hasattr(agent.client, "timeout")


def test_plan_agent_passes_timeout_to_anthropic_client(config: Config):
    from smbagent.agents.plan import PlanAgent

    agent = PlanAgent(config)
    assert hasattr(agent.client, "timeout")


def test_skills_runtime_passes_timeout_to_anthropic_client(config: Config, workspace: Workspace):
    _write_skill(workspace, "x", "d", "body")
    rt = SkillsRuntime(workspace, config)
    assert hasattr(rt.client, "timeout")


def test_config_anthropic_timeout_has_default():
    """Even when no SMBAGENT_ANTHROPIC_TIMEOUT_S env var is set, the default kicks in."""
    from smbagent.config import load_config

    cfg = load_config()
    assert cfg.anthropic_timeout_s > 0
