from __future__ import annotations

import json
import platform
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from smbagent.slm.completion import build_local_slm_completion_plan

from . import __version__
from .apple_container import (
    subprocess_isolation_is_official_apple_container,
    subprocess_isolation_provider_label,
)
from .artifact_freshness import artifact_path_strings, publish_workspace_artifact_freshness
from .coding_benchmarks import coding_benchmark_policy
from .config import Config
from .customer_readiness import (
    load_customer_legal_review,
    load_japan_trust_launch_review,
    sensitive_workflow_categories,
)
from .launch_readiness import summarize_deployment_readiness, summarize_security_readiness
from .onboarding_abuse import onboarding_abuse_controls_detail, onboarding_abuse_controls_ready
from .release_records import ensure_release_record_dir, write_release_record_manifest
from .remote_acceptance import remote_smoke_evidence_paths, remote_smoke_plan_path
from .secret_storage import managed_secret_storage_supported
from .workspace import Workspace


@dataclass(frozen=True)
class CommercialReadinessGate:
    key: str
    title: str
    status: str
    detail: str
    blocking: bool = False
    remote_only: bool = False


@dataclass(frozen=True)
class CommercialReadinessReport:
    generated_at: str
    posture: str
    not_a_zero_risk_guarantee: bool
    intentional_boundaries: list[CommercialReadinessGate]
    deployment_pillars: list[dict[str, object]]
    security_domains: list[dict[str, object]]
    remaining_gates: list[CommercialReadinessGate]


@dataclass(frozen=True)
class LaunchNotesSnapshot:
    generated_at: str
    operator: str
    customer_id: str | None
    smbagent_version: str
    python_version: str
    platform: str
    coding_cmd: list[str]
    validation_backend: str
    validation_cmd: list[str]
    plan_model: str
    validation_model: str
    subprocess_isolation: str
    monitor_exposure: str
    serve_host: str
    remote_access_channel: str
    allow_lan_monitor_fallback: bool
    maintenance_access_channel: str
    sensitive_mode: bool
    local_only_mode: bool
    secret_storage_mode: str
    backup_encryption_mode: str
    voice_cloud_redaction_enabled: bool
    consent_record_required: bool
    slm_completion_enabled: bool
    filevault_confirmed: bool
    local_workspace_confirmed: bool
    no_synced_folders_confirmed: bool
    backup_restore_drill_confirmed: bool
    launch_acceptance_confirmed: bool
    benchmark_policy_version: str
    readiness_posture: str
    deferred_items: list[str]


def build_commercial_readiness_report(config: Config) -> CommercialReadinessReport:
    deployment = summarize_deployment_readiness(config)
    security = summarize_security_readiness(config)
    return CommercialReadinessReport(
        generated_at=_iso_z(),
        posture="security-hardened and locally checkable",
        not_a_zero_risk_guarantee=True,
        intentional_boundaries=_intentional_boundaries(config),
        deployment_pillars=[
            {
                "key": pillar.key,
                "title": pillar.title,
                "passed": pillar.passed,
                "failed_local": pillar.failed_local,
                "remote_only": pillar.remote_only,
            }
            for pillar in deployment
        ],
        security_domains=[
            {
                "key": domain.key,
                "title": domain.title,
                "passed": domain.passed,
                "failed_local": domain.failed_local,
                "remote_only": domain.remote_only,
            }
            for domain in security
        ],
        remaining_gates=_remaining_gates(config),
    )


def build_launch_notes_snapshot(
    config: Config, *, operator: str, customer_id: str | None = None
) -> LaunchNotesSnapshot:
    policy = coding_benchmark_policy()
    return LaunchNotesSnapshot(
        generated_at=_iso_z(),
        operator=operator,
        customer_id=customer_id,
        smbagent_version=__version__,
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        coding_cmd=list(config.coding_cmd),
        validation_backend=config.validation_backend,
        validation_cmd=list(config.validation_cmd),
        plan_model=config.plan_model,
        validation_model=config.validation_model,
        subprocess_isolation=config.subprocess_isolation,
        monitor_exposure=config.monitor_exposure,
        serve_host=config.serve_host,
        remote_access_channel=config.remote_access_channel,
        allow_lan_monitor_fallback=config.allow_lan_monitor_fallback,
        maintenance_access_channel=config.maintenance_access_channel,
        sensitive_mode=config.sensitive_mode,
        local_only_mode=config.local_only_mode,
        secret_storage_mode=config.secret_storage_mode,
        backup_encryption_mode=config.backup_encryption_mode,
        voice_cloud_redaction_enabled=config.voice_cloud_redaction_enabled,
        consent_record_required=config.consent_record_required,
        slm_completion_enabled=config.slm_completion_enabled,
        filevault_confirmed=config.filevault_confirmed,
        local_workspace_confirmed=config.local_workspace_confirmed,
        no_synced_folders_confirmed=config.no_synced_folders_confirmed,
        backup_restore_drill_confirmed=config.backup_restore_drill_confirmed,
        launch_acceptance_confirmed=config.launch_acceptance_confirmed,
        benchmark_policy_version=str(policy["version"]),
        readiness_posture="security-hardened and locally checkable",
        deferred_items=[
            "real remote API/CLI dry-run still required",
            "customer-specific legal review still required for sensitive deployments",
            "careful operator practice still required",
        ],
    )


def write_launch_notes_snapshot(
    config: Config, *, operator: str, customer_id: str | None = None, out_dir: Path | None = None
) -> tuple[Path, Path]:
    snapshot = build_launch_notes_snapshot(config, operator=operator, customer_id=customer_id)
    target_dir = out_dir or (config.root / "ops" / "launch_notes")
    target_dir.mkdir(parents=True, exist_ok=True)
    slug = customer_id or "global"
    json_body = json.dumps(asdict(snapshot), ensure_ascii=False, indent=2)
    md_body = render_launch_notes_md(snapshot)
    json_path = target_dir / f"{slug}.launch_notes.json"
    md_path = target_dir / f"{slug}.launch_notes.md"
    json_path.write_text(json_body, encoding="utf-8")
    md_path.write_text(md_body, encoding="utf-8")
    release_dir = ensure_release_record_dir(
        config.root,
        generated_at=snapshot.generated_at,
        smbagent_version=snapshot.smbagent_version,
    )
    release_launch_dir = release_dir / "launch_notes"
    release_launch_dir.mkdir(parents=True, exist_ok=True)
    archived_json = release_launch_dir / f"{slug}.launch_notes.json"
    archived_md = release_launch_dir / f"{slug}.launch_notes.md"
    archived_json.write_text(json_body, encoding="utf-8")
    archived_md.write_text(md_body, encoding="utf-8")
    manifest_path = write_release_record_manifest(
        config.root,
        generated_at=snapshot.generated_at,
        smbagent_version=snapshot.smbagent_version,
        artifact_key="launch_notes",
        artifact_title="Launch notes snapshot",
        artifact_paths=[archived_json, archived_md],
        note=f"customer_id={slug}",
    )
    if customer_id:
        workspace = Workspace(customer_id, config.workspaces_dir)
        publish_workspace_artifact_freshness(
            workspace,
            artifact_key="launch_notes",
            artifact_paths=artifact_path_strings(
                [json_path, md_path, archived_json, archived_md, manifest_path], relative_to=config.root
            ),
            writer="commercial_readiness.write_launch_notes_snapshot",
            detail="launch notes snapshot generated for customer deployment record and archived under ops/release_reviews/ with release_record_manifest.json",
            source_sections=[],
        )
    return json_path, md_path


def render_commercial_readiness_md(report: CommercialReadinessReport) -> str:
    lines = [
        "# Commercial Readiness",
        "",
        f"- generated_at: {report.generated_at}",
        f"- posture: {report.posture}",
        "- zero_risk_guarantee: false",
        "",
        "## Intentional boundaries",
        "",
    ]
    for gate in report.intentional_boundaries:
        lines.append(f"- [{gate.status}] {gate.title}: {gate.detail}")
    lines.extend(["", "## Remaining gates", ""])
    for gate in report.remaining_gates:
        suffix = " (remote)" if gate.remote_only else ""
        lines.append(f"- [{gate.status}] {gate.title}{suffix}: {gate.detail}")
    return "\n".join(lines)


def render_launch_notes_md(snapshot: LaunchNotesSnapshot) -> str:
    lines = [
        "# Launch Notes",
        "",
        f"- generated_at: {snapshot.generated_at}",
        f"- operator: {snapshot.operator}",
        f"- customer_id: {snapshot.customer_id or '<global>'}",
        f"- smbagent_version: {snapshot.smbagent_version}",
        f"- python_version: {snapshot.python_version}",
        f"- platform: {snapshot.platform}",
        f"- plan_model: {snapshot.plan_model}",
        f"- validation_model: {snapshot.validation_model}",
        f"- subprocess_isolation: {snapshot.subprocess_isolation}",
        f"- monitor_exposure: {snapshot.monitor_exposure}",
        f"- remote_access_channel: {snapshot.remote_access_channel}",
        f"- allow_lan_monitor_fallback: {str(snapshot.allow_lan_monitor_fallback).lower()}",
        f"- maintenance_access_channel: {snapshot.maintenance_access_channel}",
        f"- secret_storage_mode: {snapshot.secret_storage_mode}",
        f"- backup_encryption_mode: {snapshot.backup_encryption_mode}",
        f"- voice_cloud_redaction_enabled: {str(snapshot.voice_cloud_redaction_enabled).lower()}",
        f"- consent_record_required: {str(snapshot.consent_record_required).lower()}",
        f"- slm_completion_enabled: {str(snapshot.slm_completion_enabled).lower()}",
        f"- benchmark_policy_version: {snapshot.benchmark_policy_version}",
        "",
        "## Operator attestations",
        "",
        f"- filevault_confirmed: {str(snapshot.filevault_confirmed).lower()}",
        f"- local_workspace_confirmed: {str(snapshot.local_workspace_confirmed).lower()}",
        f"- no_synced_folders_confirmed: {str(snapshot.no_synced_folders_confirmed).lower()}",
        f"- backup_restore_drill_confirmed: {str(snapshot.backup_restore_drill_confirmed).lower()}",
        f"- launch_acceptance_confirmed: {str(snapshot.launch_acceptance_confirmed).lower()}",
        "",
        "## Deferred items",
        "",
    ]
    for item in snapshot.deferred_items:
        lines.append(f"- {item}")
    return "\n".join(lines)


def _intentional_boundaries(config: Config) -> list[CommercialReadinessGate]:
    return [
        CommercialReadinessGate(
            key="no_automatic_specialist_training",
            title="No automatic specialist training",
            status="ready" if not config.slm_auto_train_enabled else "gap",
            detail="automatic SLM training remains disabled by default",
            blocking=True,
        ),
        CommercialReadinessGate(
            key="no_auto_promotion_into_active_routing",
            title="No auto-promotion into active routing",
            status="ready" if not config.slm_auto_promote_enabled else "gap",
            detail="promotion into active routing remains human-gated",
            blocking=True,
        ),
        CommercialReadinessGate(
            key="no_hidden_autonomy_path",
            title="No hidden autonomy path that bypasses governance",
            status="ready"
            if (
                config.external_execution_policy.lower() == "hitl"
                and not config.allow_unattended_external_writes
            )
            else "gap",
            detail=f"external_execution_policy={config.external_execution_policy}, allow_unattended_external_writes={config.allow_unattended_external_writes}",
            blocking=True,
        ),
        CommercialReadinessGate(
            key="no_raw_logs_or_hidden_reasoning_in_training_export",
            title="No customer-raw logs or hidden reasoning in training export",
            status="ready"
            if (
                not config.slm_training_export_allow_raw_logs
                and not config.slm_training_export_allow_hidden_reasoning
            )
            else "gap",
            detail="specialist training export remains public-only and reasoning-free",
            blocking=True,
        ),
    ]


def _remaining_gates(config: Config) -> list[CommercialReadinessGate]:
    root = config.root
    return [
        CommercialReadinessGate(
            key="full_synthetic_dry_run_real_apis",
            title="Full synthetic dry-run against real APIs/CLIs",
            status=_synthetic_dry_run_status(config),
            detail=_synthetic_dry_run_detail(config),
            remote_only=True,
        ),
        CommercialReadinessGate(
            key="apple_official_container_runtime",
            title="Apple official container runtime on the Mac mini",
            status="ready"
            if subprocess_isolation_is_official_apple_container(config.subprocess_isolation)
            else "gap",
            detail=(
                f"SMBAGENT_SUBPROCESS_ISOLATION={config.subprocess_isolation} "
                f"({subprocess_isolation_provider_label(config.subprocess_isolation)})"
            ),
            blocking=False,
        ),
        CommercialReadinessGate(
            key="hardened_subprocess_isolation_beyond_macos",
            title="Hardened subprocess isolation beyond the current macOS-first posture",
            status="ready" if config.subprocess_isolation in {"apple-container", "linux-bwrap"} else "gap",
            detail=(
                "apple-container is the Mac mini default and linux-bwrap is available for non-macOS hardened execution"
                if config.subprocess_isolation in {"apple-container", "linux-bwrap"}
                else f"current subprocess isolation is {config.subprocess_isolation}; prefer apple-container on Mac or linux-bwrap on Linux"
            ),
            blocking=False,
        ),
        CommercialReadinessGate(
            key="customer_specific_legal_review",
            title="Customer-specific legal/contract review",
            status="ready" if _customer_specific_legal_review_ready(config) else "gap",
            detail=_customer_specific_legal_review_detail(config),
            blocking=False,
        ),
        CommercialReadinessGate(
            key="japan_smb_trust_launch_reviews",
            title="Japan SMB trust-readiness launch notes completed per real customer",
            status="ready" if _japan_trust_launch_reviews_ready(config) else "gap",
            detail=_japan_trust_launch_reviews_detail(config),
            blocking=False,
        ),
        CommercialReadinessGate(
            key="managed_secret_storage",
            title="Managed secret storage for SaaS integration credentials",
            status="ready" if _managed_secret_storage_ready(config) else "gap",
            detail=_managed_secret_storage_detail(config),
            blocking=False,
        ),
        CommercialReadinessGate(
            key="production_grade_onboarding_abuse_controls",
            title="Production-grade onboarding abuse controls",
            status="ready" if onboarding_abuse_controls_ready(config) else "gap",
            detail=onboarding_abuse_controls_detail(config),
            blocking=False,
        ),
        CommercialReadinessGate(
            key="ci_lint_and_dependency_audit",
            title="Lint and dependency/security gates in CI",
            status="ready" if _ci_quality_gates_ready(root) else "gap",
            detail=_ci_quality_gates_detail(root),
            blocking=False,
        ),
        CommercialReadinessGate(
            key="rollback_recovery_documentation",
            title="Rollback/recovery documentation",
            status="ready"
            if (root / "RUNBOOK.md").exists() and (root / "DEPLOYMENT_READINESS.md").exists()
            else "gap",
            detail="backup/restore and recovery docs are expected in root docs",
            blocking=False,
        ),
        CommercialReadinessGate(
            key="ci_backed_trustworthiness_adversarial_suite",
            title="CI-backed trustworthiness evaluation with adversarial fixtures",
            status="ready" if _ci_trust_regression_ready(root) else "gap",
            detail=_ci_trust_regression_detail(root),
            blocking=False,
        ),
        CommercialReadinessGate(
            key="remote_external_benchmark_runner",
            title="Remote-machine external benchmark runner",
            status=_remote_benchmark_runner_status(config),
            detail=_remote_benchmark_runner_detail(config),
            remote_only=True,
        ),
        CommercialReadinessGate(
            key="voice_sensitive_mode_hardening",
            title="Voice / sensitive-mode hardening",
            status="ready" if _voice_sensitive_hardening_ready(config) else "gap",
            detail=_voice_sensitive_hardening_detail(config),
            blocking=False,
        ),
        CommercialReadinessGate(
            key="local_slm_completion_governed",
            title="Local SLM completion on the real machine without weakened governance",
            status="ready" if build_local_slm_completion_plan(config).governance_preserved else "gap",
            detail=_local_slm_completion_detail(config),
            blocking=False,
        ),
    ]


def _customer_specific_legal_review_ready(config: Config) -> bool:
    return not _sensitive_workspace_review_gaps(config, kind="legal")


def _customer_specific_legal_review_detail(config: Config) -> str:
    gaps = _sensitive_workspace_review_gaps(config, kind="legal")
    if not gaps:
        return "all detected sensitive workspaces have approved customer legal/contract review records"
    return "missing or incomplete legal review for: " + ", ".join(gaps)


def _japan_trust_launch_reviews_ready(config: Config) -> bool:
    return not _sensitive_workspace_review_gaps(config, kind="trust")


def _japan_trust_launch_reviews_detail(config: Config) -> str:
    gaps = _sensitive_workspace_review_gaps(config, kind="trust")
    if not gaps:
        return "all detected sensitive workspaces have approved Japan trust launch review records and required notices"
    return "missing or incomplete Japan trust review for: " + ", ".join(gaps)


def _sensitive_workspace_review_gaps(config: Config, *, kind: str) -> list[str]:
    gaps: list[str] = []
    if not config.workspaces_dir.exists():
        return gaps
    for child in sorted(config.workspaces_dir.iterdir()):
        if not child.is_dir():
            continue
        try:
            workspace = Workspace(child.name, config.workspaces_dir)
        except Exception:
            continue
        workflows = sensitive_workflow_categories(workspace)
        if not workflows:
            continue
        if kind == "legal":
            record = load_customer_legal_review(workspace)
            if record is None or not record.approved or not record.external_actions_hitl:
                gaps.append(f"{workspace.customer_id} ({', '.join(workflows)})")
            continue
        record = load_japan_trust_launch_review(workspace)
        if record is None or not record.approved or record.missing_docs:
            gaps.append(f"{workspace.customer_id} ({', '.join(workflows)})")
    return gaps


def _managed_secret_storage_ready(config: Config) -> bool:
    try:
        return managed_secret_storage_supported(config)
    except Exception:
        return False


def _managed_secret_storage_detail(config: Config) -> str:
    try:
        ready = managed_secret_storage_supported(config)
    except Exception as e:  # noqa: BLE001
        return f"secret_storage_mode={config.secret_storage_mode}; managed backend unavailable: {e}"
    return (
        f"secret_storage_mode={config.secret_storage_mode}; managed secret backend available"
        if ready
        else f"secret_storage_mode={config.secret_storage_mode}; switch to macos_keychain/managed on the Mac mini"
    )


def _voice_sensitive_hardening_ready(config: Config) -> bool:
    return bool(
        config.voice_cloud_redaction_enabled
        and config.consent_record_required
        and (config.backup_encryption_mode == "openssl-aes256" or not config.sensitive_mode)
    )


def _ci_quality_gates_ready(root: Path) -> bool:
    workflow = root / ".github" / "workflows" / "ci.yml"
    if not workflow.exists():
        return False
    text = workflow.read_text(encoding="utf-8")
    return all(item in text for item in ("lint-and-audit", "ruff check", "pip-audit"))


def _ci_quality_gates_detail(root: Path) -> str:
    if _ci_quality_gates_ready(root):
        return "ci.yml runs ruff fatal lint and pip-audit before pytest suites"
    return "add lint-and-audit job with ruff check and pip-audit to .github/workflows/ci.yml"


def _ci_trust_regression_ready(root: Path) -> bool:
    required = [
        root / ".github" / "workflows" / "ci.yml",
        root / ".github" / "workflows" / "nightly.yml",
        root / "smbagent" / "trust_regression.py",
        root / "smbagent" / "trust_eval.py",
        root / "tests" / "test_trust_eval.py",
        root / "tests" / "test_bad_llm.py",
        root / "tests" / "test_llm_output_filter_observability.py",
    ]
    if not all(path.exists() for path in required):
        return False
    workflow = root / ".github" / "workflows" / "ci.yml"
    text = workflow.read_text(encoding="utf-8")
    return all(
        item in text
        for item in (
            "trust-regression-contract",
            "PR_SMOKE_SUITE",
            "test-full",
            "upload-artifact@v4",
            "lint-and-audit",
            "repo-hygiene",
            "ruff check",
            "pip-audit",
        )
    )


def _ci_trust_regression_detail(root: Path) -> str:
    workflow = root / ".github" / "workflows" / "ci.yml"
    if not workflow.exists():
        return "missing .github/workflows/ci.yml"
    text = workflow.read_text(encoding="utf-8")
    expected = [
        "trust-regression-contract",
        "PR_SMOKE_SUITE",
        "test-full",
        "upload-artifact@v4",
        "lint-and-audit",
        "repo-hygiene",
        "ruff check",
        "pip-audit",
    ]
    missing = [item for item in expected if item not in text]
    if missing:
        return "workflow missing expected trust regression entries: " + ", ".join(missing)
    return "GitHub Actions runs ruff/pip-audit quality gates, PR smoke on pull requests, full trust regression on main pushes, and nightly full-suite coverage without outside ports"


def _synthetic_dry_run_status(config: Config) -> str:
    if remote_smoke_evidence_paths(config):
        return "ready"
    return "deferred"


def _synthetic_dry_run_detail(config: Config) -> str:
    evidence = remote_smoke_evidence_paths(config)
    if evidence:
        return f"maintainer-recorded remote smoke evidence on file ({evidence[-1].name}); real-machine acceptance remains operator-owned"
    plan_path = remote_smoke_plan_path(config)
    if plan_path.exists():
        return f"plan on file at {plan_path.relative_to(config.root)}; run the steps on the Mac mini and record with smbagent remote-smoke-record"
    return "generate ops/remote_smoke_plan.json with smbagent remote-smoke-plan, then execute on the remote Mac mini"


def _remote_benchmark_runner_status(config: Config) -> str:
    plan_path = config.root / "ops" / "remote_benchmark_plan.json"
    results_dir = config.root / "ops" / "remote_benchmarks"
    if results_dir.exists() and any(results_dir.glob("*.json")):
        return "ready"
    if plan_path.exists():
        return "deferred"
    return "deferred"


def _remote_benchmark_runner_detail(config: Config) -> str:
    results_dir = config.root / "ops" / "remote_benchmarks"
    if results_dir.exists() and any(results_dir.glob("*.json")):
        return "remote benchmark results recorded with cost and latency capture; maintainer review still required"
    plan_path = config.root / "ops" / "remote_benchmark_plan.json"
    if plan_path.exists():
        return "remote benchmark runner plan on file; real execution and evidence capture remain remote-only"
    return (
        "generate ops/remote_benchmark_plan.json with smbagent remote-benchmark-plan before remote execution"
    )


def _voice_sensitive_hardening_detail(config: Config) -> str:
    return f"redaction={str(config.voice_cloud_redaction_enabled).lower()}, backup_encryption_mode={config.backup_encryption_mode}, consent_record_required={str(config.consent_record_required).lower()}"


def _local_slm_completion_detail(config: Config) -> str:
    plan = build_local_slm_completion_plan(config)
    if plan.governance_preserved:
        return "local SLM completion stays localhost-only, bounded-stage, and default-off unless explicitly enabled"
    return "; ".join(plan.blockers)


def _iso_z() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
