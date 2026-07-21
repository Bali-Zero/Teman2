"""Unit tests for the FASE-4 sender-phone entity signal (m225, catalog v2).

PURE unit (no Postgres): the asyncpg pool/connection is faked, so these run on
any machine/CI. The DB-backed decision-matrix behaviour stays covered by the
on-Pro integration suite (test_intake_routing.py).

Locked behaviours:
  * normalize_sender_phone: +62 / leading-0 / bare-8 / spaces / separators.
  * _classify_decision slotting: strong > phone > fuzzy; phone NEVER becomes
    AUTO_ATTACH in FASE-4; agree=boost, disagree=both surfaced,
    shared-phone=AMBIGUOUS.
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


def test_phone_and_fuzzy_disagree_is_sender_subject_mismatch() -> None:
    # Sender != subject: the OCR subject name resolves to a DIFFERENT client than
    # the sender phone. The phone matched the FORWARDER, not the document holder
    # -> downgrade to AMBIGUOUS so a human must confirm (never one-click attach).
    decision, cands, reason = rt._classify_decision(
        [], [_fuzzy(9, 0.85)], [_phone(2)], subject_name="Someone Else"
    )
    assert decision == rt.DECISION_AMBIGUOUS
    assert [c["id"] for c in cands] == [2, 9]  # phone candidate first
    assert reason["sender_subject_mismatch"] is True
    assert "FORWARDER" in reason["reason"]


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


def test_person_document_types_are_not_company_doc_types() -> None:
    for doc_type in (
        "ktp", "visa", "family_card", "birth_certificate", "marriage_certificate"
    ):
        assert doc_type in rt._PERSON_DOC_TYPES
        assert doc_type not in rt._COMPANY_DOC_TYPES


# ---------------------------------------------------------------------------
# resolve_entity wiring — fake pool/conn (no PG)
# ---------------------------------------------------------------------------

class FakeConn:
    """Minimal asyncpg.Connection stand-in: dispatches fetch() on query text."""

    def __init__(
        self,
        passport_rows: list[dict[str, Any]] | None = None,
        kitas_rows: list[dict[str, Any]] | None = None,
        phone_rows: list[dict[str, Any]] | None = None,
        fuzzy_rows: list[dict[str, Any]] | None = None,
    ) -> None:
        self.passport_rows = passport_rows or []
        self.kitas_rows = kitas_rows or []
        self.phone_rows = phone_rows or []
        self.fuzzy_rows = fuzzy_rows or []
        self.queries: list[str] = []

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.queries.append(query)
        if "passport_number" in query:
            return self.passport_rows
        if "kitas_number" in query:
            return self.kitas_rows
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
        passport_rows=[{"id": 7, "full_name": "Alice Strong", "id_verified": True}],
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
async def test_resolve_entity_itap_strong_id_skips_phone_query() -> None:
    conn = FakeConn(
        kitas_rows=[{"id": 8, "full_name": "Permanent Stay", "id_verified": True}],
        phone_rows=[{"id": 42, "full_name": "Wira Phone"}],
    )
    out = await rt.resolve_entity(
        {"itap_no": {"value": "2C-123456"}}, "itap",
        FakePool(conn), sender_phone="08123456789",
    )
    assert out["decision"] == rt.DECISION_AUTO_ATTACH
    cand = out["candidates"][0]
    assert (cand["id"], cand["method"]) == (8, "kitas_number")
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


# ---------------------------------------------------------------------------
# Sender != subject guard (forwarder vs document holder) -- live 12693/12682/16251
# vs innocence 12927. Born from a VERIFIED defect: a Bali Zero staffer/agent
# forwards a CLIENT's document, the sender phone matches the agent's CRM row,
# and the doc auto-linked to the AGENT instead of the real subject.
# ---------------------------------------------------------------------------

def test_phone_match_named_subject_unknown_to_crm_is_flagged() -> None:
    # Live shape 12693 / 12682 / 16251: phone matches the sender (forwarder) but
    # the OCR-extracted subject name resolves to NO client at all (no fuzzy hit
    # >= 0.40). Must be flagged sender_subject_mismatch + AMBIGUOUS, NOT a
    # confident one-click LINK_CANDIDATE.
    decision, cands, reason = rt._classify_decision(
        [], [], [_phone(659)], subject_name="Totally Different Person"
    )
    assert decision == rt.DECISION_AMBIGUOUS
    assert reason["sender_subject_mismatch"] is True
    assert reason["subject_name"] == "Totally Different Person"
    assert "FORWARDER" in reason["reason"]
    # The phone candidate is still surfaced (so the human can reject it fast).
    assert cands[0]["id"] == 659


def test_phone_match_no_subject_name_stays_link_candidate() -> None:
    # No subject name on the document at all -> we cannot PROVE a mismatch, so the
    # conservative phone-only LINK_CANDIDATE is preserved (no false downgrade).
    decision, cands, reason = rt._classify_decision(
        [], [], [_phone(2)], subject_name=None
    )
    assert decision == rt.DECISION_LINK_CANDIDATE
    assert "sender_subject_mismatch" not in reason
    assert cands[0]["method"] == "sender_phone"


def test_innocence_12927_same_client_ocr_noise_still_links() -> None:
    # INNOCENCE (live 12927 Gennaro Piraino): phone 0.90 + fuzzy name sim 0.6154
    # pointing at the SAME client id (sender IS the subject, just OCR noise).
    # Must STILL be a boosted LINK_CANDIDATE -- NOT downgraded -- proving the rule
    # triggers on genuine name DISAGREEMENT, not merely "name_sim < 1.0".
    decision, cands, reason = rt._classify_decision(
        [], [_fuzzy(2916, 0.6154)], [_phone(2916)], subject_name="Gennaro Piraino"
    )
    assert decision == rt.DECISION_LINK_CANDIDATE
    assert "sender_subject_mismatch" not in reason
    assert cands[0]["id"] == 2916
    assert cands[0]["method"] == "sender_phone+fuzzy_full_name"
    assert reason["name_sim"] == 0.6154
    # 0.6154 sits comfortably above the agreement floor.
    assert 0.6154 >= rt.SENDER_SUBJECT_AGREE_MIN_SIM


def test_same_client_but_below_agree_floor_is_flagged() -> None:
    # Boundary: even a SAME-client fuzzy is only trusted as agreement when its
    # similarity clears the floor. Below the floor we conservatively flag (the
    # false-positive-to-human direction is acceptable; false-auto-attach is not).
    low = rt.SENDER_SUBJECT_AGREE_MIN_SIM - 0.05
    decision, cands, reason = rt._classify_decision(
        [], [_fuzzy(2, low)], [_phone(2)], subject_name="Noisy Name"
    )
    assert decision == rt.DECISION_AMBIGUOUS
    assert reason["sender_subject_mismatch"] is True


@pytest.mark.asyncio
async def test_resolve_entity_phone_match_named_subject_disagrees_is_ambiguous() -> None:
    # End-to-end via resolve_entity: phone resolves the sender, the OCR subject
    # name ("name") resolves to a DIFFERENT client via fuzzy -> sender != subject.
    conn = FakeConn(
        phone_rows=[{"id": 1526, "full_name": "Adi Bayu Santero"}],
        fuzzy_rows=[{"id": 9001, "name": "Someone Elses Visa", "sim": 0.71}],
    )
    out = await rt.resolve_entity(
        {"name": {"value": "Someone Elses Visa"}}, "kitas",
        FakePool(conn), sender_phone="081338656330",
    )
    assert out["decision"] == rt.DECISION_AMBIGUOUS
    assert out["reason"]["sender_subject_mismatch"] is True
    assert out["reason"]["subject_name"] == "Someone Elses Visa"


@pytest.mark.asyncio
async def test_resolve_entity_phone_match_no_subject_name_links() -> None:
    # Innocence wiring: phone match, document carries NO subject name -> keep the
    # conservative LINK_CANDIDATE (regression guard for the existing behaviour).
    conn = FakeConn(phone_rows=[{"id": 42, "full_name": "Wira Phone"}])
    out = await rt.resolve_entity(
        {}, "unknown", FakePool(conn), sender_phone="0812-345-6789"
    )
    assert out["decision"] == rt.DECISION_LINK_CANDIDATE
    assert "sender_subject_mismatch" not in out["reason"]
