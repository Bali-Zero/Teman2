# Mata Garuda — Inventario Esistente

> Cosa esiste gia e va solo connesso (non ricostruito)

## Harvesting (Layer 1) — 80% esistente

| Componente | Dove | Stato | Cosa manca |
|-----------|------|-------|------------|
| Unified Scraper (609 fonti) | apps/bali-intel-scraper/scripts/unified_scraper.py | LIVE | Output → Redis invece di diretto |
| Exa Scraper (17 queries) | apps/bali-intel-scraper/scripts/exa_scraper.py | LIVE | Upgrade a Exa Deep |
| NLM Research | apps/war-room/agents/11_nlm_researcher.py | LIVE | Generalizzare per tutti i topic |
| Exa War Room | apps/war-room/agents/09_exa_researcher.py | LIVE | Riutilizzare per harvesting generico |
| xAI Grok | apps/war-room/agents/10_xai_researcher.py | LIVE | Keep per X signals |
| OSINT Scrapers (7) | apps/osint-nexus/osint_nexus/scrapers/ | LIVE | Collegare output al bus |
| Source config | config/unified_sources.json (609 fonti) | LIVE | Aggiungere reliability_score field |
| Categories | config/categories.json (12 cat, CSS selectors) | LIVE | Espandere con nuove categorie |
| Brave Search MCP | ~/.mcp.json | LIVE | Usare come harvester |
| Tavily | backend env | CONFIGURATO | Attivare free tier |

## Processing (Layer 2) — 60% esistente

| Componente | Dove | Stato | Cosa manca |
|-----------|------|-------|------------|
| Quality Gate 4D | config/quality_gate.yaml | LIVE | Gia ha weights, thresholds, tiers |
| Source Tiers T1/T2/T3 | config/quality_gate.yaml | LIVE | 22 domini mappati, default T3 |
| Rule-based Dedup | scripts/rule_based_deduplicator.py | LIVE | Aggiungere semantic dedup |
| Qwen Filter | pipeline step 2.5 | LIVE | Funziona |
| Verification | pipeline step 2.7 | LIVE | Cross-check T1 + KB |
| Clustering | pipeline step 2.8 | LIVE | Semantic clustering per dossier |
| NLM Context | pipeline step 2.9 | LIVE | Query NB core + temp NB |
| Enrichment (Claude) | scripts/claude_cli_enricher.py | LIVE | Gia usa Claude CLI! |
| SEO (Gemini) | scripts/gemini_seo_optimizer.py | LIVE | Gia usa Gemini! |
| NER Extractor | apps/osint-nexus/osint_nexus/ner/extractor.py | LIVE | Indonesiano, 8 predicati |
| Entity Resolver | apps/osint-nexus/osint_nexus/resolver/ | LIVE | 4-tier fuzzy, rapidfuzz |
| Intel Classification | backend/services/intel/intel_classification.py | LIVE | Sul backend Fly.io |
| Intel Approval | backend/services/intel/intel_approval.py | LIVE | Telegram-based |

## Knowledge Graph (Layer 3) — 70% esistente

| Componente | Dove | Stato | Cosa manca |
|-----------|------|-------|------------|
| Neo4j schema | apps/osint-nexus/osint_nexus/graph/schema.py | LIVE | 17 node types, 15+ constraints |
| Neo4j loader | apps/osint-nexus/osint_nexus/graph/loader.py | LIVE | Scrape → graph |
| Neo4j queries | apps/osint-nexus/osint_nexus/graph/queries.py | LIVE | 8 tactical queries |
| Qdrant collections | nuzantara-qdrant Fly.io | LIVE | 10 collections, 93K docs |
| PostgreSQL KG | nuzantara-postgres Fly.io | LIVE | 108K nodes, 242K edges |
| Entity linking | backend/services/knowledge_graph/entity_linking.py | LIVE | Maps entities → KG |
| Community detection | backend/services/knowledge_graph/community_detection.py | LIVE | Cluster analysis |
| KG builder | backend/services/knowledge_graph/kg_incremental_builder.py | LIVE | Streaming ingestion |
| KG quality filter | backend/services/knowledge_graph/kg_quality_filter.py | LIVE | Validation |
| Graph Engine | apps/graph-engine/ | SCAFFOLD | Traversal, resolution |
| NLM Bridge | apps/nlm-bridge/ | LIVE | HTTP bridge port 18790 |

## Analysis (Layer 4) — 20% esistente

| Componente | Dove | Stato | Cosa manca |
|-----------|------|-------|------------|
| LangGraph orchestrator | backend/services/rag/kg_langgraph_orchestrator.py | LIVE | Per RAG, non per briefing |
| Dossier generator | apps/osint-nexus/osint_nexus/dossier/generator.py | LIVE | Solo OSINT, non news |
| Topic selector | apps/war-room/agents/00_topic_selector.py | LIVE | Multi-source, DeepSeek synthesis |
| Daily Briefing Agent | - | DA COSTRUIRE | Core intelligence product |
| Regulation Alert Agent | - | DA COSTRUIRE | Semantic diff + impact |
| Contradiction Agent | - | DA COSTRUIRE | KB vs news check |
| Weekly Digest Agent | - | DA COSTRUIRE | Sintesi settimanale |

## Distribution (Layer 5) — 40% esistente

| Componente | Dove | Stato | Cosa manca |
|-----------|------|-------|------------|
| Telegram bot | OpenClaw + @Balizerobot | LIVE | Aggiungere formati briefing |
| Telegram approval | scripts/telegram_approval.py | LIVE | Review queue |
| Blog publish | scripts/publish_articles.py | LIVE | POST a nuzantara-rag |
| Image generation | Fireworks Flux.1 + Pollinations | LIVE | Cover articles |
| Canva automation | apps/war-room/agents/06_canva_builder.py | LIVE | Template carousel |
| War Room delivery | agents/07_delivery.sh | LIVE | TG: Zero + Damar |
| WhatsApp channel | backend/channels/whatsapp | LIVE | Gemini 3 Flash + RAG |
| Email digest | - | DA COSTRUIRE | Newsletter tool needed |
| X/Twitter posting | - | BROKEN (CRC) | Da riparare |
| LinkedIn posting | - | DA COSTRUIRE | API integration |
| MCP garuda.query() | - | DA COSTRUIRE | Tool per AI assistants |

## Monitoring — 90% esistente

| Componente | Dove | Stato |
|-----------|------|-------|
| Prometheus | scraper monitoring | LIVE |
| Grafana dashboards | config/grafana/ | LIVE |
| Telegram alerts | scripts/fly-health-check.sh | LIVE |
| RAG canary | scripts/rag_canary.py | LIVE |
| Sentinel | scraper sentinel bridge | LIVE |
| MOS logging | ~/.claude/scripts/mem | LIVE |

## Sintesi

| Layer | % Esistente | Effort Stimato |
|-------|-------------|----------------|
| Harvesting | 80% | 3-4 giorni (connettere, non costruire) |
| Processing | 60% | 1 settimana (nuovi workers, Redis integration) |
| Knowledge | 70% | 1 settimana (KG linker, NLM feeder) |
| Analysis | 20% | 2 settimane (4 agent nuovi da costruire) |
| Distribution | 40% | 1 settimana (nuovi canali, formati) |
| **Totale** | **~55%** | **~4-5 settimane** |
