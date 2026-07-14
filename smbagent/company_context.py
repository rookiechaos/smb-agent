from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from .types import CompanyContext


@dataclass
class CompanyContextRefresh:
    ts: str
    note: str
    changed_by: str | None
    update_kind: str
    patch: dict


class CompanyContextPatch(CompanyContext):
    """Partial update form for company context."""

    mission: str | None = None
    vision: str | None = None
    values: list[str] | None = None
    current_strategy: list[str] | None = None
    current_priorities: list[str] | None = None
    decision_style: str | None = None
    risk_tolerance: str | None = None


def apply_company_context_patch(
    current: CompanyContext,
    patch: CompanyContextPatch,
) -> CompanyContext:
    data = patch.model_dump(exclude_none=True)
    return current.model_copy(update=data)


def append_company_context_refresh(
    log_path: Path,
    *,
    note: str,
    patch: CompanyContextPatch,
    changed_by: str | None = "cli",
    update_kind: str = "operator_note",
) -> CompanyContextRefresh:
    event = CompanyContextRefresh(
        ts=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        note=note[:1000],
        changed_by=changed_by,
        update_kind=update_kind,
        patch=patch.model_dump(exclude_none=True),
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
    return event


def read_company_context_refreshes(log_path: Path) -> list[CompanyContextRefresh]:
    if not log_path.exists():
        return []
    events: list[CompanyContextRefresh] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
            if "update_kind" not in raw:
                raw["update_kind"] = "legacy"
            events.append(CompanyContextRefresh(**raw))
        except (json.JSONDecodeError, TypeError):
            continue
    return events


def latest_context_refresh_at(snapshot_path: Path, updates_path: Path) -> datetime | None:
    times: list[datetime] = []
    if snapshot_path.exists():
        try:
            times.append(datetime.fromtimestamp(snapshot_path.stat().st_mtime, tz=UTC))
        except OSError:
            pass
    for ev in read_company_context_refreshes(updates_path):
        try:
            times.append(datetime.strptime(ev.ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC))
        except ValueError:
            continue
    return max(times) if times else None


def context_age_days(snapshot_path: Path, updates_path: Path) -> int | None:
    latest = latest_context_refresh_at(snapshot_path, updates_path)
    if latest is None:
        return None
    delta = datetime.now(UTC) - latest
    return max(0, delta.days)


def is_context_stale(snapshot_path: Path, updates_path: Path, *, warn_days: int) -> bool:
    age = context_age_days(snapshot_path, updates_path)
    return age is None or age >= warn_days


def context_quality_notes(context: CompanyContext) -> list[str]:
    notes: list[str] = []
    if not context.mission.strip():
        notes.append("missing mission")
    if not context.vision.strip():
        notes.append("missing vision")
    if not context.values:
        notes.append("missing values")
    if not context.current_strategy:
        notes.append("missing current strategy")
    if not context.current_priorities:
        notes.append("missing current priorities")
    if not context.decision_style.strip():
        notes.append("missing decision style")
    if not context.risk_tolerance.strip():
        notes.append("missing risk tolerance")
    return notes


def render_context_md(context: CompanyContext) -> str:
    def list_block(items: list[str]) -> str:
        if not items:
            return "- TODO\n"
        return "".join(f"- {item}\n" for item in items)

    return (
        "# Company Context\n\n"
        "This file is the operator-facing company context snapshot used by smbagent.\n"
        "Update it through `smbagent context-update` so the JSON snapshot and update log stay aligned.\n\n"
        "## Durable Principles\n\n"
        "### Mission\n\n"
        f"{context.mission or 'TODO'}\n\n"
        "### Vision\n\n"
        f"{context.vision or 'TODO'}\n\n"
        "### Values\n\n"
        f"{list_block(context.values)}\n"
        "### Decision Style\n\n"
        f"{context.decision_style or 'TODO'}\n\n"
        "### Risk Tolerance\n\n"
        f"{context.risk_tolerance or 'TODO'}\n\n"
        "## Current Operating Context\n\n"
        "### Current Strategy\n\n"
        f"{list_block(context.current_strategy)}\n"
        "### Current Priorities\n\n"
        f"{list_block(context.current_priorities)}"
    )
