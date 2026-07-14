"""Per-customer API tokens for the hosted skills runtime.

Each customer has bearer token hashes stored in workspace-local auth files.
The runtime uses `auth.json`; the owner-facing monitor uses `monitor_auth.json`.
Tokens are opaque to clients — they present them in the Authorization header
or, for the browser-friendly owner monitor, through a login flow that stores an
HttpOnly cookie. Query-token monitor access remains fallback-only.

Tokens are minted via `issue_token(workspace, ttl_days=...)` and verified via
`verify_token`. They are 32 bytes of cryptographic randomness, urlsafe-base64-
encoded. Persistence stores a salted PBKDF2 hash, not the bearer token itself.
Separate token files support separate lanes:

- `auth.json` for operator/runtime access
- `employee_auth.json` for employee-facing chat/skills access
- `monitor_auth.json` for the owner-facing read-only monitor

Backward compatibility: older auth.json files without `expires_at` or `revoked`
fields still verify correctly (never expire, never revoked).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .workspace import Workspace


class AuthError(RuntimeError):
    """Raised on any auth-resolution failure (missing token file, mismatch, etc.)."""


@dataclass
class TokenRecord:
    customer_id: str
    token: str | None  # only populated at issue/rotation time; never persisted for hashed records
    created_at: str  # ISO-8601 UTC
    expires_at: str | None = None  # ISO-8601 UTC; None = never expires
    revoked: bool = False
    token_hash: str | None = None

    def as_json(self) -> str:
        data = {
            "customer_id": self.customer_id,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "revoked": self.revoked,
        }
        if self.token_hash:
            data["token_hash"] = self.token_hash
        elif self.token:
            # Backward-compatible writer fallback. Normal issue_token() always
            # supplies token_hash, so commercial paths do not persist plaintext.
            data["token_hash"] = hash_token(self.token)
        return json.dumps(
            {
                **data,
            },
            indent=2,
        )

    @classmethod
    def from_json(cls, blob: str) -> TokenRecord:
        d = json.loads(blob)
        token = d.get("token")
        token_hash = d.get("token_hash")
        if not token and not token_hash:
            raise KeyError("token_hash")
        return cls(
            customer_id=d["customer_id"],
            token=token,
            created_at=d["created_at"],
            expires_at=d.get("expires_at"),  # backward-compat: legacy files lack this
            revoked=bool(d.get("revoked", False)),
            token_hash=token_hash,
        )

    def is_expired(self, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        now = now or datetime.now(UTC)
        try:
            exp = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        except ValueError:
            # Malformed expiry → treat as expired so we fail closed.
            return True
        return now >= exp


def _auth_path(workspace: Workspace) -> Path:
    return workspace.path / "auth.json"


def _monitor_auth_path(workspace: Workspace) -> Path:
    return workspace.path / "monitor_auth.json"


def _employee_auth_path(workspace: Workspace) -> Path:
    return workspace.path / "employee_auth.json"


def _iso_z(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def hash_token(token: str, *, iterations: int = 260_000) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", token.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_token_hash(token_hash: str, presented_token: str) -> bool:
    try:
        scheme, iterations_s, salt_s, digest_s = token_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iterations_s)
        salt = base64.urlsafe_b64decode(salt_s.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_s.encode("ascii"))
    except Exception:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", (presented_token or "").encode("utf-8"), salt, iterations)
    return secrets.compare_digest(actual, expected)


def issue_token(
    workspace: Workspace,
    force: bool = False,
    ttl_days: int = 0,
) -> TokenRecord:
    """Mint a fresh token. If one exists and `force` is False, returns existing.

    ttl_days <= 0 → token never expires.
    """
    path = _auth_path(workspace)
    return _issue_token_to_path(workspace, path=path, force=force, ttl_days=ttl_days)


def issue_monitor_token(
    workspace: Workspace,
    force: bool = False,
    ttl_days: int = 0,
) -> TokenRecord:
    """Mint a read-only token for the owner-facing workflow monitor."""
    path = _monitor_auth_path(workspace)
    return _issue_token_to_path(workspace, path=path, force=force, ttl_days=ttl_days)


def issue_employee_token(
    workspace: Workspace,
    force: bool = False,
    ttl_days: int = 0,
) -> TokenRecord:
    """Mint a narrow token for employee-facing chat + skills access."""
    path = _employee_auth_path(workspace)
    return _issue_token_to_path(workspace, path=path, force=force, ttl_days=ttl_days)


def _issue_token_to_path(
    workspace: Workspace,
    *,
    path: Path,
    force: bool,
    ttl_days: int,
) -> TokenRecord:
    if path.exists() and not force:
        rec = TokenRecord.from_json(path.read_text(encoding="utf-8"))
        if rec.token and not rec.token_hash:
            rec.token_hash = hash_token(rec.token)
            path.write_text(rec.as_json(), encoding="utf-8")
            try:
                path.chmod(0o600)
            except OSError:
                pass
        return rec

    now = datetime.now(UTC)
    expires_at: str | None = None
    if ttl_days > 0:
        expires_at = _iso_z(now + timedelta(days=ttl_days))

    token = secrets.token_urlsafe(32)
    rec = TokenRecord(
        customer_id=workspace.customer_id,
        token=token,
        created_at=_iso_z(now),
        expires_at=expires_at,
        revoked=False,
        token_hash=hash_token(token),
    )
    workspace.ensure()
    path.write_text(rec.as_json(), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return rec


def revoke_token(workspace: Workspace) -> TokenRecord:
    """Mark the current token as revoked. Subsequent verify_token() calls fail."""
    rec = load_token(workspace)
    rec.revoked = True
    _auth_path(workspace).write_text(rec.as_json(), encoding="utf-8")
    return rec


def load_token(workspace: Workspace) -> TokenRecord:
    """Read the persisted token. Raises AuthError if missing or malformed."""
    path = _auth_path(workspace)
    if not path.exists():
        raise AuthError(
            f"no auth.json for {workspace.customer_id} at {path}. "
            f"Run `smbagent auth-issue {workspace.customer_id}` first."
        )
    try:
        return TokenRecord.from_json(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError) as e:
        raise AuthError(f"malformed auth.json for {workspace.customer_id}: {e}") from e


def verify_token(workspace: Workspace, presented_token: str) -> bool:
    """Constant-time comparison + TTL + revocation check.

    Returns True iff:
      - auth.json exists and parses
      - presented_token matches stored token (constant-time compare)
      - token is not revoked
      - token has not expired

    Does NOT raise on mismatch — that's a caller decision (HTTP 401 vs structured).
    """
    try:
        record = load_token(workspace)
    except AuthError:
        return False
    if record.revoked:
        return False
    if record.is_expired():
        return False
    if record.token_hash:
        return verify_token_hash(record.token_hash, presented_token or "")
    if record.token is not None:
        return secrets.compare_digest(record.token, presented_token or "")
    return False


def load_monitor_token(workspace: Workspace) -> TokenRecord:
    """Read the persisted owner-monitor token. Raises AuthError if missing."""
    path = _monitor_auth_path(workspace)
    if not path.exists():
        raise AuthError(
            f"no monitor_auth.json for {workspace.customer_id} at {path}. "
            f"Run `smbagent monitor-auth-issue {workspace.customer_id}` first."
        )
    try:
        return TokenRecord.from_json(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError) as e:
        raise AuthError(f"malformed monitor_auth.json for {workspace.customer_id}: {e}") from e


def load_employee_token(workspace: Workspace) -> TokenRecord:
    """Read the persisted employee token. Raises AuthError if missing."""
    path = _employee_auth_path(workspace)
    if not path.exists():
        raise AuthError(
            f"no employee_auth.json for {workspace.customer_id} at {path}. "
            f"Run `smbagent employee-auth-issue {workspace.customer_id}` first."
        )
    try:
        return TokenRecord.from_json(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError) as e:
        raise AuthError(f"malformed employee_auth.json for {workspace.customer_id}: {e}") from e


def verify_monitor_token(workspace: Workspace, presented_token: str | None) -> bool:
    """Constant-time verification for the owner-facing read-only monitor token."""
    try:
        record = load_monitor_token(workspace)
    except AuthError:
        return False
    if record.revoked:
        return False
    if record.is_expired():
        return False
    if record.token_hash:
        return verify_token_hash(record.token_hash, presented_token or "")
    if record.token is not None:
        return secrets.compare_digest(record.token, presented_token or "")
    return False


def verify_employee_token(workspace: Workspace, presented_token: str | None) -> bool:
    """Constant-time verification for employee-facing chat + skills access."""
    try:
        record = load_employee_token(workspace)
    except AuthError:
        return False
    if record.revoked:
        return False
    if record.is_expired():
        return False
    if record.token_hash:
        return verify_token_hash(record.token_hash, presented_token or "")
    if record.token is not None:
        return secrets.compare_digest(record.token, presented_token or "")
    return False


def rotate_legacy_plaintext_tokens(workspaces_dir: Path) -> list[str]:
    """Migrate legacy plaintext auth.json files to hash-only storage.

    This preserves the current bearer token while removing plaintext at rest.
    It returns customer_ids that were migrated. It does not print or expose
    token values.
    """
    migrated: list[str] = []
    if not workspaces_dir.exists():
        return migrated
    for auth_path in sorted(workspaces_dir.glob("*/auth.json")):
        try:
            data = json.loads(auth_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if "token" not in data or "token_hash" in data:
            continue
        customer_id = auth_path.parent.name
        rec = TokenRecord.from_json(auth_path.read_text(encoding="utf-8"))
        if not rec.token:
            continue
        rec.token_hash = hash_token(rec.token)
        rec.token = None
        auth_path.write_text(rec.as_json(), encoding="utf-8")
        try:
            auth_path.chmod(0o600)
        except OSError:
            pass
        migrated.append(customer_id)
    return migrated
