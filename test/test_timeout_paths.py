"""Tests for the subprocess-timeout handlers in CodingAgent and ValidationAgent.

Real timeouts would require minutes of wait. These tests use the existing
popen_from_run adapter to inject `subprocess.TimeoutExpired` directly into
the `communicate()` call, hitting the handler logic without any actual delay.
"""

from __future__ import annotations

import subprocess
import sys
import types
from pathlib import Path

import pytest

from smbagent.agents import coding as coding_mod
from smbagent.agents import validation as validation_mod
from smbagent.agents.coding import CodingAgent
from smbagent.agents.validation import ValidationAgent
from smbagent.config import Config
from smbagent.voice import MLXWhisperBackend
from smbagent.workspace import Workspace

# ============================================================================
# CodingAgent timeout
# ============================================================================


def test_coding_agent_timeout_writes_log_and_reraises(monkeypatch, config: Config, workspace: Workspace):
    """When `claude` runs past coding_timeout_s, the agent logs the timeout
    (with partial stdout/stderr captured) and re-raises so the orchestrator
    can decide what to do."""

    class _PopenTimesOut:
        def __init__(self, args, **kwargs):
            self.args = args
            self.pid = 70001
            self.returncode = -1
            self._first_call = True

        def communicate(self, timeout=None):
            if self._first_call:
                self._first_call = False
                # First call raises TimeoutExpired (mimics communicate(timeout=...))
                raise subprocess.TimeoutExpired(self.args, timeout)
            # Second call (after proc.kill()) returns partial buffers — matches
            # real Popen.communicate behavior post-kill.
            return "partial-stdout-from-claude", "partial-stderr"

        kill_called = False

        def kill(self):
            type(self).kill_called = True

    monkeypatch.setattr(coding_mod.subprocess, "Popen", _PopenTimesOut)

    with pytest.raises(subprocess.TimeoutExpired):
        CodingAgent(config).run(workspace, round_n=1, prior_feedback=None)

    # Log file got the timeout-specific message
    log = workspace.coding_log_path(1).read_text(encoding="utf-8")
    assert "claude timed out" in log
    assert str(config.coding_timeout_s) in log
    assert "partial-stdout-from-claude" in log


def test_coding_agent_timeout_calls_kill_on_subprocess(monkeypatch, config: Config, workspace: Workspace):
    """proc.kill() must be invoked after a timeout so the child doesn't outlive us."""
    kill_calls = []

    class _PopenTimesOut:
        def __init__(self, args, **kwargs):
            self.args = args
            self.pid = 70002
            self.returncode = -1
            self._raised = False

        def communicate(self, timeout=None):
            if not self._raised:
                self._raised = True
                raise subprocess.TimeoutExpired(self.args, timeout)
            return "", ""

        def kill(self):
            kill_calls.append("kill")

    monkeypatch.setattr(coding_mod.subprocess, "Popen", _PopenTimesOut)
    with pytest.raises(subprocess.TimeoutExpired):
        CodingAgent(config).run(workspace, round_n=2, prior_feedback=None)

    assert kill_calls == ["kill"]


# ============================================================================
# ValidationAgent timeout (parallel to coding)
# ============================================================================


def test_validation_agent_timeout_writes_log_and_returns_tooling_failure(
    monkeypatch, config: Config, workspace: Workspace
):
    """When `codex` times out, the validator logs it and returns a structured
    tooling-failure Verdict (NOT a raise) — the orchestrator can keep going."""

    class _PopenTimesOut:
        def __init__(self, args, **kwargs):
            self.args = args
            self.pid = 70010
            self.returncode = -1
            self._raised = False

        def communicate(self, timeout=None):
            if not self._raised:
                self._raised = True
                raise subprocess.TimeoutExpired(self.args, timeout)
            return "partial-stdout-codex", "partial-stderr-codex"

        def kill(self):
            pass

    monkeypatch.setattr(validation_mod.subprocess, "Popen", _PopenTimesOut)
    verdict = ValidationAgent(config).run(workspace, round_n=1)

    assert verdict.passed is False
    assert verdict.tooling_error is not None
    assert "codex" in verdict.tooling_error.lower() or "did not produce" in verdict.tooling_error.lower()

    # Log file captured the timeout
    log = (workspace.round_dir(1) / "validation.log").read_text(encoding="utf-8")
    assert "codex timed out" in log
    assert str(config.validation_timeout_s) in log


# ============================================================================
# ValidationAgent — persistent-issue rendering branches (lines 379, 384-386)
# ============================================================================


def test_validation_feedback_renders_persistent_issue_with_no_file(
    monkeypatch, config: Config, workspace: Workspace
):
    """A persistent issue with `file=None` should render under the
    `(project-level)` label, not crash."""
    import json

    from smbagent.types import Requirements, Tier

    workspace.save_requirements(
        Requirements(
            customer_id=workspace.customer_id,
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

    # Round 1: a project-level issue (no file)
    same_issue = {
        "severity": "major",
        "description": "project missing licence file",
        # NOTE: no `file` field — renders as (project-level)
    }

    def codex_r1(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
        workspace.verdict_path(1).write_text(
            json.dumps({"passed": False, "summary": "r1", "issues": [same_issue]}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    from tests._popen_mocks import popen_from_run

    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        popen_from_run(codex_r1),
    )
    ValidationAgent(config).run(workspace, round_n=1)

    # Round 2: same issue (no file) → triggers the persistent + no-file branch
    def codex_r2(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
        workspace.verdict_path(2).write_text(
            json.dumps({"passed": False, "summary": "r2", "issues": [same_issue]}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        validation_mod.subprocess,
        "Popen",
        popen_from_run(codex_r2),
    )
    ValidationAgent(config).run(workspace, round_n=2)

    fb = workspace.feedback_path(2).read_text(encoding="utf-8")
    assert "Persistent issues" in fb
    assert "(project-level)" in fb
    assert "project missing licence file" in fb


def test_validation_feedback_renders_persistent_with_line_number(
    monkeypatch, config: Config, workspace: Workspace
):
    """A persistent issue with both file AND line should render as
    `file:line` in the persistent section."""
    import json

    from smbagent.types import Requirements, Tier
    from tests._popen_mocks import popen_from_run

    workspace.save_requirements(
        Requirements(
            customer_id=workspace.customer_id,
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

    same_issue = {
        "severity": "critical",
        "file": "agent-skills/faq.md",
        "line": 17,
        "description": "missing description field",
    }

    def codex_round(round_n):
        def fake(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
            workspace.verdict_path(round_n).write_text(
                json.dumps({"passed": False, "summary": "x", "issues": [same_issue]}),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        return fake

    monkeypatch.setattr(validation_mod.subprocess, "Popen", popen_from_run(codex_round(1)))
    ValidationAgent(config).run(workspace, round_n=1)

    monkeypatch.setattr(validation_mod.subprocess, "Popen", popen_from_run(codex_round(2)))
    ValidationAgent(config).run(workspace, round_n=2)

    fb = workspace.feedback_path(2).read_text(encoding="utf-8")
    # `file:line` in the persistent section
    assert "agent-skills/faq.md`:17" in fb


def test_validation_feedback_skips_persistent_when_issue_lookup_fails(
    monkeypatch, config: Config, workspace: Workspace
):
    """Defensive: if a fingerprint in history doesn't match any current issue
    (which shouldn't happen, but the safety branch exists), we skip it cleanly.

    Hits validation.py line 379 — the `if issue is None: continue` branch."""
    from smbagent.agents.validation import ValidationAgent

    # Create a verdict directly and call _write_feedback_md with a synthetic
    # history that references a fingerprint not in the verdict.
    from smbagent.types import Issue, Verdict

    verdict = Verdict(
        passed=False,
        round=2,
        summary="ok",
        issues=[Issue(severity="major", file="x.md", description="real issue")],
    )

    # Synthetic history: a fingerprint that doesn't match any current issue.
    history = {
        "deadbeef": [1, 2],  # bogus fingerprint not derivable from any issue
    }

    agent = ValidationAgent(config)
    agent._write_feedback_md(workspace, verdict, history=history)

    fb = workspace.feedback_path(2).read_text(encoding="utf-8")
    # The orphaned fingerprint was skipped cleanly; the real issue still rendered.
    assert "real issue" in fb


# ============================================================================
# MLXWhisperBackend — tempfile-cleanup OSError branch (lines 70-71)
# ============================================================================


def test_mlx_backend_handles_tempfile_unlink_failure(monkeypatch):
    """If tmp_path.unlink() raises OSError in the cleanup `finally`, we swallow
    it — the transcribe result must still come back successfully."""

    # Inject a working fake mlx_whisper
    fake_module = types.ModuleType("mlx_whisper")

    def fake_transcribe(audio_path, **kwargs):
        return {"text": "transcribed"}

    fake_module.transcribe = fake_transcribe
    monkeypatch.setitem(sys.modules, "mlx_whisper", fake_module)

    # Patch Path.unlink to raise OSError once (mimics a permission issue / race)
    real_unlink = Path.unlink

    def fake_unlink(self, *a, **kw):
        if self.suffix == ".wav" and "tmp" in str(self).lower():
            raise OSError("simulated unlink race")
        return real_unlink(self, *a, **kw)

    monkeypatch.setattr(Path, "unlink", fake_unlink)

    b = MLXWhisperBackend()
    # Should NOT raise — the OSError in cleanup is swallowed
    text = b.transcribe(b"audio-bytes", language="ja")
    assert text == "transcribed"
