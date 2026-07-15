from smbagent.game_studio import (
    GameAssetSpec,
    GamePackage,
    GamePlan,
    GameQualification,
    GameReleaseChecklist,
    GameRequirements,
    GameSceneSpec,
    GameTemplate,
)


def test_game_qualification_roundtrip(workspace):
    q = GameQualification(
        customer_id="test-customer",
        go=True,
        recommended_package=GamePackage.CAMPAIGN,
        recommended_templates=[GameTemplate.QUIZ],
        summary_ja="対応可能です。",
    )
    workspace.save_game_qualification(q)
    assert workspace.load_game_qualification() == q


def test_game_requirements_roundtrip(workspace):
    req = GameRequirements(
        customer_id="test-customer",
        package=GamePackage.CAMPAIGN,
        project_name="春キャンペーン",
        business_goal="送客",
        summary_ja="春のキャンペーンゲーム",
        preferred_templates=[GameTemplate.QUIZ],
        required_scenes=["title", "play", "result"],
        acceptance_criteria=["スマホで遊べる"],
    )
    workspace.save_game_requirements(req)
    assert workspace.load_game_requirements() == req


def test_game_plan_roundtrip_and_derived_artifacts(workspace):
    plan = GamePlan(
        package=GamePackage.CAMPAIGN,
        summary="Campaign quiz.",
        primary_template=GameTemplate.QUIZ,
        scenes=[
            GameSceneSpec(name="title", purpose="entry"),
            GameSceneSpec(name="play", purpose="quiz"),
            GameSceneSpec(name="result", purpose="result"),
        ],
        assets=[GameAssetSpec(name="logo", kind="logo", source="customer-uploaded")],
        site_pages=["/"],
        ops_features=["coupon display"],
        analytics_events=["game_start"],
    )
    checklist = GameReleaseChecklist(checks=["mobile ok", "jp text ok"])
    workspace.save_game_plan(plan, "# game design", checklist)

    assert workspace.game_design_path.read_text(encoding="utf-8") == "# game design"
    assert workspace.load_game_plan() == plan
    assert workspace.load_game_release_checklist() == checklist
    assert '"scenes"' in workspace.scene_map_path.read_text(encoding="utf-8")
    assert '"assets"' in workspace.asset_manifest_path.read_text(encoding="utf-8")
