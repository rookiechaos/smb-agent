from __future__ import annotations

import json
from pathlib import Path

from smbagent.release_records import ensure_release_record_dir, write_release_record_manifest


def test_release_record_manifest_merges_artifacts_into_same_archive(tmp_path: Path):
    generated_at = "2026-06-16T12:34:56Z"
    version = "0.2.0"
    release_dir = ensure_release_record_dir(tmp_path, generated_at=generated_at, smbagent_version=version)
    launch_dir = release_dir / "launch_notes"
    launch_dir.mkdir(parents=True, exist_ok=True)
    pre_dir = release_dir / "pre_release_check"
    pre_dir.mkdir(parents=True, exist_ok=True)
    launch_json = launch_dir / "acme.launch_notes.json"
    launch_md = launch_dir / "acme.launch_notes.md"
    pre_json = pre_dir / "pre_release_check.json"
    pre_md = pre_dir / "pre_release_check.md"
    for path in (launch_json, launch_md, pre_json, pre_md):
        path.write_text("x", encoding="utf-8")

    manifest_path = write_release_record_manifest(
        tmp_path,
        generated_at=generated_at,
        smbagent_version=version,
        artifact_key="launch_notes",
        artifact_title="Launch notes snapshot",
        artifact_paths=[launch_json, launch_md],
        note="customer_id=acme",
    )
    manifest_path = write_release_record_manifest(
        tmp_path,
        generated_at=generated_at,
        smbagent_version=version,
        artifact_key="pre_release_check",
        artifact_title="Pre-release check bundle",
        artifact_paths=[pre_json, pre_md],
        note="formal release review",
    )

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_key = {item["key"]: item for item in payload["artifacts"]}
    assert payload["release_review_slug"] == release_dir.name
    assert payload["archive_dir"].endswith(release_dir.name)
    assert by_key["launch_notes"]["status"] == "present"
    assert by_key["pre_release_check"]["status"] == "present"
    assert by_key["remote_smoke"]["status"] == "reserved"
    assert any(
        path.endswith("launch_notes/acme.launch_notes.json")
        for path in by_key["launch_notes"]["artifact_paths"]
    )
    assert any(
        path.endswith("pre_release_check/pre_release_check.json")
        for path in by_key["pre_release_check"]["artifact_paths"]
    )
