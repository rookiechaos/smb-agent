"""Tests for the lower-priority polish items.

- __version__ propagation + CHANGELOG presence
- Workspace schema migration framework
- Graceful server reload endpoint
- Body-size limit middleware
- Demo sample workspace integrity
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from smbagent import __version__
from smbagent.auth import issue_token
from smbagent.cli import app as cli_app
from smbagent.config import Config
from smbagent.migrations import (
    MIGRATIONS,
    SCHEMA_VERSION,
    WorkspaceMeta,
    meta_path,
    migrate_workspace,
    read_meta,
    write_meta,
)
from smbagent.server import create_app
from smbagent.workspace import Workspace

REPO_ROOT = Path(__file__).resolve().parent.parent


# ============================================================================
# __version__ + CHANGELOG
# ============================================================================


def test_version_is_a_semver_string():
    assert isinstance(__version__, str)
    parts = __version__.split(".")
    assert len(parts) >= 2
    assert all(p.isdigit() or "-" in p or "+" in p for p in parts)


def test_version_is_at_least_0_2_0():
    """Sanity: we've bumped past the initial 0.1.0 release."""
    parts = tuple(int(p) for p in __version__.split(".")[:3])
    assert parts >= (0, 2, 0)


def test_changelog_exists_and_mentions_current_version():
    cl = REPO_ROOT / "CHANGELOG.md"
    assert cl.exists()
    body = cl.read_text(encoding="utf-8")
    assert f"[{__version__}]" in body


def test_changelog_keeps_0_1_0_entry_intact():
    """Releases are append-only — never drop old entries."""
    body = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "[0.1.0]" in body


# ---- LAUNCH.md operator runbook ----


def test_launch_md_exists():
    assert (REPO_ROOT / "LAUNCH.md").exists()


def test_launch_md_references_key_commands():
    """LAUNCH.md is the operator's runbook — if it drifts away from the actual
    CLI, the runbook becomes a lie. This test keeps the doc honest.

    Every command referenced must actually exist as a smbagent subcommand.
    """
    body = (REPO_ROOT / "LAUNCH.md").read_text(encoding="utf-8")
    expected_commands = [
        "smbagent doctor",
        "smbagent dashboard",
        "smbagent state",
        "smbagent replay",
        "smbagent portal",
        "smbagent auth-issue",
        "smbagent deploy",
        "smbagent serve-http",
        "smbagent migrate",
        "smbagent run",
        "smbagent qualify",
        "smbagent negotiate",
    ]
    missing = [c for c in expected_commands if c not in body]
    assert missing == [], f"LAUNCH.md fails to reference: {missing}"


def test_launch_md_references_sibling_docs():
    """The operator's runbook should point at the other docs it complements."""
    body = (REPO_ROOT / "LAUNCH.md").read_text(encoding="utf-8")
    for doc in ("PIONEER.md", "CHANGELOG.md", "SECURITY.md"):
        assert doc in body, f"LAUNCH.md fails to reference {doc}"


def test_launch_md_mentions_critical_env_vars():
    """The runbook must surface the env vars an operator actually needs to know
    about during a real incident."""
    body = (REPO_ROOT / "LAUNCH.md").read_text(encoding="utf-8")
    for var in (
        "SMBAGENT_VALIDATION_CMD",  # codex flag override fix
        "SMBAGENT_CORS_ORIGINS",  # widget connection-error fix
        "SMBAGENT_CHAT_RATE_PER_MINUTE",  # 429 fix
        "SMBAGENT_ASR_BACKEND",  # voice setup
    ):
        assert var in body, f"LAUNCH.md doesn't mention {var}"


def test_launch_md_has_rollback_section():
    """Critical for production: the runbook needs to tell the operator how to
    back out cleanly when something breaks on a live customer site."""
    body = (REPO_ROOT / "LAUNCH.md").read_text(encoding="utf-8").lower()
    assert "rollback" in body
    # Should mention at least one specific rollback technique
    assert "revoke" in body or "auth-issue" in body


# ---- README.md ----


def test_readme_exists():
    assert (REPO_ROOT / "README.md").exists()


def test_readme_mentions_current_version():
    """README's status block should reflect the actual __version__ — keeps the
    headline number from getting stale."""
    body = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert __version__ in body


def test_readme_references_sibling_docs():
    """README is the index; it must point at the deeper docs."""
    body = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    for doc in ("LAUNCH.md", "PIONEER.md", "SECURITY.md", "CHANGELOG.md"):
        assert doc in body, f"README doesn't reference {doc}"


def test_readme_mentions_demo_workspace():
    """The demo workspace is a key selling point — prospects browse it before
    signing. README must point at it."""
    body = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "demo-tokyo-dental" in body or "examples/" in body


def test_readme_quickstart_commands_exist():
    """Every command in the README's Quickstart must be a real subcommand."""
    body = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    # Commands the quickstart section references
    for cmd in (
        "smbagent doctor",
        "smbagent new",
        "smbagent qualify",
        "smbagent run",
        "smbagent state",
        "smbagent auth-issue",
        "smbagent deploy",
        "smbagent serve-http",
    ):
        assert cmd in body, f"README quickstart drops {cmd!r}"


def test_readme_mentions_pipeline_stages():
    """The pipeline diagram is core orientation — verify all 5 stages are named."""
    body = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    for stage in ("Qualify", "Negotiat", "Plan", "Coding", "Validation"):
        assert stage in body, f"README pipeline missing {stage!r}"


# ---- .env.example completeness ----


def _env_vars_referenced_in_load_config() -> set[str]:
    """Scan config.py for every SMBAGENT_* / API key env var name read."""
    import re

    body = (REPO_ROOT / "smbagent" / "config.py").read_text(encoding="utf-8")
    return set(re.findall(r'os\.environ\.get\(\s*"([A-Z][A-Z0-9_]*)"', body))


def test_env_example_documents_every_var_load_config_reads():
    """Operators won't know features exist if .env.example doesn't list the vars."""
    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    referenced = _env_vars_referenced_in_load_config()
    missing = [v for v in sorted(referenced) if v not in env_example]
    assert missing == [], f".env.example is missing documentation for: {missing}"


def test_env_example_has_required_keys_at_top():
    """The two required keys must be among the first two declared, for operator UX."""
    body = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    lines = [line for line in body.splitlines() if "=" in line and not line.strip().startswith("#")]
    assert lines, ".env.example has no var declarations"
    first_two = " ".join(lines[:2])
    assert "ANTHROPIC_API_KEY=" in first_two
    assert "OPENAI_API_KEY=" in first_two


def test_cli_version_flag_prints_version():
    runner = CliRunner()
    result = runner.invoke(cli_app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_server_root_response_includes_version(config: Config):
    app = create_app(config)
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["version"] == __version__


def test_server_response_header_includes_version(config: Config):
    app = create_app(config)
    with TestClient(app) as client:
        r = client.get("/healthz")
        assert r.headers.get("x-smbagent-version") == __version__


def test_admin_health_includes_version(config: Config):
    cfg = replace(config, admin_token="t")
    app = create_app(cfg)
    with TestClient(app) as client:
        r = client.get("/admin/health", headers={"Authorization": "Bearer t"})
        assert r.status_code == 200
        assert r.json()["version"] == __version__


# ============================================================================
# Migration framework
# ============================================================================


def test_schema_version_is_at_least_1():
    assert SCHEMA_VERSION >= 1


def test_migrations_registry_complete():
    """For every version below SCHEMA_VERSION, there must be a migration registered."""
    for v in range(1, SCHEMA_VERSION):
        assert v in MIGRATIONS, f"no migration registered for {v}→{v + 1}"


def test_write_meta_creates_file(config: Config, workspace: Workspace):
    meta = write_meta(workspace)
    assert meta.schema_version == SCHEMA_VERSION
    assert meta.smbagent_version_at_creation == __version__
    assert meta_path(workspace).exists()


def test_read_meta_returns_none_when_absent(config: Config, workspace: Workspace):
    # ensure() didn't write meta — that's the new() command's job
    assert read_meta(workspace) is None


def test_read_meta_round_trip(config: Config, workspace: Workspace):
    written = write_meta(workspace)
    loaded = read_meta(workspace)
    assert loaded == written


def test_read_meta_returns_none_on_malformed(config: Config, workspace: Workspace):
    meta_path(workspace).write_text("not json", encoding="utf-8")
    assert read_meta(workspace) is None


def test_migrate_workspace_noop_when_already_current(config: Config, workspace: Workspace):
    write_meta(workspace)
    report = migrate_workspace(workspace)
    assert report.from_version == SCHEMA_VERSION
    assert report.to_version == SCHEMA_VERSION
    assert report.applied == []


def test_migrate_workspace_stamps_meta_on_fresh_workspace(config: Config, workspace: Workspace):
    """Without a meta file, the framework assumes current version and stamps it."""
    assert not meta_path(workspace).exists()
    report = migrate_workspace(workspace)
    assert report.applied == []
    # And the meta file is now there.
    assert meta_path(workspace).exists()


def test_migrate_workspace_rejects_newer_version(config: Config, workspace: Workspace):
    """If the workspace was written by a newer smbagent, refuse to touch it."""
    workspace.ensure()
    meta_path(workspace).write_text(
        WorkspaceMeta(
            schema_version=SCHEMA_VERSION + 10,
            created_at="2099-01-01T00:00:00Z",
            smbagent_version_at_creation="99.9.9",
        ).as_json(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as excinfo:
        migrate_workspace(workspace)
    assert "newer" in str(excinfo.value).lower() or "supports up to" in str(excinfo.value).lower()


def test_new_cli_command_stamps_meta(monkeypatch, tmp_path: Path):
    """`smbagent new <id>` must record the schema version, not just create dirs."""
    from smbagent.config import load_config

    monkeypatch.chdir(tmp_path)
    (tmp_path / "smbagent").mkdir()
    (tmp_path / "workspaces").mkdir()
    runner = CliRunner()
    # Use a unique id to avoid colliding with anyone else's workspace
    customer_id = "polish-test-fresh-cust"
    result = runner.invoke(cli_app, ["new", customer_id])
    assert result.exit_code == 0

    cfg = load_config()
    meta = cfg.workspaces_dir / customer_id / ".workspace_meta.json"
    try:
        assert meta.exists()
        import json

        assert json.loads(meta.read_text())["schema_version"] == SCHEMA_VERSION
    finally:
        # Cleanup so we don't leave junk in the real workspaces dir
        import shutil

        ws_dir = cfg.workspaces_dir / customer_id
        if ws_dir.exists():
            shutil.rmtree(ws_dir, ignore_errors=True)


def test_migrate_cli_command_runs(monkeypatch, tmp_path: Path):
    from smbagent.config import load_config

    monkeypatch.chdir(tmp_path)
    (tmp_path / "smbagent").mkdir()
    (tmp_path / "workspaces").mkdir()
    runner = CliRunner()
    cid = "polish-test-migrate-x"
    cfg = load_config()
    try:
        runner.invoke(cli_app, ["new", cid])
        result = runner.invoke(cli_app, ["migrate", cid])
        assert result.exit_code == 0
        # Already current → nothing to do
        assert "already" in result.stdout or "current" in result.stdout
    finally:
        import shutil

        shutil.rmtree(cfg.workspaces_dir / cid, ignore_errors=True)


def test_migrate_cli_errors_on_unknown_workspace(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "smbagent").mkdir()
    (tmp_path / "workspaces").mkdir()
    runner = CliRunner()
    result = runner.invoke(cli_app, ["migrate", "ghost"])
    assert result.exit_code != 0


# ============================================================================
# Graceful server reload
# ============================================================================


@pytest.fixture
def admin_client(config: Config) -> Iterator[TestClient]:
    cfg = replace(config, admin_token="t")
    app = create_app(cfg)
    with TestClient(app) as client:
        yield client


def test_admin_reload_requires_admin_token(config: Config):
    app = create_app(config)  # admin_token=None
    with TestClient(app) as client:
        r = client.post("/admin/reload")
        assert r.status_code == 503


def test_admin_reload_401_with_wrong_token(admin_client: TestClient):
    r = admin_client.post("/admin/reload", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_admin_reload_clears_runtime_cache(admin_client: TestClient, config: Config):
    """Build a runtime, then reload, then verify the cache is empty."""
    cfg = replace(config, admin_token="t")
    ws = Workspace("cache-cust", cfg.workspaces_dir)
    ws.ensure()
    token = issue_token(ws).token

    # First request: populates cache
    r1 = admin_client.get(
        "/v1/customers/cache-cust/skills",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 200
    assert "cache-cust" in admin_client.app.state.runtime_cache

    # Reload
    r = admin_client.post("/admin/reload", headers={"Authorization": "Bearer t"})
    assert r.status_code == 200
    body = r.json()
    assert body["cleared_runtimes"] >= 1
    assert body["version"] == __version__
    assert admin_client.app.state.runtime_cache == {}


def test_admin_reload_on_empty_cache_is_safe(admin_client: TestClient):
    r = admin_client.post("/admin/reload", headers={"Authorization": "Bearer t"})
    assert r.status_code == 200
    assert r.json()["cleared_runtimes"] == 0


# ============================================================================
# Body-size limit middleware
# ============================================================================


@pytest.fixture
def small_body_client(config: Config) -> Iterator[TestClient]:
    """Server config with a tight body-size cap for easy testing."""
    cfg = replace(config, max_body_bytes=500)
    app = create_app(cfg)
    with TestClient(app) as client:
        yield client


def test_body_size_under_limit_allowed(small_body_client: TestClient):
    payload = {
        "business_name": "X co",
        "contact_email": "x@y.com",
        "brief": "x" * 50,
    }
    r = small_body_client.post("/v1/onboard", json=payload)
    # Any status other than 413 is fine — we're testing the body-size middleware,
    # not the onboarding logic.
    assert r.status_code != 413


def test_body_size_over_limit_returns_413(small_body_client: TestClient):
    huge = {
        "business_name": "X co",
        "contact_email": "x@y.com",
        "brief": "x" * 1000,  # body > 500 bytes
    }
    r = small_body_client.post("/v1/onboard", json=huge)
    assert r.status_code == 413
    assert "exceeds" in r.json()["detail"]


def test_get_requests_not_affected_by_body_limit(small_body_client: TestClient):
    r = small_body_client.get("/healthz")
    assert r.status_code == 200


def test_default_body_limit_allows_normal_chat(config: Config):
    """Default 1MB should comfortably allow a typical chat message."""
    app = create_app(config)  # uses default 1MB
    ws = Workspace("body-cust", config.workspaces_dir)
    ws.ensure()
    token = issue_token(ws).token

    with TestClient(app) as client:
        r = client.post(
            "/v1/customers/body-cust/chat",
            json={"message": "hi there, normal length message"},
            headers={"Authorization": f"Bearer {token}"},
        )
        # 503 (no skills) is OK; 413 would mean the limit is wrong.
        assert r.status_code != 413


# ============================================================================
# Demo workspace integrity
# ============================================================================


DEMO_ROOT = REPO_ROOT / "examples" / "demo-tokyo-dental"


def test_demo_workspace_directory_exists():
    assert DEMO_ROOT.is_dir()


def test_demo_workspace_has_all_artifacts():
    expected = [
        ".workspace_meta.json",
        "qualification.json",
        "requirements.json",
        "transcript.txt",
        "plan.md",
        "tasks.json",
        "code/README.md",
        "code/landing-page/index.html",
        "code/landing-page/booking.html",
        "code/agent-skills/understand-white-dental.md",
        "code/agent-skills/book-appointment.md",
        "code/agent-skills/answer-faq.md",
        "code/agent-skills/follow-up.md",
        "code/integrations/forward-to-clinic/README.md",
        "code/integrations/forward-to-clinic/config.example.json",
        "code/integrations/book-viewing/README.md",
        "code/integrations/book-viewing/config.example.json",
        "runs/round-1/verdict.json",
        "runs/round-1/feedback.md",
    ]
    for rel in expected:
        path = DEMO_ROOT / rel
        assert path.exists(), f"demo workspace missing {rel}"


def test_demo_workspace_skills_pass_frontmatter_validator():
    """Run our own structural checks on the demo. If they fail, the demo is misleading."""
    from smbagent.safety import validate_skill_frontmatter

    issues = validate_skill_frontmatter(DEMO_ROOT / "code")
    assert issues == [], f"demo skills have bad frontmatter: {[i.description for i in issues]}"


def test_demo_workspace_no_secrets():
    from smbagent.safety import scan_for_secrets

    issues = scan_for_secrets(DEMO_ROOT / "code")
    assert issues == [], f"demo has secret-shaped values: {[i.description for i in issues]}"


def test_demo_workspace_respects_growth_tier_caps():
    from smbagent.safety import enforce_tier_caps
    from smbagent.types import Tier

    issues = enforce_tier_caps(DEMO_ROOT / "code", Tier.GROWTH)
    assert issues == [], f"demo exceeds growth caps: {[i.description for i in issues]}"


def test_demo_workspace_required_artifacts_present():
    from smbagent.safety import enforce_required_artifacts

    issues = enforce_required_artifacts(DEMO_ROOT / "code")
    assert issues == [], f"demo missing required artifacts: {[i.description for i in issues]}"


def test_demo_qualification_loads_as_pydantic_model():
    from smbagent.types import Qualification

    raw = (DEMO_ROOT / "qualification.json").read_text(encoding="utf-8")
    q = Qualification.model_validate_json(raw)
    assert q.go is True
    assert q.customer_id == "demo-tokyo-dental"


def test_demo_requirements_loads_as_pydantic_model():
    from smbagent.types import Requirements

    raw = (DEMO_ROOT / "requirements.json").read_text(encoding="utf-8")
    req = Requirements.model_validate_json(raw)
    assert req.tier.value == "growth"
    assert req.business_name == "デモ東京ホワイトデンタル"


def test_demo_plan_loads_as_pydantic_model():
    from smbagent.types import Plan

    raw = (DEMO_ROOT / "tasks.json").read_text(encoding="utf-8")
    p = Plan.model_validate_json(raw)
    assert p.tier.value == "growth"
    assert len(p.agent_skills) == 4
    assert any(s.name.startswith("understand-") for s in p.agent_skills)


def test_demo_verdict_loads_as_pydantic_model():
    from smbagent.types import Verdict

    raw = (DEMO_ROOT / "runs" / "round-1" / "verdict.json").read_text(encoding="utf-8")
    v = Verdict.model_validate_json(raw)
    assert v.passed is True
    assert v.tooling_error is None


def test_demo_meta_records_schema_version():
    import json

    raw = (DEMO_ROOT / ".workspace_meta.json").read_text(encoding="utf-8")
    meta = json.loads(raw)
    assert meta["schema_version"] == SCHEMA_VERSION
