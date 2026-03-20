#!/bin/zsh
# ============================================================
# BALI ZERO WAR ROOM — Master Pipeline Orchestrator
# Usage: ./pipeline.sh "Coretax 2025" [--dry-run] [--auto]
# ============================================================

set -euo pipefail

# Topic solo se primo arg non è un flag
[[ -n "${1:-}" && "${1:0:2}" != "--" ]] && TOPIC="$1" || TOPIC=""
DRY_RUN=false
AUTO_MODE=false
WAR_ROOM="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$WAR_ROOM/logs/pipeline_$(date +%Y%m%d_%H%M%S).log"

for arg in "$@"; do
  case $arg in
    --dry-run) DRY_RUN=true ;;
    --auto)    AUTO_MODE=true ;;
    --skip-manus|--skip-grok) true ;;  # legacy flags, ignored
  esac
done

# ── Logging ────────────────────────────────────────────────
log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
die() { log "❌ FATAL: $*"; exit 1; }

# Load env vars (API keys)
# Load and export all env vars (set -a = auto-export)
if [[ -f "$WAR_ROOM/.env" ]]; then
  set -a
  source "$WAR_ROOM/.env"
  set +a
fi

log "🚨 BALI ZERO WAR ROOM AVVIATA"
log "🕐 Start: $(date)"
$DRY_RUN && log "⚠️  DRY RUN MODE — nessuna azione reale"

OUTPUT="$WAR_ROOM/output"
T_START=$(date +%s)

# ── Cleanup output precedente ──────────────────────────────
rm -f "$OUTPUT"/raw/*(N) "$OUTPUT"/strategy/*(N) \
      "$OUTPUT"/images/*(N) 2>/dev/null || true
rm -f "$OUTPUT"/keynote/presentation.key 2>/dev/null || true

# ── Check Intel Scraper output — pre-seed data + auto-extract topic ──
INTEL_LATEST="$HOME/Desktop/nuzantara/apps/bali-intel-scraper/data/intel_output_latest.json"
INTEL_FRESH=false
if [[ -f "$INTEL_LATEST" ]]; then
  INTEL_AGE=$(( $(date +%s) - $(date -r "$INTEL_LATEST" +%s) ))
  if (( INTEL_AGE < 28800 )); then  # 8h
    INTEL_FRESH=true
    log "✅ Intel Scraper output fresco (${INTEL_AGE}s fa)"

    # Auto-estrai topic dall'articolo con score più alto
    if [[ -z "$TOPIC" ]]; then
      TOPIC=$(python3 -c "
import json
d = json.load(open('$INTEL_LATEST'))
arts = [a for a in d.get('articles', []) if a.get('enrichment')]
if not arts:
    arts = d.get('articles', [])
arts.sort(key=lambda a: a.get('qwen_score', 0), reverse=True)
best = arts[0] if arts else {}
title = best.get('title', '')[:60]
print(title if title else 'Indonesia Business Intelligence')
" 2>/dev/null || echo "Indonesia Business Intelligence")
      log "📌 Topic auto-estratto dall'intel: $TOPIC"
    fi

    # Pre-seed: converti intel scraper → facts per il preprocessor
    python3 -c "
import json
from pathlib import Path
with open('$INTEL_LATEST') as f: d = json.load(f)
arts = d.get('articles', [])
intel = {
  'facts': [{'title': a.get('title',''), 'brief': str(a.get('enrichment',{}).get('the_facts', a.get('enrichment',{}).get('executive_brief',''))), 'category': a.get('qwen_category',''), 'source': a.get('url','')} for a in arts if a.get('enrichment')],
  'topics': list(set(a.get('qwen_category','') for a in arts if a.get('qwen_category'))),
  'generated_at': d.get('generated_at',''),
  'source': 'intel_scraper'
}
print(json.dumps(intel, ensure_ascii=False, indent=2))
" > "$OUTPUT/raw/intel_preseed.json"
    INTEL_COUNT=$(python3 -c "import json; d=json.load(open('$INTEL_LATEST')); print(len([a for a in d.get('articles',[]) if a.get('enrichment')]))" 2>/dev/null || echo "?")
    log "   📂 Intel pre-seed → $INTEL_COUNT enriched articles"
  else
    log "⏰ Intel output vecchio (${INTEL_AGE}s)"
  fi
else
  log "ℹ️  intel_output_latest.json non trovato"
fi

[[ -z "$TOPIC" ]] && die "Nessun topic. Passa ./pipeline.sh 'topic' o assicurati che intel scraper sia fresco (<8h)"
log "📌 Topic: $TOPIC"

# ══════════════════════════════════════════════════════════
# FASE 1 — T+00:00: CHATGPT RESEARCH (web browsing + sentiment)
# ══════════════════════════════════════════════════════════
log ""
log "━━━ FASE 1: CHATGPT GPT-5.4 RESEARCH (T+00:00) ━━━"

if ! $DRY_RUN; then
  $WAR_ROOM/.venv/bin/python3 "$WAR_ROOM/agents/01_chatgpt_researcher.py" \
    --topic "$TOPIC" \
    --output "$OUTPUT/raw/chatgpt_dump.json" \
    --sentiment-output "$OUTPUT/raw/grok_dump.json" \
    || log "⚠️  ChatGPT research fallito — continuo con intel pre-seed"

  if [[ -f "$OUTPUT/raw/chatgpt_dump.json" ]]; then
    CHATGPT_COUNT=$(python3 -c "import json; d=json.load(open('$OUTPUT/raw/chatgpt_dump.json')); print(d.get('count', 0))" 2>/dev/null || echo "?")
    log "✅ ChatGPT: $CHATGPT_COUNT facts+sentiment"
  fi
fi

# ── Merge: chatgpt + intel preseed ──
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
" > "$OUTPUT/raw/merged_dump.json"
log "   ✅ Merged: $(python3 -c "import json; print(', '.join(json.load(open('$OUTPUT/raw/merged_dump.json')).get('sources_used',[])))" 2>/dev/null || echo '?') → $(python3 -c "import json; print(len(json.load(open('$OUTPUT/raw/merged_dump.json')).get('facts',[])))" 2>/dev/null || echo '?') facts totali"

# ── FASE 1.5: Pre-processing con Qwen3.5-27B (locale, gratis) ──
log ""
log "━━━ FASE 1.5: QWEN3.5 PRE-PROCESSOR (locale) ━━━"
if ! $DRY_RUN; then
  [[ ! -f "$OUTPUT/raw/grok_dump.json" ]] && echo '{"data":[]}' > "$OUTPUT/raw/grok_dump.json"
  $WAR_ROOM/.venv/bin/python3 "$WAR_ROOM/agents/015_qwen_preprocessor.py" \
    --grok   "$OUTPUT/raw/grok_dump.json" \
    --manus  "$OUTPUT/raw/merged_dump.json" \
    --output "$OUTPUT/raw/processed_dump.json"
  log "✅ Pre-processing completato"
fi

# ══════════════════════════════════════════════════════════
# FASE 2 — T+02:00: BRAIN-TRUST
# ══════════════════════════════════════════════════════════
log ""
log "━━━ FASE 2: BRAIN-TRUST (T+02:00) ━━━"

log "🧠 Gemini 3.1 Pro — generazione 3 concept..."
if ! $DRY_RUN; then
  $WAR_ROOM/.venv/bin/python3 "$WAR_ROOM/agents/03_gemini_strategist.py" \
    --dump   "$OUTPUT/raw/processed_dump.json" \
    --topic  "$TOPIC" \
    --output "$OUTPUT/strategy/gemini_concepts.json"
  log "✅ Gemini concepts generati"
fi

log "🎬 Claude director — copy + JSON slides..."
if ! $DRY_RUN; then
  $WAR_ROOM/.venv/bin/python3 "$WAR_ROOM/agents/04_claude_director.py" \
    --concepts "$OUTPUT/strategy/gemini_concepts.json" \
    --topic    "$TOPIC" \
    --output   "$OUTPUT/strategy/claude_slides.json"
  log "✅ Copy + JSON slides pronti"
fi

# ══════════════════════════════════════════════════════════
# FASE 3 — T+05:00: GENERAZIONE IMMAGINI (ComfyUI/Flux)
# ══════════════════════════════════════════════════════════
log ""
log "━━━ FASE 3: GENERAZIONE IMMAGINI ComfyUI/Flux (T+05:00) ━━━"
if ! $DRY_RUN; then
  $WAR_ROOM/.venv/bin/python3 "$WAR_ROOM/agents/05_comfyui_images.py" \
    --slides "$OUTPUT/strategy/claude_slides.json" \
    --topic  "$TOPIC" \
    --output "$OUTPUT/images/" \
    || log "⚠️  Immagini fallite — continuo con placeholder"
  log "✅ Step immagini completato"
fi

# ══════════════════════════════════════════════════════════
# FASE 4 — T+07:00: KEYNOTE BUILDER
# ══════════════════════════════════════════════════════════
log ""
log "━━━ FASE 4: KEYNOTE ENGINE (T+07:00) ━━━"
if ! $DRY_RUN; then
  mkdir -p "$OUTPUT/keynote" "$OUTPUT/master"
  $WAR_ROOM/.venv/bin/python3 "$WAR_ROOM/agents/06_keynote_builder.py" \
    --slides "$OUTPUT/strategy/claude_slides.json" \
    --images "$OUTPUT/images/" \
    --output "$OUTPUT/keynote/" \
    --master "$OUTPUT/master/"
  log "✅ Keynote esportato + JPG master pronti"
fi

# ══════════════════════════════════════════════════════════
# FASE 5 — T+10:00: DELIVERY
# ══════════════════════════════════════════════════════════
log ""
log "━━━ FASE 5: DELIVERY (T+10:00) ━━━"
if ! $DRY_RUN; then
  zsh "$WAR_ROOM/agents/07_delivery.sh" \
    --topic  "$TOPIC" \
    --master "$OUTPUT/master/"
  log "✅ Upload Google Drive + notifica team inviata"
fi

T_END=$(date +%s)
T_ELAPSED=$(( T_END - T_START ))
log ""
log "🏁 WAR ROOM COMPLETATA in ${T_ELAPSED}s"
log "📁 Output: $OUTPUT/"
log "📋 Log: $LOG_FILE"
