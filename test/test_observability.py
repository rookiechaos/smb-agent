"""Tests for the per-customer runtime chat logger."""

from __future__ import annotations

import json

from smbagent.annealing import AnnealingPhase, AnnealingState
from smbagent.config import Config
from smbagent.iteration_tuning import IterationTuning
from smbagent.observability import ChatEvent, FailureMemoryLogger, RuntimeLogger
from smbagent.types import Issue, Requirements, Tier, Verdict
from smbagent.workspace import Workspace


def test_logger_creates_runtime_dir_on_first_record(config: Config, workspace: Workspace):
    assert not (workspace.path / "runtime").exists()
    log = RuntimeLogger(workspace)
    log.record(user_message_len=10, reply_len=30, skill_used="x", latency_ms=42)
    assert (workspace.path / "runtime").is_dir()
    assert (workspace.path / "runtime" / "chat.jsonl").exists()


def test_logger_appends_jsonl(config: Config, workspace: Workspace):
    log = RuntimeLogger(workspace)
    log.record(user_message_len=10, reply_len=20, skill_used="a", latency_ms=10)
    log.record(user_message_len=11, reply_len=21, skill_used="b", latency_ms=20)
    raw = (workspace.path / "runtime" / "chat.jsonl").read_text(encoding="utf-8")
    lines = [json.loads(line) for line in raw.strip().split("\n")]
    assert len(lines) == 2
    assert lines[0]["skill_used"] == "a"
    assert lines[1]["skill_used"] == "b"


def test_logger_event_fields(config: Config, workspace: Workspace):
    log = RuntimeLogger(workspace)
    ev = log.record(user_message_len=42, reply_len=100, skill_used="book", latency_ms=350)
    assert ev.user_message_len == 42
    assert ev.reply_len == 100
    assert ev.skill_used == "book"
    assert ev.latency_ms == 350
    assert ev.error is None
    # ISO-8601 with Z suffix
    assert ev.ts.endswith("Z")
    assert "T" in ev.ts


def test_logger_records_error_path(config: Config, workspace: Workspace):
    log = RuntimeLogger(workspace)
    ev = log.record(
        user_message_len=10,
        reply_len=0,
        skill_used=None,
        latency_ms=8,
        error="No skills loaded",
    )
    assert ev.error == "No skills loaded"
    raw_line = (workspace.path / "runtime" / "chat.jsonl").read_text(encoding="utf-8").strip()
    parsed = json.loads(raw_line)
    assert parsed["error"] == "No skills loaded"
    assert parsed["skill_used"] is None
    assert parsed["reply_len"] == 0


def test_logger_privacy_does_not_store_message_content(config: Config, workspace: Workspace):
    """Critical: the log MUST NOT contain the message body, only its length.
    Otherwise customer PII flows into operator logs."""
    log = RuntimeLogger(workspace)
    sensitive = "クレジットカード番号は 4111-1111-1111-1111 です"
    log.record(
        user_message_len=len(sensitive),
        reply_len=20,
        skill_used="x",
        latency_ms=10,
    )
    raw = (workspace.path / "runtime" / "chat.jsonl").read_text(encoding="utf-8")
    assert "4111" not in raw
    assert "クレジットカード" not in raw
    assert str(len(sensitive)) in raw  # length recorded


def test_logger_read_all_returns_events(config: Config, workspace: Workspace):
    log = RuntimeLogger(workspace)
    log.record(user_message_len=1, reply_len=2, skill_used="a", latency_ms=10)
    log.record(user_message_len=3, reply_len=4, skill_used="b", latency_ms=20)
    events = log.read_all()
    assert len(events) == 2
    assert events[0].skill_used == "a"
    assert events[1].skill_used == "b"
    assert all(isinstance(e, ChatEvent) for e in events)


def test_logger_read_all_empty_when_no_log(config: Config, workspace: Workspace):
    assert RuntimeLogger(workspace).read_all() == []


def test_logger_read_all_skips_malformed_lines(config: Config, workspace: Workspace):
    log = RuntimeLogger(workspace)
    log.record(user_message_len=1, reply_len=2, skill_used="a", latency_ms=10)
    # Append a garbage line
    with (workspace.path / "runtime" / "chat.jsonl").open("a", encoding="utf-8") as f:
        f.write("not json\n")
    log.record(user_message_len=3, reply_len=4, skill_used="b", latency_ms=20)
    events = log.read_all()
    assert len(events) == 2
    assert [e.skill_used for e in events] == ["a", "b"]


def test_logger_handles_unicode_skill_names(config: Config, workspace: Workspace):
    log = RuntimeLogger(workspace)
    # Unlikely in practice but defensive — names should pass through.
    log.record(user_message_len=10, reply_len=20, skill_used="予約-受付", latency_ms=5)
    events = log.read_all()
    assert events[0].skill_used == "予約-受付"


def test_logger_jsonl_each_line_is_valid_json(config: Config, workspace: Workspace):
    log = RuntimeLogger(workspace)
    for i in range(5):
        log.record(user_message_len=i, reply_len=i * 2, skill_used=f"s{i}", latency_ms=i)
    raw = (workspace.path / "runtime" / "chat.jsonl").read_text(encoding="utf-8")
    for line in raw.strip().split("\n"):
        parsed = json.loads(line)  # raises if any line is malformed
        assert "ts" in parsed and "skill_used" in parsed


def test_failure_memory_logger_records_tuning_and_issue_counts(config: Config, workspace: Workspace):
    log = FailureMemoryLogger(workspace)
    tuning = IterationTuning.from_config(config)
    workspace.save_requirements(
        Requirements(
            customer_id=workspace.customer_id,
            tier=Tier.GROWTH,
            business_name="Tokyo White Dental",
            summary_ja="test summary",
            target_users=["patients"],
            brand_notes=["clean"],
            desired_skills=["faq", "booking"],
            desired_integrations=["Gmail"],
            acceptance_criteria=["bookings increase"],
        )
    )
    annealing = AnnealingState(
        phase=AnnealingPhase.CONVERGENCE,
        temperature=0.3,
        round_n=2,
        deadlock_detected=True,
        is_final_resolution=False,
    )
    verdict = Verdict(
        passed=False,
        round=2,
        summary="one critical left",
        issues=[
            Issue(severity="critical", description="x"),
            Issue(severity="major", description="y"),
        ],
        tooling_error=None,
    )

    ev = log.record(
        stage="validation",
        outcome="failed_verdict",
        tuning=tuning,
        round_n=2,
        summary=verdict.summary,
        verdict=verdict,
        annealing=annealing,
        coding_tool="claude",
        validation_tool="codex",
        validation_backend="cli",
    )

    assert ev.customer_id == workspace.customer_id
    assert ev.schema_version == FailureMemoryLogger.SCHEMA_VERSION
    assert ev.tier == "growth"
    assert ev.desired_skills_count == 2
    assert ev.desired_integrations_count == 1
    assert ev.acceptance_criteria_count == 1
    assert ev.coding_tool == "claude"
    assert ev.validation_tool == "codex"
    assert ev.validation_backend == "cli"
    assert ev.critical_issues == 1
    assert ev.major_issues == 1
    assert ev.annealing_phase == "convergence"
    assert ev.tuning["anneal_temp_creative"] == 0.7
    events = log.read_all()
    assert len(events) == 1
    assert events[0].outcome == "failed_verdict"
