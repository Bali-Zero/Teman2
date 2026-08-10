#!/usr/bin/env bash
# NB-AGENTS daily adaptive Deep Research
# Schedule: 07:30 WITA daily
# Logic: read yesterday's DR, extract "open questions" section, query NB-AGENTS on the first one.
# If no yesterday-file or no open questions: fall back to round-robin theme.
#
# Output: ~/nuzantara/research/agent-craft/YYYY-MM-DD-<slug>.md
#
# Hard rules (per CLAUDE.md):
#   - No paid Anthropic API. Only nlm CLI + Sonnet 4.6 via the OAuth seat helper
#     (scripts/lib/claude_seat.sh, free OAuth MAX) for slug derivation.
#   - Adaptive: yesterday's "3 domande aperte" section drives today's taglio.
#   - Idempotent same-day: if today's file exists, exit 0 (no duplicate DR).

set -euo pipefail

# The alias registry is HOME state and was found EMPTY on 2026-08-07 (`nlm alias list`
# -> "No aliases defined"), so `nlm notebook query nb-agents` returned NOT_FOUND. The
# dead NotebookLM credential had masked it since at least 2026-07-31 — curing the auth
# only revealed this one. The notebook id is stable; an alias is a lookup that can vanish.
NB_ALIAS="6d449787-04e3-430e-acbe-d6fc38d379a9"  # NB-AGENTS (was the alias "nb-agents")
RESEARCH_DIR="$HOME/nuzantara/research/agent-craft"
LOG_DIR="$HOME/.cron-agent/logs"
mkdir -p "$LOG_DIR" "$RESEARCH_DIR/_assets"

TODAY=$(date +%Y-%m-%d)
YESTERDAY=$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d "yesterday" +%Y-%m-%d)
TODAY_LOG="$LOG_DIR/nb-agents-daily-dr-$TODAY.log"

# The redirect below sends BOTH streams to the day log for the rest of the run,
# which is what a daily report wants — and it is also the reason 13 consecutive
# Telegram alerts (2026-07-28 → 08-09) could only say "Exit: 1". The invoking
# `cron-state.sh` builds its alert from what it captures on the child's stderr;
# once this line runs, nothing reaches it. Ten of those thirteen mornings the day
# log held, verbatim, "Authentication expired. Run 'nlm login' ..." — the cause
# was on disk, naming its own cure, and the channel carried an exit code.
#
# So keep a handle on the REAL stderr FIRST, and give the cause a way out.
# No `|| true` here on purpose: `exec` with only redirections is a special
# builtin, so `||` cannot protect it under `set -e` (W108) — the guard would be
# theatre. It also cannot realistically fail.
exec 3>&2
exec >>"$TODAY_LOG" 2>&1

# Bounded on purpose: the alert has a character budget, and a wall of log is how
# a real cause gets scrolled past. Three lines is what a phone notification shows.
_emit_cause_to_cron () {
  _rc=$?
  if [ "$_rc" -eq 0 ]; then return 0; fi
  {
    printf 'nb-agents-daily-dr exit %s — tail of %s:\n' "$_rc" "$TODAY_LOG"
    grep -v '^[[:space:]]*$' "$TODAY_LOG" 2>/dev/null | tail -n 3
  } >&3 2>/dev/null || true
  return 0
}
trap _emit_cause_to_cron EXIT

echo "============================================================"
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] NB-AGENTS daily adaptive DR"
echo "============================================================"

# Round-robin fallback themes (Lun..Dom) — used only if no yesterday open-questions found.
DOW=$(date +%u)  # 1=Mon..7=Sun
declare -a FALLBACK_THEMES=(
  ""  # index 0 unused
  "anatomia di un agente Claude Code: struttura completa (frontmatter, body, tool gating, model, isolation, memory)"
  "tassonomia funzionale degli agenti: orchestrator vs worker vs gate vs watcher vs synthesizer. Mappa i nostri 16 agenti su queste famiglie."
  "principi ricorrenti: fan-out parallel, bipolar verifier, devils-advocate gate, multi-LLM cascade, ground-truth NB, no-silent-reuse. Quali sono load-bearing e quali decorativi?"
  "anti-pattern visti live: capacity exhaustion, hallucinated tool output, brief stale premise, 17.2x error amplification, orchestrator race, hybrid quota trap. Quali sono ancora aperti?"
  "evolution mechanics: Voyager skill library, Reflexion weekly synthesis, Kim et al. error amplification. Come applichiamo questi paper alla nostra stack?"
  "case study: deconstruct WR2 pipeline a 5 agenti (architect → brief → storyboard → layout → critic). Cosa rende il pattern robusto? Cosa lo romperebbe?"
  "weekly synthesis: cosa è cambiato in NB-AGENTS questa settimana? Quali pattern sono emersi dai DR di lun-sab? Quale dovrebbe diventare una skill atomica?"
)

# Look for yesterday's DR file
YESTERDAY_FILE=$(ls -1 "$RESEARCH_DIR/${YESTERDAY}-"*.md 2>/dev/null | head -1 || true)

# Try to extract "3 domande aperte" or "Open questions" section from yesterday
ADAPTIVE_QUESTION=""
if [ -n "$YESTERDAY_FILE" ]; then
  echo "Yesterday file found: $YESTERDAY_FILE"
  # Extract block after "Domande Aperte" or "Open questions" heading, grab first numbered item
  ADAPTIVE_QUESTION=$(awk '
    /[Dd]omande [Aa]perte|[Oo]pen [Qq]uestions|3 [Dd]omande [Aa]perte|[Tt]aglio.*[Dd]omani/ {found=1; next}
    found && /^[0-9]+\.|^\*\*[0-9]+\./ {print; exit}
  ' "$YESTERDAY_FILE" | sed 's/^[0-9]*\.\s*//; s/^\*\*[0-9]*\.\*\*\s*//' | head -1 || true)
  echo "Extracted adaptive question: ${ADAPTIVE_QUESTION:0:200}..."
fi

# Decide question
if [ -n "$ADAPTIVE_QUESTION" ]; then
  MODE="adaptive"
  QUESTION="In italiano. Approfondisci la domanda emersa dal Deep Research di ieri: $ADAPTIVE_QUESTION

Per la risposta: (1) cita verbatim le fonti rilevanti tra i tuoi 86 sources, (2) confronta con come lo applichiamo già nei nostri agenti reali, (3) identifica almeno una linea di azione concreta che possiamo implementare nella libreria Bali Zero. Termina con altre 3 domande aperte che saranno il taglio del DR di domani."
else
  MODE="fallback"
  THEME="${FALLBACK_THEMES[$DOW]}"
  QUESTION="In italiano. Tema di oggi (round-robin giorno $DOW): $THEME

Per la risposta: (1) cita verbatim le fonti rilevanti tra i tuoi 86 sources, (2) confronta con come lo applichiamo già nei nostri agenti reali, (3) identifica almeno una linea di azione concreta. Termina con 3 domande aperte per il DR di domani."
fi

echo "MODE: $MODE"
echo "QUESTION: ${QUESTION:0:300}..."

# Derive slug via claude CLI (Sonnet 4.6, free OAuth)
# `claude` prints auth failures to STDOUT (the same property that kept the OAuth
# seat cascade from ever rotating), and `sed` always exits 0 - so the `|| echo`
# fallback below could never fire and the error text flowed straight into the
# filename: on 2026-08-07 "Not logged in - Please run /login" became the slug
# `otloggedinleaserunlogin`. Judge the EXIT CODE and the SHAPE, never the fact
# that a pipeline survived.
# The invocation goes through claude_seat.sh, not a bare `claude`. Measured on
# Pro 2026-08-08 under `bash -lc` — the exact shell this script's crontab line
# uses: `claude` is NOT on PATH there and no OAuth seat is in the environment,
# so the bare call could never have produced a slug. It degraded to the default
# one every night instead, silently, because the guard below is doing its job.
# The helper resolves the binary absolutely and rotates through the numbered
# seats; the keychain identity is deliberately not a fallback (0 successes in
# 905 attempts — it cannot work in a non-GUI session).
# shellcheck source=scripts/lib/claude_seat.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/claude_seat.sh"
SLUG_RC=0
SLUG_RAW=$(claude_seat_run --model claude-sonnet-4-6 -p "Genera uno slug kebab-case di max 6 parole in inglese che riassuma questo topic. Output: solo lo slug, niente altro. Topic: <<<$(echo "$QUESTION" | head -c 500)>>>" 2>/dev/null) || SLUG_RC=$?
SLUG=$(printf '%s' "$SLUG_RAW" | tr -d '\n' | sed 's/[^a-z0-9-]//g; s/--*/-/g' | head -c 60)
if [ "$SLUG_RC" -ne 0 ] \
   || [ "${#SLUG}" -lt 3 ] \
   || printf '%s' "$SLUG_RAW" | grep -qiE 'not logged in|please run|/login|authentication|unauthori|401|rate.?limit|quota'; then
  echo "SLUG: claude unusable (rc=$SLUG_RC) - falling back to the default slug" >&2
  SLUG="agent-craft-daily"
fi
[ -z "$SLUG" ] && SLUG="agent-craft-daily-$DOW"

OUT_FILE="$RESEARCH_DIR/${TODAY}-${SLUG}.md"

# Idempotent guard
if [ -f "$OUT_FILE" ]; then
  echo "OUT_FILE already exists: $OUT_FILE — skipping (idempotent)"
  exit 0
fi

echo "OUT_FILE target: $OUT_FILE"

# Run query
RAW_JSON=$(nlm notebook query "$NB_ALIAS" --json --timeout 300 "$QUESTION" 2>&1 | tee "$LOG_DIR/dr-raw-$TODAY.json")

# Parse and write markdown
python3 - "$OUT_FILE" "$RAW_JSON" "$MODE" "$QUESTION" <<'PYEOF'
import json, sys
from pathlib import Path

out_file = sys.argv[1]
raw = sys.argv[2]
mode = sys.argv[3]
question = sys.argv[4]

start = raw.find("{")
data = json.loads(raw[start:])
# The CLI returns the answer FLAT (answer/references/sources_used at the top
# level); an older shape wrapped it in {"value": ...}. Measured 2026-08-07 on a
# real 38KB response: no "value" key, so this raised KeyError AFTER a successful
# query — the third of three stacked defects, each hidden by the one before it.
# Accept both shapes, and if neither carries an answer say WHICH keys arrived.
v = data["value"] if isinstance(data.get("value"), dict) else data
# The CLI reports its OWN failures as {"status": "error", "error": "<msg>"}, and
# that message names its own cure. Measured 2026-08-10: six byte-identical
# 227-byte payloads (3,4,5,6,8,9 Aug) all read "Query failed: Authentication
# expired. Run 'nlm login' in your terminal to re-authenticate." — while this
# branch turned the one useful line into a complaint about JSON SHAPE, pointing
# whoever read the alert at a parser bug that does not exist. A diagnosis that
# names the wrong thing is worse than no diagnosis (W106: the cure and its
# message were written from the same belief and expire together).
# Gated on "answer" not in v so a SUCCESSFUL payload that happens to carry an
# "error" key is never hijacked into a failure.
err = v.get("error") or data.get("error")
if "answer" not in v and err:
    raise SystemExit("nlm query failed: %s" % err)
if "answer" not in v:
    raise SystemExit(
        "unexpected nlm JSON shape - top-level keys: %s" % sorted(data)[:12]
    )
answer = v.get("answer", "")
refs = v.get("references", [])
conv_id = v.get("conversation_id", "")
sources_used = v.get("sources_used", [])

md = []
md.append(f"# Agent-craft DR — {Path(out_file).stem}")
md.append("")
md.append(f"**Date**: {Path(out_file).stem.split('-')[0]}-{Path(out_file).stem.split('-')[1]}-{Path(out_file).stem.split('-')[2]}")
md.append(f"**Mode**: {mode}")
md.append(f"**NB**: NB-AGENTS (`6d449787-04e3-430e-acbe-d6fc38d379a9`)")
md.append(f"**Conversation ID**: `{conv_id}`")
md.append(f"**Sources used**: {len(sources_used)} / Citations: {len(refs)}")
md.append("")
md.append("## Question")
md.append("")
md.append(f"> {question}")
md.append("")
md.append("## Answer")
md.append("")
md.append(answer)
md.append("")
md.append(f"## Sources used ({len(sources_used)})")
md.append("")
for s in sources_used:
    md.append(f"- `{s}`")
md.append("")
md.append(f"## Citations verbatim ({len(refs)})")
md.append("")
for c in refs:
    n = c.get("citation_number", "?")
    sid = c.get("source_id", "?")[:8]
    txt = (c.get("cited_text") or "").strip()
    md.append(f"### [{n}] source `{sid}…`")
    md.append("")
    md.append(f"> {txt}")
    md.append("")

Path(out_file).write_text("\n".join(md))
print(f"WROTE: {out_file}  ({Path(out_file).stat().st_size} bytes)")
PYEOF

echo "[$(date '+%H:%M:%S')] DR completed successfully."
