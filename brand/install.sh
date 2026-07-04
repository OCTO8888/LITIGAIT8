#!/usr/bin/env bash
# =============================================================================
# Incorporate the Intrustum brand kit into the running site.
#
# Idempotent end-to-end. Run from the repo root on Replit:
#
#     bash brand/install.sh
#
# It will:
#   1. sync the canonical marks into the Django static tree,
#   2. wire css/favicon/lockup into cl/assets/templates/base.html,
#   3. verify every mark against Production Handoff v1.0 (fails on drift).
#
# Pass --check to verify only (no edits). Reverse the template edits any time
# with:  git checkout cl/assets/templates/base.html
# =============================================================================
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
echo "Intrustum brand kit → $ROOT"

# 1. Canonical marks are the source of truth; mirror them into static-global.
DEST="cl/assets/static-global/svg/intrustum"
mkdir -p "$DEST" "cl/assets/static-global/css" "cl/assets/templates/includes"
cp brand/assets/*.svg "$DEST/"
cp brand/brand.css "cl/assets/static-global/css/intrustum.css"
cp brand/django/_intrustum_lockup.html "cl/assets/templates/includes/_intrustum_lockup.html"
echo "  synced assets → $DEST, css/intrustum.css, includes/_intrustum_lockup.html"

if [[ "${1:-}" == "--check" ]]; then
  echo
  exec python3 brand/verify_marks.py
fi

# 2. Wire into base.html (idempotent; guarded by INTRUSTUM-KIT markers).
echo
echo "Wiring base.html:"
python3 brand/wire_into_site.py

# 3. Enforce the spec.
echo
python3 brand/verify_marks.py

echo
echo "Done. Restart the Django server to pick up template/static changes."
echo "Undo template edits with: git checkout cl/assets/templates/base.html"
