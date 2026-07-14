from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from .workspace import Workspace

ApprovalDecision = Literal["approved", "rejected", "override"]
ApprovalEventType = Literal["decision", "use"]

_IDENTITY_RE = re.compile(r"^(human|system|service):[A-Za-z0-9][A-Za-z0-9._@+-]{1,127}$")


@dataclass(frozen=True)
class OperatorApprovalEvent:
    schema_version: int
    event_type: ApprovalEventType
    approval_id: str
    ts: str
    customer_id: str
    action: str
    resource: str
    operator: str
    reason: str
    decision: ApprovalDecision | None = None
    expires_at: str | None = None
    command: str | None = None
    outcome: str | None = None


class OperatorApprovalLog:
    """Append-only operator approval log for HITL and override decisions."""

    SCHEMA_VERSION = 1

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.log_path = workspace.path / "operator_approvals.jsonl"

    def record_decision(
        self,
        *,
        action: str,
        resource: str,
        decision: ApprovalDecision,
        operator: str,
        reason: str,
        ttl_hours: int | None = 24,
    ) -> OperatorApprovalEvent:
        approval_id = str(uuid.uuid4())
        expires_at: str | None = None
        if ttl_hours is not None and ttl_hours > 0:
            expires_at = _iso_z(datetime.now(UTC) + timedelta(hours=ttl_hours))
        normalized_operator = normalize_operator_identity(operator)
        event = OperatorApprovalEvent(
            schema_version=self.SCHEMA_VERSION,
            event_type="decision",
            approval_id=approval_id,
            ts=_iso_z(datetime.now(UTC)),
            customer_id=self.workspace.customer_id,
            action=action,
            resource=resource,
            operator=normalized_operator,
            reason=reason,
            decision=decision,
            expires_at=expires_at,
        )
        self._append(event)
        return event

    def record_use(
        self,
        *,
        approval_id: str,
        action: str,
        resource: str,
        operator: str,
        command: str,
        outcome: str,
    ) -> OperatorApprovalEvent:
        normalized_operator = normalize_operator_identity(operator)
        event = OperatorApprovalEvent(
            schema_version=self.SCHEMA_VERSION,
            event_type="use",
            approval_id=approval_id,
            ts=_iso_z(datetime.now(UTC)),
            customer_id=self.workspace.customer_id,
            action=action,
            resource=resource,
            operator=normalized_operator,
            reason="approval consumed by operator command",
            command=command,
            outcome=outcome,
        )
        self._append(event)
        return event

    def read_all(self) -> list[OperatorApprovalEvent]:
        if not self.log_path.exists():
            return []
        out: list[OperatorApprovalEvent] = []
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(OperatorApprovalEvent(**json.loads(line)))
            except (json.JSONDecodeError, TypeError):
                continue
        return out

    def validate_approval(
        self,
        *,
        approval_id: str,
        action: str,
        resource: str,
    ) -> tuple[bool, str]:
        events = self.read_all()
        decisions = [e for e in events if e.event_type == "decision" and e.approval_id == approval_id]
        if not decisions:
            return False, f"approval_id {approval_id!r} not found"
        decision = decisions[-1]
        if decision.customer_id != self.workspace.customer_id:
            return False, "approval belongs to a different customer"
        if decision.action != action or decision.resource != resource:
            return False, (
                "approval does not match requested action/resource "
                f"(expected action={action}, resource={resource})"
            )
        if decision.decision not in ("approved", "override"):
            return False, f"approval decision is {decision.decision!r}, not approved"
        if decision.expires_at:
            try:
                expires_at = datetime.fromisoformat(decision.expires_at.replace("Z", "+00:00"))
            except ValueError:
                return False, "approval expiry is malformed"
            if datetime.now(UTC) >= expires_at:
                return False, "approval has expired"
        if any(e.event_type == "use" and e.approval_id == approval_id for e in events):
            return False, "approval has already been used"
        return True, "approval valid"

    def _append(self, event: OperatorApprovalEvent) -> None:
        self.workspace.ensure()
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")


def _iso_z(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_operator_identity(operator: str) -> str:
    """Return the canonical approval-log identity.

    Commercial convention:
      - human:<email-or-name>
      - system:<service-name>
      - service:<service-name>

    Bare values are accepted for CLI ergonomics and normalized to human:<value>.
    """
    value = (operator or "").strip()
    if not value:
        return "human:unknown"
    if _IDENTITY_RE.fullmatch(value):
        return value
    if ":" in value:
        prefix, rest = value.split(":", 1)
        prefix = prefix.lower()
        rest = _sanitize_identity_part(rest)
        if prefix in {"human", "system", "service"} and rest:
            return f"{prefix}:{rest}"
    return f"human:{_sanitize_identity_part(value) or 'unknown'}"


def count_pending_approvals(workspace: Workspace) -> int:
    log = OperatorApprovalLog(workspace)
    events = log.read_all()
    decisions = {
        event.approval_id: event
        for event in events
        if event.event_type == "decision" and event.decision in {"approved", "override"}
    }
    used = {event.approval_id for event in events if event.event_type == "use"}
    pending = 0
    now = datetime.now(UTC)
    for approval_id, event in decisions.items():
        if approval_id in used:
            continue
        if event.expires_at:
            try:
                expires_at = datetime.fromisoformat(event.expires_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            if now >= expires_at:
                continue
        pending += 1
    return pending


def _sanitize_identity_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._@+-]+", "-", value.strip())
    cleaned = cleaned.strip(".-_+")
    return cleaned[:128]
