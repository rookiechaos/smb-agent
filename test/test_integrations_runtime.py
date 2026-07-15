"""Unit tests for the integration runtime (mail forwarder + transports)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from smbagent.config import Config
from smbagent.transports import (
    MailForwarder,
    MailTransportError,
    MemoryMailTransport,
    OutgoingMessage,
    SmtpMailTransport,
)
from smbagent.transports import smtp as smtp_mod
from smbagent.transports.smtp import SmtpConfig
from smbagent.workspace import Workspace

# ---- Helpers ----


def _write_integration_config(workspace: Workspace, name: str, config: dict) -> None:
    d = workspace.code_dir / "integrations" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.json").write_text(json.dumps(config), encoding="utf-8")


# ---- MemoryMailTransport ----


def test_memory_transport_records_messages():
    t = MemoryMailTransport()
    msg = OutgoingMessage(sender="a@x", to=["b@x"], subject="hi", body="body")
    t.send(msg)
    assert t.sent == [msg]


def test_memory_transport_appends_multiple():
    t = MemoryMailTransport()
    t.send(OutgoingMessage(sender="a", to=["b"], subject="one", body="1"))
    t.send(OutgoingMessage(sender="a", to=["c"], subject="two", body="2"))
    assert len(t.sent) == 2
    assert t.sent[1].subject == "two"


# ---- SmtpMailTransport (mocked) ----


class _FakeSmtpClient:
    """Stand-in for smtplib.SMTP / SMTP_SSL. Records every method call."""

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.logged_in = None  # (user, pass) once login() is called
        self.sent: list[Any] = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.closed = True
        return False

    def login(self, user, password):
        self.logged_in = (user, password)

    def send_message(self, message):
        self.sent.append(message)


def test_smtp_transport_uses_ssl_by_default(monkeypatch):
    captured: dict[str, _FakeSmtpClient] = {}

    def fake_ssl(host, port):
        client = _FakeSmtpClient(host, port)
        captured["client"] = client
        return client

    monkeypatch.setattr(smtp_mod.smtplib, "SMTP_SSL", fake_ssl)

    t = SmtpMailTransport(SmtpConfig(host="mail.example.com", port=465, username="u", password="p"))
    t.send(OutgoingMessage(sender="from@x", to=["to@x"], subject="hi", body="hello"))

    client = captured["client"]
    assert client.host == "mail.example.com"
    assert client.port == 465
    assert client.logged_in == ("u", "p")
    assert len(client.sent) == 1
    email = client.sent[0]
    assert email["Subject"] == "hi"
    assert email["From"] == "from@x"
    assert email["To"] == "to@x"
    assert client.closed


def test_smtp_transport_plain_when_use_ssl_false(monkeypatch):
    captured: dict[str, _FakeSmtpClient] = {}

    def fake_plain(host, port):
        client = _FakeSmtpClient(host, port)
        captured["client"] = client
        return client

    monkeypatch.setattr(smtp_mod.smtplib, "SMTP", fake_plain)

    t = SmtpMailTransport(SmtpConfig(host="x", port=25, username="", password="", use_ssl=False))
    t.send(OutgoingMessage(sender="a@x", to=["b@x"], subject="x", body="y"))

    assert captured["client"].host == "x"
    assert captured["client"].logged_in is None  # no login when no username


def test_smtp_transport_wraps_errors_in_mailTransportError(monkeypatch):
    import smtplib

    def boom(host, port):
        raise smtplib.SMTPException("server down")

    monkeypatch.setattr(smtp_mod.smtplib, "SMTP_SSL", boom)

    t = SmtpMailTransport(SmtpConfig(host="x", port=465, username="u", password="p"))
    with pytest.raises(MailTransportError) as excinfo:
        t.send(OutgoingMessage(sender="a", to=["b"], subject="s", body="b"))
    assert "server down" in str(excinfo.value)


def test_smtp_transport_attaches_reply_to(monkeypatch):
    captured: dict[str, _FakeSmtpClient] = {}

    def fake_ssl(host, port):
        client = _FakeSmtpClient(host, port)
        captured["client"] = client
        return client

    monkeypatch.setattr(smtp_mod.smtplib, "SMTP_SSL", fake_ssl)

    t = SmtpMailTransport(SmtpConfig(host="x", port=465, username="u", password="p"))
    t.send(OutgoingMessage(sender="a", to=["b"], subject="s", body="b", reply_to="r@x"))

    email = captured["client"].sent[0]
    assert email["Reply-To"] == "r@x"


# ---- MailForwarder ----


def test_forwarder_with_explicit_transport_skips_config(config: Config, workspace: Workspace):
    """Passing transport= directly means we don't need config.json on disk."""
    transport = MemoryMailTransport()
    forwarder = MailForwarder(workspace, "gmail", transport=transport)

    forwarder.forward(to=["operator@x"], subject="lead", body="form data", sender="forms@business.com")

    assert len(transport.sent) == 1
    assert transport.sent[0].subject == "lead"
    assert transport.sent[0].to == ["operator@x"]


def test_forwarder_loads_memory_transport_from_config(config: Config, workspace: Workspace):
    _write_integration_config(
        workspace,
        "gmail",
        {"transport": "memory", "default_sender": "forms@biz.com"},
    )
    forwarder = MailForwarder(workspace, "gmail")
    assert isinstance(forwarder.transport, MemoryMailTransport)

    forwarder.forward(to=["operator@x"], subject="s", body="b")
    assert forwarder.transport.sent[0].sender == "forms@biz.com"


def test_forwarder_loads_smtp_transport_from_config(monkeypatch, config: Config, workspace: Workspace):
    _write_integration_config(
        workspace,
        "smtp-relay",
        {
            "transport": "smtp",
            "smtp_host": "mail.example.com",
            "smtp_port": 587,
            "smtp_username": "u",
            "smtp_password": "p",
            "smtp_use_ssl": False,
            "default_sender": "forms@biz.com",
        },
    )

    captured: dict[str, _FakeSmtpClient] = {}

    def fake_plain(host, port):
        client = _FakeSmtpClient(host, port)
        captured["client"] = client
        return client

    monkeypatch.setattr(smtp_mod.smtplib, "SMTP", fake_plain)

    forwarder = MailForwarder(workspace, "smtp-relay")
    assert isinstance(forwarder.transport, SmtpMailTransport)
    forwarder.forward(to=["a@x"], subject="hi", body="hello")
    assert captured["client"].host == "mail.example.com"
    assert captured["client"].port == 587


def test_forwarder_missing_config_raises(config: Config, workspace: Workspace):
    (workspace.code_dir / "integrations").mkdir(parents=True, exist_ok=True)
    with pytest.raises(MailTransportError) as excinfo:
        MailForwarder(workspace, "ghost-integration")
    assert "config missing" in str(excinfo.value)


def test_forwarder_malformed_config_raises(config: Config, workspace: Workspace):
    d = workspace.code_dir / "integrations" / "broken"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.json").write_text("not json {{", encoding="utf-8")

    with pytest.raises(MailTransportError) as excinfo:
        MailForwarder(workspace, "broken")
    assert "invalid JSON" in str(excinfo.value)


def test_forwarder_unknown_transport_kind_raises(config: Config, workspace: Workspace):
    _write_integration_config(workspace, "weird", {"transport": "carrier-pigeon"})
    with pytest.raises(MailTransportError) as excinfo:
        MailForwarder(workspace, "weird")
    assert "carrier-pigeon" in str(excinfo.value)


def test_forwarder_smtp_missing_required_key_raises(config: Config, workspace: Workspace):
    _write_integration_config(
        workspace,
        "incomplete-smtp",
        {"transport": "smtp", "smtp_port": 465},  # missing smtp_host
    )
    with pytest.raises(MailTransportError) as excinfo:
        MailForwarder(workspace, "incomplete-smtp")
    assert "smtp_host" in str(excinfo.value)


def test_forwarder_no_sender_no_default_raises(config: Config, workspace: Workspace):
    """If neither call site nor config provides a sender, we refuse to send."""
    _write_integration_config(workspace, "g", {"transport": "memory"})  # no default_sender
    forwarder = MailForwarder(workspace, "g")
    with pytest.raises(MailTransportError) as excinfo:
        forwarder.forward(to=["x"], subject="s", body="b")
    assert "sender" in str(excinfo.value)


def test_forwarder_uses_explicit_sender_over_default(config: Config, workspace: Workspace):
    _write_integration_config(
        workspace,
        "g",
        {"transport": "memory", "default_sender": "default@x"},
    )
    forwarder = MailForwarder(workspace, "g")
    forwarder.forward(to=["a@x"], subject="s", body="b", sender="explicit@x")
    assert forwarder.transport.sent[0].sender == "explicit@x"
