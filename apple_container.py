from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

OFF_VALUES = {"", "none", "off", "false"}
APPLE_CONTAINER_PROVIDER = "apple-container"
LEGACY_MACOS_SANDBOX_PROVIDER = "macos-sandbox"
LINUX_BWRAP_PROVIDER = "linux-bwrap"
CODING_ROLE_FAMILY = "coding"
VALIDATION_ROLE_FAMILY = "validation"


@dataclass(frozen=True)
class AppleContainerMount:
    source: str
    target: str
    readonly: bool = True

    def as_flag(self) -> str:
        suffix = ",readonly" if self.readonly else ""
        return f"type=bind,source={self.source},target={self.target}{suffix}"


@dataclass(frozen=True)
class AppleContainerRunSpec:
    container_name: str
    image: str
    command: tuple[str, ...]
    mounts: tuple[AppleContainerMount, ...]
    env_file: str | None
    env_names: tuple[str, ...]
    remove_on_exit: bool
    read_only_root: bool
    no_dns: bool
    rosetta: bool
    init: bool
    workdir: str | None
    tmpfs_targets: tuple[str, ...]


@dataclass(frozen=True)
class AppleContainerImageContract:
    role: str
    image: str
    cli_binary: str
    required_env: tuple[str, ...]
    install_contract: str
    expected_command: tuple[str, ...]


@dataclass(frozen=True)
class AppleContainerPlan:
    provider: str
    no_published_ports: bool
    shared_runtime_guarantees: tuple[str, ...]
    images: tuple[AppleContainerImageContract, ...]
    missing_env: tuple[str, ...]


def apple_container_role_family(role: str) -> str:
    normalized = (role or "").strip().lower().replace("_", "-")
    if normalized in {
        "validation",
        "smoke-validation",
        "benchmark-validation",
        "openai-sdk",
        "codex-cli",
    }:
        return VALIDATION_ROLE_FAMILY
    return CODING_ROLE_FAMILY


def apple_container_image_for_role(config, role: str) -> str:
    family = apple_container_role_family(role)
    if family == VALIDATION_ROLE_FAMILY:
        return config.apple_container_validation_image
    return config.apple_container_coding_image


def apple_container_required_env_for_role(role: str) -> tuple[str, ...]:
    family = apple_container_role_family(role)
    if family == VALIDATION_ROLE_FAMILY:
        return ("OPENAI_API_KEY",)
    return ("ANTHROPIC_API_KEY",)


def normalize_subprocess_isolation(value: str | None) -> str:
    return (value or "").strip().lower()


def subprocess_isolation_enabled(value: str | None) -> bool:
    return normalize_subprocess_isolation(value) not in OFF_VALUES


def subprocess_isolation_provider_label(value: str | None) -> str:
    normalized = normalize_subprocess_isolation(value)
    if normalized == APPLE_CONTAINER_PROVIDER:
        return "Apple official container runtime"
    if normalized == LEGACY_MACOS_SANDBOX_PROVIDER:
        return "Legacy macOS sandbox-exec"
    if normalized == LINUX_BWRAP_PROVIDER:
        return "Linux bubblewrap"
    if normalized in OFF_VALUES:
        return "disabled"
    return normalized or "disabled"


def subprocess_isolation_is_official_apple_container(value: str | None) -> bool:
    return normalize_subprocess_isolation(value) == APPLE_CONTAINER_PROVIDER


def subprocess_isolation_is_legacy_macos_sandbox(value: str | None) -> bool:
    return normalize_subprocess_isolation(value) == LEGACY_MACOS_SANDBOX_PROVIDER


def build_apple_container_run_spec(
    *,
    customer_id: str,
    stage: str,
    image: str,
    workspace_root: Path,
    command: list[str] | tuple[str, ...],
    public_mount_targets: tuple[str, ...] = (),
    writable_mount_targets: tuple[str, ...] = (),
    env_file: Path | None = None,
    env_names: tuple[str, ...] = (),
    rosetta: bool = False,
) -> AppleContainerRunSpec:
    mounts: list[AppleContainerMount] = [
        AppleContainerMount(source=str(workspace_root), target="/workspace", readonly=True),
    ]
    for target in public_mount_targets:
        mounts.append(
            AppleContainerMount(
                source=str(workspace_root / target),
                target=f"/workspace/{target}",
                readonly=True,
            )
        )
    for target in writable_mount_targets:
        mounts.append(
            AppleContainerMount(
                source=str(workspace_root / target),
                target=f"/workspace/{target}",
                readonly=False,
            )
        )
    return AppleContainerRunSpec(
        container_name=f"smbagent-{customer_id}-{stage}",
        image=image,
        command=tuple(command),
        mounts=tuple(mounts),
        env_file=str(env_file) if env_file is not None else None,
        env_names=env_names,
        remove_on_exit=True,
        read_only_root=True,
        no_dns=False,
        rosetta=rosetta,
        init=True,
        workdir="/workspace",
        tmpfs_targets=("/tmp", "/var/tmp"),
    )


def render_apple_container_command(spec: AppleContainerRunSpec) -> list[str]:
    cmd = ["container", "run", "--name", spec.container_name]
    if spec.remove_on_exit:
        cmd.append("--rm")
    if spec.read_only_root:
        cmd.append("--read-only")
    if spec.no_dns:
        cmd.append("--no-dns")
    if spec.init:
        cmd.append("--init")
    if spec.workdir:
        cmd.extend(["--workdir", spec.workdir])
    if spec.rosetta:
        cmd.append("--rosetta")
    if spec.env_file:
        cmd.extend(["--env-file", spec.env_file])
    for env_name in spec.env_names:
        cmd.extend(["--env", env_name])
    for tmpfs_target in spec.tmpfs_targets:
        cmd.extend(["--tmpfs", tmpfs_target])
    for mount in spec.mounts:
        cmd.extend(["--mount", mount.as_flag()])
    cmd.append(spec.image)
    cmd.extend(spec.command)
    return cmd


def build_apple_container_plan(config) -> AppleContainerPlan:
    images = (
        AppleContainerImageContract(
            role="coding",
            image=config.apple_container_coding_image,
            cli_binary="claude",
            required_env=apple_container_required_env_for_role("coding"),
            install_contract="npm install -g @anthropic-ai/claude-code@latest",
            expected_command=tuple(config.coding_cmd),
        ),
        AppleContainerImageContract(
            role="validation",
            image=config.apple_container_validation_image,
            cli_binary="codex",
            required_env=apple_container_required_env_for_role("validation"),
            install_contract="npm install -g @openai/codex@latest",
            expected_command=tuple(config.validation_cmd),
        ),
    )
    missing: list[str] = []
    env_map = {
        "ANTHROPIC_API_KEY": getattr(config, "anthropic_api_key", None),
        "OPENAI_API_KEY": getattr(config, "openai_api_key", None),
    }
    for name, value in env_map.items():
        if not value:
            missing.append(name)
    return AppleContainerPlan(
        provider=APPLE_CONTAINER_PROVIDER,
        no_published_ports=True,
        shared_runtime_guarantees=(
            "no published ports",
            "read-only root filesystem",
            "tmpfs for /tmp and /var/tmp",
            "read-only mounts for public plan/context artifacts",
            "writable mounts only for run outputs and validation snapshots",
            "runtime env injection for secrets; no secrets baked into image layers",
            "coding, validation, smoke, and benchmark lanes share the same Apple container contract",
        ),
        images=images,
        missing_env=tuple(sorted(set(missing))),
    )


__all__ = [
    "APPLE_CONTAINER_PROVIDER",
    "AppleContainerImageContract",
    "AppleContainerMount",
    "AppleContainerPlan",
    "AppleContainerRunSpec",
    "CODING_ROLE_FAMILY",
    "LEGACY_MACOS_SANDBOX_PROVIDER",
    "LINUX_BWRAP_PROVIDER",
    "OFF_VALUES",
    "VALIDATION_ROLE_FAMILY",
    "apple_container_image_for_role",
    "apple_container_required_env_for_role",
    "apple_container_role_family",
    "build_apple_container_plan",
    "build_apple_container_run_spec",
    "normalize_subprocess_isolation",
    "render_apple_container_command",
    "subprocess_isolation_enabled",
    "subprocess_isolation_is_legacy_macos_sandbox",
    "subprocess_isolation_is_official_apple_container",
    "subprocess_isolation_provider_label",
]
