# 🚨 BALI ZERO WAR ROOM

**Automated Marketing & Journalism Pipeline**
_Giornalismo investigativo multi-agente → carousel Instagram in 5-10 minuti_

---

## Architettura

```
T+00:00 → FASE 1:   Grok 4 (X/Twitter 72h) + Manus AI (gov/fiscal sources) — parallelo
T+01:30 → FASE 1.5: Qwen3-32B pre-processor (locale, gratuito) — dedup + classify
T+02:00 → FASE 2:   Gemini 3.1 Pro Deep Think → 3 concept asimmetrici
T+03:00 → FASE 2:   Claude Opus 4.6 → pick best → validate → JSON slides + image prompts
T+05:00 → FASE 3:   browser-use → gemini.google.com (zero@balizero.com Ultra) → immagini
T+07:00 → FASE 4:   Python + AppleScript → Keynote 1080x1350 → export JPG
T+10:00 → FASE 5:   gog upload Google Drive → WhatsApp notification team
```

## Utilizzo

```bash
# Pipeline completa
./pipeline.sh "Coretax 2025"

# Senza Manus (risparmia crediti)
./pipeline.sh "KBLI error blocca visto" --skip-manus

# Test senza azioni reali
./pipeline.sh "OSS perizinan" --dry-run
```

## Struttura

```
war_room/
├── pipeline.sh              # Orchestratore master
├── config/
│   ├── brand.json           # Canvas, font, colori, delivery
│   └── prompts.json         # Tutti i prompt per ogni agente
├── agents/
│   ├── 01_grok_scraper.py   # X/Twitter 72h via browser-use
│   ├── 02_manus_launcher.py # Manus AI (⚠️ conferma richiesta)
│   ├── 015_qwen_preprocessor.py  # Qwen3-32B locale (gratis)
│   ├── 03_gemini_strategist.py   # Gemini 3.1 Pro → 3 concept
│   ├── 04_claude_director.py     # Claude Opus → copy + JSON
│   ├── 05_gemini_images.py       # Gemini Ultra → immagini
│   ├── 06_keynote_builder.py     # Python + AppleScript → .key + JPG
│   └── 07_delivery.sh            # Drive + WhatsApp
├── assets/
│   └── bz_logo_clear.png    # Logo (copia qui)
└── output/
    ├── raw/                 # Dump Grok + Manus
    ├── strategy/            # 3 concept Gemini
    ├── copy/                # slides.json da Claude
    ├── images/              # Immagini da Gemini Ultra
    ├── keynote/             # .key + JPG esportati
    └── master/              # Output finale (ZIP + Drive)
```

## Modelli Utilizzati

| Fase | Modello         | Costo         | Ruolo                |
| ---- | --------------- | ------------- | -------------------- |
| 1    | Grok 4          | $0 (Premium+) | Sentiment X/Twitter  |
| 1    | Manus AI        | ⚠️ crediti    | Ricerca gov/fiscale  |
| 1.5  | Qwen3-32B       | $0 (locale)   | Pre-processing       |
| 2a   | Gemini 3.1 Pro  | $0 (Ultra)    | Strategia            |
| 2b   | Claude Opus 4.6 | $0 (MAX)      | Copy + validazione   |
| 3    | Gemini Ultra    | $0 (Ultra)    | Generazione immagini |
| 4    | AppleScript/JXA | $0            | Keynote automation   |

**Costo totale pipeline: €0** ✅

## Configurazione Brand

- Canvas: 1080x1350pt (Instagram Portrait 4:5)
- Background: `#373d42` (Antracite)
- Font titoli: LeagueSpartan-ExtraBold (fallback: Impact)
- Font corpo: Montserrat-Medium (fallback: Helvetica Neue)
- Logo: `assets/bz_logo_clear.png` → X=458, Y=1150
- Darkening cover: 30%

## ⚠️ Note Operative

1. **Manus AI**: richiede conferma esplicita prima dell'uso (crediti limitati)
2. **Logo**: copia `bz_logo_clear.png` in `~/war_room/assets/`
3. **Chrome profile**: Gemini images usa il profilo loggato come zero@balizero.com
4. **Claude proxy**: richiede Claude Desktop aperto su localhost:3456
5. **Qwen3**: `ollama pull qwen3:32b` se non già scaricato
