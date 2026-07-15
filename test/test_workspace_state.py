from __future__ import annotations

import json

import pytest

from smbagent.types import (
    CompanyContext,
    IntegrationSpec,
    LandingPageSpec,
    Plan,
    Qualification,
    Tier,
    Verdict,
)
from smbagent.workspace_state import WorkspaceStateConflictError, WorkspaceStateStore


def _sample_plan() -> Plan:
    return Plan(
        tier=Tier.STARTER,
        summary="Starter governed deployment.",
        landing_page=LandingPageSpec(
            pages=["/"],
            hero_copy_outline="Helpful operations assistant.",
            primary_cta="Contact us",
            sections=["hero"],
        ),
        agent_skills=[],
        integrations=[IntegrationSpec(name="Gmail", purpose="Draft review only")],
    )


def test_workspace_state_reduce_update_tracks_revision_and_merges_sections(workspace):
    store = WorkspaceStateStore(workspace)
    state = store.reduce_update(
        section="monitor",
        patch={"status": "running", "detail": {"stage": "plan"}},
        writer="test.monitor",
    )
    assert state["revision"] == 1

    state = store.reduce_update(
        section="monitor",
        patch={"detail": {"round": 2}},
        writer="test.monitor",
        expected_revision=1,
    )
    assert state["revision"] == 2
    written = json.loads(workspace.workspace_state_path.read_text(encoding="utf-8"))
    assert written["sections"]["monitor"]["status"] == "running"
    assert written["sections"]["monitor"]["detail"] == {"stage": "plan", "round": 2}
    assert written["sections"]["monitor"]["_meta"]["revision"] == 2
    assert written["sections"]["monitor"]["_meta"]["writer"] == "test.monitor"


def test_workspace_state_conflict_logs_expected_revision_mismatch(workspace):
    store = WorkspaceStateStore(workspace)
    store.reduce_update(section="plan", patch={"summary": "v1"}, writer="test.plan")

    with pytest.raises(WorkspaceStateConflictError):
        store.reduce_update(
            section="plan",
            patch={"summary": "v2"},
            writer="test.plan",
            expected_revision=0,
        )

    lines = workspace.workspace_state_conflicts_path.read_text(encoding="utf-8").splitlines()
    event = json.loads(lines[-1])
    assert event["section"] == "plan"
    assert event["expected_revision"] == 0
    assert event["actual_revision"] == 1


def test_workspace_save_helpers_publish_public_workspace_state(workspace):
    workspace.save_qualification(
        Qualification(
            customer_id=workspace.customer_id,
            go=True,
            recommended_tier=Tier.STARTER,
            summary_ja="対象業務に適合します。",
            reasoning_en="fit",
        )
    )
    workspace.save_company_context(
        CompanyContext(
            mission="Trustworthy SMB operations",
            vision="Operator-supervised local deployment",
            values=["trust", "privacy"],
            current_strategy=["Mac mini first"],
            current_priorities=["governed rollout"],
            decision_style="careful",
            risk_tolerance="low",
        )
    )
    workspace.save_plan(_sample_plan(), "# Plan")
    workspace.save_verdict(
        Verdict(
            passed=False,
            round=2,
            summary="needs review",
            issues=[],
        )
    )

    state = json.loads(workspace.workspace_state_path.read_text(encoding="utf-8"))
    assert state["revision"] >= 4
    assert state["sections"]["qualification"]["go"] is True
    assert state["sections"]["qualification"]["artifact_paths"] == ["qualification.json"]
    assert state["sections"]["company_context"]["mission"] == "Trustworthy SMB operations"
    assert state["sections"]["company_context"]["artifact_paths"] == ["company_context.json", "CONTEXT.md"]
    assert state["sections"]["plan"]["tier"] == "starter"
    assert state["sections"]["plan"]["artifact_paths"] == ["plan.md", "tasks.json"]
    assert state["sections"]["latest_verdict"]["round"] == 2
    assert state["sections"]["latest_verdict"]["status"] == "needs_attention"


def test_workspace_apply_sections_update_can_publish_multiple_sections_in_one_revision(workspace):
    store = WorkspaceStateStore(workspace)
    state = store.apply_sections_update(
        sections={
            "requirements": {"summary_ja": "one"},
            "company_context": {"mission": "two"},
        },
        writer="test.multi",
    )
    assert state["revision"] == 1
    written = json.loads(workspace.workspace_state_path.read_text(encoding="utf-8"))
    assert written["sections"]["requirements"]["_meta"]["revision"] == 1
    assert written["sections"]["company_context"]["_meta"]["revision"] == 1
