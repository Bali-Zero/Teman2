#!/usr/bin/env bash
# test_precommit_ruff_absent_gate.sh — guilt + innocence for the `.husky/pre-commit`
# Python-lint gate (RUFF_LINT_GATE block).
#
# THE DEFECT (PENDING-ARMS 2026-08-31): with no venv on PATH,
# `xargs ruff check 2>/dev/null` exits 127 ("ruff: No such file or directory"
# on stderr, swallowed by `2>/dev/null`), and the gate reported that as
# "❌ Python linting failed on staged files" — a CANNOT-VERIFY read as a
# verdict about the diff. The Golden-Rule-#8 gate a few lines above already
# guards this correctly (`if ! command -v ruff`); the cure never travelled to
# this sibling call site. This test pins both halves: ruff-absent must be
# named as such, and a real lint error must still block when ruff IS present.
#
# The block under test is EXTRACTED VERBATIM from the live hook between its
# RUFF_LINT_GATE_BEGIN/END markers, so this test breaks the moment the hook
# drifts from what is pinned here, and it runs under `sh -e` — the shell
# husky uses (`.husky/_/h`: `sh -e "$s"`). Same discipline as
# test_precommit_print_gate.sh.
#
# Run:  bash scripts/tests/test_precommit_ruff_absent_gate.sh

set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HOOK="$REPO_ROOT/.husky/pre-commit"
PASS=0
FAIL=0

ok()  { PASS=$((PASS + 1)); printf '  ✅ %s\n' "$1"; }
bad() { FAIL=$((FAIL + 1)); printf '  ❌ %s\n' "$1"; }

BLOCK="$(sed -n '/RUFF_LINT_GATE_BEGIN/,/RUFF_LINT_GATE_END/p' "$HOOK")"
if [ -z "$BLOCK" ]; then
    echo "❌ could not extract the RUFF_LINT_GATE block from $HOOK"
    echo "   The markers are load-bearing: without them this test silently tests nothing."
    exit 1
fi
case "$BLOCK" in
    *"command -v ruff"*) : ;;
    *) echo "❌ extracted block lost its ruff-absence guard"; exit 1 ;;
esac

if ! command -v ruff >/dev/null 2>&1; then
    echo "❌ ruff is not on PATH — this corpus cannot distinguish a working gate"
    echo "   from a broken one without it. Refusing to report a pass (W108)."
    exit 1
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

run_gate() {
    # $1 = STAGED_FILES-relative PY_FILES list, $2 = PATH override (empty = inherit)
    (
        cd "$WORK/tree" || exit 99
        RUN_PATH="${2:-$PATH}"
        out=$(PATH="$RUN_PATH" sh -e -c "STAGED_FILES='$1'
$BLOCK" 2>&1) && rc=0 || rc=$?
        printf '%s\n' "$out"
        printf 'RC=%s\n' "$rc"
    )
}

rm -rf "$WORK/tree"
mkdir -p "$WORK/tree/apps/backend-rag/backend/app"

echo "── pre-commit ruff-absent gate corpus ──────────────────────────────────"

# ── Case 1 (CANNOT-VERIFY): ruff missing must not read as a lint failure ─────
cat > "$WORK/tree/apps/backend-rag/backend/app/clean.py" <<'EOF'
def handler() -> None:
    return None
EOF
NORUFF_BIN="$WORK/noruff-bin"
rm -rf "$NORUFF_BIN"; mkdir -p "$NORUFF_BIN"
for util in sh grep sed xargs; do
    src="$(command -v "$util")" || { bad "CANNOT-VERIFY: $util not found, cannot build the probe PATH"; src=""; }
    [ -n "$src" ] && ln -sf "$src" "$NORUFF_BIN/$util"
done
if PATH="$NORUFF_BIN" command -v ruff >/dev/null 2>&1; then
    bad "CANNOT-VERIFY: ruff leaked into the probe PATH, this case cannot run honestly"
else
    OUT="$(run_gate "apps/backend-rag/backend/app/clean.py" "$NORUFF_BIN")"
    case "$OUT" in
        *"cannot verify Python linting"*) ok "CANNOT-VERIFY: missing ruff is named as such" ;;
        *"Python linting failed"*) bad "CANNOT-VERIFY: missing ruff was reported as a lint failure -> $OUT" ;;
        *) bad "CANNOT-VERIFY: unexpected gate output -> $OUT" ;;
    esac
    case "$OUT" in
        *"RC=1"*) ok "CANNOT-VERIFY: the gate itself exits 1 rather than passing blind" ;;
        *) bad "CANNOT-VERIFY: expected the gate's own RC=1 -> $OUT" ;;
    esac
fi

# ── Case 2 (GUILT): with ruff present, a real lint error still blocks ────────
cat > "$WORK/tree/apps/backend-rag/backend/app/leaky.py" <<'EOF'
import os
EOF
OUT="$(run_gate "apps/backend-rag/backend/app/leaky.py")"
case "$OUT" in
    *"Python linting failed on staged files"*) ok "GUILT: a real ruff violation (unused import) still blocks" ;;
    *) bad "GUILT: a real ruff violation slipped through -> $OUT" ;;
esac
case "$OUT" in
    *"RC=1"*) ok "GUILT: the gate exits non-zero on a real violation" ;;
    *) bad "GUILT: gate did not exit 1 on a real violation -> $OUT" ;;
esac

# ── Case 3 (INNOCENCE): with ruff present, a clean file passes ───────────────
OUT="$(run_gate "apps/backend-rag/backend/app/clean.py")"
case "$OUT" in
    *"Python linting failed"*) bad "INNOCENCE: a clean file was blocked -> $OUT" ;;
    *"RC=0"*) ok "INNOCENCE: a clean file passes with ruff present" ;;
    *) bad "INNOCENCE: unexpected gate output -> $OUT" ;;
esac

echo "────────────────────────────────────────────────────────────────────────"
echo "  passed: $PASS   failed: $FAIL"
[ "$FAIL" -eq 0 ] || exit 1
