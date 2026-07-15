from __future__ import annotations

import json
import tarfile
from pathlib import Path

import pytest

from smbagent.backup import BackupError, backup_workspace, restore_workspace


def test_backup_and_restore_workspace(config, workspace):
    (workspace.path / "notes.txt").write_text("hello", encoding="utf-8")
    result = backup_workspace(workspace)
    assert result.archive_path.exists()
    state = json.loads(workspace.workspace_state_path.read_text(encoding="utf-8"))
    freshness = state["sections"]["artifact_freshness"]["latest_backup"]
    assert freshness["status"] == "fresh"
    assert str(Path("_backups") / result.archive_path.name) in freshness["artifact_paths"]
    assert any(item.endswith(".backup.json") for item in freshness["artifact_paths"])
    assert "backup archive created" in freshness["detail"]

    restored = restore_workspace(
        archive_path=result.archive_path,
        workspaces_dir=config.workspaces_dir,
        customer_id="restored-co",
    )
    assert (restored.path / "notes.txt").read_text(encoding="utf-8") == "hello"


def test_restore_refuses_to_overwrite_without_force(config, workspace):
    result = backup_workspace(workspace)
    with pytest.raises(BackupError):
        restore_workspace(
            archive_path=result.archive_path,
            workspaces_dir=config.workspaces_dir,
            customer_id=workspace.customer_id,
        )


def test_restore_rejects_path_traversal_member(config, tmp_path):
    archive = tmp_path / "bad.tar.gz"
    payload = tmp_path / "payload.txt"
    payload.write_text("bad", encoding="utf-8")
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(payload, arcname="../escape.txt")

    with pytest.raises(BackupError):
        restore_workspace(
            archive_path=archive,
            workspaces_dir=config.workspaces_dir,
            customer_id="bad",
        )


def test_encrypted_backup_writes_encrypted_archive(config, workspace, monkeypatch):
    import smbagent.backup as backup_mod

    cfg = type(config)(**{**config.__dict__, "backup_encryption_mode": "openssl-aes256"})
    monkeypatch.setenv(cfg.backup_encryption_passphrase_env, "secret-passphrase")
    monkeypatch.setattr(backup_mod.shutil, "which", lambda name: "/usr/bin/openssl")

    def fake_run(cmd, **kwargs):
        out_idx = cmd.index("-out") + 1
        Path(cmd[out_idx]).write_bytes(b"encrypted")

        class _Proc:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Proc()

    monkeypatch.setattr(backup_mod.subprocess, "run", fake_run)
    result = backup_mod.backup_workspace(workspace, config=cfg)
    assert result.encrypted is True
    assert result.archive_path.name.endswith(".enc")
    assert result.manifest_path is not None and result.manifest_path.exists()
