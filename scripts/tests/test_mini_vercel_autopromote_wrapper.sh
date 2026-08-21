#!/bin/bash
# Corpus for infra/launchagents/wrappers/mini-vercel-autopromote.sh
#
# WHY A FAKE WORLD AND NOT A REAL RUN
# W107's lesson, paid for by curing one wrapper out of five and calling the disease closed: a
# wrapper's VOICE is proven by executing it in a fake world, not by reading it. Here the world
# is a temp HOME, a fake `hostname` on PATH, and a stand-in cure script whose exit code and
# output each case chooses. Nothing touches Vercel, the real HOME, or the real organism state.
#
# WHAT IT HAS TO PROVE
# The wrapper's whole job is TRANSLATION: three distinct exit codes from the cure into three
# distinct heartbeat states a silence-watcher can tell apart. Getting that wrong is invisible
# — a run that reports "ok" while nothing was promoted is exactly the green-over-dead shape of
# superscar #2. So: guilt on every outcome, and innocence that the two refusal gates (wrong
# node, kill switch) never let the payload run at all.

set -u
PASS=0; FAIL=0
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WRAPPER="$REPO_ROOT/infra/launchagents/wrappers/mini-vercel-autopromote.sh"

[ -f "$WRAPPER" ] || { echo "FATAL: wrapper not found at $WRAPPER"; exit 1; }

ok()   { PASS=$((PASS+1)); printf '  ok   %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  FAIL %s\n     %s\n' "$1" "$2"; }

# Run the wrapper in a disposable world. $1=rc the cure returns, $2=what it prints,
# $3=hostname to report, $4..=extra env assignments. Echoes the sidecar JSON.
run_case() {
    local rc="$1" out="$2" host="$3"; shift 3
    local tmp; tmp="$(mktemp -d)"
    mkdir -p "$tmp/bin" "$tmp/home/nuzantara/scripts"

    printf '#!/bin/bash\necho "%s"\n' "$host" > "$tmp/bin/hostname"
    chmod +x "$tmp/bin/hostname"

    if [ "$rc" != "MISSING" ]; then
        cat > "$tmp/home/nuzantara/scripts/vercel_prod_deploy.py" <<PYEOF
import sys
open("$tmp/cure-ran", "w").write(" ".join(sys.argv[1:]))
print("""$out""")
sys.exit($rc)
PYEOF
    fi

    env -i HOME="$tmp/home" PATH="$tmp/bin:/usr/bin:/bin" "$@" \
        /bin/bash "$WRAPPER" >/dev/null 2>&1

    printf '%s\t%s\t%s' \
        "$(cat "$tmp/home/.organism/last_seen/mini.vercel_autopromote.json" 2>/dev/null)" \
        "$([ -f "$tmp/cure-ran" ] && echo RAN || echo NOT-RUN)" \
        "$tmp"
}

field() { printf '%s' "$1" | sed -n "s/.*\"$2\":\"\([^\"]*\)\".*/\1/p"; }

echo "== guilt: the three outcomes must be three distinct states =="

r=$(run_case 0 'OK — balizero.com serves abc123def (promoted dpl_x, no rebuild)' Mini-Pro2)
hb=$(echo "$r" | cut -f1); ran=$(echo "$r" | cut -f2)
[ "$(field "$hb" status)" = "ok" ] && [ "$(field "$hb" note)" = "promoted" ] \
    && ok "rc=0 + promoted -> ok/promoted" || bad "rc=0 + promoted" "$hb"
[ "$ran" = "RAN" ] && ok "rc=0 case actually invoked the cure" || bad "cure not invoked" "$ran"

r=$(run_case 0 'production already includes this commit — nothing to do' Mini-Pro2)
hb=$(echo "$r" | cut -f1)
[ "$(field "$hb" status)" = "ok" ] && [ "$(field "$hb" note)" = "already current" ] \
    && ok "rc=0 + no promote -> ok/already current" || bad "rc=0 no promote" "$hb"

r=$(run_case 2 'no READY production build for abc123def' Mini-Pro2)
hb=$(echo "$r" | cut -f1)
[ "$(field "$hb" status)" = "warning" ] \
    && ok "rc=2 -> warning (NOT ok, NOT error)" || bad "rc=2 must be warning" "$hb"

r=$(run_case 1 '::error::promote did not move the domains' Mini-Pro2)
hb=$(echo "$r" | cut -f1)
[ "$(field "$hb" status)" = "error" ] \
    && ok "rc=1 -> error" || bad "rc=1 must be error" "$hb"

r=$(run_case MISSING '' Mini-Pro2)
hb=$(echo "$r" | cut -f1)
[ "$(field "$hb" status)" = "error" ] \
    && ok "cure script absent -> error (armed at nothing, W81)" || bad "missing cure" "$hb"

echo "== the cure is passed --promote-only, never the building default =="
r=$(run_case 0 'nothing to do' Mini-Pro2); tmp=$(echo "$r" | cut -f3)
[ "$(cat "$tmp/cure-ran" 2>/dev/null)" = "--promote-only" ] \
    && ok "invoked with --promote-only" || bad "wrong flags" "$(cat "$tmp/cure-ran" 2>/dev/null)"

echo "== innocence: neither refusal gate may run the payload =="

r=$(run_case 0 'nothing to do' Nuzantara)
hb=$(echo "$r" | cut -f1); ran=$(echo "$r" | cut -f2)
[ "$(field "$hb" status)" = "disabled" ] && [ "$ran" = "NOT-RUN" ] \
    && ok "wrong node -> disabled AND cure never ran (#10)" || bad "node guard" "$hb / $ran"

r=$(run_case 0 'nothing to do' Mini-Pro2 MINI_VERCEL_AUTOPROMOTE_ENABLED=false)
hb=$(echo "$r" | cut -f1); ran=$(echo "$r" | cut -f2)
[ "$(field "$hb" status)" = "disabled" ] && [ "$ran" = "NOT-RUN" ] \
    && ok "kill switch -> disabled AND cure never ran" || bad "kill switch" "$hb / $ran"

echo
printf 'passed %d, failed %d\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
