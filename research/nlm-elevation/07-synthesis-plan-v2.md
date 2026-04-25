---
date: 2026-04-25
type: synthesis-plan-v2
domain: notebooklm
supersedes: 05-synthesis-plan.md
inputs: 5
authors: [claude-opus-4-7, gemini-3.1-pro-preview, deepseek-reasoner, notebooklm-self, nb1-codebase]
status: refactored-after-nb1-validation
---

# Piano "NLM Elevation Nuzantara" v2 — post validation NB-1

> Questo piano supera `05-synthesis-plan.md`. Le correzioni dal `06-nb1-validation.md` sono incorporate; le hallucination di NB-1 sono identificate e escluse; il dispatcher è mappato sui moduli che esistono davvero nel filesystem al 2026-04-25.

## Verifica filesystem alla base di v2

Prima di scrivere il piano, ogni modulo menzionato è stato verificato con `ls`:

- ✅ `apps/evaluator/nlm_deep_research/claim_extractor.py` (bug riga 216)
- ✅ `apps/evaluator/nlm_deep_research/nlm_bridge.py` (subprocess wrapper `nlm` CLI)
- ✅ `apps/evaluator/nlm_deep_research/heartbeat_monitor.py`
- ✅ `apps/evaluator/nlm_deep_research/freshness_monitor.py` (+ `coverage_matrix.json`, `freshness_monitor_state.json`)
- ✅ `apps/evaluator/nlm_deep_research/registry.py` (JSONL state)
- ✅ `apps/evaluator/nlm_deep_research/db_to_nlm_sync.py`
- ✅ `apps/backend-rag/backend/core/collection_registry.py`
- ✅ `apps/backend-rag/backend/core/qdrant_db.py`
- ✅ `apps/backend-rag/backend/services/oracle/nlm_notebook_registry.py`
- ✅ `apps/backend-rag/backend/services/oracle/cross_notebook_correlator.py`
- ✅ `apps/backend-rag/backend/services/rag/nlm_verifier.py`
- ✅ `apps/backend-rag/backend/services/rag/agentic/orchestrator_core.py`
- ✅ `apps/backend-rag/backend/core/legal/hierarchical_indexer.py` (`HierarchicalChunk`)
- ✅ `apps/nlm-bridge/main.py` (FastAPI HTTP :18790, venv dedicato py3.11)
- ✅ `scripts/nuzantara-sentinel.py`
- ✅ `~/Library/LaunchAgents/ai.openclaw.gateway.plist` (nome reale, non `com.openclaw.*`)

**Esclusi dal piano perché non esistono più nel filesystem** (rimossi dal commit `0c60050e8 massive repo cleanup`):

- ❌ `apps/federation/a2a_service.py` (porta 8087) — era PoC, rimosso. Il doc `MULTI_DOMAIN_FUSION_ARCHITECTURE.md` era stale. Banner di archiviazione aggiunto 2026-04-25.
- ❌ `apps/federation/orchestrator.py`, `nlm_auth_bridge.py`, `adk_agents.py` — idem.

**Correzione errore piano v1**: lo Sprint 0 diceva "migrare da `cron-agent.sh` a `cron-runner.sh`". Entrambi esistono in `/Users/nuzantara/scripts/`, ma il dispatcher vero oggi è **`launchd` + `nuzantara-sentinel.py` + `ai.openclaw.gateway.plist`** (NB-1 ha ragione su questo). Il piano v2 opera su quel path.

---

## 1. Convergenze forti (invariate da v1)

C1 — Freshness contract P0 · C2 — NLM fuori real-time · C3 — Shadow Graphing · C4 — SLM · C5 — Fix-first.

## 2. Divergenze chiave (invariate da v1)

D1 — pool NB-SCRATCHPAD non ephemeral create/delete · D2 — ibrido (NLM extract offline, local DB serve) · D3 — audio internal only · D4 — zero nuovi NB fino Sprint 3 · D5 — DeepSeek evaluator + Ollama batch.

## 3. Verità uniche NLM self (critico)

U1 wrapper RPC bomba → Shadow Graph imperative · U2 1M ≠ precision (100-150 source sweet spot) · U3 Deep Research = agent 15min · U4 audio tronca → hallucination.

---

## 4. Sprint 0 — Riavvia il cuore (2-3 giorni, must-do)

### S0.1 — Fix bug `claim_extractor.py:216`
**File**: `apps/evaluator/nlm_deep_research/claim_extractor.py`
**Bug**: riga 216 `highest_tier = min(highest_tier, tier)` dove `tier = src.get("tier", 2)` — il default 2 vale solo se la chiave manca. Se il JSON ha `"tier": null` esplicito, torna `None` e `min(int, None)` eccepisce.
**Fix**:
```python
tier = src.get("tier") or 2   # handle None explicitly
```
**Test**: reset pipeline state (`apps/evaluator/nlm_nb2_pipeline_state.json` → `halted_at` → null, CB_NLM → CLOSED), run manuale `bash apps/evaluator/nlm_deep_research/scripts/run_nb2_pipeline.sh`, verifica log `apps/evaluator/nlm_deep_research/logs/nb2_pipeline_YYYYMMDD.log` senza TypeError.
**Exit**: NB-2 preflight passa + 1 cluster L1 completato senza crash.

### S0.2 — Diagnosticare e fixare il dispatcher cron
**Stato**: 8/9 pipeline escono in 3-5ms con `lastStatus=pending` in `~/.openclaw/cron/jobs.json`. Il dispatcher che le intercetta è `launchd → nuzantara-sentinel.py → openclaw gateway`.

**Azioni**:
1. Leggere `scripts/nuzantara-sentinel.py` per capire la logica di dispatch/mutex.
2. Confrontare con il caso che **funziona** (nb1-daily-refresh via `~/.cron-agent.sh exec`, 175s durata reale) vs il caso fallito (`10 2 * * 1-6 /bin/bash cron-runner.sh run_nb2_pipeline.sh` → 5ms).
3. Probabile root cause: `cron-runner.sh` da crontab **non** passa per openclaw/sentinel, quindi le heartbeat `~/.agent/decisions/state/*.last.json` vengono riscritte da un processo parallelo con `ts` stale preso dall'ultimo known run di openclaw (14/04).
4. Opzione A (conservativa): lasciare `cron-runner.sh` che funziona già per NB-2, **fixare il writer delle heartbeat** perché scriva `ts=real_exec_ts` non `ts=openclaw_last_seen`.
5. Opzione B (radicale): migrare tutti gli 8 cron a `~/.cron-agent.sh exec <name> <script>` come fa già nb1-daily-refresh. Rischio: eredita la stessa dispersione di status.

**Exit**: `~/.agent/decisions/state/nlm_nb2_pipeline.last.json` ha `ts` corrispondente al tempo reale di esecuzione di `nb2_pipeline.log`, non a 10 giorni fa.

### S0.3 — Pulire 4 entry crontab orfane
4 script referenziati mai esistiti: `run_yajna_scan.sh`, `run_yin_yang_audit.sh`, `run_hexagram_compute.sh`, `run_nb0_refresh.sh`.
**Azione**: `crontab -e` su Pro, rimuovere le 4 entry. Se si vuole davvero implementare uno (es. NB-0 meta refresh, richiesto da audit), aprire issue separato in Sprint 3.
**Exit**: `crontab -l | grep -E "yajna|yin_yang|hexagram|nb0_refresh"` → vuoto.

### S0.4 — Bridge HTTP NLM: accettare fallback subprocess
Il bridge `apps/nlm-bridge/main.py` su :18790 funziona con fallback subprocess CLI (testato: 38s warm, OK dentro timeout 120). **Non serve installare `notebooklm-tools` nel suo venv py3.11** perché (a) il pkg non è su PyPI sotto quel nome, (b) il CLI `/Users/nuzantara/.local/bin/nlm` già serve tramite subprocess.
**Azione**: aumentare il default timeout del bridge da 60 a 120s nel codice (riga 105 di `main.py`: `timeout: int = Field(default=60, ge=1, le=120)` → `default=100, le=180`). Aggiornare i caller che usano `timeout=60` default.
**Exit**: `curl /nlm/health` → `request_count > 0` dopo 1h di traffico normale dai cron.

### S0.5 — Honest monitoring su top esistente
NB-1 ha confermato: `heartbeat_monitor.py` (ARCH-9) esiste già e traccia DEAD/CRITICAL/timeout. **Non creare nuovi script**.
**Azione**: aggiungere al `heartbeat_monitor.py` una view `pipeline_truth_dashboard()` che incrocia 3 segnali per ogni pipeline:
1. `cron-start-event` (leggere da log `launchd` o da timestamp file marker)
2. `log-file-exists-today` (`apps/evaluator/nlm_deep_research/logs/{name}_YYYYMMDD.log` con size > 0)
3. `source-count-delta-nlm-cloud` (chiamata `nlm notebook list` vs snapshot precedente)
Alert Telegram se 2/3 segnali negativi consecutivi ≥ 2 esecuzioni.
**Exit**: 1 comando (`python -m apps.evaluator.nlm_deep_research.heartbeat_monitor --truth`) stampa tabella 9 righe (una per NB-2..NB-10) con 3 colonne segnali. Zero bugie da `mtime`.

**Sprint 0 exit criteria globale**:
- NB-2 pipeline gira ogni notte alle 02:10 WITA e produce `claims.jsonl` valido.
- NB-3/4/5/6/7/8/10 producono log reali (non più file /tmp/ assenti).
- Heartbeat dashboard veritiero.
- 4 crontab orfane eliminate.

---

## 5. Sprint 1 — Freshness contract e SLM (2 settimane)

### S1.1 — Doc hygiene gate (PRE-REQUISITO)
**Razionale**: NB-1 validation ha dimostrato che documentazione stale può far falsare il grounding (caso Federation v3 / a2a_service PoC rimosso). Prima di proceedere, pulire.

**Azione**: eseguire `scripts/docs_audit.py` (Docs Guardian esistente, PR #230-235) e flaggare doc che descrivono moduli non più presenti nel filesystem. Per ogni doc stale: banner archiviazione (come già fatto 2026-04-25 per `MULTI_DOMAIN_FUSION_ARCHITECTURE.md`, `NOTEBOOKLM_CAPABILITY_MATRIX.md`, `NOTEBOOKLM_STRATEGY.md`). Se il sospetto supera le 10 occorrenze (come `war-room-v2-a2a-phase1.md`): archivia intero file in `docs/archive/`.

**Exit**: query su NB-1 "quale è lo stato di `apps/federation/a2a_service.py` oggi?" → risposta "archiviato/rimosso, vedi banner", non "attivo".

### S1.2 — Estendere `freshness_monitor.py` (non crearne un nuovo)
**File esistente**: `apps/evaluator/nlm_deep_research/freshness_monitor.py` con `coverage_matrix.json` + `freshness_monitor_state.json` (Layer A+B+C documentati in commit history).

**Aggiunte**:
- Nuovo campo `max_staleness_h` per ogni NB nel JSON state (non YAML — NB-1 veto).
- Hook `verify_ingestion(notebook_id, uuid_marker)`: dopo ogni upload, invia source di test con UUID univoco, aspetta 30-60s, fa `nlm notebook query` chiedendo quell'UUID. Se non lo trova, flag NB come "stale despite recent write".
- Nuovo stato `STALE` nel vocabolario esistente {FRESH, DEGRADED, CRITICAL} → diventa {FRESH, DEGRADED, STALE, CRITICAL}. Retrocompatibile (DEGRADED resta).

**Exit**: `freshness_monitor.py --verify-ingestion NB-2` ritorna `FRESH` se il test UUID passa, `STALE` se manca.

### S1.3 — Oracle gate su stale
**File**: `apps/backend-rag/backend/services/oracle/nlm_notebook_registry.py` funzione `resolve_notebook()`.

**Modifica**: prima di ritornare il `notebook_id`, query `freshness_monitor.get_status(notebook_id)`. Se `STALE` o `CRITICAL` → ritornare `None` con reason. Il caller in `nlm_orchestrator.py` → fallback a Qdrant pure (no NLM).

**Test**: `test_nlm_orchestrator.py` deve essere esteso con caso `stale_notebook_returns_fallback`. Preservare i 10 test esistenti in `tests/` (NB-1 ha detto "98" ma il numero reale è 10 — stima NB-1 da verificare, probabile stima dalla snapshot 03-23).

**Exit**: chiamata reale a `/api/rag/query` con domain=tax su NB-4 artificialmente stale ritorna risposta senza citazioni NLM + header `X-Oracle-Fallback: stale_nlm`.

### S1.4 — Estendere `registry.py` per source lifecycle
**File esistente**: `apps/evaluator/nlm_deep_research/registry.py` gestisce `nlm_nb2_sources.json` etc.

**Aggiunte** al schema JSON (backward-compat, default valori per entry vecchie):
- `extracted_at`: ISO timestamp di prima ingestion
- `last_verified_at`: timestamp ultimo verify riuscito
- `next_review_at`: timestamp consigliato prossima verifica
- `upstream_url` o `upstream_drive_id`: origine se traceable
- `status`: enum {active, stale, revoked, duplicate}
- `checksum`: sha256 content

**Cron weekly**: `scripts/registry_audit.py` verifica URL reachable, aggiorna `last_verified_at`, flagga 404 come `status=revoked`.

**Exit**: `registry.py dump --nb NB-5 --status active` ritorna 73 source con tutti i campi compilati per le entry create dopo lo sprint.

### S1.5 — Pruning NB-INTEL sopra 100 source
NB-INTEL-AIResearch oggi 382 source, NLM self warning: "100-150 è sweet spot".

**Azione**: `scripts/nlm_intel_pruner.py` seleziona per ogni NB-INTEL i top-100 per `(recency × citation_frequency_in_RAG_logs)`. Soft-delete (archivia lista deleted IDs in `pruner_state.json` per rollback). Cron weekly dom 01:00 WITA.

**Exit**: `nlm notebook list | grep INTEL` tutti ≤ 120 source.

---

## 6. Sprint 2 — Shadow Graphing + CEP (3 settimane)

### S2.1 — Nuova collection Qdrant `nlm_shadow_hybrid` (NON inquinare esistenti)
NB-1 warning: "Infilare JSON claim in legal_unified provoca Validation Error su `HierarchicalChunk`".

**Azione**:
1. File `apps/backend-rag/backend/core/collection_registry.py`: aggiungere entry `nlm_shadow_hybrid` con payload schema proprio (Pydantic model `NLMShadowChunk` — NON refit `HierarchicalChunk`).
2. File `apps/backend-rag/backend/core/qdrant_db.py`: nuova collection con `text-embedding-3-small` (1536 dim, same embedder del resto — invariante golden rule).
3. Script `scripts/nlm_shadow_extractor.py`: per ogni NB domain, cron notturno 03:00 WITA, chiede a NLM claim in schema JSON strict, valida con DeepSeek (1 call, ~$0.01), commit in `nlm_shadow_hybrid` con payload `{source: 'nlm_shadow', nb_id, extracted_at, claim_text, verified_by_deepseek: bool}`.

**Red team NB-1 addressed**: `HierarchicalChunk` non toccato, `legal_unified` e `visa_oracle` intatti, zero Validation Error.

**Exit**: collection `nlm_shadow_hybrid` contiene 100+ claim/NB dopo 1 settimana di cron. `qdrant-cli inspect nlm_shadow_hybrid` ritorna count corretto, nessun errore Pydantic.

### S2.2 — Preservare `nlm_verifier.py` come async consumer
**File esistente**: `apps/backend-rag/backend/services/rag/nlm_verifier.py` verifica risposte RAG async.

**Modifica**: invece di chiamare NLM live, legge da `nlm_shadow_hybrid`. Se fallback-shadow non ha match sufficiente (confidence < soglia), allora (e solo allora) chiama NLM live via bridge :18790 asincrono. Non rompe esistente, migliora performance.

**Exit**: `nlm_verifier.verify(answer)` ritorna in <1s dal shadow invece di 15-40s dal live.

### S2.3 — Preservare `cross_notebook_correlator.py`
**File esistente**: `apps/backend-rag/backend/services/oracle/cross_notebook_correlator.py` ARCH-4 fa sub-process paralleli `nlm CLI`.

**Modifica**: wrapper async. Non rimuovere, **rendere non-blocking**. Aggiungere `BackgroundTasks` FastAPI, callback webhook, o Redis pub-sub. Il client ottiene subito risposta parziale + badge "cross-domain analysis in progress".

**Exit**: `/api/rag/query?cross_notebook=true` ritorna in <2s con risposta da Qdrant + async task id; il task completa in 30-60s e pubblica aggiornamento (WebSocket o polling endpoint).

### S2.4 — Preservare `db_to_nlm_sync.py`
**File esistente**: inietta metriche PG in NB-11/12/13 ogni notte 04:30 WITA.

**Azione**: zero modifica, ma aggiungere al monitoring S0.5 verifica che cron gira davvero. Non toccare, solo osservare.

**Exit**: log `db_to_nlm_sync_YYYYMMDD.log` esiste quotidianamente, source count NB-11/12/13 cresce.

### S2.5 — CEP (Continuous Evaluation Pipeline)
**Golden set**: 50 query legali (10 per dominio visa/company/tax/property/ops) con risposta attesa versionata `apps/evaluator/golden/golden_v20260425.json`.

**Evaluator**: DeepSeek Reasoner, ~$0.01 × 50 × 4/day = $2/day = ~$60/mese. Dentro budget.

**Output**: scoreboard Streamlit (rianimare dashboard esistente se c'è, o creare `apps/evaluator/cep_dashboard/`). Alert Telegram se hit rate <80% 2 run consecutive.

**Exit**: hit rate ≥ 80% sul golden set 7 giorni consecutivi.

---

## 7. Sprint 3 — Estensioni (solo se Sprint 0-1-2 tutti pass)

Promosso solo con freshness OK + CEP ≥ 80% 2 settimane consecutive.

- **S3.1 NB-META-SYSTEM** (U7 Gemini): changelog FastAPI/Qdrant/Fly.io + ADR → query pre-refactor. Da valutare: NLM ha forse già una forma di ADR nei nostri `docs/superpowers/specs/`? Se sì, estendere non creare.
- **S3.2 Reverse HyDE** (U8 DeepSeek) top 5000 chunk Qdrant, generatore Ollama qwen3.5 batch notturno. **NB-1 warning OOM risk**: coordinarsi con Naga/Surgeon nighttime batch schedule (verificare `apps/evaluator/core_guardian/`).
- **S3.3 NB-SANDBOX-MALICIOUS** (U9 DeepSeek) fault-injection, hard-label `malicious=true` in Qdrant payload per bloccare a runtime.
- **S3.4 Audio overview team internal** (U2.4 Gemini mitigated): briefing lunedì su cambi normativi, Telegram team. Mai client-facing.

---

## 8. Sprint 4 — Espansione dominio (gated by real user demand)

Solo se CRM segnala "queste domande clienti non hanno risposta" > 5/week:
- S4.1 NB-DIPLOMACY (DeepSeek 3.1) accordi Italia-Indonesia
- S4.2 NB-MACRO-BALI (Gemini 3.2) infrastrutture
- S4.3 NB-INFRASTRUCTURE (DeepSeek 3.3) PBG/IMB

**NON promuovere** NB-LIFESTYLE (scope creep, DeepSeek 3.5 lo sconsiglia esplicitamente).

---

## 9. Metriche di successo

Invariante da v1, con baseline aggiornato:

| Metrica | Oggi (24/04 audit) | Sprint 0 | Sprint 2 | Sprint 3 |
|---|---|---|---|---|
| Cron NB domain con log giornaliero | 1/9 | 9/9 | 9/9 | 9/9 |
| NB con freshness < 24h | N/A | baseline | ≥ 7/9 | ≥ 9/9 |
| Hit rate golden set | N/A | N/A | ≥ 80% | ≥ 90% |
| RAG query latency p95 | ? (8-30s sospetto) | ≤ 15s | ≤ 3s | ≤ 2s |
| Bridge NLM request_count/day | 0 | ≥ 50 | ≥ 200 | ≥ 500 |
| Test in `nlm_deep_research/tests/` | 10 (verificato) | 12 (+2 new) | 16 | 16 |
| Collection Qdrant `nlm_shadow_hybrid` | 0 | 0 | ≥ 500 claim | ≥ 2000 |
| Docs stale flagged (post S1.1) | 3 flaggati | 0 | 0 | 0 |

---

## 10. Red team globale del piano v2

- **R1 heartbeat writer**: S0.2 richiede capire chi scrive le heartbeat stale. Se sbagliamo root cause, stesso problema ritorna. Mitigation: prima di cambiare nulla, tracciare via `fs_usage` chi tocca `~/.agent/decisions/state/nlm_*.last.json`.
- **R2 Shadow extractor prompt drift**: NLM può cambiare output structure; parser JSON rompe silent. Mitigation: CEP (S2.5) include check "shadow graph freschezza" — se nuovi claim <10/giorno, alert.
- **R3 NLM_verifier fallback chain**: se shadow manca + live timeout, il verifier deve non bloccare RAG. Mitigation: fallback finale = skip verification, response flagged `unverified=true` nel payload utente.
- **R4 Evaluator self-judge**: DeepSeek giudica shadow da DeepSeek-validated. Bias. Mitigation: rotazione evaluator (week A DeepSeek, week B Gemini, week C Claude code-review del golden).
- **R5 NB-1 drift futuro**: NB-1 auto-refresh tutte le notti, ma i doc che legge (come MULTI_DOMAIN_FUSION) li aggiorna solo quando il file sorgente cambia. Soluzione: cron weekly `docs_audit.py` identifica doc stale, flag auto-banner. Parte di S1.1.

---

## 11. Verdict v2

Il piano v1 era concettualmente valido ma operativamente sbagliato in 4 punti critici (YAML nuovi vs JSON esistenti, cron-runner vs launchd+sentinel, venv notebooklm-tools vs subprocess fine, ignorava `nlm_verifier`/`cross_notebook_correlator`/`db_to_nlm_sync`). Il v2 mappa tutto su file che esistono e funzioni già documentate. 

**Priorità #1 domani mattina**: S0.1 (fix `claim_extractor.py:216` 1 riga) + S0.2 tracing (capire `fs_usage` che scrive heartbeat stale, 30 min). Con queste 2 cose NB-2 torna operativo e il monitoraggio smette di mentire.

Senza Sprint 0 nessuno Sprint successivo ha senso. Con Sprint 0 + Sprint 1 hai il baseline. Con Sprint 2 sei genuinamente SOTA (Shadow Graphing + CEP + async preservation). Sprint 3-4 sono ambiziosi, gated da metriche, non da tempo.

---

**Note**:
- Tutto Anthropic-safe (Claude OAuth only, DeepSeek paid OK, Gemini free OAuth, Ollama locale).
- Hardware compatibile: 48GB Pro + 16GB Air.
- Zero cloud GPU budget. Zero paid Anthropic.
- **Prossimo step**: eseguire Sprint 0 punto S0.1 ora (fix 1 riga).
