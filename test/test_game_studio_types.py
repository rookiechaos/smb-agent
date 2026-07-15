from smbagent.game_studio import (
    GameAssetSpec,
    GamePackage,
    GamePlan,
    GameQualification,
    GameRequirements,
    GameSceneSpec,
    GameTemplate,
)


def test_game_qualification_go_requires_package():
    q = GameQualification(
        customer_id="acme-game",
        go=True,
        recommended_package=GamePackage.CAMPAIGN,
        recommended_templates=[GameTemplate.QUIZ],
        summary_ja="対応可能です。",
    )
    assert q.recommended_package == GamePackage.CAMPAIGN


def test_game_qualification_no_go_clears_package():
    q = GameQualification(
        customer_id="acme-game",
        go=False,
        recommended_package=GamePackage.LITE,
        summary_ja="対象外です。",
    )
    assert q.recommended_package is None


def test_game_requirements_accepts_game_fields():
    req = GameRequirements(
        customer_id="acme-game",
        package=GamePackage.CAMPAIGN,
        project_name="夏キャンペーンクイズ",
        business_goal="見込み客の獲得",
        summary_ja="夏の販促向けクイズゲーム",
        target_audience=["20代女性", "既存顧客"],
        preferred_templates=[GameTemplate.QUIZ],
        core_mechanics=["3問クイズ", "スコア表示"],
        required_scenes=["title", "play", "result"],
        reward_flow=["結果後にクーポン表示"],
        analytics_events=["game_start", "game_complete"],
        acceptance_criteria=["スマホで快適に遊べる"],
    )
    assert req.project_name == "夏キャンペーンクイズ"
    assert req.preferred_templates == [GameTemplate.QUIZ]


def test_game_plan_package_caps():
    plan = GamePlan(
        package=GamePackage.LITE,
        summary="Lightweight quiz campaign.",
        primary_template=GameTemplate.QUIZ,
        scenes=[
            GameSceneSpec(name="title", purpose="start"),
            GameSceneSpec(name="play", purpose="gameplay"),
            GameSceneSpec(name="result", purpose="result"),
            GameSceneSpec(name="extra", purpose="overflow"),
        ],
        assets=[
            GameAssetSpec(name="logo", kind="logo", source="customer-uploaded"),
        ],
        site_pages=["/"],
        ops_features=["coupon display"],
        analytics_events=["game_start"],
    )
    violations = plan.violates_package_caps()
    assert any("scenes exceed lite cap" in v for v in violations)


def test_game_plan_valid_campaign_shape_has_no_violations():
    plan = GamePlan(
        package=GamePackage.CAMPAIGN,
        summary="Campaign quiz plan.",
        primary_template=GameTemplate.QUIZ,
        scenes=[
            GameSceneSpec(name="title", purpose="start"),
            GameSceneSpec(name="play", purpose="quiz"),
            GameSceneSpec(name="result", purpose="result"),
        ],
        assets=[
            GameAssetSpec(name="logo", kind="logo", source="customer-uploaded"),
            GameAssetSpec(name="kv", kind="background", source="placeholder"),
        ],
        site_pages=["/"],
        ops_features=["coupon display", "lead form"],
        analytics_events=["game_start", "game_complete"],
    )
    assert plan.violates_package_caps() == []
