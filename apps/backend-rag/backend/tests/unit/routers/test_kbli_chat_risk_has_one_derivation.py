"""The chat channel must derive a risk tier once, from the stores, or say so.

Until 2026-09-20 five places in this endpoint produced `risk_category` for the
same code and disagreed even about what ignorance is called: the `kbli_documents`
branch hardcoded `"Verify at OSS"` and stopped looking, the `kg_nodes` branch
defaulted to it, the Qdrant payload builder and the ILIKE fallback defaulted to
`"Unknown"`, and a hand-written answer table served tiers nobody sourced. Which
answer a client got depended on which store happened to hold the code.

The number that makes the first one a defect rather than a style complaint was
measured read-only inside the running image: `kbli_documents` carries no
`kategori_risiko` key on ANY of its 1,563 rows, while `kg_nodes` carries a value
on 1,383 of its 1,562 `kbli:` nodes. So the branch that wins for almost every
code was the one structurally incapable of answering, and it declined to ask the
store that could.

The innocence half is the expensive one here too. A cure that made the channel
LOUDER — inventing a tier where no store holds one, or overwriting a tombstone's
marker — would be worse than the silence it replaces, so every way of not knowing
is pinned: no pool, no row, an empty string, a raising query, a store that holds
the code but not the tier.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.routers import kbli_notebook_chat as chat
from backend.app.routers.kbli_notebook_chat import (
    _RISK_UNRESOLVED,
    _channel_risk,
    _resolve_code_from_stores,
)

KG_TIER = "Menengah Tinggi"


def _pool(*, doc_row=None, kg_row=None, error=None):
    """A pool whose two queries answer independently, as the real ones do."""
    conn = MagicMock()

    async def _fetchrow(sql, *args):
        if error is not None:
            raise error
        return kg_row if "kg_nodes" in sql else doc_row

    conn.fetchrow = AsyncMock(side_effect=_fetchrow)

    pool = MagicMock()

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool.acquire = _acquire
    return pool


def _doc(metadata: dict) -> dict:
    return {"kode_kbli": "56301", "judul": "AKTIVITAS BAR", "metadata": metadata}


def _kg(properties: dict, *, as_text: bool = False) -> dict:
    return {
        "entity_id": "kbli:56301",
        "name": "AKTIVITAS BAR",
        "properties": json.dumps(properties) if as_text else properties,
    }


# --------------------------------------------------------------------------
# GUILT — one derivation, and it reaches the tier we actually hold
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_documents_row_no_longer_hardcodes_ignorance_over_a_known_tier():
    """The old code returned "Verify at OSS" here while kg_nodes held the tier."""
    pool = _pool(
        doc_row=_doc({"uraian": "Bar.", "pma_status": "TERBUKA"}),
        kg_row=_kg({"kategori_risiko": KG_TIER, "uraian": "Bar."}),
    )
    match = await _resolve_code_from_stores(pool, "56301")
    assert match is not None
    assert match.risk_category == KG_TIER


@pytest.mark.asyncio
async def test_kg_fallback_uses_the_same_derivation():
    pool = _pool(doc_row=None, kg_row=_kg({"kategori_risiko": KG_TIER}))
    match = await _resolve_code_from_stores(pool, "56301")
    assert match is not None
    assert match.risk_category == KG_TIER


@pytest.mark.asyncio
async def test_kg_properties_stored_as_text_are_decoded():
    pool = _pool(doc_row=None, kg_row=_kg({"kategori_risiko": KG_TIER}, as_text=True))
    match = await _resolve_code_from_stores(pool, "56301")
    assert match is not None
    assert match.risk_category == KG_TIER


@pytest.mark.asyncio
async def test_qdrant_unknown_is_folded_into_the_one_dialect(monkeypatch):
    """`_result_from_payload` is shared with public search and floors at "Unknown"."""
    monkeypatch.setattr(
        chat,
        "_get_kbli_payload_from_qdrant",
        AsyncMock(return_value={"kode_kbli": "56301", "judul": "AKTIVITAS BAR"}),
    )
    match = await _resolve_code_from_stores(_pool(), "56301")
    assert match is not None
    assert match.risk_category == _RISK_UNRESOLVED
    assert match.risk_category != "Unknown"


def test_channel_risk_precedence_is_the_argument_order():
    assert _channel_risk(None, "", KG_TIER) == KG_TIER
    assert _channel_risk("Rendah", KG_TIER) == "Rendah"


def test_channel_risk_folds_the_second_dialect_of_ignorance():
    assert _channel_risk("Unknown") == _RISK_UNRESOLVED
    assert _channel_risk("Unknown", KG_TIER) == KG_TIER


# --------------------------------------------------------------------------
# INNOCENCE — every way of not knowing stays silent instead of inventing
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_store_carries_the_code_means_no_match(monkeypatch):
    monkeypatch.setattr(chat, "_get_kbli_payload_from_qdrant", AsyncMock(return_value=None))
    assert await _resolve_code_from_stores(_pool(), "56301") is None


@pytest.mark.asyncio
async def test_a_dead_pool_still_reaches_qdrant(monkeypatch):
    monkeypatch.setattr(chat, "_get_kbli_payload_from_qdrant", AsyncMock(return_value=None))
    assert await _resolve_code_from_stores(None, "56301") is None


@pytest.mark.asyncio
async def test_a_raising_query_falls_through_instead_of_taking_the_turn_down(monkeypatch):
    monkeypatch.setattr(
        chat,
        "_get_kbli_payload_from_qdrant",
        AsyncMock(return_value={"kode_kbli": "56301", "judul": "AKTIVITAS BAR"}),
    )
    match = await _resolve_code_from_stores(_pool(error=RuntimeError("boom")), "56301")
    assert match is not None
    assert match.risk_category == _RISK_UNRESOLVED


@pytest.mark.asyncio
async def test_a_store_that_holds_the_code_but_not_the_tier_says_so():
    pool = _pool(
        doc_row=_doc({"uraian": "Bar.", "pma_status": "TERBUKA"}),
        kg_row=_kg({"uraian": "Bar."}),
    )
    match = await _resolve_code_from_stores(pool, "56301")
    assert match is not None
    assert match.risk_category == _RISK_UNRESOLVED


@pytest.mark.asyncio
async def test_an_empty_tier_string_is_not_a_tier():
    pool = _pool(doc_row=None, kg_row=_kg({"kategori_risiko": "   "}))
    match = await _resolve_code_from_stores(pool, "56301")
    assert match is not None
    assert match.risk_category == _RISK_UNRESOLVED


@pytest.mark.asyncio
async def test_the_pma_tuple_travels_with_the_record_that_certifies_it():
    """A located verdict survives only with its whole tuple, and that is the
    ASYMMETRY this cure exists for: `_PMADisclosure._withhold_unverified_pma`
    runs `mode="before"` on every construction, so even the old hand-written
    table could not publish an unsourced ownership verdict — the model held it.
    Nothing equivalent guards the risk tier, which is why its derivation has to
    be made single at the source instead of at the response model."""
    pool = _pool(
        doc_row=_doc(
            {
                "uraian": "Bar.",
                "pma_status": "TERBUKA",
                "pma_max_asing": 100,
                "pma_verification_status": "located",
                "pma_official_basis": "Perpres 10/2021 Pasal 3(1)(d)",
                "pma_source_vintage": "2021-05-25",
                "pma_cap_verified": True,
            }
        ),
        kg_row=_kg({"kategori_risiko": KG_TIER}),
    )
    match = await _resolve_code_from_stores(pool, "56301")
    assert match is not None
    assert match.pma_status == "TERBUKA"
    assert match.pma_official_basis == "Perpres 10/2021 Pasal 3(1)(d)"
    assert match.risk_category == KG_TIER


@pytest.mark.asyncio
async def test_a_partial_pma_tuple_is_withheld_while_the_risk_tier_is_not():
    """The two halves of the same record fail differently, measured here rather
    than asserted in prose: an ownership verdict with no locator is withheld by
    the model, and a risk tier is passed through verbatim by it."""
    pool = _pool(
        doc_row=_doc({"uraian": "Bar.", "pma_status": "TERBUKA"}),
        kg_row=_kg({"kategori_risiko": "a tier nobody sourced"}),
    )
    match = await _resolve_code_from_stores(pool, "56301")
    assert match is not None
    assert match.pma_status == "NOT_VERIFIED"
    assert match.pma_verification_status == "declared_gap"
    assert match.risk_category == "a tier nobody sourced"


@pytest.mark.asyncio
async def test_a_code_no_store_knows_is_not_answered_from_a_table(monkeypatch):
    """47901 used to be answered by a hand-written table. The table is gone; if
    every store lost the code tomorrow the channel abstains rather than invent."""
    monkeypatch.setattr(chat, "_get_kbli_payload_from_qdrant", AsyncMock(return_value=None))
    assert await _resolve_code_from_stores(_pool(), "47901") is None
