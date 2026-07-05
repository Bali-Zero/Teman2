#!/bin/zsh
# regulatory-watcher cron wrapper — multi-LLM cascade
# Order: Claude OAuth (Sonnet 5) → Gemini 3.1 Pro free → Codex GPT-5.5 → Ollama qwen3.5:9b local
# Cost: 0$ (4 tier all subscription/free/local)
#
# TAC-2 A4 (2026-07-05) — the 07-05 run failure taught four lessons, all cured here:
#   1. sonnet-5 in --print mode spawned its 6-step work as a BACKGROUND task; the CLI
#      terminated it at the 600s print ceiling and exited 0 → wrapper marked SUCCESS
#      with no delta on disk. Cure: raise the ceiling + tell the model to work inline.
#   2. "exit 0 + no quota marker" is NOT success for a job whose contract is a file.
#      Cure: every tier's success now requires the delta file to EXIST (ensure_delta).
#   3. Tiers 2-4 print JSON to stdout but cannot write files → they were alert-theater.
#      Cure: ensure_delta extracts a valid delta JSON from the tier's output.
#   4. The launchd context can lose TCC on ~/Desktop (W84; Pro reboot 07-04) making the
#      whole contract unfulfillable. Cure: fail FAST and LOUD (exit 78) instead of
#      burning 4 LLM tiers to then discover the file can't land.

# NO `-e`: each tier may exit non-zero and the cascade MUST survive to capture
# EXIT=$? and fall through to the next tier (guardian-of-guardians audit 2026-06-11;
# with -e the script died at the first failing tier and fallback never fired).
set -uo pipefail

# Defense-in-depth: never pay-per-token Anthropic
unset ANTHROPIC_API_KEY

# nlm-profile (2026-06-10): single-account consolidation. zero@balizero.com is
# DECOMMISSIONED as an NLM account (login problems / expiring). All NB live under
# antonellosiano@gmail.com = the `default` profile (86 NB, 3622 sources). The old
# `zero` profile was itself logged in as antonellosiano@ and has been deleted.
# Empirically verified 2026-06-10: default sees identical NB-INTEL UUIDs.
export NLM_PROFILE=default

[ -f "$HOME/.nuzantara-secrets.env" ] && set -a && source "$HOME/.nuzantara-secrets.env" && set +a

mkdir -p "$HOME/Desktop/nuzantara/research/regulatory" "$HOME/logs"

LOG="$HOME/logs/regulatory-watcher.log"
DATE=$(TZ=Asia/Makassar date +%Y-%m-%d)
DELTA_JSON="$HOME/Desktop/nuzantara/research/regulatory/${DATE}-delta.json"
DELTA_BASENAME="${DATE}-delta.json"

# W84 fail-fast probe (TAC-2 A4): if this launchd context cannot READ ~/Desktop
# (TCC grant lost — observed on Pro after the 2026-07-04 reboot: the zsh job got
# "Operation not permitted" while a bash-rooted job read ~/Desktop fine), the
# delta can never land. Abort loudly with exit 78 (config error) BEFORE burning
# LLM tiers; launchd's non-zero exit is picked up by launchd_liveness_detector.
if [ ! -r "$HOME/Desktop/nuzantara/CLAUDE.md" ]; then
    echo "[$(date)] FATAL: TCC denies ~/Desktop/nuzantara in this launchd context (W84) — re-grant Full Disk Access to the job's interpreter. Aborting before any LLM tier." >> "$LOG"
    exit 78
fi

# sonnet-5 --print + background tasks (2026-07-05): the CLI kills backgrounded
# work after 600s by default. 30 min ceiling keeps a legitimate long run alive;
# the prompt below also forbids backgrounding outright.
export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS="${CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS:-1800000}"

# Organism heartbeat (heartbeat-organs TAC 2026-07-02): reverse-promoted from the
# M5 HOME copy 2026-07-03 — the instrumentation lived only in ~/scripts and never
# reached the repo canon (#1 HOME-fork reverse debt, caught by proprioception).
# Lib resolution prefers ~/scripts/lib (OUTSIDE the TCC-protected ~/Desktop —
# superscar #1 antidote: relocate payloads out of Desktop) and falls back to the
# repo canon. Arming the ~/scripts/lib copy on Pro/M5 is tracked in PENDING-ARMS.
if [ -n "${ORGANISM_HEARTBEAT_LIB:-}" ]; then
    HEARTBEAT_LIB="$ORGANISM_HEARTBEAT_LIB"
elif [ -r "$HOME/scripts/lib/heartbeat.sh" ]; then
    HEARTBEAT_LIB="$HOME/scripts/lib/heartbeat.sh"
else
    HEARTBEAT_LIB="$HOME/Desktop/nuzantara/scripts/lib/heartbeat.sh"
fi
ORGANISM_HB_STATUS="starting"
ORGANISM_HB_NOTE="regulatory watcher start"

organism_hb_set() {
    ORGANISM_HB_STATUS="$1"
    ORGANISM_HB_NOTE="${2:-}"
}

organism_hb_finalize() {
    local rc="${1:-0}"
    if [ "$rc" -eq 0 ]; then
        if [ "$ORGANISM_HB_STATUS" = "starting" ]; then
            organism_hb_set ok "completed"
        fi
    elif [ "$ORGANISM_HB_STATUS" = "starting" ] || [ "$ORGANISM_HB_STATUS" = "ok" ]; then
        organism_hb_set error "rc=${rc}"
    fi
    if [ -f "$HEARTBEAT_LIB" ]; then
        bash "$HEARTBEAT_LIB" "pro.regulatory_watcher_daily" "$ORGANISM_HB_STATUS" "$ORGANISM_HB_NOTE" || true
    fi
}

trap 'rc=$?; organism_hb_finalize "$rc"' EXIT

echo "[$(date)] regulatory-watcher run starting for $DATE" >> "$LOG"

PROMPT_CLAUDE="Run the regulatory-watcher agent for today ($DATE). Execute all 6 workflow steps autonomously. Read ~/.claude/agents/regulatory-watcher.md for full spec. Today is $DATE WITA. Yesterday's delta file (if any) is in ~/Desktop/nuzantara/research/regulatory/. Emit JSON to today's file and Telegram alert only if new_today_count > 0. IMPORTANT: do ALL the work INLINE in this session — never spawn background tasks or background agents: this is a one-shot print-mode run and backgrounded work is terminated at exit, leaving no file on disk (incident 2026-07-05)."

# Generic prompt re-usable across LLMs (no Claude-specific syntax)
PROMPT_GENERIC="You are the regulatory-watcher for Bali Zero (Indonesian business services agency). Today is $DATE WITA. Task: detect new Indonesian regulations published in last 48h that affect Bali Zero service lines (visa/immigration, tax, property, regulatory/HR, health). Sources to query (use whichever you can reach): Hukumonline, Ortax, DDTC, MUC, IKPI, JDIH Kemenkumham/Kemenkeu/Kemnaker, peraturan.go.id (with Mozilla User-Agent), pajak.go.id. Filter to reg-types: Permenkumham, PMK, PP, Perpres, UU, Permenaker, Permenkes, Peraturan BKPM. Emit JSON to ~/Desktop/nuzantara/research/regulatory/${DATE}-delta.json with schema: {run_at, today, new_today_count, partial:bool, deltas:[{citation,title_id,title_en,service_line,summary,source,verbatim_excerpt}], seen_citations}. If new_today_count>0, send Telegram via curl to api.telegram.org/bot\$TELEGRAM_BOT_TOKEN/sendMessage chat_id=\$TELEGRAM_OWNER_CHAT_ID. Cite verbatim. No paraphrasing. No emoji in JSON."

TMPOUT=$(mktemp)
SUCCESS=0
USED_LLM=""

# Stdlib-only python for the output-extractor (json only — no redis needed here).
# The pyenv pin below (eventbus block) stays Pro-specific; this one must work on
# any machine the wrapper is deployed to.
PYBIN="${REGWATCH_PYTHON:-$(command -v python3 || echo /usr/bin/python3)}"

# W81-fix (2026-06-15), zsh-native rewrite (TAC-2 A4): the cron `claude` runs with
# W79 worktree-isolation hooks active, so it may write the delta to a worktree
# branch instead of the main checkout. Recover it. (N.om) = null_glob + plain
# files + mtime-desc: the old `ls -t glob` printed "no matches found" noise AND
# would have listed the whole cwd under null_glob with an empty expansion.
recover_delta() {
    setopt local_options null_glob
    local -a _hits
    _hits=( "$HOME"/Desktop/nuzantara/.worktrees/*/research/regulatory/"$DELTA_BASENAME"(N.om) )
    if (( ${#_hits} > 0 )); then
        cp "${_hits[1]}" "$DELTA_JSON" && echo "[$(date)] W81-fix: recovered delta from worktree file ${_hits[1]} -> main" >> "$LOG"
        return 0
    fi
    local _wt_branch
    _wt_branch="$(cd "$HOME/Desktop/nuzantara" && git for-each-ref --sort=-committerdate --format='%(refname:short)' 'refs/heads/agent/*/intel/watcher-*' 2>/dev/null | head -1)"
    if [ -n "$_wt_branch" ] && (cd "$HOME/Desktop/nuzantara" && git cat-file -e "$_wt_branch:research/regulatory/$DELTA_BASENAME" 2>/dev/null); then
        (cd "$HOME/Desktop/nuzantara" && git show "$_wt_branch:research/regulatory/$DELTA_BASENAME") > "$DELTA_JSON" \
          && echo "[$(date)] W81-fix: recovered delta from branch $_wt_branch -> main" >> "$LOG"
        return 0
    fi
    return 1
}

# Tiers 2-4 print JSON to stdout but cannot write files (agy/ollama are pure
# text-out) — without this they were alert-theater: "success" with no artifact.
# Extract the first parseable object carrying the delta schema and land it.
extract_delta_from_output() {
    local _src="$1"
    "$PYBIN" - "$_src" "$DELTA_JSON" <<'PYEOF' 2>>"$LOG"
import json, sys
src, dst = sys.argv[1], sys.argv[2]
text = open(src, encoding="utf-8", errors="replace").read()
best = None
for start in [i for i, ch in enumerate(text) if ch == "{"]:
    depth = 0
    for end in range(start, min(len(text), start + 200_000)):
        if text[end] == "{":
            depth += 1
        elif text[end] == "}":
            depth -= 1
            if depth == 0:
                chunk = text[start:end + 1]
                try:
                    obj = json.loads(chunk)
                except Exception:
                    break
                if isinstance(obj, dict) and "new_today_count" in obj and "deltas" in obj:
                    best = obj
                break
    if best is not None:
        break
if best is None:
    sys.exit(1)
with open(dst, "w", encoding="utf-8") as fh:
    json.dump(best, fh, ensure_ascii=False, indent=2)
print(f"extracted delta JSON from LLM output -> {dst}")
PYEOF
}

# The tier contract (TAC-2 A4): a tier SUCCEEDED only if the delta file exists —
# on disk, recovered from a worktree, or extracted from the tier's own output.
# "exit 0" alone marked the 2026-07-05 hallucinated/backgrounded run as green.
ensure_delta() {
    local _out="$1"
    [ -f "$DELTA_JSON" ] && return 0
    recover_delta && [ -f "$DELTA_JSON" ] && return 0
    extract_delta_from_output "$_out" && [ -f "$DELTA_JSON" ] && return 0
    return 1
}

# Tier 1: Claude OAuth Sonnet
echo "[$(date)] tier 1 — claude sonnet" >> "$LOG"
"$HOME/.local/bin/claude" --print --model claude-sonnet-5 "$PROMPT_CLAUDE" >"$TMPOUT" 2>&1
EXIT=$?
if [ $EXIT -eq 0 ] && ! grep -qE "out of extra usage|usage limit|quota exceeded|rate.limit" "$TMPOUT" && ensure_delta "$TMPOUT"; then
    SUCCESS=1
    USED_LLM="claude-sonnet-5"
elif [ $EXIT -eq 0 ]; then
    echo "[$(date)] tier 1 exit 0 but NO delta file landed (hallucinated/backgrounded output?) — cascading" >> "$LOG"
fi
cat "$TMPOUT" >> "$LOG"

# Tier 2: agy (Antigravity CLI Gemini 3.1 Pro, Google AI Ultra sub)
if [ $SUCCESS -eq 0 ]; then
    echo "[$(date)] tier 1 failed/exhausted — falling back to agy (Gemini 3.1 Pro)" >> "$LOG"
    > "$TMPOUT"
    printf '%s' "$PROMPT_GENERIC" | /Users/nuzantara/.local/bin/agy -p --print-timeout 5m >"$TMPOUT" 2>&1
    EXIT=$?
    if [ $EXIT -eq 0 ] && ! grep -qE "quota|limit|429|exhausted|TerminalQuotaError" "$TMPOUT" && ensure_delta "$TMPOUT"; then
        SUCCESS=1
        USED_LLM="gemini-3.1-pro-agy"
    fi
    cat "$TMPOUT" >> "$LOG"
fi

# Tier 3: Codex GPT-5.5
if [ $SUCCESS -eq 0 ]; then
    echo "[$(date)] tier 2 failed/exhausted — falling back to codex" >> "$LOG"
    > "$TMPOUT"
    /opt/homebrew/bin/codex exec --full-auto "$PROMPT_GENERIC" >"$TMPOUT" 2>&1
    EXIT=$?
    if [ $EXIT -eq 0 ] && ! grep -qE "usage.limit|quota|exhausted" "$TMPOUT" && ensure_delta "$TMPOUT"; then
        SUCCESS=1
        USED_LLM="codex-gpt-5.5"
    fi
    cat "$TMPOUT" >> "$LOG"
fi

# Tier 4: Ollama local (always available, lower quality but free + unlimited)
if [ $SUCCESS -eq 0 ]; then
    echo "[$(date)] tier 3 failed/exhausted — falling back to ollama qwen3.5:9b local" >> "$LOG"
    > "$TMPOUT"
    /opt/homebrew/bin/ollama run qwen3.5:9b "$PROMPT_GENERIC" >"$TMPOUT" 2>&1
    EXIT=$?
    if [ $EXIT -eq 0 ] && ensure_delta "$TMPOUT"; then
        SUCCESS=1
        USED_LLM="ollama-qwen3.5:9b-local"
    fi
    cat "$TMPOUT" >> "$LOG"
fi

if [ $SUCCESS -eq 1 ]; then
    echo "[$(date)] regulatory-watcher run complete — used: $USED_LLM" >> "$LOG"
    organism_hb_set ok "used ${USED_LLM}"

    # W1.4: emit eventbus events for any new regulatory deltas in today's JSON.
    # Recovery/extraction already ran per-tier inside ensure_delta(); SUCCESS=1
    # implies the file exists. The guard below stays as a belt (a sibling process
    # could remove the file between the tier check and here — seen 2026-05-13).
    if [ ! -f "$DELTA_JSON" ]; then
        echo "[$(date)] WARNING: $USED_LLM reported success but $DELTA_JSON does NOT exist on disk — possible hallucinated tool output, skipping eventbus publish" >> "$LOG"
    fi

    if [ -f "$DELTA_JSON" ]; then
        # Pin pyenv python3 explicitly (PATH propagation through zsh -lc resolves
        # to Homebrew 3.14 which lacks `redis`; pyenv 3.11.11 has redis 7.3.0).
        /Users/nuzantara/.pyenv/versions/3.11.11/bin/python3 -c "
import json, sys
sys.path.insert(0, '$HOME/scripts')
from eventbus import publish
try:
    d = json.load(open('$DELTA_JSON'))
except Exception as e:
    print(f'cannot parse {\"$DELTA_JSON\"}: {e}', file=sys.stderr); sys.exit(0)
deltas = d.get('deltas', [])
if not deltas:
    print(f'no deltas to emit ({d.get(\"new_today_count\", 0)} new)')
    sys.exit(0)
for delta in deltas:
    sl = delta.get('service_line', [])
    if isinstance(sl, str): sl = [sl]
    try:
        eid = publish('regulatory.delta.detected', {
            'citation': delta.get('citation', 'unknown'),
            'regulation_type': (delta.get('citation') or '').split()[0] if delta.get('citation') else 'unknown',
            'service_lines': sl or ['unknown'],
            'summary': (delta.get('summary') or '')[:500],
            'urgency': delta.get('urgency', 'medium'),
            'source': delta.get('source', 'regulatory-watcher'),
            'detected_at': delta.get('first_seen_at') or d.get('run_at'),
        }, emitted_by='regulatory-watcher')
        print(f'emitted {eid} for {delta.get(\"citation\", \"?\")}')
    except Exception as e:
        print(f'emit failed for {delta.get(\"citation\")}: {e}', file=sys.stderr)

# Intel Lake Wave 4 (2026-05-12): enqueue each delta to the Intel Lake
# outbox so the unified pipeline sees regulatory findings alongside other
# producers. Best-effort — never block the watcher run.
try:
    import hashlib
    from intel_lake_outbox import enqueue as _lake_enqueue
    for delta in deltas:
        cit = delta.get('citation', 'unknown')
        url = delta.get('source') or f'regulatory-watcher://delta/{cit}'
        title = delta.get('title_en') or delta.get('title_id') or cit
        ch = hashlib.sha256((cit + ' ' + title).encode()).hexdigest()[:32]
        sl = delta.get('service_line', [])
        if isinstance(sl, str): sl = [sl]
        try:
            _lake_enqueue('regulatory_watcher', {
                'producer_name': 'regulatory_watcher',
                'canonical_url': url,
                'content_hash': ch,
                'title': (cit + ' — ' + title)[:500],
                'summary': (delta.get('summary') or '')[:2000],
                'source_domain': delta.get('source_domain') or 'regulatory-watcher',
                'language': 'id',
                'jurisdiction': 'ID-national',
                'topic_tags': ['regulation', delta.get('regulation_type','regulation')] + (sl or []),
                'published_at': delta.get('first_seen_at') or d.get('run_at'),
                'score': None,
                'raw_payload': {
                    'citation': cit,
                    'urgency': delta.get('urgency','medium'),
                    'verbatim_excerpt': (delta.get('verbatim_excerpt') or '')[:2000],
                },
            })
        except Exception as e2:
            print(f'lake enqueue failed for {cit}: {e2}', file=sys.stderr)
except Exception as e:
    print(f'intel_lake_outbox import skipped: {e}', file=sys.stderr)
" >> "$LOG" 2>&1
    fi
else
    echo "[$(date)] regulatory-watcher ALL TIERS FAILED — manual investigation needed" >> "$LOG"
    organism_hb_set error "all tiers failed"
fi

rm -f "$TMPOUT"
exit 0
