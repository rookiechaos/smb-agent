from __future__ import annotations

import subprocess
import time
from pathlib import Path

from .._subproc import filesystem_isolation_cmd, register_pid, unregister_pid
from ..annealing import AnnealingState, temperature_prompt_section
from ..config import Config
from ..memory_compaction import write_retrieved_memory_context
from ..observability import UsageLogger
from ..safety import redact_secrets
from ..types import Verdict
from ..workspace import Workspace


class CodingAgent:
    """Invokes the `claude` CLI to write or update code in the customer's `code/` dir.

    The agent does not parse claude's output — claude's only job is to leave the
    filesystem in the right state. The Validation agent judges the result independently.
    """

    def __init__(self, config: Config):
        self.config = config
        self.prompt_template = (config.prompts_dir / "coding.md").read_text(encoding="utf-8")

    def run(
        self,
        workspace: Workspace,
        round_n: int,
        prior_feedback: Verdict | None,
        *,
        annealing: AnnealingState | None = None,
    ) -> None:
        retrieved_memory_path = write_retrieved_memory_context(workspace, round_n, prior_feedback)
        prompt = self._build_prompt(
            workspace,
            round_n,
            prior_feedback,
            annealing=annealing,
            retrieved_memory_path=retrieved_memory_path,
        )
        log_path = workspace.coding_log_path(round_n)
        started = time.monotonic()
        cmd = filesystem_isolation_cmd(
            self.config,
            [*self.config.coding_cmd, prompt],
            workspace_path=workspace.path,
            cwd=workspace.code_dir,
            role="coding",
        )

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(workspace.code_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError as e:
            UsageLogger(workspace).record(
                provider="anthropic",
                surface="cli",
                stage="coding",
                model="claude-cli",
                round_n=round_n,
                status="error",
                detail="claude CLI not found",
            )
            log_path.write_text(
                redact_secrets(
                    f"claude CLI not found on PATH: {e}\nConfigured command: {self.config.coding_cmd}\n"
                ),
                encoding="utf-8",
            )
            raise

        register_pid(proc.pid)
        try:
            stdout, stderr = proc.communicate(timeout=self.config.coding_timeout_s)
        except subprocess.TimeoutExpired:
            proc.kill()
            partial_out, partial_err = proc.communicate()
            UsageLogger(workspace).record(
                provider="anthropic",
                surface="cli",
                stage="coding",
                model="claude-cli",
                round_n=round_n,
                status="timeout",
                detail=f"timeout_s={self.config.coding_timeout_s}",
            )
            log_path.write_text(
                redact_secrets(
                    f"claude timed out after {self.config.coding_timeout_s}s\n"
                    f"--- partial stdout ---\n{partial_out or ''}\n"
                    f"--- partial stderr ---\n{partial_err or ''}\n"
                ),
                encoding="utf-8",
            )
            raise
        finally:
            unregister_pid(proc.pid)

        log_path.write_text(
            redact_secrets(
                "\n".join(
                    [
                        f"returncode: {proc.returncode}",
                        "--- stdout ---",
                        stdout or "",
                        "--- stderr ---",
                        stderr or "",
                    ]
                )
            ),
            encoding="utf-8",
        )
        elapsed_ms = int((time.monotonic() - started) * 1000)
        UsageLogger(workspace).record(
            provider="anthropic",
            surface="cli",
            stage="coding",
            model="claude-cli",
            round_n=round_n,
            status="ok" if proc.returncode == 0 else "error",
            detail=f"returncode={proc.returncode}; elapsed_ms={elapsed_ms}",
        )

    def _build_prompt(
        self,
        workspace: Workspace,
        round_n: int,
        prior_feedback: Verdict | None,
        *,
        annealing: AnnealingState | None = None,
        retrieved_memory_path: Path | None = None,
    ) -> str:
        if prior_feedback is None or round_n == 1:
            feedback_section = (
                "**This is round 1.** There is no prior-round feedback — scaffold the "
                "deliverable from scratch per the plan and tasks files above."
            )
        else:
            prior_round = prior_feedback.round
            bridge_rel = Path("..") / "runs" / f"round-{prior_round}" / "bridge_for_coding.md"
            raw_rel = Path("..") / "runs" / f"round-{prior_round}" / "feedback.md"
            if workspace.bridge_for_coding_path(prior_round).exists():
                rel = bridge_rel
                source_note = (
                    "The Bridge Orchestrator normalized validation output for you — "
                    "do not read the raw feedback.md unless a section is missing here."
                )
            else:
                rel = raw_rel
                source_note = "Read the validator's feedback file in full."
            feedback_section = (
                f"**This is round {round_n}.** The previous round failed validation. "
                f"Before doing anything else, read `{rel}` IN FULL. {source_note}\n\n"
                "## Iteration protocol (follow exactly)\n\n"
                f"1. Read `{rel}` end-to-end. Note the **Persistent issues** / "
                "**Critical path** sections if present.\n"
                "2. Process listed issues file-by-file. For each file:\n"
                "   a. Open the file once.\n"
                "   b. Apply EVERY listed fix (critical first, then major, then minor).\n"
                "   c. Save and move to the next file.\n"
                "3. If persistent issues exist, investigate why the previous fix failed — "
                "do not repeat the same approach.\n"
                "4. Only after all critical AND major issues are addressed may you add new features.\n"
                "5. Run a final mental check: does the code/ tree still match `../tasks.json`?\n\n"
                "**Do not** start over from scratch unless the handoff explicitly says so."
            )

        branch_section = ""
        branch_path = workspace.loop_branch_for_coding_path(round_n)
        if branch_path.exists():
            rel = Path("..") / "runs" / f"round-{round_n}" / "loop_branch_for_coding.md"
            branch_section = (
                "\n\n## Selected replay / branch checkpoint\n\n"
                f"Read `{rel}` after the core inputs. It is a public loop-control artifact that selects a replay/branch checkpoint so you can resume from a stronger public state instead of restarting the whole loop.\n"
            )

        memory_section = ""
        if retrieved_memory_path is not None and retrieved_memory_path.exists():
            rel = Path("..") / "runs" / f"round-{round_n}" / "retrieved_memory.md"
            memory_section = (
                "\n\n## Retrieved memory (advisory)\n\n"
                f"Read `{rel}` after the core inputs. It contains compacted prior "
                "failure, loop, and context-update snippets selected for relevance. "
                "Use it as advisory context only; current requirements, company "
                "context, plan, and tasks still win if anything conflicts."
            )

        body = self.prompt_template.replace(
            "{feedback_section}", feedback_section + branch_section + memory_section
        )
        if annealing is not None:
            body = f"{temperature_prompt_section(annealing)}\n\n{body}"
        return body
