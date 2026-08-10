#!/usr/bin/env bash
# sync_kbli_dataset.sh — propagate the ONE canonical KBLI dataset to every consumer copy.
#
# WHY (superscar #1 HOME-fork + #9 schema-drift): the KBLI_2025_FINAL_CLEAN.json
# dataset existed in 6 physical copies + 1 broken symlink, drifting silently. The
# RAG chatbot read a stale/poor copy (86101=TERBUKA/100, no OSS source, no l4_bali)
# while the web + native app served the corrected rich OSS-base. This script makes
# the propagation a single deterministic command, and `check-kbli-dataset-sync.yml`
# fails CI if any copy diverges from canonical.
#
# CANONICAL (source of truth):
#   source_documents/KBLI_2025_FINAL_CLEAN.json   (repo ROOT, git-tracked)
# This is the path the RAG reads at runtime (backend/services/kbli_eye.py default
# db_path="source_documents/..." resolved from repo root, and reindex script's
# parents[4]/source_documents/...). The 30MB rich OSS-base (1559 codes, l4_bali +
# _l1_source/_l2_source OSS_RBA_2025 on every record).
#
# CONSUMERS kept in sync (physical files, NOT symlinks — Vercel/Fly build contexts
# do not reliably follow a symlink that exits the project/app dir, so we copy):
#   data/source_documents/KBLI_2025_FINAL_CLEAN.json    (tracked, secondary fallback)
#   apps/mouth/data/KBLI_2025_FINAL_CLEAN.json          (tracked, balizero.com/kbli prod)
#   apps/backend-rag/backend/data/KBLI_2025_FINAL_CLEAN.json  (gitignored, was MARCIA zombie)
#   apps/kbli-navigator/data/kbli-2025.json             (tracked, knowledge.balizero.com —
#     DIFFERENT basename than canonical, same {metadata,data:[...]} shape/records; was
#     `git rm --cached`'d in ab1d5b02c0 (2026-03-28) and quietly rotted to that snapshot
#     ever since — no build step ever regenerated it. Re-tracked 2026-07-19, scar #1.)
#
# REPAIRED:
#   apps/backend-rag/source_documents/KBLI_2025_FINAL_CLEAN.json
#     — was a BROKEN symlink to /Users/nuzantara/... (a dead Pro-user HOME path on
#       M5/balizero). Replaced with a physical copy of canonical.
#
# OUT OF SCOPE (handled by the native-app deploy script, not the repo):
#   ~/Desktop/logo/kbli-navigator-app/Resources/KBLI_2025_FINAL_CLEAN.json
#     — the standalone macOS app (OUTSIDE this repo, NOT apps/kbli-navigator/ above).
#       deploy/install-3mac.sh copies it from the app's own Resources/. If you change
#       canonical, re-run the app build+deploy to refresh it.
#
# Usage:
#   scripts/sync_kbli_dataset.sh           # propagate canonical → all consumers
#   scripts/sync_kbli_dataset.sh --check   # verify only, non-zero exit on drift (CI mode)
set -euo pipefail

# Resolve repo root from this script's location (works from any cwd / any worktree).
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

CANONICAL="source_documents/KBLI_2025_FINAL_CLEAN.json"

# Consumer copies that MUST be byte-identical to canonical.
CONSUMERS=(
  "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
  "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
  "apps/backend-rag/backend/data/KBLI_2025_FINAL_CLEAN.json"
  "apps/backend-rag/source_documents/KBLI_2025_FINAL_CLEAN.json"
  "apps/kbli-navigator/data/kbli-2025.json"
)

MODE="${1:-sync}"

if [[ ! -f "$CANONICAL" ]]; then
  echo "::error::canonical KBLI dataset missing at $CANONICAL — cannot sync." >&2
  exit 2
fi

# A symlink in canonical's place would defeat the SoT (it must be a real file).
if [[ -L "$CANONICAL" ]]; then
  echo "::error::$CANONICAL is a SYMLINK — canonical must be a physical file (HOME-fork #1)." >&2
  exit 2
fi

drift=0
for dst in "${CONSUMERS[@]}"; do
  if [[ "$MODE" == "--check" ]]; then
    if [[ -L "$dst" ]]; then
      echo "DRIFT: $dst is a SYMLINK (expected a physical copy of canonical)."
      drift=1
    elif [[ ! -f "$dst" ]]; then
      # A gitignored consumer (RAG copies) may legitimately be absent on a fresh
      # checkout/CI runner — it is materialised by this script at build time. Only
      # the git-TRACKED consumers must always be present & identical.
      if git ls-files --error-unmatch "$dst" >/dev/null 2>&1; then
        echo "DRIFT: tracked consumer $dst is MISSING."
        drift=1
      else
        echo "skip (gitignored, absent on this runner): $dst"
      fi
    elif ! cmp -s "$CANONICAL" "$dst"; then
      echo "DRIFT: $dst differs from canonical $CANONICAL — run scripts/sync_kbli_dataset.sh."
      drift=1
    else
      echo "ok: $dst == canonical"
    fi
  else
    mkdir -p "$(dirname -- "$dst")"
    # Replace a stale symlink with a real file.
    [[ -L "$dst" ]] && rm -f "$dst"
    if cmp -s "$CANONICAL" "$dst" 2>/dev/null; then
      echo "unchanged: $dst"
    else
      cp -f "$CANONICAL" "$dst"
      echo "synced: $dst"
    fi
  fi
done

if [[ "$MODE" == "--check" ]]; then
  if [[ "$drift" -ne 0 ]]; then
    echo "::error::KBLI dataset copies drifted from canonical ($CANONICAL). Run scripts/sync_kbli_dataset.sh and commit." >&2
    exit 1
  fi
  echo "All KBLI dataset consumers are in sync with canonical."
fi

# ── native-app fleet notice (local only — never CI, never --check) ─────────────────
# The macOS KBLI Navigator (~/Desktop/logo/kbli-navigator-app, OUTSIDE this repo) ships its
# own copy of the dataset; its build refreshes from canonical, but only a deploy pushes
# it to the 3-Mac fleet + the team zip. This block makes the drift VISIBLE at exactly
# the moment canonical changes (this script is the mandatory step after any change),
# instead of relying on someone remembering (superscar #2: costruito ≠ armato).
# 2026-08-09: the old default ($HOME/Desktop/kbli-navigator-app) was DEAD -- the repo
# actually lives at $HOME/Desktop/logo/kbli-navigator-app, so this notice self-skipped
# on M5 silently (an absent app_repo is treated as "nothing to check here", the correct
# behavior for Pro/Mini/CI -- but wrong when the repo is simply at a different path).
# APP_BUNDLE_DIR now names the app-split's INTERNAL variant (the only one the fleet
# ever installs -- see kbli-navigator-app/build.sh --variant). TRANSITION: the fleet's
# actually-installed copies still carry the OLD "KBLI Navigator.app" name until the
# NEXT run of install-3mac.sh (a separate, later step) -- until then this notice will
# correctly report "no .app on <host> to check" rather than silently comparing against
# a path nothing writes to anymore.
APP_REPO="${KBLI_APP_REPO:-$HOME/Desktop/logo/kbli-navigator-app}"
APP_BUNDLE_DIR="${KBLI_APP_BUNDLE_DIR:-$HOME/Desktop/KBLI Navigator - INTERNAL.app}"
if [[ "$MODE" == "sync" && -z "${CI:-}" ]]; then
  # The verdict itself lives in scripts/lib/kbli_fleet_notice.sh so it can be pointed at a
  # fake world and tested (guilt AND innocence) — inline, behind $HOME and `-z $CI`, it was
  # unreachable by any test, which is how it went eight days telling the reassuring half of
  # the truth. `[ -f ] &&` and NOT `source … || true`: under errexit a failed `source` is a
  # special builtin and EXITS, the `||` never runs (W108).
  FLEET_NOTICE="$(dirname "${BASH_SOURCE[0]}")/lib/kbli_fleet_notice.sh"
  if [[ -f "$FLEET_NOTICE" ]]; then
    # shellcheck source=scripts/lib/kbli_fleet_notice.sh
    . "$FLEET_NOTICE"
    kbli_fleet_notice "$CANONICAL" "$APP_REPO" "$APP_BUNDLE_DIR"
  else
    echo "⚠︎ $FLEET_NOTICE missing — the native app fleet was NOT checked (absence is not alignment)."
  fi
fi
