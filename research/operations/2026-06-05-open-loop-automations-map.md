# Open-loop automations map - SYMBIOSIS

Date: 2026-06-05

Scope: mappatura read-only delle automazioni che non hanno il loop chiuso secondo il criterio SYMBIOSIS/PulseLoop. Non ho trovato un demone canonico chiamato `symbiosisd` nel repo; per "dettagli di symbiosis" ho usato le fonti operative sotto.

## Aggiornamento operativo 2026-06-06

Questo report resta la fotografia di partenza del 2026-06-05. Dopo le wave autonome reuse-first/P0b-P0q del 2026-06-06, lo stato corrente della registry e' cambiato:

- `apps/organism/organism/organs_registry.yaml` valida.
- Organi enabled: 272 su 277 totali; 5 disabled intenzionali.
- Enabled con `bridge_source`: 272.
- Enabled senza `bridge_source`: 0.
- `APERTO-2 senza bridge` e' chiuso nella registry corrente.
- `wr2.canva_apply` non e' piu' trattato come disabled: Pro lo carica ancora, quindi il registry ora punta al vero owner `scripts/wr2_canva_desktop_apply.py` e lo script emette `~/.organism/last_seen/wr2.canva_apply.json`.
- `pro.ollama_warm_pin` non e' piu' trattato come LaunchAgent disabled: e' dichiarato come cron settimanale coperto da `scripts/ollama-warm-pin.sh`, senza label launchd fantasma, con heartbeat standard.
- `scripts/launchagent-state-bridge.py` e' stato portato dal bridge legacy Pro, adattato a `~/.organism/last_seen` e installato live su Pro con backup. Receipt verificati post-P0h: 24 `ok` / 0 failed, inclusi i 21 LaunchAgent running importati dal Pro.
- `scripts/audit/live_runtime_vs_genome.py` ora distingue anche `disabled_registry_launchctl/plists/cron`: un job disabilitato ma ancora live non puo' mascherarsi come copertura valida.
- Consumer aggiornati/verificati: `BridgeStateReader`, `GenomeAggregatorSensor` e `scripts/sentinel-aggregate.py` leggono anche bridge HTTP con `json_path`; gli endpoint HTTP senza timestamp usano il momento di lettura come liveness timestamp; lo status `down/fail/unavailable` non puo' essere classificato vivo solo perche' fresco.
- `apps/evaluator/seo_auto_fixer.py` non usa piu' `ANTHROPIC_API_KEY` ne' `https://api.anthropic.com/v1/messages`: genera la meta description localmente e ha test regressivo anti-endpoint diretto.
- `scripts/wr2_canva_lease_watchdog.py` include gia' `asyncpg.InterfaceError`; il lint `scripts/lint_asyncpg_except_completeness.py` e' verde ed e' ora agganciato a `.github/workflows/asyncpg-lint.yml`.
- I label live `skills-bridge-consumer` e `wa-dashboard-m1` non risultano caricati in `~/Library/LaunchAgents` su questa macchina. Per prevenire regressioni, il template `apps/cell/launchagent/com.nuzantara.skills-bridge-consumer.plist` non contiene piu' il segreto inline: chiama `apps/cell/scripts/skills_bridge_consumer_launcher.sh`, che carica `~/.nuzantara-secrets.env` a runtime; il runbook ora installa quel plist con `chmod 0400`.
- `APERTO-1 fuori genoma` ora ha un guardrail operativo: `scripts/audit/live_runtime_vs_genome.py` confronta registry, `launchctl`, plist e crontab. Snapshot Pro 2026-06-06 post-P0i: 191 label launchctl, 195 plist, 88 cron; fuori genoma 69 launchctl, 70 plist, 71 cron. Dei label `launchctl` fuori genoma restano 0 running, 16 falliti/non-zero, 53 scheduled-ok; `disabled_registry_*` e' 0. Il delta P0i ha chiuso il plist-only morto (`wr2.canva-renderer`, `workspace-event-bridge-sheets-import`) e importato `infra.pg_organism_bridge_watchdog` con heartbeat live `ok`; rimane plist-only solo `com.balizero.wa-mirror`. Air-M5 e' thin client: vede solo `com.balizero.caffeinate` fuori genoma. Mini non verificato: SSH `100.93.236.6:22` in timeout.
- Post-P0p/P0q il gate runtime Pro e' chiuso: snapshot `pro-live-vs-genome-p0q-after.json` con `unmanaged_launchctl=0`, `unmanaged_plists=0`, `unmanaged_cron=0`, `disabled_registry_* = 0`, `missing_loaded_labels=0`.
- La registry corrente post-P0q ha 277 organi totali, 272 enabled, 5 disabled intenzionali, 272/272 enabled con `bridge_source`, checksum `99c395caa3a3e056653d8f3c03e5fe5bcb857f05aeeb430b7dfcb427a59e154a`.
- P0p ha dichiarato e wrappato le 70 entry cron Pro residue; P0q ha filtrato l'audit per runtime (`--runtime pro_launchd`), ritirato i tre `cell-observatory*` gia' documentati come deprecated, caricato `com.nuzantara.federation-alert-dispatcher` con venv corretta e riattivato `com.nuzantara.claude-max-usage-watcher`.
- P0r ha chiuso un sotto-gap del quarto verbo sul proof post-azione: `Dispatcher.dispatch()` ora scrive `incident_ledger.record_dispatch()` prima di eseguire l'attuatore, cosi' `ActuatorBase.run()` puo' aggiornare la stessa riga a `done/failed` invece di arrivare prima dell'insert.
- P0s ha chiuso altri due sotto-gap del quarto verbo: C `robust_parse` per giudizio LLM strutturato robusto/fallback esplicito e A `red_summary` per rendere il red di Cell leggibile e persistito per sensore/causa. La suite ampia organism `supervisor + actuators + incident_ledger` ora e' verde (`185 passed`).
- P0t ha chiuso i tre sotto-gap residui del quarto verbo nel perimetro codice: D `suppression_digest` per escalation periodica delle soppressioni ripetute, B `RulesEngine.supersede()` per sostituire regole learned/reflexion/dream senza toccare le base, e auto-dismissione del watchdog WR2 quando il renderer e' kill-switch off o superseded. Verifica combinata: `56 passed` su Cell/Olympus/DeepSeek piu' `18 passed` sul watchdog WR2.
- Quarantena Pro P0q: `/Users/nuzantara/Library/LaunchAgents/quarantine-open-loop-p0q-20260605T214647Z/` contiene `com.claude-max-api.plist` e i tre plist `com.nuzantara.cell-observatory*.plist`.
- L'audit non filtrato su snapshot Pro mostra solo quattro `missing_loaded_labels` `mini_launchd` (`com.matagaruda.intel-bridge.daily`, `com.matagaruda.ner-worker.hourly`, `com.matagaruda.normalizer.hourly`, `com.matagaruda.sentinel.daily`), che non sono drift Pro. Mini resta non verificato live: ultimo ritest 2026-06-06 con `tailscale status` mostra `100.93.236.6 mini-pro2 ... offline, last seen 1d ago`; TCP/22 e SSH verso `100.93.236.6` sono ancora in timeout.

Le sezioni sotto mantengono anche la lista storica dei 91 no-bridge per spiegare da dove e' partita la closure; non sono piu' lo stato operativo corrente.

## Fonti usate

- `SYMBIOSIS.md`: PulseLoop `sense -> think -> act -> reflect -> dream -> mature`; evento durevole; Zero come ultima istanza; numeri prima.
- `packages/cell-core/cell_core/pulse.py`: implementazione concreta del ciclo.
- `apps/organism/organism/organs_registry.yaml`: genoma operativo degli organi.
- `apps/organism/organism/rules/base.yaml`: regole autonomiche che oggi chiudono il loop per pochi casi.
- `docs/automations/runtime-register.md`: registro runtime offline delle automazioni.
- `docs/automations/runtime-3of5-criterion.md`: criterio runtime/ownership.
- `docs/AUTOMATIONS_REFERENCE.md`: snapshot live 2026-05-30 generato da stato runtime.
- `research/operations/2026-05-31-organism-nervous-system-audit.md`: audit empirico LaunchAgent.
- `research/operations/2026-06-03-organism-tac.md`: TAC "quarto verbo".
- `research/operations/S15-symbiosis-FROZEN.json`: audit SYMBIOSIS con red launchagent, Law 1, W64/W65.

## Criterio

Una automazione e' "loop chiuso" solo se passa questi 4 verbi:

1. `sente`: produce heartbeat, log, receipt, state file, evento o metrica leggibile dall'organismo.
2. `giudica`: una regola o cella interpreta il segnale con soglia e contesto.
3. `agisce`: c'e' un attuatore reale, recovery action, escalation o decommission sicura.
4. `si rivede`: riflette sul risultato e aggiorna regola, genoma, soglia, skill, scar o dismette il watcher quando il target non serve piu'.

Quindi non basta che un LaunchAgent parta. Un job schedulato ma senza ricevuta leggibile e' batch, non organismo. Un watchdog che segnala ma non agisce e' osservazione aperta. Un sistema che agisce ma non sa correggere la regola o lo strumento e' loop parziale.

## Numeri base

Da `docs/AUTOMATIONS_REFERENCE.md`:

- 206 job totali nello snapshot.
- 113 healthy.
- 38 running daemons.
- 6 warning/skip/no-log.
- 34 failed.
- 13 circuiti terminal/DLQ terminal.

Da `apps/organism/organism/organs_registry.yaml` nello stato corrente 2026-06-06 post-P0q:

- 277 organi dichiarati nel genoma.
- 272 enabled.
- 5 disabled intenzionali.
- 272 enabled con `bridge_source`.
- 0 enabled senza `bridge_source` (snapshot originario 2026-06-05: 25 con bridge, 91 senza bridge).
- 259 enabled su runtime `pro_launchd`.
- 8 enabled su runtime `fly_machine`.
- 5 enabled su runtime `mini_launchd`.

Da TAC 2026-06-03:

- 183 automazioni live osservate contro 120 organi dichiarati.
- Circa 63 automazioni live risultavano fuori genoma/recovery coverage in quella fotografia.
- L'organismo ha "3 verbi e mezzo": sente, giudica, agisce, ma non rivede ancora bene i propri strumenti.

## Classi di loop non chiuso

| Classe | Cosa significa | Azione corretta |
| --- | --- | --- |
| `APERTO-0 rotto` | job fallito, wrapper mancante, segreto esposto, endpoint vietato o recovery impossibile | riparare, dismettere o mettere in quarantena prima di ragionare sul loop |
| `APERTO-1 fuori genoma` | automazione live non descritta in `organs_registry.yaml` | importare nel genoma o decommissionare |
| `APERTO-2 senza bridge` | organo enabled ma senza `bridge_source` | aggiungere state receipt/heartbeat/evento o dichiararlo batch |
| `APERTO-3 osserva ma non agisce` | alert, monitor o watchdog senza attuatore utile | collegare a action/escalation o ridurre a osservato batch |
| `APERTO-4 agisce ma non si rivede` | agisce, ma non supersede regole, non corregge sensori, non dismette target morti | implementare quarto verbo |
| `BATCH-INTENZIONALE` | cron deterministico senza promessa biologica | lasciare fuori dal concetto di organismo, ma dichiararlo esplicitamente |

## P0/P1: rotti o impossibilitati a chiudere il loop

Questi non sono semplicemente "senza bridge": sono loop bloccati a monte.

| Automazione / file | Classe | Evidenza | Loop aperto |
| --- | --- | --- | --- |
| `com.balizero.wr2.canva-renderer` | `APERTO-0` | S15: wrapper `/Users/nuzantara/.openclaw/bin/wr2/wr2-canva-renderer-wrapper.sh` assente; `StartInterval=300`; exit 78 | il watchdog osserva un arto amputato e fallisce ogni 5 minuti |
| `wr2.supervisor_watchdog` | `RIALLINEATO P0t` | TAC: kill switch renderer off, ma guardiano continuava a vigilare il vuoto; P0t aggiunge receipt persistente `last_self_silence_canva_renderer_*` e supporto `wr2_canva_renderer_superseded_by` | il ramo renderer ora si auto-silenzia quando il target e' intenzionalmente off o superseded |
| `com.nuzantara.workspace-event-bridge-sheets-import` | `APERTO-0` | S15: target script in worktree cancellata `.worktrees/docs-lab-clean-recreate`; exit 127 ogni 15 min | evento -> import non puo' produrre ricevuta reale |
| `com.balizero.wr3.editorial-bench.monthly` | `APERTO-0` | S15: directory `/Users/nuzantara/.openclaw/bin/wr3/` assente; exit 127 | batch editoriale non recuperabile |
| `com.balizero.wr3.yt-metrics.weekly` | `APERTO-0` | S15: stessa directory `wr3/` assente; exit 127 | metriche YouTube non producono ciclo |
| `com.balizero.wr3.supervisor` | `APERTO-0` | audit 2026-05-31: wrapper `wr3-supervisor-wrapper.sh` assente; exit 78 | supervisore non avviabile |
| `fly_pg_backup` | `APERTO-3` | TAC: backup fermo ~5 giorni; `backup:age_hours=113.3`; Cell lo vede rosso ma non lo spiega bene | allarme vero non diventa riparazione/escala leggibile |
| `apps/evaluator/seo_auto_fixer.py` / `seo_auto_fixer` | `APERTO-0` + Law 1 | S15: POST a `https://api.anthropic.com/v1/messages` con `ANTHROPIC_API_KEY`; lint CLI-only non copre questo file | violazione SYMBIOSIS Law 1 e loop non autorizzato |
| `scripts/wr2_canva_lease_watchdog.py` | `APERTO-0` | S15 W64: manca `asyncpg.InterfaceError` nell'exception set; lint non gate in CI | rischio silent-death: l'antibody esiste ma non protegge |
| `com.nuzantara.skills-bridge-consumer` | `APERTO-0/security` | S15 W65 + audit: backup/plist world-readable con API key 64-hex | loop HGT/skills non puo' essere considerato chiuso finche' la credenziale e' esposta |
| `com.balizero.wa-dashboard-m1` | `APERTO-0/security` | audit 2026-05-31: plist world-readable con token dashboard | sicurezza rompe la fiducia del ciclo |
| `com.nuzantara.cleanup-2026-05-16-ttl-sentinel` | `APERTO-0/tombstone` | audit 2026-05-31: target state dir mancante | da ripulire o archiviare come tombstone, non loop vivo |

## LaunchAgent falliti nello snapshot 2026-05-30

Questi sono candidati `APERTO-0` o `APERTO-3`, ma alcuni snapshot sono notoriamente stale rispetto agli audit successivi. Vanno trattati come lista di triage, non come verita' live assoluta.

- `com.balizero.intel-lake.e2e-probe.6h`
- `com.balizero.intel-lake.outbox-drain.minute`
- `com.balizero.intel-radar-daily-digest`
- `com.balizero.mos-plus.qdrant-indexer`
- `com.balizero.nuzantara-drive-sync`
- `com.balizero.post-publish-poller`
- `com.balizero.qdrant.daemon`
- `com.balizero.translate.hourly`
- `com.balizero.wa-mirror`
- `com.balizero.wa-mirror-auto-promote`
- `com.balizero.wa-mirror-strategic-recap`
- `com.balizero.wr2.canva-lease-watchdog.10min`
- `com.balizero.wr2.canva-oauth-watchdog`
- `com.balizero.wr2.canva-renderer`
- `com.balizero.wr2.canva-token-watchdog.daily`
- `com.balizero.wr2.carousel-dispatcher`
- `com.balizero.wr2.deploy-puller`
- `com.balizero.wr2.hardening`
- `com.balizero.wr2.image-generator`
- `com.balizero.wr2.measurer`
- `com.balizero.wr2.plist-watchdog`
- `com.balizero.wr2.sla-worker`
- `com.balizero.wr2.supervisor`
- `com.balizero.wr2.supervisor-watchdog`
- `com.balizero.wr2.telegram-gate`
- `com.balizero.wr3.supervisor`
- `com.cell.organism`
- `com.claude-max-api`
- `com.nuzantara.cell-observatory`
- `com.nuzantara.cell-observatory-selfcheck`
- `com.nuzantara.codex-autofix-ci`
- `com.nuzantara.federation-alert-dispatcher`
- `com.nuzantara.login-healthcheck`
- `com.nuzantara.organism.control-panel`
- `com.nuzantara.pg-organism-bridge-watchdog`

## Four reboot-bombs: loop non chiuso su scheduling

Audit 2026-05-31: questi hanno `RunAtLoad` senza schedule utile e senza `KeepAlive`. Non sono da correggere con `KeepAlive=true`; serve `StartInterval` o dismissione.

- `com.balizero.post-publish-poller`
- `com.balizero.wr2.supervisor-watchdog`
- `com.nuzantara.automap-watchdog`
- `com.nuzantara.sentinel`

## Disabled intenzionali nel genoma

Questi non sono guasti, ma vanno esclusi dalla promessa di loop chiuso finche' restano disabled.

- `backend.kg_langgraph_orchestrator`: feature-flagged off via `ENABLE_KG_LANGGRAPH=false`.
- `backend.crm.drive_poll`: disabled 2026-04-29 dopo saturazione PG.

Riallineati il 2026-06-06 e quindi rimossi da questa classe:

- `wr2.canva_apply`: Pro lo carica ancora; ora e' enabled con owner reale e heartbeat.
- `pro.ollama_warm_pin`: ora e' cron dichiarato, non LaunchAgent disabled.

## APERTO-2: chiuso nella registry corrente (era 91 organi enabled senza bridge_source)

Stato corrente 2026-06-06: nessun organo enabled resta senza `bridge_source`. La lista seguente e' la fotografia storica pre-closure usata per guidare l'intervento: erano nel genoma e avevano recovery action, ma non avevano una ricevuta normalizzata per sapere se il ciclo aveva davvero prodotto valore.

### backend (2)

- `backend.api`
- `backend.surface_router`

### infra (3)

- `infra.postgres`
- `infra.qdrant`
- `infra.redis`

### mata_garuda (18)

- `mata_garuda.bridge_adaptive.pro`
- `mata_garuda.daily_briefing.pro`
- `mata_garuda.gap_consumer.pro`
- `mata_garuda.intel_bridge_daily.mini`
- `mata_garuda.invalidation_sweep.pro`
- `mata_garuda.kg_linker.pro`
- `mata_garuda.kita_feed_daily.pro`
- `mata_garuda.ner_worker_hourly.mini`
- `mata_garuda.nlm_expander_weekly.pro`
- `mata_garuda.nlm_feeder_stream_hourly.pro`
- `mata_garuda.normalizer_hourly.mini`
- `mata_garuda.public_channel.pro`
- `mata_garuda.reg_alert_30min.pro`
- `mata_garuda.sentinel_daily.mini`
- `mata_garuda.watcher_daily.pro`
- `mata_garuda.weekly_digest.pro`
- `mata_garuda.wr2_bridge_hourly.pro`
- `mata_garuda.wr_topic.pro`

### wr2 (21)

- `wr2.canva_oauth_watchdog`
- `wr2.connector`
- `wr2.deploy_puller`
- `wr2.dossier_compiler`
- `wr2.draft_generator`
- `wr2.fact_checker`
- `wr2.fact_extractor`
- `wr2.hardening`
- `wr2.ig_scraper_daily`
- `wr2.image_generator`
- `wr2.learner_nightly`
- `wr2.measurer`
- `wr2.pg_proxy`
- `wr2.queue_server`
- `wr2.reflexion_weekly`
- `wr2.sla_worker`
- `wr2.strategos`
- `wr2.supervisor_watchdog`
- `wr2.topic_selector`
- `wr2.trend_hunter`
- `wr2.voyager_weekly`

### pro (34)

- `pro.automap_server`
- `pro.automap_telegram`
- `pro.automap_watchdog`
- `pro.automations_reference`
- `pro.bz_daily_visual_pipeline`
- `pro.claude_config_sync`
- `pro.client_value_predictor`
- `pro.codex_autofix_ci`
- `pro.codex_overnight_runner`
- `pro.cost_advisor_daily_cap`
- `pro.cost_advisor_weekly`
- `pro.domain_mesh_foundations_daily`
- `pro.federation_alert_dispatcher`
- `pro.heartbeat_bridge`
- `pro.indexing_sweep_daily`
- `pro.intel_radar_daily_digest`
- `pro.launchagent_state_bridge`
- `pro.launchd_env_loader`
- `pro.memory_sync_bidirectional`
- `pro.nb_intel_delta_watcher`
- `pro.nb_mitochondrial_monitor_daily`
- `pro.openclaw_children_watchdog`
- `pro.openclaw_logrotate`
- `pro.post_publish_poller`
- `pro.post_publish_webhook`
- `pro.prime_tunnel`
- `pro.regulatory_watcher_daily`
- `pro.secrets_sync_mini`
- `pro.sentinel_meta_watchdog`
- `pro.seo_cell_28d_check`
- `pro.seo_cell_daily`
- `pro.setup_team_daily`
- `pro.supervisor_liveness_watchdog`
- `pro.vector_reindex_check`

### codex (4)

- `codex.coverage_improver`
- `codex.overnight_feeder`
- `codex.research_actor`
- `codex.spalla_calibrate`

### sota (4)

- `sota.m13_checkpoint`
- `sota.m13_collect`
- `sota.m13_monthly`
- `sota.m13_weekly`

### cell (2)

- `cell.observatory_prune`
- `cell.observatory_selfcheck`

### nlm (1)

- `nlm.bridge`

### organism (2)

- `organism.scheduled_tick`
- `organism.supervisor`

## APERTO-1: live ma fuori genoma

Il TAC 2026-06-03 stimava 183 automazioni live contro 120 organi dichiarati. Il diff live 2026-06-06 pre-P0p su Pro mostrava che il drift reale andava letto per sorgente runtime, non come singolo delta:

| Sorgente Pro | Totale osservato | Fuori genoma | Classificazione |
| --- | ---: | ---: | --- |
| `launchctl list` | 190 label | 69 | 0 running, 15 failed/non-zero, 54 scheduled-ok |
| `~/Library/LaunchAgents/*.plist` | 197 plist | 73 | 4 plist-only, il resto caricato o schedulato |
| `crontab -l` | 88 entry | 71 | cron-only ancora da dichiarare/importare/decommissionare |
| registry label non caricati nello snapshot Pro | 131 label registry | 9 mancanti | 4 sono Mini, 5 sono Pro/cell da riallineare |
| registry disabled ancora live | 2 disabled organi | 0 | P0g ha rimosso i falsi-chiusi `wr2.canva_apply` e `pro.ollama_warm_pin` |

Guardrail aggiunto: `scripts/audit/live_runtime_vs_genome.py`.

Esempio Pro read-only:

```bash
apps/backend-rag/.venv/bin/python scripts/audit/live_runtime_vs_genome.py \
  --source Pro \
  --launchctl-file /tmp/pro.launchctl \
  --crontab-file /tmp/pro.cron \
  --plist-label-file /tmp/pro.plists \
  --no-local-probe \
  --fail-on-drift
```

Classificazione operativa:

- `importabili/running`: chiuso nella wave P0h per lo snapshot Pro; i 21 label fuori genoma con PID/daemon attivi sono stati importati nel registry con receipt standard tramite `launchagent-state-bridge`.
- `batch dichiarabili`: 54 label fuori genoma `status=0` senza PID, es. agent-library, cicatrix rotation, competitor monitor/router, Intel Lake batch, WR2 metriche/GC/bench. Se restano batch, devono essere dichiarati `genome+batch_declared` con receipt minimo.
- `repair/tombstone`: 15 label fuori genoma non-zero, es. `audit-launchd.daily`, `intel-dedup-gateway`, `meta-dispatcher`, `nuzantara-drive-sync`, `wa-intelligence-incremental`, `wr2.e2e-probe.daily`, `wr2.plist-watchdog`, `consumer-lag.check`, `redis-split-brain.check`, `codex-spark-alarm`, `homebrew.mxcl.ollama`. O si riparano e importano, o si decommissionano.
- `cron-only`: 71 entry Pro non coperte dal registry, incluse NLM pipeline, Fly backup/cost, OpenClaw, cron-agent Python, canary, quota/check, memoria Claude, RAG/cell jobs. Questo e' il backlog principale: cron deve diventare `genome+bridge`, `genome+batch_declared` o `decommissioned`.
- `mismatch registry/live`: `com.matagaruda.sentinel.daily` atteso dal registry ma Pro espone `com.matagaruda.sentinel.hourly`; i quattro Mini label non sono verificati per timeout SSH Mini.

Stato corrente post-P0q: il gate Pro e' chiuso per `launchctl`, plist e cron (`unmanaged_* = 0`, `disabled_registry_* = 0`, `missing_loaded_labels=0` con `--runtime pro_launchd`). L'audit non filtrato sulla stessa snapshot Pro mostra solo quattro label `mini_launchd` mancanti; Mini non e' raggiungibile via Tailscale/SSH in questa sessione, neanche dal path via `pro`, quindi la verifica live Mini resta esplicitamente non chiusa.

Questa classe non e' chiusa solo aggiungendo bridge agli organi gia' in registry. La chiusura richiede una decisione per ogni job live fuori genoma: `genome+bridge`, `genome+batch_declared`, oppure `decommissioned`.

## APERTO-3/4: loop vivi ma senza quarto verbo

### Cell

TAC mostra che Cell ha visto un red reale (`fly_pg_backup` fermo), ma l'allarme non era abbastanza leggibile e i freni lo hanno zittito. Quindi:

- sente: si;
- giudica: si;
- agisce/escala: parziale;
- si rivede: no, non corregge sensore, leggibilita' o soglia da solo.

Fix corretto: riparare `fly_pg_backup` e rendere l'allarme leggibile per sensore/causa, non spegnere il red.

Riallineato in P0s: `cell.fast.red_summary` deriva driver e headline dai sensori, e `PulseEngine` salva quella headline nel DB quando il pulse e' non-green e il reasoner non produce una causa. Il caso backup rosso non resta piu' un red generico: viene persistito come causa leggibile tipo `backup stale 113h`. Resta separato l'eventuale repair effettivo del backup se il job live torna rosso.

Riallineato in P0t: `cell.slow.suppression_digest` raggruppa le soppressioni `alert_suppressed`/`alert_human` sulle headline ancora attive, rispetta cooldown e kill switch, emette un digest non bloccante ogni 60 pulse e registra `suppression_digest_emitted`. Il caso "red vero zittito a ripetizione" non resta piu' invisibile.

### Olympus / rules engine

TAC: `superseded_by = 0` su 13 regole. Il sistema accumula regole, ma non ne sostituisce nessuna. Questo e' il classico loop "learns but does not refine".

Fix corretto: implementare `RulesEngine.supersede(old_rule_name, new_rule_id, reason)` solo per regole learned/reflexion/dream, mai per `source=base`.

Riallineato in P0t: `RulesEngine.supersede()` aggiorna `superseded_by`, rimuove la regola vecchia dalla cache runtime e scrive audit in `olympus_actions`. `propose_supersessions()` resta shadow di default e scrive insight; in `OLYMPUS_RULE_SUPERSEDE_MODE=enforce` applica la supersession solo su regole eleggibili, stessa categoria e signature compatibile.

### Organism dispatcher / proof post-azione

Riallineato in P0r: il ledger ora viene aperto prima del side effect dell'attuatore, e gli attuatori `ActuatorBase` chiudono la stessa riga con `done` o `failed`. Questo non completa tutto il quarto verbo, ma rende interrogabile il risultato post-azione invece di lasciare il dispatcher con una promessa non provata.

### WR2 supervisor/watchdog

WR2 supervisor e' il modello piu' vicino a loop chiuso, ma il watchdog del renderer resta attivo anche quando `canva-renderer` e' kill-switch off. Questo e' un difetto di auto-dismissione.

Fix corretto: se target kill-switch off o superseded, il watchdog si auto-silenzia con receipt esplicita.

Riallineato in P0t: `scripts/wr2_supervisor_watchdog.py` ora scrive una receipt persistente nello state file (`last_self_silence_canva_renderer`, reason, target e detail), pulisce i cooldown `pipeline_frozen`/`success_rate_low` e supporta il marker opzionale `system_settings.wr2_canva_renderer_superseded_by`. Il controllo supervisor heartbeat resta separato e continua a proteggere il daemon WR2.

### EvoSkill / agent-library evolution

Le note S13/TAC indicano che il ciclo di evoluzione skill non chiude: reflexion/voyager/evo accumulano proposte o falliscono, ma non convertono stabilmente esperienza in mutazione validata. Classe `APERTO-4`.

Fix corretto: una pipeline con receipt obbligatoria `proposed -> validated -> applied -> measured -> superseded/pruned`.

## Dove il loop e' effettivamente chiuso oggi

Non tutto e' aperto. `apps/organism/organism/rules/base.yaml` contiene regole autonomiche reali:

- `organ_silent_kickstart`: silenzio organo critical/error -> `restart_agent`.
- `cell_sustained_red_restart`: red sostenuto su `nuzantara-rag` -> `fly_machines_restart`.
- `fly_machine_stopped_restart`: macchina Fly stopped -> `fly_machines_start`.
- `outbox_backlog_propose_rule`: backlog outbox -> `propose_yaml_rule`.
- `enrichment_dep_missing_repair`: `ModuleNotFoundError` su enrichment -> `python_env_repair`.

Queste sono il nucleo da imitare: evento letto, regola, azione, ricevuta.

## Priorita' operative

1. P0 dati: riparare `fly_pg_backup`; rendere il red di Cell leggibile e non zittibile senza escalation.
2. P0 sicurezza: per `skills-bridge-consumer` il template corrente evita segreti inline e usa launcher + `~/.nuzantara-secrets.env`; su questa macchina non risultano label live caricati. Resta da verificare/gestire solo eventuale rotazione esterna se si considera ancora compromessa la chiave storica.
3. P1 rumore vivo: dismettere o ripristinare `wr2.canva-renderer`, WR3 wrappers e `workspace-event-bridge-sheets-import`.
4. P1 Law 1: completato il 2026-06-06; `seo_auto_fixer.py` non apre piu' endpoint Anthropic diretti e il test sorgente blocca la regressione.
5. P1 W64: completato il 2026-06-06; WR2 lease watchdog gia' cattura `asyncpg.InterfaceError`, lint verde e gate CI reale in `.github/workflows/asyncpg-lint.yml`.
6. P2 bridge: completato il 2026-06-06; la registry corrente ha 272/272 enabled con `bridge_source` e 0 no-bridge.
7. P2 genoma: chiuso su Pro nel gate P0q; `scripts/audit/live_runtime_vs_genome.py --runtime pro_launchd` vede 0 drift `launchctl`, plist e cron. Resta da acquisire una snapshot Mini quando `100.93.236.6` torna raggiungibile.
8. P3 quarto verbo: proof post-azione del dispatcher riallineato in P0r; C `robust_parse` e A `red_summary` riallineati in P0s; D `suppression_digest`, B `RulesEngine.supersede` e auto-dismissione watcher riallineati in P0t. Resta da verificare live Mini quando `100.93.236.6` torna raggiungibile.

## Sintesi

La parte critica non e' che "le automazioni non partono". La parte critica e' che molte partono ma non lasciano una traccia biologica utile. Oggi il sistema ha abbastanza scheduler e watchdog; manca uniformita' su receipt, genoma e revisione di se stesso. La chiusura vera del loop e' portare ogni automazione a uno stato dichiarato:

- `closed`: ha bridge, rule/action, metriche e revisione;
- `batch`: gira ma non promette autonomia biologica;
- `disabled`: dismessa esplicitamente;
- `broken`: P0/P1 da riparare o rimuovere.
