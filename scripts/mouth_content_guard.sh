#!/bin/bash
# scripts/mouth_content_guard.sh — run the two mouth content guards against a worktree.
#
# The hourly translation PRs (scripts/translate-articles-cron-wrapper.sh) were red
# on both sides: the LLM translation rewrote lines that e33-income-basis-copy.test.ts
# and secondhome-article-claims.test.ts pin. The guards are right and the content is
# wrong, so the producer asks them BEFORE it promotes anything. This script never
# edits a guard, a baseline or an article; it only runs them.
#
# usage: mouth_content_guard.sh [--base] <worktree>
#   exit 0  guards green
#   exit 1  guards red                              (without --base)
#   exit 2  guards red on the BASE tree (--base)    main is red, not the producer's to fix
#   exit 3  tooling missing (vitest, typescript, the guard files) — fail closed, visible
#   exit 64 usage
# MOUTH_GUARD_VITEST overrides the vitest binary (default: <repo>/node_modules/.bin/vitest,
# resolved from this script's own checkout). typescript is resolved next to it, because
# secondhome-article-claims.test.ts imports it. Never `npm install` to cure a missing one.
set -uo pipefail

BASE=0
if [ "${1:-}" = "--base" ]; then BASE=1; shift; fi
WT="${1:-}"
[ -n "$WT" ] && [ -d "$WT/apps/mouth" ] || { echo "usage: $0 [--base] <worktree>" >&2; exit 64; }

GUARDS=(src/lib/e33-income-basis-copy.test.ts src/i18n/secondhome-article-claims.test.ts)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VITEST="${MOUTH_GUARD_VITEST:-$SCRIPT_DIR/../node_modules/.bin/vitest}"

missing() { echo "mouth_content_guard: $1 — cannot judge, promote nothing" >&2; exit 3; }
[ -x "$VITEST" ] || missing "vitest not executable at $VITEST"
[ -e "$(dirname "$VITEST")/../typescript/package.json" ] || missing "typescript not resolvable next to $VITEST"
for g in "${GUARDS[@]}"; do
  [ -f "$WT/apps/mouth/$g" ] || missing "guard file $g absent from $WT"
done

CFG_DIR="$(mktemp -d)" || missing "no temp dir"
trap 'rm -rf "$CFG_DIR"' EXIT
# the repo vitest.config.ts needs @vitejs/plugin-react, absent from the shared root node_modules;
# the claim ratchet scans every article and ran into the 5 s default under host load (a false red)
echo 'export default { test: { include: ["src/**/*.test.ts"], testTimeout: 60000 } };' >"$CFG_DIR/vitest.guard.config.mjs"

(cd "$WT/apps/mouth" && "$VITEST" run --root . --config "$CFG_DIR/vitest.guard.config.mjs" "${GUARDS[@]}") >&2
rc=$?
[ "$rc" -eq 0 ] && exit 0
[ "$BASE" -eq 1 ] && exit 2
exit 1
