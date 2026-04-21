# NLM System Map — v2 grounded inventory

**Data:** 2026-04-22 · **Branch:** `analysis/nlm-sacred-integration-v2` · **Scope:** snapshot del working tree Pro (`/Users/nuzantara/Desktop/nuzantara`) a 04:30 WITA dopo la finestra notturna delle pipeline.

Ogni affermazione qui dentro è ancorata a un file, una riga di log, una riga di crontab, o un UUID verificato in sessione. Le ipotesi non verificate sono esplicitamente marcate `ASSUMED`. Le incongruenze tra fonti sono riportate entrambe.

Questo documento è l'unico substrato della Fase 2 e della Fase 3. Se qui c'è un errore, la lettura sacra e la proposta di redesign erediteranno l'errore.

---

## 1. Due ecosistemi, non uno

Il repo contiene **due ecosistemi NotebookLM separati che non si parlano**:

| Ecosistema | Codice | UUID immigration (esempio) | Consumer primario |
|---|---|---|---|
| **Evaluator / Bali Zero** | `apps/evaluator/nlm_deep_research/` + `apps/backend-rag/backend/services/oracle/` | `cff93ab0-813a-42f2-a8de-36987e724271` (NB-2) | chat cliente `kita.balizero.com`, Naga research, ops briefing |
| **Mata-Garuda / NB-INTEL** | `apps/mata-garuda/mata_garuda/` (config.py:22-40, workers/nlm_feeder.py, agents/nlm_expander_agent.py) | `1ed02e54-542f-426a-94f8-53c5ffde4b7d` (NB-INTEL-Immigration) | Zero via Telegram privato, analisi OSINT locale |

Sono **due NB immigration diversi**. Due NB tax diversi. Nessuno script fa il ponte. Mata-Garuda è per vincolo architetturale (`apps/mata-garuda/CLAUDE.md`) "OSINT blindato, one-way in, local only". I due ecosistemi convivono perché servono scopi diversi — ma la mappa pubblica del sistema parla solo del primo.

Il resto di questo documento è principalmente sull'**ecosistema evaluator** (il cuore produttivo). L'ecosistema Mata-Garuda è trattato in §7 come "terzo polmone".

---

## 2. Inventario NB — 11 attivi + 2 legacy + 6 paralleli NB-INTEL

### 2.1 Core evaluator (NB-2..NB-8, NB-10)

Evidence cross-verificata su 6 sorgenti convergenti: `apps/evaluator/nlm_deep_research/gap_scanner.py:54-153` (DOMAIN_TOPICS), `freshness_monitor.py:57-88` (REGULATORY_DOMAINS), `cross_notebook_correlator.py:58-101` (DOMAIN_REGISTRY), `multimodal_pipeline.py:63-104` (NOTEBOOKS), `apps/backend-rag/backend/services/oracle/nlm_notebook_registry.py:11-115` (NLM_NOTEBOOKS), `apps/backend-rag/backend/services/oracle/nlm_orchestrator.py:17-60`.

| Key | NB | Dominio canonico | UUID | Pipeline | Cron WITA | Claims oggi | Sources |
|---|---|---|---|---|---|---|---|
| immigration | NB-2 | Immigration & Visa | `cff93ab0-813a-42f2-a8de-36987e724271` | `pipeline.py` (orchestrator + T4 social + YT monitor) | **18:10** Mon-Sat ⚠︎ | 42 | 44 active |
| company | NB-3 | Company Setup & KBLI | `933509f9-1561-403d-bd44-4a7a67a36df2` | `nb3_pipeline.py` | 02:45 Mon-Sat | 31 | 47 active |
| tax | NB-4 | Tax & Fiscal | `d4b2eedb-9863-4a1a-81ff-a11b0b45d853` | `nb4_pipeline.py` | 02:20 Mon-Sat | 12 | 0 (no registry) |
| property | NB-5 | Property & Real Estate | `d9438180-5e63-4e2a-a473-6061101f6a8d` | `nb5_pipeline.py` + `nb5_t4_monitor.py` | 02:25 Mon-Sat + T4 18:00 Tue/Thu | 10 | 0 (no registry) |
| operations | NB-6 | Operations & Compliance | `85207af3-352f-4554-8d2a-18f42cc541ba` | `nb6_pipeline.py` + `peraturan_ingestion_trigger.py` | 02:30 Mon-Sat + Sun 21:30 | 10 | 0 (no registry) |
| editorial | NB-7 | Editorial & Content | `f51ab8a0-50d0-49f1-a64f-ebc131fed7b8` | `nb7_pipeline.py` | 02:35 Mon-Sat | 10 | 0 (no registry) |
| lifestyle | NB-8 | Expat Life Bali | `4fd8cd0f-93f1-4e43-9c9e-86c0d581852c` | `nb8_pipeline.py` | 02:40 Mon-Sat | 9 | 0 (no registry) |
| team | NB-10 | Team Guides / HR | `f0307c2c-9220-4160-93c8-f4a6ef4a3b65` | `nb10_pipeline.py` | 02:50 Mon-Sat | 8 | 0 (no registry) |

**Discrepanza strutturale**: `apps/evaluator/nlm_nb2_sources.json` e `nb3_sources.json` hanno 44 / 47 fonti tracciate con stage ACTIVE/QUARANTINE/ARCHIVE, SVS score, flags pinned/essential. Le equivalenti per NB-4..10 hanno **0 fonti tracciate**. Solo due pipeline su otto applicano la disciplina `SourceRegistry` (`registry.py`), le altre emettono claim direttamente senza source accounting. Implicazione: gli invariants `INV_MAX_ACTIVE_SOURCES=70`, `MIN_MASTER_DIGEST_SOURCES=4`, SVS decay — si applicano solo a NB-2 e NB-3.

### 2.2 Meta-business NB (NB-11, NB-12, NB-13)

Sorgente UUID: `apps/evaluator/nlm_deep_research/db_nlm_sync_state.json:2-4`.

| Key | NB | Dominio | UUID | Pipeline | Cron |
|---|---|---|---|---|---|
| ops | NB-11 | Bali Zero Ops Live | `2072e518-e6f9-437d-93ea-f9037ec54052` | `db_to_nlm_sync.py` (portfolio, practices, compliance, team, revenue) | 01:10 WITA daily via `scripts/nlm_pipeline_run.sh` |
| intel | NB-12 | Bali Zero Biz Intel | `5c2c3d90-eed2-4755-86b1-269e637e51e1` | `db_to_nlm_sync.py` (client_segments, company_overview, recent_changes) | idem |
| telemetry | NB-13 | Bali Zero System Telemetry | `53441d9e-fb11-44cc-8dd8-4d70637b651f` | `db_to_nlm_sync.py` (system_health) | idem |

Consumer: `ops_intelligence.py` (ARCH-10) genera briefing esecutivo lunedì 08:00 WITA interrogando NB-11/12/13 via `nlm query notebook`. NB-11/12/13 sono nutriti ESCLUSIVAMENTE da Postgres via SQL aggregati + render Markdown + SHA256 diff (skip se non cambiato).

### 2.3 NB legacy fuori namespace

- **NB-1 "Nuzantara Codebase"** — UUID `f6ecd115-dd89-4c9b-b3dd-071e0e2f1876` (fonte: `scripts/nlm_nb1_daily_refresh.py:41`). Non in `nlm_deep_research/`. Gestito da `scripts/nlm_nb1_daily_refresh.py`. Cron 04:30 WITA (crontab `30 20 * * *` via `~/scripts/cron-agent.sh exec nlm-nb1-daily-refresh`). Rigenera bundle codebase (`backend_01_app_and_agents.txt`, `backend_02_services.txt`, ecc.) e li ricarica. Self-reflection layer — Claude può interrogarlo su architettura. Snapshot pre-mutation in `nlm_deep_research/snapshots/nb1_codebase_pre_*.json`.

- **NB-14 "Claude Code Session Memory"** — UUID `1e5f9b04-9485-4620-a775-801b7e6b0395` (fonte: `~/.claude/scripts/sync-memory-to-nlm.sh:7`, cron `0 3 * * 0`). Dump domenicale `memory.db` SQLite → `group_concat` → `nlm source add` come testo. Consumer: Claude stesso via `notebook_query` per ricostruire contesto di sessioni precedenti.

### 2.4 Parallel universe — NB-INTEL (Mata-Garuda)

`apps/mata-garuda/mata_garuda/config.py:22-29` dichiara 6 UUID distinti:

| Key | Dominio | UUID |
|---|---|---|
| immigration | Intel Immigration | `1ed02e54-542f-426a-94f8-53c5ffde4b7d` |
| tax | Intel Tax | `7fb12c9c-4e12-4a8d-9bd1-c5b857bf310f` |
| regulation | Intel Regulation | `a17f134e-b9ab-42d9-bfc2-5bbc45165c76` |
| press | Intel Press | `9d262101-abeb-4e15-af9c-c38e028c62fe` |
| ai_research | AI Research | `dc5d01cd-e99f-4c8f-aae4-75060b43d0de` |
| self_evolving | MG Self-Evolving Research | `305f5f2e-d2f4-4f77-a771-c2b7aa0867e4` |

Alimentati da `nlm_feeder.py` che consuma lo stream Redis `garuda:enriched` prodotto dalla pipeline OSINT Mata-Garuda (harvesters: `imigrasi_harvester.py`, `bkpm_harvester.py`, `kemlu_harvester.py`, `regulation_watcher.py`, `arxiv_harvester.py`, `github_trending_harvester.py`, ecc.). Routing domain→NB in `config.py:33-42` (`NLM_DOMAIN_ROUTING`). L2 autonomy: `nlm_expander_agent.py:22-24` *propone* nuovi NB-INTEL quando un dominio produce >50 enriched/30gg, non crea — Zero decide via Telegram.

### 2.5 NB citati ma non esistenti

- **NB-9** — citato in `migration_070b_legal_ingest_jobs.py:5` come riferimento ADR. Nessun UUID assegnato. `ASSUMED`: placeholder di numerazione mai materializzato.
- **NB-Xa (primary law notebooks)** — `nlm_notebook_registry.py:14` dichiara `primary_notebook_id: None` per ogni dominio. L'idea di separare "NB-Xa T0+T1 law-only" da "NB-Xb T2+T3 operational" è codificata in `resolve_notebook()` (`_PRIMARY_LAW_KEYWORDS` triggerà il primary se esiste) ma nessun NB-Xa è stato creato. Conseguenza operativa: query con "pasal/uu/pp/permenkumham" fallback sull'operational.

**Totale**: 11 NB attivi (8 world + 3 body) + 2 legacy (self) + 6 NB-INTEL (parallel) = **19 notebook di produzione**.

---

## 3. Flussi dati

### 3.1 Ingest → Claim → Synth → Consume (ecosistema evaluator)

```
[MONDO ESTERNO]
  imigrasi.go.id · oss.go.id · pajak.go.id · atrbpn.go.id · kemnaker.go.id
  YouTube gov · Gemini web search · RSS social · Google Sheet peraturan
        │
        ▼
  ┌─────────────────────────────────────┐
  │   INGEST (cron 02:xx-18:10 WITA)    │
  │                                     │
  │   nbX_pipeline.py                   │◄─── query_decomposer (Ollama qwen3.5)
  │   ├── preflight 12-check invariants │     genera query adversarial per cluster
  │   ├── QueryDecomposer L1/L2         │
  │   ├── nlm query notebook (subproc)  │
  │   ├── extract_claims_from_response  │
  │   ├── SourceRegistry.add_source     │◄── solo NB-2, NB-3
  │   └── SynthesisRoller daily/weekly  │──► [SYNTH-DAILY] [SYNTH-WEEK] in NB
  │                                     │
  │   t4_monitor.py  (social RSS+X)     │──► NB-2 only
  │   nb5_t4_monitor.py (social PBN)    │──► NB-5 only
  │   yt_monitor.py  (YouTube gov RSS)  │──► NB-2,3,4,5 (quando feedparser OK)
  │   peraturan_ingestion_trigger.py    │──► NB-6 (Google Sheet driven)
  │   db_to_nlm_sync.py (Postgres)      │──► NB-11,12,13
  └──────────┬──────────────────────────┘
             │
             ▼
  ┌─────────────────────────────────────┐
  │     NB (NotebookLM, cloud Google)   │
  │                                     │
  │   sources (tier T0..T6)             │
  │   persona (ARCH-2, weekly validate) │
  │   synth rolling (daily/week/month)  │
  │   invariants (70 active cap)        │
  └──────────┬──────────────────────────┘
             │
             ▼
  ┌─────────────────────────────────────┐
  │        OBSERVATION (quotidiano)     │
  │                                     │
  │   gap_scanner.py --layer-a (21:30)  │──► coverage_matrix.gaps[]
  │   gap_scanner.py --layer-b (Sun)    │──► coverage_matrix.coverage{}
  │   gap_scanner.py --remediate (Sun)  │──► nlm research start
  │   freshness_monitor.py 06:00 2×     │──► Gemini web check + NLM research trigger
  │   heartbeat_monitor.py every 6h     │──► Telegram alert
  │   persona_engine --validate Sun     │──► persona OK check
  │   multimodal_pipeline.py weekly     │──► audio/mind-map/infographic
  └──────────┬──────────────────────────┘
             │
             ▼
  ┌─────────────────────────────────────┐
  │         CONSUMER (produzione)       │
  │                                     │
  │   backend-rag/oracle/nlm_orch       │──► chat clienti (kita.balizero.com)
  │     NLM_EXTENDED_ROUTING gate       │    (NB-2/3/4 sempre, NB-5/6/7/8/10 solo se flag)
  │   cross_notebook_correlator         │──► multi-NB fan-out
  │   nlm_enrichment_service            │──► post-RAG enrichment
  │   nlm_verifier (services/rag)       │──► fact-check RAG responses
  │   naga/domain_agent                 │──► ricerca interna (NLM as one source)
  │   ops_intelligence (weekly Mon)     │──► Telegram digest NB-11/12
  │   bali-intel-scraper nlm_research   │──► editorial NB-7 / Mouth articoli
  │   Claude session (on-demand)        │──► troubleshoot via NB-1/NB-14
  └─────────────────────────────────────┘
```

### 3.2 Mata-Garuda parallel flow

```
[MONDO OSINT]
        │
        ▼
  [mata-garuda harvesters]  (CLAUDE.md Mata-Garuda: subprocess CLI only, pydantic only)
        │  imigrasi / bkpm / kemlu / reg watcher / arxiv / github / YT / reddit / tavily
        │
        ▼
  Redis stream `garuda:raw` ─► classifier/ner/embedder/scorer workers ─► `garuda:enriched`
        │
        ▼
  workers/nlm_feeder.py
    route by domain → nb_key in NLM_DOMAIN_ROUTING
    nlm source add (subprocess, rate-limited 10/run × 5s sleep)
        │
        ▼
  NB-INTEL-{immigration|tax|regulation|press|ai_research|self_evolving}
        │
        ▼
  agents/daily_briefing_agent → Telegram Zero (privato)
  agents/nlm_expander_agent (weekly, L2 propose) → Telegram Zero
```

**Cross-ecosystem bridge**: `grep -rn "cff93ab0\|NB_INTEL\|garuda" apps/evaluator/` restituisce zero. `grep -rn "1ed02e54\|NB-2\b" apps/mata-garuda/mata_garuda/` pure zero. Non c'è nessun codice che unisce i due mondi.

---

## 4. Inventario automazioni — 23 entry

Sorgente: `crontab -l` (Pro). Classificazione: verificata via log tail + heartbeat file + pipeline_state.json.

| # | Nome | Cron Pro (WITA) | Script | Status | Evidence |
|---|---|---|---|---|---|
| 1 | nb1_daily_refresh | 04:30 daily | `cron-agent.sh exec nlm-nb1-daily-refresh run_nb1_refresh.sh` | **unknown** | heartbeat file non esiste, log `~/logs/cron-agent/nlm-nb1-daily-refresh.log` mtime 2026-04-21 20:31 |
| 2 | nb2_pipeline | 18:10 Mon-Fri | `run_nb2_pipeline.sh` → `python -m ...pipeline` | **BROKEN** | cron in local time WITA → fires at 18:10 WITA → preflight fail su deadline 02:30 WITA. log `/tmp/cron-nlm-nb2-pipeline.log` mostra "Past deadline" ad ogni run dal 2026-04-12. pipeline_state HALTED. heartbeat stale 19gg (2026-04-03) |
| 3 | nb3_pipeline | 02:45 Mon-Sat | `run_nb3_pipeline.sh` | **degraded** | log mostra COMPLETE 2026-04-22 02:48 · ma `nlm_nb3_pipeline_state.json` dice HALTED 2026-04-12 · heartbeat_nb3_pipeline.json NON esiste |
| 4 | nb4_pipeline | 02:20 Mon-Sat | `run_nb4_pipeline.sh` | **healthy (apparente)** | log COMPLETE 2026-04-22 02:22 · state COMPLETE 2026-04-21 18:22 · heartbeat NON esiste |
| 5 | nb5_pipeline | 02:25 Mon-Sat | `run_nb5_pipeline.sh` | **healthy (apparente)** | log COMPLETE 2026-04-22 02:27 · state COMPLETE · heartbeat NON esiste |
| 6 | nb5_t4_monitor | 18:00 Tue/Thu | `run_nb5_t4_monitor.sh` | **unknown** | log exists 2026-04-21 18:00 · heartbeat NON esiste |
| 7 | nb6_pipeline | 02:30 Mon-Sat | `run_nb6_pipeline.sh` | **healthy (apparente)** | log COMPLETE · state COMPLETE · heartbeat NON esiste |
| 8 | nb7_pipeline | 02:35 Mon-Sat | `run_nb7_pipeline.sh` | **healthy (apparente)** | log COMPLETE · state COMPLETE · heartbeat NON esiste |
| 9 | nb8_pipeline | 02:40 Mon-Sat | `run_nb8_pipeline.sh` | **degraded** | log COMPLETE 2026-04-22 02:44 · ma state HALTED 2026-04-12 · heartbeat NON esiste |
| 10 | nb10_pipeline | 02:50 Mon-Sat | `run_nb10_pipeline.sh` | **degraded** | log COMPLETE 2026-04-22 02:52 · ma state HALTED 2026-04-12 · heartbeat NON esiste |
| 11 | peraturan_ingestion | 21:30 Sun | `run_peraturan_ingestion.sh` | **unknown** | log file exists 2026-04-21 · ultimo run non verificato · heartbeat NON esiste |
| 12 | yt_monitor | ogni 6h :30 | `run_yt_monitor.sh` | **BROKEN** | log 2026-04-22 00:30 mostra tutti 12 canali errano `No module named 'feedparser'` · 0 video ingested da giorni · NON ha heartbeat |
| 13 | t4_monitor (NB-2 social) | non in crontab separato | eseguito via `pipeline.py` T4Monitor class | **unknown** | menzionato in `__init__.py` "every 6h" ma cron corrispondente non trovato |
| 14 | gap_scanner --layer-a | 21:30 daily | `run_gap_scanner.sh --layer-a` | **healthy** | heartbeat fresh 2026-04-22 04:19 · log 2026-04-21 21:35 "Total gaps found: 35" |
| 15 | gap_scanner --layer-b | 19:00 Sun | `run_gap_scanner.sh --layer-b` | **healthy** | heartbeat 2026-04-19 19:04 (weekly, OK) |
| 16 | gap_scanner --remediate | 20:30 Sun | `run_gap_scanner.sh --remediate` | **healthy** | heartbeat 2026-04-19 20:33 (weekly, OK) |
| 17 | freshness_monitor | 06:00 daily 2× | `run_freshness_monitor.sh` | **degraded** | heartbeat 2026-04-21 22:07 · log mostra Gemini "noise response" filtrato 3× su 5 domini + 1 timeout (Ketenagakerjaan) · 0 changes detected, 0 research triggered da giorni |
| 18 | multimodal_pipeline | 06:00 Mon-Fri+Sun | `run_multimodal.sh` | **BROKEN** | log `/tmp/cron-multimodal.log` 2026-04-21 22:00 dice: `/opt/homebrew/opt/python@3.14/bin/python3.14: No module named apps.evaluator.nlm_deep_research.multimodal_pipeline`. wrapper non attiva venv, usa python3.14 system. heartbeat file aggiornato oggi (→ update manuale?) |
| 19 | heartbeat_check | ogni 6h :30 | `run_heartbeat_check.sh --check` | **healthy** | log 2026-04-22 00:30, 06:30 eseguiti |
| 20 | heartbeat_digest | 08:00 daily | `run_heartbeat_check.sh --digest` | **healthy** | stesso log |
| 21 | ops_briefing | 08:00 Mon | `run_ops_briefing.sh` | **healthy** | heartbeat 2026-04-20 00:01 (weekly OK) |
| 22 | persona_validate | 09:00 Sun | `run_persona_validate.sh` | **healthy (oggi risolto)** | heartbeat 2026-04-22 03:52 · log `persona_validate_20260422.log`: "Validation: 7 OK, 0 restored, 0 missing/failed" · persona_state.json ultima `last_verified: 2026-04-03` (state stale ma status OK live) |
| 23 | nlm-deep-research | 01:10 daily | `scripts/nlm_pipeline_run.sh --force` | **healthy** | log `~/logs/cron-agent/nlm-deep-research.log` "NLM Pipeline Completed Successfully" 2026-04-22 01:14 (249s). Questo è orchestrator **globale** dell'evaluator, separato dai singoli nbX cron — fa db_to_nlm_sync + cluster NB-2 |
| mos-sync | 03:00 Sun | `sync-memory-to-nlm.sh` | **unknown** | cron presente, log non ispezionato |

### 4.1 Sintesi classificazione

- **Healthy (verificato)**: 10 — nb4..nb7 pipeline apparenti, gap_scanner A/B/remediate, heartbeat check/digest, ops_briefing, persona_validate, nlm-deep-research
- **Degraded**: 4 — nb3_pipeline (state non salva), nb8_pipeline (idem), nb10_pipeline (idem), freshness_monitor (Gemini noise filtered + 1 timeout)
- **BROKEN**: 3 — nb2_pipeline (cron fires WITA 18:10 → sempre past deadline), yt_monitor (feedparser missing), multimodal_pipeline (venv non attivato)
- **Unknown (non verificato in sessione)**: 6 — nb1_daily_refresh, nb5_t4_monitor, t4_monitor NB-2, peraturan_ingestion, mos-sync, Mata-Garuda watcher launchd

### 4.2 Gap strutturale del heartbeat registry

`apps/evaluator/nlm_deep_research/pipeline_heartbeat_registry.json` lista **18 pipeline** (`nb1_daily_refresh, nb2..nb10 pipeline, nb5_t4_monitor, db_nlm_sync, peraturan_ingestion, ops_briefing, persona_validate, gap_scanner, gap_scanner_layer_b, gap_scanner_remediation, freshness_monitor, multimodal_pipeline`).

Su disco (`~/.agent/decisions/state/heartbeat_*.json`) **esistono 8 file**:

```
heartbeat_freshness_monitor.json        2026-04-21 22:07 ✓
heartbeat_gap_scanner.json              2026-04-22 04:19 ✓
heartbeat_gap_scanner_layer_b.json      2026-04-19 19:04 ✓
heartbeat_gap_scanner_remediation.json  2026-04-19 20:33 ✓
heartbeat_multimodal_pipeline.json      2026-04-22 03:53 ✓ (non corrisponde al BROKEN del cron log)
heartbeat_nb2_pipeline.json             2026-04-03 13:35 ✗ stale 19gg
heartbeat_ops_briefing.json             2026-04-20 00:01 ✓
heartbeat_persona_validate.json         2026-04-22 03:52 ✓
```

**10 pipeline nel registry non registrano mai un heartbeat**: nb1_daily_refresh, nb3..nb8_pipeline, nb10_pipeline, nb5_t4_monitor, db_nlm_sync, peraturan_ingestion. Questo è il **bug di monitoring** più grave: il registry definisce `max_age_hours: 6` per ogni nbX, ma nessuno chiama `heartbeat_monitor.record_success()` al termine della pipeline. Il check a `/30 */6 * * *` quindi emette WARNING/CRITICAL su 10 pipeline **continuamente** — ma Zero non riceve 10 alert ogni 6 ore. O l'alert è muto (filtrato?) o il registry non ha mai funzionato come monitoring reale.

Il `send_alert` in `heartbeat_monitor.py:445` **non filtra** ma aggrega. Quindi se parte viene ignorato il check o Telegram è down o l'alert arriva ma Zero non l'ha notato. Verifica: l'heartbeat `nb2_pipeline` è stale 19gg — Zero dovrebbe aver visto 76 alert di WARNING/CRITICAL/DEAD per nb2 da inizio aprile. **Ipotesi più probabile**: le wrapper script `run_nbX_pipeline.sh` non invocano `python -m heartbeat_monitor --record nbX_pipeline` al termine. Solo alcuni wrapper (multimodal, gap_scanner, freshness, ops_briefing, persona_validate) lo fanno. Lo script `pipeline.py` scrive sul pipeline_state.json ma non chiama il heartbeat helper. Il disallineamento è strutturale: il registry crede di monitorare 18 pipeline ma la scrittura avviene solo da 8.

**Multimodal paradox**: log dice BROKEN 2026-04-21 22:00 ("No module named apps.evaluator.nlm_deep_research.multimodal_pipeline"). Ma heartbeat_multimodal_pipeline.json è fresh 2026-04-22 03:53. Uno dei due è un update fatto a mano o c'è un wrapper alternativo che scrive heartbeat indipendentemente. Da indagare.

### 4.3 Dipendenze Python mancanti

- **feedparser** — non installato nel venv usato dal wrapper `run_yt_monitor.sh`. Grep `ModuleNotFoundError: No module named 'feedparser'` in `/tmp/cron-yt-monitor.log` ricorre 12× per run (ogni canale YouTube in `yt_channels.json`). Installare con `pip install feedparser sgmllib3k` nel venv corretto (probabilmente `apps/backend-rag/.venv`).
- **`apps.evaluator.nlm_deep_research.multimodal_pipeline`** come modulo — il modulo esiste (`multimodal_pipeline.py` 28k righe, classe `MultimodalPipeline`), ma il wrapper `run_multimodal.sh` usa `python3.14` system senza `PYTHONPATH=.` e senza venv attivo. Il modulo non è installato pip, va chiamato `PYTHONPATH=/Users/nuzantara/Desktop/nuzantara python -m apps.evaluator.nlm_deep_research.multimodal_pipeline --run` dopo `source apps/backend-rag/.venv/bin/activate`.

---

## 5. Stato coverage matrix — congelato

`apps/evaluator/nlm_deep_research/coverage_matrix.json` (scritto da gap_scanner layer-A + layer-B):

```
immigration     gaps= 5 coverage= 8 fresh= 0 gap= 8 updated_gaps=2026-04-03 updated_cov=2026-04-12
company         gaps= 5 coverage= 8 fresh= 0 gap= 8 updated_gaps=2026-04-03 updated_cov=2026-04-12
tax             gaps= 5 coverage= 8 fresh= 0 gap= 8 updated_gaps=2026-04-03 updated_cov=2026-04-12
property        gaps= 5 coverage= 8 fresh= 0 gap= 8 updated_gaps=2026-04-03 updated_cov=2026-04-12
operations      gaps= 5 coverage= 8 fresh= 0 gap= 8 updated_gaps=2026-04-03 updated_cov=2026-04-12
editorial       gaps= 5 coverage= 8 fresh= 0 gap= 8 updated_gaps=2026-04-03 updated_cov=2026-04-12
lifestyle       gaps= 5 coverage= 8 fresh= 0 gap= 8 updated_gaps=2026-04-03 updated_cov=2026-04-12
```

Osservazioni:

1. **Tutti i 7 domini: 8/8 topic classificati GAP** (coverage 0% fresh). Layer-B non gira dal 2026-04-12 (`gap_scanner_state.json: layer_a_runs=4, layer_b_runs=1`). Però gap_scanner heartbeat è fresh 2026-04-22 04:19 e il log di ieri 2026-04-21 21:35 dice "Total gaps found: 35" (5 gap × 7 domini = 35). Quindi **gap_scanner --layer-a gira, scrive log, aggiorna heartbeat, ma NON aggiorna `coverage_matrix.json [domain.gaps]`**.

   Lettura del codice: `gap_scanner.py:352-356` scrive `matrix[domain]["gaps"] = gaps` e `matrix[domain]["gaps_updated"] = _now_iso()`, poi `_save_matrix(matrix)` a linea 369. La logica c'è. L'update timestamp dice `2026-04-03`, ma il heartbeat è `2026-04-22`. Due scenari:

   - Scenario A: la scrittura ha successo ma la `coverage_matrix.json` viene successivamente sovrascritta da un altro processo (race con layer-B?). File locale su Pro, cron seriale, non dovrebbe succedere.
   - Scenario B: il match dell'ordine non è così: il heartbeat viene `record_success` dal wrapper `run_gap_scanner.sh`, ma la `_save_matrix` fallisce silenziosamente (eccezione in `_extract_gap_topics` che svuota i gap → `gaps=[]` → condition diversa?).

   Il log `/tmp/cron-gap-scanner.log` di ieri sera (21:35) chiude con "Total gaps found: 35" → non c'è eccezione. Quindi il path riesce. **Ma la data dice 2026-04-03**. Incongruenza.

   Probabile terza causa: `_save_matrix` scrive `coverage_matrix.json` con `default=str`. La `default` serializzerà oggetti datetime come strings — nessun problema. Però il `_now_iso()` è `datetime.now(timezone.utc).isoformat()`. Il 2026-04-03 è vecchio ma non impossible: il file potrebbe essere stato **sovrascritto da un rollback manuale** di stato vecchio (es. restore da snapshot) tra il 12 e il 22 aprile. Da indagare con `git log apps/evaluator/nlm_deep_research/coverage_matrix.json`.

2. **`gaps` contiene dati puliti 5×7=35** (le 5 domande per dominio), **non** frammenti JSON raw. Il bug di parsing che commit `ee1b88c` e `c2b664c` (presenti su `analysis/nlm-sacred-integration` v1, NON su v2) hanno risolto riguardava una vecchia lettura; il file attuale sembra pulito. Da confermare con `jq '.immigration.gaps[]' coverage_matrix.json`.

3. **Divergenza con pipeline**: le pipeline `nbX_pipeline` interrogano NB sui loro cluster-rotation (`CLUSTER_ROTATION` A-F), ma `gap_scanner Layer-B` interroga NB sul `DOMAIN_TOPICS.topics` (lista fissa di 8 topic). **Le due checklist non si sovrappongono** → le pipeline "ingerono" su topic T, ma il coverage matrix misura su topic T'. Questo è un **bug architetturale**, non operativo: finché le due liste divergono, il coverage matrix resterà strutturalmente 100% gap anche con ingest perfetto.

---

## 6. Consumer della conoscenza — chi legge gli NB?

Grep `grep -rln "notebook_query\|resolve_notebook\|NLM_NOTEBOOKS\|nlm_orchestrator" apps/backend-rag/backend/services/` produce 10 moduli non-test.

### 6.1 Mappa consumer reale (ecosistema evaluator)

| Consumer | File | NB letti | Modalità |
|---|---|---|---|
| `NLMOrchestrator` | `backend/services/oracle/nlm_orchestrator.py` | base: NB-2/3/4. extended (env var `NLM_EXTENDED_ROUTING=1`): +NB-5/6/7/8/10 | single-NB + cross-NB fan-out |
| `CrossNotebookCorrelator` | `backend/services/oracle/cross_notebook_correlator.py` | 7 NB core (immigration..lifestyle) | multi-NB parallel query + claim correlation + Ollama synthesis |
| `NLMEnrichmentService` | `backend/services/oracle/` (evocato da orchestrator) | delegato a orchestrator | post-RAG enrichment |
| `nlm_verifier` | `backend/services/rag/nlm_verifier.py` | subset NB per verifica | fact-check risposta RAG |
| `naga/domain_agent` | `backend/services/naga/search_agents/domain_agent.py` | dominio-specifico | NLM come una fonte tra Brave/Exa in research loop |
| `crag_router` | `backend/services/rag/crag_router.py` | via orchestrator | corrective RAG |
| `query_plan` | `backend/services/rag/agentic/query_plan.py` | via orchestrator | agentic RAG |
| `orchestrator_core` + `orchestrator_streaming_core` | `backend/services/rag/agentic/` | via orchestrator | core orchestrator agentic |
| `bali-intel-scraper nlm_research_step` | `apps/bali-intel-scraper/scripts/nlm_research_step.py` | NB-7 editorial (indirect) | research per scraper Mouth |
| `ops_intelligence` | `apps/evaluator/nlm_deep_research/ops_intelligence.py` | NB-11/12/13 | briefing esecutivo lunedì |

**Scoperta primaria**: il backend RAG ha il gate `NLM_EXTENDED_ROUTING`. Quando unset/false (default safe), la produzione **usa solo NB-2/3/4**. NB-5 (property), NB-6 (operations), NB-7 (editorial), NB-8 (lifestyle), NB-10 (team) sono ingestati dalle pipeline ma **non raggiunti dai clienti via chat**. Il lavoro notturno per 5 domini su 8 non atterra mai nella risposta al cliente. Il sistema ha già la mappa estesa (`_EXTENDED_DOMAIN_NOTEBOOK_MAP:45-60`), ha lo shadow logging (`nlm_orchestrator.py:248-260`) per osservare dove divergerebbe. Manca il flip del flag in produzione. Da verificare se è un flag su Fly secrets (`fly secrets list -a nuzantara-rag | grep NLM`).

### 6.2 Mata-Garuda — consumer paralleli

| Consumer | File | Modalità |
|---|---|---|
| `nlm_feeder` | `workers/nlm_feeder.py` | scrive sui 6 NB-INTEL |
| `daily_briefing_agent` | `agents/daily_briefing_agent.py` | query NB-INTEL per digest giornaliero Zero Telegram |
| `nlm_expander_agent` | `agents/nlm_expander_agent.py` | scan domini nuovi, propone NB aggiuntivi |
| `kita_feed_generator` | `agents/kita_feed_generator.py` | genera feed contenuti bali-zero |
| altri ~20 agenti harvester | `agents/*_harvester.py` | OSINT ingest, non leggono NB |

Consumer Mata-Garuda **non legge mai** NB-evaluator. Cliente chat **non legge mai** NB-INTEL. I due mondi sono completamente separati.

### 6.3 Orfani (pipeline senza consumer significativo)

- **Synthesis rolling** (`[SYNTH-DAILY]`, `[SYNTH-WEEK]`, `[SYNTH-MONTH]`) — produce source sintetiche per compressione, ma nessun consumer dowstream legge specificamente i synth (gli NB sono letti come blackbox). Il risultato è compressione interna al NB — utile per l'invariant 70-cap, ma invisibile alla chat.
- **Multimodal output** (`output/multimodal/audio/*.mp3`, `mind-map/*.html`, `infographic/*.pdf`) — generati weekly ma non embedded in nessun canale cliente. Zero li può scaricare e condividere manualmente. Potenziale enorme non sfruttato.
- **`coverage_matrix.gap_pct`** — computato in `gap_scanner.py:447-449`, scritto in matrix, ma nessuno legge `gap_pct` downstream. Non appare in briefing, non triggera niente.
- **`ops_briefing` NB-13 telemetry** — NB-13 esiste, è aggiornato, ma `ops_intelligence.py` interroga principalmente NB-11 e NB-12. NB-13 potenzialmente unused.

---

## 7. Gap analitici

Cinque categorie di gap emerse dalla mappatura, non dalla lettura sacra.

### 7.1 Consumer asimmetrici (ingestiamo X, consumiamo Y)

- NB-5/6/7/8/10: 4-6 cluster notturni ingestano, 40-47 claim/settimana estratti — ma produzione chat accede solo a NB-2/3/4. **~60% del lavoro di ingestion non arriva all'utente finale.**
- `coverage_matrix[topics]` vs `CLUSTER_ROTATION`: due checklist divergenti, il coverage monitor misura un set, le pipeline alimentano l'altro. 100% gap è un artefatto.

### 7.2 Feedback loop aperti (sistema detecta, non agisce)

- `gap_scanner --layer-a` produce 35 gap/giorno → `--remediate` attiva 3/settimana → ~232 gap/settimana evaporano senza remediation.
- `freshness_monitor --scan` ha detectato 0 change in 2 settimane di run; il test con Gemini produce 3/5 "noise filtered" e 1/5 timeout → il sensore è cieco ma non si auto-calibra. Nessuno alerta che Gemini non risponde sensibilmente.
- `persona_validate` heartbeat fresh 2026-04-22 ma `persona_state.json` last_verified 2026-04-03 → lo script valida OK live ma non aggiorna lo state file. Due fonti di verità divergenti.
- `nb_expander_agent` (Mata-Garuda) propone nuovi NB-INTEL solo per Mata-Garuda, non per l'ecosistema evaluator.
- `heartbeat_monitor` alerta quando un NB "DEAD" ma non propone fix automatico né apre ticket.

### 7.3 Ridondanze strutturali

- `_query_notebook(nb_id, query)` subprocess `nlm query notebook` è duplicato in almeno 4 file: `gap_scanner.py:172`, `freshness_monitor.py`, `ops_intelligence.py:98`, `cross_notebook_correlator.py`, `persona_engine.py` (via `_nlm_source_list`). Manca un `apps/evaluator/nlm_deep_research/nlm_bridge.py` helper unificato (il file `nlm_bridge.py:30` esiste ed esporta `NLM_CLI_VERSION` check, ma non espone helper di query).
- `_send_telegram` è duplicato in gap_scanner, freshness_monitor, ops_intelligence, persona_engine, heartbeat_monitor, multimodal_pipeline, t4_monitor, nb5_t4_monitor — 8 copie. Wrapper simile, config stesso (`TELEGRAM_BOT_TOKEN` + `TELEGRAM_OWNER_CHAT_ID`).
- `DOMAIN_TOPICS` (gap_scanner:54), `DOMAIN_REGISTRY` (cross_notebook_correlator:58), `NLM_NOTEBOOKS` (nlm_notebook_registry:11), `REGULATORY_DOMAINS` (freshness_monitor:57), `NOTEBOOKS` (multimodal_pipeline:63), `_BASE_DOMAIN_NOTEBOOK_MAP` + `_EXTENDED_DOMAIN_NOTEBOOK_MAP` (nlm_orchestrator:23/45) — **6 copie** degli stessi UUID, con sottili differenze (keyword sets non allineate, NB-10 mancante in molti, NB-INTEL nessuno). Un refactor in un posto può desync gli altri 5.
- NB-INTEL-Regulation vs NB-6 Operations: entrambi contengono regolamentazione (Mata-Garuda via OSINT, evaluator via peraturan_ingestion Google Sheet). Overlap parziale non riconosciuto.

### 7.4 Dati orfani (produciamo, nessuno legge)

- `apps/evaluator/nlm_nbX_synthesis_state.json` — stato del synthesis_roller: consumer nessuno (usato solo internamente al roller per non re-sintetizzare).
- `handoff/*.json` (generato da `handoff.py`) — per bali-intel-scraper. Consumer vivo ma fragile — se handoff validate fallisce, lo scraper non sa.
- `apps/evaluator/nlm_deep_research/output/multimodal/` — file audio/video/infographic accumulati, nessun canale li distribuisce.
- `snapshots/nbX_sources_pre_*.json` — snapshot pre-mutation, solo per rollback manuale.

### 7.5 Consumer orfani (codice si aspetta X, X non esiste)

- `_PRIMARY_LAW_KEYWORDS` keywords triggerano `primary_notebook_id` path in `resolve_notebook()`, ma `primary_notebook_id: None` per ogni dominio. Il code path è dead finché qualcuno non crea NB-Xa.
- `NB-9` citato in migration 070b come placeholder ADR, mai materializzato. Se il progetto citato viene importato altrove aspettandosi UUID, rompe.
- `ops_intelligence.py:_load_nb_ids` cerca NB-13 telemetry ma nessuna query nel file lo usa nel briefing — solo NB-11/12.
- `CROSS_DOMAIN_NOTEBOOKS` definisce combinazioni `property+tax`, `property+company`, `team+tax`, `operations+compliance` — tutte attive solo se `NLM_EXTENDED_ROUTING=1`. Altrimenti dead code.
- `primary_notebook_id` pathway in backend resolve: 12 linee di logica unreachable fino a creazione NB-Xa.

---

## 8. Stato sinottico (TL;DR)

Un lettore che scorre rapidamente deve portare a casa questi cinque fatti:

1. **19 NB totali** (11 evaluator + 2 legacy + 6 NB-INTEL paralleli). Due ecosistemi isolati: evaluator/Bali-Zero (chat cliente) e Mata-Garuda/NB-INTEL (OSINT Zero-only).

2. **3 pipeline broken su 23 automazioni**: `nb2_pipeline` (cron WITA 18:10 past deadline 02:30), `yt_monitor` (feedparser missing), `multimodal_pipeline` (wrapper venv). 4 degradate. 6 unknown. 10 verificate healthy.

3. **Monitoring scollegato dal monitorato**: heartbeat registry liste 18 pipeline, solo 8 scrivono heartbeat; le altre 10 emettono WARNING ogni 6h in teoria ma l'alert non è mai stato percepito dall'umano → probabile che i wrapper nbX non chiamino mai `heartbeat_monitor --record`.

4. **Consumer asimmetrico**: chat cliente accede solo a NB-2/3/4 (base map default). NB-5/6/7/8/10 ingestati nightly ma **non arrivano mai all'utente** finché `NLM_EXTENDED_ROUTING=1` non viene settato. Il codice è pronto (`_EXTENDED_DOMAIN_NOTEBOOK_MAP` + shadow logging).

5. **Coverage matrix bug architetturale**: le pipeline ingerono su `CLUSTER_ROTATION` (es. NB-2 cluster A-E), ma `gap_scanner layer-B` misura su `DOMAIN_TOPICS.topics` (8 topic fissi per dominio). Le due liste non convergono. Coverage 100% GAP è un artefatto di misura, non una diagnosi di ingestion.

Questa mappa è il substrato di Fase 2 (sacred reading) e Fase 3 (redesign). Da qui, ogni proposta deve (a) ridurre ridondanza, (b) chiudere un loop aperto, (c) rendere accessibile un NB orfano, oppure (d) allineare due fonti di verità divergenti. Proposte che non fanno nessuna di queste quattro cose sono ornamentali.

---

## 9. Post-publication correction (2026-04-22 Sprint 0 investigation)

Eseguendo Sprint 0 §2.5 "Investigate nb3/8/10 state write-back" e §2.6 "Investigate coverage_matrix divergence", è emerso che **i due bug segnalati in §4 (degraded nb3/nb8/nb10) e in §5 (coverage matrix frozen) sono falsi positivi** con la stessa causa radice: **i file di stato runtime sono tracciati in git E marcati in `.gitignore`**. Il git honors la tracciatura. Ogni `git checkout` ripristina il file al contenuto del commit HEAD (tipicamente 2026-04-12 o precedente), sovrascrivendo la scrittura che la pipeline effettua correttamente a runtime.

### Cosa correggere nelle classificazioni di §4.1

- **nb3_pipeline, nb8_pipeline, nb10_pipeline**: da "degraded" a "**healthy**". Il log conferma COMPLETE + synth daily OK; il state file appariva stale solo per il bug git.
- **Coverage matrix §5**: non è "layer-B non gira" o "gap_scanner non scrive"; è "git overwrite". `gap_scanner.py:317 _save_gap_state` scrive regolarmente, ma al successivo checkout il contenuto torna al commit del 2026-04-12.

### Cosa resta corretto in §4.1

- **nb2_pipeline** BROKEN — confermato bug cron timezone (fix applicato Sprint 0.1).
- **yt_monitor** BROKEN — feedparser era davvero mancante (risolto pre-sessione).
- **multimodal_pipeline** BROKEN — wrapper venv era davvero rotto (risolto da sessione concorrente, commit `52a60db43`).
- **Gap strutturale heartbeat §4.2**: 10 wrapper non chiamavano mai `heartbeat_monitor --record` — bug reale, fix applicato Sprint 0.4 (commit `0b7f2e6cf`).

### Impatto sullo "Stato sinottico" §8

Punto 2 andrebbe ri-scritto: "3 pipeline broken" resta (con un fix applicato a nb2, uno pre-sessione, uno dalla parallela). "4 degradate" scende a **1** (solo freshness_monitor Gemini noise resta degradato, perché Gemini API è fuori dal nostro controllo).

Punto 5 "Coverage matrix bug architetturale" resta valido in astratto (le due checklist `CLUSTER_ROTATION` vs `DOMAIN_TOPICS.topics` divergono davvero), ma la percezione "100% GAP" era amplificata dal git overwrite — i dati live del gap_scanner potrebbero mostrare una distribuzione diversa quando non soggetti a ripristino git.

### Dettagli completi

Vedi `BUGS_FOUND.md` (Bug 1) sulla stessa directory — elenca i ~40 file affected, il fix consigliato (`git rm --cached` dedicato su main), e perché non è stato applicato qui (out-of-scope per il branch analisi, conflitti attesi con sessioni parallele attive).

**Lezione operativa per future analisi**: prima di classificare "pipeline degraded" basandosi su discrepanza log vs state file, verifica `git ls-files <state-file>` e `grep <state-file> .gitignore`. Se entrambi non-vuoti → sospetta il tracked-before-ignore, non la pipeline.
