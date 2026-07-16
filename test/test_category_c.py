"""Coverage push for Category C — genuine error paths and edge cases.

Each test in this file targets a specific uncovered line range identified by
`pytest --cov-report=term-missing`. The goal isn't coverage-as-vanity-metric;
it's verifying that defensive error handlers actually behave as designed.
"""

from __future__ import annotations

import json
import urllib.error
from dataclasses import replace
from pathlib import Path

import pytest

from smbagent.config import Config
from smbagent.observability.transitions import _current_output_hash_for, hash_file
from smbagent.workspace import Workspace

# ============================================================================
# server/metrics.py — _read_chat_events edge cases
# ============================================================================


def test_read_chat_events_returns_zero_when_workspaces_dir_missing(tmp_path: Path):
    from smbagent.server.metrics import _read_chat_events

    total, errors = _read_chat_events(tmp_path / "does-not-exist")
    assert (total, errors) == (0, 0)


def test_read_chat_events_skips_non_directories_at_top(tmp_path: Path):
    """Stray files at workspaces/ root (like dashboard.html) must not crash."""
    from smbagent.server.metrics import _read_chat_events

    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "dashboard.html").write_text("...", encoding="utf-8")
    total, errors = _read_chat_events(tmp_path)
    assert (total, errors) == (0, 0)


def test_read_chat_events_skips_customers_without_chat_log(tmp_path: Path):
    from smbagent.server.metrics import _read_chat_events

    (tmp_path / "cust").mkdir()  # customer with no runtime/chat.jsonl
    total, errors = _read_chat_events(tmp_path)
    assert (total, errors) == (0, 0)


def test_read_chat_events_counts_events_and_errors(tmp_path: Path):
    from smbagent.server.metrics import _read_chat_events

    log_dir = tmp_path / "cust" / "runtime"
    log_dir.mkdir(parents=True)
    log = log_dir / "chat.jsonl"
    log.write_text(
        json.dumps({"skill_used": "x", "error": None})
        + "\n"
        + json.dumps({"skill_used": "y", "error": "boom"})
        + "\n"
        + json.dumps({"skill_used": "z", "error": None})
        + "\n",
        encoding="utf-8",
    )
    total, errors = _read_chat_events(tmp_path)
    assert total == 3
    assert errors == 1


def test_read_chat_events_skips_malformed_jsonl_lines(tmp_path: Path):
    """Garbage lines in the log don't kill the scan — they're silently skipped."""
    from smbagent.server.metrics import _read_chat_events

    log_dir = tmp_path / "cust" / "runtime"
    log_dir.mkdir(parents=True)
    log = log_dir / "chat.jsonl"
    log.write_text(
        json.dumps({"skill_used": "x"})
        + "\n"
        + "not json at all\n"
        + json.dumps({"skill_used": "y", "error": "oops"})
        + "\n",
        encoding="utf-8",
    )
    total, errors = _read_chat_events(tmp_path)
    # Only the 2 valid lines counted.
    assert total == 2
    assert errors == 1


def test_read_chat_events_tail_reads_large_files(tmp_path: Path):
    """For logs > 100KB, only the last 100KB is scanned (bounded read).
    Each event has padding so the file crosses the threshold in ~2000 lines."""
    from smbagent.server.metrics import _read_chat_events

    log_dir = tmp_path / "cust" / "runtime"
    log_dir.mkdir(parents=True)
    log = log_dir / "chat.jsonl"

    # ~80 bytes per line × 2000 ≈ 160KB — well past the 100KB threshold.
    padding = "x" * 50
    lines = [
        json.dumps({"skill_used": f"skill-{i:04d}", "error": None, "_pad": padding}) for i in range(2000)
    ]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert log.stat().st_size > 100_000  # sanity: tail-read branch will fire

    total, errors = _read_chat_events(tmp_path)
    # Tail-read sees fewer than all 2000 events but a meaningful number.
    assert 0 < total < 2000
    assert errors == 0


def test_read_chat_events_handles_oserror(tmp_path: Path, monkeypatch):
    """When the log file can't be opened, the scan moves on (no crash)."""
    from smbagent.server import metrics as metrics_mod

    log_dir = tmp_path / "cust" / "runtime"
    log_dir.mkdir(parents=True)
    log = log_dir / "chat.jsonl"
    log.write_text(json.dumps({"skill_used": "x"}) + "\n", encoding="utf-8")

    real_open = Path.open

    def fake_open(self, *args, **kwargs):
        if "chat.jsonl" in str(self):
            raise OSError("simulated permission denied")
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fake_open)
    total, errors = metrics_mod._read_chat_events(tmp_path)
    assert total == 0  # silently skipped


# ============================================================================
# observability/transitions.py — _current_output_hash_for branches
# ============================================================================


def test_current_hash_qualify_returns_file_hash(workspace: Workspace):
    workspace.qualification_path.write_text('{"x": 1}', encoding="utf-8")
    h = _current_output_hash_for(workspace, "qualify", None)
    assert h == hash_file(workspace.qualification_path)


def test_current_hash_qualify_returns_none_when_missing(workspace: Workspace):
    assert _current_output_hash_for(workspace, "qualify", None) is None


def test_current_hash_negotiation_combines_requirements_and_transcript(workspace: Workspace):
    workspace.requirements_path.write_text("req", encoding="utf-8")
    workspace.transcript_path.write_text("transcript", encoding="utf-8")
    h = _current_output_hash_for(workspace, "negotiation", None)
    assert h is not None
    # Determinism: same files → same hash
    h2 = _current_output_hash_for(workspace, "negotiation", None)
    assert h == h2


def test_current_hash_plan_combines_plan_and_tasks(workspace: Workspace):
    workspace.plan_path.write_text("# plan", encoding="utf-8")
    workspace.tasks_path.write_text('{"tier": "starter"}', encoding="utf-8")
    h = _current_output_hash_for(workspace, "plan", None)
    assert h is not None


def test_current_hash_coding_without_round_returns_none(workspace: Workspace):
    """Coding hash requires a round number — without it, can't locate the log."""
    assert _current_output_hash_for(workspace, "coding", None) is None


def test_current_hash_coding_returns_log_hash(workspace: Workspace):
    log = workspace.coding_log_path(1)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("claude output", encoding="utf-8")
    h = _current_output_hash_for(workspace, "coding", 1)
    assert h == hash_file(log)


def test_current_hash_coding_returns_none_when_log_missing(workspace: Workspace):
    """Round directory exists but the log file doesn't."""
    workspace.round_dir(1)  # creates the dir
    assert _current_output_hash_for(workspace, "coding", 1) is None


def test_current_hash_validation_combines_verdict_and_feedback(workspace: Workspace):
    workspace.verdict_path(1).write_text('{"passed": true}', encoding="utf-8")
    workspace.feedback_path(1).write_text("# PASSED", encoding="utf-8")
    h = _current_output_hash_for(workspace, "validation", 1)
    assert h is not None


def test_current_hash_validation_without_round_returns_none(workspace: Workspace):
    assert _current_output_hash_for(workspace, "validation", None) is None


def test_current_hash_unknown_agent_returns_none(workspace: Workspace):
    assert _current_output_hash_for(workspace, "exotic-agent", None) is None
    assert _current_output_hash_for(workspace, "exotic-agent", 5) is None


# ============================================================================
# orchestrator — deadline pre-stage halts
# ============================================================================


@pytest.fixture
def expired_deadline_pipeline(config: Config):
    """Pipeline configured with `pipeline_timeout_s=0` so the first deadline
    check fires immediately."""
    cfg = replace(config, pipeline_timeout_s=0)
    from smbagent.orchestrator import Pipeline

    p = Pipeline(cfg)
    # Replace all agents with no-op fakes so we never actually call them.

    class _Boom:
        def run(self, *a, **kw):
            raise AssertionError("agent should not run when deadline already expired")

    p.qualify = _Boom()
    p.negotiation = _Boom()
    p.plan = _Boom()
    p.coding = _Boom()
    p.validation = _Boom()
    return p, cfg


def test_pipeline_halts_at_qualify_if_deadline_already_expired(expired_deadline_pipeline, config: Config):
    """With pipeline_timeout_s=0, time.monotonic() > deadline immediately, so
    `_check_deadline("qualify")` returns False BEFORE any agent runs."""
    p, cfg = expired_deadline_pipeline
    result = p.run("acme-co", customer_brief="some brief")
    assert result is None  # halt
    # Alert was fired
    assert any(e.event == "pipeline_timeout" for e in p.alert_hook.fired)


def test_pipeline_halts_at_negotiation_if_deadline_expires_after_qualify(config: Config, monkeypatch):
    """Qualify completes successfully, then deadline expires before negotiation."""
    from smbagent.orchestrator import Pipeline
    from smbagent.types import Qualification, Tier

    p = Pipeline(config)
    times = iter([1000.0, 1000.5, 9_999_999.0, 9_999_999.0, 9_999_999.0])
    monkeypatch.setattr("smbagent.orchestrator.time.monotonic", lambda: next(times))

    class _OkQualify:
        def run(self, workspace, brief):
            q = Qualification(
                customer_id=workspace.customer_id,
                go=True,
                recommended_tier=Tier.STARTER,
                summary_ja=".",
            )
            workspace.save_qualification(q)
            return q

    class _Boom:
        def run(self, *a, **kw):
            raise AssertionError("should not run past expired deadline")

    p.qualify = _OkQualify()
    p.negotiation = _Boom()
    p.plan = _Boom()
    p.coding = _Boom()
    p.validation = _Boom()

    result = p.run("acme-co", customer_brief="brief")
    assert result is None
    assert any(e.event == "pipeline_timeout" for e in p.alert_hook.fired)


# NOTE on orchestrator.py:154-157 ("No tier could be resolved" branch):
# The Qualification Pydantic invariant guarantees go=True ⟹ recommended_tier
# is not None. After that invariant landed, that branch became defense-in-depth
# (dead under current invariants). We keep the branch as a safety net but don't
# write a test that has to fake-bypass Pydantic to reach it.


# ============================================================================
# safety — frontmatter validation edge cases
# ============================================================================


def test_validate_skill_frontmatter_unreadable_file(workspace: Workspace, monkeypatch):
    """When a skill .md can't be decoded as UTF-8, it surfaces as a major issue."""
    from smbagent.safety import validate_skill_frontmatter

    skills = workspace.code_dir / "agent-skills"
    skills.mkdir(parents=True, exist_ok=True)
    bad = skills / "binary.md"
    # Write bytes that are not valid UTF-8
    bad.write_bytes(b"\x80\x81\x82 not utf-8")

    issues = validate_skill_frontmatter(workspace.code_dir)
    assert any("could not read" in i.description.lower() for i in issues)


def test_validate_skill_frontmatter_name_present_but_blank_description(workspace: Workspace):
    """Description key exists but its value is empty/whitespace → flagged."""
    from smbagent.safety import validate_skill_frontmatter

    skills = workspace.code_dir / "agent-skills"
    skills.mkdir(parents=True, exist_ok=True)
    (skills / "x.md").write_text(
        "---\nname: x\ndescription: \n---\n\nbody",
        encoding="utf-8",
    )
    issues = validate_skill_frontmatter(workspace.code_dir)
    assert any("description" in i.description for i in issues)


# ============================================================================
# doctor — failure-path branches
# ============================================================================


def test_doctor_workspaces_writable_mkdir_fails(tmp_path: Path, monkeypatch):
    """If the workspaces dir can't be created, the doctor reports it cleanly."""
    from smbagent.doctor import check_workspaces_writable

    def fake_mkdir(self, *a, **kw):
        raise OSError("read-only filesystem")

    monkeypatch.setattr(Path, "mkdir", fake_mkdir)
    c = check_workspaces_writable(tmp_path / "ws")
    assert c.ok is False
    assert "could not create" in c.detail
    assert "write access" in c.hint


def test_doctor_config_loads_failure(monkeypatch):
    """When load_config() raises, the check surfaces the exception clearly."""
    from smbagent import doctor as doctor_mod

    def boom_loader(*a, **kw):
        raise ValueError("simulated bad .env value")

    monkeypatch.setattr("smbagent.config.load_config", boom_loader)
    c = doctor_mod.check_config_loads()
    assert c.ok is False
    assert "simulated bad .env value" in c.detail
    assert ".env" in c.hint


def test_run_doctor_checks_continues_when_load_config_fails(monkeypatch):
    """Even if load_config() itself raises, the cheap checks still run."""
    from smbagent import doctor as doctor_mod

    def boom_loader(*a, **kw):
        raise RuntimeError("config import broken")

    monkeypatch.setattr("smbagent.config.load_config", boom_loader)
    checks = doctor_mod.run_doctor_checks()
    # We still get a list of checks (with the config-loads one failing).
    assert len(checks) >= 5
    config_check = next(c for c in checks if c.name == "Configuration loads")
    assert config_check.ok is False


# ============================================================================
# workspace.size_bytes — stat-error branch
# ============================================================================


def test_size_bytes_zero_for_missing_workspace(config: Config):
    ws = Workspace("ghost", config.workspaces_dir)
    # Don't .ensure() — path doesn't exist
    assert ws.size_bytes() == 0


def test_size_bytes_handles_stat_error_per_file(workspace: Workspace, monkeypatch):
    """If one file's stat() raises (e.g. permission denied mid-walk), the
    walker continues rather than aborting the whole size calculation."""
    (workspace.path / "good.txt").write_text("hello", encoding="utf-8")
    (workspace.path / "bad.txt").write_text("world", encoding="utf-8")

    real_stat = Path.stat
    bad = workspace.path / "bad.txt"

    def fake_stat(self, *a, **kw):
        if self == bad:
            raise OSError("simulated permission denied")
        return real_stat(self, *a, **kw)

    monkeypatch.setattr(Path, "stat", fake_stat)
    size = workspace.size_bytes()
    # "hello" is 5 bytes; "bad.txt" is skipped due to OSError
    assert size == 5


# ============================================================================
# transports/booking — HTTP error edge cases
# ============================================================================


def _stub_urlopen(scripted: list, captured: list | None = None):
    """Helper from test_booking pattern."""
    captured = captured if captured is not None else []
    idx = {"n": 0}

    class _FakeResp:
        def __init__(self, body):
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return self._body

    def fake(request, timeout=None):  # noqa: ARG001
        if idx["n"] >= len(scripted):
            raise AssertionError("urlopen called more than scripted")
        item = scripted[idx["n"]]
        captured.append(request)
        idx["n"] += 1
        if isinstance(item, BaseException):
            raise item
        return _FakeResp(item)

    return fake


def test_booking_event_create_http_error_unreadable_detail(monkeypatch):
    """HTTPError where .read() itself raises — detail falls back to empty string."""
    from datetime import UTC, datetime

    from smbagent.transports import (
        BookingRequest,
        BookingTransportError,
        GoogleCalendarConfig,
        GoogleCalendarTransport,
    )
    from smbagent.transports import booking as booking_mod

    class _BrokenHTTPError(urllib.error.HTTPError):
        def read(self):
            raise OSError("can't read body")

    scripted = [
        json.dumps({"access_token": "abc"}).encode("utf-8"),
        _BrokenHTTPError("http://x", 500, "ISE", {}, None),  # type: ignore[arg-type]
    ]
    monkeypatch.setattr(
        booking_mod.urllib.request,
        "urlopen",
        _stub_urlopen(scripted),
    )

    t = GoogleCalendarTransport(
        GoogleCalendarConfig(
            client_id="c",
            client_secret="s",
            refresh_token="r",
        )
    )
    req = BookingRequest(
        summary="x",
        start=datetime(2026, 6, 1, 10, tzinfo=UTC),
        end=datetime(2026, 6, 1, 11, tzinfo=UTC),
    )
    with pytest.raises(BookingTransportError) as excinfo:
        t.create_event(req)
    # Detail was unreadable, so it's empty; error still surfaces the HTTP code
    assert "500" in str(excinfo.value)


def test_booking_event_create_urlerror_unreachable(monkeypatch):
    """urlopen raising URLError (DNS / network) wraps into BookingTransportError."""
    from datetime import UTC, datetime

    from smbagent.transports import (
        BookingRequest,
        BookingTransportError,
        GoogleCalendarConfig,
        GoogleCalendarTransport,
    )
    from smbagent.transports import booking as booking_mod

    scripted = [
        json.dumps({"access_token": "abc"}).encode("utf-8"),
        urllib.error.URLError("DNS failure"),
    ]
    monkeypatch.setattr(
        booking_mod.urllib.request,
        "urlopen",
        _stub_urlopen(scripted),
    )

    t = GoogleCalendarTransport(
        GoogleCalendarConfig(
            client_id="c",
            client_secret="s",
            refresh_token="r",
        )
    )
    req = BookingRequest(
        summary="x",
        start=datetime(2026, 6, 1, 10, tzinfo=UTC),
        end=datetime(2026, 6, 1, 11, tzinfo=UTC),
    )
    with pytest.raises(BookingTransportError) as excinfo:
        t.create_event(req)
    assert "unreachable" in str(excinfo.value).lower()


def test_booking_token_mint_http_error_unreadable_detail(monkeypatch):
    """During token mint, an HTTPError whose body can't be read."""
    from datetime import UTC, datetime

    from smbagent.transports import (
        BookingRequest,
        BookingTransportError,
        GoogleCalendarConfig,
        GoogleCalendarTransport,
    )
    from smbagent.transports import booking as booking_mod

    class _BrokenHTTPError(urllib.error.HTTPError):
        def read(self):
            raise OSError("body unreadable")

    monkeypatch.setattr(
        booking_mod.urllib.request,
        "urlopen",
        _stub_urlopen([_BrokenHTTPError("http://oauth", 401, "Unauthorized", {}, None)]),  # type: ignore[arg-type]
    )

    t = GoogleCalendarTransport(
        GoogleCalendarConfig(
            client_id="c",
            client_secret="s",
            refresh_token="r",
        )
    )
    req = BookingRequest(
        summary="x",
        start=datetime(2026, 6, 1, 10, tzinfo=UTC),
        end=datetime(2026, 6, 1, 11, tzinfo=UTC),
    )
    with pytest.raises(BookingTransportError) as excinfo:
        t.create_event(req)
    assert "401" in str(excinfo.value)


# ============================================================================
# transports/crm — HTTP error edge cases
# ============================================================================


def test_crm_post_http_error_unreadable_body(monkeypatch):
    """HubspotCrmTransport._post: HTTPError whose .read() also fails."""
    from smbagent.transports import (
        CrmContact,
        CrmTransportError,
        HubspotConfig,
        HubspotCrmTransport,
    )
    from smbagent.transports import crm as crm_mod

    class _BrokenHTTPError(urllib.error.HTTPError):
        def read(self):
            raise OSError("body gone")

    def fake(request, timeout=None):  # noqa: ARG001
        raise _BrokenHTTPError("http://hubapi", 502, "Bad Gateway", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(crm_mod.urllib.request, "urlopen", fake)
    with pytest.raises(CrmTransportError) as excinfo:
        HubspotCrmTransport(HubspotConfig(access_token="t")).create_contact(
            CrmContact(email="x@y.com"),
        )
    assert "502" in str(excinfo.value)


def test_crm_post_urlerror(monkeypatch):
    from smbagent.transports import (
        CrmContact,
        CrmTransportError,
        HubspotConfig,
        HubspotCrmTransport,
    )
    from smbagent.transports import crm as crm_mod

    def boom(request, timeout=None):  # noqa: ARG001
        raise urllib.error.URLError("DNS failure")

    monkeypatch.setattr(crm_mod.urllib.request, "urlopen", boom)
    with pytest.raises(CrmTransportError) as excinfo:
        HubspotCrmTransport(HubspotConfig(access_token="t")).create_contact(
            CrmContact(email="x@y.com"),
        )
    assert "unreachable" in str(excinfo.value).lower()


def test_crm_deal_contact_lookup_returns_empty_results(monkeypatch):
    """Lookup-by-email returns no results; deal still created without association."""
    from smbagent.transports import (
        CrmDeal,
        HubspotConfig,
        HubspotCrmTransport,
    )
    from smbagent.transports import crm as crm_mod

    scripted_responses = [
        # Lookup: no results
        json.dumps({"results": []}).encode("utf-8"),
        # Deal creation
        json.dumps({"id": "deal-456"}).encode("utf-8"),
    ]
    monkeypatch.setattr(
        crm_mod.urllib.request,
        "urlopen",
        _stub_urlopen(scripted_responses),
    )

    res = HubspotCrmTransport(HubspotConfig(access_token="t")).create_deal(
        CrmDeal(name="Pro plan", contact_email="ghost@example.com"),
    )
    assert res.deal_id == "deal-456"


def test_crm_deal_lookup_returns_result_with_empty_id(monkeypatch):
    """Edge case: lookup returns a result but its id is empty string."""
    from smbagent.transports import (
        CrmDeal,
        HubspotConfig,
        HubspotCrmTransport,
    )
    from smbagent.transports import crm as crm_mod

    scripted = [
        json.dumps({"results": [{"id": ""}]}).encode("utf-8"),
        json.dumps({"id": "deal-789"}).encode("utf-8"),
    ]
    monkeypatch.setattr(
        crm_mod.urllib.request,
        "urlopen",
        _stub_urlopen(scripted),
    )

    res = HubspotCrmTransport(HubspotConfig(access_token="t")).create_deal(
        CrmDeal(name="X", contact_email="z@y"),
    )
    assert res.deal_id == "deal-789"
