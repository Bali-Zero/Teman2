---
date: 2026-07-14
domain: operations
client_case: none
sources: ["workflow scheduler-necropsy wf_380e0d6c (21 agents: 12 task investigators + disable-history archaeologist + adversarial refuters on every RESURRECT/RETIRE verdict + synthesis)", "apps/backend-rag/backend/services/misc/autonomous_scheduler.py", "apps/backend-rag/backend/app/setup/service_initializer.py", "git log/blame service_initializer.py"]
adversarial_review: gemini
---

## Adversarial review

Two layers, none of the objections survived (10 raised in first external pass, 0 in second):

1. **Inside the workflow**: every RESURRECT/RETIRE verdict was refuted by an independent verifier
   agent and coverage claims were re-executed against repo ground truth (5+ "covered by X" comments
   proven FALSE, W82).
2. **External seat — Gemini via `agy`**: re-attacked all 12 per-task claims against grepped worktree
   evidence. First pass: FAIL with 10 objections — 7 were evidence-starved by the prompt (not wrong
   on the merits), 3 misreads; second pass with the full evidence pack: **12/12 CONFIRMED-SOUND,
   VERDICT: PASS**. Key empirical confirmations: scheduler call commented at
   `service_initializer.py:1363`; `run_incremental_extraction` exists / `run_incremental_update`
   never did; `GoldenRouterService` instantiated only in tests; renewals coverage real at
   `scripts/crm_automation_engine.py:567`; §10d guardian live; §10e per-machine scope deliberate.
   Codex seat attempted first but silent-dead on both MCP (30min) and CLI (10min) — cascade fell to
   Tier 2 per doctrine.

# AutonomousScheduler necropsy — triage of 12 tasks on an engine dead since 2026-02-11

> Implementation PR: scheduler-necropsy (branch `backend-rag-scheduler-necropsy`). Companion memory:
> `ops_wa_subscription_guardian_shipped_2026_07_14.md` (how the corpse was discovered: the WABA
> guardian's Redis lock never appeared post-deploy because `_init_background_services` is commented
> out in service_initializer §10 — "omnichannel stabilization", 2026-02-11).

# Triage — AutonomousScheduler morto (spento dal 2026-02-11, service_initializer.py:1363-1364)

## 1. Tabella per-task

| Task | Verdetto | Copertura verificata? | Rischio se resta morto |
|---|---|---|---|
| `auto_ingestion` | **RETIRE** (blocco scheduler; NON cancellare la classe — vedi Piano) | ❌ FALSA (W82): `intel.nightly` scrive in `intel_articles`, non nelle 4 collection RAG (`kbli_2025_final`/`visa_oracle`/`tax_updates`/`legal_updates`) | Basso (codice mai funzionante: `scrape_source` crasha, `ingest_content` è stub fake-success). Gap vero: nessun refresh automatico delle collection RAG — oggi solo regen manuali |
| `self_healing` | **RESURRECT (ridotto)**: solo GCAction + visibilità `/api/admin/self-healing/stats` | ❌ NOT_FOUND per il gc; ✅ redis-reconnect GIÀ coperto da `redis_manager._reconnect_loop` (sempre attivo) | Basso-moderato: OOM già morso (fly.toml 2GB→3GB, W60); unico `gc.collect()` del backend è qui |
| `conversation_trainer` | **OPERATOR_DECISION** (A13 aperta dal 2026-07-05) | ❌ "migrato a OpenClaw" mai materializzato (`jobs.json.migrated`, grep vuoto) | Quasi zero: mai eseguito una volta (total_runs=0). Solo cron-theater sugli endpoint `/status` |
| `golden_routes_seeder` | **RETIRE** | ❌ NOT_FOUND — e il consumer `GoldenRouterService` non è mai istanziato nell'app | Nullo: seminerebbe righe che nessuno legge, con `document_ids=[]` mai popolati |
| `renewal_alerts` | **COVERED** | ⚠️ Claim letterale ("practice-lifecycle-check") FALSO; copertura reale = `crm_automation_engine.py` modulo "renewals" (crontab Pro 23:00 UTC, verificato forense 2026-06-02, non ri-provato oggi) | Basso — ma zero rete di sicurezza se quel crontab muore (famiglia #1/#2) |
| `birthplace_enrichment` | **ESCALATE → Zero** (NEEDS-ANTONELLO già aperto da S12, 2026-06-02) | ❌ NOT_FOUND; DB live: 945 candidati, 0 arricchiti EVER | Basso: fronzolo cosmetico; consumer (birthday email) degrada a "" senza crash |
| `birthday_notifier` | **KEEP_DEAD** — kill intenzionale di Zero, 2026-07-12 (PR #2293: "no autonomous outbound to client") | ✅ Copertura ESISTEVA (`.github/workflows/cron-notifiers-birthday.yml`, viva 04/24→07/12) poi DISARMATA deliberatamente; `workflow_dispatch` manuale resta | Accettato per decisione: re-arm = decisione R3 ratificata, non un default |
| `conversation_cleanup` | **COVERED** | ✅ VERIFIED_ALIVE: endpoint `POST /api/admin/conversation-cleanup` registrato in prod + cron OpenClaw "agent" tier (ri-verificato `crontab -l` Pro 2026-07-11 nel drift-ledger) | Quasi zero. ⚠️ drift retention: docs dicono 7d/30d, endpoint live fa 30d/90d — rilevante per review UU PDP |
| `daily_ops_autopilot` | **RETIRE** | ❌ NOT_FOUND: OpenClaw cron congelato 04-30, heartbeat zombie archiviato 05-19; e il codice POSTava a una route HTTP che il server MCP (stdio-only) non ha mai esposto | Basso; expiry-reminder coperto da `scripts/expiry_alerter.py`. Gap residuo (auto-articoli intel, digest ops giornaliero) = build nuova, decisione business |
| `drive_changes_poll` | **COVERED** | ✅ VERIFIED_ALIVE: process group Fly dedicato `drive_poll_worker` (fly.toml:33), heartbeat DB 2026-07-14T02:59Z, monitor GH Actions 15min | Nullo. Residuo: comment "Air cron" stale + wrapper OpenClaw in 4xx da ritirare |
| `kg_incremental_builder` | **OPERATOR_DECISION** (A13 aperta) | ❌ NOT_FOUND — nessun cron/plist da nessuna parte | Slow-burn: KG 108K nodi senza feeder, 30K+ chunk non processati; freshness drift (W90). **Bug latente**: scheduler chiama `run_incremental_update()` che NON esiste (il metodo è `run_incremental_extraction`) — qualunque ARM crasha al primo tick |
| `wa_subscription_guardian` | **RETIRE** (solo la registrazione scheduler morta) | ✅ VERIFIED_ALIVE: path vivo §10d in `initialize_services()` (PR #2423, merged, 23/23 test) — gemello dormiente intenzionale | Zero per il canale WA. Solo debito di leggibilità |

## 2. Meta-pattern — la malattia unica

**Scar famiglia #2 "esiste ≠ armato", in due strati:**

1. **Motore spento senza data di scadenza**: il disable del 2026-02-11 era un fence di rollout ("omnichannel stabilization"), non un incidente. Il fence non è mai stato rimosso né riesaminato: 12 task hanno continuato ad accumularsi/esistere su un motore che nessuno ha notato essere off per 5 mesi. La credenza difettosa: *registrare un task = averlo armato*.
2. **Claim-rot W82 nei commenti**: 5+ commenti "covered by X / migrated to Y" dove X/Y non esiste (client-health-monitor), è morto (OpenClaw cron, Air), o copre un'altra cosa (intel_articles ≠ collection RAG). I commenti di copertura non sono mai stati verificati contro il ground truth — sono asserzioni, non prove.

Corollario positivo: il pattern §10b/§10d (estrazione per-task sul path vivo) è l'antidoto già validato due volte.

## 3. Piano

### RESURRECT (1 solo)
- **`self_healing` (ridotto)**: estrazione per-task in `service_initializer.py` sul modello §10d — asyncio task standalone + `_acquire_task_lock` Redis (import diretto da autonomous_scheduler.py:87, come fa il WA guardian). Scope: `GCAction` + `set_active_agent()` per rendere vivo `/api/admin/self-healing/stats`. **Nella stessa PR**: rimuovere/riparare l'OrchestratorReporter — il target `nuzantara-orchestrator.fly.dev` non esiste (`fly apps list`: solo 2 app). NON portare ReconnectCacheAction (già coperto da `redis_manager`) né RestartServiceAction (no-op corretto, Fly supervisiona). **NON rianimare `_init_background_services` in blocco** — 5 mesi di drift non esercitato + stesso pattern connection-holding del crash asyncpg di aprile.

### RETIRE (cosa cancellare)
- **`auto_ingestion`**: cancellare SOLO il blocco di registrazione (autonomous_scheduler.py:317-365). ⚠️ `AutoIngestionOrchestrator` è importato a livello modulo da `routers/agents.py:28,48` (router montato live): cancellare la classe = crash al boot. O sventrare il fake-success di `ingest_content` lasciando la classe importabile, o rimuovere classe + i 2 endpoint placeholder di agents.py nella STESSA change.
- **`golden_routes_seeder`**: cancellare il blocco (righe 452-541). Follow-up separato: `GoldenRouterService` + tabella `golden_routes` orfani (wire-or-delete, call architetturale).
- **`daily_ops_autopilot`**: cancellare TASK 11 (righe 714-759); `chain_daily_ops_autopilot` MCP da ritirare dopo verifica non-uso altrove. `expiry_alerter.py` resta unico owner dei reminder.
- **`renewal_alerts`** (post-COVERED): cancellare il blocco morto (543-621) + correggere il commento falso "practice-lifecycle-check".
- **`wa_subscription_guardian`**: cancellare `register_whatsapp_subscription_guardian` + call site (816-834) — il path vivo §10d resta intatto. In alternativa, riga TECH-DEBT in PENDING-ARMS.
- **Igiene commenti**: correggere i claim stale ("Air cron" in drive_poll, docstring migrazioni OpenClaw) + fix docs retention conversation_cleanup (7/30 → 30/90).

### Motore
Lasciare `create_and_start_scheduler` spento; la sua sorte complessiva resta dietro la ledger A13 (PENDING-ARMS:63), non un flip di lato.

## 4. Solo-operatore (decisioni business per Zero)

1. **A13 (aperta dal 05/07)** — ARM/RETIRE per: `conversation_trainer` (revive richiede rebuild: push+PR vera, cron Pro, persistenza `agent_executions`) e `kg_incremental_builder` (se ARM: fixare prima il bug `run_incremental_update` inesistente; è l'unico feeder del KG da 108K nodi).
2. **`birthplace_enrichment`** — NEEDS-ANTONELLO di S12 ancora aperto: revive su Mini con Ollama vs retire formale (+ birthday email resta senza personalizzazione).
3. **`birthday_notifier`** — nessuna azione: kill ratificato da Zero il 12/07. Eventuale re-arm = decisione R3 esplicita.
4. **Gap RAG-freshness** (emerso da auto_ingestion): nessun processo automatico tiene fresche le collection KBLI/visa/tax/legal da fonti ufficiali — oggi solo regen manuali curate. Costruire una pipeline ingestion-with-review è una call prodotto/compliance (auto-embedding di testo governativo non revisionato in un KB che dà consigli legali/fiscali), da scopare come lavoro nuovo, non flag-flip.
5. **Nota**: la copertura `renewal_alerts` poggia su un crontab HOME-fork su Pro verificato l'ultima volta 06-02 — vale una ri-prova `crontab -l` e idealmente una dichiarazione in `declared-pairs.json`.
