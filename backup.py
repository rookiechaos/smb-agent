from __future__ import annotations

import json
import os
import shutil
import subprocess
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .artifact_freshness import artifact_path_strings, publish_workspace_artifact_freshness
from .config import Config
from .workspace import Workspace


class BackupError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackupResult:
    archive_path: Path
    customer_id: str
    encrypted: bool = False
    manifest_path: Path | None = None


@dataclass(frozen=True)
class BackupManifest:
    generated_at: str
    customer_id: str
    archive_path: str
    encrypted: bool
    encryption_mode: str


def backup_workspace(
    workspace: Workspace,
    backup_dir: Path | None = None,
    *,
    config: Config | None = None,
) -> BackupResult:
    if not workspace.path.exists():
        raise BackupError(f"workspace does not exist: {workspace.path}")
    backup_root = backup_dir or (workspace.path.parent / "_backups")
    backup_root.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archive_path = backup_root / f"{workspace.customer_id}-{ts}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(workspace.path, arcname=workspace.customer_id, recursive=True)
    final_path = archive_path
    encrypted = False
    encryption_mode = "none"
    if config is not None and config.backup_encryption_mode == "openssl-aes256":
        passphrase = os.environ.get(config.backup_encryption_passphrase_env, "")
        if not passphrase:
            raise BackupError(
                f"encrypted backup requested, but {config.backup_encryption_passphrase_env} is not set"
            )
        if shutil.which("openssl") is None:
            raise BackupError("openssl is required for SMBAGENT_BACKUP_ENCRYPTION_MODE=openssl-aes256")
        final_path = archive_path.with_suffix(archive_path.suffix + ".enc")
        _encrypt_archive_openssl(archive_path, final_path, passphrase)
        archive_path.unlink(missing_ok=True)
        encrypted = True
        encryption_mode = config.backup_encryption_mode
    manifest = BackupManifest(
        generated_at=_iso_z(),
        customer_id=workspace.customer_id,
        archive_path=str(final_path),
        encrypted=encrypted,
        encryption_mode=encryption_mode,
    )
    manifest_path = final_path.with_name(final_path.name + ".backup.json")
    manifest_path.write_text(json.dumps(manifest.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
    publish_workspace_artifact_freshness(
        workspace,
        artifact_key="latest_backup",
        artifact_paths=artifact_path_strings([final_path, manifest_path], relative_to=workspace.path.parent),
        writer="backup.backup_workspace",
        detail=(
            "workspace backup archive created"
            if not encrypted
            else f"workspace backup archive created with {encryption_mode} encryption"
        ),
        source_sections=[],
    )
    return BackupResult(
        archive_path=final_path,
        customer_id=workspace.customer_id,
        encrypted=encrypted,
        manifest_path=manifest_path,
    )


def restore_workspace(
    *,
    archive_path: Path,
    workspaces_dir: Path,
    customer_id: str | None = None,
    force: bool = False,
    config: Config | None = None,
) -> Workspace:
    if not archive_path.exists():
        raise BackupError(f"backup archive does not exist: {archive_path}")
    effective_archive = archive_path
    cleanup_tmp: Path | None = None
    if archive_path.name.endswith(".enc"):
        if config is None:
            raise BackupError("encrypted restore requires config for passphrase env resolution")
        passphrase = os.environ.get(config.backup_encryption_passphrase_env, "")
        if not passphrase:
            raise BackupError(
                f"encrypted restore requested, but {config.backup_encryption_passphrase_env} is not set"
            )
        if shutil.which("openssl") is None:
            raise BackupError("openssl is required for encrypted restore")
        cleanup_tmp = (
            workspaces_dir / f".restore-decrypted-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.tar.gz"
        )
        _decrypt_archive_openssl(archive_path, cleanup_tmp, passphrase)
        effective_archive = cleanup_tmp
    try:
        with tarfile.open(effective_archive, "r:gz") as tar:
            members = tar.getmembers()
        archive_root = _archive_root(members) or _infer_customer_id(archive_path)
        target_id = customer_id or archive_root
        workspace = Workspace(target_id, workspaces_dir)
        if workspace.path.exists():
            if not force:
                raise BackupError(
                    f"workspace already exists: {workspace.path}. Use --force to move it aside before restore."
                )
            moved = workspace.path.with_name(
                f"{workspace.path.name}.pre-restore-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
            )
            shutil.move(str(workspace.path), str(moved))
        workspaces_dir.mkdir(parents=True, exist_ok=True)
        restore_tmp = workspaces_dir / f".restore-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
        if restore_tmp.exists():
            shutil.rmtree(restore_tmp)
        restore_tmp.mkdir(parents=True)
        try:
            with tarfile.open(effective_archive, "r:gz") as tar:
                _validate_members(members, archive_root)
                try:
                    tar.extractall(restore_tmp, members=members, filter="data")
                except TypeError:
                    tar.extractall(restore_tmp, members=members)
            extracted = restore_tmp / archive_root
            if not extracted.exists():
                raise BackupError(f"archive did not contain expected root: {archive_root}")
            shutil.move(str(extracted), str(workspace.path))
        finally:
            if restore_tmp.exists():
                shutil.rmtree(restore_tmp)
        return workspace
    finally:
        if cleanup_tmp is not None and cleanup_tmp.exists():
            cleanup_tmp.unlink()


def _encrypt_archive_openssl(source: Path, target: Path, passphrase: str) -> None:
    subprocess.run(
        [
            "openssl",
            "enc",
            "-aes-256-cbc",
            "-pbkdf2",
            "-salt",
            "-in",
            str(source),
            "-out",
            str(target),
            "-pass",
            f"pass:{passphrase}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def _decrypt_archive_openssl(source: Path, target: Path, passphrase: str) -> None:
    subprocess.run(
        [
            "openssl",
            "enc",
            "-d",
            "-aes-256-cbc",
            "-pbkdf2",
            "-in",
            str(source),
            "-out",
            str(target),
            "-pass",
            f"pass:{passphrase}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def _infer_customer_id(archive_path: Path) -> str:
    name = archive_path.name
    for suffix in (".tar.gz.enc", ".tar.gz"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    parts = name.rsplit("-", 1)
    return parts[0] if parts else name


def _validate_members(members: list[tarfile.TarInfo], customer_id: str) -> None:
    prefix = f"{customer_id}/"
    for member in members:
        name = member.name
        if name == customer_id:
            continue
        if not name.startswith(prefix):
            raise BackupError(f"archive member escapes customer root: {name}")
        if ".." in Path(name).parts:
            raise BackupError(f"archive member contains parent traversal: {name}")
        if member.islnk() or member.issym():
            raise BackupError(f"archive contains link member, refusing restore: {name}")


def _archive_root(members: list[tarfile.TarInfo]) -> str | None:
    roots: set[str] = set()
    for member in members:
        parts = Path(member.name).parts
        if not parts:
            continue
        roots.add(parts[0])
    if len(roots) != 1:
        return None
    return next(iter(roots))


def _iso_z() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
