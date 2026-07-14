# Clean export for IP transfer

Use this before sending a zip/tarball to a buyer.

## Recommended commands

Clean tree only:

```bash
./scripts/export_product_tree.sh /tmp/smbagent-transfer
```

**SPA delivery package (preferred for counsel):**

```bash
./scripts/package_transfer_release.sh /tmp
# produces: smbagent-transfer-<UTC>/ , .tar.gz , .sha256 , PROVENANCE.txt
shasum -a 256 -c /tmp/smbagent-transfer-*.sha256
```

Attach [`SPA_SCHEDULE_OF_ASSETS_EN.md`](SPA_SCHEDULE_OF_ASSETS_EN.md) /
[`SPA_SCHEDULE_OF_ASSETS_JA.md`](SPA_SCHEDULE_OF_ASSETS_JA.md) to the SPA.

## Always exclude

- **`do-not-upload/`** — seller-only pricing, partner brand assets, pioneer notes, local IDE/ops/tuning state
- `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`
- `.env` (secrets)
- `.DS_Store`
- `.claude/` (local IDE state)
- `ops/fleet_state.json`, `ops/slm_framework_status.json`, `ops/.fleet_state.lock`
- `ops/runtime/` (sqlite rate limits, etc.)
- `ops/slm_packs/*` except `.gitkeep`
- `ops/launchd/*.plist` except `.gitkeep`
- `ops/release_reviews/`, `ops/pre_release_check.*`
- `tuning/changes.jsonl`, `tuning/iteration.json`
- Any real content under `workspaces/*` / `analytics/*` except README + `.gitkeep`
- `.artifacts/`

## Include

- Source: `smbagent/`, `slm/`, `tests/`, `portal/`, `japan_trust/`
- Containers contract: `containers/`
- Docs: root commercial docs + `docs/buyer/` + `internal_doc/` (stubs for withheld notes)
- Examples: `examples/demo-tokyo-dental/` (not partner-demo)
- `pyproject.toml`, `LICENSE`, `NOTICE`, `.env.example`, `.gitignore`
- CI: `.github/`

## After export

```bash
cd /tmp/smbagent-transfer-*   # or your dest
test ! -d do-not-upload
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
shasum -a 256 -b ../smbagent-transfer-*.tar.gz   # if you archived it
```

## Archive example

```bash
DEST=/tmp/smbagent-transfer-$(date +%Y%m%d)
./scripts/export_product_tree.sh "$DEST"
tar -C "$(dirname "$DEST")" -czf "${DEST}.tar.gz" "$(basename "$DEST")"
shasum -a 256 "${DEST}.tar.gz"
```
