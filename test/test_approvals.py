from __future__ import annotations

from smbagent.approvals import OperatorApprovalLog, count_pending_approvals, normalize_operator_identity


def test_operator_identity_normalizes_bare_names():
    assert normalize_operator_identity("alice") == "human:alice"
    assert normalize_operator_identity("alice@example.com") == "human:alice@example.com"
    assert normalize_operator_identity("system:ci-runner") == "system:ci-runner"


def test_approval_log_stores_canonical_operator_identity(workspace):
    event = OperatorApprovalLog(workspace).record_decision(
        action="deploy",
        resource="target=vercel",
        decision="approved",
        operator="Alice Example",
        reason="launch approved",
    )
    assert event.operator == "human:Alice-Example"

    use = OperatorApprovalLog(workspace).record_use(
        approval_id=event.approval_id,
        action="deploy",
        resource="target=vercel",
        operator="system:release-bot",
        command="deploy --target vercel",
        outcome="allowed",
    )
    assert use.operator == "system:release-bot"


def test_count_pending_approvals_only_counts_unused_valid_decisions(workspace):
    log = OperatorApprovalLog(workspace)
    first = log.record_decision(
        action="deploy",
        resource="target=vercel",
        decision="approved",
        operator="alice",
        reason="ok",
    )
    second = log.record_decision(
        action="email",
        resource="customer=acme",
        decision="approved",
        operator="alice",
        reason="ok",
    )
    log.record_use(
        approval_id=first.approval_id,
        action="deploy",
        resource="target=vercel",
        operator="system:bot",
        command="deploy",
        outcome="allowed",
    )
    assert count_pending_approvals(workspace) == 1
