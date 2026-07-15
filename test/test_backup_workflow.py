from __future__ import annotations

from smbagent.backup_workflow import evaluate_encrypted_backup_posture, run_encrypted_backup_drill


def test_evaluate_encrypted_backup_posture_requires_passphrase(config):
    cfg = type(config)(
        **{
            **config.__dict__,
            "sensitive_mode": True,
            "backup_encryption_mode": "openssl-aes256",
        }
    )
    ready, detail = evaluate_encrypted_backup_posture(cfg)
    assert ready is False
    assert "SMBAGENT_BACKUP_PASSPHRASE" in detail


def test_run_encrypted_backup_drill_round_trip(config, workspace, monkeypatch):
    cfg = type(config)(
        **{
            **config.__dict__,
            "sensitive_mode": True,
            "backup_encryption_mode": "openssl-aes256",
        }
    )
    monkeypatch.setenv(cfg.backup_encryption_passphrase_env, "test-passphrase")
    result = run_encrypted_backup_drill(cfg, workspace)
    assert result.restore_verified is True
    assert str(result.archive_path).endswith(".tar.gz.enc")
