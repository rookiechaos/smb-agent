from __future__ import annotations

import json
from dataclasses import replace
from unittest.mock import MagicMock

from smbagent.agents.humanize_critic import HumanizeCriticAgent
from smbagent.agents.humanize_writer import HumanizeWriterAgent
from smbagent.humanize_loop import HumanizeLoop, detect_humanize_deadlock
from smbagent.humanize_targets import is_allowed_humanize_rel, iter_humanize_target_paths
from smbagent.observability import TransitionLogger, hash_file
from smbagent.pipeline_state import HUMANIZE_PASSED_STATE, HUMANIZE_STATE, PipelineState
from smbagent.types import (
    HumanizeVerdict,
    Requirements,
    Tier,
    Verdict,
)
from smbagent.workspace import Workspace


def _fake_block(text: str):
    b = MagicMock()
    b.type = "text"
    b.text = text
    return b


def _seed_requirements(workspace: Workspace) -> None:
    workspace.save_requirements(
        Requirements(
            customer_id=workspace.customer_id,
            tier=Tier.GROWTH,
            business_name="テスト歯科",
            summary_ja="地域の歯科医院",
            target_users=["近所の家族"],
            brand_notes=["親しみやすい"],
            desired_skills=["faq"],
            desired_integrations=["gmail"],
            acceptance_criteria=["予約導線"],
        )
    )


def _seed_copy(workspace: Workspace) -> None:
    lp = workspace.code_dir / "landing-page"
    lp.mkdir(parents=True, exist_ok=True)
    (lp / "index.html").write_text(
        "<p>まず、当社は革新的なソリューションを提供します。最後にぜひお問い合わせください。</p>",
        encoding="utf-8",
    )
    skills = workspace.code_dir / "agent-skills"
    skills.mkdir(parents=True, exist_ok=True)
    (skills / "faq.md").write_text(
        "---\nname: faq\ndescription: FAQ\n---\n\n弊社のサービスについてお答えします。",
        encoding="utf-8",
    )


def test_humanize_targets_only_landing_and_skills(workspace: Workspace):
    _seed_copy(workspace)
    paths = iter_humanize_target_paths(workspace.code_dir)
    rels = {p.name for p in paths}
    assert "index.html" in rels
    assert "faq.md" in rels
    assert is_allowed_humanize_rel("landing-page/index.html")
    assert not is_allowed_humanize_rel("integrations/foo/README.md")


def test_critic_enforces_pass_threshold(config, workspace: Workspace):
    _seed_requirements(workspace)
    _seed_copy(workspace)
    agent = HumanizeCriticAgent(config)
    payload = {
        "passed": True,
        "round": 1,
        "summary": "ok",
        "rubric_score": 0.5,
        "issues": [
            {
                "severity": "major",
                "file": "landing-page/index.html",
                "pattern": "template_triad",
                "description": "x",
            }
        ],
    }
    agent.client = MagicMock()
    agent.client.messages.create.return_value = MagicMock(content=[_fake_block(json.dumps(payload))])
    verdict = agent.run(workspace, 1)
    assert verdict.passed is False
    assert workspace.humanize_verdict_path(1).exists()


def test_critic_accepts_polyarch_humanize_envelope(config, workspace: Workspace):
    _seed_requirements(workspace)
    _seed_copy(workspace)
    agent = HumanizeCriticAgent(config)
    payload = {
        "format": "polyarch/humanize",
        "payload": {
            "passed": True,
            "round": 1,
            "summary": "自然",
            "rubric_score": 0.9,
            "issues": [],
        },
    }
    agent.client = MagicMock()
    agent.client.messages.create.return_value = MagicMock(content=[_fake_block(json.dumps(payload))])
    verdict = agent.run(workspace, 1)
    assert verdict.passed is True
    assert verdict.summary == "自然"


def test_writer_applies_edits(config, workspace: Workspace):
    _seed_requirements(workspace)
    _seed_copy(workspace)
    agent = HumanizeWriterAgent(config)
    new_html = "<p>テスト歯科のホームページです。ご予約はお電話で。</p>"
    agent.client = MagicMock()
    agent.client.messages.create.return_value = MagicMock(
        content=[
            _fake_block(
                json.dumps(
                    {
                        "edits": [{"path": "landing-page/index.html", "content": new_html}],
                        "notes": "直した",
                    }
                )
            )
        ]
    )
    agent.run(workspace, 1, None)
    assert (workspace.code_dir / "landing-page" / "index.html").read_text(encoding="utf-8") == new_html


def test_writer_accepts_polyarch_humanize_envelope(config, workspace: Workspace):
    _seed_requirements(workspace)
    _seed_copy(workspace)
    agent = HumanizeWriterAgent(config)
    new_html = "<p>テスト歯科です。</p>"
    agent.client = MagicMock()
    agent.client.messages.create.return_value = MagicMock(
        content=[
            _fake_block(
                json.dumps(
                    {
                        "format": "polyarch/humanize",
                        "payload": {
                            "edits": [{"path": "landing-page/index.html", "content": new_html}],
                            "notes": "polyarch envelope",
                        },
                    }
                )
            )
        ]
    )
    agent.run(workspace, 1, None)
    assert (workspace.code_dir / "landing-page" / "index.html").read_text(encoding="utf-8") == new_html


def test_humanize_deadlock_on_repeated_summary(config, workspace: Workspace):
    for r in (1, 2):
        v = HumanizeVerdict(
            passed=False,
            round=r,
            summary="同じ要約",
            rubric_score=0.6,
            issues=[],
        )
        workspace.humanize_verdict_path(r).write_text(v.model_dump_json(indent=2), encoding="utf-8")
    assert detect_humanize_deadlock(workspace, through_round=2)


def test_humanize_loop_skipped_when_disabled(config, workspace: Workspace, monkeypatch):
    cfg = replace(config, humanize_enabled=False)
    loop = HumanizeLoop(cfg)
    assert loop.run(workspace) is None


def test_humanize_loop_passes_in_one_round(config, workspace: Workspace, monkeypatch):
    _seed_requirements(workspace)
    _seed_copy(workspace)
    workspace.save_verdict(Verdict(passed=True, round=1, summary="validation ok"))

    passing = HumanizeVerdict(
        passed=True,
        round=1,
        summary="自然",
        rubric_score=0.9,
        issues=[],
    )

    class FakeWriter:
        def run(self, ws: Workspace, round_n: int, *a, **k):
            ws.humanize_writer_log_path(round_n).write_text(
                "fake writer\n",
                encoding="utf-8",
            )

    class FakeCritic:
        def run(self, ws: Workspace, round_n: int, *a, **k):
            ws.humanize_verdict_path(round_n).write_text(
                passing.model_dump_json(indent=2),
                encoding="utf-8",
            )
            return passing

    transitions = TransitionLogger(workspace)
    loop = HumanizeLoop(config)
    loop.writer = FakeWriter()
    loop.critic = FakeCritic()
    result = loop.run(workspace, transitions=transitions)
    assert result is not None and result.passed

    events = transitions.read_all()
    assert len(events) == 2
    assert events[0].agent == "humanize"
    assert events[0].from_state == PipelineState.PASSED.value
    assert events[0].to_state == HUMANIZE_STATE
    assert events[0].round_n == 1
    assert events[0].success is True

    assert events[1].agent == "humanize_critic"
    # Critic writes humanize_verdict.json before enforce runs, so derive_state
    # already reflects humanize_passed when the transition is recorded.
    assert events[1].from_state == HUMANIZE_PASSED_STATE
    assert events[1].to_state == HUMANIZE_PASSED_STATE
    assert events[1].round_n == 1
    assert events[1].success is True
    assert events[1].output_hash == hash_file(workspace.humanize_verdict_path(1))
