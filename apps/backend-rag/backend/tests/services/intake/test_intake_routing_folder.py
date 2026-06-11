"""Unit tests for the FASE-4 folder-name entity signal (m227, Drive intake).

PURE unit (no Postgres): the asyncpg pool/connection is faked, so these run on
any machine/CI. Mirrors test_intake_routing_phone.py (m225) — the folder signal
rides the same transport-hint slot in the decision matrix.

Locked behaviours:
  * _clean_folder_segment: decoration stripping, parenthetical suffixes,
    first-segment-only, <3 chars rejected.
  * _match_folder_name: only sim >= FUZZY_APPLY_THRESHOLD counts; one clear
    winner -> single CONF_FOLDER_MATCH hint; top-2 within the ambiguity margin
    -> both returned (AMBIGUOUS downstream).
  * _classify_decision: folder hint NEVER auto-attaches; agree=boost,
    disagree=both surfaced, >1 match=AMBIGUOUS; reason strings say
    "folder name" (phone strings unchanged — covered by the m225 suite).
  * resolve_entity wiring: folder consulted ONLY when no strong identifier and
    no sender-phone resolved.
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.services.intake import routing as rt

# ---------------------------------------------------------------------------
# _clean_folder_segment
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("BUDI/passport.jpg", "BUDI"),
        ("Jane Doe/kitas/scan.pdf", "Jane Doe"),
        ("###PERPANJANGAN KITAS JOHN DOE###/doc.pdf", "PERPANJANGAN KITAS JOHN DOE"),
        ("@arsip Cetak (2027)/x.pdf", "arsip Cetak"),
        ("file-at-root.pdf", "file-at-root.pdf"),
        ("ab/x.pdf", None),  # <3 chars after cleaning
        ("###/x.pdf", None),  # decorations only
        ("", None),
        (None, None),
    ],
)
def test_clean_folder_segment(raw: str | None, expected: str | None) -> None:
    assert rt._clean_folder_segment(raw) == expected


# ---------------------------------------------------------------------------
# _classify_decision — folder-hint slotting (pure)
# ---------------------------------------------------------------------------

def _strong(cid: int = 1) -> dict[str, Any]:
    return {"table": "clients", "id": cid, "name": "Strong Match",
            "method": "passport_number", "score": rt.CONF_STRONG_EXACT,
            "matched_value": "ZZ123"}


def _folder(cid: int = 2, table: str = "clients") -> dict[str, Any]:
    return {"table": table, "id": cid, "name": "Folder Match",
            "method": "folder_name", "score": rt.CONF_FOLDER_MATCH,
            "matched_value": "BUDI", "basis": "folder", "folder_sim": 0.82}


def _fuzzy(cid: int, sim: float) -> dict[str, Any]:
    return {"table": "clients", "id": cid, "name": "Fuzzy Match",
            "method": "fuzzy_full_name", "score": sim, "matched_value": "Fuzzy"}


def test_folder_only_is_link_candidate_never_auto() -> None:
    decision, cands, reason = rt._classify_decision([], [], [_folder()])
    assert decision == rt.DECISION_LINK_CANDIDATE
    assert len(cands) == 1
    assert cands[0]["method"] == "folder_name"
    assert cands[0]["score"] == rt.CONF_FOLDER_MATCH
    assert "folder name" in reason["reason"]
    assert "folder_score" in reason


def test_strong_identifier_ignores_folder() -> None:
    decision, cands, _ = rt._classify_decision([_strong(1)], [], [_folder(2)])
    assert decision == rt.DECISION_AUTO_ATTACH
    assert cands == [_strong(1)]


def test_folder_and_fuzzy_agree_boosts() -> None:
    decision, cands, reason = rt._classify_decision(
        [], [_fuzzy(2, 0.82)], [_folder(2)]
    )
    assert decision == rt.DECISION_LINK_CANDIDATE
    assert len(cands) == 1
    assert cands[0]["id"] == 2
    assert cands[0]["score"] == pytest.approx(
        rt.CONF_FOLDER_MATCH + rt.PHONE_NAME_AGREE_BOOST
    )
    assert cands[0]["score"] < rt.CONF_STRONG_EXACT
    assert cands[0]["method"] == "folder_name+fuzzy_full_name"
    assert "folder name" in reason["reason"]


def test_folder_and_fuzzy_disagree_surfaces_both() -> None:
    decision, cands, reason = rt._classify_decision(
        [], [_fuzzy(9, 0.85)], [_folder(2)]
    )
    assert decision == rt.DECISION_LINK_CANDIDATE
    assert [c["id"] for c in cands] == [2, 9]  # folder candidate first
    assert "disagree" in reason["reason"]


def test_shared_folder_is_ambiguous() -> None:
    decision, cands, reason = rt._classify_decision(
        [], [], [_folder(2), _folder(3)]
    )
    assert decision == rt.DECISION_AMBIGUOUS
    assert len(cands) == 2
    assert "share the folder name" in reason["reason"]


# ---------------------------------------------------------------------------
# _match_folder_name — candidate selection (monkeypatched fuzzy)
# ---------------------------------------------------------------------------

def _patch_fuzzy(monkeypatch: pytest.MonkeyPatch, per_table: dict[str, list[dict]]) -> None:
    async def _fake_fuzzy(conn: Any, table: str, name_col: str, name: str) -> list[dict]:
        return [dict(c) for c in per_table.get(table, [])]

    monkeypatch.setattr(rt, "_match_fuzzy_name", _fake_fuzzy)


@pytest.mark.asyncio
async def test_match_folder_name_single_winner(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_fuzzy(monkeypatch, {
        "clients": [{"table": "clients", "id": 7, "name": "Budi Santoso",
                     "method": "fuzzy_full_name", "score": 0.86, "matched_value": "BUDI"}],
        "companies": [],
    })
    out = await rt._match_folder_name(None, "BUDI/passport.jpg")
    assert len(out) == 1
    assert out[0]["method"] == "folder_name"
    assert out[0]["score"] == rt.CONF_FOLDER_MATCH
    assert out[0]["basis"] == "folder"
    assert out[0]["folder_sim"] == 0.86


@pytest.mark.asyncio
async def test_match_folder_name_weak_sim_is_noise(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_fuzzy(monkeypatch, {
        "clients": [{"table": "clients", "id": 7, "name": "Someone Else",
                     "method": "fuzzy_full_name", "score": 0.55, "matched_value": "BUDI"}],
        "companies": [],
    })
    assert await rt._match_folder_name(None, "BUDI/passport.jpg") == []


@pytest.mark.asyncio
async def test_match_folder_name_homonyms_return_both(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_fuzzy(monkeypatch, {
        "clients": [{"table": "clients", "id": 7, "name": "Budi W",
                     "method": "fuzzy_full_name", "score": 0.80, "matched_value": "BUDI"}],
        "companies": [{"table": "companies", "id": 4, "name": "PT Budi",
                       "method": "fuzzy_company_name", "score": 0.78, "matched_value": "BUDI"}],
    })
    out = await rt._match_folder_name(None, "BUDI/doc.pdf")
    assert len(out) == 2  # within ambiguity margin -> AMBIGUOUS downstream


@pytest.mark.asyncio
async def test_match_folder_name_no_path() -> None:
    assert await rt._match_folder_name(None, None) == []


# ---------------------------------------------------------------------------
# resolve_entity wiring — fake pool/conn (no PG)
# ---------------------------------------------------------------------------

class FakeConn:
    """asyncpg.Connection stand-in: dispatches fetch() on query text + table."""

    def __init__(
        self,
        passport_rows: list[dict[str, Any]] | None = None,
        phone_rows: list[dict[str, Any]] | None = None,
        client_fuzzy_rows: list[dict[str, Any]] | None = None,
        company_fuzzy_rows: list[dict[str, Any]] | None = None,
    ) -> None:
        self.passport_rows = passport_rows or []
        self.phone_rows = phone_rows or []
        self.client_fuzzy_rows = client_fuzzy_rows or []
        self.company_fuzzy_rows = company_fuzzy_rows or []
        self.queries: list[str] = []

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.queries.append(query)
        if "passport_number" in query:
            return self.passport_rows
        if "phone_normalized" in query:
            return self.phone_rows
        if "similarity" in query and "FROM clients" in query:
            return self.client_fuzzy_rows
        if "similarity" in query and "FROM companies" in query:
            return self.company_fuzzy_rows
        return []


class FakePool:
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
async def test_resolve_entity_folder_match_no_strong_no_phone() -> None:
    conn = FakeConn(client_fuzzy_rows=[{"id": 7, "name": "Budi Santoso", "sim": 0.84}])
    out = await rt.resolve_entity(
        {}, "unknown", FakePool(conn), source_path="BUDI/passport.jpg"
    )
    assert out["decision"] == rt.DECISION_LINK_CANDIDATE
    assert out["subject_kind"] == "person"
    cand = out["candidates"][0]
    assert (cand["table"], cand["id"], cand["method"]) == ("clients", 7, "folder_name")
    assert cand["score"] == rt.CONF_FOLDER_MATCH


@pytest.mark.asyncio
async def test_resolve_entity_strong_id_skips_folder_query() -> None:
    conn = FakeConn(
        passport_rows=[{"id": 7, "full_name": "Alice Strong"}],
        client_fuzzy_rows=[{"id": 9, "name": "Budi Santoso", "sim": 0.84}],
    )
    out = await rt.resolve_entity(
        {"passport_no": {"value": "ZZ9988770"}}, "passport",
        FakePool(conn), source_path="BUDI/passport.jpg",
    )
    assert out["decision"] == rt.DECISION_AUTO_ATTACH
    assert not any("similarity" in q for q in conn.queries)


@pytest.mark.asyncio
async def test_resolve_entity_phone_wins_over_folder() -> None:
    conn = FakeConn(
        phone_rows=[{"id": 42, "full_name": "Wira Phone"}],
        client_fuzzy_rows=[{"id": 7, "name": "Budi Santoso", "sim": 0.84}],
    )
    out = await rt.resolve_entity(
        {}, "unknown", FakePool(conn),
        sender_phone="08123456789", source_path="BUDI/passport.jpg",
    )
    assert out["decision"] == rt.DECISION_LINK_CANDIDATE
    assert out["candidates"][0]["method"] == "sender_phone"
    # Folder fuzzy never queried: phone resolved first.
    assert not any("similarity" in q for q in conn.queries)
