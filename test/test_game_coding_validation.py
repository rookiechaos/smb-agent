from smbagent.game_studio import (
    GamePackage,
    GamePlan,
    GameRequirements,
    GameSceneSpec,
    GameTemplate,
)
from smbagent.game_studio.coding import GameCodingAgent
from smbagent.game_studio.runtime_validation import GameValidationAgent


def test_game_coding_agent_materializes_plan_artifacts(config, workspace):
    workspace.save_game_requirements(
        GameRequirements(
            customer_id=workspace.customer_id,
            package=GamePackage.CAMPAIGN,
            project_name="夏クイズ",
            business_goal="集客",
            summary_ja="販促クイズ",
            required_scenes=["title", "play", "result"],
            acceptance_criteria=["スマホで快適に遊べる"],
        )
    )
    workspace.save_game_plan(
        GamePlan(
            package=GamePackage.CAMPAIGN,
            summary="Campaign quiz",
            primary_template=GameTemplate.QUIZ,
            scenes=[
                GameSceneSpec(name="title", purpose="entry", key_ui=["cta"]),
                GameSceneSpec(name="play", purpose="quiz", key_ui=["question"]),
                GameSceneSpec(name="result", purpose="result", key_ui=["coupon"]),
            ],
            site_pages=["/"],
            ops_features=["coupon display"],
            analytics_events=["game_start", "game_complete"],
        ),
        "# Design",
    )

    GameCodingAgent(config).run(workspace, round_n=1)

    assert (workspace.code_dir / "game" / "scenes" / "title.scene.json").exists()
    assert (workspace.code_dir / "site" / "index.html").exists()
    assert (workspace.code_dir / "analytics" / "events.json").exists()
    assert workspace.game_coding_log_path(1).exists()


def test_game_validation_agent_writes_verdict_and_feedback(config, workspace):
    workspace.save_game_requirements(
        GameRequirements(
            customer_id=workspace.customer_id,
            package=GamePackage.CAMPAIGN,
            project_name="夏クイズ",
            business_goal="集客",
            summary_ja="販促クイズ",
            required_scenes=["title", "play", "result"],
            acceptance_criteria=["スマホで快適に遊べる"],
        )
    )
    workspace.save_game_plan(
        GamePlan(
            package=GamePackage.CAMPAIGN,
            summary="Campaign quiz",
            primary_template=GameTemplate.QUIZ,
            scenes=[
                GameSceneSpec(name="title", purpose="entry", key_ui=["cta"]),
                GameSceneSpec(name="play", purpose="quiz", key_ui=["question"]),
                GameSceneSpec(name="result", purpose="result", key_ui=["coupon"]),
            ],
            site_pages=["/"],
            ops_features=["coupon display"],
            analytics_events=["game_start", "game_complete"],
        ),
        "# Design",
    )
    GameCodingAgent(config).run(workspace, round_n=1)

    verdict = GameValidationAgent(config).run(workspace, round_n=1)
    assert verdict.passed is True
    assert workspace.game_verdict_path(1).exists()
    assert workspace.game_feedback_path(1).exists()
    assert workspace.game_validation_log_path(1).exists()


def test_game_validation_agent_flags_missing_required_scene(config, workspace):
    workspace.save_game_requirements(
        GameRequirements(
            customer_id=workspace.customer_id,
            package=GamePackage.CAMPAIGN,
            project_name="夏クイズ",
            business_goal="集客",
            summary_ja="販促クイズ",
            required_scenes=["title", "play", "result", "bonus"],
            acceptance_criteria=["スマホで快適に遊べる"],
        )
    )
    workspace.save_game_plan(
        GamePlan(
            package=GamePackage.CAMPAIGN,
            summary="Campaign quiz",
            primary_template=GameTemplate.QUIZ,
            scenes=[
                GameSceneSpec(name="title", purpose="entry", key_ui=["cta"]),
                GameSceneSpec(name="play", purpose="quiz", key_ui=["question"]),
                GameSceneSpec(name="result", purpose="result", key_ui=["coupon"]),
            ],
            site_pages=["/"],
            ops_features=["coupon display"],
        ),
        "# Design",
    )
    GameCodingAgent(config).run(workspace, round_n=1)
    verdict = GameValidationAgent(config).run(workspace, round_n=1)
    assert verdict.passed is False
    assert any("required scene `bonus`" in i.description for i in verdict.issues)
