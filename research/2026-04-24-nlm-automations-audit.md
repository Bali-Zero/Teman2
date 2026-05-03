# Audit automazioni NotebookLM (nlm) e NB — 2026-04-24

**Scope**: tutte le automazioni che coinvolgono `nlm` CLI, il bridge HTTP NLM, e i notebook NB-0..NB-14 + NB-INTEL.
**Metodo**: inventario scripts + crontab + launchd + log + state file + consumer backend + test live sul bridge + confronto con account NotebookLM reale.
**Executive summary**: **l'impianto è progettato bene, ma in produzione la maggior parte dei cron non esegue realmente**. NB-1 si aggiorna ogni notte. NB-2 è in circuit-breaker OPEN da 2 giorni. NB-3/4/5/6/7/8/10 non generano un solo log da quando sono stati pianificati. Gli NB-INTEL (Mata Garuda) risultano vuoti lato NotebookLM (0 source).

---

## 1. Inventario delle pipeline schedulate

### 1.1 Crontab utente (macOS Pro)

| # | Job | Schedule (WITA) | Script | Stato reale |
|---|---|---|---|---|
| 1 | **NB-1 daily refresh** | 04:30 quotidiano | `run_nb1_refresh.sh` → `nlm_nb1_daily_refresh.py` | ⚠️ Gira ogni giorno ma **fallisce sempre** (timeout ollama qwen3.5:9b, 175s). L'upload dei bundle a NotebookLM OK (verificato log 24/04 20:34: 5 bundle, 266.8s). Il "fallito" è lo step downstream di summarization. |
| 2 | **NB-2 immigration pipeline** | 02:10 lun-sab | `run_nb2_pipeline.sh` → `pipeline.py` | ❌ **HALTED da 22/04**: CB_NLM=OPEN (3 fallimenti consecutivi, bug Python `min(None, int)` in `claim_extractor.py:216`). Preflight blocca. |
| 3 | **NB-3 company** | 02:45 lun-sab | `run_nb3_pipeline.sh` | ❌ **Mai loggato**: 0 file in `logs/`, cron parte ma esce in 5ms (`lastStatus=pending`). |
| 4 | **NB-4 tax** | 02:20 lun-sab | `run_nb4_pipeline.sh` | ❌ Come NB-3. Mai eseguito in pratica. |
| 5 | **NB-5 property** | 02:35 lun-sab | `run_nb5_pipeline.sh` | ❌ Come NB-3. |
| 6 | **NB-6 ops compliance** | 02:30 lun-sab | `run_nb6_pipeline.sh` | ❌ Come NB-3. |
| 7 | **NB-7 editorial** | 02:40 lun-sab | `run_nb7_pipeline.sh` | ❌ Come NB-3. |
| 8 | **NB-8 expat life** | 02:47 lun-sab | `run_nb8_pipeline.sh` | ❌ Come NB-3. |
| 9 | **NB-10 team guides** | 02:50 lun-sab | `run_nb10_pipeline.sh` | ❌ Come NB-3. |
| 10 | **NB-5 T4 monitor** | 18:00 mar/gio | `run_nb5_t4_monitor.sh` | ❌ Mai loggato. |
| 11 | **peraturan ingestion** | 21:30 dom | `run_peraturan_ingestion.sh` | ❌ Mai loggato. |
| 12 | **db → NLM sync (C2.11)** | 04:30 quotidiano | `run_db_nlm_sync.sh` | ❌ Mai loggato. |
| 13 | **MOS memory sync** | 03:00 dom | `sync-memory-to-nlm.sh` | ❌ Mai loggato. |
| 14 | **gap scanner Layer A** | 21:30 quotidiano | `run_gap_scanner.sh --layer-a` | ✅ Gira (log 24/04 21:37). |
| 15 | **gap scanner Layer B** | 19:00 dom | idem `--layer-b` | ⏳ settimanale, ultimo 20/04. |
| 16 | **gap scanner remediate** | 20:30 dom | idem `--remediate` | ⏳ settimanale. |
| 17 | **freshness monitor** | 22:00 quotidiano | `run_freshness_monitor.sh` | ✅ Gira (log 24/04 22:10). |
| 18 | **multimodal** | 22:00 dom-sab (tranne ven) | `run_multimodal.sh` | ❌ Mai loggato. |
| 19 | **heartbeat check** | ogni 6h | `run_heartbeat_check.sh --check` | ⚠️ Ultimo log 24/04 18:30. |
| 20 | **heartbeat digest** | 00:00 quotidiano | idem `--digest` | ⚠️ Idem. |
| 21 | **ops briefing weekly** | 00:00 lun | `run_ops_briefing.sh` | ⏳ ultimo 20/04. |
| 22 | **persona validate** | 01:00 dom | `run_persona_validate.sh` | ⏳ ultimo 22/04. |
| 23 | **YT monitor** | ogni 6h | `run_yt_monitor.sh` | ⚠️ Ultimo log 24/04 18:30 (in `/tmp`, volatile). |
| 24 | **yajna scan** | 17:00 dom | `run_yajna_scan.sh` | ❌ **Script inesistente**, crontab referenzia file mancante. |
| 25 | **yin-yang audit** | 17:05 dom | `run_yin_yang_audit.sh` | ❌ **Script inesistente**. |
| 26 | **hexagram compute** | 08:00 quotidiano | `run_hexagram_compute.sh` | ❌ **Script inesistente**. |
| 27 | **NB-0 meta refresh** | 09:00 quotidiano | `run_nb0_refresh.sh` | ❌ **Script inesistente**. |
| 28 | **T4 monitor (cron-wrapper)** | ogni 6h | `run_t4_monitor.sh` | ❌ Mai loggato. |
| 29 | **deep-research via cron-agent** | 01:10 quotidiano | `~/.cron-agent.sh exec nlm-deep-research nlm_pipeline_run.sh --force` | ❌ **Ultimo success 23/04 01:12 ma fallito con bug `claim_extractor`**. Oggi 24/04 non loggato. |
| 30 | **NB-1 via cron-agent** | 20:30 UTC (04:30 WITA) | `~/.cron-agent.sh exec nlm-nb1-daily-refresh run_nb1_refresh.sh` | ⚠️ **Duplicato** del #1. Entrambi puntano allo stesso script ma con PID file diverso. |

### 1.2 LaunchAgents NLM/Mata Garuda (`~/Library/LaunchAgents`)

| Plist | Schedule | Status |
|---|---|---|
| `com.balizero.nlm-bridge` | KeepAlive | ✅ **PID 1864 running dal 24/04 09:18**, ma `/nlm/query` va in timeout 60s in test live. |
| `com.matagaruda.nlm-expander.weekly` | Dom 09:00 | Caricato, L2 autonomy (propone NB-INTEL nuovi via Telegram, non auto-crea). |
| `com.matagaruda.intel-bridge.daily` | Daily | Caricato. |
| `com.matagaruda.kita-feed.daily` | Daily | Caricato. |
| `com.matagaruda.reg-alert.30min` | 30min | Caricato. |
| `com.matagaruda.wr2-bridge.hourly` | 1h | Caricato. |
| + 10 altri matagaruda/garuda | varie | Caricati (exit code 0 ultima esecuzione). |

---

## 2. NB Registry — mappatura logica vs realtà

### 2.1 Design (da `backend/services/oracle/nlm_notebook_registry.py` + `core/legal_config.py`)

| NB | UUID | Ruolo operativo | Domain |
|---|---|---|---|
| NB-1 | f6ecd115… | Aggregatore monorepo (codebase + frontend + rules) per fallback RAG | Infra/self-knowledge |
| NB-2 | cff93ab0… | Immigration deep research (T2/T3 verified guides) | immigration_visa |
| NB-3 | 933509f9… | Company setup / KBLI / PMA / OSS | company_biz |
| NB-4 | d4b2eedb… | Tax & fiscal compliance | tax_fiscal |
| NB-5 | d9438180… | Property & real estate | property_real_estate |
| NB-6 | 85207af3… | Operations & manpower / HR | operations_labor |
| NB-7 | f51ab8a0… | Editorial & content strategy | editorial_press |
| NB-0 (meta) | 9a70162a… | Meta-NLM system reflection | — |

Plus: NB-8 (expat life), NB-9 (research lab), NB-10 (team guides), NB-11 (ops live), NB-12 (BI), NB-13 (telemetry), NB-14 (Claude Code memory), NB-INTEL-{AIResearch, Regulation, Tax, Immigration, Press}.

### 2.2 Stato source NotebookLM (dati reali da `nlm notebook list` 24/04 23:53)

| NB | Source count | Ultimo update cloud | Note |
|---|---|---|---|
| NB-1 | **51** | 24/04 15:51 | ✅ bundle freschi (target = 60) |
| NB-2 | 73 | 24/04 13:30 | ✅ stabile, ma pipeline HALTED |
| NB-3 | 165 | 24/04 13:30 | ✅ ricco, ma pipeline mai giri |
| NB-4 | 102 | 24/04 13:31 | ✅ ricco, stesso problema |
| NB-5 | 75 | 24/04 13:32 | ✅ ricco, stesso problema |
| NB-6 | 181 | 24/04 13:34 | ✅ ricco, stesso problema |
| NB-7 | 81 | 24/04 13:44 | ✅ ricco, stesso problema |
| NB-8 | 132 | 24/04 13:36 | ✅ |
| NB-10 | 144 | 22/04 18:52 | |
| NB-0 | **3** | 22/04 06:11 | ⚠️ quasi vuoto |
| NB-INTEL-AIResearch | **382** | 12/04 13:33 | ✅ attivissimo |
| NB-INTEL-Regulation | **0** | 19/04 | ❌ vuoto |
| NB-INTEL-Tax | **0** | 19/04 | ❌ vuoto |
| NB-INTEL-Immigration | **0** | 19/04 | ❌ vuoto |
| NB-INTEL-Press | **0** | 19/04 | ❌ vuoto |
| Mata Garuda — Self-Evolving | 57 | 14/04 | |

---

## 3. Flusso logico del sistema (disegno originale)

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. MONOREPO Git (~/Desktop/nuzantara)                              │
│       │                                                              │
│       ▼                                                              │
│  2. nlm_nb1_daily_refresh (04:30 WITA) → regenera 5-8 bundle        │
│       │                                                              │
│       ▼                                                              │
│  3. NB-1 cloud (aggregatore codebase, 51 source)                    │
│       ▲                                                              │
│       │ uploaded by `nlm` CLI                                       │
├───────┴─────────────────────────────────────────────────────────────┤
│  4. Pipeline specialistiche (NB-2..NB-10) — 02:10-02:50 WITA        │
│       - preflight (CB, budget, deadline)                            │
│       - L1 query → NLM bridge :18790/nlm/query                      │
│       - claim_extractor → claims.jsonl                              │
│       - L2 consolidation + sources snapshot                         │
│       - handoff → backend RAG oracle                                │
├─────────────────────────────────────────────────────────────────────┤
│  5. Mata Garuda (L1 autonomy)                                       │
│       - bali-intel-scraper + feeds → garuda:enriched (Redis)        │
│       - intel-bridge → NB-INTEL-{domain}                            │
│       - nlm_expander weekly → propone nuovi NB (Telegram)           │
├─────────────────────────────────────────────────────────────────────┤
│  6. Consumer RAG backend (apps/backend-rag/)                        │
│       - NLMOrchestrator (oracle/nlm_orchestrator.py)                │
│       - crag_router.py (enable_nlm_orchestrator flag)               │
│       - agentic/orchestrator_core.py (nlm_match, nlm_enrichment)    │
│       → popola risposte utente con grounding NLM                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Fatti — problemi confermati

### 4.1 Bug critico `claim_extractor.py:216`
```
TypeError: '<' not supported between instances of 'NoneType' and 'int'
  at highest_tier = min(highest_tier, tier)
```
Questa eccezione ha messo il Circuit Breaker NB-2 in OPEN, bloccando tutte le run successive su preflight (`cb_nlm=❌`). Log: `~/logs/cron-agent/nlm-deep-research.log` riga ~45 del run 23/04 01:12, e `apps/evaluator/nlm_deep_research/logs/nb2_pipeline_20260423.log`.

### 4.2 Timeout ollama qwen3.5:9b in NB-1 refresh
Dal heartbeat ~/.agent/decisions/state/nlm_nb1_daily_refresh.last.json:
```
lastError: FallbackSummaryError: All models failed (3): ollama/qwen3.5:9b: LLM request timed out
```
L'upload a NotebookLM funziona (51 source freschi). Fallisce lo step di summarization post-upload (non critico per RAG, ma rompe la metrica di successo del cron).

### 4.3 Cron → openclaw → "pending" in 3-5ms
Pattern identico su **9 pipeline** (NB-2, NB-3, NB-4, NB-5, NB-6, NB-7, NB-8, NB-10, deep-research):
- `cron` entra
- `cron-runner.sh` viene invocato dal crontab
- I log in `/tmp/cron-nlm-*.log` **non vengono mai scritti** (0 byte, assenti)
- I log reali in `apps/evaluator/nlm_deep_research/logs/*_20260424.log` **non esistono**
- In `~/.openclaw/cron/jobs.json` compare `lastStatus=pending`, `lastDurationMs=3-5`

Interpretazione: c'è un `cron-agent.sh` intermedio che intercetta la chiamata e non la fa mai arrivare allo script reale. L'unica pipeline che gira davvero (nb2 22/04, 23/04) usa `cron-runner.sh` diretto, non `cron-agent.sh`. Le heartbeat dicono "failed/pending" da **10 giorni** (`ts=14 aprile`), ma la `mtime` è di oggi → un bridge ri-scrive lo stesso contenuto stale.

### 4.4 4 script inesistenti in crontab
```
run_yajna_scan.sh       — referenziato ma non esistente (dom 17:00)
run_yin_yang_audit.sh   — referenziato ma non esistente (dom 17:05)
run_hexagram_compute.sh — referenziato ma non esistente (daily 08:00)
run_nb0_refresh.sh      — referenziato ma non esistente (daily 09:00)
```
Quattro entry crontab che falliscono silenziosamente ogni giorno. I log in `/tmp/cron-*.log` vengono creati ma vuoti/con errore `ERROR: ... not found`.

### 4.5 NB-INTEL vuoti
I 4 NB-INTEL operativi (Regulation, Tax, Immigration, Press) risultano **source_count=0** su NotebookLM, ultimo update 19/04. Solo NB-INTEL-AIResearch ha 382 source attivi. Il design prevede "continuous feed via enriched stream"; in pratica 4/5 canali sono spenti.

### 4.6 NLM bridge health "degraded"
`GET /nlm/health` → `{"status":"degraded","uptime":52420.4,"request_count":0}`. Zero richieste soddisfatte da 14h di uptime. Test live query a 60s → timeout 504. La causa è probabilmente l'assenza della libreria `notebooklm_tools` (log startup: *"notebooklm_tools not installed — using CLI subprocess fallback"*), che costringe il bridge a fare subprocess `nlm` sincroni per ogni chiamata — e `nlm` CLI può essere lento/appeso.

### 4.7 Duplicato schedulazione NB-1
Crontab #1 e #30 schedulano entrambe `run_nb1_refresh.sh` alle 04:30 WITA, uno via `cron-runner.sh` l'altro via `cron-agent.sh`. La race sul PID file (`/tmp/nz_nb1_pipeline.pid`) probabilmente fa sì che il secondo veda il primo in corso e skippi — spiega perché cron-agent logga mentre cron-runner no, ma sarebbe comunque da consolidare.

### 4.8 Script `run_mos_sync` obsoleto
Sopra nel commento Air è annotato: *"C2.16 memory→NLM sync — SKIPPED (Pro already runs same script, same NB_SESSION_ID)"*. Il Pro schedula `sync-memory-to-nlm.sh` domenica 03:00 → `/tmp/cron-mos-sync.log` → **mai scritto**. Quindi la memoria di Claude Code **non si è mai sincronizzata** con NB-14 (NB_SESSION_ID: 1e5f9b04). NB-14 su cloud mostra `source_count=5`, updated 10/04/2026 → il cron non gira da 2+ settimane.

---

## 5. Considerazioni

### 5.1 Il disegno è corretto, l'esecuzione no
L'architettura logica (NB-1 bundle aggregator + pipeline specialistiche + NB-INTEL feed + orchestrator RAG) è coerente e ben pensata. I bug sono concentrati in 4 aree:
1. **Bridge cron-agent/openclaw** intercetta e non esegue il 70% dei job.
2. **Un bug Python** (`min(None, int)`) ha rotto il CB di NB-2.
3. **NLM bridge HTTP** usa fallback CLI subprocess che va in timeout.
4. **4 script referenziati ma mai creati**: crontab va pulita.

### 5.2 Il sistema "sembra" in salute
Le heartbeat `~/.agent/decisions/state/nlm_*.last.json` vengono riscritte ogni giorno con `mtime` fresco, ma il contenuto è stale da 14/04. Questo rende **il monitoraggio auto-generato falsamente positivo**: un dashboard che guardasse solo `mtime` concluderebbe "tutto verde". È lo stesso pattern già documentato nella lesson *"self-repair cieco"* (PR #149, 2026-04-19).

### 5.3 Cosa funziona davvero
- ✅ **NB-1 bundle upload**: genera 5-8 bundle `.txt` dal monorepo, delete-before-add verso NotebookLM cloud. Log completo 24/04 20:34. 51 source freschi.
- ✅ **gap_scanner Layer A**: daily 21:30.
- ✅ **freshness_monitor**: daily 22:00.
- ✅ **nlm CLI auth**: `~/.nlm/auth.json` valido, `nlm notebook list` funziona.
- ✅ **NLM bridge processo**: uvicorn attivo porta 18790 (anche se poi le query vanno in timeout).
- ✅ **NB cloud ricchi**: source count 51-381 sui primary notebook → **le query RAG possono comunque risolvere**, perché il materiale è stato uploadato da sessioni interattive passate.

### 5.4 Cosa NON sta servendo al sistema
Il design prevede che le pipeline specialistiche aggiungano **claims + snapshots freschi** ogni giorno ai NB-2..NB-10. Siccome nessuna di queste gira davvero:
- Il RAG backend, che chiama `nlm_orchestrator.query(notebook_id)`, riceve risposte basate su source **statici dall'ultimo upload manuale** (13/04-24/04).
- Non c'è detection di nuova normativa/visa/tax: **NB-INTEL-Regulation/Tax/Immigration/Press** (canali di intelligence) sono a 0 source.
- Il cross-notebook correlator (`cross_notebook_correlator.py`) opera su pipeline_state obsoleti.

In pratica il backend RAG sta interrogando un "fermo-immagine" del 22/04, non una knowledge base viva.

### 5.5 Costo implicito
I cron che "partono ma non eseguono" sprecano 30+ trigger/giorno → non bruciano API (regola OAuth-only) ma rumore su log + falsi positivi heartbeat. Quelli che eseguirebbero davvero (NB-2..NB-10 daily deep research) sono esattamente i più costosi in tempo (5-15 min/run × 9 NB), quindi il loro **non funzionamento** paradossalmente risparmia quota CLI Claude Max — ma non sta producendo il materiale promesso.

---

## 6. Linee d'azione proposte (priorità)

### P0 — bloccanti (fai oggi/domani)
1. **Fix `claim_extractor.py:216`** — guard `None` su `tier`:
   ```python
   if tier is None: continue
   highest_tier = min(highest_tier, tier) if highest_tier is not None else tier
   ```
   Poi reset del CB: `rm apps/evaluator/nlm_nb2_pipeline_state.json.cb` (o equivalente campo in JSON). Test manuale `run_nb2_pipeline.sh`.
2. **Capire perché cron-agent/openclaw restituisce `pending` in 3-5ms** — leggere `~/.openclaw/openclaw.json` → job dispatcher. Sospetto: mutex/lock globale che rifiuta se già un job sta girando. Una volta confermato, decidere: tornare a `cron-runner.sh` puro (come NB-1 refresh legacy #1) oppure fixare il dispatcher.
3. **Rimuovere 4 entry crontab orfane** (yajna/yin-yang/hexagram/nb0). Se i file vanno creati, aprire issue; altrimenti `crontab -e` e cancellare.

### P1 — entro una settimana
4. **NLM bridge: installare `notebooklm-tools` nel venv** `/Users/nuzantara/venvs/nlm-bridge/` per eliminare il fallback subprocess e rientrare sotto i 60s.
5. **Consolidare duplicato NB-1 refresh** (crontab #1 vs #30) → tenere solo cron-agent path.
6. **Investigare NB-INTEL** (Regulation/Tax/Immigration/Press → 0 source): verificare `intel-bridge.daily` launchd. Stato exit=0 ma evidentemente il payload non arriva.
7. **NB-0 Meta-NLM**: 3 source totali, script inesistente. Decidere: creare `run_nb0_refresh.sh` o togliere la voce cron.
8. **Restore sync MOS → NB-14** (memoria Claude Code): fermo da 14 giorni.

### P2 — pulizia architettura
9. **Monitoraggio truthful**: le heartbeat `nlm_*.last.json` devono aggiornare `ts` solo quando il job **esegue davvero** (non basta mtime fresh). Al prossimo reboot, scrivere solo su exit code reale.
10. **Dashboard single-source-of-truth**: uno script che ogni mattina stampa tabella `NB → ultimo_run_reale → status → source_count_cloud`. Consuma `apps/evaluator/nlm_deep_research/logs/*.log` (non `/tmp`) + `nlm notebook list`.
11. **Ridurre la superficie**: il crontab ha 30 entry NLM. Serve davvero runnarle TUTTE ogni giorno? NB-3/NB-4/NB-5/NB-6/NB-7/NB-8/NB-10 ai livelli attuali (100-180 source) potrebbero girare settimanalmente invece che daily.

---

## 7. Verdict complessivo

**Il sistema NLM/NB è strutturalmente buono e logicamente coerente** (NB-1 aggregatore + pipeline domain + NB-INTEL + orchestrator RAG è un design solido). **Operativamente è compromesso**:

- 1 bug Python blocca 1/9 pipeline.
- 1 bridge cron (openclaw) blocca 8/9 pipeline.
- 4/5 canali intelligence (NB-INTEL) sono a 0.
- Il bridge HTTP NLM risponde ma non serve query reali.
- Il materiale che il RAG sta servendo a produzione è **un fermo-immagine del 22/04** travestito da "aggiornato oggi" dalle mtime delle heartbeat.

Priorità: sbloccare cron-agent (P0#2) + fix claim_extractor (P0#1). Questi due insieme riportano online NB-2..NB-10 e riattivano il flusso promesso al backend RAG.

---

**Autore**: Claude Opus 4.7 (1M context) · **Data**: 2026-04-24 · **Repo**: /Users/nuzantara/Desktop/nuzantara
