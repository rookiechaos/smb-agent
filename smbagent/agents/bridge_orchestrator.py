"""Deterministic relay between Coding (A) and Validation (B).

Parallel creative agents must not pass raw conversational context to each other.
This agent uses temperature=0 and a short token budget to normalize handoffs.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..config import Config
from ..iteration_tuning import IterationTuning
from ..observability import UsageLogger
from ..types import HumanizeVerdict, Verdict
from ..workspace import Workspace
from . import build_anthropic_client

_MAX_SOURCE_CHARS = 12_000
_MAX_CODE_FILES = 200
_PATH_RE = re.compile(r"(?:landing-page|agent-skills|integrations)/[A-Za-z0-9._/-]+|README\.md")


class BridgeOrchestratorAgent:
    """Parameter-isolated relay: extract → format → write bridge artifact."""

    def __init__(self, config: Config, tuning: IterationTuning):
        self.config = config
        self.tuning = tuning
        self.client = None
        self.system_prompt = (config.prompts_dir / "bridge_orchestrator.md").read_text(encoding="utf-8")

    def relay_validation_to_coding(
        self,
        workspace: Workspace,
        verdict: Verdict,
    ) -> Path:
        """After B rejects A: produce ``bridge_for_coding.md`` for the next coding round."""
        round_dir = workspace.round_dir(verdict.round)
        sources: list[str] = []

        feedback_path = workspace.feedback_path(verdict.round)
        if feedback_path.exists():
            sources.append(
                f"# feedback.md (round {verdict.round})\n\n"
                + _truncate(feedback_path.read_text(encoding="utf-8"), _MAX_SOURCE_CHARS)
            )

        sources.append(
            f"# verdict.json (round {verdict.round})\n\n"
            + _truncate(verdict.model_dump_json(indent=2), _MAX_SOURCE_CHARS)
        )

        user_msg = (
            "Validation agent (B) finished reviewing. Format a **coding handoff** for agent A.\n\n"
            "Required output sections (use these exact headings):\n"
            "## Round\n"
            "## Verdict\n"
            "## Critical path (ordered list)\n"
            "## Issues by file\n"
            "## Do not\n\n"
            "Source material:\n\n" + "\n\n---\n\n".join(sources)
        )

        body = self._complete(workspace, user_msg, stage="bridge_validation_to_coding")
        out = round_dir / "bridge_for_coding.md"
        out.write_text(body, encoding="utf-8")
        return out

    def relay_coding_to_validation(
        self,
        workspace: Workspace,
        round_n: int,
    ) -> Path:
        """Legacy A→B relay.

        The main orchestrator no longer calls this in strict isolation mode:
        validation must not receive coding logs, summaries, private intent, or
        memory. Kept only for backward compatibility with older tests/tools.
        """
        round_dir = workspace.round_dir(round_n)
        log_path = workspace.coding_log_path(round_n)
        log_summary = (
            _summarize_coding_log(log_path.read_text(encoding="utf-8"))
            if log_path.exists()
            else "(no coding.log yet)"
        )
        code_inventory = _code_inventory(workspace.code_dir)

        user_msg = (
            f"Coding agent (A) completed round {round_n}. Format a **validation handoff** "
            "for agent B.\n\n"
            "Required output sections (use these exact headings):\n"
            "## Round\n"
            "## Files likely touched\n"
            "## Stated intent\n"
            "## Risks called out in summary\n\n"
            f"# code inventory (round {round_n})\n\n{code_inventory}\n\n"
            f"# sanitized coding summary (round {round_n})\n\n{log_summary}"
        )

        body = self._complete(workspace, user_msg, stage="bridge_coding_to_validation")
        out = round_dir / "bridge_for_validation.md"
        out.write_text(body, encoding="utf-8")
        return out

    def relay_humanize_critic_to_writer(
        self,
        workspace: Workspace,
        verdict: HumanizeVerdict,
    ) -> Path:
        """After humanize critic (B) fails: handoff for writer (A) next round."""
        round_dir = workspace.humanize_round_dir(verdict.round)
        sources: list[str] = []
        fb = workspace.humanize_feedback_path(verdict.round)
        if fb.exists():
            sources.append(
                f"# humanize_feedback.md (round {verdict.round})\n\n"
                + _truncate(fb.read_text(encoding="utf-8"), _MAX_SOURCE_CHARS)
            )
        sources.append(
            "# humanize_verdict.json\n\n" + _truncate(verdict.model_dump_json(indent=2), _MAX_SOURCE_CHARS)
        )
        user_msg = (
            "Humanize critic (B) finished. Format a **humanize writer handoff** for agent A.\n\n"
            "Required sections:\n"
            "## Round\n"
            "## Rubric score\n"
            "## Critical path (ordered)\n"
            "## Issues by file (pattern tags)\n"
            "## Do not (no new facts)\n\n" + "\n\n---\n\n".join(sources)
        )
        body = self._complete(workspace, user_msg, stage="bridge_humanize_critic_to_writer")
        out = round_dir / "bridge_for_humanize.md"
        out.write_text(body, encoding="utf-8")
        return out

    def _complete(self, workspace: Workspace, user_msg: str, *, stage: str) -> str:
        client = self.client or build_anthropic_client(self.config)
        response = client.messages.create(
            model=self.tuning.bridge_orchestrator_model,
            max_tokens=self.tuning.bridge_orchestrator_max_tokens,
            temperature=self.tuning.bridge_orchestrator_temperature,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )
        UsageLogger(workspace).record(
            provider="anthropic",
            surface="api",
            stage=stage,
            model=self.tuning.bridge_orchestrator_model,
            response=response,
        )
        return "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ).strip()


def _truncate(s: str, limit: int) -> str:
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


def _code_inventory(code_dir: Path) -> str:
    files = [p.relative_to(code_dir).as_posix() for p in sorted(code_dir.rglob("*")) if p.is_file()]
    if not files:
        return "(code/ is empty)"
    if len(files) > _MAX_CODE_FILES:
        files = files[:_MAX_CODE_FILES] + ["(truncated)"]
    return "\n".join(f"- {path}" for path in files)


def _summarize_coding_log(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("returncode:"):
            lines.append(line)
            continue
        if any(word in line.lower() for word in ("edited", "created", "updated", "wrote", "saved")):
            paths = _PATH_RE.findall(line)
            if paths:
                lines.append(f"mentioned paths: {', '.join(dict.fromkeys(paths))}")
    if not lines:
        return "(no structured coding summary found in log)"
    return _truncate("\n".join(dict.fromkeys(lines)), _MAX_SOURCE_CHARS)
