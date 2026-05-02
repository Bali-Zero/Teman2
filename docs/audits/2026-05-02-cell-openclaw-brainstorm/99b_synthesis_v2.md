# Synthesis cross-LLM brainstorm Round 2 — 2 May 2026

**Reviewers:** Codex GPT-5.5 xhigh + Gemini 3.1 Pro CLI + DeepSeek V4 Reasoner + Claude Opus 4.7

**Round 1 verdict (per riferimento):** 12 cell candidate, 6 OpenClaw candidate, 5 sprint 6-8 settimane, costo $30-45/mese.

**Round 2 corrections:** 4 audit completezza files (04-07) hanno rivelato briefing round 1 sotto-stimato del 50%+. Round 2 incorpora 300+ automazioni reali, Innervation Genoma vs cell-core hierarchy, 7 Leggi immutabili, Symbiosis 8 Pilastri, Cognitive Levels L0-L4.5, cron-agent-python competitor runtime LIVE, OpenClaw deep research v2026.4.29.

---

## Quorum overview

| Domanda | Claude Opus | Codex GPT-5.5 | Gemini 3.1 Pro | DeepSeek V4 |
|---|---|---|---|---|
| **Q1** cell candidates con L0-L4.5 + 7 Leggi | promote 12 flat | PARTIAL | DISAGREE | PARTIAL |
| **Q2** runtime consolidation | propone Opzione C | CONCUR Opzione C | CONCUR Opzione C | CONCUR Opzione C |
| **Q3** Intel + WR2 + Mata-Garuda | esplicitare cell-mapping | PARTIAL | PARTIAL | PARTIAL |

**Q2 unanime** (4/4 Opzione C split clean).
**Q1+Q3 PARTIAL/DISAGREE** unanime contro round 1 — round 2 reasoning era ancora insufficiente.

---

## Q1 — Cell candidates: lista finale

### Convergenza forte (4/4)

1. **Round 1 lista flat di 12 era sbagliata** — non rispettava gerarchia L0-L4.5
2. **Bali Zero Dispatch LaunchAgents NON sono sub-module flat di WR2** — sono cell mature a vari livelli (oracle=L4, strategos=L3, connector=L1)
3. **CRM 13 automazioni → 1 sola `crm-cell` (L1) consolidata** (share crm_automation_engine.py, no 13 micro-cell)
4. **Mata-Garuda L4.5 SEPARATO** da WR2 (NON sub-cell)
5. **Innervation Genoma NON è cell candidate** — è nervous system/signal routing sopra cell-core
6. **HGT coordinator = pilastro Confrontation** mancante (esattamente)

### Disagreement sostanziale tra reviewer

| Reviewer | Lista finale | Promotion philosophy |
|---|---|---|
| Codex | **14 cell** (12 round 1 + crm-cell + mata-garuda) | conservative, gerarchia stretta, organelle non promote |
| Gemini | **non quantificate** (ridefinisce per L1-L4.5) | Bali LA = cell mature non sub-module |
| DeepSeek | **18 cell** (12 + crm + mata-garuda + connector + strategos + oracle + sub-cell aggregate) | espansiva, ogni LA Bali a livello cognitive proprio |

**Mediana convergente**: **14-15 cell candidate finali** (Codex baseline + parziale espansione DeepSeek).

### Lista finale PROPOSTA (14 cell, gerarchia L0-L4.5)

**L0 (cellular core):**
- (nessuna nuova — questi sono i framework cell-core stessi)

**L1 (tissue):**
1. **system-doctor-cell**
2. **seo-guardian-cell** (esistente seo_cell pattern)
3. **fact-checker-cell**
4. **tech-orchestrator-cell** (con escalation Claude per HIGH risk)
5. **conversation-trainer-cell**
6. **daily-ops-cell**
7. **crm-cell** ⭐ NEW (consolidata da 13 CRM automations)
8. **intel-scraper-cell** ⭐ LEGGERA (Genome+HGT publisher only, no PulseLoop)

**L2 (organ):**
9. **HGT coordinator** ⭐ NEW (Confrontation pillar, propose-only quarantine)
10. **gap-scanner-cell** (no OpenClaw, Ollama locale)
11. **kg-cell**
12. **research-cell** (NB pipelines orchestrator)

**L3 (system):**
13. **war-room-organism** (federazione che CONTIENE Bali Zero Dispatch 7-9 LA come organelle: connector L1, strategos L3, oracle L4, draft-generator/image-generator/canva-apply/dossier-compiler/topic-selector/newsletter come sub-organelle)

**L4.5 (meta-awareness):**
14. **mata-garuda-cell** ⭐ NEW (separato da WR2, innervation incrociata bidirezionale)

### Disagreement tra DeepSeek e Codex (importante)

DeepSeek vuole promuovere **`oracle` L4 + `strategos` L3 + `connector` L1 come cell autonome**, non come organelle WR2.

Codex risponde: "Non promuoverei i Dispatch LaunchAgents uno-a-uno: creerebbe micro-cell senza autonomia reale e violerebbe Local sovereignty per dipendenza dal WR2 pipeline state."

**Mia decisione**: **scelgo Codex** — Bali Zero LA dipendono dallo state condiviso WR2 (10-consumer fanout Qdrant ResearchDossier), promuoverle a cell autonome violerebbe Legge "Local sovereignty" (non possono decidere indipendentemente). Restano organelle dentro `war-room-organism`.

### Missed cases incorporati

- **Codex**: 7 vs 9 Dispatch names → da normalizzare prima di mapping (briefing diceva "7 LaunchAgents" ma elenca 9). **Audit gap da chiudere Sprint 0**.
- **Codex**: admission test 7 Leggi formale per ogni candidate (CLI-only / OSINT blindato / Event-driven / Graceful degradation / Zero final / Local sovereignty / Numbers first).
- **Codex**: classificazione "observed-shell" per traduzione, BI, regulatory monitors (oss/pajak/imigrasi/bi-exchange-rate), backup, NLM refresh, webhook → emettono eventi senza importare cell-core.
- **DeepSeek**: oracle L4 può violare "OSINT blindato" se usa fonti non verificate → vincolato a feed solo intel-scraper + cron-agent-python OSS.
- **DeepSeek**: cost drift — oracle L4 limitato a 5 query/giorno.

### Risk callouts unanimi

- **Over-promotion**: troppe cell = operabilita fragile, non intelligenza (Codex)
- **Genome bloat** 300+ automazioni saturano skills senza decay aggressivo (Codex + Gemini)
- **HGT poisoning**: pattern propagati prima di ≥10 uses + conf>0.7 (Codex unanime con round 1)
- **Oracle/WR2 SPOF decisionale**: oracle L4 può bypassare war-room (DeepSeek)
- **Event substrate drift**: HGT detto Redis Streams ma reality EventBus PG NOTIFY (Codex)
- **OSINT contamination**: Intel/Mata-Garuda/WR2 non devono mischiare fonti non verificate con client facts (Codex)

---

## Q2 — Runtime consolidation: UNANIMOUS Opzione C (split clean)

### 4/4 CONCUR Opzione C

OpenClaw e cron-agent-python hanno **ontologie diverse**, mantenere split clean con confine quantitativo.

### Confine quantitativo (Codex 3/5 criterio)

**OpenClaw** se task soddisfa **≥3/5**:
1. Sessione multi-turn
2. ≥2 tool/MCP concatenati
3. Memoria persistente cambia decisioni future
4. Human channel/review (Telegram/voice/browser)
5. Bounded action con budget cap + max steps + kill switch + fallback diretto

**cron-agent-python** se task soddisfa **≥3/5**:
1. Schedule deterministico
2. Input/output replayable
3. SLA operativo
4. Task single-purpose
5. Alta frequenza o indipendenza dal gateway

### Convergenza azioni urgenti (3/3 reviewer)

| Azione | Priorità | Reviewer |
|---|---|---|
| **Log rotation gateway.log 21.7GB** | 🔴 critica | Gemini + DeepSeek + Codex |
| **Disabilitare mcporter 129 idle tools** | 🟡 alta (~150-200MB RAM) | Gemini + DeepSeek + Codex |
| **Ridurre Telegram commands a <80-90** | 🟡 alta (limite 100) | Codex (più conservativo) |
| **Upgrade OpenClaw v2026.3.31 → v2026.4.29** | 🟡 alta (probabile fix scheduler) | Tutti |
| **Disabilitare 24 OpenClaw frozen jobs** | 🟢 media | Codex |
| **Attivare Knowledge Agents v12.1.0** | 🟢 media (per HGT coordinator + intel-radar) | DeepSeek + Codex |
| **Documentare/rimuovere `claude-code` 3rd agent** | 🟢 media | Codex (missed da round 1) |
| **Decisione su `cagent` 19 strategies** | 🟢 media (freeze/dismiss/assegnare dominio) | Codex |

### Applicazione split clean alle 19 strategie cron-agent-python (DeepSeek dettagliato)

| Strategia | Decisione | Rationale |
|---|---|---|
| fact-checker | **resta cron-agent-python** | scheduled + tool limitati (fetch + reasoning singolo) |
| tech-orchestrator | **hybrid: cron-agent trigger + OpenClaw sub-step** | se ≥3 tool, sub-step OpenClaw |
| daily-ops | resta cron | reporting semplice |
| system-doctor | resta cron | system monitor |
| log-anomaly | resta cron | batch analysis |
| fly-watcher | resta cron | single API |
| **intel-radar** | **CANDIDATO migrare OpenClaw** | multi-source aggregator → Knowledge Agents v12.1.0 |
| oss/pajak/imigrasi/bi-exchange-rate | resta cron | batch read-only regulatory |
| vision-doc | resta cron | OCR singolo tool |
| tdd-pipeline | resta cron | sequenziale |
| client-health-monitor | resta cron | polling semplice |
| compliance-ops | resta cron | batch deterministic |
| intel-feed-processor | resta cron | crawl + parse |

**Risultato**: 18/19 strategie restano cron-agent-python. Solo **intel-radar** candidato OpenClaw (Knowledge Agents).

### Dismissione runtime morti

- **Jules / kradle / kimi**: dismessi (dormant, no recent activity)
- **cagent**: freeze per nuove automation finché non ha ownership distinto
- **claude-squad**: solo git/PR orchestration, no automation runner
- **mcporter**: NON è runtime — diventa tool surface per OpenClaw/Lobster (129 tools idle vanno disabilitati per default, abilitati on-demand)

### Risk callouts unanimi

- **Scheduler ambiguity**: due runtime possono eseguire la stessa automazione o nessuno dei due (Codex)
- **Reliability inversion**: migrare batch stabili su OpenClaw prima di fix scheduler = perdita SLA (Codex)
- **Single-machine SPOF**: OpenClaw no federation; cron-agent-python deve restare degradazione locale (Codex + Gemini)
- **Cost drift**: OpenClaw multi-model fallback può moltiplicare chiamate senza per-agent ceiling (Codex + DeepSeek)
- **Manutenzione dual-runtime**: 2 codebase da patchare, accettabile se confini chiari (DeepSeek)
- **OpenClaw upgrade rischia rompere Lobster**: testare in ambiente isolato prima (DeepSeek)

---

## Q3 — Intel Scraper + WR2 + Mata-Garuda: PARTIAL unanime

### Convergenza forte (4/4)

1. **WR2 NON è roadmap** — già LIVE con LaunchAgents Dispatch (anche se 7 vs 9 da normalizzare)
2. **WR2 è cell-organism mascherato** (Trend=sensor, Consiglio=reasoner, Drafter=act, Validator=SafetyGate, Learner=reflection)
3. **WR2 lavoro ≠ redesign** — è **esplicitazione + hardening del cell-mapping** già esistente
4. **Intel Scraper resta cell leggera** (Genome scar registry + HGT publisher + event bridge, no PulseLoop, no Homeostasis)
5. **Mata-Garuda L4.5 SEPARATO** da WR2 — innervation incrociata bidirezionale, NON sub-cell
6. **3 OpenClaw insertions WR2** (L1 Connector + Learner M14 + Trend pre-filter) restano valide MA solo dopo audit duplicate vs cron-agent-python intel-feed-processor

### Disagreement DeepSeek vs Codex/Gemini

DeepSeek dice: "Le 3 insertions OpenClaw del round 1 sono **probabilmente DUPLICATE** a cron-agent-python intel-feed-processor + Connector LA. Da verificare e dismettere se duplicate."

Codex dice: "Le insertions restano candidate, ma non come 'micro-task non agentic' — solo se sub-step multi-tool/stateful."

**Mia decisione**: Sprint 0 verifica duplicazione → se duplicate dismettere, altrimenti applicare criterio Codex 3/5.

### Missed cases

**Codex** (riconosce gap audit):
- "7 vs 9 LaunchAgents" da normalizzare prima di mapping
- Health audit WR2: running PID, last success, last failure, output artifact, event emission
- PG load budget (drive-poll disabled 2026-04-29 dimostra ingest mal calibrato degrada substrate)
- Asset provenance per Mata-Garuda: ogni asset indicizzato deve avere source + confidence + owner + invalidation path

**Gemini**:
- Audit WR2 IPC: i 7-9 LA comunicano via filesystem o EventBus? Se filesystem → violazione Legge "Event-driven" → migrare PG NOTIFY

**DeepSeek**:
- WR2 oracle L4 SPOF decisionale (può bypassare war-room)
- Scars cicatrix: WR2 ha ereditato scars da vecchia pipeline?
- Trend pre-filter recall safety: confidence <0.6 passa comunque a Consiglio

### Risk callouts unanimi

- **WR2 latent failure**: LaunchAgents live senza organism-level observability sembrano sani producendo output stale (Codex)
- **Publication latency**: Legge 5 human gate va preservata, pre-processing async (Codex)
- **Council deadlock**: quorum 3/4 sufficiente (round 1 mantenuto)
- **OSINT contamination**: Intel/Mata-Garuda/WR2 no fonti non verificate mischiate con client facts (Codex)
- **OpenClaw dependency creep**: scheduler OpenClaw per WR2 prima del fix v2026.4.29 = SPOF (Codex)
- **Intel Scraper PG load**: drive-poll disabled prova ingest può degradare substrate (Codex)

---

## Sprint plan finale (sintesi 4-LLM)

**Total: 9 sprint, ~10 settimane** (era 5 sprint 6-8 settimane in round 1).

### Sprint 0 — Inventory + Hardening (1 settimana, urgente)

**Audit + cleanup**:
- Normalizzare 263/300+ automazioni in 5 categorie: `full-cell`, `light-cell`, `organism-submodule`, `observed-shell`, `leave-alone`
- Normalizzare 7 vs 9 Bali Zero Dispatch LaunchAgents
- Audit WR2 IPC (filesystem o EventBus)
- Audit duplicate 3 OpenClaw insertions vs cron-agent-python intel-feed-processor
- Verificare main path Intel Scraper 03:00 WITA daily

**OpenClaw hardening**:
- logrotate gateway.log 21.7GB
- Upgrade v2026.3.31 → v2026.4.29 (rollback-safe, isolato)
- Riduzione Telegram commands <80
- Disabilitazione mcporter 129 idle tools
- Documentare/rimuovere `claude-code` 3rd agent

**Runtime register**:
- Per ogni job: owner runtime + schedule + state store + kill switch + duplicate risk
- Disabilitare 24 OpenClaw frozen jobs (o svuotare queue)
- Decisione su cagent (freeze/dismiss/dominio)
- Dismissione Jules/kradle/kimi

**7 Leggi admission test**:
- Per ogni candidate cell: CLI-only / OSINT blindato / Event-driven / Graceful degradation / Zero final / Local sovereignty / Numbers first

### Sprint 1 — Intel Scraper light + HGT quarantine (1 settimana)

- `intel-scraper-cell` leggera: Genome scar registry + HGT publisher + event bridge
- HGT coordinator standalone (Kimi K2.6 via OpenClaw) **propose-only quarantine** — NO merge diretto, audit log, soglia ≥10 uses + conf>0.7

### Sprint 2 — WR2 mapping + event contracts (1 settimana)

- WR2 mapping doc: connector=L1, strategos=L3, oracle=L4, organelle operative
- Event contracts per ogni LaunchAgent
- Cablare WR2 7-9 LA all'EventBus PG NOTIFY (rispetto Legge "Event-driven")
- WR2 observed-shell bridge: ogni LA emette events_outbox con trace ID + status + artifact URI

### Sprint 3 — crm-cell + mata-garuda-cell (2 settimane)

- `crm-cell` consolidata da 13 CRM automations (crm_automation_engine + practice_status_listener + proactive_compliance_monitor + ecc.)
- `mata-garuda-cell` standalone L4.5 con asset provenance schema (source + confidence + owner + invalidation path)
- Innervation incrociata bidirezionale Mata-Garuda ↔ WR2

### Sprint 4 — Cell promotion remaining (2 settimane)

Dopo event bridge + observed-shell telemetry pronti:
- system-doctor-cell, seo-guardian-cell, fact-checker-cell, tech-orchestrator-cell
- conversation-trainer-cell, daily-ops-cell

### Sprint 5 — OpenClaw insertions WR2 (1 settimana)

Solo dopo Q2 split clean operativo:
- L1 Connector assist (OpenClaw sub-step se duplicate ridondanti dismessi)
- Learner M14 feedback loop (DeepSeek-Reasoner)
- Trend-Hunter pre-filter (MiniMax M2.7, recall safety conf<0.6 passa comunque)
- Optional: Research retrieval planning (Qwen3-Max)

### Sprint 6 — kg-cell + research-cell + gap-scanner-cell (1 settimana)

- kg-cell promotion (no OpenClaw)
- research-cell (NB pipelines orchestrator)
- gap-scanner-cell (no OpenClaw, Ollama locale)

### Sprint 7 — Hybrid runtime fact-checker/tech-orch/daily-ops (1 settimana)

- fact-checker: cron-agent-python trigger + OpenClaw sub-step solo se 3/5
- tech-orchestrator: idem + escalation Claude HIGH risk
- daily-ops: idem

### Sprint 8 — Intel-radar OpenClaw migration (opzionale, 1 settimana)

- Migrare intel-radar da cron-agent-python a OpenClaw + Knowledge Agents v12.1.0 (multi-source aggregation)

---

## Stima costi finale (revisionata)

**Round 1**: $30-45/mese OpenClaw (era $10-15 troppo ottimistico).

**Round 2 corrections**:
- Solo intel-radar migra a OpenClaw → costo OpenClaw ridotto
- WR2 3 insertions verificate (potrebbero essere duplicate) → costo OpenClaw ulteriormente ridotto
- HGT coordinator propose-only (no merge) → calls limitate
- 13 CRM automations → 1 cell (no scale-out)
- mata-garuda-cell L4.5 isolato (basso volume)

**Stima realistica**: **$15-25/mese OpenClaw + $0 cron-agent-python** (gratis, locale Python). Total infrastructure cost **<$30/mese**.

---

## Risk register consolidato (deve essere mitigato)

| Rischio | Reviewer | Sprint | Mitigazione |
|---|---|---|---|
| **gateway.log 21.7GB disk exhaustion** | 4/4 | Sprint 0 | logrotate immediata |
| **OpenClaw scheduler frozen** | 4/4 | Sprint 0 | upgrade v2026.4.29 |
| **Telegram BOT_COMMANDS_TOO_MUCH** | Codex + DeepSeek | Sprint 0 | <80 commands |
| **mcporter idle 200MB RAM** | Gemini + DeepSeek | Sprint 0 | disable default |
| **WR2 IPC filesystem** | Gemini | Sprint 0 audit | migrare PG NOTIFY se confermato |
| **3 OpenClaw insertions duplicate cron-agent-python** | DeepSeek | Sprint 0 audit | dismettere se duplicate |
| **Oracle L4 SPOF decisionale** | DeepSeek | Sprint 2 | regola "oracle raccomanda, war-room decide" |
| **HGT poisoning** | 4/4 unanime | Sprint 1 | propose-only + ≥10 uses + conf>0.7 |
| **Genome bloat** | Codex + Gemini | continuo | decay aggressivo monitorato |
| **Over-promotion** | Codex | continuo | 7 Leggi admission test |
| **Council deadlock WR2** | Gemini round 1 | mantenuto | quorum 3/4 |
| **State drift KG-Genome** | Gemini round 1 | mantenuto | tag invalidation |
| **OpenClaw upgrade rompe Lobster** | DeepSeek | Sprint 0 | test in isolated env |
| **OSINT contamination** | Codex | Sprint 1+3 | feed allowlist Intel/Mata-Garuda/WR2 |
| **PG load substrate degrade** | Codex | Sprint 0 | budget calibrato (lesson drive-poll) |

---

## Final list

**14 cell candidate** (era 12 round 1, +2 nuovi: crm-cell + mata-garuda-cell):

L1: system-doctor, seo-guardian, fact-checker, tech-orchestrator, conversation-trainer, daily-ops, **crm-cell ⭐**, intel-scraper-cell (light)
L2: HGT coordinator (propose-only), gap-scanner, kg-cell, research-cell
L3: war-room-organism (federazione contiene Bali Dispatch 7-9 LA come organelle)
L4.5: **mata-garuda-cell ⭐**

**Runtime split** (4/4 unanime Opzione C):
- OpenClaw: Telegram + Lobster + Knowledge Agents + intel-radar (nuovo) + WR2 sub-step agentici
- cron-agent-python: 18/19 strategie scheduled deterministiche
- mcporter: tool surface, default disabled
- Jules/kradle/kimi: dismessi
- cagent: freeze
- claude-squad: solo git/PR

**Sprint plan**: 9 sprint ~10 settimane (era 5 sprint 6-8 settimane round 1).

**Costo**: <$30/mese infrastruttura totale (era $30-45 round 1).

---

## Convergence summary (da round 1 → round 2)

| Aspetto | Round 1 | Round 2 |
|---|---|---|
| Cell candidate | 12 flat | **14 gerarchici L0-L4.5** |
| OpenClaw candidate | 6 (con gap-scanner) | 5 (gap-scanner escluso, intel-radar nuovo) |
| Runtime decision | non chiaro | **Opzione C unanime** |
| Sprint count | 5 | **9** |
| Settimane | 6-8 | **~10** |
| Costo/mese | $30-45 | **<$30** |
| Risk register | 5 voci | **15 voci** |
| 7 Leggi check | non considerato | **admission test obbligatorio** |
| Innervation hierarchy | non considerata | **organism→innervation→cell-cores** |
| Audit completezza | "130 automazioni" | **300+ documentate** |
| Bali Zero Dispatch | dimenticato | **organelle WR2 (7-9 LA)** |
| Mata-Garuda | dimenticato | **cell L4.5 separata** |
| CRM cluster | dimenticato | **crm-cell L1 unificata** |
| cron-agent-python | dimenticato | **REAL production runner** |
| Knowledge Agents v12.1.0 | dimenticato | **NUOVO valore non sfruttato** |
| Log rotation gateway 21.7GB | dimenticato | **rischio critico Sprint 0** |
| Telegram commands limit | dimenticato | **<80 Sprint 0** |
| mcporter idle 129 tools | dimenticato | **disable default Sprint 0** |
| Upgrade OpenClaw | dimenticato | **v2026.4.29 Sprint 0** |

---

**Documento finale.** Pronto per Sprint 0 working plan dettagliato.
