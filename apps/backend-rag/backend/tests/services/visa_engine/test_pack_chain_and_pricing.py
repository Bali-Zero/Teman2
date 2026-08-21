"""E5 increment 3, Step 5 — chain/pricing/retirement/dangling-ref gates for
the assembled ``rulepack-prod-009.source.json`` (see
``backend.scripts.visa_engine.fold_pack``, which produces this file
deterministically from seq-7 + seq-8 + the blocked7 manifest + the Step-4
source edits).

Five checks, each independently verified against the real files on disk
(never against a value copy-pasted from a prior session's terminal
output):

(a) chain gate — seq-9's ``previous_payload_sha256`` equals the
    RECOMPUTED SHA256(JCS(...)) of seq-7's own source payload — never just
    a declared-field-vs-declared-field comparison (Codex refuter finding
    5 / Kimi refuter finding 6, 2026-08-19: the earlier version of this
    test compared ``seq9_source["previous_payload_sha256"]`` against
    ``seq7_signed["payload_sha256"]`` as two trusted strings; a corrupted
    or hand-edited seq-7 signed file with a wrong-but-64-hex-char
    ``payload_sha256`` would have passed. The house pattern for this is
    ``test_seq7_sponsor_witnesses.py``'s
    ``test_previous_payload_sha256_chains_to_the_real_seq6_file``, which
    recomputes via ``canonicalize_json`` rather than trusting a declared
    field — same fix applied here one generation later in the chain);
    ``sequence``/``rule_pack_id`` match the Anchors convention; the seq-8
    broken-chain lesson (OD-2) is pinned permanently (seq-8's
    ``previous_payload_sha256`` does NOT chain to seq-7, and no
    ``rulepack-prod-008.signed.json`` exists on disk).
(b) pricing-key parity — the exact 24-product non-null / 14-product null
    table, with the 11 seq-8-sourced entries deep-equal to seq-8 and the
    13 already-priced-in-seq-7 entries deep-equal (unchanged) to seq-7.
(c) the 2 retired seq-7 rule ids are absent from seq-9; the 8 inserted
    rule ids are present.
(d) the inc-2 lint functions (UNSAT brute-force + VACUOUS duplicate-
    subtree) run over EVERY seq-9 rule. This does NOT assert "zero
    findings" — it asserts the TRUE state discovered this session: seq-9
    inherits exactly 2 pre-existing duplicate-subtree defects from seq-7
    (``el.c2.corporate-sponsor-type``, ``el.e31c-mixed-marriage-parents``)
    that are OUTSIDE this increment's authorized scope (the spec's Step 3
    names only ``el.e33e.deposit-income-basis`` /
    ``el.e33g.income-60k-manual`` for cure; C2/E31C have no claim citation
    or doctrine authorization in this increment to touch). Declaring them
    here — rather than silently asserting a false "zero findings" — is
    the CP3 residual this test exists to surface; it also proves (i) both
    Step-3 cure targets are gone and (ii) none of the 8 newly-inserted
    rules introduced a NEW defect.
(e) every rule's/product's ``source_refs`` resolves to a ``source_record``
    in seq-9 — no dangling refs survive the Step-4 edits (0497cb52 drop,
    ee8fe5b8 co-ref removal, hf.e31e-*/c9e6f0e4 repoint).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine.compile_claims import (
    compile_manifest,
    lint_duplicate_subtree,
    lint_unsatisfiable_condition,
    load_manifest,
)
from backend.services.visa_engine.bundle import canonicalize_json
from backend.services.visa_engine.claim_ledger import load_claim_ledgers

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

_SEQ7_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-007.source.json"
_SEQ7_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-007.signed.json"
_SEQ8_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-008.source.json"
_SEQ8_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-008.signed.json"
_SEQ6_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-006.signed.json"
_SEQ9_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-009.source.json"

_CLAIMS_DIR = _REPO_ROOT / "research" / "visa" / "doctrine-factory" / "claims"
_LEDGER_FILES = [
    _CLAIMS_DIR / "e2a-claim-ledger.md",
    _CLAIMS_DIR / "e2b-batch1-claim-ledger.md",
    _CLAIMS_DIR / "e2b-batch2-claim-ledger.md",
    _CLAIMS_DIR / "e3a-cf1-resolution.md",
    _CLAIMS_DIR / "e2b-batch3-claim-ledger.md",
    _CLAIMS_DIR / "e2c-blocked5-claim-ledger.md",
]
_E5_DIR = _REPO_ROOT / "research" / "visa" / "doctrine-factory" / "e5"
_BLOCKED7_MANIFEST_PATH = _E5_DIR / "blocked7-rule-manifest.json"
_CURE_E33G_PATH = _E5_DIR / "inc3-pack-edits" / "cure-e33g.json"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def seq7_source() -> dict[str, Any]:
    return _load(_SEQ7_SOURCE_PATH)


@pytest.fixture(scope="module")
def seq7_signed() -> dict[str, Any]:
    return _load(_SEQ7_SIGNED_PATH)


@pytest.fixture(scope="module")
def seq8_source() -> dict[str, Any]:
    return _load(_SEQ8_SOURCE_PATH)


@pytest.fixture(scope="module")
def seq9_source() -> dict[str, Any]:
    return _load(_SEQ9_SOURCE_PATH)


@pytest.fixture(scope="module")
def blocked7_compiled_by_id() -> dict[str, dict[str, Any]]:
    """Independently RE-COMPILE ``blocked7-rule-manifest.json`` against the
    same 6 claim ledgers ``fold_pack.py`` uses — a fresh ``compile_manifest``
    call on the manifest/ledger files on disk, never fold_pack.py's own
    already-materialized pack output. This is the "compiled manifest
    output" the content-parity tests below diff the PACK against (Kimi
    refuter finding 1, 2026-08-19: the prior suite pinned rule identity/
    counts/lints but never semantic content — a live mutation of the
    COMMITTED PACK swapping which product code
    ``review.e23u/e23v.requested-product``'s ``eq`` leaf targets, or
    Codex's in-memory inversion of ``hf.e33a``'s ``neq GOVERNMENT`` to
    ``eq GOVERNMENT``, passed the manifest compiler + both inc-2 lints +
    every pre-existing test in this file clean).
    """

    ledger = load_claim_ledgers(_LEDGER_FILES)
    manifest = load_manifest(_BLOCKED7_MANIFEST_PATH)
    report = compile_manifest(manifest, ledger)
    assert report.ok, report.render()
    return {
        entry.rule.rule_id: entry.rule.model_dump(mode="json", by_alias=True)
        for entry in report.compiled
    }


@pytest.fixture(scope="module")
def cure_e33g_rules_by_id() -> dict[str, dict[str, Any]]:
    cure = _load(_CURE_E33G_PATH)
    return {r["rule_id"]: r for r in cure["rules"]}


# ---------------------------------------------------------------------------
# (a) chain gate
# ---------------------------------------------------------------------------


class TestChainGate:
    def test_seq9_previous_payload_sha256_chains_to_seq7_signed(
        self,
        seq9_source: dict[str, Any],
        seq7_source: dict[str, Any],
        seq7_signed: dict[str, Any],
    ) -> None:
        """Recompute seq-7's canonical payload hash from the real seq-7
        SOURCE file bytes (``canonicalize_json`` + sha256 — RFC 8785 JCS,
        the same recipe ``bundle.py`` uses to produce ``payload_sha256`` at
        signing time), never trusting either file's own declared string.

        Two assertions, deliberately kept separate so a future break names
        WHICH side lied: (1) the signed envelope's own declared
        ``payload_sha256`` is itself honest — it equals the hash recomputed
        from the source file's bytes (this is the self-consistency check
        ``verify_rule_pack``/``_verify_unsigned_dev`` perform at trust-
        boundary crossings, re-run here independently); (2) seq-9's
        ``previous_payload_sha256`` equals that SAME recomputed value —
        the actual anti-rollback chain assertion, now anchored to real
        bytes on disk instead of two copy-pasted strings that happen to
        match.
        """

        recomputed_seq7_hash = hashlib.sha256(canonicalize_json(seq7_source)).hexdigest()
        assert recomputed_seq7_hash == seq7_signed["payload_sha256"], (
            "seq-7 SIGNED envelope's declared payload_sha256 does not match "
            "SHA256(JCS(rulepack-prod-007.source.json)) — the signed file's "
            "own self-consistency is broken, independent of seq-9 entirely"
        )
        assert seq9_source["previous_payload_sha256"] == recomputed_seq7_hash

    def test_seq9_sequence_is_9(self, seq9_source: dict[str, Any]) -> None:
        assert seq9_source["sequence"] == 9

    def test_seq9_rule_pack_id_matches_uuid5_convention(self, seq9_source: dict[str, Any]) -> None:
        expected = uuid.uuid5(
            uuid.NAMESPACE_URL,
            "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/9",
        )
        assert seq9_source["rule_pack_id"] == str(expected)
        # Same convention reproduces seq-7's own id for sequence 7 — pins
        # that the formula, not just this one output, is correct (Anchors
        # section: "reproduces seq-7's id with domain IMMIGRATION_VISA").
        expected_seq7 = uuid.uuid5(
            uuid.NAMESPACE_URL,
            "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/7",
        )
        assert expected_seq7 == uuid.UUID("453ee842-7f35-5d77-b460-31d67e2784c2")

    def test_seq8_chain_is_broken_od2_lesson_pinned(
        self, seq8_source: dict[str, Any], seq7_signed: dict[str, Any]
    ) -> None:
        """OD-2 (2026-08-16/18 rulings): seq-8 was never signed standalone
        and its ``previous_payload_sha256`` does NOT chain to seq-7 —
        this is why seq-8 is FOLDED into seq-9 rather than activated on
        its own. A future "helpful" edit that makes seq-8 look chained
        would silently undo the reason this fold exists at all.
        """

        assert seq8_source["previous_payload_sha256"] != seq7_signed["payload_sha256"]
        if _SEQ6_SIGNED_PATH.exists():
            seq6_signed = _load(_SEQ6_SIGNED_PATH)
            assert seq8_source["previous_payload_sha256"] == seq6_signed["payload_sha256"]

    def test_no_seq8_signed_pack_exists(self) -> None:
        assert not _SEQ8_SIGNED_PATH.exists(), (
            "rulepack-prod-008.signed.json must not exist — seq-8 was folded "
            "into seq-9, never activated standalone (OD-2)"
        )


# ---------------------------------------------------------------------------
# (b) pricing-key parity
# ---------------------------------------------------------------------------

#: The 11 products whose pricing_key seq-9 folds in from seq-8 (Anchors
#: section of the E5 inc-3 spec, verified this session against both packs).
_PRICING_FOLDED_FROM_SEQ8 = frozenset(
    {"E28A", "E33", "E33E", "E33F", "E33G", "A1", "B1", "C1", "C6", "C2", "BRIDGING"}
)

#: The 13 products already priced in seq-7, untouched by this fold.
_ALREADY_PRICED_IN_SEQ7 = frozenset(
    {
        "D1",
        "D12",
        "D2",
        "E23",
        "E31A",
        "E31B",
        "E31C",
        "E31D",
        "E31E",
        "E31F",
        "E31G",
        "E31H",
        "E31J",
    }
)

#: The 14 products with no pricing_key at all in seq-7, seq-8, or seq-9.
_STILL_UNPRICED = frozenset(
    {
        "E23U",
        "E23V",
        "E28B",
        "E28C",
        "E28D",
        "E28F",
        "E30",
        "E30A",
        "E30B",
        "E30E",
        "E30F",
        "E33A",
        "E33B",
        "E33C",
    }
)


def _products_by_code(pack: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {p["product_code"]: p for p in pack["products"]}


class TestPricingParity:
    def test_the_three_groups_partition_every_product(self, seq9_source: dict[str, Any]) -> None:
        all_codes = {p["product_code"] for p in seq9_source["products"]}
        groups = _PRICING_FOLDED_FROM_SEQ8 | _ALREADY_PRICED_IN_SEQ7 | _STILL_UNPRICED
        assert all_codes == groups
        assert len(all_codes) == 38
        assert len(_PRICING_FOLDED_FROM_SEQ8) == 11
        assert len(_ALREADY_PRICED_IN_SEQ7) == 13
        assert len(_STILL_UNPRICED) == 14

    def test_folded_products_match_seq8_pricing_key_exactly(
        self, seq9_source: dict[str, Any], seq8_source: dict[str, Any]
    ) -> None:
        seq9_by_code = _products_by_code(seq9_source)
        seq8_by_code = _products_by_code(seq8_source)
        for code in _PRICING_FOLDED_FROM_SEQ8:
            assert seq9_by_code[code]["pricing_key"] is not None
            assert seq9_by_code[code]["pricing_key"] == seq8_by_code[code]["pricing_key"]

    def test_already_priced_products_unchanged_from_seq7(
        self, seq9_source: dict[str, Any], seq7_source: dict[str, Any]
    ) -> None:
        seq9_by_code = _products_by_code(seq9_source)
        seq7_by_code = _products_by_code(seq7_source)
        for code in _ALREADY_PRICED_IN_SEQ7:
            assert seq9_by_code[code]["pricing_key"] is not None
            assert seq9_by_code[code]["pricing_key"] == seq7_by_code[code]["pricing_key"]

    def test_still_unpriced_products_remain_null(self, seq9_source: dict[str, Any]) -> None:
        seq9_by_code = _products_by_code(seq9_source)
        for code in _STILL_UNPRICED:
            assert seq9_by_code[code]["pricing_key"] is None


# ---------------------------------------------------------------------------
# (c) retired / inserted rule ids
# ---------------------------------------------------------------------------

_RETIRED_RULE_IDS = frozenset({"el.e33e.deposit-income-basis", "el.e33g.income-60k-manual"})

_INSERTED_RULE_IDS = frozenset(
    {
        "review.e33g.income-evidence",
        "el.e30e-student-support",
        "el.e30f-student-support",
        "hf.e33a.sponsor-not-government",
        "hf.e33b.sponsor-not-government-or-none",
        "hf.e33c.sponsor-not-government-or-none",
        "review.e23u.requested-product",
        "review.e23v.requested-product",
    }
)


class TestRuleRetirementAndInsertion:
    def test_retired_rules_absent(self, seq9_source: dict[str, Any]) -> None:
        ids = {r["rule_id"] for r in seq9_source["rules"]}
        assert ids.isdisjoint(_RETIRED_RULE_IDS)
        # el.e33g.remote-work-configuration was deliberately NOT added
        # (Assembly decision #2 — would be byte-identical to the
        # pre-existing el.e33g.remote-work).
        assert "el.e33g.remote-work-configuration" not in ids

    def test_inserted_rules_present(self, seq9_source: dict[str, Any]) -> None:
        ids = {r["rule_id"] for r in seq9_source["rules"]}
        assert _INSERTED_RULE_IDS <= ids

    def test_rule_count_is_seq7_minus_2_plus_8(
        self, seq9_source: dict[str, Any], seq7_source: dict[str, Any]
    ) -> None:
        assert len(seq9_source["rules"]) == len(seq7_source["rules"]) - 2 + 8


# ---------------------------------------------------------------------------
# (d) inc-2 lints over every seq-9 rule
# ---------------------------------------------------------------------------

#: Pre-existing seq-7 duplicate-subtree defects, inherited unchanged into
#: seq-9 (see class docstring — out of this increment's authorized scope,
#: declared here rather than silently swept under a false "zero findings").
_KNOWN_PRE_EXISTING_LINT_RESIDUALS = frozenset(
    {"el.c2.corporate-sponsor-type", "el.e31c-mixed-marriage-parents"}
)


class TestInc2LintsOverEverySeq9Rule:
    def test_only_the_known_pre_existing_residuals_have_findings(
        self, seq9_source: dict[str, Any]
    ) -> None:
        flagged: set[str] = set()
        for rule in seq9_source["rules"]:
            unsat_findings, skip_note = lint_unsatisfiable_condition(
                rule_id=rule["rule_id"], when=rule["when"]
            )
            assert skip_note is None, f"{rule['rule_id']}: unexpected skip ({skip_note})"
            dup_findings = lint_duplicate_subtree(rule_id=rule["rule_id"], when=rule["when"])
            if unsat_findings or dup_findings:
                flagged.add(rule["rule_id"])

        assert flagged == _KNOWN_PRE_EXISTING_LINT_RESIDUALS

    def test_the_two_retired_defects_are_gone(self, seq9_source: dict[str, Any]) -> None:
        ids = {r["rule_id"] for r in seq9_source["rules"]}
        assert "el.e33e.deposit-income-basis" not in ids
        assert "el.e33g.income-60k-manual" not in ids

    def test_none_of_the_8_inserted_rules_have_a_lint_finding(
        self, seq9_source: dict[str, Any]
    ) -> None:
        by_id = {r["rule_id"]: r for r in seq9_source["rules"]}
        for rule_id in _INSERTED_RULE_IDS:
            rule = by_id[rule_id]
            unsat_findings, skip_note = lint_unsatisfiable_condition(
                rule_id=rule_id, when=rule["when"]
            )
            assert skip_note is None
            assert unsat_findings == []
            dup_findings = lint_duplicate_subtree(rule_id=rule_id, when=rule["when"])
            assert dup_findings == []


# ---------------------------------------------------------------------------
# (e) source_refs resolve — no dangling refs
# ---------------------------------------------------------------------------


class TestNoDanglingSourceRefs:
    def test_every_rule_source_ref_resolves(self, seq9_source: dict[str, Any]) -> None:
        known = {r["source_record_id"] for r in seq9_source["source_records"]}
        dangling: dict[str, list[str]] = {}
        for rule in seq9_source["rules"]:
            unknown = [ref for ref in rule["source_refs"] if ref not in known]
            if unknown:
                dangling[rule["rule_id"]] = unknown
        assert dangling == {}

    def test_every_product_source_ref_resolves(self, seq9_source: dict[str, Any]) -> None:
        known = {r["source_record_id"] for r in seq9_source["source_records"]}
        dangling: dict[str, list[str]] = {}
        for product in seq9_source["products"]:
            unknown = [ref for ref in product.get("source_refs", []) if ref not in known]
            if unknown:
                dangling[product["product_code"]] = unknown
        assert dangling == {}

    def test_0497cb52_is_dropped(self, seq9_source: dict[str, Any]) -> None:
        ids = {r["source_record_id"] for r in seq9_source["source_records"]}
        assert "0497cb52-9c10-5ad5-a0ea-596e7678bd9b" not in ids

    def test_ee8fe5b8_still_present_referenced_only_by_products_now(
        self, seq9_source: dict[str, Any]
    ) -> None:
        """Assembly decision #5 scoped the co-ref cleanup to RULES only —
        the record itself must survive (3 D1/D2/D12 product refs still
        cite it), but zero rules should cite it any more.
        """

        target = "ee8fe5b8-b0b4-544a-bf9a-fe53c3e316f2"
        ids = {r["source_record_id"] for r in seq9_source["source_records"]}
        assert target in ids

        rule_refs = [r["rule_id"] for r in seq9_source["rules"] if target in r["source_refs"]]
        assert rule_refs == []

        product_refs = [
            p["product_code"]
            for p in seq9_source["products"]
            if target in p.get("source_refs", [])
        ]
        assert set(product_refs) == {"D1", "D2", "D12"}

    def test_e31e_hard_filter_rules_repointed_to_c9e6f0e4(
        self, seq9_source: dict[str, Any]
    ) -> None:
        by_id = {r["rule_id"]: r for r in seq9_source["rules"]}
        for rule_id in ("hf.e31e-adult-excluded", "hf.e31e-married-excluded"):
            assert by_id[rule_id]["source_refs"] == ["c9e6f0e4-5e84-572d-b1ca-e4e11ab50c24"]

    def test_c9e6f0e4_gained_the_pasal_33_locator(self, seq9_source: dict[str, Any]) -> None:
        by_id = {r["source_record_id"]: r for r in seq9_source["source_records"]}
        locators = by_id["c9e6f0e4-5e84-572d-b1ca-e4e11ab50c24"]["locators"]
        assert {"kind": "ARTICLE", "value": "Pasal 33"} in locators


# ---------------------------------------------------------------------------
# (f) inserted-rule CONTENT parity (Codex refuter finding 3/6, Kimi refuter
#     finding 1, 2026-08-19) — the checks above pin identity, counts, refs,
#     and lints, but nothing above pins the semantic CONTENT of the 8
#     inserted rules' `when`/`effect`/`scope` (which includes reason_code).
# ---------------------------------------------------------------------------

_CONTENT_PINNED_FIELDS = ("when", "effect", "scope")


class TestInsertedRuleContentParity:
    """Live-mutation-proven gap (Kimi refuter, 2026-08-19): swapping the
    `eq(intent.requested_product_code, ...)` values of
    `review.e23u.requested-product` <-> `review.e23v.requested-product` in
    the COMMITTED pack (a full semantic inversion — E23U's rule now fires
    for E23V requesters and vice versa), or Codex's in-memory mutation of
    `hf.e33a.sponsor-not-government` from `neq GOVERNMENT` to
    `eq GOVERNMENT`, left every test in this file (as it stood before this
    class) green. These tests diff the PACK's actual `when`/`effect`/
    `scope` for each of the 8 inserted rules against an INDEPENDENT
    recompilation of the same source artifacts (blocked7-rule-manifest.json
    + the 6 ledgers via a fresh `compile_manifest` call, or cure-e33g.json's
    raw JSON directly) — never against fold_pack.py's own already-
    materialized output, so a mutation of the tracked pack file itself (not
    just the manifest at rest) goes red here.
    """

    def test_blocked7_rules_content_matches_independent_recompile(
        self, seq9_source: dict[str, Any], blocked7_compiled_by_id: dict[str, dict[str, Any]]
    ) -> None:
        by_id = {r["rule_id"]: r for r in seq9_source["rules"]}
        assert set(blocked7_compiled_by_id) <= set(by_id)
        mismatches: dict[str, dict[str, Any]] = {}
        for rule_id, expected in blocked7_compiled_by_id.items():
            actual = by_id[rule_id]
            for field in _CONTENT_PINNED_FIELDS:
                if actual[field] != expected[field]:
                    mismatches.setdefault(rule_id, {})[field] = {
                        "pack": actual[field],
                        "recompiled": expected[field],
                    }
        assert mismatches == {}

    def test_e33g_review_rule_content_matches_cure_source(
        self, seq9_source: dict[str, Any], cure_e33g_rules_by_id: dict[str, dict[str, Any]]
    ) -> None:
        by_id = {r["rule_id"]: r for r in seq9_source["rules"]}
        actual = by_id["review.e33g.income-evidence"]
        expected = cure_e33g_rules_by_id["review.e33g.income-evidence"]
        for field in _CONTENT_PINNED_FIELDS:
            assert actual[field] == expected[field], (
                f"{field} diverged from cure-e33g.json's source"
            )

    def test_reason_codes_match_the_recompiled_effect(
        self,
        seq9_source: dict[str, Any],
        blocked7_compiled_by_id: dict[str, dict[str, Any]],
        cure_e33g_rules_by_id: dict[str, dict[str, Any]],
    ) -> None:
        """Explicit ``reason_code`` assertion — spec wording calls it out
        separately from ``effect`` even though it lives inside ``effect``;
        kept as its own test so a future refactor that narrows the
        ``effect`` comparison can't silently drop reason_code coverage.
        """

        by_id = {r["rule_id"]: r for r in seq9_source["rules"]}
        for rule_id, expected in blocked7_compiled_by_id.items():
            assert by_id[rule_id]["effect"]["reason_code"] == expected["effect"]["reason_code"]
        e33g_expected = cure_e33g_rules_by_id["review.e33g.income-evidence"]
        assert (
            by_id["review.e33g.income-evidence"]["effect"]["reason_code"]
            == e33g_expected["effect"]["reason_code"]
        )


# ---------------------------------------------------------------------------
# (g) full product-object parity (Codex refuter finding 6, 2026-08-19) —
#     TestPricingParity above checks ONLY the pricing_key field; mutating
#     any other product field (e.g. E28A's names.en) stayed green.
# ---------------------------------------------------------------------------


class TestFullProductObjectParity:
    """Every one of the 38 products in seq-9 must equal its seq-7
    counterpart on EVERY field except ``pricing_key`` — the 11
    pricing-folded products differ only there (asserted equal to seq-8's
    value by ``TestPricingParity`` above); the other 27 are fully
    byte-equal to seq-7.
    """

    def test_every_product_field_matches_seq7_except_pricing_key(
        self, seq9_source: dict[str, Any], seq7_source: dict[str, Any]
    ) -> None:
        seq9_by_code = _products_by_code(seq9_source)
        seq7_by_code = _products_by_code(seq7_source)
        assert set(seq9_by_code) == set(seq7_by_code)

        mismatches: dict[str, dict[str, Any]] = {}
        for code, seq9_product in seq9_by_code.items():
            seq7_product = seq7_by_code[code]
            seq9_without_pricing = {k: v for k, v in seq9_product.items() if k != "pricing_key"}
            seq7_without_pricing = {k: v for k, v in seq7_product.items() if k != "pricing_key"}
            if seq9_without_pricing != seq7_without_pricing:
                mismatches[code] = {"seq9": seq9_without_pricing, "seq7": seq7_without_pricing}
        assert mismatches == {}
