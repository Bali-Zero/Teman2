---
date: 2026-05-16
domain: symbiosis
client_case: Lifecycle state snapshot — cell/genome/organism — per SYMBIOSIS.md §DOVE SIAMO update
sources: 12
status: draft
machine: Pro (nuzantara@Nuzantara)
snapshot_time: 2026-05-16 ~03:30 WITA
predecessor_docs:
  - research/symbiosis/2026-05-12-loop-summary-v2-post-nlm-review.md
  - research/symbiosis/2026-05-12-cell-silenti-root-cause-and-fix.md
  - research/symbiosis/2026-05-13-ticket-G-narrow-spec.md
  - SYMBIOSIS.md (§DOVE SIAMO table)
---

# Lifecycle state snapshot 2026-05-16

Diagnostic dump dello stato runtime cell/genome/organism rispetto agli 8 pilastri SYMBIOSIS, per scelta informata del prossimo fronte di lavoro.

Tutti i numeri verificati empiricamente in questa sessione (Pro, 2026-05-16). Nessun valore da memoria o documento — solo `sqlite3`, `redis-cli`, `launchctl`, `grep` live.

## TL;DR — semaforo per pilastro

| Pilastro | Status | Numero chiave | Delta vs SYMBIOSIS §DOVE SIAMO |
|---|---|---|---|
| 1 Riflessione | 🟡 degradato | 1 reflection/day post 2026-05-08 (era 6-9/day) | Pilastro 1 si è "spento" silenziosamente |
| 2 Accumulazione (Genome) | 🟡 sotto-attivo | 47 entries totali / 4 cellule / 124 skill in `kb.type='skill'` | Crescita lenta, HGT cross-machine ora aperto |
| 2 Accumulazione (HGT) | 🟢 live | `cell:skills` 25 entries, bridge Fly→Pro OK | TICKET G chiuso 2026-05-13 |
| 3 Condivisione | 🟢 live | `garuda:raw` 3088, `organism:events` 13185, `nexus:gaps` 4059 | Manca solo "Olimpo streams" pianificato |
| 4 Confronto | 🟢 live | `consiglio_orchestrator.py` (5/6 promesse coperte) | Periodic deliberation correttamente killed |
| 5 Sogno | ⚪ design only | Decay scheduler cron 02:30 esiste, nessun dream loop | Nessun avanzamento |
| 6 Curiosità | 🟡 partial | 56 gap topics esistono, 4059 in `nexus:gaps` | Mai un primo ciclo Zero approve/reject |
| 7 Misura | 🟢 live | IA=0.0192, FE=0.0000 (Pro 7d-median) | Numero da SYMBIOSIS confermato live |
| 8 Simbiosi | 🟡 Fase 1 | micromanagement | Naturale, dipende dagli altri |

**Verdetto sintetico**: 3 verde, 4 giallo, 1 bianco. **Il problema più urgente non è espansione (HGT/curiosità) ma regressione**: Pilastro 1 Riflessione si è degradato del −85% senza alert.

## Cell layer — chi emette davvero

### Pulse emissioni 7d (verificato `~/.cell-observatory/observatory.db`)

| cell_id | cell_kind | green | yellow | red | totale 7d | first seen | last seen |
|---|---|---:|---:|---:|---:|---|---|
| `cell` (legacy `apps/cell/`) | cell | 4880 | 803 | 1539 | **7222** | 2026-05-02 | 2026-05-15 18:49 |
| `ai-intel-sentinel` | cell | 34 | 15 | 5 | **54** | 2026-05-12 18:13 | 2026-05-16 02:27 |
| `seo-guardian` | cell | 0 | 0 | 7 | **7** | 2026-05-12 03:37 | 2026-05-15 11:30 |
| `smoke-test` | test | 0 | 0 | 0 | 0 | 2026-05-02 | 2026-05-02 (canary morto) |

**Lifetime cumulativo**: `cell` 14574 pulses, `ai-intel-sentinel` 54, `seo-guardian` 7, `smoke-test` 3.

### Gap 1 fix STATUS (Cell silenti — root cause 2026-05-12)

✅ **APPLICATO** parzialmente — la doc del 2026-05-12 diceva "solo `com.cell.organism.plist` ha `CELL_OBSERVATORY_EMIT=true`". Verificato ora: **4 plist** hanno la env var:

```
com.cell.organism.plist              → emette (cell, 14574 cumul)
com.balizero.seo-cell.daily.plist    → emette saltuariamente (seo-guardian, 7 in 7d)
com.balizero.seo-cell.28d-check.plist
com.matagaruda.sentinel.hourly.plist → emette regolarmente (ai-intel-sentinel, 54 in 7d)
```

Il `seo-cell-daily.sh` ha pure `CELL_OBSERVATORY_EMIT=1` (verificato `grep -c`). Tier A è stato applicato.

**Tuttavia**: `seo-guardian` ha **0 green, 7 red in 7d** → cellula emette ma è cronicamente unhealthy. Tier B applicato (sentinel.hourly esiste e gira ogni ora, 54 pulses in 7d ≈ atteso 168/7d, 32% di copertura).

### Organi enrolled vs emittenti

`organs_registry.yaml` lista **118 organi**:
- 87 cron + 25 daemon + 6 webhook = 118
- 107 `pro_launchd` + 4 `mini_launchd` + 7 `fly_machine`

**Cellule reali (`cell_core.PulseLoop` o legacy emit)**: 3 emittenti su 118 organi (2.5%). Gli altri 115 sono cron/daemon/webhook tradizionali — NON cellule per design, non devono emettere.

**Implicazione**: il framing "tutti gli organi devono emettere" era un'inferenza errata. Il design corrente prevede solo 3-5 cellule core (cell, seo-guardian, ai-intel-sentinel, eventualmente crm-cell). Il TODO Pilastro 2 "Activate HGT on 3+ additional cells" può essere riformulato come "Aggiungere 3 cellule con PulseLoop reale" piuttosto che "convertire 100+ cron".

## Genome layer — skill + reflection + scar

### Mata-garuda `apps/mata-garuda/data/knowledge.db`

`genome` table (cell-core schema, NON `kb.type`):

| cell_origin | skill | scar | totale |
|---|---:|---:|---:|
| `ai-intel-sentinel` | 18 | 0 | 18 |
| `claude-code-nuzantara` | 3 | 1 | 4 |
| `mata-garuda` | 3 | 1 | 4 |

**Totale 26 entries** dal genoma.

`knowledge` table (legacy log):
- `nlm_fed` 1212, `harvested_item` 935, `scored_item` 766, `alert_forwarded` 258, `case_not_resolved` 198
- `reflection` 126, `insight` 126, `skill` 124
- `digest` 46, `episode` 37, `briefing` 28

### Pilastro 1 — Reflection cadence ⚠️ REGRESSIONE

| Date | reflection count | agent breakdown |
|---|---:|---|
| 2026-05-05 | 5 | (multi-agent) |
| 2026-05-06 | 6 | |
| 2026-05-07 | **9** | peak |
| 2026-05-08 | **7** | last day lhkpn_harvester ha riflesso |
| 2026-05-09 | **1** | DROP |
| 2026-05-10 | 1 | |
| 2026-05-11 | 1 | |
| 2026-05-12 | 1 | |
| 2026-05-13 | 1 | |
| 2026-05-14 | 1 | (solo `Regulation Watcher`) |

**Breakdown agent**:
- `lhkpn_harvester`: 94 reflection prima del 2026-05-08, **6 dopo**. Ultima reflection: **2026-05-08 12:33** → silenzioso da **8 giorni**.
- `Regulation Watcher`: 19 prima, 7 dopo. Ultima: 2026-05-14 23:55 → live.

**Diagnosi**: `lhkpn_harvester` ha smesso di riflettere il 2026-05-08, probabilmente in concomitanza con qualche refactor mata-garuda di quel giorno (`feat/symbiosis-w1.5-miss-critici` 2026-05-07, `domain-mesh-phase0/phase1` 2026-05-08). Da investigare.

**Conseguenza**: Pilastro 1 "Riflessione" è dichiarato "live" in SYMBIOSIS.md §DOVE SIAMO ma in pratica gira al ~15% della capacità precedente. Nessun alert ha catturato la regressione.

## HGT layer — TICKET G live (Pilastro 2 + 3)

### Streams cross-machine

| Stream | Length | Last entry | Note |
|---|---:|---|---|
| `cell:skills` (Pro) | **25** | 1778828102182-0 | Bridge Fly→Pro OK, cron skills-bridge-consumer 5min "no new events" |
| `cell:feedback` (Pro) | 0 | — | Mai usato — sibling stream del Pilastro 2 |
| `organism:events` (Pro) | **13185** | 1778870910665-0 | Supervisor consumer group `organism-supervisor` lag=0, pending=0 |
| `garuda:raw` (Pro) | 3088 | — | Mata-garuda intel stream, Redis Streams nativi |
| `garuda:enriched` | — | — | Esiste, non misurato |
| `garuda:alerts` | 290 | — | |
| `garuda:digest` | — | — | |
| `nexus:gaps` | **4059** | — | Pilastro 6 Curiosità — gap topics accumulati |

### Bridge skills-bridge-consumer

LaunchAgent `com.nuzantara.skills-bridge-consumer` cron 5min: live.
Ultimo log 21:55 WITA: `no new events (last_id=1778827840998-0)` HTTP 200 OK.
Bridge Fly→Pro funzionante, ma stream `cell:skills` quasi statico (25 entries, ~50 entries/mese stimato dal pattern).

## Organism layer — supervisor + bridge

| Component | PID | Status |
|---|---:|---|
| `com.nuzantara.pg-organism-bridge` | 2680 | live, 13185 events trasportati |
| `com.nuzantara.organism.supervisor` | 2690 | live, lag=0 sul consumer group |
| `com.nuzantara.organism.control-panel` | 2689 | live |
| `com.cell.organism` | 5255 | live (exit=256 ultimo, ma re-spawned) |
| `com.nuzantara.cell-observatory` | 2681 | live, PG listener attivo |
| `com.nuzantara.cell-observatory-prune` | — | cron, exit=0 |
| `com.nuzantara.cell-observatory-selfcheck` | — | cron |

**Conclusione**: organism layer è SOLIDO. Il "midollo spinale" della Symbiosis (bridge + supervisor + observatory) funziona. Il problema NON è infrastruttura — è che ci sono solo 3 cellule che inviano segnali nel midollo.

## Pilastro 4 — Confronto (Consiglio v1)

`apps/backend-rag/backend/services/research/consiglio_orchestrator.py` esiste e copre 5/6 promesse:
- P4.2 moderator ✅
- P4.3 architectural diversity 4-LLM (Claude+Gemini+DeepSeek+NotebookLM) ✅
- P4.4 output channels ✅
- P4.5 groupthink detection ≥3/4 threshold ✅
- P4.6 devil's advocate role ✅
- P4.1 periodic deliberation ❌ — correttamente KILLED in PR #468 (Air decommissionato, nessun trigger production)

Prototipo `apps/mata-garuda/.disabled-2026-05-06/council/` archived. Mai usato.

## Pilastro 5 — Sogno (decay scheduler)

Cron `02:30` documentato in SYMBIOSIS.md, ma nessun "dream loop" implementato. Solo `silence_stale_skills()` nel passo DREAM del PulseLoop (epigenetic silencing). Niente compressione N-experiences→regole astratte. Pilastro completamente teorico.

## Pilastro 6 — Curiosità

- 56 gap topics esistono (dichiarato 2026-04-16)
- `nexus:gaps` stream ha **4059 entries** accumulate
- `CuriosityGrader`, propose-only pipeline, 40 tests — codebase live in `apps/cell/cell/cortex/curiosity_engine.py` + `apps/graph-engine/src/nuzantara_graph/curiosity/`
- "First cycle on real gaps, Zero approve/reject flow" → **mai eseguito**

Il pilastro è "infrastruttura pronta, mai acceso".

## Pilastro 7 — Misura (T0-Pro snapshot)

Da SYMBIOSIS.md §DOVE SIAMO row Pilastro 7:
- **IA (Indice Autonomia)**: 0.0192 (7d-median, 2026-05-12 calc)
- **FE (Frequenza Escalation)**: 0.0000 (6/9 giorni zero, 1 outlier 0.9598 il 2026-05-09)
- Sample: 9 snapshots ultimi 7d
- IA range: 0.0056 – 0.0231

**IA = 1.92%** significa che il 98.08% delle azioni sono esogene (prompt umano). L'organismo è ancora quasi totalmente reactivo. Numero atteso per Fase 1 Simbiosi (micromanagement).

## Gap consolidati (rispetto a SYMBIOSIS.md §DOVE SIAMO)

| Pilastro | Promessa SYMBIOSIS | Reale 2026-05-16 | Gap |
|---|---|---|---|
| 1 Riflessione | live | live ma −85% throughput post 2026-05-08 | **REGRESSIONE silente** |
| 2 Accumulazione | v1 + HGT live 2 organi | 4 cellule emittenti, 26 entries genome | Crescita lenta |
| 2 HGT | bridge | TICKET G chiuso, 25 entries cross-machine | Manca scale (3+ cellule attive) |
| 3 Condivisione | `cell:skills` + `garuda:raw` | 4 stream live | Olimpo streams + KG gap routing pendente |
| 4 Confronto | non implementato | `consiglio_orchestrator.py` live | ✅ migliorato vs §DOVE SIAMO |
| 5 Sogno | hypothesis | nessun loop | Identico |
| 6 Curiosità | v1 live | 4059 gap, mai primo ciclo Zero | Identico (mai acceso) |
| 7 Misura | live | IA=0.0192 | Identico |
| 8 Simbiosi | Fase 1 | Fase 1 | Identico |

## Tre fronti aperti — analisi costo/impatto

| Fronte | Effort | Impatto sintomatico | Reversibilità | Prerequisiti |
|---|---|---|---|---|
| **A — Cell silenti (Tier A residuo)** | 2-3h | Basso (3 cellule attive già; manca solo investigare seo-guardian 0 green + cell crash 1539 red 7d) | Alta | Nessuno |
| **B — HGT activate 3+ cells** | 4-6h | Medio (porta 25→100+ entries `cell:skills`) | Alta | A done (cellule devono emettere) |
| **C — Cross-cell reflection** | 6-10h (spec+impl) | Alto (sblocca Pilastro 1 maturazione) | Media (refactor) | Riflessione attiva ≥3 cellule |
| **D — Reflection regression (NUOVO)** | 1-2h investigare | Alto (Pilastro 1 dichiarato live ma −85%) | Alta | Nessuno |

## Raccomandazione

**Aggiungere D al menu**. Pilastro 1 è "live but degraded" da 8 giorni senza alert. Investigare `lhkpn_harvester` reflection drop 2026-05-08 prima di lanciare progetti nuovi (HGT/curiosity) che assumono Pilastro 1 sano.

Sequenza suggerita:
1. **D (1-2h)** — root cause reflection regression
2. **A (2-3h)** — chiudere residuo cell silenti (seo-guardian 0 green diagnosis)
3. **B (4-6h)** — HGT activate 3+ cellule (ora prerequisiti veri)
4. **C (6-10h)** — cross-cell reflection (Pilastro 1 evoluzione)

Salta **D** se Antonello considera la reflection regression "ok per ora" (es. lhkpn_harvester deprecato di proposito).

## Sources

1. `~/.cell-observatory/observatory.db` pulse_events table (live query)
2. `apps/mata-garuda/data/knowledge.db` genome + knowledge tables (live query)
3. `apps/organism/organism/organs_registry.yaml` 118 organi enrolled
4. `redis-cli XLEN` cell:skills cell:feedback organism:events nexus:gaps garuda:raw garuda:alerts
5. `redis-cli XINFO GROUPS organism:events` consumer lag=0
6. `launchctl list` PID + status per `com.cell.*`, `com.nuzantara.organism.*`, `com.matagaruda.*`
7. `~/Library/LaunchAgents/com.cell.organism.plist` + 3 sibling con `CELL_OBSERVATORY_EMIT=true`
8. `~/Library/Logs/skills-bridge-consumer.log` ultimo tick 2026-05-15 21:55 OK
9. `SYMBIOSIS.md` §DOVE SIAMO table (lines 200-212)
10. `research/symbiosis/2026-05-12-cell-silenti-root-cause-and-fix.md` Gap 1 doc
11. `research/symbiosis/2026-05-13-ticket-G-narrow-spec.md` TICKET G v2
12. `apps/backend-rag/backend/services/research/consiglio_orchestrator.py` Consiglio v1 source
