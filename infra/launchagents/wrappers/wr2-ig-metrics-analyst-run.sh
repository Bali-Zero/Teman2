#!/bin/bash
# WR2 IG Metrics Analyst — weekly run wrapper
# Cron: Monday 06:00 WITA via com.balizero.wr2.ig-metrics-analyst.weekly.plist
# Reads engagement metrics from human-review-queue.json + wr2-episodic.db,
# correlates with carousel attributes, proposes amendments to
# ~/.claude/skills/bali-zero-brand/_proposed-amendments/<date>-ig-insights.md.
# Spec: .claude/agents/wr2-ig-metrics-analyst.md (Sonnet 4.6 frontmatter).
# Phase B Phase D — created 2026-05-10 to close ciclo-vitale loop.
#
# Sonnet-5 runtime proof gap (PENDING-ARMS 2026-07-03/07-06): this wrapper called
# `claude` directly with no explicit "used: <tier>" log line, unlike
# regulatory-watcher-run.sh (via claude-cascade.sh) — structurally unprovable
# which model actually answered a given run. Fix: log an explicit provenance
# line keyed off the claude exit code. The agent stays Claude-only because it
# needs Read/Bash tools, but rotates across all configured OAuth seats.
#
# B7 wall-clock timeout + loud logging (2026-07-14, WR2 deep audit §4/§10.7):
# a run hung 28h+ until externally SIGTERM'd, and BOTH log files were
# completely empty for the entire hang — nothing in this wrapper bounded the
# child's runtime, and `claude -p` in non-streaming mode writes nothing to
# stdout/stderr until the turn completes, so a hung child was structurally
# indistinguishable from "still working" (the wrapper itself never emitted a
# byte while waiting on `wait`/redirected `>>`). Fix: background the child,
# poll it with a heartbeat (log is never silent even if the child never
# writes anything) plus a hard wall-clock ceiling (SIGTERM, escalate to
# SIGKILL after a grace period, exit 124) — same convention as
# scripts/cron-wrapper.sh's bash-watchdog fallback for machines without
# gtimeout/timeout, and the same "background + sleep + kill" idiom this file
# already used for the agy health-check below. N=7200s (2h) — generous: the
# analyst legitimately reads a full carousel+metrics corpus. Override via
# WR2_IG_METRICS_TIMEOUT_SECS.

set -euo pipefail

LOGDIR="${HOME}/logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/wr2-ig-metrics-analyst.log"
ERR="$LOGDIR/wr2-ig-metrics-analyst.err.log"

TIMEOUT_SECS="${WR2_IG_METRICS_TIMEOUT_SECS:-7200}"
HEARTBEAT_SECS=300
POLL_SECS="${WR2_IG_METRICS_POLL_SECS:-5}"
KILL_GRACE_SECS="${WR2_IG_METRICS_KILL_GRACE_SECS:-10}"
if [ "$POLL_SECS" -lt 1 ]; then
  POLL_SECS=1
fi

# G2_heartbeat — sidecar EVERY exit path (Esiste≠Armato: prove life, every
# run — a fleet-wide dead-organ scan reads this sidecar, not the log tail).
# Wired into on_exit_voice() below so it fires on both the early EXIT trap
# and cleanup_active_claude's later replacement (which itself calls
# on_exit_voice — see that trap's own comment on why the voice must be
# carried forward rather than re-declared).
ORGAN_ID="wr2.ig_metrics_analyst_weekly"
SIDECAR_DIR="${HOME}/.organism/last_seen"
PIDFILE=""
heartbeat() { # $1 status $2 note
  mkdir -p "$SIDECAR_DIR" 2>/dev/null || true
  printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" > "$SIDECAR_DIR/$ORGAN_ID.json" 2>/dev/null || true
}

# --- FAILURE GATEWAY (2026-08-08) ---------------------------------------------
# Until today this wrapper had ZERO gateway references and no voice at all.
# launchd invokes it DIRECTLY (`/bin/bash <script>` in
# com.balizero.wr2.ig-metrics-analyst.weekly — no cron-runner.sh, no
# wr2-cron-wrapper.sh), so nothing wrote a receipt and nothing read its exit
# code; `missed_runs_alerter` watches WarRoom DB rows, not launchd labels, and
# knows nothing about this job; and no probe watches the freshness of its output
# dir. Three consecutive weekly runs died with no surface anywhere able to
# notice — W81/W108 in its plainest form.
#
# Routed through the ONE gateway (tg_notify.py owns token resolution, tiering and
# dedup), like the sibling wr2-external-bench-run.sh. Two deliberate choices:
#   - the interpreter is ABSOLUTE (W108): the alarm must not share a failure mode
#     with what it reports, and launchd hands this job a PATH whose FIRST entry is
#     a user-writable ~/.local/bin;
#   - a missing gateway is LOGGED, never silent — "armed at nothing" and "fired"
#     must not look the same afterwards. That branch writes its own line and no
#     `notify rc=`, because there was no call to have an rc; whenever the gateway
#     IS invoked, its rc is written whether it worked or not.
# It can never be the thing that kills the run — and getting that right needed the
# final log line to be written BEFORE errexit is restored: with `set -e` back on, a
# `$LOG` that has become unwritable (full disk, wrong owner) would abort the
# CALLER from inside the reporting code, which is the alarm killing the run it came
# to report. The gateway itself is bounded, so this cannot hang: tg_notify.py
# calls `urlopen(..., timeout=6)` and its relay fallback `subprocess.run(...,
# timeout=15)` — measured, not assumed.
NOTIFIED=0
notify_failure() {
  local msg="$1"
  local dedup="$2"
  local gateway notify_py rc had_errexit=0
  NOTIFIED=1
  # Disarm for the WHOLE body, not just around the gateway call: the
  # gateway-MISSING branch writes to $ERR and returns, and with errexit still
  # armed an unwritable $ERR would abort the caller from inside the alarm too.
  case $- in *e*) had_errexit=1 ;; esac
  set +e
  notify_py=/opt/homebrew/bin/python3
  [ -x "$notify_py" ] || notify_py=/usr/bin/python3
  gateway="$(dirname "$0")/tg_notify.py"
  [ -f "$gateway" ] || gateway="${HOME}/nuzantara/scripts/tg_notify.py"
  if [ ! -f "$gateway" ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] gateway MISSING (${gateway}) — alert NOT sent: ${msg}" >> "$ERR"
    if [ "$had_errexit" -eq 1 ]; then set -e; fi
    return 0
  fi
  "$notify_py" "$gateway" --tier p0 --source wr2-ig-metrics-analyst \
    --dedup-key "$dedup" -- "$msg" >> "$LOG" 2>&1
  rc=$?
  # Order matters: log FIRST, restore errexit AFTER. Reversed, an unwritable $LOG
  # aborts the caller from inside the alarm.
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] telegram notify rc=${rc} (gateway=${gateway}, python=${notify_py})" >> "$LOG"
  if [ "$had_errexit" -eq 1 ]; then set -e; fi
  return 0
}

# Voice of last resort. Naming the two KNOWN failure exits is not enough: under
# `set -e` this script can also die at any un-guarded line — a failing `mkdir`,
# `python3` absent so the pre-flight assignment aborts, `mktemp` failing because
# TMPDIR does not exist — and every one of those was as silent as the errexit bug
# this commit cures. Curing only the exits I happened to think of is the W107
# mistake (one mouth out of five) at the scale of a single organ. So: any non-zero
# exit that has NOT already spoken gets a message naming that it died WITHOUT a
# diagnosis, which is a different and more alarming fact than a named failure.
#
# Deliberate limit, declared rather than hidden — and stated by MEASUREMENT,
# because the first version of this very comment was false. It claimed a
# non-integer WR2_IG_METRICS_POLL_SECS would make `[ … -lt 1 ]` fail and errexit
# take the script out before any voice existed. It does not: that test sits inside
# an `if`, where errexit is EXEMPT (measured: `set -e; P=nope; if [ "$P" -lt 1 ];`
# prints to stderr, rc=0, script alive). The same test OUTSIDE an `if` exits 2.
# So the sentence written to be MORE precise was the wrong one — the correct
# statement is narrow: the ONLY thing above this trap that can kill the script is
# the bare `mkdir -p "$LOGDIR"`. A bad POLL_SECS survives to
# `$((elapsed + sleep_step))`, which is BELOW the trap and therefore has a voice.
on_exit_voice() {
  local rc="$1"
  rm -f "${PIDFILE:-}" 2>/dev/null || true
  if [ "$rc" -eq 0 ]; then
    heartbeat "ok" "exit=0"
  else
    heartbeat "error" "exit=${rc}"
  fi
  if [ "$rc" -eq 0 ] || [ "$NOTIFIED" -eq 1 ]; then
    return 0
  fi
  notify_failure "⚠️ wr2-ig-metrics-analyst exited ${rc} with NO diagnosis on $(hostname -s) — it died outside every path that knows how to explain itself. Weekly IG-insights amendment NOT produced. See ${LOG} / ${ERR}" \
    "wr2-ig-metrics-analyst:undiagnosed:$(date +%Y-W%V):$(hostname -s)"
  return 0
}
# Per-signal exit codes, and HUP included. launchd's own path is SIGTERM, but a
# manual run over a dropped ssh gets SIGHUP, which nothing trapped before today:
# the shell dies, the EXIT trap reads `$?` as 0 (measured — a bash killed by a
# signal runs its EXIT trap with `$?` = 0) and the voice stays silent for a run cut
# off mid-flight. Codes are conventional 128+signum instead of the old blanket 130
# (which is SIGINT's, and was reported for SIGTERM too), so the launchd status
# names what actually happened. SIGKILL stays outside any trap by definition —
# declared, not covered.
signal_exit() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] killed by SIG${1} — exiting ${2}" >> "$ERR"
  on_exit_voice "$2"
  exit "$2"
}
# Installed HERE, before the first line that can fail, and re-installed later by
# cleanup_active_claude (which REPLACES these and therefore has to carry the voice
# itself — a `trap ... EXIT` written later silently unarms this one).
trap 'on_exit_voice $?' EXIT
trap 'signal_exit HUP 129' HUP
trap 'signal_exit INT 130' INT
trap 'signal_exit TERM 143' TERM

# G5_kill_switch — operator stop without uninstall (default enabled).
if [ "${WR2_IG_METRICS_ANALYST_ENABLED:-true}" = "false" ]; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] kill switch WR2_IG_METRICS_ANALYST_ENABLED=false — exiting" >> "$LOG"
  exit 0
fi

# G10_single_instance — the cascade below can legitimately run close to the
# full 2h budget; a pidfile turns a launchd overlap into a clean skip instead
# of two Claude cascades racing on the same OAuth seats. Cleanup lives in
# on_exit_voice (fires on both the early trap and cleanup_active_claude's
# later replacement) rather than a second `trap ... EXIT` here, which would
# be silently unarmed the moment cleanup_active_claude installs its own.
PIDFILE="/tmp/nuzantara-wr2-ig-metrics-analyst.pid"
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] previous run still alive (pid $(cat "$PIDFILE")) — skipping" >> "$LOG"
  exit 0
fi
echo $$ > "$PIDFILE"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] wr2-ig-metrics-analyst starting" >> "$LOG"

# Source secrets for Gemini OAuth + any future env
if [ -f "${HOME}/.nuzantara-secrets.env" ]; then
  set -a
  # shellcheck source=/dev/null
  source "${HOME}/.nuzantara-secrets.env"
  set +a
fi

# Pre-flight: do we have ≥10 published carousels with metrics?
PUBLISHED_COUNT=$(python3 -c "
import json
try:
    with open('${HOME}/nuzantara/apps/war-room/output/queue/human-review-queue.json') as f:
        data = json.load(f)
    items = data.get('items', data) if isinstance(data, dict) else data
    n = sum(1 for i in items if i.get('state') in ('published', 'published_with_edits') and (i.get('engagement_metrics') or {}).get('likes') is not None)
    print(n)
except Exception as e:
    # NOT 0 (2026-08-08). Printing 0 on any exception made 'the queue file is
    # gone / moved / corrupt' indistinguishable from 'fewer than 10 carousels
    # published', and the second of those exits 0 in silence after writing an
    # insufficient-data stub. So a broken path would have parked this organ in a
    # permanent, well-documented, entirely wrong 'not enough data yet' — the
    # W114 shape, where an empty measurement means either 'all present' or 'the
    # check never ran'. Name the cause and let the caller alarm.
    print('ERR:%s' % type(e).__name__)
")

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] published-with-metrics count: $PUBLISHED_COUNT" >> "$LOG"

case "$PUBLISHED_COUNT" in
  ERR:*)
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] pre-flight could NOT read the review queue (${PUBLISHED_COUNT}) — this is not 'no data', it is 'no measurement'" >> "$ERR"
    notify_failure "⚠️ wr2-ig-metrics-analyst: review queue UNREADABLE (${PUBLISHED_COUNT}) on $(hostname -s) — cannot tell 'not enough data' from 'no file'. Amendment NOT produced." \
      "wr2-ig-metrics-analyst:queue-unreadable:$(date +%Y-W%V):$(hostname -s)"
    exit 66
    ;;
esac

if [ "$PUBLISHED_COUNT" -lt 10 ]; then
  STUB="${HOME}/.claude/skills/bali-zero-brand/_proposed-amendments/$(date +%Y-%m-%d)-ig-insights-insufficient-data.md"
  cat > "$STUB" <<EOF
# IG Insights — Insufficient Data — $(date +%Y-%m-%d)

**Run**: weekly cron Monday 06:00 WITA
**Published+metrics count**: $PUBLISHED_COUNT (threshold: ≥10)
**Action**: STOP. No analysis run. Re-evaluate next week.

Once Damar marks ≥10 carousels as 'published' with IG URLs and the daily ig-scraper
fills engagement_metrics, the analyst will produce real amendments.

## Bootstrap path (2026-05-10)
First-prod publish: kep71-spt-extension-test6-FIRSTPROD (DAHJRpG2QIs).
N=1 — need 9 more publishes to unlock analysis.
EOF
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] insufficient data — stub written: $STUB" >> "$LOG"
  exit 0
fi

# --- GEMINI HEALTH-CHECK (2026-06-23, fixes the agy-hang bug) -----------------
# The agent's Step-2 calls `agy -p` for 1M-context analysis. When agy is NOT logged in,
# it opens an OAuth flow and BLOCKS (CPU 0%, up to 5m timeout per call) instead of failing
# cleanly — the agent then hangs and never reaches its local-stats fallback. We probe agy
# here with a hard 25s ceiling; if it does not return a clean answer, we tell the agent
# explicitly to SKIP Gemini and go straight to the local Python/jq fallback path.
#
# 2026-07-14 zombie fix: the previous watchdog only `kill $AGY_PID` — the exact
# PID named after backgrounding the `echo | agy` pipeline. If agy forks a
# detached grandchild that keeps the pipe's write-end open, agy itself dies on
# the kill but the command-substitution's read() blocks forever waiting for
# EOF from that orphaned descendant (live incident: a 32h zombie found+killed
# on 2026-07-14). Fix: no pipe at all (prompt goes in via a temp file, so
# capture never depends on every fd holder closing), agy runs as the sole/
# first process of its own job so `set -m` gives it its own process group
# (PGID == its own PID), and the watchdog kills the WHOLE group
# (`kill -- -$PGID`, TERM then KILL) — no descendant can outlive the timeout.
#
# 2026-08-08 errexit fix (W101, fourth generation). Read the tenses here: this
# paragraph describes the code AS IT WAS, because after the fix the subshell exits
# agy's own status and a healthy probe therefore exits 0. As written before today,
# the probe subshell ran under this script's own `set -e`, and a subshell INHERITS
# errexit — and BOTH of its exits were non-zero by construction:
#   - agy DOWN -> `wait "$AGY_PID"` returned agy's own non-zero code;
#   - agy UP   -> `wait "$WATCHDOG_PID"` returned 143, the watchdog WE just killed.
# So the block aborted the entire script, always, and nothing after it ever ran.
# Measured on the live log (Pro): the 2026-07-19, 07-26 and 08-02 runs each stop
# dead between "published-with-metrics count" and the health-check verdict —
# zero further lines, .err.log untouched since 2026-06-23, last complete run
# 2026-06-28. The DOWN branch — the local-fallback hint, the whole reason this
# probe exists — was unreachable on the exact path it was written for.
# Fix: disarm errexit around the probe (OUTSIDE *and* INSIDE — the subshell
# inherits it) and judge by the CAPTURED rc, never by having survived the line.
GEMINI_HINT=""
# Overridable ONLY so the corpus can drive the probe; the default is the live Pro
# path and is what every real run uses. Without the override the guilt test is
# unwritable on M5, where this path does not exist at all (user `balizero`), so
# `[ -x ]` is false, the whole block is skipped, and the dev machine is
# structurally incapable of reproducing the red (W108 GOTCHA).
AGY="${WR2_IG_AGY_BIN:-/Users/nuzantara/.local/bin/agy}"
if [ -x "$AGY" ]; then
  AGY_PROMPT="$(mktemp "${TMPDIR:-/tmp}/wr2-ig-agy-prompt.XXXXXX")"
  AGY_TMP="$(mktemp "${TMPDIR:-/tmp}/wr2-ig-agy-health.XXXXXX")"
  echo "reply with exactly: AGYUP" > "$AGY_PROMPT"
  set +e
  (
    set +e
    set -m
    # `-p`/`--print` TAKES A VALUE (measured live 2026-08-13, both forms exit
    # 0): `-p --print-timeout 20s < file` binds the literal string
    # "--print-timeout" as the prompt and never reads $AGY_PROMPT from stdin —
    # this probe was answering NOTHING and therefore reporting DOWN on every
    # run. Prompt must be `-p`'s own argv value. NOTE: agy v1.1.12 has no
    # stdin path, so the prompt is now `ps`-visible while the process runs —
    # harmless here (fixed literal "reply with exactly: AGYUP" health probe,
    # no client data).
    "$AGY" -p "$(cat "$AGY_PROMPT")" --print-timeout 20s > "$AGY_TMP" 2>&1 &
    AGY_PID=$!
    (
      sleep 25
      kill -TERM -- -"$AGY_PID" 2>/dev/null
      sleep 2
      kill -KILL -- -"$AGY_PID" 2>/dev/null
    ) &
    WATCHDOG_PID=$!
    wait "$AGY_PID" 2>/dev/null
    AGY_RC=$?
    kill "$WATCHDOG_PID" 2>/dev/null
    wait "$WATCHDOG_PID" 2>/dev/null
    # Propagate agy's OWN status, not the watchdog reap's: without this explicit
    # exit the captured rc is always the `wait` on the watchdog we killed (143),
    # which says nothing about the thing being probed.
    exit "$AGY_RC"
  ) 2>/dev/null
  AGY_PROBE_RC=$?
  set -e
  AGY_OUT="$(cat "$AGY_TMP" 2>/dev/null || true)"
  rm -f "$AGY_PROMPT" "$AGY_TMP"
  # BOTH conditions, not just the answer. Logging `probe_rc` without judging it
  # would have been decoration: agy can print `AGYUP` and then exit non-zero, or
  # be killed mid-flight by the 25s watchdog having already emitted the token, and
  # the old test called both of those UP — then the agent walks into a Gemini that
  # is not there, which is the whole failure this probe exists to prevent. This is
  # also what makes the watchdog-timeout path correct for free: a killed agy exits
  # by signal, so rc != 0 and the verdict is DOWN.
  if [ "$AGY_PROBE_RC" -eq 0 ] && printf '%s' "$AGY_OUT" | grep -qi 'AGYUP'; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] gemini health-check: UP (probe_rc=0)" >> "$LOG"
  else
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] gemini health-check: DOWN (agy not logged in / unreachable, probe_rc=${AGY_PROBE_RC}) — instructing local fallback" >> "$LOG"
    GEMINI_HINT=" IMPORTANT: agy/Gemini is NOT available right now (auth required or unreachable). DO NOT call agy at Step 2 — skip it and use the LOCAL statistical fallback (Python/jq on the corpus) directly, and mark partial:true. Do not block waiting for Gemini."
  fi
else
  GEMINI_HINT=" IMPORTANT: agy binary not found — use the LOCAL statistical fallback at Step 2, mark partial:true."
fi

# Spawn Claude agent (Sonnet 5) per spec frontmatter. Each OAuth seat gets a
# bounded attempt; auth/quota/empty failures rotate to the next seat while the
# aggregate worst-case stays within the original two-hour budget.
#
# G6_spawn_hardened — TCC is PER-BINARY (W84): launchd granting bash access to
# a path says nothing about the node binary behind `claude`. This is
# diagnostic-only (log the context, never gate on it) so a sandboxed/mocked
# HOME used by this wrapper's own test corpus (test_wr2_ig_metrics_analyst_wrapper.sh)
# is not mistaken for a TCC-denied production host.
if [ -z "${SSH_CONNECTION:-}" ]; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] no SSH_CONNECTION — running in direct launchd/local context" >> "$LOG"
fi
cd "${HOME}/nuzantara"
CLAUDE_PROMPT="Use the wr2-ig-metrics-analyst agent to run the weekly IG metrics analysis. Follow the spec in .claude/agents/wr2-ig-metrics-analyst.md exactly. Output the proposed amendment file path on the last line.${GEMINI_HINT}"

CLAUDE_BIN="${WR2_IG_CLAUDE_BIN:-$(command -v claude || true)}"
if [ -z "$CLAUDE_BIN" ]; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] claude binary not found" >> "$ERR"
  notify_failure "⚠️ wr2-ig-metrics-analyst: claude binary not found (exit=127) on $(hostname -s). Weekly IG-insights amendment NOT produced." \
    "wr2-ig-metrics-analyst:nobin:$(date +%Y-W%V):$(hostname -s)"
  exit 127
fi
MAX_CLAUDE_ATTEMPTS=7
DEFAULT_ACCOUNT_TIMEOUT_SECS=$((TIMEOUT_SECS / MAX_CLAUDE_ATTEMPTS))
if [ "$DEFAULT_ACCOUNT_TIMEOUT_SECS" -lt 1 ]; then
  DEFAULT_ACCOUNT_TIMEOUT_SECS=1
fi
# MEASURED FLOOR, not arithmetic (2026-08-08). `TIMEOUT_SECS / MAX_CLAUDE_ATTEMPTS`
# is 7200/7 = 1028s, and the only successful full run in this organ's whole log
# took **1065s** (2026-06-28: `starting` 22:07:00 -> `done` 22:24:45) — the last
# run that actually worked would be SIGTERM'd 37 seconds before finishing. That
# never bit because the errexit bug killed the script before the cascade was ever
# reached; curing that bug is exactly what makes this ceiling reachable for the
# first time, and shipping the cure without this would have revived the organ into
# a louder corpse: killed at 17 min on all seven seats, then a weekly P0.
# The aggregate is already bounded by CASCADE_DEADLINE and run_claude_account
# clamps each attempt to what remains, so the per-attempt number does not need to
# divide the total — it needs to exceed a real run. 2700s is ~2.5x the observed
# worst case with room for the corpus to grow (45 -> 50 published carousels since).
# What re-measures it: the `starting` / `done (exit=…)` pair in this organ's log.
ACCOUNT_TIMEOUT_MIN_SECS="${WR2_IG_METRICS_ACCOUNT_TIMEOUT_MIN_SECS:-2700}"
if [ "$DEFAULT_ACCOUNT_TIMEOUT_SECS" -lt "$ACCOUNT_TIMEOUT_MIN_SECS" ]; then
  DEFAULT_ACCOUNT_TIMEOUT_SECS="$ACCOUNT_TIMEOUT_MIN_SECS"
fi
if [ "$DEFAULT_ACCOUNT_TIMEOUT_SECS" -gt "$TIMEOUT_SECS" ]; then
  DEFAULT_ACCOUNT_TIMEOUT_SECS="$TIMEOUT_SECS"
fi
ACCOUNT_TIMEOUT_SECS="${WR2_IG_METRICS_ACCOUNT_TIMEOUT_SECS:-$DEFAULT_ACCOUNT_TIMEOUT_SECS}"
if [ "$ACCOUNT_TIMEOUT_SECS" -lt 1 ]; then
  ACCOUNT_TIMEOUT_SECS=1
fi
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] cascade budget: total=${TIMEOUT_SECS}s max_attempts=${MAX_CLAUDE_ATTEMPTS} account_timeout=${ACCOUNT_TIMEOUT_SECS}s" >> "$LOG"
CASCADE_DEADLINE=$(( $(date +%s) + TIMEOUT_SECS ))
ACTIVE_CLAUDE_PID=""
ACTIVE_CLAUDE_PGID=""

terminate_claude_group() {
  local pgid="$1"
  if kill -TERM -- -"$pgid" 2>/dev/null; then
    sleep "$KILL_GRACE_SECS"
    # The group leader may already be gone while a descendant ignored TERM.
    kill -KILL -- -"$pgid" 2>/dev/null || true
  fi
}

cleanup_active_claude() {
  # First line, before anything can clobber it: this is also the script's exit
  # status when we get here from the EXIT trap.
  local rc="${1:-$?}"
  trap - EXIT HUP INT TERM
  if [ -n "$ACTIVE_CLAUDE_PGID" ]; then
    terminate_claude_group "$ACTIVE_CLAUDE_PGID"
  fi
  if [ -n "$ACTIVE_CLAUDE_PID" ]; then
    wait "$ACTIVE_CLAUDE_PID" 2>/dev/null || true
  fi
  # This trap REPLACED the early `trap 'on_exit_voice $?' EXIT`, so it has to
  # carry the voice or installing it would have unarmed it — a cure that deletes
  # another cure by being written later in the file.
  on_exit_voice "$rc"
  if [ -n "${1:-}" ]; then
    exit "$rc"
  fi
}
trap cleanup_active_claude EXIT
# An explicit code, never `$?`: on an external SIGTERM (the 28h hang of 2026-07-14
# was killed exactly that way) `$?` can be 0, and a voice that reads 0 stays quiet
# for the single incident that most needs reporting. One trap per signal so the
# reported status names the signal (the old single line reported SIGINT's 130 for
# a SIGTERM too), and HUP is covered here as well as in the early phase — these
# lines REPLACE the early traps, so anything missing from them is unarmed.
trap 'cleanup_active_claude 129' HUP
trap 'cleanup_active_claude 130' INT
trap 'cleanup_active_claude 143' TERM

claude_stderr_retryable() {
  local stderr_file="$1"
  grep -qiE \
    'rate.?limit|too many requests|(^|[^0-9/])429([^0-9/]|$)|exhausted|quota|usage limit|weekly limit|hit your limit|authentication (failed|required|expired)|auth required|login required|please (log in|login)|not logged in|not authenticated|invalid[_ ](grant|token)|token[_ ]revoked|refresh_token|unauthori[sz]ed|(^|[^0-9/])401([^0-9/]|$)' \
    "$stderr_file"
}

claude_stdout_retryable() {
  local stdout_file="$1"
  python3 - "$stdout_file" <<'PY'
import json
import re
import sys

text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
broad = re.compile(
    r"rate.?limit|too many requests|(?<![\d/])429(?![\d/])|exhausted|quota|"
    r"usage limit|weekly limit|hit your limit|authentication "
    r"(?:failed|required|expired)|auth required|login required|"
    r"please (?:log in|login)|not logged in|not authenticated|"
    r"invalid[_ ](?:grant|token)|token[_ ]revoked|refresh_token|"
    r"unauthori[sz]ed|(?<![\d/])401(?![\d/])",
    re.I,
)
whole = re.compile(
    r"\s*(?:(?:error|fatal)(?:\s*[:\-]\s*|\s+))?"
    r"(?:rate.?limit(?:ed| exceeded)?|too many requests|"
    r"429(?:\s+too many requests)?|quota (?:exceeded|exhausted)|"
    r"usage limit(?: reached| exceeded)?|weekly limit(?: reached| exceeded)?|"
    r"hit your limit|authentication (?:failed|required|expired)|auth required|"
    r"login required|please (?:log in|login)|not logged in|not authenticated|"
    r"invalid[_ ](?:grant|token)|token[_ ]revoked|refresh_token(?:_reused)?|"
    r"unauthori[sz]ed|401(?: unauthori[sz]ed)?)"
    r"(?:[\s:.,;\-].{0,240})?\s*",
    re.I | re.S,
)
try:
    payload = json.loads(text)
except (json.JSONDecodeError, TypeError):
    payload = None
is_error = False
if isinstance(payload, dict):
    result = payload.get("result")
    result_kind = ""
    if isinstance(result, dict):
        result_kind = str(
            result.get("type") or result.get("status") or result.get("subtype") or ""
        ).lower()
    envelope_kind = str(payload.get("type") or payload.get("status") or "").lower()
    is_error = (
        payload.get("is_error") is True
        or envelope_kind in {"error", "failed", "failure"}
        or (
            envelope_kind == "result"
            and payload.get("subtype") not in (None, "success")
        )
        or result_kind in {"error", "failed", "failure"}
    )
retryable = (
    bool(is_error and broad.search(json.dumps(payload, ensure_ascii=False)))
    or bool(whole.fullmatch(text))
)
raise SystemExit(0 if retryable else 1)
PY
}

claude_retryable_files() {
  claude_stderr_retryable "$2" || claude_stdout_retryable "$1"
}

run_claude_account() {
  local label="$1"
  local token="$2"
  local attempt_out attempt_err elapsed last_heartbeat sleep_step timed_out claude_pid
  local remaining=$(( CASCADE_DEADLINE - $(date +%s) ))
  if [ "$remaining" -le 0 ]; then
    return 124
  fi
  local attempt_budget="$ACCOUNT_TIMEOUT_SECS"
  if [ "$remaining" -lt "$attempt_budget" ]; then
    attempt_budget="$remaining"
  fi
  attempt_out="$(mktemp "${TMPDIR:-/tmp}/wr2-ig-claude-out.XXXXXX")"
  attempt_err="$(mktemp "${TMPDIR:-/tmp}/wr2-ig-claude-err.XXXXXX")"

  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] trying ${label}" >> "$LOG"
  local oauth_env=(env)
  local provider_var
  while IFS= read -r provider_var; do
    case "$provider_var" in
      CLAUDE_CODE_OAUTH_TOKEN*|CLAUDE_CODE_USE_*|ANTHROPIC_*|AWS_*|VERTEX_AI_*|\
      OPENAI_*|OPENROUTER_*|GEMINI_*|GOOGLE_API_KEY|\
      GOOGLE_APPLICATION_CREDENTIALS|CLOUD_ML_REGION|DEEPSEEK_*|\
      TOGETHER_*|FIREWORKS_*|MISTRAL_*|COHERE_*|GROQ_*|XAI_*|PERPLEXITY_*)
        oauth_env+=(-u "$provider_var")
        ;;
    esac
  done < <(compgen -e)
  set -m
  if [ -n "$token" ]; then
    "${oauth_env[@]}" CLAUDE_CODE_OAUTH_TOKEN="$token" \
      "$CLAUDE_BIN" -p \
      --model claude-sonnet-5 \
      --permission-mode bypassPermissions \
      --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
      --max-budget-usd "${WR2_IG_MAX_BUDGET_USD:-10}" \
      "$CLAUDE_PROMPT" < /dev/null > "$attempt_out" 2> "$attempt_err" &
  else
    "${oauth_env[@]}" -u CLAUDE_CODE_OAUTH_TOKEN \
      "$CLAUDE_BIN" -p \
      --model claude-sonnet-5 \
      --permission-mode bypassPermissions \
      --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
      --max-budget-usd "${WR2_IG_MAX_BUDGET_USD:-10}" \
      "$CLAUDE_PROMPT" < /dev/null > "$attempt_out" 2> "$attempt_err" &
  fi
  claude_pid=$!
  ACTIVE_CLAUDE_PID="$claude_pid"
  ACTIVE_CLAUDE_PGID="$claude_pid"
  set +m

  elapsed=0
  last_heartbeat=0
  timed_out=0
  while kill -0 "$claude_pid" 2>/dev/null; do
    if [ "$elapsed" -ge "$attempt_budget" ]; then
      echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] ${label} TIMEOUT after ${attempt_budget}s — sending SIGTERM to process group $claude_pid" >> "$LOG"
      terminate_claude_group "$claude_pid"
      timed_out=1
      break
    fi
    sleep_step="$POLL_SECS"
    if [ $((elapsed + sleep_step)) -gt "$attempt_budget" ]; then
      sleep_step=$((attempt_budget - elapsed))
    fi
    sleep "$sleep_step"
    elapsed=$((elapsed + sleep_step))
    if kill -0 "$claude_pid" 2>/dev/null && \
       [ $((elapsed - last_heartbeat)) -ge "$HEARTBEAT_SECS" ]; then
      echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] ${label} still running (${elapsed}s elapsed, pid $claude_pid)" >> "$LOG"
      last_heartbeat="$elapsed"
    fi
  done

  CLAUDE_EXIT=0
  wait "$claude_pid" 2>/dev/null && CLAUDE_EXIT=0 || CLAUDE_EXIT=$?
  # Reap any background descendant the CLI left in its dedicated group.
  terminate_claude_group "$claude_pid"
  ACTIVE_CLAUDE_PID=""
  ACTIVE_CLAUDE_PGID=""
  if [ "$timed_out" -eq 1 ]; then
    CLAUDE_EXIT=124
  fi

  if [ "$CLAUDE_EXIT" -eq 124 ] || \
     { [ "$CLAUDE_EXIT" -eq 0 ] && ! grep -q '[^[:space:]]' "$attempt_out"; } || \
     claude_retryable_files "$attempt_out" "$attempt_err"; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] ${label} unavailable (exit=${CLAUDE_EXIT}) — trying next account" >> "$ERR"
    rm -f "$attempt_out" "$attempt_err"
    return 98
  fi
  if [ "$CLAUDE_EXIT" -eq 0 ]; then
    cat "$attempt_out" >> "$LOG"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] used: ${label} claude-sonnet-5 (exit=0)" >> "$LOG"
    rm -f "$attempt_out" "$attempt_err"
    return 0
  fi

  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] ${label} failed (exit=${CLAUDE_EXIT})" >> "$ERR"
  rm -f "$attempt_out" "$attempt_err"
  return "$CLAUDE_EXIT"
}

CLAUDE_EXIT=98
CLAUDE_LABELS=()
CLAUDE_TOKENS=()
for token_var in CLAUDE_CODE_OAUTH_TOKEN_1 CLAUDE_CODE_OAUTH_TOKEN_2 CLAUDE_CODE_OAUTH_TOKEN_3 CLAUDE_CODE_OAUTH_TOKEN_4 CLAUDE_CODE_OAUTH_TOKEN_5 CLAUDE_CODE_OAUTH_TOKEN_6 CLAUDE_CODE_OAUTH_TOKEN; do
  token_value="${!token_var:-}"
  [ -z "$token_value" ] && continue
  duplicate=0
  for seen_token in "${CLAUDE_TOKENS[@]:-}"; do
    [ "$seen_token" = "$token_value" ] && duplicate=1
  done
  if [ "$duplicate" -eq 0 ]; then
    CLAUDE_LABELS+=("$token_var")
    CLAUDE_TOKENS+=("$token_value")
  fi
done

for token_index in "${!CLAUDE_LABELS[@]}"; do
  if run_claude_account "${CLAUDE_LABELS[$token_index]}" "${CLAUDE_TOKENS[$token_index]}"; then
    CLAUDE_EXIT=0
    break
  else
    attempt_rc=$?
    if [ "$attempt_rc" -ne 98 ]; then
      CLAUDE_EXIT="$attempt_rc"
      break
    fi
  fi
done

if [ "$CLAUDE_EXIT" -ne 0 ] && [ "$CLAUDE_EXIT" -eq 98 ]; then
  if run_claude_account "keychain" ""; then
    CLAUDE_EXIT=0
  else
    CLAUDE_EXIT=$?
  fi
fi

if [ "$CLAUDE_EXIT" -eq 98 ]; then
  CLAUDE_EXIT=1
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [wr2-ig-metrics] all Claude OAuth accounts unavailable" >> "$ERR"
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] wr2-ig-metrics-analyst done (exit=${CLAUDE_EXIT})" >> "$LOG"

if [ "$CLAUDE_EXIT" -ne 0 ]; then
  notify_failure "⚠️ wr2-ig-metrics-analyst FAILED (exit=${CLAUDE_EXIT}) on $(hostname -s). Weekly IG-insights amendment NOT produced — see ${ERR}" \
    "wr2-ig-metrics-analyst:$(date +%Y-W%V):$(hostname -s)"
fi

exit "$CLAUDE_EXIT"
