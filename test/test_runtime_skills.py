"""Unit tests for the skills runtime."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

import smbagent.runtime.skills as skills_module
from smbagent.config import Config
from smbagent.runtime.skills import (
    SkillsRuntime,
    SkillsRuntimeError,
)
from smbagent.workspace import Workspace

# ---- Fake Anthropic client ----


@dataclass
class _Block:
    text: str
    type: str = "text"


@dataclass
class _Resp:
    content: list


@dataclass
class _Msgs:
    """Scripted Anthropic stub. Each call returns the next item in `scripted`."""

    scripted: list[str]
    calls: list[dict] = field(default_factory=list)
    idx: int = 0

    def create(self, *, model, max_tokens, system, messages):
        if self.idx >= len(self.scripted):
            raise AssertionError(f"LLM called {self.idx + 1} times, only scripted {len(self.scripted)}")
        text = self.scripted[self.idx]
        self.calls.append({"system": system, "messages": messages})
        self.idx += 1
        return _Resp(content=[_Block(text)])


@dataclass
class _FakeAnthropic:
    messages: _Msgs


# ---- Helpers ----


def _write_skill(skills_dir: Path, name: str, description: str, body: str) -> None:
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / f"{name}.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n{body}",
        encoding="utf-8",
    )


def _runtime_with_scripted(
    workspace: Workspace, config: Config, scripted: list[str]
) -> tuple[SkillsRuntime, _Msgs]:
    rt = SkillsRuntime(workspace, config)
    msgs = _Msgs(scripted=scripted)
    rt.client = _FakeAnthropic(messages=msgs)  # type: ignore[assignment]
    return rt, msgs


# ---- Loading ----


def test_runtime_loads_skills_from_disk(config: Config, workspace: Workspace):
    skills_dir = workspace.code_dir / "agent-skills"
    _write_skill(skills_dir, "understand-acme", "Acme context", "You represent Acme.")
    _write_skill(skills_dir, "book-appointment", "Schedules visits", "You book appointments.")

    rt = SkillsRuntime(workspace, config)
    names = [s.name for s in rt.skills]
    assert names == ["book-appointment", "understand-acme"]  # sorted glob order


def test_runtime_skill_object_carries_system_prompt(config: Config, workspace: Workspace):
    skills_dir = workspace.code_dir / "agent-skills"
    _write_skill(skills_dir, "x", "test skill", "BODY GOES HERE\nmore lines")

    rt = SkillsRuntime(workspace, config)
    assert len(rt.skills) == 1
    assert rt.skills[0].name == "x"
    assert rt.skills[0].description == "test skill"
    assert "BODY GOES HERE" in rt.skills[0].system_prompt
    assert rt.skills[0].source_path.name == "x.md"


def test_runtime_ignores_skills_with_no_frontmatter(config: Config, workspace: Workspace):
    skills_dir = workspace.code_dir / "agent-skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / "broken.md").write_text("no frontmatter just text", encoding="utf-8")
    _write_skill(skills_dir, "ok", "fine", "body")

    rt = SkillsRuntime(workspace, config)
    assert [s.name for s in rt.skills] == ["ok"]


def test_runtime_ignores_skills_missing_name_or_description(config: Config, workspace: Workspace):
    skills_dir = workspace.code_dir / "agent-skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / "no-desc.md").write_text("---\nname: no-desc\n---\n\nbody", encoding="utf-8")
    (skills_dir / "no-name.md").write_text("---\ndescription: orphan\n---\n\nbody", encoding="utf-8")
    _write_skill(skills_dir, "ok", "fine", "body")

    rt = SkillsRuntime(workspace, config)
    assert [s.name for s in rt.skills] == ["ok"]


def test_runtime_empty_skills_dir_returns_empty_list(config: Config, workspace: Workspace):
    # workspace.ensure() in the fixture creates code/ but not agent-skills/.
    rt = SkillsRuntime(workspace, config)
    assert rt.skills == []


def test_runtime_no_workspace_yet_returns_empty_list(config: Config, workspace: Workspace):
    """Skills dir doesn't exist — loader returns empty rather than raising."""
    (workspace.code_dir / "agent-skills").rmdir() if (workspace.code_dir / "agent-skills").exists() else None
    rt = SkillsRuntime(workspace, config)
    assert rt.skills == []


def test_list_skills_returns_name_description_tuples(config: Config, workspace: Workspace):
    skills_dir = workspace.code_dir / "agent-skills"
    _write_skill(skills_dir, "a", "first", "body a")
    _write_skill(skills_dir, "b", "second", "body b")

    rt = SkillsRuntime(workspace, config)
    assert rt.list_skills() == [("a", "first"), ("b", "second")]


# ---- Respond / routing ----


def test_respond_raises_when_no_skills_loaded(config: Config, workspace: Workspace):
    rt = SkillsRuntime(workspace, config)
    with pytest.raises(SkillsRuntimeError):
        rt.respond("hello")


def test_respond_routes_to_chosen_skill(config: Config, workspace: Workspace):
    skills_dir = workspace.code_dir / "agent-skills"
    _write_skill(skills_dir, "understand-acme", "Acme context", "You represent Acme.")
    _write_skill(skills_dir, "book-appointment", "Schedules visits", "You book appointments.")

    # Router picks "book-appointment", skill returns greeting.
    rt, msgs = _runtime_with_scripted(
        workspace,
        config,
        scripted=["book-appointment", "Sure, what date works for you?"],
    )

    response = rt.respond("I'd like to book a cleaning next Tuesday.")
    assert response.reply == "Sure, what date works for you?"
    assert response.skill_used == "book-appointment"

    assert len(msgs.calls) == 2
    # Router call's system prompt lists both skills with their descriptions
    router_sys = msgs.calls[0]["system"]
    assert "understand-acme" in router_sys and "Acme context" in router_sys
    assert "book-appointment" in router_sys and "Schedules visits" in router_sys
    # Skill call's system prompt is the chosen skill's body
    skill_sys = msgs.calls[1]["system"]
    assert "You book appointments." in skill_sys
    # Skill call gets the original user message verbatim
    assert msgs.calls[1]["messages"][0]["content"] == "I'd like to book a cleaning next Tuesday."


def test_respond_falls_back_to_first_skill_on_unknown_router_reply(config: Config, workspace: Workspace):
    """If router picks a skill name we don't know (or says "none"), we fall back to
    the first skill — which by convention is the `understand-<business>` context skill."""
    skills_dir = workspace.code_dir / "agent-skills"
    _write_skill(skills_dir, "understand-acme", "context", "I am the context skill.")
    _write_skill(skills_dir, "other-skill", "other", "I am the other skill.")

    rt, msgs = _runtime_with_scripted(
        workspace,
        config,
        scripted=["none", "fallback response"],
    )

    response = rt.respond("random off-topic question")
    assert response.reply == "fallback response"
    # The skill call used the FIRST skill (alphabetical: `other-skill` < `understand-acme`).
    assert response.skill_used == "other-skill"
    assert "other skill" in msgs.calls[1]["system"]


def test_respond_strips_quotes_and_backticks_from_router_reply(config: Config, workspace: Workspace):
    skills_dir = workspace.code_dir / "agent-skills"
    _write_skill(skills_dir, "x", "desc", "body")

    rt, msgs = _runtime_with_scripted(
        workspace,
        config,
        scripted=['`"x"`', "got it"],
    )

    response = rt.respond("hi")
    assert response.reply == "got it"
    assert response.skill_used == "x"
    # Despite the noisy router output, we found skill `x`.
    assert msgs.calls[1]["system"] == "body"


def test_respond_sends_skill_body_not_filename(config: Config, workspace: Workspace):
    """Defensive: the skill call must use the BODY (after frontmatter), not the raw file."""
    skills_dir = workspace.code_dir / "agent-skills"
    _write_skill(skills_dir, "x", "desc", "ONLY THIS LINE IS THE SYSTEM PROMPT")

    rt, msgs = _runtime_with_scripted(workspace, config, scripted=["x", "ok"])
    rt.respond("hi")

    sys_used = msgs.calls[1]["system"]
    assert "ONLY THIS LINE" in sys_used
    assert "---" not in sys_used  # frontmatter not leaked
    assert "name:" not in sys_used


def test_runtime_router_includes_slm_advisory_hint_when_available(
    config: Config, workspace: Workspace, monkeypatch
):
    skills_dir = workspace.code_dir / "agent-skills"
    _write_skill(skills_dir, "x", "desc", "body")

    monkeypatch.setattr(
        skills_module,
        "get_runtime_slm_advisory",
        lambda cfg, ws, msg: {  # noqa: ARG005
            "route_target": "workflow",
            "workflow_family": "ikida_gps",
            "hitl_recommended": False,
            "confidence": 0.91,
            "reasons_public": ["gps-like request"],
            "backend": "sglang",
            "model_name": "qwen3.5-2b",
        },
    )
    rt, msgs = _runtime_with_scripted(workspace, config, scripted=["x", "ok"])
    rt.respond("please help with gps report")

    router_sys = msgs.calls[0]["system"]
    assert "Advisory routing hint from the local SLM" in router_sys
    assert "workflow_family=ikida_gps" in router_sys
    advisory_log = workspace.path / "slm_advisory.jsonl"
    event = json.loads(advisory_log.read_text(encoding="utf-8").splitlines()[-1])
    assert event["stage"] == "runtime"
    assert event["applied"] is True
    assert event["skill_used"] == "x"


def test_runtime_replaces_unsafe_llm_reply_with_safe_fallback(config: Config, workspace: Workspace):
    skills_dir = workspace.code_dir / "agent-skills"
    _write_skill(skills_dir, "x", "desc", "body")

    rt, _msgs = _runtime_with_scripted(
        workspace,
        config,
        scripted=["x", "I have already sent the email and approved the booking."],
    )

    response = rt.respond("hi")
    assert "human-reviewed next step" in response.reply
    assert response.skill_used == "x"
    log_path = workspace.path / "llm_output_filter.jsonl"
    event = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert event["stage"] == "runtime"
    assert event["blocked"] is True
    assert "fake_external_action_claim" in event["categories"]
