from __future__ import annotations

from dataclasses import dataclass

from smbagent.game_studio.agents import GameNegotiationAgent, GamePlanAgent
from smbagent.game_studio.types import GamePackage, GameTemplate


@dataclass
class _Block:
    text: str
    type: str = "text"


@dataclass
class _Resp:
    content: list


@dataclass
class _Msgs:
    scripted: list[str]
    idx: int = 0

    def create(self, *, model, max_tokens, system, messages):  # noqa: ARG002
        text = self.scripted[self.idx]
        self.idx += 1
        return _Resp(content=[_Block(text)])


@dataclass
class _FakeAnthropic:
    messages: _Msgs


def test_game_negotiation_extract_done_payload():
    text = (
        '```json\n{"done": true, "requirements": {"project_name": "夏クイズ", '
        '"business_goal": "集客", "summary_ja": "キャンペーン向け", '
        '"preferred_templates": ["quiz"], "required_scenes": ["title", "play", "result"]}}\n```'
    )
    done, req = GameNegotiationAgent._try_extract_done(text)
    assert done is True
    assert req["project_name"] == "夏クイズ"


def test_game_negotiation_run_writes_game_requirements(monkeypatch, config, workspace):
    agent = GameNegotiationAgent(config)
    agent.client = _FakeAnthropic(
        messages=_Msgs(
            scripted=[
                '```json\n{"done": true, "requirements": {'
                '"project_name": "夏クイズ", '
                '"business_goal": "集客", '
                '"summary_ja": "夏の販促クイズ", '
                '"target_audience": ["新規顧客"], '
                '"preferred_templates": ["quiz"], '
                '"core_mechanics": ["3問クイズ"], '
                '"required_scenes": ["title", "play", "result"], '
                '"reward_flow": ["結果後にクーポン表示"], '
                '"brand_notes": ["明るい"], '
                '"available_assets": ["ロゴ"], '
                '"missing_assets": ["BGM"], '
                '"analytics_events": ["game_start"], '
                '"integrations": ["Google Analytics"], '
                '"acceptance_criteria": ["スマホで快適に遊べる"]'
                "}}\n```"
            ]
        )
    )
    monkeypatch.setattr("builtins.input", lambda prompt="": "販促用のゲームを作りたいです")
    req = agent.run(workspace, package=GamePackage.CAMPAIGN)
    assert req.project_name == "夏クイズ"
    assert workspace.game_requirements_path.exists()
    assert workspace.game_transcript_path.exists()
    assert req.preferred_templates == [GameTemplate.QUIZ]


def test_game_plan_agent_writes_game_artifacts(config, workspace):
    workspace.save_game_requirements(
        __import__("smbagent.game_studio", fromlist=["GameRequirements"]).GameRequirements(
            customer_id=workspace.customer_id,
            package=GamePackage.CAMPAIGN,
            project_name="夏クイズ",
            business_goal="集客",
            summary_ja="夏の販促クイズ",
            acceptance_criteria=["スマホで快適に遊べる"],
        )
    )
    workspace.game_transcript_path.write_text("USER: 夏の販促です", encoding="utf-8")

    agent = GamePlanAgent(config)
    agent.client = _FakeAnthropic(
        messages=_Msgs(
            scripted=[
                '```json\n{"design_markdown": "# Game Plan", "plan": {'
                '"package": "campaign", '
                '"summary": "Campaign quiz for summer promotion.", '
                '"primary_template": "quiz", '
                '"scenes": ['
                '{"name": "title", "purpose": "entry", "key_ui": ["cta"]}, '
                '{"name": "play", "purpose": "quiz", "key_ui": ["question"]}, '
                '{"name": "result", "purpose": "result", "key_ui": ["coupon"]}'
                "], "
                '"assets": ['
                '{"name": "logo", "kind": "logo", "required": true, "source": "customer-uploaded", "usage": ["title"]}'
                "], "
                '"site_pages": ["/"], '
                '"ops_features": ["coupon display"], '
                '"analytics_events": ["game_start", "game_complete"]'
                "}}\n```"
            ]
        )
    )
    plan = agent.run(workspace)
    assert plan.primary_template == GameTemplate.QUIZ
    assert workspace.game_design_path.exists()
    assert workspace.scene_map_path.exists()
    assert workspace.release_checklist_path.exists()
