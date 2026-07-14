"""Subprocess lifecycle helpers — track live PIDs and kill them on exit.

Shared by CodingAgent and ValidationAgent. The motivation: when the operator
hits Ctrl-C or the parent process crashes mid-pipeline, we want any in-flight
`claude` / `codex` invocations to die with us, not become orphans burning API
quota for hours.

POSIX behavior: a child process inherits the parent's process group; SIGINT
delivered to the foreground PG is broadcast. That handles Ctrl-C already. The
atexit hook is for the harder case — parent killed by SIGKILL / OOM / crash —
where the kernel doesn't propagate signals.
"""

from __future__ import annotations

import atexit
import os
import platform
import signal
import threading
from pathlib import Path

from .apple_container import (
    VALIDATION_ROLE_FAMILY,
    AppleContainerMount,
    AppleContainerRunSpec,
    apple_container_image_for_role,
    apple_container_role_family,
    render_apple_container_command,
)
from .config import Config

_LIVE_PIDS: set[int] = set()
_LOCK = threading.Lock()


def register_pid(pid: int) -> None:
    with _LOCK:
        _LIVE_PIDS.add(pid)


def unregister_pid(pid: int) -> None:
    with _LOCK:
        _LIVE_PIDS.discard(pid)


def _kill_all() -> None:
    """Best-effort: SIGTERM every tracked child. Called at interpreter shutdown."""
    with _LOCK:
        pids = list(_LIVE_PIDS)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, OSError):
            continue


atexit.register(_kill_all)


def filesystem_isolation_cmd(
    config: Config,
    cmd: list[str],
    *,
    workspace_path: Path,
    cwd: Path,
    role: str,
    extra_read_paths: list[Path] | None = None,
    extra_writable_paths: list[Path] | None = None,
) -> list[str]:
    """Wrap a subprocess command with the configured filesystem isolation.

    Supported modes:
      - none: return cmd unchanged.
      - apple-container: use Apple's official container runtime with same-path
        workspace mounts and no published ports.
      - macos-sandbox: use sandbox-exec with workspace-scoped writes.
      - linux-bwrap: use bubblewrap with workspace-scoped writes.

    The macOS profile intentionally keeps network access available because the
    vendor CLIs need to call model APIs. It narrows filesystem access: writes go
    to the customer workspace and temp dirs; reads include system paths, common
    CLI config dirs, the repo root, and operator-supplied read paths.
    """
    mode = config.subprocess_isolation.lower().strip()
    if mode in ("", "none", "off", "false"):
        return cmd
    if mode == "apple-container":
        if platform.system() != "Darwin":
            raise ValueError("apple-container isolation requires macOS")
        return _apple_container_cmd(
            config=config,
            cmd=cmd,
            workspace_path=workspace_path,
            cwd=cwd,
            role=role,
            extra_read_paths=extra_read_paths or [],
            extra_writable_paths=extra_writable_paths or [],
        )
    if mode in ("linux-bwrap", "bwrap"):
        if platform.system() != "Linux":
            raise ValueError("linux-bwrap isolation requires Linux bubblewrap")
        return _linux_bwrap_cmd(
            cmd=cmd,
            workspace_path=workspace_path,
            cwd=cwd,
            extra_writable_paths=extra_writable_paths or [],
        )
    if mode not in ("macos-sandbox", "sandbox-exec"):
        raise ValueError(
            f"unsupported SMBAGENT_SUBPROCESS_ISOLATION={config.subprocess_isolation!r}; "
            "expected none, apple-container, macos-sandbox, or linux-bwrap"
        )
    if platform.system() != "Darwin":
        raise ValueError("macos-sandbox isolation requires macOS sandbox-exec")

    profile = _macos_sandbox_profile(
        config=config,
        workspace_path=workspace_path,
        cwd=cwd,
        role=role,
        extra_read_paths=extra_read_paths or [],
        extra_writable_paths=extra_writable_paths or [],
    )
    return ["sandbox-exec", "-p", profile, *cmd]


def _apple_container_cmd(
    *,
    config: Config,
    cmd: list[str],
    workspace_path: Path,
    cwd: Path,
    role: str,
    extra_read_paths: list[Path],
    extra_writable_paths: list[Path],
) -> list[str]:
    role_family = apple_container_role_family(role)
    home = Path.home()
    base_read_paths = [
        cwd,
        config.root,
        Path("/etc/hosts"),
        Path("/etc/resolv.conf"),
    ]
    if config.apple_container_home_mounts:
        base_read_paths.extend(
            [
                home / ".claude",
                home / ".codex",
                home / ".config",
                home / ".cache",
                home / ".npm",
                home / ".local",
            ]
        )
    if role_family == VALIDATION_ROLE_FAMILY:
        read_paths = [*base_read_paths, cwd.parent, *extra_read_paths]
    else:
        read_paths = [*base_read_paths, workspace_path, *extra_read_paths]
    read_paths.extend(Path(p) for p in config.subprocess_read_paths)
    writable_paths = [
        workspace_path,
        *extra_writable_paths,
    ]

    mounts: list[AppleContainerMount] = []
    seen_targets: set[str] = set()
    for path in _existing_paths(read_paths):
        target = str(path)
        if target in seen_targets:
            continue
        seen_targets.add(target)
        mounts.append(AppleContainerMount(source=target, target=target, readonly=True))
    for path in _existing_paths(writable_paths):
        target = str(path)
        if target in seen_targets:
            mounts = [m for m in mounts if m.target != target]
        seen_targets.add(target)
        mounts.append(AppleContainerMount(source=target, target=target, readonly=False))

    image = apple_container_image_for_role(config, role)
    spec = AppleContainerRunSpec(
        container_name=f"smbagent-{role}",
        image=image,
        command=tuple(cmd),
        mounts=tuple(mounts),
        env_file=None,
        env_names=tuple(
            name
            for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "HOME", "USER", "TMPDIR")
            if os.environ.get(name)
        ),
        remove_on_exit=True,
        read_only_root=True,
        no_dns=False,
        rosetta=False,
        init=True,
        workdir=str(cwd.resolve()),
        tmpfs_targets=("/tmp", "/var/tmp"),
    )
    return render_apple_container_command(spec)


def _scheme_path(path: Path | str) -> str:
    return f"(subpath {_quote(str(Path(path).expanduser().resolve()))})"


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _macos_sandbox_profile(
    *,
    config: Config,
    workspace_path: Path,
    cwd: Path,
    role: str,
    extra_read_paths: list[Path],
    extra_writable_paths: list[Path],
) -> str:
    role_family = apple_container_role_family(role)
    home = Path.home()
    base_read_paths = [
        Path("/bin"),
        Path("/sbin"),
        Path("/usr"),
        Path("/System"),
        Path("/Library"),
        Path("/opt"),
        Path("/etc"),
        cwd,
        home / ".claude",
        home / ".codex",
        home / ".config",
        home / ".cache",
        home / ".npm",
        home / ".local",
    ]
    if role_family == VALIDATION_ROLE_FAMILY:
        # Validation must not read Claude logs, bridge files, prior verdicts, or
        # plan artifacts outside the sanitized snapshot. The cwd is
        # runs/round-N/validation_snapshot/code, so cwd.parent is the complete
        # public validation bundle.
        read_paths = [*base_read_paths, cwd.parent, *extra_read_paths]
    else:
        read_paths = [*base_read_paths, config.root, workspace_path, *extra_read_paths]
    read_paths.extend(Path(p) for p in config.subprocess_read_paths)
    writable_paths = [
        workspace_path,
        Path("/tmp"),
        Path("/private/tmp"),
        Path(os.environ.get("TMPDIR", "/tmp")),
        *extra_writable_paths,
    ]

    read_rules = "\n".join(_scheme_path(p) for p in _existing_paths(read_paths))
    write_rules = "\n".join(_scheme_path(p) for p in _existing_paths(writable_paths))
    literal_role = role.replace('"', "")
    return f"""
(version 1)
(deny default)
(allow process*)
(allow signal)
(allow sysctl-read)
(allow mach-lookup)
(allow network*)
(allow file-read-metadata)
(allow file-read* {read_rules})
(allow file-write* {write_rules})
; smbagent role: {literal_role}
""".strip()


def _existing_paths(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        try:
            resolved = path.expanduser().resolve()
        except OSError:
            continue
        if not resolved.exists():
            continue
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        out.append(resolved)
    return out


def _linux_bwrap_cmd(
    *,
    cmd: list[str],
    workspace_path: Path,
    cwd: Path,
    extra_writable_paths: list[Path],
) -> list[str]:
    writable_paths = _existing_paths(
        [
            workspace_path,
            Path("/tmp"),
            Path("/var/tmp"),
            Path(os.environ.get("TMPDIR", "/tmp")),
            *extra_writable_paths,
        ]
    )
    argv = [
        "bwrap",
        "--die-with-parent",
        "--unshare-all",
        "--share-net",
        "--ro-bind",
        "/",
        "/",
        "--dev-bind",
        "/dev",
        "/dev",
        "--proc",
        "/proc",
        "--chdir",
        str(cwd),
    ]
    for path in writable_paths:
        argv.extend(["--bind", str(path), str(path)])
    argv.extend(cmd)
    return argv
