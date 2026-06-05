---
date: 2026-06-04
domain: operations
study: doc-intake-unified
phase: 1 — SYNTHESIS (consolidates 01a/01b/01c/01d)
client_case: false
sources:
  - research/operations/doc-intake-unified/01a-whatsapp-source.md
  - research/operations/doc-intake-unified/01b-drive-zoho-sources.md
  - research/operations/doc-intake-unified/01c-processing-pipeline.md
  - research/operations/doc-intake-unified/01d-destinations.md
  - live psql nuzantara_dev + grep/Read/ls on Pro (2026-06-04)
---

# FASE 1 — Document-Intake Unified: System Study (synthesis)

> Sintesi dei 4 report di mappatura empirica (sorgenti + pipeline + destinazioni).
> Tutti i numeri sono query live al DB locale `nuzantara_dev` del 2026-06-04, non a
> memoria. Questo è il dossier di pianificazione per la FASE 2 (design + build).

## TL;DR

I documenti cliente entrano già da **3 fonti** (WhatsApp, Google Drive, Zoho) con
maturità molto diversa. Esiste **una pipeline OCR→classify→extract→CRM completa e in
produzione**, ancorata su `dispatch_ocr_by_folder`, ma è **cloud-tainted** (fallback
Gemini su immagini PII = superficie di leak UU-PDP) e oggi **serve solo il flusso
Drive/portal/upload**. WhatsApp ha tutto lo scaffolding (file su disco, coda
`ocr_status='pending'`, evento EventBus) ma **0 worker**: 1.207+ documenti fermi, 0
processati. Zoho legge le mail + scarica allegati ma **non li ingerisce**. Il punto di
convergenza naturale già esiste in codice: **`dispatch_ocr_by_folder` è
source-agnostic** e la coda `ocr_status` è il landing comune — manca una variante
**strict-local** (senza tier Gemini) e un **trigger di ingest** per WhatsApp/Zoho.

---

## 1. Architettura ATTUALE (cosa esiste e funziona)

### Fonte A — WHATSAPP (wa-mirror)  · stato: RICEVE, NON PROCESSA
- Bridge TypeScript/Baileys (`apps/wa-mirror/`), daemon Node live sul **Pro**
  (LaunchAgent `com.balizero.wa-mirror-launcher`).
- Scrive su **Postgres LOCALE** `nuzantara_dev` (NON Fly — sovranità Law 2).
- Foto/PDF scaricati come **FILE REALI** su `/Users/nuzantara/wa-mirror-media/<phone>/`,
  path scritto in `whatsapp_message_context.media_stored_path`.
- Esiste la **coda OCR**: colonna `ocr_status` (default `pending`, mig 185) + indice
  `idx_wmc_ocr_pending` (`WHERE ocr_status='pending' AND media_stored_path NOT NULL`),
  progettato per un worker `SELECT … FOR UPDATE SKIP LOCKED` **mai scritto**.
- Esiste l'evento EventBus `whatsapp_message_received` (outbox + pg_notify), ma è
  emesso **PRIMA** del download media → payload senza `media_stored_path`, non dice
  "è un documento". L'handler Python (`_core.py`) logga solo l'interazione CRM.
- OCR inline (`media.ts` → `POST /api/ocr/extract`) è cablato ma **disattivo**:
  l'endpoint `/api/ocr/extract` NON esiste → skip.

### Fonte B — GOOGLE DRIVE  · stato: ATTIVO (event-driven, ma Mini-only)
- Pipeline reale di detection nuovi file via **Drive Changes API** con `page_token`
  incrementale (`drive_poll_service.py`), `DriveCircuitBreaker` + alert Telegram.
- Routing folder→client/company (3 lookup map da Postgres) con **self-healing**
  (auto-registra subfolder annidate sconosciute).
- File in subfolder cliente nota → `dispatch_ocr_by_folder` (OCR + estrazione).
  File in root cliente/azienda → enqueue refresh CRM-Guardian (summary semantico).
- Struttura canonica: `00_Profile/01_Immigration/02_Company/03_Tax/04_Family/99_Misc`.
- **Trigger**: scheduler in-process **DISABILITATO** (`autonomous_scheduler.py
  enabled=False`, "moved to Air cron"); job Pro crontab **COMMENTED OUT** (2026-04-29,
  "drive_poll satura PG"). **Vive SOLO sul cron Mini H24** (`*/5`).
- Token health: `drive_token_watchdog.py` ogni 6h (alert 7gg pre-scadenza OAuth 90gg).

### Fonte C — ZOHO EMAIL  · stato: API integrata, NESSUN intake
- Client REST Zoho Mail completo (OAuth): `list_emails`, `get_email`,
  `get_attachment() -> bytes`, send/reply, ecc. (`zoho_email_service.py`, 1236 righe).
- **Nessun poll schedulato, nessun cron, nessun auto-ingest**: gli allegati sono
  serviti alla UI mailbox on-demand, mai instradati a OCR/documents/Drive.
- Brevo è send-only (non è un path di ricezione).

### Pipeline OCR — `dispatch_ocr_by_folder`  · stato: PRODUZIONE, cloud-tainted
- Router centrale (`ocr_dispatcher_service.py`, 399 righe). 2 tier:
  Tier-1 keyword filename/folder (passport/visa/nib/npwp/company_profile — **0 cloud**),
  Tier-2 content classifier (gate confidenza 0.70) che però chiama `_gemini_ocr`.
- Motore OCR condiviso `_gemini_ocr` (`crm_enhanced.py:74`) = cascata 3-tier:
  (1) **Ollama `qwen2.5vl:7b` locale** ✅ → (2) **Gemini CLI** ⚠️ cloud →
  (3) **Gemini API** `gemini-2.5-flash` ⚠️ cloud+paid. Su Ollama down, PII va a Google.
- `crm_guardian/ocr.py`: estrazione testo 100% locale (pdfminer → tesseract ind+eng →
  qwen2.5vl), MA il testo prodotto viene poi spedito a Gemini per il summary L1.
- `PDFVisionService` / `VisionRAGService`: Ollama-first + fallback Gemini (logga
  `[CROSS-BORDER]`). Attivi, ma RAG/parsing — stessa taint.
- Agente `document-intake-classifier` = **SOLO spec markdown**, non wired, nessun
  trigger automatico. La sua spec già impone strict-local (qwen2.5vl only, no cloud).

### Destinazioni — dove finisce un doc classificato  · stato: ESISTONO (D1/D2)
- **D1 CRM Postgres `documents`** (destinazione strutturata primaria): row per-cliente,
  chiave `client_id` (+ `practice_id`/`family_member_id`), `document_type`,
  `document_category`, `expiry_date`, `ocr_status`. Variante azienda `company_documents`.
  Provenienza loggabile in `interactions` (oggi quasi-vuota).
- **D2 Drive ordinato**: file rinominato nella subfolder per-categoria
  (`CATEGORY_TO_FOLDER`: immigration→01, pma→02, tax→03, family→04, other→99),
  `file_id`/`google_drive_file_url` riscritti in D1.
- **D3 `company-docs-consistency-auditor`** = CONSUMER (read-only) della intake JSON.
- **B1 RAG/Qdrant** e **B2 NotebookLM/cloud** = **VIETATI per PII** (firewall).

---

## 2. Tabella componente | stato | locale-o-cloud | riusabile

| Componente | Stato | Locale/Cloud | Riusabile |
|---|---|---|---|
| wa-mirror bridge (download media → disco) | ATTIVO | Locale (Pro) | Sì |
| `whatsapp_message_context` + `ocr_status` coda + indice | ESISTE, senza worker | Locale | Sì (landing intake) |
| EventBus `whatsapp_message_received` | EMESSO, non consumato (locale) | Locale | Parziale (manca media_path) |
| OCR inline `media.ts` → `/api/ocr/extract` | CABLATO, disattivo (endpoint assente) | — | Sì (se si crea endpoint) |
| Drive `drive_poll_service` (Changes API + routing) | ATTIVO | Cloud (Drive API) | Sì |
| Drive trigger (in-proc scheduler) | DISABILITATO | — | No (sostituire) |
| Drive trigger (Pro cron) | COMMENTED OUT | — | No |
| Drive trigger (Mini cron `*/5`) | ATTIVO (SPOF) | Locale (Mini) | Sì, ma fragile |
| Zoho Mail API client (`get_attachment`) | ATTIVO (UI on-demand) | Cloud (Zoho) | Sì |
| Zoho poll/ingest | INESISTENTE | — | Da costruire |
| `dispatch_ocr_by_folder` (router) | PRODUZIONE | Misto | Sì (Tier-1 + struttura) |
| Tier-1 keyword routing | PRODUZIONE | Locale | Sì |
| `_gemini_ocr` Tier-2/3 (cascata Gemini) | PRODUZIONE | CLOUD | **No** (per PII) |
| Ollama `qwen2.5vl:7b` branch | PRODUZIONE | Locale | Sì (unica via PII) |
| pdfminer + tesseract (ind+eng) | PRODUZIONE | Locale | Sì |
| crm_guardian L1 summary step | PRODUZIONE | CLOUD (Gemini) | **No** (per PII) |
| `documents` OCR-status schema (mig 061) | PRODUZIONE | Locale | Sì |
| field→clients/documents writers | PRODUZIONE (auto-write) | Locale | Sì (dietro human-verify) |
| D1 CRM `documents` / D2 Drive ordinato | PRODUZIONE | D1 locale-Fly / D2 cloud | Sì |
| `company-docs-consistency-auditor` | SPEC (proposed) | Locale | Sì (consumer) |
| `document-intake-classifier` agent | SPEC, non wired | Locale | Sì (da implementare) |

---

## 3. I GAP precisi (fonte → OCR locale → CRM/Drive auto)

### WhatsApp
1. **Consumer locale EventBus** (P0): nessun processo drena la coda locale
   (8.355 unconsumed). Il backend Fly NON vede il DB locale → serve listener
   Node/Python sul Pro.
2. **Trigger sul MEDIA, non sul messaggio** (P0): l'evento parte prima del download e
   non segnala "documento". Serve O un 2° evento post-`updateMediaStoredPath`, O un
   poller sulla coda `ocr_status='pending' AND media_stored_path NOT NULL AND
   media_type IN ('document','image')`.
3. **Worker OCR/intake** (P0): la coda `ocr_status` non ha worker su
   `whatsapp_message_context`. Opzioni: (a) implementare `POST /api/ocr/extract` che
   `media.ts` già chiamerebbe; (b) adattare un worker `--table
   whatsapp_message_context`; (c) nuovo worker `FOR UPDATE SKIP LOCKED` → vision
   locale → scrive `ocr_result` + instrada al CRM via `client_id` già risolto.

### Drive
4. **Eliminare la fragilità Air-era** (P1): trigger solo su cron Mini con commento
   stale. Re-enable scheduler Fly-compatibile O cron first-class su Pro+Mini con
   **leader-election** (evitare double-OCR active-active, cf. scar mata_garuda).
   Aggiungere liveness alert sul 200-rate di `/api/admin/drive/poll`.
5. **Guard saturazione PG** (P1): la ragione del disable 2026-04-29 ("drive_poll
   satura PG") è irrisolta alla radice — qualsiasi re-enable richiede
   batching/rate-limit sul fan-out OCR.

### Zoho
6. **Inbound poll service** (P1): replicare `drive_poll_service` —
   `list_emails(inbox, is_unread)` → per ogni con `has_attachments`, `get_attachment()`
   → instradare nello STESSO dispatcher. Read-cursor (message_id) = analogo del
   `page_token`.
7. **Risoluzione sender→client** (P1): mappare `from` a una row `clients` (il CRM
   riconcilia già le email, mig 166). Sender non risolti → coda di quarantena.
8. **Idempotenza** (P1): dedup per (message_id, attachment_id); ledger allegati
   processati.

### Trasversale (tutte le fonti)
9. **Servizio di estrazione strict-local** (P0): il dispatcher + handler ma con i tier
   Gemini **rimossi/disabilitati** (modo `local_only=True` o nuovo `local_ocr_service`
   che chiama solo Ollama/tesseract/pdfminer). È il deliverable chiave.
10. **Auto-create client da doc** (P1): gli handler oggi solo `UPDATE` un cliente
    esistente — un nuovo lead non ha row di atterraggio.
11. **Coda human-review + verify-before-commit** (P1): l'agente disegna la JSON,
    nessuna coda DB-backed esiste.
12. **PII masking in log/Telegram** (P1): speccato ma non enforced (gli handler oggi
    loggano passport number).

---

## 4. PUNTO DI CONVERGENZA

`dispatch_ocr_by_folder` è **già source-agnostic** (Drive/portal/upload/company lo
chiamano tutti) e la coda `ocr_status='pending'` è il **landing comune**. La FASE 2
unifica le 3 fonti su quell'entrypoint, in versione **strict-local** (no tier Gemini
per PII), con la coda come buffer idempotente.

```
   WHATSAPP            DRIVE                 ZOHO
   (wa-mirror)         (Changes API)         (Mail API)
   file su disco       file in subfolder     get_attachment() bytes
       |                    |                      |
       | media_stored_path  | folder→client        | sender→client + subfolder
       v                    v                      v
  +----------------------------------------------------------+
  |   ENQUEUE  →  coda  ocr_status = 'pending'                |
  |   (whatsapp_message_context  +  documents)               |
  +----------------------------------------------------------+
                            |
                            v
        +-------------------------------------------+
        |  dispatch_ocr_by_folder  (SOURCE-AGNOSTIC)|
        |  Tier-1 keyword routing  (locale, riuso)  |
        |  estrazione STRICT-LOCAL:                 |
        |    pdfminer → tesseract → qwen2.5vl:7b    |
        |    (NESSUN tier Gemini — PII firewall)    |
        +-------------------------------------------+
                            |
                            v
              [ structured intake JSON ]
            (contratto verso D3 auditor)
                            |
              +-------------+-------------------+
              v             v                   v
        (D1) CRM PG    (D2) Drive ordinato  (D3) docs-auditor
        documents row  02_Company/03_Tax/.. (consumer R/O)
        client_id      file rinominato +
        + practice_id  file_id → D1
              |
              +-- interactions (provenienza: "doc via WA/email <data>")

        human-verify gate PRIMA di scrivere D1/clients
        BOUNDARY: PII →/→ B1 RAG/Qdrant   →/→ B2 NotebookLM/cloud  (VIETATO)
```

---

## 5. I 3 problemi noti

1. **Split-brain wa-mirror locale/Fly.** wa-mirror scrive ed emette eventi sul
   Postgres **locale** del Pro; l'handler `whatsapp_message_received` gira sul backend
   **Fly** che ascolta il DB **Fly**. → la coda locale (8.355 unconsumed) non ha mai un
   consumer. Qualsiasi worker WhatsApp DEVE girare sul Pro, sul DB locale.

2. **Dispatcher cloud-tainted (PII).** `dispatch_ocr_by_folder` → `_gemini_ocr` cade su
   Gemini CLI/API quando Ollama è giù: immagini di passaporti/KTP/NPWP + PII estratti
   vanno ai server Google (leak UU-PDP). Stessa taint in crm_guardian L1 summary,
   PDFVisionService, VisionRAGService. → l'intake unificato NON deve chiamare questi
   path per doc PII; serve la variante strict-local.

3. **drive_poll solo-Mini.** Il trigger Drive vive solo sul cron Mini H24
   (scheduler in-proc disabilitato, cron Pro commentato): single point of failure, con
   commento ancora riferito all'Air decommissionato. Se Mini cade, l'intake Drive si
   ferma silenziosamente, senza alert sul 200-rate.

---

## 6. KEY NUMBERS verificati (DB locale nuzantara_dev, 2026-06-04)

| Metrica | Valore |
|---|---|
| Messaggi WhatsApp totali | **24.081** |
| File WhatsApp su disco (`/Users/nuzantara/wa-mirror-media`) | **1.612** (715 MB) |
| → di cui PDF | **578** |
| Media con `media_stored_path` non NULL (DB) | **1.282** |
| Messaggi con `client_id` risolto | **1.282** |
| `ocr_status='done'` / `ocr_result` non NULL | **0** processati |
| `events_outbox.whatsapp_message_received` unconsumed (locale) | **8.355** |

> Nota di riconciliazione: 1.612 file su disco > 1.282 DB-stored-path (alcuni file
> scritti ma update riga async fallito o pre-migrazione). I 578 PDF + 629 documenti
> (media_type=document) confermano >1.200 documenti in attesa, **0 processati**.

---

## Verdetto FASE 1

L'infrastruttura per "fonte → OCR locale → CRM/Drive auto" è **per l'80% già scritta e
in produzione** ma frammentata e cloud-tainted. La FASE 2 non costruisce da zero:
**riusa** Tier-1 routing + schema `ocr_status` + writer CRM/Drive + estrattori locali;
**forka e strippa** il dispatcher in un path `local_only`; **costruisce nuovo** il
trigger di ingest (consumer locale WA + poll Zoho + re-enable Drive robusto), il
create-from-OCR, la coda human-review e il PII-masking.
