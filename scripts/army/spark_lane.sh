#!/bin/bash
# army.spark_lane — Armata H24 lane 1: standing read-only analysis on the
# gpt-5.3-codex-spark weekly bucket (measured idle 2026-08-14, separate
# bucket from the primary codex quota — see
# research/operations/2026-08-14-armata-h24-standing-lanes.md).
#
# Contract (non-negotiable, cicatrix-superscar.md families #1/#2/#5/#7):
#   - repo-canonical only: the plist invokes THIS file's repo path directly,
#     no HOME-fork copy (family #1).
#   - StartInterval, never KeepAlive (family #7): the plist owns the tick.
#   - read-only: codex runs with --sandbox read-only against the MAIN
#     checkout; this lane never writes/commits/pushes/opens a PR (family #5,
#     and the explicit "no auto-PR" contract for both Armata H24 lanes).
#   - quota-aware backoff, daily run cap, single-instance pidfile.
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
PIDFILE="${ARMY_SPARK_PIDFILE:-/tmp/nuzantara-army-spark-lane.pid}"

DAILY_CAP="${ARMY_SPARK_DAILY_CAP:-6}"
TIMEOUT_S="${ARMY_SPARK_TIMEOUT_S:-900}"
BACKOFF_HOURS="${ARMY_SPARK_BACKOFF_HOURS:-6}"
DIGEST_HOUR="${ARMY_SPARK_DIGEST_HOUR:-7}"
MODEL="${ARMY_SPARK_MODEL:-gpt-5.3-codex-spark}"
EFFORT="${ARMY_SPARK_EFFORT:-medium}"
CODEX_HOME_OVERRIDE="${ARMY_SPARK_CODEX_HOME:-$HOME/.codex-acct2}"
CODEX_BIN="${ARMY_SPARK_CODEX_BIN:-codex}"

mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/run.log"
ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" >> "$LOG"; }

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

telegram() {  # $1 tier, $2 dedup-key, $3 text — through the ONE gateway
    local tier="$1" key="$2" text="$3" gateway py
    gateway="$REPO/scripts/tg_notify.py"
    [ -f "$gateway" ] || { log "NO GATEWAY at $gateway — alert NOT sent: ${text:0:80}"; return 0; }
    for py in /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
        command -v "$py" >/dev/null 2>&1 || continue
        log "tg_notify[$key]: $("$py" "$gateway" --tier "$tier" --source "army-spark-lane" \
            --dedup-key "$key" -- "$text" 2>&1 | tail -1)"
        return 0
    done
    log "no python3 found — alert NOT sent: ${text:0:80}"
}

# ── G4 node guard — this lane is Pro-only by design (M5 = no cron, per
#    CLAUDE.md; Mini would be active-active with Pro on the same queue,
#    superscar #10) ──────────────────────────────────────────────────────
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

# ── G5 kill switch ──────────────────────────────────────────────────────
if [ "${ARMY_SPARK_ENABLED:-true}" = "false" ]; then
    log "kill switch ARMY_SPARK_ENABLED=false — exiting"
    heartbeat "disabled" "kill switch"
    exit 0
fi

# ── G10 single instance ─────────────────────────────────────────────────
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
    log "previous run still alive (pid $(cat "$PIDFILE")) — skipping"
    heartbeat "ok" "skipped: previous run alive"
    exit 0
fi
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

mkdir -p "$REPORTS_DIR" "$STATE_DIR"
DONE_LIST="$STATE_DIR/done-list.txt"
BACKOFF_FILE="$STATE_DIR/backoff-until.txt"
COUNT_FILE="$STATE_DIR/run-count-$(date +%Y-%m-%d).txt"
PROCESSED_LOG="$STATE_DIR/processed-log.jsonl"
touch "$DONE_LIST" "$PROCESSED_LOG"

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

RUN_STATUS="idle"
RUN_NOTE="no task processed this tick"

# ── backoff check ────────────────────────────────────────────────────────
now_epoch="$(date +%s)"
backoff_until=0
[ -f "$BACKOFF_FILE" ] && backoff_until="$(cat "$BACKOFF_FILE" 2>/dev/null || echo 0)"
case "$backoff_until" in ''|*[!0-9]*) backoff_until=0 ;; esac

if [ "$backoff_until" -gt "$now_epoch" ]; then
    log "backoff active until epoch $backoff_until — skipping dispatch this tick"
    RUN_STATUS="degraded"
    RUN_NOTE="backoff active until $backoff_until"
else
    # ── daily cap ────────────────────────────────────────────────────────
    run_count=0
    [ -f "$COUNT_FILE" ] && run_count="$(cat "$COUNT_FILE" 2>/dev/null || echo 0)"
    case "$run_count" in ''|*[!0-9]*) run_count=0 ;; esac

    if [ "$run_count" -ge "$DAILY_CAP" ]; then
        log "daily cap reached ($run_count/$DAILY_CAP) — skipping dispatch this tick"
        RUN_STATUS="ok"
        RUN_NOTE="daily cap reached ($run_count/$DAILY_CAP)"
    elif [ ! -d "$QUEUE_DIR" ]; then
        log "queue dir missing: $QUEUE_DIR"
        RUN_STATUS="error"
        RUN_NOTE="queue dir missing"
    else
        # ── pick oldest not-yet-done task ──────────────────────────────
        TASK_FILE=""
        # mtime-sorted oldest-first; macOS/BSD stat, so no GNU --time-style.
        while IFS= read -r f; do
            [ -f "$f" ] || continue
            base="$(basename "$f")"
            digest="$(sha256_of "$f")"
            key="${base}:${digest}"
            if ! grep -qxF "$key" "$DONE_LIST" 2>/dev/null; then
                TASK_FILE="$f"
                TASK_KEY="$key"
                break
            fi
        done < <(
            for f in "$QUEUE_DIR"/*.md; do
                [ -f "$f" ] || continue
                mt="$(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f" 2>/dev/null || echo 0)"
                printf '%s\t%s\n' "$mt" "$f"
            done | sort -n | cut -f2-
        )

        if [ -z "$TASK_FILE" ]; then
            log "queue empty or fully processed — nothing to dispatch"
            RUN_STATUS="ok"
            RUN_NOTE="queue empty"
        else
            title_line="$(head -1 "$TASK_FILE" 2>/dev/null | sed 's/^#\+ *//')"
            slug="$(slugify "${title_line:-$(basename "$TASK_FILE" .md)}")"
            [ -n "$slug" ] || slug="task"
            log "dispatching task=$(basename "$TASK_FILE") slug=$slug model=$MODEL effort=$EFFORT"

            _to="$(command -v timeout || command -v gtimeout || true)"
            OUT_TMP="$(mktemp "${TMPDIR:-/tmp}/army-spark.XXXXXX" 2>/dev/null || echo "/tmp/army-spark.$$")"

            (
                cd "$REPO" || exit 90
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

            if grep -qiE 'out of extra usage|usage limit|quota exceeded|rate.limit|429|weekly limit' "$OUT_TMP" 2>/dev/null; then
                new_backoff=$((now_epoch + BACKOFF_HOURS * 3600))
                echo "$new_backoff" > "$BACKOFF_FILE"
                log "quota marker detected — backoff until epoch $new_backoff (${BACKOFF_HOURS}h)"
                RUN_STATUS="degraded"
                RUN_NOTE="quota: backoff ${BACKOFF_HOURS}h"
                printf '{"ts":"%s","task":"%s","slug":"%s","status":"quota"}\n' \
                    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(basename "$TASK_FILE")" "$slug" >> "$PROCESSED_LOG"
                telegram digest "army-spark:quota" \
                    "🐢 army.spark_lane: bucket gpt-5.3-codex-spark in quota — backoff ${BACKOFF_HOURS}h. Task NON consumato: $(basename "$TASK_FILE")"
            elif [ "$CODEX_RC" -eq 0 ]; then
                report_date="$(date +%Y-%m-%d)"
                report_path="$REPORTS_DIR/${report_date}-${slug}.md"
                {
                    echo "# ${title_line:-$(basename "$TASK_FILE" .md)}"
                    echo
                    echo "- source task: \`infra/army/spark-queue/$(basename "$TASK_FILE")\`"
                    echo "- model: $MODEL (effort=$EFFORT)"
                    echo "- generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
                    echo
                    cat "$OUT_TMP"
                } > "$report_path"
                echo "$TASK_KEY" >> "$DONE_LIST"
                log "report written: $report_path"
                RUN_STATUS="ok"
                RUN_NOTE="report: $report_path"
                printf '{"ts":"%s","task":"%s","slug":"%s","status":"ok","report":"%s"}\n' \
                    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(basename "$TASK_FILE")" "$slug" "$report_path" >> "$PROCESSED_LOG"
            else
                log "codex exec failed rc=$CODEX_RC — task left pending (not marked done)"
                tail_text="$(tail -c 600 "$OUT_TMP" 2>/dev/null | tr '\n' ' ' | tr -s ' ')"
                RUN_STATUS="error"
                RUN_NOTE="codex rc=$CODEX_RC"
                printf '{"ts":"%s","task":"%s","slug":"%s","status":"error","rc":%s}\n' \
                    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(basename "$TASK_FILE")" "$slug" "$CODEX_RC" >> "$PROCESSED_LOG"
                telegram p0 "army-spark:codex-failed" \
                    "🔴 army.spark_lane: codex exec rc=$CODEX_RC su $(basename "$TASK_FILE"). Tail: ${tail_text:0:400}"
            fi
            rm -f "$OUT_TMP" 2>/dev/null
        fi
    fi
fi

# ── daily digest (once per day, first tick at/after DIGEST_HOUR local) ───
DIGEST_MARK="$STATE_DIR/last-digest-date.txt"
today="$(date +%Y-%m-%d)"
cur_hour="$(date +%H | sed 's/^0//')"
[ -z "$cur_hour" ] && cur_hour=0
last_digest_date=""
[ -f "$DIGEST_MARK" ] && last_digest_date="$(cat "$DIGEST_MARK" 2>/dev/null)"

if [ "$cur_hour" -ge "$DIGEST_HOUR" ] && [ "$last_digest_date" != "$today" ]; then
    yesterday="$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d yesterday +%Y-%m-%d 2>/dev/null)"
    if [ -f "$PROCESSED_LOG" ] && [ -n "$yesterday" ]; then
        # `printf` above writes the JSON compact (no space after `:`); the
        # optional-space pattern still matches that shape, so counting it a
        # second time without the space would double-count every line.
        n_yesterday="$(grep -c "\"ts\": *\"${yesterday}" "$PROCESSED_LOG" 2>/dev/null || echo 0)"
    else
        n_yesterday=0
    fi
    log "daily digest: $n_yesterday task(s) processed on $yesterday — reports in $REPORTS_DIR"
    telegram digest "army-spark:daily-digest:$today" \
        "🌅 army.spark_lane digest: ${n_yesterday} task processati ieri (${yesterday:-?}). Report dir: $REPORTS_DIR"
    echo "$today" > "$DIGEST_MARK"
fi

log "tick done status=$RUN_STATUS note=$RUN_NOTE"
heartbeat "$RUN_STATUS" "$RUN_NOTE"
exit 0
