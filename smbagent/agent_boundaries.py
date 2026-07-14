"""Agent isolation boundaries for the five-stage pipeline and runtime execution.

External integration side effects (email, calendar, CRM, deploy) must never call
transports directly. They must pass ``execution_guard.guard_proposed_external_action``
(schema → semantic scan → governance authz) first.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .apple_container import (
    subprocess_isolation_enabled,
    subprocess_isolation_is_legacy_macos_sandbox,
    subprocess_isolation_is_official_apple_container,
    subprocess_isolation_provider_label,
)
from .artifact_freshness import artifact_path_strings
from .config import Config
from .fleet_state import publish_fleet_artifact_freshness
from .workspace import InvalidCustomerIdError, Workspace


@dataclass(frozen=True)
class AgentBoundary:
    stage: str
    agent: str
    allowed_inputs: tuple[str, ...]
    allowed_shared_rules: tuple[str, ...]
    writes: tuple[str, ...]
    forbidden_private_channels: tuple[str, ...]


@dataclass(frozen=True)
class AgentCommunicationLane:
    lane: str
    producer: str
    consumer: str
    public_only: bool
    allowed_artifacts: tuple[str, ...]
    forbidden_payloads: tuple[str, ...]


@dataclass(frozen=True)
class AgentIsolationStatus:
    schema_version: int
    generated_at: str
    posture: str
    coding_surface: str
    validation_surface: str
    agents_separate: bool
    subprocess_isolation_enabled: bool
    subprocess_isolation_provider: str
    subprocess_isolation_label: str
    subprocess_isolation_official_apple_container: bool
    public_shared_rule_count: int
    communication_lane_count: int
    forbidden_channel_count: int
    warnings: list[str]
    allowed_public_artifacts: list[str]
    communication_lanes: list[AgentCommunicationLane]


@dataclass(frozen=True)
class CustomerIsolationSummary:
    customer_id: str
    posture: str
    has_plan_harness_manifest: bool
    has_validation_snapshot_manifest: bool
    recent_workspace_conflict_count: int
    visible_public_artifact_count: int


PUBLIC_SHARED_RULES = (
    "tier caps",
    "standardized deliverable schema",
    "Pydantic artifact schemas",
    "company context schema",
    "governance and HITL rules",
    "security and no-secret rules",
)

FORBIDDEN_PRIVATE_CHANNELS = (
    "hidden chain-of-thought",
    "private model reasoning",
    "agent private memory",
    "vendor CLI session memory",
    "raw coding logs as validation input",
    "private bridge summaries",
    "prior customer memory",
    "hidden reasoning",
    "raw logs",
)

EXTERNAL_EXECUTION_GUARD_RULES = (
    "all external side effects must pass execution_guard before transport I/O",
    "layer 1: Pydantic ProposedExternalAction schema validation",
    "layer 2: safety.review_proposed_action semantic scan",
    "layer 3: governance.enforce_action with HITL approval when required",
)

EXTERNAL_EXECUTION_BOUNDARY = AgentBoundary(
    stage="runtime",
    agent="ExternalIntegration",
    allowed_inputs=("ProposedExternalAction payload", "ExecutionGuardContext"),
    allowed_shared_rules=EXTERNAL_EXECUTION_GUARD_RULES,
    writes=("transport side effects only after guard_proposed_external_action passes",),
    forbidden_private_channels=FORBIDDEN_PRIVATE_CHANNELS
    + ("direct transport call without execution_guard",),
)

PUBLIC_SHARED_ARTIFACTS = (
    "qualification.json",
    "requirements.json",
    "company_context.json",
    "CONTEXT.md",
    "plan.md",
    "tasks.json",
    "plan_harness_manifest.json",
    "runs/round-N/harness_manifest.json",
    "runs/round-N/feedback.md",
    "runs/round-N/verdict.json",
    "runs/round-N/validation_snapshot/snapshot_manifest.json",
)

AGENT_BOUNDARIES = (
    AgentBoundary(
        stage="1/5",
        agent="Qualify",
        allowed_inputs=("customer brief",),
        allowed_shared_rules=("qualification rubric", "tier caps", "SMB fit policy"),
        writes=("qualification.json",),
        forbidden_private_channels=FORBIDDEN_PRIVATE_CHANNELS,
    ),
    AgentBoundary(
        stage="2/5",
        agent="Negotiation",
        allowed_inputs=("qualification tier", "current customer voice/text turns"),
        allowed_shared_rules=("tier caps", "standardized deliverable schema", "company context schema"),
        writes=("requirements.json", "transcript.txt", "company_context.json", "CONTEXT.md"),
        forbidden_private_channels=FORBIDDEN_PRIVATE_CHANNELS,
    ),
    AgentBoundary(
        stage="3/5",
        agent="Plan",
        allowed_inputs=("requirements.json", "company_context.json", "transcript.txt"),
        allowed_shared_rules=PUBLIC_SHARED_RULES,
        writes=("plan.md", "tasks.json", "plan_harness_manifest.json"),
        forbidden_private_channels=FORBIDDEN_PRIVATE_CHANNELS,
    ),
    AgentBoundary(
        stage="4/5",
        agent="Coding",
        allowed_inputs=(
            "requirements.json",
            "company_context.json",
            "CONTEXT.md",
            "plan.md",
            "tasks.json",
            "prior round validation feedback, when present",
        ),
        allowed_shared_rules=PUBLIC_SHARED_RULES,
        writes=("code/", "runs/round-N/coding.log", "runs/round-N/harness_manifest.json"),
        forbidden_private_channels=FORBIDDEN_PRIVATE_CHANNELS,
    ),
    AgentBoundary(
        stage="5/5",
        agent="Validation",
        allowed_inputs=(
            "validation_snapshot/requirements.json",
            "validation_snapshot/company_context.json",
            "validation_snapshot/public_plan.md",
            "validation_snapshot/public_tasks.json",
            "validation_snapshot/code/",
        ),
        allowed_shared_rules=PUBLIC_SHARED_RULES,
        writes=(
            "runs/round-N/verdict.json",
            "runs/round-N/feedback.md",
            "runs/round-N/validation_snapshot/snapshot_manifest.json",
        ),
        forbidden_private_channels=FORBIDDEN_PRIVATE_CHANNELS,
    ),
)

COMMUNICATION_LANES = (
    AgentCommunicationLane(
        lane="qualify_to_negotiation",
        producer="Qualify",
        consumer="Negotiation",
        public_only=True,
        allowed_artifacts=("qualification.json",),
        forbidden_payloads=FORBIDDEN_PRIVATE_CHANNELS,
    ),
    AgentCommunicationLane(
        lane="negotiation_to_plan",
        producer="Negotiation",
        consumer="Plan",
        public_only=True,
        allowed_artifacts=("requirements.json", "company_context.json", "CONTEXT.md", "transcript.txt"),
        forbidden_payloads=FORBIDDEN_PRIVATE_CHANNELS,
    ),
    AgentCommunicationLane(
        lane="plan_to_coding",
        producer="Plan",
        consumer="Coding",
        public_only=True,
        allowed_artifacts=("plan.md", "tasks.json", "plan_harness_manifest.json"),
        forbidden_payloads=FORBIDDEN_PRIVATE_CHANNELS,
    ),
    AgentCommunicationLane(
        lane="coding_to_validation",
        producer="Coding",
        consumer="Validation",
        public_only=True,
        allowed_artifacts=(
            "runs/round-N/validation_snapshot/requirements.json",
            "runs/round-N/validation_snapshot/company_context.json",
            "runs/round-N/validation_snapshot/public_plan.md",
            "runs/round-N/validation_snapshot/public_tasks.json",
            "runs/round-N/validation_snapshot/code/",
            "runs/round-N/validation_snapshot/snapshot_manifest.json",
        ),
        forbidden_payloads=FORBIDDEN_PRIVATE_CHANNELS,
    ),
    AgentCommunicationLane(
        lane="validation_to_coding",
        producer="Validation",
        consumer="Coding",
        public_only=True,
        allowed_artifacts=("runs/round-N/feedback.md", "runs/round-N/verdict.json"),
        forbidden_payloads=FORBIDDEN_PRIVATE_CHANNELS,
    ),
)


def validate_external_execution_guard_contract() -> list[str]:
    errors: list[str] = []
    if not EXTERNAL_EXECUTION_GUARD_RULES:
        errors.append("external execution guard rules must be declared")
    forbidden = " ".join(EXTERNAL_EXECUTION_BOUNDARY.forbidden_private_channels).lower()
    if "execution_guard" not in forbidden:
        errors.append("external execution boundary must forbid bypassing execution_guard")
    shared = " ".join(EXTERNAL_EXECUTION_BOUNDARY.allowed_shared_rules).lower()
    if "execution_guard" not in shared:
        errors.append("external execution boundary must declare execution_guard layers")
    return errors


def validate_agent_boundary_contract() -> list[str]:
    errors: list[str] = []
    errors.extend(validate_external_execution_guard_contract())
    agents = [b.agent for b in AGENT_BOUNDARIES]
    if agents != ["Qualify", "Negotiation", "Plan", "Coding", "Validation"]:
        errors.append("agent boundary contract must declare the five pipeline agents in order")
    for boundary in AGENT_BOUNDARIES:
        if not boundary.allowed_inputs:
            errors.append(f"{boundary.agent} has no declared allowed inputs")
        if not boundary.allowed_shared_rules:
            errors.append(f"{boundary.agent} has no declared shared rules")
        if not boundary.writes:
            errors.append(f"{boundary.agent} has no declared writes")
        forbidden = " ".join(boundary.forbidden_private_channels).lower()
        for required in ("memory", "reasoning", "logs"):
            if required not in forbidden:
                errors.append(f"{boundary.agent} forbidden channels must include {required}")
    validation = next((b for b in AGENT_BOUNDARIES if b.agent == "Validation"), None)
    if validation is None or not all("validation_snapshot/" in item for item in validation.allowed_inputs):
        errors.append("validation must read only from validation_snapshot inputs")
    if not any(
        any("feedback.md" in artifact for artifact in lane.allowed_artifacts)
        for lane in COMMUNICATION_LANES
        if lane.producer == "Validation"
    ):
        errors.append("validation must communicate back through structured public feedback only")
    return errors


def build_agent_isolation_status(config: Config) -> AgentIsolationStatus:
    coding_surface = " ".join(config.coding_cmd) if config.coding_cmd else "none"
    validation_surface = (
        " ".join(config.validation_cmd)
        if config.uses_validation_cli() and config.validation_cmd
        else f"api:{config.validation_model}"
    )
    coding_head = Path(config.coding_cmd[0]).name if config.coding_cmd else ""
    validation_head = (
        Path(config.validation_cmd[0]).name
        if config.uses_validation_cli() and config.validation_cmd
        else "api"
    )
    agents_separate = bool(coding_head) and bool(validation_head) and coding_head != validation_head
    isolation_provider = config.subprocess_isolation
    isolation_enabled = subprocess_isolation_enabled(isolation_provider)
    isolation_label = subprocess_isolation_provider_label(isolation_provider)
    official_apple_container = subprocess_isolation_is_official_apple_container(isolation_provider)
    warnings: list[str] = []
    if not isolation_enabled:
        warnings.append("subprocess isolation is not enabled for coding/validation separation")
    elif subprocess_isolation_is_legacy_macos_sandbox(isolation_provider):
        warnings.append(
            "prefer SMBAGENT_SUBPROCESS_ISOLATION=apple-container on Mac mini; macos-sandbox is legacy-only"
        )
    elif not official_apple_container and "linux" not in isolation_label.lower():
        warnings.append(f"unrecognized subprocess isolation provider: {isolation_provider}")
    if not agents_separate:
        warnings.append("coding and validation surfaces are not clearly separated")
    if config.slm_training_export_allow_raw_logs:
        warnings.append("SLM training export currently allows raw logs")
    if config.slm_training_export_allow_hidden_reasoning:
        warnings.append("SLM training export currently allows hidden reasoning")
    return AgentIsolationStatus(
        schema_version=1,
        generated_at=_generated_at(),
        posture="public-artifact-only communication between separated agents",
        coding_surface=coding_surface,
        validation_surface=validation_surface,
        agents_separate=agents_separate,
        subprocess_isolation_enabled=isolation_enabled,
        subprocess_isolation_provider=isolation_provider,
        subprocess_isolation_label=isolation_label,
        subprocess_isolation_official_apple_container=official_apple_container,
        public_shared_rule_count=len(PUBLIC_SHARED_RULES),
        communication_lane_count=len(COMMUNICATION_LANES),
        forbidden_channel_count=len(FORBIDDEN_PRIVATE_CHANNELS),
        warnings=warnings,
        allowed_public_artifacts=list(PUBLIC_SHARED_ARTIFACTS),
        communication_lanes=list(COMMUNICATION_LANES),
    )


def write_agent_isolation_status(config: Config, out_dir: Path | None = None) -> Path:
    status = build_agent_isolation_status(config)
    target_dir = out_dir or (config.root / "ops")
    target_dir.mkdir(parents=True, exist_ok=True)
    out = target_dir / "agent_isolation_status.json"
    out.write_text(json.dumps(asdict(status), ensure_ascii=False, indent=2), encoding="utf-8")
    pack_paths = write_agent_packs(config, status, target_dir / "agent_packs")
    publish_fleet_artifact_freshness(
        config.root,
        artifact_key="agent_isolation_status",
        artifact_paths=artifact_path_strings([out, *pack_paths], relative_to=config.root),
        writer="agent_boundaries.write",
        detail="agent isolation status and packs generated for maintainer review",
        source_artifacts=["workspaces/", "ops/agent_packs/", "ops/agent_isolation_status.json"],
    )
    return out


def write_agent_packs(
    config: Config,
    status: AgentIsolationStatus | None,
    out_dir: Path,
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    status = status or build_agent_isolation_status(config)
    customers = _collect_customer_isolation_summaries(config)
    payloads = {
        "runtime": {
            "schema_version": status.schema_version,
            "generated_at": status.generated_at,
            "pack_type": "agent_runtime",
            "payload": {
                "posture": status.posture,
                "coding_surface": status.coding_surface,
                "validation_surface": status.validation_surface,
                "agents_separate": status.agents_separate,
                "subprocess_isolation_enabled": status.subprocess_isolation_enabled,
                "external_execution_guard_rules": list(EXTERNAL_EXECUTION_GUARD_RULES),
                "warnings": status.warnings,
            },
        },
        "lanes": {
            "schema_version": status.schema_version,
            "generated_at": status.generated_at,
            "pack_type": "agent_lanes",
            "payload": {
                "public_shared_rule_count": status.public_shared_rule_count,
                "communication_lane_count": status.communication_lane_count,
                "forbidden_channel_count": status.forbidden_channel_count,
                "allowed_public_artifacts": status.allowed_public_artifacts,
                "communication_lanes": [asdict(item) for item in status.communication_lanes],
            },
        },
        "customers": {
            "schema_version": status.schema_version,
            "generated_at": status.generated_at,
            "pack_type": "agent_customer_isolation",
            "payload": {
                "customer_count": len(customers),
                "customers": [asdict(item) for item in customers],
            },
        },
    }
    written: list[Path] = []
    for name, payload in payloads.items():
        path = out_dir / f"{name}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(path)
    return written


def _collect_customer_isolation_summaries(config: Config) -> list[CustomerIsolationSummary]:
    summaries: list[CustomerIsolationSummary] = []
    if not config.workspaces_dir.exists():
        return summaries
    for child in sorted(config.workspaces_dir.iterdir()):
        if not child.is_dir():
            continue
        try:
            workspace = Workspace(child.name, config.workspaces_dir)
        except InvalidCustomerIdError:
            continue
        plan_manifest = workspace.path / "plan_harness_manifest.json"
        validation_snapshots = sorted(
            workspace.path.glob("runs/round-*/validation_snapshot/snapshot_manifest.json")
        )
        public_artifact_count = sum(
            1
            for rel_path in (
                "qualification.json",
                "requirements.json",
                "company_context.json",
                "CONTEXT.md",
                "plan.md",
                "tasks.json",
            )
            if (workspace.path / rel_path).exists()
        )
        conflict_count = 0
        if workspace.workspace_state_conflicts_path.exists():
            conflict_count = len(
                workspace.workspace_state_conflicts_path.read_text(encoding="utf-8").splitlines()
            )
        posture = "growing"
        if plan_manifest.exists() and validation_snapshots:
            posture = "observable"
        if plan_manifest.exists() and validation_snapshots and conflict_count == 0:
            posture = "strong"
        summaries.append(
            CustomerIsolationSummary(
                customer_id=workspace.customer_id,
                posture=posture,
                has_plan_harness_manifest=plan_manifest.exists(),
                has_validation_snapshot_manifest=bool(validation_snapshots),
                recent_workspace_conflict_count=conflict_count,
                visible_public_artifact_count=public_artifact_count,
            )
        )
    return summaries


def _generated_at() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


__all__ = [
    "AGENT_BOUNDARIES",
    "COMMUNICATION_LANES",
    "EXTERNAL_EXECUTION_BOUNDARY",
    "EXTERNAL_EXECUTION_GUARD_RULES",
    "FORBIDDEN_PRIVATE_CHANNELS",
    "PUBLIC_SHARED_ARTIFACTS",
    "PUBLIC_SHARED_RULES",
    "AgentBoundary",
    "AgentCommunicationLane",
    "CustomerIsolationSummary",
    "AgentIsolationStatus",
    "build_agent_isolation_status",
    "validate_agent_boundary_contract",
    "validate_external_execution_guard_contract",
    "write_agent_packs",
    "write_agent_isolation_status",
]
