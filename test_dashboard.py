"""Tests for the operator dashboard (multi-customer index)."""

from __future__ import annotations

import json
import time
from pathlib import Path

from smbagent.config import Config
from smbagent.customer_readiness import write_customer_legal_review, write_japan_trust_launch_review
from smbagent.iteration_tuning import IterationTuning
from smbagent.memory_analytics import summarize_all_workspaces, write_memory_analytics
from smbagent.observability import SLMAdvisoryLogger
from smbagent.observability.loop_memory import LoopMemoryLogger
from smbagent.portal import (
    collect_customer_summaries,
    render_operator_dashboard,
    write_operator_dashboard,
)
from smbagent.slm.dataset_review import build_weekly_dataset_review, write_weekly_dataset_review
from smbagent.slm.specialist_dataset import (
    build_specialist_dataset_snapshot,
    default_specialist_dataset_paths,
)
from smbagent.types import (
    AgentSkillSpec,
    IntegrationSpec,
    LandingPageSpec,
    Plan,
    Qualification,
    Requirements,
    Tier,
    Verdict,
)
from smbagent.workflow_circuit_breaker import reset_workflow_circuit_breaker
from smbagent.workflow_monitor import update_workflow_monitor
from smbagent.workspace import Workspace


def _make_workspace(config: Config, customer_id: str) -> Workspace:
    ws = Workspace(customer_id, config.workspaces_dir)
    ws.ensure()
    return ws


def _full_state(ws: Workspace, *, go: bool = True, passed: bool = True) -> None:
    ws.save_qualification(
        Qualification(
            customer_id=ws.customer_id,
            go=go,
            recommended_tier=Tier.GROWTH if go else None,
            summary_ja="ok",
        )
    )
    if go:
        ws.save_requirements(
            Requirements(
                customer_id=ws.customer_id,
                tier=Tier.GROWTH,
                business_name="X",
                summary_ja="x",
                target_users=["x"],
                brand_notes=["y"],
                desired_skills=["s"],
                desired_integrations=["i"],
                acceptance_criteria=["a"],
            )
        )
        ws.save_plan(
            Plan(
                tier=Tier.GROWTH,
                summary="s",
                landing_page=LandingPageSpec(pages=["/"], hero_copy_outline="h", primary_cta="c"),
                agent_skills=[AgentSkillSpec(name="s1", description="d", system_prompt_outline="o")],
                integrations=[IntegrationSpec(name="i", purpose="p")],
            ),
            plan_md="# plan",
        )
        ws.save_verdict(Verdict(passed=passed, round=1, summary="ok", issues=[]))
        (ws.code_dir / "marker.txt").write_text("present", encoding="utf-8")


# ---- collect_customer_summaries ----


def test_collect_returns_empty_when_workspaces_dir_missing(config: Config, tmp_path: Path):
    summaries = collect_customer_summaries(tmp_path / "nope")
    assert summaries == []


def test_collect_returns_empty_when_no_customers(config: Config):
    config.workspaces_dir.mkdir(parents=True, exist_ok=True)
    assert collect_customer_summaries(config.workspaces_dir) == []


def test_collect_skips_non_directories(config: Config):
    config.workspaces_dir.mkdir(parents=True, exist_ok=True)
    (config.workspaces_dir / "stray.tar.gz").write_text("x", encoding="utf-8")
    _make_workspace(config, "real-customer")
    summaries = collect_customer_summaries(config.workspaces_dir)
    assert [s.customer_id for s in summaries] == ["real-customer"]


def test_collect_skips_directories_with_invalid_names(config: Config):
    """A dir whose name fails customer_id validation must be skipped, not crash."""
    config.workspaces_dir.mkdir(parents=True, exist_ok=True)
    (config.workspaces_dir / ".hidden").mkdir()
    (config.workspaces_dir / "bad name with space").mkdir()
    _make_workspace(config, "ok-name")
    summaries = collect_customer_summaries(config.workspaces_dir)
    assert [s.customer_id for s in summaries] == ["ok-name"]


def test_collect_extracts_tier_from_qualification(config: Config):
    ws = _make_workspace(config, "from-qual")
    ws.save_qualification(
        Qualification(
            customer_id="from-qual",
            go=True,
            recommended_tier=Tier.BUSINESS,
            summary_ja="ok",
        )
    )
    s = collect_customer_summaries(config.workspaces_dir)[0]
    assert s.has_qualification is True
    assert s.go is True
    assert s.tier == Tier.BUSINESS


def test_collect_falls_back_to_requirements_tier_when_no_qualification(config: Config):
    ws = _make_workspace(config, "no-qual")
    ws.save_requirements(
        Requirements(
            customer_id="no-qual",
            tier=Tier.STARTER,
            business_name="X",
            summary_ja="x",
            target_users=["x"],
            brand_notes=["y"],
            desired_skills=["s"],
            desired_integrations=["i"],
            acceptance_criteria=["a"],
        )
    )
    s = collect_customer_summaries(config.workspaces_dir)[0]
    assert s.has_qualification is False
    assert s.tier == Tier.STARTER


def test_collect_handles_full_workspace(config: Config):
    ws = _make_workspace(config, "full")
    _full_state(ws, go=True, passed=True)
    s = collect_customer_summaries(config.workspaces_dir)[0]
    assert s.go is True
    assert s.has_requirements
    assert s.has_plan
    assert s.has_code
    assert s.last_verdict_round == 1
    assert s.last_verdict_passed is True
    assert s.loop_posture == "bounded_checkpointed_learning_loop"
    assert s.loop_ready_count >= 1
    assert "5項目中" in s.loop_summary_ja or "bounded loops" in s.loop_summary_ja
    assert s.tuning_suggestions == []


def test_collect_handles_no_go_customer(config: Config):
    ws = _make_workspace(config, "no-go")
    _full_state(ws, go=False)
    s = collect_customer_summaries(config.workspaces_dir)[0]
    assert s.go is False
    assert s.tier is None  # qualification has no recommended_tier
    assert s.has_requirements is False
    assert s.has_plan is False


def test_collect_sorts_by_last_activity_desc(config: Config):
    """Most recent activity appears first."""
    a = _make_workspace(config, "older-cust")
    a.save_qualification(
        Qualification(customer_id="older-cust", go=True, recommended_tier=Tier.STARTER, summary_ja=".")
    )
    time.sleep(0.05)
    b = _make_workspace(config, "newer-cust")
    b.save_qualification(
        Qualification(customer_id="newer-cust", go=True, recommended_tier=Tier.STARTER, summary_ja=".")
    )
    summaries = collect_customer_summaries(config.workspaces_dir)
    assert [s.customer_id for s in summaries] == ["newer-cust", "older-cust"]


def test_collect_handles_malformed_qualification_gracefully(config: Config):
    ws = _make_workspace(config, "malformed")
    ws.qualification_path.write_text("not json", encoding="utf-8")
    s = collect_customer_summaries(config.workspaces_dir)[0]
    # has_qualification=True (file is there) but parsed fields are unset
    assert s.has_qualification is True
    assert s.go is None
    assert s.tier is None


def test_collect_skips_dashboard_html_file(config: Config):
    """dashboard.html written into workspaces/ must not be treated as a customer."""
    config.workspaces_dir.mkdir(parents=True, exist_ok=True)
    (config.workspaces_dir / "dashboard.html").write_text("...", encoding="utf-8")
    _make_workspace(config, "real-cust")
    summaries = collect_customer_summaries(config.workspaces_dir)
    assert [s.customer_id for s in summaries] == ["real-cust"]


# ---- render_operator_dashboard ----


def test_render_empty_dashboard(config: Config):
    out = render_operator_dashboard(config.workspaces_dir)
    assert out.startswith("<!doctype html>")
    assert "No customers yet" in out


def test_render_dashboard_with_one_customer(config: Config):
    ws = _make_workspace(config, "acme-co")
    _full_state(ws)
    out = render_operator_dashboard(config.workspaces_dir)
    assert "acme-co" in out
    assert "GO" in out
    assert "growth" in out
    assert "PASSED" in out
    assert "Fleet memory analytics" in out
    assert "SLM framework posture" in out
    assert "default_off=true" in out
    assert "SLM pack-based tuning view" in out
    assert "Maintainer suggestions" in out
    assert "Maintainer entry points" in out
    assert "Agent memory isolation" in out
    assert "Owner view" in out
    assert "Maintainer signals" in out
    assert "Isolation" in out
    assert "Remote access posture" in out
    assert "preferred=tailscale" in out
    assert "localhost/no-port" in out or "tailscale-first" in out
    assert "loop=" in out
    assert "bounded_checkpointed_learning_loop" in out
    assert "Loop maturity watchlist" in out
    assert "smbagent loop-engineering acme-co" in out
    assert "attention" in out or "growing" in out or "mature" in out


def test_render_dashboard_shows_network_posture_fallback_flags(config: Config):
    out = render_operator_dashboard(config.workspaces_dir)
    assert "Remote access posture" in out
    assert "query_fallback=false" in out
    assert "lan_fallback=false" in out
    assert "vpn posture" in out


def test_render_dashboard_escapes_jp_safe(config: Config):
    """customer_id is regex-validated so it can't contain <script>, but defensively
    verify that customer_id values are HTML-escaped in the rendered output."""
    ws = _make_workspace(config, "a.b-co")
    _full_state(ws)
    out = render_operator_dashboard(config.workspaces_dir)
    assert "a.b-co" in out
    # The primary link points at the workflow monitor; the portal remains linked too.
    assert 'href="a.b-co/monitor.html"' in out
    assert 'href="a.b-co/portal.html"' in out


def test_render_dashboard_shows_pending_when_qualification_missing(config: Config):
    _make_workspace(config, "fresh-cust")  # nothing in it
    out = render_operator_dashboard(config.workspaces_dir)
    assert "fresh-cust" in out
    # Pending pill appears in the qualify column
    assert "pending" in out


def test_render_dashboard_shows_failed_verdict_pill(config: Config):
    ws = _make_workspace(config, "still-stuck")
    _full_state(ws, go=True, passed=False)
    out = render_operator_dashboard(config.workspaces_dir)
    assert "FAILED" in out
    assert "still-stuck" in out


def test_render_dashboard_shows_maintainer_tuning_suggestions(config: Config):
    ws = _make_workspace(config, "needs-tune")
    update_workflow_monitor(
        ws,
        status="failed_max_rounds",
        active_stage="validation",
        current_round=4,
        detail="Loop exhausted.",
    )
    out = render_operator_dashboard(config.workspaces_dir)
    assert "Tuning suggestions" in out
    assert "Consider increasing anneal_stale_rounds." in out
    assert "Copy and run" in out
    assert "smbagent tune set --customer needs-tune --stale-rounds 3" in out
    assert "attention" in out


def test_render_dashboard_shows_workflow_breaker_state(config: Config):
    ws = _make_workspace(config, "breaker-co")
    _full_state(ws)
    reset_workflow_circuit_breaker(
        ws,
        config,
        reason="operator armed breaker for future runtime protection",
    )
    breaker_path = ws.workflow_circuit_breaker_path
    data = json.loads(breaker_path.read_text(encoding="utf-8"))
    data["enabled"] = True
    data["open"] = True
    data["status"] = "open"
    data["reason"] = "Paused for safety after repeated background errors."
    breaker_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    out = render_operator_dashboard(config.workspaces_dir)

    assert "Breaker" in out
    assert "breaker-co" in out
    assert "Paused for safety after repeated background errors." in out
    assert "open" in out


def test_render_dashboard_shows_fleet_memory_analytics_from_file(config: Config):
    ws = _make_workspace(config, "fleet-acme")
    _full_state(ws)
    analytics_dir = config.root / "analytics"
    summaries = summarize_all_workspaces(config.workspaces_dir)
    write_memory_analytics(analytics_dir, summaries)

    out = render_operator_dashboard(config.workspaces_dir)

    assert "Fleet memory analytics" in out
    assert "Derived from <code>memory_analytics.json</code>" in out
    assert "Workspaces analyzed" in out


def test_render_dashboard_shows_fleet_recommendation_commands(config: Config):
    ws = _make_workspace(config, "fleet-tune")
    tuning = IterationTuning.from_config(config)
    LoopMemoryLogger(ws).record(
        outcome="failed_max_rounds",
        rounds_used=5,
        round_budget=5,
        complexity_score=8,
        benchmark_policy_version="v1",
        adaptive_reason="exhausted",
        tuning=tuning.model_dump(),
        validation_backend="cli",
    )
    LoopMemoryLogger(ws).record(
        outcome="failed_max_rounds",
        rounds_used=5,
        round_budget=5,
        complexity_score=8,
        benchmark_policy_version="v1",
        adaptive_reason="exhausted again",
        tuning=tuning.model_dump(),
        validation_backend="cli",
    )
    analytics_dir = config.root / "analytics"
    summaries = summarize_all_workspaces(config.workspaces_dir)
    write_memory_analytics(analytics_dir, summaries)

    out = render_operator_dashboard(config.workspaces_dir)

    assert "Suggested next moves" in out
    assert "fleet-tune: raise stale_rounds to 3" in out
    assert "smbagent tune set --customer fleet-tune --stale-rounds 3" in out


def test_render_dashboard_lists_multiple_customers(config: Config):
    for i, name in enumerate(["alpha", "beta", "gamma"]):
        ws = _make_workspace(config, name)
        _full_state(ws)
        time.sleep(0.01)
    out = render_operator_dashboard(config.workspaces_dir)
    assert "alpha" in out and "beta" in out and "gamma" in out
    # Header reports the count
    assert "3 customer" in out


def test_render_dashboard_no_go_column_value(config: Config):
    ws = _make_workspace(config, "rejected")
    _full_state(ws, go=False)
    out = render_operator_dashboard(config.workspaces_dir)
    assert "NO-GO" in out


# ---- write_operator_dashboard ----


def test_write_operator_dashboard_persists_to_workspaces_dir(config: Config):
    _make_workspace(config, "any-cust")
    out_path = write_operator_dashboard(config.workspaces_dir)
    assert out_path == config.workspaces_dir / "dashboard.html"
    assert out_path.exists()
    text = out_path.read_text(encoding="utf-8")
    assert text.startswith("<!doctype html>")
    assert "any-cust" in text
    state = json.loads((config.root / "ops" / "fleet_state.json").read_text(encoding="utf-8"))
    freshness = state["sections"]["artifact_freshness"]["operator_dashboard_html"]
    assert freshness["status"] == "fresh"
    assert freshness["artifact_paths"] == ["workspaces/dashboard.html"]
    assert (config.root / "ops" / "next_stage_priorities.json").exists()
    assert (config.root / "ops" / "agent_isolation_status.json").exists()
    assert (config.root / "ops" / "agent_packs" / "customers.json").exists()


def test_render_dashboard_shows_latest_slm_dataset_review(config: Config):
    ws = _make_workspace(config, "slm-review")
    _full_state(ws)
    SLMAdvisoryLogger(ws).record(
        stage="workflow_dispatch",
        applied=True,
        workflow_family="ikida_gps",
        task_class="gps_analysis",
        risk_band="medium",
        hitl_recommended=False,
        confidence=0.82,
        notes="dataset review sample",
    )
    manifest, examples = build_specialist_dataset_snapshot(
        dataset_snapshot_id="weekly-2026-06-10",
        workspaces=[ws],
        config=config,
    )
    review = build_weekly_dataset_review(manifest=manifest, examples=examples)
    write_weekly_dataset_review(
        paths=default_specialist_dataset_paths(config.root / "slm"),
        review=review,
    )

    out = render_operator_dashboard(config.workspaces_dir)

    assert "Latest SLM dataset review" in out
    assert "weekly-2026-06-10" in out
    assert "Maintainer next step" in out
    assert "READY" in out or "REVIEW" in out or "HOLD" in out


def test_render_dashboard_shows_slm_governance_lifecycle(config: Config):
    ws = _make_workspace(config, "slm-life")
    _full_state(ws)
    SLMAdvisoryLogger(ws).record(
        stage="workflow_dispatch",
        applied=True,
        workflow_family="ikida_gps",
        task_class="gps_analysis",
        risk_band="medium",
        hitl_recommended=False,
        confidence=0.82,
        notes="lifecycle sample",
    )
    manifest, examples = build_specialist_dataset_snapshot(
        dataset_snapshot_id="weekly-2026-06-12",
        workspaces=[ws],
        config=config,
    )
    review = build_weekly_dataset_review(manifest=manifest, examples=examples)
    write_weekly_dataset_review(
        paths=default_specialist_dataset_paths(config.root / "slm"),
        review=review,
    )
    (config.root / "slm" / "registry").mkdir(parents=True, exist_ok=True)
    (config.root / "slm" / "registry" / "governance_state.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "revision": 2,
                "updated_at": "2026-06-08T00:00:00Z",
                "sections": {
                    "promotion_lifecycle": {
                        "status": "pending_review",
                        "candidate_version": "qwen3.5-2b-lora-2026-06-12-r1",
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    out = render_operator_dashboard(config.workspaces_dir)

    assert "Lifecycle: pending_review" in out
    assert "qwen3.5-2b-lora-2026-06-12-r1" in out


def test_render_dashboard_shows_slm_governance_conflicts(config: Config):
    ws = _make_workspace(config, "slm-conflict")
    _full_state(ws)
    registry_dir = config.root / "slm" / "registry"
    registry_dir.mkdir(parents=True, exist_ok=True)
    (registry_dir / "governance_state_conflicts.jsonl").write_text(
        json.dumps(
            {
                "writer": "cli.slm_dataset_build",
                "section": "weekly_review",
                "expected_revision": 0,
                "actual_revision": 2,
                "ts": "2026-06-08T10:00:00.000000Z",
                "reason": "expected_revision_mismatch",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    out = render_operator_dashboard(config.workspaces_dir)

    assert "SLM governance observability" in out
    assert "1 conflict(s)" in out
    assert "section=weekly_review" in out
    assert "writer=cli.slm_dataset_build" in out


def test_render_dashboard_shows_workspace_occ_conflicts(config: Config):
    ws = _make_workspace(config, "workspace-conflict")
    _full_state(ws)
    ws.workspace_state_conflicts_path.write_text(
        json.dumps(
            {
                "customer_id": ws.customer_id,
                "writer": "workspace.save_plan",
                "section": "plan,requirements",
                "expected_revision": 2,
                "actual_revision": 3,
                "ts": "2026-06-10T12:00:00.000000Z",
                "reason": "expected_revision_mismatch",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    out = render_operator_dashboard(config.workspaces_dir)

    assert "Workspace OCC observability" in out
    assert "1 conflict(s)" in out
    assert "customer=workspace-conflict" in out
    assert "section=plan,requirements" in out
    assert "writer=workspace.save_plan" in out


def test_render_dashboard_shows_commercial_readiness_summary(config: Config):
    ws = _make_workspace(config, "commercial-ready")
    _full_state(ws)
    (config.root / "ops").mkdir(parents=True, exist_ok=True)
    (config.root / "ops" / "pre_release_check.json").write_text(
        json.dumps(
            {"schema_version": 1, "smbagent_version": "0.2.0", "generated_at": "2026-06-15T12:00:00Z"},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    out = render_operator_dashboard(config.workspaces_dir)

    assert "Commercial readiness" in out
    assert "security-hardened and locally checkable" in out
    assert "Local blocking gaps" in out
    assert "Remote deferred gates" in out
    assert "local_blocking_gaps=" in out
    assert "remote_deferred_gates=" in out
    assert "Pre-release check" in out
    assert "Prioritized release queue" in out
    assert "Full synthetic dry-run against real APIs/CLIs" in out
    assert "last_review=2026-06-15T12:00:00Z | version=0.2.0" in out


def test_render_dashboard_shows_fleet_artifact_freshness(config: Config):
    ws = _make_workspace(config, "fleet-fresh")
    _full_state(ws)
    analytics_dir = config.root / "analytics"
    summaries = summarize_all_workspaces(config.workspaces_dir)
    write_memory_analytics(analytics_dir, summaries)
    write_operator_dashboard(config.workspaces_dir)

    out = render_operator_dashboard(config.workspaces_dir)

    assert "Fleet artifact freshness" in out
    assert "dashboard: fresh" in out
    assert "analytics: fresh" in out
    assert "pre-release: unknown" in out or "pre-release: fresh" in out


def test_render_dashboard_shows_occ_reducer_integration(config: Config):
    ws = _make_workspace(config, "occ-co")
    _full_state(ws)

    out = render_operator_dashboard(config.workspaces_dir)

    assert "OCC / reducer integration" in out
    assert "Workspace reducer layer" in out
    assert "Fleet reducer layer" in out
    assert "SLM governance reducer layer" in out


def test_render_dashboard_shows_agent_isolation_entry_points(config: Config):
    ws = _make_workspace(config, "isolation-co")
    _full_state(ws)

    out = render_operator_dashboard(config.workspaces_dir)

    assert "Agent memory isolation" in out
    assert "../internal_doc/MAINTAINER_RUNBOOK.md" in out
    assert "../ops/agent_isolation_status.json" in out
    assert "coding_surface=" in out
    assert "validation_surface=" in out


def test_render_dashboard_shows_owner_and_maintainer_customer_views(config: Config):
    ws = _make_workspace(config, "owner-signal-co")
    _full_state(ws)
    update_workflow_monitor(
        ws,
        status="running",
        active_stage="validation",
        current_round=1,
        detail="Awaiting approval.",
    )

    out = render_operator_dashboard(config.workspaces_dir)

    assert "Running" in out
    assert "pending_approvals=" in out
    assert "alerts=" in out


def test_render_dashboard_shows_agent_isolation_posture_by_customer(config: Config):
    ws = _make_workspace(config, "iso-pack-co")
    _full_state(ws)
    write_operator_dashboard(config.workspaces_dir)

    out = render_operator_dashboard(config.workspaces_dir)

    assert "Agent isolation posture by customer" in out
    assert "iso-pack-co" in out
    assert "public_artifacts=" in out
    assert "conflicts=" in out


def test_render_dashboard_shows_next_stage_priorities(config: Config):
    ws = _make_workspace(config, "priority-co")
    _full_state(ws)

    out = render_operator_dashboard(config.workspaces_dir)

    assert "Next-stage priorities" in out
    assert "Global action queue" in out
    assert "Workflow operating system" in out
    assert "Deliverable system" in out
    assert "Decision support surfaces" in out
    assert "Closed-loop improvement" in out
    assert "Trust evidence" in out
    assert "Service model" in out


def test_render_dashboard_shows_loop_search_reason_and_customer_reviews(config: Config):
    ws = _make_workspace(config, "loop-co")
    _full_state(ws)
    ws.loop_search_status_path.write_text(
        '{"selected_action":"stop","selected_source_round":1,"selected_reason":"Stop when extra search is unlikely to be commercially worth the added cost or churn.","cost_guard_status":"high"}',
        encoding="utf-8",
    )
    write_customer_legal_review(
        ws,
        operator="human:alice",
        purpose_of_use="clinic support",
        data_categories=["clinic", "voice"],
        sensitive_workflows=["clinic", "voice"],
        retention_summary="30 days",
        access_summary="owner + operator",
        external_actions_hitl=True,
        approved=True,
        approval_note="ok",
    )
    (ws.path / "japan_trust_launch_note.md").write_text("note", encoding="utf-8")
    (ws.path / "customer_ai_use_policy_ja.md").write_text("policy", encoding="utf-8")
    write_japan_trust_launch_review(
        ws,
        operator="human:alice",
        workflow_categories=["clinic", "voice"],
        sensitive_mode=config.sensitive_mode,
        human_approval_required=True,
        approved=True,
        approval_note="ok",
    )
    out = render_operator_dashboard(config.workspaces_dir)
    assert "search=stop from round 1" in out
    assert "commercially worth the added cost" in out
    assert "legal_review=true | trust_launch=true" in out
