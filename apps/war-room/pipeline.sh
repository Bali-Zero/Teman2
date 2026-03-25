#!/bin/zsh
# ============================================================
# BALI ZERO WAR ROOM — Master Pipeline Orchestrator
# Usage: ./pipeline.sh "Coretax 2025" [--dry-run] [--auto]
#
# V2 (A2A): python apps/war-room/pipeline_v2.py "topic" [--dry-run]
# Override env vars:
#   CANVA_ROW=upper|lower   (default: upper)
#   CANVA_PAGE=1|2|3        (default: 1)
#   CANVA_DESIGN_ID=...     (default: DAHE6lx1lf8)
# ============================================================

set -euo pipefail

# ── Args ────────────────────────────────────────────────────
[[ -n "${1:-}" && "${1:0:2}" != "--" ]] && TOPIC="$1" || TOPIC=""
DRY_RUN=false
AUTO_MODE=false
WAR_ROOM="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$WAR_ROOM/logs"
LOG_FILE="$WAR_ROOM/logs/pipeline_$(date +%Y%m%d_%H%M%S).log"

for arg in "$@"; do
  case $arg in
    --dry-run) DRY_RUN=true ;;
    --auto)    AUTO_MODE=true ;;
    --skip-legacy) true ;;  # legacy flag, ignored
  esac
done

# ── Logging ─────────────────────────────────────────────────
log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
die() { log "❌ FATAL: $*"; exit 1; }

# ── Phase runner: timeout + error isolation ──────────────────
# run_phase <label> <timeout_secs> <command...>
# Returns 0 on success, 1 on failure (never kills pipeline)
run_phase() {
  local label="$1" timeout_secs="$2"
  shift 2
  log "   ▶ Running: $label"
  if timeout "$timeout_secs" "$@"; then
    return 0
  else
    local rc=$?
    if (( rc == 124 )); then
      log "   ⏰ TIMEOUT after ${timeout_secs}s: $label"
    else
      log "   ❌ FAILED (rc=$rc): $label"
    fi
    return 1
  fi
}

# ── Load .env ───────────────────────────────────────────────
if [[ -f "$WAR_ROOM/.env" ]]; then
  set -a
  source "$WAR_ROOM/.env"
  set +a
fi

# ── Validate required env vars ───────────────────────────────
[[ -z "${OPENAI_API_KEY:-}" ]] && log "⚠️  OPENAI_API_KEY not set — FASE 1 may fail"
[[ -z "${TELEGRAM_BOT_TOKEN:-}" ]] && log "⚠️  TELEGRAM_BOT_TOKEN not set — FASE 5 notifications disabled"

log "🚨 BALI ZERO WAR ROOM AVVIATA"
log "🕐 Start: $(date)"
$DRY_RUN && log "⚠️  DRY RUN MODE — nessuna azione reale"

OUTPUT="$WAR_ROOM/output"
T_START=$(date +%s)

# ── Canva params (overridable) ───────────────────────────────
CANVA_ROW="${CANVA_ROW:-upper}"
CANVA_PAGE="${CANVA_PAGE:-1}"
CANVA_DESIGN="${CANVA_DESIGN_ID:-DAHE6lx1lf8}"

# ── Cleanup output precedente ────────────────────────────────
mkdir -p "$OUTPUT/raw" "$OUTPUT/strategy" "$OUTPUT/images" \
         "$OUTPUT/canva" "$OUTPUT/master"
rm -f "$OUTPUT"/raw/*(N) "$OUTPUT"/strategy/*(N) \
      "$OUTPUT"/images/*(N) "$OUTPUT"/canva/*(N) 2>/dev/null || true

# ── Check Intel Scraper output ───────────────────────────────
INTEL_LATEST="$HOME/Desktop/nuzantara/apps/bali-intel-scraper/data/intel_output_latest.json"
INTEL_FRESH=false
if [[ -f "$INTEL_LATEST" ]]; then
  INTEL_AGE=$(( $(date +%s) - $(date -r "$INTEL_LATEST" +%s) ))
  if (( INTEL_AGE < 28800 )); then
    INTEL_FRESH=true
    log "✅ Intel Scraper output fresco (${INTEL_AGE}s fa)"

    # Pre-seed intel facts (sempre, indipendentemente dal topic)
    python3 -c "
import json
with open('$INTEL_LATEST') as f: d = json.load(f)
arts = d.get('articles', [])
intel = {
  'facts': [{'title': a.get('title',''), 'brief': str(a.get('enrichment',{}).get('the_facts', a.get('enrichment',{}).get('executive_brief',''))), 'category': a.get('qwen_category',''), 'source': a.get('url','')} for a in arts if a.get('enrichment')],
  'topics': list(set(a.get('qwen_category','') for a in arts if a.get('qwen_category'))),
  'generated_at': d.get('generated_at',''),
  'source': 'intel_scraper'
}
print(json.dumps(intel, ensure_ascii=False, indent=2))
" > "$OUTPUT/raw/intel_preseed.json" 2>/dev/null || echo '{"facts":[],"topics":[]}' > "$OUTPUT/raw/intel_preseed.json"

    INTEL_COUNT=$(python3 -c "import json; d=json.load(open('$INTEL_LATEST')); print(len([a for a in d.get('articles',[]) if a.get('enrichment')]))" 2>/dev/null || echo "?")
    log "   📂 Intel pre-seed → $INTEL_COUNT enriched articles"

    # ── FASE 0: Topic Selector (Gemini + Google Trends) ──────
    if [[ -z "$TOPIC" ]]; then
      log ""
      log "━━━ FASE 0: TOPIC SELECTOR (Gemini + Google Trends) ━━━"
      SELECTED_TOPIC_FILE="$OUTPUT/strategy/selected_topic.json"
      mkdir -p "$OUTPUT/strategy"

      run_phase "topic_selector" 240 \
        $WAR_ROOM/.venv/bin/python3 "$WAR_ROOM/agents/00_topic_selector.py" \
        --intel  "$INTEL_LATEST" \
        --output "$SELECTED_TOPIC_FILE" \
        2>>"$LOG_FILE" 1>>"$LOG_FILE"
      TOPIC=$(python3 -c "import json; print(json.load(open('$SELECTED_TOPIC_FILE'))['topic'])" 2>/dev/null || echo "")

      if [[ -n "$TOPIC" ]]; then
        TOPIC_ANGLE=$(python3 -c "import json; print(json.load(open('$SELECTED_TOPIC_FILE')).get('angle',''))" 2>/dev/null || echo "")
        TOPIC_TREND=$(python3 -c "import json; print(json.load(open('$SELECTED_TOPIC_FILE')).get('trend_signal',''))" 2>/dev/null || echo "")
        log "✅ Topic selezionato: $TOPIC"
        [[ -n "$TOPIC_ANGLE" ]] && log "   Angle: $TOPIC_ANGLE"
        [[ -n "$TOPIC_TREND" ]] && log "   Trend: $TOPIC_TREND"
      else
        # Fallback: titolo articolo con score più alto
        TOPIC=$(python3 -c "
import json
d = json.load(open('$INTEL_LATEST'))
arts = [a for a in d.get('articles', []) if a.get('enrichment')]
if not arts: arts = d.get('articles', [])
arts.sort(key=lambda a: a.get('qwen_score', 0), reverse=True)
best = arts[0] if arts else {}
print(best.get('title', 'Indonesia Business Intelligence')[:60])
" 2>/dev/null || echo "Indonesia Business Intelligence")
        log "⚠️  Topic selector fallito — fallback: $TOPIC"
      fi
    else
      log "📌 Topic manuale: $TOPIC"
    fi
  else
    log "⏰ Intel output vecchio (${INTEL_AGE}s)"
  fi
else
  log "ℹ️  intel_output_latest.json non trovato"
fi

[[ -z "$TOPIC" ]] && die "Nessun topic. Passa ./pipeline.sh 'topic' o assicurati che intel scraper sia fresco (<8h)"
log "📌 Topic: $TOPIC"

# ══════════════════════════════════════════════════════════
# FASE 1 — CHATGPT RESEARCH
# ══════════════════════════════════════════════════════════
log ""
log "━━━ FASE 1: RESEARCH (ChatGPT + Exa + Gemini parallelo) (T+00:00) ━━━"

if ! $DRY_RUN; then
  # Launch all 3 researchers in parallel
  run_phase "chatgpt_researcher" 600 \
    $WAR_ROOM/.venv/bin/python3 "$WAR_ROOM/agents/01_chatgpt_researcher.py" \
    --topic "$TOPIC" \
    --output "$OUTPUT/raw/chatgpt_dump.json" \
    --sentiment-output "$OUTPUT/raw/social_dump.json" \
    &
  CHATGPT_PID=$!

  run_phase "exa_researcher" 300 \
    $WAR_ROOM/.venv/bin/python3 "$WAR_ROOM/agents/09_exa_researcher.py" \
    --topic "$TOPIC" \
    --output "$OUTPUT/raw/exa_dump.json" \
    &
  EXA_PID=$!

  run_phase "gemini_researcher" 240 \
    $WAR_ROOM/.venv/bin/python3 "$WAR_ROOM/agents/02_gemini_researcher.py" \
    --topic "$TOPIC" \
    --output "$OUTPUT/raw/gemini_dump.json" \
    &
  GEMINI_PID=$!

  # Wait for all (non-blocking failures)
  wait $CHATGPT_PID 2>/dev/null || log "⚠️  ChatGPT research fallito"
  wait $EXA_PID 2>/dev/null || log "⚠️  Exa research fallito"
  wait $GEMINI_PID 2>/dev/null || log "⚠️  Gemini research fallito"

  if [[ -f "$OUTPUT/raw/chatgpt_dump.json" ]]; then
    CHATGPT_COUNT=$(python3 -c "import json; d=json.load(open('$OUTPUT/raw/chatgpt_dump.json')); print(d.get('count', 0))" 2>/dev/null || echo "0")
    log "✅ ChatGPT: $CHATGPT_COUNT facts"
  fi
  if [[ -f "$OUTPUT/raw/exa_dump.json" ]]; then
    EXA_COUNT=$(python3 -c "import json; d=json.load(open('$OUTPUT/raw/exa_dump.json')); print(len(d.get('facts', d.get('results', []))))" 2>/dev/null || echo "0")
    log "✅ Exa: $EXA_COUNT facts"
  fi
  if [[ -f "$OUTPUT/raw/gemini_dump.json" ]]; then
    GEMINI_COUNT=$(python3 -c "import json; d=json.load(open('$OUTPUT/raw/gemini_dump.json')); print(d.get('count', 0))" 2>/dev/null || echo "0")
    log "✅ Gemini: $GEMINI_COUNT legal facts"
  fi
fi

# ── Merge intelligence sources ──────────────────────────────
log "🔗 Merging intelligence sources..."
python3 -c "
import json
from pathlib import Path

output_raw = Path('$OUTPUT/raw')
all_facts = []
seen_titles = set()
sources_used = []

for name, path in [
    ('chatgpt', output_raw / 'chatgpt_dump.json'),
    ('exa',     output_raw / 'exa_dump.json'),
    ('gemini',  output_raw / 'gemini_dump.json'),
    ('intel',   output_raw / 'intel_preseed.json'),
]:
    if not path.exists():
        continue
    try:
        data = json.load(open(path))
        facts = data.get('facts', [])
        added = 0
        for f in facts:
            title_key = f.get('title', '').lower()[:50]
            if title_key and title_key not in seen_titles:
                seen_titles.add(title_key)
                f['_source'] = name
                all_facts.append(f)
                added += 1
        if added > 0:
            sources_used.append(f'{name}:{added}')
    except Exception:
        pass

merged = {
    'facts': all_facts,
    'topics': list(set(f.get('category','') for f in all_facts if f.get('category'))),
    'sources_used': sources_used,
    'merged_at': __import__('datetime').datetime.now().isoformat(),
}
print(json.dumps(merged, ensure_ascii=False, indent=2))
" > "$OUTPUT/raw/merged_dump.json" 2>/dev/null || echo '{"facts":[],"topics":[]}' > "$OUTPUT/raw/merged_dump.json"

MERGED_COUNT=$(python3 -c "import json; print(len(json.load(open('$OUTPUT/raw/merged_dump.json')).get('facts',[])))" 2>/dev/null || echo "?")
log "   ✅ Merged → $MERGED_COUNT facts totali"

# ── FASE 1.5: Qwen3.5 Pre-processor ─────────────────────────
log ""
log "━━━ FASE 1.5: QWEN3.5 PRE-PROCESSOR (locale) ━━━"
if ! $DRY_RUN; then
  [[ ! -f "$OUTPUT/raw/social_dump.json" ]] && echo '{"data":[]}' > "$OUTPUT/raw/social_dump.json"
  run_phase "qwen_preprocessor" 300 \
    $WAR_ROOM/.venv/bin/python3 "$WAR_ROOM/agents/015_qwen_preprocessor.py" \
    --sentiment "$OUTPUT/raw/social_dump.json" \
    --research "$OUTPUT/raw/merged_dump.json" \
    --output "$OUTPUT/raw/processed_dump.json" \
    || log "⚠️  Qwen pre-processor fallito — uso merged_dump direttamente"

  # Fallback: se processed_dump non esiste, usa merged_dump
  if [[ ! -f "$OUTPUT/raw/processed_dump.json" ]]; then
    cp "$OUTPUT/raw/merged_dump.json" "$OUTPUT/raw/processed_dump.json"
    log "   ↩️  Fallback: processed_dump = merged_dump"
  fi
  log "✅ Pre-processing completato"
fi

# ══════════════════════════════════════════════════════════
# FASE 2 — BRAIN-TRUST (Gemini + Claude Director)
# ══════════════════════════════════════════════════════════
log ""
log "━━━ FASE 2: BRAIN-TRUST (T+02:00) ━━━"

log "🧠 Gemini strategist — generazione 3 concept..."
if ! $DRY_RUN; then
  # Fallback: se Gemini fallisce usa Ollama qwen3.5
  if ! run_phase "gemini_strategist" 600 \
    $WAR_ROOM/.venv/bin/python3 "$WAR_ROOM/agents/03_gemini_strategist.py" \
    --dump   "$OUTPUT/raw/processed_dump.json" \
    --topic  "$TOPIC" \
    --output "$OUTPUT/strategy/gemini_concepts.json"; then

    log "⚠️  Gemini fallito — tentativo fallback Ollama..."
    # Genera concetti minimali come fallback
    python3 -c "
import json
topic = '$TOPIC'
fallback = {'concepts': [
  {'title': f'The {topic} Alert', 'hook': f'What you need to know about {topic}',
   'core_insight': f'Key implications of {topic} for foreign investors in Bali',
   'asymmetric_angle': 'Most people are missing the second-order consequences',
   'recommended_tone': 'istituzionale_severo',
   'why_this_will_perform': 'Actionable, specific, time-sensitive'},
]}
print(json.dumps(fallback, ensure_ascii=False, indent=2))
" > "$OUTPUT/strategy/gemini_concepts.json"
    log "   ↩️  Fallback concept generato"
  fi
  log "✅ Concepts pronti"
fi

log "🎬 Claude director — copy + JSON slides..."
if ! $DRY_RUN; then
  run_phase "claude_director" 600 \
    $WAR_ROOM/.venv/bin/python3 "$WAR_ROOM/agents/04_claude_director.py" \
    --concepts "$OUTPUT/strategy/gemini_concepts.json" \
    --topic    "$TOPIC" \
    --output   "$OUTPUT/strategy/claude_slides.json" \
    || die "Claude director fallito — impossibile generare slides JSON"
  log "✅ JSON slides pronti"
fi

# ══════════════════════════════════════════════════════════
# FASE 3 — GENERAZIONE IMMAGINI (solo slide con image_prompt)
# ══════════════════════════════════════════════════════════
log ""
log "━━━ FASE 3: GENERAZIONE IMMAGINI ComfyUI/Flux (T+05:00) ━━━"
if ! $DRY_RUN; then
  IMAGE_PROMPTS_FILE="$OUTPUT/images/image_prompts.json"

  # Estrai solo slide con image_prompt != null
  python3 -c "
import json
data = json.load(open('$OUTPUT/strategy/claude_slides.json'))
slides = data.get('slides', [])
prompts = [
  {'slide': s.get('slide_number'), 'is_cover': s.get('is_cover', False),
   'prompt': s.get('image_prompt'), 'placement': s.get('image_placement', '')}
  for s in slides if s.get('image_prompt')
]
print(json.dumps(prompts, ensure_ascii=False, indent=2))
" > "$IMAGE_PROMPTS_FILE" 2>/dev/null || echo '[]' > "$IMAGE_PROMPTS_FILE"

  IMG_COUNT=$(python3 -c "import json; print(len(json.load(open('$IMAGE_PROMPTS_FILE'))))" 2>/dev/null || echo "0")
  log "   🖼️  Slide con image_prompt: $IMG_COUNT"

  if (( IMG_COUNT > 0 )); then
    log "   ℹ️  $IMG_COUNT image_prompt nelle slides — annotazioni testuali, nessuna generazione"
    log "   💡 I prompt sono embedded nel testo Canva per il designer"
  fi
  log "✅ Step immagini completato (solo annotazioni)"
fi

# ══════════════════════════════════════════════════════════
# FASE 4 — CANVA CAROUSEL BUILDER
# Bridge: claude -p → MCP Canva → design DAHE6lx1lf8
# ══════════════════════════════════════════════════════════
log ""
log "━━━ FASE 4: CANVA CAROUSEL (T+07:00) ━━━"
log "   Design: $CANVA_DESIGN  Row: $CANVA_ROW  Page: $CANVA_PAGE"

if ! $DRY_RUN; then
  run_phase "canva_builder" 600 \
    $WAR_ROOM/.venv/bin/python3 "$WAR_ROOM/agents/06_canva_builder.py" \
    --slides    "$OUTPUT/strategy/claude_slides.json" \
    --output    "$OUTPUT/canva/" \
    --master    "$OUTPUT/master/" \
    --design-id "$CANVA_DESIGN" \
    --row       "$CANVA_ROW" \
    --page      "$CANVA_PAGE" \
    || log "⚠️  Canva builder fallito — continua senza carousel (non bloccante)"

  if [[ -f "$OUTPUT/canva/carousel_canva.json" ]]; then
    CANVA_URL=$(python3 -c "import json; d=json.load(open('$OUTPUT/canva/carousel_canva.json')); print(d.get('design_url',''))" 2>/dev/null || echo "")
    [[ -n "$CANVA_URL" ]] && log "   🔗 $CANVA_URL"
    log "✅ Canva carousel aggiornato"
  fi
else
  log "⚠️  DRY RUN — Canva builder in dry-run mode"
  $WAR_ROOM/.venv/bin/python3 "$WAR_ROOM/agents/06_canva_builder.py" \
    --slides    "$OUTPUT/strategy/claude_slides.json" \
    --output    "$OUTPUT/canva/" \
    --master    "$OUTPUT/master/" \
    --design-id "$CANVA_DESIGN" \
    --row       "$CANVA_ROW" \
    --page      "$CANVA_PAGE" \
    --dry-run   2>/dev/null || true
fi

# ══════════════════════════════════════════════════════════
# FASE 5 — DELIVERY
# ══════════════════════════════════════════════════════════
log ""
log "━━━ FASE 5: DELIVERY (T+10:00) ━━━"
if ! $DRY_RUN; then
  run_phase "delivery" 120 \
    zsh "$WAR_ROOM/agents/07_delivery.sh" \
    --topic  "$TOPIC" \
    --master "$OUTPUT/master/" \
    || log "⚠️  Delivery parziale — verifica manualmente Drive/Telegram"
  log "✅ Delivery completata"
fi

T_END=$(date +%s)
T_ELAPSED=$(( T_END - T_START ))
log ""
log "🏁 WAR ROOM COMPLETATA in ${T_ELAPSED}s"
log "📁 Output: $OUTPUT/"
log "📋 Log: $LOG_FILE"
