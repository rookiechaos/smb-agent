from __future__ import annotations

from dataclasses import dataclass

BENCHMARK_POLICY_VERSION = "2026-05-29"


@dataclass(frozen=True)
class CodingBenchmark:
    name: str
    role: str
    status: str
    url: str
    notes: str


PRIMARY_CODING_BENCHMARKS: tuple[CodingBenchmark, ...] = (
    CodingBenchmark(
        name="SWE-bench Pro",
        role="primary_agentic_software_engineering",
        status="primary",
        url="https://scale.com/blog/swe-bench-pro",
        notes=(
            "Primary 2026 benchmark for long-horizon repository-level coding agents; "
            "preferred over SWE-bench Verified for frontier coding-agent selection."
        ),
    ),
    CodingBenchmark(
        name="LiveCodeBench",
        role="fresh_algorithmic_code_generation",
        status="primary",
        url="https://livecodebench.github.io/leaderboard_v5.html",
        notes=(
            "Continuously updated, contamination-aware coding benchmark for code generation "
            "and related code reasoning tasks."
        ),
    ),
    CodingBenchmark(
        name="Terminal-Bench 2.0",
        role="terminal_agent_execution",
        status="primary",
        url="https://terminalbench.lol/",
        notes=(
            "Agent benchmark for realistic terminal work: coding, debugging, files, "
            "system tasks, and command execution."
        ),
    ),
)


SUPPLEMENTAL_CODING_BENCHMARKS: tuple[CodingBenchmark, ...] = (
    CodingBenchmark(
        name="BigCodeBench",
        role="library_and_function_call_code_generation",
        status="supplemental",
        url="https://github.com/bigcode-project/bigcodebench",
        notes=(
            "Software-engineering-oriented code generation tasks with diverse library "
            "and function-call requirements."
        ),
    ),
    CodingBenchmark(
        name="Multi-SWE-bench / SWE-bench Multilingual",
        role="multilingual_repository_issue_resolution",
        status="supplemental",
        url="https://www.swebench.com/multilingual",
        notes=(
            "Useful when selecting coding agents for TypeScript, JavaScript, Go, Rust, "
            "C/C++, Java, and other non-Python-heavy stacks."
        ),
    ),
)


LEGACY_ONLY_BENCHMARKS: tuple[CodingBenchmark, ...] = (
    CodingBenchmark(
        name="SWE-bench Verified",
        role="legacy_agentic_software_engineering",
        status="legacy_only",
        url="https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/",
        notes=(
            "No longer sufficient as a primary frontier coding benchmark because of "
            "saturation, contamination, and test-quality concerns."
        ),
    ),
    CodingBenchmark(
        name="HumanEval / MBPP",
        role="legacy_unit_function_generation",
        status="legacy_smoke_only",
        url="https://github.com/openai/human-eval",
        notes=(
            "Useful only as lightweight legacy smoke tests; too saturated and narrow "
            "for selecting coding agents."
        ),
    ),
)


def coding_benchmark_policy() -> dict[str, object]:
    return {
        "version": BENCHMARK_POLICY_VERSION,
        "primary": [b.__dict__ for b in PRIMARY_CODING_BENCHMARKS],
        "supplemental": [b.__dict__ for b in SUPPLEMENTAL_CODING_BENCHMARKS],
        "legacy_only": [b.__dict__ for b in LEGACY_ONLY_BENCHMARKS],
    }
