"""Tests for crm_kg document_linker — pure-logic + DB-mock coverage.

The real DB integration is tested via the migration smoke tests; here we
exercise the deterministic UUID generation, entity_type→lookup_col mapping,
edge-replacement semantics, and idempotent property merging. Heavy on
unit logic, light on infrastructure.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from backend.services.knowledge_graph.document_linker import (
    _NAMESPACE_BALIZERO_CRM,
    _company_uid,
    _person_uid,
    _upsert_node,
)

# ─── UUIDv5 determinism + privacy ───────────────────────────────────────


def test_person_uid_is_deterministic():
    """Same passport_number → same UUID across calls."""
    a = _person_uid("AB1234567")
    b = _person_uid("AB1234567")
    assert a is not None
    assert a == b
    assert isinstance(a, uuid.UUID)


def test_person_uid_is_namespaced():
    """UUIDs must derive from our private namespace (UUIDv5 contract)."""
    pid = _person_uid("AB1234567")
    expected = uuid.uuid5(
        _NAMESPACE_BALIZERO_CRM,
        f"person:{__import__('hashlib').sha256(b'AB1234567|').hexdigest()}",
    )
    assert pid == expected


def test_person_uid_normalizes_case_and_whitespace():
    """Passport "ab123" / " AB123 " / "AB123" must collapse to one node."""
    a = _person_uid("ab123")
    b = _person_uid(" AB123 ")
    c = _person_uid("AB123")
    assert a == b == c


def test_person_uid_handles_empty():
    """Empty/whitespace input → None (caller skips Person node)."""
    assert _person_uid(None) is None
    assert _person_uid("") is None
    assert _person_uid("   ") is None


def test_company_uid_normalizes_npwp_punctuation():
    """NPWP can be 01.234.567.8-901.000 or plain digits → same uid."""
    a = _company_uid("01.234.567.8-901.000")
    b = _company_uid("01234567890100")  # extra trailing 0 to match digits
    # Different digit strings → different uids (this is the desired behavior:
    # we DON'T silently merge typos)
    assert a != b
    # But same digit string with different punctuation → same uid
    c = _company_uid("01-234-567-8 901 000")
    assert a == c


def test_company_uid_rejects_non_digits():
    """NPWP must contain at least one digit, else None."""
    assert _company_uid("not-an-npwp") is None
    assert _company_uid("") is None
    assert _company_uid(None) is None


def test_salt_changes_uid(monkeypatch):
    """Setting CRM_KG_HASH_SALT must change the uid output (defense-in-depth)."""
    monkeypatch.delenv("CRM_KG_HASH_SALT", raising=False)
    no_salt = _person_uid("AB1234567")

    monkeypatch.setenv("CRM_KG_HASH_SALT", "secret-salt-2026")
    with_salt = _person_uid("AB1234567")

    assert no_salt != with_salt


def test_no_raw_passport_in_uid(monkeypatch):
    """Sanity: the raw passport string MUST NOT appear in the UUID bytes.
    UUIDv5 is a one-way hash — this is implicit, but we assert it explicitly
    because PII leakage via uuid bytes would be a UU PDP violation."""
    monkeypatch.delenv("CRM_KG_HASH_SALT", raising=False)
    pid = _person_uid("AB1234567")
    assert pid is not None
    assert b"AB1234567" not in pid.bytes
    assert "AB1234567" not in str(pid)


# ─── _upsert_node logic (mock asyncpg connection) ───────────────────────


@pytest.mark.asyncio
async def test_upsert_node_creates_when_missing():
    """No existing node for the lookup key → INSERT path."""
    conn = AsyncMock()
    new_uid = uuid.uuid4()
    conn.fetchrow = AsyncMock(side_effect=[
        None,  # SELECT existing returns nothing
        {"entity_id": new_uid},  # INSERT RETURNING
    ])

    result = await _upsert_node(
        conn,
        entity_type="crm_document",
        name="passport.pdf",
        properties={"document_type": "passport"},
        file_id="drive_file_123",
    )

    assert result == new_uid
    # Verify INSERT was called (second fetchrow)
    assert conn.fetchrow.call_count == 2
    insert_sql = conn.fetchrow.call_args_list[1][0][0]
    assert "INSERT INTO crm_kg_nodes" in insert_sql
    assert "RETURNING entity_id" in insert_sql


@pytest.mark.asyncio
async def test_upsert_node_updates_existing_and_merges_properties():
    """Re-upload same file → UPDATE path, properties merged not overwritten."""
    conn = AsyncMock()
    existing_uid = uuid.uuid4()
    conn.fetchrow = AsyncMock(return_value={
        "entity_id": existing_uid,
        "properties": {
            "nationality": "RUS",
            "document_type": "passport",
        },
    })
    conn.execute = AsyncMock()

    # Re-OCR finds new field "gender" but doesn't re-extract "nationality"
    result = await _upsert_node(
        conn,
        entity_type="crm_person",
        name="Marina P",
        properties={"gender": "F"},  # ONLY new field
        person_uid=uuid.uuid4(),
    )

    assert result == existing_uid
    # The UPDATE call should merge old + new, preserving nationality
    update_args = conn.execute.call_args[0]
    merged_props = update_args[2]
    assert merged_props["nationality"] == "RUS"  # preserved from existing
    assert merged_props["document_type"] == "passport"  # preserved
    assert merged_props["gender"] == "F"  # newly added


@pytest.mark.asyncio
async def test_upsert_node_strips_none_values():
    """OCR returning None for a field must not blank existing data.

    Common scenario: passport OCR captures gender first time. A later
    re-OCR (e.g. lower-quality scan) returns nationality=null. We should
    KEEP the previously-extracted nationality, not overwrite with null.
    """
    conn = AsyncMock()
    existing_uid = uuid.uuid4()
    conn.fetchrow = AsyncMock(return_value={
        "entity_id": existing_uid,
        "properties": {"nationality": "RUS", "gender": "F"},
    })
    conn.execute = AsyncMock()

    await _upsert_node(
        conn,
        entity_type="crm_person",
        name="Marina P",
        properties={
            "nationality": None,  # explicit None, must NOT overwrite
            "date_of_birth": "1990-01-01",  # new field
        },
        person_uid=uuid.uuid4(),
    )

    merged = conn.execute.call_args[0][2]
    assert merged["nationality"] == "RUS"  # NOT clobbered by None
    assert merged["gender"] == "F"  # untouched
    assert merged["date_of_birth"] == "1990-01-01"  # added


@pytest.mark.asyncio
async def test_upsert_node_raises_on_missing_lookup_value():
    """Caller must provide the right stable-key for the entity_type."""
    conn = AsyncMock()

    with pytest.raises(ValueError, match="missing lookup value"):
        await _upsert_node(
            conn,
            entity_type="crm_document",
            name="x.pdf",
            properties={},
            # file_id NOT provided → ValueError
        )


@pytest.mark.asyncio
async def test_upsert_node_uses_correct_lookup_column_per_type():
    """entity_type → lookup_col mapping must be consistent."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchrow.return_value = None
    new_uid = uuid.uuid4()
    conn.fetchrow = AsyncMock(side_effect=[None, {"entity_id": new_uid}])

    await _upsert_node(
        conn,
        entity_type="crm_practice",
        name="KITAS Marina",
        properties={},
        practice_id=42,
    )

    # SELECT should query by practice_id
    select_sql = conn.fetchrow.call_args_list[0][0][0]
    assert "practice_id = $1" in select_sql
    select_arg = conn.fetchrow.call_args_list[0][0][1]
    assert select_arg == 42


# ─── End-to-end logic (full kg_link_document flow with deep mocking) ────


@pytest.mark.asyncio
async def test_kg_link_document_passport_full_flow(monkeypatch):
    """Verify a passport document creates Document + Client + Person nodes
    and 2 direct edges (BELONGS_TO, DESCRIBES)."""
    from backend.services.knowledge_graph import document_linker

    # Track every node UPSERT (in order of call)
    upsert_calls: list[dict] = []
    edge_calls: list[dict] = []

    async def fake_upsert(conn, **kwargs):
        upsert_calls.append(kwargs)
        return uuid.uuid4()

    async def fake_edge(conn, **kwargs):
        edge_calls.append(kwargs)
        return 1

    monkeypatch.setattr(document_linker, "_upsert_node", fake_upsert)
    monkeypatch.setattr(document_linker, "_insert_edge", fake_edge)
    monkeypatch.setattr(
        document_linker, "_client_full_name",
        AsyncMock(return_value="Marina Pinyaylova"),
    )
    monkeypatch.setattr(
        document_linker, "_practice_name",
        AsyncMock(return_value=None),
    )

    # Mock pool / conn / transaction
    conn = AsyncMock()
    conn.execute = AsyncMock()  # for DELETE FROM crm_kg_edges
    pool = _make_pool_mock(conn)

    result = await document_linker.kg_link_document(
        pool,
        file_id="drive123",
        client_id=42,
        document_type="passport",
        extracted_fields={
            "passport_number": "AB7654321",
            "full_name": "Marina Pinyaylova",
            "nationality": "RUS",
            "date_of_birth": "1990-05-15",
        },
        drive_url="https://drive.google.com/file/d/drive123",
        filename="marina_passport.pdf",
    )

    assert result["ok"] is True
    # Document + Client + Person = 3 nodes
    assert result["nodes"] == 3
    # BELONGS_TO + DESCRIBES = 2 edges
    assert result["edges"] == 2

    # Document was upserted with file_id key
    assert any(c["entity_type"] == "crm_document" for c in upsert_calls)
    # Client was upserted with client_id key
    assert any(
        c["entity_type"] == "crm_client" and c.get("client_id") == 42
        for c in upsert_calls
    )
    # Person was upserted with person_uid (deterministic UUID)
    person_calls = [c for c in upsert_calls if c["entity_type"] == "crm_person"]
    assert len(person_calls) == 1
    assert person_calls[0]["person_uid"] == _person_uid("AB7654321")
    # Person properties contain only non-PII metadata (no passport_number)
    person_props = person_calls[0]["properties"]
    assert "passport_number" not in person_props
    assert person_props["nationality"] == "RUS"

    # Edges: BELONGS_TO + DESCRIBES, both edge_tier='direct'
    edge_types = {e["rel_type"] for e in edge_calls}
    assert edge_types == {"BELONGS_TO", "DESCRIBES"}
    assert all(e["edge_tier"] == "direct" for e in edge_calls)

    # DELETE-then-INSERT semantics: outgoing edges from doc were cleared
    delete_call = conn.execute.call_args_list[0]
    assert "DELETE FROM crm_kg_edges" in delete_call[0][0]


@pytest.mark.asyncio
async def test_kg_link_document_skips_person_when_no_passport(monkeypatch):
    """A `contract` document has no passport → no Person node, no DESCRIBES."""
    from backend.services.knowledge_graph import document_linker

    upsert_calls: list[dict] = []
    edge_calls: list[dict] = []

    async def fake_upsert(conn, **kwargs):
        upsert_calls.append(kwargs)
        return uuid.uuid4()

    async def fake_edge(conn, **kwargs):
        edge_calls.append(kwargs)
        return 1

    monkeypatch.setattr(document_linker, "_upsert_node", fake_upsert)
    monkeypatch.setattr(document_linker, "_insert_edge", fake_edge)
    monkeypatch.setattr(
        document_linker, "_client_full_name",
        AsyncMock(return_value="Marina Pinyaylova"),
    )
    monkeypatch.setattr(
        document_linker, "_practice_name",
        AsyncMock(return_value=None),
    )

    conn = AsyncMock()
    conn.execute = AsyncMock()
    pool = _make_pool_mock(conn)

    result = await document_linker.kg_link_document(
        pool,
        file_id="drive456",
        client_id=42,
        document_type="contract",
        extracted_fields={"some_field": "x"},  # no passport_number, no npwp
        filename="lease.pdf",
    )

    assert result["ok"] is True
    # Only Document + Client (no Person, no Company, no Practice)
    assert result["nodes"] == 2
    # Only BELONGS_TO
    assert result["edges"] == 1
    assert all(c["entity_type"] != "crm_person" for c in upsert_calls)
    assert all(c["entity_type"] != "crm_company" for c in upsert_calls)


@pytest.mark.asyncio
async def test_kg_link_document_swallows_exceptions(monkeypatch):
    """KG-linking failure must NOT propagate — OCR caller stays happy."""
    from backend.services.knowledge_graph import document_linker

    async def boom(*a, **kw):
        msg = "Simulated DB error"
        raise RuntimeError(msg)

    monkeypatch.setattr(document_linker, "_upsert_node", boom)
    monkeypatch.setattr(
        document_linker, "_client_full_name", AsyncMock(return_value="x"),
    )
    monkeypatch.setattr(
        document_linker, "_practice_name", AsyncMock(return_value=None),
    )

    conn = AsyncMock()
    conn.execute = AsyncMock()
    pool = _make_pool_mock(conn)

    result = await document_linker.kg_link_document(
        pool,
        file_id="x",
        client_id=1,
        document_type="passport",
        extracted_fields={},
    )

    assert result["ok"] is False
    assert "Simulated DB error" in result["error"]


# ─── Helpers ────────────────────────────────────────────────────────────


def _make_pool_mock(conn):
    """Build an asyncpg.Pool-like mock that yields the given conn from
    `async with pool.acquire()` and supports `async with conn.transaction()`."""
    pool = AsyncMock()

    class _Acquire:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *exc):
            return False

    class _Tx:
        async def __aenter__(self):
            return None

        async def __aexit__(self, *exc):
            return False

    pool.acquire = lambda: _Acquire()
    conn.transaction = lambda: _Tx()
    return pool
