"""Gates for seq-14 (``rulepack-prod-014.source.json``, see
``backend.scripts.visa_engine.fold_pack_seq14``).

The blocked5 lane (2026-08-24): seq-13 reaches 29/38 products. Five of the
nine still-blocked products (E23U, E23V, E33A, E33B, E33C) have their
doctrine CLOSED (``research/visa/doctrine-factory/claims/
e2c-blocked5-claim-ledger.md``, E2c mini-batch) but carried no
ELIGIBILITY/SUPPORT rule at all.

**This fold is REMOVAL-ONLY — it inserts nothing.** An earlier revision
inserted two SUPPORT rules for E23U/E23V; adversarial review found both
WRONG (see the fold's own module docstring for the full writeup): they
constrained the sponsor CATEGORY, never the attribute that DEFINES the
product — E23U is the stay permit for the domestic staff of a
**diplomat**, but the dropped rule matched any INDIVIDUAL sponsor; E23V is
the permit for a foreign **Trade and Economic Office**, but the dropped
rule matched any GOVERNMENT sponsor. ``SponsorType`` has no member that
can express the defining attribute, and ``enums.py`` records that
E23U/E23V have no governing Permenkumham Pasal at all — there is no
statute to encode a narrower rule against. The two insertions were
dropped entirely; what this fold DOES do is remove the two pre-existing
``review.e23{u,v}.requested-product`` HUMAN_REVIEW rules, both keyed on
``intent.requested_product_code`` (hard-coded ``NOT_ASKED`` in production
at ``fact-mapper.ts:597``, hence permanently ``UNKNOWN``) — removing them
is a strict improvement (they were poisoning the whole per-product proof
to BLOCKED_UNKNOWN) and is behaviour-preserving, since a product with no
SUPPORT rule at all does not surface either way. E23U and E23V stay
unreachable by the engine and route to a human consultant; reachability
does NOT move (still 29/38). E33A/E33B/E33C get no changes at all — their
own SUPPORT-shape attempt was rejected in an earlier lane for unrelated
reasons (see the fold's module docstring) and this fold does not revisit
that.

This module SKIPS cleanly (not error, not red) while
``rulepack-prod-014.source.json`` does not exist on disk — run
``PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq14``
first. Once it exists, these checks run, each verified against the real
files on disk or the real evaluator:

(a) chain gate — seq-14's ``previous_payload_sha256`` equals the
    RECOMPUTED SHA256(JCS(...)) of seq-13's own signed payload
    declaration, cross-checked against a fresh re-hash of the seq-13
    SOURCE bytes.
(b) rule-set delta — mechanically diffed against seq-13: exactly the two
    ``review.e23{u,v}.requested-product`` rule_ids removed, ZERO added,
    zero changed, products/source_records byte-identical.
(c) zero lint findings — ``lint_duplicate_subtree`` /
    ``lint_unsatisfiable_condition`` run over every seq-14 rule.
(d) ``compile_pack`` compiles seq-14 with zero errors.
(e) idempotence — calling ``assemble_payload()`` twice yields
    canonical-JSON-identical output.
(f) evaluator witnesses (real evaluator, not the JSON): both products stay
    genuinely unreachable (the over-broad shape the dropped rule would
    have matched reaches NO support), the removed rule_ids are gone from
    the pack, and the plain E23 product's support-rule outcome is
    unchanged between seq-13 and seq-14 — the removal has no spillover.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine.compile_claims import (
    lint_duplicate_subtree,
    lint_unsatisfiable_condition,
)
from backend.scripts.visa_engine.compile_pack import (
    compile_rule_pack,
    load_rule_pack_payload,
    wrap_as_unsigned_pack,
)
from backend.scripts.visa_engine.fold_pack_seq14 import FoldPackError, assemble_payload
from backend.services.visa_engine import compiler, evaluator
from backend.services.visa_engine.bundle import canonicalize_json
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
_SEQ13_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-013.source.json"
_SEQ13_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-013.signed.json"
_SEQ14_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-014.source.json"

_REMOVED_RULE_IDS = frozenset({"review.e23u.requested-product", "review.e23v.requested-product"})

# Any instant inside every inherited rule's valid_period window.
AT = datetime(2026, 8, 24, 12, 0, 0, tzinfo=timezone.utc)

pytestmark = pytest.mark.skipif(
    not _SEQ14_SOURCE_PATH.exists(),
    reason=(
        "rulepack-prod-014.source.json does not exist yet — run "
        "`PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq14` "
        "first. This module SKIPS, not reds, until then."
    ),
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


@pytest.fixture(scope="module")
def seq13_source() -> dict[str, Any]:
    return _read_json(_SEQ13_SOURCE_PATH)


@pytest.fixture(scope="module")
def seq14_source() -> dict[str, Any]:
    return _read_json(_SEQ14_SOURCE_PATH)


def _compiled(name: str) -> compiler.CompiledRulePack:
    payload = load_rule_pack_payload(_PACKS_DIR / name)
    return compiler.build_compiled_pack(
        wrap_as_unsigned_pack(payload), fact_registry=DEFAULT_FACT_REGISTRY
    )


@pytest.fixture(scope="module")
def seq14(seq14_source: dict[str, Any]) -> compiler.CompiledRulePack:
    del seq14_source  # ensures the skip guard has already run
    return _compiled("rulepack-prod-014.source.json")


@pytest.fixture(scope="module")
def seq13() -> compiler.CompiledRulePack:
    return _compiled("rulepack-prod-013.source.json")


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
# (a) chain gate
# ---------------------------------------------------------------------------


class TestChainGate:
    def test_previous_payload_sha256_chains_to_recomputed_seq13(
        self, seq13_source: dict[str, Any], seq14_source: dict[str, Any]
    ) -> None:
        recomputed = hashlib.sha256(canonicalize_json(seq13_source)).hexdigest()
        seq13_signed = _read_json(_SEQ13_SIGNED_PATH)
        assert seq13_signed["payload_sha256"] == recomputed
        assert seq14_source["previous_payload_sha256"] == recomputed

    def test_sequence_advanced_and_rule_pack_id_changed(
        self, seq13_source: dict[str, Any], seq14_source: dict[str, Any]
    ) -> None:
        assert seq13_source["sequence"] == 13
        assert seq14_source["sequence"] == 14
        assert seq14_source["rule_pack_id"] != seq13_source["rule_pack_id"]


# ---------------------------------------------------------------------------
# (b) rule-set delta — mechanical, never eyeballed
# ---------------------------------------------------------------------------


class TestRuleSetDelta:
    def test_delta_is_exactly_two_removed_and_zero_inserted(
        self, seq13_source: dict[str, Any], seq14_source: dict[str, Any]
    ) -> None:
        """This is a REMOVAL-ONLY fold (see module docstring for why no
        SUPPORT rule replaces the two removed HUMAN_REVIEW rules): the two
        ``review.e23{u,v}.requested-product`` rules are gone, nothing new
        is added, and every rule that survives is byte-identical to its
        seq-13 self."""
        r13 = {r["rule_id"]: r for r in seq13_source["rules"]}
        r14 = {r["rule_id"]: r for r in seq14_source["rules"]}

        added = set(r14) - set(r13)
        removed = set(r13) - set(r14)
        changed = {rid for rid in (set(r13) & set(r14)) if _canon(r13[rid]) != _canon(r14[rid])}

        assert added == set()
        assert removed == _REMOVED_RULE_IDS
        assert changed == set()
        assert len(r14) == len(r13) - len(_REMOVED_RULE_IDS)

    def test_e33abc_rules_are_completely_untouched(
        self, seq13_source: dict[str, Any], seq14_source: dict[str, Any]
    ) -> None:
        """Explicit pin of the design decision: this fold makes ZERO
        changes to E33A/E33B/E33C — neither their HARD_FILTER nor their
        (still-inert) HUMAN_REVIEW rule. See the fold's module docstring
        for why."""
        e33abc_rule_ids = {
            "review.e33a.central-government-invitation",
            "hf.e33a.sponsor-not-government",
            "review.e33b.expertise-qualification",
            "hf.e33b.sponsor-not-government-or-none",
            "review.e33c.central-government-invitation",
            "hf.e33c.sponsor-not-government-or-none",
        }
        r13 = {r["rule_id"]: r for r in seq13_source["rules"]}
        r14 = {r["rule_id"]: r for r in seq14_source["rules"]}
        for rid in e33abc_rule_ids:
            assert rid in r13 and rid in r14, rid
            assert _canon(r13[rid]) == _canon(r14[rid]), rid

    def test_products_and_source_records_are_byte_identical(
        self, seq13_source: dict[str, Any], seq14_source: dict[str, Any]
    ) -> None:
        assert _canon(seq14_source["products"]) == _canon(seq13_source["products"])
        assert _canon(seq14_source["source_records"]) == _canon(seq13_source["source_records"])

    def test_no_other_top_level_key_drifted(
        self, seq13_source: dict[str, Any], seq14_source: dict[str, Any]
    ) -> None:
        identity_keys = {
            "sequence",
            "version",
            "rule_pack_id",
            "previous_payload_sha256",
            "created_at",
            "created_by",
        }
        for key in set(seq13_source) | set(seq14_source):
            if key in identity_keys or key == "rules":
                continue
            assert _canon(seq14_source.get(key)) == _canon(seq13_source.get(key)), key


# ---------------------------------------------------------------------------
# (c) zero lint findings over every seq-14 rule
# ---------------------------------------------------------------------------


class TestZeroLintFindings:
    def test_duplicate_subtree_and_unsatisfiable_condition_are_clean(
        self, seq14_source: dict[str, Any]
    ) -> None:
        findings = []
        for rule in seq14_source["rules"]:
            when = rule["when"]
            findings.extend(lint_duplicate_subtree(rule_id=rule["rule_id"], when=when))
            unsat_findings, _skip_note = lint_unsatisfiable_condition(
                rule_id=rule["rule_id"], when=when
            )
            findings.extend(unsat_findings)
        assert findings == []


# ---------------------------------------------------------------------------
# (d) compile_pack RC 0
# ---------------------------------------------------------------------------


class TestCompilePackCompilesClean:
    def test_compile_rule_pack_reports_zero_errors(self) -> None:
        payload = load_rule_pack_payload(_SEQ14_SOURCE_PATH)
        report = compile_rule_pack(wrap_as_unsigned_pack(payload))
        assert report.ok, "; ".join(f"{e.code}: {e.message}" for e in report.errors)


# ---------------------------------------------------------------------------
# (e) idempotence
# ---------------------------------------------------------------------------


class TestFoldIsIdempotent:
    def test_assemble_payload_twice_is_byte_identical(self) -> None:
        first = assemble_payload()
        second = assemble_payload()
        assert _canon(first) == _canon(second)


# ---------------------------------------------------------------------------
# (f) evaluator witnesses — E23U/E23V stay unreachable, real evaluator
# ---------------------------------------------------------------------------

#: The exact fact shape the DROPPED ``el.e23u.diplomatic-household-support``
#: rule would have matched. Kept here (not resurrected as a rule) purely to
#: witness that the shape now reaches no support at all.
_E23U_OVER_BROAD_SHAPE = {
    "intent.purposes": _known(["EMPLOYMENT"]),
    "sponsor.type": _known("INDIVIDUAL"),
    "work.employer_is_indonesian_entity": _known(False),
}

#: Same for the dropped ``el.e23v.trade-office-support`` shape.
_E23V_OVER_BROAD_SHAPE = {
    "intent.purposes": _known(["EMPLOYMENT"]),
    "sponsor.type": _known("GOVERNMENT"),
    "work.employer_is_indonesian_entity": _known(False),
}

#: A fact shape that DOES satisfy plain E23's own SUPPORT rule
#: (``el.e23-employment-support``) — used to prove the removal has no
#: spillover onto the neighbouring, unrelated product.
_E23_SUPPORT_SHAPE = {
    "intent.purposes": _known(["EMPLOYMENT"]),
    "work.employer_is_indonesian_entity": _known(True),
    "work.indonesian_work_sponsor_confirmed": _known(True),
}


class TestE23UE23VStayUnreachable:
    def test_no_seq14_rule_mentions_e23u_or_e23v(self, seq14_source: dict[str, Any]) -> None:
        """No rule in the seq-14 pack references either product — not the
        removed HUMAN_REVIEW rule (gone), and no SUPPORT rule was ever
        inserted for them (the design decision this rewrite documents)."""
        offending = [
            r["rule_id"]
            for r in seq14_source["rules"]
            if "e23u" in r["rule_id"].lower() or "e23v" in r["rule_id"].lower()
        ]
        assert offending == []

    def test_e23u_over_broad_shape_reaches_no_support(
        self, seq14: compiler.CompiledRulePack
    ) -> None:
        """The exact fact shape the dropped rule would have matched
        (EMPLOYMENT purpose, INDIVIDUAL sponsor, non-Indonesian employer)
        must reach NO support for E23U. This is the desired outcome: an
        INDIVIDUAL sponsor is not evidence of a diplomatic mission — the
        dropped rule would have declared a nanny hired by any
        non-diplomatic expat family eligible for the diplomatic-household
        stay permit, a false positive on a client-facing surface. With no
        rule authored at all, E23U stays unreachable and routes to a human
        consultant, which is the honest outcome until the fact vocabulary
        can express "sponsor is a diplomatic mission"."""
        proof = _proof(seq14, "E23U", dict(_E23U_OVER_BROAD_SHAPE))
        assert proof.status is not ProductProofStatus.SUPPORTED
        assert proof.support_rules == ()

    def test_e23v_over_broad_shape_reaches_no_support(
        self, seq14: compiler.CompiledRulePack
    ) -> None:
        """Same reasoning as E23U's over-broad witness, for E23V: a
        GOVERNMENT sponsor covers any government body, an Indonesian
        agency's own domestic hire included — it is not evidence of a
        foreign Trade and Economic Office. A SUPPORT verdict on this shape
        would be a false positive on a client-facing surface, so E23V
        reaches no support at all rather than an over-broad one."""
        proof = _proof(seq14, "E23V", dict(_E23V_OVER_BROAD_SHAPE))
        assert proof.status is not ProductProofStatus.SUPPORTED
        assert proof.support_rules == ()

    def test_removed_review_rules_are_absent_and_were_present_in_seq13(
        self, seq13_source: dict[str, Any], seq14_source: dict[str, Any]
    ) -> None:
        r13_ids = {r["rule_id"] for r in seq13_source["rules"]}
        r14_ids = {r["rule_id"] for r in seq14_source["rules"]}
        for rule_id in _REMOVED_RULE_IDS:
            assert rule_id in r13_ids, rule_id
            assert rule_id not in r14_ids, rule_id

    def test_plain_e23_support_outcome_is_unchanged_between_seq13_and_seq14(
        self, seq13: compiler.CompiledRulePack, seq14: compiler.CompiledRulePack
    ) -> None:
        """Regression guard proving the removal has no spillover onto the
        neighbouring, unrelated E23 product: the same facts that satisfy
        plain E23's own SUPPORT rule must reach the identical SUPPORTED
        outcome, with the identical set of support-rule ids, in both
        packs."""
        proof13 = _proof(seq13, "E23", dict(_E23_SUPPORT_SHAPE))
        proof14 = _proof(seq14, "E23", dict(_E23_SUPPORT_SHAPE))
        assert proof13.status is ProductProofStatus.SUPPORTED
        assert proof14.status is ProductProofStatus.SUPPORTED
        ids13 = {r.rule_id for r in proof13.support_rules}
        ids14 = {r.rule_id for r in proof14.support_rules}
        assert ids13 == ids14


# ---------------------------------------------------------------------------
# Fold-level fail-loud checks (chain mismatch)
# ---------------------------------------------------------------------------


class TestFoldFailsLoudOnDrift:
    def test_wrong_expected_seq13_hash_aborts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import backend.scripts.visa_engine.fold_pack_seq14 as mod

        monkeypatch.setattr(mod, "_EXPECTED_SEQ13_PAYLOAD_SHA256", "0" * 64)
        with pytest.raises(FoldPackError, match="not the one this fold was authored against"):
            mod.assemble_payload()
