#!/bin/zsh
# check-fleet.sh — is the KBLI Navigator fleet serving ONE dataset? (superscar #1 + #2 receptor)
#
# Compares the sha256 of KBLI_2025_FINAL_CLEAN.json across every surface of the Navigator:
#   1. canonical              origin/main:data/source_documents/KBLI_2025_FINAL_CLEAN.json
#                              (the FLEET's source of truth — never a local checkout's HEAD)
#   2. this repo Resources/  (what the next build would ship if canonical were missing)
#   3. deployed bundle       ~/Desktop/"KBLI Navigator - INTERNAL.app" on THIS machine + pro + mini (ssh)
#
# W106b (2026-08-09): a LOCAL checkout is a proxy for "canonical", and it lies whenever it
# is behind (M5's main checkout is ~235 commits behind BY DESIGN — never pulled, work happens
# in worktrees) or ahead (uncommitted local edits). This script used to hash a resolved repo's
# checked-out file directly, so on M5 it graded the whole fleet against a stale snapshot and
# its own printed remedy ("rebuild+reinstall") would have REGRESSED three aligned machines.
# Default now: resolve any local git checkout as a remote-anchor only (doesn't matter that
# ITS working tree is stale), `git fetch` origin/main refs-only, then hash the CONTENT at
# origin/main via `git show` — never the checkout's own files. If the fetch fails (offline is
# a natural state, not a fault — Law 6), the script prints CANNOT-VERIFY and exits 3; it never
# reports drift it could not actually measure. `--local-canonical` restores the pre-W106b
# behavior (hash the resolved repo's own working-tree file, no network) for offline dev only.
#
# Read-only: probes and reports, never mutates (W81 doctrine: segnalatore, non attuatore).
# Exit 0 = every reachable copy matches canonical. Exit 1 = drift somewhere reachable.
# Exit 2 = canonical unresolvable (no repo found, or path missing at origin/main / on disk).
# Exit 3 = CANNOT-VERIFY (git fetch failed, e.g. offline) — distinct from drift by design.
# ssh reachability is tested independently of the hash comparison, so a real DRIFT is never
# mislabeled "unreachable" and a truly unreachable host is never mislabeled DRIFT (both were
# collapsed into one static string before this fix).
#
# 2026-08-09 app split: the fleet always runs the INTERNAL variant (BKPM is a separate,
# on-demand build, never fleet-installed — see build.sh --variant). APP_NAME below tracks
# install-3mac.sh's new target name; until that script's NEXT run (a later phase, not this
# one), the fleet's actually-installed copies still carry the OLD "KBLI Navigator" name, so
# this check will correctly report them as unreachable/missing until the swap happens.
set -euo pipefail

ROOT="${0:A:h:h}"
APP_NAME="KBLI Navigator - INTERNAL"
DATASET_REL="Contents/Resources/KBLI_2025_FINAL_CLEAN.json"
KBLI_REL="source_documents/KBLI_2025_FINAL_CLEAN.json"      # filesystem path (symlink-transparent, --local-canonical only)
KBLI_GIT_REL="data/source_documents/KBLI_2025_FINAL_CLEAN.json"  # git-tracked real path — `source_documents` is a symlink and `git show` does not follow it

LOCAL_CANONICAL=0
if [[ "${1:-}" == "--local-canonical" ]]; then
  LOCAL_CANONICAL=1
  echo "⚠︎ --local-canonical: offline dev only — hashing a checked-out file, NOT origin/main. Do not use this mode's verdict to decide whether the fleet needs a rebuild."
fi

# repo resolution — identical ladder to build.sh (monorepo root → env override → sibling → ~/nuzantara). Any
# git checkout works here (worktree or full clone, however stale its own HEAD is) because
# the default path below only uses it to fetch + read origin/main by content.
REPO=""
for repo in "$ROOT/../.." "${NUZANTARA_REPO:-}" "$ROOT/../nuzantara" "$HOME/nuzantara"; do
  if [[ -n "$repo" ]] && git -C "$repo" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    REPO="$(cd "$repo" && git rev-parse --show-toplevel)"
    break
  fi
done
if [[ -z "$REPO" ]]; then
  echo "✗ canonical not found (set NUZANTARA_REPO or place the repo as ../nuzantara)"; exit 2
fi

if (( LOCAL_CANONICAL )); then
  CANON="$REPO/$KBLI_REL"
  if [[ ! -f "$CANON" || -L "$CANON" ]]; then
    echo "✗ canonical not found at $CANON (--local-canonical, offline dev only)"; exit 2
  fi
  CHASH="$(shasum -a 256 "$CANON" | awk '{print $1}')"
  echo "canonical  ${CHASH:0:12}  $CANON  (--local-canonical: this checkout's HEAD, NOT origin/main)"
else
  FETCH_ERR="/tmp/check-fleet-fetch-err.$$"
  if ! git -C "$REPO" fetch --quiet origin main 2>"$FETCH_ERR"; then
    echo "⚠︎ CANNOT-VERIFY: git fetch origin main failed in $REPO"
    echo "  offline is a natural state (Law 6), not a drift finding — see $FETCH_ERR. Retry when connected, or pass --local-canonical for offline dev."
    exit 3
  fi
  rm -f "$FETCH_ERR"
  CHASH=""
  if ! CHASH="$(git -C "$REPO" show "origin/main:$KBLI_GIT_REL" 2>/dev/null | shasum -a 256 | awk '{print $1}')" || [[ -z "$CHASH" ]]; then
    echo "✗ canonical not found at origin/main:$KBLI_GIT_REL (repo: $REPO)"; exit 2
  fi
  echo "canonical  ${CHASH:0:12}  origin/main:$KBLI_GIT_REL  (repo: $REPO)"
fi
DRIFT=0

verdict() {  # $1 = hash-or-empty, $2 = label, $3 = status note (drift context, or full sentence when hash is empty)
  if [[ -z "$1" ]]; then
    echo "⚠︎ $2: $3"
  elif [[ "$1" == "$CHASH" ]]; then
    echo "✓ $2  ${1:0:12}  aligned"
  else
    echo "✗ $2  ${1:0:12}  DRIFT ($3)"
    DRIFT=1
  fi
}

RH="$(shasum -a 256 "$ROOT/Resources/KBLI_2025_FINAL_CLEAN.json" 2>/dev/null | awk '{print $1}')"
verdict "${RH:-}" "app-repo Resources/" "$ROOT/Resources — next build refreshes this from canonical"

LH="$(shasum -a 256 "$HOME/Desktop/$APP_NAME.app/$DATASET_REL" 2>/dev/null | awk '{print $1}')"
verdict "${LH:-}" "$(hostname) deployed  " "~/Desktop/$APP_NAME.app"

for T in pro mini; do
  SSH_RC=0
  SSH_OUT="$(ssh -o ConnectTimeout=8 -o BatchMode=yes "$T" "shasum -a 256 ~/Desktop/'$APP_NAME.app'/$DATASET_REL" 2>/dev/null)" || SSH_RC=$?
  TH="${SSH_OUT%% *}"
  if [[ $SSH_RC -eq 255 ]]; then
    verdict "" "$T deployed      " "ssh $T unreachable, re-check when back"
  elif [[ -z "$TH" ]]; then
    verdict "" "$T deployed      " "ssh $T reached, app/dataset missing at $DATASET_REL"
  else
    verdict "$TH" "$T deployed      " "ssh $T reached"
  fi
done

# ── the editorial overlay (2026-08-03) ────────────────────────────────────────────────
# Until today this script compared ONE file — the machine dataset — and printed "fleet
# aligned with canonical" over three laptops whose EDITORIAL prose was months stale and
# materially wrong (Umrah at 100% where the law says 0%; a withdrawn UMKM-reservation
# argument closing hostels, villas and massage parlours to PT PMA). Checking the file
# that cannot lie in prose, and calling that the fleet, is how a guard delivers good news
# about a bad world.
OVERLAY_FILES=(kbli-overlay.json kbli-reason-i18n.json kbli-balicontext-i18n-id.json)
if (( LOCAL_CANONICAL )); then
  OVERLAY_CANON_DIR="$REPO/data/kbli-app-overlay"
else
  OVERLAY_CANON_DIR=""  # resolved per-file below via git show origin/main, no working-tree dir
fi
for f in "${OVERLAY_FILES[@]}"; do
  if (( LOCAL_CANONICAL )); then
    if [[ ! -f "$OVERLAY_CANON_DIR/$f" ]]; then
      echo "⚠︎ overlay $f: no canonical copy at $OVERLAY_CANON_DIR — cannot verify (--local-canonical)"
      continue
    fi
    OC="$(shasum -a 256 "$OVERLAY_CANON_DIR/$f" | awk '{print $1}')"
  else
    OC=""
    if ! OC="$(git -C "$REPO" show "origin/main:data/kbli-app-overlay/$f" 2>/dev/null | shasum -a 256 | awk '{print $1}')" || [[ -z "$OC" ]]; then
      echo "⚠︎ overlay $f: no canonical copy at origin/main:data/kbli-app-overlay/$f — cannot verify"
      continue
    fi
  fi
  RO="$(shasum -a 256 "$ROOT/Resources/$f" 2>/dev/null | awk '{print $1}')"
  [[ "${RO:-}" == "$OC" ]] || { echo "✗ overlay $f app-repo  DRIFT (${RO:0:12} vs ${OC:0:12})"; DRIFT=1; }
  LO="$(shasum -a 256 "$HOME/Desktop/$APP_NAME.app/Contents/Resources/$f" 2>/dev/null | awk '{print $1}')"
  [[ "${LO:-}" == "$OC" ]] || { echo "✗ overlay $f $(hostname)  DRIFT (${LO:0:12} vs ${OC:0:12})"; DRIFT=1; }
  for T in pro mini; do
    TO_RC=0
    TO_OUT="$(ssh -o ConnectTimeout=8 -o BatchMode=yes "$T" "shasum -a 256 ~/Desktop/'$APP_NAME.app'/Contents/Resources/$f" 2>/dev/null)" || TO_RC=$?
    TO="${TO_OUT%% *}"
    if [[ $TO_RC -eq 255 ]]; then
      echo "⚠︎ overlay $f $T: unreachable"
    elif [[ -z "${TO:-}" ]]; then
      echo "⚠︎ overlay $f $T: reached, missing"
    elif [[ "$TO" != "$OC" ]]; then
      echo "✗ overlay $f $T  DRIFT (${TO:0:12} vs ${OC:0:12})"; DRIFT=1
    fi
  done
done
echo "✓ overlay: ${#OVERLAY_FILES[@]} files compared across app-repo + 3 machines"

if (( DRIFT )); then
  echo "→ fleet NOT aligned: run deploy/install-3mac.sh (build once, deploy+verify all 3)."
  exit 1
fi
echo "→ fleet aligned with canonical."
