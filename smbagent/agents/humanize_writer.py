"""Humanize Writer (A) — rewrites customer-facing copy from critic feedback."""

from __future__ import annotations

import json

from .._jsonx import extract_json
from ..annealing import AnnealingState, temperature_prompt_section
from ..config import Config
from ..humanize_targets import build_corpus_snapshot, is_allowed_humanize_rel
from ..observability import UsageLogger
from ..types import HumanizeVerdict
from ..workspace import Workspace
from . import build_anthropic_client


class HumanizeWriterAgent:
    def __init__(self, config: Config):
        self.config = config
        self.client = None
        self.prompt_template = (config.prompts_dir / "humanize_ja.md").read_text(encoding="utf-8")

    def run(
        self,
        workspace: Workspace,
        round_n: int,
        prior_verdict: HumanizeVerdict | None,
        *,
        annealing: AnnealingState | None = None,
    ) -> None:
        requirements = workspace.load_requirements()
        corpus = build_corpus_snapshot(workspace.code_dir)
        handoff = self._handoff_section(workspace, round_n, prior_verdict)
        system = self.prompt_template.replace("{handoff_section}", handoff)

        user_msg = (
            f"# Round\n{round_n}\n\n"
            f"# requirements.json\n\n```json\n{requirements.model_dump_json(indent=2)}\n```\n\n"
            f"# Current copy\n\n{corpus}\n"
        )
        if annealing is not None:
            user_msg = f"{temperature_prompt_section(annealing)}\n\n{user_msg}"

        client = self.client or build_anthropic_client(self.config)
        response = client.messages.create(
            model=self.config.plan_model,
            max_tokens=16000,
            temperature=annealing.temperature if annealing else 0.7,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
        UsageLogger(workspace).record(
            provider="anthropic",
            surface="api",
            stage="humanize_writer",
            model=self.config.plan_model,
            round_n=round_n,
            response=response,
        )
        text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
        log_path = workspace.humanize_writer_log_path(round_n)
        try:
            payload = extract_json(text)
            if (
                isinstance(payload, dict)
                and payload.get("format") == "polyarch/humanize"
                and isinstance(payload.get("payload"), dict)
            ):
                payload = payload["payload"]
            edits = payload.get("edits", [])
            applied = self._apply_edits(workspace, edits)
            log_path.write_text(
                json.dumps({"applied": applied, "notes": payload.get("notes", "")}, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            log_path.write_text(
                f"humanize writer failed to parse/apply: {e}\n\n--- raw ---\n{text[:8000]}",
                encoding="utf-8",
            )
            raise

    def _handoff_section(
        self,
        workspace: Workspace,
        round_n: int,
        prior_verdict: HumanizeVerdict | None,
    ) -> str:
        if prior_verdict is None or round_n == 1:
            return (
                "## Handoff\n\n"
                "**Round 1.** 初回の人間味調整。上記コピー全体を読み、"
                "SMB のお客様らしい自然な日本語に整える。"
            )
        prev = prior_verdict.round
        bridge = workspace.bridge_for_humanize_path(prev)
        feedback = workspace.humanize_feedback_path(prev)
        if bridge.exists():
            body = bridge.read_text(encoding="utf-8")
            source = "bridge_for_humanize.md"
        elif feedback.exists():
            body = feedback.read_text(encoding="utf-8")
            source = "humanize_feedback.md"
        else:
            body = prior_verdict.summary
            source = "prior verdict summary only"
        return (
            f"## Handoff\n\n"
            f"**Round {round_n}.** 前ラウンド（{prev}）は不合格。以下の {source} に従い、"
            "listed issues をすべて解消してから `edits` を返す。\n\n"
            f"{body}\n"
        )

    def _apply_edits(self, workspace: Workspace, edits: list) -> list[str]:
        applied: list[str] = []
        if not isinstance(edits, list):
            return applied
        for item in edits:
            if not isinstance(item, dict):
                continue
            rel = str(item.get("path", "")).strip().lstrip("/")
            content = item.get("content")
            if not rel or not isinstance(content, str):
                continue
            if not is_allowed_humanize_rel(rel):
                continue
            dest = workspace.code_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            applied.append(rel)
        return applied
