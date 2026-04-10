# Mata Garuda — Session Handover 2026-04-10

> Questa sessione è durata ~6 ore. Leggere TUTTO prima di agire.

## COSA È STATO FATTO

### 1. Cron Regulation Watcher (OPERATIVO)
- LaunchAgent `com.matagaruda.watcher.daily` — 06:00 WITA daily
- Bridge TCC-safe: `~/scripts/mata-garuda-watcher.sh`
- Plist: `~/Library/LaunchAgents/com.matagaruda.watcher.daily.plist`
- Testato: 10 regolazioni harvested, exit=0
- Log: `~/logs/mata-garuda-watcher.log`

### 2. Mata Garuda integrato nel monorepo
- Path: `apps/mata-garuda/` (38 file, 105 test pass)
- Vecchio repo standalone `~/Desktop/mata-garuda/` CANCELLATO
- Cron bridge aggiornato a nuovo path

### 3. OSINT Nexus scrubbed dal monorepo
- `apps/osint-nexus/` e `apps/osint-nexus-ui/` RIMOSSI dal tracking git
- Zero menzioni di "OSINT Nexus" in tutta la codebase (verificato 3 volte)
- Codice spostato in `~/Desktop/OSINT-Nexus/` (segreto, no repo)
- Docs OSINT copiati in `~/Desktop/OSINT-Nexus/docs/from-nuzantara/`

### 4. Bridge Garuda → Nexus (OPERATIVO)
- **Schema condiviso:** `~/Desktop/OSINT-Nexus/bridge/schema.py` (5 msg types: regulation, personnel, tender, lhkpn, entity + GapRequest)
- **Consumer:** `~/Desktop/OSINT-Nexus/bridge/consumer.py` — garuda:raw → Neo4j MERGE
- **Testato:** 10 Document nodes creati nel grafo Neo4j (backfill OK)
- **Audit:** `~/Desktop/OSINT-Nexus/data/bridge_changelog.jsonl`
- **Consumer LaunchAgent semplice:** `~/Library/LaunchAgents/com.garuda.consumer.daily.plist` (06:15 WITA) — questo è il consumer JSONL vecchio, va aggiornato al bridge Neo4j
- **Neo4j:** Docker su Pro, porta 17687 (Bolt) / 17474 (Browser), auth: neo4j/osint-nexus-2026, 1406 nodi

### 5. Piano Sprint 5 "Self-Evolving Organism" v2
- Path: `apps/mata-garuda/docs/superpowers/plans/2026-04-09-self-evolving-organism.md`
- Reviewato da Gemini 2.5 Pro, 7/9 critiche accettate
- 7 task, ~25 test, zero nuove dipendenze
- PRONTO per implementazione (non ancora iniziata)

### 6. Ricerca profonda completata
- **Self-evolving agents:** NLM notebook `305f5f2e` (57 fonti), Exa deep research
- **Palantir/intelligence architecture:** NLM notebook `d97ff70b` (44 fonti), Exa deep research
- **Brainstorm multi-AI:** DeepSeek R1 32B (locale), Gemini (rate limited), Claude Sonnet
- Report: `~/Desktop/OSINT-Nexus/docs/SYMBIOSIS_ARCHITECTURE.md`
- Report: `apps/mata-garuda/docs/SELF_EVOLVING_AGENT_RESEARCH.md`
- Report: `apps/mata-garuda/docs/STRATEGIC_REPORT_2026-04-09.md`

---

## COSA MANCA (in ordine di priorità)

### IMMEDIATO — Completare il bridge

1. **Aggiornare il LaunchAgent consumer** — il `com.garuda.consumer.daily.plist` oggi chiama il vecchio `scripts/garuda_consumer.py` (JSONL flat). Va aggiornato per chiamare `bridge/consumer.py` (Neo4j MERGE). File bridge script: `~/scripts/garuda-consumer.sh` — aggiornare per usare il venv Nexus e il bridge module.

2. **Gap detector v1** — Script Python in `~/Desktop/OSINT-Nexus/bridge/gap_detector.py` che:
   - Esegue 5-10 query Cypher predefinite (LHKPN mancante, attributi stale, relazioni mancanti)
   - Pubblica risultati su Redis stream `nexus:gaps`
   - Cron: LaunchAgent alle 07:00 e 18:00 WITA

3. **Task consumer in MG** — Un consumer in `apps/mata-garuda/` che legge `nexus:gaps` e dispatcha agenti. MG non sa che i task vengono da Nexus — vede solo uno stream Redis con richieste generiche.

### SPRINT 5 — Self-Evolving Organism

Piano completo in `apps/mata-garuda/docs/superpowers/plans/2026-04-09-self-evolving-organism.md`.

7 task:
1. RunOutcome model (types.py)
2. SQLite Knowledge Base (unified — facts, insights, skills)
3. Reflection Engine (JSON-based, post-run, success AND failure)
4. Knowledge tools per agenti (kb_search, kb_store, kb_get_skill)
5. Hook reflection nel Lamarckian + prompt injection con token budget
6. Integration test end-to-end
7. Docs + verification

Approccio raccomandato: subagent-driven development.

### DOPO SPRINT 5 — Espansione harvester

Nuovi agenti da creare (da Strategic Report):
1. **Pasal.id Harvester** — API REST JSON, 40K regolamenti, nessun auth
2. **JDIH Perpusnas Harvester** — API REST JSON, token auth
3. **DDTCNews Scraper** — news fiscale quotidiana
4. **JDIH Bali Scraper** — Perda provinciali

---

## STATO INFRASTRUTTURA

| Componente | Stato | Path/Port |
|---|---|---|
| Redis | ✅ Running su Pro | localhost:6379 |
| Neo4j | ✅ Docker su Pro | Bolt 17687, Browser 17474 |
| garuda:raw stream | 10 entries | Redis XLEN = 10 |
| Mata Garuda venv | .venv (Python 3.14) | `apps/mata-garuda/.venv/` |
| Nexus venv | .venv (Python 3.14 + neo4j 6.1) | `~/Desktop/OSINT-Nexus/.venv/` |
| Docker Desktop | Running su Pro | Engine v4.68.0 |

## CRON ATTIVI (LaunchAgents)

| Plist | Schedule | Cosa fa |
|---|---|---|
| `com.matagaruda.watcher.daily` | 06:00 WITA | Scrapa peraturan.go.id → garuda:raw |
| `com.garuda.consumer.daily` | 06:15 WITA | Legge garuda:raw → JSONL (DA AGGIORNARE a bridge Neo4j) |

## NEO4J GRAPH STATO

```
Nodi: 1406
  Property: 565, Vehicle: 329, Organization: 211, Official: 170,
  BankAccount: 107, Person: 11, Document: 10, Kanim_Office: 3

Relazioni: 2121
  OWNS: 2028, WORKS_AT: 69, FAMILY_OF: 8, MET_WITH: 8,
  SUPERVISES: 3, PART_OF: 3, ALUMNI: 1, PARENT_OF: 1

Constraints: 16 UNIQUENESS
Indexes: fulltext su Person/Official name + Organization name
```

## FILE CHIAVE (leggere prima di toccare)

| File | Dove | Cosa |
|---|---|---|
| `apps/mata-garuda/CLAUDE.md` | Monorepo | Vincoli inviolabili MG |
| `apps/mata-garuda/docs/superpowers/plans/2026-04-09-self-evolving-organism.md` | Monorepo | Piano Sprint 5 v2 |
| `apps/mata-garuda/docs/SELF_EVOLVING_AGENT_RESEARCH.md` | Monorepo | Ricerca 6 pattern (Reflexion, Voyager, DGM, EvoPrompt) |
| `apps/mata-garuda/docs/STRATEGIC_REPORT_2026-04-09.md` | Monorepo | Report strategico pipeline 7 layer |
| `~/Desktop/OSINT-Nexus/docs/SYMBIOSIS_ARCHITECTURE.md` | Nexus (segreto) | Architettura simbiosi MG↔Nexus |
| `~/Desktop/OSINT-Nexus/docs/GARUDA_BRIDGE_PLAN.md` | Nexus (segreto) | Piano del bridge consumer |
| `~/Desktop/OSINT-Nexus/bridge/schema.py` | Nexus (segreto) | Schema condiviso |
| `~/Desktop/OSINT-Nexus/bridge/consumer.py` | Nexus (segreto) | Bridge consumer garuda:raw → Neo4j |

## VINCOLI CRITICI (non dimenticare MAI)

1. **OSINT Nexus non esiste nel monorepo** — zero menzioni, zero tracce
2. **LLM CLI-only** — subprocess claude/gemini, MAI API HTTP
3. **OSINT blindato** — dati Nexus mai su cloud/frontend/team
4. **Lamarckian** — ogni agente ha GENOME.md, feedback loop
5. **Il consumer bridge NON è nel monorepo** — vive solo in ~/Desktop/OSINT-Nexus/
6. **Neo4j Docker** — deve essere avviato manualmente (Docker Desktop su Pro)

## DECISIONI PRESE IN QUESTA SESSIONE

1. **Mata Garuda nel monorepo** come `apps/mata-garuda/` — codice pubblico, dati gitignored
2. **OSINT Nexus solo locale** — `~/Desktop/OSINT-Nexus/`, no repo GitHub
3. **Redis su Pro** — tutto locale, niente rete
4. **Bridge consumer: Neo4j MERGE** — non più JSONL flat
5. **Schema v1: 6 entity types** — Person, Organization, Role, LHKPNReport, Procurement, Document
6. **Gap detector: 2x/giorno** — 07:00 e 18:00 WITA
7. **Audit trail: JSONL** — `bridge_changelog.jsonl`
8. **LLM nel bridge: CLI only, non nel loop automatico v1**
9. **skills.py eliminato** — tutto in SQLite KB (critica Gemini accettata)
10. **Reflection JSON** — non regex (critica Gemini accettata)
