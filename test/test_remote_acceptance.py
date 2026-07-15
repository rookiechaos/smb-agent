from __future__ import annotations

import json

from smbagent.remote_acceptance import (
    build_remote_smoke_plan,
    record_remote_smoke_result,
    remote_smoke_evidence_paths,
    write_remote_smoke_plan,
)


def test_remote_smoke_plan_includes_api_and_cli_steps(config):
    plan = build_remote_smoke_plan(config, customer_id="dry-run-01")
    names = {step.name for step in plan.steps}
    assert {
        "anthropic_sdk_negotiation",
        "openai_sdk_validation",
        "claude_cli_coding",
        "codex_cli_validation",
        "full_pipeline_dry_run",
    } <= names
    assert plan.remote_only is True


def test_write_remote_smoke_plan_writes_json(config):
    path = write_remote_smoke_plan(config)
    assert path.exists()
    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["customer_id"] == "dry-run-01"


def test_record_remote_smoke_result_updates_release_manifest(config):
    path = record_remote_smoke_result(
        config,
        runner_id="macmini-1",
        customer_id="dry-run-01",
        pipeline_passed=True,
        anthropic_api_ok=True,
        openai_api_ok=True,
        claude_cli_ok=True,
        codex_cli_ok=True,
        replay_verify_ok=True,
        notes=["acceptance complete"],
    )
    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["runner_id"] == "macmini-1"
    assert remote_smoke_evidence_paths(config)
    manifests = sorted((config.root / "ops" / "release_reviews").glob("*/release_record_manifest.json"))
    assert manifests
    manifest = json.loads(manifests[-1].read_text(encoding="utf-8"))
    by_key = {item["key"]: item for item in manifest["artifacts"]}
    assert by_key["remote_smoke"]["status"] == "present"
