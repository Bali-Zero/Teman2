#!/bin/zsh
# ============================================================
# BALI ZERO WAR ROOM — Master Pipeline Orchestrator
# Usage: ./pipeline.sh "Coretax 2025" [--dry-run] [--skip-manus]
# ============================================================

set -euo pipefail

# Topic solo se primo arg non è un flag
[[ -n "${1:-}" && "${1:0:2}" != "--" ]] && TOPIC="$1" || TOPIC=""
DRY_RUN=false
SKIP_MANUS=false
AUTO_MODE=false
WAR_ROOM="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$WAR_ROOM/logs/pipeline_$(date +%Y%m%d_%H%M%S).log"

for arg in "$@"; do
  case $arg in
    --dry-run) DRY_RUN=true ;;
    --skip-manus) SKIP_MANUS=true ;;
    --auto) AUTO_MODE=true ;;  # non-interactive mode (cron/pipeline chain)
  esac
done

# ── Logging ────────────────────────────────────────────────
log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
die() { log "❌ FATAL: $*"; exit 1; }

# Load env vars (API keys)
[[ -f "$WAR_ROOM/.env" ]] && source "$WAR_ROOM/.env"

log "🚨 BALI ZERO WAR ROOM AVVIATA"
log "🕐 Start: $(date)"
$DRY_RUN && log "⚠️  DRY RUN MODE — nessuna azione reale"

OUTPUT="$WAR_ROOM/output"
T_START=$(date +%s)

# ── Cleanup output precedente ──────────────────────────────
# (N) = null glob — nessun errore se la dir è vuota (zsh)
rm -f "$OUTPUT"/raw/*(N) "$OUTPUT"/strategy/*(N) \
      "$OUTPUT"/images/*(N) 2>/dev/null || true
rm -f "$OUTPUT"/keynote/presentation.key 2>/dev/null || true

# ── Check Intel Scraper output — pre-seed data + auto-extract topic ────────
INTEL_LATEST="$HOME/Desktop/nuzantara/apps/bali-intel-scraper/data/intel_output_latest.json"
INTEL_FRESH=false
if [[ -f "$INTEL_LATEST" ]]; then
  INTEL_AGE=$(( $(date +%s) - $(date -r "$INTEL_LATEST" +%s) ))
  if (( INTEL_AGE < 28800 )); then  # 8h
    INTEL_FRESH=true
    log "✅ Intel Scraper output fresco (${INTEL_AGE}s fa)"

    # Auto-estrai topic dall'articolo più rilevante (score più alto, non categoria generica)
    if [[ -z "$TOPIC" ]]; then
      TOPIC=$(python3 -c "
import json
d = json.load(open('$INTEL_LATEST'))
arts = [a for a in d.get('articles', []) if a.get('enrichment')]
if not arts:
    arts = d.get('articles', [])
# Ordina per score decrescente, prendi il titolo più rilevante
arts.sort(key=lambda a: a.get('qwen_score', 0), reverse=True)
best = arts[0] if arts else {}
# Estrai parole chiave dal titolo (max 60 chars)
title = best.get('title', '')[:60]
print(title if title else 'Indonesia Business Intelligence')
" 2>/dev/null || echo "Indonesia Business Intelligence")
      log "📌 Topic auto-estratto dall'intel: $TOPIC"
    fi

    # Pre-seed: converti intel → formato manus per il preprocessor
    python3 -c "
import json
with open('$INTEL_LATEST') as f: d = json.load(f)
arts = d.get('articles', [])
manus = {
  'facts': [{'title': a.get('title',''), 'brief': str(a.get('enrichment',{}).get('executive_brief','')), 'category': a.get('qwen_category',''), 'source': a.get('url','')} for a in arts if a.get('enrichment')],
  'topics': list(set(a.get('qwen_category','') for a in arts if a.get('qwen_category'))),
  'generated_at': d.get('generated_at',''),
  'source': 'intel_scraper'
}
print(json.dumps(manus, ensure_ascii=False, indent=2))
" > "$OUTPUT/raw/intel_preseed.json"
    INTEL_COUNT=$(python3 -c "import json; d=json.load(open('$INTEL_LATEST')); print(len([a for a in d.get('articles',[]) if a.get('enrichment')]))" 2>/dev/null || echo "?")
    log "   📂 Intel pre-seed → $OUTPUT/raw/intel_preseed.json ($INTEL_COUNT enriched articles)"
  else
    log "⏰ Intel output vecchio (${INTEL_AGE}s)"
  fi
else
  log "ℹ️  intel_output_latest.json non trovato"
fi

# Topic finale — fallback
[[ -z "$TOPIC" ]] && die "Nessun topic disponibile. Passa ./pipeline.sh 'topic' o assicurati che intel scraper sia fresco (<8h)"
log "📌 Topic: $TOPIC"

# ══════════════════════════════════════════════════════════
# FASE 1 — T+00:00: SCRAPING PARALLELO
# ══════════════════════════════════════════════════════════
log ""
log "━━━ FASE 1: INTELLIGENCE GATHERING (T+00:00) ━━━"

# Grok scraper (background)
log "🔍 Lanciando Grok scraper..."
if ! $DRY_RUN; then
  $WAR_ROOM/.venv/bin/python3 "$WAR_ROOM/agents/01_grok_scraper.py" \
    --topic "$TOPIC" \
    --output "$OUTPUT/raw/grok_dump.json" &
  GROK_PID=$!
  log "   Grok PID: $GROK_PID"
fi

# Exa AI Researcher (background — API, veloce, affidabile)
log "🔎 Lanciando Exa AI researcher..."
if ! $DRY_RUN; then
  $WAR_ROOM/.venv/bin/python3 "$WAR_ROOM/agents/09_exa_researcher.py" \
    --topic "$TOPIC" \
    --output "$OUTPUT/raw/exa_dump.json" \
    --deep &
  EXA_PID=$!
  log "   Exa PID: $EXA_PID"
fi

# Manus AI (foreground — --force in auto mode, conferma interattiva altrimenti)
if ! $SKIP_MANUS; then
  log "🤖 Manus AI — ricerca gov/fiscale"
  if ! $DRY_RUN; then
    MANUS_ARGS="--topic $TOPIC --output $OUTPUT/raw/manus_dump.json"
    $AUTO_MODE && MANUS_ARGS="$MANUS_ARGS --force"
    $WAR_ROOM/.venv/bin/python3 "$WAR_ROOM/agents/02_manus_launcher.py" \
      $MANUS_ARGS || log "⚠️  Manus fallito — continuo con altri dati"
  fi
else
  log "⏭️  Manus saltato (--skip-manus)"
  echo '{"facts": [], "skipped": true}' > "$OUTPUT/raw/manus_dump.json"
fi

# Attendi Grok (max 120s timeout)
if ! $DRY_RUN; then
  log "⏳ Attendo completamento Grok (max 120s)..."
  GROK_TIMEOUT=120
  GROK_ELAPSED=0
  while kill -0 $GROK_PID 2>/dev/null; do
    sleep 5; GROK_ELAPSED=$((GROK_ELAPSED+5))
    if [ $GROK_ELAPSED -ge $GROK_TIMEOUT ]; then
      log "⏰ Grok timeout (${GROK_TIMEOUT}s) — killing"
      kill $GROK_PID 2>/dev/null || true
      break
    fi
  done
  wait $GROK_PID 2>/dev/null || true
  if [ -f "$OUTPUT/raw/grok_dump.json" ]; then
    log "✅ Grok completato"
  else
    log "⚠️  Grok fallito/timeout — continuo con altri dati"
  fi

  # Attendi Exa (max 90s — API, dovrebbe finire in ~15s)
  log "⏳ Attendo completamento Exa (max 90s)..."
  EXA_TIMEOUT=90
  EXA_ELAPSED=0
  while kill -0 $EXA_PID 2>/dev/null; do
    sleep 3; EXA_ELAPSED=$((EXA_ELAPSED+3))
    if [ $EXA_ELAPSED -ge $EXA_TIMEOUT ]; then
      log "⏰ Exa timeout (${EXA_TIMEOUT}s) — killing"
      kill $EXA_PID 2>/dev/null || true
      break
    fi
  done
  wait $EXA_PID 2>/dev/null || true
  if [ -f "$OUTPUT/raw/exa_dump.json" ]; then
    EXA_COUNT=$(python3 -c "import json; print(json.load(open('$OUTPUT/raw/exa_dump.json')).get('stats',{}).get('total_unique',0))" 2>/dev/null || echo "?")
    log "✅ Exa completato ($EXA_COUNT facts)"
  else
    log "⚠️  Exa fallito/timeout"
  fi
fi

# ── Merge all data sources: intel + manus + exa ──
log "🔗 Merging all intelligence sources..."
python3 -c "
import json
from pathlib import Path

output_raw = Path('$OUTPUT/raw')
all_facts = []
seen_titles = set()
sources_used = []

# Load each source in priority order
for name, path in [
    ('manus', output_raw / 'manus_dump.json'),
    ('exa', output_raw / 'exa_dump.json'),
    ('intel', output_raw / 'intel_preseed.json'),
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
    'topics': list(set(f.get('category', '') for f in all_facts if f.get('category'))),
    'sources_used': sources_used,
    'merged_at': __import__('datetime').datetime.now().isoformat(),
}
print(json.dumps(merged, ensure_ascii=False, indent=2))
" > "$OUTPUT/raw/manus_dump.json"
log "   ✅ Merged: $(python3 -c "import json; d=json.load(open('$OUTPUT/raw/manus_dump.json')); print(', '.join(d.get('sources_used',[])))" 2>/dev/null || echo '?') → $(python3 -c "import json; print(len(json.load(open('$OUTPUT/raw/manus_dump.json')).get('facts',[])))" 2>/dev/null || echo '?') facts totali"

# ── FASE 1.5: Pre-processing con Qwen3.5-27B (locale, gratis) ──
log ""
log "━━━ FASE 1.5: QWEN3.5 PRE-PROCESSOR (locale) ━━━"
if ! $DRY_RUN; then
  $WAR_ROOM/.venv/bin/python3 "$WAR_ROOM/agents/015_qwen_preprocessor.py" \
    --grok "$OUTPUT/raw/grok_dump.json" \
    --manus "$OUTPUT/raw/manus_dump.json" \
    --output "$OUTPUT/raw/processed_dump.json"
  log "✅ Pre-processing completato"
fi

# ══════════════════════════════════════════════════════════
# FASE 2 — T+02:00: BRAIN-TRUST
# ══════════════════════════════════════════════════════════
log ""
log "━━━ FASE 2: BRAIN-TRUST (T+02:00) ━━━"

# Gemini 3.1 Pro Deep Think — Stratega
log "🧠 Gemini 3.1 Pro — generazione 3 concept..."
if ! $DRY_RUN; then
  $WAR_ROOM/.venv/bin/python3 "$WAR_ROOM/agents/03_gemini_strategist.py" \
    --dump "$OUTPUT/raw/processed_dump.json" \
    --topic "$TOPIC" \
    --output "$OUTPUT/strategy/gemini_concepts.json"
  log "✅ Gemini concepts generati"
fi

# Gemini 3.1 Pro — Direttore Creativo (ex Claude Opus)
log "🎬 Gemini 3.1 Pro — copy + JSON slides..."
if ! $DRY_RUN; then
  $WAR_ROOM/.venv/bin/python3 "$WAR_ROOM/agents/04_claude_director.py" \
    --concepts "$OUTPUT/strategy/gemini_concepts.json" \
    --output   "$OUTPUT/strategy/claude_slides.json"
  log "✅ Copy + JSON slides pronti"
fi

# ══════════════════════════════════════════════════════════
# FASE 3 — T+05:00: GENERAZIONE IMMAGINI
# ══════════════════════════════════════════════════════════
log ""
log "━━━ FASE 3: GENERAZIONE IMMAGINI GEMINI (T+05:00) ━━━"
if ! $DRY_RUN; then
  # PREREQUISITO: Chrome deve girare con --remote-debugging-port=9222
  # chrome-debug.sh lo avvia/riavvia se necessario (non fa nulla se già attivo)
  log "🔧 Verifico Chrome CDP (porta 9222)..."
  "$WAR_ROOM/chrome-debug.sh" || { log "❌ Chrome CDP non disponibile — skip immagini"; }

  $WAR_ROOM/.venv/bin/python3 "$WAR_ROOM/agents/05_gemini_images.py" \
    --slides "$OUTPUT/strategy/claude_slides.json" \
    --output "$OUTPUT/images/" \
    --model  "2.0 Flash" \
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
  bash "$WAR_ROOM/agents/07_delivery.sh" \
    --topic "$TOPIC" \
    --master "$OUTPUT/master/"
  log "✅ Upload Google Drive + WhatsApp notification inviata"
fi

T_END=$(date +%s)
T_ELAPSED=$(( T_END - T_START ))
log ""
log "🏁 WAR ROOM COMPLETATA in ${T_ELAPSED}s"
log "📁 Output: $OUTPUT/"
log "📋 Log: $LOG_FILE"
