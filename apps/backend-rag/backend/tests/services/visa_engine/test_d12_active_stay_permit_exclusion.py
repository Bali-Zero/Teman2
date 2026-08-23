"""``hf.d12-active-stay-permit-excluded`` — the D12 HARD_FILTER drafted for
a future seq-14 fold (E5 increment 8, author v2-d12).

This test is deliberately NOT built against any ``rulepack-prod-*.source.json``
file — no such file with this rule exists yet, and the fold that will add it
has to wait for seq-13 to be signed and activated (its rule_pack_id/sequence
chain off seq-13's SIGNED payload hash, which does not exist while seq-13 is
still mid-review). Instead this proves the RULE's evaluator-level behavior in
isolation against a synthetic, hand-built minimal payload (``conftest.py``'s
``make_*`` builders — the same pattern every other ``visa_engine`` unit test
in this directory uses for non-pack-specific checks), and separately proves
the draft JSON that will actually be folded in (
``research/visa/doctrine-factory/e5/inc8-pack-edits/d12-active-stay-permit-rule-and-source.json``)
parses into valid ``models.Rule``/``models.SourceRecord`` objects today. When
the real fold lands, its own pack-level test (mirroring
``test_seq13_rules_pack.py``'s pattern) is the integration proof; this file
stays as the unit-level guilt/innocence pin for the rule's own logic.

Owner ruling being encoded (fact_registry.py's ``_derive_has_active_stay_permit``
docstring, verbatim): "an applicant WITH an active KITAS is excluded from D12."
Tri-state safety is the point under test as much as the exclusion itself — an
UNKNOWN current-status must never be silently read as "no active permit."

LIVE, NOT DORMANT as of PR #4695 (merged 2026-08-23T14:56:27Z, SHA
``88faa0e0450a4986730829b8d2990229b11bf216``): ``derived.has_active_stay_permit``
can only resolve KNOWN(True) when ``immigration.current_status_code`` matches
an E-series shape (``^E\\d+[A-Z]?$``), and until #4695 the live mouth
interview's ``CURRENT_STATUS_CODES`` enum had no E-series member — this rule
was drafted, correct, and reachable only via a direct API payload, not via
the public interview. That gap is now closed: #4695 added a two-step gate
("do you hold a stay permit?" then a 29-code E-series selector, transcribed
from the applicant's own KITAS/KITAP card, wired to
``immigration.current_status_code``) — verified this session, programmatically,
that all 29 codes match ``_STAY_PERMIT_STATUS_CODE_SHAPE`` (0 mismatches,
`fact_registry.py:99`), so no code the interview can now send resolves to a
silently-useless UNKNOWN. **This rule therefore ships enforcing from the
moment its own fold (seq-14, still pending seq-13) activates — it will exclude
a real applicant on day one, not merely be correct-but-unreachable.** The
former dormancy tripwire (`test_declared_dormancy_no_interview_status_code_is_e_series_shaped`)
stayed GREEN through #4695's merge for a structural reason worth recording:
it is a backend-only Python test asserting a hardcoded snapshot of the OLD
8 non-E codes, and #4695 touched only `apps/mouth` frontend files — a
backend test has no mechanism to observe a frontend-only diff, so the
"red means the extension landed" framing this file originally carried was
built on a premise that never actually held. Replaced (and, after a further review round, RENAMED and NARROWED — the
first replacement's own claim to "prove reachability... for the full
catalogue the interview can actually send" repeated the exact
cross-boundary mistake being fixed, just with a JSON-sourced list instead
of a hardcoded one; reading a file is not the same as observing the
frontend) by `test_e_series_shape_activates_permit_fact_visit_class_shape_does_not`
below, which proves the DERIVATION's shape rule only — E-shaped codes
activate, the 8 old visit-class codes do not — using real product codes as
representative examples, not as a claim about the interview's live
offering. Whether `fact-mapper.ts`'s actual arrays match either list is
UNVERIFIED by any automated check; see the PENDING-ARMS row "v2-d12,
interview-catalogue cross-boundary sync unverified" for the real cure.

The inclusive expiry-boundary case tested below ("expiring today is still
active") is NOT this rule's own judgment call — it is inherited from
``_derive_has_active_stay_permit``'s pre-existing, engine-wide convention
(that function's own docstring: "mirrors ``_derive_age_years``'s own
reference-date comparison"), authored in #4650, not here. This file pins
that inherited behavior; it does not assert it as a new decision. Whether a
real KITAS/ITAS document's "valid until DD-MM-YYYY" is itself inclusive of
that date under Indonesian immigration practice is NOT independently
verified anywhere in this codebase — the `_derive_age_years` analogy is an
internal consistency choice, not a cited legal fact. If that assumption is
ever wrong, the fix belongs in the shared derivation function, not here.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.scripts.visa_engine.compile_pack import wrap_as_unsigned_pack
from backend.services.visa_engine import compiler, evaluator
from backend.services.visa_engine import models as M
from backend.services.visa_engine.enums import FactPath
from backend.services.visa_engine.evaluator import ProductProof, ProductProofStatus
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY
from backend.tests.services.visa_engine.conftest import (
    make_applicant_facts,
    make_product,
    make_rule_pack_payload,
    make_source_record,
    make_support_rule,
)

AT = datetime(2026, 8, 23, 12, 0, 0, tzinfo=timezone.utc)

_DRAFT_JSON = (
    Path(__file__).resolve().parents[6]
    / "research/visa/doctrine-factory/e5/inc8-pack-edits"
    / "d12-active-stay-permit-rule-and-source.json"
)


def _known(value: Any) -> dict[str, Any]:
    return {"status": "KNOWN", "value": value}


def _unknown(reason: str = "NOT_ASKED") -> dict[str, Any]:
    return {"status": "UNKNOWN", "reason": reason}


# ---------------------------------------------------------------------------
# Part 1 — the draft artifact that will actually be folded parses cleanly
# ---------------------------------------------------------------------------


def test_draft_source_record_and_rule_are_schema_valid() -> None:
    """The exact JSON staged for the future seq-14 fold — not a copy of it —
    round-trips through the real Pydantic models with no coercion needed.
    Guards against the draft silently drifting from the schema between now
    and whenever the fold actually runs.
    """

    draft = json.loads(_DRAFT_JSON.read_text())

    source_kwargs = {k: v for k, v in draft["source_record"].items() if not k.startswith("_")}
    record = M.SourceRecord(**source_kwargs)
    assert record.authority_type == "BALI_ZERO_POLICY"
    assert record.canonical_url == (
        "research/visa/doctrine-factory/e5/inc8-pack-edits/"
        "d12-active-stay-permit-policy-2026-08-23.md"
    )

    rule_kwargs = {k: v for k, v in draft["rule_insertion"].items() if not k.startswith("_")}
    rule = M.Rule(**rule_kwargs)
    assert rule.rule_id == "hf.d12-active-stay-permit-excluded"
    assert rule.stage == "HARD_FILTER"
    assert rule.effect.type == "EXCLUDE"
    assert rule.on_unknown == "NEEDS_INPUT"


def test_draft_source_record_content_sha256_matches_the_actual_policy_doc() -> None:
    """The one guarantee a BALI_ZERO_POLICY source pointed at a repo file can
    make that an OFLFICIAL_PORTAL source never can: the hash is exactly
    reproducible, forever, by hashing the cited file's own bytes — no CSRF
    token, no session state, no "which fetch" ambiguity. Prove it holds today
    rather than merely asserting it in prose.
    """

    import hashlib

    draft = json.loads(_DRAFT_JSON.read_text())
    cited_path = _DRAFT_JSON.parent / "d12-active-stay-permit-policy-2026-08-23.md"
    actual_sha256 = hashlib.sha256(cited_path.read_bytes()).hexdigest()
    assert draft["source_record"]["content_sha256"] == actual_sha256


# ---------------------------------------------------------------------------
# Part 2 — the rule's evaluator-level behavior, isolated
# ---------------------------------------------------------------------------

_PRODUCT_VERSION_ID = uuid.uuid4()
_SOURCE_RECORD_ID = uuid.uuid4()

_EXCLUSION_RULE = M.Rule(
    rule_id="hf.d12-active-stay-permit-excluded",
    stage="HARD_FILTER",
    scope="PRODUCTS",
    product_version_ids=[_PRODUCT_VERSION_ID],
    priority=100,
    valid_period={"from": AT - timedelta(days=1), "to": None},
    when={"fact": "derived.has_active_stay_permit", "op": "eq", "value": True},
    effect={"type": "EXCLUDE", "reason_code": "D12_ACTIVE_STAY_PERMIT_EXCLUDED"},
    on_unknown="NEEDS_INPUT",
    required_facts=["derived.has_active_stay_permit"],
    source_refs=[_SOURCE_RECORD_ID],
    explanation_key="explain.hf.d12-active-stay-permit-excluded",
    safety_critical=False,
)


def _compiled_pack() -> compiler.CompiledRulePack:
    support_rule = make_support_rule(
        rule_id="el.d12-multi-entry-support",
        product_version_ids=[_PRODUCT_VERSION_ID],
        source_refs=[_SOURCE_RECORD_ID],
        covered_purposes=["INVESTMENT"],
    )
    payload = make_rule_pack_payload(
        rules=[_EXCLUSION_RULE, support_rule],
        products=[
            make_product(
                product_version_id=_PRODUCT_VERSION_ID,
                source_refs=[_SOURCE_RECORD_ID],
                product_code="D12",
                covered_purposes=["INVESTMENT"],
            )
        ],
        source_records=[make_source_record(source_record_id=_SOURCE_RECORD_ID)],
        sequence=1,
    )
    report = compiler.compile_rule_pack(
        wrap_as_unsigned_pack(payload, observed_at=AT), fact_registry=DEFAULT_FACT_REGISTRY
    )
    assert report.ok, [f"{e.code}: {e.message}" for e in report.errors]
    return compiler.build_compiled_pack(
        wrap_as_unsigned_pack(payload, observed_at=AT), fact_registry=DEFAULT_FACT_REGISTRY
    )


def _proof(overrides: dict[str, Any]) -> ProductProof:
    base = {
        "intent.purposes": _known(["INVESTMENT"]),
        "immigration.current_status_code": _unknown(),
        "immigration.current_status_expiry": _unknown(),
    }
    base.update(overrides)
    baseline = make_applicant_facts()
    merged = dict(baseline.facts.model_dump(by_alias=True, mode="json"))
    merged.update(base)
    # Rebuild through full construction (not model_copy, which does not
    # re-validate) so `facts.facts` becomes the real validated sub-model
    # again, not a raw dict — model_dump() downstream needs the former.
    facts = M.ApplicantFacts(
        schema_version=baseline.schema_version,
        assessment_id=baseline.assessment_id,
        collected_at=baseline.collected_at,
        facts=merged,
    )
    snapshot = DEFAULT_FACT_REGISTRY.derive(facts, effective_at=AT)
    compiled = _compiled_pack()
    product = next(p for p in compiled.products if p.product_code == "D12")
    rules = compiled.rules_for(product, effective_at=AT)
    purposes = frozenset(snapshot.values[FactPath.INTENT_PURPOSES].value)
    return evaluator.evaluate_product(
        product=product,
        rules=rules,
        facts=snapshot,
        purposes=purposes,
        fact_registry=DEFAULT_FACT_REGISTRY,
    )


def _reason_codes(proof: ProductProof) -> set[str]:
    return {r.code for r in proof.reasons}


def test_active_e_series_permit_not_expired_excludes_d12() -> None:
    """Guilt case: an E-shaped current-status code with a future expiry is
    exactly what an owner-ruling-compliant applicant looks like — D12 must
    exclude them.
    """

    proof = _proof(
        {
            "immigration.current_status_code": _known("E30"),
            "immigration.current_status_expiry": _known(
                (AT.date() + timedelta(days=180)).isoformat()
            ),
        }
    )
    assert proof.status is ProductProofStatus.EXCLUDED
    assert "D12_ACTIVE_STAY_PERMIT_EXCLUDED" in _reason_codes(proof)


def test_visit_class_status_code_does_not_exclude_and_d12_still_supports() -> None:
    """Innocence case: a visit-class code (C1) is definitively not a
    residence permit regardless of its own expiry — the exclusion must not
    fire, and D12 must still reach SUPPORTED through its own support rule
    (proving the filter doesn't merely "not exclude" but leaves the rest of
    the product's evaluation genuinely untouched).
    """

    proof = _proof(
        {
            "immigration.current_status_code": _known("C1"),
            "immigration.current_status_expiry": _known("2020-01-01"),
        }
    )
    assert proof.status is ProductProofStatus.SUPPORTED
    assert "D12_ACTIVE_STAY_PERMIT_EXCLUDED" not in _reason_codes(proof)


def test_expired_e_series_permit_does_not_exclude() -> None:
    """Innocence case, the specific nuance the owner ruling and the
    derivation's own docstring both call out explicitly: an EXPIRED permit
    is a real, tested POSITIVE False, not an exclusion — the owner ruled
    that person CAN apply. A cure that collapsed "has an E-series code" into
    "excluded" without checking expiry would fail exactly this case.
    """

    proof = _proof(
        {
            "immigration.current_status_code": _known("E28A"),
            "immigration.current_status_expiry": _known(
                (AT.date() - timedelta(days=1)).isoformat()
            ),
        }
    )
    assert proof.status is ProductProofStatus.SUPPORTED
    assert "D12_ACTIVE_STAY_PERMIT_EXCLUDED" not in _reason_codes(proof)


def test_expiring_today_is_still_active_inclusive_boundary() -> None:
    """A permit expiring exactly on ``effective_at``'s date is still active
    that day. This is NOT a judgment this rule makes: it pins the pre-existing
    ``_derive_has_active_stay_permit`` convention (``expiry_date >=
    reference_date``, that function's own docstring: "mirrors
    ``_derive_age_years``'s own reference-date comparison") — an engine-wide
    date-boundary choice from #4650, not a D12-specific decision.

    RULED, 2026-08-23 (upgraded from inference): Zero ruled directly on this,
    verbatim in Italian, "si valido fino alle 10pm del giorno" — a permit
    stated as valid "until DD-MM-YYYY" is valid through that date, until
    22:00. See ``.claude/skills/modus/PENDING-ARMS.md``'s "v2-d12, Zero's
    ruling on the permit-validity axis" row and the policy doc's "Boundary
    choice" section for the full record. Before this ruling, the boundary
    here was inherited-but-unverified (the ``_derive_age_years`` analogy was
    internal consistency, not an external authority); it is now grounded.
    One gap the ruling itself introduces, not closed by this test: it names
    a TIME (22:00) while this derivation compares DATES only, so a two-hour
    window between 22:00 and midnight on the expiry date is technically
    mismatched — judged immaterial for an eligibility-only tool, recorded in
    the PENDING-ARMS row and the policy doc rather than silently accepted.
    This test still only proves the rule correctly inherits whatever the
    shared derivation decides, and would catch a strict '<' vs '<=' slip in
    EITHER that function or this rule's own condition.
    """

    proof = _proof(
        {
            "immigration.current_status_code": _known("E23"),
            "immigration.current_status_expiry": _known(AT.date().isoformat()),
        }
    )
    assert proof.status is ProductProofStatus.EXCLUDED


def test_unknown_current_status_code_is_blocked_unknown_never_admits() -> None:
    """Fail-closed case: the applicant never answered the current-status
    question at all. Must ask (BLOCKED_UNKNOWN via on_unknown=NEEDS_INPUT),
    never silently resolve to SUPPORTED — a False guess here would wrongly
    ADMIT an applicant who might hold an active permit.
    """

    proof = _proof({})  # both current_status_code and _expiry default UNKNOWN
    assert proof.status is ProductProofStatus.BLOCKED_UNKNOWN
    assert proof.status is not ProductProofStatus.SUPPORTED


def test_known_e_series_code_but_unknown_expiry_is_blocked_unknown() -> None:
    """The code alone looks like a stay permit, but its validity cannot be
    confirmed without the expiry — must still ask, never guess either
    direction.
    """

    proof = _proof({"immigration.current_status_code": _known("E33")})
    assert proof.status is ProductProofStatus.BLOCKED_UNKNOWN


def test_unrecognized_code_shape_is_blocked_unknown_not_a_guess() -> None:
    """A code that is neither a known visit-class code nor E-series shaped
    (typo, legacy code, unrecognized permit class) must surface as UNKNOWN,
    never be silently classified either way.
    """

    proof = _proof({"immigration.current_status_code": _known("ZZ99")})
    assert proof.status is ProductProofStatus.BLOCKED_UNKNOWN


# ---------------------------------------------------------------------------
# Part 3 — declared dormancy via the live interview, re-verified here so a
# future edit to fact-mapper.ts silently un-breaks (or re-breaks) this
# without anyone noticing
# ---------------------------------------------------------------------------


def test_e_series_shape_activates_permit_fact_visit_class_shape_does_not() -> None:
    """Successor to ``test_declared_dormancy_no_interview_status_code_is_e_series_shaped``,
    replaced rather than patched (see the module docstring's "LIVE, NOT
    DORMANT" section for why the original went — and had to go — GREEN
    through #4695's merge instead of red: it was a backend-only Python test
    with a hardcoded snapshot of the OLD codes, and #4695 touched only
    ``apps/mouth`` frontend files — there was never a mechanism by which a
    Python test could observe that diff).

    RENAMED AND NARROWED after team-lead's review of the first replacement
    (which iterated `rulepack-prod-007.source.json`'s 29 E-prefix product
    codes and claimed this "proves reachability... for the full catalogue
    the interview can actually send"). That claim was wrong for the same
    structural reason the original tripwire was: this file cannot read
    ``fact-mapper.ts``, so it cannot know what the interview currently
    offers — asserting a Python-side catalogue matches the frontend's
    ``STAY_PERMIT_CODES`` array is exactly the cross-boundary claim a
    backend test cannot back up, hardcoded-in-Python or read-from-JSON
    makes no difference: neither observes the TS file.

    **What this test CAN and DOES prove — a genuinely backend-only
    property**: ``derived.has_active_stay_permit``'s derivation activates
    on E-series-SHAPED codes (``^E\\d+[A-Z]?$``) and does not activate on
    the original 8 visit-class codes, regardless of which specific codes
    any frontend chooses to offer. The E-shaped examples below are drawn
    from ``rulepack-prod-007.source.json``'s real product catalogue — used
    here only as realistic, valid instances of the shape, not as a claim
    about the interview's live offering.

    **What this test CANNOT and does NOT prove, stated so the limitation is
    visible rather than implied by a green result**: whether
    ``fact-mapper.ts``'s actual ``STAY_PERMIT_CODES``/``CURRENT_STATUS_CODES``
    arrays match either list below. That agreement is UNVERIFIED by any
    automated check today — see the PENDING-ARMS row "v2-d12,
    interview-catalogue cross-boundary sync unverified" for the real cure
    (a shared generated artifact or a frontend-side test, not a pytest
    parsing TypeScript).

    **Why seq-7 specifically, not "whichever pack is current" — a
    deliberate pin, verified stable, not an accident of which file was
    open.** This test always reads ``rulepack-prod-007.source.json``, never
    the live sequence. Checked empirically this session (not assumed): the
    E-prefix ``LIMITED_STAY`` product-code set is BYTE-IDENTICAL across
    every signed/rules-only pack this repo has — seq-7 (this pin), seq-12
    (current production as of this draft), and seq-13 (about to activate,
    rules-only, ``rules-only.json`` still carries a full ``products`` array)
    — 29/29 codes, zero additions, zero removals, across the entire
    observed history. Product-code identifiers are a fundamentally
    lower-churn space than the RULES layered over them (which have moved
    seq-9 through seq-13 in this same window): a code corresponds to a
    distinct legal visa product type, added rarely by regulatory event and,
    once granted, not observed to be retired even when a product goes
    dormant/BLOCKED (see the catalogue-wide restriction sweep,
    ``research/visa/2026-08-23-catalogue-wide-name-encoded-restriction-sweep.md``,
    for products that are unreachable in practice yet still carry a live
    code). On that evidence the pin is a reasonable choice, not merely an
    untested one — though "stable across everything observed so far" is
    what was actually checked, not a guarantee against a future regulatory
    catalogue change no test here could see coming either way.
    """

    import json
    from pathlib import Path

    pack_path = (
        Path(__file__).resolve().parents[6]
        / "apps/backend-rag/backend/services/visa_engine/contracts/packs"
        / "rulepack-prod-007.source.json"
    )
    catalogue = json.loads(pack_path.read_text())
    e_shaped_examples = sorted(
        prod["product_code"]
        for prod in catalogue["products"]
        if prod.get("category") == "LIMITED_STAY" and prod["product_code"].startswith("E")
    )
    assert len(e_shaped_examples) > 0, "expected at least one E-shaped example product code"

    for code in e_shaped_examples:
        proof = _proof(
            {
                "immigration.current_status_code": _known(code),
                "immigration.current_status_expiry": _known(
                    (AT.date() + timedelta(days=180)).isoformat()
                ),
            }
        )
        assert proof.status is ProductProofStatus.EXCLUDED, (
            f"{code} is E-shaped and unexpired but did NOT exclude D12 — "
            f"the derivation is not reachable for this shape despite "
            f"matching _STAY_PERMIT_STATUS_CODE_SHAPE"
        )
        assert "D12_ACTIVE_STAY_PERMIT_EXCLUDED" in _reason_codes(proof)

    non_e_shaped_codes = [
        "A1",
        "C1",
        "C2",
        "C6",
        "ITK_FROM_BVK",
        "ITK_FROM_VISIT_C",
        "ITK_FROM_VISIT_D",
        "ITK_PERALIHAN",
    ]
    for code in non_e_shaped_codes:
        proof = _proof(
            {
                "immigration.current_status_code": _known(code),
                "immigration.current_status_expiry": _known(
                    (AT.date() + timedelta(days=180)).isoformat()
                ),
            }
        )
        assert proof.status is not ProductProofStatus.EXCLUDED, (
            f"{code} is not E-shaped but unexpectedly excluded D12 — the "
            f"derivation's shape check has regressed"
        )
