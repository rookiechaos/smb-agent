from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

from smbagent.agents.bridge_orchestrator import BridgeOrchestratorAgent
from smbagent.iteration_tuning import IterationTuning
from smbagent.types import Issue, Verdict


@dataclass
class _FakeBlock:
    type: str = "text"
    text: str = ""


def test_relay_validation_to_coding_writes_bridge_file(config, workspace, monkeypatch):
    verdict = Verdict(
        passed=False,
        round=2,
        summary="needs work",
        issues=[Issue(severity="critical", file="a.ts", description="broken")],
    )
    workspace.feedback_path(2).write_text("# FAILED\n\nfix a.ts", encoding="utf-8")

    tuning = IterationTuning.from_config(config)
    agent = BridgeOrchestratorAgent(config, tuning)
    mock_response = MagicMock()
    mock_response.content = [_FakeBlock(text="## Round\n2\n## Verdict\nfail")]
    agent.client = MagicMock()
    agent.client.messages.create.return_value = mock_response

    out = agent.relay_validation_to_coding(workspace, verdict)

    assert out == workspace.bridge_for_coding_path(2)
    assert out.exists()
    assert "Round" in out.read_text(encoding="utf-8")
    agent.client.messages.create.assert_called_once()
    call_kwargs = agent.client.messages.create.call_args.kwargs
    assert call_kwargs["temperature"] == 0.0
    assert call_kwargs["max_tokens"] == tuning.bridge_orchestrator_max_tokens


def test_relay_coding_to_validation_uses_log(config, workspace, monkeypatch):
    workspace.coding_log_path(1).write_text("returncode: 0\nedited index.html", encoding="utf-8")

    tuning = IterationTuning.from_config(config)
    agent = BridgeOrchestratorAgent(config, tuning)
    mock_response = MagicMock()
    mock_response.content = [_FakeBlock(text="## Round\n1\n## Files likely touched\nindex.html")]
    agent.client = MagicMock()
    agent.client.messages.create.return_value = mock_response

    out = agent.relay_coding_to_validation(workspace, 1)

    assert out == workspace.bridge_for_validation_path(1)
    assert out.exists()


def test_relay_coding_to_validation_sanitizes_log_before_bridge_prompt(config, workspace):
    workspace.coding_log_path(1).write_text(
        "returncode: 0\n"
        "thoughts: I compared ../tasks.json and prior verdicts in detail\n"
        "edited landing-page/index.html and agent-skills/faq.md\n",
        encoding="utf-8",
    )
    (workspace.code_dir / "landing-page").mkdir(parents=True, exist_ok=True)
    (workspace.code_dir / "landing-page" / "index.html").write_text("x", encoding="utf-8")
    (workspace.code_dir / "agent-skills").mkdir(parents=True, exist_ok=True)
    (workspace.code_dir / "agent-skills" / "faq.md").write_text("x", encoding="utf-8")

    tuning = IterationTuning.from_config(config)
    agent = BridgeOrchestratorAgent(config, tuning)
    mock_response = MagicMock()
    mock_response.content = [_FakeBlock(text="## Round\n1")]
    agent.client = MagicMock()
    agent.client.messages.create.return_value = mock_response

    agent.relay_coding_to_validation(workspace, 1)

    call_kwargs = agent.client.messages.create.call_args.kwargs
    msg = call_kwargs["messages"][0]["content"]
    assert "thoughts:" not in msg
    assert "../tasks.json" not in msg
    assert "landing-page/index.html" in msg
    assert "agent-skills/faq.md" in msg
