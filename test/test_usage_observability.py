from __future__ import annotations

from types import SimpleNamespace

from smbagent.observability import (
    UsageLogger,
    extract_usage,
    summarize_monthly_api_cost,
    summarize_usage,
)
from smbagent.portal import render_operator_dashboard, render_portal


def test_extract_usage_supports_anthropic_shape():
    response = SimpleNamespace(
        usage=SimpleNamespace(input_tokens=123, output_tokens=45, cache_read_input_tokens=7)
    )
    assert extract_usage(response) == {
        "input_tokens": 123,
        "output_tokens": 45,
        "cached_input_tokens": 7,
    }


def test_extract_usage_supports_openai_shape():
    response = SimpleNamespace(usage=SimpleNamespace(input_tokens=100, output_tokens=20, total_tokens=120))
    assert extract_usage(response) == {
        "input_tokens": 100,
        "output_tokens": 20,
        "total_tokens": 120,
    }


def test_usage_logger_summarizes_api_and_cli_events(workspace):
    UsageLogger(workspace).record(
        provider="anthropic",
        surface="api",
        stage="plan",
        model="claude-opus",
        input_tokens=100,
        output_tokens=50,
    )
    UsageLogger(workspace).record(
        provider="openai",
        surface="cli",
        stage="validation",
        model="codex-cli",
    )
    summary = summarize_usage(workspace)
    assert summary.api_events == 1
    assert summary.cli_events == 1
    assert summary.total_tokens == 150
    assert summary.unknown_token_events == 1


def test_portal_and_dashboard_render_usage(workspace, config):
    UsageLogger(workspace).record(
        provider="anthropic",
        surface="api",
        stage="qualify",
        model="claude-opus",
        input_tokens=10,
        output_tokens=5,
    )
    portal = render_portal(workspace)
    dashboard = render_operator_dashboard(config.workspaces_dir)
    assert "Model usage" in portal
    assert "15" in portal
    assert "15 tok" in dashboard


def test_monthly_api_cost_summary_estimates_budget_percent(workspace, config):
    UsageLogger(workspace).record(
        provider="anthropic",
        surface="api",
        stage="plan",
        model="claude-opus-4-7",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    summary = summarize_monthly_api_cost(workspace, config)
    assert summary.estimated_monthly_api_cost_jpy == 4500
    assert summary.monthly_api_budget_jpy == 30000
    assert summary.monthly_api_budget_percent == 15
    assert summary.known_cost_api_events == 1
    assert summary.unknown_cost_api_events == 0
