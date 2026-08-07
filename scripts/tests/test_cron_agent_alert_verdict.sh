#!/usr/bin/env bash
# test_cron_agent_alert_verdict.sh — a lost alert must not buy 30 minutes of silence.
#
# WHY THIS EXISTS (measured on Pro, 2026-08-08)
#   cron-agent.sh's send_telegram() called the notification gateway as
#       python3 tg_notify.py … >/dev/null 2>&1 || true
#       touch "$COOLDOWN_FILE"
#   Both channels discarded, then the 30-minute cooldown armed unconditionally.
#   tg_notify.py can end in six different ways and only ONE of them reached
#   Telegram:
#       sent · deduped · logged · spooled · p0_overflow_spooled · p0_unsent_spooled
#   So an alert that was merely parked also silenced its own successor, and the
#   log kept no record of which of the six had happened.
#
#   The exit code cannot carry this verdict: tg_notify.py's main() returns 0
#   unconditionally — its except branch is commented "NEVER fail the caller",
#   spools best-effort and still returns 0. An rc check would be decorative by
#   construction (W104). The verdict is the status word on STDERR.
#
# WHAT IT PINS
#   guilt     — each non-delivering status leaves the cooldown UNARMED and says so.
#   innocence — sent/deduped still arm it; a fresh cooldown still suppresses; an
#               expired one still lets through. The cure must not make the wrapper
#               chattier, only honest.
#   W104 pin  — a gateway that says "sent" while exiting non-zero still arms the
#               cooldown. If someone later "tidies" this into an rc check, this
#               check is the one that goes red.
#
# Runs anywhere: no network, no real gateway, no real Telegram, no real HOME.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
WRAPPER="$REPO_ROOT/infra/launchagents/wrappers/cron-agent.sh"

[ -f "$WRAPPER" ] || { echo "FAIL: wrapper not found at $WRAPPER"; exit 2; }

failures=0
check() {
  local name="$1" cond="$2"
  if [ "$cond" = "1" ]; then printf '  ok   %s\n' "$name"
  else printf '  FAIL %s\n' "$name"; failures=$((failures + 1)); fi
}
# `case ... in *x*)` inline inside $( ) trips the parser on the unbalanced ')'.
has()   { case "$2" in *"$1"*) return 0 ;; *) return 1 ;; esac; }
yesno() { if "$@"; then echo 1; else echo 0; fi; }
armed()     { [ "$LAST_COOLDOWN_EXISTS" = "1" ]; }
not_armed() { [ "$LAST_COOLDOWN_EXISTS" = "0" ]; }

# ── harness ───────────────────────────────────────────────────────────────────
# Source the LIVE definitions out of the wrapper rather than a copy, so this
# corpus cannot drift into judging a function nobody runs.
#
# log() is a ONE-LINER, so a /^log() {/,/^}/ range would not close on its own
# line — it would run on and swallow send_telegram(), truncating it mid-`case`.
# That produced a first draft where every check "passed" the not-armed assertions
# because the harness never ran at all: a fake world measuring its own poverty
# (W108). Hence the two extractions are separate, and the guard below is fatal.
EXTRACT="$(sed -n '/^log() {/p' "$WRAPPER"
           sed -n '/^_file_mtime() {/,/^}/p' "$WRAPPER"
           sed -n '/^send_telegram() {/,/^}/p' "$WRAPPER")"
poverty_check() {
  local why="$1" cond="$2"
  [ "$cond" = "1" ] && return 0
  echo "HARNESS TOO POOR TO JUDGE: $why" >&2
  echo "(exiting 2 — an unrunnable probe must not report verdicts)" >&2
  exit 2
}
poverty_check "send_telegram() not extracted" "$(yesno has 'send_telegram' "$EXTRACT")"
poverty_check "_file_mtime() not extracted"   "$(yesno has '_file_mtime' "$EXTRACT")"
poverty_check "log() not extracted"            "$(yesno has 'log() {'      "$EXTRACT")"
poverty_check "extraction is not syntactically complete (truncated function?)" \
  "$(printf '%s\n' "$EXTRACT" | bash -n 2>/dev/null && echo 1 || echo 0)"

SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/alertverdict.XXXXXX")"
trap 'rm -rf "$SANDBOX"' EXIT

# One scenario = one fresh world. Returns the log; leaves the cooldown state on
# disk for the caller to inspect.
#   $1 = what the fake gateway prints on stderr ("" = print nothing)
#   $2 = the fake gateway's exit code
#   $3 = "missing" to omit the gateway entirely
#   $4 = age in seconds of a pre-existing cooldown ("" = none)
run_scenario() {
  local reply="$1" grc="$2" mode="${3:-present}" cooldown_age="${4:-}"
  local w; w="$(mktemp -d "$SANDBOX/w.XXXXXX")"
  mkdir -p "$w/fakehome/nuzantara/scripts" "$w/bin"

  if [ "$mode" != "missing" ]; then
    # The gateway lands next to the harness, which is what dirname "$0" resolves
    # to — the same first branch the real wrapper takes.
    cat > "$w/bin/tg_notify.py" <<GW
import sys
r = """$reply"""
if r:
    sys.stderr.write(r + "\n")
sys.exit($grc)
GW
  fi

  local cd_file="$w/job.cooldown"
  if [ -n "$cooldown_age" ]; then
    : > "$cd_file"
    # Backdate it. touch -t needs a wall time; compute it portably.
    local when; when="$(python3 -c "import time;print(time.strftime('%Y%m%d%H%M.%S', time.localtime(time.time()-$cooldown_age)))")"
    touch -t "$when" "$cd_file"
  fi

  cat > "$w/bin/harness.sh" <<HARNESS
#!/usr/bin/env bash
set -uo pipefail
JOB_NAME="probe-job"
LOG_FILE="$w/job.log"
COOLDOWN_FILE="$cd_file"
export HOME="$w/fakehome"
$EXTRACT
send_telegram "a message that must not vanish"
HARNESS
  chmod +x "$w/bin/harness.sh"
  bash "$w/bin/harness.sh" >/dev/null 2>&1

  LAST_LOG="$(cat "$w/job.log" 2>/dev/null || true)"
  LAST_COOLDOWN_EXISTS=0; [ -f "$cd_file" ] && LAST_COOLDOWN_EXISTS=1
  LAST_W="$w"
}

echo "guilt — a status that did NOT reach Telegram leaves the cooldown unarmed:"
for st in logged spooled p0_overflow_spooled p0_unsent_spooled; do
  run_scenario "tg_notify: $st" 0
  check "'$st' -> cooldown NOT armed" "$(yesno not_armed)"
  check "'$st' -> log says it was not delivered, naming the status" \
        "$(yesno eval "has 'ALERT NOT DELIVERED' \"\$LAST_LOG\" && has '$st' \"\$LAST_LOG\"")"
done

echo "guilt — the gateway itself failing is not silence:"
run_scenario "" 127 missing
check "gateway absent -> logged as missing, cooldown NOT armed" \
      "$(yesno eval 'has "gateway missing" "$LAST_LOG" && not_armed')"

run_scenario "Traceback (most recent call last):" 1
check "gateway crashes -> cooldown NOT armed, traceback recorded" \
      "$(yesno eval 'has Traceback "$LAST_LOG" && not_armed')"

echo "innocence — delivery, and intended silence, still arm the cooldown:"
run_scenario "tg_notify: sent" 0
check "'sent' -> cooldown armed" "$(yesno armed)"
run_scenario "tg_notify: deduped" 0
check "'deduped' (an equivalent message already went out) -> cooldown armed" "$(yesno armed)"

echo "the mtime helper — the cooldown gate is only as real as this (W108):"
# `stat -f%m` is BSD; on GNU coreutils -f means --file-system and %m is the mount
# point, so it SUCCEEDS and prints a non-timestamp. An exit-code-keyed fallback
# never fires there and the gate goes silently inert. These two run on whatever
# OS the runner is, which is the point: the assertion below about a 60s-old
# cooldown is only meaningful because this helper works on both.
mt_probe="$(mktemp "$SANDBOX/mt.XXXXXX")"
mt_now="$(bash -c "$EXTRACT"$'\n''_file_mtime "'"$mt_probe"'"')"
check "returns a plausible epoch for a real file (got '${mt_now}')" \
      "$(yesno eval '[ -n "$mt_now" ] && [ "$mt_now" -gt 1700000000 ] 2>/dev/null')"
mt_gone="$(bash -c "$EXTRACT"$'\n''_file_mtime "'"$SANDBOX"'/definitely-absent"')"
check "returns 0 — never a non-numeric — for a file that is not there (got '${mt_gone}')" \
      "$(yesno test "$mt_gone" = "0")"

echo "innocence — the pre-existing cooldown semantics are untouched:"
run_scenario "tg_notify: sent" 0 present 60
check "a 60s-old cooldown still suppresses the send" \
      "$(yesno has 'cooldown active' "$LAST_LOG")"
run_scenario "tg_notify: sent" 0 present 2000
check "a 2000s-old cooldown (>1800s) no longer suppresses" \
      "$(yesno has 'gateway rc=' "$LAST_LOG")"

echo "W104 pin — the REPLY is judged, never the exit code:"
run_scenario "tg_notify: sent" 3
check "'sent' with a non-zero exit still arms the cooldown" "$(yesno armed)"
run_scenario "tg_notify: spooled" 0
check "'spooled' with a ZERO exit still does not" "$(yesno not_armed)"

echo "superscar #3 pin — the status is read as an entity, not a substring:"
run_scenario "tg_notify: internal error (connection reset while sent) — best-effort spooled" 0
check "a free-form error line containing the word 'sent' is NOT read as delivered" \
      "$(yesno not_armed)"

echo "forensics — the gateway's reply reaches the log every time:"
run_scenario "tg_notify: sent" 0
check "the reply is recorded verbatim in the job log" \
      "$(yesno has 'reply=tg_notify: sent' "$LAST_LOG")"

if [ "$failures" -eq 0 ]; then echo "PASS (all checks)"; exit 0; fi
echo "FAIL ($failures check(s))"; exit 1
