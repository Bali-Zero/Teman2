---
date: 2026-06-04
domain: operations
study: doc-intake-unified
phase: 1 (source mapping)
source: WHATSAPP (wa-mirror)
client_case: false
sources:
  - apps/wa-mirror/bridge/media.ts
  - apps/wa-mirror/bridge/message_capture.ts
  - apps/wa-mirror/bridge/events.ts
  - apps/wa-mirror/bridge/session.ts
  - apps/backend-rag/backend/db/migrations_v2/177_wa_mirror_message_capture_columns.sql
  - apps/backend-rag/backend/db/migrations_v2/185_wa_mirror_v2_lid_session_history_ocr.sql
  - apps/backend-rag/backend/services/events/handlers/_core.py
  - live psql nuzantara_dev (2026-06-04)
---

# FASE 1 — Fonte WHATSAPP: come entrano i documenti cliente

> Mappatura empirica (grep/Read/ls/psql su Pro, NON a memoria). Tutti i numeri
> sono query live al DB locale `nuzantara_dev` del 2026-06-04.

## TL;DR

WhatsApp riceve **già** foto e PDF dei clienti, li scarica su disco e ne registra
i metadati in Postgres. La pipeline si ferma lì: **0 documenti su 24.081 messaggi
sono mai stati processati (OCR/intake)**. Esiste lo scaffolding completo per
l'aggancio (colonna coda `ocr_status='pending'`, canale EventBus
`whatsapp_message_received`) ma **manca il worker che consuma**. È il punto di
innesto ideale per un document-intake automatico.

---

## 1. Architettura wa-mirror

- **Cos'è**: bridge TypeScript/Node basato su Baileys (`@whiskeysockets/baileys`),
  multi-device WhatsApp. NON è codice Python del backend-rag.
- **Dove gira**: Pro, daemon Node live (`ps`: PID 82133 `node dist/bridge/index.js`).
  LaunchAgent `com.balizero.wa-mirror-launcher` (PID 47278). Wrapper
  `apps/wa-mirror/scripts/run-wa-mirror.sh` → `dist/bridge/index.js`.
- **Su quale DB scrive**: **Postgres LOCALE** `postgresql://nuzantara@localhost:5432/nuzantara_dev`
  (verificato in `~/.wa-mirror.env` → `WA_MIRROR_DATABASE_URL`). NON Fly. Conferma
  la cutover OSINT Law 2 (sovranità WhatsApp locale).
- **Connessione**: `apps/wa-mirror/bridge/pg.ts:18-46` — pool `pg`, `application_name='wa-mirror'`.

### Tabella principale: `whatsapp_message_context`

Schema reale (da `message_capture.ts:166-210` INSERT + migrazioni 177/185):

| Colonna | Significato (per doc-intake) |
|---|---|
| `id` (bigint PK) | usato come `message_context_id` nell'evento |
| `media_type` | `text\|image\|document\|audio\|video\|sticker\|location` |
| `media_mime` | es. `image/jpeg`, `application/pdf` |
| `media_url` | URL/directPath Baileys (NON il file, riferimento Meta) |
| **`media_stored_path`** | **path assoluto del file scaricato su disco** (NULL finché download non finisce) |
| **`ocr_result`** (JSONB) | risultato OCR strutturato — **sempre NULL oggi** |
| **`ocr_status`** (varchar16, default `pending`) | **coda worker OCR** — mig 185 |
| `ocr_engine`, `ocr_completed_at` | metadati worker (mai valorizzati) |
| `body` / `message_text` | testo o caption del media |
| `client_id`, `practice_id` | join CRM risolto inline (per phone/LID) |
| `raw_baileys_event` (JSONB) | payload Baileys completo |

Indice coda OCR (mig 185): `idx_wmc_ocr_pending` su
`WHERE ocr_status='pending' AND media_stored_path IS NOT NULL` — progettato per un
worker `SELECT ... FOR UPDATE SKIP LOCKED` **che non esiste**.

---

## 2. DOVE finiscono i media (foto/PDF)

Flusso file binario — `apps/wa-mirror/bridge/media.ts`:

1. Su ogni messaggio media (non-text/location), `queueMediaDownload()` parte
   **async** via `setImmediate` (`media.ts:39`), DOPO la persistenza della riga.
2. `downloadAndStoreMedia()` (`media.ts:54`): `downloadMediaMessage()` Baileys →
   buffer → scrive su **filesystem**.
3. **Path su disco** (`media.ts:78-86`):
   `${WA_MIRROR_MEDIA_ROOT}/<segment>/<baileysMessageId>.<ext>`
   - root reale: **`/Users/nuzantara/wa-mirror-media`**
   - `<segment>` = telefono cliente (direct) o `groups/<groupJid>` (gruppo)
   - estensione da MIME: `application/pdf→pdf`, `image/jpeg→jpg`, `document→bin` fallback
4. Dopo la scrittura: `updateMediaStoredPath(id, filePath, ocrResult)`
   (`media.ts:88`) scrive `media_stored_path` nella riga.

→ **I media NON sono in colonna bytea né solo riferimento Meta: sono FILE REALI su
disco del Pro.** La colonna `media_url` è solo il riferimento Baileys/Meta;
`media_stored_path` è il file scaricato.

### OCR inline: cablato ma DISATTIVO

`media.ts:120-180`: dopo il download, `maybeRunOcr()` POSTerebbe il file a un
endpoint backend `POST /api/ocr/extract` (`{file_path}`), SE l'endpoint esiste.
`scanRoutersForOcrEndpoint()` fa grep nei router Python per `/api/ocr/extract`.

**Empirico: quell'endpoint NON esiste.** I router OCR presenti
(`crm_enhanced.py`, `crm_enhanced_documents.py`) sono per il flusso CRM/Drive
(Gemini OCR su tabella `documents`), non espongono `/api/ocr/extract`. Quindi
`hasOcrEndpoint()` → false → **OCR inline saltato** ("OCR endpoint not found; skipping").

---

## 3. Trigger esistenti (su cui agganciare l'intake)

### EventBus channel `whatsapp_message_received` — ESISTE

- **Emitter** (`apps/wa-mirror/bridge/events.ts:42` + `session.ts:654`):
  ad ogni messaggio persistito, `emitMessageReceived()` fa
  `INSERT INTO events_outbox(channel='whatsapp_message_received', payload)` +
  `pg_notify('whatsapp_message_received', {..., _outbox_id})`.
  Payload: `{ message_context_id, bridge_session_id, team_member_email,
  client_id, direction, message_date, preview }`.
- **GAP TEMPORALE**: l'evento viene emesso PRIMA del download media
  (`session.ts:654` emit, poi `:666` `queueMediaDownload`). Quindi il payload
  **non contiene `media_stored_path`** (non ancora scritto) e NON segnala "è un doc".
- **Mappatura** (`backend/services/events/event_bus.py:129`):
  `"whatsapp_message_received" → "whatsapp.message_received"`.
- **Handler Python** (`backend/services/events/handlers/_core.py:326-340`):
  `on_whatsapp_message_received()` → fa SOLO `_log_whatsapp_message_interaction`
  (timeline CRM). **Nessun processing di media/documenti.**

### SPLIT-BRAIN consumer (gap critico)

L'handler Python `_core.py` gira nel **backend su Fly**, che ascolta il **DB Fly**.
wa-mirror emette su **DB locale**. Empirico sul DB locale:
`events_outbox.whatsapp_message_received` = **9.999 righe, 8.355 unconsumed**
(max created_at 2026-06-04 01:03). → **Nessun consumer drena la coda locale.**
L'evento esiste ma cade nel vuoto sul nodo dove vivono i file.

### Coda OCR `ocr_status` — ESISTE ma SENZA WORKER

Mig 185 crea coda + indice. I consumatori di `ocr_status='pending'` nel codebase
(`ocr_pipeline_gemma.py`, `crm_enhanced_documents.py`,
`crm_drive_backfill_service.py`) targettano le tabelle `documents`/`company_documents`
(flusso Drive), **mai `whatsapp_message_context`**. `ocr_pipeline_gemma.py` è
parametrizzato `--table` ma con logica company-specific e non schedulato sulla WA.

### Altri consumer wa (NON doc-aware)

`wa_copilot/*` (attention-classifier, team_promises, extraction_pipeline,
identity_resolver) e router leggono `whatsapp_message_context` ma **solo testo /
attention / promesse**. L'unico che tocca i campi media è il router read-only
`wa_mirror_messages.py:110-172` che espone flag `has_ocr`/`has_media` alla
dashboard (`:7790`) — display, non processing.

---

## 4. Volume (DB locale, 2026-06-04)

| Metrica | Valore |
|---|---|
| Messaggi totali | **24.081** |
| Con media (≠ text/location) | **1.596** |
| → immagini | 772 |
| → documenti (PDF/doc) | 629 |
| Media scaricati su disco (`media_stored_path` non NULL) | **1.282** |
| **`ocr_status='pending'`** | **24.081 (100%)** |
| `ocr_status='done'` | **0** |
| `ocr_result` non NULL | **0** |

File su disco `/Users/nuzantara/wa-mirror-media`: **1.612 file, 715 MB**, di cui
**578 PDF**. (Disco > DB-stored-path: alcuni file scritti ma update riga
fallito/async, oppure pre-migrazione colonna.)

→ **1.207 documenti totali (629 doc + 578 PDF su disco) in attesa, ZERO processati.**

---

## 5. GAP: cosa manca per "wa-mirror riceve doc → agente lo processa auto"

Tutto lo scaffolding c'è. Mancano 3 anelli:

1. **Consumer locale dell'EventBus** (P0). Nessun processo drena
   `events_outbox.whatsapp_message_received` sul DB locale (8.355 unconsumed). Serve
   un listener Node/Python sul Pro (il backend Fly NON vede questo DB).

2. **Trigger sul MEDIA, non sul messaggio** (P0). L'evento attuale parte prima del
   download e non dice "è un documento". Serve O un secondo evento dopo
   `updateMediaStoredPath` (quando `media_stored_path` è scritto e si conosce il
   `media_type`), O un poller sulla coda `ocr_status='pending' AND
   media_stored_path IS NOT NULL AND media_type IN ('document','image')`.

3. **Worker OCR/intake per WhatsApp** (P0). La coda `ocr_status` non ha worker
   wired su `whatsapp_message_context`. Opzioni: (a) implementare l'endpoint
   `POST /api/ocr/extract` che `media.ts` già chiamerebbe (sblocca OCR inline a
   costo zero di re-architettura); (b) adattare `ocr_pipeline_gemma.py
   --table whatsapp_message_context`; (c) nuovo worker che legge la coda,
   chiama vision (`qwen2.5vl:7b` locale per Law 2, o Gemini), scrive `ocr_result` +
   `ocr_status='done'`, e instrada al CRM via `client_id` già risolto sulla riga.

### Punto di innesto consigliato

La coda `ocr_status='pending' + media_stored_path NOT NULL` (indice
`idx_wmc_ocr_pending` già pronto) è l'aggancio più pulito: idempotente, già
indicizzato, già popolato da 1.282 righe con file su disco e `client_id`
pre-risolto. Un worker `SELECT ... FOR UPDATE SKIP LOCKED` su quella coda è
esattamente ciò per cui la mig 185 è stata scritta — e mai completata.

### Note di sovranità

I file e il DB vivono SOLO sul Pro (Law 2). Qualsiasi intake deve restare locale
(vision locale `qwen2.5vl:7b`) o usare cloud solo se esplicitamente sancito. Non
replicare i media su Fly/Drive senza decisione operatore.
