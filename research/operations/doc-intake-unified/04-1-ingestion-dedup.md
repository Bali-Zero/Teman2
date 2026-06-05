---
date: 2026-06-04
domain: operations
study: doc-intake-unified
phase: 4.1 — INGESTION & DEDUP
client_case: false
sources:
  - research/operations/doc-intake-unified/01-system-study.md
  - research/operations/doc-intake-unified/02a-external-sota.md
  - research/operations/doc-intake-unified/03-panel-review.md
  - live psql nuzantara_dev + source inspection on Pro (2026-06-04)
recepisce:
  - PANEL C1 (P0) dedup composito
  - PANEL C2 (P0) coda exactly-once
---

# FASE 4 — PARTE 1/5 — Ingestion & Dedup

> Le 3 fonti (WhatsApp wa-mirror, Google Drive poll, Zoho email) convergono su UNA
> coda unica `intake_queue`, sul **Postgres LOCALE del Pro** (`nuzantara_dev`), con dedup
> composito (C1) e claim atomico exactly-once (C2). Questo documento definisce schema SQL,
> i 3 adapter, la logica di dedup e il **contratto-output verbatim** verso PARTE 2.

---

## 0. Decisioni di design vincolanti (da FASE 1-3)

1. **La coda vive sul Pro, DB locale `nuzantara_dev`** — NON Fly. Risolve lo split-brain
   wa-mirror (8.355 eventi locali senza consumer su Fly) e rispetta Symbiosis Law 2: i
   media PII (passaporti, KTP, NPWP) restano sulla macchina di Zero. Il backend Fly NON
   tocca questa coda. Tutti i worker di PARTE 2 girano sul Pro.
2. **Dedup composito (C1)**: NON solo `blob_hash` SHA-256. Chiave = `blob_hash` +
   `normalized_text_hash` + `phash` (immagini) + `pipeline_version`. Uccide i duplicati
   esatti cross-source, MA permette ri-OCR dopo upgrade modello (pipeline_version nella
   chiave) e cattura ri-scansioni/ricompressioni (phash + text_hash) come **near-dup
   linkati**, non scartati ciecamente.
3. **Exactly-once (C2)**: `FOR UPDATE SKIP LOCKED` + lease/visibility-timeout + retry budget
   + dead-state esplicito. Ogni stage idempotente sulla chiave.
4. **Due tabelle, non una**: `intake_queue` (unità di LAVORO, mutabile, stato di pipeline)
   + `document_instances` (registro IMMUTABILE append-only di ogni blob fisico visto, con
   le 3 hash). La coda referenzia l'instance. Questo separa "che lavoro devo fare" da "che
   blob ho già visto" — necessario perché lo STESSO blob può essere legittimo per più
   pratiche/clienti (C1/C2: "stesso byte puo essere legittimo per piu pratiche").

---

## 1. Schema SQL — migration `206_intake_queue_and_instances.sql`

> Estende, NON sostituisce, `whatsapp_message_context.ocr_status`: quella colonna resta
> il segnale di provenienza WhatsApp; l'adapter WA legge da lì e PROIETTA in `intake_queue`.
> Per Drive/Zoho la coda è l'unico landing. Prossimo numero libero verificato = 206.

```sql
-- ============================================================================
-- 206_intake_queue_and_instances.sql
-- Unified document-intake queue + immutable blob registry (LOCAL Pro DB only).
-- Recepisce PANEL C1 (dedup composito) + C2 (exactly-once).
-- ============================================================================

-- ── A. Registro IMMUTABILE dei blob fisici visti (append-only) ──────────────
-- Una riga per (blob fisico × pipeline_version). NON per pratica/cliente:
-- l'attaccamento a client/practice avviene a valle, nella queue/route.
CREATE TABLE IF NOT EXISTS document_instances (
    id                  BIGSERIAL PRIMARY KEY,
    -- Identità composita del CONTENUTO (C1)
    blob_hash           CHAR(64)  NOT NULL,             -- SHA-256 dei byte raw
    normalized_text_hash CHAR(64),                      -- SHA-256 del testo OCR normalizzato (NULL pre-OCR)
    phash               CHAR(16),                        -- perceptual hash (immagini); NULL per PDF puro/testo
    pipeline_version    VARCHAR(32) NOT NULL,            -- es. 'ocr-v3-qwen2.5vl-2026.06'
    -- Metadati fisici del blob
    blob_path           TEXT NOT NULL,                   -- path locale sul Pro (mai URL cloud per PII)
    byte_size           BIGINT,
    mime_type           VARCHAR(100),
    -- Provenienza della PRIMA volta che è stato visto
    first_source        VARCHAR(8) NOT NULL,             -- wa | drive | zoho
    first_source_ref    TEXT,                            -- riferimento opaco lato fonte (vedi adapter)
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_di_source CHECK (first_source IN ('wa','drive','zoho'))
);

-- DEDUP ESATTO cross-source: stesso blob + stessa pipeline = stessa instance.
-- pipeline_version nella UNIQUE => upgrade modello crea una NUOVA instance => ri-OCR permesso.
CREATE UNIQUE INDEX IF NOT EXISTS uq_di_blob_pipeline
    ON document_instances (blob_hash, pipeline_version);

-- NEAR-DUP lookup: ricompressioni/ri-scansioni (blob_hash diverso ma phash/text_hash uguale)
CREATE INDEX IF NOT EXISTS idx_di_phash
    ON document_instances (phash, pipeline_version) WHERE phash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_di_text_hash
    ON document_instances (normalized_text_hash, pipeline_version) WHERE normalized_text_hash IS NOT NULL;


-- ── B. Coda di LAVORO unificata (mutabile, stato pipeline) ──────────────────
CREATE TABLE IF NOT EXISTS intake_queue (
    id                  BIGSERIAL PRIMARY KEY,
    instance_id         BIGINT NOT NULL REFERENCES document_instances(id) ON DELETE RESTRICT,

    -- Provenienza (denormalizzata per query/filtri rapidi)
    source              VARCHAR(8)  NOT NULL,            -- wa | drive | zoho
    source_ref          TEXT        NOT NULL,            -- chiave naturale lato fonte (vedi §2 adapter)

    blob_path           TEXT        NOT NULL,            -- copia del path (immutato durante la vita della riga)
    blob_hash           CHAR(64)    NOT NULL,            -- denormalizzato per dedup-check O(1) all'enqueue
    text_hash           CHAR(64),                        -- popolato post-OCR
    phash               CHAR(16),

    client_id_hint      BIGINT,                          -- risoluzione FONTE (folder/sender/phone); NON autoritativo
    pipeline_version    VARCHAR(32) NOT NULL,

    -- Macchina a stati (C2)
    status              VARCHAR(16) NOT NULL DEFAULT 'pending',
    -- pending -> ocr -> classified -> extracted -> review -> routed -> done | dead | duplicate

    -- Exactly-once / lease (C2)
    locked_by           TEXT,                            -- worker id che ha il claim
    lease_expires_at    TIMESTAMPTZ,                     -- visibility timeout
    attempts            INT NOT NULL DEFAULT 0,
    max_attempts        INT NOT NULL DEFAULT 5,          -- retry budget
    last_error          TEXT,
    dedup_of            BIGINT REFERENCES intake_queue(id), -- se status='duplicate': punta all'originale

    -- Idempotency
    idempotency_key     TEXT NOT NULL,                   -- vedi §3 (source + source_ref + blob_hash + pipeline_version)

    -- Linking near-dup (versioning a valle)
    near_dup_of         BIGINT REFERENCES intake_queue(id),
    near_dup_reason     VARCHAR(16),                     -- 'phash' | 'text_hash'

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_iq_source CHECK (source IN ('wa','drive','zoho')),
    CONSTRAINT chk_iq_status CHECK (status IN
        ('pending','ocr','classified','extracted','review','routed','done','dead','duplicate'))
);

-- Idempotenza all'ENQUEUE: un (source,source_ref,blob_hash,pipeline_version) entra UNA volta.
-- Un retry dell'adapter (stesso file ri-letto) fa ON CONFLICT DO NOTHING.
CREATE UNIQUE INDEX IF NOT EXISTS uq_iq_idempotency
    ON intake_queue (idempotency_key);

-- Claim atomico del worker: SELECT ... WHERE claimabile ... FOR UPDATE SKIP LOCKED
CREATE INDEX IF NOT EXISTS idx_iq_claimable
    ON intake_queue (status, lease_expires_at, created_at)
    WHERE status IN ('pending','ocr','classified','extracted');

-- Dead-letter inspection
CREATE INDEX IF NOT EXISTS idx_iq_dead
    ON intake_queue (status, updated_at) WHERE status = 'dead';

-- Trigger updated_at
CREATE OR REPLACE FUNCTION trg_intake_queue_touch() RETURNS trigger AS $$
BEGIN NEW.updated_at := now(); RETURN NEW; END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS t_intake_queue_touch ON intake_queue;
CREATE TRIGGER t_intake_queue_touch BEFORE UPDATE ON intake_queue
    FOR EACH ROW EXECUTE FUNCTION trg_intake_queue_touch();


-- ── C. Cursori di poll per-source (riusa pattern system_settings di drive_poll) ─
-- drive: già 'drive_poll_page_token' in system_settings (riuso).
-- zoho:  nuovo cursore message-id/last-seen.
-- wa:    nessun cursore (proietta dalla coda ocr_status esistente).
INSERT INTO system_settings (key, value, updated_at)
VALUES ('zoho_intake_cursor', '{}', now())
ON CONFLICT (key) DO NOTHING;

-- ROLLBACK
-- DROP TRIGGER IF EXISTS t_intake_queue_touch ON intake_queue;
-- DROP FUNCTION IF EXISTS trg_intake_queue_touch();
-- DROP TABLE IF EXISTS intake_queue;
-- DROP TABLE IF EXISTS document_instances;
-- DELETE FROM system_settings WHERE key = 'zoho_intake_cursor';
```

**Perché NON estendere solo `whatsapp_message_context.ocr_status`**: quella colonna è
mono-fonte (WhatsApp) e accoppiata al modello dati dei messaggi. Drive/Zoho non hanno una
riga `whatsapp_message_context`. Una coda unica trasversale richiede una tabella propria.
La colonna `ocr_status` resta come **segnale di provenienza WA** che l'adapter WA consuma.

---

## 2. I 3 adapter di ingestione

Ogni adapter ha UN solo compito: **normalizzare un item-fonte in una riga `intake_queue`**
(via la procedura `enqueue()` di §3). NON fanno OCR, NON toccano il CRM. Girano TUTTI sul Pro.

### 2a. Adapter WhatsApp — `wa_intake_adapter.py` (consumer locale, NO poll cloud)
- **Sorgente di verità**: la coda `ocr_status` GIÀ esistente su `whatsapp_message_context`.
- **Query di pickup** (riusa l'indice `idx_wmc_ocr_pending`):
  ```sql
  SELECT id, client_id, media_stored_path, media_mime, media_type, baileys_message_id
  FROM whatsapp_message_context
  WHERE ocr_status = 'pending'
    AND media_stored_path IS NOT NULL
    AND media_type IN ('document','image')
  ORDER BY id
  LIMIT :batch FOR UPDATE SKIP LOCKED;
  ```
- **Normalizzazione**: per ogni riga legge il FILE su disco
  (`/Users/nuzantara/wa-mirror-media/<phone>/...`), calcola le hash (§3), chiama `enqueue()`.
  - `source='wa'`
  - `source_ref = 'wmc:' || id` (la PK di whatsapp_message_context; stabile, unica)
  - `client_id_hint = client_id` (già risolto dal CRM, 1.282 righe)
  - `blob_path = media_stored_path`
- **Post-enqueue**: porta `whatsapp_message_context.ocr_status` da `pending` a `enqueued`
  (nuovo valore, entro il limite di 16 char) per evitare ri-pickup. Lo stato OCR REALE vive
  ora in `intake_queue.status`; `wmc.ocr_result` verrà riscritto a valle dal route-stage.
- **Trigger**: poller leggero (LaunchAgent o loop) ogni 30-60s. È il consumer mancante che
  chiude gli 8.355 eventi unconsumed. SPOF noto (C2) -> mitigato da idempotenza: un crash
  ri-fa il pickup senza doppioni (`ON CONFLICT DO NOTHING` sull'idempotency_key).

### 2b. Adapter Drive — `drive_intake_adapter.py` (avvolge `poll_drive_changes`)
- **Riuso**: `drive_poll_service.poll_drive_changes()` già fa Changes API + `page_token`
  incrementale (`system_settings.drive_poll_page_token`) + routing folder->client_id.
- **Cambio chirurgico**: dove oggi chiama `_dispatch_ocr_by_folder(...)` DIRETTAMENTE
  (riga ~245), l'adapter intercetta PRIMA: **scarica il file in locale** sul Pro
  (`/Users/nuzantara/drive-intake-media/<client_id>/<file_id>_<name>`), calcola le hash,
  chiama `enqueue()`. L'OCR non parte più inline: lo farà il worker di PARTE 2 leggendo
  dalla coda. Questo elimina la "saturazione PG" (GAP P1) perché il fan-out OCR è ora
  rate-limitato dal worker, non dal poll.
  - `source='drive'`
  - `source_ref = 'drive:' || file_id` (Drive fileId, stabile)
  - `client_id_hint` = quello risolto dalla folder map (subfolder->client)
  - Mantiene `folder_name`/`document_type` nei `routing_hints` per il Tier-1 routing a valle
    (passati nel contratto-output, §5).
- **Trigger**: re-enable robusto con leader-election Pro+Mini (GAP P1) — un solo nodo
  esegue il poll; l'altro è standby. Liveness alert sul 200-rate.

### 2c. Adapter Zoho — `zoho_intake_adapter.py` (NUOVO, replica il pattern drive_poll)
- **Costruito da zero** sul client REST esistente (`zoho_email_service`, signature
  verificate: `list_emails(user_id, folder_id='inbox', is_unread=...)`,
  `get_attachment(user_id, message_id, attachment_id) -> bytes`).
- **Cursore**: `system_settings.zoho_intake_cursor` (JSON: `{"last_seen_message_id": ...}`),
  analogo del `page_token` di Drive.
- **Flusso**:
  1. `list_emails(user_id=<zoho service account>, folder_id='inbox', is_unread=True)`.
  2. Per ogni mail con `has_attachments`, per ogni allegato: `get_attachment(...) -> bytes`.
  3. Scrive i bytes su disco locale (`/Users/nuzantara/zoho-intake-media/<message_id>/<att>`),
     calcola le hash, chiama `enqueue()`.
  - `source='zoho'`
  - `source_ref = 'zoho:' || message_id || ':' || attachment_id` (dedup allegati, GAP P1 #8)
  - `client_id_hint` = risoluzione `from`-email -> `clients` (il CRM riconcilia email,
    mig 166). Non risolto -> `client_id_hint = NULL` (va in quarantena a valle, non qui).
  - `routing_hints.sender_email`, `routing_hints.subject` passati nel contratto per
    entity-resolution a valle (PARTE 2 fa il match robusto; l'adapter NON auto-attacca — C4).
  4. Avanza il cursore + (opzionale) `mark_read`.
- **Idempotenza** (GAP P1 #8): l'idempotency_key include `message_id+attachment_id`, quindi
  un re-poll della stessa mail non crea doppioni.
- **Trigger**: poll schedulato (cron/LaunchAgent) ogni 5-10 min, stesso pattern di Drive.

> NOTA path: i 3 media-dir (`wa-mirror-media`, `drive-intake-media`, `zoho-intake-media`)
> sono tutti LOCALI al Pro. Nessun blob PII lascia la macchina (Law 2 / UU-PDP).

---

## 3. Dedup logic — "già visto" vs "nuovo" vs "nuova versione"

Calcolo hash (eseguito dall'adapter prima di `enqueue`):
- `blob_hash`   = `sha256(file_bytes)`.
- `phash`       = perceptual hash (es. `imagehash.phash`, 64-bit->16 hex) SOLO se immagine
  (mime `image/*`); per PDF -> render prima pagina opzionale, altrimenti NULL.
- `text_hash`   = **NULL all'enqueue** (non c'è ancora OCR); popolato dal worker OCR di
  PARTE 2 = `sha256(normalize(ocr_text))` dove `normalize` = lowercase + collapse-whitespace
  + strip-punteggiatura. È il segnale per i near-dup post-OCR.
- `pipeline_version` = costante corrente da `MODEL_TOPOLOGY.json` (es. `ocr-v3-qwen2.5vl-2026.06`).

**`idempotency_key` = `f"{source}|{source_ref}|{blob_hash}|{pipeline_version}"`**.

Procedura `enqueue(adapter_row)` (transazione singola sul DB locale):

```
1. UPSERT in document_instances ON CONFLICT (blob_hash, pipeline_version) DO NOTHING
   RETURNING id  -> instance_id  (se conflict, SELECT l'esistente).
       => Questo è il punto di dedup ESATTO cross-source:
          stesso PDF da WhatsApp E da email con stessa pipeline_version
          => stessa instance_id, NON ri-OCR.

2. Decisione di stato per la nuova riga intake_queue:
   a) "GIÀ VISTO" (duplicato esatto):
        esiste già una intake_queue con stesso blob_hash + pipeline_version
        E stesso client_id_hint (o client_id_hint entrambi NULL)
        => INSERT con status='duplicate', dedup_of=<id originale>.  NON ri-processa.
        (Se client_id_hint DIVERSO: NON è duplicato — stesso blob legittimo per
         due pratiche/clienti, C1. INSERT status='pending' normale.)
   b) "NUOVA VERSIONE" (near-dup): blob_hash DIVERSO ma
        phash uguale (immagine ricompressa/ri-scansionata)  OPPURE
        text_hash uguale (dopo OCR, contenuto identico)
        => INSERT status='pending' MA con near_dup_of=<id> +
           near_dup_reason='phash'|'text_hash'.
           Il worker la processa, ma il route-stage la LINKA come versione
           (layer versioning SK<->PERBAIKAN, gestito in PARTE 2/3), non la fonde.
   c) "NUOVO": nessun match => INSERT status='pending'.

3. INSERT intake_queue (...) ON CONFLICT (idempotency_key) DO NOTHING.
   => Un retry dell'adapter sullo stesso item è no-op idempotente.
```

Matrice decisionale:

| Confronto col registro | blob_hash | text_hash/phash | client_id_hint | Esito |
|---|---|---|---|---|
| Nessun match | nuovo | — | — | **NUOVO** -> pending |
| Esatto, stesso cliente | uguale | uguale | uguale | **GIÀ VISTO** -> duplicate (scartato) |
| Esatto, cliente diverso | uguale | uguale | diverso | **NUOVO** (multi-pratica legittimo) -> pending |
| Ricompresso/ri-scansionato | diverso | phash uguale | qualsiasi | **NUOVA VERSIONE** -> pending + near_dup_of |
| Stesso contenuto, file diverso | diverso | text_hash uguale (post-OCR) | qualsiasi | **NUOVA VERSIONE** -> pending + near_dup_of |
| Stesso blob, pipeline aggiornata | uguale | — | qualsiasi | **NUOVO** (ri-OCR permesso) -> pending |

Il **ri-OCR dopo upgrade modello** è garantito perché `pipeline_version` è nella UNIQUE di
`document_instances` e nell'`idempotency_key`: bump della versione => nuova instance => nuova
riga coda => riprocessamento, senza scarto silenzioso (fix esplicito al rischio C1 "doc in
stato dead con stesso hash scartato in silenzio").

---

## 4. Risoluzione SPLIT-BRAIN — dove vive la coda

**La coda vive sul Postgres LOCALE del Pro (`127.0.0.1:5432/nuzantara_dev`), MAI su Fly.**

Motivazioni (convergenti FASE 1 §5.1 + Law 2):
- I blob sono PII (passaporti, KTP, NPWP) — non possono lasciare il Pro.
- wa-mirror scrive ed emette eventi sul DB locale; gli 8.355 unconsumed esistono PERCHÉ
  l'handler girava su Fly. Mettere coda+worker sul Pro CHIUDE il loop senza violare Law 2.
- Drive/Zoho: gli adapter scaricano i blob in locale e accodano in locale. Il backend Fly
  non vede né i blob né la coda.

Conseguenza per PARTE 2: **tutti i worker (OCR/classify/extract/route) girano sul Pro**,
contro `nuzantara_dev`. L'unico ponte verso Fly è il route-stage finale, che scrive le
righe STRUTTURATE non-PII (riferimenti, document_type, expiry) verso `documents`/`clients`
DOPO il gate human-verify — quello è progetto di PARTE 4/5, non di qui.

Leader-election (Drive/Zoho poll su Pro+Mini): un solo nodo esegue il poll per evitare
double-enqueue; ma anche in caso di doppio poll, l'`idempotency_key` rende l'enqueue
idempotente — la leader-election è ottimizzazione, l'idempotenza è la safety net.

---

## 5. CONTRATTO DI OUTPUT verso PARTE 2 (verbatim)

Ogni adapter, per ogni blob normalizzato, produce **una riga `intake_queue`** e (per i
consumatori event-driven) emette **un evento `intake.enqueued`**. La forma canonica della
unità di lavoro che la queue/orchestrator di PARTE 2 consuma è il JSON seguente. Questo è
il contratto: PARTE 2 NON deve leggere wa-mirror/Drive/Zoho direttamente.

```json
{
  "contract": "doc-intake/intake-item",
  "contract_version": "1.0",
  "queue_id": 84213,
  "instance_id": 51199,
  "idempotency_key": "zoho|zoho:18f3a2b9c4d:att-2|9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08|ocr-v3-qwen2.5vl-2026.06",
  "source": "zoho",
  "source_ref": "zoho:18f3a2b9c4d:att-2",
  "blob": {
    "path": "/Users/nuzantara/zoho-intake-media/18f3a2b9c4d/passport_scan.pdf",
    "blob_hash": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
    "text_hash": null,
    "phash": null,
    "byte_size": 482113,
    "mime_type": "application/pdf"
  },
  "pipeline_version": "ocr-v3-qwen2.5vl-2026.06",
  "status": "pending",
  "client_id_hint": 1042,
  "dedup": {
    "is_duplicate": false,
    "dedup_of": null,
    "near_dup_of": null,
    "near_dup_reason": null
  },
  "routing_hints": {
    "folder_name": null,
    "document_type": null,
    "sender_email": "wayan.surya@gmail.com",
    "subject": "Passport for KITAS renewal",
    "wa_message_id": null,
    "drive_file_id": null
  },
  "attempts": 0,
  "max_attempts": 5,
  "created_at": "2026-06-04T11:42:07.512Z"
}
```

Regole del contratto (vincolanti per PARTE 2):
- **`queue_id`** è l'unità di claim. PARTE 2 fa:
  ```sql
  UPDATE intake_queue SET status='ocr', locked_by=:w,
         lease_expires_at=now()+interval '10 min', attempts=attempts+1
  WHERE id IN (
      SELECT id FROM intake_queue
      WHERE status='pending'
        AND (lease_expires_at IS NULL OR lease_expires_at < now())
        AND attempts < max_attempts
      ORDER BY created_at
      FOR UPDATE SKIP LOCKED LIMIT :n)
  RETURNING ...;
  ```
- **`client_id_hint`** è SOLO un suggerimento di fonte. PARTE 2/3 fa la entity-resolution
  robusta (C4: default link-candidate, mai auto-attach). Mai trattarlo come autoritativo.
- **`text_hash`/`phash`**: `phash` arriva già valorizzato per le immagini; `text_hash` è
  NULL all'ingestione — PARTE 2 lo POPOLA dopo l'OCR (`sha256(normalize(text))`) e
  ri-controlla i near-dup prima di route.
- **`dedup.is_duplicate=true`** => la riga è già in stato `duplicate`, PARTE 2 la salta.
- **`routing_hints`** alimentano il Tier-1 keyword routing riusato da `dispatch_ocr_by_folder`
  (folder_name/document_type per Drive; sender/subject per Zoho; wa_message_id per WA).
- **`pipeline_version`** deve essere propagato invariato attraverso tutti gli stage; un suo
  cambio implica una NUOVA instance (ri-OCR), mai una mutazione in-place.

Evento di notifica (opzionale, per consumer push invece di poll):

```json
{ "event": "intake.enqueued", "queue_id": 84213, "source": "zoho", "blob_hash": "9f86d081...", "pipeline_version": "ocr-v3-qwen2.5vl-2026.06", "ts": "2026-06-04T11:42:07.512Z" }
```

---

## 6. Cosa NON è in scope di PARTE 1 (handoff esplicito)

- OCR/classify/extract/validate/route stages -> **PARTE 2**.
- Entity-resolution robusta (C4), versioning SK<->PERBAIKAN (C5), HITL per-campo (C3),
  PII-masking nei sottoprodotti (C6), definizione di `verify` (C7) -> **PARTE 2/3/4**.
- Scrittura su `documents`/`clients` post-verify + Drive ordinato -> **PARTE 4/5**.

PARTE 1 garantisce: le 3 fonti convergono, ogni blob è registrato una sola volta per
pipeline_version, i duplicati esatti cross-source sono uccisi, i near-dup sono linkati non
fusi, il ri-OCR post-upgrade è permesso, e la coda è claimabile exactly-once sul Pro.
