#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  Run the CURRENT fleet verify — origin/main's verify.sh, never a stale copy.
#
#    bash ~/.config/ghostty/verify-latest.sh      # what nuz/v types
#    bash infra/ghostty/verify-latest.sh          # same thing, from the repo
#
#  Why this exists (PENDING-ARMS 2026-08-18, closed 2026-08-19): nuz/v used to
#  type `bash ~/nuzantara/infra/ghostty/verify.sh` — a path that does not exist
#  on a checkout older than PR #4295. M5's main checkout is behind BY POLICY
#  (pulling it races its live worktrees), so on M5 the key typed a dead path.
#  The deeper defect is the same one W106b names: even where the path exists,
#  it runs the CHECKOUT's copy of the guardian, and a behind checkout serves
#  old guardian code however fresh the invocation. The fleet truth is
#  origin/main, so that is what this launcher runs — on every machine.
#
#  Mechanics: best-effort fetch (offline is a natural state, never an error
#  here — but it is SAID, because arbitrating against a stale origin/main ref
#  is the disease this script cures), extract infra/ghostty from origin/main
#  into a temp dir, run THAT verify.sh. verify.sh resolves its source dir from
#  its own location, so its drift check compares ~/.config/ghostty against the
#  extracted origin/main content — the right reference on any checkout.
#
#  This file is itself installed to ~/.config/ghostty/ by install.sh, declared
#  in infra/home-fork/declared-pairs.json, and covered by verify.sh's own
#  drift loop — the launcher does not get to rot unwatched (family #1).
# ═══════════════════════════════════════════════════════════════════════════
set -uo pipefail

REPO="${NUZANTARA_REPO:-$HOME/nuzantara}"

if ! git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1; then
  echo "FAIL  $REPO is not a git repository — cannot reach origin/main" >&2
  echo "      (set NUZANTARA_REPO if the monorepo lives elsewhere)" >&2
  exit 1
fi

if ! git -C "$REPO" fetch origin main --quiet 2>/dev/null; then
  echo "  warn  fetch failed — verifying against the last-known origin/main (offline?)"
fi

TMP="$(mktemp -d)" || { echo "FAIL  mktemp failed" >&2; exit 1; }
trap 'rm -rf "$TMP"' EXIT

# No silent fallback to a checkout copy on failure: running a possibly-stale
# verify.sh under an error banner would reintroduce exactly what this cures.
if ! git -C "$REPO" archive origin/main -- infra/ghostty | tar -x -C "$TMP"; then
  echo "FAIL  could not extract infra/ghostty from origin/main" >&2
  exit 1
fi

bash "$TMP/infra/ghostty/verify.sh"
