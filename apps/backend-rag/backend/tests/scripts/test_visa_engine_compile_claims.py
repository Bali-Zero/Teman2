"""Tests for ``backend.scripts.visa_engine.compile_claims`` (E5 increment 1).

Guilt+innocence pairs for both hard lints (VERIFIED-only, R-OVERSTAY-
PLANNING), plus a golden compile of the real E5 vertical-slice manifest
against the real committed claim ledgers — the same invocation
``compile_claims.main`` documents in its module docstring, run for real
here rather than only described.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.scripts.visa_engine.compile_claims import (
    compile_manifest,
    lint_duplicate_subtree,
    lint_must_reference_facts,
    lint_overstay_planning,
    lint_unsatisfiable_condition,
    lint_verified_only,
    load_claim_ledgers,
    load_manifest,
    main,
)
from backend.services.visa_engine.claim_ledger import ClaimRecord, parse_claim_ledger_text

_PACK_PATH = (
    Path(__file__).resolve().parents[3]
    / "backend"
    / "services"
    / "visa_engine"
    / "contracts"
    / "packs"
    / "rulepack-prod-007.source.json"
)

_REPO_ROOT = Path(__file__).resolve().parents[5]
_CLAIMS_DIR = _REPO_ROOT / "research" / "visa" / "doctrine-factory" / "claims"
_SLICE_MANIFEST = (
    _REPO_ROOT / "research" / "visa" / "doctrine-factory" / "e5" / "slice-rule-manifest.json"
)
_LEDGER_FILES = [
    _CLAIMS_DIR / "e2a-claim-ledger.md",
    _CLAIMS_DIR / "e2b-batch1-claim-ledger.md",
    _CLAIMS_DIR / "e2b-batch2-claim-ledger.md",
    _CLAIMS_DIR / "e3a-cf1-resolution.md",
    # E5 increment 3, seq-9 fold (2026-08-19): wired in for the blocked7
    # manifest's E23U/E23V/E30E/E30F/E33A/E33B/E33C rules — see
    # TestLedgerHygiene below for the dual-header + product-state-clause
    # regressions these two files' fixes are pinned by.
    _CLAIMS_DIR / "e2b-batch3-claim-ledger.md",
    _CLAIMS_DIR / "e2c-blocked5-claim-ledger.md",
]


def _rec(claim_id: str, state: str) -> ClaimRecord:
    return ClaimRecord(
        claim_id=claim_id, state=state, header="test", backs=(), source_file="<test>"
    )


def _minimal_rule(rule_id: str = "el.test-rule", *, when: dict | None = None) -> dict:
    return {
        "rule_id": rule_id,
        "stage": "ELIGIBILITY",
        "scope": "PRODUCTS",
        "product_version_ids": ["5d5f9bd4-349b-54d7-841a-784c0afba068"],
        "priority": 100,
        "valid_period": {"from": "2026-07-24T00:00:00Z", "to": None},
        "when": when or {"fact": "intent.purposes", "op": "intersects", "values": ["FAMILY"]},
        "effect": {
            "type": "SUPPORT",
            "reason_code": "PURPOSE_PRODUCT_MATCH",
            "covered_purposes": ["FAMILY"],
        },
        "on_unknown": "NEEDS_INPUT",
        "source_refs": ["570f2bc4-5120-561f-90ba-58fcd9507514"],
        "explanation_key": f"explain.{rule_id}",
        "safety_critical": False,
    }


# ---------------------------------------------------------------------------
# Lint 1 — VERIFIED-only: guilt + innocence
# ---------------------------------------------------------------------------


class TestVerifiedOnlyLint:
    def test_guilt_conflicting_claim_is_rejected(self) -> None:
        ledger = {"CL-X-01": _rec("CL-X-01", "CONFLICTING")}
        findings = lint_verified_only(
            rule_id="el.x", claim_ids=["CL-X-01"], caveats=[], ledger=ledger
        )
        assert len(findings) == 1
        assert "CONFLICTING" in findings[0].message
        assert "el.x" == findings[0].rule_id

    def test_guilt_stale_claim_is_rejected(self) -> None:
        ledger = {"CL-X-01": _rec("CL-X-01", "STALE")}
        findings = lint_verified_only(
            rule_id="el.x", claim_ids=["CL-X-01"], caveats=[], ledger=ledger
        )
        assert findings and "STALE" in findings[0].message

    def test_guilt_unverified_claim_is_rejected(self) -> None:
        ledger = {"CL-X-01": _rec("CL-X-01", "UNVERIFIED")}
        findings = lint_verified_only(
            rule_id="el.x", claim_ids=["CL-X-01"], caveats=[], ledger=ledger
        )
        assert findings and "UNVERIFIED" in findings[0].message

    def test_guilt_unknown_claim_id_is_rejected(self) -> None:
        findings = lint_verified_only(
            rule_id="el.x", claim_ids=["CL-GHOST-01"], caveats=[], ledger={}
        )
        assert findings and "does not resolve" in findings[0].message

    def test_guilt_caveat_with_verified_with_caveat_but_no_note(self) -> None:
        ledger = {"CL-X-01": _rec("CL-X-01", "VERIFIED-WITH-CAVEAT")}
        findings = lint_verified_only(
            rule_id="el.x", claim_ids=["CL-X-01"], caveats=[], ledger=ledger
        )
        assert findings and "no matching caveat note" in findings[0].message

    def test_guilt_zero_claim_ids(self) -> None:
        findings = lint_verified_only(rule_id="el.x", claim_ids=[], caveats=[], ledger={})
        assert findings and "zero claim_ids" in findings[0].message

    def test_guilt_caveat_with_empty_note_does_not_satisfy_the_requirement(self) -> None:
        """kimi-k3 finding (2026-08-18): a caveat entry with the claim_id
        present but an empty/missing note satisfied the original lint —
        the brief requires the caveat actually be propagated, not a stub."""

        ledger = {"CL-X-01": _rec("CL-X-01", "VERIFIED-WITH-CAVEAT")}
        findings = lint_verified_only(
            rule_id="el.x",
            claim_ids=["CL-X-01"],
            caveats=[{"claim_id": "CL-X-01", "note": ""}],
            ledger=ledger,
        )
        assert findings and "empty note" in findings[0].message

    def test_guilt_malformed_caveat_entry_reports_finding_never_crashes(self) -> None:
        """kimi-k3 finding (2026-08-18): the original
        ``{c["claim_id"] for c in caveats}`` set-comprehension raised a bare
        ``KeyError``/``TypeError`` on a malformed caveats entry, contradicting
        this module's own "never a bare traceback for a data problem"
        contract. Must report a finding instead, for every malformed shape."""

        ledger = {"CL-X-01": _rec("CL-X-01", "VERIFIED")}
        for bad_caveats in (
            [{"note": "missing claim_id"}],
            [{"claim_id": "CL-X-01"}],  # missing note
            ["not-a-dict"],
            [{"claim_id": 123, "note": "wrong type"}],
        ):
            findings = lint_verified_only(
                rule_id="el.x", claim_ids=["CL-X-01"], caveats=bad_caveats, ledger=ledger
            )
            assert findings, f"expected a finding for {bad_caveats!r}"

    def test_innocence_verified_claim_passes(self) -> None:
        ledger = {"CL-X-01": _rec("CL-X-01", "VERIFIED")}
        findings = lint_verified_only(
            rule_id="el.x", claim_ids=["CL-X-01"], caveats=[], ledger=ledger
        )
        assert findings == []

    def test_innocence_verified_with_caveat_and_matching_note_passes(self) -> None:
        ledger = {"CL-X-01": _rec("CL-X-01", "VERIFIED-WITH-CAVEAT")}
        findings = lint_verified_only(
            rule_id="el.x",
            claim_ids=["CL-X-01"],
            caveats=[{"claim_id": "CL-X-01", "note": "explains the caveat"}],
            ledger=ledger,
        )
        assert findings == []

    def test_innocence_multiple_verified_claims_pass(self) -> None:
        ledger = {
            "CL-X-01": _rec("CL-X-01", "VERIFIED"),
            "CL-X-02": _rec("CL-X-02", "VERIFIED"),
        }
        findings = lint_verified_only(
            rule_id="el.x", claim_ids=["CL-X-01", "CL-X-02"], caveats=[], ledger=ledger
        )
        assert findings == []

    def test_guilt_product_conditional_claim_without_caveat_is_rejected_for_its_caveated_product(
        self,
    ) -> None:
        """kimi-k3 P0 finding (2026-08-18): CL-D-FUNDS is VERIFIED for
        D1/D12 but VERIFIED-WITH-CAVEAT for D2 on ONE state line —
        ``ClaimRecord.state`` alone (first token) would resolve to plain
        VERIFIED for every product, silently bypassing the caveat
        requirement for D2. A D2 rule citing it with no caveat must be
        REJECTED — proving the per-product lookup, not the claim-wide
        state, is what the lint actually consults."""

        ledger = {
            "CL-D-FUNDS": ClaimRecord(
                claim_id="CL-D-FUNDS",
                state="VERIFIED",
                header="Financial-proof minima.",
                backs=(),
                source_file="<test>",
                product_states={"D1": "VERIFIED", "D12": "VERIFIED", "D2": "VERIFIED-WITH-CAVEAT"},
            )
        }
        findings = lint_verified_only(
            rule_id="el.d2-funds",
            claim_ids=["CL-D-FUNDS"],
            caveats=[],
            ledger=ledger,
            product_code="D2",
        )
        assert findings and "no matching caveat note" in findings[0].message

    def test_innocence_product_conditional_claim_passes_for_its_verified_products(self) -> None:
        """Innocence twin: D1/D12 rules citing the SAME product-conditional
        claim must pass without needing a caveat — their per-product state
        is plain VERIFIED, not VERIFIED-WITH-CAVEAT."""

        ledger = {
            "CL-D-FUNDS": ClaimRecord(
                claim_id="CL-D-FUNDS",
                state="VERIFIED",
                header="Financial-proof minima.",
                backs=(),
                source_file="<test>",
                product_states={"D1": "VERIFIED", "D12": "VERIFIED", "D2": "VERIFIED-WITH-CAVEAT"},
            )
        }
        for product_code in ("D1", "D12"):
            findings = lint_verified_only(
                rule_id=f"el.{product_code.lower()}-funds",
                claim_ids=["CL-D-FUNDS"],
                caveats=[],
                ledger=ledger,
                product_code=product_code,
            )
            assert findings == [], f"{product_code} should not require a caveat"

    def test_innocence_product_conditional_claim_with_caveat_passes_for_d2(self) -> None:
        ledger = {
            "CL-D-FUNDS": ClaimRecord(
                claim_id="CL-D-FUNDS",
                state="VERIFIED",
                header="Financial-proof minima.",
                backs=(),
                source_file="<test>",
                product_states={"D1": "VERIFIED", "D12": "VERIFIED", "D2": "VERIFIED-WITH-CAVEAT"},
            )
        }
        findings = lint_verified_only(
            rule_id="el.d2-funds",
            claim_ids=["CL-D-FUNDS"],
            caveats=[
                {
                    "claim_id": "CL-D-FUNDS",
                    "note": "statute delegates the figure; portal hardcodes it",
                }
            ],
            ledger=ledger,
            product_code="D2",
        )
        assert findings == []


# ---------------------------------------------------------------------------
# Lint 2 — R-OVERSTAY-PLANNING: guilt + innocence
# ---------------------------------------------------------------------------


class TestOverstayPlanningLint:
    def test_guilt_bare_overstay_reference_is_rejected(self) -> None:
        """Reproduces the seq-6 smoke symptom the ruling names: a rule
        referencing overstay_days with no onshore guard at all."""

        when = {"fact": "immigration.overstay_days", "op": "eq", "value": 0}
        findings = lint_overstay_planning(rule_id="hf.test", when=when)
        assert len(findings) == 1
        assert "immigration.overstay_days" in findings[0].message
        assert "immigration.currently_in_indonesia" in findings[0].message

    def test_guilt_overstay_nested_in_all_without_onshore_sibling(self) -> None:
        when = {
            "op": "all",
            "args": [
                {"fact": "intent.purposes", "op": "intersects", "values": ["TOURISM"]},
                {"fact": "immigration.overstay_days", "op": "gt", "value": 0},
            ],
        }
        findings = lint_overstay_planning(rule_id="hf.test", when=when)
        assert findings

    def test_guilt_overstay_guarded_only_inside_sibling_any_branch(self) -> None:
        """An onshore guard that lives inside an `any` branch protects only
        that branch's own leaves, never a sibling branch's — an `any` is
        satisfied by EITHER branch, so a guard local to one branch gives no
        guarantee about facts collected via the other."""

        when = {
            "op": "any",
            "args": [
                {
                    "op": "all",
                    "args": [
                        {"fact": "immigration.currently_in_indonesia", "op": "eq", "value": True},
                        {"fact": "intent.purposes", "op": "intersects", "values": ["TOURISM"]},
                    ],
                },
                {"fact": "immigration.overstay_days", "op": "gt", "value": 0},
            ],
        }
        findings = lint_overstay_planning(rule_id="hf.test", when=when)
        assert findings

    def test_innocence_overstay_guarded_by_onshore_sibling_passes(self) -> None:
        """The onshore branch: currently_in_indonesia==true still asks
        about overstay — this must NEVER be blocked by the lint."""

        when = {
            "op": "all",
            "args": [
                {"fact": "immigration.currently_in_indonesia", "op": "eq", "value": True},
                {"fact": "immigration.overstay_days", "op": "gt", "value": 0},
            ],
        }
        findings = lint_overstay_planning(rule_id="hf.test", when=when)
        assert findings == []

    def test_innocence_overstay_guarded_by_ancestor_all_two_levels_up(self) -> None:
        when = {
            "op": "all",
            "args": [
                {"fact": "immigration.currently_in_indonesia", "op": "eq", "value": True},
                {
                    "op": "all",
                    "args": [
                        {"fact": "intent.purposes", "op": "intersects", "values": ["TOURISM"]},
                        {"fact": "immigration.overstay_days", "op": "gt", "value": 0},
                    ],
                },
            ],
        }
        findings = lint_overstay_planning(rule_id="hf.test", when=when)
        assert findings == []

    def test_innocence_no_overstay_reference_at_all_passes(self) -> None:
        when = {"fact": "intent.purposes", "op": "intersects", "values": ["TOURISM"]}
        findings = lint_overstay_planning(rule_id="hf.test", when=when)
        assert findings == []

    def test_guilt_not_wrapped_negative_onshore_check_does_not_count_as_a_guard(self) -> None:
        """kimi-k3 P1 finding to VERIFY (2026-08-18): does a guard-shaped
        leaf inside a ``not`` subtree wrongly get credited as protecting a
        SIBLING overstay reference? ``not(eq onshore false)`` is a
        de Morgan-equivalent of ``onshore==true`` in ordinary boolean
        logic, but this walker only ever collects a local_true_fact from a
        DIRECT ``{"op":"eq","value":True}`` child of an ``all`` node — a
        ``not`` node is never such a child (its own ``op`` is ``"not"``),
        so it must contribute NOTHING to ``all_ancestor_facts``. Confirmed
        by this test: the sibling overstay leaf is still flagged — the
        walker does not (incorrectly) treat the not-wrapped check as a
        guard. (This is also why the phrasing is rejected elsewhere as a
        declined P2 false-positive, not a bypass: it is REJECTED, i.e.
        safe, never silently accepted.)"""

        when = {
            "op": "all",
            "args": [
                {
                    "op": "not",
                    "arg": {
                        "fact": "immigration.currently_in_indonesia",
                        "op": "eq",
                        "value": False,
                    },
                },
                {"fact": "immigration.overstay_days", "op": "gt", "value": 0},
            ],
        }
        findings = lint_overstay_planning(rule_id="hf.test", when=when)
        assert findings, (
            "a not-wrapped negative-onshore-check must NOT protect a sibling overstay leaf"
        )

    def test_innocence_real_onshore_guard_still_protects_a_not_wrapped_overstay_leaf(self) -> None:
        """The mirror case: a REAL onshore guard (a direct true-eq sibling)
        must still protect an overstay reference even when that reference
        itself sits inside a ``not`` — the guard is an AND-sibling of the
        `not` node, so it holds regardless of what's inside the `not`."""

        when = {
            "op": "all",
            "args": [
                {"fact": "immigration.currently_in_indonesia", "op": "eq", "value": True},
                {"op": "not", "arg": {"fact": "immigration.overstay_days", "op": "eq", "value": 0}},
            ],
        }
        findings = lint_overstay_planning(rule_id="hf.test", when=when)
        assert findings == []


# ---------------------------------------------------------------------------
# Lint 3 — UNSATISFIABLE-CONDITION: guilt + innocence
# ---------------------------------------------------------------------------

#: Copied verbatim from ``el.e33e.deposit-income-basis`` in
#: ``backend/services/visa_engine/contracts/packs/rulepack-prod-007.source.json``
#: (2026-08-18) — the real E5-increment-2 defect this lint exists to catch.
#: The outer `all` re-asserts the same four deposit/state-bank/own-name/
#: passive-income leaves that the inner `any` demands an XOR of, so the
#: whole tree is unsatisfiable once identical leaves are treated as the
#: SAME boolean atom.
_E33E_DEPOSIT_INCOME_BASIS_WHEN: dict = {
    "op": "all",
    "args": [
        {
            "op": "all",
            "args": [
                {"op": "intersects", "fact": "intent.purposes", "values": ["RETIREMENT"]},
                {"op": "gte", "fact": "derived.age_years", "value": 55},
                {
                    "op": "any",
                    "args": [
                        {
                            "op": "all",
                            "args": [
                                {
                                    "op": "all",
                                    "args": [
                                        {
                                            "op": "gte",
                                            "fact": "secondhome.bank_deposit_usd",
                                            "value": 50000,
                                        },
                                        {
                                            "op": "eq",
                                            "fact": "secondhome.bank_deposit_at_state_bank",
                                            "value": True,
                                        },
                                        {
                                            "op": "eq",
                                            "fact": "secondhome.bank_deposit_in_own_name",
                                            "value": True,
                                        },
                                    ],
                                },
                                {
                                    "op": "not",
                                    "arg": {
                                        "op": "gte",
                                        "fact": "secondhome.passive_monthly_income_usd",
                                        "value": 3000,
                                    },
                                },
                            ],
                        },
                        {
                            "op": "all",
                            "args": [
                                {
                                    "op": "not",
                                    "arg": {
                                        "op": "all",
                                        "args": [
                                            {
                                                "op": "gte",
                                                "fact": "secondhome.bank_deposit_usd",
                                                "value": 50000,
                                            },
                                            {
                                                "op": "eq",
                                                "fact": "secondhome.bank_deposit_at_state_bank",
                                                "value": True,
                                            },
                                            {
                                                "op": "eq",
                                                "fact": "secondhome.bank_deposit_in_own_name",
                                                "value": True,
                                            },
                                        ],
                                    },
                                },
                                {
                                    "op": "gte",
                                    "fact": "secondhome.passive_monthly_income_usd",
                                    "value": 3000,
                                },
                            ],
                        },
                    ],
                },
            ],
        },
        {
            "op": "all",
            "args": [
                {"op": "intersects", "fact": "intent.purposes", "values": ["RETIREMENT"]},
                {"op": "gte", "fact": "derived.age_years", "value": 55},
                {
                    "op": "all",
                    "args": [
                        {"op": "gte", "fact": "secondhome.bank_deposit_usd", "value": 50000},
                        {
                            "op": "eq",
                            "fact": "secondhome.bank_deposit_at_state_bank",
                            "value": True,
                        },
                        {"op": "eq", "fact": "secondhome.bank_deposit_in_own_name", "value": True},
                    ],
                },
                {"op": "gte", "fact": "secondhome.passive_monthly_income_usd", "value": 3000},
            ],
        },
    ],
}


class TestUnsatisfiableConditionLint:
    def test_guilt_e33e_deposit_income_basis_is_unsatisfiable(self) -> None:
        """The real E33E defect: brute-force over 6 distinct leaves finds
        zero of 64 assignments that satisfy `when`."""

        findings, skip_note = lint_unsatisfiable_condition(
            rule_id="el.e33e.deposit-income-basis", when=_E33E_DEPOSIT_INCOME_BASIS_WHEN
        )
        assert skip_note is None
        assert len(findings) == 1
        assert "UNSATISFIABLE" in findings[0].message
        assert "6 distinct leaf" in findings[0].message
        assert "64 assignments" in findings[0].message

    def test_guilt_e33e_matches_pack_on_disk(self) -> None:
        """Anti-drift: the frozen fixture above must still equal the live
        pack's `when` — if the pack changes, this test forces the fixture
        (and the finding it proves) to be re-verified, not silently stale."""

        pack = json.loads(_PACK_PATH.read_text(encoding="utf-8"))
        rule = next(r for r in pack["rules"] if r["rule_id"] == "el.e33e.deposit-income-basis")
        assert rule["when"] == _E33E_DEPOSIT_INCOME_BASIS_WHEN

    def test_innocence_satisfiable_condition_passes(self) -> None:
        when = {
            "op": "all",
            "args": [
                {"op": "intersects", "fact": "intent.purposes", "values": ["RETIREMENT"]},
                {"op": "gte", "fact": "derived.age_years", "value": 55},
            ],
        }
        findings, skip_note = lint_unsatisfiable_condition(rule_id="hf.test", when=when)
        assert findings == []
        assert skip_note is None

    def test_guilt_simple_contradiction_by_shared_leaf_is_caught(self) -> None:
        """A minimal `A AND NOT A` (same leaf, negated) must be flagged —
        sanity check the shared-atom mechanism independent of E33E's size.

        (Renamed from a stray "innocence" prefix — kimi-k3 finding,
        2026-08-18: the assertion was always correct, the test's own
        guilt/innocence naming convention was violated by the name.)
        """

        leaf = {"op": "eq", "fact": "immigration.currently_in_indonesia", "value": True}
        when = {"op": "all", "args": [leaf, {"op": "not", "arg": leaf}]}
        findings, skip_note = lint_unsatisfiable_condition(rule_id="hf.test", when=when)
        assert skip_note is None
        assert findings and "UNSATISFIABLE" in findings[0].message

    def test_innocence_no_leaves_passes(self) -> None:
        findings, skip_note = lint_unsatisfiable_condition(
            rule_id="hf.test", when={"op": "all", "args": []}
        )
        assert findings == []
        assert skip_note is None

    def test_guilt_empty_any_is_unsatisfiable(self) -> None:
        """kimi-k3 finding (2026-08-18): `{"op": "any", "args": []}` is
        Kleene-FALSE (an `any` of nothing has nothing to make it true) —
        genuinely unsatisfiable, and has ZERO leaves. The original
        `if not leaves: return [], None` early-return would have missed
        this entirely; the fix removed that special case so the general
        brute-force (with `2**0 == 1` assignment) evaluates it for real."""

        findings, skip_note = lint_unsatisfiable_condition(
            rule_id="hf.empty-any", when={"op": "any", "args": []}
        )
        assert skip_note is None
        assert findings and "UNSATISFIABLE" in findings[0].message

    def test_guilt_empty_any_nested_under_all_with_other_leaves_is_unsatisfiable(self) -> None:
        """The same defect nested one level down, alongside a real leaf —
        confirms the fix isn't special-casing "when IS exactly empty-any"."""

        when = {
            "op": "all",
            "args": [
                {"fact": "intent.purposes", "op": "intersects", "values": ["TOURISM"]},
                {"op": "any", "args": []},
            ],
        }
        findings, skip_note = lint_unsatisfiable_condition(rule_id="hf.test", when=when)
        assert skip_note is None
        assert findings and "UNSATISFIABLE" in findings[0].message

    def test_innocence_malformed_null_args_does_not_crash(self) -> None:
        """kimi-k3 finding (2026-08-18): `condition.get("args", [])` only
        applies its default when the KEY is absent — a manifest with
        `"args": null` (or any non-list) previously crashed the compiler
        with an uncaught TypeError instead of degrading gracefully. Must
        never raise; malformed `args` is treated as "no children" here
        (schema validation elsewhere is what actually rejects the shape)."""

        for malformed in (None, "not-a-list", 5, {"not": "a-list-either"}):
            findings, skip_note = lint_unsatisfiable_condition(
                rule_id="hf.test", when={"op": "all", "args": malformed}
            )
            # Must not raise. `all` with (effectively) zero children is
            # vacuously satisfiable, never a finding.
            assert findings == []
            assert skip_note is None

    def test_guilt_more_than_twenty_leaves_is_skipped_with_declared_note(self) -> None:
        """21 distinct leaves must NOT be brute-forced (2**21 is too much
        per-rule compute) — the compiler must emit an explicit note, never
        silence. Silence is not success (task brief, verbatim)."""

        leaves = [{"op": "eq", "fact": f"synthetic.leaf_{i}", "value": True} for i in range(21)]
        when = {"op": "all", "args": leaves}
        findings, skip_note = lint_unsatisfiable_condition(rule_id="hf.synthetic-21", when=when)
        assert findings == []
        assert skip_note is not None
        assert "21 leaves > 20" in skip_note
        assert "hf.synthetic-21" in skip_note

    def test_innocence_exactly_twenty_leaves_is_checked_not_skipped(self) -> None:
        """The boundary: 20 leaves (all True, trivially satisfiable) must
        still be brute-forced, not skipped — the limit is `> 20`."""

        leaves = [{"op": "eq", "fact": f"synthetic.leaf_{i}", "value": True} for i in range(20)]
        when = {"op": "all", "args": leaves}
        findings, skip_note = lint_unsatisfiable_condition(rule_id="hf.synthetic-20", when=when)
        assert findings == []
        assert skip_note is None


# ---------------------------------------------------------------------------
# Lint 4 — VACUOUS-RULE: guilt + innocence
# ---------------------------------------------------------------------------

#: Copied verbatim from ``el.e33g.income-60k-manual`` in
#: ``backend/services/visa_engine/contracts/packs/rulepack-prod-007.source.json``
#: (2026-08-18) — the real E5-increment-2 defect: the rule's name promises
#: an income check, but its `when` is the same remote-work block literally
#: duplicated twice, and references zero income facts (the literal 60000
#: appears nowhere in the pack).
_E33G_INCOME_60K_MANUAL_WHEN: dict = {
    "op": "all",
    "args": [
        {
            "op": "all",
            "args": [
                {"op": "intersects", "fact": "intent.purposes", "values": ["REMOTE_WORK"]},
                {"op": "eq", "fact": "work.employer_is_indonesian_entity", "value": False},
                {"op": "eq", "fact": "work.serves_indonesian_clients", "value": False},
                {"op": "eq", "fact": "work.indonesia_source_compensation", "value": False},
            ],
        },
        {
            "op": "all",
            "args": [
                {"op": "intersects", "fact": "intent.purposes", "values": ["REMOTE_WORK"]},
                {"op": "eq", "fact": "work.employer_is_indonesian_entity", "value": False},
                {"op": "eq", "fact": "work.serves_indonesian_clients", "value": False},
                {"op": "eq", "fact": "work.indonesia_source_compensation", "value": False},
            ],
        },
    ],
}


class TestDuplicateSubtreeLint:
    def test_guilt_e33g_income_60k_manual_has_duplicate_subtree(self) -> None:
        findings = lint_duplicate_subtree(
            rule_id="el.e33g.income-60k-manual", when=_E33G_INCOME_60K_MANUAL_WHEN
        )
        assert len(findings) == 1
        assert "structurally identical children" in findings[0].message
        assert "args[0] == args[1]" in findings[0].message

    def test_guilt_e33g_matches_pack_on_disk(self) -> None:
        pack = json.loads(_PACK_PATH.read_text(encoding="utf-8"))
        rule = next(r for r in pack["rules"] if r["rule_id"] == "el.e33g.income-60k-manual")
        assert rule["when"] == _E33G_INCOME_60K_MANUAL_WHEN

    def test_guilt_duplicate_detected_nested_inside_any(self) -> None:
        leaf = {"op": "eq", "fact": "immigration.currently_in_indonesia", "value": True}
        when = {"op": "any", "args": [leaf, leaf]}
        findings = lint_duplicate_subtree(rule_id="hf.test", when=when)
        assert findings

    def test_guilt_duplicate_detected_deep_in_tree(self) -> None:
        leaf = {"op": "eq", "fact": "immigration.currently_in_indonesia", "value": True}
        when = {
            "op": "all",
            "args": [
                {"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
                {"op": "all", "args": [leaf, leaf]},
            ],
        }
        findings = lint_duplicate_subtree(rule_id="hf.test", when=when)
        assert findings

    def test_innocence_two_different_children_pass(self) -> None:
        when = {
            "op": "all",
            "args": [
                {"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
                {"op": "eq", "fact": "intent.entry_pattern", "value": "MULTIPLE"},
            ],
        }
        findings = lint_duplicate_subtree(rule_id="hf.test", when=when)
        assert findings == []

    def test_innocence_slightly_different_children_do_not_false_positive(self) -> None:
        """Two leaves that differ by a single value must NOT be flagged —
        this is a structural-equality check, not a fuzzy one."""

        when = {
            "op": "any",
            "args": [
                {"op": "eq", "fact": "intent.entry_pattern", "value": "MULTIPLE"},
                {"op": "eq", "fact": "intent.entry_pattern", "value": "SINGLE"},
            ],
        }
        findings = lint_duplicate_subtree(rule_id="hf.test", when=when)
        assert findings == []

    def test_innocence_malformed_null_args_does_not_crash(self) -> None:
        """kimi-k3 finding (2026-08-18), same class as the satisfiability
        lint's fix: `"args": null` (or any non-list) must never raise."""

        for malformed in (None, "not-a-list", 5, {"not": "a-list-either"}):
            findings = lint_duplicate_subtree(
                rule_id="hf.test", when={"op": "any", "args": malformed}
            )
            assert findings == []


class TestMustReferenceFactsLint:
    def test_guilt_declared_fact_never_derived_is_rejected(self) -> None:
        findings = lint_must_reference_facts(
            rule_id="el.e33g.income-60k-manual",
            must_reference_facts=["secondhome.passive_monthly_income_usd"],
            derived_facts=["intent.purposes", "work.employer_is_indonesian_entity"],
        )
        assert findings and "secondhome.passive_monthly_income_usd" in findings[0].message

    def test_innocence_absent_field_means_no_check(self) -> None:
        """The field is OPTIONAL — a manifest entry that doesn't declare it
        must never be flagged for anything (checked at the compile_manifest
        level via an empty list default, see TestCompileManifest)."""

        findings = lint_must_reference_facts(
            rule_id="el.x", must_reference_facts=[], derived_facts=["intent.purposes"]
        )
        assert findings == []

    def test_innocence_declared_fact_is_derived_passes(self) -> None:
        findings = lint_must_reference_facts(
            rule_id="el.x",
            must_reference_facts=["intent.purposes"],
            derived_facts=["intent.purposes", "work.employer_is_indonesian_entity"],
        )
        assert findings == []

    def test_guilt_unhashable_entry_reports_finding_never_crashes(self) -> None:
        """team-lead parallel-gate finding (2026-08-18): a non-string (and
        possibly unhashable, e.g. a dict) entry in must_reference_facts
        must never blow up `fact not in derived_set` with a bare TypeError
        — that is exactly the "never a bare traceback for a data problem"
        contract this module's own docstring commits to."""

        for bad_entry in ({"typo": 1}, ["nested", "list"], 123, None):
            findings = lint_must_reference_facts(
                rule_id="el.x",
                must_reference_facts=[bad_entry],
                derived_facts=["intent.purposes"],
            )
            assert findings, f"expected a finding for {bad_entry!r}"
            assert "is not a string" in findings[0].message

    def test_guilt_unhashable_entry_end_to_end_via_compile_manifest(self) -> None:
        """Same defect, exercised through the real entrypoint so a future
        refactor of compile_manifest's must_reference_facts wiring can't
        silently reopen the crash."""

        ledger = {"CL-X-01": _rec("CL-X-01", "VERIFIED")}
        manifest = {
            "rules": [
                {
                    "product_code": "X",
                    "claim_ids": ["CL-X-01"],
                    "caveats": [],
                    "must_reference_facts": [{"typo": 1}],
                    "rule": _minimal_rule(),
                }
            ]
        }
        report = compile_manifest(manifest, ledger)  # must not raise
        assert not report.ok
        assert "is not a string" in report.render()


# ---------------------------------------------------------------------------
# Full compiler: end-to-end guilt + innocence
# ---------------------------------------------------------------------------


class TestCompileManifest:
    def test_guilt_manifest_with_conflicting_claim_fails_whole_report(self) -> None:
        ledger = {"CL-X-01": _rec("CL-X-01", "CONFLICTING")}
        manifest = {
            "rules": [
                {
                    "product_code": "X",
                    "claim_ids": ["CL-X-01"],
                    "caveats": [],
                    "rule": _minimal_rule(),
                }
            ]
        }
        report = compile_manifest(manifest, ledger)
        assert not report.ok
        assert report.compiled == []
        assert "CONFLICTING" in report.render()

    def test_guilt_overstay_bare_reference_fails(self) -> None:
        ledger = {"CL-X-01": _rec("CL-X-01", "VERIFIED")}
        rule = _minimal_rule(when={"fact": "immigration.overstay_days", "op": "eq", "value": 0})
        manifest = {
            "rules": [{"product_code": "X", "claim_ids": ["CL-X-01"], "caveats": [], "rule": rule}]
        }
        report = compile_manifest(manifest, ledger)
        assert not report.ok

    def test_innocence_clean_manifest_compiles(self) -> None:
        ledger = {"CL-X-01": _rec("CL-X-01", "VERIFIED")}
        manifest = {
            "rules": [
                {
                    "product_code": "X",
                    "claim_ids": ["CL-X-01"],
                    "caveats": [],
                    "rule": _minimal_rule(),
                }
            ]
        }
        report = compile_manifest(manifest, ledger)
        assert report.ok
        assert len(report.compiled) == 1
        assert report.compiled[0].rule.rule_id == "el.test-rule"
        # required_facts must be derived, never trusted from the manifest —
        # the minimal rule's `when` references exactly one fact.
        assert list(report.compiled[0].rule.required_facts) == ["intent.purposes"]

    def test_innocence_required_facts_are_always_derived_not_trusted(self) -> None:
        """A manifest that lied about required_facts (stale/omitted) must
        not propagate the lie — the compiler recomputes it."""

        ledger = {"CL-X-01": _rec("CL-X-01", "VERIFIED")}
        rule = _minimal_rule()
        rule["required_facts"] = ["totally.wrong.path"]  # would fail FactPath validation if trusted
        manifest = {
            "rules": [{"product_code": "X", "claim_ids": ["CL-X-01"], "caveats": [], "rule": rule}]
        }
        report = compile_manifest(manifest, ledger)
        assert report.ok
        assert list(report.compiled[0].rule.required_facts) == ["intent.purposes"]

    def test_guilt_unsatisfiable_when_fails_whole_report(self) -> None:
        ledger = {"CL-X-01": _rec("CL-X-01", "VERIFIED")}
        rule = _minimal_rule(
            rule_id="el.e33e.deposit-income-basis", when=_E33E_DEPOSIT_INCOME_BASIS_WHEN
        )
        manifest = {
            "rules": [
                {"product_code": "E33E", "claim_ids": ["CL-X-01"], "caveats": [], "rule": rule}
            ]
        }
        report = compile_manifest(manifest, ledger)
        assert not report.ok
        assert report.compiled == []
        assert "UNSATISFIABLE" in report.render()

    def test_guilt_duplicate_subtree_when_fails_whole_report(self) -> None:
        ledger = {"CL-X-01": _rec("CL-X-01", "VERIFIED")}
        rule = _minimal_rule(rule_id="el.e33g.income-60k-manual", when=_E33G_INCOME_60K_MANUAL_WHEN)
        manifest = {
            "rules": [
                {"product_code": "E33G", "claim_ids": ["CL-X-01"], "caveats": [], "rule": rule}
            ]
        }
        report = compile_manifest(manifest, ledger)
        assert not report.ok
        assert report.compiled == []
        assert "structurally identical children" in report.render()

    def test_guilt_must_reference_facts_declared_but_absent_fails(self) -> None:
        ledger = {"CL-X-01": _rec("CL-X-01", "VERIFIED")}
        manifest = {
            "rules": [
                {
                    "product_code": "X",
                    "claim_ids": ["CL-X-01"],
                    "caveats": [],
                    "must_reference_facts": ["secondhome.passive_monthly_income_usd"],
                    "rule": _minimal_rule(),
                }
            ]
        }
        report = compile_manifest(manifest, ledger)
        assert not report.ok
        assert "secondhome.passive_monthly_income_usd" in report.render()

    def test_innocence_must_reference_facts_declared_and_present_passes(self) -> None:
        ledger = {"CL-X-01": _rec("CL-X-01", "VERIFIED")}
        manifest = {
            "rules": [
                {
                    "product_code": "X",
                    "claim_ids": ["CL-X-01"],
                    "caveats": [],
                    "must_reference_facts": ["intent.purposes"],
                    "rule": _minimal_rule(),
                }
            ]
        }
        report = compile_manifest(manifest, ledger)
        assert report.ok

    def test_innocence_manifest_without_must_reference_facts_field_passes(self) -> None:
        """Confirms the field is genuinely optional at the compile_manifest
        level, not merely optional in the helper's signature."""

        ledger = {"CL-X-01": _rec("CL-X-01", "VERIFIED")}
        manifest = {
            "rules": [
                {
                    "product_code": "X",
                    "claim_ids": ["CL-X-01"],
                    "caveats": [],
                    "rule": _minimal_rule(),
                }
            ]
        }
        report = compile_manifest(manifest, ledger)
        assert report.ok

    def test_guilt_falsy_non_list_must_reference_facts_is_rejected_not_swallowed(self) -> None:
        """kimi-k3 finding (2026-08-18): `entry.get(...) or []` treated any
        FALSY-but-present value (`""`, `0`, `False`) as if the field were
        simply absent, silently skipping the "must be a list" check. Only
        an explicit JSON null (or a genuinely missing key) should mean
        "not declared"; anything else non-list is malformed."""

        ledger = {"CL-X-01": _rec("CL-X-01", "VERIFIED")}
        for falsy_non_list in ("", 0, False):
            manifest = {
                "rules": [
                    {
                        "product_code": "X",
                        "claim_ids": ["CL-X-01"],
                        "caveats": [],
                        "must_reference_facts": falsy_non_list,
                        "rule": _minimal_rule(),
                    }
                ]
            }
            report = compile_manifest(manifest, ledger)
            assert not report.ok, f"expected rejection for must_reference_facts={falsy_non_list!r}"
            assert "must be a list" in report.render()

    def test_innocence_null_must_reference_facts_means_not_declared(self) -> None:
        """Explicit JSON null IS treated as absent — distinguishing "not
        declared" from "declared wrong" is the point of the fix above."""

        ledger = {"CL-X-01": _rec("CL-X-01", "VERIFIED")}
        manifest = {
            "rules": [
                {
                    "product_code": "X",
                    "claim_ids": ["CL-X-01"],
                    "caveats": [],
                    "must_reference_facts": None,
                    "rule": _minimal_rule(),
                }
            ]
        }
        report = compile_manifest(manifest, ledger)
        assert report.ok

    def test_guilt_synthetic_21_leaves_reports_note_and_still_compiles(self) -> None:
        """End-to-end through `compile_manifest`: a `when` with 21 distinct
        (real, FactPath-valid) leaves must skip the satisfiability check —
        never brute-force it — and the skip note must be visible in the
        rendered report even though the rule has no OTHER defect and
        compiles clean. Silence is not success (task brief, verbatim)."""

        from backend.services.visa_engine.enums import FactPath

        # Exclude immigration.overstay_days — Lint 2 (R-OVERSTAY-PLANNING)
        # flags any reference to it regardless of `op`, and this fixture is
        # testing Lint 3's skip-note in isolation.
        fact_paths = [f.value for f in FactPath if f.value != "immigration.overstay_days"]
        assert len(fact_paths) >= 21, "need >=21 real FactPath members for this fixture"
        leaves = [{"op": "known", "fact": fp} for fp in fact_paths[:21]]
        when = {"op": "all", "args": leaves}

        ledger = {"CL-X-01": _rec("CL-X-01", "VERIFIED")}
        rule = _minimal_rule(rule_id="hf.synthetic-21", when=when)
        manifest = {
            "rules": [{"product_code": "X", "claim_ids": ["CL-X-01"], "caveats": [], "rule": rule}]
        }
        report = compile_manifest(manifest, ledger)
        assert report.ok, report.render()
        assert len(report.notes) == 1
        assert "21 leaves > 20" in report.notes[0]
        rendered = report.render()
        assert "NOTES" in rendered
        assert "21 leaves > 20" in rendered


# ---------------------------------------------------------------------------
# E5 increment 3, Step 1 — ledger hygiene regressions (dual-header split +
# product-state-clause trap), see
# research/visa/doctrine-factory/e5/2026-08-19-e5-increment3-spec.md Step 1.
# ---------------------------------------------------------------------------


class TestLedgerHygiene:
    """Pins the two 2026-08-19 ledger fixes and proves — against the REAL
    parser, never by re-reading the regex — that the pre-fix shapes really
    were broken (guilt) and the post-fix shapes really do resolve correctly
    (innocence). Anti-hallucination discipline: every assertion below was
    verified by an actual ``parse_claim_ledger_text``/``load_claim_ledgers``
    call before being written into this file.
    """

    # -- 1a: e2b-batch3 dual-header split (CL-E31C-01 / CL-E31F-01) --------

    def test_innocence_cl_e31c_01_resolves_with_full_id_post_fix(self) -> None:
        ledger = load_claim_ledgers(_LEDGER_FILES)
        record = ledger["CL-E31C-01"]
        assert record.state == "VERIFIED-WITH-CAVEAT"
        assert record.compilable

    def test_innocence_cl_e31f_01_resolves_post_fix(self) -> None:
        ledger = load_claim_ledgers(_LEDGER_FILES)
        record = ledger["CL-E31F-01"]
        assert record.state == "VERIFIED-WITH-CAVEAT"
        assert record.compilable

    def test_guilt_unsplit_dual_header_shape_never_created_cl_e31f_01(self) -> None:
        """Reproduces the PRE-FIX shape (a single ``**CL-E31C-01 /
        CL-E31F-01 — ...**`` header) in an isolated fixture — never against
        the real ledger file, which is now fixed — and proves it: (a) never
        creates a ``CL-E31F-01`` record at all, and (b) truncates the first
        id to the bare ``CL-E31C`` (the ``-01`` suffix is consumed by
        ``_HEADER_RE``'s backtrack onto the literal hyphen inside
        ``E31C-01`` as its id/name separator — verified empirically against
        the real regex before writing this assertion). This is WHY the split
        in Step 1a was structurally necessary, not merely cosmetic."""

        old_broken_shape = (
            "**CL-E31C-01 / CL-E31F-01 — category identity, closed via "
            "production-catalog cross-reference.** E31C = \"Family Visa "
            "Child of Legal Mixed Marriage\"; E31F = \"Family Visa Anak "
            "Dengan Orang Tua WNI\".\n"
            "- Source: seed_visa_types_complete_2026.py.\n"
            "- **State: VERIFIED-WITH-CAVEAT** (dual-header pre-fix shape). "
            "Products: E31C, E31F.\n"
        )
        records = parse_claim_ledger_text(old_broken_shape, source_name="fixture-old-dual-header")
        assert "CL-E31F-01" not in records
        assert "CL-E31C-01" not in records
        assert "CL-E31C" in records  # the truncated survivor — proves the mis-parse, not a no-op

    # -- 1b: e2c-blocked5 product-state-clause trap (CL-E33B-03) -----------

    def test_innocence_cl_e33b_03_state_for_product_e33b_post_fix(self) -> None:
        ledger = load_claim_ledgers(_LEDGER_FILES)
        record = ledger["CL-E33B-03"]
        assert record.state_for_product("E33B") == "VERIFIED-WITH-CAVEAT"
        assert record.compilable_for_product("E33B")
        # The real parser returns `None`, not a literal `{}`, when the state
        # bullet contains fewer than 2 `**TOKEN** for PRODUCTS` clauses (see
        # claim_ledger.py::_parse_product_conditional_states) — `not record.
        # product_states` is the falsy check that actually matches the
        # runtime type, verified against the live parser before writing this
        # assertion (the increment-3 spec's literal "== {}" wording does not
        # match the field's real `dict | None` type; recorded as a spec
        # wording note in the implementer report, not a re-adjudication of
        # the claim's content).
        assert not record.product_states

    def test_guilt_old_product_state_clause_shape_produces_spurious_split(self) -> None:
        """Reproduces the PRE-FIX ``**VERIFIED** for the duration figure
        (...); **UNVERIFIED** for the flat ...`` shape in an isolated
        fixture and proves it trips ``_PRODUCT_STATE_CLAUSE_RE`` into a
        spurious ``product_states={"the": ...}`` split — "the" comes from
        the regex's product-list capture group greedily matching only the
        word "the" out of "the duration figure" / "the flat ...". This is
        exactly the defect Step 1b's rewrite (a single plain state bullet,
        with the nuance moved to prose that cannot match ``**TOKEN** for``)
        eliminates."""

        old_broken_shape = (
            "**CL-E33B-03 — Duration and sponsor per primary law.** "
            "Multiple entry.\n"
            "- Source: some source.\n"
            "- **State: VERIFIED** for the duration figure (5/10 years, "
            "machine-audited VERIFIED); **UNVERIFIED** for the flat "
            "sponsor-always-mandatory reading specifically, pending "
            "reconciliation. Products: E33B.\n"
        )
        records = parse_claim_ledger_text(old_broken_shape, source_name="fixture-old-e33b-03")
        record = records["CL-E33B-03"]
        assert record.product_states == {"the": "UNVERIFIED"}

    # -- 1c: e2c SUPERSEDED (CF-17) marker never becomes an authoritative
    #    claim state — proven against the real, unmodified ledger file. ----

    def test_innocence_e2c_superseded_marker_stays_non_compilable(self) -> None:
        """CF-17's in-block ``- **State: SUPERSEDED (Level 6 side).**``
        bullet (``e2c-blocked5-claim-ledger.md``) lives inside
        ``CL-E33C-03``'s header block (it is the LAST ``**CL-...**`` header
        in the file, so its block runs to end-of-file) but is the SECOND
        ``- **State: ...**`` bullet in that block — ``_STATE_RE`` only ever
        resolves the FIRST one. Prove the SUPERSEDED marker never won: (a)
        ``CL-E33C-03`` itself resolves to its own real first-bullet state,
        ``VERIFIED`` (compilable), never ``SUPERSEDED``; (b) no claim_id in
        the merged ledger resolves to state ``SUPERSEDED`` at all — the
        marker is descriptive prose about a cross-level conflict resolution
        (CF-17 has no ``**CL-...**`` header of its own), not a claim any
        rule could ever cite, so it is non-compilable by never being a
        resolvable claim_id in the first place."""

        ledger = load_claim_ledgers(_LEDGER_FILES)
        e33c_03 = ledger["CL-E33C-03"]
        assert e33c_03.state == "VERIFIED"
        assert e33c_03.compilable

        superseded_claims = [cid for cid, rec in ledger.items() if rec.state == "SUPERSEDED"]
        assert superseded_claims == []


# ---------------------------------------------------------------------------
# Golden: the real vertical-slice manifest against the real committed ledgers
# ---------------------------------------------------------------------------


class TestSliceGolden:
    def test_slice_manifest_compiles_clean_against_real_ledgers(self) -> None:
        ledger = load_claim_ledgers(_LEDGER_FILES)
        manifest = load_manifest(_SLICE_MANIFEST)
        report = compile_manifest(manifest, ledger)
        assert report.ok, report.render()
        assert len(report.compiled) == 26

        by_product: dict[str, int] = {}
        for entry in report.compiled:
            by_product[entry.product_code] = by_product.get(entry.product_code, 0) + 1
        assert by_product == {"D1": 6, "D2": 6, "D12": 7, "E31B": 2, "E31D": 5}

    def test_slice_e31b_gate_is_no_longer_value_blind(self) -> None:
        ledger = load_claim_ledgers(_LEDGER_FILES)
        manifest = load_manifest(_SLICE_MANIFEST)
        report = compile_manifest(manifest, ledger)
        sponsor_rule = next(
            e for e in report.compiled if e.rule.rule_id == "el.e31b-sponsor-itas-itap"
        )
        rendered = json.loads(sponsor_rule.rule.model_dump_json())
        assert "known" not in json.dumps(rendered["when"])
        assert "ITAS_ACTIVE" in json.dumps(rendered["when"])

    def test_slice_e31d_rules_no_longer_reduce_to_bare_family_purpose(self) -> None:
        ledger = load_claim_ledgers(_LEDGER_FILES)
        manifest = load_manifest(_SLICE_MANIFEST)
        report = compile_manifest(manifest, ledger)
        e31d_eligibility = [
            e
            for e in report.compiled
            if e.product_code == "E31D" and e.rule.stage.value == "ELIGIBILITY"
        ]
        assert len(e31d_eligibility) == 3
        for entry in e31d_eligibility:
            required = set(entry.rule.required_facts)
            assert "family.relation_to_sponsor" in required, entry.rule.rule_id

        hard_filters = {e.rule.rule_id for e in report.compiled if e.product_code == "E31D"} & {
            "hf.e31d-adult-excluded",
            "hf.e31d-married-excluded",
        }
        assert hard_filters == {"hf.e31d-adult-excluded", "hf.e31d-married-excluded"}

    def test_cli_main_runs_clean_on_the_real_slice(self, tmp_path: Path) -> None:
        out = tmp_path / "compiled.json"
        rc = main(
            [
                "--claims",
                *[str(p) for p in _LEDGER_FILES],
                "--manifest",
                str(_SLICE_MANIFEST),
                "--out",
                str(out),
            ]
        )
        assert rc == 0
        assert out.exists()
        compiled = json.loads(out.read_text(encoding="utf-8"))
        assert len(compiled) == 26

    def test_cli_main_fails_cleanly_on_missing_manifest(self, tmp_path: Path) -> None:
        rc = main(
            [
                "--claims",
                *[str(p) for p in _LEDGER_FILES],
                "--manifest",
                str(tmp_path / "does-not-exist.json"),
            ]
        )
        assert rc == 1
