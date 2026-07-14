from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from .artifact_freshness import artifact_path_strings, publish_workspace_artifact_freshness
from .workspace import Workspace

SENSITIVE_SIGNAL_KEYWORDS = {
    "gps": ("gps", "位置情報", "行動管理", "移動", "ルート"),
    "employee": ("employee", "従業員", "社員", "スタッフ", "勤怠", "日報", "人事", "評価", "懲戒"),
    "payroll": ("payroll", "salary", "給与", "報酬", "賃金"),
    "clinic": ("clinic", "medical", "patient", "歯科", "クリニック", "患者", "医療", "介護"),
    "voice": ("voice", "audio", "transcribe", "asr", "音声", "録音", "文字起こし"),
}


@dataclass(frozen=True)
class CustomerLegalReviewRecord:
    schema_version: int
    generated_at: str
    customer_id: str
    operator: str
    purpose_of_use: str
    data_categories: list[str]
    sensitive_workflows: list[str]
    third_party_processors: list[str]
    retention_summary: str
    access_summary: str
    external_actions_hitl: bool
    approved: bool
    approval_note: str


@dataclass(frozen=True)
class JapanTrustLaunchReviewRecord:
    schema_version: int
    generated_at: str
    customer_id: str
    operator: str
    workflow_categories: list[str]
    required_docs: list[str]
    present_docs: list[str]
    missing_docs: list[str]
    sensitive_mode: bool
    human_approval_required: bool
    approved: bool
    approval_note: str


def workspace_text(workspace: Workspace) -> str:
    parts: list[str] = []
    for path in [
        workspace.requirements_path,
        workspace.company_context_path,
        workspace.company_context_md_path,
        workspace.transcript_path,
    ]:
        if path.exists():
            try:
                parts.append(path.read_text(encoding="utf-8"))
            except OSError:
                pass
    return "\n".join(parts).lower()


def detect_sensitive_signals(workspace: Workspace) -> set[str]:
    text = workspace_text(workspace)
    return {
        label
        for label, keywords in SENSITIVE_SIGNAL_KEYWORDS.items()
        if any(keyword.lower() in text for keyword in keywords)
    }


def sensitive_workflow_categories(workspace: Workspace) -> list[str]:
    categories = detect_sensitive_signals(workspace)
    return sorted(categories)


def required_japan_trust_docs(workspace: Workspace, categories: list[str] | None = None) -> list[Path]:
    workflows = set(categories or sensitive_workflow_categories(workspace))
    docs = [workspace.path / "japan_trust_launch_note.md", workspace.path / "customer_ai_use_policy_ja.md"]
    if workflows & {"employee", "payroll", "gps"}:
        docs.append(workspace.path / "employee_data_notice_ja.md")
    if "gps" in workflows:
        docs.append(workspace.path / "gps_analysis_notice_ja.md")
    return docs


def load_customer_legal_review(workspace: Workspace) -> CustomerLegalReviewRecord | None:
    path = workspace.customer_legal_review_path
    if not path.exists():
        return None
    try:
        return CustomerLegalReviewRecord(**json.loads(path.read_text(encoding="utf-8")))
    except (OSError, TypeError, json.JSONDecodeError):
        return None


def load_japan_trust_launch_review(workspace: Workspace) -> JapanTrustLaunchReviewRecord | None:
    path = workspace.japan_trust_launch_review_path
    if not path.exists():
        return None
    try:
        return JapanTrustLaunchReviewRecord(**json.loads(path.read_text(encoding="utf-8")))
    except (OSError, TypeError, json.JSONDecodeError):
        return None


def write_customer_legal_review(
    workspace: Workspace,
    *,
    operator: str,
    purpose_of_use: str,
    data_categories: list[str],
    sensitive_workflows: list[str] | None = None,
    third_party_processors: list[str] | None = None,
    retention_summary: str,
    access_summary: str,
    external_actions_hitl: bool,
    approved: bool,
    approval_note: str,
) -> tuple[Path, Path]:
    record = CustomerLegalReviewRecord(
        schema_version=1,
        generated_at=_iso_z(),
        customer_id=workspace.customer_id,
        operator=operator,
        purpose_of_use=purpose_of_use.strip(),
        data_categories=_clean_list(data_categories),
        sensitive_workflows=_clean_list(sensitive_workflows or sensitive_workflow_categories(workspace)),
        third_party_processors=_clean_list(third_party_processors or []),
        retention_summary=retention_summary.strip(),
        access_summary=access_summary.strip(),
        external_actions_hitl=bool(external_actions_hitl),
        approved=bool(approved),
        approval_note=approval_note.strip(),
    )
    return _write_dual_artifacts(
        workspace,
        artifact_key="customer_legal_review",
        writer="customer_readiness.write_customer_legal_review",
        detail="customer-specific legal/contract review recorded for sensitive SMB deployment",
        json_path=workspace.customer_legal_review_path,
        md_path=workspace.customer_legal_review_md_path,
        json_body=json.dumps(asdict(record), ensure_ascii=False, indent=2),
        md_body=render_customer_legal_review_md(record),
    )


def write_japan_trust_launch_review(
    workspace: Workspace,
    *,
    operator: str,
    workflow_categories: list[str] | None = None,
    sensitive_mode: bool,
    human_approval_required: bool,
    approved: bool,
    approval_note: str,
) -> tuple[Path, Path]:
    categories = _clean_list(workflow_categories or sensitive_workflow_categories(workspace))
    required = required_japan_trust_docs(workspace, categories)
    present = [path.name for path in required if path.exists()]
    missing = [path.name for path in required if not path.exists()]
    record = JapanTrustLaunchReviewRecord(
        schema_version=1,
        generated_at=_iso_z(),
        customer_id=workspace.customer_id,
        operator=operator,
        workflow_categories=categories,
        required_docs=[path.name for path in required],
        present_docs=present,
        missing_docs=missing,
        sensitive_mode=bool(sensitive_mode),
        human_approval_required=bool(human_approval_required),
        approved=bool(approved),
        approval_note=approval_note.strip(),
    )
    return _write_dual_artifacts(
        workspace,
        artifact_key="japan_trust_launch_review",
        writer="customer_readiness.write_japan_trust_launch_review",
        detail="Japan SMB trust launch review recorded for sensitive workflow categories",
        json_path=workspace.japan_trust_launch_review_path,
        md_path=workspace.japan_trust_launch_review_md_path,
        json_body=json.dumps(asdict(record), ensure_ascii=False, indent=2),
        md_body=render_japan_trust_launch_review_md(record),
    )


def render_customer_legal_review_md(record: CustomerLegalReviewRecord) -> str:
    lines = [
        "# Customer Legal Review",
        "",
        f"- generated_at: {record.generated_at}",
        f"- customer_id: {record.customer_id}",
        f"- operator: {record.operator}",
        f"- approved: {str(record.approved).lower()}",
        f"- external_actions_hitl: {str(record.external_actions_hitl).lower()}",
        f"- purpose_of_use: {record.purpose_of_use}",
        f"- data_categories: {', '.join(record.data_categories) or '-'}",
        f"- sensitive_workflows: {', '.join(record.sensitive_workflows) or '-'}",
        f"- third_party_processors: {', '.join(record.third_party_processors) or '-'}",
        f"- retention_summary: {record.retention_summary}",
        f"- access_summary: {record.access_summary}",
        f"- approval_note: {record.approval_note or '-'}",
    ]
    return "\n".join(lines) + "\n"


def render_japan_trust_launch_review_md(record: JapanTrustLaunchReviewRecord) -> str:
    lines = [
        "# Japan Trust Launch Review",
        "",
        f"- generated_at: {record.generated_at}",
        f"- customer_id: {record.customer_id}",
        f"- operator: {record.operator}",
        f"- approved: {str(record.approved).lower()}",
        f"- sensitive_mode: {str(record.sensitive_mode).lower()}",
        f"- human_approval_required: {str(record.human_approval_required).lower()}",
        f"- workflow_categories: {', '.join(record.workflow_categories) or '-'}",
        f"- required_docs: {', '.join(record.required_docs) or '-'}",
        f"- present_docs: {', '.join(record.present_docs) or '-'}",
        f"- missing_docs: {', '.join(record.missing_docs) or '-'}",
        f"- approval_note: {record.approval_note or '-'}",
    ]
    return "\n".join(lines) + "\n"


def customer_readiness_summary(workspace: Workspace) -> dict[str, object]:
    legal = load_customer_legal_review(workspace)
    trust = load_japan_trust_launch_review(workspace)
    workflows = sensitive_workflow_categories(workspace)
    return {
        "sensitive_workflows": workflows,
        "legal_review_present": legal is not None,
        "legal_review_approved": bool(legal.approved) if legal is not None else False,
        "trust_review_present": trust is not None,
        "trust_review_approved": bool(trust.approved) if trust is not None else False,
        "trust_missing_docs": list(trust.missing_docs)
        if trust is not None
        else [path.name for path in required_japan_trust_docs(workspace, workflows) if not path.exists()],
    }


def _write_dual_artifacts(
    workspace: Workspace,
    *,
    artifact_key: str,
    writer: str,
    detail: str,
    json_path: Path,
    md_path: Path,
    json_body: str,
    md_body: str,
) -> tuple[Path, Path]:
    workspace.ensure()
    json_path.write_text(json_body, encoding="utf-8")
    md_path.write_text(md_body, encoding="utf-8")
    publish_workspace_artifact_freshness(
        workspace,
        artifact_key=artifact_key,
        artifact_paths=artifact_path_strings([json_path, md_path], relative_to=workspace.path),
        writer=writer,
        detail=detail,
        source_sections=[],
    )
    return json_path, md_path


def _clean_list(values: list[str]) -> list[str]:
    return sorted({value.strip() for value in values if value and value.strip()})


def _iso_z() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


__all__ = [
    "CustomerLegalReviewRecord",
    "JapanTrustLaunchReviewRecord",
    "customer_readiness_summary",
    "detect_sensitive_signals",
    "load_customer_legal_review",
    "load_japan_trust_launch_review",
    "render_customer_legal_review_md",
    "render_japan_trust_launch_review_md",
    "required_japan_trust_docs",
    "sensitive_workflow_categories",
    "write_customer_legal_review",
    "write_japan_trust_launch_review",
]
