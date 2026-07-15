from __future__ import annotations

import json

import pytest

from smbagent.auth import (
    AuthError,
    TokenRecord,
    hash_token,
    issue_employee_token,
    issue_monitor_token,
    issue_token,
    load_employee_token,
    load_monitor_token,
    load_token,
    rotate_legacy_plaintext_tokens,
    verify_employee_token,
    verify_monitor_token,
    verify_token,
)
from smbagent.config import Config
from smbagent.workspace import Workspace


def test_issue_token_creates_auth_json(config: Config, workspace: Workspace):
    rec = issue_token(workspace)
    auth_path = workspace.path / "auth.json"
    assert auth_path.exists()
    assert rec.customer_id == workspace.customer_id
    assert rec.token is not None
    assert len(rec.token) >= 32  # urlsafe-base64 of 32 bytes ≈ 43 chars
    on_disk = json.loads(auth_path.read_text(encoding="utf-8"))
    assert "token_hash" in on_disk
    assert "token" not in on_disk
    # ISO-8601 with Z suffix
    assert rec.created_at.endswith("Z")


def test_issue_token_is_idempotent_by_default(config: Config, workspace: Workspace):
    first = issue_token(workspace)
    second = issue_token(workspace)
    assert first.token is not None
    assert second.token is None  # existing hash-only token cannot be recovered
    assert first.created_at == second.created_at


def test_issue_token_force_rotates(config: Config, workspace: Workspace):
    first = issue_token(workspace)
    second = issue_token(workspace, force=True)
    assert first.token != second.token


def test_issue_token_creates_workspace_dir_if_missing(config: Config):
    """Workspace doesn't need to be `ensured` before issuing — issue_token handles it."""
    ws = Workspace("freshcust", config.workspaces_dir)
    issue_token(ws)
    assert (ws.path / "auth.json").exists()


def test_load_token_returns_record(config: Config, workspace: Workspace):
    rec = issue_token(workspace)
    loaded = load_token(workspace)
    assert loaded.customer_id == rec.customer_id
    assert loaded.token is None
    assert loaded.token_hash == rec.token_hash


def test_load_token_raises_when_missing(config: Config, workspace: Workspace):
    with pytest.raises(AuthError) as excinfo:
        load_token(workspace)
    assert "no auth.json" in str(excinfo.value)


def test_load_token_raises_on_malformed_json(config: Config, workspace: Workspace):
    (workspace.path / "auth.json").write_text("not json", encoding="utf-8")
    with pytest.raises(AuthError) as excinfo:
        load_token(workspace)
    assert "malformed" in str(excinfo.value)


def test_load_token_raises_on_missing_required_key(config: Config, workspace: Workspace):
    (workspace.path / "auth.json").write_text(json.dumps({"token": "x"}), encoding="utf-8")
    with pytest.raises(AuthError):
        load_token(workspace)


def test_verify_token_accepts_correct_token(config: Config, workspace: Workspace):
    rec = issue_token(workspace)
    assert rec.token is not None
    assert verify_token(workspace, rec.token) is True


def test_verify_token_rejects_wrong_token(config: Config, workspace: Workspace):
    issue_token(workspace)
    assert verify_token(workspace, "definitely-not-the-token") is False


def test_verify_token_rejects_empty_string(config: Config, workspace: Workspace):
    issue_token(workspace)
    assert verify_token(workspace, "") is False


def test_verify_token_rejects_none(config: Config, workspace: Workspace):
    issue_token(workspace)
    assert verify_token(workspace, None) is False  # type: ignore[arg-type]


def test_verify_token_returns_false_when_no_auth_json(config: Config, workspace: Workspace):
    """Customer that hasn't been issued a token yet → verify always False (no crash)."""
    assert verify_token(workspace, "anything") is False


def test_tokens_are_unique_across_customers(config: Config):
    ws1 = Workspace("alpha", config.workspaces_dir)
    ws2 = Workspace("beta", config.workspaces_dir)
    t1 = issue_token(ws1)
    t2 = issue_token(ws2)
    assert t1.token != t2.token


def test_verify_one_customers_token_doesnt_unlock_another(config: Config):
    """Token for customer A must NOT pass verification for customer B."""
    ws_a = Workspace("alpha", config.workspaces_dir)
    ws_b = Workspace("beta", config.workspaces_dir)
    t_a = issue_token(ws_a)
    assert t_a.token is not None
    issue_token(ws_b)
    # presenting alpha's token against beta's workspace must fail
    assert verify_token(ws_b, t_a.token) is False


def test_issue_monitor_token_creates_monitor_auth_json(config: Config, workspace: Workspace):
    rec = issue_monitor_token(workspace)
    auth_path = workspace.path / "monitor_auth.json"
    assert auth_path.exists()
    assert rec.customer_id == workspace.customer_id
    assert rec.token is not None
    on_disk = json.loads(auth_path.read_text(encoding="utf-8"))
    assert "token_hash" in on_disk
    assert "token" not in on_disk


def test_load_monitor_token_raises_when_missing(config: Config, workspace: Workspace):
    with pytest.raises(AuthError) as excinfo:
        load_monitor_token(workspace)
    assert "no monitor_auth.json" in str(excinfo.value)


def test_verify_monitor_token_accepts_correct_token(config: Config, workspace: Workspace):
    rec = issue_monitor_token(workspace)
    assert rec.token is not None
    assert verify_monitor_token(workspace, rec.token) is True


def test_verify_monitor_token_rejects_other_customers_token(config: Config):
    ws_a = Workspace("alpha-monitor", config.workspaces_dir)
    ws_b = Workspace("beta-monitor", config.workspaces_dir)
    t_a = issue_monitor_token(ws_a)
    assert t_a.token is not None
    issue_monitor_token(ws_b)
    assert verify_monitor_token(ws_b, t_a.token) is False


def test_issue_employee_token_creates_employee_auth_json(config: Config, workspace: Workspace):
    rec = issue_employee_token(workspace)
    auth_path = workspace.path / "employee_auth.json"
    assert auth_path.exists()
    assert rec.customer_id == workspace.customer_id
    assert rec.token is not None
    on_disk = json.loads(auth_path.read_text(encoding="utf-8"))
    assert "token_hash" in on_disk
    assert "token" not in on_disk


def test_load_employee_token_raises_when_missing(config: Config, workspace: Workspace):
    with pytest.raises(AuthError) as excinfo:
        load_employee_token(workspace)
    assert "no employee_auth.json" in str(excinfo.value)


def test_verify_employee_token_accepts_correct_token(config: Config, workspace: Workspace):
    rec = issue_employee_token(workspace)
    assert rec.token is not None
    assert verify_employee_token(workspace, rec.token) is True


def test_verify_token_accepts_legacy_plaintext_record(config: Config, workspace: Workspace):
    legacy = TokenRecord(
        customer_id=workspace.customer_id,
        token="legacy-token",
        created_at="2026-01-01T00:00:00Z",
    )
    (workspace.path / "auth.json").write_text(
        json.dumps(
            {
                "customer_id": legacy.customer_id,
                "token": legacy.token,
                "created_at": legacy.created_at,
            }
        ),
        encoding="utf-8",
    )
    assert verify_token(workspace, "legacy-token") is True


def test_hash_token_uses_random_salt():
    first = hash_token("same-token")
    second = hash_token("same-token")
    assert first != second
    assert first.startswith("pbkdf2_sha256$")


def test_rotate_legacy_plaintext_tokens_migrates_without_exposing_token(config: Config):
    ws = Workspace("legacy-rotate", config.workspaces_dir)
    ws.ensure()
    (ws.path / "auth.json").write_text(
        json.dumps(
            {
                "customer_id": ws.customer_id,
                "token": "legacy-token",
                "created_at": "2026-01-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    migrated = rotate_legacy_plaintext_tokens(config.workspaces_dir)

    assert migrated == ["legacy-rotate"]
    data = json.loads((ws.path / "auth.json").read_text(encoding="utf-8"))
    assert "token_hash" in data
    assert "token" not in data
    assert verify_token(ws, "legacy-token") is True
