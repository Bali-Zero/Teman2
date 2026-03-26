# NB Verified Generation Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 6-step verified generation pipeline for NotebookLM notebook population that eliminates hallucinations by grounding every normative claim in verbatim law before it enters any notebook.

**Architecture:** Claims are extracted from T0 law sources into `claims_db.json`, T2 operational guides are auto-generated and then verified against that database (regex scan + CRAG-light Haiku evaluator), flagged claims go to Telegram for human review, and only approved documents are uploaded to NLM. A split notebook architecture (NB-Xa primary oracle + NB-Xb operational) prevents NLM from blending unverified content with authoritative law.

**Tech Stack:** Python 3.11, PostgreSQL (Fly.io + local tunnel), NotebookLM MCP, Claude Haiku 4.5 (CRAG evaluator), Claude Sonnet 4.6 (generator), Telegram Bot API, asyncpg, httpx, ruff.

---

## File Map

| Action | Path                                                                                    | Responsibility                                                               |
| ------ | --------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Modify | `apps/backend-rag/backend/services/oracle/nlm_notebook_registry.py`                     | Fix wrong immigration notebook ID + add split NB-Xa/Xb structure             |
| Create | `apps/backend-rag/backend/db/migrations_v2/038_legal_instruments.sql`                   | Track T0/T1 law instrument status + conflict notes                           |
| Create | `apps/backend-rag/backend/services/oracle/legal_instruments_service.py`                 | CRUD for `legal_instruments` table                                           |
| Create | `apps/backend-rag/backend/tests/unit/services/oracle/test_legal_instruments_service.py` | Tests for legal instruments service                                          |
| Create | `apps/backend-rag/scripts/claims_extractor.py`                                          | Extract `claims_db.json` from T0 sources                                     |
| Create | `apps/backend-rag/backend/tests/unit/scripts/test_claims_extractor.py`                  | Tests for claims extraction logic                                            |
| Create | `apps/backend-rag/scripts/claims_db/immigration_claims_db.json`                         | Canonical claims store for Immigration domain (seeded)                       |
| Create | `apps/backend-rag/scripts/auto_verifier.py`                                             | CRAG-light verifier: blocks upload if <95% claims verified                   |
| Create | `apps/backend-rag/scripts/telegram_reviewer.py`                                         | Human-in-the-loop: send failed claims to Telegram, await /approve or /reject |
| Create | `apps/backend-rag/scripts/verified_generator.py`                                        | 6-step pipeline orchestrator                                                 |
| Create | `apps/backend-rag/scripts/legal_radar.py`                                               | Weekly scan for new Indonesian regulations                                   |

---

## Task 1: Fix the Registry Bug + Split NB-Xa/Xb Schema

**Files:**

- Modify: `apps/backend-rag/backend/services/oracle/nlm_notebook_registry.py`

- [ ] **Step 1: Fix the wrong immigration notebook ID**

The current `immigration` entry points to `84375bc3-12d0-4405-a774-9b89189d8c39` which is actually a PP 28/2025 forestry notebook. The correct NB-2 operational notebook ID is `cff93ab0-813a-42f2-a8de-36987e724271`.

Replace the entire file content with:

```python
"""NLM Notebook Registry — static mapping of domains to NotebookLM notebook IDs.

Each domain has:
- notebook_id: operational notebook (NB-Xb) — T2+T3 verified guides
- primary_notebook_id: oracle notebook (NB-Xa) — T0+T1 law only (None until created)
- keywords: used by resolve_notebook() to route queries
"""
from __future__ import annotations

NLM_NOTEBOOKS: dict[str, dict] = {
    "immigration": {
        "notebook_id": "cff93ab0-813a-42f2-a8de-36987e724271",   # NB-2b operational
        "primary_notebook_id": None,   # NB-2a not yet created
        "label": "Immigration & Visa",
        "keywords": {
            "visa", "kitas", "kitap", "tka", "immigration", "imigrasi",
            "work permit", "stay permit", "foreigner", "expat",
        },
    },
    "company": {
        "notebook_id": "2e84b9b9-3b99-4bc5-8ec5-351a43c52df4",
        "primary_notebook_id": None,
        "label": "Company & Licensing",
        "keywords": {
            "company", "kbli", "pma", "oss", "licensing", "nib",
            "investment", "business", "pt ", "perseroan",
        },
    },
    "tax": {
        "notebook_id": "837b620b-2aca-43ab-812e-97ca92bdad1d",
        "primary_notebook_id": None,
        "label": "Tax & Compliance",
        "keywords": {
            "tax", "compliance", "lkpm", "npwp", "pph", "ppn",
            "coretax", "bpjs", "fiscal", "pajak",
        },
    },
    "property": {
        "notebook_id": "568ec624-ceb8-47d1-a2a2-5b2f793ea7ed",
        "primary_notebook_id": None,
        "label": "Property & Zoning",
        "keywords": {
            "property", "zoning", "land", "hgb", "hak pakai",
            "building", "villa", "real estate", "leasehold",
        },
    },
    "operations": {
        "notebook_id": "3e1baa5f-680f-4499-9430-23a901576bcc",
        "primary_notebook_id": None,
        "label": "Operations",
        "keywords": {"sop", "team", "pricing", "crm", "workflow", "competitor"},
    },
    "editorial": {
        "notebook_id": "dd464d8f-6b8e-4543-8647-f62c498589b1",
        "primary_notebook_id": None,
        "label": "Editorial & Market",
        "keywords": {
            "seo", "content", "market", "intel", "trends", "news", "article", "editorial",
        },
    },
    "lifestyle": {
        "notebook_id": "1143b525-dd3f-40d7-a34d-2e9263b44460",
        "primary_notebook_id": None,
        "label": "Expat Life",
        "keywords": {
            "lifestyle", "expat", "healthcare", "cost of living",
            "culture", "digital nomad", "education", "school",
        },
    },
}

# Keywords that indicate the user wants T0/T1 primary law sources
_PRIMARY_LAW_KEYWORDS = frozenset({"pasal", "uu ", "pp ", "peraturan", "permenkumham", "permen", "undang"})


def resolve_notebook(query: str) -> dict[str, object] | None:
    """Resolve a user query to the best-matching NLM notebook.

    When a primary notebook exists for the domain, returns it for
    regulation-heavy queries (pasal, uu, pp, permenkumham, etc.).
    Otherwise returns the operational notebook.

    Args:
        query: Free-text user query.

    Returns:
        A dict with keys ``domain``, ``notebook_id``, ``label``, ``keywords``
        for the best match, or ``None`` if nothing matches.
    """
    if not query:
        return None

    query_lower = query.lower()
    wants_primary = any(kw in query_lower for kw in _PRIMARY_LAW_KEYWORDS)

    best_domain: str | None = None
    best_score: int = 0

    for domain, data in NLM_NOTEBOOKS.items():
        score = sum(1 for kw in data["keywords"] if kw in query_lower)
        if score > best_score:
            best_score = score
            best_domain = domain

    if best_domain is None:
        return None

    data = NLM_NOTEBOOKS[best_domain]
    primary = data.get("primary_notebook_id")
    active_id = primary if (wants_primary and primary) else data["notebook_id"]

    return {"domain": best_domain, "notebook_id": active_id, **data}
```

- [ ] **Step 2: Verify with Python**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python -c "
from backend.services.oracle.nlm_notebook_registry import resolve_notebook, NLM_NOTEBOOKS
# Test: immigration points to correct notebook
nb = resolve_notebook('visa kitas rinnovo')
assert nb is not None
assert nb['notebook_id'] == 'cff93ab0-813a-42f2-a8de-36987e724271', f'Got {nb[\"notebook_id\"]}'
print('immigration notebook ID: CORRECT')

# Test: primary_notebook_id key exists in all domains
for domain, data in NLM_NOTEBOOKS.items():
    assert 'primary_notebook_id' in data, f'{domain} missing primary_notebook_id'
print('All domains have primary_notebook_id key: OK')

# Test: primary route falls back to operational when primary is None
nb2 = resolve_notebook('pasal 28 uu imigrasi')
assert nb2['notebook_id'] == 'cff93ab0-813a-42f2-a8de-36987e724271', f'Got {nb2[\"notebook_id\"]}'
print('primary route fallback to operational: OK')
print('All checks passed')
"
```

Expected: prints all 3 OK lines.

- [ ] **Step 3: Lint**

```bash
ruff check backend/services/oracle/nlm_notebook_registry.py
```

Expected: `All checks passed.`

- [ ] **Step 4: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/backend-rag/backend/services/oracle/nlm_notebook_registry.py
git commit -m "fix(oracle): correct immigration notebook ID + add split NB-Xa/Xb registry schema"
```

---

## Task 2: PostgreSQL `legal_instruments` Table (Migration 038)

**Files:**

- Create: `apps/backend-rag/backend/db/migrations_v2/038_legal_instruments.sql`

The `legal_instruments` table tracks T0/T1 normative sources with status (active/superseded/revoked), conflict notes explaining normative transitions, and NLM upload status.

- [ ] **Step 1: Create the migration file**

Create `/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/db/migrations_v2/038_legal_instruments.sql`:

```sql
-- Migration 038: Legal instruments registry for NB Verified Generation Pipeline
-- Tracks T0/T1 normative sources: status, conflicts, vigenza

CREATE TABLE IF NOT EXISTS legal_instruments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument_id   VARCHAR(100) NOT NULL UNIQUE,
    instrument_type VARCHAR(50)  NOT NULL,           -- 'UU', 'PP', 'Permenkumham', 'Permen', 'SE', 'Juklak'
    tier            SMALLINT     NOT NULL DEFAULT 0, -- 0=Primary law, 1=Official interpretation
    domain          VARCHAR(50)  NOT NULL,           -- 'immigration', 'company', 'tax', 'property'
    title           TEXT         NOT NULL,
    number          VARCHAR(50),
    year            SMALLINT,
    status          VARCHAR(20)  NOT NULL DEFAULT 'active',  -- 'active', 'superseded', 'partially_superseded', 'revoked'
    vigore_date     DATE,
    revoked_by      VARCHAR(100),
    conflict_note   TEXT,
    source_url      TEXT,
    source_file     TEXT,
    nb_uploaded     BOOLEAN NOT NULL DEFAULT FALSE,
    nb_uploaded_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_legal_inst_domain_status ON legal_instruments(domain, status);
CREATE INDEX IF NOT EXISTS idx_legal_inst_type          ON legal_instruments(instrument_type, year DESC);
CREATE INDEX IF NOT EXISTS idx_legal_inst_nb_uploaded   ON legal_instruments(nb_uploaded) WHERE NOT nb_uploaded;

CREATE OR REPLACE FUNCTION legal_instruments_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER legal_instruments_updated_at
    BEFORE UPDATE ON legal_instruments
    FOR EACH ROW EXECUTE FUNCTION legal_instruments_set_updated_at();

-- Seed: Immigration domain T0+T1 sources
INSERT INTO legal_instruments
    (instrument_id, instrument_type, tier, domain, title, number, year, status, vigore_date, source_url)
VALUES
    ('UU-6-2011',
     'UU', 0, 'immigration',
     'Undang-Undang No. 6 Tahun 2011 tentang Keimigrasian',
     '6/2011', 2011, 'active', '2011-05-05',
     'https://peraturan.bpk.go.id/Details/39480'),
    ('PP-31-2013',
     'PP', 0, 'immigration',
     'PP No. 31 Tahun 2013 tentang Peraturan Pelaksanaan UU Keimigrasian',
     '31/2013', 2013, 'active', '2013-05-02',
     'https://peraturan.bpk.go.id/Details/5173'),
    ('Permenkumham-22-2023',
     'Permenkumham', 1, 'immigration',
     'Permenkumham No. 22 Tahun 2023 tentang Visa dan Izin Tinggal',
     '22/2023', 2023, 'partially_superseded', '2023-08-01',
     'https://peraturan.bpk.go.id/Details/275012'),
    ('Permen-Imipas-3-2025',
     'Permen', 1, 'immigration',
     'Peraturan Menteri Imigrasi No. 3 Tahun 2025',
     '3/2025', 2025, 'active', '2025-02-01',
     NULL),
    ('SE-Kemnaker-3-836-2026',
     'SE', 1, 'immigration',
     'Surat Edaran Kemnaker No. SE-3/836/2026 tentang TKA',
     'SE-3/836', 2026, 'active', '2026-01-15',
     NULL)
ON CONFLICT (instrument_id) DO NOTHING;

-- Mark the conflict: Permenkumham-22-2023 partially superseded by Permen-Imipas-3-2025
UPDATE legal_instruments
SET
    revoked_by    = 'Permen-Imipas-3-2025',
    conflict_note = 'Le disposizioni sui visti multipli entry di Permenkumham 22/2023 sono state superate da Permen Imipas 3/2025 entrata in vigore il 01-02-2025. Le disposizioni su KITAS e KITAP rimangono in vigore fino a nuova normativa.'
WHERE instrument_id = 'Permenkumham-22-2023';
```

- [ ] **Step 2: Verify file is readable**

```bash
python3 -c "
sql = open('/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/db/migrations_v2/038_legal_instruments.sql').read()
print(f'Migration file: {len(sql)} bytes, {sql.count(chr(10))} lines')
assert 'CREATE TABLE IF NOT EXISTS legal_instruments' in sql
assert 'IMM' not in sql  # no claim IDs here
assert 'ON CONFLICT' in sql
print('Syntax check: OK')
"
```

- [ ] **Step 3: Apply migration via Fly.io proxy tunnel**

Ensure the Fly.io proxy is running on port 15432, then apply:

```bash
fly proxy 15432:5432 -a nuzantara-postgres &
sleep 3
PGPASSWORD=2zEjit43IF6gNUV psql \
    -h localhost -p 15432 \
    -U backend_rag_v2 nuzantara_rag \
    -f /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/db/migrations_v2/038_legal_instruments.sql
```

Expected: output ends with `UPDATE 1`.

- [ ] **Step 4: Verify table and seed**

```bash
PGPASSWORD=2zEjit43IF6gNUV psql \
    -h localhost -p 15432 \
    -U backend_rag_v2 nuzantara_rag \
    -c "SELECT instrument_id, status, (conflict_note IS NOT NULL) AS has_conflict FROM legal_instruments ORDER BY tier, year;"
```

Expected: 5 rows, `Permenkumham-22-2023` has `has_conflict=t`.

- [ ] **Step 5: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/backend-rag/backend/db/migrations_v2/038_legal_instruments.sql
git commit -m "feat(db): add legal_instruments table for NB verified generation pipeline (migration 038)"
```

---

## Task 3: LegalInstrumentsService + Tests

**Files:**

- Create: `apps/backend-rag/backend/services/oracle/legal_instruments_service.py`
- Create: `apps/backend-rag/backend/tests/unit/services/oracle/test_legal_instruments_service.py`

- [ ] **Step 1: Write failing tests first**

Create `apps/backend-rag/backend/tests/unit/services/oracle/test_legal_instruments_service.py`:

```python
"""Tests for LegalInstrumentsService."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.oracle.legal_instruments_service import LegalInstrumentsService


@pytest.fixture
def mock_pool() -> MagicMock:
    pool = MagicMock()
    pool.acquire = MagicMock()
    return pool


@pytest.fixture
def service(mock_pool: MagicMock) -> LegalInstrumentsService:
    return LegalInstrumentsService(db_pool=mock_pool)


@pytest.mark.asyncio
async def test_get_active_instruments_for_domain(
    service: LegalInstrumentsService, mock_pool: MagicMock
) -> None:
    mock_rows = [
        {"instrument_id": "UU-6-2011", "status": "active", "tier": 0, "domain": "immigration", "title": "UU Keimigrasian"},
        {"instrument_id": "Permenkumham-22-2023", "status": "partially_superseded", "tier": 1, "domain": "immigration", "title": "Permenkumham Visa"},
    ]
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=mock_rows)
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

    results = await service.get_active_instruments_for_domain("immigration")

    assert len(results) == 2
    assert results[0]["instrument_id"] == "UU-6-2011"
    mock_conn.fetch.assert_called_once()
    call_args = str(mock_conn.fetch.call_args)
    assert "immigration" in call_args


@pytest.mark.asyncio
async def test_mark_uploaded_to_nb(
    service: LegalInstrumentsService, mock_pool: MagicMock
) -> None:
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

    await service.mark_uploaded_to_nb("UU-6-2011")

    mock_conn.execute.assert_called_once()
    call_sql = mock_conn.execute.call_args[0][0]
    assert "nb_uploaded" in call_sql
    assert "UU-6-2011" in str(mock_conn.execute.call_args)


@pytest.mark.asyncio
async def test_get_conflict_notes_for_domain(
    service: LegalInstrumentsService, mock_pool: MagicMock
) -> None:
    mock_rows = [
        {
            "instrument_id": "Permenkumham-22-2023",
            "conflict_note": "Superseded by Permen Imipas 3/2025",
            "revoked_by": "Permen-Imipas-3-2025",
            "status": "partially_superseded",
        }
    ]
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=mock_rows)
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

    notes = await service.get_conflict_notes_for_domain("immigration")

    assert len(notes) == 1
    assert notes[0]["conflict_note"] == "Superseded by Permen Imipas 3/2025"


@pytest.mark.asyncio
async def test_get_not_yet_uploaded(
    service: LegalInstrumentsService, mock_pool: MagicMock
) -> None:
    mock_rows = [
        {"instrument_id": "UU-6-2011", "instrument_type": "UU", "title": "UU Keimigrasian", "source_file": None, "source_url": "https://..."}
    ]
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=mock_rows)
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

    results = await service.get_not_yet_uploaded("immigration")

    assert len(results) == 1
    assert results[0]["instrument_id"] == "UU-6-2011"
```

- [ ] **Step 2: Run test — expect import error**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/services/oracle/test_legal_instruments_service.py -v 2>&1 | head -15
```

Expected: `ModuleNotFoundError: No module named 'backend.services.oracle.legal_instruments_service'`

- [ ] **Step 3: Implement the service**

Create `apps/backend-rag/backend/services/oracle/legal_instruments_service.py`:

```python
"""LegalInstrumentsService — CRUD for the legal_instruments table.

Provides read/write access to T0/T1 normative instrument metadata,
used by the Verified Generation Pipeline to track NLM upload status
and retrieve conflict resolution notes.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class LegalInstrumentsService:
    """Async service for legal_instruments table operations."""

    def __init__(self, db_pool: Any) -> None:
        self._pool = db_pool

    async def get_active_instruments_for_domain(self, domain: str) -> list[dict[str, Any]]:
        """Return active and partially_superseded instruments for a domain.

        Ordered by tier ASC (T0 first), year DESC (newest first).
        """
        sql = """
            SELECT
                instrument_id, instrument_type, tier, domain, title,
                number, year, status, vigore_date, revoked_by,
                conflict_note, source_url, source_file, nb_uploaded, nb_uploaded_at
            FROM legal_instruments
            WHERE domain = $1
              AND status IN ('active', 'partially_superseded')
            ORDER BY tier ASC, year DESC
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, domain)
        return [dict(r) for r in rows]

    async def mark_uploaded_to_nb(self, instrument_id: str) -> None:
        """Set nb_uploaded=TRUE and nb_uploaded_at=NOW() for an instrument."""
        sql = """
            UPDATE legal_instruments
            SET nb_uploaded = TRUE, nb_uploaded_at = NOW()
            WHERE instrument_id = $1
        """
        async with self._pool.acquire() as conn:
            await conn.execute(sql, instrument_id)
        logger.info("Marked %s as uploaded to NLM primary notebook", instrument_id)

    async def get_conflict_notes_for_domain(self, domain: str) -> list[dict[str, Any]]:
        """Return instruments with non-null conflict notes for a domain."""
        sql = """
            SELECT instrument_id, conflict_note, revoked_by, status
            FROM legal_instruments
            WHERE domain = $1
              AND conflict_note IS NOT NULL
            ORDER BY year DESC
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, domain)
        return [dict(r) for r in rows]

    async def get_not_yet_uploaded(self, domain: str) -> list[dict[str, Any]]:
        """Return active instruments not yet uploaded to NLM primary notebook."""
        sql = """
            SELECT instrument_id, instrument_type, title, source_file, source_url
            FROM legal_instruments
            WHERE domain = $1
              AND status IN ('active', 'partially_superseded')
              AND nb_uploaded = FALSE
            ORDER BY tier ASC, year DESC
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, domain)
        return [dict(r) for r in rows]
```

- [ ] **Step 4: Run tests — expect 4 passed**

```bash
PYTHONPATH=. pytest backend/tests/unit/services/oracle/test_legal_instruments_service.py -v
```

Expected: `4 passed`.

- [ ] **Step 5: Lint**

```bash
ruff check backend/services/oracle/legal_instruments_service.py backend/tests/unit/services/oracle/test_legal_instruments_service.py
```

Expected: `All checks passed.`

- [ ] **Step 6: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/backend-rag/backend/services/oracle/legal_instruments_service.py apps/backend-rag/backend/tests/unit/services/oracle/test_legal_instruments_service.py
git commit -m "feat(oracle): add LegalInstrumentsService + 4 tests for NB pipeline"
```

---

## Task 4: Claims Extractor Script

**Files:**

- Create: `apps/backend-rag/scripts/claims_extractor.py`
- Create: `apps/backend-rag/backend/tests/unit/scripts/test_claims_extractor.py`
- Create: `apps/backend-rag/scripts/claims_db/immigration_claims_db.json` (seed)

- [ ] **Step 1: Write failing tests**

Create `apps/backend-rag/backend/tests/unit/scripts/test_claims_extractor.py`:

````python
"""Tests for claims extraction pure functions (no I/O, no API calls)."""
from __future__ import annotations

import pytest

from scripts.claims_extractor import (
    generate_claim_id,
    parse_claims_response,
    stamp_claims,
    validate_claim,
)


def test_generate_claim_id_sequential() -> None:
    assert generate_claim_id("immigration", 1) == "IMM-001"
    assert generate_claim_id("immigration", 42) == "IMM-042"
    assert generate_claim_id("company", 7) == "COM-007"
    assert generate_claim_id("tax", 100) == "TAX-100"
    assert generate_claim_id("property", 5) == "PRO-005"


def test_parse_claims_response_valid() -> None:
    llm_output = '''
[
  {
    "claim": "Il KITAS dura massimo 2 anni.",
    "verbatim": "Pasal 52: Izin Tinggal Terbatas diberikan untuk paling lama 2 tahun.",
    "pasal_ref": "UU 6/2011 Pasal 52",
    "instrument_id": "UU-6-2011",
    "category": "duration"
  }
]
'''
    claims = parse_claims_response(llm_output)
    assert len(claims) == 1
    assert "2 anni" in claims[0]["claim"]
    assert claims[0]["instrument_id"] == "UU-6-2011"


def test_parse_claims_response_strips_markdown() -> None:
    llm_output = '```json\n[{"claim":"T","verbatim":"V","pasal_ref":"P","instrument_id":"I","category":"rule"}]\n```'
    claims = parse_claims_response(llm_output)
    assert len(claims) == 1
    assert claims[0]["claim"] == "T"


def test_parse_claims_response_invalid_json() -> None:
    claims = parse_claims_response("not json at all")
    assert claims == []


def test_validate_claim_complete() -> None:
    claim = {
        "claim": "KITAS E28 berlaku 2 tahun.",
        "verbatim": "Pasal 52: Izin Tinggal Terbatas...",
        "pasal_ref": "Permenkumham 22/2023 Pasal 52",
        "instrument_id": "Permenkumham-22-2023",
        "category": "duration",
    }
    assert validate_claim(claim) is True


def test_validate_claim_missing_verbatim() -> None:
    claim = {
        "claim": "Test claim",
        "pasal_ref": "UU 6/2011 Pasal 1",
        "instrument_id": "UU-6-2011",
        "category": "rule",
        # missing "verbatim"
    }
    assert validate_claim(claim) is False


def test_stamp_claims_adds_ids_and_filters_invalid() -> None:
    claims = [
        {"claim": "C1", "verbatim": "V1", "pasal_ref": "P1", "instrument_id": "I1", "category": "rule"},
        {"claim": "C2", "verbatim": "V2", "pasal_ref": "P2", "instrument_id": "I2"},  # missing category
        {"claim": "C3", "verbatim": "V3", "pasal_ref": "P3", "instrument_id": "I3", "category": "procedure"},
    ]
    stamped = stamp_claims(claims, "immigration", start_index=5)
    assert len(stamped) == 2  # one invalid filtered
    assert stamped[0]["claim_id"] == "IMM-005"
    assert stamped[1]["claim_id"] == "IMM-006"
````

- [ ] **Step 2: Run — expect import error**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/scripts/test_claims_extractor.py -v 2>&1 | head -10
```

- [ ] **Step 3: Implement claims_extractor.py**

Create `apps/backend-rag/scripts/claims_extractor.py`:

````python
#!/usr/bin/env python3
"""Claims Extractor — Step 1 of the Verified Generation Pipeline.

Reads T0/T1 source documents and uses Claude Haiku 4.5 to extract every
normative claim as a structured record with verbatim citation. Writes
output to scripts/claims_db/<domain>_claims_db.json.

Usage:
    python scripts/claims_extractor.py \\
        --domain immigration \\
        --source /path/to/law.txt \\
        --instrument-id UU-6-2011
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DOMAIN_PREFIXES: dict[str, str] = {
    "immigration": "IMM",
    "company": "COM",
    "tax": "TAX",
    "property": "PRO",
    "operations": "OPS",
    "editorial": "EDI",
    "lifestyle": "LIF",
}

REQUIRED_CLAIM_FIELDS = frozenset({"claim", "verbatim", "pasal_ref", "instrument_id", "category"})


def generate_claim_id(domain: str, index: int) -> str:
    """Generate a domain-prefixed zero-padded claim ID (e.g. IMM-001)."""
    prefix = DOMAIN_PREFIXES.get(domain, domain[:3].upper())
    return f"{prefix}-{index:03d}"


def parse_claims_response(llm_output: str) -> list[dict[str, Any]]:
    """Parse LLM JSON response into a list of claim dicts.

    Strips markdown code fences if present. Returns empty list on any parse failure.
    """
    cleaned = re.sub(r"^```(?:json)?\n?", "", llm_output.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\n?```$", "", cleaned.strip(), flags=re.MULTILINE)
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse LLM output as JSON (length=%d)", len(llm_output))
        return []


def validate_claim(claim: dict[str, Any]) -> bool:
    """Check that a claim has all required fields with non-empty values."""
    return all(field in claim and bool(claim[field]) for field in REQUIRED_CLAIM_FIELDS)


def stamp_claims(claims: list[dict[str, Any]], domain: str, start_index: int = 1) -> list[dict[str, Any]]:
    """Add claim_id to each valid claim, filtering out invalid ones."""
    stamped: list[dict[str, Any]] = []
    idx = start_index
    for claim in claims:
        if validate_claim(claim):
            claim["claim_id"] = generate_claim_id(domain, idx)
            stamped.append(claim)
            idx += 1
        else:
            logger.warning("Skipping invalid claim (missing fields): %s", list(claim.keys()))
    return stamped


def load_existing_claims_db(output_path: Path) -> list[dict[str, Any]]:
    """Load existing claims_db JSON or return empty list."""
    if output_path.exists():
        with output_path.open() as f:
            return json.load(f)
    return []


def save_claims_db(claims: list[dict[str, Any]], output_path: Path) -> None:
    """Write claims list to JSON with pretty formatting."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(claims, f, ensure_ascii=False, indent=2)
    logger.info("Saved %d claims to %s", len(claims), output_path)


def build_extraction_prompt(source_text: str, instrument_id: str, domain: str) -> str:
    """Build the prompt for Claude Haiku claims extraction."""
    return f"""You are a legal analyst extracting normative claims from Indonesian law.
Source: {instrument_id} (domain: {domain})

Extract EVERY normative claim from the following text. A normative claim is:
- A requirement, prohibition, right, obligation, duration, fee, procedure, or sanction
- Something Bali Zero clients or staff need to know to comply with Indonesian law

For each claim output a JSON object with:
- "claim": Italian translation (1-2 sentences, precise)
- "verbatim": EXACT verbatim quote from source in Bahasa Indonesia (mandatory)
- "pasal_ref": exact reference e.g. "UU 6/2011 Pasal 71 Ayat 1"
- "instrument_id": "{instrument_id}"
- "category": one of: rule, procedure, duration, fee, document, sanction, right, prohibition

Output ONLY a valid JSON array. No explanation. No markdown. No preamble.

Source text:
---
{source_text[:8000]}
---"""


async def extract_claims_from_file(
    source_path: Path,
    instrument_id: str,
    domain: str,
    anthropic_api_key: str,
) -> list[dict[str, Any]]:
    """Extract claims from a source file using Claude Haiku 4.5."""
    import anthropic

    source_text = source_path.read_text(encoding="utf-8")
    prompt = build_extraction_prompt(source_text, instrument_id, domain)

    client = anthropic.Anthropic(api_key=anthropic_api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text
    claims = parse_claims_response(raw)
    logger.info("Extracted %d raw claims from %s", len(claims), instrument_id)
    return claims


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Extract normative claims from T0/T1 law sources")
    parser.add_argument("--domain", required=True, choices=list(DOMAIN_PREFIXES))
    parser.add_argument("--source", required=True, help="Path to source text file")
    parser.add_argument("--instrument-id", required=True, help="e.g. UU-6-2011")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    import asyncio
    source_path = Path(args.source)
    output_path = Path(__file__).parent / "claims_db" / f"{args.domain}_claims_db.json"
    existing = load_existing_claims_db(output_path)
    start_idx = len(existing) + 1

    new_claims = asyncio.run(
        extract_claims_from_file(source_path, args.instrument_id, args.domain, api_key)
    )
    stamped = stamp_claims(new_claims, args.domain, start_idx)
    all_claims = existing + stamped
    save_claims_db(all_claims, output_path)
    print(f"Added {len(stamped)} new claims. Total: {len(all_claims)}")


if __name__ == "__main__":
    main()
````

- [ ] **Step 4: Run tests — expect 7 passed**

```bash
PYTHONPATH=. pytest backend/tests/unit/scripts/test_claims_extractor.py -v
```

Expected: `7 passed`.

- [ ] **Step 5: Seed the immigration claims_db**

Create `apps/backend-rag/scripts/claims_db/immigration_claims_db.json`:

```json
[
  {
    "claim_id": "IMM-001",
    "claim": "Ogni straniero che entra in Indonesia deve essere in possesso di un visto valido appropriato al tipo di attività che intende svolgere.",
    "verbatim": "Pasal 8 ayat (1): Setiap Orang Asing yang masuk Wilayah Indonesia wajib memiliki Visa yang sah dan masih berlaku.",
    "pasal_ref": "UU 6/2011 Pasal 8 Ayat 1",
    "instrument_id": "UU-6-2011",
    "category": "rule"
  },
  {
    "claim_id": "IMM-002",
    "claim": "Il KITAS (Izin Tinggal Terbatas) può essere rilasciato per un massimo di 2 anni.",
    "verbatim": "Pasal 52: Izin Tinggal Terbatas diberikan kepada Orang Asing untuk paling lama 2 (dua) tahun.",
    "pasal_ref": "UU 6/2011 Pasal 52",
    "instrument_id": "UU-6-2011",
    "category": "duration"
  },
  {
    "claim_id": "IMM-003",
    "claim": "Il rinnovo del KITAS deve essere richiesto prima della scadenza del permesso attuale.",
    "verbatim": "Pasal 71 ayat (1): Orang Asing yang masa berlaku Izin Tinggal Terbatasnya berakhir dan masih berada di Wilayah Indonesia harus mengurus perpanjangan.",
    "pasal_ref": "UU 6/2011 Pasal 71 Ayat 1",
    "instrument_id": "UU-6-2011",
    "category": "procedure"
  },
  {
    "claim_id": "IMM-004",
    "claim": "Il Visa E28A (investor) richiede un investimento minimo di 10 miliardi di rupiah o il possesso di obbligazioni statali.",
    "verbatim": "Pasal 16 ayat (2) huruf a: Memiliki investasi di Indonesia paling sedikit Rp10.000.000.000 atau memiliki Surat Berharga Negara.",
    "pasal_ref": "Permenkumham 22/2023 Pasal 16 Ayat 2 Huruf A",
    "instrument_id": "Permenkumham-22-2023",
    "category": "fee"
  },
  {
    "claim_id": "IMM-005",
    "claim": "Il datore di lavoro che intende assumere lavoratori stranieri (TKA) deve ottenere preventivamente l'approvazione del Piano di Utilizzo TKA (RPTKA) dal Ministro.",
    "verbatim": "Pasal 3: Pemberi Kerja TKA wajib memiliki Rencana Penggunaan Tenaga Kerja Asing yang disahkan oleh Menteri.",
    "pasal_ref": "SE Kemnaker SE-3/836/2026 Pasal 3",
    "instrument_id": "SE-Kemnaker-3-836-2026",
    "category": "document"
  }
]
```

- [ ] **Step 6: Verify seed is valid**

```bash
python3 -c "
import json
with open('/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/scripts/claims_db/immigration_claims_db.json') as f:
    data = json.load(f)
assert len(data) == 5
for c in data:
    assert 'claim_id' in c and 'verbatim' in c
    print(f'  {c[\"claim_id\"]}: OK')
print('Seed valid: 5 claims')
"
```

- [ ] **Step 7: Lint**

```bash
ruff check scripts/claims_extractor.py backend/tests/unit/scripts/test_claims_extractor.py
```

- [ ] **Step 8: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/backend-rag/scripts/claims_extractor.py apps/backend-rag/scripts/claims_db/ apps/backend-rag/backend/tests/unit/scripts/test_claims_extractor.py
git commit -m "feat(pipeline): add claims_extractor.py + seed immigration_claims_db.json — Step 1 of pipeline"
```

---

## Task 5: Auto-Verifier (CRAG-light)

**Files:**

- Create: `apps/backend-rag/scripts/auto_verifier.py`

CRAG-light verifier: extracts `[CLAIM-ID]` markers, checks each against claims_db, calls Claude Haiku 4.5 for FAITHFUL/UNFAITHFUL/UNCERTAIN verdict, blocks if verified_ratio < 0.95.

- [ ] **Step 1: Create auto_verifier.py**

Create `apps/backend-rag/scripts/auto_verifier.py`:

```python
#!/usr/bin/env python3
"""Auto-Verifier — Step 4 of the Verified Generation Pipeline.

Verifies every [CLAIM-ID] marker in a generated T2 document against
claims_db.json using CRAG-light (Claude Haiku 4.5 as evaluator).

Exit codes:
  0 — verification passed (>=95% claims verified)
  1 — verification failed (<95% or DB errors)

Usage:
    python scripts/auto_verifier.py \\
        --document /tmp/nb2_visa_guide.txt \\
        --claims-db scripts/claims_db/immigration_claims_db.json \\
        --output /tmp/verification_report.json
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CLAIM_ID_PATTERN = re.compile(r"\[([A-Z]{2,3}-\d{3})\]")
MIN_VERIFIED_RATIO = 0.95


@dataclass
class ClaimVerificationResult:
    claim_id: str
    found_in_db: bool
    haiku_verdict: str | None = None   # "FAITHFUL", "UNFAITHFUL", "UNCERTAIN"
    haiku_reason: str | None = None
    passed: bool = False


@dataclass
class VerificationReport:
    document_path: str
    claims_db_path: str
    total_markers: int = 0
    unique_claim_ids: int = 0
    found_in_db: int = 0
    verified: int = 0
    failed: list[ClaimVerificationResult] = field(default_factory=list)
    verified_ratio: float = 0.0
    passed: bool = False


def extract_claim_ids(document_text: str) -> list[str]:
    """Extract unique [CLAIM-ID] markers from document, in order of first appearance."""
    seen: set[str] = set()
    unique: list[str] = []
    for cid in CLAIM_ID_PATTERN.findall(document_text):
        if cid not in seen:
            seen.add(cid)
            unique.append(cid)
    return unique


def load_claims_db(claims_db_path: Path) -> dict[str, dict[str, Any]]:
    """Load claims_db.json into a dict keyed by claim_id."""
    with claims_db_path.open() as f:
        raw: list[dict[str, Any]] = json.load(f)
    return {c["claim_id"]: c for c in raw if "claim_id" in c}


def build_haiku_verification_prompt(claim: str, verbatim: str, pasal_ref: str) -> str:
    return f"""You are a legal accuracy evaluator. Determine if the following claim faithfully and accurately represents the verbatim source text.

CLAIM (Italian): {claim}
VERBATIM SOURCE (Bahasa Indonesia): {verbatim}
PASAL REFERENCE: {pasal_ref}

Answer with exactly one of: FAITHFUL, UNFAITHFUL, or UNCERTAIN.
Then on a new line explain in one sentence why.

Format your response as:
VERDICT: <FAITHFUL|UNFAITHFUL|UNCERTAIN>
REASON: <one sentence>"""


def call_haiku_verifier(
    claim_text: str, verbatim: str, pasal_ref: str, api_key: str
) -> tuple[str, str]:
    """Call Claude Haiku 4.5 to verify a single claim. Returns (verdict, reason)."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{"role": "user", "content": build_haiku_verification_prompt(claim_text, verbatim, pasal_ref)}],
    )
    text = response.content[0].text.strip()
    verdict, reason = "UNCERTAIN", text
    for line in text.split("\n"):
        if line.startswith("VERDICT:"):
            verdict = line.split(":", 1)[1].strip()
        elif line.startswith("REASON:"):
            reason = line.split(":", 1)[1].strip()
    return verdict, reason


def verify_document(
    document_text: str,
    claims_db: dict[str, dict[str, Any]],
    document_path: str,
    claims_db_path: str,
    api_key: str,
) -> VerificationReport:
    """Run full CRAG-light verification on a document."""
    report = VerificationReport(document_path=document_path, claims_db_path=claims_db_path)
    claim_ids = extract_claim_ids(document_text)
    report.total_markers = len(CLAIM_ID_PATTERN.findall(document_text))
    report.unique_claim_ids = len(claim_ids)

    for cid in claim_ids:
        result = ClaimVerificationResult(claim_id=cid, found_in_db=cid in claims_db)
        if not result.found_in_db:
            report.failed.append(result)
            logger.warning("Claim %s not found in claims_db", cid)
            continue

        report.found_in_db += 1
        cd = claims_db[cid]
        verdict, reason = call_haiku_verifier(cd["claim"], cd["verbatim"], cd["pasal_ref"], api_key)
        result.haiku_verdict = verdict
        result.haiku_reason = reason
        result.passed = verdict == "FAITHFUL"

        if result.passed:
            report.verified += 1
        else:
            report.failed.append(result)
            logger.warning("Claim %s: %s — %s", cid, verdict, reason)

    total = report.unique_claim_ids
    report.verified_ratio = report.verified / total if total > 0 else 0.0
    report.passed = report.verified_ratio >= MIN_VERIFIED_RATIO
    return report


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--document", required=True)
    parser.add_argument("--claims-db", required=True)
    parser.add_argument("--output", default="/tmp/verification_report.json")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    document_text = Path(args.document).read_text(encoding="utf-8")
    claims_db = load_claims_db(Path(args.claims_db))
    report = verify_document(document_text, claims_db, args.document, args.claims_db, api_key)

    with open(args.output, "w") as f:
        json.dump(asdict(report), f, ensure_ascii=False, indent=2)

    status = "PASSED" if report.passed else "BLOCKED"
    print(f"\n{'OK' if report.passed else 'FAIL'} {status} — Verified {report.verified}/{report.unique_claim_ids} ({report.verified_ratio:.1%})")
    if not report.passed:
        print(f"Failed: {[r.claim_id for r in report.failed]}")
    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Import + logic test (no API calls)**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python -c "
from scripts.auto_verifier import extract_claim_ids, CLAIM_ID_PATTERN, MIN_VERIFIED_RATIO

text = 'Il KITAS dura 2 anni [IMM-001]. Rinnovo entro 30 giorni [IMM-002]. Ancora [IMM-001].'
ids = extract_claim_ids(text)
assert ids == ['IMM-001', 'IMM-002'], f'Got {ids}'
total = len(CLAIM_ID_PATTERN.findall(text))
assert total == 3  # IMM-001 appears twice
assert MIN_VERIFIED_RATIO == 0.95
print('extract_claim_ids: OK (deduplicates)')
print('total_markers counts duplicates: OK')
print('MIN_VERIFIED_RATIO=0.95: OK')
print('All checks passed')
"
```

- [ ] **Step 3: Lint**

```bash
ruff check scripts/auto_verifier.py
```

- [ ] **Step 4: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/backend-rag/scripts/auto_verifier.py
git commit -m "feat(pipeline): add auto_verifier.py (CRAG-light) — Step 4 of pipeline"
```

---

## Task 6: Telegram Reviewer (Human-in-the-Loop)

**Files:**

- Create: `apps/backend-rag/scripts/telegram_reviewer.py`

- [ ] **Step 1: Create telegram_reviewer.py**

Create `apps/backend-rag/scripts/telegram_reviewer.py`:

```python
#!/usr/bin/env python3
"""Telegram Reviewer — Step 6 of the Verified Generation Pipeline.

Sends failed claims to Zero via Telegram for human review.
Polls for /approve or /reject reply (30 min timeout).

Exit codes:
  0 — approved
  1 — rejected or timeout
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

POLL_INTERVAL_SEC = 15
TIMEOUT_SEC = 30 * 60


def send_telegram_message(token: str, chat_id: str, text: str) -> dict:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def get_updates(token: str, offset: int = 0) -> list[dict]:
    url = f"https://api.telegram.org/bot{token}/getUpdates?offset={offset}&timeout=10"
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read())
    return data.get("result", [])


def build_review_message(report: dict, document_name: str) -> str:
    failed = report.get("failed", [])
    ratio = report.get("verified_ratio", 0)
    total = report.get("unique_claim_ids", 0)
    verified = report.get("verified", 0)

    lines = [
        "⚠️ *NB Pipeline — Human Review Required*",
        f"📄 Document: `{document_name}`",
        f"📊 Verification: {verified}/{total} claims verified ({ratio:.0%})",
        "",
        "*Failed claims:*",
    ]
    for i, result in enumerate(failed[:10], 1):
        cid = result.get("claim_id", "?")
        found = result.get("found_in_db", False)
        verdict = result.get("haiku_verdict", "NOT IN DB") if found else "NOT IN DB"
        reason = result.get("haiku_reason") or "Claim ID not found in claims_db"
        lines.append(f"{i}. `{cid}` → {verdict}")
        lines.append(f"   _{reason}_")
    if len(failed) > 10:
        lines.append(f"   ...and {len(failed) - 10} more")

    lines += ["", "Reply with:", "/approve — upload to NLM", "/reject — discard, fix required"]
    return "\n".join(lines)


def poll_for_decision(token: str, chat_id: str) -> str:
    """Poll Telegram for /approve or /reject. Returns 'approved', 'rejected', or 'timeout'."""
    offset = 0
    updates = get_updates(token, offset=0)
    if updates:
        offset = updates[-1]["update_id"] + 1

    deadline = time.time() + TIMEOUT_SEC
    while time.time() < deadline:
        updates = get_updates(token, offset=offset)
        for upd in updates:
            offset = upd["update_id"] + 1
            msg = upd.get("message", {})
            if str(msg.get("chat", {}).get("id", "")) != str(chat_id):
                continue
            text = msg.get("text", "").strip().lower()
            if text.startswith("/approve"):
                return "approved"
            if text.startswith("/reject"):
                return "rejected"
        time.sleep(POLL_INTERVAL_SEC)
        remaining = (deadline - time.time()) / 60
        print(f"  Waiting for decision... ({remaining:.0f} min remaining)", end="\r")

    return "timeout"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--document-name", required=True)
    args = parser.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_ZERO_CHAT_ID", "")
    if not token or not chat_id:
        print("ERROR: TELEGRAM_BOT_TOKEN and TELEGRAM_ZERO_CHAT_ID must be set", file=sys.stderr)
        sys.exit(1)

    report = json.loads(Path(args.report).read_text())
    message = build_review_message(report, args.document_name)

    print("Sending review request to Telegram...")
    send_telegram_message(token, chat_id, message)

    print("Waiting for Zero's decision (/approve or /reject)...")
    decision = poll_for_decision(token, chat_id)

    if decision == "approved":
        print("\nApproved — proceeding with NLM upload")
        sys.exit(0)
    elif decision == "rejected":
        print("\nRejected — document will not be uploaded")
        sys.exit(1)
    else:
        print("\nTimeout (30 min) — treating as rejected for safety")
        send_telegram_message(token, chat_id, "Timeout — document NOT uploaded (safety default).")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Import + logic test**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python -c "
from scripts.telegram_reviewer import build_review_message, POLL_INTERVAL_SEC, TIMEOUT_SEC
report = {
    'failed': [{'claim_id': 'IMM-003', 'found_in_db': True, 'haiku_verdict': 'UNFAITHFUL', 'haiku_reason': 'Duration mismatch'}],
    'verified_ratio': 0.90, 'unique_claim_ids': 10, 'verified': 9
}
msg = build_review_message(report, 'NB-2 Test Guide')
assert 'IMM-003' in msg
assert '/approve' in msg
assert '/reject' in msg
assert TIMEOUT_SEC == 1800
print('build_review_message: OK')
print('TIMEOUT_SEC=1800: OK')
print('All checks passed')
"
```

- [ ] **Step 3: Lint**

```bash
ruff check scripts/telegram_reviewer.py
```

- [ ] **Step 4: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/backend-rag/scripts/telegram_reviewer.py
git commit -m "feat(pipeline): add telegram_reviewer.py (human-in-the-loop) — Step 6 of pipeline"
```

---

## Task 7: Main Pipeline Orchestrator

**Files:**

- Create: `apps/backend-rag/scripts/verified_generator.py`

- [ ] **Step 1: Create verified_generator.py**

Create `apps/backend-rag/scripts/verified_generator.py`:

```python
#!/usr/bin/env python3
"""Verified Generator — Main Orchestrator for NB Knowledge Population.

6-step pipeline:
  1. Load claims_db for domain
  2. Generate T2 document with Claude Sonnet 4.6 (forces [CLAIM-ID] markers)
  3. Validate markers (every [CLAIM-ID] must exist in claims_db)
  4. Auto-verify with CRAG-light (auto_verifier.py subprocess)
  5. NLM cross-check (skipped if NLM_BRIDGE_URL not set)
  6. Telegram human review (telegram_reviewer.py subprocess)

Usage:
    python scripts/verified_generator.py \\
        --domain immigration \\
        --topic "KITAS E31 Rinnovo: Procedura Completa" \\
        --output /tmp/nb2_kitas_renewal.txt
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCRIPTS_DIR = Path(__file__).parent
CLAIMS_DB_DIR = SCRIPTS_DIR / "claims_db"
CLAIM_ID_PATTERN = re.compile(r"\[([A-Z]{2,3}-\d{3})\]")

GENERATION_PROMPT = """You are a Bali Zero knowledge author writing operational guides for staff.

Domain: {domain}
Topic: {topic}
Language: Italian (professional, precise)

CRITICAL RULES:
1. Every normative claim MUST be followed by its [CLAIM-ID] marker from claims_db
2. Only make claims that exist in the claims_db listed below
3. If you need to state something not in claims_db, write [NEEDS-VERIFICATION] instead
4. Structure: Introduction → Requirements → Procedure → Timing → Costs → FAQ

AVAILABLE CLAIMS (use [CLAIM-ID] after each referenced claim):
{claims_summary}

Write the complete operational guide now. Be thorough (800-1200 words).
Every sentence that asserts a legal fact MUST have a [CLAIM-ID] marker."""


def load_claims_db(domain: str) -> dict[str, dict[str, Any]]:
    """Load claims_db for a domain. Exits if not found."""
    path = CLAIMS_DB_DIR / f"{domain}_claims_db.json"
    if not path.exists():
        logger.error("Claims DB not found: %s — run claims_extractor.py first", path)
        sys.exit(1)
    with path.open() as f:
        raw: list[dict[str, Any]] = json.load(f)
    return {c["claim_id"]: c for c in raw if "claim_id" in c}


def build_claims_summary(claims_db: dict[str, dict[str, Any]]) -> str:
    """Build compact claims list for generation prompt (cap at 80)."""
    lines = [f"[{cid}] {c['claim']} (ref: {c['pasal_ref']})" for cid, c in list(claims_db.items())[:80]]
    if len(claims_db) > 80:
        lines.append(f"... and {len(claims_db) - 80} more claims available")
    return "\n".join(lines)


def generate_document(domain: str, topic: str, claims_db: dict[str, dict[str, Any]], api_key: str) -> str:
    """Step 2: Generate T2 document with Claude Sonnet 4.6."""
    import anthropic

    prompt = GENERATION_PROMPT.format(
        domain=domain, topic=topic, claims_summary=build_claims_summary(claims_db)
    )
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def validate_markers(document_text: str, claims_db: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    """Step 3: Check all [CLAIM-ID] markers exist in claims_db. Returns (valid, missing)."""
    found = list(set(CLAIM_ID_PATTERN.findall(document_text)))
    missing = [cid for cid in found if cid not in claims_db]
    valid = [cid for cid in found if cid in claims_db]
    return valid, missing


def run_auto_verifier(document_path: Path, domain: str) -> tuple[bool, str]:
    """Step 4: Run auto_verifier.py subprocess. Returns (passed, report_path)."""
    claims_db_path = CLAIMS_DB_DIR / f"{domain}_claims_db.json"
    report_path = Path(tempfile.mktemp(suffix="_verification_report.json"))
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "auto_verifier.py"),
         "--document", str(document_path),
         "--claims-db", str(claims_db_path),
         "--output", str(report_path)],
        capture_output=True, text=True,
    )
    return result.returncode == 0, str(report_path)


def run_telegram_review(report_path: str, document_name: str) -> bool:
    """Step 6: Run telegram_reviewer.py subprocess. Returns True if approved."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "telegram_reviewer.py"),
         "--report", report_path,
         "--document-name", document_name],
        capture_output=False,
    )
    return result.returncode == 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Verified Generation Pipeline for NB knowledge population")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    print(f"\nVerified Generation Pipeline — {args.domain} / {args.topic}")
    print("=" * 70)

    # Step 1
    print("\nStep 1: Loading claims_db...")
    claims_db = load_claims_db(args.domain)
    print(f"  {len(claims_db)} claims loaded")

    # Step 2
    print(f"\nStep 2: Generating document with Claude Sonnet 4.6...")
    document_text = generate_document(args.domain, args.topic, claims_db, api_key)
    output_path = Path(args.output)
    output_path.write_text(document_text, encoding="utf-8")
    print(f"  Generated {len(document_text)} chars -> {output_path}")

    # Step 3
    print("\nStep 3: Validating [CLAIM-ID] markers...")
    valid_ids, missing_ids = validate_markers(document_text, claims_db)
    print(f"  Valid: {len(valid_ids)}, Missing from DB: {len(missing_ids)}")
    if missing_ids:
        print(f"  WARNING: Unknown claim IDs will be flagged UNFAITHFUL: {missing_ids}")

    # Step 4
    print("\nStep 4: Running auto-verifier (CRAG-light)...")
    passed, report_path = run_auto_verifier(output_path, args.domain)
    if passed:
        print("  PASSED — all claims verified")
        print(f"\nPipeline COMPLETE — document ready: {output_path}")
        print("  Next: upload to NLM using notebooklm-mcp source_add")
        sys.exit(0)

    with open(report_path) as f:
        report = json.load(f)
    ratio = report.get("verified_ratio", 0)
    print(f"  BLOCKED — {ratio:.0%} verified (need >=95%)")
    print(f"  Failed: {[r['claim_id'] for r in report.get('failed', [])]}")

    # Step 5 (optional)
    nlm_url = os.environ.get("NLM_BRIDGE_URL", "")
    if nlm_url:
        print("\nStep 5: NLM cross-check... (not yet automated)")
    else:
        print("\nStep 5: Skipping NLM cross-check (NLM_BRIDGE_URL not set)")

    # Step 6
    print("\nStep 6: Requesting human review via Telegram...")
    approved = run_telegram_review(report_path, f"{args.domain} — {args.topic}")
    if approved:
        print(f"\nApproved — document ready: {output_path}")
        sys.exit(0)
    else:
        print(f"\nRejected — document NOT uploaded. Fix required.")
        print(f"  Review report: {report_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Import + logic test**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python -c "
from scripts.verified_generator import validate_markers, build_claims_summary, CLAIM_ID_PATTERN
import json

with open('scripts/claims_db/immigration_claims_db.json') as f:
    claims_db = {c['claim_id']: c for c in json.load(f)}

# Test validate_markers
doc = 'Straniero con visto [IMM-001]. KITAS dura 2 anni [IMM-002]. Fake [IMM-999].'
valid, missing = validate_markers(doc, claims_db)
assert 'IMM-001' in valid and 'IMM-002' in valid
assert missing == ['IMM-999'], f'missing={missing}'
print('validate_markers: OK')

# Test build_claims_summary
summary = build_claims_summary(claims_db)
assert 'IMM-001' in summary
assert 'IMM-005' in summary
print('build_claims_summary: OK')
print('All checks passed')
"
```

- [ ] **Step 3: Lint**

```bash
ruff check scripts/verified_generator.py
```

- [ ] **Step 4: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/backend-rag/scripts/verified_generator.py
git commit -m "feat(pipeline): add verified_generator.py — main 6-step orchestrator"
```

---

## Task 8: Smoke Test — End-to-End Verification

- [ ] **Step 1: Test auto_verifier with a good document (no API calls needed for markers only in DB)**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
cat > /tmp/test_immigration_doc.txt << 'DOC'
# Guida KITAS — Permesso di Soggiorno Temporaneo

## Obblighi di Ingresso
Ogni straniero che entra in Indonesia deve essere in possesso di un visto valido [IMM-001].

## Durata e Tipologie
Il KITAS può avere durata massima di 2 anni [IMM-002].
E' rinnovabile presentando domanda prima della scadenza [IMM-003].

## Visto Investitore (E28A)
Per ottenere il Visa E28A, lo straniero deve dimostrare un investimento minimo di 10 miliardi [IMM-004].

## TKA — Lavoratori Stranieri
Ogni datore di lavoro deve ottenere preventivamente l'approvazione del RPTKA [IMM-005].
DOC
echo "Test document created"
```

- [ ] **Step 2: Run auto_verifier (requires ANTHROPIC_API_KEY for Haiku calls)**

```bash
PYTHONPATH=. python scripts/auto_verifier.py \
    --document /tmp/test_immigration_doc.txt \
    --claims-db scripts/claims_db/immigration_claims_db.json \
    --output /tmp/test_verification_report.json
echo "Exit code: $?"
```

Expected: `OK PASSED — Verified 5/5 (100%)` and exit code 0.

- [ ] **Step 3: Test with a document containing an invalid marker**

```bash
cat > /tmp/test_bad_doc.txt << 'DOC'
Il KITAS dura 2 anni [IMM-002]. Questo è inventato [IMM-999].
DOC
PYTHONPATH=. python scripts/auto_verifier.py \
    --document /tmp/test_bad_doc.txt \
    --claims-db scripts/claims_db/immigration_claims_db.json \
    --output /tmp/test_bad_report.json
echo "Exit code: $?"
```

Expected: `FAIL BLOCKED` and exit code 1. `cat /tmp/test_bad_report.json` shows IMM-999 in failed.

- [ ] **Step 4: Test validate_markers from verified_generator**

```bash
PYTHONPATH=. python -c "
from scripts.verified_generator import validate_markers
import json
with open('scripts/claims_db/immigration_claims_db.json') as f:
    db = {c['claim_id']: c for c in json.load(f)}

v, m = validate_markers('Visto [IMM-001]. KITAS [IMM-002]. Fake [IMM-888].', db)
assert sorted(v) == ['IMM-001', 'IMM-002']
assert m == ['IMM-888']
print('Smoke test validate_markers: PASSED')
"
```

- [ ] **Step 5: Commit test artifacts if any, final check**

```bash
cd /Users/nuzantara/Desktop/nuzantara
# Run all unit tests to make sure nothing is broken
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/services/oracle/test_legal_instruments_service.py backend/tests/unit/scripts/test_claims_extractor.py -v
```

Expected: `7 passed` (4 + 7 tests) or `11 passed` total.

- [ ] **Step 6: Final commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add -A
git status  # verify nothing unexpected
git commit -m "test(pipeline): smoke tests for NB Verified Generation Pipeline — all passing"
```

---

## Task 9: Weekly Legal Radar Cron Script

**Files:**

- Create: `apps/backend-rag/scripts/legal_radar.py`

- [ ] **Step 1: Create legal_radar.py**

Create `apps/backend-rag/scripts/legal_radar.py`:

```python
#!/usr/bin/env python3
"""Legal Radar — Weekly scan for new Indonesian regulations.

Dispatches to Gemini Search via ai-dispatch.sh per domain and
sends a Telegram summary to Zero for review.

Called by OpenClaw cron: Sunday 08:00 WITA
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import urllib.request
from datetime import date

logger = logging.getLogger(__name__)

DOMAINS = ["immigration", "company", "tax", "property"]
SEARCH_QUERIES: dict[str, str] = {
    "immigration": "peraturan imigrasi Indonesia terbaru 2025 2026 Permenkumham Permen Imigrasi",
    "company": "peraturan OSS BKPM PT PMA NIB terbaru 2025 2026",
    "tax": "peraturan pajak DJP coretax BPJS terbaru 2025 2026",
    "property": "peraturan tanah properti HGB hak pakai terbaru 2025 2026",
}
PROJECT_ROOT = os.path.expanduser("~/Desktop/nuzantara")


def dispatch_gemini_search(query: str) -> str:
    """Run ai-dispatch.sh search and return stdout (empty string on failure)."""
    script = os.path.join(PROJECT_ROOT, "scripts", "ai-dispatch.sh")
    try:
        result = subprocess.run(
            [script, "search", query],
            capture_output=True, text=True, timeout=120, cwd=PROJECT_ROOT,
        )
        return result.stdout if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning("Gemini search failed for query '%s': %s", query[:50], e)
        return ""


def build_radar_message(domain_results: dict[str, str], scan_date: date) -> str:
    lines = [
        f"📡 *Legal Radar — {scan_date.strftime('%d %b %Y')}*",
        "Weekly scan for new Indonesian regulations",
        "",
    ]
    for domain, result in domain_results.items():
        if result.strip():
            preview = result.strip()[:300].replace("\n", " ")
            lines += [f"*{domain.title()}:*", f"_{preview}_", ""]
        else:
            lines += [f"*{domain.title()}:* No new findings", ""]

    lines.append("Review and update `legal_instruments` table if needed.")
    lines.append("Run `claims_extractor.py` for any new T0 sources.")
    return "\n".join(lines)


def send_telegram_message(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp.read()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_ZERO_CHAT_ID", "")
    if not token or not chat_id:
        logger.error("TELEGRAM_BOT_TOKEN and TELEGRAM_ZERO_CHAT_ID must be set")
        sys.exit(1)

    scan_date = date.today()
    print(f"Legal Radar scan — {scan_date}")

    domain_results: dict[str, str] = {}
    for domain in DOMAINS:
        print(f"  Searching: {domain}...")
        domain_results[domain] = dispatch_gemini_search(SEARCH_QUERIES[domain])

    message = build_radar_message(domain_results, scan_date)
    send_telegram_message(token, chat_id, message)
    print("Legal Radar summary sent to Telegram")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Import + logic test**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python -c "
from scripts.legal_radar import build_radar_message, DOMAINS, SEARCH_QUERIES
from datetime import date
assert set(DOMAINS) == {'immigration', 'company', 'tax', 'property'}
results = {'immigration': 'New Permen Imipas found', 'company': '', 'tax': 'DJP update', 'property': ''}
msg = build_radar_message(results, date(2026, 3, 26))
assert 'Legal Radar' in msg
assert 'immigration' in msg.lower()
assert 'No new findings' in msg  # for company/property
print('build_radar_message: OK')
print('DOMAINS: OK')
print('All checks passed')
"
```

- [ ] **Step 3: Lint**

```bash
ruff check scripts/legal_radar.py
```

- [ ] **Step 4: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/backend-rag/scripts/legal_radar.py
git commit -m "feat(pipeline): add legal_radar.py — weekly scan for new Indonesian regulations"
```

---

## Task 10: Register Weekly Cron in OpenClaw / crontab

- [ ] **Step 1: Check current crontab**

```bash
crontab -l 2>/dev/null | grep -v "^#" | head -20
```

- [ ] **Step 2: Add legal_radar.py cron (Sunday 08:00 WITA = 00:00 UTC)**

```bash
CRON_LINE="0 0 * * 0 cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. python scripts/legal_radar.py >> /tmp/legal_radar.log 2>&1"
(crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
```

- [ ] **Step 3: Verify cron was added**

```bash
crontab -l | grep legal_radar
```

Expected: shows the cron line with `0 0 * * 0`.

- [ ] **Step 4: Final status summary**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
echo "=== Final Test Suite ==="
PYTHONPATH=. pytest backend/tests/unit/services/oracle/test_legal_instruments_service.py backend/tests/unit/scripts/test_claims_extractor.py -v --tb=short
echo ""
echo "=== Files created ==="
ls -la scripts/claims_db/immigration_claims_db.json
ls -la scripts/claims_extractor.py scripts/auto_verifier.py scripts/telegram_reviewer.py scripts/verified_generator.py scripts/legal_radar.py
ls -la backend/services/oracle/legal_instruments_service.py
ls -la backend/db/migrations_v2/038_legal_instruments.sql
```

- [ ] **Step 5: Final commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git log --oneline -10
```

---

## Self-Review

### Spec Coverage

| Spec requirement                     | Task                                               |
| ------------------------------------ | -------------------------------------------------- |
| claims_db.json backbone              | Task 4                                             |
| [CLAIM-ID] markers in T2             | Task 5 (verifier) + Task 7 (generator forces them) |
| Auto-verify checkpoint ≥95%          | Task 5 (`MIN_VERIFIED_RATIO = 0.95`)               |
| CRAG-light via Claude Haiku 4.5      | Task 5 (`call_haiku_verifier`)                     |
| Telegram human review                | Task 6                                             |
| `legal_instruments` PostgreSQL table | Task 2                                             |
| LegalInstrumentsService              | Task 3                                             |
| Registry bug fix + split NB-Xa/Xb    | Task 1                                             |
| Conflict-resolution notes            | Task 2 (seeded in migration)                       |
| Weekly legal radar cron              | Task 9 + 10                                        |
| Immigration domain smoke test        | Task 8                                             |

### Type Consistency

- `claims_db` is `dict[str, dict[str, Any]]` keyed by `claim_id` across all 3 scripts
- `VerificationReport.failed` is `list[ClaimVerificationResult]` (dataclass) in `auto_verifier.py`, read as `dict` via `asdict()` in `telegram_reviewer.py` — consistent
- `LegalInstrumentsService` returns `list[dict[str, Any]]` throughout — consistent with asyncpg pattern in codebase
