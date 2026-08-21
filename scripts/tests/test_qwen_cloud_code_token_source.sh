#!/usr/bin/env bash
# test_qwen_cloud_code_token_source.sh — the qwen-cloud-code wrapper's credential gate
# must accept a Keychain token (locked in every case here — simulated, matching the real
# non-interactive-ssh failure "User interaction is not allowed") OR fall back to
# ~/.qwen/settings.json ONLY when its mode is exactly 0600 AS FOUND and
# env.BAILIAN_TOKEN_PLAN_API_KEY is non-empty; die otherwise. It must log WHICH source was
# accepted, NEVER the value (W106 class: name the source, not the secret).
# 2026-08-21, qwen-seat-fleet arming (fleet-wide over ssh where Keychain is locked).
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
WRAPPER="$REPO_ROOT/scripts/qwen-cloud-code.sh"
[ -f "$WRAPPER" ] || { echo "FAIL: wrapper not found at $WRAPPER"; exit 2; }

SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/qwentoken.XXXXXX")"
trap 'rm -rf "$SANDBOX"' EXIT
FAILED=0
DUMMY="sk-test-000"

ok()  { echo "  ok   — $1"; }
bad() { echo "  FAIL — $1"; FAILED=1; }

# Fake `security`: always simulates a LOCKED Keychain (the real non-interactive-ssh
# failure mode), forcing every case through the settings.json fallback under test.
# Fake `qwen`: proves the wrapper reached exec, without ever printing the token value.
mkfakebin() {
    local dir="$1"
    mkdir -p "$dir"
    cat > "$dir/security" <<'FAKE'
#!/usr/bin/env bash
echo "security: User interaction is not allowed." >&2
exit 1
FAKE
    chmod +x "$dir/security"
    cat > "$dir/qwen" <<'FAKE'
#!/usr/bin/env bash
if [ -n "${BAILIAN_TOKEN_PLAN_API_KEY:-}" ]; then
    echo "FAKE_QWEN_INVOKED token_set=yes"
else
    echo "FAKE_QWEN_INVOKED token_set=no"
fi
exit 0
FAKE
    chmod +x "$dir/qwen"
}

run_wrapper() {  # $1 = fake HOME; prints "rc|combined stdout+stderr"
    local home="$1" bindir="$SANDBOX/bin" out
    mkfakebin "$bindir"
    out="$SANDBOX/out.$$"
    ( HOME="$home" PATH="$bindir:$PATH" bash "$WRAPPER" --help ) > "$out" 2>&1
    local rc=$?
    printf '%s|%s' "$rc" "$(cat "$out")"
    rm -f "$out"
}

write_settings() {  # $1=home $2=mode ("600"/"644") $3=value ("" to omit the key)
    local home="$1" mode="$2" val="$3"
    mkdir -p "$home/.qwen"
    if [ -n "$val" ]; then
        printf '{"env": {"BAILIAN_TOKEN_PLAN_API_KEY": "%s"}}\n' "$val" > "$home/.qwen/settings.json"
    else
        printf '{"env": {}}\n' > "$home/.qwen/settings.json"
    fi
    chmod "$mode" "$home/.qwen/settings.json"
}

# ── 1. settings.json 0600 + value → ACCEPTED, source=settings.json, exec reached ─────
H1="$SANDBOX/home1"; mkdir -p "$H1"
write_settings "$H1" 600 "$DUMMY"
R="$(run_wrapper "$H1")"
RC="${R%%|*}"; OUT="${R#*|}"
if [ "$RC" = "0" ] && echo "$OUT" | grep -q "token source accepted: settings.json" \
   && echo "$OUT" | grep -q "FAKE_QWEN_INVOKED token_set=yes"; then
    ok "0600 settings.json with value → accepted, source logged, exec reached"
else
    bad "0600 settings.json with value: got rc=$RC out=[$OUT]"
fi
if echo "$OUT" | grep -qF "$DUMMY"; then
    bad "0600 case leaked the dummy token value into output"
else
    ok "0600 case never printed the dummy token value"
fi

# ── 2. settings.json 0644 (wrong mode, AS FOUND) → REFUSED, die, no leak ─────────────
#    (proves step-0's own chmod-0600-reassert does NOT retroactively launder the file
#    into passing this gate — the mode captured is the mode the caller left it in)
H2="$SANDBOX/home2"; mkdir -p "$H2"
write_settings "$H2" 644 "$DUMMY"
R="$(run_wrapper "$H2")"
RC="${R%%|*}"; OUT="${R#*|}"
if [ "$RC" != "0" ] && echo "$OUT" | grep -qi "UNARMED"; then
    ok "0644 settings.json (wrong mode as found) → refused (seat UNARMED)"
else
    bad "0644 settings.json: got rc=$RC out=[$OUT] (want non-zero + UNARMED)"
fi
if echo "$OUT" | grep -qF "$DUMMY"; then
    bad "0644 case leaked the dummy token value into output"
else
    ok "0644 case never printed the dummy token value"
fi

# ── 3. no Keychain (locked) + no settings.json at all → die, no leak ─────────────────
H3="$SANDBOX/home3"; mkdir -p "$H3"
R="$(run_wrapper "$H3")"
RC="${R%%|*}"; OUT="${R#*|}"
if [ "$RC" != "0" ] && echo "$OUT" | grep -qi "UNARMED"; then
    ok "no keychain + no settings.json → refused (seat UNARMED)"
else
    bad "no-settings case: got rc=$RC out=[$OUT] (want non-zero + UNARMED)"
fi
if echo "$OUT" | grep -qF "$DUMMY"; then
    bad "no-settings case leaked the dummy token value"
else
    ok "no-settings case never printed the dummy token value"
fi

# ── 4. settings.json 0600 but the key is EMPTY → refused (non-empty required) ────────
H4="$SANDBOX/home4"; mkdir -p "$H4"
write_settings "$H4" 600 ""
R="$(run_wrapper "$H4")"
RC="${R%%|*}"; OUT="${R#*|}"
if [ "$RC" != "0" ] && echo "$OUT" | grep -qi "UNARMED"; then
    ok "0600 settings.json with EMPTY value → refused (seat UNARMED)"
else
    bad "0600-empty case: got rc=$RC out=[$OUT] (want non-zero + UNARMED)"
fi

echo
if [ "$FAILED" -eq 0 ]; then
    echo "PASS — qwen_cloud_code_token_source"; exit 0
else
    echo "FAIL — qwen_cloud_code_token_source"; exit 1
fi
