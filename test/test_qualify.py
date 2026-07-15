from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from smbagent.agents.qualify import QualifyAgent
from smbagent.config import Config
from smbagent.types import Tier
from smbagent.workspace import Workspace


@dataclass
class FakeAnthropicResponse:
    content: list


@dataclass
class FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class FakeMessages:
    """Stand-in for client.messages — records every create() call."""

    response_text: str
    calls: list[dict] = field(default_factory=list)

    def create(self, *, model, max_tokens, system, messages):
        self.calls.append({"model": model, "system": system, "messages": messages})
        return FakeAnthropicResponse(content=[FakeTextBlock(self.response_text)])


@dataclass
class FakeAnthropic:
    messages: FakeMessages


def _agent_with_response(config: Config, response_text: str) -> tuple[QualifyAgent, FakeMessages]:
    fake_msgs = FakeMessages(response_text=response_text)
    agent = QualifyAgent(config)
    agent.client = FakeAnthropic(messages=fake_msgs)  # type: ignore[assignment]
    return agent, fake_msgs


def test_qualify_returns_go_with_recommended_tier(config: Config, workspace: Workspace):
    response = """```json
{
  "go": true,
  "recommended_tier": "growth",
  "summary_ja": "中規模事業者で適合します。",
  "reasoning_en": "Mid-sized SMB, growth tier appropriate."
}
```"""
    agent, msgs = _agent_with_response(config, response)
    q = agent.run(workspace, "Acme Dental clinic with 20 staff in Tokyo.")

    assert q.go is True
    assert q.recommended_tier == Tier.GROWTH
    assert q.summary_ja.startswith("中規模")
    assert q.customer_id == workspace.customer_id

    # persisted to disk
    loaded = workspace.load_qualification()
    assert loaded == q

    # SDK invoked once with the brief
    assert len(msgs.calls) == 1
    assert msgs.calls[0]["messages"][0]["content"].startswith("Acme")


def test_qualify_returns_no_go_with_null_tier(config: Config, workspace: Workspace):
    response = """```json
{
  "go": false,
  "recommended_tier": null,
  "summary_ja": "範囲外です。"
}
```"""
    agent, _ = _agent_with_response(config, response)
    q = agent.run(workspace, "国際的な大手銀行")

    assert q.go is False
    assert q.recommended_tier is None


def test_qualify_normalizes_tier_capitalization(config: Config, workspace: Workspace):
    """Model might return 'Starter' or 'STARTER' — we lowercase before coercing."""
    response = """```json
{"go": true, "recommended_tier": "Starter", "summary_ja": "個人事業主に最適。"}
```"""
    agent, _ = _agent_with_response(config, response)
    q = agent.run(workspace, "個人タロット占い師")
    assert q.recommended_tier == Tier.STARTER


def test_qualify_raises_on_go_true_with_unknown_tier(config: Config, workspace: Workspace):
    """An LLM that says go=true but ships an unknown tier is incoherent.
    The Qualification model invariant forces a hard fail so the operator notices."""
    response = """```json
{"go": true, "recommended_tier": "enterprise", "summary_ja": "."}
```"""
    agent, _ = _agent_with_response(config, response)
    with pytest.raises(Exception) as excinfo:
        agent.run(workspace, "...")
    # Pydantic raises ValidationError, which is a subclass of ValueError.
    assert "recommended_tier" in str(excinfo.value)


def test_qualify_soft_corrects_no_go_with_stray_tier(config: Config, workspace: Workspace):
    """An LLM that says no-go but still recommends a tier — we drop the tier."""
    response = """```json
{"go": false, "recommended_tier": "starter", "summary_ja": "範囲外。"}
```"""
    agent, _ = _agent_with_response(config, response)
    q = agent.run(workspace, "...")
    assert q.go is False
    assert q.recommended_tier is None


def test_qualify_raises_on_unparseable_response(config: Config, workspace: Workspace):
    agent, _ = _agent_with_response(config, "the model just rambled without any JSON")
    with pytest.raises(ValueError):
        agent.run(workspace, "...")
