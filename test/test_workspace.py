from __future__ import annotations

import pytest

from smbagent.config import Config
from smbagent.types import (
    AgentSkillSpec,
    CompanyContext,
    IntegrationSpec,
    Issue,
    LandingPageSpec,
    Plan,
    Qualification,
    Requirements,
    Tier,
    Verdict,
)
from smbagent.workspace import InvalidCustomerIdError, Workspace


def test_ensure_creates_directories(workspace: Workspace):
    assert workspace.path.is_dir()
    assert workspace.code_dir.is_dir()
    assert workspace.runs_dir.is_dir()


def test_requirements_roundtrip(workspace: Workspace):
    req = Requirements(
        customer_id="test-customer",
        tier=Tier.GROWTH,
        business_name="アクメ商事",
        summary_ja="テストです",
        target_users=["既存顧客"],
        brand_notes=["親しみやすい"],
        desired_skills=["問い合わせ対応", "予約受付"],
        desired_integrations=["Gmail"],
        acceptance_criteria=["A1"],
        company_context=CompanyContext(
            mission="地域の患者さんを安心させる",
            vision="最も信頼される町の歯科医院",
            values=["親切", "正確"],
            current_strategy=["予約導線の改善"],
            current_priorities=["新患対応の平準化"],
            decision_style="慎重だが実務的",
            risk_tolerance="低め",
        ),
    )
    workspace.save_requirements(req)
    loaded = workspace.load_requirements()
    assert loaded == req
    assert workspace.load_company_context() == req.company_context
    content = workspace.requirements_path.read_text(encoding="utf-8")
    assert "テストです" in content
    assert "アクメ商事" in content


def test_qualification_roundtrip(workspace: Workspace):
    q = Qualification(
        customer_id="test-customer",
        go=True,
        recommended_tier=Tier.GROWTH,
        summary_ja="適合します",
        reasoning_en="Solo-op-plus expanding team.",
    )
    workspace.save_qualification(q)
    assert workspace.load_qualification() == q


def test_qualification_no_go_has_no_tier(workspace: Workspace):
    q = Qualification(
        customer_id="test-customer",
        go=False,
        recommended_tier=None,
        summary_ja="範囲外です",
    )
    workspace.save_qualification(q)
    loaded = workspace.load_qualification()
    assert loaded.go is False
    assert loaded.recommended_tier is None


def test_plan_roundtrip(workspace: Workspace):
    plan = Plan(
        tier=Tier.STARTER,
        summary="s",
        landing_page=LandingPageSpec(
            pages=["/"], hero_copy_outline="hero", primary_cta="Book a call", sections=["hero"]
        ),
        agent_skills=[
            AgentSkillSpec(
                name="understand-acme", description="Acme context", system_prompt_outline="outline"
            )
        ],
        integrations=[IntegrationSpec(name="Gmail", purpose="lead forwarding")],
    )
    workspace.save_plan(plan, plan_md="# plan\n\nbody")
    assert workspace.plan_path.read_text(encoding="utf-8") == "# plan\n\nbody"
    assert workspace.load_plan() == plan


def test_plan_violates_tier_caps_detects_overflow():
    plan = Plan(
        tier=Tier.STARTER,
        summary="too big",
        landing_page=LandingPageSpec(
            pages=["/", "/about", "/contact"],  # starter cap = 1
            hero_copy_outline="x",
            primary_cta="x",
        ),
        agent_skills=[
            AgentSkillSpec(name="s1", description="d", system_prompt_outline="o"),
            AgentSkillSpec(name="s2", description="d", system_prompt_outline="o"),
        ],
        integrations=[
            IntegrationSpec(name="A", purpose="x"),
            IntegrationSpec(name="B", purpose="x"),
        ],
    )
    violations = plan.violates_tier_caps()
    assert len(violations) == 3
    assert any("skills" in v for v in violations)
    assert any("pages" in v for v in violations)
    assert any("integrations" in v for v in violations)


def test_plan_fits_growth_tier_when_within_caps():
    plan = Plan(
        tier=Tier.GROWTH,
        summary="ok",
        landing_page=LandingPageSpec(
            pages=["/", "/about", "/contact"],
            hero_copy_outline="x",
            primary_cta="x",
        ),
        agent_skills=[
            AgentSkillSpec(name=f"s{i}", description="d", system_prompt_outline="o") for i in range(5)
        ],
        integrations=[IntegrationSpec(name=str(i), purpose="x") for i in range(3)],
    )
    assert plan.violates_tier_caps() == []


def test_verdict_save_and_load(workspace: Workspace):
    v = Verdict(
        passed=False,
        round=2,
        summary="bad",
        issues=[Issue(severity="critical", description="x")],
    )
    workspace.save_verdict(v)
    loaded = workspace.load_verdict(2)
    assert loaded == v
    # round_dir is created
    assert workspace.round_dir(2).is_dir()


def test_load_verdict_returns_none_when_missing(workspace: Workspace):
    assert workspace.load_verdict(99) is None


def test_load_verdict_returns_none_on_invalid_json(workspace: Workspace):
    workspace.verdict_path(1).write_text("not json", encoding="utf-8")
    assert workspace.load_verdict(1) is None


def test_last_verdict_returns_most_recent(workspace: Workspace):
    v1 = Verdict(passed=False, round=1, summary="r1")
    v2 = Verdict(passed=True, round=2, summary="r2")
    workspace.save_verdict(v1)
    workspace.save_verdict(v2)
    assert workspace.last_verdict() == v2


def test_last_verdict_handles_round_10_vs_round_2(workspace: Workspace):
    # numeric sort, not lex sort
    for i in (1, 2, 10):
        workspace.save_verdict(Verdict(passed=False, round=i, summary=f"r{i}"))
    last = workspace.last_verdict()
    assert last is not None and last.round == 10


def test_last_verdict_skips_corrupt(workspace: Workspace):
    workspace.save_verdict(Verdict(passed=False, round=1, summary="ok"))
    workspace.verdict_path(2).write_text("garbage", encoding="utf-8")
    last = workspace.last_verdict()
    assert last is not None and last.round == 1


# ---- Security: customer_id validation ----


@pytest.mark.parametrize(
    "bad_id",
    [
        "../escape",
        "../../etc",
        "..",
        ".",
        "/absolute",
        "with/slash",
        "with\\backslash",
        "with space",
        "-leading-hyphen",  # could be parsed as a CLI flag downstream
        ".leading-dot",
        "",
        "x" * 65,  # too long
        "unicode-名前",  # we restrict to ASCII for safety
        "../",
        "..\\..\\",
        "customer\x00null",
        "customer\nnewline",
    ],
)
def test_invalid_customer_id_is_rejected(bad_id: str, config: Config):
    with pytest.raises(InvalidCustomerIdError):
        Workspace(bad_id, config.workspaces_dir)


@pytest.mark.parametrize(
    "ok_id",
    [
        "customer1",
        "Customer_1",
        "acme-corp",
        "a.b.c",
        "X",
        "a" * 64,  # max length
    ],
)
def test_valid_customer_id_is_accepted(ok_id: str, config: Config):
    ws = Workspace(ok_id, config.workspaces_dir)
    assert ws.customer_id == ok_id
    assert str(ws.path).startswith(str(config.workspaces_dir.resolve()))


def test_resolved_path_stays_under_workspaces_root(config: Config):
    """If a valid-looking customer_id somehow resolved outside, we'd reject it."""
    ws = Workspace("acme-corp", config.workspaces_dir)
    # The resolved path must be a child of workspaces_dir, no exceptions.
    assert ws.path.is_relative_to(config.workspaces_dir.resolve())
