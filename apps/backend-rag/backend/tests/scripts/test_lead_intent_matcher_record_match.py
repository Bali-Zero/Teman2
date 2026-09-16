"""`_record_match` binds each client id to the type its column declares.

Why this file exists rather than an assertion folded into the mirror tests:
the two UPDATEs in `_record_match` write the SAME client id to two columns of
DIFFERENT types, and asyncpg encodes every parameter against the column it is
bound to.

    lead_intents.matched_client_id   VARCHAR(20)   (migrations_v2/122)
    clients.id                       INTEGER

Every producer of `client["id"]` hands back the native integer — `clients.id`
on Fly for both `_resolve_client_by_phone` and `_fetch_recent_wa_touches`, and
`whatsapp_message_context.client_id` (bigint) on the Pro's local mirror. So the
first UPDATE needs the id as TEXT and the second needs it left ALONE, and a fix
that converts in one place while forgetting the other trades one DataError for
the other. Between the deploy and 2026-09-16 the text side was the broken one:
every scheduled pass died with `expected str, got int` and 0 of 170 captured
intents had ever been attributed to a client.

Both directions are asserted on purpose. The guilt assertion catches the bug
that actually shipped; the innocence assertion catches the over-correction
(a blanket `str()` on both parameters), which would fail against the integer
primary key instead — and no other test in the suite reads these bindings.

No client PII appears here: an id and a lead nanoid this system minted itself.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[5]
_MATCHER_PATH = _REPO_ROOT / "scripts" / "lead_intent_matcher.py"

_spec = importlib.util.spec_from_file_location("lead_intent_matcher", _MATCHER_PATH)
assert _spec is not None and _spec.loader is not None
lim = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lim)

_CLIENT_ID = 9790  # the integer the live matcher choked on, 2026-09-16
_LEAD_ID = "li_p7nz6ul6rq"


class _FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: Any) -> bool:
        return False


class _RecordingConn:
    """Records what `_record_match` would hand to asyncpg, in order."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def transaction(self) -> _FakeTransaction:
        return _FakeTransaction()

    async def execute(self, query: str, *args: Any) -> None:
        self.calls.append((query, args))


def _intent() -> dict[str, Any]:
    return {
        "id": _LEAD_ID,
        "source": "homepage_hero",
        "context": {},
        "utm": None,
        "fingerprint": None,
        "created_at": None,
    }


async def _record(match_method: str = "lead_id") -> _RecordingConn:
    conn = _RecordingConn()
    await lim._record_match(
        conn,
        intent=_intent(),
        client={"id": _CLIENT_ID, "lead_metadata": None},
        match_method=match_method,
    )
    return conn


@pytest.mark.asyncio
async def test_lead_intents_update_binds_the_client_id_as_text() -> None:
    """GUILT: the binding that failed every scheduled pass for months."""
    conn = await _record()

    query, args = conn.calls[0]
    assert "UPDATE lead_intents" in query
    assert "matched_client_id = $1" in query
    assert type(args[0]) is str, f"$1 must be str for VARCHAR(20), got {type(args[0])}"
    assert args[0] == str(_CLIENT_ID)
    assert len(args[0]) <= 20  # the column's declared width
    assert args[1] == _LEAD_ID


@pytest.mark.asyncio
async def test_clients_update_keeps_the_native_integer_id() -> None:
    """INNOCENCE: converting both parameters just moves the DataError."""
    conn = await _record()

    query, args = conn.calls[1]
    assert "UPDATE clients" in query
    assert "WHERE id = $3" in query
    assert type(args[2]) is int, f"$3 must stay int for the PK, got {type(args[2])}"
    assert args[2] == _CLIENT_ID


@pytest.mark.asyncio
async def test_both_updates_run_and_in_that_order() -> None:
    """The two bindings above describe the whole write, not a sample of it."""
    conn = await _record()

    assert len(conn.calls) == 2
    assert "UPDATE lead_intents" in conn.calls[0][0]
    assert "UPDATE clients" in conn.calls[1][0]
