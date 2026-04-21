# NLM System Map — Inventario tecnico grounded

**Data:** 2026-04-22 · **Branch:** `analysis/nlm-sacred-integration` · **Snapshot:** working tree @ Pro cwd `/Users/nuzantara/Desktop/nuzantara`

Ogni affermazione in questo documento ha come ancora un file, una riga di log, o una riga di crontab verificata in sessione. Dove un'ipotesi non è stata verificata è marcata `ASSUMED`. Dove un'informazione è contraddittoria tra due fonti, entrambe sono riportate.

---

## 1. Inventario dei notebook (11 NB + 2 legacy)

Bali Zero ha **11 NotebookLM attivi** (UUID verificati) più 2 notebook legacy (NB-1 master e NB-14 session memory) che vivono fuori dal namespace `nlm_deep_research`. Gli 11 attivi sono gestiti dal modulo `apps/evaluator/nlm_deep_research/` e consumati sia dalle pipeline di ingestion notturne sia dal backend RAG (`apps/backend-rag/backend/services/oracle/`).

### 1.1 Dominio NB: il core (NB-2..NB-8, NB-10)

Questa è la tassonomia canonica su cui si regge tutto il sistema. Ogni NB ha un UUID, un dominio, un label, un set di keyword di routing e una pipeline notturna dedicata. Fonti verificate: `apps/evaluator/nlm_deep_research/gap_scanner.py:54-153` (DOMAIN_TOPICS), `apps/evaluator/nlm_deep_research/freshness_monitor.py:57-97` (REGULATORY_DOMAINS), `apps/evaluator/nlm_deep_research/cross_notebook_correlator.py:58-101` (DOMAIN_REGISTRY), `apps/backend-rag/backend/services/oracle/nlm_notebook_registry.py:11-115` (NLM_NOTEBOOKS), `apps/backend-rag/backend/core/legal_config.py:21-25` (NB_NOTEBOOKS), `apps/evaluator/nlm_deep_research/multimodal_pipeline.py:63-104` (NOTEBOOKS).

| Key             | NB    | Dominio canonico        | UUID                                   | Pipeline script                                         | Cron WITA                        | Cron UTC                      | File stato                                                                                                    |
| --------------- | ----- | ----------------------- | -------------------------------------- | ------------------------------------------------------- | -------------------------------- | ----------------------------- | ------------------------------------------------------------------------------------------------------------- |
| immigration     | NB-2  | Immigration & Visa      | `cff93ab0-813a-42f2-a8de-36987e724271` | `pipeline.py` (main orchestrator con T4 social monitor) | Mon-Sat 02:10                    | 10 18 \* \* 0-5               | `nlm_nb2_pipeline_state.json`, `nlm_nb2_sources.json`, `nlm_nb2_claims.jsonl`, `nlm_nb2_synthesis_state.json` |
| company         | NB-3  | Company Setup & KBLI    | `933509f9-1561-403d-bd44-4a7a67a36df2` | `nb3_pipeline.py`                                       | Mon-Sat 02:45                    | 45 2 \* \* 1-6                | `nlm_nb3_*` (4 file)                                                                                          |
| tax             | NB-4  | Tax & Fiscal            | `d4b2eedb-9863-4a1a-81ff-a11b0b45d853` | `nb4_pipeline.py`                                       | Mon-Sat 02:20                    | 20 2 \* \* 1-6                | `nlm_nb4_*`                                                                                                   |
| property        | NB-5  | Property & Real Estate  | `d9438180-5e63-4e2a-a473-6061101f6a8d` | `nb5_pipeline.py` + `t4_monitor` (social)               | Mon-Sat 02:25 + T4 Tue/Thu 18:00 | 25 2 \* _ 1-6 / 0 18 _ \* 2,4 | `nlm_nb5_*` + `t4_nb5_config.json`, `t4_state.json`                                                           |
| operations      | NB-6  | Operations & Compliance | `85207af3-352f-4554-8d2a-18f42cc541ba` | `nb6_pipeline.py` + `peraturan_ingestion_trigger`       | Mon-Sat 02:30 + Sun 21:30        | 30 2 \* _ 1-6 / 30 21 _ \* 0  | `nlm_nb6_*`                                                                                                   |
| editorial       | NB-7  | Editorial & Content     | `f51ab8a0-50d0-49f1-a64f-ebc131fed7b8` | `nb7_pipeline.py`                                       | Mon-Sat 02:35                    | 35 2 \* \* 1-6                | `nlm_nb7_*`                                                                                                   |
| lifestyle/expat | NB-8  | Expat Life Bali         | `4fd8cd0f-93f1-4e43-9c9e-86c0d581852c` | `nb8_pipeline.py`                                       | Mon-Sat 02:40                    | 40 2 \* \* 1-6                | `nlm_nb8_*`                                                                                                   |
| team            | NB-10 | Team Guides Bali Zero   | `f0307c2c-9220-4160-93c8-f4a6ef4a3b65` | `nb10_pipeline.py`                                      | Mon-Sat 02:50                    | 50 2 \* \* 1-6                | `nlm_nb10_*`                                                                                                  |

### 1.2 NB meta-operativi: ops/intel/telemetry (NB-11, NB-12, NB-13)

Questi tre notebook non hanno pipeline di ingestion esterna: sono riempiti da `db_to_nlm_sync.py`, che estrae aggregati da Postgres (CRM, practices, compliance, team activity) e li renderizza come Markdown narrativo prima di caricarli in NLM. UUID verificati in `db_nlm_sync_state.json:2-4`. Documentazione codice in `ops_intelligence.py:34-64` (ARCH-10) e `db_nlm_templates.py` (renderers).

| Key       | NB    | Dominio                         | UUID                                   | Pipeline                                                                                                                     | Cron                                               | Note                                                              |
| --------- | ----- | ------------------------------- | -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- | ----------------------------------------------------------------- |
| ops       | NB-11 | Bali Zero Ops Live              | `2072e518-e6f9-437d-93ea-f9037ec54052` | `db_to_nlm_sync.py` → renderers (portfolio_snapshot, practices_pipeline, compliance_radar, team_activity, revenue_dashboard) | Daily 01:10 WITA via `scripts/nlm_pipeline_run.sh` | 10 source-hash tracked in state (SHA256 diff → skip if unchanged) |
| intel     | NB-12 | Bali Zero Business Intelligence | `5c2c3d90-eed2-4755-86b1-269e637e51e1` | `db_to_nlm_sync.py` → renderers (client_segments, company_overview, recent_changes)                                          | idem                                               | consumer: `ops_intelligence.py` per briefing lunedì               |
| telemetry | NB-13 | Bali Zero System Telemetry      | `53441d9e-fb11-44cc-8dd8-4d70637b651f` | `db_to_nlm_sync.py` → renderer (system_health)                                                                               | idem                                               |                                                                   |

Consumer downstream per NB-11/12: `ops_intelligence.py:34-48` produce un "executive briefing" settimanale (lunedì 08:00 WITA) che interroga i tre NB meta e invia digest Telegram.

### 1.3 NB legacy fuori namespace (NB-1, NB-14)

**NB-1 "Nuzantara Codebase"** — UUID `f6ecd115-dd89-4c9b-b3dd-071e0e2f1876` (fonte: `scripts/nlm_nb1_daily_refresh.py:41`). Non fa parte di `nlm_deep_research/`: è gestito da `scripts/nlm_nb1_daily_refresh.py`, che rigenera i bundle di sorgenti del monorepo (backend app, services, migrations) e li ricarica quotidianamente. Cron: `30 20 * * *` WITA 04:30 via `~/scripts/cron-agent.sh exec nlm-nb1-daily-refresh`. Snapshot pre-mutation in `nlm_deep_research/snapshots/nb1_codebase_pre_*.json`. NB-1 è "il codice stesso dell'organismo" — self-reflection layer, consumabile da Claude durante troubleshooting architetturale.

**NB-14 "Claude Code Session Memory"** — UUID `1e5f9b04-9485-4620-a775-801b7e6b0395` (fonte: `~/.claude/scripts/sync-memory-to-nlm.sh:7`). Non gestito da `nlm_deep_research/`: riceve dump settimanale domenicale (03:00 WITA) delle sessioni Claude Code (SQLite `memory.db` → group_concat → `nlm source add`). Consumer: Claude stesso via `notebook_query` per ricostruire il contesto di conversazioni passate. NB-14 è "memoria episodica esterna di Claude".

### 1.4 NB citati in comments ma non implementati

- **NB-9** — citato in `migration_070b_legal_ingest_jobs.py:5` come riferimento ADR ("zero new services") ma non esiste notebook con questo numero nel registry. `ASSUMED`: placeholder nomenclaturale per "ADR repository" mai materializzato.
- **NB-2a** (immigration primary law) — `nlm_notebook_registry.py:14` dichiara `primary_notebook_id: None` per ogni dominio. I notebook "a-side" (T0+T1 primary law only) sono pianificati ma mai creati. Conseguenza operativa: keyword "pasal/uu/pp/permenkumham" in `_PRIMARY_LAW_KEYWORDS` causano fallback all'operational notebook — nessuna separazione legge/prassi.

### 1.5 Fonti di ingestion per NB (tabella condensata)

| NB    | Ingest attivi oggi (verificato nei log)                                                                                                                                                                                                               | Fonti esterne                                                                                                                           |
| ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| NB-2  | pipeline L1/L2 (Ollama qwen3.5 decomposer + NLM query cluster rotation) + T4 social monitor (RSS ngurahrai/ditjenimigrasi + government websites + X/Twitter) + yt_monitor (RSS YouTube `UCgBMrLLtuI2ULWvWQ4CTYOw` ditjen_imigrasi + 3-4 altri canali) | imigrasi.go.id, kemenkumham.go.id, YouTube gov channels                                                                                 |
| NB-3  | nb3_pipeline cluster rotation (6 cluster A-F)                                                                                                                                                                                                         | oss.go.id, bkpm.go.id, UU 40/2007, notaris sources                                                                                      |
| NB-4  | nb4_pipeline (7 cluster A-G)                                                                                                                                                                                                                          | pajak.go.id, DJP, DDTC, Kemenkeu, PMK updates                                                                                           |
| NB-5  | nb5_pipeline (6 cluster) + T4 social monitor property (RSS + Twitter PBN, RTRW, WNA property)                                                                                                                                                         | atrbpn.go.id, bpn.go.id, perda Bali, BPN                                                                                                |
| NB-6  | nb6_pipeline (6 cluster) + peraturan_ingestion_trigger (Google Sheet driven, domenicale)                                                                                                                                                              | Google Sheet `1Je7eAK3ya_P5yY9L_JtnwRzkTDrucnzgZ4PvvWlb2us` + PDF official → /api/legal/upload su Fly + Drive folder + `nlm source add` |
| NB-7  | nb7_pipeline (5 cluster)                                                                                                                                                                                                                              | Google Helpful Content, E-E-A-T, YMYL, SEO best practice                                                                                |
| NB-8  | nb8_pipeline (6 cluster)                                                                                                                                                                                                                              | assicurazioni expat, BIMC Siloam, cost of living, banking                                                                               |
| NB-10 | nb10_pipeline (6 cluster Indonesia-centric)                                                                                                                                                                                                           | Kemnaker, BPJS, UU Cipta Kerja, AI legal liability                                                                                      |
| NB-11 | db_to_nlm_sync: portfolio/practices/compliance/team                                                                                                                                                                                                   | Postgres → Markdown → NLM                                                                                                               |
| NB-12 | db_to_nlm_sync: client_segments/company_overview/recent_changes                                                                                                                                                                                       | idem                                                                                                                                    |
| NB-13 | db_to_nlm_sync: system_health                                                                                                                                                                                                                         | idem                                                                                                                                    |
| NB-1  | scripts/nlm_nb1_daily_refresh.py genera bundle codebase (`backend_01_app_and_agents.txt`, `backend_02_services.txt`, etc.) e rimpiazza i source modificati                                                                                            | git diff, monorepo walk                                                                                                                 |
| NB-14 | ~/.claude/scripts/sync-memory-to-nlm.sh: SQLite memory.db → group_concat → source text                                                                                                                                                                | Sessioni Claude Code passate                                                                                                            |

### 1.6 Stato health per NB (snapshot 2026-04-22 ~02:50 WITA)

Verificato da: log `/tmp/cron-nlm-nb*-pipeline.log` + `~/.agent/decisions/state/heartbeat_*.json` + brief files `~/.agent/decisions/nlm_briefs/daily_intelligence_brief_nb*.json`.

| NB        | Last run completato                | Esito                                              | Claims totali     | Note                                                                                                                                                                                                                                                                                     |
| --------- | ---------------------------------- | -------------------------------------------------- | ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| NB-2      | 2026-04-21 10:10 UTC (18:10 WITA)  | **halted_at preflight**                            | 42                | Pre-flight fallita — non è chiaro quale check; log dice `degradation: NOMINAL` ma nessun cluster eseguito. Last heartbeat `heartbeat_nb2_pipeline.json` = 2026-04-03 13:35 (non registrato da 19 giorni).                                                                                |
| NB-3      | 2026-04-21 02:47 WITA              | success (cluster F)                                | ? (brief scritto) |                                                                                                                                                                                                                                                                                          |
| NB-4      | 2026-04-22 02:22 WITA (10 min fa)  | success (cluster F "Tax Admin & Coretax")          | 12                |                                                                                                                                                                                                                                                                                          |
| NB-5      | 2026-04-22 02:27 WITA              | success (cluster "Property Taxes")                 | 10                |                                                                                                                                                                                                                                                                                          |
| NB-6      | 2026-04-22 02:32 WITA              | success (cluster "OSS-RBA Licensing & KBLI 2025")  | 10                |                                                                                                                                                                                                                                                                                          |
| NB-7      | 2026-04-22 02:37 WITA              | success (cluster "Content Formats & Distribution") | 10                |                                                                                                                                                                                                                                                                                          |
| NB-8      | 2026-04-22 02:42 WITA              | in progress (PP 28/2025 query in L2)               | 10                | Produce `nb8.lock` — verificato presente in working tree                                                                                                                                                                                                                                 |
| NB-10     | 2026-04-21 02:52 WITA              | ? (brief scritto)                                  | ?                 |                                                                                                                                                                                                                                                                                          |
| NB-11..13 | last_uploaded 2026-04-01 14:05 UTC | **stale 21 giorni**                                | —                 | `db_nlm_sync_state.json` non è stato aggiornato dal 1° aprile. Cron nlm-deep-research configurato daily 01:10 WITA (`scripts/nlm_pipeline_run.sh`) ma scrive solo su `~/logs/cron-agent/nlm-deep-research.log`; non è stato verificato se sta eseguendo il sync DB→NLM o solo un subset. |
| NB-1      | ? (nessun heartbeat*nb1*\*)        | ?                                                  | —                 | Cron migrato 2026-04-14 a `cron-agent.sh exec nlm-nb1-daily-refresh` → log `~/logs/cron-agent/nlm-nb1-daily-refresh.log`. Non ispezionato in questa sessione (sarebbe quarta lettura log).                                                                                               |
| NB-14     | 2026-04-20 03:00 WITA domenicale   | `ASSUMED` ok                                       | —                 | Cron `0 3 * * 0`. Non verificato il log `/tmp/cron-mos-sync.log`.                                                                                                                                                                                                                        |

**Health summary verificato dall'ultimo heartbeat digest (2026-04-22 00:30 WITA)**: `persona_validate: CRITICAL (434.7h)`, `multimodal_pipeline: NEVER_RAN`, `gap_scanner: OK 2.9h`, `freshness_monitor: OK 2.4h`, `gap_scanner_layer_b: OK 53.4h`, `gap_scanner_remediation: OK 51.9h`. Mancano dal digest tutti i `nb*_pipeline` eccetto `nb2_pipeline` (CRITICAL, ultimo heartbeat 19 giorni fa). Questo indica che i pipeline nb3-nb10 **funzionano** (log recenti lo confermano) ma **non registrano heartbeat** — probabile bug di cabling: gli script `run_nb*_pipeline.sh` lo fanno (verificato `run_nb2_pipeline.sh:44-46`), quindi heartbeat dovrebbe essere registrato se lo script exit=0. Se il log mostra success ma nessun heartbeat, o lo script exit è non-zero (nonostante log dica success) o il percorso Python `-m apps.evaluator.nlm_deep_research.heartbeat_monitor --record` fallisce silenziosamente. **GAP DA VERIFICARE.**

---

## 2. Mappa dei flussi

### 2.1 Flusso core di un NB di dominio (NB-2..8, NB-10)

```
   ┌─────────────────────────┐
   │ Cron cron-runner.sh     │  (OpenClaw)
   │ 02:10-02:50 WITA Mon-Sat│
   └───────────┬─────────────┘
               │
               ▼
   ┌─────────────────────────┐
   │ run_nbX_pipeline.sh     │  pid-file guard, venv activate, secrets load
   └───────────┬─────────────┘
               │
               ▼
   ┌─────────────────────────┐       ┌──────────────────┐
   │ nbX_pipeline.py (main)  │──────▶│ Preflight gate   │ 12 check
   │ PIPELINE_DEADLINE=03:00 │       │ — weekend/budget │
   └───────────┬─────────────┘       │ — circuit breaker│
               │ pass                │ — invariants     │
               ▼                     └──────────────────┘
   ┌─────────────────────────┐
   │ today_cluster()         │  weekday → cluster letter (A-F)
   └───────────┬─────────────┘
               │
               ▼
   ┌─────────────────────────┐
   │ QueryDecomposer         │  Ollama qwen3.5:9b (local, no API paid)
   │ (ARCH-3 adaptive L1)    │  fallback: static L1_QUERIES templates
   └───────────┬─────────────┘
               │
               ▼
   ┌─────────────────────────┐
   │ take_snapshot (ARCH-8)  │──▶ snapshots/nbX_*_pre_YYYY-MM-DD_HH-MM.json
   └───────────┬─────────────┘
               │
               ▼
   ┌─────────────────────────┐
   │ nlm_bridge.nlm_query()  │──▶ HTTP POST /nlm/query on :18790 (HMAC)
   │ or nlm CLI subprocess   │   or subprocess `nlm query notebook <id> <q>`
   └───────────┬─────────────┘
               │
               ▼
   ┌─────────────────────────┐
   │ claim_extractor         │  15 claim categories (LEGAL_CHANGE, etc.)
   │ → claims.jsonl append   │  confidence thresholds: 0.35/0.55/0.75
   └───────────┬─────────────┘
               │
               ▼
   ┌─────────────────────────┐
   │ L2 query (with L1 conv) │  cross-cluster context injection
   └───────────┬─────────────┘
               │
               ▼
   ┌─────────────────────────┐
   │ compute_svs (per source)│  tier/freshness/claims/citations/unique/bonus
   │ compute_nhs (notebook)  │  aggregate health 0-1, 5 bands
   └───────────┬─────────────┘
               │
               ▼
   ┌─────────────────────────┐
   │ synthesis_roller        │  daily → weekly → monthly compression
   │ Ollama qwen3.5 synth    │  prevents NLM overflow (300-600 src cap)
   │ tombstone old synths    │
   └───────────┬─────────────┘
               │
               ▼
   ┌─────────────────────────┐
   │ handoff.generate        │  TRS-filtered (>=0.65) findings
   │ → ~/.agent/decisions/   │
   │   nlm_to_scraper/       │  consumer: bali-intel-scraper 03:00
   └───────────┬─────────────┘
               │
               ▼
   ┌─────────────────────────┐
   │ heartbeat_monitor       │  atomic write ~/.agent/decisions/state/
   │ --record nbX_pipeline   │  heartbeat_nbX_pipeline.json
   └─────────────────────────┘
               │
               ▼
   ┌─────────────────────────┐
   │ brief JSON output       │  ~/.agent/decisions/nlm_briefs/
   │                         │  daily_intelligence_brief_nbX.json
   └─────────────────────────┘
```

### 2.2 Flussi orizzontali (inter-NB / meta)

**Gap scanner Layer A (`gap_scanner.py --layer-a`)** — daily 21:30 WITA:

```
for NB in [NB-2..NB-8]:
  query(NB, "Quali sono le 5 domande a cui NON puoi rispondere?")
  extract gap topics → coverage_matrix.json [domain.gaps]
telegram digest
```

**Gap scanner Layer B (`gap_scanner.py --layer-b`)** — weekly Sun 19:00 WITA:

```
for NB in [NB-2..NB-8]:
  for topic in DOMAIN_TOPICS[domain].topics:
    query(NB, "Qual è il regolamento più recente su {topic}? Se non hai info: GAP")
    classify: FRESH/AGING/STALE/GAP (based on year extraction + keyword)
  write coverage_matrix.json [domain.coverage]
telegram digest with health_pct and gap_pct per domain
```

**Gap remediation (`gap_scanner.py --remediate`)** — weekly Sun 20:30 WITA:

```
read coverage_matrix.json
targets = [(domain, topic, nb_id) for all GAP first, then STALE]
for target in targets[:3]:  # MAX_REMEDIATIONS_PER_RUN=3
  content = gemini_search(f"{topic} Indonesia 2025 2026")  # subprocess CLI
  nlm source add <nb_id> --title "[label] topic — date" --text content
  update coverage_matrix: mark topic FRESH
telegram digest
```

**Freshness monitor (`freshness_monitor.py --scan`)** — daily 07:00+19:00 WITA:

```
for domain_config in REGULATORY_DOMAINS:  # 5 domains (imm/oss/djp/bpn/kemnaker)
  response = gemini_search(domain_config.query)  # site:imigrasi.go.id OR site:kemenkumham.go.id etc.
  if "NO_CHANGE" not in response:
    nlm research start <nb_id> --query RESEARCH_QUERY_TEMPLATES[domain]  # async
    research_triggered += 1 (max 3/run)
telegram digest changes
```

**Cross-notebook correlator (`cross_notebook_correlator.py`)** — on-demand (no cron):

```
query user → detect_domains(q) via keyword overlap
if len(domains) >= 2:
  parallel async calls to each NB (max 4, timeout 90s each)
  extract claims from each
  build correlation matrix: AGREE / CONTRADICT / COMPLEMENT
  ollama qwen3.5:9b synthesis of unified answer
  return CrossNotebookResult
consumer: apps/backend-rag/backend/services/oracle/cross_notebook_correlator.py (backend-side mirror)
```

**Ops briefing (`ops_intelligence.py --briefing`)** — Monday 08:00 WITA:

```
load NB-11/12/13 IDs from db_nlm_sync_state.json
query NB-11 "pipeline practices bottleneck"
query NB-12 "pattern clients segment"
detect anomalies (threshold 25%)
telegram executive briefing
```

**Multi-modal factory (`multimodal_pipeline.py --run`)** — daily/weekly WEEKLY_SCHEDULE:

```
day_of_week → [(nb_key, artifact_type)]  # Mon: NB-2 audio, Tue: NB-3 mind-map, ...
for target in today_targets:
  nlm artifact create <nb_id> --type {audio|infographic|mind-map|report}  # async, poll status
  nlm download artifact <id> → output/multimodal/<nb>_<type>_<date>.{m4a|png|json|md}
```

**Peraturan ingestion (`peraturan_ingestion_trigger.py`)** — weekly Sun 21:30 WITA:

```
read Google Sheet 'list peraturan' (SA auth)
for row with Status=PENDING:
  download PDF from official URL
  POST /api/legal/upload on Fly.io (X-API-Key)  # RAG + KG pipeline
  upload PDF to Drive PERATURAN folder (SA)
  nlm source add NB-6 --type file --file pdf
  update Sheet row: Status=INGESTED, Drive_File_ID, timestamp
```

### 2.3 Entry point umani ("dove legge un operatore")

- **Terminale** `mcp__notebooklm-mcp__notebook_query` tool (Claude Desktop / claude-in-chrome) — query diretta a qualunque NB per diagnostica o Q&A.
- **Backend API** `apps/backend-rag/backend/services/oracle/oracle_service.py` + `smart_oracle.py` — routing automatico delle domande utente RAG verso il giusto NB via `resolve_notebook()`.
- **Telegram** — digest automatici (Heartbeat digest 00:00, Gap Layer A 21:35, Freshness 07:00/19:00, Ops briefing lunedì 08:00, Remediation domenicale).
- **Brief files** `~/.agent/decisions/nlm_briefs/daily_intelligence_brief_nb*.json` — consumabili da altri agenti (scraper, dashboard, feed processor).
- **Handoff files** `~/.agent/decisions/nlm_to_scraper/handoff/*.json` — consumati dal bali-intel-scraper alle 03:00 WITA per enriching del content editoriale.

### 2.4 Loop di feedback strutturali esistenti

1. **Gap → remediate → FRESH.** Loop attivo: layer-B scopre GAP/STALE, remediate fa gemini search e aggiunge source, matrix marca FRESH. **Freno**: max 3 remediation/run, rate limit NLM.
2. **Freshness scan → research trigger.** Loop attivo: scan gemini detecta "cambiamento regolatorio", triggera `nlm research start` su NB (async). **Freno**: max 3 trigger/run, 30s delay.
3. **Claims → synthesis roller → tombstone.** Loop attivo: claims giornalieri → SYNTH-DAILY → SYNTH-WEEKLY → SYNTH-MONTHLY. **Freno**: word cap 400/600/800.
4. **Heartbeat check → telegram alert.** Loop attivo: ogni 6h check tutti i pipeline, alert su WARNING+. **Freno**: soglie staleness, emoji degradation.
5. **Preflight → halt.** Loop attivo: 12-point pre-flight (weekend, budget, CB, invariants) blocca pipeline prima di spendere NLM quota.

### 2.5 Cicli di feedback che il sistema **non** chiude

1. **Gap detection non cambia gli obiettivi.** Layer-A trova 35 gap/giorno (verified 2026-04-21: "Total gaps found: 35" in log), ma solo 3 GAP vengono remediate via search automatica. I gap di Layer-A (domande che NB non sa rispondere) non alimentano il `DOMAIN_TOPICS.topics` checklist: restano in `coverage_matrix.json [domain.gaps]` come diagnostica passiva. **Il sistema sa cosa non sa ma non cambia il piano di studio.**
2. **Claim categorization non riconfigura query future.** I 15 claim categories sono raccolti ma non feedback sulle query del QueryDecomposer.
3. **Contradictions cross-notebook non escalate.** Il correlator detecta contraddizioni (campo `contradictions` in CrossNotebookResult) ma nessun cron le legge per riconciliare o flag.
4. **db_to_nlm_sync SHA-256 dedup è one-way.** Se un renderer Postgres produce Markdown identico, skip upload. Ma se NLM risponde incoerentemente con la nuova versione, nessun feedback loop DB→NLM.
5. **Nessun NB osserva se stesso.** Non esiste un "meta-NB" che ingesti gap_scanner_state + heartbeat_monitor + claim_extractor stats e produca insight sull'operatività del proprio sistema di gap detection.

---

## 3. Inventario automazioni (grounded)

### 3.1 Pipeline registrate e cron

| Script / modulo                                                                   | Cron             | Schedule WITA                   | Status                                | Errore (se broken)                                                                                                                                                                            | Heartbeat in registry                             |
| --------------------------------------------------------------------------------- | ---------------- | ------------------------------- | ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| `pipeline.py` (NB-2) via `run_nb2_pipeline.sh`                                    | `10 18 * * 0-5`  | Mon-Sat 02:10                   | **degraded**                          | Halted at preflight 2026-04-21 (cause ignota)                                                                                                                                                 | `nb2_pipeline` (stale 19gg)                       |
| `nb3_pipeline.py` via `run_nb3_pipeline.sh`                                       | `45 2 * * 1-6`   | Mon-Sat 02:45                   | healthy (log 21/04 02:47 OK)          | —                                                                                                                                                                                             | `nb3_pipeline` (nessun file heartbeat registrato) |
| `nb4_pipeline.py` via `run_nb4_pipeline.sh`                                       | `20 2 * * 1-6`   | Mon-Sat 02:20                   | healthy                               | —                                                                                                                                                                                             | `nb4_pipeline`                                    |
| `nb5_pipeline.py` via `run_nb5_pipeline.sh`                                       | `25 2 * * 1-6`   | Mon-Sat 02:25                   | healthy                               | —                                                                                                                                                                                             | `nb5_pipeline`                                    |
| `nb6_pipeline.py` via `run_nb6_pipeline.sh`                                       | `30 2 * * 1-6`   | Mon-Sat 02:30                   | healthy                               | —                                                                                                                                                                                             | `nb6_pipeline`                                    |
| `nb7_pipeline.py` via `run_nb7_pipeline.sh`                                       | `35 2 * * 1-6`   | Mon-Sat 02:35                   | healthy                               | —                                                                                                                                                                                             | `nb7_pipeline`                                    |
| `nb8_pipeline.py` via `run_nb8_pipeline.sh`                                       | `40 2 * * 1-6`   | Mon-Sat 02:40                   | healthy (in-flight 02:42)             | —                                                                                                                                                                                             | `nb8_pipeline`                                    |
| `nb10_pipeline.py` via `run_nb10_pipeline.sh`                                     | `50 2 * * 1-6`   | Mon-Sat 02:50                   | healthy                               | —                                                                                                                                                                                             | `nb10_pipeline`                                   |
| `scripts/nlm_nb1_daily_refresh.py` via `cron-agent.sh exec nlm-nb1-daily-refresh` | `30 20 * * *`    | Daily 04:30                     | unknown (log non ispezionato)         | —                                                                                                                                                                                             | `nb1_daily_refresh`                               |
| `scripts/nlm_pipeline_run.sh --force` via `cron-agent.sh exec nlm-deep-research`  | `10 1 * * *`     | Daily 01:10                     | **degraded (NB-11/12/13 stale 21gg)** | db_nlm_sync_state non aggiornato dal 2026-04-01                                                                                                                                               | `db_nlm_sync`                                     |
| `gap_scanner.py --layer-a` via `run_gap_scanner.sh --layer-a`                     | `30 21 * * *`    | Daily 21:30                     | healthy (35 gap trovati 21/04)        | —                                                                                                                                                                                             | `gap_scanner` OK 2.9h                             |
| `gap_scanner.py --layer-b` via `run_gap_scanner.sh --layer-b`                     | `0 19 * * 0`     | Sun 19:00                       | healthy                               | —                                                                                                                                                                                             | `gap_scanner_layer_b` OK 53.4h                    |
| `gap_scanner.py --remediate` via `run_gap_scanner.sh --remediate`                 | `30 20 * * 0`    | Sun 20:30                       | healthy                               | —                                                                                                                                                                                             | `gap_scanner_remediation` OK 51.9h                |
| `freshness_monitor.py --scan` via `run_freshness_monitor.sh`                      | `0 22 * * *`     | Daily 06:00                     | **degraded**                          | Gemini CLI 4/5 response "noisy" (filtered out) — DJP/OSS/BPN/Kemnaker, solo Imigrasi responde pulito                                                                                          | `freshness_monitor` OK 2.4h                       |
| `multimodal_pipeline.py` via `run_multimodal.sh`                                  | `0 22 * * 0-4,6` | Daily (eccetto sabato) 06:00    | **broken**                            | `ModuleNotFoundError: No module named 'apps.evaluator.nlm_deep_research.multimodal_pipeline'` — lo script usa `python3.14` system invece del venv                                             | `multimodal_pipeline` NEVER_RAN                   |
| `yt_monitor.py` via `run_yt_monitor.sh`                                           | `30 */6 * * *`   | Ogni 6h 04:30/10:30/16:30/22:30 | **broken**                            | `ModuleNotFoundError: No module named 'feedparser'` — dipendenza mancante in venv cron                                                                                                        | — (non in registry)                               |
| `t4_monitor.py` NB-5 via `run_nb5_t4_monitor.sh`                                  | `0 18 * * 2,4`   | Tue/Thu 02:00                   | **broken**                            | `ModuleNotFoundError: No module named 'feedparser'` (stesso)                                                                                                                                  | — (non in registry)                               |
| `peraturan_ingestion_trigger.py` via `run_peraturan_ingestion.sh`                 | `30 21 * * 0`    | Sun 05:30                       | unknown                               | —                                                                                                                                                                                             | `peraturan_ingestion`                             |
| `ops_intelligence.py --briefing` via `run_ops_briefing.sh`                        | `0 0 * * 1`      | Mon 08:00                       | healthy (heartbeat 20/04)             | —                                                                                                                                                                                             | `ops_briefing`                                    |
| `persona_engine.py --validate` via `run_persona_validate.sh`                      | `0 1 * * 0`      | Sun 09:00                       | **CRITICAL (stale 434h = 18 giorni)** | Ultimo success 2026-04-03 21:48. Log `persona_validate_20260403.log` + `20260412.log` + `20260419.log` presenti — va ispezionato perché i run dal 12/19 aprile non hanno registrato heartbeat | `persona_validate`                                |
| `heartbeat_monitor.py --check`                                                    | `30 */6 * * *`   | Ogni 6h                         | healthy (è il monitor)                | —                                                                                                                                                                                             | self                                              |
| `heartbeat_monitor.py --digest`                                                   | `0 0 * * *`      | Daily 08:00                     | healthy                               | —                                                                                                                                                                                             | self                                              |
| `sync-memory-to-nlm.sh` (NB-14)                                                   | `0 3 * * 0`      | Sun 11:00                       | unknown                               | —                                                                                                                                                                                             | non in registry                                   |

### 3.2 Classificazione finale

- **Healthy (verificato):** 6 (nb3-nb8 pipelines, gap_scanner layer-A+B+remediate, heartbeat self, ops_briefing)
- **Degraded (funziona ma produce output incompleto):** 4 (nb2 preflight halt, freshness_monitor gemini noise, db_nlm_sync stale, yt/t4 broken su rami RSS)
- **Broken (non esegue):** 3 (multimodal_pipeline, yt_monitor, nb5_t4_monitor) — tutti per missing deps (`feedparser` + venv mismatch)
- **Critical stale (probabile heartbeat wiring):** 1 (persona_validate)
- **Unknown (non verificato in sessione):** 4 (nb1, peraturan_ingestion, mos-sync, nlm-pipeline-run db_sync)

### 3.3 Dipendenze mancanti verificate

Da log cron e traceback:

- `feedparser` — richiesto da `yt_monitor.py:73` e `t4_monitor.py:405`. Il venv `apps/backend-rag/.venv` non ha `feedparser` installato. Fix triviale: `pip install feedparser` in quel venv.
- `apps.evaluator.nlm_deep_research.multimodal_pipeline` — errore è nel wrapper `run_multimodal.sh:44-46` che cerca `.venv/bin/python` e fallisce back su `python3` (di sistema) — il quale a sua volta chiama `python3.14 -m apps.evaluator.nlm_deep_research.multimodal_pipeline` senza `PYTHONPATH=.` e senza venv attivo. Fix: allineare lo script ai pattern di `run_nbX_pipeline.sh` (attivare venv, `PYTHONPATH=.`).

---

## 4. Gap analitici (cose che il sistema **non** fa)

### 4.1 Domini coperti parzialmente o male

1. **HR/Payroll cross-cluster.** NB-10 copre "Team Guides" (PKWT, PPh 21 TER, BPJS mixed team, EOR) ma sovrappone con NB-6 "Operations & Compliance" (BPJS, UU Cipta Kerja, UMR). Le keyword `bpjs` sono in entrambi i registry (NB-6 e NB-10 implicitamente). Ambiguità routing: se utente chiede "quanto costa BPJS per un expat?", `resolve_notebook()` porta a NB-6 (prima match). Nessun NB dedicato a HR/payroll.
2. **Marketing/SEO analytics.** NB-7 è "Editorial & Content" — copre tone/format/SEO — ma non copre analytics performativi (quale articolo ha generato più lead?). L'analisi performativa vive in altro stack (GSC MCP, GA4) separato dal RAG. Gap: nessun NB è il posto dove "chiedo: qual è il topic più convertente per visa?".
3. **Client-specific knowledge.** Non esiste un NB "Casi clienti" / "Dossier cliente". La memoria per-cliente vive in `shared/escalations_*.jsonl` + Postgres CRM. Quando Claude vuole rispondere "Cosa ho fatto per il cliente X la settimana scorsa?", non c'è NB: deve query Postgres via tool dedicato. NB-11 ha un rendering `client_segments` aggregato ma non per-cliente.
4. **Incidenti / scar tissue.** `.claude/rules/cicatrix-scars.md` è un file statico. Non esiste un NB "Incident knowledge" che riceva scar tissue automatiche da post-deploy failures.
5. **Knowledge Graph topology / gap cognitivi.** Il KG ha 108K nodi, 243K edge; `nexus:gaps` Redis stream ha 552 entries di gap scoperti. Nessun NB riceve questi dati. Gap: Knowledge Graph insight non confluisce in NotebookLM ground truth.

### 4.2 Ridondanze / automazioni che fanno la stessa cosa

1. **Tre `_query_notebook` function identiche.** `gap_scanner.py:172-189`, `freshness_monitor.py` (simile), `cross_notebook_correlator.py:178-195`, `peraturan_ingestion_trigger.py` (implicito). Ogni modulo ri-implementa subprocess → nlm CLI con timeout. Candidati estrazione: `nlm_cli.query(nb_id, q, timeout)` helper condiviso.
2. **Tre `_send_telegram`.** Stesso pattern HTTP POST Markdown in `gap_scanner.py:247-263`, `freshness_monitor.py:161-177`, `heartbeat_monitor.py:370-415`, `ops_intelligence.py:69+`, etc. Candidato: `nlm_notifier.send_telegram(msg, parse_mode)`.
3. **Heartbeat wiring ripetuto in 10 script.** Ogni `run_nbX_pipeline.sh` fa `PYTHONPATH=. python -m heartbeat_monitor --record <name>` alla fine. Candidato: hook comune.
4. **gap_scanner `--remediate` vs freshness_monitor `--remediate-stale`.** Entrambe leggono `coverage_matrix.json`, filtrano GAP/STALE, chiamano Gemini search per content, caricano in NLM. Differenza sottile: gap_scanner aggiunge source via `nlm source add --text`; freshness_monitor triggera `nlm research start` (async). Overlap funzionale ~70%. Candidati: consolidare in un singolo `gap_remediator` con modalità `--sync-fill` (gap_scanner attuale) o `--async-research` (freshness_monitor attuale).
5. **NB-6 (Operations & Compliance) vs NB-10 (Team Guides).** BPJS, UU Cipta Kerja, payroll — overlap ~60%. Verificare con `cross_notebook_correlator.query("BPJS rate 2026")` se la fan-out restituisce claim contraddittori. Candidato consolidamento.

### 4.3 Pipeline senza consumer downstream

1. **Synthesis roller daily/weekly/monthly.** Produce `[SYNTH-DAILY] NB-X YYYY-MM-DD` in NLM, ma nessun downstream legge i synth titoli. Servono a comprimere il source count per evitare overflow — ma il valore aggiunto semantico (trend week-over-week) non è consultato programmaticamente. Le `SYNTH-WEEKLY` potrebbero feedback al gap_scanner checklist per re-weighting topics, non lo fanno.
2. **ops_intelligence executive briefing.** Invia Telegram → Zero. Non persiste, non alimenta un NB, non genera skill. Monouso.
3. **coverage_matrix.json gap_pct per domain.** Calcolato, salvato, mandato in Telegram. Non consumato per decidere quali NB priorityzare nei prossimi run.
4. **claim_extractor con 15 categorie.** Le categorie sono in `claims.jsonl` ma nessun aggregatore le legge. `FEE_CHANGE`, `ENFORCEMENT_ACTION`, `POLICY_SIGNAL` — distinzioni semantiche ricche ma inerti downstream.

### 4.4 Consumer senza pipeline (codice che si aspetta NB_X che non esiste)

1. **`nlm_notebook_registry.py` `primary_notebook_id: None`** per tutti i 7 domini. I "primary law notebook" NB-Xa sono pianificati (vedi `_PRIMARY_LAW_KEYWORDS` logic) ma mai materializzati. Codice in `resolve_notebook()` ha un branch per `wants_primary` che cade sempre su operational.
2. **NB-9 citato in `migration_070b_legal_ingest_jobs.py:5`.** Riferimento ADR pattern "zero new services" — `ASSUMED` era l'ADR repo ma non è un NB attivo.
3. **Persona definitions per NB-7/NB-8/NB-10.** `persona_engine.py` inject persone solo per NB-2..6 (`persona_definitions.json` mostra nb2_immigration, nb3_company, nb4_tax, nb5_property — non ispezionato oltre i 30 righe ma il pattern è chiaro). NB-7, NB-8, NB-10 possibly senza persona injected. **VERIFICA DA FARE.**

### 4.5 Fonti che producono dati "ciechi" (nessuno vede i log)

Come da lesson 2026-04-19 in MOS: self-repair cieco `system_doctor.py` / `anomaly-detector.py` / `zombie-hunter.sh` non leggono `~/logs/cron-agent/`. Nel namespace NLM stesso:

- **Log per-giorno** `apps/evaluator/nlm_deep_research/logs/gap_scanner_YYYYMMDD.log`, `nb2_pipeline_YYYYMMDD.log`, `ops_briefing_YYYYMMDD.log`, `persona_validate_YYYYMMDD.log`. **Nessuna rotazione visibile** (da log ispezionato con `ls` fino al 21/04 presente). `ASSUMED`: log grow linearly.
- **Log `/tmp/cron-*.log`.** Per molti cron. Rotazione dipende da OS `/tmp` cleanup. Non visibile retention.
- **Nessun aggregator.** Non esiste uno script che legge `gap_scanner_YYYYMMDD.log` e verifica "trends in gap counts" (e.g. lunedì 40 gap, martedì 38, mercoledì 50 → spike significativo?). I log sono sepolti.

---

## 5. Budget & quota

Fonti: `pipeline.py:62-64`, `gap_scanner.py:44-47`, `freshness_monitor.py:100-102`, `multimodal_pipeline.py:135-138`.

- **NLM query budget:** ogni pipeline NB ha `MAX_DAILY_QUERIES = 2` e `MAX_WEEKLY_CALLS = 40`. 8 NB pipelines × 40 = 320 calls/week teorici — circa 45/day. Gap_scanner layer-A: 7 queries/day. Layer-B: 7 × 8 topics = 56 queries/week. Remediate: max 3/run = 9/week. Freshness: 5 × 2 = 10/day + max 3 research trigger/run. Multimodal: 1-8 artifact/day. **Totale stimato:** 60-80 NLM queries/day in steady state. Quota NLM è soft-limited OAuth: rate limiting HTTP 429.
- **Gemini CLI budget:** freshness_monitor 5 search/run × 2 run/day = 10/day. gap_scanner remediate 3/run × 1 run/week = 3/week. Gemini uso via `-p` headless OAuth — quota gratis.
- **Ollama local:** QueryDecomposer per ogni `_build_query()`, Synthesis roller qwen3.5:9b daily/weekly. Zero cost cloud.
- **Telegram:** ~ 10 msg/day digest + alert.

Il budget è ben definito; non c'è cost runway rischio. Il limite reale è NLM rate limiting + wall-clock (20-25 min totali per tutte le pipeline NB 02:10-02:50, seriali).

---

## 6. Invarianti

`invariants.py` implementa 526 righe di check. Esempi (grep + lettura parziale):

- Max 70 active sources per NB (overflow → emergency_prune).
- Claim `confidence > 0.75` => classificato VERIFIED; `< 0.35` => MONITORING.
- Pinned sources non possono essere archived (anche se SVS basso).
- Duplicati dedup: `url_hash` + `title_normalized` equal → mark known_duplicates.
- Schema version = 1 (pipeline state file).

Il sistema ha cultura di invariants + CRITICAL severity. Post-consolidation re-check impedisce corruzione progressiva. È un dettaglio importante: il sistema è **difensivo**, non permette naive accumulation.

---

## 7. Discrepanze e zone grigie

1. **Heartbeat registry dice `nb2_pipeline` etc. hanno schedule "weekday"** (`pipeline_heartbeat_registry.json:3`) con `max_age_hours: 6`. Ma in realtà la cron `10 18 * * 0-5` gira Mon-Sat UTC (= Mon-Sat WITA 02:10). "weekday" nel sense in cui UTC weekend ≠ WITA weekend. **Ambiguità lasciata.**
2. **`nlm_notebook_registry.py` in apps/evaluator/nlm_deep_research (non esiste)** vs `apps/backend-rag/backend/services/oracle/nlm_notebook_registry.py` (esiste, 212 righe). Il primo è importato da `cross_notebook_correlator.py:59-100` tramite `DOMAIN_REGISTRY` hardcoded (duplicazione intenzionale, commento dice "mirrors nlm_notebook_registry.py"). Discrepanza: se il registry backend cambia (e.g., nuovo dominio), il correlator evaluator non lo sa.
3. **Freshness_monitor REGULATORY_DOMAINS = 5** (imm/oss/djp/bpn/kemnaker). **Gap_scanner DOMAIN_TOPICS = 7** (incluso editorial/lifestyle). Il freshness scan monitora solo i 5 domini regolatori ufficiali (sensato: non esiste "ministero dell'expat life" da scrapare). Ma la coverage_matrix.json ha 7 domini con gap/topic; e remediate_stale di freshness_monitor itera SU TUTTI i domini (anche editorial/lifestyle). Non è un bug ma merita nota: la simmetria non è perfetta.
4. **NB-10 "team" keyword in DOMAIN_REGISTRY cross-notebook** è `{"sop", "team", "pricing", "crm", "workflow", "competitor", "bpjs", "umr", "salary"}` — ma in `nlm_notebook_registry.py` "operations" è `{"sop", "team", "pricing", "crm", "workflow", "competitor"}` e non ha NB-10 mappato. **In backend NB-10 non esiste come dominio routable.** Il correlator evaluator ha NB-10 (via `f0307c2c-9220...`) ma il backend no. Quando un utente chiede "payroll PPh21 per il team" sul backend, route → NB-6 (operations), che copre il 70% ma è la copia vecchia. Gap: pipeline NB-10 alimenta un NB che il RAG non interroga.

---

## 8. Sintesi

- **Oggi esistono 11 NB attivi** (più 2 legacy). Core domini: NB-2..8, NB-10. Meta-op: NB-11, 12, 13. Legacy: NB-1, NB-14.
- **8 pipeline di dominio funzionano** (6 healthy verificati, 1 degraded, 1 in-flight). 3 automazioni sono oggi rotte (multimodal, yt_monitor, t4_monitor) per dipendenze missing. 1 è CRITICAL stale (persona_validate). 1 è stale 21 giorni senza alert (db_nlm_sync).
- **Il sistema ha un'architettura a 10 "ARCH"** (ARCH-1 query, ARCH-2 persona, ARCH-3 decomposer, ARCH-4 cross-notebook, ARCH-5 gap/coverage/freshness, ARCH-6 multimodal, ARCH-7 ?, ARCH-8 snapshot, ARCH-9 heartbeat, ARCH-10 ops_intelligence). Mostra intento progettuale di un "organismo" che osserva se stesso.
- **Il gap più significativo:** il sistema **rileva** i suoi buchi (gap_scanner, heartbeat, contradictions) ma **non cambia il proprio piano** in risposta. È riflessivo parzialmente (scrive log, manda telegram) ma non auto-correttivo a livello di obiettivi/checklist. Remediation è tattica (fill one topic) non strategica (ri-pesare i domini).
- **Oracolazione asimmetrica:** backend RAG routing (`resolve_notebook`) conosce 7 domini; pipeline NLM ingesta 8 domini + 3 meta. NB-10 è popolato ma non consumato dal RAG. Pipeline NB-2a/3a/... primary-law non sono state create.

**Fine Sezione 1.** Le fasi 2 (sacred reading) e 3 (redesign) si basano su questa mappa — ogni proposta lì deve ancorarsi a un gap/ridondanza/asimmetria qui documentato.
