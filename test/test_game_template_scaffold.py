from pathlib import Path

from smbagent.game_studio import run_all_game_structural_checks
from smbagent.game_studio.types import GamePackage


def test_game_campaign_quiz_scaffold_meets_basic_contract():
    root = Path(__file__).resolve().parent.parent / "smbagent" / "templates" / "game-campaign-quiz"

    assert (root / "game" / "scenes" / "title.scene.json").exists()
    assert (root / "site" / "index.html").exists()
    assert (root / "analytics" / "events.json").exists()


def test_game_campaign_quiz_scaffold_passes_structural_checks(tmp_path: Path):
    from shutil import copytree

    scaffold = Path(__file__).resolve().parent.parent / "smbagent" / "templates" / "game-campaign-quiz"
    code = tmp_path / "code"
    copytree(scaffold, code)
    (code / "README.md").write_text("# Scaffold", encoding="utf-8")

    issues = run_all_game_structural_checks(code, GamePackage.CAMPAIGN)
    assert issues == []
