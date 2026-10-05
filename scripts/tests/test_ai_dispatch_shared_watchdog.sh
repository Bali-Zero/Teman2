#!/usr/bin/env bash
# L50 — proves scripts/ai-dispatch.sh uses the SHARED run_with_timeout from
# scripts/lib/seat_watchdog.sh (single source), offline, with no real LLM CLI.
#
# Knobs discovered by reading ai-dispatch.sh (do not invent flags):
#   - `gemini-scan` → run_gemini "scan" "$PROMPT" → run_with_timeout 120 "$AGY_BIN" -p …
#     (120s is run_gemini's ${3:-120} default; no subcommand exposes a smaller one)
#   - AGY_BIN is env-overridable (line: AGY_BIN="${AGY_BIN:-agy}") and require_gemini
#     only does `command -v "$AGY_BIN"`, so a stub script path satisfies the gate.
#   - AI_DISPATCH_TIMEOUT_GRACE_SECS shortens the TERM→KILL grace (default 2).
# On timeout the dispatcher documents: err "TIMEOUT: agy did not respond…" + return 1.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DISPATCHER="$REPO_ROOT/scripts/ai-dispatch.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/ai-dispatch-shared-watchdog.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

PASS_COUNT=0
FAIL_COUNT=0

check() { # <name> <rc>
    if [ "$2" -eq 0 ]; then
        PASS_COUNT=$((PASS_COUNT + 1)); printf 'PASS: %s\n' "$1"
    else
        FAIL_COUNT=$((FAIL_COUNT + 1)); printf 'FAIL: %s\n' "$1"
    fi
}

# ── (a) GUILT/positive control ─────────────────────────────────────────────
# gemini-scan through the shared watchdog: stub agy traps+ignores TERM, so the
# watchdog must escalate to KILL on the whole process group.
STUB="$TMP/agy-stub.sh"
STUB_PID_FILE="$TMP/stub.pid"
cat > "$STUB" <<'EOF'
#!/usr/bin/env bash
echo $$ > "$STUB_PID_FILE"
trap '' TERM INT
while :; do sleep 1; done
EOF
chmod +x "$STUB"

printf 'Running gemini-scan guilt case (~120s hardcoded run_gemini timeout)…\n'
start=$(date +%s)
AGY_BIN="$STUB" STUB_PID_FILE="$STUB_PID_FILE" \
AI_DISPATCH_TIMEOUT_GRACE_SECS=1 \
bash "$DISPATCHER" gemini-scan "harmless read-only scan of a test fixture" \
    >"$TMP/guilt.out" 2>"$TMP/guilt.err"
guilt_rc=$?
elapsed=$(( $(date +%s) - start ))
printf 'guilt case finished: rc=%d elapsed=%ss\n' "$guilt_rc" "$elapsed"

rc=0
[ "$guilt_rc" -ne 0 ] || { echo "  expected non-zero dispatcher exit"; rc=1; }
grep -q "TIMEOUT: agy did not respond" "$TMP/guilt.err" \
    || { echo "  missing documented TIMEOUT stderr line"; rc=1; cat "$TMP/guilt.err"; }
if [ -f "$STUB_PID_FILE" ]; then
    stub_pid=$(cat "$STUB_PID_FILE")
    if kill -0 "$stub_pid" 2>/dev/null; then
        echo "  stub pid $stub_pid SURVIVED the watchdog"; kill -KILL "$stub_pid" 2>/dev/null; rc=1
    fi
else
    echo "  stub never recorded its pid (did the dispatcher even reach agy?)"; rc=1
fi
[ "$elapsed" -ge 115 ] || { echo "  watchdog fired too early (${elapsed}s < 120s timeout)"; rc=1; }
check "guilt: gemini-scan timeout kills TERM-ignoring stub process group" "$rc"

# ── (b) fail-loud when the lib is missing ──────────────────────────────────
LOUD_TMP="$TMP/no-lib"
mkdir -p "$LOUD_TMP/scripts"
cp "$DISPATCHER" "$LOUD_TMP/scripts/ai-dispatch.sh"
chmod +x "$LOUD_TMP/scripts/ai-dispatch.sh"
# NOTE: deliberately no scripts/lib/seat_watchdog.sh next to the copy.
bash "$LOUD_TMP/scripts/ai-dispatch.sh" help >"$TMP/loud.out" 2>"$TMP/loud.err"
loud_rc=$?
rc=0
[ "$loud_rc" -ne 0 ] || { echo "  expected non-zero exit without the lib"; rc=1; }
grep -q "seat_watchdog.sh" "$TMP/loud.err" \
    || { echo "  missing clear stderr message"; rc=1; cat "$TMP/loud.err"; }
check "fail-loud: dispatcher without lib exits non-zero with clear stderr" "$rc"

# ── (c) syntax ─────────────────────────────────────────────────────────────
bash -n "$DISPATCHER"
check "bash -n ai-dispatch.sh" $?

printf 'SUMMARY %d passed, %d failed\n' "$PASS_COUNT" "$FAIL_COUNT"
[ "$FAIL_COUNT" -eq 0 ]
