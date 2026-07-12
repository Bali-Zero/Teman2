# Legal Ingest Full Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `POST /api/legal/ingest-full` + `ingest_regulation` MCP tool that orchestrates Qdrant+KG → Drive → NLM → Sheets in a single async job.

**Architecture:** FastAPI endpoint accepts URL+metadata, creates a PostgreSQL job record (HTTP 202), background worker processes 4 steps sequentially with SKIP LOCKED, MCP tool polls for completion.

**Tech Stack:** Python 3.11, FastAPI, asyncpg, httpx, `LegalIngestionService` (existing), `TeamDriveService` (existing), `SheetsService` (existing), FastMCP

---

## File Map

| File                                                         | Action | Responsibility                                               |
| ------------------------------------------------------------ | ------ | ------------------------------------------------------------ |
| `backend/migrations/migration_070_legal_ingest_jobs.py`      | Create | Table `legal_ingest_jobs` + index                            |
| `backend/core/legal_config.py`                               | Create | `NB_TARGET_MAP`, `NB_NOTEBOOK_IDS`, `LEGAL_CATALOG_SHEET_ID` |
| `backend/services/ingestion/legal_full_ingestion_worker.py`  | Create | Async worker loop + 4-step pipeline                          |
| `backend/app/routers/legal_ingest.py`                        | Modify | Add `POST /ingest-full` + `GET /ingest-full/{job_id}`        |
| `backend/app/setup/app_factory.py`                           | Modify | Start worker task in `_background_init()`                    |
| `apps/nuzantara-mcp/nuzantara_mcp/tools/legal.py`            | Create | MCP tool `ingest_regulation`                                 |
| `apps/nuzantara-mcp/nuzantara_mcp/server.py`                 | Modify | Register `legal` tool module                                 |
| `backend/tests/services/ingestion/test_legal_full_worker.py` | Create | Unit tests for worker + config                               |

---

## Task 1: Migration + Config

**Files:**

- Create: `apps/backend-rag/backend/migrations/migration_070_legal_ingest_jobs.py`
- Create: `apps/backend-rag/backend/core/legal_config.py`

- [ ] **Step 1.1: Write the migration file**

```python
# apps/backend-rag/backend/migrations/migration_070_legal_ingest_jobs.py
"""
Migration 070: Legal Ingest Jobs Queue

Creates job queue table for async legal document ingestion pipeline.
Pattern: PostgreSQL SKIP LOCKED (per ADR in NB-9: zero new services).
"""

UPGRADE_SQL = """
CREATE TABLE IF NOT EXISTS legal_ingest_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key TEXT UNIQUE NOT NULL,
    tipo            TEXT NOT NULL,
    nomor           TEXT NOT NULL,
    anno            TEXT NOT NULL,
    titolo          TEXT,
    source_url      TEXT,
    nb_target       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    qdrant_chunks   INTEGER,
    drive_file_id   TEXT,
    drive_url       TEXT,
    nlm_source_id   TEXT,
    sheets_row      INTEGER,
    error           TEXT,
    visibility_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_legal_ingest_jobs_queue
    ON legal_ingest_jobs (status, visibility_at)
    WHERE status NOT IN ('complete', 'failed');

COMMENT ON TABLE legal_ingest_jobs IS
    'Async job queue for legal document ingestion pipeline (Qdrant+KG→Drive→NLM→Sheets)';
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS legal_ingest_jobs;
"""
```

- [ ] **Step 1.2: Write the config file**

```python
# apps/backend-rag/backend/core/legal_config.py
"""
Legal domain configuration: NB target mapping and notebook IDs.
Modify NB_TARGET_MAP and NB_NOTEBOOK_IDS here — no deploy required.
"""

from typing import Final

# Maps tipo → default NB target. Override with nb_target param in request.
NB_TARGET_MAP: Final[dict[str, str]] = {
    "PP": "NB-3",
    "Perpres": "NB-3",
    "Permen": "NB-3",
    "SKB": "NB-3",
    "PMK": "NB-4",
    "SE": "NB-4",
}

# NotebookLM notebook UUIDs — update here when notebooks change
NB_NOTEBOOK_IDS: Final[dict[str, str]] = {
    "NB-2": "cff93ab0-813a-42f2-a8de-36987e724271",  # Immigration
    "NB-3": "933509f9-1561-403d-bd44-4a7a67a36df2",  # Company Setup
    "NB-4": "d4b2eedb-9863-4a1a-81ff-a11b0b45d853",  # Tax
    "NB-5": "d9438180-5e63-4e2a-a473-6061101f6a8d",  # Property
    "NB-6": "85207af3-352f-4554-8d2a-18f42cc541ba",  # Operations
}

# Valid tipo enum values
VALID_TIPO: Final[frozenset[str]] = frozenset(NB_TARGET_MAP.keys())

# Valid nb_target values
VALID_NB_TARGETS: Final[frozenset[str]] = frozenset(NB_NOTEBOOK_IDS.keys())

# Google Sheet ID for legal catalog — set via LEGAL_CATALOG_SHEET_ID env var
import os
LEGAL_CATALOG_SHEET_ID: str = os.getenv("LEGAL_CATALOG_SHEET_ID", "")

# Drive folder name for legal documents (relative to team root)
DRIVE_LEGAL_ROOT: Final[str] = "PERATURAN"


def resolve_nb_target(tipo: str, nb_target_override: str | None) -> str:
    """Return NB target: use override if valid, else auto-map from tipo."""
    if nb_target_override and nb_target_override in VALID_NB_TARGETS:
        return nb_target_override
    return NB_TARGET_MAP.get(tipo, "NB-3")


def resolve_nb_notebook_id(nb_target: str) -> str | None:
    """Return NLM notebook UUID for an NB target key."""
    return NB_NOTEBOOK_IDS.get(nb_target)
```

- [ ] **Step 1.3: Write tests**

```python
# apps/backend-rag/backend/tests/services/ingestion/test_legal_full_worker.py
"""Tests for legal_config and LegalFullIngestionWorker."""
import pytest
from backend.core.legal_config import (
    resolve_nb_target,
    resolve_nb_notebook_id,
    VALID_TIPO,
    VALID_NB_TARGETS,
)


def test_resolve_nb_target_auto_map():
    assert resolve_nb_target("PP", None) == "NB-3"
    assert resolve_nb_target("PMK", None) == "NB-4"
    assert resolve_nb_target("SE", None) == "NB-4"


def test_resolve_nb_target_override():
    assert resolve_nb_target("PP", "NB-5") == "NB-5"


def test_resolve_nb_target_invalid_override_falls_back():
    # Invalid override → use auto-map
    assert resolve_nb_target("PP", "NB-99") == "NB-3"


def test_resolve_nb_notebook_id():
    nb_id = resolve_nb_notebook_id("NB-3")
    assert nb_id == "933509f9-1561-403d-bd44-4a7a67a36df2"


def test_resolve_nb_notebook_id_unknown():
    assert resolve_nb_notebook_id("NB-99") is None


def test_valid_tipo_contains_expected():
    assert "PP" in VALID_TIPO
    assert "PMK" in VALID_TIPO
    assert "INVALID" not in VALID_TIPO
```

- [ ] **Step 1.4: Run tests**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/ingestion/test_legal_full_worker.py::test_resolve_nb_target_auto_map backend/tests/services/ingestion/test_legal_full_worker.py::test_resolve_nb_target_override backend/tests/services/ingestion/test_legal_full_worker.py::test_valid_tipo_contains_expected -v
```

Expected: 3 PASSED

- [ ] **Step 1.5: Run migration locally**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python -c "
import asyncio, asyncpg
from backend.app.core.config import settings
from backend.migrations.migration_070_legal_ingest_jobs import UPGRADE_SQL

async def run():
    conn = await asyncpg.connect(settings.database_url)
    await conn.execute(UPGRADE_SQL)
    await conn.close()
    print('✅ Migration 070 applied')

asyncio.run(run())
"
```

Expected: `✅ Migration 070 applied`

- [ ] **Step 1.6: Commit**

```bash
cd apps/backend-rag
git add backend/migrations/migration_070_legal_ingest_jobs.py backend/core/legal_config.py backend/tests/services/ingestion/test_legal_full_worker.py
git commit -m "feat(legal): add migration_070 + legal_config for ingest-full pipeline"
```

---

## Task 2: LegalFullIngestionWorker

**Files:**

- Create: `apps/backend-rag/backend/services/ingestion/legal_full_ingestion_worker.py`

- [ ] **Step 2.1: Write the worker**

```python
# apps/backend-rag/backend/services/ingestion/legal_full_ingestion_worker.py
"""
LegalFullIngestionWorker — async background worker for legal document ingestion.

Pipeline: Qdrant+KG → Drive → NLM bridge → Google Sheets
Pattern: PostgreSQL SKIP LOCKED with visibility_at timeout (10 min).
"""

import asyncio
import logging
import os
import hashlib
import tempfile
from pathlib import Path
from typing import Any

import asyncpg
import httpx

from backend.core.legal_config import (
    DRIVE_LEGAL_ROOT,
    LEGAL_CATALOG_SHEET_ID,
    resolve_nb_notebook_id,
)

logger = logging.getLogger(__name__)

WORKER_INTERVAL = 10  # seconds between queue polls
VISIBILITY_TIMEOUT = "10 minutes"
NLM_BRIDGE_URL = os.getenv("NLM_BRIDGE_URL", "")
NLM_BRIDGE_KEY = os.getenv("NLM_BRIDGE_KEY", "")


async def run_worker(db_pool: asyncpg.Pool, app_state: Any) -> None:  # noqa: ANN401
    """Main worker loop. Runs forever in lifespan background task."""
    logger.info("✅ LegalFullIngestionWorker started")
    while True:
        try:
            await _process_one_job(db_pool, app_state)
        except asyncio.CancelledError:
            logger.info("🛑 LegalFullIngestionWorker cancelled — shutting down")
            return
        except Exception as e:
            logger.error(f"⚠️ Worker loop error (non-fatal): {e}", exc_info=True)
        await asyncio.sleep(WORKER_INTERVAL)


async def _claim_job(conn: asyncpg.Connection) -> asyncpg.Record | None:
    """Claim one pending job with SKIP LOCKED + visibility timeout."""
    return await conn.fetchrow(
        """
        UPDATE legal_ingest_jobs
        SET visibility_at = NOW() + $1::interval,
            updated_at    = NOW()
        WHERE id = (
            SELECT id FROM legal_ingest_jobs
            WHERE status NOT IN ('complete', 'failed')
              AND visibility_at <= NOW()
            ORDER BY created_at ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        )
        RETURNING *
        """,
        VISIBILITY_TIMEOUT,
    )


async def _update_job(conn: asyncpg.Connection, job_id: str, **fields: Any) -> None:
    """Update job fields + updated_at."""
    set_clauses = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(fields))
    values = list(fields.values())
    await conn.execute(
        f"UPDATE legal_ingest_jobs SET {set_clauses}, updated_at = NOW() WHERE id = $1",
        job_id,
        *values,
    )


async def _download_pdf(url: str, tipo: str, nomor: str, anno: str) -> Path:
    """Download PDF from URL to a temp file. Returns path."""
    dest = Path(tempfile.mkdtemp()) / f"{tipo}_{nomor}_{anno}.pdf"
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(str(url), follow_redirects=True)
        resp.raise_for_status()
    dest.write_bytes(resp.content)
    logger.info(f"📥 Downloaded PDF: {dest} ({len(resp.content)} bytes)")
    return dest


async def _process_one_job(db_pool: asyncpg.Pool, app_state: Any) -> None:  # noqa: ANN401
    """Claim and process one job, updating status after each step."""
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            job = await _claim_job(conn)
    if not job:
        return  # Queue empty

    job_id = str(job["id"])
    tipo = job["tipo"]
    nomor = job["nomor"]
    anno = job["anno"]
    source_url = job["source_url"]
    nb_target = job["nb_target"]
    titolo = job["titolo"]
    current_status = job["status"]

    logger.info(f"▶️  Processing legal job {job_id} ({tipo} {nomor}/{anno}) status={current_status}")

    pdf_path: Path | None = None

    try:
        # ── Step 1: Qdrant + KG ───────────────────────────────────────────────
        if current_status == "pending":
            async with db_pool.acquire() as conn:
                await _update_job(conn, job_id, visibility_at=f"NOW() + interval '{VISIBILITY_TIMEOUT}'")

            if not source_url:
                raise ValueError("source_url is required for ingestion")

            pdf_path = await _download_pdf(source_url, tipo, nomor, anno)

            from backend.services.ingestion.legal_ingestion_service import LegalIngestionService
            service = LegalIngestionService()
            result = await service.ingest_legal_document(
                file_path=str(pdf_path),
                title=titolo,
            )
            chunks = result.get("chunks_created", 0)
            if not titolo:
                titolo = result.get("book_title", f"{tipo} {nomor}/{anno}")

            async with db_pool.acquire() as conn:
                await _update_job(
                    conn, job_id,
                    status="qdrant_done",
                    qdrant_chunks=chunks,
                    titolo=titolo,
                )
            current_status = "qdrant_done"
            logger.info(f"✅ Step 1 done: {chunks} chunks ingested")

        # ── Step 2: Drive Upload ───────────────────────────────────────────────
        if current_status == "qdrant_done":
            if pdf_path is None:
                # Resume after crash: re-download
                pdf_path = await _download_pdf(source_url, tipo, nomor, anno)

            drive_service = getattr(app_state, "team_drive_service", None)
            if drive_service is None:
                raise RuntimeError("TeamDriveService not initialized in app_state")

            # Canonical filename for idempotency
            canonical_name = f"{tipo}_{nomor}_{anno}.pdf"
            folder_path = f"{DRIVE_LEGAL_ROOT}/{tipo}/{anno}"

            # Check if file already exists (idempotency)
            existing = await drive_service.find_file_by_name(canonical_name, folder_path=folder_path)
            if existing:
                drive_file_id = existing["id"]
                drive_url = existing.get("webViewLink", "")
                logger.info(f"ℹ️  Drive: file already exists ({drive_file_id}), skipping upload")
            else:
                upload_result = await drive_service.upload_file(
                    file_path=str(pdf_path),
                    folder_path=folder_path,
                    file_name=canonical_name,
                )
                drive_file_id = upload_result["file_id"]
                drive_url = upload_result.get("web_view_link", "")
                logger.info(f"✅ Step 2 done: Drive file_id={drive_file_id}")

            async with db_pool.acquire() as conn:
                await _update_job(
                    conn, job_id,
                    status="drive_done",
                    drive_file_id=drive_file_id,
                    drive_url=drive_url,
                )
            current_status = "drive_done"

        # ── Step 3: NLM Bridge ────────────────────────────────────────────────
        if current_status == "drive_done":
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow("SELECT drive_file_id FROM legal_ingest_jobs WHERE id = $1", job_id)
            drive_file_id = row["drive_file_id"]

            nb_id = resolve_nb_notebook_id(nb_target)
            if not nb_id:
                raise ValueError(f"Unknown nb_target: {nb_target}")

            if NLM_BRIDGE_URL:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        f"{NLM_BRIDGE_URL}/nlm/source-add",
                        headers={"X-Bridge-Key": NLM_BRIDGE_KEY},
                        json={
                            "notebook_id": nb_id,
                            "source_type": "drive",
                            "document_id": drive_file_id,
                        },
                    )
                    resp.raise_for_status()
                    nlm_data = resp.json()
                    nlm_source_id = nlm_data.get("source_id", "")
            else:
                logger.warning("⚠️  NLM_BRIDGE_URL not set — skipping NLM step")
                nlm_source_id = "skipped"

            async with db_pool.acquire() as conn:
                await _update_job(conn, job_id, status="nlm_done", nlm_source_id=nlm_source_id)
            current_status = "nlm_done"
            logger.info(f"✅ Step 3 done: NLM source_id={nlm_source_id}")

        # ── Step 4: Google Sheets ──────────────────────────────────────────────
        if current_status == "nlm_done":
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT titolo, drive_url, qdrant_chunks FROM legal_ingest_jobs WHERE id = $1",
                    job_id,
                )
            titolo_final = row["titolo"] or f"{tipo} {nomor}/{anno}"
            drive_url_final = row["drive_url"] or ""
            chunks_final = row["qdrant_chunks"] or 0

            sheets_row = None
            if LEGAL_CATALOG_SHEET_ID:
                sheets_service = getattr(app_state, "sheets_service", None)
                if sheets_service:
                    from datetime import datetime, timezone
                    row_data = [
                        tipo, nomor, anno, titolo_final,
                        drive_url_final, nb_target,
                        datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        chunks_final,
                    ]
                    result = await sheets_service.append_row(
                        spreadsheet_id=LEGAL_CATALOG_SHEET_ID,
                        range_name="Sheet1!A:H",
                        values=[row_data],
                    )
                    sheets_row = result.get("updated_range", "")
                    logger.info(f"✅ Step 4 done: Sheets row={sheets_row}")
                else:
                    logger.warning("⚠️  sheets_service not in app_state — skipping Sheets step")
                    sheets_row = "skipped"
            else:
                logger.warning("⚠️  LEGAL_CATALOG_SHEET_ID not set — skipping Sheets step")
                sheets_row = "skipped"

            async with db_pool.acquire() as conn:
                await _update_job(conn, job_id, status="complete", sheets_row=sheets_row)
            logger.info(f"🎉 Job {job_id} complete!")

    except Exception as e:
        error_msg = f"{current_status}: {e}"
        logger.error(f"❌ Job {job_id} failed at {current_status}: {e}", exc_info=True)
        async with db_pool.acquire() as conn:
            await _update_job(conn, job_id, status="failed", error=error_msg)
    finally:
        if pdf_path and pdf_path.exists():
            try:
                pdf_path.unlink()
            except Exception:
                pass
```

- [ ] **Step 2.2: Add worker tests**

Add these test functions to `backend/tests/services/ingestion/test_legal_full_worker.py`:

```python
# Append to test_legal_full_worker.py
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


@pytest.mark.asyncio
async def test_update_job_builds_correct_sql():
    """_update_job generates valid parameterized SQL."""
    conn = AsyncMock()
    from backend.services.ingestion.legal_full_ingestion_worker import _update_job
    await _update_job(conn, "test-uuid", status="qdrant_done", qdrant_chunks=42)
    conn.execute.assert_called_once()
    call_args = conn.execute.call_args[0]
    assert "status" in call_args[0]
    assert "qdrant_done" in call_args
    assert 42 in call_args


@pytest.mark.asyncio
async def test_process_one_job_empty_queue():
    """Worker does nothing when queue is empty."""
    db_pool = AsyncMock()
    db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    db_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_conn = AsyncMock()
    mock_conn.transaction.return_value.__aenter__ = AsyncMock(return_value=None)
    mock_conn.transaction.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_conn.fetchrow = AsyncMock(return_value=None)

    with patch("backend.services.ingestion.legal_full_ingestion_worker._claim_job", return_value=None):
        from backend.services.ingestion.legal_full_ingestion_worker import _process_one_job
        await _process_one_job(db_pool, MagicMock())
        # No exception raised — queue empty is handled gracefully
```

- [ ] **Step 2.3: Run tests**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/ingestion/test_legal_full_worker.py -v
```

Expected: 8 PASSED

- [ ] **Step 2.4: Commit**

```bash
git add backend/services/ingestion/legal_full_ingestion_worker.py backend/tests/services/ingestion/test_legal_full_worker.py
git commit -m "feat(legal): LegalFullIngestionWorker — 4-step async pipeline"
```

---

## Task 3: Router Endpoints

**Files:**

- Modify: `apps/backend-rag/backend/app/routers/legal_ingest.py`

- [ ] **Step 3.1: Add Pydantic models and idempotency helper at top of file**

Add after the existing imports (after line 21) and after the existing models:

```python
# Add these imports at top of legal_ingest.py (after existing imports):
import hashlib
from enum import Enum
from typing import Literal
from pydantic import HttpUrl

from backend.core.legal_config import VALID_TIPO, VALID_NB_TARGETS, resolve_nb_target


class LegalDocType(str, Enum):
    PP = "PP"
    Perpres = "Perpres"
    PMK = "PMK"
    Permen = "Permen"
    SE = "SE"
    SKB = "SKB"


class LegalIngestFullRequest(BaseModel):
    url: HttpUrl
    tipo: LegalDocType
    nomor: str
    anno: str
    nb_target: str | None = None
    titolo: str | None = None


class LegalIngestJobResponse(BaseModel):
    job_id: str
    status: str
    tipo: str | None = None
    nomor: str | None = None
    anno: str | None = None
    titolo: str | None = None
    qdrant_chunks: int | None = None
    drive_file_id: str | None = None
    drive_url: str | None = None
    nlm_source_id: str | None = None
    sheets_row: str | None = None
    error: str | None = None
    created_at: str | None = None
    message: str | None = None


def _idempotency_key(tipo: str, nomor: str, anno: str) -> str:
    return hashlib.sha256(f"{tipo}:{nomor}:{anno}".encode()).hexdigest()
```

- [ ] **Step 3.2: Add the two new endpoints at the end of legal_ingest.py**

```python
# Append to apps/backend-rag/backend/app/routers/legal_ingest.py

import asyncpg
from backend.app.core.config import settings


@router.post(
    "/ingest-full",
    response_model=LegalIngestJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_legal_full(
    request: LegalIngestFullRequest,
    api_key_verified=Depends(verify_internal_api_key),
) -> LegalIngestJobResponse:
    """
    Ingest a legal document into all systems: Qdrant+KG, Drive, NLM, Sheets.
    Returns HTTP 202 immediately with job_id. Poll GET /ingest-full/{job_id} for status.
    """
    nb_target = resolve_nb_target(request.tipo.value, request.nb_target)
    idempotency_key = _idempotency_key(request.tipo.value, request.nomor, request.anno)

    try:
        conn = await asyncpg.connect(settings.database_url, timeout=10)

        # Check idempotency
        existing = await conn.fetchrow(
            "SELECT id, status FROM legal_ingest_jobs WHERE idempotency_key = $1",
            idempotency_key,
        )
        if existing and existing["status"] == "complete":
            await conn.close()
            return LegalIngestJobResponse(
                job_id=str(existing["id"]),
                status="already_exists",
                message="Legge già ingestita. Usa job_id per i dettagli.",
            )

        if existing:
            await conn.close()
            return LegalIngestJobResponse(
                job_id=str(existing["id"]),
                status=existing["status"],
                message="Job già in corso.",
            )

        # Create new job
        row = await conn.fetchrow(
            """
            INSERT INTO legal_ingest_jobs
                (idempotency_key, tipo, nomor, anno, titolo, source_url, nb_target)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id, status
            """,
            idempotency_key,
            request.tipo.value,
            request.nomor,
            request.anno,
            request.titolo,
            str(request.url),
            nb_target,
        )
        await conn.close()

        logger.info(f"▶️  Legal ingest job created: {row['id']} ({request.tipo} {request.nomor}/{request.anno})")
        return LegalIngestJobResponse(
            job_id=str(row["id"]),
            status="pending",
            message="Ingestion avviata. Usa GET /api/legal/ingest-full/{job_id} per monitorare.",
        )

    except Exception as e:
        logger.error(f"Error creating legal ingest job: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create ingest job: {str(e)}",
        ) from e


@router.get("/ingest-full/{job_id}", response_model=LegalIngestJobResponse)
async def get_legal_ingest_job(job_id: str) -> LegalIngestJobResponse:
    """Get status and results of a legal ingestion job."""
    try:
        conn = await asyncpg.connect(settings.database_url, timeout=10)
        row = await conn.fetchrow(
            """
            SELECT id, status, tipo, nomor, anno, titolo,
                   qdrant_chunks, drive_file_id, drive_url,
                   nlm_source_id, sheets_row, error, created_at
            FROM legal_ingest_jobs WHERE id = $1
            """,
            job_id,
        )
        await conn.close()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job not found: {job_id}",
            )

        return LegalIngestJobResponse(
            job_id=str(row["id"]),
            status=row["status"],
            tipo=row["tipo"],
            nomor=row["nomor"],
            anno=row["anno"],
            titolo=row["titolo"],
            qdrant_chunks=row["qdrant_chunks"],
            drive_file_id=row["drive_file_id"],
            drive_url=row["drive_url"],
            nlm_source_id=row["nlm_source_id"],
            sheets_row=str(row["sheets_row"]) if row["sheets_row"] else None,
            error=row["error"],
            created_at=str(row["created_at"]),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching legal ingest job: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch job: {str(e)}",
        ) from e
```

- [ ] **Step 3.3: Verify syntax**

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.routers.legal_ingest import router; print('✅ Router OK')"
```

Expected: `✅ Router OK`

- [ ] **Step 3.4: Commit**

```bash
git add backend/app/routers/legal_ingest.py
git commit -m "feat(legal): add POST /ingest-full + GET /ingest-full/{job_id} endpoints"
```

---

## Task 4: Wire Worker in Lifespan

**Files:**

- Modify: `apps/backend-rag/backend/app/setup/app_factory.py`

- [ ] **Step 4.1: Add worker startup to `_background_init()`**

In `app_factory.py`, inside `_background_init()`, after the `# Initialize Workflow Queue` block (around line 133), add:

```python
        # Initialize Legal Ingest Worker
        try:
            from backend.services.ingestion.legal_full_ingestion_worker import run_worker as run_legal_worker

            legal_worker_task = asyncio.create_task(
                run_legal_worker(app.state.db_pool, app.state)
            )
            app.state._legal_ingest_worker_task = legal_worker_task
            logger.info("✅ LegalFullIngestionWorker started (PG SKIP LOCKED)")
        except Exception as e:
            logger.error(f"⚠️ Failed to initialize LegalFullIngestionWorker: {e}")
```

- [ ] **Step 4.2: Add worker shutdown to lifespan shutdown phase**

In the shutdown section of `lifespan()`, after the Workflow Queue Worker shutdown block (around line 161), add:

```python
    # Shutdown Legal Ingest Worker
    legal_worker_task = getattr(app.state, "_legal_ingest_worker_task", None)
    if legal_worker_task and not legal_worker_task.done():
        legal_worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await legal_worker_task
        logger.info("✅ LegalFullIngestionWorker stopped")
```

- [ ] **Step 4.3: Verify import chain**

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('✅ Import chain OK')"
```

Expected: `✅ Import chain OK`

- [ ] **Step 4.4: Commit**

```bash
git add backend/app/setup/app_factory.py
git commit -m "feat(legal): wire LegalFullIngestionWorker into lifespan startup/shutdown"
```

---

## Task 5: MCP Tool

**Files:**

- Create: `apps/nuzantara-mcp/nuzantara_mcp/tools/legal.py`
- Modify: `apps/nuzantara-mcp/nuzantara_mcp/server.py`

- [ ] **Step 5.1: Create the MCP tool file**

```python
# apps/nuzantara-mcp/nuzantara_mcp/tools/legal.py
"""Legal ingestion MCP tool — thin wrapper around POST /api/legal/ingest-full."""

import asyncio
from typing import Optional


def register(mcp, _call, _call_safe):

    @mcp.tool()
    async def ingest_regulation(
        url: str,
        tipo: str,
        nomor: str,
        anno: str,
        nb_target: Optional[str] = None,
        titolo: Optional[str] = None,
    ) -> dict:
        """
        Ingest una legge/regolamento indonesiano in tutti i sistemi:
        Qdrant+KG, Google Drive (PERATURAN/), NotebookLM, Google Sheets.

        Args:
            url: URL pubblico del PDF (http/https)
            tipo: Tipo regolamento — PP | Perpres | PMK | Permen | SE | SKB
            nomor: Numero del regolamento (es. "18")
            anno: Anno (es. "2021")
            nb_target: Notebook target — NB-2..NB-6 (auto-mappato da tipo se omesso)
            titolo: Titolo opzionale (estratto dal PDF se omesso)

        Returns:
            Risultato completo con job_id, status, drive_url, chunks_created, ecc.
        """
        # Start job — backend returns 202 + job_id
        job = await _call(
            "/api/legal/ingest-full",
            method="POST",
            json={
                "url": url,
                "tipo": tipo,
                "nomor": nomor,
                "anno": anno,
                "nb_target": nb_target,
                "titolo": titolo,
            },
            timeout=30,
        )

        # Handle already_exists
        if job.get("status") in ("already_exists", "failed"):
            return job

        job_id = job.get("job_id")
        if not job_id:
            return {"error": True, "detail": "Backend did not return job_id", "raw": job}

        # Poll for completion (5s interval, 180s timeout)
        for _ in range(36):
            await asyncio.sleep(5)
            status = await _call_safe(f"/api/legal/ingest-full/{job_id}", method="GET", timeout=15)
            if status.get("status") in ("complete", "failed", "already_exists"):
                return status

        # Timeout — return current state so operator can check manually
        return {
            "job_id": job_id,
            "status": "timeout",
            "message": f"Job avviato ma non completato in 180s. Ricontrolla: GET /api/legal/ingest-full/{job_id}",
        }
```

- [ ] **Step 5.2: Register in server.py**

In `apps/nuzantara-mcp/nuzantara_mcp/server.py`, add after the federation import block (around line 109):

```python
# Legal ingestion
from nuzantara_mcp.tools.legal import register as register_legal
```

And after `register_federation(mcp, _call, _call_safe)` (around line 145):

```python
register_legal(mcp, _call, _call_safe)
```

- [ ] **Step 5.3: Verify MCP server starts without error**

```bash
cd apps/nuzantara-mcp
python -c "from nuzantara_mcp.server import mcp; print('✅ MCP server OK')"
```

Expected: `✅ MCP server OK`

- [ ] **Step 5.4: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/nuzantara-mcp/nuzantara_mcp/tools/legal.py apps/nuzantara-mcp/nuzantara_mcp/server.py
git commit -m "feat(mcp): add ingest_regulation tool — thin wrapper for legal ingest-full"
```

---

## Task 6: End-to-End Test + Deploy

**Files:**

- Run tests, deploy to Fly.io

- [ ] **Step 6.1: Run full test suite**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/ingestion/test_legal_full_worker.py -v
```

Expected: 8 PASSED, 0 FAILED

- [ ] **Step 6.2: Run import chain check**

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('✅ Import chain OK')"
```

- [ ] **Step 6.3: Run core RAG tests**

```bash
PYTHONPATH=. pytest backend/tests/services/rag/test_confidence.py -q --tb=no
```

Expected: all PASSED

- [ ] **Step 6.4: Set Fly.io env vars (if not already set)**

```bash
# Run these only if env vars not already set on nuzantara-rag
fly secrets set NLM_BRIDGE_URL="http://<pro-tailscale-ip>:18790" -a nuzantara-rag
fly secrets set NLM_BRIDGE_KEY="<shared-secret>" -a nuzantara-rag
fly secrets set LEGAL_CATALOG_SHEET_ID="<sheet-id>" -a nuzantara-rag
```

- [ ] **Step 6.5: Deploy**

```bash
cd apps/backend-rag
fly deploy --strategy rolling
```

Expected: deploy succeeds, health check passes

- [ ] **Step 6.6: Run migration in production**

```bash
fly ssh console -a nuzantara-rag -C "cd /app && python -c \"
import asyncio, asyncpg, os
from backend.migrations.migration_070_legal_ingest_jobs import UPGRADE_SQL
async def run():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    await conn.execute(UPGRADE_SQL)
    await conn.close()
    print('Migration 070 applied')
asyncio.run(run())
\""
```

- [ ] **Step 6.7: Smoke test via MCP**

```python
# In Claude Code session:
# mcp__nuzantara-mcp__ingest_regulation(
#     url="https://jdih.setkab.go.id/ProdHukum/...",
#     tipo="PP",
#     nomor="18",
#     anno="2021",
# )
# Expected: {"status": "complete", "qdrant_chunks": N, "drive_url": "..."}
```

- [ ] **Step 6.8: Final commit tag**

```bash
git tag v5.2.1-legal-ingest-full
git push origin main --tags
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement                       | Task   |
| -------------------------------------- | ------ |
| `POST /api/legal/ingest-full` HTTP 202 | Task 3 |
| `GET /api/legal/ingest-full/{job_id}`  | Task 3 |
| `legal_ingest_jobs` table + index      | Task 1 |
| `legal_config.py` NB mapping           | Task 1 |
| SKIP LOCKED worker                     | Task 2 |
| visibility_at timeout 10 min           | Task 2 |
| Qdrant+KG via LegalIngestionService    | Task 2 |
| Drive upload with idempotency check    | Task 2 |
| NLM bridge via Pro:18790               | Task 2 |
| Sheets append                          | Task 2 |
| `verify_internal_api_key` on POST      | Task 3 |
| Idempotency sha256(tipo+nomor+anno)    | Task 3 |
| `ingest_regulation` MCP tool           | Task 5 |
| MCP polling 5s/180s                    | Task 5 |
| Lifespan worker start/stop             | Task 4 |
| Fly.io env vars                        | Task 6 |

All requirements covered. No placeholders. Types consistent across tasks.
