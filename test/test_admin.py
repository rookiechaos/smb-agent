"""Tests for the admin diagnostic interface."""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from smbagent.config import Config
from smbagent.observability import RuntimeLogger
from smbagent.server import create_app
from smbagent.types import (
    AgentSkillSpec,
    IntegrationSpec,
    LandingPageSpec,
    Plan,
    Qualification,
    Requirements,
    Tier,
    Verdict,
)
from smbagent.workspace import Workspace

# ---- Fixtures ----


@pytest.fixture
def admin_config(config: Config) -> Config:
    """Same as `config` but with a real admin token set."""
    return replace(config, admin_token="secret-admin-token-for-tests")


@pytest.fixture
def admin_client(admin_config: Config) -> Iterator[TestClient]:
    app = create_app(admin_config)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def no_admin_client(config: Config) -> Iterator[TestClient]:
    """Server with admin_token unset — all /admin/* must return 503."""
    app = create_app(config)
    with TestClient(app) as client:
        yield client


def _admin_headers() -> dict:
    return {"Authorization": "Bearer secret-admin-token-for-tests"}


def _populate_full_customer(workspace: Workspace, *, passed: bool = True) -> None:
    workspace.save_qualification(
        Qualification(
            customer_id=workspace.customer_id,
            go=True,
            recommended_tier=Tier.GROWTH,
            summary_ja="ok",
        )
    )
    workspace.save_requirements(
        Requirements(
            customer_id=workspace.customer_id,
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
    workspace.save_plan(
        Plan(
            tier=Tier.GROWTH,
            summary="ok",
            landing_page=LandingPageSpec(pages=["/"], hero_copy_outline="o", primary_cta="c"),
            agent_skills=[AgentSkillSpec(name="understand-x", description="d", system_prompt_outline="o")],
            integrations=[IntegrationSpec(name="Gmail", purpose="x")],
        ),
        plan_md="# plan",
    )
    workspace.save_verdict(Verdict(passed=passed, round=1, summary="r", issues=[]))


def _populate_minimal_code(workspace: Workspace) -> None:
    (workspace.code_dir / "agent-skills").mkdir(exist_ok=True)
    (workspace.code_dir / "agent-skills" / "understand-x.md").write_text(
        "---\nname: understand-x\ndescription: d\n---\n\nb",
        encoding="utf-8",
    )
    (workspace.code_dir / "landing-page").mkdir(exist_ok=True)
    (workspace.code_dir / "landing-page" / "index.html").write_text("<html/>", encoding="utf-8")
    (workspace.code_dir / "README.md").write_text("# r", encoding="utf-8")


# ============================================================================
# Auth — admin endpoints are opt-in (require SMBAGENT_ADMIN_TOKEN)
# ============================================================================


def test_admin_endpoints_503_when_token_unset(no_admin_client: TestClient):
    r = no_admin_client.get("/admin/customers")
    assert r.status_code == 503
    assert "disabled" in r.json()["detail"].lower()


def test_admin_endpoints_503_for_diagnose_when_token_unset(no_admin_client: TestClient):
    r = no_admin_client.get(
        "/admin/customers/foo/diagnose",
        headers={"Authorization": "Bearer anything"},
    )
    assert r.status_code == 503


def test_admin_endpoints_503_for_health_when_token_unset(no_admin_client: TestClient):
    r = no_admin_client.get("/admin/health")
    assert r.status_code == 503


def test_admin_endpoint_401_with_missing_bearer(admin_client: TestClient):
    r = admin_client.get("/admin/customers")
    assert r.status_code == 401


def test_admin_endpoint_401_with_wrong_token(admin_client: TestClient):
    r = admin_client.get(
        "/admin/customers",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert r.status_code == 401


def test_admin_endpoint_401_with_non_bearer_scheme(admin_client: TestClient):
    r = admin_client.get(
        "/admin/customers",
        headers={"Authorization": "Basic abcd"},
    )
    assert r.status_code == 401


def test_admin_endpoint_200_with_correct_token(admin_client: TestClient):
    r = admin_client.get("/admin/customers", headers=_admin_headers())
    assert r.status_code == 200


# ============================================================================
# /admin/customers — listing
# ============================================================================


def test_admin_customers_empty(admin_client: TestClient, admin_config: Config):
    """No workspaces present → empty list, not 404."""
    admin_config.workspaces_dir.mkdir(parents=True, exist_ok=True)
    r = admin_client.get("/admin/customers", headers=_admin_headers())
    assert r.status_code == 200
    assert r.json() == []


def test_admin_customers_lists_each(admin_client: TestClient, admin_config: Config):
    ws_a = Workspace("alpha", admin_config.workspaces_dir)
    ws_a.ensure()
    _populate_full_customer(ws_a, passed=True)
    time.sleep(0.02)
    ws_b = Workspace("beta", admin_config.workspaces_dir)
    ws_b.ensure()
    _populate_full_customer(ws_b, passed=False)

    r = admin_client.get("/admin/customers", headers=_admin_headers())
    assert r.status_code == 200
    body = r.json()
    assert {c["customer_id"] for c in body} == {"alpha", "beta"}

    # Per-customer fields populated
    alpha = next(c for c in body if c["customer_id"] == "alpha")
    assert alpha["go"] is True
    assert alpha["tier"] == "growth"
    assert alpha["has_requirements"] is True
    assert alpha["has_plan"] is True
    assert alpha["last_verdict_round"] == 1
    assert alpha["last_verdict_passed"] is True

    beta = next(c for c in body if c["customer_id"] == "beta")
    assert beta["last_verdict_passed"] is False


def test_admin_customers_sorted_most_recent_first(admin_client: TestClient, admin_config: Config):
    ws_a = Workspace("older", admin_config.workspaces_dir)
    ws_a.ensure()
    _populate_full_customer(ws_a)
    time.sleep(0.05)
    ws_b = Workspace("newer", admin_config.workspaces_dir)
    ws_b.ensure()
    _populate_full_customer(ws_b)

    body = admin_client.get("/admin/customers", headers=_admin_headers()).json()
    assert [c["customer_id"] for c in body] == ["newer", "older"]


# ============================================================================
# /admin/customers/{id}/diagnose
# ============================================================================


def test_diagnose_404_for_unknown_customer(admin_client: TestClient):
    r = admin_client.get(
        "/admin/customers/ghost/diagnose",
        headers=_admin_headers(),
    )
    assert r.status_code == 404


def test_diagnose_400_for_invalid_customer_id(admin_client: TestClient):
    r = admin_client.get(
        "/admin/customers/..%2Fetc/diagnose",
        headers=_admin_headers(),
    )
    assert r.status_code in (400, 404)  # depending on FastAPI path decoding


def test_diagnose_empty_workspace(admin_client: TestClient, admin_config: Config):
    Workspace("empty", admin_config.workspaces_dir).ensure()
    r = admin_client.get(
        "/admin/customers/empty/diagnose",
        headers=_admin_headers(),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["customer_id"] == "empty"
    assert body["workspace_exists"] is True
    assert body["artifacts"]["qualification"] is False
    assert body["artifacts"]["requirements"] is False
    assert body["tier"] is None
    assert body["runtime_cached"] is False
    # Without a tier we can't run structural checks
    assert body["structural_issues"] == []
    assert any("tier" in n.lower() for n in body["notes"])


def test_diagnose_full_workspace_no_structural_issues(admin_client: TestClient, admin_config: Config):
    ws = Workspace("healthy", admin_config.workspaces_dir)
    ws.ensure()
    _populate_full_customer(ws)
    _populate_minimal_code(ws)

    body = admin_client.get(
        "/admin/customers/healthy/diagnose",
        headers=_admin_headers(),
    ).json()
    assert body["tier"] == "growth"
    # All four artifact flags true
    assert body["artifacts"]["qualification"] is True
    assert body["artifacts"]["requirements"] is True
    assert body["artifacts"]["plan"] is True
    assert body["artifacts"]["tasks"] is True
    assert body["artifacts"]["code_readme"] is True
    # No structural issues — code/ has the required artifacts
    assert body["structural_issues"] == []


def test_diagnose_surfaces_structural_issues(admin_client: TestClient, admin_config: Config):
    """A workspace with requirements but an empty code/ should surface critical issues."""
    ws = Workspace("broken", admin_config.workspaces_dir)
    ws.ensure()
    _populate_full_customer(ws)
    # NOTE: not calling _populate_minimal_code — code/ is empty
    body = admin_client.get(
        "/admin/customers/broken/diagnose",
        headers=_admin_headers(),
    ).json()
    severities = {i["severity"] for i in body["structural_issues"]}
    assert "critical" in severities
    descs = " ".join(i["description"] for i in body["structural_issues"])
    assert "agent-skills" in descs
    assert "landing-page" in descs


def test_diagnose_includes_recent_chat_events(admin_client: TestClient, admin_config: Config):
    ws = Workspace("chatty", admin_config.workspaces_dir)
    ws.ensure()
    _populate_full_customer(ws)
    _populate_minimal_code(ws)

    logger = RuntimeLogger(ws)
    for i in range(3):
        logger.record(
            user_message_len=10 + i,
            reply_len=20 + i,
            skill_used=f"s{i}",
            latency_ms=100 + i,
        )

    body = admin_client.get(
        "/admin/customers/chatty/diagnose",
        headers=_admin_headers(),
    ).json()
    events = body["recent_chat_events"]
    assert len(events) == 3
    assert [e["skill_used"] for e in events] == ["s0", "s1", "s2"]


def test_diagnose_caps_recent_chat_events_to_20(admin_client: TestClient, admin_config: Config):
    ws = Workspace("verbose", admin_config.workspaces_dir)
    ws.ensure()
    _populate_full_customer(ws)
    _populate_minimal_code(ws)
    logger = RuntimeLogger(ws)
    for i in range(50):
        logger.record(
            user_message_len=1,
            reply_len=1,
            skill_used=f"s{i}",
            latency_ms=1,
        )
    body = admin_client.get(
        "/admin/customers/verbose/diagnose",
        headers=_admin_headers(),
    ).json()
    assert len(body["recent_chat_events"]) == 20
    # Last 20 are returned (most recent)
    assert body["recent_chat_events"][-1]["skill_used"] == "s49"


def test_diagnose_corrupt_requirements_notes_it(admin_client: TestClient, admin_config: Config):
    ws = Workspace("corrupt", admin_config.workspaces_dir)
    ws.ensure()
    ws.requirements_path.write_text("not json", encoding="utf-8")
    body = admin_client.get(
        "/admin/customers/corrupt/diagnose",
        headers=_admin_headers(),
    ).json()
    assert any("requirements.json" in n for n in body["notes"])


# ============================================================================
# /admin/health
# ============================================================================


def test_admin_health_returns_aggregates(admin_client: TestClient, admin_config: Config):
    # Set up 3 customers in different states
    ws1 = Workspace("go-passed", admin_config.workspaces_dir)
    ws1.ensure()
    _populate_full_customer(ws1, passed=True)
    ws2 = Workspace("go-failed", admin_config.workspaces_dir)
    ws2.ensure()
    _populate_full_customer(ws2, passed=False)
    ws3 = Workspace("nogo", admin_config.workspaces_dir)
    ws3.ensure()
    ws3.save_qualification(
        Qualification(
            customer_id="nogo",
            go=False,
            recommended_tier=None,
            summary_ja="not a fit",
        )
    )

    r = admin_client.get("/admin/health", headers=_admin_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["customer_count"] == 3
    assert body["go_count"] == 2
    assert body["no_go_count"] == 1
    assert body["passed_latest_count"] == 1
    assert body["failed_latest_count"] == 1
    assert body["runtime_cache_size"] == 0  # nothing chatted yet


def test_admin_health_runtime_cache_size_grows_with_use(admin_client: TestClient, admin_config: Config):
    ws = Workspace("active", admin_config.workspaces_dir)
    ws.ensure()
    _populate_minimal_code(ws)
    # Force runtime cache population by hitting the public skills endpoint
    admin_client.get("/v1/customers/active/skills.json")

    body = admin_client.get("/admin/health", headers=_admin_headers()).json()
    assert body["runtime_cache_size"] == 1


# ============================================================================
# Root-route discovery
# ============================================================================


def test_root_lists_admin_endpoints(admin_client: TestClient):
    body = admin_client.get("/").json()
    endpoint_text = " ".join(body["endpoints"])
    assert "/admin/customers" in endpoint_text
    assert "/admin/health" in endpoint_text
    assert "iteration-tuning" in endpoint_text


# ============================================================================
# /admin/iteration-tuning
# ============================================================================


def test_global_iteration_tuning_get_and_put(admin_client: TestClient, admin_config: Config):
    r = admin_client.get("/admin/iteration-tuning", headers=_admin_headers())
    assert r.status_code == 200
    assert r.json()["effective"]["anneal_temp_creative"] == 0.7

    r2 = admin_client.put(
        "/admin/iteration-tuning",
        headers=_admin_headers(),
        json={"anneal_temp_creative": 0.65, "notes": "post-launch tune"},
    )
    assert r2.status_code == 200
    assert r2.json()["effective"]["anneal_temp_creative"] == 0.65
    assert r2.json()["global_override"]["notes"] == "post-launch tune"

    path = admin_config.root / "tuning" / "iteration.json"
    assert path.exists()


def test_customer_iteration_tuning_put(admin_client: TestClient, admin_config: Config):
    ws = Workspace("tuned", admin_config.workspaces_dir)
    ws.ensure()
    r = admin_client.put(
        "/admin/customers/tuned/iteration-tuning",
        headers=_admin_headers(),
        json={"anneal_temp_final": 0.05, "bridge_orchestrator_enabled": False},
    )
    assert r.status_code == 200
    assert r.json()["effective"]["anneal_temp_final"] == 0.05
    assert r.json()["customer_override"]["bridge_orchestrator_enabled"] is False


def test_iteration_tuning_requires_admin(no_admin_client: TestClient):
    assert no_admin_client.get("/admin/iteration-tuning").status_code == 503
