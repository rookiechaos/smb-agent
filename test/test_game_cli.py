from __future__ import annotations

import shutil
from collections.abc import Iterator

import pytest
from typer.testing import CliRunner

from smbagent.cli import app as cli_app
from smbagent.config import load_config

runner = CliRunner()


@pytest.fixture
def cleanup_workspaces() -> Iterator[list[str]]:
    cleanup_ids: list[str] = []
    try:
        yield cleanup_ids
    finally:
        cfg = load_config()
        for cid in cleanup_ids:
            ws_path = cfg.workspaces_dir / cid
            if ws_path.exists():
                shutil.rmtree(ws_path, ignore_errors=True)


def test_qualify_game_command_success(monkeypatch, cleanup_workspaces):
    from smbagent.game_studio import GamePackage, GameQualification, GameTemplate

    cid = "clitest-game-qualify"
    cleanup_workspaces.append(cid)

    class _FakeQualify:
        def __init__(self, cfg):
            pass

        def run(self, workspace, brief):
            q = GameQualification(
                customer_id=workspace.customer_id,
                go=True,
                recommended_package=GamePackage.CAMPAIGN,
                recommended_templates=[GameTemplate.QUIZ],
                summary_ja="対応可能です。",
            )
            workspace.save_game_qualification(q)
            return q

    monkeypatch.setattr("smbagent.cli.GameQualifyAgent", _FakeQualify)
    runner.invoke(cli_app, ["new", cid])
    result = runner.invoke(cli_app, ["qualify-game", cid, "--brief", "夏の販促クイズ"])
    assert result.exit_code == 0
    assert "recommended package" in result.stdout
    assert "campaign" in result.stdout


def test_negotiate_game_uses_qualification_package(monkeypatch, cleanup_workspaces):
    from smbagent.game_studio import GamePackage, GameQualification
    from smbagent.workspace import Workspace

    cid = "clitest-game-negotiate"
    cleanup_workspaces.append(cid)
    captured = {}

    class _FakeNegotiation:
        def __init__(self, cfg):
            pass

        def run(self, workspace, package):
            captured["package"] = package

    monkeypatch.setattr("smbagent.cli.GameNegotiationAgent", _FakeNegotiation)
    runner.invoke(cli_app, ["new", cid])
    cfg = load_config()
    ws = Workspace(cid, cfg.workspaces_dir)
    ws.save_game_qualification(
        GameQualification(
            customer_id=cid,
            go=True,
            recommended_package=GamePackage.LITE,
            summary_ja="ok",
        )
    )
    result = runner.invoke(cli_app, ["negotiate-game", cid])
    assert result.exit_code == 0
    assert captured["package"] == GamePackage.LITE


def test_plan_game_errors_when_requirements_missing(cleanup_workspaces):
    cid = "clitest-game-plan-missing"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])
    result = runner.invoke(cli_app, ["plan-game", cid])
    assert result.exit_code != 0


def test_game_template_materialize(cleanup_workspaces):
    cid = "clitest-game-template"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])
    result = runner.invoke(cli_app, ["game-template", "materialize", "campaign-quiz", "--customer", cid])
    assert result.exit_code == 0
    assert "Materialized game scaffold" in result.stdout
    cfg = load_config()
    assert (cfg.workspaces_dir / cid / "code" / "game" / "scenes" / "title.scene.json").exists()


def test_check_game_structure_passes_on_scaffold(cleanup_workspaces):
    cid = "clitest-game-check"
    cleanup_workspaces.append(cid)
    runner.invoke(cli_app, ["new", cid])
    runner.invoke(cli_app, ["game-template", "materialize", "campaign-quiz", "--customer", cid])
    cfg = load_config()
    (cfg.workspaces_dir / cid / "code" / "README.md").write_text("# Scaffold", encoding="utf-8")
    result = runner.invoke(cli_app, ["check-game-structure", cid, "--package", "campaign"])
    assert result.exit_code == 0
    assert "passed" in result.stdout.lower()


def test_run_game_happy_path(monkeypatch, cleanup_workspaces):
    from smbagent.game_studio import (
        GamePackage,
        GamePlan,
        GameQualification,
        GameReleaseChecklist,
        GameRequirements,
        GameSceneSpec,
        GameTemplate,
    )

    cid = "clitest-run-game"
    cleanup_workspaces.append(cid)

    class _FakeQualify:
        def __init__(self, cfg):
            pass

        def run(self, workspace, brief):
            q = GameQualification(
                customer_id=workspace.customer_id,
                go=True,
                recommended_package=GamePackage.CAMPAIGN,
                recommended_templates=[GameTemplate.QUIZ],
                summary_ja="対応可能です。",
            )
            workspace.save_game_qualification(q)
            return q

    class _FakeNegotiation:
        def __init__(self, cfg):
            pass

        def run(self, workspace, package):
            req = GameRequirements(
                customer_id=workspace.customer_id,
                package=package,
                project_name="夏クイズ",
                business_goal="集客",
                summary_ja="販促クイズ",
                required_scenes=["title", "play", "result"],
                acceptance_criteria=["スマホで快適に遊べる"],
            )
            workspace.save_game_requirements(req)
            workspace.game_transcript_path.write_text("USER: 販促", encoding="utf-8")
            return req

    class _FakePlan:
        def __init__(self, cfg):
            pass

        def run(self, workspace):
            plan = GamePlan(
                package=GamePackage.CAMPAIGN,
                summary="Campaign quiz",
                primary_template=GameTemplate.QUIZ,
                scenes=[
                    GameSceneSpec(name="title", purpose="entry"),
                    GameSceneSpec(name="play", purpose="quiz"),
                    GameSceneSpec(name="result", purpose="result"),
                ],
                site_pages=["/"],
                ops_features=["coupon display"],
            )
            workspace.save_game_plan(plan, "# Design", GameReleaseChecklist(checks=["ok"]))
            return plan

    monkeypatch.setattr("smbagent.cli.GameQualifyAgent", _FakeQualify)
    monkeypatch.setattr("smbagent.cli.GameNegotiationAgent", _FakeNegotiation)
    monkeypatch.setattr("smbagent.cli.GamePlanAgent", _FakePlan)

    runner.invoke(cli_app, ["new", cid])
    result = runner.invoke(cli_app, ["run-game", cid, "--brief", "夏の販促ゲーム"])
    assert result.exit_code == 0
    assert "completed" in result.stdout.lower()
