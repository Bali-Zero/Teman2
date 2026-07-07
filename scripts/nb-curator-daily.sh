#!/bin/zsh
# nb-curator-daily.sh — Daily nb-curator orchestrator (Mode A on-demand / B+C cron).
#
# Runs every day 04:00 WITA. Steps:
#   1.  Exact-URL dedup (deterministic Python, --apply, cap 20/run) on 5 NB-INTEL.
#   1c. Challenge-page sweep at the 500 ceiling (deterministic, gated, kill-switch).
#   2.  Mode B health check on all NBs (always).
#   3.  Mode C-Press dedup/summarize proposals (Press grows ~30/wk → daily).
#       + Monday: Mode C full pass on all 5 NB-INTEL.
#       + First Monday/month: stale >90d deep pass.
#   4.  Telegram digest ONLY if action/anomaly (dedup>0 OR challenge>0 OR broken>0 OR proposals>0).
#
# Invoked by: com.balizero.nb-curator.daily.plist
# Logs: ~/logs/nb-curator.log (per-run) + ~/logs/nb-curator-daily-launchd.{log,err}
#
# SSOT: this file lives in the repo (scripts/nb-curator-daily.sh). The LaunchAgent
# must point HERE, not at a ~/scripts/ copy (cicatrix superscar #1 — HOME-fork).

set -uo pipefail

# ── Secrets & defense-in-depth ────────────────────────────────────────────────
unset ANTHROPIC_API_KEY
[ -f "$HOME/.nuzantara-secrets.env" ] && { set -a; source "$HOME/.nuzantara-secrets.env"; set +a; }
unset ANTHROPIC_API_KEY

# ── Paths ─────────────────────────────────────────────────────────────────────
LOCK_FILE="/tmp/nb-curator.lock"
LOG="$HOME/logs/nb-curator.log"
OUTPUT_DIR="$HOME/Desktop/nuzantara/research/nb-health"
DEDUP_SCRIPT="$HOME/Desktop/nuzantara/apps/bali-intel-scraper/scripts/nb_dedup_exact_url.py"
DATE_STR=$(TZ=Asia/Makassar date +%Y-%m-%d)
MONTH_STR=$(TZ=Asia/Makassar date +%Y-%m)
DOW=$(TZ=Asia/Makassar date +%u)   # 1=Mon..7=Sun
DAY=$(TZ=Asia/Makassar date +%-d)  # day-of-month
TG_CHAT="1125336968"

mkdir -p "$HOME/logs" "$OUTPUT_DIR"

# ── flock — prevent overlapping runs ──────────────────────────────────────────
exec 9>"$LOCK_FILE"
flock -n 9 || {
    echo "$(TZ=Asia/Makassar date '+%Y-%m-%dT%H:%M:%S WITA'): nb-curator already running, skipping" >> "$LOG"
    exit 0
}

log() { echo "$(TZ=Asia/Makassar date '+%Y-%m-%dT%H:%M:%S WITA'): $*" >> "$LOG"; }
log "nb-curator-daily started (DOW=$DOW DAY=$DAY)"

# ── Step 1: deterministic exact-URL dedup (auto-apply, cap 20) ────────────────
DEDUP_DELETED=0
if [ -f "$DEDUP_SCRIPT" ]; then
    DEDUP_OUT=$(timeout 300 /usr/bin/python3 "$DEDUP_SCRIPT" --apply --cap 20 2>>"$LOG")
    log "dedup: $DEDUP_OUT"
    DEDUP_DELETED=$(echo "$DEDUP_OUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('deleted',0))" 2>/dev/null || echo 0)
    # cap-exceeded (exit 2) → alert: anomaly, possible matching bug
    if echo "$DEDUP_OUT" | grep -q 'aborted_cap'; then
        curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TG_CHAT}" \
            -d "text=⚠️ nb-curator dedup ABORT: planned deletes > cap 20 (possible matching bug). Check ~/logs/nb-curator.log" >/dev/null 2>&1
    fi
else
    log "WARN: dedup script missing at $DEDUP_SCRIPT"
fi

# ── Step 1c: challenge-page sweep at ceiling (deterministic, gated) ───────────
# Step 1 deliberately skips anti-bot placeholder titles ("Just a moment...",
# "Vercel Security Checkpoint") because they share no URL. The LLM (Step 2+3) can
# only PROPOSE their removal (Article 1, propose-only) — so they piled up unapplied
# for weeks until NB-INTEL-AIResearch hit NotebookLM's hard 500-source ceiling and
# silently dropped new sources. This step deletes ONLY those exact-title garbage
# pages, ONLY when a notebook is at/near the ceiling (--near-cap 480). Strict
# allowlist, never fuzzy. Kill-switch: NB_CURATOR_CHALLENGE_SWEEP_ENABLED=false.
CHALLENGE_DELETED=0
if [ "${NB_CURATOR_CHALLENGE_SWEEP_ENABLED:-true}" = "true" ] && [ -f "$DEDUP_SCRIPT" ]; then
    SWEEP_OUT=$(timeout 300 /usr/bin/python3 "$DEDUP_SCRIPT" --challenge-sweep --apply --near-cap 480 --cap 20 2>>"$LOG")
    log "challenge-sweep: $SWEEP_OUT"
    CHALLENGE_DELETED=$(echo "$SWEEP_OUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('challenge_deleted',0))" 2>/dev/null || echo 0)
    if echo "$SWEEP_OUT" | grep -q 'aborted_cap'; then
        curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TG_CHAT}" \
            -d "text=⚠️ nb-curator challenge-sweep ABORT: planned deletes > cap 20 (possible title-match bug). Check ~/logs/nb-curator.log" >/dev/null 2>&1
    fi
else
    log "challenge-sweep skipped (NB_CURATOR_CHALLENGE_SWEEP_ENABLED!=true or script missing)"
fi

# -- Step 1b: auto-regenerate inventory from live nlm (stdlib-only, no venv) ---
# nb_generate_inventory.py is stdlib-only (/usr/bin/python3, no venv needed).
# It calls `nlm notebook list` once + `nlm source list` for each NB-INTEL (5
# calls), writes research/nb-health/nb-inventory-live.json. The Mode B brain
# reads THAT FILE instead of making ~88 sequential `nlm query` calls per NB.
# Exit code 3 = nlm error; non-zero on any failure → logged WARN, not silent skip.
INV_GEN="$HOME/Desktop/nuzantara/scripts/nb_generate_inventory.py"
if [ -f "$INV_GEN" ]; then
    INV_EXIT=0
    timeout 180 /usr/bin/python3 "$INV_GEN" --write >> "$LOG" 2>&1 || INV_EXIT=$?
    if [ "$INV_EXIT" -eq 0 ]; then
        log "inventory auto-regenerated: $OUTPUT_DIR/nb-inventory-live.json"
    else
        log "WARN: inventory regen failed (exit=$INV_EXIT) — brain will use stale or missing file"
    fi
else
    log "WARN: nb_generate_inventory.py missing at $INV_GEN — inventory not regenerated"
fi

# ── Step 2+3: Mode B (always) + Mode C scope by day ───────────────────────────
if [ "$DOW" -eq 1 ] && [ "$DAY" -le 7 ]; then
    C_SCOPE="full pass on all 5 NB-INTEL + stale >90d deep cleanup (first Monday of month)"
    REPORT_PATH="$OUTPUT_DIR/${MONTH_STR}-nb-intel-curation.md"
elif [ "$DOW" -eq 1 ]; then
    C_SCOPE="full pass on all 5 NB-INTEL (weekly Monday)"
    REPORT_PATH="$OUTPUT_DIR/${DATE_STR}-curation.md"
else
    C_SCOPE="NB-INTEL-Press only (daily — Press grows ~30/week)"
    REPORT_PATH="$OUTPUT_DIR/${DATE_STR}-health.md"
fi

MODE_PROMPT="Run nb-curator daily pass. FIRST read your full operating spec at ~/.claude/agents/nb-curator.md (use your file-read tool) and follow it exactly. You have shell + file tools: use them to write the report file. Today is $DATE_STR.

HARD LIMITS — violating these = failure:
- Do NOT write, create, or run ANY python/bash analysis or diff scripts. Read files and reason directly.
- Make AT MOST 2 file reads total (the inventory JSON + at most the single latest report in $OUTPUT_DIR), then write the report and stop.
- Single pass. Finish within ~3 minutes. Brevity over completeness.

PART 1 — Mode B health check (ALL notebooks):
1. Read the pre-gathered live inventory at $OUTPUT_DIR/nb-inventory-live.json (generated by nb_generate_inventory.py immediately before this prompt — it ran nlm notebook list + nlm source list for all NB-INTEL).
   DO NOT run 'nlm query <uuid>' or 'nlm notebook list' per notebook — structural health (health: healthy/empty) and near_cap flag for all notebooks are already in that JSON.
2. From the inventory JSON: count notebooks by health field, identify near_cap=true notebooks. The 'notebooks' array has one entry per NB with fields: id, title, source_count, health, near_cap.
3. Optionally glance at the single most recent report in $OUTPUT_DIR for obvious new/empty transitions — do NOT diff programmatically; if unclear, skip.
4. NB-INTEL source titles are in the 'nb_intel' section of the JSON (key → {uuid, source_count, titles[], near_cap}). Read those directly — no extra nlm calls needed for PART 1.

PART 2 — Mode C dedup/summarize proposals: $C_SCOPE
5. For in-scope NB-INTEL: source titles are already in inventory 'nb_intel.<key>.titles' — use those for near-dup analysis. Only call 'nlm source list <uuid> --json' if you need fields not in the inventory (e.g., URL or type).
6. Eyeball nb_intel.<key>.titles for a FEW (0-5) obviously near-identical title pairs (same event reworded). Do NOT compute Levenshtein in code — just eyeball. If unsure, propose 0.
7. For NB-INTEL-Press: propose summarization for topic clusters >=10 sources
8. Flag stale sources (>90d) where applicable

NOTE: exact-URL duplicates AND exact-title anti-bot challenge pages (\"Just a moment...\", \"Vercel Security Checkpoint\") in near-cap notebooks are already auto-removed by deterministic pre-steps ($DEDUP_DELETED exact-dup + $CHALLENGE_DELETED challenge removed today) — do NOT propose exact-URL merges or challenge-page deletions, only fuzzy/title/summarization.

OUTPUT:
9. Write report to: $REPORT_PATH
Write the report in ONE pass (max ~40 lines), then immediately emit the SUMMARY line. Do not re-analyze.
10. End your response with a single line: SUMMARY: broken=<n> stale=<n> proposals=<n> press_new=<n>

Hard rules: read-only on NB content. NEVER call 'nlm source add/delete' or any mutating command. Propose only (Article 1)."

log "Mode B+C ($C_SCOPE) via brain=${NB_CURATOR_BRAIN:-agy}. Report: $REPORT_PATH"

# ── Brain: agy Gemini 3.5 Flash primary, claude-cascade --agent fallback ──────
# The brain is PROPOSE-ONLY now that every deletion is deterministic (Step 1 +
# Step 1c), so Flash is sufficient — and it frees Claude MAX quota. It is also a
# REAL fallback: the old path (claude-cascade --agent) made tier3-5 self-skip
# whenever --agent was set ("neither CLI loads Claude Code agents"), so a
# quota-exhausted nb-curator simply died (ALL TIERS FAILED). agy in print mode
# with --dangerously-skip-permissions executes nlm + writes files autonomously
# (verified 2026-06-16). Override with NB_CURATOR_BRAIN=claude.
export PATH="$HOME/.local/bin:$PATH"   # ensure the brain (agy/claude) finds nlm
TMPOUT=$(mktemp)
AGY_BIN="$HOME/.local/bin/agy"
BRAIN_USED=""; EXIT=1
if [ "${NB_CURATOR_BRAIN:-agy}" = "agy" ] && [ -x "$AGY_BIN" ]; then
    printf '%s' "$MODE_PROMPT" | "$AGY_BIN" --dangerously-skip-permissions \
        --model "Gemini 3.5 Flash (Medium)" -p --print-timeout 20m \
        > "$TMPOUT" 2>> "$LOG"
    EXIT=$?
    if [ "$EXIT" -eq 0 ] && grep -qE 'SUMMARY:' "$TMPOUT"; then
        BRAIN_USED="agy-flash"
    else
        log "agy brain failed (exit=$EXIT or no SUMMARY line) — falling back to claude-cascade"
    fi
fi
if [ -z "$BRAIN_USED" ]; then
    "$HOME/scripts/claude-cascade.sh" "$MODE_PROMPT" \
        --model claude-sonnet-5 \
        --agent nb-curator \
        > "$TMPOUT" 2>> "$LOG"
    EXIT=$?
    BRAIN_USED="claude-cascade"
fi
log "brain used: $BRAIN_USED (exit=$EXIT)"
cat "$TMPOUT" >> "$LOG"

# ── Step 4: Telegram digest ONLY if action/anomaly ────────────────────────────
SUMMARY_LINE=$(grep -oE 'SUMMARY: broken=[0-9]+ stale=[0-9]+ proposals=[0-9]+ press_new=[0-9]+' "$TMPOUT" | tail -1)
rm -f "$TMPOUT"

BROKEN=$(echo "$SUMMARY_LINE" | grep -oE 'broken=[0-9]+' | cut -d= -f2); BROKEN=${BROKEN:-0}
PROPOSALS=$(echo "$SUMMARY_LINE" | grep -oE 'proposals=[0-9]+' | cut -d= -f2); PROPOSALS=${PROPOSALS:-0}

if [ "$EXIT" -ne 0 ]; then
    log "nb-curator ALL TIERS FAILED (exit=$EXIT)"
    curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TG_CHAT}" \
        -d "text=⚠️ nb-curator daily FAILED (exit=$EXIT). Log: ~/logs/nb-curator.log" >/dev/null 2>&1
elif [ "$DEDUP_DELETED" -gt 0 ] || [ "$CHALLENGE_DELETED" -gt 0 ] || [ "$BROKEN" -gt 0 ] || [ "$PROPOSALS" -gt 0 ]; then
    MSG="🗂 nb-curator $DATE_STR: ${DEDUP_DELETED} exact-dup + ${CHALLENGE_DELETED} challenge removed · ${BROKEN} broken · ${PROPOSALS} proposals. Report: ${REPORT_PATH##*/}"
    curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TG_CHAT}" -d "text=$MSG" >/dev/null 2>&1
    log "Telegram sent: $MSG"
else
    log "nb-curator daily OK — no action/anomaly, no Telegram (dedup=0 challenge=0 broken=0 proposals=0)"
fi

exit 0
