#!/usr/bin/env bash
# Build a checksummed SPA transfer archive with provenance metadata.
# Usage: ./scripts/package_transfer_release.sh [output_dir]
#
# Does not require git history. Emits:
#   <stem>/                 clean export tree
#   <stem>.tar.gz           archive
#   <stem>.sha256           sha256 of the archive
#   <stem>/PROVENANCE.txt   authorship + hash + packing notes

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_ROOT="${1:-/tmp}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
STEM="smbagent-transfer-${STAMP}"
DEST="${OUT_ROOT%/}/${STEM}"
ARCHIVE="${DEST}.tar.gz"
CHECKSUM_FILE="${DEST}.sha256"

"$ROOT/scripts/export_product_tree.sh" "$DEST"

GIT_HEAD="none"
GIT_DESC="working-tree-without-commit"
if git -C "$ROOT" rev-parse --verify HEAD >/dev/null 2>&1; then
  GIT_HEAD="$(git -C "$ROOT" rev-parse HEAD)"
  GIT_DESC="$(git -C "$ROOT" describe --always --dirty 2>/dev/null || echo "${GIT_HEAD}")"
fi

TREE_HASH="$(
  python3 - "$DEST" <<'PY'
import hashlib
import sys
from pathlib import Path

root = Path(sys.argv[1])
h = hashlib.sha256()
paths = sorted(
    p for p in root.rglob("*") if p.is_file() and p.name != "PROVENANCE.txt"
)
for path in paths:
    rel = path.relative_to(root).as_posix().encode()
    digest = hashlib.sha256(path.read_bytes()).hexdigest().encode()
    h.update(rel + b"\0" + digest + b"\n")
print(h.hexdigest())
PY
)"

python3 - "$DEST/PROVENANCE.txt" <<PY
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = """smbagent SPA transfer provenance
================================
packed_at_utc=${STAMP}
package_stem=${STEM}
source_root=${ROOT}
git_head=${GIT_HEAD}
git_describe=${GIT_DESC}
content_tree_sha256=${TREE_HASH}

authorship
----------
See NOTICE and LICENSE in this package.
Copyright line: Copyright 2026 the smbagent authors.
Commercial ownership / copyright assignment is governed by the SPA, not by
git history alone. If git_head=none, provenance for counsel is this archive
checksum plus the signed Schedule of Assets.

schedule_of_assets
------------------
docs/buyer/SPA_SCHEDULE_OF_ASSETS_EN.md
docs/buyer/SPA_SCHEDULE_OF_ASSETS_JA.md

disclosures
-----------
1. Historical product-shape wording may have referenced third-party market
   names in older drafts; active prompts/comments were scrubbed for transfer.
   Any residual mention is descriptive residue only and does not grant or imply
   third-party trademark/software license rights.
2. Root PRICING.md is a buyer-must-replace placeholder. Seller rate cards are
   excluded under do-not-upload/.
3. Seller-withheld partner/customer workflow packages and partner-demo assets
   are excluded from this package under do-not-upload/.

verify
------
shasum -a 256 -c ${STEM}.sha256
"""
path.write_text(text, encoding="utf-8")
PY

{
  echo ""
  echo "provenance_file=PROVENANCE.txt"
  echo "content_tree_sha256=${TREE_HASH}"
  echo "git_head=${GIT_HEAD}"
  echo "spa_schedule_en=docs/buyer/SPA_SCHEDULE_OF_ASSETS_EN.md"
  echo "spa_schedule_ja=docs/buyer/SPA_SCHEDULE_OF_ASSETS_JA.md"
} >> "${DEST}/TRANSFER_MANIFEST.txt"

PARENT="$(dirname "${DEST}")"
BASE="$(basename "${DEST}")"
tar -C "${PARENT}" -czf "${ARCHIVE}" "${BASE}"
(
  cd "${PARENT}"
  shasum -a 256 "${BASE}.tar.gz" > "${BASE}.sha256"
)

echo "Archive:  ${ARCHIVE}"
echo "Checksum: ${CHECKSUM_FILE}"
echo "Tree:     ${DEST}"
echo "Verify:   shasum -a 256 -c ${CHECKSUM_FILE}"
echo "Next:     attach docs/buyer/SPA_SCHEDULE_OF_ASSETS_EN.md and _JA.md to the SPA"
