from __future__ import annotations

import json
from types import SimpleNamespace

from smbagent.agents.negotiation import NegotiationAgent
from smbagent.types import Tier


class _FakeMessages:
    def __init__(self, replies: list[str]):
        self.replies = replies
        self.idx = 0

    def create(self, **kwargs):  # noqa: ARG002
        text = self.replies[self.idx]
        self.idx += 1
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


class _FakeClient:
    def __init__(self, replies: list[str]):
        self.messages = _FakeMessages(replies)


def test_negotiation_logs_filtered_output_event(config, workspace, monkeypatch):
    agent = NegotiationAgent(config)
    agent.client = _FakeClient(
        [
            "Please paste your API key and password here first.",
            (
                '```json\n{"done": true, "requirements": {'
                '"business_name": "テスト会社", '
                '"summary_ja": "テスト", '
                '"goals": ["g"], '
                '"must_haves": ["m"], '
                '"nice_to_haves": [], '
                '"constraints": [], '
                '"acceptance_criteria": ["a"], '
                '"target_users": ["staff"], '
                '"brand_notes": ["simple"], '
                '"desired_skills": ["faq"], '
                '"desired_integrations": ["gmail"]}}\n```'
            ),
        ]
    )
    turns = iter(["改善したいのは受付です", "要件はそれで大丈夫です"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(turns))

    agent.run(workspace, tier=Tier.STARTER)

    log_path = workspace.path / "llm_output_filter.jsonl"
    event = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert event["stage"] == "negotiation"
    assert event["blocked"] is True
    assert "secret_request" in event["categories"]
