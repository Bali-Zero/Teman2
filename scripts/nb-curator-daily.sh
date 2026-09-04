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
# Sibling scripts resolve from THIS file's own directory, never from $HOME: the
# gate and the notification gateway must be the versions that ship with this
# wrapper, or the wrapper is verifying itself against a copy it did not bring
# (superscar #1 — HOME-fork). OUTPUT_DIR deliberately stays $HOME-anchored: the
# reports belong to the machine's checkout, not to whatever worktree happens to
# be executing.
SCRIPT_DIR="${0:A:h}"
ARTIFACT_GATE="$SCRIPT_DIR/nb_curator_artifact_gate.py"
TG_NOTIFY="$SCRIPT_DIR/tg_notify.py"
# Overridable so a test can take its OWN lock instead of the machine-wide one —
# a test that grabs /tmp/nb-curator.lock would block (or be blocked by) the real
# 04:00 cron on Pro (W96: tests must never touch production state).
LOCK_FILE="${NB_CURATOR_LOCK_FILE:-/tmp/nb-curator.lock}"
LOG="$HOME/logs/nb-curator.log"

# Agent definitions are project-level (`.claude/agents/`, git-tracked) and OUTRANK the
# machine-local `~/.claude/agents/` copy -- but only when the process cwd is inside the repo.
# launchd starts this job with cwd=/ and claude-cascade.sh never cd's, so without this the
# untracked HOME copy is the only definition that can ever load (cicatrix family #1, HOME-fork).
NUZ_ROOT="${NUZ_ROOT:-$HOME/nuzantara}"
if [ -f "$NUZ_ROOT/.claude/agents/nb-curator.md" ]; then
  cd "$NUZ_ROOT" || exit 1
else
  echo "[$(date)] WARN: $NUZ_ROOT/.claude/agents/nb-curator.md missing -- falling back to the ~/.claude/agents copy" >> "$LOG"
fi
# G2_heartbeat — proof of life at ~/.organism/last_seen/<id>.json, which is what
# organs_registry.yaml (bridge_source.path) and the stale-detector actually read.
# The library is INVOKED under `bash`, never sourced: this wrapper is zsh, and
# heartbeat.sh declares `local status=…` — `status` is a read-only special
# parameter in zsh, so sourcing it dies with "read-only variable: status" and
# writes nothing (measured 2026-07-29). Every other zsh wrapper on the fleet
# already invokes it the same way; the lib's own docstring only advertises the
# bash source-pattern. Resolution prefers THIS checkout's copy over ~/scripts/
# for the same reason as ARTIFACT_GATE above (superscar #1).
ORGAN_ID="pro.nb_curator_daily"
if [ -n "${ORGANISM_HEARTBEAT_LIB:-}" ]; then
    HEARTBEAT_LIB="$ORGANISM_HEARTBEAT_LIB"
elif [ -r "$SCRIPT_DIR/lib/heartbeat.sh" ]; then
    HEARTBEAT_LIB="$SCRIPT_DIR/lib/heartbeat.sh"
else
    HEARTBEAT_LIB="$HOME/scripts/lib/heartbeat.sh"
fi
OUTPUT_DIR="$HOME/nuzantara/research/nb-health"
DEDUP_SCRIPT="$HOME/nuzantara/apps/bali-intel-scraper/scripts/nb_dedup_exact_url.py"
DATE_STR=$(TZ=Asia/Makassar date +%Y-%m-%d)
MONTH_STR=$(TZ=Asia/Makassar date +%Y-%m)
DOW=$(TZ=Asia/Makassar date +%u)   # 1=Mon..7=Sun
DAY=$(TZ=Asia/Makassar date +%-d)  # day-of-month
# (TG_CHAT removed: the gateway resolves the destination. A hardcoded chat_id
# left behind here would read like a knob and change nothing when turned.)

mkdir -p "$HOME/logs" "$OUTPUT_DIR"

# The sidecar must carry the REAL outcome and must be written on EVERY exit
# path. One unconditional write at the end would say "alive" for a run that
# reported ALL TIERS FAILED — the same cron-theater the exit codes below were
# added to kill. The EXIT trap covers the paths nobody wrote on purpose (an
# unset variable under `set -u`, an `exit` added later): without it those runs
# leave NO sidecar, which reads as "never scheduled" rather than "died", and the
# two want different cures. Measured, so nobody trusts it further than it goes:
# zsh runs this trap on `exit`, on a `set -u` abort and on a `set -e` abort, but
# NOT on a fatal signal — a SIGTERM'd run (rc=143) still leaves no sidecar.
HB_EMITTED=0
heartbeat() {  # heartbeat <status> [note]
    HB_EMITTED=1
    [ -f "$HEARTBEAT_LIB" ] || return 0
    bash "$HEARTBEAT_LIB" "$ORGAN_ID" "$1" "${2:-}" || true
}
_hb_on_exit() {
    local rc=$?
    if [ "$HB_EMITTED" -eq 0 ]; then
        heartbeat error "aborted before verdict (rc=$rc)"
    fi
    return 0
}
trap _hb_on_exit EXIT

# ── flock — prevent overlapping runs ──────────────────────────────────────────
# `flock` is NOT a macOS builtin — it arrives via homebrew util-linux and is
# present on Pro (/opt/homebrew/bin/flock) and absent on M5 (measured
# 2026-07-28). The old form was `flock -n 9 || { log "already running"; exit 0; }`,
# so on a machine without the binary the 127 took the same branch as a held lock:
# every run would log "already running, skipping" and exit 0 having done nothing,
# green and inert (superscar #2 — the guard's own failure is indistinguishable
# from the state it guards). Missing binary now degrades LOUDLY to an unlocked
# run; only a genuinely held lock skips.
exec 9>"$LOCK_FILE"
if command -v flock >/dev/null 2>&1; then
    flock -n 9 || {
        echo "$(TZ=Asia/Makassar date '+%Y-%m-%dT%H:%M:%S WITA'): nb-curator already running, skipping" >> "$LOG"
        # `warning`, not `ok`: the organ is alive but did NO work. A lock held by
        # a run that hung would otherwise paint a green heartbeat every day for
        # a curator that has not curated anything since.
        heartbeat warning "skipped: another run holds $LOCK_FILE"
        exit 0
    }
else
    echo "$(TZ=Asia/Makassar date '+%Y-%m-%dT%H:%M:%S WITA'): WARN: flock not found — running WITHOUT the overlap lock (brew install util-linux)" >> "$LOG"
fi

log() { echo "$(TZ=Asia/Makassar date '+%Y-%m-%dT%H:%M:%S WITA'): $*" >> "$LOG"; }
log "nb-curator-daily started (DOW=$DOW DAY=$DAY)"

# ── Telegram: through the gateway, never a naked curl ─────────────────────────
# `curl … >/dev/null 2>&1` makes a 401, a wrong chat_id and a delivered message
# indistinguishable — judge the REPLY, never the exit code (W104) — and it needs
# TELEGRAM_BOT_TOKEN to already be in this process's environment, which on a
# launchd cron is exactly the thing that goes missing. tg_notify.py owns the
# token chain (env -> ~/.nuzantara-secrets.env -> ssh relay -> spool) and never
# fails its caller; the one thing it cannot do is exist when it is absent, so
# THAT case is the loud one — an alarm that cannot be delivered still leaves a
# trace in the log instead of evaporating.
tg() {  # tg <tier> <text...>
    local tier="$1"; shift
    if [ ! -f "$TG_NOTIFY" ]; then
        log "ALERT NOT SENT — gateway missing at $TG_NOTIFY [$tier]: $*"
        return 1
    fi
    local out rc
    if out=$(/usr/bin/python3 "$TG_NOTIFY" --tier "$tier" --source nb-curator "$*" 2>&1); then
        rc=0
    else
        rc=$?
    fi
    log "tg[$tier] rc=$rc ${out:-<no output>}"
    return $rc
}

# ── Step 1: deterministic exact-URL dedup (auto-apply, cap 20) ────────────────
DEDUP_DELETED=0
if [ -f "$DEDUP_SCRIPT" ]; then
    DEDUP_OUT=$(timeout 300 /usr/bin/python3 "$DEDUP_SCRIPT" --apply --cap 20 2>>"$LOG")
    log "dedup: $DEDUP_OUT"
    DEDUP_DELETED=$(echo "$DEDUP_OUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('deleted',0))" 2>/dev/null || echo 0)
    # cap-exceeded (exit 2) → alert: anomaly, possible matching bug
    if echo "$DEDUP_OUT" | grep -q 'aborted_cap'; then
        tg p0 "⚠️ nb-curator dedup ABORT: planned deletes > cap 20 (possible matching bug). Check ~/logs/nb-curator.log"
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
        tg p0 "⚠️ nb-curator challenge-sweep ABORT: planned deletes > cap 20 (possible title-match bug). Check ~/logs/nb-curator.log"
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
INV_GEN="$HOME/nuzantara/scripts/nb_generate_inventory.py"
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

MODE_PROMPT="Run nb-curator daily pass. FIRST read your full operating spec at $NUZ_ROOT/.claude/agents/nb-curator.md (use your file-read tool) and follow it exactly. You have shell + file tools: use them to write the report file. Today is $DATE_STR.

HARD LIMITS — violating these = failure:
- Do NOT write, create, or run ANY python/bash analysis or diff scripts. Read files and reason directly.
- Do NOT run 'git add', 'git commit', 'git push', or any other git command. Write the report file
  with your file-write tool and stop there — promoting the report to origin/main is a SEPARATE
  process, not part of this task (three prior local-only commits on this machine's main checkout
  came from exactly this: an agentic run that finished writing and then 'helpfully' committed on
  its own, bypassing the worktree+PR flow and leaving a commit that sits ahead of origin unpushed).
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
The file's FIRST THREE LINES must be exactly this YAML frontmatter block (verbatim, no
variation) so the report passes the repo's R1 adversarial-review CI gate as a declared
machine-generated exemption — every prior report missing this failed R1 on the PR that
harvested it:
---
adversarial_review: exempt-machine-report # nb-curator daily health snapshot (generated artifact, not a research deliverable)
---
Then a blank line, then the report body starting with the '# NB Arsenal Health Report' heading.
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
    # `-p`/`--print` TAKES A VALUE (measured live 2026-08-13, both forms exit 0):
    # `-p --print-timeout 20m` binds the literal string "--print-timeout" as the
    # prompt and leaves "20m" a stray positional — agy never reads stdin. Prompt
    # must be `-p`'s own argv value; --print-timeout stays a separate flag.
    # NOTE: agy v1.1.12 has no stdin path, so $MODE_PROMPT is now `ps`-visible
    # while the process runs (see PR body for the PII disclosure this forces).
    "$AGY_BIN" --dangerously-skip-permissions \
        --model "Gemini 3.5 Flash (Medium)" -p "$MODE_PROMPT" --print-timeout 20m \
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

# ── Step 3b: ARTIFACT GATE — did the brain actually write the report? ─────────
# Everything below this line reads the brain's STDOUT. Nothing read the FILE.
# A run whose brain prints a flawless `SUMMARY:` line and writes no report at all
# used to land here as "OK — no action/anomaly" with a green cron receipt, and
# the R1 frontmatter that the prompt mandates verbatim was enforced by nothing
# but the model's compliance — which measured 3-of-4 on the reports that reached
# main (2026-07-27 arrived with no frontmatter; PR #3254 merged with the required
# R1 check RED; #3416 was blocked by it). This step is the deterministic half.
# `|| GATE_RC=$?` is the errexit-immune capture (W101): a bare assignment aborts
# the script under `set -e` BEFORE the verdict can be read, which is exactly how
# a fail-closed branch gets decapitated.
GATE_RC=0
if [ -f "$ARTIFACT_GATE" ]; then
    /usr/bin/python3 "$ARTIFACT_GATE" --report "$REPORT_PATH" --fix >>"$LOG" 2>&1 || GATE_RC=$?
    log "artifact gate rc=$GATE_RC on $REPORT_PATH"
else
    # Not a silent skip: an absent gate means the artifact is unverified, and
    # "unverified" must never read the same as "verified clean" (superscar #2).
    GATE_RC=127
    log "ARTIFACT GATE MISSING at $ARTIFACT_GATE — report NOT verified"
fi

# ── Step 4: Telegram digest ONLY if action/anomaly ────────────────────────────
SUMMARY_LINE=$(grep -oE 'SUMMARY: broken=[0-9]+ stale=[0-9]+ proposals=[0-9]+ press_new=[0-9]+' "$TMPOUT" | tail -1)
rm -f "$TMPOUT"

BROKEN=$(echo "$SUMMARY_LINE" | grep -oE 'broken=[0-9]+' | cut -d= -f2); BROKEN=${BROKEN:-0}
PROPOSALS=$(echo "$SUMMARY_LINE" | grep -oE 'proposals=[0-9]+' | cut -d= -f2); PROPOSALS=${PROPOSALS:-0}

if [ "$EXIT" -ne 0 ]; then
    log "nb-curator ALL TIERS FAILED (exit=$EXIT)"
    tg p0 "⚠️ nb-curator daily FAILED (exit=$EXIT). Log: ~/logs/nb-curator.log"
elif [ "$GATE_RC" -ne 0 ]; then
    # The brain said it succeeded and the artifact says otherwise. Believing the
    # brain here is the whole disease: green receipt, no report.
    log "nb-curator ARTIFACT GATE FAILED (rc=$GATE_RC) despite brain exit=0"
    tg p0 "⚠️ nb-curator $DATE_STR: brain OK but the report failed the artifact gate (rc=$GATE_RC) — ${REPORT_PATH##*/}. Log: ~/logs/nb-curator.log"
elif [ "$DEDUP_DELETED" -gt 0 ] || [ "$CHALLENGE_DELETED" -gt 0 ] || [ "$BROKEN" -gt 0 ] || [ "$PROPOSALS" -gt 0 ]; then
    MSG="🗂 nb-curator $DATE_STR: ${DEDUP_DELETED} exact-dup + ${CHALLENGE_DELETED} challenge removed · ${BROKEN} broken · ${PROPOSALS} proposals. Report: ${REPORT_PATH##*/}"
    tg digest "$MSG"
else
    log "nb-curator daily OK — no action/anomaly, no Telegram (dedup=0 challenge=0 broken=0 proposals=0)"
fi

# The old unconditional `exit 0` made every cron receipt green, including the
# runs that reported ALL TIERS FAILED two lines above — the receipt is the only
# thing a downstream watcher reads (W107: five wrapper families write receipts,
# and a job that never fails is a job nobody ever looks at).
if [ "$EXIT" -ne 0 ]; then
    heartbeat error "all brain tiers failed (exit=$EXIT)"
    exit 1
elif [ "$GATE_RC" -ne 0 ]; then
    # degraded, not error: the brain ran, the ARTIFACT is what failed.
    heartbeat degraded "artifact gate rc=$GATE_RC on ${REPORT_PATH##*/}"
    exit 2
fi
heartbeat ok "dedup=$DEDUP_DELETED challenge=$CHALLENGE_DELETED broken=$BROKEN proposals=$PROPOSALS brain=$BRAIN_USED"
exit 0
