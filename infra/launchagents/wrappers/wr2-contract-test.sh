#!/bin/zsh
# wr2-contract-test.sh — invoke wr2-design-architect + verify contracts ABC forensicamente
#
# Usage:
#   ./wr2-contract-test.sh                      # use default test topic
#   ./wr2-contract-test.sh "topic text" "domain" "audience"
#
# Returns 0 if all 3 contracts PASS, non-zero otherwise.
#
# W89 class-audit fix (2026-07-11, PENDING-ARMS ledger ~68): sonnet-5/opus in --print mode
# can silently spawn its work as a background task; the CLI kills it at the print-mode
# ceiling and exits 0 with no orchestrator-output.txt on disk (incident: regulatory-watcher
# 2026-07-05). Fix here: raise the background ceiling, tell the model inline never to
# background, and log an explicit "used: tier1-<model>" provenance line (single-tier by
# design — this is a manual forensic harness for the Claude-only wr2-design-architect agent).

set -uo pipefail

TOPIC="${1:-BPJS Ketenagakerjaan tarif update Q3 2026}"
DOMAIN="${2:-regulatory}"
AUDIENCE="${3:-founder}"
OUT="${WR2_TEST_OUT:-/tmp/wr2-contract-test}"
LOG="${HOME}/logs/wr2-contract-test.log"
mkdir -p "$(dirname "$LOG")"

echo "[$(date)] WR2 contract test starting" >&2
echo "  topic: $TOPIC" >&2
echo "  domain: $DOMAIN" >&2
echo "  audience: $AUDIENCE" >&2
echo "  output: $OUT" >&2

mkdir -p "$OUT"
rm -rf "$OUT"/* 2>/dev/null || true

# sonnet-5/opus --print + background tasks (W89 class-audit, 2026-07-11): the CLI kills
# backgrounded work after the print-mode ceiling; 30min keeps a legitimate 4-subagent
# fan-out run alive.
export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS="${CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS:-1800000}"

# Spawn orchestrator via claude --print --agent
PROMPT="Standalone manual contract verification run.
Topic: $TOPIC
Domain: $DOMAIN. Audience: $AUDIENCE.
Output dir: $OUT/
Per Step 0 ENFORCEMENT PROLOGUE: invoke 4 sub-agents (Contract A), brief MUST have nb_sources_consulted+nb_query_log (B), declare image_strategy explicitly (C), no silent placeholder reuse.
Run final Self-audit. Output STATUS line at end. NO Playwright render. NO canva_pending.json write.
Do ALL the work inline in this session — never spawn a background task or background agent
for this; this is a one-shot print-mode run and backgrounded work is terminated at exit,
leaving no orchestrator-output.txt on disk (W89 class-audit, regulatory-watcher incident 2026-07-05)."

unset ANTHROPIC_API_KEY
$HOME/.local/bin/claude --print --model claude-opus-4-7 \
    --agent wr2-design-architect "$PROMPT" \
    > "$OUT/orchestrator-output.txt" 2>&1
EXIT=$?

echo "[$(date)] orchestrator exit=$EXIT" >&2

# Explicit tier-provenance line (W89 class-audit, 2026-07-11): single-tier by design (no
# claude-cascade.sh fallback — this harness exercises the Claude-only wr2-design-architect
# agent and its 4 subagent fan-out).
if [ "$EXIT" -eq 0 ]; then
    echo "[$(date)] [wr2-contract-test] used: tier1-claude-opus-4-7 (exit=0)" | tee -a "$LOG" >&2
else
    echo "[$(date)] [wr2-contract-test] agent run FAILED (exit=$EXIT) model=claude-opus-4-7" | tee -a "$LOG" >&2
fi

# ============== FORENSIC VERIFICATION ==============
echo ""
echo "===== CONTRACT VERIFICATION ====="

PASS_A=0; PASS_B=0; PASS_C=0

# Contract A — fan-out: 4 sub-agent transcripts present?
A_COUNT=$(ls "$OUT"/{brief,storyboard,layout,critic}-raw.txt 2>/dev/null | wc -l | tr -d ' ')
if [ "$A_COUNT" -ge 4 ]; then
    echo "Contract A (fan-out): PASS — $A_COUNT subagent transcripts found"
    PASS_A=1
else
    echo "Contract A (fan-out): FAIL — only $A_COUNT/4 transcripts"
fi

# Contract B — NB query: brief.json has nb_sources_consulted ≥1 + nb_query_log ≥1
if [ -f "$OUT/brief.json" ]; then
    B_RESULT=$(/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3 -c "
import json, sys
try:
    d = json.load(open('$OUT/brief.json'))
    src = len(d.get('nb_sources_consulted', []))
    logs = len(d.get('nb_query_log', []))
    if src >= 1 and logs >= 1:
        print(f'PASS sources={src} queries={logs}')
    else:
        print(f'FAIL sources={src} queries={logs}')
except Exception as e:
    print(f'FAIL parse-error: {e}')
")
    if [[ "$B_RESULT" == PASS* ]]; then
        echo "Contract B (NB query): $B_RESULT"
        PASS_B=1
    else
        echo "Contract B (NB query): $B_RESULT"
    fi
else
    echo "Contract B (NB query): FAIL — brief.json missing"
fi

# Contract C — image strategy declared per hero, no silent placeholder reuse
if [ -f "$OUT/slides.json" ]; then
    C_RESULT=$(/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3 -c "
import json
d = json.load(open('$OUT/slides.json'))
slides = d.get('slides', d) if isinstance(d, dict) else d
heroes = [s for s in slides if s.get('is_hero_image')]
if not heroes:
    print('FAIL no-hero-slides')
else:
    missing = [s for s in heroes if not s.get('image_strategy') or not s.get('image_source')]
    if missing:
        print(f'FAIL {len(missing)}/{len(heroes)} heroes missing image_strategy/source')
    else:
        print(f'PASS all {len(heroes)} heroes declare image_strategy + image_source')
")
    if [[ "$C_RESULT" == PASS* ]]; then
        echo "Contract C (image strategy): $C_RESULT"
        PASS_C=1
    else
        echo "Contract C (image strategy): $C_RESULT"
    fi
else
    echo "Contract C (image strategy): FAIL — slides.json missing"
fi

echo ""
TOTAL=$((PASS_A + PASS_B + PASS_C))
echo "===== TOTAL: $TOTAL/3 contracts PASS ====="

if [ "$TOTAL" -eq 3 ]; then
    exit 0
fi
exit 1
