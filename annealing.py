"""Dynamic temperature annealing for the coding ↔ validation iteration loop.

Agent A (coding) drafts; Agent B (validation) reviews. Early rounds use higher
temperature to encourage exploration; when the loop stalls, temperature steps
down toward deterministic, compliance-oriented output on the final round.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .loop_stall import default_issue_fingerprint, default_verdict_summary_hash, detect_stall
from .types import Issue
from .workspace import Workspace


class AnnealingPhase(str, Enum):
    CREATIVE = "creative"
    CONVERGENCE = "convergence"
    FINAL = "final"


@dataclass(frozen=True)
class AnnealingState:
    phase: AnnealingPhase
    temperature: float
    round_n: int
    deadlock_detected: bool
    is_final_resolution: bool


@dataclass(frozen=True)
class AnnealingTemps:
    creative: float = 0.7
    convergence: float = 0.3
    final: float = 0.0


def issue_fingerprint(issue: Issue) -> str:
    """Stable id for an issue — aligned with ValidationAgent's fingerprint."""
    return default_issue_fingerprint(issue)


def detect_deadlock(
    workspace: Workspace,
    *,
    through_round: int,
    stale_round_threshold: int = 2,
    convergence=None,
) -> bool:
    """True when iteration looks stuck (conflict / loop) after failed rounds."""
    return detect_stall(
        through_round=through_round,
        stale_round_threshold=stale_round_threshold,
        load_verdict=workspace.load_verdict,
        issue_fingerprint=default_issue_fingerprint,
        verdict_summary_hash=default_verdict_summary_hash,
        convergence=convergence,
    )


def compute_annealing(
    round_n: int,
    *,
    max_rounds: int,
    consecutive_failures: int,
    deadlock: bool,
    temps: AnnealingTemps | None = None,
    stale_round_threshold: int = 2,
) -> AnnealingState:
    """Pick phase/temperature for a coding or validation invocation.

    Schedule:
      - Round 1 (and early rounds without deadlock): CREATIVE (default 0.7).
      - After ``stale_round_threshold`` failed rounds with deadlock: CONVERGENCE (0.3).
      - Last allowed round (``round_n == max_rounds``): FINAL (0.0) — forced resolution.
    """
    t = temps or AnnealingTemps()
    is_final = round_n >= max_rounds

    if is_final:
        return AnnealingState(
            phase=AnnealingPhase.FINAL,
            temperature=t.final,
            round_n=round_n,
            deadlock_detected=deadlock,
            is_final_resolution=True,
        )

    if consecutive_failures >= stale_round_threshold and deadlock:
        return AnnealingState(
            phase=AnnealingPhase.CONVERGENCE,
            temperature=t.convergence,
            round_n=round_n,
            deadlock_detected=True,
            is_final_resolution=False,
        )

    return AnnealingState(
        phase=AnnealingPhase.CREATIVE,
        temperature=t.creative,
        round_n=round_n,
        deadlock_detected=deadlock,
        is_final_resolution=False,
    )


def temperature_prompt_section(state: AnnealingState) -> str:
    """Injected into subprocess agent prompts (claude / codex) when they cannot take API temperature."""
    phase_notes = {
        AnnealingPhase.CREATIVE: (
            "Explore fixes thoroughly; multiple reasonable approaches are acceptable "
            "if they stay within the spec."
        ),
        AnnealingPhase.CONVERGENCE: (
            "Prior rounds failed to converge. Prefer the smallest, most deterministic "
            "fix that clears every listed issue — avoid speculative refactors."
        ),
        AnnealingPhase.FINAL: (
            "Final resolution round. Produce exactly one compliant outcome: no "
            "alternatives, no open questions, no creative detours."
        ),
    }
    note = phase_notes[state.phase]
    return (
        f"## Sampling policy (orchestrator-enforced)\n\n"
        f"- Phase: `{state.phase.value}`\n"
        f"- Target temperature: **{state.temperature}** "
        f"(treat as authoritative; lower = more deterministic)\n"
        f"- Deadlock detected: **{state.deadlock_detected}**\n"
        f"- Final resolution: **{state.is_final_resolution}**\n\n"
        f"{note}\n"
    )
