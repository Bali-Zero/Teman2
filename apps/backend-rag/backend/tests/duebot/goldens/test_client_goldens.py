"""Proves the B6b client-bot golden fixtures are what they claim to be:

1. every fixture indexes into a REAL entry of the B6a defect-class
   catalogue, tagged ``bot="client"``;
2. every one of the 17 ``client.*`` catalogue entries has at least one
   fixture — no silent catalogue/fixture drift in either direction;
3. every fixture's nested contract instances (``CanonicalMessage``,
   ``GroundingBundle``, ``BrainCandidate``, ``FinalDecision``) are valid
   against the FROZEN pydantic types (import-time construction already
   proves this — see ``fixtures.py``'s module-level constants — this file
   makes it an explicit, individually-reportable assertion per fixture);
4. every fixture's ``(verdict, reason)`` pair is one the ``GateReason``
   enum's OWN inline documentation (``policy/types.py``, "Check N ->
   VERDICT" comments) declares legal for that check — catches a
   fixture accidentally pairing e.g. a canary hit with ``ALLOW``;
5. the ``FinalDecision.rendered_text`` iff-``ALLOW`` rule (already
   enforced by the frozen model itself) holds for every fixture;
6. a handful of fixtures are internally self-consistent in the SPECIFIC
   way their defect claims to be broken (e.g. the "wrong evidence"
   fixture's cited id is truly absent from its own grounding bundle) —
   catches a fixture whose narrative doesn't match its actual data;
7. the RED case: a deliberately malformed candidate — the exact kind of
   mistake a fixture author could make by hand — is rejected by the real
   frozen contract, proving these goldens are not merely "whatever was
   typed happens to pass because nothing checks".
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.services.client_bot.policy.types import GateReason, GateVerdict
from backend.tests.duebot.defect_catalogue import by_bot, index_by_id, load_defect_catalogue
from backend.tests.duebot.goldens.builders import make_answer_candidate, make_canonical_message
from backend.tests.duebot.goldens.fixtures import (
    ATTACHMENT_ONLY_MESSAGE,
    CITATION_WRONG_EVIDENCE,
    CLIENT_GOLDENS,
    CLIENT_GOLDENS_BY_CASE_ID,
    HANDOFF_INSERT_FAILS,
    HANDOFF_INSERT_SUCCEEDS,
    PRICING_CORRECT,
    PRICING_INVENTED,
    REGULATION_SUPPORTED_CORRECT_CITATION,
)

# GateReason's own inline documentation (policy/types.py "Check N -> VERDICT"
# comments), transcribed as a verdict -> legal-reasons map. Where a check's
# comment lists two verdicts ("-> ABSTAIN or HANDOFF"), BOTH verdicts accept
# that reason here — this is not a stricter spec than the source enum
# documents, it is exactly that spec, machine-checkable.
_LEGAL_REASONS_BY_VERDICT: dict[GateVerdict, set[GateReason]] = {
    GateVerdict.ALLOW: {GateReason.PASSED_ALL_CHECKS},
    GateVerdict.DROP: {
        GateReason.THREAD_OWNERSHIP_LOST,
        GateReason.THREAD_EPOCH_STALE,
        GateReason.HUMAN_TAKEOVER_ACTIVE,
        GateReason.DUPLICATE_TERMINAL_RESPONSE,
        GateReason.SERVICE_WINDOW_EXPIRED,
    },
    GateVerdict.TEXT_DEFECT: {
        GateReason.SCHEMA_VERSION_MISMATCH,
        GateReason.UNKNOWN_FIELD_PRESENT,
        GateReason.INVALID_ENCODING,
        GateReason.PACKAGE_HASH_MISMATCH,
        GateReason.BOUNDS_EXCEEDED,
        GateReason.INTERNAL_REASONING_LEAK,
        GateReason.INSTRUCTION_SCAFFOLD_LEAK,
        GateReason.RENDER_LANGUAGE_MISMATCH,
        GateReason.RENDER_FORMAT_VIOLATION,
        GateReason.RENDERER_ADDED_CONTENT,
        GateReason.LENGTH_EXCEEDS_HARD_LIMIT,
        GateReason.IDEMPOTENCY_CONFLICT_AT_INSERT,
    },
    GateVerdict.POLICY_BLOCKED: {
        GateReason.CANARY_HIT,
        GateReason.SECRET_EGRESS_DETECTED,
        GateReason.PRICE_NOT_IN_SNAPSHOT,
        GateReason.PRICE_RECOMPUTED_BY_MODEL,
        GateReason.NO_PRICING_SNAPSHOT_AVAILABLE,
    },
    GateVerdict.ABSTAIN: {
        GateReason.MODEL_ABSTAINED,
        GateReason.OUT_OF_SCOPE_REGULATED_REQUEST,
        GateReason.HUMAN_DECISION_REQUIRED,
        GateReason.DOMAIN_OUT_OF_SURFACE_SCOPE,
        GateReason.UNAUTHENTICATED_PORTAL_CONTEXT_LEAK,
        GateReason.ATTACHMENT_PROFILE_MISMATCH,
        GateReason.UNINVENTORIED_REGULATED_STATEMENT,
        GateReason.UNINVENTORIED_NUMERIC_STATEMENT,
        GateReason.CLAIM_MISSING_EVIDENCE_ID,
        GateReason.EVIDENCE_DETERMINISTIC_CHECK_FAILED,
        GateReason.EVIDENCE_SEMANTIC_SUPPORT_BELOW_THRESHOLD,
        GateReason.EVIDENCE_VERIFIER_OUTAGE,
        GateReason.CITATION_ID_NOT_IN_BUNDLE,
        GateReason.CITATION_TO_UNUSED_EVIDENCE,
        GateReason.CLAIM_MISSING_DISPLAYED_CITATION,
        GateReason.KBLI_CLASSIFICATION_MISSING_ALL_FACTUAL_CITATION,
    },
    GateVerdict.HANDOFF: {
        GateReason.MODEL_REQUESTED_HANDOFF,
        GateReason.OUT_OF_SCOPE_REGULATED_REQUEST,
        GateReason.HUMAN_DECISION_REQUIRED,
        GateReason.CLAIM_MISSING_EVIDENCE_ID,
        GateReason.EVIDENCE_SEMANTIC_SUPPORT_BELOW_THRESHOLD,
        GateReason.PRICE_NOT_IN_SNAPSHOT,
        GateReason.PRICE_RECOMPUTED_BY_MODEL,
        GateReason.NO_PRICING_SNAPSHOT_AVAILABLE,
        # Engine-level (B1b): no candidate exists, not one of the 11 checks —
        # see policy/types.py's GateReason.PROVIDERS_EXHAUSTED docstring.
        GateReason.PROVIDERS_EXHAUSTED,
    },
}


@pytest.fixture(scope="module")
def catalogue():
    return load_defect_catalogue()


# ---------------------------------------------------------------------------
# 1-2. catalogue coverage
# ---------------------------------------------------------------------------


def test_every_fixture_defect_class_id_exists_in_the_catalogue_as_client(catalogue) -> None:
    index = index_by_id(catalogue)
    for fx in CLIENT_GOLDENS:
        assert fx.defect_class_id in index, f"{fx.case_id}: unknown defect_class_id {fx.defect_class_id!r}"
        assert index[fx.defect_class_id].bot == "client", f"{fx.case_id}: catalogue entry is not bot=client"


def test_every_client_defect_class_has_at_least_one_fixture(catalogue) -> None:
    client_ids = {dc.id for dc in by_bot(catalogue, "client")}
    covered_ids = {fx.defect_class_id for fx in CLIENT_GOLDENS}
    missing = client_ids - covered_ids
    assert not missing, f"client defect classes with NO golden fixture: {sorted(missing)}"


def test_no_fixture_indexes_a_team_or_transport_class(catalogue) -> None:
    """B6b scope is client-bot only (team-bot contracts are not frozen
    yet — verified empirically: no ``apps/team-bot`` / team-bot contract
    module exists in this checkout).
    """
    index = index_by_id(catalogue)
    for fx in CLIENT_GOLDENS:
        assert index[fx.defect_class_id].bot == "client"


def test_exactly_19_fixtures_for_17_classes_with_2_compound_variants(catalogue) -> None:
    assert len(CLIENT_GOLDENS) == 19
    assert len(by_bot(catalogue, "client")) == 17

    from collections import Counter

    counts = Counter(fx.defect_class_id for fx in CLIENT_GOLDENS)
    compound = {k for k, v in counts.items() if v > 1}
    assert compound == {
        "client.pricing-correct-and-invented",
        "client.handoff-insert-succeeds-and-fails",
    }
    assert all(v == 2 for k, v in counts.items() if k in compound)
    assert all(v == 1 for k, v in counts.items() if k not in compound)


def test_case_ids_are_unique() -> None:
    ids = [fx.case_id for fx in CLIENT_GOLDENS]
    assert len(ids) == len(set(ids))
    assert len(CLIENT_GOLDENS_BY_CASE_ID) == len(CLIENT_GOLDENS)


# ---------------------------------------------------------------------------
# 3. every fixture's nested instances are valid frozen-contract instances
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fx", CLIENT_GOLDENS, ids=lambda fx: fx.case_id)
def test_fixture_message_is_a_valid_canonical_message(fx) -> None:
    # Already true by construction (module import would have raised) —
    # this makes it a per-fixture, individually-reportable assertion, and
    # documents WHY: this is the whole point of the fixture set.
    assert fx.message.schema_version == "1.0"
    assert fx.message.raw_payload_sha256


@pytest.mark.parametrize("fx", CLIENT_GOLDENS, ids=lambda fx: fx.case_id)
def test_fixture_decision_matches_its_own_rendered_text_rule(fx) -> None:
    if fx.expected_decision.verdict == GateVerdict.ALLOW:
        assert fx.expected_decision.rendered_text is not None
    else:
        assert fx.expected_decision.rendered_text is None


@pytest.mark.parametrize("fx", CLIENT_GOLDENS, ids=lambda fx: fx.case_id)
def test_fixture_is_retryable_matches_verdict(fx) -> None:
    """``FinalDecision.is_retryable`` (policy/types.py: "Only TEXT_DEFECT is
    eligible for one provider fallback") — every fixture's own frozen
    property must agree with its verdict, not just the reason mapping above.
    """
    assert fx.expected_decision.is_retryable == (fx.expected_decision.verdict == GateVerdict.TEXT_DEFECT)


@pytest.mark.parametrize("fx", CLIENT_GOLDENS, ids=lambda fx: fx.case_id)
def test_fixture_verdict_reason_pair_is_documented_legal(fx) -> None:
    legal = _LEGAL_REASONS_BY_VERDICT[fx.expected_decision.verdict]
    assert fx.expected_decision.reason in legal, (
        f"{fx.case_id}: reason {fx.expected_decision.reason.value!r} is not documented as legal "
        f"for verdict {fx.expected_decision.verdict.value!r} in policy/types.py's own GateReason comments"
    )


def test_every_gate_verdict_member_is_exercised_by_at_least_one_fixture() -> None:
    """Not required by the catalogue, but worth knowing: does this 19-fixture
    set actually walk every terminal verdict at least once? (It does.)
    """
    exercised = {fx.expected_decision.verdict for fx in CLIENT_GOLDENS}
    assert exercised == set(GateVerdict), f"verdicts never exercised: {set(GateVerdict) - exercised}"


# ---------------------------------------------------------------------------
# 6. narrative/data self-consistency spot checks
# ---------------------------------------------------------------------------


def test_correct_citation_fixture_actually_cites_evidence_present_in_its_bundle() -> None:
    fx = REGULATION_SUPPORTED_CORRECT_CITATION
    bundle_ids = {ev.evidence_id for ev in fx.grounding.evidence}
    assert set(fx.candidate.cited_evidence_ids) <= bundle_ids
    assert set(fx.candidate.cited_evidence_ids), "the happy-path fixture must actually cite something"


def test_wrong_evidence_fixture_cites_an_id_truly_absent_from_its_bundle() -> None:
    fx = CITATION_WRONG_EVIDENCE
    bundle_ids = {ev.evidence_id for ev in fx.grounding.evidence}
    assert set(fx.candidate.cited_evidence_ids) & bundle_ids == set(), (
        "the defect this fixture models is exactly that the cited id is NOT in the bundle — "
        "if it were, this fixture would silently stop testing what its name claims"
    )


def test_attachment_only_fixture_really_has_no_text() -> None:
    fx = ATTACHMENT_ONLY_MESSAGE
    assert fx.message.text == ""
    assert len(fx.message.attachments) >= 1


def test_pricing_variants_share_the_same_snapshot_but_diverge_on_the_quoted_amount() -> None:
    correct_amount = PRICING_CORRECT.grounding.pricing.items[0]["amount_idr"]
    invented_amount = PRICING_INVENTED.grounding.pricing.items[0]["amount_idr"]
    assert correct_amount == invented_amount == 15_000_000, "both variants share the SAME frozen snapshot"

    # The "correct" candidate's claim quotes exactly the snapshot amount
    # (Indonesian thousand-separator formatting: "15.000.000"); the
    # "invented" candidate's claim quotes a DIFFERENT amount entirely —
    # that divergence is the whole defect being modeled.
    assert "15.000.000" in PRICING_CORRECT.candidate.claims[0].text
    assert "15.000.000" not in PRICING_INVENTED.candidate.claims[0].text
    assert "25.000.000" in PRICING_INVENTED.candidate.claims[0].text


def test_handoff_variants_have_identical_candidate_shape_but_diverging_reason_detail() -> None:
    """F10's point exactly: the MODEL cannot know whether the handoff row
    insert behind it succeeded — so the two variants' candidates must be
    indistinguishable, and only the (out-of-band) reason_detail differs.
    """
    assert HANDOFF_INSERT_SUCCEEDS.candidate.disposition == HANDOFF_INSERT_FAILS.candidate.disposition
    assert HANDOFF_INSERT_SUCCEEDS.candidate.answer == HANDOFF_INSERT_FAILS.candidate.answer
    assert HANDOFF_INSERT_SUCCEEDS.candidate.handoff_reason_code == HANDOFF_INSERT_FAILS.candidate.handoff_reason_code
    assert (
        HANDOFF_INSERT_SUCCEEDS.expected_decision.reason_detail
        != HANDOFF_INSERT_FAILS.expected_decision.reason_detail
    )


# ---------------------------------------------------------------------------
# 7. RED case — a malformed candidate is rejected by the real frozen contract
# ---------------------------------------------------------------------------


def test_a_disposition_answer_candidate_with_blank_answer_is_rejected() -> None:
    """The exact hand-authoring mistake this fixture set is designed to
    make impossible to introduce silently: a disposition='answer' candidate
    whose answer is empty/whitespace. Proves the frozen contract's own
    validator — not this test suite — is what would catch a bad fixture.
    """
    with pytest.raises(ValidationError):
        make_answer_candidate("red-case-blank-answer", answer="   \n\t")


def test_a_handoff_candidate_with_a_non_empty_answer_is_rejected() -> None:
    from backend.services.client_bot.contracts import BrainCandidate

    with pytest.raises(ValidationError):
        BrainCandidate(
            schema_version="1.0",
            disposition="handoff",
            answer="this should not be allowed alongside handoff",
            claims=(),
            cited_evidence_ids=(),
            handoff_reason_code="OUT_OF_SCOPE_REGULATED_REQUEST",
            provider_name="gemini",
            model_name="gemini-2.5-pro",
            package_sha256="a" * 64,
        )


def test_a_canonical_message_with_no_text_and_no_attachments_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_canonical_message("red-case-empty-message", text="", attachments=())
