from __future__ import annotations

from pathlib import Path


def test_maintainer_runbook_covers_slm_governance_chains():
    root = Path(__file__).resolve().parents[1]
    text = (root / "internal_doc" / "MAINTAINER_RUNBOOK.md").read_text(encoding="utf-8")
    assert "slm-acceptance-checklist" in text
    assert "slm-customer-policy-set" in text
    assert "slm-quality-gate" in text
    assert "slm-promotion-approve" in text


def test_runbook_points_to_real_maintainer_runbook():
    root = Path(__file__).resolve().parents[1]
    text = (root / "RUNBOOK.md").read_text(encoding="utf-8")
    assert "internal_doc/MAINTAINER_RUNBOOK.md" in text
    assert "SLM maintainer chain" in text


def test_launch_gaps_calls_out_launch_proof_package():
    root = Path(__file__).resolve().parents[1]
    text = (root / "internal_doc" / "LAUNCH_GAPS.md").read_text(encoding="utf-8")
    assert "Launch Proof Package Still Required" in text
    assert "slm_acceptance_checklist.json" in text
    assert "slm_policy.json" in text
    assert ".quality_gate.json" in text
