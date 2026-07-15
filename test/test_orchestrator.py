from __future__ import annotations

from dataclasses import dataclass, field

from smbagent.config import Config
from smbagent.orchestrator import Pipeline
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


@dataclass
class FakeCoding:
    """Records every call so tests can assert on what was passed."""

    calls: list[tuple[int, Verdict | None]] = field(default_factory=list)

    def run(self, workspace: Workspace, round_n: int, prior_feedback: Verdict | None):
        self.calls.append((round_n, prior_feedback))


@dataclass
class FakeValidation:
    """Returns a scripted sequence of verdicts."""

    scripted: list[Verdict]
    calls: int = 0

    def run(self, workspace: Workspace, round_n: int) -> Verdict:
        idx = min(self.calls, len(self.scripted) - 1)
        v = self.scripted[idx]
        self.calls += 1
        # respect the round_n we were called with so the verdict's round is accurate
        return v.model_copy(update={"round": round_n})


def _make_pipeline(config: Config, coding: FakeCoding, validation: FakeValidation) -> Pipeline:
    p = Pipeline(config)
    p.coding = coding  # type: ignore[assignment]
    p.validation = validation  # type: ignore[assignment]
    return p


def test_loop_exits_immediately_when_first_round_passes(config: Config, workspace: Workspace):
    coding = FakeCoding()
    validation = FakeValidation(scripted=[Verdict(passed=True, round=1, summary="ok")])
    p = _make_pipeline(config, coding, validation)

    result = p._code_validate_loop(workspace)

    assert result is not None and result.passed
    assert len(coding.calls) == 1
    assert coding.calls[0] == (1, None)  # no prior feedback on round 1
    assert validation.calls == 1


def test_loop_passes_prior_verdict_to_next_coding_round(config: Config, workspace: Workspace):
    fail = Verdict(
        passed=False,
        round=1,
        summary="bad",
        issues=[Issue(severity="critical", description="x")],
    )
    passing = Verdict(passed=True, round=2, summary="ok")
    coding = FakeCoding()
    validation = FakeValidation(scripted=[fail, passing])
    p = _make_pipeline(config, coding, validation)

    result = p._code_validate_loop(workspace)

    assert result is not None and result.passed
    assert len(coding.calls) == 2
    # Round 1: no prior feedback
    assert coding.calls[0][0] == 1 and coding.calls[0][1] is None
    # Round 2: prior verdict from round 1 is passed in
    assert coding.calls[1][0] == 2
    assert coding.calls[1][1] is not None
    assert coding.calls[1][1].round == 1


def test_loop_terminates_at_max_rounds_and_returns_last_failure(config: Config, workspace: Workspace):
    assert config.max_rounds == 5  # sanity-check fixture
    fail = Verdict(
        passed=False,
        round=0,
        summary="never passes",
        issues=[Issue(severity="critical", description="x")],
    )
    coding = FakeCoding()
    validation = FakeValidation(scripted=[fail])
    p = _make_pipeline(config, coding, validation)

    result = p._code_validate_loop(workspace)

    assert result is not None
    assert result.passed is False
    assert len(coding.calls) == config.max_rounds
    assert validation.calls == config.max_rounds
    assert coding.calls[-1][0] == config.max_rounds


def test_loop_returns_none_when_coding_agent_raises_file_not_found(config: Config, workspace: Workspace):
    class BrokenCoding:
        def run(self, *a, **kw):
            raise FileNotFoundError("claude")

    validation = FakeValidation(scripted=[Verdict(passed=True, round=1, summary="ok")])
    p = _make_pipeline(config, BrokenCoding(), validation)  # type: ignore[arg-type]

    result = p._code_validate_loop(workspace)
    assert result is None
    assert validation.calls == 0  # never reached the validator


# ---- Pipeline.run with qualify gate ----


@dataclass
class FakeQualify:
    qualification: Qualification
    calls: list[str] = field(default_factory=list)

    def run(self, workspace: Workspace, customer_brief: str) -> Qualification:
        self.calls.append(customer_brief)
        workspace.save_qualification(self.qualification)
        return self.qualification


@dataclass
class FakeNegotiation:
    """Persists a Requirements that mirrors the tier it was called with."""

    calls: list[Tier] = field(default_factory=list)

    def run(self, workspace: Workspace, tier: Tier) -> Requirements:
        self.calls.append(tier)
        req = Requirements(
            customer_id=workspace.customer_id,
            tier=tier,
            business_name="Acme",
            summary_ja="テスト",
            target_users=["x"],
            brand_notes=["y"],
            desired_skills=["s1"],
            desired_integrations=["Gmail"],
            acceptance_criteria=["A1"],
        )
        workspace.save_requirements(req)
        return req


@dataclass
class FakePlan:
    calls: int = 0

    def run(self, workspace: Workspace) -> Plan:
        self.calls += 1
        req = workspace.load_requirements()
        plan = Plan(
            tier=req.tier,
            summary="x",
            landing_page=LandingPageSpec(pages=["/"], hero_copy_outline="o", primary_cta="cta"),
            agent_skills=[AgentSkillSpec(name="understand-acme", description="d", system_prompt_outline="o")],
            integrations=[IntegrationSpec(name="Gmail", purpose="x")],
        )
        workspace.save_plan(plan, plan_md="# plan")
        return plan


def _install_fakes(p: Pipeline, *, qualify, negotiation, plan, coding, validation) -> None:
    p.qualify = qualify  # type: ignore[assignment]
    p.negotiation = negotiation  # type: ignore[assignment]
    p.plan = plan  # type: ignore[assignment]
    p.coding = coding  # type: ignore[assignment]
    p.validation = validation  # type: ignore[assignment]


def test_run_halts_on_no_go_qualification(config: Config):
    p = Pipeline(config)
    q = FakeQualify(Qualification(customer_id="c", go=False, recommended_tier=None, summary_ja="not a fit"))
    neg = FakeNegotiation()
    pl = FakePlan()
    coding = FakeCoding()
    validation = FakeValidation(scripted=[])
    _install_fakes(p, qualify=q, negotiation=neg, plan=pl, coding=coding, validation=validation)

    result = p.run("c", customer_brief="dental clinic in Tokyo")

    assert result is None
    assert q.calls == ["dental clinic in Tokyo"]
    assert neg.calls == []  # never reached negotiation
    assert pl.calls == 0
    assert validation.calls == 0


def test_run_uses_recommended_tier_when_no_override(config: Config):
    p = Pipeline(config)
    q = FakeQualify(Qualification(customer_id="c", go=True, recommended_tier=Tier.GROWTH, summary_ja="fit"))
    neg = FakeNegotiation()
    pl = FakePlan()
    coding = FakeCoding()
    validation = FakeValidation(scripted=[Verdict(passed=True, round=1, summary="ok")])
    _install_fakes(p, qualify=q, negotiation=neg, plan=pl, coding=coding, validation=validation)

    result = p.run("c", customer_brief="...")

    assert result is not None and result.passed
    assert neg.calls == [Tier.GROWTH]


def test_run_tier_override_beats_recommendation(config: Config):
    p = Pipeline(config)
    q = FakeQualify(Qualification(customer_id="c", go=True, recommended_tier=Tier.GROWTH, summary_ja="fit"))
    neg = FakeNegotiation()
    pl = FakePlan()
    coding = FakeCoding()
    validation = FakeValidation(scripted=[Verdict(passed=True, round=1, summary="ok")])
    _install_fakes(p, qualify=q, negotiation=neg, plan=pl, coding=coding, validation=validation)

    result = p.run("c", customer_brief="...", tier_override=Tier.BUSINESS)

    assert result is not None and result.passed
    assert neg.calls == [Tier.BUSINESS]


def test_run_fails_when_no_brief_and_no_prior_qualification(config: Config):
    p = Pipeline(config)
    _install_fakes(
        p,
        qualify=FakeQualify(
            Qualification(customer_id="c", go=True, recommended_tier=Tier.STARTER, summary_ja="fit")
        ),
        negotiation=FakeNegotiation(),
        plan=FakePlan(),
        coding=FakeCoding(),
        validation=FakeValidation(scripted=[]),
    )
    result = p.run("c")  # no brief
    assert result is None


def test_run_reuses_existing_qualification(config: Config, workspace: Workspace):
    """If qualification.json exists, skip re-running qualify (and no brief required)."""
    existing = Qualification(
        customer_id="test-customer",
        go=True,
        recommended_tier=Tier.STARTER,
        summary_ja="prior fit",
    )
    workspace.save_qualification(existing)

    p = Pipeline(config)
    q = FakeQualify(Qualification(customer_id="should-not-be-called", go=False, summary_ja="WRONG"))
    neg = FakeNegotiation()
    pl = FakePlan()
    coding = FakeCoding()
    validation = FakeValidation(scripted=[Verdict(passed=True, round=1, summary="ok")])
    _install_fakes(p, qualify=q, negotiation=neg, plan=pl, coding=coding, validation=validation)

    result = p.run("test-customer")  # no brief

    assert result is not None and result.passed
    assert q.calls == []  # qualify NOT invoked
    assert neg.calls == [Tier.STARTER]


def test_qualification_invariant_blocks_go_without_tier():
    """The Qualification model itself refuses go=True with recommended_tier=None.
    This is the safety net that prevents the orchestrator from ever reaching
    a 'go but no tier' state — the invalid state is unrepresentable."""
    import pytest

    with pytest.raises(Exception) as excinfo:
        Qualification(customer_id="c", go=True, recommended_tier=None, summary_ja="fit but no tier")
    assert "recommended_tier" in str(excinfo.value)


def test_run_halts_when_qualify_agent_raises(config: Config):
    """If the qualify agent itself raises (e.g. LLM returned incoherent output),
    the orchestrator halts gracefully with a clear message instead of crashing."""
    p = Pipeline(config)

    class ExplodingQualify:
        def run(self, workspace, customer_brief):
            raise ValueError("incoherent LLM output: go=true without tier")

    p.qualify = ExplodingQualify()  # type: ignore[assignment]
    p.negotiation = FakeNegotiation()  # type: ignore[assignment]
    p.plan = FakePlan()  # type: ignore[assignment]
    p.coding = FakeCoding()  # type: ignore[assignment]
    p.validation = FakeValidation(scripted=[])  # type: ignore[assignment]

    result = p.run("c", customer_brief="...")
    assert result is None
