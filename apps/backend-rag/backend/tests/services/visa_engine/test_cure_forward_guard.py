"""Sequence-agnostic forward guard for the E5 inc-4 cure (seq-10):
``el.c2.corporate-sponsor-type`` retired, ``el.e31c-mixed-marriage-parents``
tightened to 4 conjuncts, ``hf.e31c-marriage-not-registered`` inserted.

Why this module exists (it is NOT a duplicate of ``test_seq10_pack.py``'s
``TestCureStructure``/``TestE31CMarriageGateWitnesses``): that module pins
the cure against the LITERAL seq-10 file. ``test_seq11_pack.py`` and
``test_seq12_pack.py`` assert byte-invariance of ``rules``/``products`` as
WHOLE collections against their immediate predecessor — true today only
because those two folds declare zero rule edits. The first fold that DOES
edit rules (seq-13 is slated to carry E30-family pricing) is
byte-invariance-exempt by construction, and at that moment nothing on disk
asserts the cure survived the edit. This module closes that gap by
re-deriving the cure's structural and behavioural shape against WHATEVER
pack is highest-sequence on disk, so it keeps biting at seq-13, seq-14, ...
with no edit to this file.

Discovery authority — ``.source.json``, not ``.signed.json``: every
sequence on disk has a source file; two historical sequences
(``rulepack-prod-005``, ``rulepack-prod-008``) have NO signed counterpart
(superseded before activation) — gating discovery on ``.signed.json`` would
silently skip exactly that case, and would misidentify "the current tip"
for any fold that ships its source file before its signing step (the
pattern ``test_seq12_pack.py``'s docstring itself calls out: "seq-12 ships
in the same PR as its fold"). The source file is also sufficient for both
halves of this guard: ``load_rule_pack_payload`` + ``wrap_as_unsigned_pack``
(the same helper ``test_seq10_pack.py``'s ``_compiled`` uses) builds a real
``CompiledRulePack`` from it directly, no signed envelope required.

Two halves, per the mandate:

(a) structural — ``el.c2.corporate-sponsor-type`` absent;
    ``el.e31c-mixed-marriage-parents`` present with its exact 4-conjunct
    semantic shape (fact/op/value triples, never a JSON blob string —
    field reordering must not produce a false red); ``hf.e31c-marriage
    -not-registered`` present, HARD_FILTER/EXCLUDE/safety_critical,
    ``on_unknown=NEEDS_INPUT``, scoped to its exact 3-conjunct shape.
(b) behavioural — evaluator witnesses (house pattern
    ``test_seq9_new_rule_witnesses.py``/``test_seq10_pack.py``: per-product
    ``evaluate_product``, never the aggregated ``Decision``) for guilt,
    innocence, tri-state, and non-contamination on the highest pack.

Plus a `TestConjunctCheckerIsNotVacuous` class: positive-control tests
(house pattern: ``test_seq12_pack.py``'s
``test_positive_control_checker_detects_a_mutated_record``) that mutate a
COPY of the real rule dicts in memory (never a file on disk) to reintroduce
each historical defect shape and prove the semantic-set checker actually
distinguishes them from the cured shape — permanent, runs on every
invocation, never just a one-off manual demonstration.

Finally, a separate, clearly-banner-divided section pins a DIFFERENT,
still-open defect discovered against the real evaluator: E31C's
NATIONALITY leg is unenforced (``el.e31c-child-mixed-marriage-support``,
2 conjuncts, no nationality/marriage gate, independently sufficient for
SUPPORTED under the ``COVER_ALL_DECLARED_PURPOSES`` OR-like hit-policy).
seq-10's cure closed the REGISTRATION leg only. See the banner comment
immediately above ``TestE31CNationalityGapKnownOpen`` for the full
mechanism and — most importantly — what a future session must do when
that class starts failing (it means the gap was finally cured; do not
just re-widen the assertion).
"""

from __future__ import annotations

import copy
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine.compile_pack import (
    load_rule_pack_payload,
    wrap_as_unsigned_pack,
)
from backend.services.visa_engine import compiler, evaluator
from backend.services.visa_engine.enums import FactPath
from backend.services.visa_engine.evaluator import ProductProof, ProductProofStatus
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY
from backend.tests.services.visa_engine import _gold_fixtures as gf

_REPO_ROOT = Path(__file__).resolve().parents[6]
_PACKS_DIR = (
    _REPO_ROOT
    / "apps"
    / "backend-rag"
    / "backend"
    / "services"
    / "visa_engine"
    / "contracts"
    / "packs"
)

_SEQ_RE = re.compile(r"^rulepack-prod-(\d+)\.source\.json$")

_RETIRED_RULE_ID = "el.c2.corporate-sponsor-type"
_EDITED_RULE_ID = "el.e31c-mixed-marriage-parents"
_INSERTED_RULE_ID = "hf.e31c-marriage-not-registered"

_E31C_SUPPORT_CONJUNCTS = frozenset(
    {
        ("intent.purposes", "intersects", ("FAMILY",)),
        ("family.relation_to_sponsor", "eq", "PARENT"),
        ("family.sponsor_nationalities", "intersects", ("ID",)),
        ("family.marriage_registered", "eq", True),
    }
)
_HF_EXCLUDE_CONJUNCTS = frozenset(
    {
        ("intent.purposes", "intersects", ("FAMILY",)),
        ("family.relation_to_sponsor", "eq", "PARENT"),
        ("family.marriage_registered", "eq", False),
    }
)

# Any instant on/after both target rules' valid_period.from
# (el.e31c-mixed-marriage-parents: 2026-07-24T00:00:00Z;
# hf.e31c-marriage-not-registered: 2026-08-19T00:00:00Z, seq-10) and inside
# every inherited rule's window. seq-11/seq-12 declare zero rule edits, so
# this stays valid forward; if a future fold ever moves either rule's own
# valid_period.from later than this instant, bump it — the structural
# checks below do not depend on it and will keep catching drift regardless.
AT = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)


def _discover_highest_pack_path() -> Path:
    candidates: list[tuple[int, Path]] = []
    for path in _PACKS_DIR.glob("rulepack-prod-*.source.json"):
        match = _SEQ_RE.match(path.name)
        if match:
            candidates.append((int(match.group(1)), path))
    assert candidates, f"no rulepack-prod-*.source.json found under {_PACKS_DIR}"
    candidates.sort(key=lambda pair: pair[0])
    return candidates[-1][1]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_rule(rules: list[dict[str, Any]], rule_id: str) -> dict[str, Any]:
    return next(r for r in rules if r["rule_id"] == rule_id)


def _conjunct(arg: dict[str, Any]) -> tuple[str, str, Any]:
    fact = arg["fact"]
    op = arg["op"]
    if op in ("intersects", "in"):
        value: Any = tuple(sorted(arg["values"]))
    else:
        value = arg["value"]
    return (fact, op, value)


def _conjuncts(when: dict[str, Any]) -> frozenset[tuple[str, str, Any]]:
    """Semantic content of an ``all`` condition as a set of (fact, op,
    value) triples — immune to key reordering or list ordering, which a
    raw JSON-blob-string comparison would NOT be."""
    assert when["op"] == "all", f"expected a top-level 'all', got {when['op']!r}"
    return frozenset(_conjunct(a) for a in when["args"])


def _compiled_from_path(path: Path) -> compiler.CompiledRulePack:
    payload = load_rule_pack_payload(path)
    return compiler.build_compiled_pack(
        wrap_as_unsigned_pack(payload), fact_registry=DEFAULT_FACT_REGISTRY
    )


@pytest.fixture(scope="module")
def highest_pack_path() -> Path:
    return _discover_highest_pack_path()


@pytest.fixture(scope="module")
def highest_source(highest_pack_path: Path) -> dict[str, Any]:
    return _read_json(highest_pack_path)


@pytest.fixture(scope="module")
def highest_compiled(highest_pack_path: Path) -> compiler.CompiledRulePack:
    return _compiled_from_path(highest_pack_path)


def _known(value: Any) -> dict[str, Any]:
    return {"status": "KNOWN", "value": value}


def _proof(
    compiled: compiler.CompiledRulePack, product_code: str, overrides: dict[str, Any]
) -> ProductProof:
    facts = gf.applicant_facts(overrides=overrides)
    snapshot = DEFAULT_FACT_REGISTRY.derive(facts, effective_at=AT)
    product = next(p for p in compiled.products if p.product_code == product_code)
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


# ---------------------------------------------------------------------------
# discovery sanity — the guard is actually looking at something recent
# ---------------------------------------------------------------------------


class TestDiscovery:
    def test_highest_pack_is_at_least_seq10(self, highest_source: dict[str, Any]) -> None:
        """The cure landed in seq-10; a discovered pack older than that
        would mean the glob/regex broke, not that the cure regressed."""
        assert highest_source["sequence"] >= 10


# ---------------------------------------------------------------------------
# (a) structural — c2 absent, e31c tightened, hf inserted
# ---------------------------------------------------------------------------


class TestC2Retired:
    def test_c2_rule_id_absent(self, highest_source: dict[str, Any]) -> None:
        ids = {r["rule_id"] for r in highest_source["rules"]}
        assert _RETIRED_RULE_ID not in ids


class TestE31CSupportRuleShape:
    def test_present_with_exact_four_conjuncts(self, highest_source: dict[str, Any]) -> None:
        rule = _find_rule(highest_source["rules"], _EDITED_RULE_ID)
        assert _conjuncts(rule["when"]) == _E31C_SUPPORT_CONJUNCTS

    def test_stage_and_effect(self, highest_source: dict[str, Any]) -> None:
        rule = _find_rule(highest_source["rules"], _EDITED_RULE_ID)
        assert rule["stage"] == "ELIGIBILITY"
        assert rule["effect"]["type"] == "SUPPORT"
        assert rule["effect"]["reason_code"] == "REQ_MIXED_MARRIAGE_PARENTS"


class TestHardFilterShape:
    def test_present_with_exact_three_conjuncts(self, highest_source: dict[str, Any]) -> None:
        rule = _find_rule(highest_source["rules"], _INSERTED_RULE_ID)
        assert _conjuncts(rule["when"]) == _HF_EXCLUDE_CONJUNCTS

    def test_stage_effect_and_safety_flags(self, highest_source: dict[str, Any]) -> None:
        rule = _find_rule(highest_source["rules"], _INSERTED_RULE_ID)
        assert rule["stage"] == "HARD_FILTER"
        assert rule["effect"]["type"] == "EXCLUDE"
        assert rule["effect"]["reason_code"] == "REQ_PARENTS_MARRIAGE_REGISTERED"
        assert rule["safety_critical"] is True
        assert rule["on_unknown"] == "NEEDS_INPUT"

    def test_not_contaminating_conjuncts_present(self, highest_source: dict[str, Any]) -> None:
        """Codex refuter finding 1 (2026-08-19): dropping either the
        purposes-intersects-FAMILY or the relation-eq-PARENT conjunct
        turns this HARD_FILTER into a single-leaf ``marriage==false``
        gate that fires for every non-FAMILY, non-PARENT applicant too —
        explicit call-out per the mandate, on top of the full-set
        equality above."""
        rule = _find_rule(highest_source["rules"], _INSERTED_RULE_ID)
        conjuncts = _conjuncts(rule["when"])
        assert ("intent.purposes", "intersects", ("FAMILY",)) in conjuncts
        assert ("family.relation_to_sponsor", "eq", "PARENT") in conjuncts


# =============================================================================
# CURED (was: KNOWN-OPEN GAP) — E31C's nationality leg. Closed by PR #4660
# (seq-13 rules-only fold, merged 2026-08-23): `el.e31c-child-mixed-
# marriage-support` gained a `family.sponsor_nationalities intersects
# [ID]` conjunct, and a paired `hf.e31c-sponsor-not-indonesian` HARD_FILTER
# was inserted. Confirmed deliberate against PR #4660's own body (FIX 1)
# before this section was rewritten — this is the exact migration the
# banner that used to live here scripted in advance (see git history on
# this file, or `test_cure_forward_guard.py` in PR #4667, for the four-step
# instructions this rewrite followed). What used to be a KNOWN-OPEN pin is
# now `TestNationalityGapCuredShape` (structural, grouped with the other
# structural classes above) and `TestNationalityGapCuredWitnesses`
# (behavioural, grouped with `TestE31CForwardWitnesses` below).
# =============================================================================

_NATIONALITY_GAP_RULE_ID = "el.e31c-child-mixed-marriage-support"
_NATIONALITY_GAP_CURED_CONJUNCTS = frozenset(
    {
        ("intent.purposes", "intersects", ("FAMILY",)),
        ("family.relation_to_sponsor", "eq", "PARENT"),
        ("family.sponsor_nationalities", "intersects", ("ID",)),
    }
)


class TestNationalityGapCuredShape:
    """Structural half of the cure (mirrors `TestE31CSupportRuleShape` /
    `TestHardFilterShape` above) — pins `el.e31c-child-mixed-marriage-
    support`'s new 3-conjunct shape now that PR #4660 closed the
    nationality leg. If this goes red, the rule's conjuncts drifted from
    the shape the cure shipped; re-derive from the real pack, do not
    just widen the assertion."""

    def test_present_with_exact_three_conjuncts(self, highest_source: dict[str, Any]) -> None:
        rule = _find_rule(highest_source["rules"], _NATIONALITY_GAP_RULE_ID)
        assert _conjuncts(rule["when"]) == _NATIONALITY_GAP_CURED_CONJUNCTS

    def test_stage_and_effect(self, highest_source: dict[str, Any]) -> None:
        rule = _find_rule(highest_source["rules"], _NATIONALITY_GAP_RULE_ID)
        assert rule["stage"] == "ELIGIBILITY"
        assert rule["effect"]["type"] == "SUPPORT"


# ---------------------------------------------------------------------------
# positive control — prove the semantic checker is not vacuous
# ---------------------------------------------------------------------------


class TestConjunctCheckerIsNotVacuous:
    """Mutates COPIES of the real rule dicts (never a file on disk) to
    reintroduce each historical defect shape, and shows ``_conjuncts``
    stops matching the cured expectation — the RED case — right next to
    the unmutated GREEN case, so this test module cannot pass by having a
    checker that always returns True."""

    def test_dropping_a_conjunct_from_e31c_breaks_the_match(
        self, highest_source: dict[str, Any]
    ) -> None:
        rule = _find_rule(highest_source["rules"], _EDITED_RULE_ID)
        mutated_when = copy.deepcopy(rule["when"])
        mutated_when["args"].pop()  # historical seq-9 shape: fewer conjuncts
        assert _conjuncts(mutated_when) != _E31C_SUPPORT_CONJUNCTS  # RED
        assert _conjuncts(rule["when"]) == _E31C_SUPPORT_CONJUNCTS  # GREEN, unmutated

    def test_flipping_marriage_registered_value_breaks_the_match(
        self, highest_source: dict[str, Any]
    ) -> None:
        rule = _find_rule(highest_source["rules"], _EDITED_RULE_ID)
        mutated_when = copy.deepcopy(rule["when"])
        for arg in mutated_when["args"]:
            if arg["fact"] == "family.marriage_registered":
                arg["value"] = False
        assert _conjuncts(mutated_when) != _E31C_SUPPORT_CONJUNCTS  # RED
        assert _conjuncts(rule["when"]) == _E31C_SUPPORT_CONJUNCTS  # GREEN

    def test_dropping_the_relation_conjunct_from_hf_reproduces_the_contamination_bug(
        self, highest_source: dict[str, Any]
    ) -> None:
        rule = _find_rule(highest_source["rules"], _INSERTED_RULE_ID)
        mutated_when = copy.deepcopy(rule["when"])
        mutated_when["args"] = [
            a for a in mutated_when["args"] if a["fact"] != "family.relation_to_sponsor"
        ]
        assert _conjuncts(mutated_when) != _HF_EXCLUDE_CONJUNCTS  # RED
        assert _conjuncts(rule["when"]) == _HF_EXCLUDE_CONJUNCTS  # GREEN

    def test_reinserting_the_retired_c2_id_is_detected(
        self, highest_source: dict[str, Any]
    ) -> None:
        ids = {r["rule_id"] for r in highest_source["rules"]}
        mutated_ids = ids | {_RETIRED_RULE_ID}
        assert _RETIRED_RULE_ID in mutated_ids  # RED shape
        assert _RETIRED_RULE_ID not in ids  # GREEN, real pack

    def test_widening_the_nationality_intersects_values_breaks_the_match(
        self, highest_source: dict[str, Any]
    ) -> None:
        """Positive control for the ``values`` LIST specifically (Kimi K3
        refuter finding, 2026-08-23) — none of the four controls above
        mutate it; they mutate cardinality, an ``eq`` value, a conjunct's
        presence, and rule-ID membership. ``_conjunct`` normalizes
        ``values`` via ``tuple(sorted(...))``, so a checker regression that
        compared only (fact, op) and ignored ``values`` would pass every
        existing control AND every real test in this module, even if the
        pack's ``family.sponsor_nationalities`` values drifted from
        ``["ID"]`` to ``["ID", "US"]`` — the exact nationality dimension
        this file exists to guard."""
        rule = _find_rule(highest_source["rules"], _EDITED_RULE_ID)
        mutated_when = copy.deepcopy(rule["when"])
        for arg in mutated_when["args"]:
            if arg["fact"] == "family.sponsor_nationalities":
                arg["values"] = list(arg["values"]) + ["US"]
        assert _conjuncts(mutated_when) != _E31C_SUPPORT_CONJUNCTS  # RED
        assert _conjuncts(rule["when"]) == _E31C_SUPPORT_CONJUNCTS  # GREEN, unmutated


# ---------------------------------------------------------------------------
# (b) evaluator witnesses on the highest pack (behavioural half)
# ---------------------------------------------------------------------------

_E31C_BASE = {
    "intent.purposes": _known(["FAMILY"]),
    "family.relation_to_sponsor": _known("PARENT"),
    "family.sponsor_nationalities": _known(["ID"]),
}


class TestE31CForwardWitnesses:
    def test_guilt_unregistered_marriage_is_excluded(
        self, highest_compiled: compiler.CompiledRulePack
    ) -> None:
        proof = _proof(
            highest_compiled,
            "E31C",
            {**_E31C_BASE, "family.marriage_registered": _known(False)},
        )
        assert proof.status is ProductProofStatus.EXCLUDED
        assert "REQ_PARENTS_MARRIAGE_REGISTERED" in _reason_codes(proof)

    def test_innocence_registered_marriage_wni_parent_is_supported(
        self, highest_compiled: compiler.CompiledRulePack
    ) -> None:
        proof = _proof(
            highest_compiled,
            "E31C",
            {**_E31C_BASE, "family.marriage_registered": _known(True)},
        )
        assert proof.status is ProductProofStatus.SUPPORTED
        # SUPPORT reasons live in support_rules, not reasons (ProductProof
        # populates `reasons` only for EXCLUDED/REVIEW).
        assert _EDITED_RULE_ID in {r.rule_id for r in proof.support_rules}

    def test_tristate_unknown_marriage_blocks_never_excludes(
        self, highest_compiled: compiler.CompiledRulePack
    ) -> None:
        proof = _proof(
            highest_compiled,
            "E31C",
            {**_E31C_BASE, "family.marriage_registered": gf.unknown("NOT_ASKED")},
        )
        assert proof.status is ProductProofStatus.BLOCKED_UNKNOWN
        assert proof.status is not ProductProofStatus.EXCLUDED

    def test_non_family_applicant_is_not_contaminated(
        self, highest_compiled: compiler.CompiledRulePack
    ) -> None:
        """Codex refuter finding 1 (2026-08-19), regression-pinned forward:
        a STUDY applicant, relation OTHER, with
        ``family.marriage_registered`` UNKNOWN must resolve UNSUPPORTED
        (silent — the scoped HARD_FILTER never fires outside FAMILY+
        PARENT) and must NOT demand ``family.marriage_registered`` as a
        missing fact. Regressing the scoping conjuncts would turn this
        into BLOCKED_UNKNOWN, interviewing a student about their parents'
        marriage."""
        overrides = {
            "intent.purposes": _known(["STUDY"]),
            "family.relation_to_sponsor": _known("OTHER"),
            "family.marriage_registered": gf.unknown("NOT_ASKED"),
        }
        proof = _proof(highest_compiled, "E31C", overrides)
        assert proof.status is ProductProofStatus.UNSUPPORTED
        assert FactPath.FAMILY_MARRIAGE_REGISTERED not in proof.missing_facts


class TestNationalityGapCuredWitnesses:
    """Behavioural half of the cure (mirrors `TestE31CForwardWitnesses`
    above), driven against the real evaluator on the highest pack. Sponsor
    nationality is the discriminator: US (no Indonesian nationality
    anywhere) must no longer reach SUPPORTED via
    `el.e31c-child-mixed-marriage-support`; ID must still reach it, and
    must ALSO still fire the properly-scoped sibling
    `el.e31c-mixed-marriage-parents` (the discrimination control that used
    to live in the deleted `TestE31CNationalityGapKnownOpen` class — kept
    here because it still proves the fix targets nationality specifically,
    not "E31C always excluded now")."""

    def test_us_nationality_no_longer_reaches_supported_via_this_rule(
        self, highest_compiled: compiler.CompiledRulePack
    ) -> None:
        """Cured direction. Marriage IS registered — the registration
        leg's cure (hf.e31c-marriage-not-registered) does not fire here,
        because that HARD_FILTER only excludes on
        `marriage_registered eq False`. This is the nationality leg
        specifically, not a retest of the registration cure above."""
        overrides = {
            "intent.purposes": _known(["FAMILY"]),
            "family.relation_to_sponsor": _known("PARENT"),
            "family.sponsor_nationalities": _known(["US"]),
            "family.marriage_registered": _known(True),
        }
        proof = _proof(highest_compiled, "E31C", overrides)
        assert _NATIONALITY_GAP_RULE_ID not in {r.rule_id for r in proof.support_rules}
        assert proof.status is not ProductProofStatus.SUPPORTED

    def test_indonesian_nationality_control_fires_both_sibling_rules(
        self, highest_compiled: compiler.CompiledRulePack
    ) -> None:
        """Discrimination control: the SAME fact pattern but with an
        Indonesian sponsor nationality reaches SUPPORTED via BOTH sibling
        rules — the properly-scoped `el.e31c-mixed-marriage-parents` fires
        too. Proves the fix above is not simply "E31C never SUPPORTED
        regardless of facts": it specifically requires ID nationality on
        both the previously nationality-blind sibling and the always-
        scoped one."""
        overrides = {
            "intent.purposes": _known(["FAMILY"]),
            "family.relation_to_sponsor": _known("PARENT"),
            "family.sponsor_nationalities": _known(["ID"]),
            "family.marriage_registered": _known(True),
        }
        proof = _proof(highest_compiled, "E31C", overrides)
        assert proof.status is ProductProofStatus.SUPPORTED
        support_rule_ids = {r.rule_id for r in proof.support_rules}
        assert _NATIONALITY_GAP_RULE_ID in support_rule_ids
        assert _EDITED_RULE_ID in support_rule_ids


def _write_temp_pack(source: dict[str, Any]) -> Path:
    """Writes ``source`` to a fresh temp file and returns its path — the
    ONLY way ``load_rule_pack_payload``/``_compiled_from_path`` can build a
    ``CompiledRulePack`` from a MUTATED payload, since that loader takes a
    ``Path``, never an in-memory dict. Never touches a real pack file on
    disk. Caller owns cleanup (``path.unlink()``)."""
    fd, name = tempfile.mkstemp(suffix=".source.json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(source, f)
    return Path(name)


class TestNationalityGapPinIsNotVacuous:
    """Positive control (same discipline as `TestConjunctCheckerIsNotVacuous`
    above): proves `el.e31c-child-mixed-marriage-support`'s presence is
    what makes a mismatched-nationality applicant fail to reach SUPPORTED
    via this rule — not asserting something that would be true of E31C
    regardless. Operates on a TEMP COPY of the highest pack
    (`_write_temp_pack`) — never a file on disk. Answers "what would make
    this rule's contribution to E31C fail?": removing it does, and this
    test proves it does, right now, against the real evaluator."""

    def test_removing_the_gap_rule_flips_the_us_case_to_unsupported(
        self, highest_source: dict[str, Any]
    ) -> None:
        mutated = copy.deepcopy(highest_source)
        mutated["rules"] = [r for r in mutated["rules"] if r["rule_id"] != _NATIONALITY_GAP_RULE_ID]
        temp_path = _write_temp_pack(mutated)
        try:
            compiled_mutated = _compiled_from_path(temp_path)
            overrides_us = {
                "intent.purposes": _known(["FAMILY"]),
                "family.relation_to_sponsor": _known("PARENT"),
                "family.sponsor_nationalities": _known(["US"]),
                "family.marriage_registered": _known(True),
            }
            proof_us = _proof(compiled_mutated, "E31C", overrides_us)
            assert proof_us.status is ProductProofStatus.UNSUPPORTED  # RED case, cured

            # Control: the Indonesian-nationality case is UNAFFECTED by
            # removing the gap rule — it still reaches SUPPORTED via the
            # properly-scoped el.e31c-mixed-marriage-parents alone. Proves
            # the mutation targets the gap rule specifically, not E31C
            # eligibility wholesale.
            overrides_id = dict(overrides_us)
            overrides_id["family.sponsor_nationalities"] = _known(["ID"])
            proof_id = _proof(compiled_mutated, "E31C", overrides_id)
            assert proof_id.status is ProductProofStatus.SUPPORTED  # GREEN, unaffected
            assert {r.rule_id for r in proof_id.support_rules} == {_EDITED_RULE_ID}
        finally:
            temp_path.unlink()
