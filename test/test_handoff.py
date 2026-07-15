"""Tests for the Claude↔Codex handoff features:

- Stdout fallback when codex doesn't write verdict.json
- Persistent-issue tracking across rounds
- Feedback.md grouped by file with persistent section
"""

from __future__ import annotations

import json
import subprocess

from smbagent.agents import validation as validation_mod
from smbagent.agents.validation import ValidationAgent, _issue_fingerprint
from smbagent.config import Config
from smbagent.types import Issue
from smbagent.workspace import Workspace
from tests._popen_mocks import popen_from_run

# ---------- stdout fallback ----------


def _fake_codex_stdout_only(stdout: str, returncode: int = 0):
    """A codex stand-in that writes NOTHING to verdict.json but puts content in stdout."""

    def fake_run(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
        return subprocess.CompletedProcess(args=cmd, returncode=returncode, stdout=stdout, stderr="")

    return fake_run


def test_stdout_fallback_when_codex_skips_verdict_file(monkeypatch, config: Config, workspace: Workspace):
    """Codex puts the verdict JSON in stdout instead of writing the file → we salvage it."""
    stdout = (
        "I audited the deliverable. Here is my verdict:\n"
        "```json\n" + json.dumps({"passed": True, "summary": "all good", "issues": []}) + "\n```\n"
    )
    monkeypatch.setattr(validation_mod.subprocess, "Popen", popen_from_run(_fake_codex_stdout_only(stdout)))
    verdict = ValidationAgent(config).run(workspace, round_n=1)

    assert verdict.passed is True
    assert verdict.tooling_error is None
    assert verdict.summary == "all good"
    # And verdict.json was materialized for downstream consumers.
    assert workspace.verdict_path(1).exists()
    data = json.loads(workspace.verdict_path(1).read_text(encoding="utf-8"))
    assert data["passed"] is True


def test_stdout_fallback_handles_failed_verdict_with_issues(
    monkeypatch, config: Config, workspace: Workspace
):
    stdout = json.dumps(
        {
            "passed": False,
            "summary": "missing thing",
            "issues": [
                {"severity": "critical", "file": "code/x.md", "description": "x not found"},
            ],
        }
    )
    monkeypatch.setattr(validation_mod.subprocess, "Popen", popen_from_run(_fake_codex_stdout_only(stdout)))
    verdict = ValidationAgent(config).run(workspace, round_n=2)

    assert verdict.passed is False
    assert verdict.tooling_error is None
    assert len(verdict.issues) == 1
    assert verdict.issues[0].file == "code/x.md"


def test_stdout_fallback_skipped_when_stdout_has_no_json(monkeypatch, config: Config, workspace: Workspace):
    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        popen_from_run(_fake_codex_stdout_only("just prose, no JSON here.")),
    )
    verdict = ValidationAgent(config).run(workspace, round_n=1)

    assert verdict.passed is False
    assert verdict.tooling_error is not None
    assert "verdict.json" in verdict.tooling_error
    assert "stdout" in verdict.tooling_error


def test_stdout_fallback_skipped_when_stdout_json_lacks_passed_field(
    monkeypatch, config: Config, workspace: Workspace
):
    """The fallback requires the parsed JSON to look like a verdict (have `passed`)."""
    stdout = '```json\n{"summary": "ok", "issues": []}\n```'  # no passed field
    monkeypatch.setattr(validation_mod.subprocess, "Popen", popen_from_run(_fake_codex_stdout_only(stdout)))
    verdict = ValidationAgent(config).run(workspace, round_n=1)
    assert verdict.tooling_error is not None


def test_verdict_file_wins_over_stdout_when_both_present(monkeypatch, config: Config, workspace: Workspace):
    """If verdict.json is well-formed and schema-valid, it wins. Stdout is ignored."""

    def fake_run(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
        workspace.verdict_path(1).write_text(
            json.dumps({"passed": True, "summary": "from file", "issues": []}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=json.dumps({"passed": False, "summary": "from stdout", "issues": []}),
            stderr="",
        )

    monkeypatch.setattr(validation_mod.subprocess, "Popen", popen_from_run(fake_run))
    verdict = ValidationAgent(config).run(workspace, round_n=1)
    assert verdict.passed is True
    assert verdict.summary == "from file"


def test_malformed_file_falls_back_to_valid_stdout(monkeypatch, config: Config, workspace: Workspace):
    """File has bad JSON syntax → fall through to stdout, which has a clean verdict."""

    def fake_run(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
        workspace.verdict_path(1).write_text("not json at all", encoding="utf-8")
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=json.dumps({"passed": True, "summary": "salvaged from stdout", "issues": []}),
            stderr="",
        )

    monkeypatch.setattr(validation_mod.subprocess, "Popen", popen_from_run(fake_run))
    verdict = ValidationAgent(config).run(workspace, round_n=1)
    assert verdict.passed is True
    assert verdict.summary == "salvaged from stdout"


def test_well_formed_file_with_bad_schema_does_not_fall_through(
    monkeypatch, config: Config, workspace: Workspace
):
    """If file is valid JSON but bad schema, we report schema error — codex's
    intent was clear, just wrong. Stdout is not consulted."""

    def fake_run(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
        workspace.verdict_path(1).write_text(
            json.dumps(
                {
                    "passed": False,
                    "summary": "x",
                    "issues": [{"severity": "INVALID_SEVERITY", "description": "x"}],
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=json.dumps({"passed": True, "summary": "stdout should be ignored", "issues": []}),
            stderr="",
        )

    monkeypatch.setattr(validation_mod.subprocess, "Popen", popen_from_run(fake_run))
    verdict = ValidationAgent(config).run(workspace, round_n=1)
    assert verdict.passed is False
    assert verdict.tooling_error is not None
    assert "schema" in verdict.tooling_error.lower()


# ---------- Issue fingerprinting + persistent tracking ----------


def test_issue_fingerprint_is_stable():
    a = Issue(severity="critical", file="x.py", line=10, description="thing broken")
    b = Issue(severity="critical", file="x.py", line=99, description="thing broken")  # diff line
    # Line is intentionally NOT part of the fingerprint — same problem at a slightly
    # moved line should still be recognized as the same issue.
    assert _issue_fingerprint(a) == _issue_fingerprint(b)


def test_issue_fingerprint_distinguishes_severity():
    a = Issue(severity="critical", file="x.py", description="thing")
    b = Issue(severity="major", file="x.py", description="thing")
    assert _issue_fingerprint(a) != _issue_fingerprint(b)


def test_issue_fingerprint_distinguishes_file():
    a = Issue(severity="critical", file="x.py", description="thing")
    b = Issue(severity="critical", file="y.py", description="thing")
    assert _issue_fingerprint(a) != _issue_fingerprint(b)


def test_persistent_issue_marked_in_feedback_md(monkeypatch, config: Config, workspace: Workspace):
    """An issue seen in rounds 1 AND 2 should be tagged as persistent in round 2's feedback."""
    same_issue = {"severity": "critical", "file": "skills/foo.md", "description": "missing description"}

    def codex_round_1(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
        workspace.verdict_path(1).write_text(
            json.dumps({"passed": False, "summary": "r1", "issues": [same_issue]}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(validation_mod.subprocess, "Popen", popen_from_run(codex_round_1))
    ValidationAgent(config).run(workspace, round_n=1)

    def codex_round_2(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
        workspace.verdict_path(2).write_text(
            json.dumps({"passed": False, "summary": "r2", "issues": [same_issue]}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(validation_mod.subprocess, "Popen", popen_from_run(codex_round_2))
    ValidationAgent(config).run(workspace, round_n=2)

    feedback_r2 = workspace.feedback_path(2).read_text(encoding="utf-8")
    assert "Persistent issues" in feedback_r2
    assert "seen in rounds: 1, 2" in feedback_r2


def test_fresh_issue_not_marked_persistent(monkeypatch, config: Config, workspace: Workspace):
    issue_r1 = {"severity": "major", "file": "a.md", "description": "old problem"}
    issue_r2 = {"severity": "critical", "file": "b.md", "description": "new problem"}

    def codex_r1(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
        workspace.verdict_path(1).write_text(
            json.dumps({"passed": False, "summary": "", "issues": [issue_r1]}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(validation_mod.subprocess, "Popen", popen_from_run(codex_r1))
    ValidationAgent(config).run(workspace, round_n=1)

    def codex_r2(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
        workspace.verdict_path(2).write_text(
            json.dumps({"passed": False, "summary": "", "issues": [issue_r2]}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(validation_mod.subprocess, "Popen", popen_from_run(codex_r2))
    ValidationAgent(config).run(workspace, round_n=2)

    feedback_r2 = workspace.feedback_path(2).read_text(encoding="utf-8")
    # The "new problem" appeared only in round 2 — no persistent flag.
    assert (
        "Persistent issues" not in feedback_r2
        or "new problem"
        not in (
            feedback_r2.split("## Issues to fix")[0]  # check the persistent section header part
        )
    )


# ---------- Feedback-by-file grouping ----------


def _set_round_verdict(workspace: Workspace, round_n: int, verdict: dict) -> None:
    workspace.verdict_path(round_n).write_text(json.dumps(verdict), encoding="utf-8")


def test_feedback_md_groups_issues_by_file(monkeypatch, config: Config, workspace: Workspace):
    """All issues for one file should appear together, with file-level header."""
    verdict_data = {
        "passed": False,
        "summary": "needs work",
        "issues": [
            {"severity": "minor", "file": "landing-page/index.html", "description": "missing alt text"},
            {"severity": "critical", "file": "agent-skills/x.md", "description": "no frontmatter"},
            {"severity": "major", "file": "landing-page/index.html", "description": "no h1"},
            {"severity": "major", "file": "agent-skills/x.md", "description": "name mismatch"},
        ],
    }
    _set_round_verdict(workspace, 1, verdict_data)

    def fake_codex(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
        # Verdict.json already written above — just return.
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(validation_mod.subprocess, "Popen", popen_from_run(fake_codex))
    ValidationAgent(config).run(workspace, round_n=1)

    feedback = workspace.feedback_path(1).read_text(encoding="utf-8")
    # File-headers exist
    assert "### `agent-skills/x.md`" in feedback
    assert "### `landing-page/index.html`" in feedback
    # File with critical issue appears BEFORE file with only major/minor
    idx_skill = feedback.index("### `agent-skills/x.md`")
    idx_landing = feedback.index("### `landing-page/index.html`")
    assert idx_skill < idx_landing
    # Within agent-skills/x.md, critical appears before major
    skill_block = feedback[idx_skill:idx_landing]
    assert skill_block.index("[CRITICAL]") < skill_block.index("[MAJOR]")


def test_feedback_md_has_iteration_protocol(monkeypatch, config: Config, workspace: Workspace):
    _set_round_verdict(
        workspace,
        1,
        {
            "passed": False,
            "summary": "",
            "issues": [{"severity": "critical", "file": "x", "description": "y"}],
        },
    )

    def fake_codex(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(validation_mod.subprocess, "Popen", popen_from_run(fake_codex))
    ValidationAgent(config).run(workspace, round_n=1)

    feedback = workspace.feedback_path(1).read_text(encoding="utf-8")
    assert "Protocol:" in feedback
    assert "open each file once" in feedback


def test_feedback_md_groups_unfiled_issues_under_general(monkeypatch, config: Config, workspace: Workspace):
    _set_round_verdict(
        workspace,
        1,
        {
            "passed": False,
            "summary": "",
            "issues": [
                {"severity": "major", "description": "no project README"},  # no file
                {"severity": "major", "file": "a.md", "description": "x"},
            ],
        },
    )

    def fake_codex(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(validation_mod.subprocess, "Popen", popen_from_run(fake_codex))
    ValidationAgent(config).run(workspace, round_n=1)

    feedback = workspace.feedback_path(1).read_text(encoding="utf-8")
    assert "no file" in feedback or "project root" in feedback
    assert "no project README" in feedback


# ---------- 3-round convergence (e2e of the iterative handoff) ----------


def test_three_round_convergence_through_feedback_loop(monkeypatch, config: Config, workspace: Workspace):
    """End-to-end of the validation feedback loop in isolation:
       Round 1: 3 issues (2 critical, 1 major)
       Round 2: 1 critical persists, others fixed → 1 issue
       Round 3: all clear → pass.

    Verifies that:
      - persistent issue gets flagged in round-2 feedback.md
      - the validator correctly tracks the verdict chain
    """
    verdicts_by_round = {
        1: {
            "passed": False,
            "summary": "lots missing",
            "issues": [
                {"severity": "critical", "file": "agent-skills/faq.md", "description": "missing description"},
                {
                    "severity": "critical",
                    "file": "integrations/gmail/README.md",
                    "description": "no setup notes",
                },
                {"severity": "major", "file": "landing-page/index.html", "description": "no h1"},
            ],
        },
        2: {
            "passed": False,
            "summary": "one critical left",
            "issues": [
                # SAME description + file + severity as round 1 issue #1 → persistent
                {"severity": "critical", "file": "agent-skills/faq.md", "description": "missing description"},
            ],
        },
        3: {
            "passed": True,
            "summary": "all fixed",
            "issues": [],
        },
    }

    for round_n in (1, 2, 3):
        v = verdicts_by_round[round_n]

        def make_fake(rd=round_n, vdata=v):
            def fake(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
                workspace.verdict_path(rd).write_text(json.dumps(vdata), encoding="utf-8")
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

            return fake

        monkeypatch.setattr(validation_mod.subprocess, "Popen", popen_from_run(make_fake()))
        v_result = ValidationAgent(config).run(workspace, round_n=round_n)
        if round_n == 3:
            assert v_result.passed is True
        else:
            assert v_result.passed is False

    # Round 2 feedback.md should flag the FAQ issue as persistent (rounds 1+2).
    fb_r2 = workspace.feedback_path(2).read_text(encoding="utf-8")
    assert "Persistent issues" in fb_r2
    assert "agent-skills/faq.md" in fb_r2
    assert "missing description" in fb_r2
    assert "seen in rounds: 1, 2" in fb_r2

    # Round 3 feedback is the PASSED summary, no file groupings.
    fb_r3 = workspace.feedback_path(3).read_text(encoding="utf-8")
    assert "PASSED" in fb_r3
    assert "Persistent issues" not in fb_r3
