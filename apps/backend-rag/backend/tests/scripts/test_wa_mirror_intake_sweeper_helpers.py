"""Pure helper tests for the wa-mirror intake sweeper.

The end-to-end sweeper test needs the Pro's live ``nuzantara_dev`` schema. These
tests keep the phone-keyed CRM logic covered without touching a real database.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[5]
_SWEEPER_PATH = _REPO_ROOT / "scripts" / "wa_mirror_intake_sweeper.py"


def _load_sweeper():
    spec = importlib.util.spec_from_file_location("wms_helpers_under_test", _SWEEPER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeConn:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows or []
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.fetch_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.fetchval_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def execute(self, query: str, *args: Any) -> str:
        self.execute_calls.append((query, args))
        return "OK"

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.fetch_calls.append((query, args))
        return self.rows

    async def fetchval(self, query: str, *args: Any) -> int:
        self.fetchval_calls.append((query, args))
        return 9001


@pytest.mark.asyncio
async def test_upsert_client_by_phone_creates_placeholder_lead() -> None:
    sweeper = _load_sweeper()
    conn = FakeConn(rows=[])

    client_id = await sweeper._upsert_client_by_phone(
        conn,
        raw_phone="+62 812-0000-1111",
        push_name=None,
        assigned_to="ari@balizero.com",
        note_kind="direct message",
    )

    assert client_id == 9001
    assert conn.fetch_calls[0][1] == ("6281200001111", "+6281200001111")
    insert_args = conn.fetchval_calls[0][1]
    assert insert_args[0] == "Lead +6281200001111"
    assert insert_args[1] == "6281200001111"
    assert insert_args[3] == "ari@balizero.com"
    assert "raw message content not stored" in insert_args[5]


@pytest.mark.asyncio
async def test_upsert_client_by_phone_reuses_existing_client() -> None:
    sweeper = _load_sweeper()
    conn = FakeConn(rows=[{"id": 42, "full_name": "Maria Existing"}])

    client_id = await sweeper._upsert_client_by_phone(
        conn,
        raw_phone="0812 0000 1111",
        push_name="Ignored Better Name",
        assigned_to="ari@balizero.com",
    )

    assert client_id == 42
    assert conn.fetchval_calls == []
    assert not any("UPDATE clients" in q for q, _args in conn.execute_calls)


@pytest.mark.asyncio
async def test_upsert_client_by_phone_improves_junk_name_only() -> None:
    sweeper = _load_sweeper()
    conn = FakeConn(rows=[{"id": 42, "full_name": "Lead +6281200001111"}])

    client_id = await sweeper._upsert_client_by_phone(
        conn,
        raw_phone="0812 0000 1111",
        push_name="Maria Rossi",
        assigned_to="ari@balizero.com",
    )

    assert client_id == 42
    updates = [args for q, args in conn.execute_calls if "UPDATE clients" in q]
    assert updates == [("Maria Rossi", sweeper._CRM_ACTOR, 42)]


def test_direct_chat_keeps_phone_identity_for_crm_and_routing() -> None:
    sweeper = _load_sweeper()
    row = {
        "chat_type": "direct",
        "group_jid": None,
        "sender_phone": "+62 812-0000-1111",
        "counterpart_phone": None,
        "phone_number": None,
    }

    assert sweeper._is_direct_chat(row) is True
    assert sweeper._client_identity_phone(row) == "+62 812-0000-1111"
    assert sweeper._queue_sender_phone(row) == "+62 812-0000-1111"
    assert sweeper._source_context(row) == {
        "transport": "wa-mirror",
        "context_version": "wa-mirror-v1",
        "chat_type": "direct",
        "crm_identity_policy": "phone_keyed_direct_chat",
        "routing_identity_policy": "sender_phone_enabled",
        "sender_phone_forwarded": True,
    }


def test_group_chat_suppresses_participant_phone_identity() -> None:
    sweeper = _load_sweeper()
    row = {
        "chat_type": "group",
        "group_jid": "120363000000000000@g.us",
        "sender_phone": "+62 812-0000-1111",
        "counterpart_phone": None,
        "phone_number": None,
        "group_subject_snapshot": "Bali Zero Team Internal",
    }

    assert sweeper._is_direct_chat(row) is False
    assert sweeper._client_identity_phone(row) is None
    assert sweeper._queue_sender_phone(row) is None
    context = sweeper._source_context(row)
    assert context["transport"] == "wa-mirror"
    assert context["chat_type"] == "group"
    assert context["group_scope"] == "unclassified"
    assert context["crm_identity_policy"] == "disabled_for_group"
    assert context["routing_identity_policy"] == "group_participant_phone_suppressed"
    assert context["sender_phone_forwarded"] is False
    assert "group_jid_hash" in context
    assert "group_subject_hash" in context
    assert "120363000000000000@g.us" not in str(context)
    assert "Bali Zero Team Internal" not in str(context)


def test_group_jid_wins_over_inconsistent_direct_chat_type() -> None:
    sweeper = _load_sweeper()
    row = {
        "chat_type": "direct",
        "group_jid": "120363000000000000@g.us",
        "sender_phone": "+62 812-0000-1111",
    }

    assert sweeper._is_direct_chat(row) is False
    assert sweeper._client_identity_phone(row) is None
    assert sweeper._queue_sender_phone(row) is None


def test_legacy_missing_chat_scope_preserves_direct_behavior() -> None:
    sweeper = _load_sweeper()
    row = {"sender_phone": "+62 812-0000-1111"}

    assert sweeper._is_direct_chat(row) is True
    assert sweeper._client_identity_phone(row) == "+62 812-0000-1111"
    assert sweeper._queue_sender_phone(row) == "+62 812-0000-1111"
