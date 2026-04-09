# Mata Garuda — NLM come Cervello Analitico

> Data: 2026-04-08 | Sessione: brainstorming iniziale

## Perche NLM e' Centrale

NotebookLM Ultra (account antonellosiano@gmail.com):
- 600 source per notebook
- Deep Research gratuito e quasi illimitato
- Sintesi multi-documento automatica
- Grounding con citazioni verificabili
- MCP server gia configurato (`nlm` CLI + `notebooklm-mcp`)

Non e' un accessorio. E' il **cervello analitico** che processa, sintetizza e genera insight
che nessun singolo LLM puo produrre da solo (perche ha 600 fonti di contesto).

## Notebook Domain Strategy

| ID | Notebook | Ruolo | Come si alimenta | Output |
|----|----------|-------|-------------------|--------|
| NB-1 | STRATEGY (esistente) | Architettura, decisioni | Manuale | Grounding architetturale |
| NB-7 | WAR ROOM (esistente) | Audience insights | War Room agents | Pain points, topics |
| NB-14 | MOS MIRROR (esistente) | Sessioni storiche | Auto weekly | Context storico |
| NB-NEW-1 | **INTEL-Immigration** | Esperto immigrazione live | Auto-feed URL articoli immigration | Risposte grounded, trend |
| NB-NEW-2 | **INTEL-Tax** | Esperto fiscale live | Auto-feed URL articoli tax | Cross-check normativo |
| NB-NEW-3 | **INTEL-Property** | Esperto immobiliare live | Auto-feed URL articoli property | Market analysis |
| NB-NEW-4 | **INTEL-Regulation** | Monitor cambiamenti normativi | Auto-feed PDF/URL peraturan.go.id | Semantic diff esperto |
| NB-NEW-5 | **INTEL-Competitor** | Competitor intelligence | Auto-feed news competitor | Strategic intelligence |
| NB-NEW-6 | **INTEL-BaliEconomy** | Macro economia Bali | Auto-feed BPS, tourism | Trend macro |

## Pipeline NLM Feeder

```
Scraper produce articoli classificati
         │
         ▼
  NLM Feeder Worker (garuda:classified consumer)
         │
    ┌────┴────────────────────────────────────────────┐
    │ Per ogni articolo con score > 0.50:             │
    │  1. Leggi topic classification                  │
    │  2. Mappa topic → notebook ID                   │
    │     immigration → NB-INTEL-Immigration           │
    │     tax → NB-INTEL-Tax                          │
    │     property → NB-INTEL-Property                │
    │     regulation_change → NB-INTEL-Regulation      │
    │     competitor → NB-INTEL-Competitor             │
    │     bali_economy → NB-INTEL-BaliEconomy          │
    │  3. source_add(notebook_id, source_type="url",   │
    │     url=article.url)                            │
    │  4. Se notebook ha > 550 fonti:                 │
    │     - Rimuovi le piu vecchie (FIFO)             │
    │     - O crea notebook overflow (INTEL-Tax-2)     │
    └─────────────────────────────────────────────────┘
```

## NLM come Harvester Autonomo (Deep Research)

```
Daily Briefing Agent identifica tema emergente
  │ es: "Nuova regolazione crypto per stranieri in Indonesia"
  │ coverage nel KB: insufficiente
  │
  ▼
Lancia NLM Deep Research:
  research_start(
    notebook_id=temp_nb,
    query="Indonesia crypto regulation foreigners 2026 impact business",
    max_sources=50
  )
  │
  ▼
Attendi completamento (poll research_status)
  │
  ▼
Risultati:
  1. Sources trovate → aggiunte al NB domain permanente
  2. Research summary → ingestito come articolo enriched nel bus
  3. NB temporaneo → eliminato o mantenuto se topic persistente
```

## NLM per Intelligence Products

### Daily Briefing (07:00 WITA)
```
1. Query NB-INTEL-Immigration: "Cosa e' cambiato nelle ultime 24h?"
2. Query NB-INTEL-Tax: "Nuovi obblighi o scadenze?"
3. Query NB-INTEL-Regulation: "Regolamenti modificati?"
4. Claude CLI: sintetizza le 3 risposte in briefing strutturato
```

### Semantic Diff (regulation changes)
```
1. Scraper detecta cambio su pagina .go.id
2. Old text vs new text → NB-INTEL-Regulation query:
   "Confronta questi due testi normativi. Cosa e' cambiato?
    Qual e' l'impatto pratico per un cliente straniero a Bali?"
3. Risposta NLM (grounded sulle 600 fonti di contesto) → alert
```

### Cross-Topic Synthesis (Weekly)
```
notebook_query su tutti i NB-INTEL:
  "Quali pattern emergono questa settimana tra immigrazione,
   tasse, property e regolamenti? Ci sono correlazioni?"
→ Input per Weekly Digest Agent
```

## [OPEN] Da approfondire

- Limiti rate NLM source_add: quante source/giorno possiamo aggiungere?
- NLM Deep Research: limiti mensili su piano Ultra?
- Strategia overflow quando un NB supera 600 fonti
- Costo computazionale NLM query vs query diretta a Claude CLI
- Come gestire la latenza NLM (3-8s per query) nel pipeline real-time
