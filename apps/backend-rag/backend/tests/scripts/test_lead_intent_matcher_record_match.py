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
    """Records what `_record_match` would hand to asyncpg, in order.

    `claimed` is what the first UPDATE's `RETURNING id` yields: the intent's id
    when this caller won the row, None when another pass had already claimed
    it. That is the only difference between the two races, so it is the only
    knob these tests need.
    """

    def __init__(self, claimed: str | None = _LEAD_ID) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self._claimed = claimed

    def transaction(self) -> _FakeTransaction:
        return _FakeTransaction()

    async def fetchval(self, query: str, *args: Any) -> str | None:
        self.calls.append((query, args))
        return self._claimed

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


async def _record(
    match_method: str = "lead_id", *, claimed: str | None = _LEAD_ID
) -> tuple[_RecordingConn, bool]:
    conn = _RecordingConn(claimed=claimed)
    recorded = await lim._record_match(
        conn,
        intent=_intent(),
        client={"id": _CLIENT_ID, "lead_metadata": None},
        match_method=match_method,
    )
    return conn, recorded


@pytest.mark.asyncio
async def test_lead_intents_update_binds_the_client_id_as_text() -> None:
    """GUILT: the binding that failed every scheduled pass for months."""
    conn, _ = await _record()

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
    conn, _ = await _record()

    query, args = conn.calls[1]
    assert "UPDATE clients" in query
    assert "WHERE id = $3" in query
    assert type(args[2]) is int, f"$3 must stay int for the PK, got {type(args[2])}"
    assert args[2] == _CLIENT_ID


@pytest.mark.asyncio
async def test_both_updates_run_and_in_that_order() -> None:
    """The two bindings above describe the whole write, not a sample of it."""
    conn, _ = await _record()

    assert len(conn.calls) == 2
    assert "UPDATE lead_intents" in conn.calls[0][0]
    assert "UPDATE clients" in conn.calls[1][0]


# ----------------------------------------------------------------------
# The race. Found by an adversarial review of the type fix above, which is
# the change that made this code path reachable at all: before it, the first
# UPDATE never succeeded, so the second never ran.
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_lost_race_leaves_the_clients_row_untouched() -> None:
    """GUILT: the write that used to land on the WRONG client.

    `WHERE matched_client_id IS NULL` guards the first UPDATE. The second one
    is keyed on `clients.id` and has no such guard, so a pass arriving after
    another had already claimed the intent still wrote its `lead_metadata`
    patch — onto whichever client IT resolved. Two passes that disagree about
    the client attributed the same lead to both, last writer winning.

    `claimed=None` is exactly what `RETURNING id` yields in that case.
    """
    conn, recorded = await _record(claimed=None)

    assert recorded is False
    assert len(conn.calls) == 1, "the clients UPDATE must not run on a lost race"
    assert "UPDATE lead_intents" in conn.calls[0][0]
    assert not any("UPDATE clients" in q for q, _ in conn.calls)


@pytest.mark.asyncio
async def test_claiming_the_intent_reports_true_and_writes_both_rows() -> None:
    """INNOCENCE: the ordinary path is unchanged.

    Without this, a `return False` at the top of the function would satisfy
    the guilt test perfectly and stop the matcher writing anything at all.
    """
    conn, recorded = await _record()

    assert recorded is True
    assert len(conn.calls) == 2
    assert "UPDATE clients" in conn.calls[1][0]


@pytest.mark.asyncio
async def test_the_claim_is_read_from_returning_not_from_a_status_string() -> None:
    """The first statement must go through `fetchval` + `RETURNING id`.

    `conn.execute` hands back `"UPDATE 0"` / `"UPDATE 1"` — two strings one
    character apart, where a wrong parse fails OPEN and restores the bug. A
    returned id is unambiguous. `_RecordingConn.execute` cannot report a
    claim, so routing the first statement through it would break this.
    """
    conn, _ = await _record()

    first_query, _args = conn.calls[0]
    assert "RETURNING id" in first_query
