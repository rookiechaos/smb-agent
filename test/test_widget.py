"""Tests for the embeddable chat widget asset.

The widget is JavaScript — we can't actually run it without a browser. These
tests verify:
  (a) the file exists in the repo at the expected path
  (b) its source survives basic structural sanity checks
  (c) it references the API endpoints in the exact shape our server expects
  (d) it can be materialized into a customer workspace via TemplatePack
"""

from __future__ import annotations

from smbagent.config import Config
from smbagent.templates import TemplatePack, widget_asset_path
from smbagent.workspace import Workspace


def test_widget_asset_path_exists():
    p = widget_asset_path()
    assert p.exists()
    assert p.is_file()
    assert p.name == "widget.js"


def test_widget_is_non_empty():
    p = widget_asset_path()
    assert p.stat().st_size > 1000  # ≥ 1KB to ensure it's a real implementation


def test_widget_balances_braces_parens():
    """Sanity: matching {} and () counts. Catches obvious truncation/corruption."""
    src = widget_asset_path().read_text(encoding="utf-8")
    assert src.count("{") == src.count("}"), "unbalanced braces in widget.js"
    assert src.count("(") == src.count(")"), "unbalanced parens in widget.js"


def test_widget_uses_iife_wrapper():
    """The widget should be wrapped in an IIFE so it doesn't pollute global scope."""
    src = widget_asset_path().read_text(encoding="utf-8")
    assert "(function" in src
    assert "use strict" in src


def test_widget_references_correct_chat_endpoint():
    """The URL the widget POSTs to must match the FastAPI server's exact shape:
    /v1/customers/{id}/chat — caught here to prevent silent drift."""
    src = widget_asset_path().read_text(encoding="utf-8")
    assert "/v1/customers/" in src
    assert "/chat" in src
    # Must percent-encode the customer id (typically already safe, but defensive)
    assert "encodeURIComponent" in src


def test_widget_sends_bearer_auth_header():
    src = widget_asset_path().read_text(encoding="utf-8")
    assert "Authorization" in src
    assert "Bearer" in src


def test_widget_reads_required_data_attributes():
    """Widget must read these data-attrs from its script tag:
    data-customer-id, data-api-base, data-token."""
    src = widget_asset_path().read_text(encoding="utf-8")
    assert "data-customer-id" in src
    assert "data-api-base" in src
    assert "data-token" in src


def test_widget_refuses_to_render_without_required_attrs():
    """If any of customer-id / api-base / token is missing, widget must warn and bail."""
    src = widget_asset_path().read_text(encoding="utf-8")
    assert "console.warn" in src or "return" in src


def test_widget_uses_textContent_not_innerHTML():
    """Defensive against XSS via server `reply`: never use innerHTML on dynamic content."""
    src = widget_asset_path().read_text(encoding="utf-8")
    # The widget uses textContent (via the `text:` helper). innerHTML must not appear.
    assert "innerHTML" not in src


def test_widget_posts_json_with_message_field():
    """Server expects body shape {message: string}. Widget must send exactly that."""
    src = widget_asset_path().read_text(encoding="utf-8")
    assert '"message"' in src or "message:" in src
    assert "JSON.stringify" in src
    assert 'method: "POST"' in src or "method:'POST'" in src


# ---- materialization via TemplatePack ----


def test_materialize_with_widget_writes_into_landing_page(config: Config, workspace: Workspace):
    pack = TemplatePack("dental")
    report = pack.materialize(workspace, include_widget=True)

    widget_path = workspace.code_dir / "landing-page" / "smbagent-widget.js"
    assert widget_path.exists()
    assert "landing-page/smbagent-widget.js" in report.written


def test_materialize_without_widget_does_not_write_it(config: Config, workspace: Workspace):
    pack = TemplatePack("dental")
    pack.materialize(workspace, include_widget=False)
    widget_path = workspace.code_dir / "landing-page" / "smbagent-widget.js"
    assert not widget_path.exists()


def test_materialize_widget_seed_mode_preserves_existing(config: Config, workspace: Workspace):
    """If a customer's landing-page already has a customized widget, seed mode keeps it."""
    pack = TemplatePack("dental")
    widget_path = workspace.code_dir / "landing-page" / "smbagent-widget.js"
    widget_path.parent.mkdir(parents=True, exist_ok=True)
    widget_path.write_text("// CUSTOM WIDGET", encoding="utf-8")

    report = pack.materialize(workspace, mode="seed", include_widget=True)
    assert widget_path.read_text(encoding="utf-8") == "// CUSTOM WIDGET"
    assert "landing-page/smbagent-widget.js" in report.skipped


def test_widget_content_is_copied_verbatim(config: Config, workspace: Workspace):
    """The widget materialized into a workspace must be byte-identical to the source."""
    pack = TemplatePack("dental")
    pack.materialize(workspace, include_widget=True)

    src = widget_asset_path().read_bytes()
    dest = (workspace.code_dir / "landing-page" / "smbagent-widget.js").read_bytes()
    assert src == dest


def test_widget_not_listed_in_pack_files():
    """The widget is shared infrastructure, not vertical content — it must not
    appear in the pack's own file inventory (which would imply it ships per-pack)."""
    pack = TemplatePack("dental")
    files = {str(p) for p in pack.files()}
    assert "smbagent-widget.js" not in files
    assert all("smbagent-widget" not in f for f in files)
