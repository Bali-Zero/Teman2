"""seq-7's actual scope, pinned as tests.

The mandate for this pack asked for two ELIGIBILITY rules —
``el.e33a.sponsor-government`` and ``el.e33c.sponsor-government``, each
``sponsor.type eq GOVERNMENT`` conjoined with "the genuine E33A/E33C gate
existing in the pack" — plus a third, ``el.e33b.sponsor-none``, contingent on
whether E33B's gate turned out expressible with current facts.

That premise checked false. ``rulepack-prod-006.source.json`` binds exactly
one rule to each of E33A/E33B/E33C/E28C's ``product_version_id``, and it is
a ``HUMAN_REVIEW`` rule in every case — there is no ``HARD_FILTER`` or
``ELIGIBILITY`` rule to conjoin anything with.
``test_reachability_is_what_the_document_claims`` in
``test_seq6_refuter_witnesses.py`` already pins this: 27/38 products
reachable, and E28C/E33A/E33B/E33C are three of the eleven that are not.

Two shapes of ``el.<product>.sponsor-government`` were tried against the
real evaluator for BOTH E33A and E33C (script discarded after the run,
results pinned here as ``test_narrow_sponsor_only_eligibility_rule_is_dead
_code`` and ``test_broad_sponsor_only_eligibility_rule_manufactures_an
_offer``, both parametrized over the two products — a cross-family
adversarial pass independently re-ran the same two simulations and
confirmed the same outcomes before this parametrization existed): a narrow
one (``covered_purposes`` limited to the existing review rule's own purpose
scope — EMPLOYMENT for E33A, INVESTMENT for E33C) is dead code —
``evaluate_product()`` evaluates every ``SUPPORT`` condition (they are
always recorded in the audit trace), but it returns ``REVIEW`` before their
COVERAGE can ever produce a ``SUPPORTED`` proof, for every applicant whose
purposes intersect the review rule's own scope; coverage fails outright for
anyone whose purposes do not. A broad one (``covered_purposes`` matching the
product's full product-record value) is *not* dead: it manufactures a
``SUPPORTED_CANDIDATES`` offer for an applicant whose ONLY stated purpose is
one the review rule never inspects (TOURISM, for both), who merely answers
"government" to the sponsor question, with none of Pasal 57/59's actual
content — a confirmed central-government invitation — ever checked. These
two tests pin exactly the two shapes tried; they are not a proof that every
conceivable future sponsor.type rule is safe, only that these two specific
ones are not. E33B was already covered by the mandate's own contingency:
the factbase's gap #4 (no fact for certification, university
ranking/recency/GPA, or the 90-day cooperation commitment) means its gate
is not expressible either, so ``el.e33b.sponsor-none`` was not written for
the identical reason.

What this pack DOES contain: an ``enums.py`` documentation pass (SponsorType
per-value semantics + a corrected ``FactPath.SPONSOR_TYPE`` comment that
previously overclaimed E23U/E23V's sponsor category as "always known"), one
product-record data correction (E28C's ``sponsor_types``
``["INDIVIDUAL"]`` -> ``["NONE"]``, Pasal 39/40 self-filed reading — NOT the
same thing as E33B's "tanpa Penjamin": E28C substitutes ``Jaminan
Keimigrasian`` rather than stating the absence of a Penjamin explicitly),
and a citation-precision fix on the shared Permenkumham 22/2023 jo. 11/2024
source record (its own ``locators`` array never listed Pasal 39/40/57/58/59
even though E33A/E33B/E33C already cited it for exactly those Pasal in
seq-6 — a cross-family review caught this; the fix only enriches the
locator list, it does not change ``content_sha256`` or touch seq-6's own
immutable copy of the record). Every RULE is byte-identical to seq-6: 0
added, 0 removed. Full rationale:
``research/visa/2026-08-11-seq7-sponsor-semantics-and-the-gate-that-does
-not-exist.md``.
"""

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.scripts.visa_engine.compile_pack import (
    load_rule_pack_payload,
    wrap_as_unsigned_pack,
)
from backend.services.visa_engine import compiler, evaluator
from backend.services.visa_engine.bundle import canonicalize_json
from backend.services.visa_engine.evaluator import build_decision_identity
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY
from backend.tests.services.visa_engine import _gold_fixtures as gf

PACKS = Path(__file__).resolve().parents[3] / "services/visa_engine/contracts/packs"

# Same anchor as test_seq6_refuter_witnesses.py: after both packs' valid_period
# windows open (seq-6 opens 2026-07-25), before any future pack changes the
# clock-dependent products underneath this measurement.
AT = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)


def _known(value):
    return {"status": "KNOWN", "value": value}


def _identity(facts, rule_pack_ref, effective_at, _environment):
    return build_decision_identity(
        facts,
        rule_pack_ref,
        effective_at,
        fingerprint_key=b"seq7-witness-non-secret-test-key",
        fingerprint_key_id="seq7-witness-test",
    )


def _load(name: str):
    payload = load_rule_pack_payload(PACKS / name)
    return compiler.build_compiled_pack(
        wrap_as_unsigned_pack(payload), fact_registry=DEFAULT_FACT_REGISTRY
    )


def _load_raw(name: str) -> dict:
    return json.loads((PACKS / name).read_text())


@pytest.fixture(scope="module")
def seq6():
    return _load("rulepack-prod-006.source.json")


@pytest.fixture(scope="module")
def seq7():
    return _load("rulepack-prod-007.source.json")


@pytest.fixture(scope="module")
def seq6_raw():
    return _load_raw("rulepack-prod-006.source.json")


@pytest.fixture(scope="module")
def seq7_raw():
    return _load_raw("rulepack-prod-007.source.json")


def _decide(compiled, overrides):
    return evaluator.evaluate(
        gf.applicant_facts(overrides=overrides),
        compiled,
        effective_at=AT,
        observed_at=AT,
        identity_provider=_identity,
    )


def _offers(compiled, decision) -> list[str]:
    codes = {p.product_version_id: p.product_code for p in compiled.products}
    return sorted(codes.get(c.product_version_id, "?") for c in decision.candidates)


def _reachable_codes(raw: dict) -> set[str]:
    codes = {p["product_version_id"]: p["product_code"] for p in raw["products"]}
    supported = {
        pid
        for rule in raw["rules"]
        if rule["effect"]["type"] == "SUPPORT"
        for pid in (rule.get("product_version_ids") or [])
    }
    return {codes[pid] for pid in supported}


# ---------------------------------------------------------------------------
# Chain integrity
# ---------------------------------------------------------------------------


def test_previous_payload_sha256_chains_to_the_real_seq6_file(seq6_raw, seq7_raw):
    """seq-7's ``previous_payload_sha256`` must match the CANONICAL hash of
    the live seq-6 source file, recomputed here — not copied from the
    mandate or from seq-7's own claimed value."""
    canon = canonicalize_json(seq6_raw)
    actual = hashlib.sha256(canon).hexdigest()
    assert actual == "9691534c15e95821992d975f8f03a529aa5c46702b94ccf6f71fe7aba3ca83f6"
    assert seq7_raw["previous_payload_sha256"] == actual


def test_seq7_metadata(seq7_raw):
    assert seq7_raw["sequence"] == 7
    assert seq7_raw["version"] == "2026.8.11"
    assert seq7_raw["environment"] == "PRODUCTION"
    assert seq7_raw["jurisdiction"] == "ID"
    assert seq7_raw["rollback_of_payload_sha256"] is None


# ---------------------------------------------------------------------------
# Zero rule delta — the pack's only real content change is data, not logic
# ---------------------------------------------------------------------------


def test_zero_rules_added_or_removed(seq6_raw, seq7_raw):
    assert seq6_raw["rules"] == seq7_raw["rules"]
    assert len(seq7_raw["rules"]) == 104


def test_source_records_unchanged_except_one_locator_enrichment(seq6_raw, seq7_raw):
    """Every source record is byte-identical EXCEPT the shared Permenkumham
    22/2023 jo. 11/2024 record, whose ``locators`` array gains Pasal
    39/40/57/58/59 (a cross-family review finding: those Pasal were already
    the cited basis for E28C/E33A/E33B/E33C's sponsor_types but were never
    in this record's own structured locator list). ``content_sha256`` is
    unchanged — this is a citation-precision enrichment, not a content
    change — and seq-6's own copy of the record (a separate, immutable
    file) is untouched."""
    target_id = "9248b1d7-9172-54d9-ad61-251e83a2285b"
    by_id_before = {sr["source_record_id"]: sr for sr in seq6_raw["source_records"]}
    by_id_after = {sr["source_record_id"]: sr for sr in seq7_raw["source_records"]}
    assert set(by_id_before) == set(by_id_after)
    changed = [sid for sid in by_id_before if by_id_before[sid] != by_id_after[sid]]
    assert changed == [target_id]
    before_locators = {loc["value"] for loc in by_id_before[target_id]["locators"]}
    after_locators = {loc["value"] for loc in by_id_after[target_id]["locators"]}
    assert after_locators - before_locators == {
        "Pasal 39",
        "Pasal 40",
        "Pasal 57",
        "Pasal 58",
        "Pasal 59",
    }
    assert before_locators <= after_locators, "enrichment must never remove a locator"
    assert by_id_before[target_id]["content_sha256"] == by_id_after[target_id]["content_sha256"], (
        "the underlying document did not change, only the citation's precision"
    )


# ---------------------------------------------------------------------------
# The one real change: E28C's sponsor_types correction
# ---------------------------------------------------------------------------


def test_e28c_sponsor_types_corrected_to_none(seq6_raw, seq7_raw):
    e28c_before = next(p for p in seq6_raw["products"] if p["product_code"] == "E28C")
    e28c_after = next(p for p in seq7_raw["products"] if p["product_code"] == "E28C")
    assert e28c_before["sponsor_types"] == ["INDIVIDUAL"]
    assert e28c_after["sponsor_types"] == ["NONE"]
    # Pasal 39/40's basis is the same Permenkumham 22/2023/11/2024 record
    # E33A/E33B/E33C already cite for their own sponsor-clause Pasal.
    assert "9248b1d7-9172-54d9-ad61-251e83a2285b" in e28c_after["source_refs"]


def test_only_e28c_product_record_changed(seq6_raw, seq7_raw):
    by_code_before = {p["product_code"]: p for p in seq6_raw["products"]}
    by_code_after = {p["product_code"]: p for p in seq7_raw["products"]}
    assert set(by_code_before) == set(by_code_after)
    changed = [code for code in by_code_before if by_code_before[code] != by_code_after[code]]
    assert changed == ["E28C"]


def test_e28c_product_record_still_compiles_and_is_active(seq7):
    """The data correction must not break the product's own validity — it
    is not claimed to become SUPPORTED-reachable (it was never reachable;
    see test_reachability_is_unchanged_from_seq6 below)."""
    e28c = next(p for p in seq7.products if p.product_code == "E28C")
    assert e28c.product.status.value == "ACTIVE"
    assert tuple(t.value for t in e28c.product.sponsor_types) == ("NONE",)


# ---------------------------------------------------------------------------
# Regression: reachability set is byte-for-byte unchanged from seq-6
# ---------------------------------------------------------------------------


def test_reachability_is_unchanged_from_seq6(seq6_raw, seq7_raw):
    """Witness (v) from the mandate: no product loses support relative to
    seq-6.

    This check itself only proves a STATIC fact — which products have at
    least one SUPPORT rule bound to their ``product_version_id`` in the raw
    JSON — the same thing ``test_seq6_refuter_witnesses.py::
    test_reachability_is_what_the_document_claims`` measures upstream. It
    does not by itself prove those SUPPORT conditions are satisfiable, or
    that no HUMAN_REVIEW rule masks them at runtime (`evaluate_product()`
    returns REVIEW before SUPPORT coverage is ever applied — see the module
    docstring). The STRONGER behavioral claim — that seq-7 evaluates
    identically to seq-6 for every possible input, not just for this
    static count — follows deductively from two separately-verified facts,
    not from this count alone: `test_zero_rules_added_or_removed` (the rule
    set that `evaluate_product()` actually consumes is byte-identical) and
    the fact that `sponsor_types` on a product record is never read by the
    evaluator (checked directly: no reference to it outside `models.py`'s
    field declaration and `contract.schema.json`'s generated description).
    Both are separately pinned; this test's own job is only the narrower,
    static one its name says."""
    before = _reachable_codes(seq6_raw)
    after = _reachable_codes(seq7_raw)
    assert before == after
    assert len(after) == 27
    assert sorted({p["product_code"] for p in seq7_raw["products"]} - after) == [
        "E23U",
        "E23V",
        "E28B",
        "E28C",
        "E28D",
        "E28F",
        "E30E",
        "E30F",
        "E33A",
        "E33B",
        "E33C",
    ]


@pytest.mark.parametrize(
    "product_code,purposes,expected_reason_code",
    [
        ("E33A", ["EMPLOYMENT"], "GOVT_INVITATION_REQUIRED"),
        ("E33C", ["INVESTMENT"], "GOVT_INVITATION_REQUIRED"),
        ("E33B", ["EMPLOYMENT"], "E33B_EXPERTISE_QUALIFICATION_CHECK"),
    ],
)
def test_a_well_grounded_sponsor_answer_does_not_manufacture_an_offer(
    seq7, product_code, purposes, expected_reason_code
):
    """A "genuinely plausible" applicant for E33A/E33C/E33B — the correct
    statutory sponsor category, the purpose the product's own Hak clause
    names — still resolves to HUMAN_REVIEW_REQUIRED on seq-7, unchanged from
    seq-6, AND for the SAME reason as seq-6 (the pre-existing review rule,
    not some new sponsor.type-triggered path). Asserting the specific
    reason code, not just the global state, is the point: a global-state-only
    check would also pass if some unrelated review rule fired instead,
    which would not actually prove sponsor.type semantics stayed inert."""
    sponsor = "NONE" if product_code == "E33B" else "GOVERNMENT"
    decision = _decide(
        seq7,
        {
            "intent.requested_product_code": _known(product_code),
            "intent.purposes": _known(purposes),
            "sponsor.type": _known(sponsor),
        },
    )
    assert decision.state.value == "HUMAN_REVIEW_REQUIRED"
    assert product_code not in _offers(seq7, decision)
    review_codes = {r.code for r in decision.review_reasons}
    assert expected_reason_code in review_codes, review_codes


# ---------------------------------------------------------------------------
# The manufacture-risk finding, reproduced and pinned as a regression test
# against a synthetic pack for BOTH E33A and E33C (the codex refuter's own
# independent simulation confirmed the same two outcomes for E33C; this
# parametrization is what turns that confirmation into a repository check).
# These pin ONE specific bad shape each — a future author who reproduces
# either of these two exact `when`/`covered_purposes` combinations without
# reading the research note gets a red test, not a silent ship. They do NOT
# guarantee every conceivable future sponsor.type rule is safe; that
# judgment still has to be made fresh each time, against the real evaluator,
# the way this file's own tests were.
# ---------------------------------------------------------------------------


def _pvid(raw: dict, product_code: str) -> str:
    return next(
        p["product_version_id"] for p in raw["products"] if p["product_code"] == product_code
    )


def _with_synthetic_sponsor_rule(raw: dict, product_code: str, covered_purposes: list[str]) -> dict:
    raw = copy.deepcopy(raw)
    raw["rules"].append(
        {
            "rule_id": f"el.{product_code.lower()}.sponsor-government.HYPOTHETICAL",
            "stage": "ELIGIBILITY",
            "scope": "PRODUCTS",
            "priority": 100,
            "valid_period": {"from": "2026-07-24T00:00:00Z", "to": None},
            "when": {
                "op": "all",
                "args": [
                    {"op": "eq", "fact": "intent.requested_product_code", "value": product_code},
                    {"op": "eq", "fact": "sponsor.type", "value": "GOVERNMENT"},
                ],
            },
            "effect": {
                "type": "SUPPORT",
                "reason_code": f"{product_code}_SPONSOR_GOVERNMENT_HYPOTHETICAL",
                "covered_purposes": covered_purposes,
            },
            "on_unknown": "NEEDS_INPUT",
            "required_facts": ["intent.requested_product_code", "sponsor.type"],
            "source_refs": ["6f5135f2-1f77-571f-88ed-26d1d2b9efba"],
            "explanation_key": f"explain.el.{product_code.lower()}.sponsor-government.hypothetical",
            "safety_critical": False,
            "product_version_ids": [_pvid(raw, product_code)],
        }
    )
    return raw


def _compile_raw(raw: dict):
    fd, name = tempfile.mkstemp(suffix=".json")
    path = Path(name)
    try:
        with open(fd, "w") as f:
            json.dump(raw, f)
        payload = load_rule_pack_payload(path)
        return compiler.build_compiled_pack(
            wrap_as_unsigned_pack(payload), fact_registry=DEFAULT_FACT_REGISTRY
        )
    finally:
        path.unlink(missing_ok=True)


# (product_code, review-scoped purpose, full product covered_purposes,
# a purpose the review rule does NOT police but the product's own record
# still covers)
_SPONSOR_ONLY_CASES = [
    ("E33A", "EMPLOYMENT", ["EMPLOYMENT", "TOURISM", "FAMILY"], "TOURISM"),
    ("E33C", "INVESTMENT", ["INVESTMENT", "BUSINESS_MEETINGS", "TOURISM", "FAMILY"], "TOURISM"),
]


@pytest.mark.parametrize(
    "product_code,review_purpose,_full_purposes,sidestep_purpose", _SPONSOR_ONLY_CASES
)
def test_narrow_sponsor_only_eligibility_rule_is_dead_code(
    seq6_raw, product_code, review_purpose, _full_purposes, sidestep_purpose
):
    """covered_purposes matching only the review rule's own purpose scope:
    never contributes the product to the decision, for anyone.

    ``intent.stay_days`` is pinned to 1825 (both products' own stay-policy
    minimum, a multi-year second-home-style stay) in both cases specifically
    to exclude short-stay tourism products (C1/A1/B1) from independently
    satisfying the sidestep-purpose branch — without it, the gold baseline's
    other facts let an unrelated product supply a real offer and the
    assertion would measure the wrong thing."""
    compiled = _compile_raw(_with_synthetic_sponsor_rule(seq6_raw, product_code, [review_purpose]))
    review_decision = _decide(
        compiled,
        {
            "intent.requested_product_code": _known(product_code),
            "intent.purposes": _known([review_purpose]),
            "intent.stay_days": _known(1825),
            "sponsor.type": _known("GOVERNMENT"),
        },
    )
    assert review_decision.state.value == "HUMAN_REVIEW_REQUIRED"
    assert product_code not in _offers(compiled, review_decision)
    sidestep_decision = _decide(
        compiled,
        {
            "intent.requested_product_code": _known(product_code),
            "intent.purposes": _known([sidestep_purpose]),
            "intent.stay_days": _known(1825),
            "sponsor.type": _known("GOVERNMENT"),
        },
    )
    assert sidestep_decision.state.value == "NO_SUPPORTED_PATH"
    assert product_code not in _offers(compiled, sidestep_decision)


@pytest.mark.parametrize(
    "product_code,_review_purpose,full_purposes,sidestep_purpose", _SPONSOR_ONLY_CASES
)
def test_broad_sponsor_only_eligibility_rule_manufactures_an_offer(
    seq6_raw, product_code, _review_purpose, full_purposes, sidestep_purpose
):
    """covered_purposes matching the product's full product-record value:
    offers the product to an applicant whose ONLY stated purpose is one the
    review rule never inspects, and who merely answers "government" to the
    sponsor question, with zero check of the product's actual substantive
    requirement (a confirmed central-government invitation, Pasal 57/59).
    This is the shape that must never ship — pinned here so it stays
    provably unshippable, for both E33A and E33C."""
    compiled = _compile_raw(_with_synthetic_sponsor_rule(seq6_raw, product_code, full_purposes))
    sidestep_decision = _decide(
        compiled,
        {
            "intent.requested_product_code": _known(product_code),
            "intent.purposes": _known([sidestep_purpose]),
            "intent.stay_days": _known(1825),
            "sponsor.type": _known("GOVERNMENT"),
        },
    )
    assert sidestep_decision.state.value == "SUPPORTED_CANDIDATES"
    assert product_code in _offers(compiled, sidestep_decision), (
        f"if this ever stops offering {product_code}, the finding this test "
        "pins no longer reproduces and the module docstring's claim needs "
        "re-checking"
    )
