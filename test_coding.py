from __future__ import annotations

import subprocess
from typing import Any

import pytest

from smbagent.agents import coding as coding_mod
from smbagent.agents.coding import CodingAgent
from smbagent.annealing import compute_annealing
from smbagent.config import Config
from smbagent.types import Verdict
from smbagent.workspace import Workspace
from tests._popen_mocks import popen_from_run


def _ok(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
    return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="done", stderr="")


def test_first_round_prompt_says_no_prior_feedback(config: Config, workspace: Workspace):
    agent = CodingAgent(config)
    prompt = agent._build_prompt(workspace, round_n=1, prior_feedback=None)
    assert "no prior-round feedback" in prompt.lower() or "first round" in prompt.lower()
    assert "{feedback_section}" not in prompt


def test_prompt_includes_single_tenant_and_hitl_posture(config: Config, workspace: Workspace):
    agent = CodingAgent(config)
    prompt = agent._build_prompt(workspace, round_n=1, prior_feedback=None)
    assert "dedicated Mac mini or MacBook operator boundary" in prompt
    assert "do NOT describe the system as a broad shared multi-tenant SaaS" in prompt
    assert "human approval at critical execution boundaries" in prompt


def test_later_round_prompt_prefers_bridge_file_when_present(config: Config, workspace: Workspace):
    prior = Verdict(passed=False, round=4, summary="x", issues=[])
    workspace.bridge_for_coding_path(4).write_text("## Critical path\n- fix x", encoding="utf-8")
    agent = CodingAgent(config)
    prompt = agent._build_prompt(workspace, round_n=5, prior_feedback=prior)
    assert "../runs/round-4/bridge_for_coding.md" in prompt
    assert "Bridge Orchestrator" in prompt


def test_prompt_references_retrieved_memory_when_available(config: Config, workspace: Workspace):
    prior = Verdict(passed=False, round=2, summary="GPS analysis needs fixes", issues=[])
    path = workspace.retrieved_memory_path(3)
    path.write_text("## Prior failure pattern\n- summary: GPS issue", encoding="utf-8")
    agent = CodingAgent(config)
    prompt = agent._build_prompt(
        workspace,
        round_n=3,
        prior_feedback=prior,
        retrieved_memory_path=path,
    )
    assert "../runs/round-3/retrieved_memory.md" in prompt
    assert "Retrieved memory" in prompt


def test_later_round_prompt_references_prior_feedback_file(config: Config, workspace: Workspace):
    prior = Verdict(passed=False, round=4, summary="x", issues=[])
    agent = CodingAgent(config)
    prompt = agent._build_prompt(workspace, round_n=5, prior_feedback=prior)
    # Path is relative to the workspace/code/ cwd
    assert "../runs/round-4/feedback.md" in prompt
    # Iteration protocol must give claude explicit instructions:
    assert "Iteration protocol" in prompt
    assert "EVERY listed fix" in prompt
    assert "Persistent issues" in prompt
    # Don't reset — preserve prior work
    assert "Do not" in prompt and "start over" in prompt


def test_prompt_includes_annealing_section(config: Config, workspace: Workspace):
    annealing = compute_annealing(
        2,
        max_rounds=5,
        consecutive_failures=1,
        deadlock=False,
    )
    prompt = CodingAgent(config)._build_prompt(
        workspace,
        round_n=2,
        prior_feedback=None,
        annealing=annealing,
    )
    assert "Sampling policy" in prompt
    assert str(annealing.temperature) in prompt


def test_round_1_with_prior_feedback_still_treats_as_first(config: Config, workspace: Workspace):
    """Defensive: orchestrator should never pass prior_feedback to round 1, but if it
    does, the agent must not point at a non-existent round-0 file."""
    prior = Verdict(passed=False, round=0, summary="x", issues=[])
    agent = CodingAgent(config)
    prompt = agent._build_prompt(workspace, round_n=1, prior_feedback=prior)
    assert "round-0" not in prompt


def test_run_invokes_claude_with_correct_command_and_cwd(monkeypatch, config: Config, workspace: Workspace):
    captured: dict[str, Any] = {}

    def spy(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(coding_mod.subprocess, "Popen", popen_from_run(spy))
    CodingAgent(config).run(workspace, round_n=1, prior_feedback=None)

    assert captured["cmd"][: len(config.coding_cmd)] == config.coding_cmd
    assert isinstance(captured["cmd"][-1], str)
    assert captured["cwd"] == str(workspace.code_dir)
    # NOTE: with Popen+communicate, `timeout` is passed to communicate, not Popen.
    # The timeout *behavior* is covered by the dedicated timeout test.


def test_run_writes_log(monkeypatch, config: Config, workspace: Workspace):
    def fake(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="claude said hi", stderr="")

    monkeypatch.setattr(coding_mod.subprocess, "Popen", popen_from_run(fake))
    CodingAgent(config).run(workspace, round_n=2, prior_feedback=None)

    log = workspace.coding_log_path(2).read_text(encoding="utf-8")
    assert "claude said hi" in log
    assert "returncode: 0" in log


def test_run_raises_on_file_not_found_but_still_logs(monkeypatch, config: Config, workspace: Workspace):
    def boom(cmd, cwd, capture_output, text, timeout, check):  # noqa: ARG001
        raise FileNotFoundError("claude")

    monkeypatch.setattr(coding_mod.subprocess, "Popen", popen_from_run(boom))

    with pytest.raises(FileNotFoundError):
        CodingAgent(config).run(workspace, round_n=1, prior_feedback=None)

    log = workspace.coding_log_path(1).read_text(encoding="utf-8")
    assert "not found" in log
