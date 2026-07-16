#!/usr/bin/env bash
# Create a clean product tree for IP transfer / buyer due diligence.
# Usage: ./scripts/export_product_tree.sh [dest_dir]

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-/tmp/smbagent-transfer-$(date +%Y%m%d)}"

if [[ -e "$DEST" ]]; then
  echo "Destination already exists: $DEST" >&2
  echo "Choose a new path or remove it first." >&2
  exit 1
fi

mkdir -p "$DEST"

# Copy tracked-like product content while excluding local runtime junk.
# Prefer rsync when available.
RSYNC_EXCLUDES=(
  --exclude '.git/'
  --exclude '.venv/'
  --exclude '__pycache__/'
  --exclude '.pytest_cache/'
  --exclude '.ruff_cache/'
  --exclude '.mypy_cache/'
  --exclude '.artifacts/'
  --exclude '.DS_Store'
  --exclude '.env'
  --exclude '.claude/'
  --exclude 'do-not-upload/'
  --exclude 'ops/fleet_state.json'
  --exclude 'ops/slm_framework_status.json'
  --exclude 'ops/.fleet_state.lock'
  --exclude 'ops/runtime/'
  --exclude 'ops/slm_packs/*'
  --exclude 'ops/launchd/*.plist'
  --exclude 'ops/release_reviews/'
  --exclude 'ops/pre_release_check.json'
  --exclude 'ops/pre_release_check.md'
  --exclude 'tuning/changes.jsonl'
  --exclude 'tuning/iteration.json'
  --exclude 'workspaces/*'
  --exclude 'analytics/*'
  --exclude '*.pyc'
  --exclude 'dist/'
  --exclude 'build/'
  --exclude '*.egg-info/'
)

if command -v rsync >/dev/null 2>&1; then
  rsync -a "${RSYNC_EXCLUDES[@]}" "$ROOT/" "$DEST/"
else
  echo "rsync not found; falling back to tar stream" >&2
  tar -C "$ROOT" \
    --exclude '.git' \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '.pytest_cache' \
    --exclude '.ruff_cache' \
    --exclude '.mypy_cache' \
    --exclude '.artifacts' \
    --exclude '.DS_Store' \
    --exclude '.env' \
    --exclude '.claude' \
    --exclude 'do-not-upload' \
    --exclude 'ops/runtime' \
    --exclude 'dist' \
    --exclude 'build' \
    -cf - . | tar -C "$DEST" -xf -
fi

# Ensure runtime placeholders exist and stay empty of customer data.
mkdir -p "$DEST/workspaces" "$DEST/analytics" "$DEST/ops/slm_packs" "$DEST/ops/launchd"
touch "$DEST/workspaces/.gitkeep" "$DEST/analytics/.gitkeep" \
  "$DEST/ops/slm_packs/.gitkeep" "$DEST/ops/launchd/.gitkeep"

# Drop accidental workspace/analytics copies except README/.gitkeep
find "$DEST/workspaces" "$DEST/analytics" -mindepth 1 -maxdepth 1 \
  ! -name '.gitkeep' ! -name 'README.md' -exec rm -rf {} + 2>/dev/null || true

# Restore README placeholders if present in source
[[ -f "$ROOT/workspaces/README.md" ]] && cp "$ROOT/workspaces/README.md" "$DEST/workspaces/README.md"
[[ -f "$ROOT/analytics/README.md" ]] && cp "$ROOT/analytics/README.md" "$DEST/analytics/README.md"

cat > "$DEST/TRANSFER_MANIFEST.txt" <<EOF
smbagent transfer tree
exported_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
source_root=$ROOT
buyer_docs=docs/buyer/README.md
transfer_onepager_en=docs/buyer/TRANSFER_ONEPAGER_EN.md
transfer_onepager_ja=docs/buyer/TRANSFER_ONEPAGER_JA.md
excluded=do-not-upload/, .venv/, .env, caches, local ops/tuning state
note=Seller-only materials under do-not-upload/ were not copied. Fill .env from .env.example on the buyer machine.
EOF

echo "Clean tree written to: $DEST"
echo "Next: see docs/buyer/EXPORT.md and docs/buyer/HANDOFF_CHECKLIST.md"
