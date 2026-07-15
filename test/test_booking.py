"""Tests for the booking integration runtime."""

from __future__ import annotations

import io
import json
import urllib.error
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from smbagent.config import Config
from smbagent.transports import (
    BookingForwarder,
    BookingRequest,
    BookingTransportError,
    GoogleCalendarConfig,
    GoogleCalendarTransport,
    MemoryBookingTransport,
)
from smbagent.transports import booking as booking_mod
from smbagent.workspace import Workspace


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC)


def _req(**kwargs) -> BookingRequest:
    """A valid BookingRequest with overridable fields."""
    defaults = {
        "summary": "Cleaning - Tanaka-san",
        "start": _utc(datetime(2026, 6, 1, 10, 0)),
        "end": _utc(datetime(2026, 6, 1, 11, 0)),
        "description": "Regular cleaning",
        "attendees": ["tanaka@example.com"],
        "location": "Tokyo clinic",
    }
    defaults.update(kwargs)
    return BookingRequest(**defaults)


# ---- BookingRequest validation ----


def test_booking_request_requires_tz_aware_start():
    with pytest.raises(BookingTransportError):
        BookingRequest(
            summary="x",
            start=datetime(2026, 6, 1, 10),  # naive
            end=_utc(datetime(2026, 6, 1, 11)),
        )


def test_booking_request_requires_tz_aware_end():
    with pytest.raises(BookingTransportError):
        BookingRequest(
            summary="x",
            start=_utc(datetime(2026, 6, 1, 10)),
            end=datetime(2026, 6, 1, 11),  # naive
        )


def test_booking_request_rejects_end_at_or_before_start():
    with pytest.raises(BookingTransportError):
        BookingRequest(
            summary="x",
            start=_utc(datetime(2026, 6, 1, 11)),
            end=_utc(datetime(2026, 6, 1, 10)),
        )


def test_booking_request_accepts_valid_input():
    req = _req()
    assert req.summary == "Cleaning - Tanaka-san"
    assert (req.end - req.start) == timedelta(hours=1)


# ---- MemoryBookingTransport ----


def test_memory_transport_records_call():
    t = MemoryBookingTransport()
    res = t.create_event(_req())
    assert res.event_id == "mem-evt-1"
    assert res.html_url is None
    assert len(t.events) == 1


def test_memory_transport_increments_ids():
    t = MemoryBookingTransport()
    r1 = t.create_event(_req())
    r2 = t.create_event(_req(summary="second"))
    assert (r1.event_id, r2.event_id) == ("mem-evt-1", "mem-evt-2")
    assert t.events[1].summary == "second"


# ---- GoogleCalendarTransport (mocked) ----


class _FakeHTTPResponse:
    """Stand-in for the context-manager returned by urlopen()."""

    def __init__(self, body: bytes):
        self._body = body
        self.read_called = False

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        self.read_called = True
        return self._body


def _stub_urlopen(scripted: list[bytes], captured: list[Any] | None = None):
    """Returns a function that takes (request, timeout=...) and returns
    the next scripted body. Records every Request object into `captured`."""

    captured = captured if captured is not None else []
    idx = {"n": 0}

    def fake(request, timeout=None):  # noqa: ARG001
        if idx["n"] >= len(scripted):
            raise AssertionError("urlopen called more than scripted")
        body = scripted[idx["n"]]
        captured.append(request)
        idx["n"] += 1
        return _FakeHTTPResponse(body)

    return fake, captured


def _gcal_cfg() -> GoogleCalendarConfig:
    return GoogleCalendarConfig(
        client_id="cid",
        client_secret="csecret",
        refresh_token="rtok",
        calendar_id="primary",
        timezone="Asia/Tokyo",
    )


def test_google_calendar_creates_event(monkeypatch):
    scripted = [
        json.dumps({"access_token": "abc123", "expires_in": 3600}).encode("utf-8"),
        json.dumps({"id": "evt-xyz", "htmlLink": "https://calendar.google.com/event?eid=evt-xyz"}).encode(
            "utf-8"
        ),
    ]
    fake, captured = _stub_urlopen(scripted)
    monkeypatch.setattr(booking_mod.urllib.request, "urlopen", fake)

    t = GoogleCalendarTransport(_gcal_cfg())
    res = t.create_event(_req())

    assert res.event_id == "evt-xyz"
    assert res.html_url and "calendar.google.com" in res.html_url
    assert len(captured) == 2

    # First request: OAuth token exchange
    token_req = captured[0]
    assert token_req.full_url == "https://oauth2.googleapis.com/token"
    assert b"grant_type=refresh_token" in token_req.data
    assert b"refresh_token=rtok" in token_req.data

    # Second request: event creation with Bearer
    event_req = captured[1]
    assert "/calendar/v3/calendars/primary/events" in event_req.full_url
    assert event_req.headers.get("Authorization") == "Bearer abc123"
    assert event_req.get_method() == "POST"
    payload = json.loads(event_req.data.decode("utf-8"))
    assert payload["summary"] == "Cleaning - Tanaka-san"
    assert payload["start"]["timeZone"] == "Asia/Tokyo"
    assert payload["attendees"] == [{"email": "tanaka@example.com"}]


def test_google_calendar_oauth_failure_raises(monkeypatch):
    def boom(request, timeout=None):  # noqa: ARG001
        raise urllib.error.HTTPError(
            request.full_url,
            400,
            "Bad Request",
            {},
            io.BytesIO(b'{"error":"invalid_grant"}'),
        )

    monkeypatch.setattr(booking_mod.urllib.request, "urlopen", boom)
    t = GoogleCalendarTransport(_gcal_cfg())
    with pytest.raises(BookingTransportError) as excinfo:
        t.create_event(_req())
    assert "OAuth" in str(excinfo.value)
    assert "invalid_grant" in str(excinfo.value)


def test_google_calendar_oauth_missing_access_token_raises(monkeypatch):
    fake, _ = _stub_urlopen([json.dumps({"expires_in": 3600}).encode("utf-8")])
    monkeypatch.setattr(booking_mod.urllib.request, "urlopen", fake)
    t = GoogleCalendarTransport(_gcal_cfg())
    with pytest.raises(BookingTransportError) as excinfo:
        t.create_event(_req())
    assert "access_token" in str(excinfo.value)


def test_google_calendar_event_creation_failure_raises(monkeypatch):
    scripted_first = json.dumps({"access_token": "abc", "expires_in": 3600}).encode("utf-8")
    calls = {"n": 0}

    def fake(request, timeout=None):  # noqa: ARG001
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeHTTPResponse(scripted_first)
        # Second call (event creation) blows up.
        raise urllib.error.HTTPError(
            request.full_url,
            403,
            "Forbidden",
            {},
            io.BytesIO(b'{"error":{"message":"insufficient scope"}}'),
        )

    monkeypatch.setattr(booking_mod.urllib.request, "urlopen", fake)
    t = GoogleCalendarTransport(_gcal_cfg())
    with pytest.raises(BookingTransportError) as excinfo:
        t.create_event(_req())
    assert "403" in str(excinfo.value)
    assert "insufficient scope" in str(excinfo.value)


def test_google_calendar_event_response_missing_id_raises(monkeypatch):
    scripted = [
        json.dumps({"access_token": "abc"}).encode("utf-8"),
        json.dumps({"summary": "ok"}).encode("utf-8"),  # no `id`
    ]
    fake, _ = _stub_urlopen(scripted)
    monkeypatch.setattr(booking_mod.urllib.request, "urlopen", fake)
    t = GoogleCalendarTransport(_gcal_cfg())
    with pytest.raises(BookingTransportError) as excinfo:
        t.create_event(_req())
    assert "event id" in str(excinfo.value)


def test_google_calendar_url_unreachable_raises(monkeypatch):
    def boom(request, timeout=None):  # noqa: ARG001
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(booking_mod.urllib.request, "urlopen", boom)
    t = GoogleCalendarTransport(_gcal_cfg())
    with pytest.raises(BookingTransportError) as excinfo:
        t.create_event(_req())
    assert "unreachable" in str(excinfo.value).lower()


def test_google_calendar_url_encodes_calendar_id(monkeypatch):
    """Calendar IDs can be email addresses (e.g. user@example.com) — must be URL-escaped."""
    scripted = [
        json.dumps({"access_token": "x"}).encode("utf-8"),
        json.dumps({"id": "evt1"}).encode("utf-8"),
    ]
    fake, captured = _stub_urlopen(scripted)
    monkeypatch.setattr(booking_mod.urllib.request, "urlopen", fake)

    cfg = _gcal_cfg()
    cfg.calendar_id = "team@example.com"
    GoogleCalendarTransport(cfg).create_event(_req())

    event_url = captured[1].full_url
    assert "team%40example.com" in event_url


# ---- BookingForwarder (config-driven) ----


def _write_config(workspace: Workspace, name: str, body: dict) -> None:
    d = workspace.code_dir / "integrations" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.json").write_text(json.dumps(body), encoding="utf-8")


def test_forwarder_explicit_transport_skips_config(config: Config, workspace: Workspace):
    transport = MemoryBookingTransport()
    f = BookingForwarder(workspace, "any-integration", transport=transport)
    res = f.book(_req())
    assert res.event_id.startswith("mem-evt-")
    assert len(transport.events) == 1


def test_forwarder_loads_memory_from_config(config: Config, workspace: Workspace):
    _write_config(workspace, "bookings", {"transport": "memory"})
    f = BookingForwarder(workspace, "bookings")
    assert isinstance(f.transport, MemoryBookingTransport)
    f.book(_req())
    assert len(f.transport.events) == 1


def test_forwarder_loads_google_calendar_from_config(config: Config, workspace: Workspace):
    _write_config(
        workspace,
        "gcal",
        {
            "transport": "google-calendar",
            "client_id": "cid",
            "client_secret": "csec",
            "refresh_token": "rt",
        },
    )
    f = BookingForwarder(workspace, "gcal")
    assert isinstance(f.transport, GoogleCalendarTransport)
    assert f.transport.config.calendar_id == "primary"  # default


def test_forwarder_google_calendar_missing_required_key_raises(config: Config, workspace: Workspace):
    _write_config(
        workspace,
        "gcal-broken",
        {
            "transport": "google-calendar",
            "client_id": "cid",  # missing client_secret + refresh_token
        },
    )
    with pytest.raises(BookingTransportError) as excinfo:
        BookingForwarder(workspace, "gcal-broken")
    assert "client_secret" in str(excinfo.value) or "refresh_token" in str(excinfo.value)


def test_forwarder_unknown_transport_raises(config: Config, workspace: Workspace):
    _write_config(workspace, "weird", {"transport": "calendly"})
    with pytest.raises(BookingTransportError) as excinfo:
        BookingForwarder(workspace, "weird")
    assert "calendly" in str(excinfo.value)


def test_forwarder_missing_config_raises(config: Config, workspace: Workspace):
    (workspace.code_dir / "integrations").mkdir(parents=True, exist_ok=True)
    with pytest.raises(BookingTransportError) as excinfo:
        BookingForwarder(workspace, "ghost")
    assert "config missing" in str(excinfo.value)


def test_forwarder_malformed_config_raises(config: Config, workspace: Workspace):
    d = workspace.code_dir / "integrations" / "broken"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.json").write_text("not json {{", encoding="utf-8")
    with pytest.raises(BookingTransportError) as excinfo:
        BookingForwarder(workspace, "broken")
    assert "invalid JSON" in str(excinfo.value)
