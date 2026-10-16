#!/usr/bin/env bash
# test_claude_seat_pick.sh — claude_seat_pick must select the first LIVE seat and
# SUSPEND (never guess) when all refuse. Fake `claude` binaries decide live/dead
# from the token in the env, so the test exercises the helper, not a real account.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
LIB="$REPO_ROOT/scripts/lib/claude_seat.sh"
WRAPPER="$REPO_ROOT/infra/launchagents/wrappers/cron-agent.sh"
[ -f "$LIB" ] || { echo "FAIL: lib not found at $LIB"; exit 2; }
[ -f "$WRAPPER" ] || { echo "FAIL: cron-agent.sh (classifier source) not found at $WRAPPER"; exit 2; }

SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/seatpick.XXXXXX")"
trap 'rm -rf "$SANDBOX"' EXIT
FAILED=0
ok()   { echo "  ok   — $1"; }
bad()  { echo "  FAIL — $1"; FAILED=1; }

# A fake `claude`: refuses unless CLAUDE_CODE_OAUTH_TOKEN matches $LIVE_TOKEN.
# "refuse" prints a classifier-matching line (weekly limit) to stdout and exits 1,
# exactly how the real CLI reports a capped seat.
make_fake() {  # $1 = path, $2 = the token value that is "live" ("" => default seat is live)
    local path="$1" live="$2"
    cat > "$path" <<FAKE
#!/usr/bin/env bash
# args ignored; verdict is by the token in the env
if [ "\${CLAUDE_CODE_OAUTH_TOKEN:-}" = "$live" ]; then
    echo "PONG"; exit 0
fi
echo "You've hit your weekly limit. Resets later."; exit 1
FAKE
    chmod +x "$path"
}

run_pick() {  # $@ = env assignments; prints "rc|stdout"
    local out; out="$SANDBOX/out"
    env "$@" bash -c "source '$LIB'; claude_seat_pick" > "$out" 2>/dev/null
    printf '%s|%s' "$?" "$(cat "$out")"
}

COMMON=(CLAUDE_SEAT_WRAPPER="$WRAPPER" CLAUDE_SEAT_SECRETS_FILE=/dev/null
        CLAUDE_CODE_OAUTH_TOKEN= )   # neutralise any real secret in the env

# ── 1. default seat live → picks "default", never touches numbered seats ──────
BIN="$SANDBOX/claude_default_live"; make_fake "$BIN" ""   # empty token = default = live
R="$(run_pick "${COMMON[@]}" CLAUDE_SEAT_BIN="$BIN" \
        CLAUDE_CODE_OAUTH_TOKEN_1=s1 CLAUDE_CODE_OAUTH_TOKEN_5=s5)"
[ "$R" = "0|default" ] && ok "default live → 'default'" || bad "default live: got '$R' (want 0|default)"

# ── 2. default dead, token_1 dead, token_5 live → picks "token_5" ─────────────
BIN="$SANDBOX/claude_t5_live_rot"; make_fake "$BIN" "LIVE5"
R="$(run_pick "${COMMON[@]}" CLAUDE_SEAT_BIN="$BIN" \
        CLAUDE_CODE_OAUTH_TOKEN_1=dead1 CLAUDE_CODE_OAUTH_TOKEN_5=LIVE5 CLAUDE_CODE_OAUTH_TOKEN_6=dead6)"
[ "$R" = "0|token_5" ] && ok "default+t1 dead, t5 live → 'token_5'" || bad "rotation: got '$R' (want 0|token_5)"

# ── 3. skip the default (CLAUDE_SEAT_TRY_DEFAULT=0), token_5 live → "token_5" ──
BIN="$SANDBOX/claude_t5_live"; make_fake "$BIN" "LIVE5"
R="$(run_pick "${COMMON[@]}" CLAUDE_SEAT_TRY_DEFAULT=0 CLAUDE_SEAT_BIN="$BIN" \
        CLAUDE_CODE_OAUTH_TOKEN_1=dead1 CLAUDE_CODE_OAUTH_TOKEN_5=LIVE5)"
[ "$R" = "0|token_5" ] && ok "skip-default, t5 live → 'token_5'" || bad "skip-default: got '$R' (want 0|token_5)"

# ── 4. every seat refused → rc 1, no selector (SUSPEND, never guess) ──────────
BIN="$SANDBOX/claude_all_dead"; make_fake "$BIN" "__none__"
R="$(run_pick "${COMMON[@]}" CLAUDE_SEAT_BIN="$BIN" \
        CLAUDE_CODE_OAUTH_TOKEN_1=d1 CLAUDE_CODE_OAUTH_TOKEN_5=d5)"
[ "$R" = "1|" ] && ok "all refused → rc 1, empty (SUSPEND)" || bad "all refused: got '$R' (want 1|)"

# ── 5. duplicate token across slots is probed ONCE, not twice ────────────────
#    (t1 and t5 hold the same dead value; t6 is live — pick must reach t6)
BIN="$SANDBOX/claude_t6_live_dedup"; make_fake "$BIN" "LIVE6"
R="$(run_pick "${COMMON[@]}" CLAUDE_SEAT_BIN="$BIN" \
        CLAUDE_CODE_OAUTH_TOKEN_1=same CLAUDE_CODE_OAUTH_TOKEN_5=same CLAUDE_CODE_OAUTH_TOKEN_6=LIVE6)"
[ "$R" = "0|token_6" ] && ok "dedup dead dupes, reach live t6 → 'token_6'" || bad "dedup: got '$R' (want 0|token_6)"

# ── 6. slot 6 (the Team seat) is reachable ───────────────────────────────────
#    Regression guard for 2026-08-23: the range said `1 2 3 4 5` in three places,
#    so slot 6 was armed in the secrets file and NEVER selected by any cron. A
#    seat the picker cannot see is not a seat. Keep this test slot-6 specific:
#    it is the one the hardcoded range excluded.
BIN="$SANDBOX/claude_t6_live"; make_fake "$BIN" "LIVE6"
R="$(run_pick "${COMMON[@]}" CLAUDE_SEAT_TRY_DEFAULT=0 CLAUDE_SEAT_BIN="$BIN" \
        CLAUDE_CODE_OAUTH_TOKEN_1=dead1 CLAUDE_CODE_OAUTH_TOKEN_6=LIVE6)"
[ "$R" = "0|token_6" ] && ok "slot 6 (Team seat) reachable → 'token_6'" || bad "slot 6 unreachable: got '$R' (want 0|token_6)"

# ── 7. a CLOSED seat is never probed, even when it is the only live token ────
#    Slots 2, 3, 4 (A5, A3, A4) are retired in FLEET_TOPOLOGY.json; the fake
#    claude would answer for them, so a pick that returns one is the bug.
for retired in 2 3 4; do
    BIN="$SANDBOX/claude_retired_$retired"; make_fake "$BIN" "LIVE$retired"
    R="$(run_pick "${COMMON[@]}" CLAUDE_SEAT_TRY_DEFAULT=0 CLAUDE_SEAT_BIN="$BIN" \
            CLAUDE_CODE_OAUTH_TOKEN_1=dead1 "CLAUDE_CODE_OAUTH_TOKEN_$retired=LIVE$retired")"
    [ "$R" = "1|" ] && ok "retired slot $retired never selected → SUSPEND" || bad "retired slot $retired: got '$R' (want 1|)"
done

# ── 8. a closed account's value is not spent through a LIVE numbered slot ────
#    Council refuter (codex, 2026-10-17): slot 1 carrying slot 3's value must
#    not make the closed account answer as token_1.
BIN="$SANDBOX/claude_alias_live"; make_fake "$BIN" "LIVEALIAS"
R="$(run_pick "${COMMON[@]}" CLAUDE_SEAT_TRY_DEFAULT=0 CLAUDE_SEAT_BIN="$BIN" \
        CLAUDE_CODE_OAUTH_TOKEN_1=LIVEALIAS CLAUDE_CODE_OAUTH_TOKEN_3=LIVEALIAS)"
[ "$R" = "1|" ] && ok "retired value aliased into slot 1 never selected → SUSPEND" || bad "retired alias: got '$R' (want 1|)"

echo
[ "$FAILED" -eq 0 ] && { echo "PASS — claude_seat_pick"; exit 0; } || { echo "FAIL — claude_seat_pick"; exit 1; }
