## Q1 — Cell+Genoma×Automazioni — Candidate List Finale

### Verdict
**PARTIAL** — Il ragionamento di Claude Opus round 2 è corretto nell’identificare i cluster mancanti, ma la lista finale proposta deve essere riorganizzata gerarchicamente (L0-L4.5) e filtrata dalle 7 Leggi. Le Bali Zero LaunchAgents sono **cell già mature a vari livelli**, non sub-module di war-room: vanno promosse come tali, creando però una struttura innervata.

### Reasoning
- **Bali Zero 7 LaunchAgents** vanno mappate ai Cognitive Levels reali:
  - `oracle` (L4) → cell di livello organismo, non tissue.
  - `strategos` (L3) → cell sistema (war-room come innervation, non come cell).
  - `connector` (L1) → cell tissue, già traccia di innervation.
  - Le restanti (newsletter, canva-apply, draft-generator, image-generator, dossier-compiler, topic-selector) → L1-L2, alcune possono essere subservite da `oracle`.
- **7 Leggi immutabili**: nessuna delle candidate round 1 le viola _apertamente_, ma `oracle` potrebbe sfidare “OSINT blindato” se usa fonti non verificate. Va vincolata a feed SOLO da intel-scraper + cron-agent-python OSS. Inoltre `seo-guardian` deve restare CLI-only (nessuna UI).
- **CRM 13 automazioni**: promuovere **una singola cell `crm-cell` (L1)** — non 13, perché share lo stesso runtime engine (crm_automation_engine.py). La practice_status_listener e proactive_compliance_monitor sono suoi moduli.
- **Mata-Garuda Layer 4.5**: cell separata `mata-garuda-cell` (L4.5), indipendente ma pubblich su innervation bus per meta-awareness.
- **HGT coordinator** è giustamente il pilastro Confrontation mancante. Va inserito come cell L2 con priorità Sprint 1.
- **Lista finale proposta** (18 candidate, +6 rispetto round 1):
  - L0: kg-cell, research-cell (esistenti)
  - L1: system-doctor, seo-guardian, fact-checker, tech-orchestrator, conversation-trainer, daily-ops, crm-cell, intel-scraper-cell (esistenti), connector (nuovo da Bali)
  - L2: HGT coordinator (nuovo), gap-scanner (esistente)
  - L3: strategos (nuovo da Bali), war-room-organism (esistente, ridefinito come L3 system)
  - L4: oracle (nuovo da Bali)
  - L4.5: mata-garuda-cell (nuovo)
  - Sub-cell: draft-generator, image-generator, dossier-compiler, topic-selector → aggregati sotto `oracle` come moduli, non cell autonome.

### Disagreements
- Claude Opus suggeriva di mantenere Bali Zero come sub-module di war-room. **Non condividiamo**: hanno già runtime autonomo (LaunchAgents), quindi sono cell. War-room deve rimanere sistema di orchestrazione (L3), non contenitore.
- CRM: round 1 non menzionava. Va inserita come singola cell, non sparso.
- Mata-Garuda: round 1 lo trattava come “Layer 4.5 asset indexer” ma non lo promuoveva a cell. **Va promosso subito** perché è l’unico punto di meta-awareness attivo.

### Missed cases
- **7 Leggi immutabili** non sono state verificate sulle candidate round 1. `oracle` e `strategos` potrebbero ereditare dati da Telegram (viola “Event-driven” se polling invece di eventi). Va forzato bus PG LISTEN/NOTIFY.
- **Cicatrix**: le 7 Bali LaunchAgents sono state create senza vincolo “never inherited”? Audit mostra che cicatrix è implementato, ma va verificato che nessuna cell Bali abbia ereditato scars da vecchie automazioni.
- **Cost drift**: ogni nuova cell aumenta costo KG + innervation. `oracle` L4 può diventare runaway se non limitato a 5 query/giorno.

### Risk callouts
- **Violazione Legge “Numbers first”**: le nuove cell (crm, mata-garuda) potrebbero generare metriche spurie. Necessario registro metriche univoco (war-room).
- **Orphan cells**: `newsletter` e `dossier-compiler` sono funzionalmente dead? Audit non dice se sono in produzione. Se sì, vanno dismesse o congelate.
- **Confusion L3/L4**: war-room (L3) e oracle (L4) hanno confini sfumati. Possibile conflitto di autorità su decisioni strategiche. Serve regola: oracle raccomanda, war-room decide.

### Sprint plan revisionato
Rispetto al round 1 (5 sprint, 6-8 settimane, 12 candidate):
- **Sprint 0 (1 settimana)**: mapping esatto di tutte 18 candidate su Cognitive Levels, verifica 7 Leggi, spegnimento cell morte.
- **Sprint 1 (2 settimane)**: HGT coordinator + integrazione CRM cell (confrontation pillar).
- **Sprint 2 (2 settimane)**: oracle cell + integrazione strategos (innervation bridge).
- **Sprint 3 (2 settimane)**: mata-garuda cell + meta-awareness feed.
- **Sprint 4 (1 settimana)**: sub-cell consolidation (draft-generator, etc.) sotto oracle.
- **Totale 8 settimane**, candidate da 12 a 18 ma con riuso di codice esistente (Bali LaunchAgents già live).

---

## Q2 — OpenClaw Runtime Consolidation

### Verdict
**CONCUR** con l’analisi di Claude Opus round 2: situazione reale è frammentata, servono criteri netti. Scegliamo **Opzione C (Split Clean)** con condizioni precise.

### Reasoning
- **cron-agent-python** esegue 19 strategie LIVE con stabilità provata. Il manager-based dispatch con unified_memory.py è leggero e affidabile. Non c’è motivo di migrare su OpenClaw, che ha **scheduler frozen, gateway log 21.7GB, Telegram command overload**.
- **OpenClaw** residua ha valore solo in:
  - Lobster workflows (4 file, 45 step) — usano `openclaw agent --agent coder`, non sostituibili facilmente da cron-agent-python.
  - Telegram multi-turn con memoria persistente (claude-mem).
  - **Knowledge Agents v12.1.0** (6 MCP tools) — mai sfruttati, potenziale alto per HGT coordinator.
- **mcporter 129 tools idle**: vanno disabilitati per ridurre carico, risparmiare ~200 MB RAM.
- **Criteri decisionali quantitativi** per assegnazione compito:
  - **Stato**: scheduled deterministico a esecuzione singola → cron-agent-python.
  - **Stato**: multi-step con dipendenze (tool calling, fallback, memory) → OpenClaw.
  - **Stato**: batch read-only (OSS monitor, pajak) → cron-agent-python.
  - **Criterio tool diversity**: se il compito usa ≤2 tool e non richiede fallback → cron-agent-python. Se usa ≥3 tool o ha cicli di ragionamento → OpenClaw.
  - **Criterio memoria**: se necessita di contesto persistente tra invocazioni → OpenClaw (claude-mem).
- **Applicazione alle 19 strategie**:
  - fact-checker (usa web, memory) → migrare a OpenClaw? No, perché è scheduled e usa tool limitati (fetch + ragionamento singolo). Resta in cron-agent-python.
  - tech-orchestrator (multi-tool? da audit non chiaro) → se usa ≥3 tool, va in OpenClaw. Altrimenti resta.
  - daily-ops (reporting semplice) → cron-agent-python.
  - system-doctor (system monitor) → cron-agent-python.
  - log-anomaly (batch analysis) → cron-agent-python.
  - fly-watcher (single API) → cron-agent-python.
  - intel-radar (multi-source aggregator) → potrebbe trarre vantaggio da Knowledge Agents. **Promuovere a OpenClaw** da valutare.
  - oss-monitor, pajak-monitor, imigrasi-monitor, bi-exchange-rate → batch read-only, cron-agent-python.
  - vision-doc (OCR + processing) → singolo tool, cron-agent-python.
  - tdd-pipeline (test automation) → esecuzione sequenziale, cron-agent-python.
  - client-health-monitor (polling semplice) → cron-agent-python.
  - compliance-ops (multi-step regole) → potrebbe usare Lobster? No, è batch. Resta cron-agent-python.
  - intel-feed-processor (crawl + parse) → cron-agent-python.

  **Risultato**: solo intel-radar è candidato a OpenClaw. Le altre 18 restano in cron-agent-python.

- **OpenClaw deve essere aggiornato** a v2026.4.29 per risolvere scheduler, log rotation (aggiungere policy esterna), ridurre comandi Telegram a <100 (eliminare mcporter, disabilitare bindings[] inutili).
- **cagent, claude-squad**: mantenerli dormienti. Jules/kradle/kimi dismessi.

### Disagreements
- Claude Opus round 2 sembra propendere per Opzione B (cron-agent-python vince) perché OpenClaw è trouble. **Non condividiamo**: Lobster workflows e Knowledge Agents sono asset differenzianti. Con una manutenzione mirata (aggiornamento + pulizia) OpenClaw torna stabile e copre il caso d’uso agentico che cron-agent-python non può fare.
- Opzione A (OpenClaw vince) è rischiosa per lo stato attuale. Opzione C è il compromesso pragmatico.

### Missed cases
- **Knowledge Agents**: non menzionati nel round 2 ma decisivi per scelta. Se OpenClaw resta, va sfruttato per costruire corpus queryable dalle osservazioni HGT e intel.
- **Scheduler frozen**: la causa è probabilmente il bug fix di v2026.4.29. Aggiornando si sblocca. Va testato.
- **Telegram BOT_COMMANDS_TOO_MUCH**: riducendo le command registration da 97 a 70 si risolve senza perdere funzionalità (mcporter idle non serve).
- **gateway.log**: è il rischio #1. Se scoppia il disco, tutto si ferma. Va implementata logrotate immediata (Sprint 0).

### Risk callouts
- **Manutenzione dual-runtime**: due codebase da patchare. Accettabile se i confini sono chiari.
- **OpenClaw upgrade potrebbe rompere Lobster**: testare in ambiente isolato (Fly.io staging) prima di deploy.
- **cron-agent-python sta usando sessions.db SQLite con locking?** Se sì, possibile concorrenza tra strategie simultanee. Da verificare e migrare a SQLite WAL mode.
- **mcporter 129 tools idle = risorse sprecate**: vanno disabilitati immediatamente per liberare RAM ~150MB.

### Sprint plan revisionato
Rispetto round 1 (nessuna consolidazione esplicita):
- **Sprint 0 (1 settimana)**: logrotate su OpenClaw gateway.log, upgrade a v2026.4.29, riduzione comandi Telegram a <90, disabilitazione mcporter idle.
- **Sprint 1 (1 settimana)**: test scheduler sbloccato, attivare Knowledge Agents per intel-radar. Valutare se migrare intel-radar da cron-agent-python a OpenClaw.
- **Sprint 2 (2 settimane)**: clean splitting — tutte le strategie cron-agent-python restano, Lobster resta su OpenClaw. Documentazione dei criteri decisionali.
- **Sprint 3 (1 settimana)**: rimozione definitiva di Jules/kradle/kimi, cagent in freezer.

---

## Q3 — Intel Scraper + WR2: Riconsiderazione

### Verdict
**PARTIAL** — Claude Opus round 2 identifica correttamente che WR2 è già una costellazione di 7 LaunchAgents vivi, ma la proposta di “esplicitare cell-mapping” è troppo debole. Serve **ristrutturazione gerarchica immediata**, non solo documentazione.

### Reasoning
- **WR2 non è più una pipeline**: è un organismo L3 con componenti a diversi livelli:
  - `oracle` (L4) — cell guida che detta priorità.
  - `strategos` (L3) — cell decisionale che orchestra le altre.
  - `connector` (L1) — cell di input/output.
  - Le restanti (newsletter, canva-apply, draft-generator, image-generator, dossier-compiler, topic-selector) sono **sub-cell** (moduli di oracle).
  - Fractal principle: WR2 dovrebbe essere visto come una federazione di cell minori con innervation condivisa.
- **Intel Scraper** (04_spider+03_oss+enrich+feed) è il **canale di input principale** di WR2. Deve diventare un modulo del WR2 innervation, non una cell separata. La sua funzione di “HGT publisher” è già implicita in connector + cron-agent-python intel-feed. **Non serve cell indipendente**.
- **Mata-Garuda** è Layer 4.5 e va tenuto separato da WR2. WR2 produce attivi (immagini, draft, dossier), Mata-Garuda li indicizza e crea meta-awareness. Sono due organismi distinti con innervation incrociata (Mata-Garuda legge da WR2, WR2 riceve insight da Mata-Garuda).
- **3 OpenClaw insertions** (L1 Connector, Learner M14, Trend pre-filter) del round 1 sono oggi probabilmente sovrapposte a cron-agent-python intel-feed-processor. Se il Connector LaunchAgent fa già polling e arricchimento, le insertions sono ridondanti. Vanno **verificate e dismesse** se duplicate.
- **INTEL SCRAPER MAIN PATH**: l’audit dice che drive-poll è DISABLED 2026-04-29, ma lo scraper 03:00 WITA daily è ancora attivo? Probabile che continui via cron-agent-python `intel-radar` (LIVE). Quindi la cell “intel-scraper-cell” proposta nel round 1 è **di fatto cron-agent-python intel-radar + qualche cron**. Va ridefinita come **cron-agent-python intel-radar** con mapping formale a WR2 innervation.

### Disagreements
- Claude Opus round 2 suggerisce di considerare Intel Scraper ancora come cell. **Disagree**: è un feed, non un’entità autonoma. Deve essere fusa in WR2 innervation.
- La domanda “WR2 è lavoro di mapping o redesign?” -> **redesign parziale**: mappare gerarchia, spegnere ridondanze (3 OpenClaw insertions), mantenere le automazioni esistenti (non toccare LaunchAgents).
- Mata-Garuda sub-cell di WR2? **No**, separato come da audit L4.5.

### Missed cases
- **Scars cicatrix**: WR2 ha ereditato scars da vecchia pipeline? Non menzionato. Se sì, vanno isolate.
- **Cron intel-feed-processor**: eseguito da cron-agent-python, non da WR2. Questo crea **dipendenza nascosta**. Va esplicitato nell’innervation diagram.
- **WR2 ha già un proprio event bus?** I 7 LaunchAgents comunicano tra loro? Forse via LaunchAgent IPC o file system. Non sappiamo. Se usano file system, violano “Event-driven” (7 Leggi). Da verificare.

### Risk callouts
- **Duplicazione OpenClaw-WR2**: se le 3 insertions sono attive ma non dismesse, si generano output duplicati (dossier, draft). Possibile degrado qualità.
- **WR2 oracle L4 influenza decisioni war-room**: se oracle prende decisioni autonomamente senza passare da war-room, si crea SPOF decisionale.
- **Intel Scraper come modulo di WR2**: se intel-radar fallisce, WR2 rimane cieco. Va implementato failover (backup via cron-agent-python OSS).

### Sprint plan revisionato
Rispetto round 1 (sprint 2-3 per WR2 + intel scraper):
- **Sprint 0 (1 settimana)**: audit completo WR2 — determinare comunicazione tra LaunchAgents, verificare 7 Leggi, rimuovere 3 OpenClaw insertions se duplicate.
- **Sprint 1 (1 settimana)**: rinominare intel-scraper-cell → modulo WR2 innervation. Aggiornare war-room config per includere WR2 come L3 federazione.
- **Sprint 2 (2 settimane)**: integrare innervation tra WR2 e cron-agent-python intel-radar (pub/sub su PG NOTIFY). Disabilitare il cron 03:00 WITA indipendente, farlo gestire da WR2 schedule.
- **Sprint 3 (1 settimana)**: test end-to-end: Mata-Garuda indicizza output WR2, war-room consulta oracle per decisioni.

---DEEPSEEK META---
reasoning_tokens: 1424
completion_tokens: 5501
prompt_tokens: 3970
model_used: deepseek-v4-flash
