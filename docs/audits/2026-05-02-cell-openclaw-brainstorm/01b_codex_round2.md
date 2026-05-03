## Q1 — Cell+genoma x automazioni: lista candidate finale

### Verdict
PARTIAL con il reasoning di Claude Opus round 2

### Reasoning (max 400 parole)
Round 1 non era sbagliato sul principio: promuovere selettivamente, non trasformare ogni cron in cell. Era incompleto per inventario e livelli cognitivi. Il salto 130 -> ~300+ automazioni non implica 300 cell: implica un filtro di maturita piu duro basato su 7 Leggi, eventi, memoria, decisioni e HGT.

Lista finale: 14 promotion unit. Mantengo le 12 round 1, con vincoli: `gap-scanner-cell` resta no OpenClaw; `intel-scraper-cell` resta leggero Genome+HGT publisher, no PulseLoop; `HGT coordinator` e Confrontation pillar ma propose+audit+quarantine, mai merge diretto. Aggiungo `mata-garuda-cell` come L4.5 meta-awareness/asset indexer e `crm-practice-cell` come cluster unico per CRM 13 automazioni (`crm_automation_engine.py`, `practice_status_listener`, lead scoring, proactive compliance, client health), perche hanno stato business, feedback loop e impatto decisionale.

I Bali Zero Dispatch LaunchAgents non diventano top-level cell separati: vanno mappati dentro `war-room-organism`. `connector` e L1, `strategos` L3, `oracle` L4; newsletter, draft-generator, canva-apply, image-generator, dossier-compiler e topic-selector sono organelle/sub-moduli del WR2 organism. Regulatory monitors (`oss`, `pajak`, `imigrasi`, `bi-exchange-rate`) e translation hourly restano observed-shell finche non dimostrano memoria, scars e decision changes.

Gerarchia corretta: organism -> innervation -> cell-cores; L0 cell, L1 tissue, L2 organ, L3 system, L4 organism, L4.5 meta-awareness. Round 1 collassava troppi candidati in L1.

### Disagreements
Non promuoverei i Dispatch LaunchAgents uno-a-uno: creerebbe micro-cell senza autonomia reale e violerebbe Local sovereignty per dipendenza dal WR2 pipeline state.

Non tratterei Innervation Genoma come cell candidate: e nervous system/signal routing sopra i cell-core.

Non promuoverei CRM in 13 cell: serve un solo `crm-practice-cell` con sub-handlers, altrimenti aumentano drift, costi e HGT noise.

Qualsiasi candidate che scrive stato senza `events_outbox`/PG LISTEN-NOTIFY viola la Legge Event-driven. Qualsiasi candidate OpenClaw-only senza fallback viola Graceful degradation, visto scheduler frozen Apr 30.

### Missed cases
Il briefing nota "7 LaunchAgents" ma ne elenca 9: va normalizzato prima del mapping.

Manca un admission test formale per le 7 Leggi: CLI-only, OSINT blindato, Event-driven, Graceful degradation, Zero final instance, Local sovereignty, Numbers first.

Manca classificazione "observed-shell" esplicita per traduzione, BI, regulatory monitors, backups, NLM refresh e webhook: devono emettere eventi senza importare cell-core.

Manca una policy per scars/cicatrix: scope Personal, never inherited, confidence 0.9. HGT coordinator non deve propagare scars.

### Risk callouts
Over-promotion: troppe cell aumentano operabilita fragile, non intelligenza.

Event substrate drift: HGT citato su Redis Streams, realta EventBus su PG LISTEN/NOTIFY + outbox.

HGT poisoning: pattern cross-cell propagati prima di avere >=10 usi e confidence >0.7.

Genome bloat: 300+ automazioni possono saturare skills/patterns senza decay aggressivo.

Centralizzazione WR2/Oracle: rischia di violare Zero as final instance se diventa decision gate unico.

### Sprint plan revisionato
Sprint 0: inventory gate. Normalizzare 263/~300 automazioni in `full-cell`, `light-cell`, `organism-submodule`, `observed-shell`, `leave-alone`.

Sprint 1: cell admission harness. Ogni candidate deve passare 7 Leggi, event emission, fallback, budget cap, trace ID, kill switch.

Sprint 2: `intel-scraper-cell` leggero + HGT quarantine queue. Nessun OpenClaw scheduler.

Sprint 3: WR2 organism mapping dei LaunchAgents live + Innervation contracts.

Sprint 4: `mata-garuda-cell` e `crm-practice-cell`.

Sprint 5: promozione rimanenti round 1 cell solo dopo event bridge e observed-shell telemetry.

## Q2 — OpenClaw runtime consolidation

### Verdict
CONCUR con il reasoning di Claude Opus round 2

### Reasoning (max 400 parole)
La risposta concreta e C) Split clean. Round 1 trattava OpenClaw come unico player e proponeva 6 candidate OpenClaw. L'audit cambia il centro: `cron-agent-python` e il vero production runner, con 19 strategie live oggi (`fact-checker`, `tech-orchestrator`, `daily-ops`, `system-doctor`, `log-anomaly-detector`, `fly-watcher`, `intel-radar`, `client-health-monitor`, `compliance-ops`, `oss`, `pajak`, `imigrasi`, `bi-exchange-rate`, `vision-doc`, `tdd-pipeline`). OpenClaw ha 24 jobs frozen dal 30 Apr e il suo uso production reale sono i 4 Lobster workflows, 45 step, via `openclaw agent --agent coder`.

Confine quantitativo:

OpenClaw solo se soddisfa almeno 3/5: sessione multi-turn; >=2 tool/MCP concatenati; memoria persistente cambia decisioni future; human channel/review via Telegram/voice/browser; azione bounded con budget cap, max steps, kill switch e fallback diretto.

cron-agent-python se soddisfa almeno 3/5: schedule deterministico; input/output replayable; SLA operativo; task single-purpose; alta frequenza o indipendenza dal gateway.

cagent: freeze per nuove business automations finche non ha ownership distinta. `claude-squad`: solo git/PR orchestration. `mcporter`: non "runtime"; diventa tool surface per OpenClaw/Lobster quando serve semantic leverage.

Quindi: spegnere OpenClaw scheduler come source of truth, non cron-agent-python. OpenClaw resta gateway agentic, Telegram stateful, Lobster coder workflows, Knowledge Agents e mcporter orchestration.

### Disagreements
Disaccordo con A) OpenClaw vince. Sarebbe regressione operativa: scheduler frozen, log 21.7 GB, Telegram command limit quasi saturo, single-machine, nessun Prometheus.

Disaccordo con D) status quo. Tre runtime paralleli senza ownership producono doppie code, state drift e incidenti invisibili.

Non migrerei `fact-checker` e `tech-orchestrator` wholesale: cron-agent-python deve restare trigger/SLA; puo chiamare OpenClaw solo per sub-step agentic.

### Missed cases
Manca piano per `cagent` 19 registered strategies: spegnere, congelare o assegnare dominio.

Manca owner per upgrade OpenClaw 2026.3.31 -> 2026.4.29 e rollback.

Manca retention/log rotation per `gateway.log` 21.7 GB prima di qualsiasi aumento traffico.

Manca policy per Telegram command budget: <80 comandi registrati, skill low-use disabilitate.

Manca decisione su `claude-code` terzo agent undocumented: documentare o rimuovere.

### Risk callouts
Scheduler ambiguity: due runtime possono eseguire la stessa automazione o nessuno dei due.

Reliability inversion: migrare batch stabili su OpenClaw prima di fixare cron significherebbe perdere SLA.

Security: sandbox off, token e plugin trust warning `claude-mem` manual install.

Cost drift: OpenClaw multi-model fallback puo moltiplicare chiamate senza per-agent ceilings.

Single-machine SPOF: OpenClaw non ha federation native; cron-agent-python deve restare degradazione locale.

### Sprint plan revisionato
Sprint 0: runtime register. Per ogni job: owner runtime, schedule, state store, kill switch, duplicate risk.

Sprint 1: disabilitare o svuotare OpenClaw cron queue frozen; mantenere cron-agent-python come scheduler autorevole.

Sprint 2: upgrade/test OpenClaw 2026.4.29 in rollback-safe mode; `openclaw doctor`; verificare scheduler ma non promuoverlo ancora.

Sprint 3: integrare mcporter e Knowledge Agents in Lobster/Telegram per 2 workflow ad alto valore.

Sprint 4: convertire fact-checker/tech-orchestrator/daily-ops in hybrid: cron-agent-python trigger, OpenClaw sub-step solo se supera criteria 3/5.

Sprint 5: rimuovere cagent overlap o assegnargli dominio non sovrapposto.

## Q3 — Intel Scraper, WR2 e Mata-Garuda

### Verdict
PARTIAL con il reasoning di Claude Opus round 2

### Reasoning (max 400 parole)
Round 1 era corretto sul macro-verdetto: Intel Scraper non deve diventare OpenClaw main path; WR2 e un cell-organism mascherato. Round 2 corregge il piano operativo: WR2 non e roadmap, e gia live con LaunchAgents Dispatch. Il lavoro non e redesign, e esplicitazione + hardening del cell mapping.

WR2: mappare i LaunchAgents live dentro il modello cognitivo. `connector` = L1 ingestion/tissue boundary; `strategos` = L3 system planner; `oracle` = L4 forward model; newsletter/draft-generator/canva-apply/image-generator/dossier-compiler/topic-selector = organelle operative. Le tre insertions OpenClaw round 1 restano candidate, ma non come "micro-task non agentic": OpenClaw va usato solo per sub-step multi-tool/stateful. Consiglio multi-LLM resta diretto; Drafter Claude OAuth resta diretto; Imagen resta diretto.

Intel Scraper: ancora cell leggera, non full cell. Genome scar registry + HGT publisher + event bridge; no PulseLoop e no Homeostasis finche la pipeline resta lineare/replayable. Il fatto che `drive-poll.sh` sia disabilitato dal 2026-04-29 per PG load impone verifica del main path daily 03:00 WITA prima di qualunque integrazione.

Mata-Garuda: separato da WR2. E L4.5 meta-awareness/asset indexer, non sub-cell editoriale. Deve nutrire WR2 tramite contract/eventi, non vivere dentro WR2.

### Disagreements
Non farei redesign WR2: sostituire parti live introduce rischio senza ROI. Serve contract mapping, telemetry, fallback e scars.

Non chiamerei OpenClaw per micro-task non agentic: se e deterministic/replayable resta cron-agent-python o shell.

Non fonderei Mata-Garuda in WR2: perderebbe il ruolo L4.5 cross-organism e diventerebbe asset helper editoriale.

Trend pre-filter OpenClaw deve essere recall-safe: se confidence <0.6 passa comunque al Consiglio, come round 1 synthesis.

### Missed cases
Serve health audit dei LaunchAgents WR2: running PID, last success, last failure, output artifact, event emission.

Serve distinguere 7 vs 9 Dispatch names prima di scrivere mapping definitivo.

Serve explicit contract Intel -> WR2: fake-source scar da Intel deve arrivare a WR2 Trend-Hunter via HGT quarantine, non merge diretto.

Serve PG load budget: drive-poll disabled dimostra che ingest mal calibrato puo degradare il substrate.

Serve asset provenance per Mata-Garuda: ogni asset indicizzato deve avere source, confidence, owner e invalidation path.

### Risk callouts
WR2 latent failure: LaunchAgents live senza organism-level observability possono sembrare sani mentre producono output stale.

Publication latency: Legge 5 human final gate va preservata, ma pre-processing deve essere async.

Council deadlock: se un LLM manca, quorum 3/4 deve bastare.

OSINT contamination: Intel, Mata-Garuda e WR2 non devono mischiare fonti esterne non verificate con client facts.

OpenClaw dependency creep: usare scheduler OpenClaw per WR2 prima del fix Apr 30 crea SPOF.

### Sprint plan revisionato
Sprint 0: verificare stato reale WR2 e Intel. `launchctl`, last-run artifacts, 03:00 Intel path, disabled drive-poll impact.

Sprint 1: WR2 mapping doc + event contracts per connector/strategos/oracle e organelle operative.

Sprint 2: Intel light cell: scar registry, HGT publisher quarantine, no blocking LLM.

Sprint 3: WR2 observed-shell bridge: ogni LaunchAgent emette events_outbox con trace ID, status, artifact URI.

Sprint 4: Mata-Garuda standalone L4.5 contract verso WR2, non nested inside WR2.

Sprint 5: OpenClaw insertions solo dopo Q2 split: L1 connector assist, Learner M14, Trend pre-filter, optional research retrieval planner.
