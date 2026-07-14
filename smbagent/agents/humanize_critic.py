"""Humanize Critic (B) — rubric scan of customer-facing Japanese copy."""

from __future__ import annotations

import hashlib

from .._jsonx import extract_json
from ..annealing import AnnealingState, temperature_prompt_section
from ..config import Config
from ..humanize_targets import build_corpus_snapshot
from ..observability import UsageLogger
from ..types import HumanizeIssue, HumanizeVerdict
from ..workspace import Workspace
from . import build_anthropic_client


def _issue_fingerprint(issue: HumanizeIssue) -> str:
    raw = f"{issue.severity}|{issue.file}|{issue.pattern}|{(issue.description or '')[:80]}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


class HumanizeCriticAgent:
    def __init__(self, config: Config):
        self.config = config
        self.client = None
        self.system_prompt = (config.prompts_dir / "humanize_critic_ja.md").read_text(encoding="utf-8")

    def run(
        self,
        workspace: Workspace,
        round_n: int,
        *,
        annealing: AnnealingState | None = None,
    ) -> HumanizeVerdict:
        requirements = workspace.load_requirements()
        corpus = build_corpus_snapshot(workspace.code_dir)
        user_msg = (
            f"# Round\n{round_n}\n\n"
            f"# requirements.json（事実の根拠）\n\n"
            f"```json\n{requirements.model_dump_json(indent=2)}\n```\n\n"
            f"# 審査対象コピー\n\n{corpus}\n"
        )
        if annealing is not None:
            user_msg = f"{temperature_prompt_section(annealing)}\n\n{user_msg}"

        client = self.client or build_anthropic_client(self.config)
        response = client.messages.create(
            model=self.config.plan_model,
            max_tokens=4000,
            temperature=annealing.temperature if annealing else 0.2,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )
        UsageLogger(workspace).record(
            provider="anthropic",
            surface="api",
            stage="humanize_critic",
            model=self.config.plan_model,
            round_n=round_n,
            response=response,
        )
        text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
        try:
            payload = extract_json(text)
            if (
                isinstance(payload, dict)
                and payload.get("format") == "polyarch/humanize"
                and isinstance(payload.get("payload"), dict)
            ):
                payload = payload["payload"]
            verdict = HumanizeVerdict.model_validate({**payload, "round": round_n})
        except (ValueError, Exception) as e:
            verdict = HumanizeVerdict(
                passed=False,
                round=round_n,
                summary=f"Humanize critic tooling failure: {e}",
                rubric_score=0.0,
                tooling_error=str(e)[:300],
            )

        verdict = self._enforce_invariants(verdict)
        workspace.humanize_verdict_path(round_n).write_text(
            verdict.model_dump_json(indent=2), encoding="utf-8"
        )
        history = self._issue_history(workspace, round_n, verdict)
        self._write_feedback_md(workspace, verdict, history)
        return verdict

    @staticmethod
    def _enforce_invariants(verdict: HumanizeVerdict) -> HumanizeVerdict:
        if verdict.tooling_error is not None:
            return verdict.model_copy(update={"passed": False})

        has_critical = any(i.severity == "critical" for i in verdict.issues)
        major_count = sum(1 for i in verdict.issues if i.severity == "major")

        passed = verdict.passed
        if has_critical:
            passed = False
        if verdict.rubric_score < 0.85:
            passed = False
        if major_count > 3:
            passed = False
        if verdict.rubric_score >= 0.85 and not has_critical and major_count <= 3:
            passed = True

        return verdict.model_copy(update={"passed": passed})

    def _issue_history(
        self,
        workspace: Workspace,
        current_round: int,
        current: HumanizeVerdict,
    ) -> dict[str, list[int]]:
        history: dict[str, list[int]] = {_issue_fingerprint(i): [current_round] for i in current.issues}
        for r in range(1, current_round):
            prior = workspace.load_humanize_verdict(r)
            if prior is None:
                continue
            for issue in prior.issues:
                fp = _issue_fingerprint(issue)
                if fp in history:
                    history[fp].insert(-1, r)
        return history

    def _write_feedback_md(
        self,
        workspace: Workspace,
        verdict: HumanizeVerdict,
        history: dict[str, list[int]],
    ) -> None:
        if verdict.passed:
            body = (
                f"# Humanize round {verdict.round} — PASSED\n\n"
                f"rubric_score: {verdict.rubric_score}\n\n{verdict.summary}\n"
            )
            workspace.humanize_feedback_path(verdict.round).write_text(body, encoding="utf-8")
            return

        persistent = [(fp, rs) for fp, rs in history.items() if len(rs) >= 2]
        lines = [
            f"# Humanize round {verdict.round} — FAILED",
            "",
            f"**rubric_score:** {verdict.rubric_score}",
            "",
            "## Summary",
            verdict.summary or "(なし)",
            "",
        ]
        if persistent:
            lines.append("## ⚠️ 繰り返し指摘（前のラウンドから残存）")
            lines.append("")
            fp_map = {_issue_fingerprint(i): i for i in verdict.issues}
            for fp, rounds in persistent:
                issue = fp_map.get(fp)
                if issue is None:
                    continue
                lines.append(
                    f"- **[{issue.pattern}]** `{issue.file}` — {issue.description} "
                    f"_(rounds: {', '.join(str(r) for r in rounds)})_"
                )
            lines.append("")

        lines.append("## Issues to fix")
        lines.append("")
        for issue in verdict.issues:
            lines.append(f"- **[{issue.severity}]** `{issue.file}` (`{issue.pattern}`) — {issue.description}")
            if issue.suggested_fix:
                lines.append(f"  - 修正案: {issue.suggested_fix}")
            if issue.excerpt:
                lines.append(f"  - 抜粋: {issue.excerpt}")
        lines.append("")

        workspace.humanize_feedback_path(verdict.round).write_text("\n".join(lines), encoding="utf-8")
