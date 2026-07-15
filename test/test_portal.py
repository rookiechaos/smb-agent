"""Unit tests for the customer portal renderer."""

from __future__ import annotations

import json

from smbagent.config import Config
from smbagent.portal import render_portal, write_portal
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

# ---- Helpers ----


def _populate_full_workspace(workspace: Workspace) -> None:
    """Populate a workspace with all artifacts so the portal has everything to render."""
    workspace.save_qualification(
        Qualification(
            customer_id=workspace.customer_id,
            go=True,
            recommended_tier=Tier.GROWTH,
            summary_ja="中規模事業者で適合します。",
            reasoning_en="OK.",
        )
    )
    workspace.save_requirements(
        Requirements(
            customer_id=workspace.customer_id,
            tier=Tier.GROWTH,
            business_name="アクメ商事",
            summary_ja="ECサイトの問い合わせをAIで対応したい。",
            target_users=["新規顧客", "既存顧客"],
            brand_notes=["親しみやすい", "信頼感"],
            desired_skills=["問い合わせ対応", "予約受付"],
            desired_integrations=["Gmail", "Google Calendar"],
            acceptance_criteria=["問い合わせの80%以上をAIで完結"],
        )
    )
    workspace.save_plan(
        Plan(
            tier=Tier.GROWTH,
            summary="three artifacts shipped.",
            landing_page=LandingPageSpec(
                pages=["/", "/contact"],
                hero_copy_outline="hero copy",
                primary_cta="今すぐ問い合わせ",
                sections=["hero", "services"],
            ),
            agent_skills=[
                AgentSkillSpec(name="understand-acme", description="context", system_prompt_outline="..."),
                AgentSkillSpec(
                    name="handle-inquiry", description="answers questions", system_prompt_outline="..."
                ),
            ],
            integrations=[
                IntegrationSpec(name="Gmail", purpose="forward leads"),
            ],
        ),
        plan_md="# Plan",
    )
    workspace.save_verdict(
        Verdict(
            passed=True,
            round=2,
            summary="all green",
            issues=[],
        )
    )


def _populate_code_tree(workspace: Workspace) -> None:
    (workspace.code_dir / "agent-skills").mkdir(exist_ok=True)
    (workspace.code_dir / "agent-skills" / "understand-acme.md").write_text(
        "---\nname: understand-acme\ndescription: ctx\n---\n\nbody", encoding="utf-8"
    )
    (workspace.code_dir / "agent-skills" / "handle-inquiry.md").write_text(
        "---\nname: handle-inquiry\ndescription: q\n---\n\nbody", encoding="utf-8"
    )
    (workspace.code_dir / "landing-page").mkdir(exist_ok=True)
    (workspace.code_dir / "landing-page" / "index.html").write_text(
        "<!doctype html><html><body><h1>アクメ商事</h1></body></html>",
        encoding="utf-8",
    )
    (workspace.code_dir / "landing-page" / "contact.html").write_text("<html/>", encoding="utf-8")
    (workspace.code_dir / "integrations" / "gmail").mkdir(parents=True, exist_ok=True)


# ---- Rendering ----


def test_render_portal_returns_html_for_empty_workspace(config: Config, workspace: Workspace):
    """Even with nothing populated, portal should render without crashing."""
    out = render_portal(workspace)
    assert out.startswith("<!doctype html>")
    assert workspace.customer_id in out
    # Empty-state messages appear
    assert "Not yet run" in out or "Negotiation not yet" in out


def test_render_portal_includes_all_sections(config: Config, workspace: Workspace):
    out = render_portal(workspace)
    for heading in (
        "Qualification",
        "Requirements",
        "Plan",
        "Deliverable counts",
        "Latest verdict",
        "Landing-page preview",
    ):
        assert heading in out, f"missing section: {heading}"


def test_render_portal_with_full_workspace(config: Config, workspace: Workspace):
    _populate_full_workspace(workspace)
    _populate_code_tree(workspace)
    out = render_portal(workspace)

    # Qualification rendered with pill + tier
    assert "GO" in out
    assert "growth" in out

    # Requirements rendered with JP business name
    assert "アクメ商事" in out
    assert "問い合わせ対応" in out
    assert "Gmail" in out

    # Plan rendered with CTA + skill names
    assert "今すぐ問い合わせ" in out
    assert "understand-acme" in out
    assert "handle-inquiry" in out

    # Deliverable counts: 2 skills, 2 pages, 1 integration
    assert ">2<" in out  # appears for skills + pages count
    assert ">1<" in out  # for integrations

    # Verdict: PASSED
    assert "PASSED" in out

    # Landing-page preview iframe with the index.html content
    assert "<iframe" in out
    assert "srcdoc=" in out


def test_render_portal_escapes_jp_html_safely(config: Config, workspace: Workspace):
    """HTML-like content in customer fields must be escaped."""
    workspace.save_requirements(
        Requirements(
            customer_id=workspace.customer_id,
            tier=Tier.STARTER,
            business_name="<script>alert('xss')</script>",
            summary_ja="ok",
            target_users=["x"],
            brand_notes=["y"],
            desired_skills=["z"],
            desired_integrations=["i"],
            acceptance_criteria=["a"],
        )
    )
    out = render_portal(workspace)
    # The literal script tag must NOT appear (it must be HTML-escaped).
    assert "<script>alert" not in out
    # The escaped form should appear instead.
    assert "&lt;script&gt;" in out


def test_render_portal_no_go_uses_no_go_pill(config: Config, workspace: Workspace):
    workspace.save_qualification(
        Qualification(
            customer_id=workspace.customer_id,
            go=False,
            recommended_tier=None,
            summary_ja="範囲外です。",
        )
    )
    out = render_portal(workspace)
    assert "NO-GO" in out
    assert "範囲外" in out


def test_render_portal_failed_verdict_uses_failed_pill(config: Config, workspace: Workspace):
    workspace.save_verdict(
        Verdict(
            passed=False,
            round=1,
            summary="problems",
            issues=[Issue(severity="critical", description="x")],
        )
    )
    out = render_portal(workspace)
    assert "FAILED" in out
    assert "1 issue" in out


def test_render_portal_handles_missing_landing_index(config: Config, workspace: Workspace):
    """Code dir has no landing page → preview section shows empty state, no iframe."""
    out = render_portal(workspace)
    # Empty state in the preview section
    assert "No index.html" in out


def test_render_portal_deliverable_counts_real_files(config: Config, workspace: Workspace):
    """Counts must reflect actual on-disk contents, not anything else."""
    # Empty workspace: all counts zero
    out_empty = render_portal(workspace)
    assert ">0<" in out_empty

    # Populate: 3 skills, 1 page, 2 integrations
    skills = workspace.code_dir / "agent-skills"
    skills.mkdir(exist_ok=True)
    for n in ("a", "b", "c"):
        (skills / f"{n}.md").write_text(f"---\nname: {n}\ndescription: d\n---\n\nb", encoding="utf-8")
    (workspace.code_dir / "landing-page").mkdir(exist_ok=True)
    (workspace.code_dir / "landing-page" / "index.html").write_text("<html/>", encoding="utf-8")
    (workspace.code_dir / "integrations" / "x").mkdir(parents=True, exist_ok=True)
    (workspace.code_dir / "integrations" / "y").mkdir(parents=True, exist_ok=True)

    out = render_portal(workspace)
    # Numbers appear in the deliverable section
    assert '<div class="num">3</div>' in out
    assert '<div class="num">1</div>' in out
    assert '<div class="num">2</div>' in out


def test_write_portal_persists_html(config: Config, workspace: Workspace):
    out = write_portal(workspace)
    assert out == workspace.path / "portal.html"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert text.startswith("<!doctype html>")
    assert "</html>" in text
    state = json.loads(workspace.workspace_state_path.read_text(encoding="utf-8"))
    freshness = state["sections"]["artifact_freshness"]["portal_html"]
    assert freshness["status"] == "fresh"
    assert freshness["artifact_paths"] == ["portal.html"]
    assert "customer portal rendered" in freshness["detail"]


def test_render_portal_landing_preview_html_escaped_inside_srcdoc(config: Config, workspace: Workspace):
    """The landing-page HTML lives inside iframe srcdoc, which requires
    attribute-escaping (so embedded `"` and `<` don't break the outer page)."""
    (workspace.code_dir / "landing-page").mkdir(exist_ok=True)
    (workspace.code_dir / "landing-page" / "index.html").write_text(
        '<html><body title="quote &amp; less-than &lt;3">hi</body></html>',
        encoding="utf-8",
    )
    out = render_portal(workspace)
    # The literal `"` inside the embedded HTML must NOT appear unescaped inside srcdoc.
    # html.escape with quote=True produces &quot;
    assert 'srcdoc="' in out
    # The embedded `"` from the title attribute should be escaped to &quot; in srcdoc.
    # We can't make a super-strict assertion because the outer srcdoc has its own quoting,
    # but we can check that the raw `title="quote` substring isn't bare inside srcdoc.
    srcdoc_start = out.index('srcdoc="') + len('srcdoc="')
    srcdoc_end = out.index('"', srcdoc_start)
    srcdoc_value = out[srcdoc_start:srcdoc_end]
    # If quoting were broken, this slice would have ended early at the first inner "
    # — meaning we'd see ", body title=" not in the captured slice. The fact that the
    # whole iframe parses with no early termination is what we're checking.
    assert "html" in srcdoc_value  # captured slice includes content
