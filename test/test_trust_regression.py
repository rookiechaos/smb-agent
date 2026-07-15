from __future__ import annotations

import json
from pathlib import Path

from smbagent.trust_regression import (
    PR_SMOKE_SUITE,
    TRUST_REGRESSION_SUITES,
    build_trust_regression_contract,
    uncovered_trust_regression_test_paths,
    write_trust_regression_bundle,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_trust_regression_contract_has_expected_suites(config):
    contract = build_trust_regression_contract(config)
    assert [suite.key for suite in contract.suites] == [suite.key for suite in TRUST_REGRESSION_SUITES]
    by_key = {suite.key: suite for suite in contract.suites}
    assert "tests/test_trust_eval.py" in by_key["trust_core"].test_paths
    assert "tests/test_bad_llm.py" in by_key["adversarial_boundaries"].test_paths
    assert "tests/test_llm_output_filter_observability.py" in by_key["adversarial_boundaries"].test_paths
    assert "tests/test_orchestrator.py" in by_key["pipeline_core"].test_paths
    assert "tests/test_repo_hygiene.py" in by_key["runtime_governance"].test_paths


def test_trust_regression_contract_covers_all_test_modules():
    assert uncovered_trust_regression_test_paths(REPO_ROOT) == []


def test_write_trust_regression_bundle_publishes_fleet_freshness(tmp_path, config):
    cfg = type(config)(
        **{
            **config.__dict__,
            "root": tmp_path,
            "workspaces_dir": tmp_path / "workspaces",
            "prompts_dir": config.prompts_dir,
        }
    )
    cfg.workspaces_dir.mkdir(parents=True, exist_ok=True)

    contract, json_path, md_path = write_trust_regression_bundle(cfg)

    assert json_path == tmp_path / "ops" / "trust_regression_contract.json"
    assert md_path == tmp_path / "ops" / "trust_regression_contract.md"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["posture"] == "ci_backed_pr_smoke_plus_full_regression_without_outside_ports"
    assert payload["junit_outputs"] == [suite.junit_xml for suite in TRUST_REGRESSION_SUITES]
    state = json.loads((tmp_path / "ops" / "fleet_state.json").read_text(encoding="utf-8"))
    freshness = state["sections"]["artifact_freshness"]["trust_regression_contract"]
    assert freshness["status"] == "fresh"
    assert "ops/trust_regression_contract.json" in freshness["artifact_paths"]
    assert "ops/trust_regression_contract.md" in freshness["artifact_paths"]
    assert contract.smbagent_version == payload["smbagent_version"]


def test_pr_smoke_suite_is_subset_of_discovered_tests():
    discovered = {f"tests/{path.name}" for path in (REPO_ROOT / "tests").glob("test_*.py")}
    assert set(PR_SMOKE_SUITE.test_paths) <= discovered


def test_ci_workflow_uses_contract_and_artifact_upload():
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    nightly = (REPO_ROOT / ".github" / "workflows" / "nightly.yml").read_text(encoding="utf-8")
    assert "trust-regression-contract" in workflow
    assert "Run PR smoke suite" in workflow
    assert "PR_SMOKE_SUITE" in workflow
    assert "test-full" in workflow
    assert "repo-hygiene" in workflow
    assert "SMBAGENT_SERVE_HOST" in workflow
    assert "uncovered_trust_regression_test_paths" in workflow
    assert "upload-artifact@v4" in workflow
    assert "TRUST_REGRESSION_SUITES" in nightly
    assert "schedule:" in nightly
