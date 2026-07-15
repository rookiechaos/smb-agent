from __future__ import annotations

import json
import subprocess
import sys
import types
from dataclasses import replace
from typing import Any

from smbagent.agents import validation as validation_mod
from smbagent.agents.validation import ValidationAgent
from smbagent.config import Config
from smbagent.types import CompanyContext
from smbagent.workspace import Workspace
from tests._popen_mocks import (  # noqa: E402
    make_codex_popen as _fake_codex,
)
from tests._popen_mocks import (
    popen_from_run,
)

# ---- happy paths ----


def test_validation_snapshot_contains_public_inputs_only(config: Config, workspace: Workspace):
    workspace.requirements_path.write_text('{"customer_id":"x"}', encoding="utf-8")
    workspace.company_context_path.write_text('{"mission":"m"}', encoding="utf-8")
    workspace.plan_path.write_text("private plan artifact but public to both agents", encoding="utf-8")
    workspace.tasks_path.write_text('{"tasks":[]}', encoding="utf-8")
    workspace.coding_log_path(1).write_text("claude private reasoning", encoding="utf-8")
    (workspace.code_dir / "README.md").write_text("customer file", encoding="utf-8")

    snapshot = ValidationAgent(config)._prepare_validation_snapshot(workspace, round_n=1)

    assert (snapshot / "requirements.json").exists()
    assert (snapshot / "company_context.json").exists()
    assert (snapshot / "public_plan.md").exists()
    assert (snapshot / "public_tasks.json").exists()
    assert (snapshot / "code" / "README.md").exists()
    assert not (snapshot / "runs").exists()
    assert not (snapshot / "coding.log").exists()
    assert "claude private reasoning" not in "\n".join(
        p.read_text(encoding="utf-8") for p in snapshot.rglob("*") if p.is_file()
    )


def test_validation_cli_runs_from_snapshot_code_dir(monkeypatch, config: Config, workspace: Workspace):
    seen: dict[str, str] = {}

    def fake_run(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
        seen["cwd"] = str(cwd)
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=json.dumps({"passed": True, "summary": "ok", "issues": []}),
            stderr="",
        )

    (workspace.code_dir / "README.md").write_text("customer file", encoding="utf-8")
    monkeypatch.setattr(validation_mod.subprocess, "Popen", popen_from_run(fake_run))

    ValidationAgent(config).run(workspace, round_n=1)

    assert seen["cwd"].endswith("runs/round-1/validation_snapshot/code")
    assert seen["cwd"] != str(workspace.code_dir)


def test_passes_when_codex_writes_valid_passed_verdict(monkeypatch, config: Config, workspace: Workspace):
    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        _fake_codex(
            workspace,
            round_n=1,
            write_verdict={"passed": True, "summary": "looks good", "issues": []},
        ),
    )
    agent = ValidationAgent(config)
    verdict = agent.run(workspace, round_n=1)

    assert verdict.passed is True
    assert verdict.tooling_error is None
    assert verdict.round == 1
    assert verdict.summary == "looks good"
    assert verdict.issues == []


def test_parses_issues_with_all_fields(monkeypatch, config: Config, workspace: Workspace):
    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        _fake_codex(
            workspace,
            round_n=3,
            write_verdict={
                "passed": False,
                "summary": "missing feature",
                "issues": [
                    {
                        "severity": "critical",
                        "file": "app.py",
                        "line": 12,
                        "description": "endpoint missing",
                        "suggested_fix": "add POST /widgets",
                    },
                    {"severity": "minor", "description": "no docstring"},
                ],
            },
        ),
    )
    agent = ValidationAgent(config)
    verdict = agent.run(workspace, round_n=3)

    assert verdict.passed is False
    assert verdict.round == 3
    assert len(verdict.issues) == 2
    assert verdict.issues[0].severity == "critical"
    assert verdict.issues[0].file == "app.py"
    assert verdict.issues[0].line == 12
    assert verdict.issues[1].severity == "minor"
    assert verdict.issues[1].file is None


def test_invokes_codex_with_correct_command_and_cwd(monkeypatch, config: Config, workspace: Workspace):
    """The agent must invoke `validation_cmd + [prompt]` inside workspace/code/."""
    captured: dict[str, Any] = {}

    def spy_run(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        workspace.verdict_path(1).write_text(
            json.dumps({"passed": True, "summary": "", "issues": []}), encoding="utf-8"
        )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(validation_mod.subprocess, "Popen", popen_from_run(spy_run))
    ValidationAgent(config).run(workspace, round_n=1)

    assert captured["cmd"][: len(config.validation_cmd)] == config.validation_cmd
    # prompt is appended as the last arg
    assert isinstance(captured["cmd"][-1], str)
    assert "verdict.json" in captured["cmd"][-1]  # prompt mentions the target file
    assert captured["cwd"].endswith("runs/round-1/validation_snapshot/code")
    # Timeout behavior covered by test_codex_timeout_is_tooling_failure.


def test_round_token_is_substituted_in_prompt(monkeypatch, config: Config, workspace: Workspace):
    captured: dict[str, Any] = {}

    def spy_run(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
        captured["prompt"] = cmd[-1]
        workspace.verdict_path(7).write_text(
            json.dumps({"passed": True, "summary": "", "issues": []}), encoding="utf-8"
        )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(validation_mod.subprocess, "Popen", popen_from_run(spy_run))
    ValidationAgent(config).run(workspace, round_n=7)

    assert "round-7" in captured["prompt"]
    assert "{round}" not in captured["prompt"]


# ---- tooling failures ----


def test_missing_verdict_file_is_tooling_failure(monkeypatch, config: Config, workspace: Workspace):
    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        _fake_codex(workspace, round_n=1, write_verdict=None),  # codex writes nothing
    )
    verdict = ValidationAgent(config).run(workspace, round_n=1)

    assert verdict.passed is False
    assert verdict.tooling_error is not None
    assert "verdict.json" in verdict.tooling_error
    assert len(verdict.issues) == 1
    assert verdict.issues[0].severity == "critical"


def test_invalid_json_is_tooling_failure_when_stdout_also_unparseable(
    monkeypatch, config: Config, workspace: Workspace
):
    """When verdict.json is malformed JSON AND stdout has no parseable verdict,
    the agent reports a tooling failure citing both channels."""
    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        _fake_codex(
            workspace,
            round_n=1,
            write_verdict="not valid json {{",
            stdout="claude also rambled here",
        ),
    )
    verdict = ValidationAgent(config).run(workspace, round_n=1)

    assert verdict.passed is False
    assert verdict.tooling_error is not None
    # New, more precise message mentions both channels failed.
    assert "verdict.json" in verdict.tooling_error
    assert "stdout" in verdict.tooling_error


def test_schema_mismatch_is_tooling_failure(monkeypatch, config: Config, workspace: Workspace):
    """Verdict with bad issue severity should be caught."""
    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        _fake_codex(
            workspace,
            round_n=1,
            write_verdict={
                "passed": False,
                "summary": "x",
                "issues": [{"severity": "WHATEVER", "description": "x"}],
            },
        ),
    )
    verdict = ValidationAgent(config).run(workspace, round_n=1)

    assert verdict.passed is False
    assert verdict.tooling_error is not None
    assert "schema" in verdict.tooling_error.lower()


def test_codex_not_found_is_tooling_failure(monkeypatch, config: Config, workspace: Workspace):
    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        _fake_codex(workspace, round_n=1, raises=FileNotFoundError("codex")),
    )
    verdict = ValidationAgent(config).run(workspace, round_n=1)

    assert verdict.passed is False
    assert verdict.tooling_error is not None
    assert "not found" in verdict.tooling_error or "did not produce" in verdict.tooling_error
    log_text = (workspace.round_dir(1) / "validation.log").read_text(encoding="utf-8")
    assert "not found" in log_text


def test_codex_start_oserror_is_tooling_failure(monkeypatch, config: Config, workspace: Workspace):
    class _PopenStartFails:
        def __init__(self, args, **kwargs):  # noqa: ARG002
            raise OSError("permission denied")

    monkeypatch.setattr(validation_mod.subprocess, "Popen", _PopenStartFails)
    verdict = ValidationAgent(config).run(workspace, round_n=1)

    assert verdict.passed is False
    assert verdict.tooling_error is not None
    log_text = (workspace.round_dir(1) / "validation.log").read_text(encoding="utf-8")
    assert "failed to start" in log_text
    assert "permission denied" in log_text


def test_codex_timeout_is_tooling_failure(monkeypatch, config: Config, workspace: Workspace):
    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        _fake_codex(
            workspace,
            round_n=1,
            raises=subprocess.TimeoutExpired(cmd=["codex"], timeout=5),
        ),
    )
    verdict = ValidationAgent(config).run(workspace, round_n=1)

    assert verdict.passed is False
    assert verdict.tooling_error is not None
    log_text = (workspace.round_dir(1) / "validation.log").read_text(encoding="utf-8")
    assert "timed out" in log_text


def test_codex_communicate_oserror_is_tooling_failure(monkeypatch, config: Config, workspace: Workspace):
    class _PopenCommunicateFails:
        def __init__(self, args, **kwargs):  # noqa: ARG002
            self.pid = 70020

        def communicate(self, timeout=None):  # noqa: ARG002
            raise OSError("broken pipe")

    monkeypatch.setattr(validation_mod.subprocess, "Popen", _PopenCommunicateFails)
    verdict = ValidationAgent(config).run(workspace, round_n=1)

    assert verdict.passed is False
    assert verdict.tooling_error is not None
    log_text = (workspace.round_dir(1) / "validation.log").read_text(encoding="utf-8")
    assert "communication failed" in log_text
    assert "broken pipe" in log_text


# ---- artifacts written ----


def test_verdict_file_is_rewritten_in_canonical_form(monkeypatch, config: Config, workspace: Workspace):
    """codex's raw output may be sloppy (extra fields, weird whitespace); we rewrite it."""
    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        _fake_codex(
            workspace,
            round_n=1,
            write_verdict={
                "passed": True,
                "summary": "ok",
                "issues": [],
                "extra_garbage_field": "ignored",
            },
        ),
    )
    ValidationAgent(config).run(workspace, round_n=1)

    raw = json.loads(workspace.verdict_path(1).read_text(encoding="utf-8"))
    assert raw["passed"] is True
    assert "extra_garbage_field" not in raw  # canonicalized


def test_feedback_md_orders_critical_first(monkeypatch, config: Config, workspace: Workspace):
    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        _fake_codex(
            workspace,
            round_n=2,
            write_verdict={
                "passed": False,
                "summary": "stuff broken",
                "issues": [
                    {"severity": "minor", "description": "minor1"},
                    {"severity": "critical", "description": "crit1"},
                    {"severity": "major", "description": "major1"},
                ],
            },
        ),
    )
    ValidationAgent(config).run(workspace, round_n=2)

    fb = workspace.feedback_path(2).read_text(encoding="utf-8")
    pos_crit = fb.index("crit1")
    pos_major = fb.index("major1")
    pos_minor = fb.index("minor1")
    assert pos_crit < pos_major < pos_minor


def test_feedback_md_for_passed_round_is_short(monkeypatch, config: Config, workspace: Workspace):
    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        _fake_codex(
            workspace,
            round_n=1,
            write_verdict={"passed": True, "summary": "great", "issues": []},
        ),
    )
    ValidationAgent(config).run(workspace, round_n=1)

    fb = workspace.feedback_path(1).read_text(encoding="utf-8")
    assert "PASSED" in fb
    assert "great" in fb


def test_validation_log_is_written_on_success(monkeypatch, config: Config, workspace: Workspace):
    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        _fake_codex(
            workspace,
            round_n=1,
            write_verdict={"passed": True, "summary": "", "issues": []},
            stdout="hello from codex",
            stderr="some warning",
        ),
    )
    ValidationAgent(config).run(workspace, round_n=1)

    log = (workspace.round_dir(1) / "validation.log").read_text(encoding="utf-8")
    assert "hello from codex" in log
    assert "some warning" in log
    assert "returncode: 0" in log


def test_validation_log_redacts_api_keys(monkeypatch, config: Config, workspace: Workspace):
    """Secrets in CLI stdout/stderr must never end up in validation.log."""
    fake_key = "sk-ant-api03-" + "a" * 40
    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        _fake_codex(
            workspace,
            round_n=1,
            write_verdict={"passed": True, "summary": "", "issues": []},
            stdout=f"error: bad key {fake_key}",
            stderr="",
        ),
    )
    ValidationAgent(config).run(workspace, round_n=1)
    log = (workspace.round_dir(1) / "validation.log").read_text(encoding="utf-8")
    assert fake_key not in log
    assert "[REDACTED:Anthropic API key]" in log


def test_validation_api_backend_uses_openai_responses_without_codex_cli(
    monkeypatch, config: Config, workspace: Workspace
):
    _write_requirements(workspace, "starter")
    _good_starter_deliverable(workspace)
    captured: dict[str, Any] = {}

    class _Responses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return types.SimpleNamespace(
                output_text=json.dumps(
                    {
                        "passed": True,
                        "summary": "api validator ok",
                        "issues": [],
                    }
                )
            )

    class _OpenAI:
        def __init__(self, api_key=None):  # noqa: ARG002
            self.responses = _Responses()

    fake_openai = types.ModuleType("openai")
    fake_openai.OpenAI = _OpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    cfg = replace(config, validation_backend="api", validation_model="gpt-test")
    verdict = ValidationAgent(cfg).run(workspace, round_n=1)

    assert verdict.passed is True
    assert verdict.summary == "api validator ok"
    assert captured["model"] == "gpt-test"
    assert "### FILE: landing-page/index.html" in captured["input"]
    log = (workspace.round_dir(1) / "validation.log").read_text(encoding="utf-8")
    assert "backend: api" in log


# ---- Structural override of codex's passed=True ----


def _write_requirements(workspace: Workspace, tier_value: str = "starter") -> None:
    """Helper: write a minimal requirements.json so structural checks engage."""
    from smbagent.types import Requirements, Tier

    req = Requirements(
        customer_id=workspace.customer_id,
        tier=Tier(tier_value),
        business_name="Test Co",
        summary_ja="テスト",
        target_users=["x"],
        brand_notes=["y"],
        desired_skills=["s1"],
        desired_integrations=["Gmail"],
        acceptance_criteria=["A1"],
        company_context=CompanyContext(
            mission="Help customers quickly.",
            vision="Reliable SMB operations.",
            values=["trust", "clarity"],
            current_strategy=["pilot one governed workflow"],
            current_priorities=["safe delivery"],
            decision_style="conservative and reviewed",
            risk_tolerance="low for external execution",
        ),
    )
    workspace.save_requirements(req)


def _good_starter_deliverable(workspace: Workspace) -> None:
    """Helper: build a tier-starter-compliant code/ tree.
    Includes README.md so the required-artifacts structural check passes."""
    code = workspace.code_dir
    (code / "agent-skills").mkdir(exist_ok=True)
    (code / "agent-skills" / "understand-x.md").write_text(
        "---\nname: understand-x\ndescription: stub\n---\n\nbody",
        encoding="utf-8",
    )
    (code / "landing-page").mkdir(exist_ok=True)
    (code / "landing-page" / "index.html").write_text("<html/>", encoding="utf-8")
    (code / "integrations" / "gmail").mkdir(parents=True, exist_ok=True)
    (code / "integrations" / "gmail" / "config.example.json").write_text(
        '{"api_key": "<PLACEHOLDER>"}', encoding="utf-8"
    )
    (code / "README.md").write_text("# Deliverable\n", encoding="utf-8")


def test_structural_critical_overrides_codex_passed(monkeypatch, config: Config, workspace: Workspace):
    """If codex says passed=True but the deliverable has hard-coded secrets,
    the final verdict must be passed=False with the structural issues merged in."""
    _write_requirements(workspace, "starter")
    _good_starter_deliverable(workspace)
    # Now inject a secret into one of the files — structural check should catch it.
    (workspace.code_dir / "integrations" / "gmail" / "config.example.json").write_text(
        '{"api_key": "sk-ant-api03-' + "a" * 40 + '"}', encoding="utf-8"
    )

    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        _fake_codex(
            workspace,
            round_n=1,
            write_verdict={"passed": True, "summary": "all good", "issues": []},
        ),
    )
    verdict = ValidationAgent(config).run(workspace, round_n=1)

    assert verdict.passed is False  # structural critical wins
    assert any(i.severity == "critical" and "Anthropic API key" in i.description for i in verdict.issues)
    assert "Structural checks found" in verdict.summary


def test_structural_tier_overflow_overrides_codex_passed(monkeypatch, config: Config, workspace: Workspace):
    """Codex misses overflow → structural check forces fail."""
    _write_requirements(workspace, "starter")
    # 3 skills on a starter (cap = 1)
    skills = workspace.code_dir / "agent-skills"
    skills.mkdir(exist_ok=True)
    for i in range(3):
        (skills / f"s{i}.md").write_text(f"---\nname: s{i}\ndescription: d\n---\nbody", encoding="utf-8")

    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        _fake_codex(
            workspace,
            round_n=1,
            write_verdict={"passed": True, "summary": "looks fine", "issues": []},
        ),
    )
    verdict = ValidationAgent(config).run(workspace, round_n=1)
    assert verdict.passed is False
    assert any("exceed starter cap" in i.description for i in verdict.issues)


def test_structural_check_skipped_when_requirements_missing(
    monkeypatch, config: Config, workspace: Workspace
):
    """No requirements.json (test fixture path) → structural check is a no-op,
    preserves codex's verdict as-is."""
    # NB: no _write_requirements call here.
    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        _fake_codex(
            workspace,
            round_n=1,
            write_verdict={"passed": True, "summary": "ok", "issues": []},
        ),
    )
    verdict = ValidationAgent(config).run(workspace, round_n=1)
    assert verdict.passed is True  # codex's verdict preserved


def test_structural_check_skipped_when_tooling_error(monkeypatch, config: Config, workspace: Workspace):
    """If codex itself failed (tooling error), don't run structural checks —
    the tooling error must surface clearly without being diluted by other issues."""
    _write_requirements(workspace, "starter")
    # Even with severe structural problems (no agent-skills dir):
    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        _fake_codex(workspace, round_n=1, write_verdict=None),  # codex writes nothing
    )
    verdict = ValidationAgent(config).run(workspace, round_n=1)
    assert verdict.passed is False
    assert verdict.tooling_error is not None
    # Tooling error is the sole issue; no structural noise appended.
    assert len(verdict.issues) == 1
    assert "Validator could not produce a verdict" in verdict.issues[0].description


def test_structural_minor_issues_dont_override_codex_pass(monkeypatch, config: Config, workspace: Workspace):
    """Major/minor structural issues are appended but do NOT flip passed=True → False.
    Only critical structural issues override."""
    _write_requirements(workspace, "starter")
    _good_starter_deliverable(workspace)
    # Introduce a frontmatter mismatch (major, not critical).
    (workspace.code_dir / "agent-skills" / "understand-x.md").write_text(
        "---\nname: WRONG\ndescription: d\n---\nbody", encoding="utf-8"
    )

    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        _fake_codex(
            workspace,
            round_n=1,
            write_verdict={"passed": True, "summary": "ok", "issues": []},
        ),
    )
    verdict = ValidationAgent(config).run(workspace, round_n=1)
    assert verdict.passed is True  # major doesn't override
    assert any(i.severity == "major" for i in verdict.issues)
