from __future__ import annotations

import json

from smbagent.remote_benchmarks import (
    build_remote_benchmark_plan,
    record_remote_benchmark_result,
    write_remote_benchmark_plan,
)


def test_remote_benchmark_plan_includes_primary_benchmarks(config):
    plan = build_remote_benchmark_plan(config)
    names = {item.name for item in plan.benchmarks}
    assert {"SWE-bench Pro", "LiveCodeBench", "Terminal-Bench 2.0"} <= names
    assert plan.remote_only is True
    assert len(plan.execution_lanes) == 2
    assert plan.subprocess_isolation == config.subprocess_isolation


def test_remote_benchmark_record_writes_result(config):
    path = record_remote_benchmark_result(
        config,
        benchmark="SWE-bench Pro",
        runner_id="macmini-1",
        model_label="claude+codex",
        score=42.0,
        cost_usd=12.5,
        latency_s=81.2,
        cases_run=50,
        notes=["weekly"],
    )
    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["benchmark"] == "SWE-bench Pro"
    assert body["cost_usd"] == 12.5


def test_write_remote_benchmark_plan_writes_json(config):
    path = write_remote_benchmark_plan(config)
    assert path.exists()


def test_remote_benchmark_plan_wraps_execution_lanes_for_apple_container(config, monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    cfg = type(config)(**{**config.__dict__, "subprocess_isolation": "apple-container"})
    plan = build_remote_benchmark_plan(cfg)
    rendered = "\n".join(" ".join(item.command_preview) for item in plan.execution_lanes)
    assert "container run" in rendered
    assert "smbagent.remote_benchmark_worker" in rendered
