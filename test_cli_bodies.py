"""Full coverage for cli.py command bodies via CliRunner + mocked agents.

The existing test_cli.py covers help / error paths / a few smoke commands.
This file invokes each command's happy path with mocked agents / services so
the body interiors are exercised (state setup → call → output → exit code).

Pattern: monkeypatch the agent classes / functions imported INTO cli.py
(NOT the source modules) so the CLI body uses our fakes.

Side-effect note: smbagent.config.load_config() resolves workspaces_dir from
__file__, not cwd — so tests that create workspaces write to the real project's
workspaces/ directory. Each test uses a unique `clitest-*` prefix and cleans
up in a finally block.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator

import pytest
from typer.testing import CliRunner

from smbagent.cli import app as cli_app
from smbagent.config import load_config

runner = CliRunner()


@pytest.fixture
def cleanup_workspaces() -> Iterator[list[str]]:
    """Collect customer ids to wipe in teardown."""
    cleanup_ids: list[str] = []
    try:
        yield cleanup_ids
    finally:
        cfg = load_config()
        for cid in cleanup_ids:
            ws_path = cfg.workspaces_dir / cid
            if ws_path.exists():
                shutil.rmtree(ws_path, ignore_errors=True)


# ---- Helpers: shared fake agent / pipeline factories ----


def _populate_qualification(workspace, *, go: bool = True, tier=None):
    from smbagent.types import Qualification, Tier

    q = Qualification(
        customer_id=workspace.customer_id,
        go=go,
        recommended_tier=(tier or (Tier.STARTER if go else None)),
        summary_ja="fake",
    )
    workspace.save_qualification(q)
    return q


def _populate_requirements(workspace, tier=None):
    from smbagent.types import CompanyContext, Requirements, Tier

    req = Requirements(
        customer_id=workspace.customer_id,
        tier=(tier or Tier.STARTER),
        business_name="X",
        summary_ja="x",
        target_users=["x"],
        brand_notes=["y"],
        desired_skills=["s"],
        desired_integrations=["i"],
        acceptance_criteria=["a"],
        company_context=CompanyContext(
            mission="m",
            vision="v",
            values=["kind"],
            current_strategy=["grow"],
            current_priorities=["priority-a"],
            decision_style="careful",
            risk_tolerance="low",
        ),
    )
    workspace.save_requirements(req)
    return req


# ============================================================================
# qualify
# ============================================================================


def test_qualify_command_body_success(monkeypatch, cleanup_workspaces):
    """`smbagent qualify <id> --brief X` invokes QualifyAgent and prints GO."""
    from smbagent.types import Qualification, Tier

    cid = "clitest-qualify-go"
    cleanup_workspaces.append(cid)

    class _FakeQualify:
        def __init__(self, cfg):
            pass

        def run(self, workspace, brief):
            q = Qualification(
                customer_id=workspace.customer_id,
                go=True,
                recommended_tier=Tier.GROWTH,
                summary_ja="fit",
            )
            workspace.save_qualification(q)
            return q

    monkeypatch.setattr("smbagent.cli.QualifyAgent", _FakeQualify)
    r1 = runner.invoke(cli_app, ["new", cid])
    assert r1.exit_code == 0
    r2 = runner.invoke(cli_app, ["qualify", cid, "--brief", "test brief"])
    assert r2.exit_code == 0
    assert "GO" in r2.stdout
    assert "growth" in r2.stdout


def test_qualify_command_no_go_path(monkeypatch, cleanup_workspaces):
    from smbagent.types import Qualification

    cid = "clitest-qualify-nogo"
    cleanup_workspaces.append(cid)

    class _FakeNoGo:
        def __init__(self, cfg):
            pass

        def run(self, workspace, brief):
            q = Qualification(
                customer_id=workspace.customer_id,
                go=False,
                recommended_tier=None,
                summary_ja="not a fit",
            )
            workspace.save_qualification(q)
            return q

    monkeypatch.setattr("smbagent.cli.QualifyAgent", _FakeNoGo)
    runner.invoke(cli_app, ["new", cid])
    result = runner.invoke(cli_app, ["qualify", cid, "--brief", "x"])
    assert result.exit_code == 0
    assert "NO-GO" in result.stdout


# ============================================================================
# run (full pipeline via mocked Pipeline)
# ============================================================================


def test_run_command_invokes_pipeline(monkeypatch, cleanup_workspaces):
    cid = "clitest-run-cust"
    cleanup_workspaces.append(cid)

    invocations: list[dict] = []

    class _FakePipeline:
        def __init__(self, cfg, console=None):
            self.cfg = cfg

        def run(self, customer_id, customer_brief=None, tier_override=None):
            invocations.append(
                {
                    "customer_id": customer_id,
                    "brief": customer_brief,
                    "tier": tier_override,
                }
            )
            return None  # mimic graceful halt

    monkeypatch.setattr("smbagent.cli.Pipeline", _FakePipeline)
    runner.invoke(cli_app, ["new", cid])
    result = runner.invoke(
        cli_app,
        ["run", cid, "--brief", "ACME dental"],
    )
    assert result.exit_code == 0
    assert invocations == [
        {
            "customer_id": cid,
            "brief": "ACME dental",
            "tier": None,
        }
    ]


def test_run_command_with_tier_override(monkeypatch, cleanup_workspaces):
    from smbagent.types import Tier

    cid = "clitest-run-tier"
    cleanup_workspaces.append(cid)

    captured = {}

    class _FakePipeline:
        def __init__(self, cfg, console=None):
            pass

        def run(self, customer_id, customer_brief=None, tier_override=None):
            captured["tier"] = tier_override
            return None

    monkeypatch.setattr("smbagent.cli.Pipeline", _FakePipeline)
    runner.invoke(cli_app, ["new", cid])
    result = runner.invoke(
        cli_app,
        ["run", cid, "--brief", "x", "--tier", "business"],
    )
    assert result.exit_code == 0
    assert captured["tier"] == Tier.BUSINESS


# ============================================================================
# negotiate
# ============================================================================


def test_negotiate_command_uses_qualification_tier(monkeypatch, cleanup_workspaces):
    cid = "clitest-negotiate"
    cleanup_workspaces.append(cid)

    captured = {}

    class _FakeNegotiation:
        def __init__(self, cfg, asr=None, tts=None):
            pass

        def run(self, workspace, tier):
            captured["tier"] = tier

    monkeypatch.setattr("smbagent.cli.NegotiationAgent", _FakeNegotiation)
    runner.invoke(cli_app, ["new", cid])

    # Pre-populate qualification so negotiate can derive tier
    from smbagent.types import Qualification, Tier

    cfg = load_config()
    from smbagent.workspace import Workspace

    ws = Workspace(cid, cfg.workspaces_dir)
    ws.save_qualification(
        Qualification(
            customer_id=cid,
            go=True,
            recommended_tier=Tier.STARTER,
            summary_ja=".",
        )
    )

    result = runner.invoke(cli_app, ["negotiate", cid])
    assert result.exit_code == 0
    assert captured["tier"] == Tier.STARTER


def test_negotiate_command_with_explicit_tier_override(monkeypatch, cleanup_workspaces):
    from smbagent.types import Tier

    cid = "clitest-negotiate-tier"
    cleanup_workspaces.append(cid)

    captured = {}

    class _FakeNegotiation:
        def __init__(self, cfg, asr=None, tts=None):
            pass

        def run(self, workspace, tier):
            captured["tier"] = tier

    monkeypatch.setattr("smbagent.cli.NegotiationAgent", _FakeNegotiation)
    runner.invoke(cli_app, ["new", cid])
    result = runner.invoke(cli_app, ["negotiate", cid, "--tier", "business"])
    assert result.exit_code == 0
    assert captured["tier"] == Tier.BUSINESS


def test_negotiate_command_errors_when_qualification_has_no_tier(
    monkeypatch,
    cleanup_workspaces,
):
    """If qualification.json exists but has recommended_tier=None and no
    override, the CLI must error out cleanly."""
    cid = "clitest-negotiate-no-tier"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])

    # Write a synthetic qualification.json with no tier (bypasses Pydantic
    # since we write the file directly)
    import json

    cfg = load_config()
    (cfg.workspaces_dir / cid / "qualification.json").write_text(
        json.dumps(
            {
                "customer_id": cid,
                "go": False,
                "recommended_tier": None,
                "summary_ja": "x",
                "reasoning_en": "",
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(cli_app, ["negotiate", cid])
    assert result.exit_code != 0


# ============================================================================
# plan
# ============================================================================


def test_plan_command_invokes_plan_agent(monkeypatch, cleanup_workspaces):
    from smbagent.types import (
        AgentSkillSpec,
        IntegrationSpec,
        LandingPageSpec,
        Plan,
        Tier,
    )

    cid = "clitest-plan"
    cleanup_workspaces.append(cid)
    invocations = []

    class _FakePlan:
        def __init__(self, cfg):
            pass

        def run(self, workspace):
            invocations.append(workspace.customer_id)
            plan = Plan(
                tier=Tier.STARTER,
                summary="ok",
                landing_page=LandingPageSpec(
                    pages=["/"],
                    hero_copy_outline="o",
                    primary_cta="c",
                ),
                agent_skills=[
                    AgentSkillSpec(name="understand-x", description="d", system_prompt_outline="o"),
                ],
                integrations=[IntegrationSpec(name="g", purpose="p")],
            )
            workspace.save_plan(plan, plan_md="# plan")
            return plan

    monkeypatch.setattr("smbagent.cli.PlanAgent", _FakePlan)
    runner.invoke(cli_app, ["new", cid])
    # plan requires requirements.json to exist; populate
    cfg = load_config()
    from smbagent.workspace import Workspace

    _populate_requirements(Workspace(cid, cfg.workspaces_dir))

    result = runner.invoke(cli_app, ["plan", cid])
    assert result.exit_code == 0
    assert invocations == [cid]
    assert "skills" in result.stdout
    assert "starter" in result.stdout


# ============================================================================
# validate
# ============================================================================


def test_validate_command_invokes_validation_agent(monkeypatch, cleanup_workspaces):
    from smbagent.types import Verdict

    cid = "clitest-validate"
    cleanup_workspaces.append(cid)
    captured = {}

    class _FakeValidation:
        def __init__(self, cfg):
            pass

        def run(self, workspace, round_n):
            captured["round"] = round_n
            return Verdict(passed=True, round=round_n, summary="ok")

    monkeypatch.setattr("smbagent.cli.ValidationAgent", _FakeValidation)
    runner.invoke(cli_app, ["new", cid])
    result = runner.invoke(cli_app, ["validate", cid, "--round", "3"])
    assert result.exit_code == 0
    assert captured["round"] == 3
    assert '"passed": true' in result.stdout
    assert '"round": 3' in result.stdout


# ============================================================================
# state + replay
# ============================================================================


def test_state_command_prints_state(monkeypatch, cleanup_workspaces):
    cid = "clitest-state"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])

    # Empty workspace → INITIAL
    result = runner.invoke(cli_app, ["state", cid])
    assert result.exit_code == 0
    assert "initial" in result.stdout.lower()
    # No transitions yet
    assert "no transitions" in result.stdout.lower()


def test_state_command_shows_recent_transitions(monkeypatch, cleanup_workspaces):
    cid = "clitest-state-history"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])

    # Inject a couple of transitions
    cfg = load_config()
    from smbagent.observability import TransitionLogger
    from smbagent.workspace import Workspace

    ws = Workspace(cid, cfg.workspaces_dir)
    log = TransitionLogger(ws)
    log.record(
        agent="qualify",
        from_state="initial",
        to_state="qualified_go",
        input_hash="a",
        output_hash="b",
        latency_ms=42,
        success=True,
    )
    log.record(
        agent="negotiation",
        from_state="qualified_go",
        to_state="negotiated",
        input_hash="b",
        output_hash="c",
        latency_ms=100,
        success=True,
    )

    result = runner.invoke(cli_app, ["state", cid])
    assert result.exit_code == 0
    assert "qualify" in result.stdout
    assert "negotiation" in result.stdout
    assert "42ms" in result.stdout or "42" in result.stdout


def test_state_command_errors_when_workspace_missing(cleanup_workspaces):
    result = runner.invoke(cli_app, ["state", "clitest-ghost-state"])
    assert result.exit_code != 0


def test_replay_command_lists_transitions(cleanup_workspaces):
    cid = "clitest-replay-list"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])

    cfg = load_config()
    from smbagent.observability import TransitionLogger
    from smbagent.workspace import Workspace

    ws = Workspace(cid, cfg.workspaces_dir)
    TransitionLogger(ws).record(
        agent="qualify",
        from_state="initial",
        to_state="qualified_go",
        input_hash="a",
        output_hash="b",
        latency_ms=10,
    )

    result = runner.invoke(cli_app, ["replay", cid])
    assert result.exit_code == 0
    assert "qualify" in result.stdout
    assert "initial" in result.stdout


def test_replay_verify_with_no_tampering_passes(cleanup_workspaces):
    cid = "clitest-replay-verify"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])

    cfg = load_config()
    from smbagent.observability import TransitionLogger, hash_file
    from smbagent.types import Qualification, Tier
    from smbagent.workspace import Workspace

    ws = Workspace(cid, cfg.workspaces_dir)
    ws.save_qualification(
        Qualification(
            customer_id=cid,
            go=True,
            recommended_tier=Tier.STARTER,
            summary_ja=".",
        )
    )
    TransitionLogger(ws).record(
        agent="qualify",
        from_state="initial",
        to_state="qualified_go",
        input_hash="a",
        output_hash=hash_file(ws.qualification_path),
        latency_ms=10,
    )

    result = runner.invoke(cli_app, ["replay", cid, "--verify"])
    assert result.exit_code == 0
    assert "mismatches" in result.stdout
    assert "0" in result.stdout  # zero mismatches


def test_replay_verify_with_tampering_exits_nonzero(cleanup_workspaces):
    cid = "clitest-replay-tampered"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])

    cfg = load_config()
    from smbagent.observability import TransitionLogger
    from smbagent.types import Qualification, Tier
    from smbagent.workspace import Workspace

    ws = Workspace(cid, cfg.workspaces_dir)
    ws.save_qualification(
        Qualification(
            customer_id=cid,
            go=True,
            recommended_tier=Tier.STARTER,
            summary_ja=".",
        )
    )
    # Record a wrong hash — simulates tampering after recording
    TransitionLogger(ws).record(
        agent="qualify",
        from_state="initial",
        to_state="qualified_go",
        input_hash="a",
        output_hash="x" * 64,
        latency_ms=10,
    )

    result = runner.invoke(cli_app, ["replay", cid, "--verify"])
    assert result.exit_code == 2  # exit code defined in the CLI
    assert "mismatch" in result.stdout.lower()


def test_replay_command_errors_on_missing_workspace():
    result = runner.invoke(cli_app, ["replay", "clitest-ghost-replay"])
    assert result.exit_code != 0


# ============================================================================
# serve (skills runtime, one-shot)
# ============================================================================


def test_serve_command_routes_message_through_runtime(monkeypatch, cleanup_workspaces):
    cid = "clitest-serve"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])

    from smbagent.runtime import RuntimeResponse

    class _FakeRuntime:
        def __init__(self, ws, cfg):
            pass

        def respond(self, message):
            return RuntimeResponse(
                reply=f"got: {message}",
                skill_used="x",
            )

    monkeypatch.setattr("smbagent.cli.SkillsRuntime", _FakeRuntime)
    result = runner.invoke(cli_app, ["serve", cid, "--message", "hello"])
    assert result.exit_code == 0
    assert "got: hello" in result.stdout
    assert "skill: x" in result.stdout


def test_serve_command_handles_runtime_error(monkeypatch, cleanup_workspaces):
    """When the runtime raises SkillsRuntimeError (e.g. no skills), CLI exits 1."""
    cid = "clitest-serve-empty"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])

    from smbagent.runtime import SkillsRuntimeError

    class _FakeBroken:
        def __init__(self, ws, cfg):
            raise SkillsRuntimeError("no skills loaded")

    monkeypatch.setattr("smbagent.cli.SkillsRuntime", _FakeBroken)
    result = runner.invoke(cli_app, ["serve", cid, "--message", "hi"])
    assert result.exit_code != 0


# ============================================================================
# serve-http (uvicorn startup is mocked)
# ============================================================================


def test_serve_http_invokes_uvicorn(monkeypatch):
    """Mocking the import + uvicorn.run so we don't actually start a server."""
    import types

    captured = {}

    class _FakeUvicorn(types.ModuleType):
        def run(self, app, host, port):
            captured["host"] = host
            captured["port"] = port

    fake_uvicorn = _FakeUvicorn("uvicorn")
    monkeypatch.setitem(__import__("sys").modules, "uvicorn", fake_uvicorn)
    result = runner.invoke(cli_app, ["serve-http", "--host", "127.0.0.1", "--port", "9999"])
    assert result.exit_code == 0
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 9999


def test_serve_http_blocks_bare_lan_posture(monkeypatch):
    import types

    captured = {}

    class _FakeUvicorn(types.ModuleType):
        def run(self, app, host, port):
            captured["host"] = host
            captured["port"] = port

    fake_uvicorn = _FakeUvicorn("uvicorn")
    monkeypatch.setitem(__import__("sys").modules, "uvicorn", fake_uvicorn)
    monkeypatch.setenv("SMBAGENT_SERVE_HOST", "0.0.0.0")
    monkeypatch.setenv("SMBAGENT_MONITOR_EXPOSURE", "lan-only")
    monkeypatch.setenv("SMBAGENT_ALLOW_LAN_MONITOR_FALLBACK", "false")
    result = runner.invoke(cli_app, ["serve-http"])
    assert result.exit_code != 0
    assert captured == {}


def test_serve_http_uvicorn_missing_exits_with_hint(monkeypatch):
    """If uvicorn isn't installed, the CLI tells the operator to install it."""
    import sys

    # Remove uvicorn from sys.modules if cached, then make the import raise.
    monkeypatch.delitem(sys.modules, "uvicorn", raising=False)

    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def fake_import(name, *args, **kwargs):
        if name == "uvicorn":
            raise ImportError("simulated")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    result = runner.invoke(cli_app, ["serve-http"])
    assert result.exit_code != 0


def test_network_posture_command_prints_recommendation(monkeypatch):
    result = runner.invoke(cli_app, ["network-posture", "--customer-id", "demo-co"])
    assert result.exit_code == 0
    assert "preferred_remote_stack: tailscale" in result.stdout


def test_vpn_plan_command_prints_wireguard_secondary(monkeypatch):
    result = runner.invoke(cli_app, ["vpn-plan", "--customer-id", "demo-co"])
    assert result.exit_code == 0
    assert "secondary_remote_stack: wireguard" in result.stdout


# ============================================================================
# book
# ============================================================================


def test_book_command_creates_event(monkeypatch, cleanup_workspaces):
    cid = "clitest-book"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])

    from smbagent.transports import BookingResult

    captured = {}

    class _FakeForwarder:
        def __init__(self, ws, integration):
            captured["integration"] = integration

        def book(self, req):
            captured["summary"] = req.summary
            captured["attendees"] = list(req.attendees)
            return BookingResult(event_id="evt-321", html_url="https://x.example/evt")

    monkeypatch.setattr("smbagent.cli.BookingForwarder", _FakeForwarder)

    result = runner.invoke(
        cli_app,
        [
            "book",
            cid,
            "--integration",
            "book-viewing",
            "--summary",
            "Cleaning - Yamada-san",
            "--start",
            "2026-06-01T10:00:00+09:00",
            "--end",
            "2026-06-01T11:00:00+09:00",
            "--attendee",
            "yamada@example.com",
            "--description",
            "Annual checkup",
        ],
    )
    assert result.exit_code == 0
    assert "evt-321" in result.stdout
    assert "https://x.example/evt" in result.stdout
    assert captured["integration"] == "book-viewing"
    assert captured["summary"] == "Cleaning - Yamada-san"
    assert captured["attendees"] == ["yamada@example.com"]


def test_book_command_invalid_datetime_errors(cleanup_workspaces):
    cid = "clitest-book-bad-date"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])
    result = runner.invoke(
        cli_app,
        [
            "book",
            cid,
            "--integration",
            "x",
            "--summary",
            "s",
            "--start",
            "not-a-date",
            "--end",
            "also-bad",
        ],
    )
    assert result.exit_code != 0


def test_book_command_blocked_for_external_transport_by_default(cleanup_workspaces):
    cid = "clitest-book-hitl"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])
    cfg = load_config()
    integ = cfg.workspaces_dir / cid / "code" / "integrations" / "book-viewing"
    integ.mkdir(parents=True, exist_ok=True)
    (integ / "config.json").write_text('{"transport":"google-calendar"}', encoding="utf-8")

    result = runner.invoke(
        cli_app,
        [
            "book",
            cid,
            "--integration",
            "book-viewing",
            "--summary",
            "Cleaning - Yamada-san",
            "--start",
            "2026-06-01T10:00:00+09:00",
            "--end",
            "2026-06-01T11:00:00+09:00",
        ],
    )
    assert result.exit_code != 0
    assert "governance policy" in result.stdout


def test_book_command_forwarder_error_exits_nonzero(monkeypatch, cleanup_workspaces):
    cid = "clitest-book-error"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])

    from smbagent.transports import BookingTransportError

    class _FakeBroken:
        def __init__(self, ws, integration):
            raise BookingTransportError("config missing")

    monkeypatch.setattr("smbagent.cli.BookingForwarder", _FakeBroken)
    result = runner.invoke(
        cli_app,
        [
            "book",
            cid,
            "--integration",
            "x",
            "--summary",
            "s",
            "--start",
            "2026-06-01T10:00:00+09:00",
            "--end",
            "2026-06-01T11:00:00+09:00",
        ],
    )
    assert result.exit_code != 0


# ============================================================================
# deploy — success path with mocked target
# ============================================================================


def test_deploy_command_invokes_resolved_target(monkeypatch, cleanup_workspaces):
    cid = "clitest-deploy"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])

    # Populate a minimal landing-page so the deploy target has something to work on
    cfg = load_config()
    code = cfg.workspaces_dir / cid / "code" / "landing-page"
    code.mkdir(parents=True, exist_ok=True)
    (code / "index.html").write_text("<html/>", encoding="utf-8")

    from smbagent.deploy.base import DeployResult

    class _FakeTarget:
        name = "fake-target"

        def deploy(self, workspace):
            return DeployResult(
                target=self.name,
                url="https://fake.example/site",
                artifact_path=None,
                log="ok",
            )

    monkeypatch.setattr("smbagent.cli.resolve_target", lambda name: _FakeTarget())
    result = runner.invoke(cli_app, ["deploy", cid, "--target", "tarball"])
    assert result.exit_code == 0
    assert "https://fake.example/site" in result.stdout


def test_deploy_command_blocks_external_hosted_target_by_default(cleanup_workspaces):
    cid = "clitest-deploy-hitl"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])
    cfg = load_config()
    code = cfg.workspaces_dir / cid / "code" / "landing-page"
    code.mkdir(parents=True, exist_ok=True)
    (code / "index.html").write_text("<html/>", encoding="utf-8")

    result = runner.invoke(cli_app, ["deploy", cid, "--target", "vercel"])
    assert result.exit_code != 0
    assert "governance policy" in result.stdout


# ============================================================================
# send — success path with mocked MailForwarder
# ============================================================================


def test_send_command_invokes_mail_forwarder(monkeypatch, cleanup_workspaces):
    cid = "clitest-send"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])

    captured = {}

    class _FakeForwarder:
        def __init__(self, ws, integration_name, transport=None):
            captured["integration"] = integration_name

        def forward(self, to, subject, body, sender=None, reply_to=None):
            captured["to"] = to
            captured["subject"] = subject
            captured["body"] = body
            captured["sender"] = sender

    monkeypatch.setattr("smbagent.cli.MailForwarder", _FakeForwarder)
    result = runner.invoke(
        cli_app,
        [
            "send",
            cid,
            "--integration",
            "forward-to-clinic",
            "--to",
            "ops@example.com",
            "--subject",
            "lead",
            "--body",
            "form data",
            "--from",
            "noreply@biz.com",
        ],
    )
    assert result.exit_code == 0
    assert "Sent to ops@example.com" in result.stdout
    assert captured["integration"] == "forward-to-clinic"
    assert captured["subject"] == "lead"
    assert captured["sender"] == "noreply@biz.com"


def test_context_update_command_writes_snapshot_and_log(cleanup_workspaces):
    cid = "clitest-context-update"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])
    cfg = load_config()
    ws = cfg.workspaces_dir / cid
    from smbagent.workspace import Workspace

    _populate_requirements(Workspace(cid, cfg.workspaces_dir))

    result = runner.invoke(
        cli_app,
        [
            "context-update",
            cid,
            "--note",
            "quarterly refresh",
            "--mission",
            "support local clinics",
            "--vision",
            "be the most trusted neighborhood clinic",
            "--value",
            "kindness",
            "--strategy",
            "improve conversion",
            "--priority",
            "reduce booking friction",
            "--decision-style",
            "careful but practical",
            "--risk-tolerance",
            "low",
        ],
    )
    assert result.exit_code == 0
    assert "Updated company context" in result.stdout
    assert (ws / "company_context.json").exists()
    assert (ws / "company_context_updates.jsonl").exists()
    body = (ws / "company_context.json").read_text(encoding="utf-8")
    assert "support local clinics" in body
    assert "reduce booking friction" in body


def test_send_command_blocked_for_external_transport_by_default(cleanup_workspaces):
    cid = "clitest-send-hitl"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])
    cfg = load_config()
    integ = cfg.workspaces_dir / cid / "code" / "integrations" / "forward-to-clinic"
    integ.mkdir(parents=True, exist_ok=True)
    (integ / "config.json").write_text('{"transport":"smtp"}', encoding="utf-8")

    result = runner.invoke(
        cli_app,
        [
            "send",
            cid,
            "--integration",
            "forward-to-clinic",
            "--to",
            "ops@example.com",
            "--subject",
            "lead",
            "--body",
            "form data",
        ],
    )
    assert result.exit_code != 0
    assert "governance policy" in result.stdout


# ============================================================================
# auth-issue + auth-show
# ============================================================================


def test_auth_show_prints_token_for_existing_workspace(cleanup_workspaces):
    cid = "clitest-auth-show"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])
    issue_result = runner.invoke(cli_app, ["auth-issue", cid])
    assert issue_result.exit_code == 0

    show_result = runner.invoke(cli_app, ["auth-show", cid])
    assert show_result.exit_code == 0
    assert "token:" in show_result.stdout


def test_auth_issue_force_rotates(cleanup_workspaces):
    cid = "clitest-auth-rotate"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])

    r1 = runner.invoke(cli_app, ["auth-issue", cid])
    r2 = runner.invoke(cli_app, ["auth-issue", cid, "--force"])
    assert r1.exit_code == 0 and r2.exit_code == 0
    # Different outputs (different tokens) — extract via prefix
    import re

    t1 = re.search(r"Token for \S+:\s*(\S+)", r1.stdout)
    t2 = re.search(r"Token for \S+:\s*(\S+)", r2.stdout)
    assert t1 and t2
    assert t1.group(1) != t2.group(1)


# ============================================================================
# portal + dashboard happy paths
# ============================================================================


def test_portal_command_for_populated_workspace(monkeypatch, cleanup_workspaces):
    cid = "clitest-portal"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])

    # Populate qualification so portal has something to render
    cfg = load_config()
    from smbagent.workspace import Workspace

    ws = Workspace(cid, cfg.workspaces_dir)
    _populate_qualification(ws)

    result = runner.invoke(cli_app, ["portal", cid])
    assert result.exit_code == 0
    assert "portal.html" in result.stdout
    assert (ws.path / "portal.html").exists()


def test_dashboard_command_with_multiple_customers(cleanup_workspaces):
    a = "clitest-dash-a"
    b = "clitest-dash-b"
    cleanup_workspaces.extend([a, b])
    runner.invoke(cli_app, ["new", a])
    runner.invoke(cli_app, ["new", b])

    result = runner.invoke(cli_app, ["dashboard"])
    assert result.exit_code == 0
    cfg = load_config()
    dash_html = (cfg.workspaces_dir / "dashboard.html").read_text(encoding="utf-8")
    assert a in dash_html and b in dash_html


# ============================================================================
# template materialize happy path
# ============================================================================


def test_template_materialize_command(cleanup_workspaces):
    cid = "clitest-template"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])
    result = runner.invoke(cli_app, ["template", "materialize", "dental", "--customer", cid])
    assert result.exit_code == 0
    assert "Materialized" in result.stdout

    cfg = load_config()
    # Verify one of the dental skill files materialized
    expected = cfg.workspaces_dir / cid / "code" / "agent-skills" / "understand-dental.md"
    assert expected.exists()


def test_template_materialize_overlay_mode(cleanup_workspaces):
    """The overlay mode branch isn't hit by default 'seed'. Cover it explicitly."""
    cid = "clitest-template-overlay"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])
    # Materialize once
    runner.invoke(cli_app, ["template", "materialize", "dental", "--customer", cid])
    # Now overlay — should report overwritten files
    result = runner.invoke(
        cli_app,
        [
            "template",
            "materialize",
            "dental",
            "--customer",
            cid,
            "--mode",
            "overlay",
        ],
    )
    assert result.exit_code == 0
    assert "overwritten" in result.stdout
