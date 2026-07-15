from __future__ import annotations

import subprocess
from pathlib import Path

from smbagent._subproc import filesystem_isolation_cmd
from smbagent.apple_container import (
    build_apple_container_run_spec,
    render_apple_container_command,
    subprocess_isolation_is_official_apple_container,
    subprocess_isolation_provider_label,
)
from smbagent.harness import run_smoke_harness


def test_subprocess_isolation_provider_helpers():
    assert subprocess_isolation_is_official_apple_container("apple-container") is True
    assert subprocess_isolation_provider_label("apple-container") == "Apple official container runtime"
    assert subprocess_isolation_provider_label("macos-sandbox") == "Legacy macOS sandbox-exec"


def test_build_apple_container_run_spec_defaults_to_read_only_no_dns():
    spec = build_apple_container_run_spec(
        customer_id="acme-co",
        stage="validation",
        image="ghcr.io/acme/smbagent-validation:latest",
        workspace_root=Path("/srv/acme-co"),
        command=["codex", "exec", "--json"],
        public_mount_targets=("plan.md", "tasks.json"),
        writable_mount_targets=("runs",),
    )
    cmd = render_apple_container_command(spec)
    assert cmd[:3] == ["container", "run", "--name"]
    assert "--read-only" in cmd
    assert "--init" in cmd
    assert "--workdir" in cmd
    assert "--mount" in cmd
    assert "ghcr.io/acme/smbagent-validation:latest" in cmd
    assert "codex" in cmd


def test_filesystem_isolation_cmd_builds_apple_container_command(config, workspace, monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    cfg = type(config)(
        **{
            **config.__dict__,
            "subprocess_isolation": "apple-container",
            "apple_container_coding_image": "example/claude:latest",
        }
    )
    cmd = filesystem_isolation_cmd(
        cfg,
        ["claude", "-p", "hello"],
        workspace_path=workspace.path,
        cwd=workspace.path,
        role="coding",
    )
    rendered = " ".join(cmd)
    assert cmd[0:2] == ["container", "run"]
    assert "--read-only" in cmd
    assert "--workdir" in cmd
    assert "--mount" in cmd
    assert "example/claude:latest" in cmd
    assert "--publish" not in cmd
    assert str(workspace.path) in rendered


def test_run_smoke_harness_wraps_cli_steps_for_apple_container(config, tmp_path, monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/fake")
    calls: list[list[str]] = []

    def _fake_run(cmd, **kwargs):  # noqa: ANN001
        calls.append(list(cmd))
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="ok", stderr="")

    cfg = type(config)(
        **{
            **config.__dict__,
            "subprocess_isolation": "apple-container",
            "apple_container_coding_image": "example/claude:latest",
            "apple_container_validation_image": "example/codex:latest",
        }
    )
    monkeypatch.setattr("subprocess.run", _fake_run)

    out = tmp_path / "smoke.json"
    result = run_smoke_harness(cfg, out_path=out, timeout_s=5)

    assert result["passed"] is True
    rendered = "\n".join(" ".join(cmd) for cmd in calls)
    assert "example/claude:latest" in rendered
    assert "example/codex:latest" in rendered
    assert "python -m smbagent.smoke anthropic" in rendered
    assert "python -m smbagent.smoke openai" in rendered
