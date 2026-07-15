from __future__ import annotations

from pathlib import Path


def test_apple_container_files_exist():
    root = Path(__file__).resolve().parent.parent
    expected = [
        root / "containers" / "apple" / "README.md",
        root / "containers" / "apple" / "claude-code" / "Containerfile",
        root / "containers" / "apple" / "claude-code" / "entrypoint.sh",
        root / "containers" / "apple" / "codex-validation" / "Containerfile",
        root / "containers" / "apple" / "codex-validation" / "entrypoint.sh",
    ]
    for path in expected:
        assert path.exists(), f"missing {path}"


def test_apple_container_contract_mentions_no_ports_and_runtime_env():
    root = Path(__file__).resolve().parent.parent
    body = (root / "containers" / "apple" / "README.md").read_text(encoding="utf-8")
    assert "no published ports" in body
    assert "ANTHROPIC_API_KEY" in body
    assert "OPENAI_API_KEY" in body


def test_apple_containerfiles_pin_cli_install_contract():
    root = Path(__file__).resolve().parent.parent
    claude = (root / "containers" / "apple" / "claude-code" / "Containerfile").read_text(encoding="utf-8")
    codex = (root / "containers" / "apple" / "codex-validation" / "Containerfile").read_text(encoding="utf-8")
    assert "CLAUDE_CODE_INSTALL_CMD" in claude
    assert "@anthropic-ai/claude-code" in claude
    assert "pip install --no-cache-dir anthropic" in claude
    assert "CODEX_INSTALL_CMD" in codex
    assert "@openai/codex" in codex
    assert "pip install --no-cache-dir openai" in codex
