"""End-to-end pipeline evaluation with every external service stubbed.

This is an *evaluation* test, not a unit test: it runs the actual Pipeline.run()
top to bottom — Qualify, Negotiation, Plan, Coding loop, Validation — and asserts
that every workspace artifact materializes with the right shape and content.

No network. No real subprocess. The point is to verify the wiring between stages.

Implementation note: `coding_mod.subprocess` and `validation_mod.subprocess` are
the same shared module object, so we cannot install two different `run` patches
in parallel — the second would shadow the first. We use one dispatcher fake that
routes based on argv[0] ("claude" vs "codex").
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from smbagent.config import Config
from smbagent.orchestrator import Pipeline
from smbagent.types import Tier
from smbagent.workspace import Workspace
from tests._popen_mocks import popen_from_run

# ---- Fake LLM client (Anthropic SDK stand-in for Qualify, Negotiation, Plan) ----


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

    def create(self, *, model, max_tokens, system, messages):
        if self.idx >= len(self.scripted):
            raise AssertionError(f"LLM called more times than scripted ({self.idx + 1})")
        text = self.scripted[self.idx]
        self.idx += 1
        return _Resp(content=[_Block(text)])


@dataclass
class _FakeAnthropic:
    messages: _Msgs


# ---- Canned LLM responses ----


def _qualify_response() -> str:
    return json.dumps(
        {
            "go": True,
            "recommended_tier": "growth",
            "summary_ja": "中規模クリニック向けに適合します。",
            "reasoning_en": "Mid-sized dental clinic — growth tier fits.",
        }
    )


def _negotiation_user_turns() -> list[str]:
    return [
        "東京の歯科医院です。患者さんからの問い合わせと予約をAIに任せたい。",
        "メインの利用者は新規の患者さんです。ブランドは清潔感があって親しみやすい雰囲気で。",
        "問い合わせ対応、予約受付、よくある質問への回答、フォローアップの4つのスキルが欲しい。",
        "GmailとGoogle Calendarに繋いでほしい。",
        "毎月20件以上の新規予約が取れていて、問い合わせの90%以上がAIで完結すれば完成と言える。",
    ]


def _negotiation_agent_responses() -> list[str]:
    return [
        "ありがとうございます。対象となる利用者はどなたですか？",
        "なるほど。AIに任せたい業務を具体的に教えてください。",
        "了解しました。連携したいツールはありますか？",
        "ありがとうございます。完成と判断する基準は？",
        "ありがとうございました。要件を整理します。\n\n```json\n"
        + json.dumps(
            {
                "done": True,
                "requirements": {
                    "business_name": "東京ホワイトデンタル",
                    "summary_ja": "東京の歯科医院向け問い合わせ・予約AIシステム。",
                    "target_users": ["新規の患者", "既存の患者"],
                    "brand_notes": ["清潔感", "親しみやすい"],
                    "desired_skills": ["問い合わせ対応", "予約受付", "FAQ", "フォローアップ"],
                    "desired_integrations": ["Gmail", "Google Calendar"],
                    "acceptance_criteria": [
                        "毎月20件以上の新規予約",
                        "問い合わせの90%以上がAIで完結",
                    ],
                },
            }
        )
        + "\n```",
    ]


def _plan_response() -> str:
    return json.dumps(
        {
            "plan_markdown": "# Plan for 東京ホワイトデンタル\n\nStandardized growth-tier deliverable.",
            "plan": {
                "tier": "growth",
                "summary": "Branded site + 4 agent skills + 2 integrations for a Tokyo dental clinic.",
                "landing_page": {
                    "pages": ["/", "/services", "/booking", "/contact"],
                    "hero_copy_outline": "Clean, welcoming hero. CTA to book.",
                    "primary_cta": "今すぐ予約",
                    "sections": ["hero", "services", "testimonials", "contact"],
                },
                "agent_skills": [
                    {
                        "name": "understand-white-dental",
                        "description": "Company context.",
                        "system_prompt_outline": "...",
                    },
                    {
                        "name": "handle-inquiry",
                        "description": "Patient questions.",
                        "system_prompt_outline": "...",
                    },
                    {
                        "name": "book-appointment",
                        "description": "Schedules new appts.",
                        "system_prompt_outline": "...",
                    },
                    {"name": "answer-faq", "description": "Answers FAQ.", "system_prompt_outline": "..."},
                    {
                        "name": "follow-up",
                        "description": "Post-visit follow-up.",
                        "system_prompt_outline": "...",
                    },
                ],
                "integrations": [
                    {"name": "Gmail", "purpose": "Forward leads from contact form."},
                    {"name": "Google Calendar", "purpose": "Read/write appointment slots."},
                ],
            },
        }
    )


# ---- Subprocess dispatcher: one fake handles both claude AND codex ----


def _make_dispatch(
    workspace: Workspace,
    *,
    claude_writes: bool = True,
    codex_pass_on_round: int | None = 1,
    missing_file_on_first_round: str | None = None,
):
    """Build a `subprocess.run` stand-in that routes based on argv[0].

    Args:
        claude_writes: If True, claude writes the standardized skeleton on each call.
        codex_pass_on_round: Round number at which codex starts passing (None = never).
        missing_file_on_first_round: If set, on round 1 claude skips writing this filename
                                     under code/agent-skills/ — useful for testing the loop.
    """
    round_state = {"claude_calls": 0, "codex_calls": 0}

    def dispatch(cmd, cwd=None, capture_output=False, text=False, timeout=None, check=False, **_kwargs):
        tool = cmd[0]
        if tool == "claude":
            round_state["claude_calls"] += 1
            current = round_state["claude_calls"]
            if claude_writes:
                _write_skeleton(
                    workspace.code_dir,
                    skip_skill=missing_file_on_first_round if current == 1 else None,
                )
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="claude done", stderr="")

        if tool == "codex":
            round_state["codex_calls"] += 1
            r = round_state["codex_calls"]
            passed = codex_pass_on_round is not None and r >= codex_pass_on_round
            issues = []
            if not passed:
                issues = [
                    {
                        "severity": "critical",
                        "description": (
                            f"missing {missing_file_on_first_round}.md"
                            if missing_file_on_first_round
                            else "not yet satisfied"
                        ),
                    }
                ]
            workspace.verdict_path(r).write_text(
                json.dumps(
                    {
                        "passed": passed,
                        "summary": "all good" if passed else "needs work",
                        "issues": issues,
                    }
                ),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="codex done", stderr="")

        raise AssertionError(f"Unexpected subprocess invocation: {cmd!r}")

    return dispatch, round_state


def _write_skeleton(code_dir: Path, *, skip_skill: str | None = None) -> None:
    """Write the standardized smbagent deliverable under code_dir."""
    code_dir.mkdir(parents=True, exist_ok=True)

    lp = code_dir / "landing-page"
    lp.mkdir(exist_ok=True)
    (lp / "index.html").write_text(
        "<!doctype html><html><body><h1>東京ホワイトデンタル</h1>"
        "<a href='/booking'>今すぐ予約</a></body></html>",
        encoding="utf-8",
    )
    for page in ("services", "booking", "contact"):
        (lp / f"{page}.html").write_text(f"<!doctype html><html><body>{page}</body></html>", encoding="utf-8")

    skills_dir = code_dir / "agent-skills"
    skills_dir.mkdir(exist_ok=True)
    for name in ("understand-white-dental", "handle-inquiry", "book-appointment", "answer-faq", "follow-up"):
        if name == skip_skill:
            continue
        (skills_dir / f"{name}.md").write_text(
            f"---\nname: {name}\ndescription: stub skill\n---\n\n# Instructions\n\nStub.\n",
            encoding="utf-8",
        )

    integ_dir = code_dir / "integrations"
    integ_dir.mkdir(exist_ok=True)
    for provider in ("gmail", "google-calendar"):
        p = integ_dir / provider
        p.mkdir(exist_ok=True)
        (p / "README.md").write_text(f"# {provider}\n\nSetup notes.\n", encoding="utf-8")
        (p / "config.example.json").write_text(json.dumps({"api_key": "<PLACEHOLDER>"}), encoding="utf-8")

    (code_dir / "README.md").write_text("# Deliverable\n", encoding="utf-8")


def _install_anthropic_fake(pipeline: Pipeline, scripted: list[str]) -> _Msgs:
    msgs = _Msgs(scripted=scripted)
    client = _FakeAnthropic(messages=msgs)
    pipeline.qualify.client = client  # type: ignore[assignment]
    pipeline.negotiation.client = client  # type: ignore[assignment]
    pipeline.plan.client = client  # type: ignore[assignment]
    return msgs


def _build_full_script() -> list[str]:
    script = [_qualify_response()]
    script.extend(_negotiation_agent_responses())
    script.append(_plan_response())
    return script


# ============================================================================
# Tests
# ============================================================================


def test_full_pipeline_end_to_end_with_mocks(config: Config, monkeypatch):
    """Pipeline.run() top-to-bottom; verify every artifact materializes correctly."""
    customer_id = "white-dental"
    workspace = Workspace(customer_id, config.workspaces_dir)
    workspace.ensure()

    p = Pipeline(config)
    _install_anthropic_fake(p, _build_full_script())

    turn_iter = iter(_negotiation_user_turns())
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(turn_iter))

    dispatch, _ = _make_dispatch(workspace, codex_pass_on_round=1)
    monkeypatch.setattr(subprocess, "Popen", popen_from_run(dispatch))  # patches the shared subprocess.run

    result = p.run(customer_id, customer_brief="Tokyo dental clinic, 8 staff.")

    assert result is not None
    assert result.passed is True
    assert result.round == 1

    # qualification.json
    q = workspace.load_qualification()
    assert q.go is True
    assert q.recommended_tier == Tier.GROWTH

    # requirements.json — must reflect the negotiation conversation
    req = workspace.load_requirements()
    assert req.tier == Tier.GROWTH
    assert req.business_name == "東京ホワイトデンタル"
    assert "問い合わせ対応" in req.desired_skills
    assert "Gmail" in req.desired_integrations
    assert len(req.acceptance_criteria) >= 2

    # transcript.txt
    transcript = workspace.transcript_path.read_text(encoding="utf-8")
    assert "東京の歯科医院" in transcript
    assert "AGENT:" in transcript and "USER:" in transcript

    # plan.md + tasks.json — within growth-tier caps
    plan = workspace.load_plan()
    assert plan.tier == Tier.GROWTH
    assert len(plan.agent_skills) == 5
    assert len(plan.landing_page.pages) == 4
    assert len(plan.integrations) == 2
    assert plan.violates_tier_caps() == []

    # code/ has the standardized shape
    assert (workspace.code_dir / "landing-page").is_dir()
    assert (workspace.code_dir / "agent-skills").is_dir()
    assert (workspace.code_dir / "integrations").is_dir()
    assert (workspace.code_dir / "README.md").exists()

    skills = sorted((workspace.code_dir / "agent-skills").glob("*.md"))
    assert len(skills) == 5
    for sf in skills:
        content = sf.read_text(encoding="utf-8")
        assert content.startswith("---\nname:"), f"{sf.name} missing frontmatter"
        assert f"name: {sf.stem}" in content

    integ_dirs = sorted(d for d in (workspace.code_dir / "integrations").iterdir() if d.is_dir())
    assert len(integ_dirs) == 2
    for d in integ_dirs:
        assert (d / "README.md").exists()
        assert (d / "config.example.json").exists()

    # round-1 artifacts
    rd = workspace.round_dir(1)
    assert (rd / "coding.log").exists()
    assert (rd / "validation.log").exists()
    assert (rd / "verdict.json").exists()
    fb = (rd / "feedback.md").read_text(encoding="utf-8")
    assert "PASSED" in fb
    monitor = json.loads(workspace.workflow_monitor_path.read_text(encoding="utf-8"))
    assert monitor["status"] == "passed"
    assert monitor["active_stage"] == "done"


def test_pipeline_iterates_then_passes(config: Config, monkeypatch):
    """Round 1 fails (missing skill), round 2 passes after Claude addresses feedback."""
    customer_id = "clinic-iter"
    workspace = Workspace(customer_id, config.workspaces_dir)
    workspace.ensure()

    p = Pipeline(config)
    _install_anthropic_fake(p, _build_full_script())
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(turn_iter))
    turn_iter = iter(_negotiation_user_turns())  # noqa: F841 (used above via closure)

    dispatch, state = _make_dispatch(
        workspace,
        codex_pass_on_round=2,
        missing_file_on_first_round="answer-faq",
    )
    monkeypatch.setattr(subprocess, "Popen", popen_from_run(dispatch))

    result = p.run(customer_id, customer_brief="dental, 8 staff")

    assert result is not None and result.passed is True
    assert result.round == 2
    assert state["claude_calls"] == 2
    assert state["codex_calls"] == 2

    # Round 1 feedback.md should list the critical issue
    fb1 = workspace.feedback_path(1).read_text(encoding="utf-8")
    assert "FAILED" in fb1
    assert "answer-faq" in fb1
    # Round 2 feedback.md is the passed-summary form
    fb2 = workspace.feedback_path(2).read_text(encoding="utf-8")
    assert "PASSED" in fb2
    mem = workspace.path / "failure_memory.jsonl"
    assert mem.exists()
    rows = [json.loads(line) for line in mem.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) >= 1
    assert rows[0]["schema_version"] == 2
    assert rows[0]["stage"] == "validation"
    assert rows[0]["outcome"] == "failed_verdict"
    assert rows[0]["round_n"] == 1
    assert rows[0]["tier"] == "growth"
    assert rows[0]["coding_tool"] == "claude"
    assert rows[0]["validation_tool"] == "codex"
    assert rows[0]["validation_backend"] == config.validation_backend
    assert rows[0]["tuning"]["anneal_temp_creative"] == config.anneal_temp_creative


def test_pipeline_no_go_halts_before_any_code_or_input(config: Config, monkeypatch):
    """A no-go qualification must NOT trigger negotiation, coding, or validation."""
    customer_id = "out-of-scope"
    p = Pipeline(config)

    no_go = json.dumps(
        {
            "go": False,
            "recommended_tier": None,
            "summary_ja": "国際的な大手銀行は範囲外です。",
        }
    )
    p.qualify.client = _FakeAnthropic(messages=_Msgs(scripted=[no_go]))  # type: ignore[assignment]

    # Sentinels: anything downstream getting invoked is a bug.
    def boom_subprocess(*a, **kw):
        raise AssertionError("subprocess should NOT run after no-go qualification")

    monkeypatch.setattr(subprocess, "Popen", boom_subprocess)
    monkeypatch.setattr("builtins.input", lambda _prompt="": pytest.fail("negotiation must not run"))

    result = p.run(customer_id, customer_brief="multinational bank")
    assert result is None

    ws = Workspace(customer_id, config.workspaces_dir)
    assert ws.qualification_path.exists()
    assert not ws.requirements_path.exists()
    assert not ws.plan_path.exists()
    assert ws.code_dir.exists()  # ensure() created it
    assert list(ws.code_dir.iterdir()) == []  # but nothing inside


def test_pipeline_respects_tier_override_in_full_run(config: Config, monkeypatch):
    """--tier business overrides the qualifier's recommendation."""
    customer_id = "override-test"
    workspace = Workspace(customer_id, config.workspaces_dir)
    workspace.ensure()

    p = Pipeline(config)
    # Build a script where qualify recommends growth but we override to business.
    # Plan response also returns "growth" (the model is consistent with whatever).
    # Negotiation should still ask using business tier caps in its prompt.
    # We expect requirements.tier == business after negotiation.
    script = _build_full_script()
    # Patch the plan response to use business tier so Plan validation passes.
    script[-1] = script[-1].replace('"tier": "growth"', '"tier": "business"')
    _install_anthropic_fake(p, script)

    turn_iter = iter(_negotiation_user_turns())
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(turn_iter))

    dispatch, _ = _make_dispatch(workspace, codex_pass_on_round=1)
    monkeypatch.setattr(subprocess, "Popen", popen_from_run(dispatch))

    result = p.run(
        customer_id,
        customer_brief="dental, 8 staff",
        tier_override=Tier.BUSINESS,
    )

    assert result is not None and result.passed is True
    req = workspace.load_requirements()
    assert req.tier == Tier.BUSINESS  # override took effect
