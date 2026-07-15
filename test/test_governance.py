from __future__ import annotations

import json
from pathlib import Path

from smbagent.approvals import OperatorApprovalLog
from smbagent.config import Config
from smbagent.governance import (
    ExecutionLane,
    GovernanceError,
    classify_deploy_target,
    decide_action,
    enforce_action,
    enforce_deploy_target,
    enforce_integration_action,
    integration_transport_kind,
)


def _write_integration_transport(workspace, integration_name: str, transport: str) -> Path:
    cfg_dir = workspace.code_dir / "integrations" / integration_name
    cfg_dir.mkdir(parents=True, exist_ok=True)
    path = cfg_dir / "config.json"
    path.write_text(json.dumps({"transport": transport}), encoding="utf-8")
    return path


def test_default_config_is_trustable_and_hitl_for_external_writes(config: Config):
    assert config.trust_principle == "trustable"
    assert config.external_execution_policy == "hitl"
    assert config.allow_unattended_external_writes is False
    assert config.unattended_external_writes_allowed() is False


def test_decide_action_allows_unattended_lane_by_default(config: Config):
    decision = decide_action(config, action="validate", lane=ExecutionLane.UNATTENDED)
    assert decision.allowed is True
    assert decision.lane == ExecutionLane.UNATTENDED


def test_decide_action_blocks_external_hitl_lane_by_default(config: Config):
    decision = decide_action(config, action="send_email", lane=ExecutionLane.HITL)
    assert decision.allowed is False
    assert "HITL" in decision.reason


def test_employee_impacting_actions_are_not_unattended(config: Config):
    decision = decide_action(config, action="employee_evaluation", lane=ExecutionLane.UNATTENDED)
    assert decision.allowed is False
    assert "employee-impacting" in decision.reason


def test_employee_impacting_actions_ignore_external_override(config: Config):
    cfg = Config(**{**config.__dict__, "allow_unattended_external_writes": True})
    decision = decide_action(cfg, action="payroll_decision", lane=ExecutionLane.HITL)
    assert decision.allowed is False
    assert "human approval" in decision.reason


def test_enforce_action_allows_external_when_override_enabled(config: Config):
    cfg = Config(**{**config.__dict__, "allow_unattended_external_writes": True})
    enforce_action(cfg, action="send_email", lane=ExecutionLane.HITL)


def test_enforce_action_raises_for_external_hitl_lane_by_default(config: Config):
    try:
        enforce_action(config, action="send_email", lane=ExecutionLane.HITL)
    except GovernanceError as e:
        assert "HITL" in str(e)
    else:
        raise AssertionError("expected GovernanceError")


def test_classify_deploy_target_marks_hosted_targets_hitl():
    assert classify_deploy_target("vercel") == ExecutionLane.HITL
    assert classify_deploy_target("netlify") == ExecutionLane.HITL
    assert classify_deploy_target("tarball") == ExecutionLane.UNATTENDED


def test_integration_transport_kind_reads_customer_config(workspace):
    _write_integration_transport(workspace, "forward-to-clinic", "smtp")
    assert integration_transport_kind(workspace, "forward-to-clinic") == "smtp"


def test_approval_id_allows_one_matching_hosted_deploy(config: Config, workspace):
    event = OperatorApprovalLog(workspace).record_decision(
        action="deploy",
        resource="target=vercel",
        decision="approved",
        operator="alice",
        reason="customer approved production deploy",
    )

    enforce_deploy_target(
        config,
        "vercel",
        workspace=workspace,
        approval_id=event.approval_id,
        operator="alice",
    )
    events = OperatorApprovalLog(workspace).read_all()
    assert [e.event_type for e in events] == ["decision", "use"]

    try:
        enforce_deploy_target(
            config,
            "vercel",
            workspace=workspace,
            approval_id=event.approval_id,
            operator="alice",
        )
    except GovernanceError as e:
        assert "already been used" in str(e)
    else:
        raise AssertionError("expected used approval to be rejected")


def test_approval_must_match_integration_resource(config: Config, workspace):
    _write_integration_transport(workspace, "forward-to-clinic", "smtp")
    event = OperatorApprovalLog(workspace).record_decision(
        action="send_email",
        resource="integration=other, transport=smtp",
        decision="approved",
        operator="alice",
        reason="wrong integration on purpose",
    )

    try:
        enforce_integration_action(
            config,
            workspace,
            "forward-to-clinic",
            action="send_email",
            approval_id=event.approval_id,
            operator="alice",
        )
    except GovernanceError as e:
        assert "does not match" in str(e)
    else:
        raise AssertionError("expected mismatched approval to be rejected")


def test_memory_mail_transport_stays_unattended(config: Config, workspace):
    _write_integration_transport(workspace, "forward-to-clinic", "memory")
    enforce_integration_action(
        config,
        workspace,
        "forward-to-clinic",
        action="send_email",
    )


def test_smtp_mail_transport_requires_hitl_approval(config: Config, workspace):
    _write_integration_transport(workspace, "forward-to-clinic", "smtp")
    try:
        enforce_integration_action(
            config,
            workspace,
            "forward-to-clinic",
            action="send_email",
        )
    except GovernanceError as e:
        assert "HITL approval" in str(e)
        assert "transport=smtp" in str(e)
    else:
        raise AssertionError("expected smtp transport to be blocked by default")


def test_memory_booking_transport_stays_unattended(config: Config, workspace):
    _write_integration_transport(workspace, "book-viewing", "memory")
    enforce_integration_action(
        config,
        workspace,
        "book-viewing",
        action="book_calendar",
    )


def test_google_calendar_transport_requires_hitl_approval(config: Config, workspace):
    _write_integration_transport(workspace, "book-viewing", "google-calendar")
    try:
        enforce_integration_action(
            config,
            workspace,
            "book-viewing",
            action="book_calendar",
        )
    except GovernanceError as e:
        assert "HITL approval" in str(e)
        assert "transport=google-calendar" in str(e)
    else:
        raise AssertionError("expected google-calendar transport to be blocked by default")


def test_memory_crm_transport_stays_unattended(config: Config, workspace):
    _write_integration_transport(workspace, "crm", "memory")
    enforce_integration_action(
        config,
        workspace,
        "crm",
        action="update_crm",
    )


def test_hubspot_transport_requires_hitl_approval(config: Config, workspace):
    _write_integration_transport(workspace, "crm", "hubspot")
    try:
        enforce_integration_action(
            config,
            workspace,
            "crm",
            action="update_crm",
        )
    except GovernanceError as e:
        assert "HITL approval" in str(e)
        assert "transport=hubspot" in str(e)
    else:
        raise AssertionError("expected hubspot transport to be blocked by default")
