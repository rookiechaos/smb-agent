from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from .._jsonx import extract_json
from .._subproc import filesystem_isolation_cmd, register_pid, unregister_pid
from ..annealing import AnnealingState, temperature_prompt_section
from ..company_context import context_quality_notes
from ..config import Config
from ..harness import write_validation_snapshot_manifest
from ..observability import UsageLogger
from ..safety import redact_secrets, run_all_structural_checks
from ..types import Issue, Verdict
from ..workspace import Workspace

_MAX_RAW_BYTES = 16_000  # cap stored stdout/stderr so verdict.json stays manageable
_MAX_DESCRIPTION_CHARS_IN_FEEDBACK = 500
_MAX_API_FILE_CHARS = 12_000
_MAX_API_TOTAL_CHARS = 80_000
# Truncate per-issue descriptions when rendering feedback.md so the next coding
# round's prompt stays manageable. The full text is preserved in verdict.json.


def _truncate(s: str, limit: int) -> str:
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


def _issue_fingerprint(issue: Issue) -> str:
    """Stable hash of (severity, file, first 80 chars of description).
    Used to detect issues that survive across rounds."""
    raw = f"{issue.severity}|{issue.file or ''}|{(issue.description or '')[:80]}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


class ValidationAgent:
    """Independent code auditor backed by the `codex` CLI.

    Each round:
      1. Loads the validation prompt template and substitutes `{round}`.
      2. Runs `codex` inside `workspace/code/` with that prompt.
      3. Codex is instructed to write `../runs/round-{N}/verdict.json`.
      4. We read & parse that file. Missing / malformed file → tooling-failure Verdict.

    Independence is enforced by the prompt: codex is told to read only
    `../requirements.json` and `./`, never the plan / tasks / prior verdicts.
    """

    def __init__(self, config: Config):
        self.config = config
        self.prompt_template = (config.prompts_dir / "validation.md").read_text(encoding="utf-8")

    # ---- public API ----

    def run(
        self,
        workspace: Workspace,
        round_n: int,
        *,
        annealing: AnnealingState | None = None,
    ) -> Verdict:
        round_dir = workspace.round_dir(round_n)
        log_path = round_dir / "validation.log"
        verdict_path = workspace.verdict_path(round_n)
        snapshot_root = self._prepare_validation_snapshot(workspace, round_n)
        prompt = self._build_prompt(
            workspace,
            round_n,
            verdict_path=verdict_path,
            annealing=annealing,
        )

        completed = self._invoke_codex(prompt, workspace, log_path, snapshot_root=snapshot_root)
        verdict = self._read_verdict(verdict_path, round_n, completed)
        verdict = self._apply_structural_checks(workspace, verdict)
        verdict = self._enforce_critical_blocks_pass(verdict)

        # Rewrite verdict.json AFTER all merges so the on-disk artifact reflects
        # the final, authoritative verdict.
        verdict_path.write_text(verdict.model_dump_json(indent=2), encoding="utf-8")

        # Build the issue-fingerprint history across rounds so feedback.md can flag
        # issues that the coding agent has failed to fix.
        history = self._issue_history(workspace, current_round=round_n, current=verdict)
        self._write_feedback_md(workspace, verdict, history)
        return verdict

    def _issue_history(
        self,
        workspace: Workspace,
        current_round: int,
        current: Verdict,
    ) -> dict[str, list[int]]:
        """For each fingerprint in the current verdict's issues, return the list
        of round numbers (including the current one) where it appeared.

        Allows the next coding round's prompt to flag issues that survived prior fixes.
        """
        history: dict[str, list[int]] = {_issue_fingerprint(i): [current_round] for i in current.issues}
        for r in range(1, current_round):
            prior = workspace.load_verdict(r)
            if prior is None:
                continue
            for issue in prior.issues:
                fp = _issue_fingerprint(issue)
                if fp in history:
                    history[fp].insert(-1, r)  # keep rounds chronologically sorted
        return history

    @staticmethod
    def _enforce_critical_blocks_pass(verdict: Verdict) -> Verdict:
        """Invariant: passed=True is only valid if NO critical issue exists, codex-
        reported or structural. If codex contradicts itself (passed=true with a
        critical issue listed), the prompt rule wins and we force passed=false.

        Does not apply to tooling-failure verdicts — those already have passed=False.
        """
        if not verdict.passed:
            return verdict
        if any(i.severity == "critical" for i in verdict.issues):
            note = " (passed overridden to false: critical issue(s) listed)"
            return verdict.model_copy(
                update={
                    "passed": False,
                    "summary": (verdict.summary or "").rstrip() + note,
                }
            )
        return verdict

    def _apply_structural_checks(self, workspace: Workspace, verdict: Verdict) -> Verdict:
        """Run hard, code-enforced checks (tier caps, secrets, frontmatter) and
        merge their issues into the verdict. Any critical structural issue forces
        passed=False regardless of what codex said.

        Skips when the verdict is already a tooling failure (codex never ran or
        couldn't produce a parseable verdict) — those need to be surfaced as-is.
        Also skips if requirements.json hasn't been written yet (which can happen
        in test scenarios that invoke validation directly).
        """
        if verdict.tooling_error is not None:
            return verdict
        if not workspace.requirements_path.exists():
            return verdict

        requirements = workspace.load_requirements()
        structural_issues = run_all_structural_checks(workspace.code_dir, requirements.tier)
        context_issues = [
            Issue(
                severity="major",
                file="../company_context.json",
                description=f"Company context incomplete: {note}",
                suggested_fix="Run `smbagent context-update` or refresh negotiation context.",
            )
            for note in context_quality_notes(workspace.load_company_context())
        ]
        structural_issues = [*structural_issues, *context_issues]
        if not structural_issues:
            return verdict

        merged_issues = list(verdict.issues) + structural_issues
        has_critical_structural = any(i.severity == "critical" for i in structural_issues)
        new_passed = verdict.passed and not has_critical_structural

        suffix = f" Structural checks found {len(structural_issues)} additional issue(s)."
        return verdict.model_copy(
            update={
                "passed": new_passed,
                "issues": merged_issues,
                "summary": (verdict.summary or "").rstrip() + suffix,
            }
        )

    # ---- internals ----

    def _build_prompt(
        self,
        workspace: Workspace,
        round_n: int,
        *,
        verdict_path: Path,
        annealing: AnnealingState | None = None,
    ) -> str:
        prompt = self.prompt_template.replace("{round}", str(round_n)).replace(
            "{verdict_path}", str(verdict_path.resolve())
        )
        if annealing is not None:
            prompt = f"{temperature_prompt_section(annealing)}\n\n{prompt}"
        return prompt

    def _prepare_validation_snapshot(self, workspace: Workspace, round_n: int) -> Path:
        """Create a sanitized validation bundle for Codex.

        Codex gets the same public plan-derived facts as Claude can use, plus a
        copy of generated code. It does not get Claude logs, coding summaries,
        raw bridge files, feedback history, prior verdicts, or the live
        workspace root.
        """
        snapshot_root = workspace.round_dir(round_n) / "validation_snapshot"
        if snapshot_root.exists():
            shutil.rmtree(snapshot_root)
        snapshot_root.mkdir(parents=True, exist_ok=True)

        for src, name in (
            (workspace.requirements_path, "requirements.json"),
            (workspace.company_context_path, "company_context.json"),
            (workspace.plan_path, "public_plan.md"),
            (workspace.tasks_path, "public_tasks.json"),
        ):
            if src.exists():
                shutil.copy2(src, snapshot_root / name)

        snapshot_code = snapshot_root / "code"
        if workspace.code_dir.exists():
            shutil.copytree(
                workspace.code_dir,
                snapshot_code,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
            )
        else:
            snapshot_code.mkdir()
        write_validation_snapshot_manifest(
            workspace,
            self.config,
            round_n,
            snapshot_root=snapshot_root,
            verdict_path=workspace.verdict_path(round_n),
        )
        return snapshot_root

    def _invoke_codex(
        self,
        prompt: str,
        workspace: Workspace,
        log_path: Path,
        *,
        snapshot_root: Path,
    ) -> subprocess.CompletedProcess[str] | None:
        backend = self.config.validation_backend.lower()
        if backend == "cli":
            return self._invoke_codex_cli(prompt, workspace, log_path, snapshot_root=snapshot_root)
        if backend == "api":
            return self._invoke_codex_api(prompt, workspace, log_path)
        log_path.write_text(
            f"unsupported validation backend: {self.config.validation_backend}\n",
            encoding="utf-8",
        )
        return None

    def _invoke_codex_cli(
        self,
        prompt: str,
        workspace: Workspace,
        log_path: Path,
        *,
        snapshot_root: Path,
    ) -> subprocess.CompletedProcess[str] | None:
        snapshot_code_dir = snapshot_root / "code"
        started = time.monotonic()
        cmd = filesystem_isolation_cmd(
            self.config,
            [*self.config.validation_cmd, prompt],
            workspace_path=snapshot_root,
            cwd=snapshot_code_dir,
            role="validation",
            extra_writable_paths=[log_path.parent],
        )
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(snapshot_code_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError as e:
            UsageLogger(workspace).record(
                provider="openai",
                surface="cli",
                stage="validation",
                model="codex-cli",
                status="error",
                detail="codex CLI not found",
            )
            log_path.write_text(
                redact_secrets(
                    f"codex CLI not found on PATH: {e}\nConfigured command: {self.config.validation_cmd}\n"
                ),
                encoding="utf-8",
            )
            return None
        except OSError as e:
            UsageLogger(workspace).record(
                provider="openai",
                surface="cli",
                stage="validation",
                model="codex-cli",
                status="error",
                detail=f"codex CLI failed to start: {e}",
            )
            log_path.write_text(
                redact_secrets(
                    f"codex CLI failed to start: {e}\nConfigured command: {self.config.validation_cmd}\n"
                ),
                encoding="utf-8",
            )
            return None

        register_pid(proc.pid)
        try:
            stdout, stderr = proc.communicate(timeout=self.config.validation_timeout_s)
        except subprocess.TimeoutExpired:
            proc.kill()
            partial_out, partial_err = proc.communicate()
            UsageLogger(workspace).record(
                provider="openai",
                surface="cli",
                stage="validation",
                model="codex-cli",
                status="timeout",
                detail=f"timeout_s={self.config.validation_timeout_s}",
            )
            log_path.write_text(
                redact_secrets(
                    f"codex timed out after {self.config.validation_timeout_s}s\n"
                    f"--- partial stdout ---\n{partial_out or ''}\n"
                    f"--- partial stderr ---\n{partial_err or ''}\n"
                ),
                encoding="utf-8",
            )
            return None
        except OSError as e:
            UsageLogger(workspace).record(
                provider="openai",
                surface="cli",
                stage="validation",
                model="codex-cli",
                status="error",
                detail=f"codex communication failed: {e}",
            )
            log_path.write_text(
                redact_secrets(
                    f"codex communication failed: {e}\nConfigured command: {self.config.validation_cmd}\n"
                ),
                encoding="utf-8",
            )
            return None
        finally:
            unregister_pid(proc.pid)

        log_parts = [
            f"returncode: {proc.returncode}",
            "--- stdout ---",
            stdout or "",
            "--- stderr ---",
            stderr or "",
        ]
        log_path.write_text(redact_secrets("\n".join(log_parts)), encoding="utf-8")
        elapsed_ms = int((time.monotonic() - started) * 1000)
        UsageLogger(workspace).record(
            provider="openai",
            surface="cli",
            stage="validation",
            model="codex-cli",
            status="ok" if proc.returncode == 0 else "error",
            detail=f"returncode={proc.returncode}; elapsed_ms={elapsed_ms}",
        )
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=proc.returncode,
            stdout=stdout,
            stderr=stderr,
        )

    def _invoke_codex_api(
        self,
        prompt: str,
        workspace: Workspace,
        log_path: Path,
    ) -> subprocess.CompletedProcess[str] | None:
        if self.config.local_only_mode:
            log_path.write_text(
                "SMBAGENT_LOCAL_ONLY_MODE=true blocks OpenAI API validation until "
                "a real local validation backend is integrated.\n",
                encoding="utf-8",
            )
            return None
        try:
            from openai import OpenAI
        except ModuleNotFoundError:
            log_path.write_text(
                "OpenAI SDK not installed; install project dependencies or use "
                "SMBAGENT_VALIDATION_BACKEND=cli\n",
                encoding="utf-8",
            )
            return None

        api_prompt = (
            f"{prompt}\n\n"
            "## API validation context\n\n"
            "You are running through the OpenAI API, not the Codex CLI, so the "
            "customer code tree is provided below as read-only text. Judge only "
            "against this snapshot and requirements.json.\n\n"
            f"# requirements.json\n\n```json\n"
            f"{workspace.load_requirements().model_dump_json(indent=2) if workspace.requirements_path.exists() else '{}'}"
            "\n```\n\n"
            f"# company_context.json\n\n```json\n"
            f"{workspace.load_company_context().model_dump_json(indent=2)}"
            "\n```\n\n"
            f"# code/ snapshot\n\n{self._build_code_snapshot(workspace.code_dir)}\n"
        )
        try:
            client = OpenAI(api_key=self.config.openai_api_key) if self.config.openai_api_key else OpenAI()
            response = client.responses.create(
                model=self.config.validation_model,
                instructions=(
                    "Return only the validation verdict JSON. Do not include prose or markdown fences."
                ),
                input=api_prompt,
                max_output_tokens=4000,
            )
            UsageLogger(workspace).record(
                provider="openai",
                surface="api",
                stage="validation",
                model=self.config.validation_model,
                response=response,
            )
            stdout = self._response_text(response)
        except Exception as e:
            log_path.write_text(
                redact_secrets(
                    f"OpenAI validation API call failed: {e}\n"
                    f"Configured model: {self.config.validation_model}\n"
                ),
                encoding="utf-8",
            )
            return None

        log_path.write_text(
            redact_secrets(
                "\n".join(
                    [
                        "backend: api",
                        f"model: {self.config.validation_model}",
                        "--- output ---",
                        stdout,
                    ]
                )
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            args=["openai.responses.create", self.config.validation_model],
            returncode=0,
            stdout=stdout,
            stderr="",
        )

    @staticmethod
    def _response_text(response: Any) -> str:
        text = getattr(response, "output_text", None)
        if isinstance(text, str):
            return text
        output = getattr(response, "output", None) or []
        parts: list[str] = []
        for item in output:
            for content in getattr(item, "content", []) or []:
                value = getattr(content, "text", None)
                if isinstance(value, str):
                    parts.append(value)
        return "".join(parts)

    @staticmethod
    def _build_code_snapshot(code_dir: Path) -> str:
        parts: list[str] = []
        used = 0
        for path in sorted(p for p in code_dir.rglob("*") if p.is_file()):
            rel = path.relative_to(code_dir).as_posix()
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if len(text) > _MAX_API_FILE_CHARS:
                text = text[: _MAX_API_FILE_CHARS - 1].rstrip() + "…"
            block = f"### FILE: {rel}\n\n```\n{text}\n```\n"
            if used + len(block) > _MAX_API_TOTAL_CHARS:
                parts.append("(code snapshot truncated)")
                break
            parts.append(block)
            used += len(block)
        return "\n".join(parts) if parts else "(code/ is empty)"

    def _read_verdict(
        self,
        verdict_path: Path,
        round_n: int,
        completed: subprocess.CompletedProcess[str] | None,
    ) -> Verdict:
        """Resolve codex's output into a Verdict.

        Resolution order:
          1. `verdict.json` exists and is well-formed JSON:
                 a. matches Verdict schema → use it.
                 b. doesn't match schema → tooling failure with a schema-specific message
                    (don't try stdout fallback — codex's intent was clear but wrong).
          2. `verdict.json` is missing OR malformed JSON syntax:
                 → fall back to extracting JSON from codex stdout. If that parses
                   into a verdict shape, materialize verdict.json from it and proceed.
          3. Nothing parses → tooling failure.
        """
        raw = ""
        stdout = ""
        if completed is not None:
            stdout = completed.stdout or ""
            raw = (stdout + (completed.stderr or ""))[:_MAX_RAW_BYTES]

        if completed is None:
            return self._tooling_failure(
                round_n,
                "codex failed to run (not found or timed out — see validation.log)",
                raw,
            )

        # 1. Primary path: verdict.json
        if verdict_path.exists():
            try:
                data = json.loads(verdict_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                # File is corrupt — fall through to stdout fallback below.
                data = None

            if data is not None:
                verdict = self._build_verdict_from_dict(data, round_n, raw)
                if verdict is not None:
                    return verdict
                return self._tooling_failure(
                    round_n,
                    "verdict.json did not match schema (file present but fields invalid)",
                    raw,
                )

        # 2. Fallback: stdout
        verdict_from_stdout = self._try_parse_stdout_verdict(stdout, round_n, raw)
        if verdict_from_stdout is not None:
            verdict_path.write_text(verdict_from_stdout.model_dump_json(indent=2), encoding="utf-8")
            return verdict_from_stdout

        # 3. Nothing worked
        return self._tooling_failure(
            round_n,
            "codex did not produce verdict.json and stdout had no parseable verdict",
            raw,
        )

    def _try_parse_stdout_verdict(self, stdout: str, round_n: int, raw: str) -> Verdict | None:
        """Salvage path: if codex put the verdict JSON in stdout, extract & use it."""
        if not stdout.strip():
            return None
        try:
            data = extract_json(stdout)
        except ValueError:
            return None
        if not isinstance(data, dict) or "passed" not in data:
            return None
        return self._build_verdict_from_dict(data, round_n, raw)

    @staticmethod
    def _build_verdict_from_dict(data: dict, round_n: int, raw: str) -> Verdict | None:
        """Construct a Verdict from a parsed dict. Returns None on schema mismatch."""
        try:
            issues = [Issue.model_validate(i) for i in data.get("issues", [])]
            return Verdict(
                passed=bool(data.get("passed", False)),
                round=round_n,
                summary=str(data.get("summary", "")),
                issues=issues,
                raw_codex_output=raw,
            )
        except Exception:
            return None

    def _tooling_failure(self, round_n: int, msg: str, raw: str) -> Verdict:
        return Verdict(
            passed=False,
            round=round_n,
            summary=f"Validation tooling failure: {msg}",
            issues=[
                Issue(
                    severity="critical",
                    description=f"Validator could not produce a verdict: {msg}",
                    suggested_fix="Check codex CLI installation and validation.log for this round.",
                )
            ],
            raw_codex_output=raw,
            tooling_error=msg,
        )

    def _write_feedback_md(
        self,
        workspace: Workspace,
        verdict: Verdict,
        history: dict[str, list[int]] | None = None,
    ) -> None:
        """Human-readable feedback file consumed by the next coding round.

        Format (when failed):
          - Summary
          - Issues grouped by file, severity-first within each file
          - Persistent-issues section listing fingerprints seen across multiple rounds
          - Explicit action protocol for the next coding round
        """
        history = history or {}

        if verdict.passed:
            body = f"# Round {verdict.round} — PASSED\n\n{verdict.summary}\n"
            workspace.feedback_path(verdict.round).write_text(body, encoding="utf-8")
            return

        sev_order = {"critical": 0, "major": 1, "minor": 2}

        # Group by file (None grouped under "General").
        by_file: dict[str, list[Issue]] = {}
        for issue in verdict.issues:
            key = issue.file or "(no file — applies to project root)"
            by_file.setdefault(key, []).append(issue)
        for issues in by_file.values():
            issues.sort(key=lambda x: sev_order.get(x.severity, 99))

        # Persistent issues: fingerprints that appeared in ≥2 rounds.
        persistent = [(fp, rounds) for fp, rounds in history.items() if len(rounds) >= 2]
        # Map fp → issue for rendering
        fp_to_issue = {_issue_fingerprint(i): i for i in verdict.issues}

        lines: list[str] = [
            f"# Round {verdict.round} — FAILED",
            "",
            "## Summary",
            verdict.summary or "(no summary)",
            "",
        ]

        if persistent:
            lines.append("## ⚠️  Persistent issues (survived prior round(s))")
            lines.append("")
            lines.append(
                "These were flagged in earlier rounds but were not fixed. "
                "If you keep applying the same approach, you'll keep failing — "
                "investigate why the previous attempt didn't work."
            )
            lines.append("")
            for fp, rounds in persistent:
                issue = fp_to_issue.get(fp)
                if issue is None:
                    continue
                where = ""
                if issue.file:
                    where = f"`{issue.file}`"
                    if issue.line is not None:
                        where += f":{issue.line}"
                else:
                    where = "(project-level)"
                rounds_str = ", ".join(str(r) for r in rounds)
                lines.append(
                    f"- **[{issue.severity.upper()}]** {where} — "
                    f"{_truncate(issue.description, _MAX_DESCRIPTION_CHARS_IN_FEEDBACK)}  "
                    f"_(seen in rounds: {rounds_str})_"
                )
            lines.append("")

        # Issues grouped by file
        lines.append("## Issues to fix")
        lines.append("")
        lines.append(
            "**Protocol:** open each file once, apply ALL listed fixes for that file, "
            "save, then move to the next file. Do NOT add new features until every "
            "critical and major issue in this section is gone."
        )
        lines.append("")

        # Sort file groups: files with critical issues first, then alphabetical.
        def _file_sort_key(item: tuple[str, list[Issue]]) -> tuple[int, str]:
            fname, issues = item
            top_sev = min(sev_order.get(i.severity, 99) for i in issues)
            return (top_sev, fname)

        for fname, issues in sorted(by_file.items(), key=_file_sort_key):
            lines.append(f"### `{fname}`")
            for i, issue in enumerate(issues, start=1):
                loc = f":{issue.line}" if issue.line is not None else ""
                desc = _truncate(issue.description, _MAX_DESCRIPTION_CHARS_IN_FEEDBACK)
                lines.append(f"{i}. **[{issue.severity.upper()}]**{loc} {desc}")
                if issue.suggested_fix:
                    fix = _truncate(issue.suggested_fix, _MAX_DESCRIPTION_CHARS_IN_FEEDBACK)
                    lines.append(f"   - Suggested fix: {fix}")
            lines.append("")

        body = "\n".join(lines)
        workspace.feedback_path(verdict.round).write_text(body, encoding="utf-8")
