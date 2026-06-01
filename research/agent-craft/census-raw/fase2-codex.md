# FASE 2 - Codex Panel Findings

Data: 2026-06-02  
Scope Codex: aree 7-12 del brief, cioe multi-agent consolidation, document-AI/OCR, browser/computer-use, voice/WhatsApp, predictive agents, evals/observability.

## Metodo e vincoli

- Grounding locale: `phase1-synthesis.md`, `zone-frontend.md`, `zone-channels-services.md`, `zone-meta-orchestration.md`, piu grep diretto su agenti, servizi, launch labels e riferimenti `canva_renderer`, `wa-mirror`, WR2/WR3.
- Ricerca esterna: 30+ query raggruppate sui sei temi Codex, con priorita a fonti primarie: Anthropic, OpenAI, LangChain/LangGraph, Microsoft AutoGen, Google/Meta/AWS/Microsoft/Google Cloud, OpenTelemetry, paper arXiv e documentazione framework.
- Nessun dato cliente/PII esportato. Le query esterne sono state solo su SOTA generico, framework e benchmark.
- ROI espresso come impatto operativo misurabile, non come euro inventati. Le metriche proposte sono benchmark before/after da raccogliere in produzione o shadow mode.

## Executive Delta

| Area | Stato Nuzantara verificato Fase 1 | SOTA 2026 rilevante | Opportunita concreta | ROI atteso |
| --- | --- | --- | --- | --- |
| 7. Consolidamento multi-agent | 5+ relazioni duplicate, chat frontend frammentate, council multipli, namespace launchd doppi | agenti solo quando workflow statici non bastano; supervisor/handoff con contratti espliciti; costo come metrica di progetto | Agent Contract Registry + Duplicate Reconciler + primitive condivise | Alto: meno drift, meno daemon morti, meno manutenzione parallela |
| 8. Document-AI/OCR | OCR/vision esistono ma non governano akta/KITAS/company docs end-to-end | OCR/layout + extraction schema + confidence + human review; Docling/Mistral/Document AI/Textract/Azure | Akta/OCR Triage Agent locale-first con checklist e provenance | Alto: riduce triage manuale e revisioni documentali |
| 9. Browser/computer-use | portali governativi ancora manuali; chain MCP non invocate; organism in shadow mode | browser agent sandboxed, Playwright MCP, checkpoints, HITL, eval su WebArena/OSWorld/WorkArena | Portal Copilot Runner per OSS/BKPM/Imigrasi/DJP, read-only prima | Alto ma rischio alto: partire da status-checker e form prefill |
| 10. Voice/WhatsApp | WhatsApp e wa-mirror vivi; copilot locale estrae, ma dashboard mostra solo draft statici; FAB pubblico morto | WhatsApp Flows + Cloud API + voice transcription/realtime + human handoff | WA Operator Copilot + Flow Pack + voice-note summarizer | Molto alto: canale principale e lead funnel |
| 11. Predictive | competitor/yield mai usati; deadline/upsell/churn non governati; compliance calendar non diventa queue | survival/risk calibrated models + deterministic rules + LLM explanation, not LLM prediction | Revenue & Deadline Sentinel con queue giornaliera | Alto: rinnovi, scadenze, upsell, minore ritardo pratica |
| 12. Evals/observability | LangSmith/Ragas presenti ma non impediscono agenti morti; self-improvement rotto a ogni giunto | trajectory eval, trace per tool/action, OTEL GenAI, cost/latency/policy gates | Agent Observatory + Trajectory Eval Gate + launchd smoke tests | Fondazionale: evita regressioni silenziose e loop vuoti |

---

## 7. Multi-Agent Consolidation

### SOTA 2026

La traiettoria SOTA non e "piu agenti". E consolidamento controllato:

1. **Semplicita prima, agenti solo dove servono.** Anthropic raccomanda di partire da workflow semplici e aumentare complessita solo quando serve decisione dinamica, uso tool non prevedibile o autonomia multi-step. Il pattern utile non e "swarm" generico, ma orchestrator-worker, evaluator-optimizer, routing e parallelization composti con confini chiari.
2. **Supervisor e handoff, non duplicati casuali.** LangChain multi-agent separa due topologie: supervisor/tool-calling centralizzato e handoff decentralizzato tra agenti. OpenAI Agents SDK espone agenti, handoff, guardrail, sessioni e tracing come primitive. AutoGen punta su runtime event-driven e osservabilita per sistemi multi-agent distribuiti.
3. **Contratti di interoperabilita.** MCP standardizza tool/resource/prompt via JSON-RPC. Google A2A spinge agent-card, task, message e artifact per agenti cross-platform. Il punto pratico e ridurre accoppiamento: un agente non deve conoscere implementazioni interne di altri agenti.
4. **Cost-aware agent design.** "AI Agents That Matter" mostra che il costo va controllato insieme all'accuratezza: un agente piu complesso puo vincere benchmark ma perdere economicamente. Per Nuzantara il costo critico e doppio: token + manutenzione operativa di daemon/launchd/servizi.

### Fit Nuzantara

Fase 1 ha trovato duplicazione e frammentazione reali:

- `wr2-brief-interpreter` quasi uguale a `wr3-brief-interpreter`.
- `wr2-external-bench` quasi uguale a `wr3-editorial-bench`.
- `canva_renderer` legacy vs `canva_renderer_v2`; il codice moderno importa v2, ma riferimenti legacy restano in script/test.
- `wa-mirror` vs `wa-mirror-launcher`; solo launcher live, il README chiarisce che `wa-mirror` non e reply bot ma capture bridge verso CRM.
- Namespace launchd `com.balizero.*` vs `com.nuzantara.*` con orphan dup e nessun reconciliation job.
- Chat frontend frammentate: gateway/terminal/workspace assistant per team, `ZantaraFAB` pubblico morto, widget completo solo in backup, web chat graph-engine separata, KBLI chat separata.
- Multi-LLM council duplicati: `research/consiglio_orchestrator.py`, `cognitive/oracle.py`, `council/tone_council.py`, `federation_alerts` che incorpora Consiglio senza primitiva comune.

Il problema non e la mancanza di agenti. E l'assenza di un livello di contratto che dica: chi possiede la funzione, quali input/output sono validi, quali agenti sono alias, quali sono deprecated, quali metriche provano che vive.

### Opportunita: Agent Contract Registry + Duplicate Reconciler

Creare un registro operativo, non documentazione aspirazionale:

- `agent_id`, `domain`, `owner_lane`, `runtime` (`launchd`, CLI, backend service, frontend component, MCP chain), `entrypoint`, `input_schema`, `output_schema`, `approval_mode`, `pii_policy`, `last_seen`, `health_probe`, `replacement_for`, `deprecated_by`.
- Un test/cron `agent_contract_reconciler` che fallisce se:
  - due agenti dichiarano stesso `domain+capability` senza rapporto `variant_of` o `deprecated_by`;
  - un LaunchAgent live non ha contract;
  - un contract ha 0 importer, 0 launch label e 0 CLI entrypoint;
  - un frontend copilot/chat non ha backend contract associato.
- Primitive condivise da estrarre:
  - `BriefGrounder` per WR2/WR3.
  - `ExternalBench` per design/video/editorial benchmark.
  - `CouncilService` per Consiglio/Oracle/Tone/Federation alerts.
  - `ChatStreamContract` per FAB, portal assistant, KBLI chat, graph-engine web chat.
  - `LaunchNamespaceReconciler` per `com.balizero.*` / `com.nuzantara.*`.

### ROI e misure

- ROI: alto, per riduzione drift e bug organizzativi.
- Metriche before/after:
  - duplicati Fase 1: D1-D6 -> 0 non governati;
  - LaunchAgent senza contract -> 0;
  - frontend chat surfaces senza backend owner -> 0;
  - test di import/health per ogni agent contract in CI;
  - manutenzione: ogni deprecazione ha `safe_remove_plan` e prova di 0 importer.
- Effort: 2-4 giorni per registry + reconciler iniziale; 1-2 settimane per normalizzare WR2/WR3, council e chat surfaces.

---

## 8. Document-AI / OCR per Akta, KITAS, Company Docs

### SOTA 2026

Il pattern SOTA documentale non e "OCR poi LLM libero". E pipeline ibrida:

1. **Conversione layout-aware.** Docling, Google Document AI, Azure AI Document Intelligence, AWS Textract, Mistral OCR e VLM moderni estraggono testo, tabelle, layout, immagini, checkbox, firme o campi specifici. Il documento diventa Markdown/JSON strutturato con provenance.
2. **Schema extraction + confidence.** I campi critici devono uscire in schema versionato: tipo documento, nome, passaporto/NIK, date, scadenze, azienda, KBLI, capitale, indirizzi, firme, missing pages. Ogni campo deve avere source span/page, confidence e validation rule.
3. **Human review per decisioni legali.** Google Document AI Workbench e servizi enterprise includono review/human-in-the-loop. Per immigration/company setup e un requisito operativo: l'agente propone, Zero/team decide.
4. **Benchmark su documenti reali.** OmniDocBench e benchmark simili mostrano che testo, tabelle, formule, layout e lingue diverse restano variabili difficili. Per Nuzantara serve eval locale su akta, paspor, KITAS, NIB/OSS, NPWP, PKKPR, SK, invoice.
5. **Privacy-by-design.** Per Law 2, i documenti sensibili vanno prima processati localmente o redatti. Cloud OCR puo entrare solo con consenso/allowlist o su estratti sanitizzati.

### Fit Nuzantara

Fase 1/code-read mostra pezzi gia presenti ma non una catena agente end-to-end:

- `crm_guardian/ocr.py` usa vision via subprocess.
- `multimodal/pdf_vision_service.py` esiste come servizio PDF/vision.
- `wa_copilot/extraction_pipeline.py` usa Ollama locale `qwen3.5:9b`.
- wa-mirror cattura media e puo collegare WhatsApp -> CRM, ma non e reply bot e non governa l'intero ciclo documentale.
- G1 Fase 1: quoting cliente non affidabile; G11: nessun agente possiede CRM mutation/Guardian hygiene; G13: test non coprono drift backend-script/manifest-registration.
- Frontend cliente non ha copilot documentale: portale solo messaggistica umana, nessuna triage AI visibile al cliente.

### Opportunita: Akta/OCR Triage Agent

Costruire un agente verticale, locale-first, che non decide legalmente ma trasforma caos documentale in queue verificabile.

Flusso proposto:

1. **Ingest locale** da WhatsApp media, portale upload, Drive shortcut o cartella watched.
2. **Classifier**: `passport`, `akta`, `SK Kemenkumham`, `NIB/OSS`, `NPWP`, `KITAS`, `KITAP`, `photo`, `bank statement`, `lease`, `invoice`, `unknown`.
3. **Extractor schema-based**:
   - persone: full name, DOB, nationality, passport number, expiry;
   - company: PT/PMA name, deed number, notary, shareholders, directors, KBLI, capital, domicile;
   - immigration: visa type, sponsor, expiry, permit number;
   - evidence: page, bbox/span, OCR confidence.
4. **Validator**:
   - missing required doc per practice type;
   - expiry/deadline risk;
   - mismatch between CRM person/company and document fields;
   - low-confidence fields -> human review.
5. **Human approval UI** in team workspace/CRM Guardian, then write allowlisted fields only.

Implementation shape:

- Use local OCR/VLM first for PII-heavy docs. Keep optional adapters for Google Document AI/Azure/Textract/Mistral behind `DocumentExtractorProvider`, disabled unless configured.
- Persist extracted fields in a staging table, not directly into CRM.
- Every field has `source_document_id`, `page`, `span_or_bbox`, `confidence`, `extractor_version`, `approved_by`.
- Add document eval set: 20-50 redacted/synthetic docs per type, golden fields, false-accept threshold.

### ROI e misure

- ROI: alto. Manual document triage is repeat-heavy and legally risky.
- Primary metrics:
  - minutes per document before/after;
  - auto-classification accuracy;
  - field exact-match on golden docs;
  - false accept rate for critical fields, target 0 before CRM write;
  - percent practices with complete checklist within 24h;
  - reduction of "please resend/missing doc" loops.
- Effort: 1 week MVP classifier + staging extraction for 3 doc types; 3-5 weeks production with UI, eval set, approval gate, providers.

---

## 9. Browser / Computer-Use Agents per Portali Governativi Indonesiani

### SOTA 2026

Browser/computer-use e utile ma fragile. Lo stato dell'arte maturo segue queste regole:

1. **Preferire API/deterministic automation quando esistono.** Un browser agent e ultima interfaccia quando portale non espone API.
2. **Ambiente controllato.** Anthropic Computer Use e OpenAI computer-use richiedono sandbox, screenshot/action loop e safeguards contro prompt injection. Non si lascia un agente libero sul desktop principale.
3. **Playwright-first per web ripetibile.** Playwright MCP fornisce automazione browser via accessibility snapshot e tool strutturati, piu stabile di click coordinate pure. Per portali governativi serve ricetta deterministica con fallback agentico, non agent libero.
4. **Human-in-the-loop durevole.** Login, submit, pagamento, invio documento e modifica pratica devono essere checkpoint approvati. Il browser agent puo preparare, leggere, precompilare, ma non finalizzare senza Law 5.
5. **Benchmark reali mostrano il limite.** WebArena, WebVoyager, WorkArena, OSWorld e BrowserGym esistono proprio perche i task browser/GUI sono difficili, dinamici e facili da rompere. Bisogna misurare task success, non fidarsi di demo.

### Fit Nuzantara

Fase 1 trova una lacuna netta:

- MCP deterministic chains sono code-complete ma nessuna auto-invocata.
- `federation_orchestrator.py` e on-demand, idle, senza checkpointer, con `input()` bloccante.
- `organism.supervisor` ha consumato 92k eventi Redis ma ha attuato zero: shadow brain.
- Frontend browser automation e stato incerto/rotto in Fase 1, con riferimenti banned/legacy.
- Portali client-facing non hanno copilot; portali governativi restano lavoro manuale ad alto valore.

### Opportunita: Portal Copilot Runner

Non creare subito un "agente che fa tutto". Creare un runner con ricette e checkpoint:

Domain iniziali:

- OSS/BKPM status check e prefill NIB/KBLI.
- Imigrasi status check per permit/visa.
- DJP/NPWP read-only lookup o download documenti dove legalmente permesso.
- Company registry/Kemenkumham read-only document/status verification.

Architettura:

- `portal_recipe.yaml`: steps deterministici, selectors, expected page states, screenshots required.
- `PortalSession`: browser isolated profile, credential access via vault/manual unlock, no shared desktop cookies by default.
- `StateDetector`: LLM/VLM solo per classificare stato pagina o recuperare label quando selector cambia.
- `Checkpoint`: `READ`, `PREFILL`, `SUBMIT`, `PAY`, `SEND_MESSAGE`. Solo `READ/PREFILL` automatizzabili in MVP; gli altri richiedono approvazione esplicita.
- `EvidencePack`: screenshot, DOM snapshot/accessibility snapshot, timestamp, portal URL, extracted status, run trace.
- `Replay/Eval`: ogni ricetta ha test su mock portal e, dove possibile, dry-run su account sandbox.

### ROI e misure

- ROI: alto ma con rischio operativo alto. L'MVP deve essere read-only.
- Primary metrics:
  - status-check success rate;
  - manual minutes saved per portal session;
  - number of portal drift incidents caught by recipe smoke test;
  - zero unauthorized submit/pay/send;
  - evidence pack completeness for each run.
- Effort:
  - 3-5 giorni: one read-only status checker with screenshot evidence.
  - 2-3 settimane: recipe DSL + 3 portals + HITL dashboard.
  - 1-2 mesi: robust prefill, credentials, visual drift eval, operator training.

---

## 10. Voice / WhatsApp Agents

### SOTA 2026

WhatsApp e voice nel 2026 convergono su un pattern ibrido:

1. **WhatsApp Flows per dati strutturati.** Meta Flows consente esperienze end-to-end dentro WhatsApp per form, booking, lead qualification, checklist. E piu affidabile di chiedere a un LLM di fare intake libero.
2. **Cloud API + templates + webhooks.** Il canale enterprise va gestito con template approvati, finestre conversazionali, webhook idempotenti, opt-in e logging.
3. **LLM copilot, non auto-reply legale.** Per immigration/tax/company setup, l'agente dovrebbe sintetizzare, estrarre, suggerire e preparare Flow/link/template. Invio finale approvato dal team.
4. **Voice notes as first-class input.** In WhatsApp reale molti utenti mandano audio. SOTA pratico: trascrizione, lingua detection, diarization leggera, entity extraction, summary, draft response.
5. **Realtime voice solo dove ha senso.** OpenAI Realtime/voice agents e Twilio ConversationRelay abilitano voice agent bassa latenza, ma per Bali Zero il primo ROI e voice-note -> task/CRM, non call-center autonomo.

### Fit Nuzantara

Fase 1/code-read:

- WhatsApp channel esiste tra i canali live.
- wa-mirror e vivo come capture bridge, non reply bot.
- `wa_copilot/extraction_pipeline.py` usa LLM locale per estrazione.
- Dashboard WA mostra `suggested_message_draft` statico, non un copilot generativo governato.
- Frontend pubblico ha `ZantaraFAB` morto; widget SSE + auto CRM lead esiste solo in backup.
- Portale cliente non ha copilot, mentre team workspace ha assistant su ogni pagina.

Questo e il gap ROI piu immediato: il canale principale vive, ma il cervello non e collegato in modo sicuro all'azione.

### Opportunita: WA Operator Copilot + Flow Pack

Funzionalita MVP:

- Thread summary in CRM: situazione, intento, urgency, missing docs, next best action.
- Reply draft con policy guardrails: visa/pricing solo da tool/reference, uncertainty disclaimer, no legal finality.
- Lead qualification: budget, timeline, nationality, service type, location, company/property status.
- WhatsApp Flow links:
  - visa intake;
  - PT/PMA company setup intake;
  - document upload checklist;
  - appointment scheduling;
  - renewal/KITAS expiry check.
- Voice note processing:
  - transcribe locally when PII-sensitive;
  - summarize and extract entities;
  - attach transcript to CRM staging;
  - generate draft reply for human approval.
- Send gate: never auto-send; operator clicks approve/edit/send.

Implementation notes:

- Use wa-mirror as ingestion spine.
- Create `conversation_event` -> `copilot_suggestion` queue.
- Reuse `wa_copilot/extraction_pipeline.py`, but add schema, eval and approval.
- One `ChatStreamContract` should power team WA copilot, public FAB, portal copilot and KBLI chat to avoid another fragmented frontend.

### ROI e misure

- ROI: very high, because WhatsApp is the main commercial/ops interface.
- Primary metrics:
  - average first-response preparation time;
  - accepted draft rate;
  - edit distance from draft to sent message;
  - lead qualification completeness;
  - missing-doc loop count per practice;
  - number of CRM fields staged/approved from WA per week;
  - conversion from public FAB/Flow to CRM lead.
- Effort:
  - 3-5 giorni: operator-only draft + summary on captured WA threads.
  - 1-2 settimane: Flows for 2 service lines + voice note transcription.
  - 3-4 settimane: portal/FAB unification and analytics.

---

## 11. Predictive Agents: Churn, Upsell, Deadline Sentinel

### SOTA 2026

Predictive agents should not be "LLM predicts churn from vibes". The reliable pattern:

1. **Deterministic rules for legal deadlines.** Visa expiry, KITAS/KITAP renewals, tax deadlines, company reporting and document validity are rule calendars first.
2. **Calibrated ML for ranking.** Survival/time-to-event, gradient boosted trees, calibrated probabilities and uplift/propensity models are better than free-form LLM for churn/upsell risk.
3. **LLM as explanation and action composer.** The LLM explains why a client is on the queue, drafts a message, checks policy, and proposes next step. It does not own the probability.
4. **Monitoring and drift.** Calibration, feature drift, label leakage and seasonality must be tracked. Evidently/OTEL-style monitoring can catch silent decay.
5. **Human queue, not autonomous outreach.** In legal/immigration services, risk score becomes a review queue. Team decides before contact.

### Fit Nuzantara

Fase 1 gaps:

- G3 competitor/revenue intelligence still manual; `competitor-monitor` and `yield-optimizer` never used.
- G5 MCP chains exist but no autonomous scheduler.
- G11 no agent owns CRM mutation/Guardian hygiene.
- G1 client quoting no trustworthy automation.
- Compliance/calendar machinery exists but is not surfaced as a predictive action queue.
- Frontend client portal is not proactive about deadlines or missing docs.

Nuzantara has enough event exhaust for useful prediction: CRM practice status, WhatsApp cadence, document completeness, payment/invoice signals, service type, deadlines, KBLI/company metadata, portal messages, escalation history.

### Opportunita: Revenue & Deadline Sentinel

Two-layer system:

1. **Deadline engine**:
   - deterministic rules per visa/practice/company/tax type;
   - source-of-truth document expiry from OCR/staged CRM;
   - severity: `expired`, `due_7d`, `due_30d`, `missing_required`, `blocked_by_client`, `blocked_by_team`.
2. **Predictive ranking**:
   - churn risk for active clients;
   - renewal likelihood;
   - upsell propensity: KITAS -> KITAP, PT/PMA add-ons, tax/accounting, property legal support;
   - high-value dormant leads.

Output:

- Daily operator queue: `why_now`, evidence, risk score, recommended action, draft message.
- No auto-contact.
- Every accepted/rejected action becomes feedback label.

Modeling approach:

- Start with rules + logistic/GBM baseline.
- Add survival model for time-to-renewal/time-to-churn.
- Calibrate probabilities and monitor drift.
- LLM only for explanation/draft generation, using cited evidence.

### ROI e misure

- ROI: high, because it catches revenue and compliance leakage.
- Primary metrics:
  - overdue practice count;
  - renewal outreach lead time;
  - recall@K for renewals/churn among top daily queue;
  - accepted recommendation rate;
  - revenue influenced by accepted sentinel actions;
  - false alarm rate per operator hour.
- Effort:
  - 1 week: deterministic deadline queue.
  - 2-3 weeks: first calibrated risk model with feedback capture.
  - 4-6 weeks: production dashboard + monitoring + CRM writeback approval.

---

## 12. Agent Evals / Observability

### SOTA 2026

Agent evals moved from "final answer score" to trajectory and operations:

1. **Trace every run.** OpenAI Agents SDK tracing, LangSmith, Langfuse, Phoenix and OpenTelemetry GenAI conventions all converge on run/tool spans, inputs/outputs, latency, token/cost and metadata.
2. **Trajectory eval.** LangSmith agent evaluators, tau-bench, ToolSandbox and related work evaluate whether the agent used the right tools in the right order, respected policy, mutated DB correctly and handled user changes.
3. **Task completion plus policy.** For Nuzantara, a correct answer that violates Law 2, pricing source, visa disclaimer or approval gate is failure.
4. **Cost and latency are first-class.** "AI Agents That Matter" argues cost-controlled evaluation is mandatory; multi-agent workflows must prove net utility.
5. **Prod sampling + CI gates.** Evals should run in CI on fixtures and in production on sampled traces, with redacted payloads and local-only sensitive data.

### Fit Nuzantara

Fase 1 shows observability is partial and not closing the loop:

- `agent-library-evolver` stuck at generation 0, `DEEPSEEK_API_KEY` missing, failed runs.
- `wr3.reflexion` dead at launch with codesigning/interpreter failure.
- `wr2.reflexion` alive but starved, `carousel_runs=0`.
- `federation_orchestrator.py` has no checkpointer, no scheduler, idle, blocking `input()`.
- `organism.supervisor` consumed 92k Redis events but actuated zero.
- G7: no daemon-level dependency/model/plist-health enforcement.
- G13: tests do not catch backend-script and manifest-registration drift.
- LangSmith/Ragas-style pieces exist but do not gate these failures.

This is the root cause behind "sophisticated architecture, loop not closed": no common trace/eval/health contract defines alive, useful and improving.

### Opportunita: Agent Observatory + Trajectory Eval Gate

Create one observability spine for all agentic entities.

Run schema:

- `trace_id`, `agent_id`, `contract_version`, `runtime`, `lane`, `task_type`, `pii_class`, `input_digest`, `tool_calls`, `approval_checkpoints`, `output_digest`, `cost`, `latency`, `success`, `failure_reason`, `artifact_paths`, `human_feedback`.

Eval suites:

- **WA copilot eval:** correct classification, safe draft, no auto-send, pricing/visa source compliance.
- **Document OCR eval:** golden field extraction, confidence calibration, no CRM write without approval.
- **Browser portal eval:** follows recipe, captures evidence, stops at submit/pay checkpoint.
- **MCP chain eval:** deterministic chain invoked with expected side effects in sandbox.
- **Council eval:** compares council outputs without duplicate tool cost.
- **Self-improvement eval:** a skill/library change only merges if benchmark improves and cost/regression gates pass.

Health probes:

- LaunchAgent active/loaded/log-mtime/import smoke.
- Python venv/interpreter existence for each agent.
- Required env presence without exposing secret values.
- "Alive but idle" detection: a daemon consuming events but producing zero actions/drafts/alerts is degraded, not healthy.

Implementation:

- Start with local JSONL/SQLite trace sink to avoid external PII leakage.
- Add OpenTelemetry GenAI-compatible fields for future export.
- Export sanitized summaries to LangSmith/Langfuse/Phoenix only when allowed.
- Add CI command: `python scripts/agent_eval_gate.py --changed`.
- Add daily report: broken agents, duplicate agents, cost per accepted outcome, eval failures.

### ROI e misure

- ROI: foundational. It prevents silent dead loops and justifies which agents survive.
- Primary metrics:
  - percent agent runs traced;
  - percent active agents with health probe;
  - mean time to detect dead daemon;
  - eval pass rate by domain;
  - cost per accepted recommendation/action;
  - number of stale/idle agents quarantined safely;
  - self-improvement frontier generation moves from 0 to >0 only with regression-proof benchmark.
- Effort:
  - 3-5 giorni: trace schema + local sink + health probes for 10 critical agents.
  - 2 settimane: trajectory eval gate for WA/doc/browser/MCP.
  - 1 mese: full observability dashboard and merge gate for self-improvement.

---

## Priorita Codex per FASE 3

1. **Creare Agent Observatory + Contract Registry prima di nuovi agenti.** Senza contratti e trace, ogni nuovo agente aumenta entropia.
2. **Merge/elimina duplicati WR2/WR3 brief+bench e canva v1/v2.** Sono duplicati misurabili e a basso rischio se prima si aggiunge contract/import check.
3. **WA Operator Copilot e Akta/OCR Triage sono i due game-changer piu vicini al fatturato.** Sono agganciati a canali gia vivi.
4. **Portal Copilot deve partire read-only.** Browser agents sono potenti ma fragili: prove, screenshot, checkpoint, no submit/pay.
5. **Predictive Sentinel deve usare regole+ML calibrato, non LLM prediction.** LLM solo per spiegazione e draft.

## Fonti primarie e riferimenti esterni

- Anthropic, "Building effective agents": https://www.anthropic.com/engineering/building-effective-agents
- Anthropic Computer Use docs: https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/computer-use-tool
- OpenAI Agents SDK: https://openai.github.io/openai-agents-python/
- OpenAI Agents SDK handoffs: https://openai.github.io/openai-agents-python/handoffs/
- OpenAI Agents SDK tracing: https://openai.github.io/openai-agents-python/tracing/
- OpenAI computer-use guide: https://platform.openai.com/docs/guides/tools-computer-use
- OpenAI Realtime guide: https://platform.openai.com/docs/guides/realtime
- LangChain multi-agent docs: https://docs.langchain.com/oss/python/langchain/multi-agent
- Microsoft AutoGen docs: https://microsoft.github.io/autogen/
- Model Context Protocol specification: https://modelcontextprotocol.io/specification/2025-03-26
- Google Agent2Agent documentation: https://google-a2a.github.io/A2A/latest/
- Google A2A announcement: https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/
- Google Cloud Document AI docs: https://cloud.google.com/document-ai/docs
- Google Cloud custom extractor docs: https://cloud.google.com/document-ai/docs/create-custom
- Azure AI Document Intelligence docs: https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/
- AWS Textract AnalyzeDocument API: https://docs.aws.amazon.com/textract/latest/dg/API_AnalyzeDocument.html
- AWS Textract Queries: https://docs.aws.amazon.com/textract/latest/dg/queries.html
- Mistral OCR/document understanding docs: https://docs.mistral.ai/capabilities/document/
- IBM Docling: https://github.com/docling-project/docling
- IBM Docling docs: https://docling-project.github.io/docling/
- Meta WhatsApp Flows docs: https://developers.facebook.com/docs/whatsapp/flows
- Meta WhatsApp Cloud API send messages: https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-messages
- Twilio ConversationRelay docs: https://www.twilio.com/docs/voice/twiml/connect/conversationrelay
- OpenTelemetry GenAI semantic conventions: https://opentelemetry.io/docs/specs/semconv/gen-ai/
- LangSmith evaluation concepts: https://docs.smith.langchain.com/evaluation/concepts
- LangSmith agent evaluation guide: https://docs.smith.langchain.com/evaluation/how_to_guides/agents
- Langfuse tracing docs: https://langfuse.com/docs/tracing
- Arize Phoenix docs: https://docs.arize.com/phoenix/
- Ragas docs: https://docs.ragas.io/
- DeepEval agentic metrics: https://docs.confident-ai.com/docs/metrics-agentic
- scikit-learn probability calibration: https://scikit-learn.org/stable/modules/calibration.html
- scikit-survival user guide: https://scikit-survival.readthedocs.io/en/stable/user_guide/
- lifelines documentation: https://lifelines.readthedocs.io/
- XGBoost survival AFT tutorial: https://xgboost.readthedocs.io/en/stable/tutorials/aft_survival_analysis.html
- Evidently AI docs: https://docs.evidentlyai.com/
- arXiv, "AI Agents That Matter": https://arxiv.org/abs/2407.01502
- arXiv, "tau-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains": https://arxiv.org/abs/2406.12045
- arXiv, "AgentBench: Evaluating LLMs as Agents": https://arxiv.org/abs/2308.03688
- arXiv, "WebArena: A Realistic Web Environment for Building Autonomous Agents": https://arxiv.org/abs/2307.13854
- arXiv, "WebVoyager": https://arxiv.org/abs/2401.13919
- arXiv, "WorkArena": https://arxiv.org/abs/2403.07718
- arXiv, "OSWorld": https://arxiv.org/abs/2404.07972
- arXiv, "BrowserGym": https://arxiv.org/abs/2407.08142
- arXiv, "OmniDocBench": https://arxiv.org/abs/2409.07626

## Local evidence anchors

- `research/agent-craft/census-raw/phase1-synthesis.md`: macro-groups, duplicates D1-D6, global gaps G1-G13.
- `research/agent-craft/census-raw/zone-frontend.md`: public FAB dead, portal without copilot, fragmented chat surfaces.
- `research/agent-craft/census-raw/zone-channels-services.md`: channels, wa-copilot, OCR/vision services, council duplication, CRM shim sprawl.
- `research/agent-craft/census-raw/zone-meta-orchestration.md`: federation orchestrator no checkpointer/scheduler, agent-library-evolver generation 0, WR2/WR3 reflexion failures.
- Grep direct checks: WR2/WR3 duplicate agent definitions, `canva_renderer_v2` replacing legacy renderer, wa-mirror capture bridge semantics, static `suggested_message_draft` in WA dashboard.
