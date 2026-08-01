#!/usr/bin/env bash
# test_precommit_print_gate.sh — guilt + innocence for the `.husky/pre-commit`
# Golden Rule #8 gate (no print() in backend code).
#
# THE DEFECT (measured 2026-08-01): the gate re-implemented ruff's T201 with a
# text scan. A text scan cannot see `# noqa: T201` — which ruff honors, and which
# `sentry_config.py::_before_send` genuinely needs, because a logger call there
# re-enters Sentry's LoggingIntegration — and it cannot tell a call from the word
# "print(" sitting in a comment. Across the gate's whole scope it flagged three
# files and ALL THREE were false positives: two were comments, one of which
# literally reads "(no print() — logger.info would ...)". Zero true positives.
# Its only live effect was to hard-block any commit touching those files, which
# is how it was found: it blocked the Sentry PII-redaction fix.
#
# The cure is not a better regex, it is deleting the second implementation:
# Golden Rule #8 IS T201, ruff already runs on the same staged files a few steps
# further down this very hook, so the gate now calls ruff. One rule, one
# implementation, and the suppression mechanism is the standard reviewable one.
#
# The block under test is EXTRACTED VERBATIM from the live hook between its
# PRINT_GATE_BEGIN/END markers, so this test breaks the moment the hook drifts
# from what is pinned here, and it runs under `sh -e` — the shell husky uses
# (`.husky/_/h`: `sh -e "$s"`) — so an errexit-sensitive construct fails here
# exactly as it would in production (W101). Same discipline as
# test_pii_gate_merge_scope.sh.
#
# Run:  bash scripts/tests/test_precommit_print_gate.sh

set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HOOK="$REPO_ROOT/.husky/pre-commit"
PASS=0
FAIL=0

ok()  { PASS=$((PASS + 1)); printf '  ✅ %s\n' "$1"; }
bad() { FAIL=$((FAIL + 1)); printf '  ❌ %s\n' "$1"; }

BLOCK="$(sed -n '/PRINT_GATE_BEGIN/,/PRINT_GATE_END/p' "$HOOK")"
if [ -z "$BLOCK" ]; then
    echo "❌ could not extract the PRINT_GATE block from $HOOK"
    echo "   The markers are load-bearing: without them this test silently tests nothing."
    exit 1
fi
# Guard against the marker surviving while the logic behind it is gutted — the
# whole point of the cure is that the rule is executed by ruff, not re-typed.
case "$BLOCK" in
    *"ruff check"*) : ;;
    *) echo "❌ extracted block no longer calls ruff — the second implementation is back"; exit 1 ;;
esac

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

BACKEND_DIR="apps/backend-rag/backend/app/routers"

# Run the extracted gate over $1 (a newline-separated PY_FILES list) inside a
# throwaway tree, and echo its output. Exit code is appended as a final RC= line
# so a caller reading stdout can never mistake "the gate said nothing" for
# "the gate passed" (W97: never read an exit code through a pipe).
run_gate() {
    (
        cd "$WORK/tree" || exit 99
        out=$(sh -e -c "PY_FILES='$1'
$BLOCK" 2>&1) && rc=0 || rc=$?
        printf '%s\n' "$out"
        printf 'RC=%s\n' "$rc"
    )
}

fresh_tree() {
    rm -rf "$WORK/tree"
    mkdir -p "$WORK/tree/$BACKEND_DIR" "$WORK/tree/scripts"
}

echo "── pre-commit print() gate corpus ──────────────────────────────────────"

if ! command -v ruff >/dev/null 2>&1; then
    echo "❌ ruff is not on PATH — this corpus cannot distinguish a working gate"
    echo "   from a broken one without it. Refusing to report a pass (W108: a"
    echo "   test environment that cannot reproduce red measures its own poverty)."
    exit 1
fi

# ── Case 1 (GUILT): a plain new print() in backend code is still caught ──────
fresh_tree
cat > "$WORK/tree/$BACKEND_DIR/leaky.py" <<'EOF'
def handler(client_id: str) -> None:
    print(f"processing {client_id}")
EOF
OUT="$(run_gate "$BACKEND_DIR/leaky.py")"
case "$OUT" in
    *"Found print() statements in backend code"*) ok "GUILT: a bare print() in backend code is blocked" ;;
    *) bad "GUILT: a bare print() slipped through -> $OUT" ;;
esac
case "$OUT" in
    *"RC=1"*) ok "GUILT: the gate exits non-zero (the hook actually aborts)" ;;
    *) bad "GUILT: gate did not exit 1 -> $OUT" ;;
esac

# ── Case 2 (INNOCENCE): the noqa'd print — the exact line that blocked the ────
#    Sentry PII fix. Deliberate, reviewed, and ruff-approved.
fresh_tree
cat > "$WORK/tree/$BACKEND_DIR/sentryish.py" <<'EOF'
def _before_send(event, hint):
    # logger is unsafe here: it re-enters Sentry's LoggingIntegration.
    print("sentry: redaction failed")  # noqa: T201 — logger would recurse
    return event
EOF
OUT="$(run_gate "$BACKEND_DIR/sentryish.py")"
case "$OUT" in
    *"Found print()"*) bad "INNOCENCE: a '# noqa: T201' print was blocked -> $OUT" ;;
    *"RC=0"*) ok "INNOCENCE: a '# noqa: T201' print passes, as ruff itself rules" ;;
    *) bad "INNOCENCE: unexpected gate output -> $OUT" ;;
esac

# ── Case 3 (INNOCENCE): the word print( inside a COMMENT ─────────────────────
#    This is verbatim the shape of drive_folder_setup.py:385, which the old
#    grep blocked for a comment stating the code does NOT print.
fresh_tree
cat > "$WORK/tree/$BACKEND_DIR/commented.py" <<'EOF'
import logging

logger = logging.getLogger(__name__)


def setup() -> None:
    # (no print() — logger.info would route via logging config which a CLI
    # caller has not configured yet.)
    logger.info("ready")
EOF
OUT="$(run_gate "$BACKEND_DIR/commented.py")"
case "$OUT" in
    *"Found print()"*) bad "INNOCENCE: a comment mentioning print( was blocked -> $OUT" ;;
    *"RC=0"*) ok "INNOCENCE: the word print( in a comment is not a call" ;;
    *) bad "INNOCENCE: unexpected gate output -> $OUT" ;;
esac

# ── Case 4 (INNOCENCE): >>> docstring examples ───────────────────────────────
#    The old grep special-cased these; the cure must not lose that.
fresh_tree
cat > "$WORK/tree/$BACKEND_DIR/documented.py" <<'EOF'
def search(q: str) -> list:
    """Search.

    Example:
        >>> print(search("visa")[0])
        'E33G'
    """
    return []
EOF
OUT="$(run_gate "$BACKEND_DIR/documented.py")"
case "$OUT" in
    *"Found print()"*) bad "INNOCENCE: a '>>> print(...)' docstring was blocked -> $OUT" ;;
    *"RC=0"*) ok "INNOCENCE: a '>>> print(...)' docstring example still passes" ;;
    *) bad "INNOCENCE: unexpected gate output -> $OUT" ;;
esac

# ── Case 5 (INNOCENCE): identifiers that merely END in print( ────────────────
#    The reason the old grep carried a word-boundary class in the first place.
fresh_tree
cat > "$WORK/tree/$BACKEND_DIR/fingerprints.py" <<'EOF'
def _signal_fingerprint(x: str) -> str:
    return x


def import_blueprint(y: str) -> str:
    return _signal_fingerprint(y)
EOF
OUT="$(run_gate "$BACKEND_DIR/fingerprints.py")"
case "$OUT" in
    *"Found print()"*) bad "INNOCENCE: _signal_fingerprint( was read as print( -> $OUT" ;;
    *"RC=0"*) ok "INNOCENCE: identifiers ending in print( are not print()" ;;
    *) bad "INNOCENCE: unexpected gate output -> $OUT" ;;
esac

# ── Case 6 (INNOCENCE): print() outside the backend scope is allowed ─────────
fresh_tree
cat > "$WORK/tree/scripts/tool.py" <<'EOF'
print("scripts may print")
EOF
OUT="$(run_gate "scripts/tool.py")"
case "$OUT" in
    *"Found print()"*) bad "INNOCENCE: a print() in scripts/ was blocked -> $OUT" ;;
    *"RC=0"*) ok "INNOCENCE: scripts/ stays out of scope" ;;
    *) bad "INNOCENCE: unexpected gate output -> $OUT" ;;
esac

# ── Case 7 (HAZARD PIN): no backend file staged must not scan the whole repo ──
#    A lost `[ -n ]` guard degrades the gate into a bare `ruff check` over the
#    entire tree, which would fail on the unstaged file below and blame a commit
#    that never touched it.
#    PLATFORM NOTE, declared rather than assumed: this case only bites where
#    xargs runs its command on empty input. GNU xargs (Linux CI) does — that is
#    what `-r/--no-run-if-empty` turns off. BSD xargs (macOS, measured
#    2026-08-01) does NOT, so removing the guard cannot redden this case on a
#    dev Mac. It is pinned here because CI is where it would bite, and the line
#    below says out loud which of the two shells is running, so nobody reads a
#    structurally-vacuous pass as coverage (W108).
fresh_tree
if printf '' | xargs echo XARGS_RUNS_ON_EMPTY 2>/dev/null | grep -q XARGS_RUNS_ON_EMPTY; then
    printf '  ℹ  xargs runs on empty input here (GNU-like) — case 7 is load-bearing\n'
else
    printf '  ℹ  xargs does NOT run on empty input here (BSD) — case 7 cannot bite on this machine\n'
fi
cat > "$WORK/tree/$BACKEND_DIR/preexisting_leak.py" <<'EOF'
print("this file is not staged")
EOF
cat > "$WORK/tree/scripts/tool.py" <<'EOF'
x = 1
EOF
OUT="$(run_gate "scripts/tool.py")"
case "$OUT" in
    *"Found print()"*) bad "HAZARD: the gate scanned unstaged files -> $OUT" ;;
    *"RC=0"*) ok "HAZARD PIN: with no backend file staged the gate scans nothing" ;;
    *) bad "HAZARD: unexpected gate output -> $OUT" ;;
esac

# ── Case 8 (CANNOT-VERIFY): ruff missing must not be reported as a clean bill ─
#    nor as "found print()" — W106: a diagnosis that names the wrong cause sends
#    the next reader away from the real one.
#    The PATH is built from scratch with symlinks to exactly the utilities the
#    block needs, rather than assuming /usr/bin holds no ruff: where a machine
#    happens to install ruff is not something this corpus should depend on.
fresh_tree
cat > "$WORK/tree/$BACKEND_DIR/leaky.py" <<'EOF'
print("leak")
EOF
NORUFF_BIN="$WORK/noruff-bin"
rm -rf "$NORUFF_BIN"; mkdir -p "$NORUFF_BIN"
# `sh` belongs in this list: the block is INVOKED as `sh -e -c`, so leaving the
# shell itself unreachable makes the case die at "sh: command not found" and
# measure its own poverty rather than the gate's behaviour (W108).
for util in sh grep xargs; do
    src="$(command -v "$util")" || { bad "CANNOT-VERIFY: $util not found, cannot build the probe PATH"; src=""; }
    [ -n "$src" ] && ln -sf "$src" "$NORUFF_BIN/$util"
done
if PATH="$NORUFF_BIN" command -v ruff >/dev/null 2>&1; then
    bad "CANNOT-VERIFY: ruff leaked into the probe PATH, this case cannot run honestly"
else
    OUT="$(
        cd "$WORK/tree" || exit 99
        out=$(PATH="$NORUFF_BIN" sh -e -c "PY_FILES='$BACKEND_DIR/leaky.py'
$BLOCK" 2>&1) && rc=0 || rc=$?
        printf '%s\nRC=%s\n' "$out" "$rc"
    )"
    case "$OUT" in
        *"cannot verify Golden Rule #8"*) ok "CANNOT-VERIFY: missing ruff is named as such" ;;
        *"Found print()"*) bad "CANNOT-VERIFY: missing ruff was reported as a print() finding -> $OUT" ;;
        *) bad "CANNOT-VERIFY: unexpected gate output -> $OUT" ;;
    esac
    # Assert the gate's OWN exit code, not merely "non-zero": an earlier draft of
    # this case accepted RC=127 — the probe shell failing to start — as proof of
    # fail-closed. A test that can pass for the wrong reason is not a test.
    case "$OUT" in
        *"RC=1"*) ok "CANNOT-VERIFY: the gate itself exits 1 rather than passing blind" ;;
        *) bad "CANNOT-VERIFY: expected the gate's own RC=1 -> $OUT" ;;
    esac
fi

echo "────────────────────────────────────────────────────────────────────────"
echo "  passed: $PASS   failed: $FAIL"
[ "$FAIL" -eq 0 ] || exit 1
