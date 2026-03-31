# Legal Ingest Full — Design Spec

**Data:** 2026-03-31
**Versione:** 1.0
**Status:** Approved — Ready for Implementation
**Review:** Gemini Pro 6/10 · Codex 6/10 · DeepSeek 7/10 · NB-1 Oracle GO

---

## Problema

Un operatore trova una nuova legge indonesiana (URL PDF o file locale). Oggi deve manualmente:

1. Uploadare su Qdrant via endpoint legacy
2. Uploadare su Google Drive
3. Aggiungere fonte a NotebookLM
4. Aggiornare il catalogo Google Sheets

Il processo richiede 4 step separati, è error-prone e non garantisce coerenza tra i sistemi.

## Soluzione

Un singolo trigger — `ingest_regulation(url, tipo, nomor, anno)` — che orchestra tutto in background e ritorna lo stato in tempo reale.

---

## Architettura

```
Operatore/MCP
    │
    ▼
POST /api/legal/ingest-full          ← FastAPI router
    │  HTTP 202 + job_id immediato
    ▼
legal_ingest_jobs (PostgreSQL)       ← job queue SKIP LOCKED
    │
    ▼
LegalFullIngestionWorker             ← asyncio task nel lifespan
    ├── Step 1: LegalIngestionService  → Qdrant + KG
    ├── Step 2: TeamDriveService       → Google Drive PERATURAN/
    ├── Step 3: nlm-bridge (Pro:18790) → NotebookLM source_add
    └── Step 4: SheetsService          → Catalogo leggi

GET /api/legal/ingest-full/{job_id}  ← status polling
```

---

## Componenti

### 1. Endpoint `POST /api/legal/ingest-full`

**Auth:** `Depends(verify_internal_api_key)` — obbligatorio.

**Request body:**

```python
class LegalIngestFullRequest(BaseModel):
    url: Optional[HttpUrl] = None        # URL pubblico PDF (http/https only)
    tipo: LegalDocType                   # enum: PP|Perpres|PMK|Permen|SE|SKB
    nomor: str                           # numero del regolamento
    anno: str                            # anno (es. "2021")
    nb_target: Optional[str] = None      # override NB target (auto-map se None)
    titolo: Optional[str] = None         # titolo (estratto dal PDF se None)
```

**Sicurezza:** `url` accetta solo schema `http`/`https`. Nessun `file_path` nel payload pubblico (path traversal prevention).

**Idempotency:** chiave `sha256(tipo + nomor + anno)`. Se job già `complete` → 200 `{"status": "already_exists", "job_id": "..."}`.

**Response 202:**

```json
{ "job_id": "uuid", "status": "pending", "message": "Ingestion in corso" }
```

---

### 2. Tabella `legal_ingest_jobs` (migration_070)

```sql
CREATE TABLE legal_ingest_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key TEXT UNIQUE NOT NULL,    -- sha256(tipo+nomor+anno)
    tipo            TEXT NOT NULL,
    nomor           TEXT NOT NULL,
    anno            TEXT NOT NULL,
    titolo          TEXT,
    source_url      TEXT,
    nb_target       TEXT NOT NULL,           -- NB-3, NB-4, NB-5, ecc.
    status          TEXT DEFAULT 'pending',  -- pending|qdrant_done|drive_done|nlm_done|complete|failed
    qdrant_chunks   INTEGER,
    drive_file_id   TEXT,
    drive_url       TEXT,
    nlm_source_id   TEXT,
    sheets_row      INTEGER,
    error           TEXT,
    visibility_at   TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON legal_ingest_jobs (status, visibility_at);
```

**Pattern worker:** `SELECT ... FOR UPDATE SKIP LOCKED WHERE status != 'complete' AND status != 'failed' AND visibility_at <= NOW()`. Imposta `visibility_at = NOW() + interval '10 minutes'` al claim — se il worker muore, il job torna disponibile automaticamente dopo 10 min.

---

### 3. `LegalFullIngestionWorker`

Asyncio task avviato nel `lifespan()` di `app_factory.py`. Loop ogni 10s.

**Pipeline per job:**

```
Step 1 — Qdrant + KG
  → LegalIngestionService.ingest_legal_document(file_path, titolo, tier_override, nb_target_collection)
  → UPDATE status='qdrant_done', qdrant_chunks=N

Step 2 — Drive Upload
  → Scarica PDF da source_url se non ancora in /tmp (o usa file già scaricato in step 1)
  → TeamDriveService.upload_file(path, folder="PERATURAN/{tipo}/{anno}/", name="{tipo}_{nomor}_{anno}.pdf")
  → Controlla esistenza per nome prima di uploadare (idempotenza Drive)
  → UPDATE status='drive_done', drive_file_id=..., drive_url=...

Step 3 — NLM Bridge
  → POST http://pro-tailscale:18790/nlm/source-add
    headers: {"X-Bridge-Key": NLM_BRIDGE_KEY}
    body: {"notebook_id": nb_id, "source_type": "drive", "document_id": drive_file_id}
  → UPDATE status='nlm_done', nlm_source_id=...

Step 4 — Google Sheets
  → SheetsService.append_row(LEGAL_CATALOG_SHEET_ID, [tipo, nomor, anno, titolo, drive_url, nb_target, now(), qdrant_chunks])
  → Cerca riga esistente prima di appendere (idempotenza Sheets)
  → UPDATE status='complete', sheets_row=N
```

**Error handling:** ogni step failure → `UPDATE status='failed', error='step_name: msg'`. Job non viene ritentato automaticamente — operatore può re-triggerare via MCP.

---

### 4. nb_target mapping (`backend/core/legal_config.py`)

```python
NB_TARGET_MAP = {
    "PP": "NB-3",
    "Perpres": "NB-3",
    "PMK": "NB-4",
    "SE": "NB-4",
    "Permen": "NB-3",  # default company, override manuale per altri domini
    "SKB": "NB-3",
}

NB_NOTEBOOK_IDS = {
    "NB-2": "cff93ab0-813a-42f2-a8de-36987e724271",  # Immigration
    "NB-3": "933509f9-1561-403d-bd44-4a7a67a36df2",  # Company Setup
    "NB-4": "d4b2eedb-9863-4a1a-81ff-a11b0b45d853",  # Tax
    "NB-5": "d9438180-5e63-4e2a-a473-6061101f6a8d",  # Property
    "NB-6": "85207af3-352f-4554-8d2a-18f42cc541ba",  # Operations
}
```

Modificabile senza deploy. Se `nb_target` fornito nel request, override il mapping.

---

### 5. Endpoint `GET /api/legal/ingest-full/{job_id}`

Ritorna stato corrente + risultati parziali. Nessuna auth (job_id è già un segreto sufficiente per questo endpoint di sola lettura).

```json
{
  "job_id": "uuid",
  "status": "drive_done",
  "tipo": "PP",
  "nomor": "18",
  "anno": "2021",
  "qdrant_chunks": 47,
  "drive_file_id": "1abc...",
  "drive_url": "https://drive.google.com/...",
  "nlm_source_id": null,
  "sheets_row": null,
  "error": null,
  "created_at": "2026-03-31T..."
}
```

---

### 6. MCP Tool `ingest_regulation`

**File:** `apps/nuzantara-mcp/nuzantara_mcp/tools/legal.py` (nuovo)

```python
@mcp.tool()
async def ingest_regulation(
    url: str,
    tipo: str,
    nomor: str,
    anno: str,
    nb_target: str = None,
    titolo: str = None,
) -> dict:
    """Ingest una legge/regolamento indonesiano in tutti i sistemi:
    Qdrant, Knowledge Graph, Google Drive, NotebookLM, Google Sheets.

    tipo: PP | Perpres | PMK | Permen | SE | SKB
    nb_target: NB-2..NB-6 (auto-mappato da tipo se omesso)
    """
    # 1. Avvia job
    result = await _call("/api/legal/ingest-full", method="POST", json={
        "url": url, "tipo": tipo, "nomor": nomor, "anno": anno,
        "nb_target": nb_target, "titolo": titolo,
    })
    job_id = result["job_id"]

    # 2. Polling con timeout 180s
    for _ in range(36):  # 36 * 5s = 180s
        await asyncio.sleep(5)
        status = await _call(f"/api/legal/ingest-full/{job_id}", method="GET")
        if status["status"] in ("complete", "failed", "already_exists"):
            return status

    return {"job_id": job_id, "status": "timeout", "message": "Job avviato, usa job_id per monitorare"}
```

---

## File da creare/modificare

| File                                                        | Azione                                                                |
| ----------------------------------------------------------- | --------------------------------------------------------------------- |
| `backend/migrations/migration_070_legal_ingest_jobs.py`     | Nuovo — tabella `legal_ingest_jobs`                                   |
| `backend/core/legal_config.py`                              | Nuovo — `NB_TARGET_MAP`, `NB_NOTEBOOK_IDS`, `LEGAL_CATALOG_SHEET_ID`  |
| `backend/services/ingestion/legal_full_ingestion_worker.py` | Nuovo — worker loop + pipeline 4 step                                 |
| `backend/app/routers/legal_ingest.py`                       | Modifica — aggiunge `POST /ingest-full` + `GET /ingest-full/{job_id}` |
| `backend/app/setup/app_factory.py`                          | Modifica — avvia worker in `lifespan()`                               |
| `apps/nuzantara-mcp/nuzantara_mcp/tools/legal.py`           | Nuovo — MCP tool `ingest_regulation`                                  |
| `apps/nuzantara-mcp/nuzantara_mcp/server.py`                | Modifica — registra tool legal                                        |

---

## Dipendenze ambientali

| Variabile                | Valore                            |
| ------------------------ | --------------------------------- |
| `NLM_BRIDGE_URL`         | `http://<pro-tailscale-ip>:18790` |
| `NLM_BRIDGE_KEY`         | segreto condiviso Pro↔Fly         |
| `LEGAL_CATALOG_SHEET_ID` | ID Google Sheet catalogo leggi    |

> `apps/nlm-bridge/` deve essere attivo su Pro (già progettato in spec `2026-03-25-nlm-knowledge-fabric-integration-design.md`). Verificare che sia running prima del deploy.

---

## Non incluso in questo spec

- Auto-detection di nuove leggi (monitoring automatico JDIH) — task separato
- UI frontend per status monitoring — fuori scope
- Upload PDF da file locale (solo URL per ora — sicurezza)
- Retry automatico dei job falliti — operatore re-triggera manualmente

---

## Ordine di implementazione suggerito

1. Migration 070 + `legal_config.py`
2. `LegalFullIngestionWorker` (step 1+2 prima, step 3+4 dopo)
3. Router endpoints + lifespan wiring
4. MCP tool
5. Test end-to-end con un PP reale

**Stima:** ~6-8h implementazione, ~2h testing.
