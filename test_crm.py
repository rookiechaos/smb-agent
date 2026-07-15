"""Tests for the CRM integration runtime."""

from __future__ import annotations

import io
import json
import urllib.error
from typing import Any

import pytest

from smbagent.config import Config
from smbagent.transports import (
    CrmContact,
    CrmDeal,
    CrmForwarder,
    CrmTransportError,
    HubspotConfig,
    HubspotCrmTransport,
    MemoryCrmTransport,
)
from smbagent.transports import crm as crm_mod
from smbagent.workspace import Workspace

# ---- MemoryCrmTransport ----


def test_memory_create_contact_records_and_returns_id():
    t = MemoryCrmTransport()
    res = t.create_contact(CrmContact(email="x@example.com", first_name="X"))
    assert res.contact_id == "mem-c-1"
    assert res.provider == "memory"
    assert len(t.contacts) == 1


def test_memory_create_contact_requires_email():
    t = MemoryCrmTransport()
    with pytest.raises(CrmTransportError):
        t.create_contact(CrmContact(email=""))


def test_memory_create_deal_records_and_returns_id():
    t = MemoryCrmTransport()
    res = t.create_deal(CrmDeal(name="Sample deal", amount=10000.0, stage="proposal"))
    assert res.deal_id == "mem-d-1"
    assert res.provider == "memory"
    assert len(t.deals) == 1


def test_memory_create_deal_requires_name():
    t = MemoryCrmTransport()
    with pytest.raises(CrmTransportError):
        t.create_deal(CrmDeal(name=""))


def test_memory_increments_ids():
    t = MemoryCrmTransport()
    r1 = t.create_contact(CrmContact(email="a@x"))
    r2 = t.create_contact(CrmContact(email="b@x"))
    assert (r1.contact_id, r2.contact_id) == ("mem-c-1", "mem-c-2")


# ---- HubspotCrmTransport (mocked) ----


class _FakeResp:
    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._body


def _stub_urlopen(scripted: list[bytes], captured: list[Any] | None = None):
    captured = captured if captured is not None else []
    idx = {"n": 0}

    def fake(request, timeout=None):  # noqa: ARG001
        if idx["n"] >= len(scripted):
            raise AssertionError("urlopen called more than scripted")
        body = scripted[idx["n"]]
        captured.append(request)
        idx["n"] += 1
        return _FakeResp(body)

    return fake, captured


def _hub_cfg() -> HubspotConfig:
    return HubspotConfig(access_token="pat-na1-fake-token", timeout_s=10)


def test_hubspot_create_contact_posts_correct_payload(monkeypatch):
    scripted = [json.dumps({"id": "12345", "properties": {"email": "x@example.com"}}).encode("utf-8")]
    fake, captured = _stub_urlopen(scripted)
    monkeypatch.setattr(crm_mod.urllib.request, "urlopen", fake)

    res = HubspotCrmTransport(_hub_cfg()).create_contact(
        CrmContact(email="x@example.com", first_name="X", last_name="Y", phone="03-0000-0000"),
    )

    assert res.contact_id == "12345"
    assert res.provider == "hubspot"
    assert len(captured) == 1
    req = captured[0]
    assert "/crm/v3/objects/contacts" in req.full_url
    assert req.headers["Authorization"] == "Bearer pat-na1-fake-token"
    assert req.headers["Content-type"] == "application/json"
    body = json.loads(req.data.decode("utf-8"))
    assert body["properties"]["email"] == "x@example.com"
    assert body["properties"]["firstname"] == "X"
    assert body["properties"]["lastname"] == "Y"
    assert body["properties"]["phone"] == "03-0000-0000"


def test_hubspot_create_contact_merges_custom_properties(monkeypatch):
    scripted = [json.dumps({"id": "ok"}).encode("utf-8")]
    fake, captured = _stub_urlopen(scripted)
    monkeypatch.setattr(crm_mod.urllib.request, "urlopen", fake)

    HubspotCrmTransport(_hub_cfg()).create_contact(
        CrmContact(email="a@x", properties={"lifecyclestage": "lead", "source_system": "smbagent"}),
    )
    body = json.loads(captured[0].data.decode("utf-8"))
    assert body["properties"]["lifecyclestage"] == "lead"
    assert body["properties"]["source_system"] == "smbagent"
    assert body["properties"]["email"] == "a@x"


def test_hubspot_create_contact_requires_email():
    with pytest.raises(CrmTransportError):
        HubspotCrmTransport(_hub_cfg()).create_contact(CrmContact(email=""))


def test_hubspot_create_contact_no_id_in_response_raises(monkeypatch):
    fake, _ = _stub_urlopen([json.dumps({"properties": {}}).encode("utf-8")])
    monkeypatch.setattr(crm_mod.urllib.request, "urlopen", fake)
    with pytest.raises(CrmTransportError) as excinfo:
        HubspotCrmTransport(_hub_cfg()).create_contact(CrmContact(email="a@x"))
    assert "contact id" in str(excinfo.value)


def test_hubspot_create_deal_basic(monkeypatch):
    scripted = [json.dumps({"id": "deal-77"}).encode("utf-8")]
    fake, captured = _stub_urlopen(scripted)
    monkeypatch.setattr(crm_mod.urllib.request, "urlopen", fake)

    res = HubspotCrmTransport(_hub_cfg()).create_deal(
        CrmDeal(name="Pro plan signup", amount=999.0, stage="proposal_sent"),
    )
    assert res.deal_id == "deal-77"
    body = json.loads(captured[0].data.decode("utf-8"))
    assert body["properties"]["dealname"] == "Pro plan signup"
    assert body["properties"]["amount"] == "999.0"
    assert body["properties"]["dealstage"] == "proposal_sent"
    assert "associations" not in body  # no contact_email → no association


def test_hubspot_create_deal_associates_to_contact_by_email(monkeypatch):
    """First call: contact lookup-by-email. Second: deal creation with association."""
    scripted = [
        # lookup response
        json.dumps({"results": [{"id": "5678", "properties": {"email": "buyer@x"}}]}).encode("utf-8"),
        # deal creation
        json.dumps({"id": "deal-99"}).encode("utf-8"),
    ]
    fake, captured = _stub_urlopen(scripted)
    monkeypatch.setattr(crm_mod.urllib.request, "urlopen", fake)

    res = HubspotCrmTransport(_hub_cfg()).create_deal(
        CrmDeal(name="X", contact_email="buyer@x"),
    )
    assert res.deal_id == "deal-99"
    assert "/objects/contacts/search" in captured[0].full_url
    assert "/objects/deals" in captured[1].full_url
    body = json.loads(captured[1].data.decode("utf-8"))
    assert "associations" in body
    assoc = body["associations"][0]
    assert assoc["to"]["id"] == "5678"


def test_hubspot_deal_lookup_failure_is_tolerated(monkeypatch):
    """If contact lookup fails (404 / network), deal creation still proceeds without association."""
    calls = {"n": 0}

    def fake(request, timeout=None):  # noqa: ARG001
        calls["n"] += 1
        if calls["n"] == 1:
            # Lookup fails
            raise urllib.error.HTTPError(
                request.full_url,
                500,
                "boom",
                {},
                io.BytesIO(b'{"error":"x"}'),
            )
        # Deal creation succeeds
        return _FakeResp(json.dumps({"id": "deal-no-assoc"}).encode("utf-8"))

    monkeypatch.setattr(crm_mod.urllib.request, "urlopen", fake)
    res = HubspotCrmTransport(_hub_cfg()).create_deal(
        CrmDeal(name="Y", contact_email="who@example.com"),
    )
    assert res.deal_id == "deal-no-assoc"


def test_hubspot_http_error_raises_with_body(monkeypatch):
    def boom(request, timeout=None):  # noqa: ARG001
        raise urllib.error.HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            {},
            io.BytesIO(b'{"category":"INVALID_AUTH"}'),
        )

    monkeypatch.setattr(crm_mod.urllib.request, "urlopen", boom)
    with pytest.raises(CrmTransportError) as excinfo:
        HubspotCrmTransport(_hub_cfg()).create_contact(CrmContact(email="x@y"))
    assert "401" in str(excinfo.value)
    assert "INVALID_AUTH" in str(excinfo.value)


def test_hubspot_url_unreachable_raises(monkeypatch):
    def boom(request, timeout=None):  # noqa: ARG001
        raise urllib.error.URLError("dns failure")

    monkeypatch.setattr(crm_mod.urllib.request, "urlopen", boom)
    with pytest.raises(CrmTransportError) as excinfo:
        HubspotCrmTransport(_hub_cfg()).create_contact(CrmContact(email="x@y"))
    assert "unreachable" in str(excinfo.value).lower()


# ---- CrmForwarder ----


def _write_config(workspace: Workspace, name: str, body: dict) -> None:
    d = workspace.code_dir / "integrations" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.json").write_text(json.dumps(body), encoding="utf-8")


def test_forwarder_explicit_transport_skips_config(config: Config, workspace: Workspace):
    transport = MemoryCrmTransport()
    f = CrmForwarder(workspace, "any", transport=transport)
    res = f.create_contact(CrmContact(email="x@y"))
    assert res.contact_id == "mem-c-1"


def test_forwarder_loads_memory_from_config(config: Config, workspace: Workspace):
    _write_config(workspace, "crm", {"transport": "memory"})
    f = CrmForwarder(workspace, "crm")
    assert isinstance(f.transport, MemoryCrmTransport)


def test_forwarder_loads_hubspot_from_config(config: Config, workspace: Workspace):
    _write_config(workspace, "hub", {"transport": "hubspot", "access_token": "pat-xxx"})
    f = CrmForwarder(workspace, "hub")
    assert isinstance(f.transport, HubspotCrmTransport)
    assert f.transport.config.access_token == "pat-xxx"


def test_forwarder_hubspot_missing_token_raises(config: Config, workspace: Workspace):
    _write_config(workspace, "hub", {"transport": "hubspot"})
    with pytest.raises(CrmTransportError) as excinfo:
        CrmForwarder(workspace, "hub")
    assert "access_token" in str(excinfo.value)


def test_forwarder_missing_config_raises(config: Config, workspace: Workspace):
    (workspace.code_dir / "integrations").mkdir(parents=True, exist_ok=True)
    with pytest.raises(CrmTransportError) as excinfo:
        CrmForwarder(workspace, "ghost")
    assert "config missing" in str(excinfo.value)


def test_forwarder_unknown_transport_raises(config: Config, workspace: Workspace):
    _write_config(workspace, "weird", {"transport": "salesforce"})
    with pytest.raises(CrmTransportError) as excinfo:
        CrmForwarder(workspace, "weird")
    assert "salesforce" in str(excinfo.value)
