---
date: 2026-06-11
domain: operations
client_case: none (internal system audit)
sources:
  - 6 area subagents (backend RAG, WA channels, WR2, WR3, guardians/cron, deploy/DB/MCP) — read-only, M5 + ssh Pro
  - direct re-verification of all load-bearing findings on disk in-session (anti-hallucination discipline)
  - SYMBIOSIS.md / CLAUDE.md / VADEMECUM.md / INDEX.md / cicatrix-scars.md
auditor: Fable 5 (claude-fable-5), session 2026-06-11, machine Air-M5
---

# SYSTEM AUDIT — Nuzantara / Bali Zero (2026-06-11)

**Metodo**: 6 agenti di area (backend RAG, canali WA, WR2, WR3, guardiani/cron, deploy/DB/MCP) + verifica diretta dell'orchestratore sui documenti di sistema e su ogni finding load-bearing (ri-letto su disco in questa sessione). Nessuna modifica eseguita durante l'audit. Nessun valore di segreto riportato. Le citazioni `file:line` sono state lette dal tool che le riporta; dove un'affermazione non è stata verificata, è marcata.

## 1. Executive summary

L'organismo è **in salute migliore di quanto le cicatrici suggeriscano**: molti antibody dati per "pending" risultano oggi eseguiti e funzionanti (W38 demotion fatta, EventBus Phase 3 completa con prune cron, zero HOME-fork drift sul bridge WA, migrations senza duplicati, FASE-0 governance armata e fresca, test-matrix W73 shippata 10/10). Però: **1 leak di credenziale attivo** (token Telegram in chiaro nei log a ogni run), la **produzione WR2 gira su codice 12 commit stale con alert soppressi** (replay esatto della scar dei 32h), il **loop di auto-healing è morto** (41 DLQ terminal, healing=0, 16 guasti reali ignorati), e la famiglia `_guard_*` WhatsApp ha ancora **2 over-match P1 + 1 time-bomb deterministica** che daranno risposte sbagliate ai clienti. Conteggio: **1 P0, 9 P1, ~21 P2, ~16 P3**. Rischio sistemico #1: *risposte clobberate silenziosamente ai clienti WhatsApp* (i guard sbagliano ora in entrambe le direzioni) — perché è l'unico che danneggia direttamente i clienti senza che nessun guardiano lo veda.

In più, un punto di governance: **il contratto Autonomous Ops L2 è formalmente scaduto** per la sua stessa regola (vedi F04).

## 2. Findings (P0 → P3)

### P0 — Sicurezza attiva

**F01 · SICUREZZA · Token Telegram bot in chiaro nei log WR2, leak continuo**
Area: WR2 / Pro. Prova: `scripts/wr2_html_render_apply.py:58` — `logging.basicConfig(level=logging.INFO, ...)` senza silenziare il logger `httpx`; `_ops_alert` usa httpx (riga 73-75) → httpx a INFO logga l'URL completo della Bot API, che contiene il token. Visto in chiaro in `~/logs/wr2-html-apply.log` sul Pro (riga del 2026-06-11 06:10); per effetto del `tail` di audit è ora anche nel transcript della sessione. Famiglia: scar plist-secrets 2026-04-29, P0 cell/.env 2026-06-03.
Fix: (1) `logging.getLogger("httpx").setLevel(logging.WARNING)` — XS, 1 riga; (2) **rotazione del bot token via BotFather** + aggiornamento consumer (la rotazione è l'unica vera remediation). Confidenza: ALTA.

### P1 — Bug seri / produzione degradata / sicurezza

**F02 · SICUREZZA · Google OAuth client_secret hardcoded nel repo**
Area: backend scripts. Prova (valore redatto): `apps/backend-rag/scripts/bulk_populate_clients.py:149-150` — `client_id` e `client_secret = "GOCSPX-…"` letterali. È in git history.
Fix: spostare in env var + **ruotare il client_secret** su Google Cloud Console. S, ~20 min + rotazione. Confidenza: ALTA.

**F03 · BUG · WR2 in produzione su codice 12 commit stale, puller bloccato da diff dirty non committato, alert soppressi (replay scar W55/32h)**
Area: deploy worktree Pro. Prova: `~/Desktop/nuzantara-deploy` su `deploy/main` HEAD `893892a83`, `rev-list HEAD..origin/main` = 12; `~/logs/wr2-deploy-pull.log` ogni ora `deploy worktree unhealthy — dirty=1 (M scripts/wr2_draft_generator.py)` + `alert suppressed (cooldown active)`. Il dirty è +43/-3 di tuning prompt REALE (anti-orphan headline) mai committato — a rischio perdita (famiglia W59) e probabilmente è la mitigazione dei render-failure di F10.
Fix: adottare il diff (commit+PR), ripulire il worktree → il puller riparte da solo. S, ~20 min. Strutturale: digest settimanale degli alert soppressi (proposto in W55, **terza recidiva**, mai costruito). Confidenza: ALTA.

**F04 · GUARDIANO-DISARMATO · Contratto Autonomous Ops L2 formalmente scaduto + l'hook di staleness misura la cosa sbagliata**
Area: governance. Prova: `AUTONOMOUS_OPS.md:17` "active since 2026-04-21" (51 giorni fa); riga 20: ">30 days without a refresh commit → conservative fallback". `git log` sul file: nessun refresh (ultimo commit è un refactor di scope diverso). L'hook SessionStart riporta "file age 17d" — misura il **mtime** (resettato da qualunque edit) invece della data dichiarata, quindi non scatterà mai.
Fix: re-certificazione di Antonello (commit che aggiorna "active since") + fix dell'hook per leggere la data dichiarata. XS+S. Confidenza: ALTA. *Nota: tutte le operazioni L2 correnti girano su un contratto tecnicamente lapsed.*

**F05 · BUG · Guard WhatsApp `_guard_property_zoning_reply`: trigger substring `lease⊂please`, `villa⊂village` — clobbera risposte corrette ai clienti**
Area: canale WA. Prova: `scripts/openclaw_whatsapp_bridge.py:648-649` — `_contains_any(("villa","vila","airbnb")) and _contains_any(("zoning","residential","zone","lease"))` substring nudo. *"I'm buying a villa, can you **please** explain the purchase process?"* → clobberata con la lezione Airbnb/zoning (escape positive-gating irraggiungibile per una risposta corretta). Classe identica al live-proven W68. Il file è in 3 copie byte-identiche (M5/Pro-repo/Pro-HOME, hash md5 verificati identici) — il fix va in entrambe le copie + restart bridge.
Fix: `_contains_any_word()` (già esiste a riga 227) sul trigger + 2 test matrix. XS. Confidenza: ALTA.

**F06 · BUG · Guard nominee: `"'s name"` e `"atas nama"` clobberano domande banali con la lezione "è illegale"**
Area: canale WA. Prova: `scripts/openclaw_whatsapp_bridge.py:927-928` in `_NOMINEE_DIRECT_TERMS`. *"Can I change my company's name?"* o *"bisa buat faktur atas nama PT saya?"* (fattura intestata) → risposta sostituita con il canonical "this is illegal…". Il fix anti-under-match W73 ha introdotto l'over-match simmetrico.
Fix: co-occorrenza asset/proxy per `"'s name"`; esclusione contesti faktur/invoice/booking per "atas nama". S (~10 righe + 3 test). Confidenza: ALTA.

**F07 · BUG · Instagram adapter: invio senza `raise_for_status` — 4xx/5xx Meta loggato come "✅ Sent", risposta al cliente persa senza DLQ**
Area: canali backend. Prova: `apps/backend-rag/backend/channels/instagram/adapter.py:106-107` — `await self.client.post(...)` senza check status, poi log di successo. Il WhatsApp adapter fa `raise_for_status()` (confronto :183-184). Bonus: versioni Graph API miste (v22.0 send, v18.0 mark-seen, riga 110).
Fix: 1 riga + 1 test MockTransport 400. XS. Confidenza: ALTA.

**F08 · GUARDIANO-DISARMATO · DLQ/auto-heal morto: 41 TERMINAL (25 stale di job già guariti + 16 guasti REALI ignorati), healing=0, autopilot cieco**
Area: cron/Pro. Prova: `~/.agent/decisions/dlq.json` = 41 entry TERMINAL (count ri-verificato); `sentinel_status.json`: `healing_actions_24h=0`; `dlq_autopilot.last.json`: `processed=41 fixed=0`. Cross-check con `state/<job>.last.json`: 25 job oggi `ok` ma mai rimossi dal DLQ; 16 ancora `failed` adesso (qdrant_snapshot, garuda_indexer, garuda_gc, knowledge_graph_builder, spark_alarm, curiosity_loop, run_persona_validate, coverage_trend, sentry_quota_check, nb_agents_daily_dr, run_peraturan_ingestion, run_ops_briefing, nextdns_weekly_digest, auto_test, zantara_vision_warmup, run_gap_scanner_layer_a). Causa-META (W70 #3 mai eseguito): `log_tail` cattura solo "exit 1 after 3 attempts", `classification=UNKNOWN confidence 0.0` → autopilot non può classificare nulla.
Fix: (a) pruning/resurrection delle entry guarite (S); (b) cattura stderr reale nel log_tail (M, ~2-4h — riarma l'intero loop); (c) triage dei 16 vivi (sessione Pro). Confidenza: ALTA.

**F09 · BUG/QUICK-WIN · Backup Qdrant locale rotto da 37 giorni: path Air morto**
Area: cron/Pro. Prova (verificata via ssh): `~/scripts/qdrant-snapshot.sh:21` → `QDRANT_ENV="$HOME/Projects/nuzantara/apps/backend-rag/.env"` (path Air decommissionato 2026-05-05); `qdrant_snapshot.last.json: failed`. W70 antibody #1 eseguito solo a metà (fly_pg_backup e fly_qdrant_backup oggi ok). Altri file con path morto: `launch-strategic-8.sh:12,50`, `qwen-code-review.sh:11` (probabilmente archeologia).
Fix: 1 riga → `$HOME/Desktop/nuzantara/...`. XS. Confidenza: ALTA.

**F10 · FEATURE-NON-CHIUSA · WR2 render che falliscono OGGI mentre i ~16 fix del designer-loop sono fermi su branch non merged**
Area: WR2. Prova: `wr2-html-apply.log` 2026-06-11 06:10 `draft 1ca69dc1 → render_failed: slide 3 did not converge (max_iters reached or not CSS-fixable)`; i fix sono su `agent/nuzantara/wr2/designer-loop-orphan-fix` (~50 test, mai mergiato), e il tuning prompt è il diff dirty di F03. La produzione paga oggi il problema che il lavoro già fatto risolve.
Fix: landing del branch (E2E + PR) + adozione diff F03. M (~½ giornata, lavoro già fatto). Confidenza: ALTA.

### P2 — Incoerenze strutturali / debito / guardiani a metà

**F11 · BUG (time-bomb) · Guard LKPM: finestra "1–15 aprile Q1 2026" hardcoded in 4 punti — decadimento deterministico al prossimo quarter**
Prova: `openclaw_whatsapp_bridge.py:624-631` (whitelist solo varianti aprile), `:586-595` (stale marker "10 july" che clobbererebbe una finestra Q2 legittima "1-10 July"), canonical `:440`, prompt `:186-188`/`:1081`. Quando BKPM annuncia la finestra Q2 (tipicamente luglio), risposte corrette verranno clobberate col canonical di aprile (passato).
Fix: config con `valid_until` + degradazione del guard a stale-markers-only dopo scadenza; estrarre i fatti datati in un blocco `REGULATORY_FACTS` unico (oggi ogni fatto vive in 2-4 copie × 3 file fisici = fino a ~12 punti da toccare per un aggiornamento normativo: LKPM, VAT 11/12%, C2/C12, KBLI villa/cafe, hak milik). S-M. Confidenza: ALTA. **Il finding più urgente del Q3.**

**F12 · BUG · Guard hak_milik content-blind**: gating solo su lunghezza (`:569` `if _reply_word_count(reply) > 125`) — una risposta SBAGLIATA e corta ("Yes, a foreigner can hold Hak Milik through a PMA") **passa**; il test matrix copre solo wrong-AND-long. Fix: negative-gating sul contenuto. S. Confidenza: ALTA.

**F13 · BUG · `villa⊂village` in `_is_villa_kbli_query` (`:259`) e nel ramo `:792`** — domanda KBLI handicraft "in an Ubud village" clobberata col canonical villa 55203. Fix: `_contains_any_word` su `_VILLA_TERMS`. XS. Confidenza: ALTA.

**F14 · BUG (fail-open) · Guard b211: escape `"old"⊂"holders"`, `"lama"⊂"selama"`** (`:530-545`) — risposte UNSAFE ("B211A holders can work…") passano per accidente lessicale. Il fix W72 anti-over-match ha aperto l'under-match. Fix: word-boundary sui marker escape. XS. Confidenza: ALTA.

**F15 · GUARDIANO-DISARMATO · Lint asyncpg W64: 0 violazioni oggi MA ancora ZERO consumer CI/pre-commit** (deferral W35 aperta dal 23/5). Doppia evidenza indipendente: grep `.github/workflows` + `.husky` = zero hit, lint exit 0 reale isolato; E il meta-verifier FASE-0 stesso (`verify_the_verifiers.json`: WARN "lint exists but has NO consumer — gates nothing"). La dinamica che ha generato W64 (sibling-fix regressa lo stesso giorno) è di nuovo possibile. Fix: step in `tests.yml`. XS — **il quick-win più alto-valore dell'audit**. Confidenza: ALTA.

**F16 · FEATURE-NON-CHIUSA · Anti-monotonia P-4 funzionalmente morta: l'unico writer di `topic_type_log` è la lane Canva, spenta dal cutover HTML**
Prova: `INSERT INTO topic_type_log` esiste SOLO in `scripts/wr2_canva_desktop_apply.py` (riga ~267; lane che oggi esce con `enabled != true`); zero occorrenze nella lane HTML (`wr2_html_render_apply.py`, `canva_renderer_v2/_pg.py`). Il reader/soft-steer (`wr2_draft_generator.py:825-872`) leggerà righe sempre più stale; il flag `WR2_ANTIMONOTONE_ENFORCE` (default OFF, attivabile "quando la tabella si riempie", commento `:944-946`) non potrà mai accendersi. Fix: INSERT idempotente nel chokepoint HTML (`_pg.persist_html_result_and_enqueue_notifications`). S (~1h). Confidenza: ALTA.

**F17 · INCOERENZA/FEATURE-NON-CHIUSA · Pipeline A WR2: 1.643 righe di dead code con 2 daemon KeepAlive ancora VIVI sul Pro che ascoltano un canale senza publisher**
Prova: `wr2_carousel_dispatcher.py:55,173` `LISTEN topic_ready` — unico file nel repo che menziona il canale (nessun NOTIFY mai). Su Pro `com.balizero.wr2.carousel-dispatcher` e `wr2.telegram-gate` PID vivi, last-exit 75, installati a mano (non versionati). Dead code: 969 (orchestrator) + 212 (dispatcher) + 462 (telegram-gate) righe + 661 di test. Il telegram-gate è superato by-design dalla lane HTML ("NO Telegram gate — Legge 5", header `wr2_html_render_apply.py:8-10`).
Fix: bootout dei 2 daemon (5 min, reversibile) + decisione P-1 (consolidare o tagliare il codice). Decisione operatore. Confidenza: ALTA.

**F18 · FEATURE-NON-CHIUSA · Evolution loop evoskill: scorer FIXATO (run 7/6 exit 0, $0.055) ma zero pressione evolutiva — benchmark saturo al 100% → 0 proposte per costruzione**
Prova: fix in `vendor/evoskill/src/cli/shared.py:197-211` (root cause era `max_tokens=16` → `content=''` su reasoning model; ora `max_tokens=2000` + `reasoning_effort=low` + default `deepseek-v4-pro` esplicito a `:255`); run report 2026-06-07: Baseline 100%, Final 100%, "All samples passed, no proposal needed", 0 proposte. Contorno: `TELEGRAM_BOT_TOKEN` non settato nell'env dell'evolver (alert saltati), SECRETS_FILE drift, doppio LaunchAgent weekly+daily da chiarire. NOTA: la memoria cita `vendor/evoskill/cli/scorer.py` che NON esiste (lo scorer è `make_scorer` in `src/cli/shared.py:229+`) — file:line fantasma intercettato.
Fix: curriculum con casi che il programma base FALLISCE (lavoro vero, giorni) o sospendere il cron. Decisione. Confidenza: ALTA.

**F19 · INCOERENZA · Fact-checker WR2: "degraded" è lo stato normale e non blocca; claims-vuoti = pass vacuo; tier LLM scritto ma `llm_enabled=False` in prod**
Prova: `wr2_fact_checker.py:556-590` aggregazione (contradicted→fail OK fail-closed; unverifiable→degraded che avanza comunque a `drafts_imaged_checked`); `:573-574` lista claims vuota → `pass`; `:567-571` cap a degraded senza fonte esterna (fix autopsy P-5 ok); `LAW_PATTERNS :96-118` ora copre Permen* (fix post-autopsy). Kill-switch `wr2_fact_checker_enabled` live ON; ogni run live esce `degraded` (30/11 claims), tier LLM (`_llm_verify_claim:453-489`) mai eseguito.
Fix: chiudere il corner claims-vuoti (→degraded) + decidere se attivare il tier LLM o documentare il pass-through. S-M. Confidenza: ALTA.

**F20 · INCOERENZA · WR3: manifest di produzione incompatibile col proprio validator (per 2 vie indipendenti)**
Prova: `scripts/wr3_episode_manifest.py:20-37` MANDATORY_FIELDS include `claim_ids`/`asset_hashes`/`contract_versions`; `validate_manifest` (righe ~123-144) fallisce su campi mancanti, su `claim_ids` vuoto E su verdict fuori da `{PENDING,PASS,FAIL,DEGRADED}`. L'unico episodio reale (`content-creator-3-roads-2026-05-29`: master.mp4 44MB, 4 varianti, ArcFace 0.790, 360 cr) ha 17 chiavi senza i 3 campi e verdict `PASS-WITH-NOTES`. La traceability legale (claim_ids→NB ground truth) promessa dal contratto non è mantenuta dalla produzione.
Fix: wiring del builder nel path del post-assembler prima del prossimo episodio. M. Confidenza: ALTA.

**F21 · GUARDIANO-DISARMATO · WR3 Reflexion weekly = cron-teatro**: plist verde (Sun 02:30) che esegue uno stub dichiarato. Prova (verificata via ssh): `~/.claude/skills/bali-zero-brand/wr3/_reflexion-synthesis.py` = 816 byte, riga 4 "PLACEHOLDER (S7.3 stub) — full implementation lands at S7.5", riga 21 print+exit 0. Zero `lessons.md` mai prodotti, `_proposed/` vuota. Correlati WR3: yt-metrics-analyst = solo design (plist inesistente, runbook `docs/wr3/runbook-supervisor.md:51` lo cita come esistente); editorial-bench monthly mai cron-fired con certezza (log inesistenti); 3 plist WR3 vivi sul Pro non versionati in `infra/launchagents/`; zero episodi nuovi da 12 giorni con supervisor H24 acceso.
Fix: implementare S7.5 o rimuovere il plist; decidere produzione regolare vs congelamento supervisor. Decisione. Confidenza: ALTA.

**F22 · GUARDIANO-DISARMATO · Sentinel: one-shot senza StartInterval, meta-watchdog cronicamente "stale+cooldown_skip"**
Prova: `sentinel_meta_watchdog.json`: `sentinel_status_age_s=2399 vs threshold 900, action=cooldown_skip`; il plist sentinel ha RunAtLoad senza schedule (W70 #4 mai chiuso). Un verdetto quasi-sempre-rosso-soppresso non discrimina nulla (famiglia W55).
Fix: StartInterval ~600s al sentinel o soglia 3× cadenza reale. S. Confidenza: ALTA su sintomo.

**F23 · GUARDIANO-DISARMATO · 22/180 LaunchAgent Pro in bad-exit**, incluso il cluster WR2 74/75 ciclante da settimane (dispatcher/telegram-gate = F17; supervisor exit 74 storici). Il tracker `launchd_bad_exits.json` li registra già ma nessun consumer agisce ("esiste-ma-disarmato a metà"). Fix: triage in sessione Pro + bootout pipeline A. M. Confidenza: ALTA sull'elenco, BASSA sulle cause individuali.

**F24 · GUARDIANO-DISARMATO · `guardrails-static.py` esiste in `~/.claude/hooks/` ma NON è registrato in settings.json** (W71 deferred ancora aperta). Nota positiva verificata: stop_verify RIARMATO (la disattivazione `STOP_VERIFY_ALLOW_DIRTY=1` della scar è sparita da settings/zshenv/launchctl; hook aggiornato 9/6), seam_verify wired (settings.json:492). Fix: registrare o deprecare guardrails-static. XS. Confidenza: ALTA su configurazione.

**F25 · GUARDIANO-DISARMATO · Required checks su main: 2/7 workflow P\* promossi (col pattern sentinel skip→success corretto, W69-aware), p6-federation-parallelize in failure ×2 (9/6) e non riparato**; p3/p7/p8/p9/hot-zone girano verdi ma non bloccano. Fix: fix p6 + promozione progressiva col pattern sentinel (NON as-is: hanno paths-filter). M. Confidenza: ALTA.

**F26 · BUG · Worktree cleanup assente su M5: 21/38 worktree stale >24h** (su Pro i 3 plist cleanup esistono e lavorano — 4 rimossi il 10/6 — ma escono exit 1 quando skippano WIP → rumore nel bad-exit tracker). M5 è oggi macchina principale di coding = superficie sibling-race W62 in crescita. Fix: installare `install_agent_worktree_cleanup.sh` su M5 + exit 0 sugli skip-WIP. S. Confidenza: ALTA.

**F27 · INCOERENZA · Router parity inversa: `experience`, `skill`, `metabolic_health` dichiarati `_API`-only nel manifest ma inclusi anche in `include_heavy_routers()`**
Prova: `router_manifest.py:187-189` vs `router_registration.py:880-884`. Con `EXPERIENCE_DB_PATH=/data/experience.db` in `[env]` fly.toml (vale per entrambi i processi) e volumi `/data` diversi per processo → split-brain SQLite potenziale per caller interni a `rag.internal` (`/api/experience` non è in HEAVY_PREFIXES, il traffico pubblico resta su api). Il test di parità copre solo la direzione manifest→registration, non l'inversa.
Fix: allineare (togliere i 3 include da heavy o promuovere a `_BOTH` con commento) + check inverso nel test. S. Confidenza: ALTA.

**F28 · FEATURE-NON-CHIUSA · Router orfano `crm_migration`: 3 endpoint con auth e logica DB completi, mai montati** (`backend/app/routers/crm_migration.py:20,149,244`; zero riferimenti in manifest/registration — verificato). Il test associato (`test_crm_migration_endpoints.py`) dichiara di testare 4 feature ma importa solo il document_categorizer. Fix: montare o rimuovere. XS-S. Confidenza: ALTA.

**F29 · INCOERENZA · `memory_vector` mai montato ma pubblicato nel catalogo master dei tool** (`handlers.py:52,65` lo importa per il catalogo "che ZANTARA usa per vedere i tool disponibili"; zero mount in `backend/app/setup/` — verificato). L'AI può pianificare chiamate verso 8 route (`memory_vector.py:109-351`) che 404ano. Correlato: `system_observability`/`root_endpoints`/`audio` montati solo via `app_factory.py:673-687` (full-app) → non serviti dai processi Fly `main_api`/`main_rag`; `/system-health` 404 in prod, non documentato (a differenza di olympus che ha eccezione esplicita nel test di parità).
Fix: montare (`_RAG`) o togliere dal catalogo; documentare i mount full-app-only nel manifest. S. Confidenza: ALTA.

**F30 · SICUREZZA · Ruoli superuser residui**: `backend_rag_v2` è stato demoted (rolsuper=f — **la cicatrice W38 "DRAFT SPEC NOT EXECUTED" è superata dalla realtà, aggiornarla**), ma restano 5 superuser di cui 2 app/legacy non-piattaforma: `nuzantara_rag`, `backend_ts_user` (i 3 di piattaforma postgres/repmgr/flypgadmin sono legittimi). Fix: audit+demote spec separata (la "future audit candidate" di W38). M. Confidenza: ALTA (query pg_roles via fly console).

**F31 · SICUREZZA · Permessi file**: 3 `.env` world-readable 0644 su Pro (`apps/bali-intel-scraper/`, `apps/war-room/`, `apps/wa-mirror/` — contenuto NON letto, da audit); `.secrets/google-credentials.json` 0644 su M5 (service-account key); 3 plist intake 0644 con DSN localhost senza password (impatto basso). Nota positiva: `apps/cell/.env` e `apps/backend-rag/.env` ora 0600 (antibody P0 2026-06-03 fatto, rotazione password resta NON confermata); backup plist W65 tutti 0400. Fix: chmod 600 sweep. XS. Confidenza: ALTA sui permessi.

**F32 · BUG · Cache invalidation service-side mancante**: i router CRM invalidano (26 chiamate mappate 1:1 sugli endpoint mutanti), i services no — `services/crm/assignment.py:524-528,557-561` (UPDATE assigned_to senza invalidate → stats per-assignee stale, `get_clients_stats` cached ttl=300 `crm_clients.py:1505`), `client_core.py:690-695`, `intake/writer.py:716-720`, + endpoint `ensure-drive-folder` (`crm_clients.py:854`) unico del suo file senza invalidazione. Stessa classe (verifica file-level): enrichment.py:337, documents.py:492, drive_poll_service.py:551, service_account_drive_service.py:370, invoice_service.py:481, billing.py:272, consolidator.py:472,587. Mitigante: TTL 300s. Fix: helper `invalidate_crm_stats()` o handler EventBus su client_changed/practice_changed. S-M. Confidenza: ALTA sulle righe citate.

**F33 · OPERATIVO · Postgres MCP inutilizzabile da M5** (porta :15432 CLOSED e keychain `nuzantara-postgres-readonly` assente su M5; sul Pro la porta è open ma il keychain è SSH-locked non-interattivo). Contraddice la doctrine "M5 dev-uguale". Workaround esistente: fly ssh console. Fix: port-forward + keychain su M5, ~30 min. Confidenza: ALTA.

**F34 · OPERATIVO · MEMORY.md a 54KB contro il limite hard di ~25.6KB** — metà dell'indice memoria silenziosamente troncato a ogni sessione, incluse entry operative recenti. Fix: sweep di compressione verso i file topic (target <20KB dichiarato nel file stesso). S. Confidenza: ALTA.

**F35 · OPERATIVO · cicatrix-scars.md a 99KB**, caricato a ogni sessione; il fix esiste (PR #1186 auto-archive, aperta dal 7/6) ma non landa. Fix: chiudere la PR. XS. Confidenza: ALTA.

### P3 — Cosmetici / igiene / decisioni minori

- **F36** · Guard tax: risk-intent gate ancora substring (`:748`, `"late"⊂"translate"`, `"fine"⊂"define"`, `"owe"⊂"lower"`) — suffisso-rumore, fix 1 riga (`_contains_any_word` su `_RISK_INTENT_TERMS`).
- **F37** · Guard document_status: marker `"is approved"` (`:506-507`) matcha condizionali ("once the application is approved…") → rifiuto canned al posto di spiegazione corretta.
- **F38** · Guard kbli_label: regex `\b\d{5}\b` (`:41`, `:806`) tratta CAP/importi come codici KBLI → prefisso "KBLI direction to check:" su contenuto non-KBLI.
- **F39** · Telegram `stream_response` inghiotte le eccezioni senza DLQ né fallback (`telegram/adapter.py:356-369`; confronto WA `:239-245` corretto); silenzio totale se il send iniziale fallisce; error-edit non guardato.
- **F40** · `channels/router.py:256-257` persistenza messaggi CRM fallita loggata a DEBUG — cronologia conversazioni si buca invisibilmente. Fix: warning + counter. 1 riga.
- **F41** · Web adapter `send_response` è un no-op che logga successo (`web/adapter.py:119-127`, latente).
- **F42** · 731 test skeleton auto-generati `@pytest.mark.skip(reason="Auto-generated skeleton")` su 765 skip totali (+~20 skip reali concentrati su `test_orchestrator*.py` RAG) — inventario test gonfiato. I 3 test pre-deploy critici sono puliti (zero skip).
- **F43** · Webhook ack-first: `get_database` swallow senza log in `twitter.py:186-193` e `instagram_chat.py:225-230` — l'antibody P0-6 può sparire in silenzio. Fix: 2 righe warning.
- **F44** · Incoerenze documentali: "Legge 8" esiste in VADEMECUM:396 ma non in SYMBIOSIS.md (7 leggi) e l'hook annuncia "8 Leggi" elencandone 7; INDEX.md promette marker `<!-- DOCSYNC:* -->` in CLAUDE.md che non esistono più; runbook WR3 cita plist yt-metrics inesistente; scar W38 e memoria (PR #1236 "aperta", evoskill "scorer rotto", `cli/scorer.py`) superate dalla realtà — da aggiornare.
- **F45** · e2e frontend `apps/mouth/e2e/*.spec.ts` = gusci "TODO: Add assertions" (test che esistono ma non verificano nulla).
- **F46** · ~40 PR aperte (batch dependabot 2/6, 7 PR "Palette" bot, draft ONDA-2 #1041/#1046, #1099 wa-corpus, #1111 olympus, #1159 guardrail-liveness…) + 151 branch remoti — graveyard attivo, il cleanup weekly è report-only by design.
- **F47** · `X-API-Key: zantara-secret-2024` hardcoded in ~15 file (debito noto by-design §13; centralizzare in config quando capita).
- **F48** · `outbox-prune.daily` logga ogni riga doppia (possibile doppio-fire/doppio-bootstrap, DELETE idempotente — famiglia active-active).
- **F49** · repomap 188KB vs ~8KB documentati (budget inject SessionStart).
- **F50** · WR2 image-generator plist senza schedule è by-design (kickstart event-driven dal supervisor) ma senza supervisor non ha NESSUN fallback schedulato — opzionale StartCalendarInterval di backstop.

## 3. Feature cominciate-ma-non-chiuse (vista dedicata)

| Feature | Dove è arrivata | Cosa manca | Verdetto |
|---|---|---|---|
| **WR2 cutover Canva→HTML** | **Completato di fatto**: PR #1236 merged 9/6, flag ON, HTML renderizza in prod, Canva no-op via proprio switch | Code: bootout plist Canva, parità topic_type_log (F16), landing designer-loop (F10), aggiornare memoria/runbook | **Chiudere** — è al 90% |
| **Anti-monotonia P-4** | Tabella (mig 216) + writer Canva + reader soft-steer shipped | Writer morto col cutover → enforce mai attivabile | **Chiudere** con 1 INSERT (1h) o tagliare onestamente |
| **Pipeline A WR2** (1.643 righe + 661 test) | Codice completo, mai wired (zero publisher su `topic_ready`) | O P-1 consolidamento o rimozione; intanto 2 daemon vivi inutili | **Tagliare il runtime subito** (bootout, reversibile); decidere P-1 dopo |
| **Evolution loop evoskill** | Infra funzionante, scorer fixato e verificato | Pressione evolutiva (curriculum) — 0 proposte per costruzione; Telegram non armato; doppio LaunchAgent | Investire nel curriculum **o sospendere il cron** |
| **WR3** | Core provato E2E 1× (29/5, episodio completo con identity gate funzionante), supervisor H24 vivo | Manifest contract bypassato (F20), Reflexion stub (F21), yt-metrics solo design, editorial-bench mai cron-fired con certezza, zero episodi da 12 giorni | **Decidere**: produzione regolare o congelare il supervisor — "armato ma inattivo" è il peggio |
| **Fact-checker tier LLM** | Deterministico live e funzionante; LLM scritto ma spento | Attivazione o accettazione documentata del pass-through "degraded"; fix claims-vuoti=pass | Chiudere la **decisione** |
| **W70 antibodies** | 1/4 fatto (backup fly ok) | stderr-capture (riarma auto-heal, F08), qdrant path 1-riga (F09), sentinel schedule (F22) | **Chiudere** — è il filo "strumentazione disarmata" |
| **W35/W64 lint CI wiring** | Lint verde, 0 violazioni | Il consumer CI (deferral aperta dal 23/5) | **Chiudere** — XS (F15) |
| **Digest alert soppressi (W55)** | Proposto 3 volte (scar 25/5, F03, F22) | Mai costruito | **Costruirlo** — terza recidiva |
| **PR #1186 cicatrix auto-archive** | PR aperta dal 7/6 | Merge | **Chiudere** — il file è a 99KB (F35) |
| **crm_migration / memory_vector router** | Codice completo orfano | Mount o rimozione | Decidere e chiudere (XS-S) |
| **Required checks P\*** (W69 #1) | 2/7 promossi col pattern sentinel corretto | p6 rotto, 5 workflow non bloccano | Fix p6 + promozione progressiva |

## 4. Top 10 ad alto impatto (shortlist azionabile)

1. **Rotazione token Telegram + 1 riga httpx WARNING** (F01) — leak attivo, ogni run lo ristampa.
2. **Adottare il diff dirty del deploy worktree → sblocco puller** (F03) — 20 min, de-stalizza la produzione WR2 e salva lavoro a rischio.
3. **Wire lint asyncpg in CI** (F15) — XS, chiude la classe W34/W64 per sempre; doppia evidenza che oggi non gata nulla.
4. **Fix guard WA F05+F06 + word-boundary sweep (F13/F14/F36)** — clienti reali ricevono risposte sbagliate ORA; harness test già pronto.
5. **`raise_for_status` su Instagram adapter** (F07) — 1 riga, ferma la perdita silenziosa di risposte.
6. **DLQ: stderr-capture + pruning entry guarite** (F08) — riarma l'intero auto-heal; senza, ogni altro guardiano lavora alla cieca.
7. **`qdrant-snapshot.sh:21-22` path fix** (F09) — 1 riga, ripristina un backup critico rotto da 37 giorni.
8. **LKPM `REGULATORY_FACTS` con valid_until** (F11) — disinnesca la time-bomb prima dell'annuncio Q2.
9. **Rotazione GOCSPX client_secret + env var** (F02).
10. **Re-certificazione L2 + fix hook staleness** (F04) — governance: l'operato autonomo attuale poggia su un contratto lapsed.

## 5. Cosa NON è stato verificato (onestà)

- **Rotazione segreti storici** (password Postgres del P0 2026-06-03, `BRIDGE_SKILLS_API_KEY` W65, e ora i 2 nuovi F01/F02): non confermabile read-only — restano "da considerare esposti finché non ruotati".
- **Contenuto** dei 3 `.env` 0644 (war-room/wa-mirror/intel-scraper): controllati solo i permessi, deliberatamente non letti.
- **Stato del Mini-Pro2**: non ispezionato (mandato M5+Pro); la storia W67c insegna che daemon orfani possono vivere lì — merita un `launchctl list` dedicato.
- **Valori live dei kill-switch in `system_settings`** (HTML renderer ON, fact-checker ON): provati per comportamento osservato nei log, non da query DB (Postgres MCP giù da M5, F33; fly console usato solo per pg_roles/events_outbox).
- **Cause individuali** dei 22 LaunchAgent bad-exit e degli heartbeat-timeout del supervisor WR3 (diagnosi log-per-log = sessione Pro dedicata).
- **Run-time** degli hook stop_verify/seam_verify (config verificata, comportamento non esercitato).
- **Chi ha prodotto** il bench editoriale WR3 di maggio (cron vs manuale): i log non esistono.
- La query `count(*)` superuser come singola query atomica (il "5" deriva da liste nomi coerenti via fly console).

## Verificato OK (aree pulite — sintesi)

- **HOME-fork bridge WA**: 3/3 copie byte-identiche (M5 repo / Pro repo / Pro HOME), hash md5 verificati.
- **Test matrix W73**: shippata e completa — 10/10 guard con doppia polarità + meta-gate dinamico (`test_guard_matrix_covers_every_guard_both_polarities`) che fallisce su guard nuovi non coperti.
- **Router parity direzione manifest→registration** (lo scar #422): pulita, test robusto in CI.
- **PUBLIC_ENDPOINTS**: nessun drift, 10/10 test passati live.
- **Golden Rule 10 (httpx)**: CI dedicata verde, 116 instanziazioni conformi.
- **Regola 8 print() / Regola 11 PricingTool / Embedding FROZEN**: pulite.
- **Migrations**: 107 file, zero duplicati, lint a 3 livelli (CI paths-filter + hot-zone replay + runtime assert).
- **W38**: `backend_rag_v2` demoted NOSUPERUSER — eseguito.
- **EventBus Phase 3**: per-handler ack reale (`event_bus.py:505-541`), prune cron daily/weekly live (935 righe il 10/6), tabella bounded (41.8k righe = finestra 30gg, 1.356 unconsumed normale).
- **FASE-0 governance (W71)**: tutti i segnali freschi <5 min, 20/21 gates armed; cost-breaker legge spesa reale via nuovo bridge `cost-ledger-export`.
- **stop_verify**: riarmato (disattivazione della scar rimossa); seam_verify wired.
- **Fly**: api+rag entrambi started, v3505; deploy venv con asyncpg ok.
- **wa-mirror (W67)**: supervisor stabile, 6 bridge vivi; repomap fresco <1min.
- **WR3 supervisor**: vivo H24, except asyncpg W34-completi, reconnect/outbox corretti.
- **Escalations**: `shared/escalations_pro.jsonl` vuoto, nessuna pendenza.

---

*Nota di metodo: durante l'audit sono stati intercettati 2 nuovi "file:line fantasma" nella memoria di progetto (`vendor/evoskill/cli/scorer.py` inesistente; PR #1236 data per aperta ma merged) — la disciplina re-verify-on-disk li ha corretti invece di costruirci sopra. Auto-conferma della tesi "verificatore imperfetto → tutto va ri-verificato su disco".*
