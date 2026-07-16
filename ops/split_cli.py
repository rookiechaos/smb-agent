#!/usr/bin/env python3
"""One-shot helper: split smbagent/cli.py into smbagent/cli/*.py modules."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = ROOT / "smbagent" / "cli.py"
OUT_DIR = ROOT / "smbagent" / "cli"

RENAME_HELPERS = {
    "_default_slm_registry_paths": "default_slm_registry_paths",
    "_render_apple_container_plan": "render_apple_container_plan",
    "_print_apple_container_plan": "print_apple_container_plan",
    "_resolve_tier": "resolve_tier",
    "_resolve_game_package": "resolve_game_package",
    "_print_tuning_view": "print_tuning_view",
    "_version_callback": "_version_callback",
}


def module_for(name: str) -> str:
    if name.startswith("tune_"):
        return "tuning"
    if name.startswith("slm_"):
        return "slm"
    if name.startswith("ikida_"):
        return "ikida"
    if name in {
        "qualify_game",
        "negotiate_game",
        "plan_game",
        "check_game_structure",
        "validate_game",
        "game_template",
        "status_game",
        "run_game",
    }:
        return "game"
    if name in {"doctor", "apple_container_plan", "image_contract"}:
        return "diagnostics"
    if name in {
        "new",
        "state",
        "context_update",
        "retention_plan",
        "qualify",
        "run",
        "negotiate",
        "plan",
        "validate",
        "migrate",
        "replay",
        "tiers",
        "status",
    }:
        return "pipeline"
    if name.startswith("workflow_"):
        return "workflows"
    if name in {
        "trust_eval",
        "trust_regression_contract",
        "japan_trust_note",
        "customer_legal_review",
        "japan_trust_launch_review",
        "launch_readiness",
        "deployment_readiness",
        "security_readiness",
        "commercial_readiness",
        "repo_hygiene",
        "pre_release_check",
        "launch_notes",
        "network_posture",
        "vpn_plan",
    }:
        return "readiness"
    if name.startswith("secret_"):
        return "secrets"
    if name in {
        "coding_benchmarks",
        "remote_benchmark_plan",
        "remote_benchmark_record",
        "harness_profiles",
        "smoke_harness",
        "loop_policy",
        "loop_engineering",
    }:
        return "benchmarks"
    if name.startswith("voice_") or name.startswith("consent_"):
        return "voice"
    if name in {"approval_record", "approval_log", "auth_rotate_legacy", "backup", "restore"}:
        return "governance"
    if name in {
        "serve",
        "deploy",
        "send",
        "template",
        "portal",
        "monitor",
        "dashboard",
        "auth_issue",
        "auth_show",
        "monitor_auth_issue",
        "monitor_auth_show",
        "employee_auth_issue",
        "employee_auth_show",
        "maintenance",
        "serve_http",
        "book",
    }:
        return "runtime"
    if name in {
        "memory_analytics",
        "next_stage_summary",
        "occ_reducer_status",
        "slm_framework_status",
        "launchd_plist",
    }:
        return "ops"
    raise ValueError(f"no module mapping for command function {name!r}")


def rename_helpers(text: str) -> str:
    for old, new in RENAME_HELPERS.items():
        if old != new:
            text = text.replace(old, new)
    return text


def extract_import_block(source: str) -> str:
    lines = source.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        if line.startswith("app = typer.Typer"):
            return "".join(lines[:idx])
    raise RuntimeError("could not find app = typer.Typer")


def extract_helpers(source: str) -> str:
    start = source.index("def _default_slm_registry_paths")
    end = source.index("@app.command()\ndef doctor")
    return source[start:end]


def split_command_blocks(source: str) -> tuple[dict[str, str], str]:
    tuning_block = ""
    if "tune_app = typer.Typer(" in source:
        tuning_start = source.index("tune_app = typer.Typer(")
        tuning_block = source[tuning_start:]
        source = source[:tuning_start]

    pattern = re.compile(
        r"^(?P<decorator>@(?:app|tune_app)\.command(?:\([^)]*\))?)\n"
        r"def (?P<name>[a-zA-Z0-9_]+)\(",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(source))
    blocks: dict[str, list[str]] = {}
    for idx, match in enumerate(matches):
        name = match.group("name")
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(source)
        chunk = rename_helpers(source[start:end].rstrip() + "\n\n")
        module = module_for(name)
        blocks.setdefault(module, []).append(chunk)
    module_bodies = {module: "".join(chunks) for module, chunks in blocks.items()}
    return module_bodies, rename_helpers(tuning_block)


MODULE_HEADER = """from __future__ import annotations

from .app import app, console, tune_app
from ._shared import *  # noqa: F403

"""


def main() -> None:
    source = CLI_PATH.read_text(encoding="utf-8")
    import_block = extract_import_block(source)
    import_block = import_block.replace("from slm.", "from ..slm.")
    import_block = re.sub(r"^from \.", "from ..", import_block, flags=re.MULTILINE)
    helpers = rename_helpers(extract_helpers(source))
    module_bodies, tuning_block = split_command_blocks(source)

    OUT_DIR.mkdir(exist_ok=True)

    (OUT_DIR / "_shared.py").write_text(
        "from __future__ import annotations\n\n"
        + import_block
        + "\n"
        + helpers,
        encoding="utf-8",
    )

    (OUT_DIR / "app.py").write_text(
        '''from __future__ import annotations

import typer
from rich.console import Console

app = typer.Typer(
    help="Trustable Mac-mini-first SMB operations backend CLI.",
)
console = Console()
tune_app = typer.Typer(
    help="Tune coding↔validation hyperparameters (annealing + bridge). "
    "Overrides env defaults via JSON files; no restart required.",
)
''',
        encoding="utf-8",
    )

    for module, body in sorted(module_bodies.items()):
        (OUT_DIR / f"{module}.py").write_text(MODULE_HEADER + body, encoding="utf-8")

    if tuning_block:
        tuning_block = tuning_block.replace("app.add_typer(tune_app, name=\"tune\")\n", "")
        (OUT_DIR / "tuning.py").write_text(MODULE_HEADER + tuning_block, encoding="utf-8")

    init = '''from __future__ import annotations

import typer

from .. import __version__
from .app import app, console, tune_app

from . import (  # noqa: E402,F401
    benchmarks,
    diagnostics,
    game,
    governance,
    ikida,
    ops,
    pipeline,
    readiness,
    runtime,
    secrets,
    slm,
    tuning,
    voice,
    workflows,
)

app.add_typer(tune_app, name="tune")


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"smbagent {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show smbagent version and exit.",
    ),
) -> None:
    """smbagent CLI."""


# Re-export symbols patched by tests that target smbagent.cli.*
from ..agents.negotiation import NegotiationAgent
from ..agents.plan import PlanAgent
from ..agents.qualify import QualifyAgent
from ..agents.validation import ValidationAgent
from ..deploy import resolve_target
from ..doctor import run_doctor_checks
from ..game_studio.agents import GameNegotiationAgent, GamePlanAgent
from ..game_studio.qualify import GameQualifyAgent
from ..launch_readiness import evaluate_launch_readiness
from ..orchestrator import Pipeline
from ..runtime import SkillsRuntime
from ..transports import BookingForwarder, MailForwarder

__all__ = [
    "app",
    "console",
    "tune_app",
    "QualifyAgent",
    "NegotiationAgent",
    "PlanAgent",
    "ValidationAgent",
    "Pipeline",
    "SkillsRuntime",
    "BookingForwarder",
    "MailForwarder",
    "resolve_target",
    "run_doctor_checks",
    "evaluate_launch_readiness",
    "GameQualifyAgent",
    "GameNegotiationAgent",
    "GamePlanAgent",
]


if __name__ == "__main__":
    app()
'''
    (OUT_DIR / "__init__.py").write_text(init, encoding="utf-8")
    print(f"Wrote cli package with modules: {', '.join(sorted(module_bodies) + (['tuning'] if tuning_block else []))}")


if __name__ == "__main__":
    main()
