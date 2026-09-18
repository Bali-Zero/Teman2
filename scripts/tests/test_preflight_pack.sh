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

# Slice 2 (contract_verify): the preflight owns no check any more, it runs the
# table in scripts/ci/contract_checks.yml through scripts/contract_verify.py.
# The table's universal row (floor-needs-brief) shells out to
# scripts/evidence_pack_lint.py, which imports the repo's own packages — so a
# synthetic root cannot host it. The arms below therefore drive the REAL tree
# with a crafted changed-file list: the fixture files are written under
# research/operations/ with a unique name and removed by the trap, and the
# list handed to the preflight names ONLY them plus paths that need not exist.
STAMP="_preflight_selftest_$$"
FIX_DIR="$ROOT/research/operations"
cleanup() { rm -f "$FIX_DIR/${STAMP}"_*.md; rm -rf "$ROOT/evidence/2026-09/${STAMP}"_*; rm -f "${OUT_FILE:-}"; }
trap cleanup EXIT

run_checks() {
    # stdin = file list. Echoes rc, prints output to $OUT_FILE.
    ( PREFLIGHT_PACK_LIB=1 PREFLIGHT_PACK_ROOT="$ROOT" . "$ROOT/scripts/preflight_pack.sh" >/dev/null 2>&1
      PREFLIGHT_SPAN="" preflight_run_checks ) > "$OUT_FILE" 2>&1
    echo $?
}

echo "test_preflight_pack.sh"

# ---------------------------------------------------------------- GUILT
# The exact condition that killed #6664 and #6665: a research report whose
# frontmatter carries no adversarial_review key.
OUT_FILE="$(mktemp)"
cat > "$FIX_DIR/${STAMP}_guilty.md" <<'MD'
---
title: "a machine-written run report"
date: 20260917T000000Z
---
# report
body with no adversarial review at all
MD
RC="$(printf 'research/operations/%s_guilty.md\n' "$STAMP" | run_checks)"
if [ "$RC" -ne 0 ]; then ok "GUILT: missing adversarial_review frontmatter REFUSES the push (rc=$RC)"
else bad "GUILT: a report with no adversarial_review frontmatter was allowed through (rc=$RC)"; fi
if grep -q "R1" "$OUT_FILE" && grep -q "PUSH REFUSED" "$OUT_FILE"; then
    ok "GUILT: the refusal names the CI check it would red, and says the push is refused"
else bad "GUILT: refusal message does not name R1 / does not say PUSH REFUSED"; cat "$OUT_FILE"; fi
if grep -q "R1 gate — adversarial review present" "$OUT_FILE"; then
    ok "GUILT: the refusal names the REQUIRED CI context by its exact name (from the table, not from bash)"
else bad "GUILT: the exact CI context name is missing — the table is not what ran"; cat "$OUT_FILE"; fi

# ---------------------------------------------------------------- INNOCENCE 1
# The cure #6666/#6667 actually shipped: same doc, valid frontmatter + section.
cat > "$FIX_DIR/${STAMP}_innocent.md" <<'MD'
---
title: "a machine-written run report"
date: 20260917T000000Z
adversarial_review: codex
---
# report

## Adversarial review

codex read this and refuted two claims; both were cured.
MD
RC="$(printf 'research/operations/%s_innocent.md\n' "$STAMP" | run_checks)"
if [ "$RC" -eq 0 ]; then ok "INNOCENCE: valid frontmatter + section is ALLOWED (rc=0)"
else bad "INNOCENCE: a correct report was refused (rc=$RC)"; cat "$OUT_FILE"; fi

# ---------------------------------------------------------------- INNOCENCE 2
# The documented escape hatch must keep working, or people route around the gate.
cat > "$FIX_DIR/${STAMP}_exempt.md" <<'MD'
---
title: "machine delta, no review possible"
adversarial_review: exempt-machine-generated-delta
---
# delta
MD
RC="$(printf 'research/operations/%s_exempt.md\n' "$STAMP" | run_checks)"
if [ "$RC" -eq 0 ]; then ok "INNOCENCE: the exempt- escape hatch is ALLOWED (rc=0)"
else bad "INNOCENCE: exempt- was refused (rc=$RC)"; cat "$OUT_FILE"; fi

# ---------------------------------------------------------------- SILENCE
# The scoping promise: a push carrying none of the governed files must exit 0
# AND print nothing. If this arm breaks, every push in the repo pays.
RC="$(printf 'apps/mouth/src/x.ts\nscripts/foo.py\n' | run_checks)"
if [ "$RC" -eq 0 ]; then ok "SILENCE: an unrelated diff is allowed (rc=0)"
else bad "SILENCE: an unrelated diff was refused (rc=$RC)"; cat "$OUT_FILE"; fi
if [ ! -s "$OUT_FILE" ]; then ok "SILENCE: an unrelated diff prints NOTHING"
else bad "SILENCE: an unrelated diff printed output"; cat "$OUT_FILE"; fi

# ---------------------------------------------------------------- GUILT 2
# The condition that killed #6670: a hot-zone path in the diff (floor 3) with
# no evidence/brief.yml. The path need not exist — the floor is computed from
# the list, exactly as harness-floor.yml computes it from hotzone_changed_files.
RC="$(printf 'apps/backend-rag/backend/db/migrations_v2/999_x.sql\n' | run_checks)"
if [ "$RC" -ne 0 ] && grep -q "Harness floor recompute" "$OUT_FILE" && grep -q "floor is 3" "$OUT_FILE"; then
    ok "GUILT: a floor-3 diff with no brief REFUSES the push and names 'Harness floor recompute'"
else bad "GUILT: floor-3 diff without a brief was allowed / not named (rc=$RC)"; cat "$OUT_FILE"; fi

# ---------------------------------------------------------------- INNOCENCE 3
# Same hot-zone path, but the diff carries its brief: the floor is satisfied
# at this stage (CI then validates the brief itself, out of the preflight's scope).
RC="$(printf 'apps/backend-rag/backend/db/migrations_v2/999_x.sql\nevidence/brief.yml\n' | run_checks)"
if [ "$RC" -eq 0 ]; then ok "INNOCENCE: a floor-3 diff that carries its brief is ALLOWED (rc=0)"
else bad "INNOCENCE: floor-3 diff WITH a brief was refused (rc=$RC)"; cat "$OUT_FILE"; fi

# ---------------------------------------------------------------- INNOCENCE 4
# The false red that PR #6761 pushed through with PREFLIGHT_PACK_SKIP=1: a
# Gear-3 pack whose council journal IS committed beside it. CI stages that
# journal (scripts/ci/stage_council_journal.py); the preflight must too, or
# every honest Gear-3 push is refused by construction. Fixture = the merged
# janitor pack, fed with its own 12-file diff exactly as the push would be.
JANITOR_PACK_DIR="evidence/2026-09/agent-air-m5-infra-mailbox-janitor-ad139989"
JANITOR_FILES="apps/organism/organism/organs_registry.yaml
docs/connectome/edges/launchd-m5-mini.yaml
docs/connectome/edges/launchd-pro.yaml
$JANITOR_PACK_DIR/brief.yml
$JANITOR_PACK_DIR/journal.jsonl
$JANITOR_PACK_DIR/pack.yml
infra/launchagents/com.nuzantara.mailbox-janitor.daily.plist
infra/launchagents/install_mailbox_janitor.sh
scripts/mailbox_janitor.py
scripts/mailbox_janitor_cron.sh
scripts/tests/test_mailbox_janitor.py
scripts/tests/test_mailbox_janitor_cron.py"
if [ -f "$ROOT/$JANITOR_PACK_DIR/journal.jsonl" ]; then
    RC="$(printf '%s\n' "$JANITOR_FILES" | run_checks)"
    if [ "$RC" -eq 0 ]; then ok "INNOCENCE: a Gear-3 pack with its council journal committed beside it is ALLOWED (rc=0)"
    else bad "INNOCENCE: a Gear-3 pack WITH its journal was refused — the journal is not being staged (rc=$RC)"; cat "$OUT_FILE"; fi
    # Span mode takes CI's own stager on the pushed sha; only provable where that sha exists.
    JANITOR_SHA="e0722cbb243a60c3a37780311fd90ec794e9ff91"
    if git -C "$ROOT" cat-file -e "$JANITOR_SHA^{commit}" 2>/dev/null && git -C "$ROOT" cat-file -e "$JANITOR_SHA^^{commit}" 2>/dev/null; then
        if CONTRACT_VERIFY_ROOT="$ROOT" python3 "$ROOT/scripts/contract_verify.py" --local --span "$JANITOR_SHA^" "$JANITOR_SHA" > "$OUT_FILE" 2>&1; then
            ok "INNOCENCE: the same pack over a base..head span is ALLOWED (journal staged from the head sha)"
        else bad "INNOCENCE: span mode refused the pack with its journal"; cat "$OUT_FILE"; fi
    else
        echo "  ⏭  span arm skipped: $JANITOR_SHA not in this clone"
    fi
else
    echo "  ⏭  journal arms skipped: $JANITOR_PACK_DIR/journal.jsonl not in this tree"
fi

# ---------------------------------------------------------------- GUILT 3
# Staging must not fail OPEN: the same pack declaring a journal that does not
# exist must still red on council_run, and say the journal was not staged.
GUILT_DIR="evidence/2026-09/${STAMP}_guilt"
if [ -f "$ROOT/$JANITOR_PACK_DIR/pack.yml" ]; then
    mkdir -p "$ROOT/$GUILT_DIR"
    sed 's/^council_run:.*/council_run: missing.jsonl/' "$ROOT/$JANITOR_PACK_DIR/pack.yml" > "$ROOT/$GUILT_DIR/pack.yml"
    cp "$ROOT/$JANITOR_PACK_DIR/brief.yml" "$ROOT/$GUILT_DIR/brief.yml"
    RC="$(printf '%s\n' "$JANITOR_FILES" | grep -v "^$JANITOR_PACK_DIR/" | { cat; printf '%s/pack.yml\n%s/brief.yml\n' "$GUILT_DIR" "$GUILT_DIR"; } | run_checks)"
    if [ "$RC" -ne 0 ] && grep -q "council_run" "$OUT_FILE" && grep -q "staging nothing" "$OUT_FILE"; then
        ok "GUILT: a Gear-3 pack whose declared journal is missing REFUSES the push and says nothing was staged (rc=$RC)"
    else bad "GUILT: a pack with a missing journal was allowed / did not explain the staging (rc=$RC)"; cat "$OUT_FILE"; fi
fi

# ---------------------------------------------------------------- GUILT 4
# CI parity for `..`: a prefix the journal path cancels that EXISTS but is not
# a directory (here a symlink) makes lexical and resolved paths name different
# files. CI stages nothing there and lets R9 judge; the working-tree branch
# must do the same instead of staging the lexical neighbour and passing.
GUILT2_DIR="evidence/2026-09/${STAMP}_guilt2"
if [ -f "$ROOT/$JANITOR_PACK_DIR/journal.jsonl" ]; then
    mkdir -p "$ROOT/$GUILT2_DIR"
    ln -s "$ROOT/$JANITOR_PACK_DIR" "$ROOT/$GUILT2_DIR/link"
    sed 's|^council_run:.*|council_run: link/../journal.jsonl|' "$ROOT/$JANITOR_PACK_DIR/pack.yml" > "$ROOT/$GUILT2_DIR/pack.yml"
    cp "$ROOT/$JANITOR_PACK_DIR/brief.yml" "$ROOT/$JANITOR_PACK_DIR/journal.jsonl" "$ROOT/$GUILT2_DIR/"
    RC="$(printf '%s\n' "$JANITOR_FILES" | grep -v "^$JANITOR_PACK_DIR/" | { cat; printf '%s/pack.yml\n%s/brief.yml\n' "$GUILT2_DIR" "$GUILT2_DIR"; } | run_checks)"
    if [ "$RC" -ne 0 ] && grep -q "cancels 'link'" "$OUT_FILE" && grep -q "staging nothing" "$OUT_FILE"; then
        ok "GUILT: a journal path whose '..' crosses a symlink is NOT staged from the working tree (rc=$RC)"
    else bad "GUILT: a '..'-through-symlink journal path was staged / not explained (rc=$RC)"; cat "$OUT_FILE"; fi
fi

echo ""
echo "  $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
