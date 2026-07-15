"""Unit tests for smbagent/server/onboarding.py — slugify + onboard()."""

from __future__ import annotations

import pytest

from smbagent.config import Config
from smbagent.server.onboarding import (
    DuplicateCustomerError,
    OnboardingError,
    onboard,
    slugify_business_name,
)
from smbagent.types import Qualification, Tier

# ---- slugify ----


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Acme Co", "acme-co"),
        ("Acme Dental Co.", "acme-dental-co"),
        ("  Spaces   Galore  ", "spaces-galore"),
        ("UPPER", "upper"),
        ("A&B", "a-b"),
        ("Company123", "company123"),
        ("multi___underscores", "multi-underscores"),
        ("hyphen-already-here", "hyphen-already-here"),
        ("a..b..c", "a..b..c"),
    ],
)
def test_slugify_basic(raw: str, expected: str):
    assert slugify_business_name(raw) == expected


def test_slugify_strips_leading_punctuation():
    """customer_id must start with [a-zA-Z0-9] per Workspace regex."""
    out = slugify_business_name("---abc")
    assert out.startswith("a")


def test_slugify_truncates_to_64_chars():
    long = "a" * 100
    out = slugify_business_name(long)
    assert len(out) <= 64
    assert out.startswith("a")


def test_slugify_unicode_japanese():
    """Japanese characters get stripped (after NFKD they aren't ASCII alnum).
    Result is a hyphen-separated remainder."""
    out = slugify_business_name("東京 Dental Clinic")
    # The JP chars are dropped; ASCII tokens survive.
    assert "dental" in out
    assert "clinic" in out


def test_slugify_xss_attempt_neutralized():
    """<script> tokens collapse into hyphens; no angle brackets in output."""
    out = slugify_business_name("<script>alert(1)</script>Acme")
    assert "<" not in out and ">" not in out
    assert "acme" in out


def test_slugify_returns_empty_for_all_non_alnum():
    assert slugify_business_name("---") == ""
    assert slugify_business_name("...") == ""
    assert slugify_business_name("") == ""


def test_slugify_collapses_consecutive_separators():
    assert slugify_business_name("a---b") == "a-b"
    assert slugify_business_name("a   b   c") == "a-b-c"


# ---- onboard() ----


def _stub_factory(go: bool = True, tier: str | None = "growth"):
    class _Fake:
        def __init__(self, _config):
            pass

        def run(self, workspace, brief):
            t = Tier(tier) if tier else None
            q = Qualification(
                customer_id=workspace.customer_id,
                go=go,
                recommended_tier=t,
                summary_ja="fake",
            )
            workspace.save_qualification(q)
            return q

    return _Fake


def test_onboard_creates_workspace_and_qualification(config: Config):
    q = onboard(
        config=config,
        business_name="Test Clinic",
        contact_email="x@y.com",
        brief="A test clinic doing test things.",
        qualify_agent_factory=_stub_factory(),
    )
    assert q.customer_id == "test-clinic"
    assert (config.workspaces_dir / "test-clinic" / "qualification.json").exists()


def test_onboard_passes_enriched_brief_to_agent(config: Config):
    captured = {}

    class _Capture:
        def __init__(self, _config):
            pass

        def run(self, workspace, brief):
            captured["brief"] = brief
            q = Qualification(
                customer_id=workspace.customer_id,
                go=True,
                recommended_tier=Tier.STARTER,
                summary_ja=".",
            )
            workspace.save_qualification(q)
            return q

    onboard(
        config=config,
        business_name="Acme",
        contact_email="ceo@acme.example",
        brief="brief text here that is at least twenty characters long",
        qualify_agent_factory=_Capture,
    )
    enriched = captured["brief"]
    assert "Business name: Acme" in enriched
    assert "ceo@acme.example" in enriched
    assert "brief text here" in enriched


def test_onboard_duplicate_workspace_raises(config: Config):
    onboard(
        config=config,
        business_name="Same Name Co",
        contact_email="x@y.com",
        brief="Some description that is at least twenty characters.",
        qualify_agent_factory=_stub_factory(),
    )
    with pytest.raises(DuplicateCustomerError):
        onboard(
            config=config,
            business_name="Same Name Co",
            contact_email="x@y.com",
            brief="Some description that is at least twenty characters.",
            qualify_agent_factory=_stub_factory(),
        )


def test_onboard_empty_slug_raises_onboarding_error(config: Config):
    with pytest.raises(OnboardingError):
        onboard(
            config=config,
            business_name="・・・",  # slugifies to empty
            contact_email="x@y.com",
            brief="A clinic description longer than twenty characters in total.",
            qualify_agent_factory=_stub_factory(),
        )


def test_onboard_propagates_qualify_failures(config: Config):
    class _Boom:
        def __init__(self, _config):
            pass

        def run(self, workspace, brief):
            raise RuntimeError("LLM is down")

    with pytest.raises(RuntimeError) as excinfo:
        onboard(
            config=config,
            business_name="Acme Co",
            contact_email="x@y.com",
            brief="A clinic description longer than twenty characters in total.",
            qualify_agent_factory=_Boom,
        )
    assert "LLM is down" in str(excinfo.value)


def test_onboard_handles_no_go_qualification(config: Config):
    q = onboard(
        config=config,
        business_name="Out Of Scope LLC",
        contact_email="x@y.com",
        brief="A multinational bank with thousands of employees that needs global AI rollout.",
        qualify_agent_factory=_stub_factory(go=False, tier=None),
    )
    assert q.go is False
    assert q.recommended_tier is None
    # Even no-go qualifications are persisted
    assert (config.workspaces_dir / "out-of-scope-llc" / "qualification.json").exists()
