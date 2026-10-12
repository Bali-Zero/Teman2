#!/bin/bash
set -u
PASS=0; FAIL=0
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WRAPPER="$REPO_ROOT/infra/launchagents/wrappers/mini-cert-monitor.sh"
ok() { PASS=$((PASS+1)); printf '  ok   %s\n' "$1"; }
bad() { FAIL=$((FAIL+1)); printf '  FAIL %s\n' "$1"; }
field() { sed -n "s/.*\"$2\":\"\([^\"]*\)\".*/\1/p" "$1"; }

run_case() { # $1 monitor rc, $2 summary JSON
    local rc="$1" body="$2"
    CASE_DIR="$(mktemp -d)"
    mkdir -p "$CASE_DIR/bin" "$CASE_DIR/home/nuzantara/scripts"
    printf '#!/bin/bash\necho Mini-Pro2\n' > "$CASE_DIR/bin/hostname"
    cat > "$CASE_DIR/bin/cert-python" <<'EOF'
#!/bin/bash
printf '%s\n' "$CERT_CASE_JSON"
exit "$CERT_CASE_RC"
EOF
    : > "$CASE_DIR/home/nuzantara/scripts/cert_monitor.py"
    cat > "$CASE_DIR/home/nuzantara/scripts/tg_notify.py" <<'EOF'
import json, os, sys
row={"routing":os.environ.get("TG_ACT_ROUTING_ENABLED"),
     "relay":os.environ.get("TG_RELAY_SSH"), "args":sys.argv[1:]}
with open(os.path.join(os.environ["HOME"], "notify.log"), "a") as out:
    out.write(json.dumps(row, sort_keys=True) + "\n")
EOF
    chmod +x "$CASE_DIR/bin/hostname" "$CASE_DIR/bin/cert-python"
    env -i HOME="$CASE_DIR/home" PATH="$CASE_DIR/bin:/usr/bin:/bin" \
        CERT_MONITOR_PYTHON="$CASE_DIR/bin/cert-python" CERT_CASE_RC="$rc" \
        CERT_CASE_JSON="$body" /bin/bash "$WRAPPER" >/dev/null 2>&1
    HB="$CASE_DIR/home/.organism/last_seen/mini.cert_monitor.json"
    CALLS="$CASE_DIR/home/notify.log"
}

GOOD='{"results":[{"host":"balizero.com","days_left":45,"status":"ok","issuer_cn":"CA"},{"host":"kita.balizero.com","days_left":60,"status":"ok","issuer_cn":"CA"},{"host":"mail.balizero.com","days_left":70,"status":"ok","issuer_cn":"CA"},{"host":"calendar.balizero.com","days_left":80,"status":"ok","issuer_cn":"CA"},{"host":"drive.balizero.com","days_left":90,"status":"ok","issuer_cn":"CA"},{"host":"knowledge.balizero.com","days_left":100,"status":"ok","issuer_cn":"CA"},{"host":"nuzantara-rag.fly.dev","days_left":110,"status":"ok","issuer_cn":"CA"}]}'
run_case 0 "$GOOD"
if [ "$(field "$HB" status)" = "ok" ] && grep -q '7 hosts ok, min 45d' "$HB" \
    && [ ! -f "$CALLS" ]; then ok "rc 0 -> healthy heartbeat, no alert"; else bad "rc 0 mapping"; fi

FINDINGS='{"results":[{"host":"balizero.com","days_left":12,"status":"expiring","issuer_cn":"CA"},{"host":"kita.balizero.com","days_left":60,"status":"ok","issuer_cn":"CA"},{"host":"mail.balizero.com","days_left":null,"status":"verify_failed","issuer_cn":null},{"host":"calendar.balizero.com","days_left":80,"status":"ok","issuer_cn":"CA"},{"host":"drive.balizero.com","days_left":90,"status":"ok","issuer_cn":"CA"},{"host":"knowledge.balizero.com","days_left":100,"status":"ok","issuer_cn":"CA"},{"host":"nuzantara-rag.fly.dev","days_left":110,"status":"ok","issuer_cn":"CA"}]}'
run_case 1 "$FINDINGS"
if [ "$(field "$HB" status)" = "ok" ] && grep -q '2 findings' "$HB" \
    && [ "$(wc -l < "$CALLS" | tr -d ' ')" = 2 ] \
    && grep -q 'cert:balizero.com:expiring' "$CALLS" \
    && grep -q 'balizero.com status=expiring days=12' "$CALLS"; then
    ok "rc 1 -> one p0 per finding and monitor stays healthy"
else bad "rc 1 mapping"; fi
if [ "$(grep -c '\"routing\": \"false\"' "$CALLS")" = 2 ] \
    && [ "$(grep -c '\"relay\": \"\"' "$CALLS")" = 2 ]; then
    ok "p0 disables board routing and relay"
else bad "p0 routing environment"; fi

run_case 3 "$GOOD"
if [ "$(field "$HB" status)" = "error" ] && [ "$(wc -l < "$CALLS" | tr -d ' ')" = 1 ] \
    && grep -q 'cert monitor broken' "$CALLS"; then
    ok "rc 3 -> broken heartbeat and p0"
else bad "rc 3 mapping"; fi

run_case 0 '{"results":[{"host":"balizero.com","days_left":45,"status":"ok","issuer_cn":"CA"}]}'
if [ "$(field "$HB" status)" = "error" ] && grep -q 'cert monitor broken' "$CALLS"; then
    ok "missing hosts -> broken, never a partial green"
else bad "seven-host contract"; fi

printf 'passed %d, failed %d\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
