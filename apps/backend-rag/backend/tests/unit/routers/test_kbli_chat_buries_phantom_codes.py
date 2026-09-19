"""The chat channel must bury a dead KBLI code, not describe it.

PR #6810 taught `inspect_kbli` that ten codes in the graph are KBLI-2020 numbers
KBLI 2025 does not carry, and to answer them with a tombstone. It taught only that
one consumer. `chat_kbli` — the path behind the WhatsApp bot, the surface clients
actually talk to — kept answering `74100` as a live regulated activity, because its
lookup selects from `kbli_documents` with no `licensing_status` filter and falls
back to `kg_nodes` when there is no row at all.

Two paths in that endpoint can produce a match — a code the client typed and an
activity keyword that routes to one — and since 2026-09-20 both resolve through
`_resolve_code_from_stores`. They converge on one variable, so the verdict is
applied once where they meet — and these tests drive that junction directly rather than the
whole chat turn, which would need an LLM gateway and an orchestrator to say nothing
more about the property under test.

The innocence half is the expensive one. The cure is worth ten codes and getting it
wrong costs 1,559, so every way of NOT knowing — no pool, no match, an illegible
answer, a catalogue below the floor, a query that raises — must return the match
exactly as it came in.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from backend.app.routers.kbli_notebook import KBLISearchResult, _tombstone_result
from backend.app.routers.kbli_notebook_chat import _bury_if_phantom
from backend.services.kbli_catalogue_membership import (
    CATALOGUE_FLOOR,
    PHANTOM_LICENSING_STATUS,
    TOMBSTONE_DESCRIPTION,
    TOMBSTONE_TITLE_SUFFIX,
)

FULL_CATALOGUE = 1563


def _match(code: str = "74100") -> KBLISearchResult:
    """A match carrying everything a phantom used to hand the LLM.

    Deliberately fully populated — a real `pma_status`, a real risk tier. A fixture
    that left these empty could not tell a tombstone apart from a blank result, and
    the assertion that matters is precisely that these do NOT survive.
    """
    return KBLISearchResult(
        code=code,
        title="Aktivitas Perancangan Khusus",
        description="Aktivitas perancangan khusus dan desain industri.",
        score=1.0,
        risk_category="Menengah Tinggi",
        pma_status="TERBUKA",
    )


def _pool(*, rows=None, error=None):
    conn = MagicMock()
    if error is not None:
        conn.fetch = AsyncMock(side_effect=error)
    else:
        conn.fetch = AsyncMock(return_value=rows)

    pool = MagicMock()

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool.acquire = _acquire
    return pool


def _rows(size=FULL_CATALOGUE, canonical=0):
    return [{"catalogue_size": size, "canonical_rows": canonical}]


# --------------------------------------------------------------------------
# GUILT — the phantom is buried before it reaches the model
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_phantom_match_is_replaced_by_a_tombstone():
    buried = await _bury_if_phantom(_pool(rows=_rows()), _match())

    assert buried is not None
    assert buried.code == "74100"
    assert buried.title.endswith(TOMBSTONE_TITLE_SUFFIX)
    assert buried.description == TOMBSTONE_DESCRIPTION
    assert buried.risk_category == PHANTOM_LICENSING_STATUS


@pytest.mark.asyncio
async def test_the_tombstone_carries_no_ownership_claim_forward():
    """An ownership verdict about a number nobody can register is meaningless.

    This is the assertion that discriminates: the incoming match says
    `pma_status: TERBUKA` — open to 100% foreign ownership — about an activity that
    cannot be registered on OSS at all. Annotating it would keep the false answer
    alive one layer down, wearing a warning label.
    """
    buried = await _bury_if_phantom(_pool(rows=_rows()), _match())

    assert buried.pma_status != "TERBUKA"
    assert buried.risk_category != "Menengah Tinggi"
    assert "Perancangan" not in buried.description


# --------------------------------------------------------------------------
# INNOCENCE — every way of not knowing returns the match untouched
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_canonical_code_is_returned_unchanged():
    match = _match("74115")
    result = await _bury_if_phantom(_pool(rows=_rows(canonical=1)), match)

    assert result is match


@pytest.mark.asyncio
async def test_no_pool_means_unknown_and_changes_nothing():
    match = _match()

    assert await _bury_if_phantom(None, match) is match


@pytest.mark.asyncio
async def test_no_match_stays_no_match():
    assert await _bury_if_phantom(_pool(rows=_rows()), None) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rows",
    [None, [], [{}], [{"catalogue_size": "nonsense", "canonical_rows": 0}]],
    ids=["none", "empty", "missing_keys", "non_integer"],
)
async def test_an_illegible_answer_is_unknown_not_absence(rows):
    match = _match()

    assert await _bury_if_phantom(_pool(rows=rows), match) is match


@pytest.mark.asyncio
async def test_a_catalogue_below_the_floor_convicts_nobody():
    """The expensive direction: one truncated table must not bury 1,559 codes."""
    match = _match()
    below = _rows(size=CATALOGUE_FLOOR - 1, canonical=0)

    assert await _bury_if_phantom(_pool(rows=below), match) is match


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        asyncpg.UndefinedTableError("relation does not exist"),
        asyncpg.InterfaceError("connection is closed"),
        RuntimeError("pool exhausted"),
    ],
    ids=["undefined_table", "interface_error", "generic"],
)
async def test_a_failing_lookup_never_takes_the_chat_turn_down(error):
    """A chat turn must survive a broken catalogue — and must not convict on one.

    Wider than the inspect path's arm on purpose. There, a connection fault earns a
    503 the client can retry; here there is no status code to return, only an answer
    to a person mid-conversation, so the degraded behaviour is the pre-cure answer
    rather than a dropped turn.
    """
    match = _match()

    assert await _bury_if_phantom(_pool(error=error), match) is match


# --------------------------------------------------------------------------
# The builder in isolation
# --------------------------------------------------------------------------


def test_the_tombstone_keeps_the_code_and_the_score():
    """Enough identity survives for the caller's dedupe and ranking to still work."""
    original = _match()
    stone = _tombstone_result(original)

    assert stone.code == original.code
    assert stone.score == original.score
    assert original.title in stone.title


# --------------------------------------------------------------------------
# The wiring — the tests above prove the helper, not that anyone calls it
# --------------------------------------------------------------------------


def test_the_endpoint_actually_calls_the_burial():
    """Without this, deleting the call site leaves every test above green.

    The helper is correct in isolation and reachable only from one line in
    `chat_kbli`. That is the exact shape of superscar #2 — a cure that exists and
    is not armed — so the call site is pinned by source, the same way this repo
    pins cache keys and duplicated constants.

    It also pins the ORDER, and that is not hypothetical: until 2026-09-20 the
    call sat BETWEEN the two paths that set `direct_kbli_match`, so a match
    injected by the activity-keyword route skipped the tombstone entirely. The
    burial must run after BOTH, or a phantom reached by the later one is
    described to a client as a live activity.
    """
    import inspect

    from backend.app.routers import kbli_notebook_chat

    source = inspect.getsource(kbli_notebook_chat)

    assert "await _bury_if_phantom(pool, direct_kbli_match)" in source, (
        "the chat endpoint no longer calls _bury_if_phantom — phantom KBLI codes "
        "are being described to clients as live activities again"
    )

    burial = source.index("await _bury_if_phantom(pool, direct_kbli_match)")
    for branch in (
        "_resolve_code_from_stores(pool, code)",
        "_resolve_code_from_stores(pool, target_code)",
    ):
        assert source.index(branch) < burial, (
            f"the {branch} branch now runs AFTER the burial, so a phantom resolved "
            "by it reaches the client unburied"
        )
