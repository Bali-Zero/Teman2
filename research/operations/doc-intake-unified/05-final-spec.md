---
date: 2026-06-04
domain: operations
study: doc-intake-unified
phase: 5 — FINAL EXECUTABLE SPEC
status: DRAFT
client_case: false
sources:
  - research/operations/doc-intake-unified/00-INDEX.md
  - research/operations/doc-intake-unified/01-system-study.md
  - research/operations/doc-intake-unified/02a-external-sota.md
  - research/operations/doc-intake-unified/03-panel-review.md
  - research/operations/doc-intake-unified/04-0-integration-check.md
  - research/operations/doc-intake-unified/04-1-ingestion-dedup.md
  - research/operations/doc-intake-unified/04-2-queue-orchestrator.md
  - research/operations/doc-intake-unified/04-3-classify-extract-validate.md
  - research/operations/doc-intake-unified/04-4-entity-routing.md
  - research/operations/doc-intake-unified/04-5-hitl-evolver.md
  - research/operations/doc-intake-unified/05a-reusable-code-internal.md
  - research/operations/doc-intake-unified/05b-reusable-libs-oss.md
  - research/operations/doc-intake-unified/05c-nb-patterns.md
  - research/operations/doc-intake-unified/05d-reusable-repos-github.md
  - research/operations/doc-intake-unified/05e-reusable-repos-infra.md
  - live: psql nuzantara_dev migrations_v2 (205 = highest, 206 free) + MODEL_TOPOLOGY.json (Pro, 2026-06-04)
---

# FASE 5 — FINAL EXECUTABLE SPEC: Unified Document-Intake (Bali Zero)

> **Scopo**: spec da cui un dev (o un agente) PARTE A COSTRUIRE. Consolida le 5 parti
> (04-1..04-5), risolve le 12 contraddizioni X1-X12 (04-0), recepisce i fix panel C1-C7
> (03) e le correzioni NB (05c: validate spezzato in script-deterministico + agente-normativo;
> HITL pull-not-push; source_page+confidence da OCR vero), e per OGNI componente dichiara la
> **provenienza-codice** (copia/forka/installa/scrivi-nuovo) rispettando le licenze.
>
> **Non si ridisegna nulla**: 04-0 ha già stabilito che le 5 parti sono architetturalmente
> concordi. Questa spec unifica i contratti dato-per-dato e mappa il codice.

---

## 0. DECISIONI CANONICHE (chiudono X1-X12)

Una sola scelta per ogni contraddizione. **Tutto il codice DEVE conformarsi a questa tabella.**

| # | Contraddizione | DECISIONE CANONICA | Conseguenza |
|---|---|---|---|
| **X1** | nome tabella coda | **`intake_queue`** (lavoro, mutabile) + **`document_instances`** (registro blob immutabile). Modello 2-tabelle di P1. | P2 scarta `intake_job`; togliere la UNIQUE `(blob_hash,pipeline_version)` su coda-lavoro (resta solo su `document_instances`). |
| **X2** | tipo `pipeline_version` | **`VARCHAR(32)`**, valore canonico **`'intake-v1'`** (sostituisce sia `ocr-v3-...` sia INT). | Concatenabile in chiave testuale. P2 abbandona INT. |
| **X3** | enum `source` | **`whatsapp \| drive \| zoho`** (P1 corregge `wa`→`whatsapp`). | CHECK constraint allineato a 4/5 doc. |
| **X4** | tipo `source_ref` | **`TEXT`**, encoding canonico **`<source>:<id>[:<subid>]`** (es. `whatsapp:wmc:123`, `drive:fileId`, `zoho:msgId:attId`). | Deterministico, concatenabile. P2 abbandona JSONB. |
| **X5** | forma payload P3→P4 | **JSON per-singolo-documento** (1 job = 1 blob). P4 consuma N JSON singoli, NO wrapper batch/`client_slug`/`summary`. | Coerente con coda 1-job-1-blob. |
| **X6** | blocco `source{}` provenance | **P3 propaga `source{}`** da P1 (sender_phone/email + media_path + source_ref) nel suo output. | Chiude la giunzione P3→P4 (entity-res phone/email→client). |
| **X7** | idempotency-key d'intake | **`intake_key = sha256(source \| source_ref \| blob_hash \| pipeline_version)`** (UNA chiave canonica). | P2 deriva la UNIQUE da `intake_key` (NON da `blob_hash,pipeline_version` da solo → multi-cliente permesso, C1). P3 per-stadio = `sha256(intake_key\|stage)`. P4 routing = `intake_key:doc_index`. |
| **X8** | macchina-stati proposta | **una sola**: `review_pending → review_claimed → routed \| rejected`. P4 adotta gli stati di P5. | P4 abbandona `proposed/approved/committed`. |
| **X9** | nome tabella proposta | **`document_routing_proposal`** (P5 la legge). | Confermato. |
| **X10** | hint cliente | **`client_id_hint`** (BIGINT, non autoritativo). P4 abbandona `client_slug`. | Coerente P1→P4. |
| **X11** | formato `blob_hash` | **hex64 grezzo, nome `blob_hash` ovunque** (P4 rinomina `blob_sha256`→`blob_hash`; P3 toglie prefisso `sha256:`). | Coerenza chiave concatenata. |
| **X12** | campi da rivedere | **`needs_review_fields[]`** (lista nomi). P4 abbandona `low_confidence_fields`/`needs_field_review`. | Concorde P3/P5. |
| **PK** | tipo PK riga coda | **`BIGSERIAL`** (`id BIGINT`) interno ovunque. P3/P5 correggono da `uuid` a BIGINT. (uuid pubblico opzionale solo se serve esporlo). | Coerente P1/P2; P3/P5 si adeguano. |

**Regola d'oro di conformità**: ogni file nuovo o forkato passa il lint `grep` contro i
nomi vietati (`intake_job`, `blob_sha256`, `client_slug`, `low_confidence_fields`, source `'wa'`,
`source_ref` JSONB) prima di merge.

---

## 1. ARCHITETTURA CONSOLIDATA

```
 P1 INGESTION             P2 ORCHESTRATOR            P3 PROCESSING (strict-local)     P4 ROUTING      P5 HITL
 ────────────             ───────────────            ────────────────────────────    ──────────      ───────
 wa_intake_adapter ─┐
 drive_intake_adapter┼─enqueue()─► intake_queue ─► worker loop ─► [1] classify ──┐                   review-gate
 zoho_intake_adapter─┘  (dedup C1) (FOR UPDATE      (claim/lease/  [2] extract    │   entity-res      (per-campo C3)
        │               document_   SKIP LOCKED,     retry/DLQ)    [3a] validate- │   (C4 link-only)  CRM web view
        │               instances)  exactly-once C2) in-process    script (det.)  │   route proposal  + intake_
   blob locali Pro                                  funcs          [3b] validate- │   (read-only,     corrections
   (Law 2)                                                         agent (norm.)  │    NO write)             │
                                                                   [4] route ─────┘        │          [evolver hook
                                                                                  document_routing_      weekly, gated]
                                                                                  proposal (queue)  ◄────────┘
                                                                                           │
                                                                  P5 ONLY WRITER ► D1 CRM documents / D2 Drive / interactions
                                                                                           │
                                                                                  D3 auditor (read-only consumer)
```

**Invarianti che attraversano tutto il sistema** (vincoli §6 del task):
- **PII 100% locale** (Law 2 / UU-PDP): coda, blob, worker, `intake_corrections` vivono su
  `127.0.0.1:5432/nuzantara_dev` sul Pro. Mai Fly, mai cloud, mai RAG/Qdrant (B1), mai NotebookLM (B2).
- **P5 è l'unico writer** verso `documents`/`clients`/Drive/`interactions`. P4 è read-only (solo
  scrive in `document_routing_proposal`). Nessuna mutation diretta sopra-soglia bypassa la queue.
- **Modelli via `MODEL_TOPOLOGY.json`** (repo root) → `get_role(...)`. Mai model-id hardcoded.
- **Anti retry-storm W61**: worker = daemon a loop interno (idle-sleep), `KeepAlive SuccessfulExit=false`,
  `ThrottleInterval=30`, circuit-breaker su DB-down.

---

## 2. SCHEMA DB UNICO — migration `206_intake_unified.sql`

> Numero **206 verificato libero** (Pro 2026-06-04: `205_cockpit_intents.sql` è il più alto).
> DB locale `nuzantara_dev`. Tutto idempotente (`IF NOT EXISTS`) + sezione ROLLBACK.

```sql
-- ============================================================================
-- 206_intake_unified.sql — Unified document-intake (LOCAL Pro DB only)
-- Recepisce X1-X12 (04-0) + C1/C2/C3/C4/C5/C6 (03-panel).
-- ============================================================================

-- ── A. Registro IMMUTABILE blob fisici (append-only) — X1 -------------------
CREATE TABLE IF NOT EXISTS document_instances (
    id                   BIGSERIAL PRIMARY KEY,
    blob_hash            CHAR(64)    NOT NULL,            -- X11 hex64 grezzo
    normalized_text_hash CHAR(64),                        -- post-OCR (C1 near-dup testo)
    phash                CHAR(16),                         -- perceptual hash immagini (C1)
    pipeline_version     VARCHAR(32) NOT NULL,            -- X2 'intake-v1'
    blob_path            TEXT        NOT NULL,            -- path locale Pro (mai URL cloud)
    byte_size            BIGINT,
    mime_type            VARCHAR(100),
    first_source         VARCHAR(8)  NOT NULL,            -- X3
    first_source_ref     TEXT,                             -- X4
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_di_source CHECK (first_source IN ('whatsapp','drive','zoho'))
);
-- DEDUP ESATTO cross-source: stesso blob+pipeline = stessa instance (ri-OCR su bump version)
CREATE UNIQUE INDEX IF NOT EXISTS uq_di_blob_pipeline
    ON document_instances (blob_hash, pipeline_version);
CREATE INDEX IF NOT EXISTS idx_di_phash
    ON document_instances (phash, pipeline_version) WHERE phash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_di_text_hash
    ON document_instances (normalized_text_hash, pipeline_version) WHERE normalized_text_hash IS NOT NULL;

-- ── B. Coda di LAVORO unificata (mutabile) — X1 -----------------------------
CREATE TABLE IF NOT EXISTS intake_queue (
    id                BIGSERIAL PRIMARY KEY,              -- PK = BIGSERIAL (decisione PK)
    instance_id       BIGINT      NOT NULL REFERENCES document_instances(id) ON DELETE RESTRICT,
    source            VARCHAR(8)  NOT NULL,               -- X3
    source_ref        TEXT        NOT NULL,               -- X4  <source>:<id>[:<subid>]
    blob_path         TEXT        NOT NULL,
    blob_hash         CHAR(64)    NOT NULL,               -- X11 denormalizzato dedup O(1)
    text_hash         CHAR(64),                            -- popolato post-OCR (P3)
    phash             CHAR(16),
    client_id_hint    BIGINT,                              -- X10 (non autoritativo)
    pipeline_version  VARCHAR(32) NOT NULL,               -- X2
    -- macchina-stati unica (C2)
    status            VARCHAR(20) NOT NULL DEFAULT 'pending',
    stage             VARCHAR(16),                          -- ultimo stage completato
    -- exactly-once / lease (C2)
    lease_owner       TEXT,
    lease_expires_at  TIMESTAMPTZ,
    attempts          INT NOT NULL DEFAULT 0,
    max_attempts      INT NOT NULL DEFAULT 5,
    next_visible_at   TIMESTAMPTZ NOT NULL DEFAULT now(), -- backoff
    last_error        TEXT,                                 -- PII-masked (C6)
    stage_output      JSONB NOT NULL DEFAULT '{}'::jsonb,  -- per-stadio + idempotency (C2/C6 minimale)
    -- dedup linking (C1/C5)
    dedup_of          BIGINT REFERENCES intake_queue(id),  -- duplicato esatto
    near_dup_of       BIGINT REFERENCES intake_queue(id),  -- versione (phash/text)
    near_dup_reason   VARCHAR(16),
    -- idempotenza enqueue (X7)
    intake_key        TEXT NOT NULL,                        -- sha256(source|source_ref|blob_hash|pipeline_version)
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_iq_source CHECK (source IN ('whatsapp','drive','zoho')),
    CONSTRAINT chk_iq_status CHECK (status IN
      ('pending','processing','ocr','classified','extracted',
       'review_pending','review_claimed','routed','rejected','done','dead','duplicate'))
);
-- X7: UNIQUE su intake_key (NON su blob_hash,pipeline_version → multi-cliente OK, C1)
CREATE UNIQUE INDEX IF NOT EXISTS uq_iq_intake_key ON intake_queue (intake_key);
-- claim atomico C2
CREATE INDEX IF NOT EXISTS idx_iq_claimable
    ON intake_queue (next_visible_at, id)
    WHERE status IN ('pending','processing','ocr','classified','extracted');
CREATE INDEX IF NOT EXISTS idx_iq_review
    ON intake_queue (status, updated_at) WHERE status IN ('review_pending','review_claimed');
CREATE INDEX IF NOT EXISTS idx_iq_dead
    ON intake_queue (status, updated_at) WHERE status = 'dead';

-- ── C. Metriche per-stadio (append-only, osservabilità C6) ------------------
CREATE TABLE IF NOT EXISTS intake_stage_metrics (
    id          BIGSERIAL PRIMARY KEY,
    queue_id    BIGINT NOT NULL REFERENCES intake_queue(id),
    stage       VARCHAR(16) NOT NULL,
    latency_ms  INT,
    confidence  REAL,
    model       VARCHAR(80),
    ok          BOOLEAN,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── D. Routing proposal (P4 scrive, P5 legge) — X8/X9 -----------------------
CREATE TABLE IF NOT EXISTS document_routing_proposal (
    id               BIGSERIAL PRIMARY KEY,
    queue_id         BIGINT NOT NULL REFERENCES intake_queue(id),
    doc_index        INT NOT NULL DEFAULT 0,
    pipeline_version VARCHAR(32) NOT NULL,
    routing_key      TEXT NOT NULL,                        -- X7  intake_key:doc_index  (UNIQUE)
    entity_resolution JSONB NOT NULL,                      -- decision/client_id/score/signals/candidates
    routing          JSONB NOT NULL,                        -- D1/D2/interactions/D3 payload-ready
    commit_gate      JSONB NOT NULL,                        -- auto_commit_eligible/requires_human/reasons
    status           VARCHAR(20) NOT NULL DEFAULT 'review_pending',  -- X8
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_rp_status CHECK (status IN ('review_pending','review_claimed','routed','rejected','dead'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_rp_routing_key ON document_routing_proposal (routing_key);

-- ── E. Correzioni HITL (seme evolver) — P5 ----------------------------------
CREATE TABLE IF NOT EXISTS intake_corrections (
    id            BIGSERIAL PRIMARY KEY,
    queue_id      BIGINT      NOT NULL REFERENCES intake_queue(id),
    blob_hash     CHAR(64)    NOT NULL,
    doc_type      TEXT        NOT NULL,
    field_name    TEXT        NOT NULL,
    source        VARCHAR(8)  NOT NULL,
    ai_value      TEXT,                                     -- PII: local-only
    human_value   TEXT,                                     -- PII: local-only
    ai_confidence REAL,
    outcome       TEXT        NOT NULL,                     -- approved|corrected|rejected|auto_committed
    model_id      TEXT, model_version TEXT, stage TEXT,
    rule_passed   BOOLEAN,
    verified_by   TEXT        NOT NULL,
    verified_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_corrections_digest ON intake_corrections (doc_type, field_name, outcome);
CREATE INDEX IF NOT EXISTS idx_corrections_recent ON intake_corrections (verified_at);

-- ── F. updated_at trigger ----------------------------------------------------
CREATE OR REPLACE FUNCTION trg_intake_queue_touch() RETURNS trigger AS $$
BEGIN NEW.updated_at := now(); RETURN NEW; END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS t_intake_queue_touch ON intake_queue;
CREATE TRIGGER t_intake_queue_touch BEFORE UPDATE ON intake_queue
    FOR EACH ROW EXECUTE FUNCTION trg_intake_queue_touch();

-- ── G. cursore poll Zoho (Drive riusa drive_poll_page_token esistente) ------
INSERT INTO system_settings (key, value, updated_at)
VALUES ('zoho_intake_cursor', '{}', now()) ON CONFLICT (key) DO NOTHING;

-- ROLLBACK ------------------------------------------------------------------
-- DROP TABLE IF EXISTS intake_corrections, document_routing_proposal,
--   intake_stage_metrics, intake_queue, document_instances CASCADE;
-- DROP FUNCTION IF EXISTS trg_intake_queue_touch();
-- DELETE FROM system_settings WHERE key='zoho_intake_cursor';
```

### Migration di colonna separata — `207_clients_birth_date_kitas.sql` (debito schema 04-4)
```sql
-- clients NON ha birth_date né kitas_number come colonne (verificato models.py:25-60).
-- C4 richiede birth_date come discriminante BLOCKING (oggi solo tie-breaker via custom_fields).
ALTER TABLE clients ADD COLUMN IF NOT EXISTS birth_date   DATE;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS kitas_number TEXT;
CREATE INDEX IF NOT EXISTS idx_clients_birth_date ON clients (birth_date) WHERE birth_date IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_clients_kitas      ON clients (kitas_number) WHERE kitas_number IS NOT NULL;
-- ROLLBACK: ALTER TABLE clients DROP COLUMN birth_date, DROP COLUMN kitas_number;
```
> Backfill da `custom_fields->>'kitas_number'` opzionale, separato, non bloccante.

---

## 3. I 5 STADI — con PROVENIENZA-CODICE per ogni componente

Legenda azione: **COPIA** da repo OSS (vendor con attribuzione) · **FORKA** da nostro file:riga ·
**INSTALLA** lib pip · **NUOVO** scrivi da zero · **STUDIA** (GPL/AGPL, leggere non vendorare).

### P1 — INGESTION & DEDUP  → modulo `backend/intake/ingest/`

| Componente | Azione | Provenienza esatta |
|---|---|---|
| `BasePollAdapter` (read_cursor/fetch_changes/save_cursor/dispatch) | **FORKA** | `services/crm/drive_poll_service.py:34-360` (astrai il poller in base-class). Pattern di astrazione ispirato a **singer-tap-template** (05e) — **STUDIA only** (AGPL-3.0, mai vendorare: re-implementa discover/sync). |
| `DriveCircuitBreaker` condiviso | **FORKA → estrai** | `services/crm/drive_poll_service.py:34-98` → nuovo `services/common/circuit_breaker.py` (parametrizzabile, condiviso da tutti gli adapter). |
| `wa_intake_adapter.py` (consumer locale, drena `ocr_status='pending'`) | **NUOVO** (thin) | Query pickup riusa indice `idx_wmc_ocr_pending`; legge file da `/Users/nuzantara/wa-mirror-media/`. Chiude gli 8.355 unconsumed. `source_ref='whatsapp:wmc:'||id`. Post-enqueue: `ocr_status='pending'→'enqueued'`. |
| `drive_intake_adapter.py` (avvolge `poll_drive_changes`) | **FORKA** | `drive_poll_service.poll_drive_changes()` (Changes API + page_token in `system_settings.drive_poll_page_token`). Cambio chirurgico: dove chiama `_dispatch_ocr_by_folder` (~riga 245), intercetta PRIMA → scarica blob in `/Users/nuzantara/drive-intake-media/` → `enqueue()`. Elimina la saturazione PG (fan-out rate-limitato dal worker). Leader-election Pro+Mini. `source_ref='drive:'||file_id`. |
| `zoho_intake_adapter.py` (poll inbox) | **NUOVO** (replica drive pattern) | Su client REST esistente `zoho_email_service` (`list_emails`, `get_attachment()->bytes`). Cursore `system_settings.zoho_intake_cursor`. `source_ref='zoho:'||msg_id||':'||att_id`. Pattern riferimento **wa-dokumen-extractor-bot** (05d, MIT) per routing-per-tipo, **COPIA** regex idea soltanto. |
| `enqueue(IntakeItem) -> EnqueueResult` (dedup C1, ON CONFLICT) | **NUOVO** | Logica dedup §3 di 04-1 (matrice GIÀ VISTO/NUOVA VERSIONE/NUOVO). Idempotenza su `intake_key` (X7). |
| hash: `blob_hash` byte-exact | **INSTALLA** | **xxhash** (05b) per byte-exact veloce, MA per `intake_key` usa **sha256** (hashlib stdlib, deterministico cross-process — decisione X7). xxhash solo per pre-check O(1) opzionale. |
| hash: `phash` immagini | **INSTALLA** | **ImageHash** (`pip install ImageHash`, 05b) — phash su immagini per near-dup. |
| hash: `normalized_text_hash` | **NUOVO** (1 funzione) | `sha256(normalize(ocr_text))` post-OCR (popolato in P3). datasketch/MinHash (05b) **rinviato** (serve solo a scala). |

**Contratto output P1→P2** (`doc-intake/intake-item` v1.0, verbatim §5 di 04-1) — con i campi
canonici X3/X4/X10/X11 e il blocco `routing_hints{sender_email, subject, wa_message_id, drive_file_id}`
che P3 propagherà come `source{}` (X6).

### P2 — QUEUE & ORCHESTRATOR  → modulo `backend/intake/worker.py` + `backend/intake/queue.py`

| Componente | Azione | Provenienza esatta |
|---|---|---|
| Motore coda (dequeue SKIP LOCKED + lease + heartbeat + retry) | **FORKA** | `services/workflow/queue.py:62-214` (template quasi perfetto: `_dequeue_one` SKIP LOCKED, `_heartbeat` 120s, `_fail_job` retry MAX=3→backoff, `run_worker`). Rinomina `workflow_jobs`→`intake_queue`, adatta colonne a §2. |
| Semantica lease/DLQ/visibility-timeout | **COPIA pattern** | **raquel** (05e, Apache-2.0): claimed/`claimed_at+1min` reclaim, backoff `base*2^attempt`, terminal `exhausted`/`expired`. Traduce 1:1 in asyncpg. SQL dequeue polished da **pgqueuer** (05e, MIT, `queries.py`). |
| DLQ vero (move-on-fail) | **NUOVO** (~40 righe) | NON esiste a row-level nel repo (05a §1d). `attempts>=max OR PoisonPill → status='dead'` + `last_error` + alert Telegram. Riga NON cancellata (ispezionabile, ri-attivabile). |
| Claim atomico C2 | **FORKA** | SQL §3.1 di 04-2 (`WITH next AS (SELECT ... FOR UPDATE SKIP LOCKED LIMIT N) UPDATE ... SET status='processing', lease_expires_at=now()+'300s', attempts=attempts+1`). |
| Resume per-stadio + idempotency-key per-stadio | **NUOVO** | `stage_output[sha256(intake_key\|stage)]` (X7). Crash a metà → riprende dallo stadio non fatto. §3.2 di 04-2. |
| LaunchAgent `com.balizero.intake-worker` (anti-W61) | **NUOVO** (plist) | `KeepAlive{SuccessfulExit=false}` + `RunAtLoad` + `ThrottleInterval=30`. 2 processi worker sul Pro (resilienza orizzontale, NON 2 nodi — byte PII restano sul Pro). §4 di 04-2. |
| `mask_pii()` (log/Telegram/last_error) | **NUOVO** | regex NIK(16)/NPWP(16/15)/passport/phone/email → `<NIK>` ecc. C6. §6 di 04-2. |

**Stadi = funzioni deterministiche in-process** (`STAGES=[classify, extract, validate, route]`),
NON agenti dialoganti (verdetto panel unanime + NB 05c "17.2× error amplification su peer-to-peer").

### P3 — CLASSIFY → EXTRACT → VALIDATE  → modulo `backend/intake/stages/`

| Stadio/Componente | Azione | Provenienza esatta |
|---|---|---|
| **Pre-processing immagine** `preprocess.py` (grayscale/CLAHE/deskew/denoise/upscale300/binarize-cond.) | **NUOVO** (~40 LOC) + **INSTALLA** | recipe OpenCV+scikit-image (05b §1: nessuna lib all-in-one matura). `pip install opencv-python-headless scikit-image`. Porta OCR ~70%→92%. |
| **PDF→immagine** | **FORKA/RIUSA** | **PyMuPDF (`fitz`)** GIÀ in `core/parsers.py:264-376` (`page.get_pixmap()`). Caveat licenza **AGPL-3.0** ma uso interno Pro (non SaaS pubblico) = accettabile (05b §6). OCR multi-page SEMPRE tutte le pagine (CLAUDE.md §13: direksi pag 2-3 akta). |
| **Docling pre-layer** (akta multi-pagina, tabelle) | **INSTALLA** (opzionale, raccomandato) | **Docling** (05b §2/05d, MIT/Apache-2.0): `pip install docling`, auto-MLX su Apple Silicon, Granite-Docling-258M. Wrappa qwen3-vl per struttura tabelle (94-98%). Local/air-gapped. |
| **[1] CLASSIFY** `classify.py` (OCR + doc-type, qwen3-vl:8b zero-shot+CoT) | **FORKA strict-local** | Estrai SOLO **Attempt-1 Ollama** da `_gemini_ocr` (`crm_enhanced.py:88-123`); **DROP tier 2-3 Gemini** (cloud, vietato PII). Refactor su `llm/ollama_client.py:ollama_chat` con `think:False` + nuovo kwarg `images=` (05a §3, risolve golden-rule #10). Tier-1 keyword router **RIUSA** `ocr_dispatcher_service.py:170-308`. Fallback OCR locale: pdfminer→tesseract(ind+eng) **RIUSA** `crm_guardian/ocr.py`. MAI Gemini → fail = DLQ. |
| Gate confidence classify per-tipo (C3) | **SOSTITUISCI** | Abbandona doc-level flat 0.70/0.60 (`dispatcher._CONTENT_CONFIDENCE_THRESHOLD`). Soglie per-tipo: passport/kitas/npwp/nib **0.85**, akta/sk/oss 0.75, ktp 0.80, unknown→sempre HITL. |
| `classify_rationale` PII-stripped (C6) | **NUOVO** | Persisti solo `{decision, signals[], model, version, ocr_text_hash}` — MAI CoT grezzo (contiene PII). NB 05c §4 anti-pattern "tool output hallucination". |
| **[2] EXTRACT** `extract.py` (campi canonici per-tipo, confidence per-campo) | **NUOVO** + **INSTALLA** | Modello `get_role("intake_extraction")` = **SEA-LION-v4-32B** (già pullato Pro). Schema-driven per-tipo (schemi da 02b §2). **"Maybe pattern" (mai inventare)**: **COPIA** da **instructor** (05e, MIT, `dsl/maybe.py` escape-hatch) + retry-loop da **ollama-instructor** (05e, MIT, validate+reask Pydantic, `think:false`). `pip install instructor ollama-instructor`. Regola d'oro: campo illeggibile → `value:null, confidence:0.0, flag:"not_found"`. |
| confidence per-campo = model self-conf × format-prior (C3) | **NUOVO** | accoppia EXTRACT↔VALIDATE: NIB 12 cifre = low-conf-per-format-mismatch, non alta-conf-con-errore. |
| **[3a] VALIDATE-SCRIPT** `validate_rules.py` (deterministico) | **NUOVO** | **NB 05c correzione**: validate è SPEZZATO. Parte deterministica = regole pure (regex/numeri/date), zero LLM, auditabile. Tabella regole 04-3 §3.1 (NIB `^\d{13}$`, NPWP `^\d{16}$`/15-legacy, NIK 16, passport ≥6 mesi, KITAS E-codes {E23,E28A-D,E33E-G}, KITAS≤passport, modal_disetor≥2,5mld, KBLI 5 cifre). |
| **[3b] VALIDATE-AGENT** (normativo, solo akta/nib) | **FORKA/RIUSA** | **NB 05c**: check normativi (KBLI PMA-eligibility, modal threshold contestuale) = agente. **RIUSA** `company-docs-consistency-auditor` come plugin post-classify per `akta`/`nib`. Math su numeri de-identificati via DeepSeek (mai identità a cloud). |
| KBLI foreign-ownership **DINAMICA** (no cache statica) | **RIUSA** | query live tabella KBLI canonica (Data Invariant §9: `kode_kbli`,`pma_status`,`kategori_risiko`). Status non in tabella → `warn` + flag `kbli_status_unresolved` + NB-3/NB-6 edge-case query (offline, fuori hot-path). MAI mappa `{73100:"TERBUKA"}` hardcoded. |
| Versioning SK↔PERBAIKAN (C5) | **NUOVO** | link su `(doc_type, client_id, document_number)`, `version_link{relation, validity_state}`, MAI fonde. |
| `source_page`/`confidence` da OCR vero | **ENFORCE** (NB 05c) | validator post-extract verifica che ogni campo abbia `source_page` reale + confidence da OCR call live, mai da context buffer. |

**Contratto output P3→P4** = JSON per-singolo-documento (X5) con blocco `source{}` (X6),
`blob_hash` hex64 (X11), `needs_review_fields[]` (X12), `client_id_hint` (X10). Schema verbatim §5 di 04-3.

### P4 — ENTITY RESOLUTION & ROUTING  → modulo `backend/intake/route/`

| Componente | Azione | Provenienza esatta |
|---|---|---|
| Entity-resolution doc→cliente (multi-signal) | **RIUSA quasi as-is** | `services/wa_copilot/identity_resolver.py:97-320` (phone_e164, lid_map, team_email, trgm fuzzy name). |
| Normalizzazione phone E.164 | **RIUSA** | `normalize_phone_e164` (`services/crm/client_core.py`, lib **phonenumbers** già nel venv). |
| Fuzzy name match | **DECISIONE** | **Default RIUSA pg_trgm** (`similarity()`/`%` SQL, già usato in identity_resolver) — **NON** introdurre rapidfuzz se basta. Se serve scoring pesato esplicito multi-segnale → **INSTALLA rapidfuzz** (05b, MIT, Jaro-Winkler). **Splink** (05b/05e, MIT, DuckDB) **RINVIATO** (riserva per quando il volume cresce; serve blocking+pesi appresi). |
| Strong-keys exact (passport/kitas/npwp/nik/phone) | **NUOVO** (thin) | §3.2 di 04-4. phone = WEAK key (`phone_owner_risk`, mai auto-attach da solo — C4). |
| Decision matrix C4 (AUTO_ATTACH solo ≥1 strong-key + ≥2 segnali + score≥0.92, default LINK_CANDIDATE) | **NUOVO** | §3.4 di 04-4. Jaro-Winkler mai da solo (Wayan/Made omonimi) — bloccato da nationality+birth_date+client_type. |
| Routing proposal payload-ready (D1/D2/interactions/D3) | **NUOVO** | scrive SOLO `document_routing_proposal` (read-only su `clients`). CATEGORY_TO_FOLDER **RIUSA** `services/crm/documents.py:214` (immigration→01/pma→02/tax→03/family→04/other→99). |
| Idempotenza routing | **NUOVO** | `routing_key = intake_key:doc_index` (X7), UNIQUE. |

### P5 — HITL GATE & EVOLVER HOOK  → endpoint + `backend/intake/review.py` + evolver step

| Componente | Azione | Provenienza esatta |
|---|---|---|
| Review-queue stati (estende C2) | **RIUSA** | `...extracted → review_pending → review_claimed → routed\|rejected` (X8). Lease atomico FOR UPDATE SKIP LOCKED (riuso C2). |
| List endpoint `GET /api/crm/intake-review` (RBAC) | **FORKA** | shape di `workspace_inbox.feed` (`app/routers/workspace_inbox.py:42-104`); gate **RIUSA** `verify_client_access` (`app/utils/crm_utils.py:108-160`, admin zero@/antonellosiano@/asya@). |
| Resolve endpoint `POST /api/crm/intake-review/{id}/resolve` (UNICO writer) | **NUOVO** | (1) scrive `intake_corrections`, (2) trigger routing P4 con `final_fields`, (3) avanza `routed`/`rejected`. Idempotente su queue_id. |
| CRM web view `(workspace)/intake-review` (editor per-campo) | **NUOVO** (frontend) + **COPIA pattern UI** | `apps/mouth`, precedent `(workspace)/inbox`. UI human-review side-by-side: **COPIA** da **paperless-gpt** (05d, MIT, `web-app/` React: AI vs dati editabili, batch, confidence-driven). |
| Telegram = **notifier pull-not-push** (NB 05c) | **NUOVO** (thin) | deep-link `kita.balizero.com/intake-review/<id>` + soli nomi-campo incerti (NO PII). MAI editor, MAI valori PII in chat (Law 2/B2). Approve-secco binario solo item senza PII. |
| HITL state-machine + adversarial-gate pre-HITL | **COPIA pattern** | NB 05c §1.2: `drafted→[adversarial_gate]→needs_human_edit\|reviewed`, max_retry=2, `ignored` NON è segnale. Schema da WR2 queue. |
| Evolver hook `intake-corrections-digest` | **FORKA** (1 step) | aggiungi step al context-gathering di `scripts/agent-library-evolver-run.sh` (riga 251-253). Volume-gated (≥30 corr/sett, no-op sotto soglia). Digest PII-redatto. Riusa gate evidence-lint+entailment+draft-PR esistente (riga 468/538). PROPONE→PR, mai auto-apply. |

---

## 4. BUILD PLAN A FASI (incrementali, ognuna deployabile/testabile da sola)

> Ordine = sblocca prima il valore più grande (chiude gli 8.355 WA unconsumed) con il
> rischio più basso, poi allarga. Ogni fase ha un kill-switch e gira sotto worktree
> (`scripts/agent_start.py --lane intake-fX`).

### FASE 0 — Debiti build (prerequisiti, ~mezza giornata)
- **Cosa**: `ollama pull qwen3-vl:8b` (verificato ASSENTE Pro 2026-06-04, solo qwen2.5vl:7b presente — fallback transitorio sicuro qwen2.5vl). Confermare `aisingapore/Qwen-SEA-LION-v4-32B-IT:q4_k_m` (verificato PRESENTE 19GB, ma SSH `ollama list` env-minimal ha restituito vuoto → ri-verificare con `bash -lc 'ollama list'`). `pip install opencv-python-headless scikit-image ImageHash xxhash instructor ollama-instructor docling` (+ rapidfuzz/splink solo se §3-P4 lo richiede). Aggiungi roles a `MODEL_TOPOLOGY.json`: `ocr_vision: qwen3-vl:8b`, `intake_extraction: aisingapore/Qwen-SEA-LION-v4-32B-IT:q4_k_m`.
- **Fonti**: 05b §6, 04-3 §6, 05e.
- **Test**: `bash -lc 'ollama list | grep -E "qwen3-vl|sea-lion"'` exit 0; `python -c "import cv2, imagehash, instructor, docling"`; `get_role("ocr_vision")` ritorna stringa.
- **Rischio**: BASSO. RAM Pro 48GB regge SEA-LION-32B(~19GB)+qwen3-vl(~6-8GB) ma NON in parallelo a freddo → serializzare CLASSIFY→EXTRACT (lo fa già il single-path).

### FASE 1 — Schema + enqueue (migration 206/207, no worker ancora)
- **Cosa**: applica `206_intake_unified.sql` + `207_clients_birth_date_kitas.sql`. Scrivi `enqueue()` + 3 adapter (wa/drive/zoho) che SOLO accodano (no OCR).
- **Fonti**: §2 di questa spec; 04-1 §1-§3; FORKA `drive_poll_service.py`, NUOVO wa/zoho adapter.
- **Test**: migration apply+rollback (Squawk lint PR #306); `wa_intake_adapter` su 10 file reali → 10 righe `intake_queue` status='pending', re-run = 0 nuove (idempotenza `intake_key`); dedup: stesso blob da 2 source = 1 `document_instances`, 2 `intake_queue` se client_id_hint diverso (C1).
- **Rischio**: BASSO. Nessun write a `documents`/`clients`. Kill: non avviare adapter.

### FASE 2 — Worker orchestrator (coda → done, stadi STUB)
- **Cosa**: FORKA `workflow/queue.py` → `intake/worker.py` (claim/lease/heartbeat/retry/DLQ). Stadi = stub passthrough (classify/extract/validate/route ritornano fixture). LaunchAgent anti-W61.
- **Fonti**: §3-P2; FORKA `queue.py:62-214`; pattern raquel/pgqueuer (05e).
- **Test**: 2 worker concorrenti, 100 job → exactly-once (no doppio-claim, SKIP LOCKED); kill -9 di un worker a metà → job ri-claimato in ≤300s, 0 persi; poison-pill → `dead`+alert; `attempts>max`→`dead`. Anti-storm: grep worker per loop interno prima di KeepAlive (verifica scar 2026-05-31).
- **Rischio**: MEDIO (concorrenza). Mitigato da test exactly-once. Kill: `launchctl bootout`.

### FASE 3 — Stadi reali strict-local (classify+extract+validate-script)
- **Cosa**: implementa preprocess.py, classify.py (FORKA Attempt-1 Ollama, DROP Gemini), extract.py (SEA-LION + Maybe-pattern), validate_rules.py (deterministico). NO routing-write ancora (route = stub che scrive solo proposal).
- **Fonti**: §3-P3; FORKA `crm_enhanced.py:88-123`, `ollama_client.py`, `crm_guardian/ocr.py`; COPIA instructor/ollama-instructor; INSTALLA docling.
- **Test**: 20 doc reali (passport/akta/nib/npwp/kitas) → type-confidence corretto; campi con `source_page` reale (NB anti-hallucination); regola d'oro: campo illeggibile = null+0.0 (mai inventato); validate: NIB 12-cifre → fail; KBLI dinamico (query live, no hardcode); **0 byte a Gemini** (grep log `[CROSS-BORDER]` = vuoto).
- **Rischio**: MEDIO (qualità OCR). Mitigato da pre-processing + fallback. Kill: worker stadi stub.

### FASE 4 — Entity-resolution + routing proposal (read-only)
- **Cosa**: route/ con identity_resolver RIUSO + decision-matrix C4 + scrittura `document_routing_proposal`. Ancora NESSUN write a documents/clients/Drive.
- **Fonti**: §3-P4; RIUSA `identity_resolver.py:97-320`, `normalize_phone_e164`, CATEGORY_TO_FOLDER.
- **Test**: passport exact → AUTO_ATTACH (score≥0.92, 2 segnali); solo-phone → LINK_CANDIDATE+`phone_owner_risk` (mai auto); omonimi Wayan Δ≤0.08 → AMBIGUOUS top-N; company docs mai su individui; proposal idempotente su routing_key.
- **Rischio**: MEDIO-ALTO (false-merge). Mitigato: read-only, default LINK_CANDIDATE, tutto passa da HITL. Kill: P5 non esegue.

### FASE 5 — HITL gate + CRM web view + writer (P5 = unico writer GO-LIVE)
- **Cosa**: endpoint `GET/POST intake-review`, view `(workspace)/intake-review`, Telegram notifier pull. Route reale: `resolve` esegue D1/D2/interactions con `final_fields`. Auto-commit ramo sopra-soglia.
- **Fonti**: §3-P5; FORKA `workspace_inbox.feed`, RIUSA `verify_client_access`; COPIA paperless-gpt UI.
- **Test**: item review → team assegnatario lo vede (RBAC), admin vede candidate-non-risolti; resolve scrive `documents`+Drive+`interactions`+`intake_corrections`; idempotente (re-resolve = no-op); Telegram = solo deep-link+nomi-campo (0 PII in chat); auto-commit solo AUTO_ATTACH∧no-review.
- **Rischio**: ALTO (primo write a prod). Mitigato: gate human obbligatorio, post-deploy QA CLAUDE.md §11. Kill: feature-flag su resolve.

### FASE 6 — Evolver hook (volume-gated, opzionale)
- **Cosa**: step `intake-corrections-digest` in `agent-library-evolver-run.sh`. No-op finché <30 corr/sett.
- **Fonti**: §3-P5 evolver; FORKA evolver script.
- **Test**: <30 corr → no-op loggato (anti-hallucination: niente segnale→niente claim); ≥30 → digest PII-redatto entra nel context → draft PR (mai auto-apply).
- **Rischio**: BASSO. Kill: feature-flag, default OFF.

---

## 5. TABELLA LICENZE (vendorabile vs solo-studiare)

| Repo/Lib | Licenza | Uso | Azione consentita |
|---|---|---|---|
| **text-extract-api** (CatchTheTornado) | MIT | blueprint worker async + OCR-strategy + LLM→JSON | **COPIA/adatta** con attribuzione |
| **paperless-gpt** (icereed) | MIT | UI human-review side-by-side (P5 view) | **COPIA** React UI con attribuzione |
| **pgqueuer** (janbjorge) | MIT | dequeue SKIP LOCKED SQL polished | **COPIA** pattern SQL |
| **raquel** (vduseev) | Apache-2.0 | state-machine lease/DLQ/backoff | **COPIA** semantica con attribuzione |
| **pg-queue** (mattbillenstein) | MIT | reference 1-file worker | **STUDIA**/COPIA |
| **splink** (MoJ) | MIT | entity resolution probabilistica (riserva) | **COPIA/INSTALLA** se serve |
| **instructor** (567-labs) | MIT | Maybe pattern (mai inventare) + reask | **COPIA** `dsl/maybe.py` |
| **ollama-instructor** (lennartpollvogt) | MIT | validate+reask loop Ollama | **COPIA/INSTALLA** |
| **Docling** (IBM/LF AI) | MIT/Apache-2.0 | pre-layer PDF→struttura | **INSTALLA/vendor** |
| **wa-dokumen-extractor-bot** (classyid) | MIT | routing per-tipo + regex NIK/NPWP | **COPIA** regex idea |
| **RapidFuzz** | MIT | scoring fuzzy nomi | **INSTALLA** |
| **ImageHash / xxhash / OpenCV / scikit-image / phonenumbers** | MIT/BSD/Apache | hash + preprocess + phone | **INSTALLA** |
| **PyMuPDF (fitz)** | **AGPL-3.0** | PDF→immagine | **OK uso interno Pro** (non SaaS pubblico). ⚠️ se mai esposto come servizio rete a terzi → rivalutare. Già nel repo. |
| **paperless-ngx** | **GPL-3.0** | consumer/classifier pattern | **STUDIA only** — leggere e re-implementare, MAI vendorare nel backend |
| **sparrow** (katanaml) | **GPL-3.0** | schema-extract+validate pattern | **STUDIA only** — riscrivere l'architettura |
| **singer-tap-template** | **AGPL-3.0** | base-adapter discover/sync | **STUDIA only** — re-implementare l'interfaccia, MAI codice verbatim |
| **ballerine** | AGPL? (verificare) | workflow KYC | **STUDIA only** finché licenza non verificata |
| cluster KTP-OCR (arakattack/YukaLangbuana/…) | no-LICENSE/varie | regex parsing campi | **STUDIA only** — no-LICENSE = all-rights-reserved, MAI copiare |

> **Regola anti-contaminazione**: nessun byte GPL/AGPL entra in `apps/backend-rag/`. Il solo
> AGPL tollerato è PyMuPDF, già presente, per uso interno non-distribuito (decisione 05b).

---

## 6. RISCHI (con mitigazione)

| # | Rischio | Sev | Mitigazione |
|---|---|---|---|
| R1 | **False-merge cliente** (C4): doc attaccato al cliente sbagliato | ALTO | Default LINK_CANDIDATE; AUTO_ATTACH solo ≥1 strong-key+≥2 segnali+score≥0.92; phone mai da solo; tutto sotto-soglia passa da HITL; P4 read-only. |
| R2 | **PII leak a cloud** (Law 2) | ALTO | Fork strict-local (DROP tier Gemini); blob/coda/worker solo su Pro DB locale; grep `[CROSS-BORDER]` in CI; mask_pii su log/Telegram; intake_corrections mai fuori Pro. |
| R3 | **Retry-storm W61** (worker respawn loop) | MEDIO | Daemon loop interno + idle-sleep; `KeepAlive SuccessfulExit=false`; `ThrottleInterval=30`; circuit-breaker DB-down; grep loop interno PRIMA di KeepAlive (scar 2026-05-31). |
| R4 | **Saturazione PG** (causa disable Drive 2026-04-29) | MEDIO | Fan-out OCR rate-limitato dal worker (non dal poll); batching; N worker fissi (non illimitati). |
| R5 | **Tool-output hallucination** in extract (NB 05c) | MEDIO | validator post-extract verifica `source_page` reale + confidence da OCR live; Maybe-pattern (null esplicito). |
| R6 | **Split-brain wa-mirror** locale/Fly | MEDIO | Worker SOLO sul Pro contro `nuzantara_dev` locale (mai Fly). Chiude 8.355 unconsumed. |
| R7 | **Sibling-race worktree** (scar W59/W62/W63) | MEDIO | `scripts/agent_start.py` per ogni fase; verify persistence contro git object store, non intermediate output. |
| R8 | **KBLI status stale** (DNI cambia) | MEDIO | Query live tabella KBLI canonica, mai cache hardcoded; unresolved → warn+NB edge-case offline. |
| R9 | **Drive SPOF Mini-only** | BASSO | Leader-election Pro+Mini + liveness alert su 200-rate; idempotenza `intake_key` come safety-net su double-poll. |
| R10 | **qwen3-vl non warm / RAM** | BASSO | Fallback transitorio qwen2.5vl; serializza CLASSIFY→EXTRACT; keep_alive selettivo. |

---

## 7. SINTESI (12 righe)

1. UN sistema, 5 stadi (P1→P5), 1 orchestratore deterministico (no swarm — panel unanime + NB 17.2×).
2. Tutto LOCALE sul Pro `nuzantara_dev` (Law 2): coda, blob PII, worker, correzioni. Mai Fly/cloud/RAG/NotebookLM.
3. Le 12 contraddizioni X1-X12 chiuse da una tabella canonica: `intake_queue`+`document_instances`, PK BIGSERIAL, `intake_key=sha256(source|source_ref|blob_hash|pipeline_version)`, source `whatsapp|drive|zoho`, pipeline_version `VARCHAR(32)='intake-v1'`, blob_hash hex64, needs_review_fields[].
4. Panel C1-C7 recepiti: dedup composito+pipeline_version (C1), exactly-once SKIP LOCKED+lease+DLQ (C2), HITL per-campo (C3), entity-res link-only default (C4), versioning supersession (C5), no CoT grezzo (C6), verify=firma+diff (C7).
5. NB recepito: validate SPEZZATO (script deterministico + agente normativo akta/nib); HITL pull-not-push (Telegram notifier, non editor); source_page+confidence da OCR vero.
6. ~70% riuso interno: FORKA `workflow/queue.py` (coda), `drive_poll_service.py` (adapter), `crm_enhanced.py:88-123` (OCR Attempt-1), RIUSA `identity_resolver.py`, `verify_client_access`, CATEGORY_TO_FOLDER, `workspace_inbox.feed`.
7. OSS al massimo (licenze rispettate): COPIA raquel+pgqueuer (queue), instructor+ollama-instructor (Maybe/reask), paperless-gpt (review UI), INSTALLA docling+ImageHash+rapidfuzz+opencv.
8. GPL/AGPL solo STUDIA (paperless-ngx, sparrow, singer-template, cluster KTP-OCR): mai vendorare nel backend. Solo PyMuPDF AGPL tollerato (interno).
9. P4 read-only (solo `document_routing_proposal`); P5 unico writer verso documents/Drive/interactions, sempre post-gate.
10. Debiti build: pull qwen3-vl:8b, install lib, migration 206 (verificata libera) + 207 colonne clients.birth_date/kitas_number.
11. Modelli via MODEL_TOPOLOGY.json (`ocr_vision`/`intake_extraction`); anti retry-storm W61 nel plist worker.
12. Build a 7 fasi incrementali, ognuna testabile da sola, rischio crescente: schema→worker→stadi→routing→HITL-write→evolver. Nessun ridisegno — solo unificazione contratti + mapping codice.

---

## BUILD PLAN A FASI (riepilogo compatto)

- **FASE 0 — Debiti**: `ollama pull qwen3-vl:8b`; verifica SEA-LION-32B; `pip install opencv-python-headless scikit-image ImageHash xxhash instructor ollama-instructor docling`; roles in MODEL_TOPOLOGY.json. Test: import+get_role. Rischio BASSO.
- **FASE 1 — Schema+enqueue**: migration 206+207; `enqueue()`+3 adapter (FORKA drive, NUOVO wa/zoho), solo accodano. Test: idempotenza intake_key, dedup C1. Rischio BASSO (no write CRM).
- **FASE 2 — Worker**: FORKA `workflow/queue.py` (claim/lease/heartbeat/retry/DLQ), stadi stub, LaunchAgent anti-W61. Test: exactly-once 2-worker, kill-9 reclaim, poison→dead. Rischio MEDIO.
- **FASE 3 — Stadi reali**: preprocess+classify(FORKA Ollama, DROP Gemini)+extract(SEA-LION+Maybe)+validate-script. Test: source_page reale, regola d'oro null, 0 byte Gemini. Rischio MEDIO.
- **FASE 4 — Entity+routing**: RIUSA identity_resolver + decision-matrix C4 → scrive solo proposal (read-only). Test: AUTO_ATTACH vs LINK_CANDIDATE, omonimi AMBIGUOUS. Rischio MEDIO-ALTO (mitigato read-only).
- **FASE 5 — HITL+writer (GO-LIVE)**: endpoint+CRM view (COPIA paperless-gpt)+Telegram notifier; resolve = unico writer D1/D2/interactions+corrections. Test: RBAC, idempotenza, 0 PII Telegram. Rischio ALTO (primo write prod, gate human obbligatorio).
- **FASE 6 — Evolver**: step intake-corrections-digest volume-gated (≥30/sett), no-op sotto soglia → draft PR. Rischio BASSO.
