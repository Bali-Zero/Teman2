#!/usr/bin/env bash
# test_canva_oauth_watchdog.sh — TDD harness for the Canva OAuth
# watchdog (Sprint B B-NEW, 2026-05-08).
#
# The watchdog itself is Pro-local at ~/scripts/wr2-canva-oauth-watchdog.sh
# (NOT in this repo); the canonical body lives at
# docs/wr2/skill-snapshots/canva-oauth-watchdog-2026-05-08.md.
# These tests embed the script via the snapshot — extracting the bash
# code block, writing it to a sandbox path, then running it with
# isolated state + a stub `claude` binary so we exercise the three
# code paths (healthy / stale-with-alert / stale-with-cooldown) without
# touching real OAuth state, real Telegram, or real launchd.
#
# Run from repo root:
#   bash tests/lint/test_canva_oauth_watchdog.sh
# Exit 0 = all paths pass, 1 = any failure.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SNAPSHOT="$REPO_ROOT/docs/wr2/skill-snapshots/canva-oauth-watchdog-2026-05-08.md"

if [[ ! -f "$SNAPSHOT" ]]; then
  echo "FAIL: snapshot not found at $SNAPSHOT" >&2
  exit 2
fi

TMP="$(mktemp -d -t canva_oauth_watchdog.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

# Extract the first ```bash fenced block from the snapshot (the script body).
# Markdown-aware: matches '```bash' on a line, copies until the next ``` line.
SCRIPT="$TMP/wr2-canva-oauth-watchdog.sh"
awk '
  /^```bash$/ { inside=1; next }
  /^```$/    { if (inside) exit }
  inside     { print }
' "$SNAPSHOT" > "$SCRIPT"

if [[ ! -s "$SCRIPT" ]]; then
  echo "FAIL: could not extract bash body from $SNAPSHOT" >&2
  exit 2
fi
chmod +x "$SCRIPT"

# Override HOME so the script writes its log + state into the sandbox.
export HOME="$TMP/home"
mkdir -p "$HOME/.agent/decisions/state" "$HOME/logs" "$HOME/scripts"

# Drop a stub `claude` binary the script will pick up via the test
# PATH-prefix env var. STUB_OUTPUT controls what it echoes.
STUB="$TMP/shim"
mkdir -p "$STUB"
cat > "$STUB/claude" <<'STUBSH'
#!/usr/bin/env bash
# Stub: emits the contents of $STUB_OUTPUT (or "stub_default" if unset).
printf '%s\n' "${STUB_OUTPUT:-stub_default}"
STUBSH
chmod +x "$STUB/claude"
export CANVA_WATCHDOG_TEST_PATH_PREFIX="$STUB"

# No real Telegram even if a real token leaked in.
export TELEGRAM_BOT_TOKEN=""

PASS=0
FAIL=0

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    printf '  PASS: %-50s (got=%s)\n' "$label" "$actual"
    PASS=$((PASS + 1))
  else
    printf '  FAIL: %-50s (expected=%s actual=%s)\n' "$label" "$expected" "$actual" >&2
    FAIL=$((FAIL + 1))
  fi
}

assert_grep() {
  local label="$1" pattern="$2" file="$3"
  if grep -qE "$pattern" "$file"; then
    printf '  PASS: %-50s (matched /%s/)\n' "$label" "$pattern"
    PASS=$((PASS + 1))
  else
    printf '  FAIL: %-50s (no match for /%s/ in %s)\n' "$label" "$pattern" "$file" >&2
    FAIL=$((FAIL + 1))
  fi
}

reset_state() {
  rm -f "$HOME/.agent/decisions/state/wr2_canva_oauth.state" \
        "$HOME/.agent/decisions/state/wr2_canva_oauth.lock"
}

# Run the watchdog and capture exit code without tripping `set -e`.
run_watchdog() {
  set +e
  rc=0
  "$SCRIPT" >/dev/null 2>&1
  rc=$?
  set -e
}

state_get() {
  local key="$1"
  awk -F= -v k="$key" '$1==k {print $2}' \
    "$HOME/.agent/decisions/state/wr2_canva_oauth.state" 2>/dev/null \
    | tail -1
}

# ─────────────────────────────────────────────────────────────────────
# Test 1: healthy probe (count >= 30 → exit 0, state.healthy)
# ─────────────────────────────────────────────────────────────────────
echo "TEST 1: healthy probe"
reset_state
STUB_OUTPUT=33 run_watchdog
assert_eq "healthy exit code" "0" "$rc"
assert_eq "state.last_status" "healthy" "$(state_get last_status)"
assert_eq "state.last_count" "33" "$(state_get last_count)"

# ─────────────────────────────────────────────────────────────────────
# Test 2: first stale transition (no prior alert → alert fires)
# ─────────────────────────────────────────────────────────────────────
echo "TEST 2: first stale transition"
reset_state
STUB_OUTPUT=5 run_watchdog
assert_eq "stale exit code" "1" "$rc"
assert_eq "state.last_status" "stale" "$(state_get last_status)"
assert_eq "state.last_count" "5" "$(state_get last_count)"
LAST_ALERT="$(state_get last_alert_ts)"
if [[ "$LAST_ALERT" =~ ^[0-9]+$ ]]; then
  printf '  PASS: %-50s (epoch=%s)\n' "alert_ts written" "$LAST_ALERT"
  PASS=$((PASS + 1))
else
  printf '  FAIL: alert_ts not numeric (got=%s)\n' "$LAST_ALERT" >&2
  FAIL=$((FAIL + 1))
fi
assert_grep "log shows alert sent" \
  "alert sent" "$HOME/logs/wr2-canva-oauth-watchdog.log"

# ─────────────────────────────────────────────────────────────────────
# Test 3: stale + cooldown active (recent alert → suppression)
# ─────────────────────────────────────────────────────────────────────
echo "TEST 3: stale + cooldown active"
reset_state
NOW=$(date +%s)
RECENT=$(( NOW - 3600 ))   # 1h ago, well within 24h cooldown
cat > "$HOME/.agent/decisions/state/wr2_canva_oauth.state" <<EOF
last_status=stale
last_count=5
last_check_ts=$RECENT
last_alert_ts=$RECENT
EOF
STUB_OUTPUT=5 run_watchdog
assert_eq "stale exit code" "1" "$rc"
# alert_ts must NOT have been bumped; remains $RECENT.
LAST_ALERT_AFTER="$(state_get last_alert_ts)"
assert_eq "alert_ts unchanged (cooldown)" "$RECENT" "$LAST_ALERT_AFTER"
assert_grep "log shows alert suppressed" \
  "alert suppressed" "$HOME/logs/wr2-canva-oauth-watchdog.log"

# ─────────────────────────────────────────────────────────────────────
# Test 4: stale + cooldown elapsed (>24h since last alert → fires again)
# ─────────────────────────────────────────────────────────────────────
echo "TEST 4: stale + cooldown elapsed"
reset_state
OLD=$(( NOW - 90000 ))     # 25h ago, cooldown elapsed
cat > "$HOME/.agent/decisions/state/wr2_canva_oauth.state" <<EOF
last_status=stale
last_count=5
last_check_ts=$OLD
last_alert_ts=$OLD
EOF
STUB_OUTPUT=5 run_watchdog
assert_eq "stale exit code" "1" "$rc"
LAST_ALERT_AFTER="$(state_get last_alert_ts)"
if [[ "$LAST_ALERT_AFTER" =~ ^[0-9]+$ ]] && (( LAST_ALERT_AFTER > OLD )); then
  printf '  PASS: %-50s (was=%s now=%s)\n' "alert_ts bumped" "$OLD" "$LAST_ALERT_AFTER"
  PASS=$((PASS + 1))
else
  printf '  FAIL: alert_ts not bumped (was=%s now=%s)\n' "$OLD" "$LAST_ALERT_AFTER" >&2
  FAIL=$((FAIL + 1))
fi

# ─────────────────────────────────────────────────────────────────────
# Test 5: probe returns non-numeric (anomalous) → treated as stale
# ─────────────────────────────────────────────────────────────────────
echo "TEST 5: non-numeric probe output"
reset_state
STUB_OUTPUT="ERROR: API limit" run_watchdog
assert_eq "stale exit code (non-numeric)" "1" "$rc"
assert_eq "state.last_status (non-numeric)" "stale" "$(state_get last_status)"

# ─────────────────────────────────────────────────────────────────────
# Test 6: probe returns 29 (just below MIN_TOOLS) → stale
# ─────────────────────────────────────────────────────────────────────
echo "TEST 6: probe returns 29 (below threshold)"
reset_state
STUB_OUTPUT=29 run_watchdog
assert_eq "stale exit code (29)" "1" "$rc"
assert_eq "state.last_count (29)" "29" "$(state_get last_count)"

# ─────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────
echo ""
echo "RESULT: ${PASS} passed, ${FAIL} failed"
if (( FAIL > 0 )); then
  exit 1
fi
exit 0
