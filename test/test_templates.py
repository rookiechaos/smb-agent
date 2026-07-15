"""Unit tests for the vertical template pack mechanism."""

from __future__ import annotations

from pathlib import Path

import pytest

from smbagent.config import Config
from smbagent.templates import AVAILABLE_PACKS, TemplatePack, TemplatePackError
from smbagent.workspace import Workspace


def test_all_packs_in_registry():
    for name in ("dental", "real-estate", "legal"):
        assert name in AVAILABLE_PACKS


def test_unknown_pack_raises():
    with pytest.raises(TemplatePackError):
        TemplatePack("nonexistent-vertical")


def test_dental_pack_files_listing():
    pack = TemplatePack("dental")
    files = [str(p) for p in pack.files()]

    # The 4 mandated skills + 2 landing-page files + 1 integration set + README
    expected_subset = {
        "agent-skills/understand-dental.md",
        "agent-skills/book-appointment.md",
        "agent-skills/answer-faq.md",
        "agent-skills/follow-up.md",
        "landing-page/index.html",
        "landing-page/booking.html",
        "integrations/forward-to-clinic/README.md",
        "integrations/forward-to-clinic/config.example.json",
        "README.md",
    }
    assert expected_subset.issubset(set(files)), f"missing: {expected_subset - set(files)}"


def test_dental_pack_skills_have_valid_frontmatter():
    """Every shipped skill MUST pass our own frontmatter validator,
    or it would fail in a real customer's validation round."""
    # Materialize into a tmp workspace, then run our existing validator on it.
    import tempfile

    from smbagent.safety import validate_skill_frontmatter

    with tempfile.TemporaryDirectory() as tmp:
        ws_root = Path(tmp) / "ws"
        ws_root.mkdir()
        ws = Workspace("dental-test", ws_root)
        ws.ensure()
        TemplatePack("dental").materialize(ws)

        issues = validate_skill_frontmatter(ws.code_dir)
        assert issues == [], f"template ships skills with bad frontmatter: {issues}"


def test_materialize_seed_writes_into_empty_workspace(config: Config, workspace: Workspace):
    pack = TemplatePack("dental")
    report = pack.materialize(workspace, mode="seed")

    assert (workspace.code_dir / "agent-skills" / "understand-dental.md").exists()
    assert (workspace.code_dir / "landing-page" / "index.html").exists()
    assert (workspace.code_dir / "integrations" / "forward-to-clinic" / "README.md").exists()
    assert report.skipped == []
    assert report.overwritten == []
    assert len(report.written) >= 8


def test_materialize_seed_preserves_existing_files(config: Config, workspace: Workspace):
    """In seed mode, files already in the workspace are NOT touched."""
    pack = TemplatePack("dental")

    # Pre-write a customized version of one of the pack files.
    skill_path = workspace.code_dir / "agent-skills" / "understand-dental.md"
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    custom = "---\nname: understand-dental\ndescription: custom\n---\n\nCUSTOMIZED CONTENT"
    skill_path.write_text(custom, encoding="utf-8")

    report = pack.materialize(workspace, mode="seed")

    # The customized file is preserved.
    assert skill_path.read_text(encoding="utf-8") == custom
    assert "agent-skills/understand-dental.md" in report.skipped


def test_materialize_overlay_clobbers_existing_files(config: Config, workspace: Workspace):
    pack = TemplatePack("dental")

    skill_path = workspace.code_dir / "agent-skills" / "understand-dental.md"
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    skill_path.write_text("old content", encoding="utf-8")

    report = pack.materialize(workspace, mode="overlay")

    assert "agent-skills/understand-dental.md" in report.overwritten
    assert "old content" not in skill_path.read_text(encoding="utf-8")
    assert "understand-dental" in skill_path.read_text(encoding="utf-8")


def test_materialize_creates_nested_dirs(config: Config, workspace: Workspace):
    """integrations/forward-to-clinic/ doesn't exist in the empty workspace —
    materialize must create the full path."""
    pack = TemplatePack("dental")
    pack.materialize(workspace)
    assert (workspace.code_dir / "integrations" / "forward-to-clinic").is_dir()
    assert (workspace.code_dir / "integrations" / "forward-to-clinic" / "config.example.json").exists()


def test_dental_index_html_references_booking_route():
    """Sanity: the CTA on index.html points to the booking page."""
    pack = TemplatePack("dental")
    index_path = pack.root / "landing-page" / "index.html"
    content = index_path.read_text(encoding="utf-8")
    assert 'href="/booking"' in content


def test_dental_skills_reference_each_other_consistently():
    """answer-faq and book-appointment reference understand-dental as the source of truth.
    follow-up references the booking flow. Mistakes in cross-refs would be subtle bugs."""
    pack = TemplatePack("dental")
    skills_dir = pack.root / "agent-skills"
    faq = (skills_dir / "answer-faq.md").read_text(encoding="utf-8")
    book = (skills_dir / "book-appointment.md").read_text(encoding="utf-8")
    follow = (skills_dir / "follow-up.md").read_text(encoding="utf-8")

    assert "understand-dental" in faq
    assert "understand-dental" in book
    assert "understand-dental" in follow
    # book-appointment is referenced by follow-up
    assert "book-appointment" in follow


def test_dental_config_example_uses_placeholders():
    """Defensive: the example config must NEVER contain real secret-shaped values
    (would get flagged by safety.scan_for_secrets)."""
    # Materialize into a tmp dir, then scan code/integrations/.
    import tempfile

    from smbagent.safety import scan_for_secrets

    with tempfile.TemporaryDirectory() as tmp:
        ws_root = Path(tmp) / "ws"
        ws_root.mkdir()
        ws = Workspace("dental-secrets-test", ws_root)
        ws.ensure()
        TemplatePack("dental").materialize(ws)

        issues = scan_for_secrets(ws.code_dir)
        assert issues == [], f"template config has secret-shaped values: {issues}"


# ---- All packs: shared correctness invariants ----


@pytest.mark.parametrize("pack_name", ["dental", "real-estate", "legal"])
def test_pack_ships_required_subdirs(pack_name: str, config: Config):
    """Every pack must populate agent-skills/, landing-page/, integrations/."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        ws_root = Path(tmp) / "ws"
        ws_root.mkdir()
        ws = Workspace(f"{pack_name}-coverage-check", ws_root)
        ws.ensure()
        TemplatePack(pack_name).materialize(ws)

        assert (ws.code_dir / "agent-skills").is_dir()
        assert (ws.code_dir / "landing-page").is_dir()
        assert (ws.code_dir / "integrations").is_dir()
        # At least one skill, one page, one integration in each pack.
        assert any((ws.code_dir / "agent-skills").glob("*.md"))
        assert any((ws.code_dir / "landing-page").glob("*.html"))
        assert any((ws.code_dir / "integrations").iterdir())


@pytest.mark.parametrize("pack_name", ["dental", "real-estate", "legal"])
def test_pack_skills_pass_frontmatter_validator(pack_name: str):
    """Skills in every shipped pack must satisfy safety.validate_skill_frontmatter."""
    import tempfile

    from smbagent.safety import validate_skill_frontmatter

    with tempfile.TemporaryDirectory() as tmp:
        ws_root = Path(tmp) / "ws"
        ws_root.mkdir()
        ws = Workspace(f"{pack_name}-fm-check", ws_root)
        ws.ensure()
        TemplatePack(pack_name).materialize(ws)

        issues = validate_skill_frontmatter(ws.code_dir)
        assert issues == [], f"{pack_name} ships skills with bad frontmatter: {issues}"


@pytest.mark.parametrize("pack_name", ["dental", "real-estate", "legal"])
def test_pack_has_no_secrets_after_materialize(pack_name: str):
    import tempfile

    from smbagent.safety import scan_for_secrets

    with tempfile.TemporaryDirectory() as tmp:
        ws_root = Path(tmp) / "ws"
        ws_root.mkdir()
        ws = Workspace(f"{pack_name}-secret-scan", ws_root)
        ws.ensure()
        TemplatePack(pack_name).materialize(ws)

        issues = scan_for_secrets(ws.code_dir)
        assert issues == [], f"{pack_name} has secret-shaped values: {issues}"


@pytest.mark.parametrize("pack_name", ["dental", "real-estate", "legal"])
def test_pack_includes_understand_skill(pack_name: str):
    """Every pack must include an `understand-<something>` foundational skill."""
    pack = TemplatePack(pack_name)
    skill_files = [str(p) for p in pack.files() if str(p).startswith("agent-skills/")]
    understand_files = [s for s in skill_files if s.startswith("agent-skills/understand-")]
    assert len(understand_files) >= 1, f"{pack_name} missing understand-* skill"


def test_realestate_pack_has_both_integrations():
    """Real-estate ships forward-to-agent (mail) AND book-viewing (calendar)."""
    pack = TemplatePack("real-estate")
    files = [str(p) for p in pack.files()]
    assert any("integrations/forward-to-agent/" in f for f in files)
    assert any("integrations/book-viewing/" in f for f in files)


def test_legal_pack_has_intake_but_no_booking():
    """Legal intentionally omits a booking integration — conflict check must
    happen before any calendar slot is offered."""
    pack = TemplatePack("legal")
    files = [str(p) for p in pack.files()]
    assert any("integrations/forward-to-firm/" in f for f in files)
    assert not any("book-" in f and "/integrations/" in f for f in files)


def test_legal_intake_references_conflict_check():
    """Legal intake skill must explicitly mention conflict-check before booking."""
    pack = TemplatePack("legal")
    intake = (pack.root / "agent-skills" / "intake-consultation.md").read_text(encoding="utf-8")
    assert "conflict" in intake.lower() or "利益相反" in intake
    assert "CONFLICT_CHECK_NEEDED" in intake


def test_legal_understand_firm_forbids_legal_opinions():
    """Defensive: the foundational skill must contain explicit no-legal-advice guidance."""
    pack = TemplatePack("legal")
    body = (pack.root / "agent-skills" / "understand-firm.md").read_text(encoding="utf-8")
    assert "弁護士" in body
    # At least one of the forbidden-phrase markers should appear.
    assert "勝てそう" in body or "違法" in body


def test_realestate_qualify_buyer_uses_temperature_tag():
    pack = TemplatePack("real-estate")
    body = (pack.root / "agent-skills" / "qualify-buyer.md").read_text(encoding="utf-8")
    for tag in ("HOT", "WARM", "COOL"):
        assert f"[temp:{tag}]" in body or tag in body
