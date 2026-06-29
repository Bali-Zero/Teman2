---
date: 2026-06-18
domain: compliance
client_case: n/a (infra/architecture)
sources:
  - crm_clients.py:506-531 (specchio CRM→Drive, verificato)
  - service_account_drive_service.py:252-255,332,508 (PDF/JPEG upload, subfolder)
  - apps/evaluator/nlm_deep_research/db_to_nlm_sync.py (pattern riuso)
  - nlm CLI `source add --file/--drive` (verificato live)
  - postgres readonly: 1478 clienti, 1439 con Drive folder, 87 new/30d
status: COUNCIL-COMPLETE → NO-GO on NLM-per-client, GO on Qdrant substrate
---

## ⚖️ VERDETTO COUNCIL (2026-06-18) — NO-GO sul design originale

Red-team (DeepSeek, 7 BLOCKER) + costruttivo (Codex) CONVERGONO indipendentemente:
**NotebookLM-per-cliente è da uccidere; Qdrant interno è il substrate giusto.**

### 3 BLOCKER che reggono
1. **Scala fisica**: NLM consumer ~100 NB/account + 50 source/NB. 1439 NB = 17× oltre il cap → rompe in silenzio (#2 esiste≠armato).
2. **`@gmail` consumer ≠ perimetro sovrano**: no DPA, no SCC, dati su server USA/SG. PII di 1478 clienti paganti = commercial-use TOS risk + cross-border senza base legale UU PDP Pasal 58. NLM-consumer è un TERZO non contrattualizzato, non "casa nostra". **Law 2 NON ok qui.**
3. **Delete-on-soft-delete distrugge evidenza**: NLM no cestino, contro retention immigration 5+ anni.

### DESIGN v1 (GO) — riusa l'esistente
```
specchio CRM→Drive (vivo) → DrivePollService (vivo: scan 5min + match file→cliente + OCR)
  → enqueue document_index_jobs(document_id, file_id, client_id, source_version, status)
  → text-embedding-3-small (FROZEN, già lì) → Qdrant (93k vettori, Law-2 OK)
  → retrieval con filtro client_id=X AND state=indexed_active  (isolamento PII by-filter)
```
- **Trigger**: riusa `DrivePollService` (drive_poll_service.py:207) — niente secondo scanner. Enqueue quando `documents` creato o OCR→completed.
- **Idempotenza**: `drive:{fileId}:{md5Checksum}` (Drive API espone md5Checksum nativo, no download). Point Qdrant: `sha256("drive:"+fileId+":"+md5+":"+chunk_idx)`.
- **Lifecycle**: mirrored→ocr_pending→ocr_completed→indexed_active→(stale_reindex|soft_deleted→reactivated|purged). Soft-delete NASCONDE dal retrieval, CONSERVA evidenza; purge solo post-retention esplicito.
- **NotebookLM**: resta SOLO per NB-dominio curati non-PII (regolatorio, aggregati come db_to_nlm_sync oggi). Notebooks-in-Gemini ragiona su quelli, MAI sui PDF clienti.
- **db_to_nlm_sync.py**: riusato come PATTERN (extract/diff/lock/alert), NON esteso a PII/client files.

### METRICA FALSIFICABILE
"Un documento caricato nella cartella-cliente è queryable via RAG interno entro N minuti dal poll, con isolamento verificato: query con filtro client_id=A non ritorna MAI chunk di client_id=B (test cross-client)."

### STATO
GO sul design Qdrant. EXECUTE (STEP 5) non ancora avviato — attende conferma owner su scope/priorità.

---

## STEP 5 — DESIGN ESEGUIBILE v2 (groundato su codice reale, 2026-06-18)

Tutti gli anelli verificati su disco. Scoperta che riduce lo scope all'osso:
**l'OCR del documento è GIÀ estratto e in DB** — niente download, niente ri-OCR, niente NLM.

### Cosa esiste già (riuso, zero da costruire)
- `documents` (mig 061/074): `client_id`, `file_id`, **`content_hash`** (MD5 già calcolato in drive_poll_service.py:457),
  `ocr_status`, `ocr_completed_at`, **`ocr_extracted_data`** (JSONB col testo OCR), `subfolder`.
- `drive_poll_service.py`: match file→cliente (subfolder_map), INSERT documents (:535), dedup per content_hash (:462), dispatch OCR (:566).
- `crm_enhanced.py:537`: setta `ocr_status='completed'` → **AGGANCIO ENQUEUE qui**.
- `core/embeddings.py`: `EmbeddingsGenerator` text-embedding-3-small 1536 dims (FROZEN) — riuso.
- `services/ingestion/ingestion_service.py:156`: `vector_db.upsert_documents(...)` — pattern upsert Qdrant.

### Anello mancante (TUTTO il lavoro nuovo)
```
crm_enhanced.py:537 (ocr_status='completed')
  → INSERT INTO document_index_jobs(document_id, client_id, file_id, content_hash, status='pending')  [NUOVO]
  → worker: legge job pending → ocr_extracted_data (testo già pronto) → chunk → EmbeddingsGenerator
    → Qdrant upsert collection 'client_documents', payload FLAT: client_id, document_id, file_id,
      content_hash, document_type, subfolder, chunk_index, state='indexed_active'                     [NUOVO]
  → retrieval: query Qdrant con filtro client_id=X AND state='indexed_active'                          [NUOVO endpoint]
```

### Migration nuova (1 tabella)
`document_index_jobs(id, document_id FK, client_id, file_id, content_hash, status, attempts, error, created_at, indexed_at)`
+ UNIQUE(document_id, content_hash) → idempotenza nativa (stesso doc+stesso contenuto = no re-enqueue).

### Idempotenza
Chiave: `(document_id, content_hash)`. content_hash è MD5 del file (già in DB). Point Qdrant id:
`sha256(f"{file_id}:{content_hash}:{chunk_index}")` → re-ingest stesso contenuto = stesso point id = upsert no-op.

### Lifecycle (state su document_index_jobs + payload Qdrant)
`pending → indexing → indexed_active → (stale_reindex se content_hash cambia | soft_deleted se doc/client deleted_at → hidden dal retrieval, NON cancellato | purged solo post-retention esplicito)`.
Soft-delete = UPDATE payload state, MAI delete del vettore (conserva evidenza, no NLM-trash problem).

### Trigger
**NO nuovo cron/scanner.** Aggancio a `crm_enhanced.py:537` (OCR-completed). DrivePollService già scansiona e popola `documents`. Riuso totale.

### NotebookLM
Resta SOLO NB-dominio non-PII (regolatorio/aggregati, come `db_to_nlm_sync` oggi). MAI PDF clienti. Notebooks-in-Gemini ragiona su quelli.

### Piano TDD (STEP 5 esecuzione — attende GO operatore, tocca critical-path L2)
1. Migration `document_index_jobs` + test apply/rollback su DB locale (MAI nuzantara_dev — cf. scar 2026-06-18 TRUNCATE).
2. `client_doc_indexer.py`: enqueue fn + worker fn. Test: enqueue idempotente, worker embedda+upserta (Qdrant mock), state machine.
3. Hook 1-riga in `crm_enhanced.py:537` → chiama enqueue (best-effort, non blocca OCR).
4. Endpoint retrieval `/api/crm/client/{id}/docs/search` con filtro client_id.
5. **Test isolamento PII (metrica falsificabile)**: query client_id=A non ritorna MAI chunk client_id=B.
6. VERIFY: pytest + import-chain + (no deploy senza GO).

### Boundary
STEP 5 esecuzione = tocca DrivePoll/OCR critical-path (L2) + nuova migration + nuovo Qdrant collection.
NON parto da solo: attende GO esplicito owner su questo piano.

# Spec — Chiudere la catena CRM → Drive → NLM (→ Gemini) per i documenti-cliente

## Contesto verificato (disk-state, non training)

Catena già viva:
```
create_client (CRM/Postgres)
  → ensure_client_folder → cartella Drive {ID}_{Name}/ + 16 subfolder   [VIVO]
  → upload PDF/JPEG documenti nei subfolder                              [VIVO]
  → subfolder IDs persistiti in DB                                       [VIVO]
```
Anello mancante: documento entra → `nlm source add --drive <fileId>` sul NB del cliente.

Fatti chiave:
- Documenti = **PDF/JPEG** (non nativi) → Autosync Drive→NLM NON si aggancia.
- `nlm source add` accetta **`--file`** e **`--drive <id>`** → NLM ingerisce PDF senza conversione.
- `db_to_nlm_sync.py` = pattern riuso (extract+diff SHA256+source_delete/add+state-lock+Telegram, cron 04:30).
  Oggi sincronizza **aggregati non-PII**, NON i documenti-cliente (scelta deliberata).

## Numeri di scala (postgres readonly, 2026-06-18)
- **1478** clienti totali · **663** attivi · **1439** con cartella Drive · **~87** nuovi/30g.
- Decisione utente: **1 NB per cliente** → ~1439 NB subito + ~87/mese. NLM oggi = 86 NB.
- **Salto di scala ~17×** in un'unica operazione di backfill.

## Decisione utente (input)
- 1 NB per cliente (isolamento PII forte, fedele al video).
- Drive nostro + NLM nostro (account antonellosiano@, profilo default) + Law 2 OK (dato resta nel perimetro Google sovrano nostro).

## Design proposto (v0 — da abbattere nel council)

### A. Trigger
- **NON real-time per-file** (race con upload, rate-limit NLM). Estendere `db_to_nlm_sync.py`:
  nuovo modulo `client_docs_to_nlm.py`, cron separato (es. 05:00 WITA, dopo il sync aggregati).
- Diff per `google_drive_folder_id` + lista file (modifiedTime) → solo delta.

### B. NB lifecycle per-cliente
- NB creato **lazy** al primo documento (non a create_client) → evita 1439 NB vuoti.
- Mapping `client_id → nlm_notebook_id` in nuova tabella `client_nlm_notebooks`.
- Cliente `deleted_at` → NB cancellato (o archiviato) — chiusura PII.

### C. Ingestione
- `nlm source add <nb_id> --drive <fileId>` (by-ID, niente download locale → meno PII su FS).
- Diff SHA256 su fileId+modifiedTime per skip invariati.

### D. Scala / backfill
- Backfill 1439 NB = problema. Opzioni: (a) lazy-only (nessun backfill, solo nuovi), (b) backfill
  graduale rate-limited, (c) solo clienti attivi (663).

## Domande aperte per il council
1. **Scala NLM**: 1439+ NB su un account è sostenibile? Rate-limit, UI, quota? (red-team)
2. **PII**: `--drive by-ID` tiene il PDF fuori dal FS locale, ma il dato è in NLM cloud nostro —
   c'è un residuo Law-2 che ho mancato? (red-team)
3. **Trigger**: cron-diff è giusto o serve event-driven dallo specchio? (costruttivo)
4. **Lifecycle**: lazy-create + delete-on-client-delete copre tutto? Cosa con client riattivato? (costruttivo)
5. **Granularità alternativa**: NB-per-cliente vs NB-per-pratica vs ibrido — la scala 17× la mette in discussione?

## Metrica falsificabile (STEP 4)
TBD post-council. Candidata: "un documento caricato nella cartella-cliente è queryable in NLM entro N ore,
con isolamento verificato (query su NB-cliente-A non ritorna doc di cliente-B)".
