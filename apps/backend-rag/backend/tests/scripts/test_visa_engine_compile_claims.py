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
    lint_overstay_planning,
    lint_verified_only,
    load_claim_ledgers,
    load_manifest,
    main,
)
from backend.services.visa_engine.claim_ledger import ClaimRecord

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
]


def _rec(claim_id: str, state: str) -> ClaimRecord:
    return ClaimRecord(claim_id=claim_id, state=state, header="test", backs=(), source_file="<test>")


def _minimal_rule(rule_id: str = "el.test-rule", *, when: dict | None = None) -> dict:
    return {
        "rule_id": rule_id,
        "stage": "ELIGIBILITY",
        "scope": "PRODUCTS",
        "product_version_ids": ["5d5f9bd4-349b-54d7-841a-784c0afba068"],
        "priority": 100,
        "valid_period": {"from": "2026-07-24T00:00:00Z", "to": None},
        "when": when or {"fact": "intent.purposes", "op": "intersects", "values": ["FAMILY"]},
        "effect": {"type": "SUPPORT", "reason_code": "PURPOSE_PRODUCT_MATCH", "covered_purposes": ["FAMILY"]},
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
        findings = lint_verified_only(rule_id="el.x", claim_ids=["CL-X-01"], caveats=[], ledger=ledger)
        assert findings and "STALE" in findings[0].message

    def test_guilt_unverified_claim_is_rejected(self) -> None:
        ledger = {"CL-X-01": _rec("CL-X-01", "UNVERIFIED")}
        findings = lint_verified_only(rule_id="el.x", claim_ids=["CL-X-01"], caveats=[], ledger=ledger)
        assert findings and "UNVERIFIED" in findings[0].message

    def test_guilt_unknown_claim_id_is_rejected(self) -> None:
        findings = lint_verified_only(rule_id="el.x", claim_ids=["CL-GHOST-01"], caveats=[], ledger={})
        assert findings and "does not resolve" in findings[0].message

    def test_guilt_caveat_with_verified_with_caveat_but_no_note(self) -> None:
        ledger = {"CL-X-01": _rec("CL-X-01", "VERIFIED-WITH-CAVEAT")}
        findings = lint_verified_only(rule_id="el.x", claim_ids=["CL-X-01"], caveats=[], ledger=ledger)
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
        findings = lint_verified_only(rule_id="el.x", claim_ids=["CL-X-01"], caveats=[], ledger=ledger)
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


# ---------------------------------------------------------------------------
# Full compiler: end-to-end guilt + innocence
# ---------------------------------------------------------------------------


class TestCompileManifest:
    def test_guilt_manifest_with_conflicting_claim_fails_whole_report(self) -> None:
        ledger = {"CL-X-01": _rec("CL-X-01", "CONFLICTING")}
        manifest = {
            "rules": [
                {"product_code": "X", "claim_ids": ["CL-X-01"], "caveats": [], "rule": _minimal_rule()}
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
                {"product_code": "X", "claim_ids": ["CL-X-01"], "caveats": [], "rule": _minimal_rule()}
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
