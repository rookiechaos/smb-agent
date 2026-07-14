from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import time

from .config import Config
from .workspace import Workspace


@dataclass(frozen=True)
class RetentionRule:
    label: str
    pattern: str
    days: int
    purpose: str


@dataclass(frozen=True)
class RetentionCandidate:
    path: Path
    label: str
    age_days: int
    rule_days: int


def retention_rules(config: Config) -> list[RetentionRule]:
    return [
        RetentionRule(
            label="runtime_chat_log",
            pattern="runtime/chat.jsonl",
            days=config.runtime_log_retention_days,
            purpose="Operational health metrics without message content.",
        ),
        RetentionRule(
            label="failure_memory",
            pattern="failure_memory.jsonl",
            days=config.failure_memory_retention_days,
            purpose="Failure analysis and future routing/tuning improvements.",
        ),
        RetentionRule(
            label="loop_memory",
            pattern="loop_memory.jsonl",
            days=config.failure_memory_retention_days,
            purpose="Adaptive coding-validation budget learning without raw prompts or model reasoning.",
        ),
        RetentionRule(
            label="transcript",
            pattern="transcript.txt",
            days=config.transcript_retention_days,
            purpose="Initial discovery review; higher sensitivity than structured requirements.",
        ),
        RetentionRule(
            label="run_log",
            pattern="runs/**/*.log",
            days=config.data_retention_days,
            purpose="Pipeline debugging logs with secret redaction.",
        ),
        RetentionRule(
            label="transition_log",
            pattern="transitions.jsonl",
            days=config.data_retention_days,
            purpose="Replay/audit trail for generated artifacts.",
        ),
        RetentionRule(
            label="company_context_updates",
            pattern="company_context_updates.jsonl",
            days=config.data_retention_days,
            purpose="Company strategy/context change history.",
        ),
    ]


def retention_candidates(workspace: Workspace, config: Config) -> list[RetentionCandidate]:
    now = time()
    out: list[RetentionCandidate] = []
    for rule in retention_rules(config):
        for path in sorted(workspace.path.glob(rule.pattern)):
            if not path.is_file() or rule.days <= 0:
                continue
            age_days = int((now - path.stat().st_mtime) // 86400)
            if age_days > rule.days:
                out.append(
                    RetentionCandidate(
                        path=path,
                        label=rule.label,
                        age_days=age_days,
                        rule_days=rule.days,
                    )
                )
    return out


def data_policy_notes(config: Config) -> list[str]:
    notes = [
        "Treat requirements, transcripts, company context, runtime logs, and failure memory as customer operational records.",
        "Runtime chat logs intentionally store message length, skill, latency, and error only; not message content.",
        "External use of failure memory for tuning/training requires customer-contract review.",
    ]
    if config.allow_failure_memory_training_use:
        notes.append(
            "SMBAGENT_ALLOW_FAILURE_MEMORY_TRAINING_USE=true: confirm this is allowed by customer terms before exporting records."
        )
    return notes
