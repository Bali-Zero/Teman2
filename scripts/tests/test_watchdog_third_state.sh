#!/bin/bash
# Corpus: a watchdog whose OWN probe failed is a THIRD state, never "healthy" and
# never "alarm fired" (superscar #2: green != working).
#
# Three watchdogs used to report fine precisely when the thing they watch had died:
#   1. healer receptor 2 (infra/healer/healer-run.sh on Mini, and the Pro twin
#      infra/launchagents/wrappers/pro-healer.sh): a crashed proprioception read as
#      "0 divergences". The Pro twin additionally read only the legacy `verdict`
#      key while proprioception emits `status`, so it could never see a divergence.
#   2. scripts/auth_sentinel_cron.sh: `|| true` then heartbeat "ok" after a crash.
#   3. infra/launchagents/wrappers/pro-llm-burn-alarm.sh: a failed cd (or a Python
#      traceback) is rc=1, the same rc as "ALARM dispatched", so it heartbeated ok.
#
# Every case runs the REAL shipped text: the receptor block is extracted verbatim
# from each healer script; the two wrappers run whole under a scratch $HOME.
# Zero network, zero writes outside a mktemp dir.
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
TMP="$(mktemp -d)" || { echo "FATAL: mktemp failed" >&2; exit 1; }
trap 'rm -rf "$TMP"' EXIT
FAIL=0
check() { # $1 label, $2 expected, $3 actual
    if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1: expected [$2] got [$3]"; FAIL=1; fi
}

# ---------------------------------------------------------------- healer receptor
HEALERS="mini:$REPO/infra/healer/healer-run.sh:# Receptor 2:# Receptor 3:
pro:$REPO/infra/launchagents/wrappers/pro-healer.sh:# Receptor B:# Receptor C:"
mkdir -p "$TMP/repo/scripts"
cp "$REPO/scripts/healer_run_checks.py" "$TMP/repo/scripts/"
cat > "$TMP/repo/scripts/proprioception.py" <<'PY'
import os, sys
mode = os.environ["FAKE_MODE"]
if mode == "crash":
    raise RuntimeError("boom")
if mode == "garbage":
    print("not json at all")
elif mode == "noprobes":
    print('{"summary": "x"}')
elif mode == "healthy":
    print('{"probes": [{"status": "RECONCILED"}, {"status": "UNPROBEABLE"}]}')
elif mode == "diverged":
    print('{"probes": [{"status": "DIVERGED"}, {"status": "RECONCILED"}, {"status": "DIVERGED"}]}')
elif mode == "legacy":
    print('{"probes": [{"verdict": "DIVERGED"}]}')
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
PY

run_receptor() { # $1 healer-spec, $2 mode, $3 exit code -> "ACT=.. REASONS=[..]"
    local script start end
    script="$(printf '%s' "$1" | cut -d: -f2)"
    start="$(printf '%s' "$1" | cut -d: -f3)"
    end="$(printf '%s' "$1" | cut -d: -f4)"
    { echo 'ACTIONABLE=0; REASONS=""'
      awk -v s="$start" -v e="$end" 'index($0, s)==1{on=1} index($0, e)==1{on=0} on' "$script"
      echo 'echo "ACT=$ACTIONABLE REASONS=[${REASONS% }]"'
    } > "$TMP/driver.sh"
    (cd "$TMP/repo" && FAKE_MODE="$2" FAKE_EXIT="$3" bash "$TMP/driver.sh" 2>/dev/null)
}

while IFS= read -r spec; do
    [ -n "$spec" ] || continue
    name="${spec%%:*}"
    check "$name healer: crash (exit 1, no output) is receptor-broken" \
        "ACT=1 REASONS=[proprioception-receptor-broken]" "$(run_receptor "$spec" crash 0)"
    check "$name healer: exit 2 with parsable JSON is receptor-broken" \
        "ACT=1 REASONS=[proprioception-receptor-broken]" "$(run_receptor "$spec" healthy 2)"
    check "$name healer: unparsable output is receptor-broken" \
        "ACT=1 REASONS=[proprioception-receptor-broken]" "$(run_receptor "$spec" garbage 0)"
    check "$name healer: JSON without probes list is receptor-broken" \
        "ACT=1 REASONS=[proprioception-receptor-broken]" "$(run_receptor "$spec" noprobes 0)"
    check "$name healer: healthy stays silent" \
        "ACT=0 REASONS=[]" "$(run_receptor "$spec" healthy 0)"
    check "$name healer: real divergences keep the alarm path" \
        "ACT=1 REASONS=[proprioception:2-diverged]" "$(run_receptor "$spec" diverged 0)"
    check "$name healer: legacy verdict schema still counted" \
        "ACT=1 REASONS=[proprioception:1-diverged]" "$(run_receptor "$spec" legacy 0)"
done <<EOF
$HEALERS
EOF

# ---------------------------------------------------------------- auth sentinel
AUTH_HOME="$TMP/auth"
mkdir -p "$AUTH_HOME/nuzantara/scripts"
cat > "$AUTH_HOME/nuzantara/scripts/auth_sentinel.py" <<'PY'
import os, sys
mode = os.environ["FAKE_MODE"]
if mode == "crash":
    raise RuntimeError("boom")
if mode == "alarm":
    print("  ACTION claude-oauth")
sys.exit(0)
PY
run_auth() { # $1 mode -> normalised heartbeat line, plus the wrapper exit code
    local rc
    rm -f "$AUTH_HOME/.organism/last_seen/auth-sentinel.json"
    HOME="$AUTH_HOME" FAKE_MODE="$1" bash "$REPO/scripts/auth_sentinel_cron.sh" >/dev/null 2>&1
    rc=$?
    sed -E 's/"host":"[^"]*"/"host":"H"/; s/"ts":"[^"]*"/"ts":"T"/' \
        "$AUTH_HOME/.organism/last_seen/auth-sentinel.json" | tr -d '\n'
    echo " rc=$rc"
}
check "auth-sentinel: healthy heartbeat is byte-identical ok" \
    '{"organ":"auth-sentinel","host":"H","ts":"T","status":"ok"} rc=0' "$(run_auth healthy)"
check "auth-sentinel: a found ACTION (sentinel exit 0) stays ok" \
    '{"organ":"auth-sentinel","host":"H","ts":"T","status":"ok"} rc=0' "$(run_auth alarm)"
check "auth-sentinel: crashed sentinel is status error with a note" \
    '{"organ":"auth-sentinel","host":"H","ts":"T","status":"error","note":"sentinel crashed rc=1"} rc=0' "$(run_auth crash)"

# ---------------------------------------------------------------- burn alarm
BURN_HOME="$TMP/burn"
mkdir -p "$TMP/bin" "$BURN_HOME/nuzantara/apps/backend-rag/.venv/bin"
printf '#!/bin/sh\necho nuzantara\n' > "$TMP/bin/hostname"; chmod +x "$TMP/bin/hostname"
cat > "$BURN_HOME/nuzantara/apps/backend-rag/.venv/bin/python" <<'SH'
#!/bin/bash
case "$FAKE_MODE" in
    ok) echo "[INFO] llm_burn_alarm: OK" >&2; exit 0 ;;
    alarm) echo "[WARNING] llm_burn_alarm: ALARM" >&2; exit 1 ;;
    crash) echo "Traceback (most recent call last):" >&2; exit 1 ;;
    cannot) echo "[ERROR] llm_burn_alarm: CANNOT_VERIFY" >&2; exit 2 ;;
esac
SH
chmod +x "$BURN_HOME/nuzantara/apps/backend-rag/.venv/bin/python"
run_burn() { # $1 mode -> "status | note"
    rm -f "$BURN_HOME/.organism/last_seen/pro.llm_burn_alarm.json" /tmp/nuzantara-pro-llm_burn_alarm.pid
    HOME="$BURN_HOME" PATH="$TMP/bin:$PATH" FAKE_MODE="$1" \
        bash "$REPO/infra/launchagents/wrappers/pro-llm-burn-alarm.sh" >/dev/null 2>&1
    python3 -c '
import json, sys
d = json.load(open(sys.argv[1]))
print(d["status"], "|", d["note"])' "$BURN_HOME/.organism/last_seen/pro.llm_burn_alarm.json"
}
check "burn-alarm: no anomaly stays ok" "ok | run done: no anomaly" "$(run_burn ok)"
check "burn-alarm: a real ALARM stays ok/dispatched" "ok | run done: ALARM dispatched" "$(run_burn alarm)"
check "burn-alarm: CANNOT_VERIFY stays error" "error | run done: CANNOT_VERIFY (rc=2)" "$(run_burn cannot)"
check "burn-alarm: crash (rc=1 without ALARM marker) is error" \
    "error | run done: rc=1 without an ALARM marker (probe crashed)" "$(run_burn crash)"
mv "$BURN_HOME/nuzantara" "$BURN_HOME/nuzantara.gone"
check "burn-alarm: failed cd is error, not ALARM dispatched" \
    "error | run done: cd failed" "$(run_burn ok)"
mv "$BURN_HOME/nuzantara.gone" "$BURN_HOME/nuzantara"

[ "$FAIL" -eq 0 ] && echo "ALL PASS" || { echo "FAILURES"; exit 1; }
