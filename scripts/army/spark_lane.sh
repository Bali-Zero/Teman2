#!/bin/bash
# army.spark_lane — Armata H24 lane 1: standing read-only analysis on the
# gpt-5.3-codex-spark weekly bucket (measured idle 2026-08-14, separate
# bucket from the primary codex quota — see
# research/operations/2026-08-14-armata-h24-standing-lanes.md).
#
# Amended same day after a cross-family Kimi K3 refutation closed 12
# numbered defects (design doc §Amendment log). What changed vs the first
# cut: atomic mkdir-based run lock (was a plain pidfile write, not atomic
# against a real race); dedup key is now sha256 of TASK CONTENT ONLY, not
# filename+sha (a rename/move no longer creates a duplicate entry); the
# done-list is an append-only JSONL of every ATTEMPT (not just successes),
# so a poisoned task gets quarantined after 2 failures instead of blocking
# the head of the queue forever, and corrupt state HALTS the lane instead
# of failing open into re-running the whole queue; backoff is a fixed 12h
# (never exponential) and also fires on 3 consecutive non-quota failures
# (protects against a silently-changed codex output format); every report
# now carries the checkout HEAD sha + task sha for reproducibility; the
# daily cap and every date computation go through an explicit WITA
# (Asia/Makassar, fixed UTC+8, no DST) clock instead of ambient system TZ;
# a kill-switch-off tick still runs the digest check so a forgotten kill
# switch stays visible; every successful tick stamps last_success_epoch
# into the SAME organism heartbeat sidecar the repo's existing
# organism_stale_detector.py already auto-discovers (no separate registry
# — confirmed by reading that detector before wiring this in).
#
# Contract (non-negotiable, cicatrix-superscar.md families #1/#2/#5/#7):
#   - repo-canonical only: the plist invokes THIS file's repo path directly,
#     no HOME-fork copy (family #1).
#   - StartInterval, never KeepAlive (family #7): the plist owns the tick.
#   - read-only: codex runs with --sandbox read-only against the MAIN
#     checkout; this lane never writes/commits/pushes/opens a PR (family #5,
#     and the explicit "no auto-PR" contract for both Armata H24 lanes).
#   - quota-aware backoff, daily run cap, single-instance lock.
#   - fail-visible via the ONE Telegram gateway (scripts/tg_notify.py) —
#     never a raw curl, never a hardcoded token.
#
# Genesis: the 2026-06 "codex-spark-loop" ecosystem (~/scripts/codex/ on Pro)
# died of runaway-alarm + 13 PR-spam (W81 firebreak, plist
# `.disabled-W81-*`). This lane is read-only, capped, and never opens a PR —
# landing is always the interactive session's job (CLAUDE.md §2).

set -u   # unset vars crash instead of expanding empty (fail-visible)

ORGAN_ID="army.spark_lane"
REPO="${ARMY_SPARK_REPO:-$HOME/nuzantara}"
QUEUE_DIR="${ARMY_SPARK_QUEUE_DIR:-$REPO/infra/army/spark-queue}"
REPORTS_DIR="${ARMY_SPARK_REPORTS_DIR:-$HOME/army/spark/reports}"
STATE_DIR="${ARMY_SPARK_STATE_DIR:-$HOME/army/spark/state}"
LOG_DIR="${ARMY_SPARK_LOG_DIR:-$HOME/logs/army-spark}"
SIDECAR_DIR="${ARMY_SPARK_SIDECAR_DIR:-$HOME/.organism/last_seen}"

DAILY_CAP="${ARMY_SPARK_DAILY_CAP:-6}"
TIMEOUT_S="${ARMY_SPARK_TIMEOUT_S:-900}"
BACKOFF_HOURS="${ARMY_SPARK_BACKOFF_HOURS:-12}"
CONSEC_FAIL_LIMIT="${ARMY_SPARK_CONSEC_FAIL_LIMIT:-3}"
DIGEST_HOUR="${ARMY_SPARK_DIGEST_HOUR:-7}"
MODEL="${ARMY_SPARK_MODEL:-gpt-5.3-codex-spark}"
EFFORT="${ARMY_SPARK_EFFORT:-medium}"
# Seat resolution goes through the fleet door (scripts/lib/codex_seat.sh):
# the second ChatGPT Pro seat has two names in the fleet (~/.codex-acct2 on
# Pro, ~/.codex-o2 on M5) and the default ~/.codex is 401-dead on Pro — a
# hardcoded name makes the other machine's seat invisible. The env var stays
# as an explicit per-install override; when unset, codex_seat_pick() supplies
# a live seat (alternating). Empty pick = no seat logged in anywhere: keep ""
# so the run fails visibly at codex exec instead of silently using ~/.codex.
. "$REPO/scripts/lib/codex_seat.sh"
CODEX_HOME_OVERRIDE="${ARMY_SPARK_CODEX_HOME:-$(codex_seat_pick)}"
CODEX_BIN="${ARMY_SPARK_CODEX_BIN:-codex}"

mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/run.log"
ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" >> "$LOG"; }

# ── WITA (Asia/Makassar) day-boundary discipline, declared explicitly ────
# Fixed UTC+8, no DST — `TZ=Asia/Makassar date` needs no tzdata beyond what
# every macOS ships. Never rely on ambient system/launchd TZ for "today"/
# "this hour": that TZ is not guaranteed to be WITA in every cron
# environment, and a day-cap or digest keyed off the wrong day is silently
# wrong, not loudly broken (family #9 discipline).
wita_date() { TZ=Asia/Makassar date '+%Y-%m-%d'; }
wita_hour() { TZ=Asia/Makassar date '+%H' | sed 's/^0//'; }
wita_yesterday() {
    TZ=Asia/Makassar date -v-1d '+%Y-%m-%d' 2>/dev/null \
        || TZ=Asia/Makassar date -d yesterday '+%Y-%m-%d' 2>/dev/null
}
wita_weekday() { TZ=Asia/Makassar date '+%u'; }  # 1=Monday

resolve_py3() {
    for py in /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
        if command -v "$py" >/dev/null 2>&1; then
            printf '%s' "$py"
            return 0
        fi
    done
    return 1
}
PY3="$(resolve_py3 || true)"

heartbeat() {  # $1 status, $2 note — every exit path (Esiste≠Armato)
    if [ -f "$REPO/scripts/lib/heartbeat.sh" ]; then
        # shellcheck disable=SC1090
        source "$REPO/scripts/lib/heartbeat.sh"
        organism_heartbeat "$ORGAN_ID" "$1" "$2"
    else
        mkdir -p "$SIDECAR_DIR" 2>/dev/null
        printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
            "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" \
            > "$SIDECAR_DIR/$ORGAN_ID.json" 2>/dev/null
    fi
}

# Item 11: stamp last_success_epoch INTO the same sidecar heartbeat() just
# wrote. organism_stale_detector.py auto-discovers every *.json file under
# ~/.organism/last_seen/ (confirmed by reading it before wiring this in —
# no separate allow-list/registry required for staleness detection; the
# only other registry in the repo, apps/organism/organism/organs_registry.yaml,
# is consumed by sentinel-aggregate.py/healer_receptor_registry.py for
# recovery-action automation, not by the stale detector — Phase 2 candidate
# if that automation is wanted, see the design doc). Kept as a field INSIDE
# the existing sidecar rather than a second file: one artifact, one reader
# contract, additive-only so a JSON reader that only looks at ts/status is
# unaffected. Only $PY3-dependent; degrades to a logged no-op without it
# (the base heartbeat above still landed, so liveness itself is not lost).
stamp_last_success() {  # $1 status
    [ -n "$PY3" ] || { log "WARN: no python3 — last_success_epoch not stamped"; return 0; }
    local sidecar_file="$SIDECAR_DIR/$ORGAN_ID.json"
    "$PY3" - "$sidecar_file" "$1" <<'PYEOF' >> "$LOG" 2>&1
import json, os, sys, time
path, status = sys.argv[1], sys.argv[2]
try:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
except Exception:
    data = {}
if status == "ok":
    data["last_success_epoch"] = int(time.time())
tmp = f"{path}.tmp.{os.getpid()}"
try:
    with open(tmp, "w", encoding="utf-8") as fh:
        # Compact separators (no space after ':') to match this repo's
        # existing sidecar convention (scripts/army/spark_lane.sh's own
        # printf fallback writes compact JSON) — some readers of this file
        # (including this lane's own test suite) grep for `"status":"x"`
        # rather than parsing JSON properly.
        json.dump(data, fh, separators=(",", ":"))
        fh.write("\n")
    os.replace(tmp, path)
except Exception as exc:
    print(f"stamp_last_success failed (non-fatal): {exc}")
PYEOF
}

telegram() {  # $1 tier, $2 dedup-key, $3 text — through the ONE gateway
    local tier="$1" key="$2" text="$3" gateway
    gateway="$REPO/scripts/tg_notify.py"
    [ -f "$gateway" ] || { log "NO GATEWAY at $gateway — alert NOT sent: ${text:0:80}"; return 0; }
    if [ -z "$PY3" ]; then
        log "no python3 found — alert NOT sent: ${text:0:80}"
        return 0
    fi
    log "tg_notify[$key]: $("$PY3" "$gateway" --tier "$tier" --source "army-spark-lane" \
        --dedup-key "$key" -- "$text" 2>&1 | tail -1)"
}

# Item 13 (2026-08-27 repair — see git log for the mandate): a fixed
# BACKOFF_HOURS blind-retries every tick against a quota wall the reply
# ITSELF names a real clear time for. Measured live 2026-08-26/27: the
# gpt-5.3-codex-spark bucket answered "ERROR: You've hit your usage limit
# for GPT-5.3-Codex-Spark. Switch to another model now, or try again at
# Aug 31st, 2026 8:06 PM." for 8 straight days while this lane kept
# retrying every 12h — every retry rediscovered the same wall, burned a
# tick, and re-sent the same deduped alert, with zero chance of success
# before the real reset. Parses codex's own reply for a reset time and
# uses it INSTEAD of the fixed backoff, but only to EXTEND the wait, never
# to shorten it below BACKOFF_HOURS — a parse of a near/garbled time must
# not cause a tighter retry loop than the safe default already gives.
# Capped at 7 days so a parser misfire (or a provider that starts quoting
# absurd future dates) cannot wedge the lane open-endedly.
#
# Codex's own timestamps are the operator's local wall clock (WITA,
# UTC+8, no DST) — this repo's own convention for "now" elsewhere in this
# file (wita_date/wita_hour) is never ambient system TZ, and there is no
# reason codex's reply would be the one exception, so the naive
# Y-M-D-H:M is interpreted as UTC+8 rather than guessed from the runner's
# TZ. Prints an epoch on a successful parse, prints nothing otherwise —
# callers MUST treat empty as "no usable reset time", never as epoch 0.
parse_quota_reset_epoch() {  # $1 = path to codex's raw output
    [ -n "$PY3" ] || return 0
    "$PY3" - "$1" <<'PYEOF'
import calendar
import re
import sys

path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
except OSError:
    sys.exit(0)

# Observed verbatim 2026-08-26: "...or try again at Aug 31st, 2026 8:06 PM."
# Tolerate st/nd/rd/th, an optional comma, and a missing leading zero.
m = re.search(
    r"try again at\s+([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+"
    r"(\d{4})\s+(\d{1,2}):(\d{2})\s*([AaPp][Mm])",
    text,
)
if not m:
    sys.exit(0)

month_name, day, year, hour, minute, ampm = m.groups()
months = {name: i for i, name in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
month = months.get(month_name[:3].title())
if not month:
    sys.exit(0)

hour_i = int(hour) % 12
if ampm.upper() == "PM":
    hour_i += 12

try:
    epoch_wita = calendar.timegm(
        (int(year), month, int(day), hour_i, int(minute), 0, 0, 0, 0)
    )
except (ValueError, OverflowError):
    sys.exit(0)

print(epoch_wita - 8 * 3600)  # WITA (UTC+8) -> UTC epoch
PYEOF
}

# ── G4 node guard — this lane is Pro-only by design (M5 = no cron, per
#    CLAUDE.md; Mini would be active-active with Pro on the same queue,
#    superscar #10). A wrong-node tick exits immediately — not my machine,
#    not my digest to send. ──────────────────────────────────────────────
if [ "${ARMY_SPARK_SKIP_NODE_GUARD:-}" != "1" ]; then
    # ARMY_SPARK_NODE_OVERRIDE lets tests exercise this guard deterministically
    # without depending on the real hostname of whatever machine runs the
    # test suite (which may itself be "nuzantara").
    node="${ARMY_SPARK_NODE_OVERRIDE:-$(hostname -s 2>/dev/null | tr '[:upper:]' '[:lower:]')}"
    required_node="${ARMY_SPARK_REQUIRED_NODE:-nuzantara}"
    if [ "$node" != "$required_node" ]; then
        log "node guard: $node != $required_node — not my node, exiting"
        heartbeat "disabled" "wrong-node $node"
        exit 0
    fi
fi

mkdir -p "$REPORTS_DIR" "$STATE_DIR"
ATTEMPTS_FILE="$STATE_DIR/attempts.jsonl"   # append-only; see select_task() below
BACKOFF_FILE="$STATE_DIR/backoff-until.txt"
CONSEC_FAIL_FILE="$STATE_DIR/consecutive-non-quota-fails.txt"
COUNT_FILE="$STATE_DIR/run-count-$(wita_date).txt"
touch "$ATTEMPTS_FILE"

sha256_of() {
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" 2>/dev/null | awk '{print $1}'
    elif command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" 2>/dev/null | awk '{print $1}'
    else
        openssl dgst -sha256 "$1" 2>/dev/null | awk '{print $NF}'
    fi
}

slugify() {
    # No `sed 's/-\+/.../'`: BSD sed (macOS, this lane's only target) does not
    # accept `\+` in BRE — that is a GNU extension. `tr -s` squeezes runs of
    # the placeholder char portably in both sed flavors' absence.
    local s
    s="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '-' | tr -s '-')"
    s="${s#-}"
    s="${s%-}"
    printf '%s' "$s"
}

# Item 2/3: content-only sha dedup + retry-count/head-of-line via a JSONL
# fold. Offloaded to python3 rather than hand-rolled bash JSON parsing —
# this repo's own scar history (W104, W108) is largely bash scripts
# mis-parsing structured state; python's json module doesn't have that
# failure mode. Prints one of:
#   CORRUPT\t<lineno>          — attempts.jsonl has an unparseable line
#   EMPTY                      — queue empty, or every task is done/quarantined
#   PICK\t<path>\t<sha256>     — the task to dispatch this tick
select_task() {
    [ -n "$PY3" ] || { printf 'CORRUPT\t(no-python3)\n'; return 0; }
    "$PY3" - "$QUEUE_DIR" "$ATTEMPTS_FILE" <<'PYEOF'
import hashlib
import json
import os
import sys

queue_dir, attempts_file = sys.argv[1], sys.argv[2]


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


by_sha = {}
if os.path.isfile(attempts_file):
    with open(attempts_file, "r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                sha = row["sha"]
                status = row["status"]
            except Exception:
                print(f"CORRUPT\t{lineno}")
                sys.exit(0)
            info = by_sha.setdefault(sha, {"ok": False, "failed": 0})
            if status == "ok":
                info["ok"] = True
            elif status == "failed":
                info["failed"] += 1
            # status == "quota" touches neither counter — not the task's fault

try:
    names = sorted(os.listdir(queue_dir))
except FileNotFoundError:
    names = []

candidates = []
for name in names:
    if not name.endswith(".md"):
        continue
    # The queue dir carries a README.md alongside real task files (it
    # documents the queue format, quota/backoff/429 behavior, etc.) — it
    # matches the *.md glob but is not a task. Case-insensitive so
    # README.md/readme.md/Readme.MD are all excluded the same way. This is
    # the ONLY place that enumerates queue files for dispatch, so this
    # exclusion is automatically the single source of truth (nothing else
    # reads QUEUE_DIR directly — the daily digest counts attempts.jsonl,
    # not the queue dir).
    if name.lower().startswith("readme"):
        continue
    path = os.path.join(queue_dir, name)
    if not os.path.isfile(path):
        continue
    candidates.append((os.path.getmtime(path), path, sha256_of(path)))
candidates.sort(key=lambda c: c[0])

cohort_never_attempted = []
cohort_one_failure = []
for _mtime, path, sha in candidates:
    info = by_sha.get(sha)
    if info is None:
        cohort_never_attempted.append((path, sha))
        continue
    if info["ok"]:
        continue  # done, permanently skip
    if info["failed"] >= 2:
        continue  # quarantined: a poisoned task must never block the head
    if info["failed"] == 1:
        cohort_one_failure.append((path, sha))
    else:
        cohort_never_attempted.append((path, sha))

picked = cohort_never_attempted or cohort_one_failure
if picked:
    path, sha = picked[0]
    print(f"PICK\t{path}\t{sha}")
else:
    print("EMPTY")
PYEOF
}

append_attempt() {  # $1 sha $2 filename $3 status(ok|failed|quota) $4 report-path-or-dash
    [ -n "$PY3" ] || { log "WARN: no python3 — attempt NOT recorded (sha=$1 status=$3)"; return 0; }
    "$PY3" - "$ATTEMPTS_FILE" "$1" "$2" "$3" "$4" <<'PYEOF' >> "$LOG" 2>&1
import json, sys, time
path, sha, filename, status, report = sys.argv[1:6]
row = {
    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "sha": sha,
    "filename": filename,
    "status": status,
    "report": (None if report == "-" else report),
    "outcome": None,  # item 12: a verification session appends a corrected row later
}
try:
    with open(path, "a", encoding="utf-8") as fh:
        # Compact separators — see stamp_last_success()'s comment: several
        # readers of this repo's sidecar/state JSON (including this lane's
        # own test suite) grep for `"key":"value"` rather than parsing.
        fh.write(json.dumps(row, separators=(",", ":")) + "\n")
except Exception as exc:
    print(f"append_attempt failed (non-fatal, dedup may miss this attempt): {exc}")
PYEOF
}

weekly_produced_consumed() {  # prints "<produced> <consumed>"
    [ -n "$PY3" ] || { echo "0 0"; return 0; }
    "$PY3" - "$ATTEMPTS_FILE" <<'PYEOF'
import json, sys
path = sys.argv[1]
produced = 0
consumed = 0
try:
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if row.get("status") == "ok":
                produced += 1
            if row.get("outcome") in ("applied", "rejected", "read"):
                consumed += 1
except FileNotFoundError:
    pass
print(f"{produced} {consumed}")
PYEOF
}

# RUN_STATUS_HB   — heartbeat.sh's normalized vocabulary (ok/degraded/error/disabled)
# RUN_STATUS_RICH — this lane's own, unrestricted vocabulary, used by the
#                   digest and this run's own log line. NEVER pass RUN_STATUS_RICH
#                   words like "killed" to heartbeat(): heartbeat.sh's own
#                   vocabulary maps "killed" to "error" (verified by reading
#                   scripts/lib/heartbeat.sh before wiring this in) — using it
#                   there would make an intentional kill-switch-off tick alarm
#                   as a crash. The two vocabularies are deliberately kept apart.
RUN_STATUS_HB="ok"
RUN_STATUS_RICH="ok"
RUN_NOTE="no task processed this tick"
SHOULD_WORK=1
WE_OWN_LOCK=0
LOCK_DIR="$STATE_DIR/run.lock"

release_lock() {
    if [ "$WE_OWN_LOCK" = "1" ]; then
        rm -rf "$LOCK_DIR" 2>/dev/null
    fi
}
trap release_lock EXIT

# ── G5 kill switch — falls through to the trailer (still sends the digest
#    check) rather than exiting immediately, so a forgotten kill switch
#    stays visible every day it's checked, not just the day it was flipped.
if [ "${ARMY_SPARK_ENABLED:-true}" = "false" ]; then
    log "kill switch ARMY_SPARK_ENABLED=false — exiting work, digest still runs"
    RUN_STATUS_HB="disabled"
    RUN_STATUS_RICH="killed"
    RUN_NOTE="kill switch"
    SHOULD_WORK=0
fi

# ── G10 single instance — atomic mkdir claim, pid-checked, self-healing on
#    a stale (dead-owner) lock. `mkdir` is atomic at the filesystem level in
#    a way a plain pidfile write is not (launchd does not guarantee
#    serialization against a manual run of the same script).
if [ "$SHOULD_WORK" = "1" ]; then
    if mkdir "$LOCK_DIR" 2>/dev/null; then
        echo $$ > "$LOCK_DIR/pid" 2>/dev/null
        WE_OWN_LOCK=1
    else
        lock_pid=""
        [ -f "$LOCK_DIR/pid" ] && lock_pid="$(cat "$LOCK_DIR/pid" 2>/dev/null)"
        if [ -n "$lock_pid" ] && kill -0 "$lock_pid" 2>/dev/null; then
            log "previous run still alive (pid $lock_pid) — skipping (overlap)"
            RUN_STATUS_HB="ok"
            RUN_STATUS_RICH="skipped-overlap"
            RUN_NOTE="skipped: previous run alive (pid $lock_pid)"
            SHOULD_WORK=0
        else
            log "reclaiming stale lock dir (owner pid $lock_pid not alive)"
            rm -rf "$LOCK_DIR" 2>/dev/null
            if mkdir "$LOCK_DIR" 2>/dev/null; then
                echo $$ > "$LOCK_DIR/pid" 2>/dev/null
                WE_OWN_LOCK=1
            else
                log "lost the race reclaiming the lock — treating as overlap, safe default"
                RUN_STATUS_HB="ok"
                RUN_STATUS_RICH="skipped-overlap"
                RUN_NOTE="skipped: lock reclaim race"
                SHOULD_WORK=0
            fi
        fi
    fi
fi

if [ "$SHOULD_WORK" = "1" ] && [ -z "$PY3" ]; then
    log "no python3 interpreter found — cannot safely manage attempts.jsonl state, skipping this tick"
    RUN_STATUS_HB="error"
    RUN_STATUS_RICH="error"
    RUN_NOTE="no python3 interpreter available"
    SHOULD_WORK=0
    telegram p0 "army-spark:no-python3" \
        "🔴 army.spark_lane: nessun interprete python3 trovato — impossibile gestire lo stato in sicurezza, tick saltato."
fi

# ── backoff check ────────────────────────────────────────────────────────
if [ "$SHOULD_WORK" = "1" ]; then
    now_epoch="$(date +%s)"
    backoff_until=0
    [ -f "$BACKOFF_FILE" ] && backoff_until="$(cat "$BACKOFF_FILE" 2>/dev/null || echo 0)"
    case "$backoff_until" in ''|*[!0-9]*) backoff_until=0 ;; esac

    if [ "$backoff_until" -gt "$now_epoch" ]; then
        log "backoff active until epoch $backoff_until — skipping dispatch this tick"
        RUN_STATUS_HB="degraded"
        RUN_STATUS_RICH="backoff"
        RUN_NOTE="backoff active until $backoff_until"
        SHOULD_WORK=0
    fi
fi

# ── daily cap (WITA calendar day, item 6) ──────────────────────────────
if [ "$SHOULD_WORK" = "1" ]; then
    run_count=0
    [ -f "$COUNT_FILE" ] && run_count="$(cat "$COUNT_FILE" 2>/dev/null || echo 0)"
    case "$run_count" in ''|*[!0-9]*) run_count=0 ;; esac

    if [ "$run_count" -ge "$DAILY_CAP" ]; then
        log "daily cap reached ($run_count/$DAILY_CAP, WITA day $(wita_date)) — skipping dispatch this tick"
        RUN_STATUS_HB="ok"
        RUN_STATUS_RICH="cap-reached"
        RUN_NOTE="daily cap reached ($run_count/$DAILY_CAP)"
        SHOULD_WORK=0
    elif [ ! -d "$QUEUE_DIR" ]; then
        log "queue dir missing: $QUEUE_DIR"
        RUN_STATUS_HB="error"
        RUN_STATUS_RICH="error"
        RUN_NOTE="queue dir missing"
        SHOULD_WORK=0
    fi
fi

# ── task selection + dispatch ────────────────────────────────────────────
if [ "$SHOULD_WORK" = "1" ]; then
    SELECT_OUT="$(select_task)"
    SELECT_KIND="$(printf '%s' "$SELECT_OUT" | head -1 | cut -f1)"

    case "$SELECT_KIND" in
        CORRUPT)
            corrupt_line="$(printf '%s' "$SELECT_OUT" | head -1 | cut -f2)"
            log "attempts.jsonl CORRUPT at line $corrupt_line — halting, NOT falling open into re-running the queue"
            RUN_STATUS_HB="error"
            RUN_STATUS_RICH="state-corrupt"
            RUN_NOTE="attempts.jsonl corrupt at line $corrupt_line"
            telegram p0 "army-spark:state-corrupt" \
                "🔴 army.spark_lane: attempts.jsonl corrotto (riga $corrupt_line) — lane FERMATA, nessun dispatch. Serve intervento manuale sullo stato."
            ;;
        EMPTY)
            log "queue empty, fully done, or fully quarantined — nothing to dispatch"
            RUN_STATUS_HB="ok"
            RUN_STATUS_RICH="ok"
            RUN_NOTE="queue empty"
            ;;
        PICK)
            TASK_FILE="$(printf '%s' "$SELECT_OUT" | head -1 | cut -f2)"
            TASK_SHA="$(printf '%s' "$SELECT_OUT" | head -1 | cut -f3)"
            title_line="$(head -1 "$TASK_FILE" 2>/dev/null | sed 's/^#\+ *//')"
            slug="$(slugify "${title_line:-$(basename "$TASK_FILE" .md)}")"
            [ -n "$slug" ] || slug="task"
            log "dispatching task=$(basename "$TASK_FILE") sha=$TASK_SHA slug=$slug model=$MODEL effort=$EFFORT"

            _to="$(command -v timeout || command -v gtimeout || true)"
            OUT_TMP="$(mktemp "${TMPDIR:-/tmp}/army-spark.XXXXXX" 2>/dev/null || echo "/tmp/army-spark.$$")"

            (
                cd "$REPO" || exit 90
                # Empty override = codex_seat_pick found no logged-in seat.
                # Exporting "" would fall back to ~/.codex silently (401-dead
                # on Pro) — refuse instead; rc=91 is recorded as a failure.
                [ -n "$CODEX_HOME_OVERRIDE" ] || exit 91
                export CODEX_HOME="$CODEX_HOME_OVERRIDE"
                PROMPT_TEXT="$(cat "$TASK_FILE")"
                if [ -n "$_to" ]; then
                    "$_to" "$TIMEOUT_S" "$CODEX_BIN" exec -m "$MODEL" \
                        -c model_reasoning_effort="$EFFORT" \
                        --sandbox read-only --skip-git-repo-check \
                        "$PROMPT_TEXT" < /dev/null
                else
                    log "WARN: no timeout/gtimeout binary — running WITHOUT a wall-clock cap"
                    "$CODEX_BIN" exec -m "$MODEL" \
                        -c model_reasoning_effort="$EFFORT" \
                        --sandbox read-only --skip-git-repo-check \
                        "$PROMPT_TEXT" < /dev/null
                fi
            ) > "$OUT_TMP" 2>&1
            CODEX_RC=$?

            run_count=$((run_count + 1))
            echo "$run_count" > "$COUNT_FILE"

            # Quota markers are classified ONLY when the invocation actually
            # FAILED (CODEX_RC != 0) — cicatrix family #3 (guard-over-match):
            # the classifier used to grep the model's OUTPUT unconditionally,
            # even on a successful (rc=0) run. Measured live 2026-08-15: the
            # dispatched task was infra/army/spark-queue/README.md (defect 1,
            # now excluded above), which *documents* this lane's own
            # quota/backoff/429 behavior — codex's legitimate analysis of
            # that doc contained those substrings, producing a false
            # status=quota, a false 12h backoff, and a false P0-class alert,
            # while a manual codex probe on the same bucket 3 minutes later
            # answered fine (the bucket was never actually in quota). A
            # successful run whose TEXT happens to mention quota is
            # innocent; only a failed run whose text names the reason is
            # guilty. The pattern itself is kept unchanged for the failure
            # branch — codex exec (unlike some CLIs) fails non-zero on a
            # genuine quota exhaustion (see the stub's `quota` mode, exit 1),
            # so gating on rc!=0 does not blind this branch to a real quota
            # hit.
            if [ "$CODEX_RC" -ne 0 ] && grep -qiE 'out of extra usage|usage limit|quota exceeded|rate.limit|429|weekly limit' "$OUT_TMP" 2>/dev/null; then
                quota_line="$(grep -iE 'out of extra usage|usage limit|quota exceeded|rate.limit|429|weekly limit' "$OUT_TMP" 2>/dev/null | head -1 | tr -s ' \t' ' ')"
                parsed_reset="$(parse_quota_reset_epoch "$OUT_TMP" 2>/dev/null | tr -d '[:space:]')"
                case "$parsed_reset" in ''|*[!0-9]*) parsed_reset="" ;; esac
                min_backoff=$((now_epoch + BACKOFF_HOURS * 3600))
                max_backoff=$((now_epoch + 7 * 86400))
                if [ -n "$parsed_reset" ] && [ "$parsed_reset" -gt "$min_backoff" ] && [ "$parsed_reset" -le "$max_backoff" ]; then
                    new_backoff="$parsed_reset"
                    backoff_source="parsed reset time in codex's reply"
                else
                    new_backoff="$min_backoff"
                    backoff_source="fixed ${BACKOFF_HOURS}h (no in-range reset time in codex's reply)"
                fi
                echo "$new_backoff" > "$BACKOFF_FILE"
                echo 0 > "$CONSEC_FAIL_FILE"   # quota is a distinct, correctly-classified state
                log "quota marker detected — backoff until epoch $new_backoff (${backoff_source}) — codex said: ${quota_line:0:200}"
                RUN_STATUS_HB="degraded"
                RUN_STATUS_RICH="quota"
                RUN_NOTE="quota until epoch $new_backoff (${backoff_source}): ${quota_line:0:160}"
                append_attempt "$TASK_SHA" "$(basename "$TASK_FILE")" "quota" "-"
                backoff_human="$(date -r "$new_backoff" '+%Y-%m-%d %H:%M UTC' 2>/dev/null || date -u -d "@$new_backoff" '+%Y-%m-%d %H:%M UTC' 2>/dev/null || echo "epoch $new_backoff")"
                telegram digest "army-spark:quota" \
                    "🐢 army.spark_lane: bucket gpt-5.3-codex-spark in quota — backoff until ${backoff_human} (${backoff_source}). Task NON consumato: $(basename "$TASK_FILE"). Codex: ${quota_line:0:200}"
            elif [ "$CODEX_RC" -eq 0 ]; then
                report_date="$(wita_date)"
                head_sha="$(cd "$REPO" && git rev-parse HEAD 2>/dev/null || echo unknown)"
                report_path="$REPORTS_DIR/${report_date}-${slug}.md"
                {
                    echo "# ${title_line:-$(basename "$TASK_FILE" .md)}"
                    echo
                    echo "- source task: \`infra/army/spark-queue/$(basename "$TASK_FILE")\`"
                    echo "- checkout HEAD: \`$head_sha\`"
                    echo "- task sha256: \`$TASK_SHA\`"
                    echo "- model: $MODEL (effort=$EFFORT)"
                    echo "- generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
                    echo
                    cat "$OUT_TMP"
                } > "$report_path"
                echo 0 > "$CONSEC_FAIL_FILE"
                log "report written: $report_path"
                RUN_STATUS_HB="ok"
                RUN_STATUS_RICH="ok"
                RUN_NOTE="report: $report_path"
                append_attempt "$TASK_SHA" "$(basename "$TASK_FILE")" "ok" "$report_path"
            else
                log "codex exec failed rc=$CODEX_RC — task attempt recorded, quarantines after 2 failures"
                tail_text="$(tail -c 600 "$OUT_TMP" 2>/dev/null | tr '\n' ' ' | tr -s ' ')"
                append_attempt "$TASK_SHA" "$(basename "$TASK_FILE")" "failed" "-"

                consec=0
                [ -f "$CONSEC_FAIL_FILE" ] && consec="$(cat "$CONSEC_FAIL_FILE" 2>/dev/null || echo 0)"
                case "$consec" in ''|*[!0-9]*) consec=0 ;; esac
                consec=$((consec + 1))
                echo "$consec" > "$CONSEC_FAIL_FILE"

                RUN_STATUS_HB="error"
                RUN_STATUS_RICH="error"
                RUN_NOTE="codex rc=$CODEX_RC (consecutive non-quota fails: $consec)"
                telegram p0 "army-spark:codex-failed" \
                    "🔴 army.spark_lane: codex exec rc=$CODEX_RC su $(basename "$TASK_FILE"). Tail: ${tail_text:0:400}"

                if [ "$consec" -ge "$CONSEC_FAIL_LIMIT" ]; then
                    new_backoff=$((now_epoch + BACKOFF_HOURS * 3600))
                    echo "$new_backoff" > "$BACKOFF_FILE"
                    echo 0 > "$CONSEC_FAIL_FILE"
                    log "$consec consecutive non-quota failures >= limit $CONSEC_FAIL_LIMIT — backoff ${BACKOFF_HOURS}h (possible format change)"
                    telegram p0 "army-spark:consecutive-fail-backoff" \
                        "🔴 army.spark_lane: $consec fallimenti non-quota consecutivi — possibile cambio di formato output codex. Backoff ${BACKOFF_HOURS}h."
                fi
            fi
            rm -f "$OUT_TMP" 2>/dev/null
            ;;
        *)
            log "select_task returned unexpected output: $SELECT_OUT"
            RUN_STATUS_HB="error"
            RUN_STATUS_RICH="error"
            RUN_NOTE="select_task: unexpected output"
            ;;
    esac
fi

# ── daily digest (once per day, first tick at/after DIGEST_HOUR WITA) ────
# Runs regardless of SHOULD_WORK — item 11: a kill-switch-off or
# lock-overlap tick must still be able to report the digest if it's the
# first tick past DIGEST_HOUR that day.
DIGEST_MARK="$STATE_DIR/last-digest-date.txt"
today="$(wita_date)"
cur_hour="$(wita_hour)"
[ -z "$cur_hour" ] && cur_hour=0
last_digest_date=""
[ -f "$DIGEST_MARK" ] && last_digest_date="$(cat "$DIGEST_MARK" 2>/dev/null)"

if [ "$cur_hour" -ge "$DIGEST_HOUR" ] && [ "$last_digest_date" != "$today" ]; then
    yesterday="$(wita_yesterday)"
    n_yesterday=0
    if [ -f "$ATTEMPTS_FILE" ] && [ -n "$yesterday" ]; then
        # attempts.jsonl writes ts compact (no space after `:`); the
        # optional-space pattern still matches that shape.
        n_yesterday="$(grep -c "\"ts\": *\"${yesterday}" "$ATTEMPTS_FILE" 2>/dev/null || echo 0)"
    fi
    digest_text="🌅 army.spark_lane digest: ${n_yesterday} task processati ieri (${yesterday:-?}). Report dir: $REPORTS_DIR"
    if [ "$RUN_STATUS_RICH" = "killed" ]; then
        digest_text="$digest_text | ⚠️ ARMY_SPARK_ENABLED=false — lane disabilitata"
    fi
    weekday="$(wita_weekday)"
    if [ "$weekday" = "1" ] && [ -n "$PY3" ]; then
        stats="$(weekly_produced_consumed)"
        produced="${stats% *}"
        consumed="${stats#* }"
        digest_text="$digest_text | 📊 settimanale: ${produced} report prodotti, ${consumed} verificati"
    fi
    log "daily digest: $n_yesterday task(s) processed on $yesterday — reports in $REPORTS_DIR"
    telegram digest "army-spark:daily-digest:$today" "$digest_text"
    echo "$today" > "$DIGEST_MARK"
fi

log "tick done status_hb=$RUN_STATUS_HB status_rich=$RUN_STATUS_RICH note=$RUN_NOTE"
heartbeat "$RUN_STATUS_HB" "$RUN_NOTE"
stamp_last_success "$RUN_STATUS_HB"
exit 0
