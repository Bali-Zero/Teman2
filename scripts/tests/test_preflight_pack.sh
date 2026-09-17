#!/usr/bin/env bash
# test_preflight_pack.sh — guilt AND innocence for scripts/preflight_pack.sh.
#
# cicatrix-superscar.md #3: "mai guardia senza guilt+innocence". A guard proven
# only to fire is indistinguishable from a guard that always fires; a guard
# proven only to stay quiet is indistinguishable from a guard that does nothing.
# Both arms are proven here against the REAL checker (scripts/check_adversarial_review.py),
# never a stub — a test that stubs the thing under test proves the stub.
#
# Run: bash scripts/tests/test_preflight_pack.sh

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
PASS=0; FAIL=0

ok()   { PASS=$((PASS+1)); echo "  ✅ $1"; }
bad()  { FAIL=$((FAIL+1)); echo "  ❌ $1"; }

sandbox() {
    # A synthetic repo root carrying only the real checker and the file under test.
    local tmp; tmp="$(mktemp -d)"
    mkdir -p "$tmp/scripts/ci" "$tmp/research/operations"
    cp "$ROOT/scripts/check_adversarial_review.py" "$tmp/scripts/"
    cp "$ROOT/scripts/ci/bites_parse.py" "$tmp/scripts/ci/" 2>/dev/null || true
    printf '%s' "$tmp"
}

run_checks() {
    # $1 = sandbox root, stdin = file list. Echoes rc, prints output to $OUT_FILE.
    local root="$1"
    ( PREFLIGHT_PACK_LIB=1 PREFLIGHT_PACK_ROOT="$root" . "$ROOT/scripts/preflight_pack.sh" >/dev/null 2>&1
      preflight_run_checks ) > "$OUT_FILE" 2>&1
    echo $?
}

echo "test_preflight_pack.sh"

# ---------------------------------------------------------------- GUILT
# The exact condition that killed #6664 and #6665: a research report whose
# frontmatter carries no adversarial_review key.
T="$(sandbox)"; OUT_FILE="$(mktemp)"
cat > "$T/research/operations/guilty.md" <<'MD'
---
title: "a machine-written run report"
date: 20260917T000000Z
---
# report
body with no adversarial review at all
MD
RC="$(printf 'research/operations/guilty.md\n' | run_checks "$T")"
if [ "$RC" -ne 0 ]; then ok "GUILT: missing adversarial_review frontmatter REFUSES the push (rc=$RC)"
else bad "GUILT: a report with no adversarial_review frontmatter was allowed through (rc=$RC)"; fi
if grep -q "R1" "$OUT_FILE" && grep -q "PUSH REFUSED" "$OUT_FILE"; then
    ok "GUILT: the refusal names the CI check it would red, and says the push is refused"
else bad "GUILT: refusal message does not name R1 / does not say PUSH REFUSED"; cat "$OUT_FILE"; fi
rm -rf "$T"

# ---------------------------------------------------------------- INNOCENCE 1
# The cure #6666/#6667 actually shipped: same doc, valid frontmatter + section.
T="$(sandbox)"
cat > "$T/research/operations/innocent.md" <<'MD'
---
title: "a machine-written run report"
date: 20260917T000000Z
adversarial_review: codex
---
# report

## Adversarial review

codex read this and refuted two claims; both were cured.
MD
RC="$(printf 'research/operations/innocent.md\n' | run_checks "$T")"
if [ "$RC" -eq 0 ]; then ok "INNOCENCE: valid frontmatter + section is ALLOWED (rc=0)"
else bad "INNOCENCE: a correct report was refused (rc=$RC)"; cat "$OUT_FILE"; fi
rm -rf "$T"

# ---------------------------------------------------------------- INNOCENCE 2
# The documented escape hatch must keep working, or people route around the gate.
T="$(sandbox)"
cat > "$T/research/operations/exempt.md" <<'MD'
---
title: "machine delta, no review possible"
adversarial_review: exempt-machine-generated-delta
---
# delta
MD
RC="$(printf 'research/operations/exempt.md\n' | run_checks "$T")"
if [ "$RC" -eq 0 ]; then ok "INNOCENCE: the exempt- escape hatch is ALLOWED (rc=0)"
else bad "INNOCENCE: exempt- was refused (rc=$RC)"; cat "$OUT_FILE"; fi
rm -rf "$T"

# ---------------------------------------------------------------- SILENCE
# The scoping promise: a push carrying none of the governed files must exit 0
# AND print nothing. If this arm breaks, every push in the repo pays.
T="$(sandbox)"
RC="$(printf 'apps/mouth/src/x.ts\nscripts/foo.py\n' | run_checks "$T")"
if [ "$RC" -eq 0 ]; then ok "SILENCE: an unrelated diff is allowed (rc=0)"
else bad "SILENCE: an unrelated diff was refused (rc=$RC)"; cat "$OUT_FILE"; fi
if [ ! -s "$OUT_FILE" ]; then ok "SILENCE: an unrelated diff prints NOTHING"
else bad "SILENCE: an unrelated diff printed output"; cat "$OUT_FILE"; fi
rm -rf "$T"; rm -f "$OUT_FILE"

echo ""
echo "  $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
