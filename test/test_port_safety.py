from __future__ import annotations

import socket
import sys
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from smbagent.cli import app as cli_app
from smbagent.server import create_app


@pytest.fixture
def isolated_root(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "smbagent").mkdir()
    (tmp_path / "workspaces").mkdir()
    yield tmp_path


def test_create_app_and_testclient_do_not_bind_network_port(config, monkeypatch):
    """FastAPI app construction/tests must stay in-process and port-free."""
    binds: list[tuple] = []
    original_bind = socket.socket.bind

    def spy_bind(self, address):
        binds.append(address)
        return original_bind(self, address)

    monkeypatch.setattr(socket.socket, "bind", spy_bind)
    app = create_app(config)
    with TestClient(app) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    assert binds == []


def test_serve_http_default_is_localhost_and_uvicorn_is_only_called_when_command_runs(
    isolated_root,
    monkeypatch,
):
    calls: list[dict] = []
    fake_uvicorn = types.SimpleNamespace(
        run=lambda app, host, port: calls.append({"app": app, "host": host, "port": port})
    )
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)

    result = CliRunner().invoke(cli_app, ["serve-http"])

    assert result.exit_code == 0
    assert len(calls) == 1
    assert calls[0]["host"] == "127.0.0.1"
    assert calls[0]["port"] == 8000


def test_serve_http_uses_configured_host_and_port_when_overlay_vpn_posture_is_configured(
    isolated_root,
    monkeypatch,
):
    calls: list[dict] = []
    fake_uvicorn = types.SimpleNamespace(
        run=lambda app, host, port: calls.append({"app": app, "host": host, "port": port})
    )
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)
    monkeypatch.setenv("SMBAGENT_SERVE_HOST", "100.64.0.10")
    monkeypatch.setenv("SMBAGENT_SERVE_PORT", "8123")
    monkeypatch.setenv("SMBAGENT_MONITOR_EXPOSURE", "public-approved")
    monkeypatch.setenv("SMBAGENT_MONITOR_PUBLIC_BASE_URL", "https://100.64.0.10:8123")
    monkeypatch.setenv("SMBAGENT_REMOTE_ACCESS_CHANNEL", "tailscale")
    monkeypatch.setenv("SMBAGENT_MAINTENANCE_ACCESS_CHANNEL", "ssh-vpn")

    result = CliRunner().invoke(cli_app, ["serve-http"])

    assert result.exit_code == 0
    assert len(calls) == 1
    assert calls[0]["host"] == "100.64.0.10"
    assert calls[0]["port"] == 8123


def test_serve_http_refuses_non_local_bind_without_vpn_overlay(isolated_root, monkeypatch):
    calls: list[dict] = []
    fake_uvicorn = types.SimpleNamespace(
        run=lambda app, host, port: calls.append({"app": app, "host": host, "port": port})
    )
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)
    monkeypatch.setenv("SMBAGENT_SERVE_HOST", "0.0.0.0")
    monkeypatch.setenv("SMBAGENT_MONITOR_EXPOSURE", "lan-only")
    monkeypatch.setenv("SMBAGENT_ALLOW_LAN_MONITOR_FALLBACK", "false")

    result = CliRunner().invoke(cli_app, ["serve-http"])

    assert result.exit_code != 0
    assert calls == []
    assert "serve-http blocked" in result.stdout


def test_serve_http_allows_overlay_vpn_posture(isolated_root, monkeypatch):
    calls: list[dict] = []
    fake_uvicorn = types.SimpleNamespace(
        run=lambda app, host, port: calls.append({"app": app, "host": host, "port": port})
    )
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)
    monkeypatch.setenv("SMBAGENT_SERVE_HOST", "100.64.0.10")
    monkeypatch.setenv("SMBAGENT_MONITOR_EXPOSURE", "public-approved")
    monkeypatch.setenv("SMBAGENT_MONITOR_PUBLIC_BASE_URL", "https://100.64.0.10:8000")
    monkeypatch.setenv("SMBAGENT_REMOTE_ACCESS_CHANNEL", "tailscale")
    monkeypatch.setenv("SMBAGENT_MAINTENANCE_ACCESS_CHANNEL", "ssh-vpn")

    result = CliRunner().invoke(cli_app, ["serve-http"])

    assert result.exit_code == 0
    assert len(calls) == 1
    assert calls[0]["host"] == "100.64.0.10"


def test_non_server_cli_checks_do_not_call_uvicorn(isolated_root, monkeypatch):
    def fail_run(*args, **kwargs):
        raise AssertionError("uvicorn.run should not be called by non-server checks")

    monkeypatch.setitem(sys.modules, "uvicorn", types.SimpleNamespace(run=fail_run))
    runner = CliRunner()

    bench = runner.invoke(cli_app, ["coding-benchmarks"])
    ready = runner.invoke(cli_app, ["launch-readiness"])

    assert bench.exit_code == 0
    assert ready.exit_code in {0, 1}
    assert "uvicorn.run should not be called" not in ready.output
