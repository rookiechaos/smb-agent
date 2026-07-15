from __future__ import annotations

from smbagent.voice_hardening import (
    evaluate_legal_launch_checklist,
    read_consent_records,
    sanitize_transcript_for_cloud,
    write_consent_record,
)


def test_sanitize_transcript_for_cloud_redacts_common_patterns():
    result = sanitize_transcript_for_cloud(
        "mail me at a@example.com or call +1 415-555-1234 https://example.com 12345678"
    )
    assert "[REDACTED_EMAIL]" in result.sanitized_text
    assert "[REDACTED_PHONE]" in result.sanitized_text
    assert "[REDACTED_URL]" in result.sanitized_text
    assert "[REDACTED_ID]" in result.sanitized_text


def test_write_consent_record_appends_jsonl(workspace):
    path = write_consent_record(
        workspace,
        workflow="gps_voice_daily_report",
        operator="human:alice",
        basis="employee_notice",
        note="approved pilot",
        scopes=["gps", "voice"],
    )
    assert path.exists()
    rows = read_consent_records(workspace)
    assert rows[-1].workflow == "gps_voice_daily_report"
    assert rows[-1].scopes == ["gps", "voice"]


def test_evaluate_legal_launch_checklist_flags_attestation_gaps(config, workspace):
    report = evaluate_legal_launch_checklist(config, workspace)
    assert report["launch_ready"] is False
    by_key = {item["key"]: item for item in report["items"]}
    assert by_key["operator_attestations"]["passed"] is False


def test_evaluate_legal_launch_checklist_passes_with_attestations(config, workspace):
    cfg = type(config)(
        **{
            **config.__dict__,
            "launch_acceptance_confirmed": True,
            "filevault_confirmed": True,
        }
    )
    report = evaluate_legal_launch_checklist(cfg, workspace)
    assert report["launch_ready"] is True
