#!/usr/bin/env python3
"""One-shot splitter for portal/dashboard.py — run from repo root."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "smbagent/portal/dashboard.py"
TYPES = ROOT / "smbagent/portal/dashboard_types.py"
LOADERS = ROOT / "smbagent/portal/dashboard_loaders.py"
SECTIONS = ROOT / "smbagent/portal/dashboard_sections.py"
HTML = ROOT / "smbagent/portal/dashboard_html.py"
FACADE = ROOT / "smbagent/portal/dashboard.py"

lines = SRC.read_text(encoding="utf-8").splitlines(keepends=True)

# 0-indexed slice boundaries (line numbers from grep, minus 1)
types_body = lines[37:209]  # dataclasses through CustomerSummary
loaders_body = lines[210:354] + lines[499:1405]  # collect/load helpers
facade_body = lines[354:419]  # write/render entrypoints
sections_body = lines[419:499] + lines[584:1047] + lines[857:906]  # header/footer + sections
html_body = lines[1405:]  # table + row render helpers

# Fix ordering: sections had _next_stage at 858 which is inside loaders range - re-read structure
# loaders: 211-354, 500-857, 907-1047, 1102-1405
loaders_body = lines[210:354] + lines[499:857] + lines[906:1047] + lines[1101:1405]
sections_body = lines[419:499] + lines[584:857] + lines[907:906] + lines[1047:1101]
# 907:906 is empty - fix sections
sections_body = lines[419:499] + lines[584:857] + lines[857:906] + lines[907:1047] + lines[1047:1101]

types_header = '''"""Operator dashboard datatypes."""

from __future__ import annotations

from dataclasses import dataclass

from ..types import Tier


'''

loaders_header = '''"""Operator dashboard data collection and artifact loaders."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from ..agent_boundaries import build_agent_isolation_status, write_agent_isolation_status
from ..artifact_freshness import artifact_path_strings
from ..commercial_readiness import build_commercial_readiness_report
from ..company_context import context_age_days, is_context_stale
from ..config import load_config
from ..fleet_state import FleetStateStore, publish_fleet_artifact_freshness
from ..loop_engineering import build_loop_engineering_contract
from ..memory_analytics import fleet_totals, summarize_all_workspaces
from ..network_posture import build_network_posture_report
from ..next_stage_priorities import _loop_maturity_sort_key
from ..next_stage_priorities import build_next_stage_priorities_summary, write_next_stage_priorities_summary
from ..occ_reducer_status import build_occ_reducer_status, write_occ_reducer_status
from ..observability import summarize_usage
from ..repo_hygiene import build_pre_release_check_report
from ..workflow_circuit_breaker import read_workflow_circuit_breaker_state
from ..workflow_maintenance import build_maintenance_report
from ..workflow_monitor import build_owner_surface, build_workflow_monitor_view
from ..workspace import InvalidCustomerIdError, Workspace
from smbagent.slm.dataset_review import load_latest_dataset_review, summarize_weekly_review_decision
from smbagent.slm.framework_status import build_slm_framework_status, write_slm_framework_status
from smbagent.slm.governance_state import SLMGovernanceStateStore
from smbagent.slm.specialist_dataset import default_specialist_dataset_paths
from smbagent.slm.training_registry import default_training_registry_paths

from .dashboard_types import (
    CommercialReadinessSummary,
    CustomerSummary,
    FleetAnalyticsRecommendation,
    FleetAnalyticsSummary,
    FleetArtifactFreshnessSummary,
    LatestDatasetReviewSummary,
    LoopMaturityFleetSummary,
    NetworkPostureSummary,
    PreReleaseCheckSummary,
    SLMGovernanceConflictSummary,
    SLMPackView,
    WorkspaceOCCConflictSummary,
)


'''

sections_header = '''"""Operator dashboard HTML section renderers."""

from __future__ import annotations

import html
import json
from pathlib import Path

from ..next_stage_priorities import _loop_maturity_sort_key
from smbagent.slm.dataset_review import summarize_weekly_review_decision

from .dashboard_loaders import (
    _coerce_count_map,
    _inline_counts,
    _list_of_dicts,
    _list_value,
    _load_agent_customer_pack,
    _load_commercial_readiness_summary,
    _load_fleet_analytics,
    _load_fleet_artifact_freshness_summary,
    _load_latest_dataset_review_summary,
    _load_loop_maturity_summary,
    _load_network_posture_summary,
    _load_pre_release_check_summary,
    _load_slm_governance_conflicts,
    _load_slm_pack_view,
    _load_slm_promotion_section,
    _load_workspace_occ_conflicts,
    _pack_payload,
    _read_json_dict,
)
from .dashboard_types import (
    CustomerSummary,
    FleetAnalyticsSummary,
    LatestDatasetReviewSummary,
    SLMPackView,
)


'''

html_header = '''"""Operator dashboard table and row HTML helpers."""

from __future__ import annotations

import html

from .dashboard_types import CustomerSummary


'''

facade_header = '''"""Operator dashboard — multi-customer overview rendered as static HTML."""

from __future__ import annotations

from pathlib import Path

from ..config import load_config
from ..fleet_state import publish_fleet_artifact_freshness
from ..occ_reducer_status import write_occ_reducer_status
from smbagent.slm.framework_status import write_slm_framework_status
from ..next_stage_priorities import write_next_stage_priorities_summary

from .dashboard_html import _table
from .dashboard_loaders import collect_customer_summaries, _load_fleet_analytics
from .dashboard_sections import (
    _agent_isolation_section,
    _fleet_analytics_section,
    _footer,
    _header,
    _next_stage_section,
    _occ_reducer_section,
    _slm_framework_section,
)
from .dashboard_types import CustomerSummary


'''

TYPES.write_text(types_header + "".join(types_body), encoding="utf-8")
LOADERS.write_text(loaders_header + "".join(loaders_body), encoding="utf-8")
SECTIONS.write_text(sections_header + "".join(sections_body), encoding="utf-8")
HTML.write_text(html_header + "".join(html_body), encoding="utf-8")
FACADE.write_text(facade_header + "".join(facade_body), encoding="utf-8")
print("Split dashboard into types/loaders/sections/html/facade")
