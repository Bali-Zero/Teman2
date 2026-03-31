# BALI ZERO WAR ROOM

**Automated Marketing & Journalism Pipeline**
_Multi-source intelligence → carousel Instagram in 10-15 minuti_

---

## Architettura

```
FASE 0  → Topic Selector    Exa + NLM NB-7 + xAI Grok (parallelo) → DeepSeek synthesis
FASE 1  → Research          Exa + xAI + NLM (parallelo) → merged_dump.json
FASE 1.5→ Pre-processor     DeepSeek R1:32b locale (o deterministic fallback)
FASE 2  → Brain-Trust       Gemini strategist → 3 concept → Claude director → JSON slides
FASE 3  → Images            Fireworks Flux.1 Dev — 1 cover + 5 slide (1440×1800)
FASE 4  → Canva             Python MCP → design DAHE6lx1lf8 → canva_pending.json
FASE 5  → Delivery          Telegram → Zero (IT) + Damar (ID) — singola notifica
```

## Utilizzo

```bash
# Pipeline completa (topic auto da intel scraper)
./pipeline.sh

# Topic manuale
./pipeline.sh "Coretax 2025"

# Dry run (nessuna azione reale)
./pipeline.sh "OSS perizinan" --dry-run
```

## Struttura agenti

```
agents/
├── 00_topic_selector.py      # Multi-source: Exa + NLM + xAI → DeepSeek synthesis
├── 09_exa_researcher.py      # Exa AI — Indonesian legal/news domains, 72h
├── 10_xai_researcher.py      # xAI Grok — X/Twitter signals Indonesia
├── 11_nlm_researcher.py      # NLM NB-7 — audience pain points
├── 015_qwen_preprocessor.py  # DeepSeek R1:32b locale (window 01:00-06:05 WITA)
├── 03_gemini_strategist.py   # Gemini → 3 concept asimmetrici
├── 04_claude_director.py     # Claude Opus → copy + JSON slides + NLM validation
├── 05_image_brainstorm.py    # Fireworks Flux.1 Dev — 6 immagini 1440×1800
├── 06_canva_builder.py       # MCP Canva → template DAHE6lx1lf8 (11 slide)
└── 07_delivery.sh            # Telegram: Zero (IT) + Damar (ID)
```

## Modelli

| Fase | Modello         | Provider      | Ruolo                     |
| ---- | --------------- | ------------- | ------------------------- |
| 0    | DeepSeek Chat   | DeepSeek API  | Topic synthesis           |
| 0    | Grok-3          | xAI API       | X/Twitter signals         |
| 1    | Exa Neural      | Exa API       | News search               |
| 1.5  | DeepSeek R1:32b | Ollama locale | Pre-processing (finestra) |
| 2a   | Gemini Pro      | Google API    | Concept strategici        |
| 2b   | Claude Opus 4.6 | Anthropic API | Copy + JSON slides        |
| 3    | Flux.1 Dev      | Fireworks API | Immagini 1440×1800        |
| 4    | MCP Canva       | Canva API     | Carousel builder          |

## Canva Template DAHE6lx1lf8 — Layout slide

| Slide | Layout                      | Body slot |
| ----- | --------------------------- | --------- |
| 1     | Cover full-bleed            | Sì        |
| 2-3   | Split image + testo         | Sì        |
| 4     | Immagine manuale + testo    | Sì        |
| 5-8   | Testo + immagine            | Sì        |
| 9     | Heading-only (no body slot) | No        |
| 10    | Testo standard              | Sì        |
| 11    | CTA logo+tagline (no body)  | No        |

Slide 4 e 9: immagini inserite manualmente nel template (non da Fireworks).

## Applicazione Canva

Dopo pipeline completata, aprire `~/Desktop/APPLICA_WAR_ROOM.md` in Claude app desktop (Pro).

## Env vars richieste

```
OPENAI_API_KEY         # Claude director (via OpenRouter)
ANTHROPIC_API_KEY      # Claude Opus
GEMINI_API_KEY         # Gemini strategist
FIREWORKS_API_KEY      # Image generation
EXA_API_KEY            # Exa researcher
GROK_API_KEY           # xAI Grok
DEEPSEEK_API_KEY       # Topic synthesis
TELEGRAM_BOT_TOKEN     # Delivery
TELEGRAM_GROUP_ID      # Chat ID Zero
CANVA_API_KEY          # Canva MCP
```
