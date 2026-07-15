from pathlib import Path

from smbagent.game_studio import (
    GamePackage,
    enforce_game_package_caps,
    enforce_required_game_artifacts,
    run_all_game_structural_checks,
    validate_game_analytics_events,
    validate_game_scene_manifests,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _populate_minimal_game_package(code: Path) -> None:
    _write(code / "README.md", "# Game package")
    _write(code / "game" / "README.md", "# Game")
    _write(
        code / "game" / "scenes" / "title.scene.json",
        '{"name":"title","purpose":"entry","key_ui":["cta"]}',
    )
    _write(code / "site" / "index.html", "<html><body>site</body></html>")
    _write(code / "assets" / "README.md", "# Assets")
    _write(code / "ops" / "README.md", "# Ops")
    _write(code / "analytics" / "events.json", '{"events":["game_start"]}')


def test_enforce_required_game_artifacts_flags_missing_dirs(tmp_path: Path):
    issues = enforce_required_game_artifacts(tmp_path / "code")
    descs = [i.description for i in issues]
    assert any("code/" in d for d in descs)


def test_enforce_required_game_artifacts_passes_for_minimal_valid_shape(tmp_path: Path):
    code = tmp_path / "code"
    _populate_minimal_game_package(code)
    assert enforce_required_game_artifacts(code) == []


def test_validate_game_scene_manifests_flags_bad_json(tmp_path: Path):
    code = tmp_path / "code"
    _populate_minimal_game_package(code)
    _write(code / "game" / "scenes" / "broken.scene.json", "{not json")
    issues = validate_game_scene_manifests(code)
    assert any("unreadable JSON" in i.description for i in issues)


def test_validate_game_analytics_events_requires_events_array(tmp_path: Path):
    code = tmp_path / "code"
    _populate_minimal_game_package(code)
    _write(code / "analytics" / "events.json", '{"nope": []}')
    issues = validate_game_analytics_events(code)
    assert any("`events` array" in i.description for i in issues)


def test_enforce_game_package_caps_flags_overflow(tmp_path: Path):
    code = tmp_path / "code"
    _populate_minimal_game_package(code)
    for i in range(2, 8):
        _write(
            code / "game" / "scenes" / f"s{i}.scene.json",
            '{"name":"x","purpose":"y","key_ui":["z"]}',
        )
    issues = enforce_game_package_caps(code, GamePackage.LITE)
    assert any("scenes exceed lite cap" in i.description for i in issues)


def test_run_all_game_structural_checks_aggregates_secrets_and_shape(tmp_path: Path):
    code = tmp_path / "code"
    _populate_minimal_game_package(code)
    _write(code / "ops" / "secrets.md", 'api_key="sk-ant-abcdefghijklmnopqrstuvwxyz1234"')
    _write(code / "analytics" / "events.json", "not-json")
    issues = run_all_game_structural_checks(code, GamePackage.CAMPAIGN)
    descs = [i.description for i in issues]
    assert any("hard-coded" in d.lower() or "appears to be hard-coded" in d for d in descs)
    assert any("analytics events file is unreadable JSON" in d for d in descs)
