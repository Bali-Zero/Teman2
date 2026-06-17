"""Unit tests for the FASE-4 sender-phone entity signal (m225, catalog v2).

PURE unit (no Postgres): the asyncpg pool/connection is faked, so these run on
any machine/CI. The DB-backed decision-matrix behaviour stays covered by the
on-Pro integration suite (test_intake_routing.py).

Locked behaviours:
  * normalize_sender_phone: +62 / leading-0 / bare-8 / spaces / separators.
  * _classify_decision slotting: strong > phone > fuzzy; phone NEVER
    auto-attaches; agree=boost, disagree=both surfaced, shared-phone=AMBIGUOUS.
  * resolve_entity wiring: phone query only when no strong identifier matched.
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.services.intake import routing as rt

# ---------------------------------------------------------------------------
# normalize_sender_phone
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+62 812-345-6789", "628123456789"),
        ("08123456789", "628123456789"),  # leading 0 -> 62
        ("8123456789", "628123456789"),  # bare 8... -> 62
        ("62812 345 6789", "628123456789"),
        ("+1 555 123 4567", "15551234567"),  # non-ID number passes through
        ("", None),
        (None, None),
        ("123", None),  # too short to be a phone
    ],
)
def test_normalize_sender_phone(raw: str | None, expected: str | None) -> None:
    assert rt.normalize_sender_phone(raw) == expected


# ---------------------------------------------------------------------------
# _classify_decision — phone slotting (pure)
# ---------------------------------------------------------------------------

def _strong(cid: int = 1) -> dict[str, Any]:
    return {"table": "clients", "id": cid, "name": "Strong Match",
            "method": "passport_number", "score": rt.CONF_STRONG_EXACT,
            "matched_value": "ZZ123"}


def _phone(cid: int = 2) -> dict[str, Any]:
    return {"table": "clients", "id": cid, "name": "Phone Match",
            "method": "sender_phone", "score": rt.CONF_PHONE_MATCH,
            "matched_value": "628123456789", "basis": "phone"}


def _fuzzy(cid: int, sim: float) -> dict[str, Any]:
    return {"table": "clients", "id": cid, "name": "Fuzzy Match",
            "method": "fuzzy_full_name", "score": sim, "matched_value": "Fuzzy"}


def test_phone_only_is_link_candidate_never_auto() -> None:
    decision, cands, reason = rt._classify_decision([], [], [_phone()])
    assert decision == rt.DECISION_LINK_CANDIDATE
    assert len(cands) == 1
    assert cands[0]["method"] == "sender_phone"
    assert cands[0]["score"] == rt.CONF_PHONE_MATCH
    assert "phone" in reason["reason"]


def test_strong_identifier_ignores_phone() -> None:
    decision, cands, _ = rt._classify_decision([_strong(1)], [], [_phone(2)])
    assert decision == rt.DECISION_AUTO_ATTACH
    assert cands == [_strong(1)]


def test_phone_and_fuzzy_agree_boosts() -> None:
    decision, cands, reason = rt._classify_decision(
        [], [_fuzzy(2, 0.82)], [_phone(2)]
    )
    assert decision == rt.DECISION_LINK_CANDIDATE
    assert len(cands) == 1
    assert cands[0]["id"] == 2
    assert cands[0]["score"] == pytest.approx(
        rt.CONF_PHONE_MATCH + rt.PHONE_NAME_AGREE_BOOST
    )
    # Boosted but still strictly below the strong-identifier confidence.
    assert cands[0]["score"] < rt.CONF_STRONG_EXACT
    assert cands[0]["method"] == "sender_phone+fuzzy_full_name"
    assert reason["name_sim"] == 0.82


def test_phone_and_fuzzy_disagree_surfaces_both() -> None:
    decision, cands, reason = rt._classify_decision(
        [], [_fuzzy(9, 0.85)], [_phone(2)]
    )
    assert decision == rt.DECISION_LINK_CANDIDATE
    assert [c["id"] for c in cands] == [2, 9]  # phone candidate first
    assert "disagree" in reason["reason"]


def test_shared_phone_is_ambiguous() -> None:
    decision, cands, reason = rt._classify_decision(
        [], [], [_phone(2), _phone(3)]
    )
    assert decision == rt.DECISION_AMBIGUOUS
    assert len(cands) == 2
    assert "share the sender phone" in reason["reason"]


def test_no_signals_still_no_match() -> None:
    # Regression: the pre-m225 paths are untouched when phone is absent.
    decision, cands, _ = rt._classify_decision([], [], [])
    assert decision == rt.DECISION_NO_MATCH
    assert cands == []


def test_fuzzy_only_path_unchanged() -> None:
    decision, cands, _ = rt._classify_decision([], [_fuzzy(5, 0.91)], [])
    assert decision == rt.DECISION_LINK_CANDIDATE
    assert cands[0]["id"] == 5


# ---------------------------------------------------------------------------
# resolve_entity wiring — fake pool/conn (no PG)
# ---------------------------------------------------------------------------

class FakeConn:
    """Minimal asyncpg.Connection stand-in: dispatches fetch() on query text."""

    def __init__(
        self,
        passport_rows: list[dict[str, Any]] | None = None,
        phone_rows: list[dict[str, Any]] | None = None,
        fuzzy_rows: list[dict[str, Any]] | None = None,
    ) -> None:
        self.passport_rows = passport_rows or []
        self.phone_rows = phone_rows or []
        self.fuzzy_rows = fuzzy_rows or []
        self.queries: list[str] = []

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.queries.append(query)
        if "passport_number" in query:
            return self.passport_rows
        if "phone_normalized" in query:
            return self.phone_rows
        if "similarity" in query:
            return self.fuzzy_rows
        return []


class FakePool:
    """Wraps a FakeConn behind the pool.acquire() async-context protocol."""

    def __init__(self, conn: FakeConn) -> None:
        self._conn = conn

    def acquire(self) -> Any:
        conn = self._conn

        class _Ctx:
            async def __aenter__(self) -> FakeConn:
                return conn

            async def __aexit__(self, *exc: Any) -> bool:
                return False

        return _Ctx()


@pytest.mark.asyncio
async def test_resolve_entity_phone_match_no_strong() -> None:
    conn = FakeConn(phone_rows=[{"id": 42, "full_name": "Wira Phone"}])
    out = await rt.resolve_entity(
        {}, "unknown", FakePool(conn), sender_phone="0812-345-6789"
    )
    assert out["decision"] == rt.DECISION_LINK_CANDIDATE
    assert out["subject_kind"] == "person"
    cand = out["candidates"][0]
    assert (cand["table"], cand["id"], cand["method"]) == ("clients", 42, "sender_phone")
    assert cand["score"] == rt.CONF_PHONE_MATCH
    # Both storage variants are probed (with and without the +).
    assert any("phone_normalized" in q for q in conn.queries)


@pytest.mark.asyncio
async def test_resolve_entity_strong_id_skips_phone_query() -> None:
    conn = FakeConn(
        passport_rows=[{"id": 7, "full_name": "Alice Strong"}],
        phone_rows=[{"id": 42, "full_name": "Wira Phone"}],
    )
    out = await rt.resolve_entity(
        {"passport_no": {"value": "ZZ9988770"}}, "passport",
        FakePool(conn), sender_phone="08123456789",
    )
    assert out["decision"] == rt.DECISION_AUTO_ATTACH
    assert out["candidates"][0]["id"] == 7
    # The phone signal must not even be queried when a strong ID matched.
    assert not any("phone_normalized" in q for q in conn.queries)


@pytest.mark.asyncio
async def test_resolve_entity_without_sender_phone_never_queries_phone() -> None:
    conn = FakeConn(phone_rows=[{"id": 42, "full_name": "Wira Phone"}])
    out = await rt.resolve_entity({}, "unknown", FakePool(conn))
    assert out["decision"] == rt.DECISION_NO_MATCH
    assert not any("phone_normalized" in q for q in conn.queries)


@pytest.mark.asyncio
async def test_resolve_entity_invalid_phone_is_inert() -> None:
    conn = FakeConn(phone_rows=[{"id": 42, "full_name": "Wira Phone"}])
    out = await rt.resolve_entity({}, "unknown", FakePool(conn), sender_phone="abc")
    assert out["decision"] == rt.DECISION_NO_MATCH
    assert not any("phone_normalized" in q for q in conn.queries)
