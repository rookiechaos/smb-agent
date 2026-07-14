from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from .backup import BackupError, backup_workspace, restore_workspace
from .config import Config
from .workspace import Workspace


@dataclass(frozen=True)
class EncryptedBackupDrillResult:
    customer_id: str
    archive_path: str
    manifest_path: str
    restore_verified: bool
    detail: str


def evaluate_encrypted_backup_posture(config: Config) -> tuple[bool, str]:
    if not config.sensitive_mode:
        return True, "sensitive mode is off; encrypted backup posture is advisory only"
    if config.backup_encryption_mode != "openssl-aes256":
        return False, f"backup_encryption_mode={config.backup_encryption_mode}"
    if not os.environ.get(config.backup_encryption_passphrase_env, "").strip():
        return False, f"{config.backup_encryption_passphrase_env} is not set"
    if shutil.which("openssl") is None:
        return False, "openssl is required for encrypted backup drills"
    return True, "encrypted backup posture is configured for sensitive deployments"


def run_encrypted_backup_drill(
    config: Config,
    workspace: Workspace,
    *,
    verify_restore: bool = True,
) -> EncryptedBackupDrillResult:
    ready, detail = evaluate_encrypted_backup_posture(config)
    if not ready:
        raise BackupError(detail)
    result = backup_workspace(workspace, config=config)
    if not result.encrypted or result.manifest_path is None:
        raise BackupError("expected encrypted backup archive and manifest")
    restore_verified = False
    if verify_restore:
        probe_dir = config.workspaces_dir / ".backup-drill"
        probe_dir.mkdir(parents=True, exist_ok=True)
        restored = restore_workspace(
            archive_path=result.archive_path,
            workspaces_dir=probe_dir,
            customer_id=f"{workspace.customer_id}-drill",
            force=True,
            config=config,
        )
        restore_verified = restored.path.exists()
        if restored.path.exists():
            shutil.rmtree(restored.path, ignore_errors=True)
    return EncryptedBackupDrillResult(
        customer_id=workspace.customer_id,
        archive_path=str(result.archive_path),
        manifest_path=str(result.manifest_path),
        restore_verified=restore_verified,
        detail="encrypted backup created and restore probe succeeded"
        if restore_verified
        else "encrypted backup created",
    )


def write_encrypted_backup_drill_report(
    config: Config, result: EncryptedBackupDrillResult, out_path: Path
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


__all__ = [
    "EncryptedBackupDrillResult",
    "evaluate_encrypted_backup_posture",
    "run_encrypted_backup_drill",
    "write_encrypted_backup_drill_report",
]
