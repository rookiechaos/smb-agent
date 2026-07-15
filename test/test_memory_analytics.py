from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from smbagent.cli import app
from smbagent.iteration_tuning import IterationTuning
from smbagent.memory_analytics import summarize_workspace_memory, write_memory_analytics
from smbagent.observability.failure_memory import FailureMemoryLogger
from smbagent.observability.loop_memory import LoopMemoryLogger
from smbagent.types import CompanyContext, Requirements, Tier

runner = CliRunner()


@pytest.fixture
def isolated_root(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "smbagent").mkdir()
    (tmp_path / "workspaces").mkdir()
    yield tmp_path


def test_summarize_workspace_memory_produces_recommendations(config, workspace):
    workspace.save_requirements(
        Requirements(
            customer_id=workspace.customer_id,
            tier=Tier.GROWTH,
            business_name="Acme",
            summary_ja="analysis",
            target_users=["ops"],
            brand_notes=[],
            desired_skills=["analysis"],
            desired_integrations=["crm"],
            acceptance_criteria=["pass"],
            company_context=CompanyContext(),
        )
    )
    tuning = IterationTuning.from_config(config)
    FailureMemoryLogger(workspace).record(
        stage="validation",
        outcome="failed_verdict",
        tuning=tuning,
        summary="round kept failing",
        validation_backend="cli",
    )
    FailureMemoryLogger(workspace).record(
        stage="validation",
        outcome="failed_verdict",
        tuning=tuning,
        summary="round kept failing again",
        validation_backend="cli",
    )
    LoopMemoryLogger(workspace).record(
        outcome="passed",
        rounds_used=2,
        round_budget=5,
        complexity_score=4,
        benchmark_policy_version="v1",
        adaptive_reason="quick pass",
        tuning={},
        validation_backend="api",
    )
    LoopMemoryLogger(workspace).record(
        outcome="failed_max_rounds",
        rounds_used=5,
        round_budget=5,
        complexity_score=8,
        benchmark_policy_version="v1",
        adaptive_reason="exhausted",
        tuning={},
        validation_backend="cli",
    )
    LoopMemoryLogger(workspace).record(
        outcome="failed_max_rounds",
        rounds_used=5,
        round_budget=5,
        complexity_score=8,
        benchmark_policy_version="v1",
        adaptive_reason="exhausted again",
        tuning={},
        validation_backend="cli",
    )
    summary = summarize_workspace_memory(workspace)
    assert summary.failure_events == 2
    assert summary.loop_events == 3
    assert summary.suggested_anneal_stale_rounds == 3
    assert summary.suggested_validation_backend == "api"


def test_write_memory_analytics_outputs_json_csv_and_fleet_freshness(tmp_path, workspace):
    summary = summarize_workspace_memory(workspace)
    out_dir = tmp_path / "analytics"
    json_path, csv_path = write_memory_analytics(out_dir, [summary])
    assert json_path.exists()
    assert csv_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["workspace_count"] == 1
    assert "fleet_totals" in payload
    assert "customer_id" in csv_path.read_text(encoding="utf-8")
    state = json.loads((tmp_path / "ops" / "fleet_state.json").read_text(encoding="utf-8"))
    freshness = state["sections"]["artifact_freshness"]["memory_analytics"]
    assert freshness["status"] == "fresh"
    assert freshness["artifact_paths"] == [
        "analytics/memory_analytics.json",
        "analytics/memory_analytics.csv",
    ]


def test_memory_analytics_cli_writes_outputs(isolated_root):
    result = runner.invoke(app, ["memory-analytics"])
    assert result.exit_code == 0
    assert "memory analytics" in result.stdout.lower()
