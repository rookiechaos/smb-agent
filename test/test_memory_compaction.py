from __future__ import annotations

from smbagent.company_context import CompanyContextPatch, append_company_context_refresh
from smbagent.iteration_tuning import IterationTuning
from smbagent.memory_compaction import (
    build_plan_context_pack,
    compact_negotiation_messages,
    retrieve_memory_snippets,
    write_plan_context_pack,
    write_retrieved_memory_context,
)
from smbagent.observability import MemoryCompactionLogger
from smbagent.observability.failure_memory import FailureMemoryLogger
from smbagent.observability.loop_memory import LoopMemoryLogger
from smbagent.types import CompanyContext, Requirements, Tier, Verdict


def test_compact_negotiation_messages_keeps_recent_turns_and_summarizes_older():
    messages = []
    for idx in range(10):
        messages.append({"role": "user", "content": f"customer detail {idx}"})
        messages.append({"role": "assistant", "content": f"follow-up question {idx}"})
    compacted = compact_negotiation_messages(messages, recent_turns=3)
    assert len(compacted.recent_messages) == 6
    assert "customer detail 0" in compacted.summary
    assert compacted.recent_messages[0]["content"] == "customer detail 7"


def test_write_plan_context_pack_writes_compact_artifact(workspace):
    req = Requirements(
        customer_id=workspace.customer_id,
        tier=Tier.GROWTH,
        business_name="Ikida",
        summary_ja="GPS analysis and daily report support",
        target_users=["field staff", "owner"],
        brand_notes=["practical"],
        desired_skills=["GPS analysis", "daily report"],
        desired_integrations=["CSV import"],
        acceptance_criteria=["highlight route anomalies"],
        company_context=CompanyContext(
            mission="make field work visible",
            vision="trusted SMB operations",
            values=["clarity"],
            current_strategy=["improve route productivity"],
            current_priorities=["reduce missed visits"],
            decision_style="practical",
            risk_tolerance="low",
        ),
    )
    workspace.save_requirements(req)
    workspace.transcript_path.write_text(
        "USER: We need GPS anomaly analysis.\n\nUSER: Keep it simple for the owner.\n",
        encoding="utf-8",
    )
    append_company_context_refresh(
        workspace.company_context_updates_path,
        note="Shift emphasis to route anomaly detection",
        patch=CompanyContextPatch(current_priorities=["route anomaly detection"]),
    )
    out = write_plan_context_pack(workspace)
    text = out.read_text(encoding="utf-8")
    assert out == workspace.plan_context_pack_path
    assert "Packed planning context" in text
    assert "GPS anomaly analysis" in text
    assert "route anomaly detection" in text
    events = MemoryCompactionLogger(workspace).read_all()
    assert events[-1].mode == "packed_context"
    assert "transcript" in events[-1].sources


def test_build_plan_context_pack_stays_compact(workspace):
    req = Requirements(
        customer_id=workspace.customer_id,
        tier=Tier.STARTER,
        business_name="Clinic",
        summary_ja="booking support",
        target_users=["patients"],
        brand_notes=["calm"],
        desired_skills=["booking"],
        desired_integrations=["calendar"],
        acceptance_criteria=["bookings confirmed"],
        company_context=CompanyContext(),
    )
    text = build_plan_context_pack(req, CompanyContext(), "USER: booking\n" * 50)
    assert len(text) <= 4000
    assert "Transcript highlights" in text


def test_retrieve_memory_snippets_prefers_relevant_failures_and_updates(config, workspace):
    req = Requirements(
        customer_id=workspace.customer_id,
        tier=Tier.GROWTH,
        business_name="Ikida",
        summary_ja="GPS analysis",
        target_users=["owner"],
        brand_notes=[],
        desired_skills=["GPS analysis"],
        desired_integrations=["CSV import"],
        acceptance_criteria=["flag anomalies"],
        company_context=CompanyContext(),
    )
    workspace.save_requirements(req)
    FailureMemoryLogger(workspace).record(
        stage="validation",
        outcome="failed_verdict",
        tuning=IterationTuning.from_config(config),
        summary="GPS anomaly report missed route gaps",
    )
    LoopMemoryLogger(workspace).record(
        outcome="failed_max_rounds",
        rounds_used=5,
        round_budget=5,
        complexity_score=8,
        benchmark_policy_version="v1",
        adaptive_reason="GPS analysis kept failing near budget limit",
        tuning={},
    )
    append_company_context_refresh(
        workspace.company_context_updates_path,
        note="GPS anomaly detection is now the top priority",
        patch=CompanyContextPatch(current_priorities=["GPS anomaly detection"]),
    )
    prior = Verdict(passed=False, round=2, summary="GPS anomaly report needs work", issues=[])
    snippets = retrieve_memory_snippets(workspace, prior)
    joined = "\n".join(snippets)
    assert "Prior failure pattern" in joined
    assert "Prior loop pattern" in joined
    assert "Recent context update" in joined


def test_write_retrieved_memory_context_records_hit_event(config, workspace):
    req = Requirements(
        customer_id=workspace.customer_id,
        tier=Tier.GROWTH,
        business_name="Ikida",
        summary_ja="GPS analysis",
        target_users=["owner"],
        brand_notes=[],
        desired_skills=["GPS analysis"],
        desired_integrations=["CSV import"],
        acceptance_criteria=["flag anomalies"],
        company_context=CompanyContext(),
    )
    workspace.save_requirements(req)
    FailureMemoryLogger(workspace).record(
        stage="validation",
        outcome="failed_verdict",
        tuning=IterationTuning.from_config(config),
        summary="GPS anomaly report missed route gaps",
    )
    prior = Verdict(passed=False, round=2, summary="GPS anomaly report needs work", issues=[])
    out = write_retrieved_memory_context(workspace, 3, prior)
    assert out == workspace.retrieved_memory_path(3)
    events = MemoryCompactionLogger(workspace).read_all()
    assert events[-1].mode == "retrieval"
    assert events[-1].snippet_count >= 1
    assert "failure_memory" in events[-1].sources


def test_write_retrieved_memory_context_records_miss_event(workspace):
    out = write_retrieved_memory_context(workspace, 2, None)
    assert out is None
    events = MemoryCompactionLogger(workspace).read_all()
    assert events[-1].mode == "retrieval"
    assert events[-1].snippet_count == 0
