"""Unit tests for the deploy backends."""

from __future__ import annotations

import subprocess
import tarfile
from pathlib import Path
from typing import Any

import pytest

from smbagent.config import Config
from smbagent.deploy import (
    DeployTargetError,
    NetlifyTarget,
    TarballTarget,
    VercelTarget,
    resolve_target,
)
from smbagent.deploy import netlify as netlify_mod
from smbagent.deploy import vercel as vercel_mod
from smbagent.workspace import Workspace

# ---- resolve_target ----


def test_resolve_target_known_names():
    assert isinstance(resolve_target("tarball"), TarballTarget)
    assert isinstance(resolve_target("vercel"), VercelTarget)
    assert isinstance(resolve_target("netlify"), NetlifyTarget)
    assert isinstance(resolve_target("TARBALL"), TarballTarget)  # case-insensitive


def test_resolve_target_unknown_name_raises():
    with pytest.raises(DeployTargetError):
        resolve_target("github-pages")


# ---- TarballTarget ----


def _populate_landing_page(workspace: Workspace) -> None:
    lp = workspace.code_dir / "landing-page"
    lp.mkdir(exist_ok=True)
    (lp / "index.html").write_text("<html><body>hi</body></html>", encoding="utf-8")
    (lp / "about.html").write_text("<html><body>about</body></html>", encoding="utf-8")
    (lp / "assets").mkdir()
    (lp / "assets" / "logo.svg").write_text("<svg/>", encoding="utf-8")


def test_tarball_target_produces_archive(config: Config, workspace: Workspace):
    _populate_landing_page(workspace)
    result = TarballTarget().deploy(workspace)

    assert result.target == "tarball"
    assert result.url is None
    assert result.artifact_path is not None
    archive = Path(result.artifact_path)
    assert archive.exists()
    assert archive.suffix == ".gz"
    assert archive.parent == workspace.path / "deploy"


def test_tarball_target_archive_contents(config: Config, workspace: Workspace):
    _populate_landing_page(workspace)
    result = TarballTarget().deploy(workspace)
    archive = Path(result.artifact_path)

    with tarfile.open(archive, "r:gz") as tf:
        names = sorted(tf.getnames())

    assert "index.html" in names
    assert "about.html" in names
    assert "assets/logo.svg" in names
    # No absolute paths leaked
    for n in names:
        assert not n.startswith("/")
        assert not n.startswith(".."), f"path traversal in tar: {n}"


def test_tarball_target_raises_when_landing_page_missing(config: Config, workspace: Workspace):
    # Workspace exists but no code/landing-page/
    with pytest.raises(DeployTargetError) as excinfo:
        TarballTarget().deploy(workspace)
    assert "landing-page" in str(excinfo.value)


def test_tarball_target_multiple_runs_dont_overwrite(config: Config, workspace: Workspace):
    """Each run produces a uniquely-timestamped archive."""
    _populate_landing_page(workspace)
    r1 = TarballTarget().deploy(workspace)
    # Force a timestamp difference (the timestamp resolution is seconds).
    import time

    time.sleep(1.01)
    r2 = TarballTarget().deploy(workspace)
    assert r1.artifact_path != r2.artifact_path


# ---- VercelTarget ----


def _spy_subprocess(captured: dict, *, stdout: str = "", returncode: int = 0):
    def fake_run(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["timeout"] = timeout
        return subprocess.CompletedProcess(args=cmd, returncode=returncode, stdout=stdout, stderr="")

    return fake_run


def test_vercel_target_invokes_correct_command(monkeypatch, config: Config, workspace: Workspace):
    _populate_landing_page(workspace)
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        vercel_mod.subprocess,
        "run",
        _spy_subprocess(captured, stdout="Deployed to https://demo.vercel.app", returncode=0),
    )

    result = VercelTarget().deploy(workspace)

    assert captured["cmd"][0] == "vercel"
    assert "deploy" in captured["cmd"]
    assert "--prod" in captured["cmd"]
    assert captured["cwd"] == str(workspace.code_dir / "landing-page")
    assert result.target == "vercel"
    assert result.url == "https://demo.vercel.app"


def test_vercel_target_extracts_url_from_stdout(monkeypatch, config: Config, workspace: Workspace):
    _populate_landing_page(workspace)
    monkeypatch.setattr(
        vercel_mod.subprocess,
        "run",
        _spy_subprocess({}, stdout="something\nhttps://customer-acme.vercel.app/\nother stuff"),
    )
    result = VercelTarget().deploy(workspace)
    assert result.url == "https://customer-acme.vercel.app/"


def test_vercel_target_no_url_in_output_returns_none(monkeypatch, config: Config, workspace: Workspace):
    _populate_landing_page(workspace)
    monkeypatch.setattr(
        vercel_mod.subprocess,
        "run",
        _spy_subprocess({}, stdout="bizarrely silent output"),
    )
    result = VercelTarget().deploy(workspace)
    assert result.url is None


def test_vercel_target_nonzero_returncode_raises(monkeypatch, config: Config, workspace: Workspace):
    _populate_landing_page(workspace)
    monkeypatch.setattr(
        vercel_mod.subprocess,
        "run",
        _spy_subprocess({}, stdout="oops", returncode=1),
    )
    with pytest.raises(DeployTargetError) as excinfo:
        VercelTarget().deploy(workspace)
    assert "returncode" in str(excinfo.value).lower() or "exited" in str(excinfo.value).lower()


def test_vercel_target_missing_cli_raises_with_hint(monkeypatch, config: Config, workspace: Workspace):
    _populate_landing_page(workspace)

    def boom(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
        raise FileNotFoundError("vercel")

    monkeypatch.setattr(vercel_mod.subprocess, "run", boom)
    with pytest.raises(DeployTargetError) as excinfo:
        VercelTarget().deploy(workspace)
    assert "vercel" in str(excinfo.value)
    assert "npm i -g" in str(excinfo.value)


def test_vercel_target_logs_are_secret_redacted(monkeypatch, config: Config, workspace: Workspace):
    """If the CLI ever echoes a secret in stdout, it must not survive into result.log."""
    _populate_landing_page(workspace)
    fake_key = "sk-ant-api03-" + "a" * 40
    monkeypatch.setattr(
        vercel_mod.subprocess,
        "run",
        _spy_subprocess({}, stdout=f"oops your key {fake_key} leaked", returncode=0),
    )
    result = VercelTarget().deploy(workspace)
    assert fake_key not in result.log
    assert "[REDACTED:Anthropic API key]" in result.log


def test_vercel_target_raises_when_landing_page_missing(monkeypatch, config: Config, workspace: Workspace):
    def never(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
        raise AssertionError("subprocess should not be invoked without landing-page/")

    monkeypatch.setattr(vercel_mod.subprocess, "run", never)

    with pytest.raises(DeployTargetError):
        VercelTarget().deploy(workspace)


# ---- NetlifyTarget ----


def test_netlify_target_invokes_correct_command(monkeypatch, config: Config, workspace: Workspace):
    _populate_landing_page(workspace)
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        netlify_mod.subprocess,
        "run",
        _spy_subprocess(captured, stdout="https://demo.netlify.app", returncode=0),
    )
    result = NetlifyTarget().deploy(workspace)

    assert captured["cmd"][0] == "netlify"
    assert "deploy" in captured["cmd"]
    assert "--prod" in captured["cmd"]
    assert result.url == "https://demo.netlify.app"


def test_netlify_target_missing_cli_raises_with_hint(monkeypatch, config: Config, workspace: Workspace):
    _populate_landing_page(workspace)

    def boom(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
        raise FileNotFoundError("netlify")

    monkeypatch.setattr(netlify_mod.subprocess, "run", boom)
    with pytest.raises(DeployTargetError) as excinfo:
        NetlifyTarget().deploy(workspace)
    assert "netlify" in str(excinfo.value)
    assert "npm i -g" in str(excinfo.value)
