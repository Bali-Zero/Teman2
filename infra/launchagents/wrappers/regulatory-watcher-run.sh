#!/bin/zsh
# regulatory-watcher cron wrapper — multi-LLM cascade
# Order: Claude OAuth (Sonnet 5) → Gemini 3.1 Pro free → Codex GPT-5.5 → Ollama qwen3.5:9b local
# Cost: 0$ (4 tier all subscription/free/local)

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

echo "[$(date)] regulatory-watcher run starting for $DATE" >> "$LOG"

PROMPT_CLAUDE="Run the regulatory-watcher agent for today ($DATE). Execute all 6 workflow steps autonomously. Read ~/.claude/agents/regulatory-watcher.md for full spec. Today is $DATE WITA. Yesterday's delta file (if any) is in ~/Desktop/nuzantara/research/regulatory/. Emit JSON to today's file and Telegram alert only if new_today_count > 0."

# Generic prompt re-usable across LLMs (no Claude-specific syntax)
PROMPT_GENERIC="You are the regulatory-watcher for Bali Zero (Indonesian business services agency). Today is $DATE WITA. Task: detect new Indonesian regulations published in last 48h that affect Bali Zero service lines (visa/immigration, tax, property, regulatory/HR, health). Sources to query (use whichever you can reach): Hukumonline, Ortax, DDTC, MUC, IKPI, JDIH Kemenkumham/Kemenkeu/Kemnaker, peraturan.go.id (with Mozilla User-Agent), pajak.go.id. Filter to reg-types: Permenkumham, PMK, PP, Perpres, UU, Permenaker, Permenkes, Peraturan BKPM. Emit JSON to ~/Desktop/nuzantara/research/regulatory/${DATE}-delta.json with schema: {run_at, today, new_today_count, partial:bool, deltas:[{citation,title_id,title_en,service_line,summary,source,verbatim_excerpt}], seen_citations}. If new_today_count>0, send Telegram via curl to api.telegram.org/bot\$TELEGRAM_BOT_TOKEN/sendMessage chat_id=\$TELEGRAM_OWNER_CHAT_ID. Cite verbatim. No paraphrasing. No emoji in JSON."

TMPOUT=$(mktemp)
SUCCESS=0
USED_LLM=""

# Tier 1: Claude OAuth Sonnet
echo "[$(date)] tier 1 — claude sonnet" >> "$LOG"
"$HOME/.local/bin/claude" --print --model claude-sonnet-5 "$PROMPT_CLAUDE" >"$TMPOUT" 2>&1
EXIT=$?
if [ $EXIT -eq 0 ] && ! grep -qE "out of extra usage|usage limit|quota exceeded|rate.limit" "$TMPOUT"; then
    SUCCESS=1
    USED_LLM="claude-sonnet-5"
fi
cat "$TMPOUT" >> "$LOG"

# Tier 2: agy (Antigravity CLI Gemini 3.1 Pro, Google AI Ultra sub)
if [ $SUCCESS -eq 0 ]; then
    echo "[$(date)] tier 1 failed/exhausted — falling back to agy (Gemini 3.1 Pro)" >> "$LOG"
    > "$TMPOUT"
    printf '%s' "$PROMPT_GENERIC" | /Users/nuzantara/.local/bin/agy -p --print-timeout 5m >"$TMPOUT" 2>&1
    EXIT=$?
    if [ $EXIT -eq 0 ] && ! grep -qE "quota|limit|429|exhausted|TerminalQuotaError" "$TMPOUT"; then
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
    if [ $EXIT -eq 0 ] && ! grep -qE "usage.limit|quota|exhausted" "$TMPOUT"; then
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
    if [ $EXIT -eq 0 ]; then
        SUCCESS=1
        USED_LLM="ollama-qwen3.5:9b-local"
    fi
    cat "$TMPOUT" >> "$LOG"
fi

if [ $SUCCESS -eq 1 ]; then
    echo "[$(date)] regulatory-watcher run complete — used: $USED_LLM" >> "$LOG"

    # W1.4: emit eventbus events for any new regulatory deltas in today's JSON
    DELTA_JSON="$HOME/Desktop/nuzantara/research/regulatory/$(TZ=Asia/Makassar date +%Y-%m-%d)-delta.json"

    # W81-fix (2026-06-15): worktree publish-drift recovery. The cron `claude`
    # runs with W79 worktree-isolation hooks active, so it CANNOT write the delta
    # to the main checkout — it commits to a worktree branch (agent/.../intel/watcher-*)
    # instead. The wrapper itself runs in plain zsh (no hooks), so it can recover the
    # file from the branch and place it in main, making the publish block below fire
    # and the anti-hallucination guard correct (real absence vs isolated write).
    if [ ! -f "$DELTA_JSON" ]; then
        _DELTA_BASENAME="$(TZ=Asia/Makassar date +%Y-%m-%d)-delta.json"
        # 1) try worktree working-tree files (freshest first)
        _WT_HIT="$(ls -t "$HOME"/Desktop/nuzantara/.worktrees/*/research/regulatory/"$_DELTA_BASENAME" 2>/dev/null | head -1)"
        if [ -n "$_WT_HIT" ] && [ -f "$_WT_HIT" ]; then
            cp "$_WT_HIT" "$DELTA_JSON" && echo "[$(date)] W81-fix: recovered delta from worktree file $_WT_HIT -> main" >> "$LOG"
        else
            # 2) try the freshest watcher branch via git show
            _WT_BRANCH="$(cd "$HOME/Desktop/nuzantara" && git for-each-ref --sort=-committerdate --format='%(refname:short)' 'refs/heads/agent/*/intel/watcher-*' 2>/dev/null | head -1)"
            if [ -n "$_WT_BRANCH" ] && (cd "$HOME/Desktop/nuzantara" && git cat-file -e "$_WT_BRANCH:research/regulatory/$_DELTA_BASENAME" 2>/dev/null); then
                (cd "$HOME/Desktop/nuzantara" && git show "$_WT_BRANCH:research/regulatory/$_DELTA_BASENAME") > "$DELTA_JSON" \
                  && echo "[$(date)] W81-fix: recovered delta from branch $_WT_BRANCH -> main" >> "$LOG"
            fi
        fi
    fi

    # Empirical disk-state verification (lesson 2026-05-13 anti-hallucination):
    # Claude/Gemini may narrate "JSON emitted" without actually writing the file.
    # If the delta file is missing after a "successful" run, log loudly and skip eventbus.
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
fi

rm -f "$TMPOUT"
exit 0
