# SINTESI BRAINSTORM — Top-3 OSS Injections per Nuzantara

**Data:** 2026-04-26 · **Macchina:** Air · **Brainstorm condotti:** 6/9 (Codex × 3 in coda — quota ChatGPT Plus reset 21:32)

---

## Metodologia

Per ognuno dei 3 candidati top del [report originale](./_initial_report.md) ho richiesto un brainstorm a 3 LLM con prospettive diverse:

- **Gemini 3.1 Pro** — concretezza, citazioni di issue/version, terse
- **DeepSeek R1 (reasoner)** — ragionamento architetturale profondo (chain-of-thought visibile, ~1000-1500 reasoning tokens per call)
- **Codex GPT-5.5 sandbox** — code review, bug hunting (RIMANDATO per quota)

I prompt sono stati calibrati per evitare l'echo chamber: domande sui rischi, edge case, counterfactual, alternative.

**Consenso emerso: 3/3 candidati ricevono ADOPT-PARTIAL** dai 2 LLM completati. Nessun REJECT, nessun ADOPT incondizionato. Le linee di adozione **convergono indipendentemente** tra Gemini e DeepSeek — segnale di robustezza della raccomandazione.

---

## #1 — Instructor (567-labs/instructor)

### Verdetto consensuale: **ADOPT-PARTIAL**

### Convergenze tra Gemini e DeepSeek

1. **Wrapper architetturale necessario** — non importare `instructor` direttamente nei service, sempre dietro `backend/llm/structured.py` per protezione futura (potenziale swap a `pydantic-ai`).
2. **Pilot su `classification/` o `grading/*`** — schema piatti, fallback gracieful.
3. **Mai migrare KG extraction** — schema profondi, token overhead 500-1000/call, qwen3.5 fallisce su nesting.
4. **Claude OAuth = legacy outlier** — non torcere l'architettura per supportarlo nello structured output. Tenere quei call nel pattern `try/except`.
5. **Ollama: include `chain_of_thought: str` come primo field Pydantic** per mitigare degradazione locale.

### Divergenze

- **Gemini**: suggerisce di considerare `pydantic-ai` come alternativa migliore di `instructor` (Pydantic team).
- **DeepSeek**: concorda che pydantic-ai è il futuro, ma il wrapper protegge contro questa scelta — migra dopo, non ora.

### Insight critici emersi (non nel report originale)

- **`reasoning: str` come PRIMO field** del Pydantic schema riduce drasticamente il fallimento di validazione (forza il modello a "pensare" prima di committere alla risposta strutturata).
- **Token inflation reale**: ogni call con schema nested ripete le chiavi JSON (e.g. `"source_node"`, `"target_node"`) nel prompt — per KG migliaia di volte è waste.
- **Native vs prompted**: il wrapper deve usare `response_mime_type="application/json"` + `response_schema` di Gemini, non solo prompt-engineering.

### Sequenza di adozione concreta

1. Implementare `backend/llm/structured.py` (Gemini + DeepSeek + Ollama, NO Claude)
2. Migrare `services/classification/` (pilot, smaller blast radius)
3. Migrare `services/rag/grading/` con `max_retries=1` e `reasoning: str` first
4. Migrare `services/kbli_eye.py` (KBLI extract)
5. Migrare `services/multimodal/pdf_vision_service.py` (vision, test isolato)
6. **NON migrare** KG extraction — resta `try/except`

**Effort:** 2-3 giorni · **Rischio:** basso · **ROI:** ⭐⭐⭐ (riduce silent JSON failures, schema-as-docs)

---

## #2 — OpenLLMetry (traceloop/openllmetry)

### Verdetto consensuale: **ADOPT-PARTIAL**

### Convergenze tra Gemini e DeepSeek

1. **NON usare blanket `Traceloop.init()`** — DeepSeek esplicito: usare `instrument_openai` / `instrument_google_genai` separatamente per controllo esplicito.
2. **PII scrubbing è un GATE non-negoziabile** — UU PDP + GDPR. Implementare custom `SpanProcessor` con Presidio prima di abilitare l'auto-instrument.
3. **Migration: layered + parallel run** — non cold cutover su 5000 client. Tenere LangSmith per orchestration spans, OpenLLMetry per LLM client spans, per 2 settimane.
4. **Claude CLI shell-out richiede istrumentazione manuale** — wrapper subprocess con `tracer.start_as_current_span` e `gen_ai.system=claude-cli` attribute (Gemini ha dato il codice esatto).
5. **W3C `traceparent` propagation** — propagare da `apps/mouth` (Next.js) a `apps/backend-rag` per linkare i trace di frontend a quelli di LLM. Senza questo i span sono orfani.

### Divergenze

- **Gemini**: suggerisce `OpenInference` (Arize) come alternativa più matura per le semantic conventions.
- **DeepSeek**: si focalizza più sulla compliance GDPR + UU PDP, sostenendo che self-host Langfuse è strategically necessary, non just nice-to-have.

### Insight critici emersi

- **Failure mode**: `BatchSpanProcessor` su daemon thread, mai blocca LLM call, queue di 2048 span max — può silently dropparli. Su Fly.io 2GB watch out per OOM se queue fill alta.
- **GDPR Right to Erasure**: Langfuse self-hosted → DELETE diretto su DB. LangSmith SaaS → ticket manuale (compliance debole).
- **OTEL gen-ai conventions ancora sperimentali** — abstract dietro helper library per localizzare future spec changes.

### Sequenza di adozione concreta (DeepSeek 5-phase)

- **Phase 0**: PII Scrubbing custom SpanProcessor + Claude manual instrumentation (deploy senza abilitare OpenLLMetry, baseline)
- **Phase 1**: Staging parallel — abilitare OpenLLMetry su Gemini + OpenAI-compat in staging, comparare con LangSmith per 1 settimana
- **Phase 2**: Production layered — LangSmith @traceable per orchestration + OpenLLMetry per LLM raw spans
- **Phase 3 (dopo 2 settimane)**: Cutover — rimuovere LangSmith dependency, retire subscription
- **Phase 4**: Long-term — dashboard Grafana/Langfuse, GDPR erasure automatica

**Effort:** 3-4 giorni iniziali + 2 settimane parallel run · **Rischio:** medio · **ROI:** ⭐⭐⭐ (vendor unlock + compliance + auto-instrument)

---

## #3 — Atlas (ariga/atlas) lint gate

### Verdetto consensuale: **ADOPT-PARTIAL** (lint-only, NOT runtime replacement)

### Convergenze tra Gemini e DeepSeek

1. **Architetturale: CI = lint, runtime = our code** — il `migration_manager.py` resta intoccato, Atlas è solo un gate aggiuntivo nel `pre-deploy-gate` GitHub Action.
2. **Format adapter in CI** beats migrating 140 file a Atlas-native format. Bash/Python script ~20 righe split `-- UPGRADE` / `-- ROLLBACK` in `NNN_up.sql` + `NNN_down.sql`.
3. **Baseline ignore per migration vecchie** — non fare big-bang cleanup di 140 file. `.atlaslint.yml` esclude pre-`migration_100`, lint stretto solo su nuove.
4. **Keep hand-written rollbacks** — Atlas valida _existence_ non rigenera. Hand-written rollback ci hanno salvato 2 volte (incidenti reali).
5. **Postgres extensions native** — Atlas usa real Postgres 17 Docker, conosce `pg_trgm`, `jsonb`, partial indexes. Solo serve `CREATE EXTENSION IF NOT EXISTS` matching prod.
6. **CI cost trascurabile** — 15-20 secondi su pipeline da 5 minuti.

### Divergenze

- **Gemini**: suggerisce di paired Atlas (CI) con runtime check in `migration_manager.py` — pre-flight `SELECT count(*)` su DROP COLUMN per evitare data loss. Atlas è shift-left only.
- **DeepSeek**: concorda ma sostiene che il runtime check è una feature separata, non blocker per l'adozione di Atlas.

### Insight critici emersi

- **PR #302** (migration 138 missing rollback_sql) sarebbe stata catturata automaticamente da Atlas.
- **`-- atlas:nolint`** annotazioni per data-only o complex functional migrations.
- **`--latest 1`** flag scope lint a sola nuova migration su ogni PR (non re-lint vecchie ad ogni PR).

### Sequenza di adozione concreta

1. **Script `ci/split_migrations.sh`** — split UPGRADE/ROLLBACK in pair per Atlas
2. **`atlas.hcl`** o `.atlaslint.yml` con baseline ignore migration < 100
3. **Add step in `.github/workflows/pre-deploy-gate.yml`** con `ariga/atlas-action/migrate/lint@v1`, `--latest 1`
4. **Cron mensile `migration_manager.py:check_rollback_debt()`** — surface migration vecchie con rollback debole, opzionale fix
5. **Future**: pair con runtime pre-flight check per data-loss prevention (separate work item)

**Effort:** 1-2 giorni · **Rischio:** basso · **ROI:** ⭐⭐⭐ (defense-in-depth, preveniva PR #302)

---

## RACCOMANDAZIONE FINALE OPERATIVA

**Tutti e 3 i candidati ottengono ADOPT-PARTIAL convergente da 2 LLM indipendenti.**

### Sequenza ottimale di iniezione

| Settimana | Iniezione                                                     | Effort                   | Rationale                                                          |
| --------- | ------------------------------------------------------------- | ------------------------ | ------------------------------------------------------------------ |
| **W1**    | Atlas lint gate                                               | 1-2d                     | Lowest-effort, blocked-by-nothing, immediate ROI on next migration |
| **W1**    | OpenLLMetry Phase 0 (PII scrubber + Claude manual instrument) | 1d                       | Foundation work, no behavior change yet                            |
| **W2**    | OpenLLMetry Phase 1 (staging parallel)                        | 1d setup + 1w validation | Low-risk staging-only test                                         |
| **W2-W3** | Instructor wrapper + classification pilot                     | 2-3d                     | Pilot small, learn before scaling                                  |
| **W3-W4** | Instructor migration: graders, KBLI, OCR akta                 | 2-3d                     | Scale to remaining hot-spots (NO KG)                               |
| **W4**    | OpenLLMetry Phase 2 (production layered)                      | 1d setup + 1-2w monitor  | Layered low-risk prod rollout                                      |
| **W6**    | OpenLLMetry Phase 3 (cutover, retire LangSmith)               | 1d                       | Final removal, vendor unlock complete                              |

### Costo totale stimato

- **Effort engineering**: 8-12 giorni distribuiti su 6 settimane (~2 giorni/settimana media)
- **Riduzione vendor lock**: LangSmith subscription eliminata (saving ricorrente)
- **Compliance UU PDP/GDPR**: passaggio da SaaS scrub a self-host scrub + erasure diretto
- **Defense in depth migrations**: Atlas previene class di bug PR #302
- **JSON output reliability**: Instructor riduce silent JSON failures su classification, graders, KBLI, OCR

### Cosa NON è cambiato dal report originale

- Tutti gli altri 13 candidati restano nelle priorità sprint 2-3 e mese 1+
- Le esclusioni sono confermate: ❌ LangGraph replace, ❌ embedding model swap, ❌ Qdrant replace, ❌ Postgres → Neo4j

### Quando completare con Codex (post 21:32)

I 3 brainstorm Codex restanti (uno per candidato) servono per **code review specifico** — concrete bugs/risks nel design proposto. Non cambieranno la raccomandazione, ma daranno findings tecnici puntuali. Lascio i task #9, #12, #15 in stato pending.

---

## File generati in questa sessione

```
~/Desktop/brainstorm_oss_2026-04-26/
├── 00_SYNTHESIS.md                    (questo file)
├── 01_instructor_gemini.md
├── 01_instructor_deepseek.md
├── 02_openllmetry_gemini.md
├── 02_openllmetry_deepseek.md
├── 03_atlas_gemini.md
├── 03_atlas_deepseek.md
└── 01_instructor_deepseek_raw.txt     (raw API output con chain-of-thought)
```

**Source originale:** `~/Desktop/REPORT_INJECTIONS_OSS_2026-04-26.md`
