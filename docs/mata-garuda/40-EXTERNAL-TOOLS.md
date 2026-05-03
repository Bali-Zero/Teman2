# Mata Garuda — External Tools & Resources

> Data: 2026-04-08 | Aggiornato continuamente

## Tool Scoperti & Da Integrare

### Tier 1 — Integrazione Immediata (gia pronti)

| Tool | Cos'e | Come integrare | Costo |
|------|-------|----------------|-------|
| **Pasal.id MCP** | 40,143 regolamenti + 937,155 articoli indonesiani strutturati | `claude mcp add pasal-id https://pasal-mcp-server-production.up.railway.app/mcp` | Free |
| **Tavily API** | Search API ottimizzata per AI agents, structured output | Free tier 1,000 ricerche/mese | Free |
| **Brave Search MCP** | Gia configurato, index indipendente, 669ms latency | Gia in stack | Free |
| **suryast/indonesia-gov-apis** | Catalogo GitHub endpoint governativi indonesiani | Fork come reference per nuovi scrapers | Free |

### Tier 2 — Integrazione Pianificata (richiede lavoro)

| Tool | Cos'e | Come integrare | Costo |
|------|-------|----------------|-------|
| **peraturan.go.id FAISS** | 541,445 segmenti legali, FAISS index 6.1GB | Fork repo, deploy locale per semantic diff | Free |
| **Exa Deep** | Query expansion, JSON structured, field-level citations | Upgrade endpoint nel scraper | Nel budget Exa |
| **Semantica** | Context graphs, decision intelligence, provenance tracking | `pip install semantica` — layer accountability su LangGraph | Free (open source) |
| **OpenBB** | Bloomberg Terminal open source, financial data, Python | Integrare per market intelligence Bali property/economy | Free |
| **neo4j-graphrag-python** | Reference GraphRAG: Neo4j + Qdrant retriever pattern | Pattern per KG Linker Agent | Free |

### Tier 3 — Da Valutare

| Tool | Cos'e | Note |
|------|-------|------|
| **Fivecast ONYX** | OSINT platform con entity resolution multilingue | Enterprise pricing, ma pattern da studiare |
| **Recorded Future Intelligence Graph** | Risk scoring automatico, 1M+ fonti | Pattern da replicare localmente |
| **AutoAgent (Meta)** | Self-improving agent harness optimization | Open source, integrabile come meta-agent |
| **HyperAgents (Meta)** | Self-modifying AI framework | Recente, da valutare |
| **indonesian-ner-spacy** | Fine-tuned spaCy NER per indonesiano | Alternative al nostro NER Ollama |

## Pattern Architetturali da "Rubare"

### Da Palantir Gotham — L'Ontologia a 3 Layer [CONFIRMED by Exa Research]

```
SEMANTIC LAYER (cosa sono le cose)
  → Object Types: Person, Organization, Location, Event, Asset, Document, Regulation
  → Property definitions per type
  → Link Types: WORKS_AT, OWNS, FAMILY_OF, ATTENDED, WON_CONTRACT...
  → NEL NOSTRO CASO: Neo4j schema (gia 17 node types!)

KINETIC LAYER (come i dati grezzi diventano oggetti)
  → ETL pipelines che mappano raw data → ontology objects
  → Lineage: ogni dato tracciato fino alla fonte originale
  → NEL NOSTRO CASO: Workers Layer 2 + NER + Entity Resolution

DYNAMIC LAYER (logica di business sugli oggetti)
  → Actions/Functions: alert rules, lifecycle states, workflows
  → Authorization per-attribute
  → NEL NOSTRO CASO: Analyst Agents + Quality Gate + Distribution Rules
```

### Da Recorded Future — Intelligence Graph + Risk Scoring

```
- 1M+ fonti scrapate continuamente
- Machine learning per risk scoring in real-time
- Score pesato: novelty, prevalence, severity
- NEL NOSTRO CASO: quality_gate.yaml gia ha 4 dimensioni di scoring
  Aggiungere: novelty (e' la prima volta?), prevalence (quante fonti?),
  severity (impatto su clienti), velocity (quanto velocemente si diffonde)
```

### Da Bloomberg Terminal — News Classification at Scale

```
- 220,000 entita tracked
- 10,000 topic
- 660,000 persone
- Sentiment scoring per articolo
- NEL NOSTRO CASO: partire con le entita del KG (108K)
  + sentiment via Ollama locale (gemma4:26b)
  + topic classification gia nel quality gate
```

### Da AutoAgent — Self-Improving Loop

```
Meta-Agent:
  1. Legge le performance correnti (precision, recall, false positives)
  2. Propone modifiche (prompt, tool, config)
  3. Testa in sandbox (containerizzato)
  4. Misura risultato
  5. Se migliore → adotta, se peggiore → rollback
  6. Repeat

NEL NOSTRO CASO:
  - Meta-Agent che ottimizza:
    a) prompt di classificazione (quality gate keywords)
    b) soglie di scoring
    c) selezione fonti (reliability calibration)
    d) prompt di NER (predicati)
  - Benchmark: feedback Zero (thumbs up/down su briefing via TG)
  - Cadenza: settimanale (domenica notte)
```

### Da Babel Street — Entity Resolution Multilingue

```
- Da un nome o email → profilo multidimensionale
- Risoluzione identita online + offline
- 200+ lingue
- NEL NOSTRO CASO: entity resolver gia a 4 tier (NIP, jabatan+kantor,
  fuzzy name, new entity). Aggiungere: cross-reference con LHKPN,
  social media handles, phone numbers (se disponibili da fonti pubbliche)
```

## Indonesia-Specific Data Sources Scoperte

### Fonti Governative Automatizzabili

| Fonte | URL | Tipo dati | Metodo accesso |
|-------|-----|-----------|----------------|
| Peraturan.go.id | peraturan.go.id | Regolamenti centrali/regionali | HTML scrape + FAISS fork |
| Putusan MA | putusan.mahkamahagung.go.id | Decisioni Corte Suprema | **JSON API pubblica** |
| LHKPN KPK | elhkpn.kpk.go.id | Dichiarazioni asset ufficiali | Browser + reCAPTCHA v3 (gia implementato) |
| LPSE | lpse.kemenkumham.go.id | Tender procurement | httpx + browser fallback (gia implementato) |
| AHU | ahu.ahu.go.id | Registrazione societa | CAPTCHA, scraper esistente |
| OSS | oss.go.id | Licenze business | Form-based, da costruire |
| Data.go.id (Satu Data) | data.go.id | Dataset statistici nazionali | API pubblica |
| BPS Bali | bali.bps.go.id | Statistiche economia Bali | HTML |
| Pasal.id | pasal.id | 40K regs strutturati | **MCP server pronto** |
| imigrasi.go.id | imigrasi.go.id | Portale immigrazione | HTML, no API |
| pajak.go.id | pajak.go.id | Portale fiscale | HTML, PDF reports |
| ATR/BPN | atrbpn.go.id | Registro fondiario | Limitato, richiede credenziali |

### Catalogo Reference

- **suryast/indonesia-gov-apis** (GitHub): catalogo community endpoint governativi con pattern di scraping
- **Open-Technology-Foundation/peraturan.go.id**: 5,817 docs procesati con FAISS
- **ilhamfp/pasal**: MCP server per 40K regolamenti

## [OPEN] Da valutare

- OpenBB: quanto utile per property/economy intelligence a Bali?
- Satellite imagery API (Google Earth Engine? Planet?): per property valuation
- Social listening beyond X: Instagram API? TikTok? Reddit Indonesia?
- Court filing monitor: putusan MA ha API JSON — integrare per legal intelligence
- Semantica vs LangGraph puro: serve il layer di accountability?
