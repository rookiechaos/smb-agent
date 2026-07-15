"""Tests for the pioneer-readiness features.

Covers: CORS, security headers (CSP / framing / nosniff), rate limiting,
alert webhook, /metrics endpoint, token TTL + revocation, pipeline timeout,
subprocess pid tracking, transports back-compat shim.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from smbagent.auth import (
    issue_token,
    load_token,
    revoke_token,
    verify_token,
)
from smbagent.config import Config
from smbagent.observability import AlertHook
from smbagent.observability import alerts as alerts_mod
from smbagent.server import create_app
from smbagent.server.rate_limit import OnboardingAbuseProtector, RateLimiter, client_ip
from smbagent.workspace import Workspace

# ============================================================================
# Rate limiter (unit)
# ============================================================================


def test_rate_limiter_allows_first_request_under_cap():
    rl = RateLimiter(max_events=3, per_seconds=60)
    for _ in range(3):
        ok, retry = rl.check("k")
        assert ok and retry == 0


def test_rate_limiter_blocks_after_cap():
    rl = RateLimiter(max_events=2, per_seconds=60)
    rl.check("k")
    rl.check("k")
    ok, retry = rl.check("k")
    assert not ok
    assert retry >= 1


def test_rate_limiter_separate_keys_dont_share_budget():
    rl = RateLimiter(max_events=1, per_seconds=60)
    assert rl.check("a")[0] is True
    assert rl.check("b")[0] is True
    assert rl.check("a")[0] is False
    assert rl.check("b")[0] is False


def test_rate_limiter_window_expires():
    rl = RateLimiter(max_events=1, per_seconds=0.05)
    rl.check("k")
    assert rl.check("k")[0] is False
    time.sleep(0.07)
    assert rl.check("k")[0] is True


def test_rate_limiter_reset_clears_key():
    rl = RateLimiter(max_events=1, per_seconds=60)
    rl.check("k")
    assert rl.check("k")[0] is False
    rl.reset("k")
    assert rl.check("k")[0] is True


def test_rate_limiter_thread_safe_under_contention():
    rl = RateLimiter(max_events=100, per_seconds=60)
    hits = []

    def worker():
        for _ in range(20):
            hits.append(rl.check("contended")[0])

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly 100 allowed, 100 blocked.
    assert hits.count(True) == 100
    assert hits.count(False) == 100


# ============================================================================
# CORS + security headers (via HTTP)
# ============================================================================


@pytest.fixture
def cors_config(config: Config) -> Config:
    return replace(config, cors_origins=["https://acme.example"])


@pytest.fixture
def cors_client(cors_config: Config) -> Iterator[TestClient]:
    app = create_app(cors_config)
    with TestClient(app) as client:
        yield client


def test_cors_preflight_returns_allowed_headers(cors_client: TestClient):
    r = cors_client.options(
        "/v1/customers/x/skills.json",
        headers={
            "Origin": "https://acme.example",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert r.status_code in (200, 204)
    assert r.headers.get("access-control-allow-origin") == "https://acme.example"


def test_cors_blocks_disallowed_origin(cors_client: TestClient):
    r = cors_client.get(
        "/healthz",
        headers={"Origin": "https://evil.example"},
    )
    # Healthz still responds 200; CORS header just isn't echoed for the wrong origin.
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") != "https://evil.example"


def test_csp_header_on_html_responses(cors_client: TestClient):
    r = cors_client.get("/onboard")
    assert r.status_code == 200
    csp = r.headers.get("content-security-policy")
    assert csp is not None
    assert "default-src 'self'" in csp
    assert r.headers.get("x-frame-options") == "DENY"


def test_nosniff_header_on_all_responses(cors_client: TestClient):
    r = cors_client.get("/healthz")
    assert r.headers.get("x-content-type-options") == "nosniff"


# ============================================================================
# Rate limiter applied to /onboard + /chat
# ============================================================================


@pytest.fixture
def strict_rate_config(config: Config) -> Config:
    """Very tight limits so we can easily hit them in tests."""
    return replace(
        config,
        onboard_rate_per_hour=2,
        chat_rate_per_minute=2,
    )


@pytest.fixture
def strict_client(strict_rate_config: Config) -> Iterator[TestClient]:
    app = create_app(strict_rate_config)
    with TestClient(app) as client:
        yield client


def test_onboard_rate_limit_returns_429(strict_client: TestClient, monkeypatch):
    """Third onboarding attempt from same IP hits 429 with Retry-After."""
    from smbagent.server import onboarding as onboarding_mod
    from smbagent.types import Qualification, Tier

    class _Stub:
        def __init__(self, _cfg):
            pass

        def run(self, ws, brief):
            q = Qualification(
                customer_id=ws.customer_id, go=True, recommended_tier=Tier.STARTER, summary_ja="."
            )
            ws.save_qualification(q)
            return q

    monkeypatch.setattr(onboarding_mod, "QualifyAgent", _Stub)

    payload = lambda i: {
        "business_name": f"Acme {i} Co",
        "contact_email": "x@y.com",
        "brief": "Long enough description of an SMB customer's needs and goals.",
    }
    r1 = strict_client.post("/v1/onboard", json=payload(1))
    r2 = strict_client.post("/v1/onboard", json=payload(2))
    r3 = strict_client.post("/v1/onboard", json=payload(3))
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    assert r3.headers.get("retry-after") is not None
    assert int(r3.headers["retry-after"]) >= 1


def test_chat_rate_limit_returns_429(strict_client: TestClient, strict_rate_config: Config):
    """No agent-skills/ in the customer's workspace → runtime returns 503 fast
    (no LLM call). The point of this test is the rate limiter at the 3rd request."""
    ws = Workspace("chatty-co", strict_rate_config.workspaces_dir)
    ws.ensure()  # creates code/ but NOT agent-skills/
    token = issue_token(ws).token
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"message": "hi"}

    # First two requests pass rate-limit, fail at runtime with 503 (no skills).
    r1 = strict_client.post("/v1/customers/chatty-co/chat", json=payload, headers=headers)
    r2 = strict_client.post("/v1/customers/chatty-co/chat", json=payload, headers=headers)
    r3 = strict_client.post("/v1/customers/chatty-co/chat", json=payload, headers=headers)

    assert r1.status_code == 503 and r2.status_code == 503  # rate limiter let them through
    assert r3.status_code == 429
    assert r3.headers.get("retry-after") is not None


# ============================================================================
# Alert webhook
# ============================================================================


def test_alert_hook_noop_when_no_webhook():
    hook = AlertHook(None)
    rec = hook.fire("test_event", "something happened")
    assert rec.event == "test_event"
    assert len(hook.fired) == 1


def test_alert_hook_posts_to_webhook(monkeypatch):
    captured: dict = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["data"] = request.data
        captured["headers"] = dict(request.headers)

        class _R:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b"ok"

        return _R()

    monkeypatch.setattr(alerts_mod.urllib.request, "urlopen", fake_urlopen)
    hook = AlertHook("https://hooks.example/x")
    hook.fire("pipeline_timeout", "limit exceeded", severity="error", customer_id="acme")

    assert captured["url"] == "https://hooks.example/x"
    body = json.loads(captured["data"])
    assert body["event"] == "pipeline_timeout"
    assert body["severity"] == "error"
    assert body["customer_id"] == "acme"
    assert body["message"] == "limit exceeded"
    # Headers must be Content-Type: application/json
    ct = captured["headers"].get("Content-type") or captured["headers"].get("Content-Type")
    assert ct == "application/json"


def test_alert_hook_swallows_webhook_failures(monkeypatch):
    def boom(request, timeout=None):
        raise urllib.error.URLError("dns down")

    monkeypatch.setattr(alerts_mod.urllib.request, "urlopen", boom)
    hook = AlertHook("https://hooks.example/x")
    # Must not raise — alerting is best-effort.
    rec = hook.fire("test", "msg")
    assert rec.event == "test"


def test_alert_hook_records_locally_even_when_webhook_fails(monkeypatch):
    def boom(request, timeout=None):
        raise urllib.error.URLError("dns down")

    monkeypatch.setattr(alerts_mod.urllib.request, "urlopen", boom)
    hook = AlertHook("https://hooks.example/x")
    hook.fire("a", "x")
    hook.fire("b", "y")
    assert [e.event for e in hook.fired] == ["a", "b"]


# ============================================================================
# Token TTL + revocation
# ============================================================================


def test_token_with_ttl_has_expires_at(config: Config, workspace: Workspace):
    rec = issue_token(workspace, ttl_days=30)
    assert rec.expires_at is not None
    assert rec.is_expired() is False


def test_token_without_ttl_never_expires(config: Config, workspace: Workspace):
    rec = issue_token(workspace, ttl_days=0)
    assert rec.expires_at is None
    assert rec.is_expired() is False


def test_token_expired_after_ttl(config: Config, workspace: Workspace, monkeypatch):
    """Mock the current time so we can check expiry without sleeping."""
    rec = issue_token(workspace, ttl_days=1)
    assert rec.is_expired() is False

    # Move 2 days forward via monkeypatched datetime
    from datetime import UTC, datetime, timedelta

    fake_now = datetime.now(UTC) + timedelta(days=2)
    assert rec.is_expired(now=fake_now) is True


def test_verify_token_rejects_expired_token(config: Config, workspace: Workspace):
    """An on-disk token with a past expiry must not verify."""
    # Issue a token, then rewrite auth.json with a past expires_at.
    rec = issue_token(workspace)
    from datetime import UTC, datetime, timedelta

    past = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rec_expired = replace(rec, expires_at=past)
    (workspace.path / "auth.json").write_text(rec_expired.as_json(), encoding="utf-8")
    assert verify_token(workspace, rec_expired.token) is False


def test_revoke_token_invalidates_verification(config: Config, workspace: Workspace):
    rec = issue_token(workspace)
    assert verify_token(workspace, rec.token) is True
    revoke_token(workspace)
    assert verify_token(workspace, rec.token) is False


def test_revoked_token_persists_to_disk(config: Config, workspace: Workspace):
    issue_token(workspace)
    revoke_token(workspace)
    loaded = load_token(workspace)
    assert loaded.revoked is True


def test_legacy_auth_json_without_expires_at_still_verifies(config: Config, workspace: Workspace):
    """Older auth.json files without expires_at / revoked must still validate."""
    legacy_blob = json.dumps(
        {
            "customer_id": workspace.customer_id,
            "token": "abc123",
            "created_at": "2024-01-01T00:00:00Z",
            # NO expires_at, NO revoked
        }
    )
    workspace.ensure()
    (workspace.path / "auth.json").write_text(legacy_blob, encoding="utf-8")
    assert verify_token(workspace, "abc123") is True


def test_token_with_malformed_expiry_fails_closed(config: Config, workspace: Workspace):
    rec = issue_token(workspace)
    bad = replace(rec, expires_at="not-a-date")
    (workspace.path / "auth.json").write_text(bad.as_json(), encoding="utf-8")
    # Fail closed: malformed expiry → reject.
    assert verify_token(workspace, bad.token) is False


# ============================================================================
# /metrics endpoint
# ============================================================================


@pytest.fixture
def admin_metrics_config(config: Config) -> Config:
    return replace(config, admin_token="metrics-admin-token")


@pytest.fixture
def metrics_client(admin_metrics_config: Config) -> Iterator[TestClient]:
    app = create_app(admin_metrics_config)
    with TestClient(app) as client:
        yield client


def _metrics_headers() -> dict:
    return {"Authorization": "Bearer metrics-admin-token"}


def test_metrics_503_when_admin_token_unset(config: Config):
    app = create_app(config)
    with TestClient(app) as client:
        r = client.get("/metrics")
        assert r.status_code == 503


def test_metrics_401_without_auth(metrics_client: TestClient):
    r = metrics_client.get("/metrics")
    assert r.status_code == 401


def test_metrics_returns_prometheus_text(metrics_client: TestClient):
    r = metrics_client.get("/metrics", headers=_metrics_headers())
    assert r.status_code == 200
    body = r.text
    # Spec format: each metric has # HELP, # TYPE, value lines
    assert "# HELP smbagent_customers_total" in body
    assert "# TYPE smbagent_customers_total gauge" in body
    assert "smbagent_customers_total 0" in body  # no customers
    # Counters present too
    assert "smbagent_chat_events_recent_total" in body


def test_metrics_reflects_customer_count(metrics_client: TestClient, admin_metrics_config: Config):
    for name in ("a", "b", "c"):
        ws = Workspace(name, admin_metrics_config.workspaces_dir)
        ws.ensure()
    body = metrics_client.get("/metrics", headers=_metrics_headers()).text
    assert "smbagent_customers_total 3" in body


# ============================================================================
# Transports back-compat shim
# ============================================================================


def test_old_integrations_runtime_import_still_works():
    """The renamed package keeps a shim — importing the old path should warn
    but succeed."""
    import warnings

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        from smbagent.integrations_runtime import MailForwarder, MemoryMailTransport  # noqa: F401
    # DeprecationWarning fired
    assert any("renamed" in str(w.message).lower() for w in caught)


def test_transports_package_is_the_new_canonical_home():
    """The same symbols import from the new location without any warning."""
    from smbagent.transports import MailForwarder, MemoryMailTransport  # noqa: F401
    # No-op — just verifying the import chain is valid.


# ============================================================================
# client_ip helper
# ============================================================================


def test_client_ip_returns_socket_when_no_forwarded_header():
    from starlette.requests import Request

    scope = {"type": "http", "client": ("198.51.100.7", 12345), "headers": []}
    req = Request(scope)
    assert client_ip(req) == "198.51.100.7"


def test_client_ip_honors_x_forwarded_for_first_hop():
    from starlette.requests import Request

    scope = {
        "type": "http",
        "client": ("10.0.0.1", 12345),
        "headers": [(b"x-forwarded-for", b"203.0.113.10, 198.51.100.5")],
    }
    req = Request(scope)
    assert client_ip(req) == "203.0.113.10"


def test_client_ip_returns_unknown_when_no_client_info():
    from starlette.requests import Request

    scope = {"type": "http", "client": None, "headers": []}
    req = Request(scope)
    assert client_ip(req) == "unknown"


def test_rate_limiter_persists_across_instances_with_sqlite_state(tmp_path):
    state_path = tmp_path / "rate_limits.sqlite3"
    a = RateLimiter(max_events=1, per_seconds=60, state_path=state_path, namespace="shared")
    b = RateLimiter(max_events=1, per_seconds=60, state_path=state_path, namespace="shared")
    assert a.check("k")[0] is True
    assert b.check("k")[0] is False


def test_onboarding_abuse_protector_blocks_repeat_fingerprint(tmp_path):
    state_path = tmp_path / "rate_limits.sqlite3"
    protector = OnboardingAbuseProtector(
        fingerprint_limiter=RateLimiter(
            max_events=1, per_seconds=86400, state_path=state_path, namespace="fp"
        ),
        contact_limiter=RateLimiter(
            max_events=5, per_seconds=86400, state_path=state_path, namespace="contact"
        ),
    )
    first = protector.evaluate(
        business_name="Acme",
        contact_email="owner@example.com",
        brief="Need a trustworthy SMB AI workflow for scheduling and operations.",
        client_ip="127.0.0.1",
    )
    second = protector.evaluate(
        business_name="Acme",
        contact_email="owner@example.com",
        brief="Need a trustworthy SMB AI workflow for scheduling and operations.",
        client_ip="127.0.0.1",
    )
    assert first.allowed is True
    assert second.allowed is False
    assert "repeat onboarding payload" in second.reason


def test_onboard_repeat_payload_returns_429(strict_rate_config: Config):
    cfg = replace(
        strict_rate_config,
        onboard_rate_per_hour=10,
        rate_limit_backend="sqlite-local",
        onboarding_repeat_fingerprint_per_day=1,
        onboarding_contact_rate_per_day=10,
    )
    app = create_app(cfg)
    with TestClient(app) as client:
        payload = {
            "business_name": "Acme Repeat Co",
            "contact_email": "x@y.com",
            "brief": "Long enough description of an SMB customer repeated for abuse-control testing.",
        }
        r1 = client.post("/v1/onboard", json=payload)
        r2 = client.post("/v1/onboard", json=payload)
        assert r1.status_code in (200, 500)
        assert r2.status_code == 429
