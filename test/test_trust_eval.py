from __future__ import annotations

from smbagent.trust_eval import evaluate_trustworthiness


def test_trust_eval_workspace_checks_pass_critical(config, workspace):
    checks = evaluate_trustworthiness(config, workspace)
    by_name = {c.name: c for c in checks}
    assert by_name["external_writes_default_hitl"].passed is True
    assert by_name["runtime_token_hash_at_rest"].passed is True
    assert by_name["runtime_external_action_blocked"].passed is True
    assert by_name["coding_benchmark_policy_current"].passed is True
    assert by_name["japan_trust_readiness_docs_present"].passed is True
    assert by_name["employee_impacting_actions_hitl"].passed is True
    assert by_name["japan_sensitive_launch_note"].passed is True
    assert by_name["employee_data_notice_ready"].passed is True
    assert by_name["subprocess_isolation_configured"].passed is False
    assert by_name["subprocess_isolation_configured"].severity == "major"
