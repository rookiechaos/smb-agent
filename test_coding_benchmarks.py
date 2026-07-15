from __future__ import annotations

from smbagent.coding_benchmarks import (
    BENCHMARK_POLICY_VERSION,
    LEGACY_ONLY_BENCHMARKS,
    PRIMARY_CODING_BENCHMARKS,
    coding_benchmark_policy,
)


def test_coding_benchmark_policy_uses_current_primary_benchmarks():
    names = {b.name for b in PRIMARY_CODING_BENCHMARKS}
    assert "SWE-bench Pro" in names
    assert "LiveCodeBench" in names
    assert "Terminal-Bench 2.0" in names
    assert BENCHMARK_POLICY_VERSION >= "2026-05-29"


def test_legacy_benchmarks_are_not_primary():
    primary_names = {b.name for b in PRIMARY_CODING_BENCHMARKS}
    legacy_names = {b.name for b in LEGACY_ONLY_BENCHMARKS}
    assert "SWE-bench Verified" in legacy_names
    assert "SWE-bench Verified" not in primary_names
    assert "HumanEval / MBPP" in legacy_names


def test_policy_serializes_for_cli_and_docs():
    policy = coding_benchmark_policy()
    assert policy["version"] == BENCHMARK_POLICY_VERSION
    assert len(policy["primary"]) >= 3
    assert all("url" in item for item in policy["primary"])  # type: ignore[union-attr]
