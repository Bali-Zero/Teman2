# Mata Garuda — Research Log

> Log cronologico di tutte le ricerche e findings

---

## 2026-04-08 — Sessione Iniziale

### Ricerche Web (12 completate)

1. **OSINT aggregation platforms** → ShadowBroker (Next.js+FastAPI), OSINT Hub (200+ tools), Knowlesys (50M msg/day)
2. **Semantic change detection** → Results mostly remote sensing. Reg monitoring: Visualping, Monity.ai, Diligent
3. **LLM news classification** → Agentic AI trend 2026, domain-specific models, MCP as standard
4. **Knowledge graph + news** → KBpedia, Neo4j GraphRAG, DeepSeek-R1/Qwen3 for KG construction
5. **OpenCTI** → STIX2 based, GraphQL, microservices. Troppo pesante per il nostro caso. Alternative: MISP, Yeti
6. **LLM news credibility** → Agentic framework per reliability assessment, BART+MNLI+FAISS pipeline
7. **Regulation monitoring** → Visualping, Monity.ai, Regology. AI summaries con redlining
8. **Exa API 2026** → Exa Deep (query expansion, JSON output, citations). 1B LinkedIn profiles, company index
9. **Search API comparison** → Brave (669ms, privacy), Exa (semantic, 81% complex retrieval), Tavily (agent-optimized, acquired by Nebius $275M)
10. **peraturan.go.id** → Open-Technology-Foundation: 5,817 docs → 541,445 segmenti FAISS. Pasal.id: 40,143 regs, 937,155 articles, MCP server pronto
11. **Neo4j + NER Python** → GraphRAG package, LLMGraphTransformer, spaCy + Transformers
12. **Tavily free tier** → 1,000 crediti/mese gratis

### Agenti Esploratori (4 completati)

1. **Scraper Explorer** → 609 fonti, 11-step pipeline, quality gate 4D, Exa 510/mo budget, Fireworks images
2. **System Explorer** → 25 app, 131 MCP tools, 10 Qdrant collections, 108K KG nodes, 7 channels
3. **OSINT Explorer** → 7 scrapers, NER 8 predicati, entity resolver 4-tier, 8 tactical queries, 17 node types
4. **Infra Explorer** → 3 Fly.io apps, PostgreSQL 106 migrations, Redis, 115 API routers, 244 services

### AI Brainstorm

1. **Gemini 2.5 Pro** → "Project Argos", 6-layer architecture, Redis Streams bus, 3-phase roadmap
   - Novel: Agentic Self-Healing, Predictive KG Analysis, /diff endpoint (sellable product)
2. **DeepSeek R1** → API key expired, no output
3. **Codex CLI** → stdin incompatible, no output

### Risorse Esterne Scoperte

| Risorsa | Valore | Integrazione |
|---------|--------|-------------|
| Pasal.id | 40K regs, 937K articles, MCP server | `claude mcp add pasal-id` — immediato |
| peraturan.go.id FAISS | 541K segmenti, 6.1GB FAISS index | Fork locale per semantic diff |
| Exa Deep | JSON structured output, citations | Upgrade endpoint nel scraper |
| Tavily free | 1000 search/mese | Complementare a Brave/Exa |
| news-watch PyPI | Indonesian news scraper package | Valutare per harvester expansion |

### Decisioni Prese

- [DECIDED] Nome: Mata Garuda
- [DECIDED] LLM: CLI only per Claude/Gemini. DeepSeek API ok. Mai API Anthropic/Google.
- [DECIDED] OSINT: blindato, one-way IN, mai frontend/clienti/team
- [DECIDED] Bus: Redis Streams
- [DECIDED] NLM: cervello analitico centrale, 6+ notebook domain

### Questioni Aperte

- [ ] CLI throughput Claude/Gemini (rate limits?)
- [ ] NLM source_add rate limits
- [ ] NLM Deep Research limiti mensili Ultra
- [ ] TG Channel BZ: esiste?
- [ ] X CRC: come riparare?
- [ ] LinkedIn page: esiste?
- [ ] Newsletter tool: Resend vs SendGrid
- [ ] WhatsApp template pre-approvazione
- [ ] xAI/Grok: keep or drop?
- [ ] Content calendar ownership

---

## 2026-04-08 — Sessione 2: Deep Research Vision

### Exa Deep Research Pro ($1.41)
- 121 pagine, 33 ricerche — Palantir 3-layer ontology, AutoAgent loop, Indonesia gov APIs
- SCOPERTA: suryast/indonesia-gov-apis (50+ endpoint gov), Putusan MA JSON API

### NLM Deep Research (4 notebook, 376 fonti)
1. Palantir Ontology: 53 fonti, 51 importate (NB 76de5123)
2. Self-Improving Agents: 56 fonti, 51 importate (NB 5af11152)
3. Indonesia Gov Data: 173 fonti (NB 0fc0de09) — SCOPERTA: indonesia-civic-stack MCP 46 tool
4. Open Source Intel: 94 fonti, 89 importate (NB e00d497a) — SCOPERTA: worldmonitor, indonesian-embedding-small

### DeepSeek API — Idee top: ontologia dinamica evolutiva, absence-of-signal detection,
Bahasa Nuance Engine, shadow economy mapping, Garuda Shortcuts via MCP

### Gemini 2.5 Pro — Idee top: HUMINT via WhatsApp bot, predicati Neo4j indonesiani,
distribution matrix single-packet multi-channel

### Risorse chiave scoperte: indonesia-civic-stack (46 tool MCP), worldmonitor (UI),
indonesian-embedding-small (HF), AutoAgent (self-improving), Semantica (decision graphs),
OpenBB (financial intel), CoreTax API, Putusan MA JSON API
