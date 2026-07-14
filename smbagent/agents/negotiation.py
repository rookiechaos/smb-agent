from __future__ import annotations

from collections.abc import Iterable

from .._jsonx import extract_json
from ..config import Config
from ..memory_compaction import compact_negotiation_messages, transcript_summary_from_lines
from ..observability import LLMOutputFilterLogger, MemoryCompactionLogger
from ..pipeline_llm import complete_pipeline_messages
from ..safety import review_llm_output_text
from ..types import TIER_CONFIGS, Requirements, Tier
from ..voice import ASRBackend, TTSBackend
from ..workspace import Workspace


class NegotiationAgent:
    """Voice-or-text conversation in Japanese that produces `requirements.json`.

    Voice backends are interface-only right now. If `asr` / `tts` are None, the
    agent reads from stdin and prints to stdout instead — this keeps the rest
    of the pipeline testable end-to-end without speech.
    """

    MAX_TURNS = 30  # safety cap so a runaway conversation can't loop forever.
    SAFE_FALLBACK_REPLY = (
        "すみません。今の返答はそのまま使わず、安全のため確認をやり直します。"
        " 秘密情報は送らず、改善したい業務内容だけを教えてください。"
    )

    def __init__(
        self,
        config: Config,
        asr: ASRBackend | None = None,
        tts: TTSBackend | None = None,
    ):
        self.config = config
        self.asr = asr
        self.tts = tts
        self.client = None
        self._prompt_template = (config.prompts_dir / "negotiation_ja.md").read_text(encoding="utf-8")

    # ---- public ----

    def run(self, workspace: Workspace, tier: Tier) -> Requirements:
        system_prompt = self._build_system_prompt(tier)

        messages: list[dict] = []
        transcript_lines: list[str] = []

        opening = "こんにちは。これからお客様のご要望をお伺いします。まず、どのような業務を改善したいかお聞かせください。"
        self._speak(opening)
        transcript_lines.append(f"AGENT: {opening}")

        for _ in range(self.MAX_TURNS):
            user_text = self._listen()
            if not user_text.strip():
                continue
            transcript_lines.append(f"USER: {user_text}")
            messages.append({"role": "user", "content": user_text})

            response_text = self._ask_claude(workspace, messages, system_prompt)
            messages.append({"role": "assistant", "content": response_text})

            done, requirements_payload = self._try_extract_done(response_text)
            if done:
                transcript_lines.append(f"AGENT (final): {response_text}")
                workspace.transcript_path.write_text("\n\n".join(transcript_lines), encoding="utf-8")
                workspace.negotiation_summary_path.write_text(
                    transcript_summary_from_lines(transcript_lines),
                    encoding="utf-8",
                )
                requirements = Requirements(
                    customer_id=workspace.customer_id,
                    tier=tier,
                    **requirements_payload,
                )
                workspace.save_requirements(requirements)
                self._speak("ありがとうございました。要件を確認しました。")
                return requirements

            verdict = review_llm_output_text(response_text, stage="negotiation")
            if not verdict.passed:
                LLMOutputFilterLogger(workspace).record(
                    stage="negotiation",
                    blocked=True,
                    categories=verdict.categories,
                    issue_count=len(verdict.issues),
                    severities=[issue.severity for issue in verdict.issues],
                    local_llm_backend=self.config.local_llm_backend,
                    text_chars=len(response_text),
                    notes="negotiation reply replaced by safe fallback",
                )
                response_text = self.SAFE_FALLBACK_REPLY
            self._speak(response_text)
            transcript_lines.append(f"AGENT: {response_text}")

        raise RuntimeError(
            f"Negotiation did not converge after {self.MAX_TURNS} turns. "
            f"Inspect transcript at {workspace.transcript_path}"
        )

    # ---- I/O ----

    def _listen(self) -> str:
        if self.asr is not None:
            return self.asr.listen_once(language="ja")
        try:
            return input("YOU> ").strip()
        except EOFError:
            return ""

    def _speak(self, text: str) -> None:
        if self.tts is not None:
            self.tts.speak(text, language="ja")
        else:
            print(f"AGENT> {text}")

    # ---- LLM ----

    def _build_system_prompt(self, tier: Tier) -> str:
        cfg = TIER_CONFIGS[tier]
        return (
            self._prompt_template.replace("{tier}", tier.value)
            .replace("{max_skills}", str(cfg.max_skills))
            .replace("{max_pages}", str(cfg.max_pages))
            .replace("{max_integrations}", str(cfg.max_integrations))
        )

    def _ask_claude(self, workspace: Workspace, messages: Iterable[dict], system_prompt: str) -> str:
        raw_messages = list(messages)
        compacted = compact_negotiation_messages(raw_messages)
        effective_system_prompt = system_prompt
        if compacted.summary:
            effective_system_prompt = (
                f"{system_prompt}\n\n"
                "# Prior conversation summary\n"
                f"{compacted.summary}\n\n"
                "Use the summary as compressed context for earlier turns. Prefer the "
                "most recent explicit user statements if there is any tension."
            )
        MemoryCompactionLogger(workspace).record(
            stage="negotiation",
            mode="rolling_summary",
            input_units=len(raw_messages),
            output_units=len(compacted.recent_messages),
            summary_chars=len(compacted.summary),
            snippet_count=1 if compacted.summary else 0,
            sources=["transcript_window"] if compacted.summary else [],
            query_terms_count=0,
            notes="older negotiation turns summarized into rolling context"
            if compacted.summary
            else "no rolling summary needed",
        )
        outbound_messages = compacted.recent_messages
        completion = complete_pipeline_messages(
            self.config,
            workspace,
            stage="negotiation",
            model=self.config.plan_model,
            max_tokens=2000,
            system=effective_system_prompt,
            messages=outbound_messages,
        )
        return completion.text

    @staticmethod
    def _try_extract_done(text: str) -> tuple[bool, dict]:
        """If the agent emitted the terminal JSON, parse and return it."""
        try:
            data = extract_json(text)
        except ValueError:
            return False, {}
        if not isinstance(data, dict) or not data.get("done"):
            return False, {}
        req = data.get("requirements")
        if not isinstance(req, dict):
            return False, {}
        return True, req
