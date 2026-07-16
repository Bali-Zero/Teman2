#!/usr/bin/env bash
# Reproducible setup for the WR2 HTML renderer venv (.venv-wr2-html).
#
# WHY THIS EXISTS (scar W81 / html-venv-evaporation):
#   The deploy worktree (~/nuzantara-deploy) is periodically re-added
#   (git worktree add) which restores only tracked files. Venvs are gitignored,
#   so .venv-wr2-html evaporates on every re-add and the html-apply worker dies
#   with "No such file or directory: .../.venv-wr2-html/bin/python".
#   The backend venv self-heals (wr2-script-wrapper.sh), but the html venv had
#   no equivalent. This script is that equivalent — idempotent, re-run anytime.
#
# Deps: render (playwright + cached chromium), vision (claude CLI, in PATH),
#       OCR (easyocr), AND the backend.* import chain the Drive uploader pulls
#       (backend/services/integrations/__init__ → zoho → metrics → psutil, +
#       config → pydantic/pydantic-settings, + google-api). Installed via the
#       backend's own requirements-prod.txt (minus the editable cell-core line,
#       which is DNA-recording, unused by the renderer, and unresolvable here).
set -euo pipefail
REPO="${WR2_REPO_ROOT:-$HOME/nuzantara-deploy}"
PYENV_PY="${PYENV_PY311:-$HOME/.pyenv/versions/3.11.11/bin/python}"
VENV="$REPO/.venv-wr2-html"
VPY="$VENV/bin/python"
REQ="$REPO/apps/backend-rag/requirements-prod.txt"

[ -x "$PYENV_PY" ] || { echo "ERROR: pyenv 3.11.11 not found at $PYENV_PY" >&2; exit 75; }
[ -f "$REQ" ]      || { echo "ERROR: requirements-prod.txt not found at $REQ" >&2; exit 75; }

echo "[setup-html-venv] creating $VENV"
"$PYENV_PY" -m venv "$VENV"
"$VPY" -m pip install -q --upgrade pip

echo "[setup-html-venv] installing backend prod deps (cell-core editable stripped)"
FILTERED="$(mktemp)"
grep -vE "^-e |cell-core" "$REQ" > "$FILTERED"
"$VPY" -m pip install -q -r "$FILTERED" || true   # torch/setuptools cosmetic conflict is non-fatal
rm -f "$FILTERED"

echo "[setup-html-venv] installing renderer-only deps (playwright/easyocr not in prod reqs)"
"$VPY" -m pip install -q playwright easyocr

echo "[setup-html-venv] verifying full import chain"
cd "$REPO"
"$VPY" - <<PYEOF
import sys
sys.path.insert(0, "$REPO/apps/backend-rag"); sys.path.insert(0, "$REPO/scripts")
from backend.services.integrations.service_account_drive_service import ServiceAccountDriveService
import playwright, easyocr, psutil, numpy, PIL, asyncpg, pydantic, pydantic_settings
from playwright.sync_api import sync_playwright
print("[setup-html-venv] OK: render + vision + OCR + Drive-uploader import chain all resolve")
PYEOF
echo "[setup-html-venv] DONE"
