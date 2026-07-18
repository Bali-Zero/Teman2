"""Unit tests for GATE-11 (identity-backfill anti-cascade), 2026-07-18.

PURE unit (no Postgres): the asyncpg connection is faked, matching the style of
test_intake_routing_phone.py / test_client_enricher_name.py — no real DB needed
for these, so they run everywhere (and never touch the operational
nuzantara_dev DB, scar W96).

Danger this gate closes (research/operations/2026-07-18-intake-identity-backfill-
design.md, "error contagion"): an id written by the unverified identity-backfill
batch (``clients.custom_fields.identity_backfill.<column>.verified == false``)
must NOT be able to trigger a confident AUTO_ATTACH on its own — a wrong fill
would otherwise cascade into a wrong attach. Two halves:

  * consumer side (routing._classify_decision) — a single strong-identifier
    match on an unverified id degrades AUTO_ATTACH -> LINK_CANDIDATE.
  * promotion side (client_enricher.enrich_client_from_extracted_fields) — a
    committed document that CONFIRMS the id already on the card (same
    normalized value) flips that provenance entry to verified, closing the
    loop without ever needing a confident auto-attach in between.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from backend.services.intake import routing as rt
from backend.services.intake.client_enricher import enrich_client_from_extracted_fields

# ---------------------------------------------------------------------------
# _classify_decision — GATE-11 slotting (pure)
# ---------------------------------------------------------------------------


def _strong(cid: int = 1, *, id_verified: Any = "unset") -> dict[str, Any]:
    """Build a passport-strong candidate dict, mirroring _match_person_strong.

    ``id_verified="unset"`` (the sentinel default) omits the key entirely —
    simulating a pre-GATE-11 candidate (company match, or any caller that
    never carried provenance). Pass ``True``/``False`` to add the key.
    """
    cand: dict[str, Any] = {
        "table": "clients", "id": cid, "name": "Strong Match",
        "method": "passport_number", "score": rt.CONF_STRONG_EXACT,
        "matched_value": "ZZ123",
    }
    if id_verified != "unset":
        cand["id_verified"] = id_verified
    return cand


def test_single_unverified_strong_id_downgrades_to_link_candidate() -> None:
    # The injective anti-cascade test: an unconfirmed backfilled id is the
    # ONLY signal, and it must NOT reach AUTO_ATTACH on its own.
    decision, cands, reason = rt._classify_decision(
        [_strong(1, id_verified=False)], [], []
    )
    assert decision == rt.DECISION_LINK_CANDIDATE
    assert cands == [_strong(1, id_verified=False)]
    assert reason["backfilled_unverified"] is True
    assert reason["method"] == "passport_number"
    assert "GATE-11" in reason["reason"]


def test_single_verified_strong_id_still_auto_attaches() -> None:
    # Unchanged behaviour: an EXPLICITLY verified id is exactly as confident
    # as it was before GATE-11 existed.
    decision, cands, reason = rt._classify_decision(
        [_strong(1, id_verified=True)], [], []
    )
    assert decision == rt.DECISION_AUTO_ATTACH
    assert cands == [_strong(1, id_verified=True)]
    assert "backfilled_unverified" not in reason
    assert reason["method"] == "passport_number"


def test_candidate_without_id_verified_key_defaults_to_auto_attach() -> None:
    # Default-true semantics: company-strong candidates (never carry
    # "id_verified") and any legacy caller must be unaffected by GATE-11.
    decision, cands, reason = rt._classify_decision([_strong(1)], [], [])
    assert "id_verified" not in cands[0]
    assert decision == rt.DECISION_AUTO_ATTACH
    assert "backfilled_unverified" not in reason


def test_collision_stays_ambiguous_regardless_of_verified_flags() -> None:
    # >1 distinct row sharing a strong identifier is a data collision — GATE-11
    # must not change this branch at all, verified or not.
    decision, cands, reason = rt._classify_decision(
        [_strong(1, id_verified=False), _strong(2, id_verified=True)], [], []
    )
    assert decision == rt.DECISION_AMBIGUOUS
    assert len(cands) == 2
    assert "collision" in reason["reason"]


# ---------------------------------------------------------------------------
# client_enricher — GATE-11 verified-promotion (pure, FakeConn)
# ---------------------------------------------------------------------------


class FakeConn:
    """Minimal asyncpg.Connection stand-in for enrich_client_from_extracted_fields.

    ``fetch`` answers the schema-drift existing_cols probe; ``fetchrow``
    answers the upfront full_name/passport_number/kitas_number/custom_fields
    read. ``execute`` records the final UPDATE for assertion.
    """

    def __init__(self, existing_cols: set[str], client_row: dict[str, Any]) -> None:
        self.existing_cols = existing_cols
        self.client_row = client_row
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, _query: str, *_args: Any) -> list[dict[str, str]]:
        return [{"column_name": c} for c in self.existing_cols]

    async def fetchrow(self, _query: str, *args: Any) -> dict[str, Any]:
        assert args == (555,)
        return dict(self.client_row)

    async def execute(self, query: str, *args: Any) -> str:
        self.execute_calls.append((query, args))
        return "UPDATE 1"


_EXISTING_COLS = {
    "full_name", "passport_number", "passport_expiry", "date_of_birth",
    "nationality", "kitas_number", "kitas_expiry_date", "custom_fields",
}


def _backfill_provenance(*, verified: bool) -> str:
    """A stored custom_fields JSON string (as a plain/no-codec pool returns it)."""
    return json.dumps({
        "identity_backfill": {
            "passport_number": {
                "verified": verified,
                "batch": "A-20260718",
                "rule": "A-strict-v1",
                "value_md5": "deadbeef",
                "written_at": "2026-07-18T00:00:00+00:00",
            }
        }
    })


@pytest.mark.asyncio
async def test_confirming_document_promotes_unverified_provenance_to_verified() -> None:
    conn = FakeConn(
        _EXISTING_COLS,
        {
            "full_name": "Existing Client",
            "passport_number": "AB123456",
            "kitas_number": None,
            "custom_fields": _backfill_provenance(verified=False),
        },
    )

    written = await enrich_client_from_extracted_fields(
        conn, 555, "passport",
        # OCR-extracted value differs only by separators from the stored one —
        # normalize() must still see them as the SAME identifier.
        {"passport_no": {"value": "AB 123456"}},
    )

    assert written["passport_number"] == "AB 123456"
    sql, args = conn.execute_calls[0]
    assert "custom_fields" in sql
    assert "::text::jsonb" in sql
    cf_param = next(a for a in args if isinstance(a, str) and "identity_backfill" in a)
    promoted = json.loads(cf_param)["identity_backfill"]["passport_number"]
    assert promoted["verified"] is True
    assert promoted["verified_by"] == "doc-commit"
    assert "verified_at" in promoted
    # Original provenance fields survive the mutation untouched.
    assert promoted["batch"] == "A-20260718"
    assert promoted["rule"] == "A-strict-v1"


@pytest.mark.asyncio
async def test_confirming_a_different_value_does_not_promote() -> None:
    conn = FakeConn(
        _EXISTING_COLS,
        {
            "full_name": "Existing Client",
            "passport_number": "AB123456",
            "kitas_number": None,
            "custom_fields": _backfill_provenance(verified=False),
        },
    )

    written = await enrich_client_from_extracted_fields(
        conn, 555, "passport",
        {"passport_no": {"value": "ZZ999999"}},
    )

    assert written["passport_number"] == "ZZ999999"
    sql, _args = conn.execute_calls[0]
    assert "custom_fields" not in sql


@pytest.mark.asyncio
async def test_already_verified_provenance_is_not_rewritten() -> None:
    # Idempotence: a value that already carries verified:true must not trigger
    # a redundant custom_fields write even when the document re-confirms it.
    conn = FakeConn(
        _EXISTING_COLS,
        {
            "full_name": "Existing Client",
            "passport_number": "AB123456",
            "kitas_number": None,
            "custom_fields": _backfill_provenance(verified=True),
        },
    )

    written = await enrich_client_from_extracted_fields(
        conn, 555, "passport",
        {"passport_no": {"value": "AB123456"}},
    )

    assert written["passport_number"] == "AB123456"
    sql, _args = conn.execute_calls[0]
    assert "custom_fields" not in sql
