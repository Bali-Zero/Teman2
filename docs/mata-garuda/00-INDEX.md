# MATA GARUDA — Intelligence Super Hub

> "Occhi dell'Aquila" — Centro unificato di intelligence per Nuzantara/Bali Zero

**Stato:** In design (2026-04-08)
**Owner:** Zero (esclusivo)

---

## Indice Documenti

### Architettura
- [01-VISION.md](01-VISION.md) — Visione, problema, soluzione, principi
- [02-ARCHITECTURE.md](02-ARCHITECTURE.md) — 5 layer, data flow, component map
- [03-LLM-POLICY.md](03-LLM-POLICY.md) — CLI only, modelli, routing, costi
- [04-SECURITY-FIREWALL.md](04-SECURITY-FIREWALL.md) — OSINT blindato, stream separation, access control

### Sistemi
- 10-HARVESTER.md _(not yet written)_ — Fonti, scrapers, API search, ingestion
- [11-NLM-BRAIN.md](11-NLM-BRAIN.md) — NotebookLM come cervello analitico, notebook domain, deep research
- 12-COGNITIVE-WORKERS.md _(not yet written)_ — Dedup, classify, score, NER, embed, diff
- 13-KNOWLEDGE-GRAPH.md _(not yet written)_ — KG linker, Neo4j, Qdrant, PostgreSQL
- 14-ANALYST-AGENTS.md _(not yet written)_ — Briefing, alert, dossier, anomaly, digest

### Target & Distribuzione
- [20-TARGETS.md](20-TARGETS.md) — Chi riceve cosa, intelligence products, consumatori
- [21-CHANNEL-STRATEGY.md](21-CHANNEL-STRATEGY.md) — 7 canali, agent per canale, format, lingua
- 22-OSINT-ENRICHMENT.md _(not yet written)_ — One-way feed verso OSINT Nexus (blindato)

### Autonomia
- [30-AUTONOMY-LEVELS.md](30-AUTONOMY-LEVELS.md) — L1-L4, decisioni autonome, escalation
- 31-SELF-EXPANSION.md _(not yet written)_ — Auto-discovery fonti, NB creation, source health

### Risorse Esterne
- [40-EXTERNAL-TOOLS.md](40-EXTERNAL-TOOLS.md) — Pasal.id, peraturan.go.id FAISS, Tavily, Exa Deep
- [40a-CIVIC-STACK-EVAL.md](40a-CIVIC-STACK-EVAL.md) — indonesia-civic-stack: 46 tool testati, valutati, strategia integrazione
- [40b-AGENT-TAXONOMY.md](40b-AGENT-TAXONOMY.md) — agent-taxonomy (Lamarckian framework) per meta-agent Mata Garuda
- [40c-AUTOAGENT-EVAL.md](40c-AUTOAGENT-EVAL.md) — HKUDS/AutoAgent evaluation: ispirazione (4 pattern), no fork
- [40d-AUTOAGENT-PATTERNS.md](40d-AUTOAGENT-PATTERNS.md) — 4 pattern AutoAgent estratti con codice + adattamento Mata Garuda CLI-only
- [41-RESEARCH-LOG.md](41-RESEARCH-LOG.md) — Log di tutte le ricerche web, AI brainstorm, findings

### Build
- [50-BUILD-ORDER.md](50-BUILD-ORDER.md) — 4 sprint per meta-agent runtime + POC Regulation Watcher
- [51-EXISTING-INVENTORY.md](51-EXISTING-INVENTORY.md) — Cosa esiste gia e va solo connesso
- [poc/](poc/) — Reference code Sprint 1: registry.py + types.py + dummy_agent.py (validato 2026-04-09)

### POC
- [poc/README.md](poc/README.md) — Sprint 1 reference code (registry, types, dummy_agent, GENOME) — validato 2026-04-09

### Sessioni di approfondimento
- [90-SESSIONS.md](90-SESSIONS.md) — Log delle sessioni di brainstorming con dettagli micro

---

## Regole di questo documento

1. Ogni micro-punto approfondito viene salvato nel file appropriato
2. Se un micro-punto merita un file dedicato, si crea (es. `10a-HARVESTER-GOVSITES.md`)
3. L'indice viene aggiornato ad ogni aggiunta
4. Mai cancellare — solo aggiornare con data e nota
5. Decisioni prese: marcate con `[DECIDED 2026-04-XX]`
6. Questioni aperte: marcate con `[OPEN]`
