# HARDWARE ROUTING MAP — Chi gira dove

**Version:** 2.0 (2026-02-14)

---

## Overview

| Mac            | CPU     | RAM   | Ruolo Primario                         | Budget RAM Agenti |
| -------------- | ------- | ----- | -------------------------------------- | ----------------- |
| **Air M4**     | 10-core | 16 GB | Gateway Zan, frontline, orchestrazione | ~8 GB max per AI  |
| **Pro M4 Pro** | 14-core | 48 GB | Heavy compute, modelli locali, Cursor  | ~32 GB max per AI |

**RAM di sistema riservata:** ~4-6 GB su Air, ~8 GB su Pro (macOS + apps).

---

## CLOUD MODELS — Routing per Mac

### Air (Gateway)

| Generale     | Modello Primario | Provider      | Costo/1M tok | Uso                   |
| ------------ | ---------------- | ------------- | ------------ | --------------------- |
| **Zan**      | Sonnet 4.5       | Anthropic MAX | $0 (incluso) | Chat, triage, routing |
| **Kodex**    | Sonnet 4.5       | Anthropic MAX | $0 (incluso) | Coding quotidiano     |
| **Sentinel** | Gemini 3 Pro     | Google Ultra  | $0 (incluso) | Research, 2M context  |
| **Vox**      | Sonnet 4.5       | Anthropic MAX | $0 (incluso) | Content creation      |
| **Flash**    | Gemini Flash     | Google Ultra  | $0 (incluso) | FAQ, triage <2s       |
| **Gravity**  | Gemini 3 Pro     | Google Ultra  | $0 (incluso) | Health monitoring     |

### Pro (Heavy Compute)

| Compito             | Modello      | Provider       | Quando                      |
| ------------------- | ------------ | -------------- | --------------------------- |
| IDE-aware coding    | cursor-ultra | Cursor Ultra   | Kodex delega task complessi |
| Architecture review | Opus 4.6     | Anthropic MAX  | Solo decisioni critiche     |
| Long context coding | Kimi 2.5     | Moonshot       | File >100K token            |
| Backup reasoning    | MiniMax M2.1 | MiniMax Portal | Free, task secondari        |

### Fallback Chain

```
Primary Failed?
  ├─ Sonnet 4.5 down → Gemini 3 Pro → Opus 4.6
  ├─ Gemini 3 Pro down → Opus 4.6 → Sonnet 4.5
  ├─ Gemini Flash down → Haiku 4.5 → MiniMax M2.1
  └─ All cloud down → Ollama local (emergency only)
```

---

## LOCAL MODELS — Cosa installare su Ollama

### Air (16 GB — MAX 6 GB per modelli locali)

| Modello            | Parametri | Quant  | RAM     | Scopo                          | Quando usare           |
| ------------------ | --------- | ------ | ------- | ------------------------------ | ---------------------- |
| `qwen2.5:3b`       | 3B        | Q4_K_M | ~2.5 GB | Classificazione, triage locale | Cloud down, rate limit |
| `deepseek-r1:1.5b` | 1.5B      | Q4_0   | ~1.2 GB | Ragionamento veloce            | Gia installato         |

**Perche solo 2 modelli:** Air ha 16 GB totali. macOS vuole ~5 GB, OpenClaw + plugins ~3 GB, Chrome/apps ~2 GB. Restano ~6 GB per modelli. Caricare modelli piu grandi causa swap e degrada le performance del gateway.

**NON installare su Air:** Modelli >7B, modelli vision, modelli embedding (usa OpenAI API).

### Pro (48 GB — MAX 24 GB per modelli locali)

| Modello                 | Parametri | Quant  | RAM     | Scopo                      | Quando usare                          |
| ----------------------- | --------- | ------ | ------- | -------------------------- | ------------------------------------- |
| `qwen2.5-coder:14b`     | 14B       | Q4_K_M | ~10 GB  | Code generation locale     | Anthropic rate limit, task bulk       |
| `qwen2.5:14b`           | 14B       | Q4_K_M | ~10 GB  | General reasoning locale   | Research offline, document processing |
| `nomic-embed-text:v1.5` | 137M      | FP16   | ~0.5 GB | Embedding locale           | Backup se OpenAI API down             |
| `deepseek-r1:7b`        | 7B        | Q4_K_M | ~5 GB   | Chain-of-thought reasoning | Complex analysis offline              |

**Perche Q4_K_M:** Miglior rapporto qualita/dimensione. Q8 raddoppia la RAM senza miglioramenti percepibili. Q4_0 e troppo lossy per coding.

**Perche 14B max:** I modelli 32B+ richiedono >20 GB e lascerebbero poco spazio per il sistema. 14B e il sweet spot su Apple Silicon per qualita/velocita.

---

## DECISIONE: Locale vs Cloud

```
                     Domanda?
                        │
            ┌───────────┴───────────┐
      Cloud disponibile?      Cloud down/rate limit?
            │                       │
            ▼                       ▼
    USA CLOUD (sempre)       USA LOCALE (fallback)
    - Qualita superiore      - qwen2.5-coder:14b (coding)
    - Velocita ok            - qwen2.5:14b (reasoning)
    - $0 con abbonamenti     - deepseek-r1:7b (analysis)
```

**Regola:** Cloud SEMPRE quando disponibile. Locale SOLO come fallback.

**Perche:** Con $640/mese di abbonamenti cloud, i modelli locali non competono in qualita. Li teniamo per:

1. Rate limiting Anthropic (limiti settimanali MAX)
2. Downtime cloud provider
3. Task bulk/batch che esaurirebbero i limiti
4. Privacy: dati che non devono uscire dalla rete locale

---

## RESOURCE BUDGET

### Air — Resource Allocation

```
16 GB RAM Total
├── macOS + System:     ~4.5 GB
├── OpenClaw Gateway:   ~2.0 GB (Zan + plugins)
├── Chrome + Apps:      ~2.5 GB
├── Ollama Models:      ~3.5 GB (qwen2.5:3b + deepseek-r1:1.5b)
├── Headroom:           ~3.5 GB (buffer per picchi)
└── SWAP:               0 GB target (swap = performance killer)
```

### Pro — Resource Allocation

```
48 GB RAM Total
├── macOS + System:     ~6.0 GB
├── OpenClaw Gateway:   ~2.0 GB (agenti Pro)
├── Cursor IDE:         ~3.0 GB
├── Docker/Dev Tools:   ~3.0 GB
├── Ollama Models:      ~25 GB (tutti i modelli caricati)
├── Headroom:           ~9.0 GB (buffer per task pesanti)
└── SWAP:               0 GB target
```

---

## BANDWIDTH & COST IMPACT

| Provider      | Piano   | Limite                      | Uso Stimato                | Margine         |
| ------------- | ------- | --------------------------- | -------------------------- | --------------- |
| Anthropic MAX | $200/mo | Settimanale (non divulgato) | ~70% con 5 agenti          | 30% buffer      |
| Google Ultra  | $200/mo | "Illimitato"\*              | Sentinel + Gravity + Flash | Alto margine    |
| Cursor Ultra  | $200/mo | "Illimitato"\*              | Kodex task pesanti         | Sottoutilizzato |
| Moonshot Kimi | $20/mo  | Abbonamento                 | Long context quando serve  | Sottoutilizzato |

**Strategia di risparmio Anthropic:**

- Flash e Gravity usano Gemini (gratuito) → risparmia ~40% delle chiamate Anthropic
- Sentinel usa Gemini 3 Pro → risparmia ulteriore ~20%
- Solo Zan, Kodex e Vox consumano Anthropic
- Haiku 4.5 per task di triage semplici (costo 5x inferiore a Sonnet)

**\*"Illimitato":** Google e Cursor hanno fair-use limits non dichiarati. Monitorare se si verificano throttling.
