#!/bin/bash
# Corpus: the Mini healer's G11 memoize (infra/healer/healer-run.sh) — port of the
# Pro block. Same fingerprint + last verdict incurable -> no spawn and a `memoized:`
# line; a changed receptor, an unreadable ledger or a broken memo tool -> spawn
# (fail-open); the session's own HEALER_VERDICT line is what gets recorded.
#
# Runs the REAL shipped text: the pre-spawn block and the post-session record block
# are extracted verbatim from the wrapper and driven under a scratch HOME/repo.
# Zero network, zero writes outside a mktemp dir.
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
WRAPPER="${MINI_HEALER_UNDER_TEST:-$REPO/infra/healer/healer-run.sh}"
MEMO_PY="${HEALER_MEMO_UNDER_TEST:-$REPO/scripts/healer_memo.py}"
TMP="$(mktemp -d)" || { echo "FATAL: mktemp failed" >&2; exit 1; }
trap 'rm -rf "$TMP"' EXIT
FAIL=0
check() { # $1 label, $2 expected, $3 actual
    if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1: expected [$2] got [$3]"; FAIL=1; fi
}

mkdir -p "$TMP/repo/scripts" "$TMP/home"
cp "$MEMO_PY" "$TMP/repo/scripts/healer_memo.py"
cat > "$TMP/repo/scripts/pending_arms_report.py" <<'PY'
import json, os, sys
mode = os.environ.get("FAKE_LEDGER", "a")
if mode == "crash":
    raise RuntimeError("boom")
rows = [{"opened": "2026-08-24", "age_days": int(os.environ.get("FAKE_AGE", "40")), "artifact": "row-one",
         "owner": "o1", "class": "TECH-DEBT", "overdue": True, "raw_head": os.environ.get("FAKE_HEAD", "h1")},
        {"opened": "2026-09-30", "age_days": 9, "artifact": "fresh", "owner": "o2", "class": "TECH-DEBT", "overdue": False}]
if mode == "b":
    rows.append({"opened": "2026-09-01", "age_days": 38, "artifact": "row-two", "owner": "o3",
                 "class": "TECH-DEBT", "overdue": True})
print(json.dumps({"entries": rows}))
PY
# The escalation hook: the memo asks for the UNCAPPED board (SESSIONSTART_HOOK_MAX_BYTES
# raised); a capped call would show FAKE_ESC_CAPPED, which hides later HIGH groups.
mkdir -p "$TMP/repo/scripts/hooks"
cat > "$TMP/repo/scripts/hooks/escalations_alert_sessionstart.sh" <<'SH'
if [ "${SESSIONSTART_HOOK_MAX_BYTES:-1500}" -ge 1000000 ]; then printf '%s' "${FAKE_ESC_FULL:-}"; else printf '%s' "${FAKE_ESC_CAPPED:-}"; fi
SH

extract() { # $1 start prefix, $2 end prefix
    awk -v s="$1" -v e="$2" 'index($0, s)==1{on=1} index($0, e)==1{on=0} on' "$WRAPPER"
}
extract '# ---- G11_memoize:' 'log "ACTIONABLE:' > "$TMP/pre.sh"
extract '# G11_memoize (continued)' 'if [ $CEXIT -eq 0 ]' > "$TMP/post.sh"
check "pre block extracted from the wrapper" 1 "$([ -s "$TMP/pre.sh" ] && echo 1 || echo 0)"
check "post block extracted from the wrapper" 1 "$([ -s "$TMP/post.sh" ] && echo 1 || echo 0)"

REG_CLEAN='{"dead":[]}'
REG_DEAD='{"dead":[{"id":"organ.x","cure":"session"}]}'
PROP='{"probes":[{"id":"p1","status":"DIVERGED","cure":"owner"},{"id":"p2","status":"RECONCILED"}]}'
ESC_A='{"hookSpecificOutput":{"additionalContext":"BOARD\n  - 1 HIGH\n    RED job-a (x4, latest 2026-10-08)\n  - 79 NORMAL pending in x (context).\n\nRun /escalations for the full board."}}'
ESC_NORMAL_MOVED='{"hookSpecificOutput":{"additionalContext":"BOARD\n  - 1 HIGH\n    RED job-a (x4, latest 2026-10-08)\n  - 91 NORMAL pending in x (context).\n\nRun /escalations for the full board."}}'
ESC_B='{"hookSpecificOutput":{"additionalContext":"BOARD\n  - 2 HIGH\n    RED job-a (x4, latest 2026-10-08)\n    RED job-b (x1, latest 2026-10-09)\n  - 79 NORMAL pending in x (context).\n\nRun /escalations for the full board."}}'
REASONS_BASE="ledger-overdue proprioception:1/2-session-curable escalations-board"
OUTBOX_A='{"exit":1,"reason":"x","counts":{"undispatched":2,"exhausted":1,"older_than_24h":0}}'
OUTBOX_B='{"exit":1,"reason":"x","counts":{"undispatched":2,"exhausted":2,"older_than_24h":0}}'

pre() { # env: REG PROP_IN ESC LEDGER REASONS_IN ACT -> "SPAWN" | "MEMOIZED", then log lines
    { echo "ACTIONABLE=${ACT:-1}; REASONS=\"${REASONS_IN:-$REASONS_BASE}\"; LOG=\"$TMP/healer.log\"; MODEL=m; MAX_WALL_S=1"
      echo 'log() { echo "$*" >> "$LOG"; }; heartbeat() { echo "HB $1" >> "$LOG"; }'
      echo "REG_OUT='${REG:-$REG_CLEAN}'; PROP_JSON='${PROP_IN:-$PROP}'; ESC_OUT='$ESC_A'"  # the hook's capped view
      echo "SESSION_CURABLE=1; NEW_DEAD=\"\"; OUTBOX_OUT='${OUTBOX:-$OUTBOX_A}'"
      cat "$TMP/pre.sh"
      echo 'env | grep -q "^_HM_" && echo "LEAK" >> "$LOG"'
      echo 'echo "SPAWN fp=${FINGERPRINT:+SET} total=$VERDICT_TOTAL"'
    } > "$TMP/driver.sh"
    : > "$TMP/healer.log"
    (cd "$TMP/repo" && HOME="$TMP/home" FAKE_LEDGER="${LEDGER:-a}" FAKE_AGE="${AGE:-40}" FAKE_HEAD="${HEAD_TXT:-h1}" \
        FAKE_ESC_FULL="${ESC:-$ESC_A}" FAKE_ESC_CAPPED="$ESC_A" bash "$TMP/driver.sh" 2>/dev/null) \
        | sed -e 's/^SPAWN.*/SPAWN/' | head -1
}
post() { # $1 session-log text, $2 fingerprint-present(1/0), $3 total
    printf '%s\n' "$1" > "$TMP/session.log"
    { echo "LOG=\"$TMP/healer.log\"; SESSION_LOG=\"$TMP/session.log\"; CEXIT=0; SPAWN_TS_ISO=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      echo "MEMO_STATE=\"$TMP/home/.organism/healer/mini-memo.json\"; VERDICT_TOTAL=$3"
      echo 'log() { echo "$*" >> "$LOG"; }'
      [ "$2" = 1 ] && echo "FINGERPRINT=\"\${FP_IN}\"" || echo 'FINGERPRINT=""'
      cat "$TMP/post.sh"
    } > "$TMP/post_driver.sh"
    (cd "$TMP/repo" && HOME="$TMP/home" FP_IN="$FP" bash "$TMP/post_driver.sh" 2>/dev/null)
}
state_field() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2],"-"))' \
    "$TMP/home/.organism/healer/mini-memo.json" "$1" 2>/dev/null || echo "-"; }
reset() { rm -f "$TMP/home/.organism/healer/mini-memo.json"; }
# ---- 1. first tick: no state -> spawn; fingerprint set; total = one per reason token
reset
check "first tick (no state) spawns" "SPAWN" "$(pre)"
{ echo "ACTIONABLE=1; REASONS=\"$REASONS_BASE\"; LOG=\"$TMP/healer.log\"; MODEL=m; MAX_WALL_S=1"
  echo 'log() { :; }; heartbeat() { :; }'
  echo "REG_OUT='$REG_CLEAN'; PROP_JSON='$PROP'; ESC_OUT='$ESC_A'; SESSION_CURABLE=1; NEW_DEAD=\"\""
  cat "$TMP/pre.sh"; echo 'echo "$FINGERPRINT $VERDICT_TOTAL"'; } > "$TMP/d2.sh"
read -r FP TOTAL < <(cd "$TMP/repo" && HOME="$TMP/home" FAKE_LEDGER=a FAKE_ESC_FULL="$ESC_A" bash "$TMP/d2.sh" 2>/dev/null | tail -1)
check "fingerprint is a sha256" 64 "${#FP}"
check "verdict total = one per reason token" 3 "$TOTAL"
check "prompt carries the HEALER_VERDICT contract" 1 "$(grep -c 'HEALER_VERDICT: cured|incurable|partial <n_cured>/${VERDICT_TOTAL}' "$WRAPPER")"

# ---- 2. verdict recording from a fake session log
post "report text
HEALER_VERDICT: incurable 0/3" 1 3
check "incurable verdict recorded" incurable "$(state_field verdict)"
check "recorded fingerprint is the tick's" "$FP" "$(state_field fingerprint)"
post "report text
HEALER_VERDICT: incurable 0/9" 1 3 ; check "another tick's total is unknown" unknown "$(state_field verdict)"
post "no verdict line at all" 1 3
check "missing verdict line records unknown" unknown "$(state_field verdict)"
check "missing verdict line is logged" 1 "$(grep -c 'verdict-line-missing' "$TMP/healer.log")"
post "HEALER_VERDICT: partial 1/3" 1 3
check "partial verdict recorded" partial "$(state_field verdict)"
check "partial never memoizes" "SPAWN" "$(pre)"
post "HEALER_VERDICT: incurable 0/3" 1 3
rm -f "$TMP/home/.organism/healer/mini-memo.json"
post "HEALER_VERDICT: incurable 0/3" 0 3
check "no fingerprint (convergence) records nothing" "-" "$(state_field verdict)"
post "HEALER_VERDICT: incurable 0/3" 1 3

# ---- 3. the memo decision. Every case re-arms the state first (a fresh incurable
# record, skip streak 0), so a SPAWN can only come from the case's own change and
# never from the skip-streak budget running out.
rearm() { post "HEALER_VERDICT: incurable 0/3" 1 3; }
rearm; check "same fingerprint + incurable -> memoized, no spawn" "" "$(pre)"
check "memoized line is logged" 1 "$(grep -c '^memoized:' "$TMP/healer.log")"
check "memoized tick heartbeats ok" 1 "$(grep -c '^HB ok' "$TMP/healer.log")"
rearm; check "ledger rows only aging (same set) stays memoized" "" "$(AGE=41 pre)"
rearm; check "NORMAL-pending tally moving stays memoized" "" "$(ESC="$ESC_NORMAL_MOVED" pre)"
rearm; check "new dead organ -> spawn" "SPAWN" "$(REG="$REG_DEAD" pre)"
check "no memo input is exported to the session" 0 "$(grep -c '^LEAK' "$TMP/healer.log")"
rearm; check "new HIGH escalation -> spawn" "SPAWN" "$(ESC="$ESC_B" pre)"
rearm; check "ledger overdue set changed -> spawn" "SPAWN" "$(LEDGER=b pre)"
rearm; check "proprioception cure boundary moved -> spawn" "SPAWN" \
    "$(PROP_IN='{"probes":[{"id":"p1","status":"DIVERGED","cure":"session"}]}' pre)"
rearm; check "new reason token -> spawn" "SPAWN" "$(REASONS_IN="$REASONS_BASE main-required-red:ci" pre)"
rearm; check "ledger unreadable -> spawn (fail-open)" "SPAWN" "$(LEDGER=crash pre)"
check "ledger unreadable logs the empty-fingerprint spawn" 1 "$(grep -c 'fail-open, spawning anyway' "$TMP/healer.log")"
rearm; check "convergence (ACTIONABLE=0) never memoizes" "SPAWN" "$(ACT=0 pre)"
rearm; pre >/dev/null; pre >/dev/null; pre >/dev/null
check "skip streak budget (3) is spent -> spawn again" "SPAWN" "$(pre)"

# council cures (2026-10-09): content behind constant tokens, the uncapped board, no export
rearm; check "HIGH change hidden by the hook's byte cap -> spawn" "SPAWN" "$(ESC="$ESC_B" pre)"
rearm; check "board unreadable -> spawn (fail-open)" "SPAWN" "$(ESC='not-json' pre)"
rearm; check "ledger row text changed, same set -> spawn" "SPAWN" "$(HEAD_TXT=h2 pre)"
REASONS_OUT="$REASONS_BASE garuda-outbox-undrained"
{ echo "ACTIONABLE=1; REASONS=\"$REASONS_OUT\"; LOG=\"$TMP/healer.log\"; MODEL=m; MAX_WALL_S=1"
  echo 'log() { :; }; heartbeat() { :; }'
  echo "REG_OUT='$REG_CLEAN'; PROP_JSON='$PROP'; ESC_OUT='$ESC_A'; SESSION_CURABLE=1; NEW_DEAD=\"\"; OUTBOX_OUT='$OUTBOX_A'"
  cat "$TMP/pre.sh"; echo 'echo "$FINGERPRINT $VERDICT_TOTAL"'; } > "$TMP/d3.sh"
read -r FP_OUT TOTAL_OUT < <(cd "$TMP/repo" && HOME="$TMP/home" FAKE_LEDGER=a FAKE_ESC_FULL="$ESC_A" bash "$TMP/d3.sh" 2>/dev/null | tail -1)
check "outbox tick has a fingerprint" 64 "${#FP_OUT}"
rearm_out() { FP="$FP_OUT" post "HEALER_VERDICT: incurable 0/$TOTAL_OUT" 1 "$TOTAL_OUT"; }
rearm_out; check "outbox counts unchanged -> memoized" "" "$(REASONS_IN="$REASONS_OUT" pre)"
rearm_out; check "outbox counts changed -> spawn" "SPAWN" "$(REASONS_IN="$REASONS_OUT" OUTBOX="$OUTBOX_B" pre)"
rearm_out; check "outbox verdict unreadable -> spawn (fail-open)" "SPAWN" "$(REASONS_IN="$REASONS_OUT" OUTBOX='{}' pre)"

# memo tool broken -> check errors -> spawn
rearm
cp "$TMP/repo/scripts/healer_memo.py" "$TMP/healer_memo.real"
printf 'import sys\nif sys.argv[1] == "fingerprint":\n    print("a" * 64)\nsys.exit(2 if sys.argv[1] == "check" else 0)\n' > "$TMP/repo/scripts/healer_memo.py"
check "memo check error -> spawn (fail-open)" "SPAWN" "$(pre)"
check "memo check error is logged fail-open" 1 "$(grep -c 'fail-open, spawning anyway' "$TMP/healer.log")"
cp "$TMP/healer_memo.real" "$TMP/repo/scripts/healer_memo.py"

[ "$FAIL" -eq 0 ] && echo "ALL PASS" || { echo "FAILURES"; exit 1; }
