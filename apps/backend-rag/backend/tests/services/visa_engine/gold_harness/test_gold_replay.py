"""Gold-persona replay: for each of the 23 gold personas x each of the 11
products in the designed gold rule pack, run the REAL evaluator
(``ast.evaluate_condition`` + ``compiler.build_compiled_pack``, via this
package's ``adapter.py``) and assert the resulting proof state -- plus
reason codes / covered purposes / missing purposes / missing facts, wherever
the persona's fixture asserts them -- matches the persona's expected outcome
EXACTLY. Zero unexplained divergence = suite green (evidence for gate G-b).

Also covers: one global-decision assertion per persona, a handful of
persona-specific "extra check" assertions (derived-fact values, the Unicode
NFC round-trip) that fall outside the per-product proof shape, and an
explicit "never raises" sweep over every persona (documents the #20
deliberately-contradictory-facts requirement directly rather than leaving it
implied by collection-time success).
"""

from __future__ import annotations

import unicodedata

import pytest

from backend.services.visa_engine.ast import KnownFact
from backend.services.visa_engine.enums import FactPath

from . import adapter, loader
from .expectations import resolve_expected

PACK = loader.load_and_compile_rule_pack()
PERSONAS = loader.load_all_personas()
PRODUCT_CODES = sorted(p.product_code for p in PACK.products)

assert len(PERSONAS) == 23, f"expected exactly 23 gold personas, found {len(PERSONAS)}"
assert len(PRODUCT_CODES) == 11, (
    f"expected exactly 11 products in the gold pack, found {len(PRODUCT_CODES)}"
)

_PERSONAS_BY_ID = {p.persona_id: p for p in PERSONAS}


def _evaluate_every_persona() -> dict[
    str, tuple[dict[str, adapter.ProductProof], adapter.GlobalDecision]
]:
    """One (proofs, global_decision) pair per persona, computed once. Every
    test below reads from this rather than re-evaluating, so the assertions
    and the eventual evidence artifact (``replay_report.py``) are built from
    the exact same single evaluation run per persona.
    """
    results: dict[str, tuple[dict[str, adapter.ProductProof], adapter.GlobalDecision]] = {}
    for persona in PERSONAS:
        snapshot = persona.derive_snapshot()
        proofs, global_decision = adapter.evaluate_all(
            PACK, snapshot, effective_at=loader.GOLD_EFFECTIVE_AT
        )
        results[persona.persona_id] = (proofs, global_decision)
    return results


RESULTS = _evaluate_every_persona()


class TestPersonaProductReplay:
    """23 personas x 11 products = 253 (persona, product) proof assertions."""

    @pytest.mark.parametrize("persona_id", sorted(_PERSONAS_BY_ID))
    @pytest.mark.parametrize("product_code", PRODUCT_CODES)
    def test_proof_state_matches_expected(self, persona_id: str, product_code: str) -> None:
        persona = _PERSONAS_BY_ID[persona_id]
        proofs, _ = RESULTS[persona_id]
        actual = proofs[product_code]
        expected = resolve_expected(persona.expected, product_code, PACK)

        assert actual.state.value == expected.proof_state, (
            f"{persona_id} / {product_code}: proof_state expected="
            f"{expected.proof_state} actual={actual.state.value}"
        )
        if expected.reason_codes:
            assert tuple(actual.reason_codes) == expected.reason_codes, (
                f"{persona_id} / {product_code}: reason_codes expected="
                f"{expected.reason_codes} actual={actual.reason_codes}"
            )
        if expected.covered_purposes:
            assert frozenset(actual.covered_purposes) == expected.covered_purposes, (
                f"{persona_id} / {product_code}: covered_purposes expected="
                f"{sorted(expected.covered_purposes)} actual={sorted(actual.covered_purposes)}"
            )
        if expected.missing_purposes:
            assert frozenset(actual.missing_purposes) == expected.missing_purposes, (
                f"{persona_id} / {product_code}: missing_purposes expected="
                f"{sorted(expected.missing_purposes)} actual={sorted(actual.missing_purposes)}"
            )
        if expected.missing_facts is not None:
            actual_mf = tuple(sorted(f.value for f in actual.missing_facts))
            assert actual_mf == expected.missing_facts, (
                f"{persona_id} / {product_code}: missing_facts expected="
                f"{expected.missing_facts} actual={actual_mf}"
            )


class TestPersonaGlobalDecision:
    """One global-decision assertion per persona (state + reason codes / missing facts)."""

    @pytest.mark.parametrize("persona_id", sorted(_PERSONAS_BY_ID))
    def test_global_state_matches_expected(self, persona_id: str) -> None:
        persona = _PERSONAS_BY_ID[persona_id]
        _, global_decision = RESULTS[persona_id]
        exp = persona.expected

        assert global_decision.state.value == exp["global_state"], (
            f"{persona_id}: global_state expected={exp['global_state']} "
            f"actual={global_decision.state.value}"
        )
        if "global_reason_codes" in exp:
            assert list(global_decision.reason_codes) == exp["global_reason_codes"], (
                f"{persona_id}: global reason_codes expected={exp['global_reason_codes']} "
                f"actual={list(global_decision.reason_codes)}"
            )
        if "global_missing_facts" in exp:
            actual_mf = sorted(f.value for f in global_decision.missing_facts)
            assert actual_mf == exp["global_missing_facts"], (
                f"{persona_id}: global missing_facts expected={exp['global_missing_facts']} "
                f"actual={actual_mf}"
            )


_EXTRA_CHECK_PERSONA_IDS = sorted(
    pid for pid, p in _PERSONAS_BY_ID.items() if p.expected.get("extra_checks")
)


class TestPersonaExtraChecks:
    """Persona-specific assertions outside the proof-state shape: derived
    fact values (age/minor) and the Unicode NFC round-trip check."""

    @pytest.mark.parametrize("persona_id", _EXTRA_CHECK_PERSONA_IDS)
    def test_extra_checks(self, persona_id: str) -> None:
        persona = _PERSONAS_BY_ID[persona_id]
        snapshot = persona.derive_snapshot()
        extra = persona.expected["extra_checks"]

        if "derived_age_years" in extra:
            fact = snapshot.values[FactPath.DERIVED_AGE_YEARS]
            assert isinstance(fact, KnownFact), (
                f"{persona_id}: derived.age_years unexpectedly unknown"
            )
            assert fact.value == extra["derived_age_years"], (
                f"{persona_id}: derived.age_years expected={extra['derived_age_years']} "
                f"actual={fact.value}"
            )
        if "derived_is_minor" in extra:
            fact = snapshot.values[FactPath.DERIVED_IS_MINOR]
            assert isinstance(fact, KnownFact), (
                f"{persona_id}: derived.is_minor unexpectedly unknown"
            )
            assert fact.value == extra["derived_is_minor"], (
                f"{persona_id}: derived.is_minor expected={extra['derived_is_minor']} "
                f"actual={fact.value}"
            )
        if "family_sponsor_status_code_nfc" in extra:
            fact = snapshot.values[FactPath.FAMILY_SPONSOR_STATUS_CODE]
            assert isinstance(fact, KnownFact), (
                f"{persona_id}: family.sponsor_status_code unexpectedly unknown"
            )
            expected_value = extra["family_sponsor_status_code_nfc"]
            assert fact.value == expected_value, (
                f"{persona_id}: family.sponsor_status_code expected={expected_value!r} "
                f"actual={fact.value!r}"
            )
            # NFC round-trip: the stored value must equal its own NFC
            # normalization -- proves the pipeline neither mangled it nor
            # silently landed a form that wasn't already NFC.
            assert unicodedata.normalize("NFC", fact.value) == fact.value


def test_no_persona_ever_raises_during_full_evaluation() -> None:
    """Every persona (including #20's deliberately contradictory fact set)
    must evaluate to completion without raising, for every product -- the
    gate's own "must not crash" requirement, asserted directly rather than
    only implied by ``RESULTS`` above having already been built successfully
    at collection time (this test documents the requirement explicitly so a
    future refactor of the module-level eager evaluation still enforces it).
    """

    for persona in PERSONAS:
        snapshot = persona.derive_snapshot()
        proofs, global_decision = adapter.evaluate_all(
            PACK, snapshot, effective_at=loader.GOLD_EFFECTIVE_AT
        )
        assert len(proofs) == len(PRODUCT_CODES)
        assert global_decision.state is not None
