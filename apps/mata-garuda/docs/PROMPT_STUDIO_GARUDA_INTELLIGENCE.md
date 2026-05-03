# Prompt di Studio — Plasmare Mata Garuda come Intelligence Engine

> Per la prossima sessione. Leggi tutto, analizza, poi proponi.

## Contesto

Mata Garuda ha il cuore biologico (cell-core PulseLoop, 212 test, cron attivo). Ma il cuore batte a vuoto — raccoglie regolamenti una volta al giorno e basta. L'intelligenza vera (L2-L5) non esiste ancora.

## Cosa leggere PRIMA di proporre qualsiasi cosa

### Architettura e visione (IN QUEST'ORDINE)
1. `docs/mata-garuda/01-VISION.md` — Filosofia fondante (Palantir, CIA CATALYST, Bloomberg)
2. `docs/mata-garuda/02-ARCHITECTURE.md` — I 5 layer + meta-agent
3. `docs/mata-garuda/20-TARGETS.md` — 6 profili consumatore (Zero, clienti, Zantara AI, War Room, Team, OSINT)
4. `docs/mata-garuda/21-CHANNEL-STRATEGY.md` — 8 canali distribuzione + livelli autonomia
5. `docs/mata-garuda/30-AUTONOMY-LEVELS.md` — L1-L4 decision framework
6. `docs/mata-garuda/51-EXISTING-INVENTORY.md` — 80-90% dei componenti esiste gia'
7. `SYMBIOSIS.md` — I pilastri dell'organismo (riflessione, accumulazione, condivisione, confronto, sogno, curiosita', misura, simbiosi)

### Infrastruttura che esiste GIA'
8. `apps/bali-intel-scraper/` — 609 sorgenti configurate, cron 03:00 WITA
9. `apps/backend-rag/backend/services/naga/` — Naga research engine (4 search agent, quality pipeline, report writer)
10. `apps/mata-garuda/docs/STRATEGIC_REPORT_2026-04-09.md` — Audit completo: agenti esistenti, sorgenti tier, analisi 7 layer
11. `apps/mata-garuda/mata_garuda/cell/` — cell-core wrap gia' operativo (sensors, actor, thinker, memory bridge, runner)
12. `apps/mata-garuda/mata_garuda/agents/` — 12 agenti registrati (solo regulation_watcher operativo)
13. Redis streams: `garuda:raw`, `garuda:enriched`, `garuda:alerts`, `garuda:digest`, `nexus:gaps`
14. Neo4j locale: 1406 nodi, 2121 archi, gap detector con 8 query Cypher

### Canali di produzione che esistono GIA'
15. Telegram bot (`@Balizerobot`) — live, chat privato Zero + broadcast
16. Blog balizero.com — 2272 pagine, auto-deploy Vercel
17. WhatsApp — live (Gemini 2.5 Flash + RAG)
18. Instagram — live
19. Newsletter — infrastruttura Zoho pronta
20. Zantara RAG — 93K vettori, 10 collection, 108K nodi KG

## Domande da rispondere

### A. Il prodotto minimo
Qual e' il PRIMO prodotto di intelligence che genera valore domani mattina? Non l'architettura completa — il singolo output che cambia la giornata di Zero.

### B. Il flusso dati
Traccia il percorso di UN dato (es. nuova regolazione immigrazione) dalla sorgente al consumatore finale. Quanti passaggi? Quali esistono, quali mancano? Dove si blocca oggi?

### C. La canalizzazione
Garuda deve alimentare TUTTI i canali di produzione (Telegram, WhatsApp, blog, newsletter, Zantara RAG). Come? Un singolo enriched stream che ogni canale consuma? O agent dedicati per canale? Qual e' il pattern giusto per non duplicare lavoro?

### D. L'LLM routing
4 modelli disponibili localmente (gemma4:26b, qwen3.5:9b, deepseek-r1:32b, qwen2.5vl:7b) + Claude CLI + Gemini CLI. Chi fa cosa? Classificazione vs arricchimento vs analisi vs scrittura. Mapping preciso.

### E. Il ciclo quotidiano
Disegna la giornata tipo di Garuda:
- 03:00 bali-intel-scraper raccoglie
- 06:00 regulation watcher scrapa
- 07:00 gap detector analizza Neo4j
- 07:30 ??? — qui cosa succede? Chi processa? Chi analizza? Chi distribuisce?
- 08:00 Zero apre Telegram e trova... cosa?

### F. Il piano a 4 settimane
- Settimana 1: ???
- Settimana 2: ???
- Settimana 3: ???
- Settimana 4: ???

## Vincoli non negoziabili
- CLI-only per LLM (subprocess, mai SDK import)
- OSINT blindato (mai cloud, mai frontend, mai team)
- Zero nuove dipendenze Python oltre pydantic
- Ogni agente ha GENOME.md + Lamarckian feedback
- cell-core PulseLoop come orchestratore
- Locale Pro first (48GB M4 Pro) — disconnessione e' stato naturale

## Output atteso
Non un documento di 500 righe. Un piano chirurgico:
1. Il primo prodotto (daily briefing? regulation alert? altro?)
2. I 3-5 file da creare
3. Il cron da aggiungere
4. Il risultato che Zero vede su Telegram alle 08:00

Poi iteriamo.
