"""Tests for ``Decision._check_quotes_reference_candidates`` (PR1b item 2 —
F6 quote<->candidate integrity, ported from design B).

Covers: a quote whose ``product_version_id`` matches no candidate at all
(orphan quote); a quote whose ``product_version_id`` matches a candidate but
whose ``product_code`` disagrees with that candidate's own ``product_code``
(cross-wired quote); the coherent 5-state builder stays innocent; a
non-``SUPPORTED_CANDIDATES`` state (where ``quotes`` is always forced empty by
``_check_state_conditionals``) trivially passes since the loop never
iterates; and a ``SUPPORTED_CANDIDATES`` decision with pricing not yet
resolved (``quotes=()``) stays valid — the check constrains only quotes that
exist, it never requires one per candidate.

Every guilt/innocence case constructs a fresh ``M.Decision(...)`` via the
real constructor (never ``model_copy(update=...)``, which — Pydantic v2,
verified empirically — skips validators entirely on a frozen model and would
silently defeat every guilt assertion here).
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from backend.services.visa_engine import models as M
from backend.tests.services.visa_engine.conftest import (
    GOLD_EFFECTIVE_AT,
    make_candidate,
    make_fingerprint,
    make_rule_pack_ref,
)


def _make_quote(*, product_version_id: uuid.UUID, product_code: str) -> M.PriceQuote:
    return M.PriceQuote(
        quote_id=uuid.uuid4(),
        product_version_id=product_version_id,
        product_code=product_code,
        status="AVAILABLE",
        currency="IDR",
        amount=1_500_000,
        pricing_key={"category": "visa", "item_key": f"{product_code.lower()}_tourism"},
        catalog_version="2026.07",
        catalog_sha256="a" * 64,
        row_sha256="b" * 64,
        quoted_at=GOLD_EFFECTIVE_AT,
        valid_until=None,
        reason_code="PRICE_FOUND",
    )


def _supported_kwargs(*, candidates: list, quotes: list) -> dict:
    return {
        "schema_version": "1.0.0",
        "decision_id": uuid.uuid4(),
        "public_id": "a" * 16,
        "state": "SUPPORTED_CANDIDATES",
        "effective_at": GOLD_EFFECTIVE_AT,
        "observed_at": GOLD_EFFECTIVE_AT,
        "evaluated_at": GOLD_EFFECTIVE_AT,
        "rule_pack": make_rule_pack_ref(),
        "facts_fingerprint": make_fingerprint(),
        "candidates": candidates,
        "missing_facts": [],
        "review_reasons": [],
        "no_path_reasons": [],
        "outage": None,
        "quotes": quotes,
        "notices": [],
        "trace_sha256": "e" * 64,
        "decision_integrity": None,
    }


def _needs_input_kwargs() -> dict:
    return {
        "schema_version": "1.0.0",
        "decision_id": uuid.uuid4(),
        "public_id": "a" * 16,
        "state": "NEEDS_INPUT",
        "effective_at": GOLD_EFFECTIVE_AT,
        "observed_at": GOLD_EFFECTIVE_AT,
        "evaluated_at": GOLD_EFFECTIVE_AT,
        "rule_pack": make_rule_pack_ref(),
        "facts_fingerprint": make_fingerprint(),
        "candidates": [],
        "missing_facts": ["person.birth_date"],
        "review_reasons": [],
        "no_path_reasons": [],
        "outage": None,
        "quotes": [],
        "notices": [],
        "trace_sha256": "e" * 64,
        "decision_integrity": None,
    }


class TestQuoteReferencesExistingCandidate:
    def test_orphan_quote_product_version_id_rejected(self) -> None:
        candidate_pv = uuid.uuid4()
        orphan_pv = uuid.uuid4()
        with pytest.raises(ValidationError, match="no matching candidate"):
            M.Decision(
                **_supported_kwargs(
                    candidates=[make_candidate(product_version_id=candidate_pv)],
                    quotes=[_make_quote(product_version_id=orphan_pv, product_code="C1")],
                )
            )

    def test_coherent_supported_candidates_decision_is_innocent(self) -> None:
        product_version_id = uuid.uuid4()
        decision = M.Decision(
            **_supported_kwargs(
                candidates=[make_candidate(product_version_id=product_version_id)],
                quotes=[_make_quote(product_version_id=product_version_id, product_code="C1")],
            )
        )
        assert decision.quotes[0].product_version_id == decision.candidates[0].product_version_id


class TestQuoteProductCodeMatchesCandidate:
    def test_product_code_divergence_from_matching_candidate_rejected(self) -> None:
        # Same product_version_id (passes membership) but a DIFFERENT
        # product_code than the candidate it claims to price — the exact
        # cross-wiring this check exists to catch.
        product_version_id = uuid.uuid4()
        with pytest.raises(ValidationError, match="does not match candidate product_code"):
            M.Decision(
                **_supported_kwargs(
                    candidates=[
                        make_candidate(product_version_id=product_version_id)
                    ],  # product_code="C1" (conftest default)
                    quotes=[
                        _make_quote(product_version_id=product_version_id, product_code="E23")
                    ],
                )
            )

    def test_product_code_matching_candidate_is_innocent(self) -> None:
        product_version_id = uuid.uuid4()
        decision = M.Decision(
            **_supported_kwargs(
                candidates=[make_candidate(product_version_id=product_version_id)],
                quotes=[_make_quote(product_version_id=product_version_id, product_code="C1")],
            )
        )
        assert decision.quotes[0].product_code == decision.candidates[0].product_code


class TestQuoteIntegrityNoOpForNonSupportedStates:
    def test_needs_input_state_with_empty_quotes_is_innocent(self) -> None:
        # quotes=() is enforced by _check_state_conditionals for every state
        # other than SUPPORTED_CANDIDATES — the new validator's loop is a
        # no-op here, proving it never falsely fires on a legitimately empty
        # quotes/candidates pair.
        decision = M.Decision(**_needs_input_kwargs())
        assert decision.state.value == "NEEDS_INPUT"


class TestCandidateWithoutQuoteStillValid:
    def test_supported_candidate_with_no_quote_is_innocent(self) -> None:
        # A SUPPORTED_CANDIDATES decision with quotes=() (pricing not yet
        # resolved) must stay valid — the new check only constrains quotes
        # that DO exist, it never requires one per candidate.
        product_version_id = uuid.uuid4()
        decision = M.Decision(
            **_supported_kwargs(
                candidates=[make_candidate(product_version_id=product_version_id)],
                quotes=[],
            )
        )
        assert decision.quotes == ()
        assert decision.candidates[0].product_version_id == product_version_id


class TestCandidatesUniqueProductVersionId:
    """PR1b item 10 (GLM adversarial review): ``candidates`` must have unique
    ``product_version_id``s — the precondition ``_check_quotes_reference_
    candidates`` now enforces BEFORE building its lookup dict. Without this,
    ``{c.product_version_id: c for c in self.candidates}`` silently clobbers
    a duplicate (last-one-wins), so two candidates for the same product
    would let the survivor arbitrarily decide any quote-match outcome
    instead of failing loud on the real defect.
    """

    def test_two_candidates_same_product_version_id_rejected(self) -> None:
        product_version_id = uuid.uuid4()
        first = make_candidate(product_version_id=product_version_id)
        second = first.model_copy(update={"rank": 2, "score": 5})
        with pytest.raises(ValidationError, match="unique product_version_id"):
            M.Decision(
                **_supported_kwargs(
                    candidates=[first, second],
                    quotes=[],
                )
            )

    def test_distinct_candidates_are_innocent(self) -> None:
        first_id = uuid.uuid4()
        second_id = uuid.uuid4()
        decision = M.Decision(
            **_supported_kwargs(
                candidates=[
                    make_candidate(product_version_id=first_id),
                    make_candidate(product_version_id=second_id).model_copy(
                        update={"rank": 2, "product_code": "E23"}
                    ),
                ],
                quotes=[],
            )
        )
        assert {c.product_version_id for c in decision.candidates} == {first_id, second_id}
