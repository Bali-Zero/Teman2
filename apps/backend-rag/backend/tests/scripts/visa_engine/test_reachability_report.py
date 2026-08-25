"""Unit tests for the reachability_report CLI (QW-3).

Ground-truth strategy: several assertions here re-derive an expected value
with an INDEPENDENT code path (a raw-JSON recursive walk, not
``ast.collect_fact_paths``/``rule.required_facts``) rather than mirroring the
production module's own logic — a test that reimplements the function under
test in slightly different words and calls that "verification" only proves
self-consistency, not correctness (cicatrix family #6). Where an independent
re-derivation isn't practical (e.g. the pydantic-model-level orphan check),
the test instead exercises guilt AND innocence on a small synthetic pack
(cicatrix family #3's guard-conformance discipline: no check ships without
both).
"""

from __future__ import annotations

import copy
import json
import re
import uuid
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.scripts.visa_engine.reachability_report import (
    DEFAULT_FACT_MAPPER_PATH,
    build_report,
    main,
    report_to_json,
    report_to_markdown,
)
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY

PACKS_DIR = Path(__file__).resolve().parents[4] / "backend/services/visa_engine/contracts/packs"
SEQ7_PACK = PACKS_DIR / "rulepack-prod-007.source.json"
SEQ6_PACK = PACKS_DIR / "rulepack-prod-006.source.json"

# The exact unreachable set pinned by
# test_seq6_refuter_witnesses.py::test_reachability_is_what_the_document_claims
# for seq-6. This module's own report on seq-7 must reproduce it (seq-7 made
# no reachability-affecting change to that set — a real drift is exactly what
# this pin exists to catch).
PINNED_UNREACHABLE_CODES = [
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


def _independent_fact_walk(when: dict) -> set[str]:
    """Ground truth for "which facts does this condition tree reference",
    written independently of ``ast.collect_fact_paths`` / ``required_facts``
    — a raw recursive walk of the JSON condition tree."""
    out: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            fact = node.get("fact")
            if fact is not None:
                out.add(fact)
            for key, value in node.items():
                if key != "fact":
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(when)
    return out


@pytest.fixture(scope="module")
def seq7_raw() -> dict:
    return json.loads(SEQ7_PACK.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def seq7_report():
    return build_report(SEQ7_PACK)


def test_seq7_pack_exists_and_is_sequence_7(seq7_raw: dict) -> None:
    """Anti-hallucination anchor (CLAUDE.md §6): assert the fixture this
    whole file leans on really is what every other assertion assumes."""
    assert seq7_raw["sequence"] == 7


def test_seq6_pack_reproduces_its_own_pinned_assertion() -> None:
    """Sanity check on the tool itself, independent of seq-7: run it against
    seq-6 and confirm it reproduces exactly what
    test_seq6_refuter_witnesses.py::test_reachability_is_what_the_document_claims
    already asserts by hand against that same file. If this ever disagrees
    with that test, the bug is in THIS script, not in seq-6."""
    report = build_report(SEQ6_PACK)
    assert len(report.reachable_product_codes) == 27
    assert list(report.blocked_product_codes) == PINNED_UNREACHABLE_CODES


def test_reachability_matches_the_seq6_pin(seq7_report) -> None:
    """The headline number the task brief asks for: does seq-7 diverge from
    the seq-6 split pinned in test_seq6_refuter_witnesses.py? Answer: no."""
    assert len(seq7_report.reachable_product_codes) == 27
    assert len(seq7_report.blocked_product_codes) == 11
    assert list(seq7_report.blocked_product_codes) == PINNED_UNREACHABLE_CODES
    assert (set(seq7_report.reachable_product_codes) | set(seq7_report.blocked_product_codes)) == {
        p.product_code for p in seq7_report.products
    }


def test_reachable_and_blocked_partition_all_products(seq7_report) -> None:
    reachable = set(seq7_report.reachable_product_codes)
    blocked = set(seq7_report.blocked_product_codes)
    assert reachable & blocked == set()
    assert len(reachable) + len(blocked) == seq7_report.product_count


def test_fact_path_usage_matches_independent_walk(seq7_raw: dict) -> None:
    used_by_independent_walk: set[str] = set()
    for rule in seq7_raw["rules"]:
        used_by_independent_walk |= _independent_fact_walk(rule["when"])

    report = build_report(SEQ7_PACK)
    assert set(report.used_fact_paths) == used_by_independent_walk


def test_unused_fact_paths_is_registry_minus_used(seq7_report) -> None:
    all_paths = {str(p.value) for p in DEFAULT_FACT_REGISTRY.all_paths()}
    assert set(seq7_report.unused_fact_paths) == all_paths - set(seq7_report.used_fact_paths)
    assert seq7_report.total_fact_paths == len(all_paths)
    # The exact 13-path headline (was 8; 2026-08-23 vocabulary extension —
    # PR #4650 — added 4 new registry paths that no rule in
    # rulepack-prod-007.source.json references yet, which is exactly what
    # "vocabulary-only, no rulepack change" means: `derived.has_active_stay_permit`,
    # `family.sponsor_permit_basis`, `family.stepchild_marriage_certificate_confirmed`,
    # `family.stepchild_birth_certificate_confirmed`). Was 12; 2026-08-24 F4
    # (D12 active-stay-permit exclusion) adds the 13th, `immigration.renewal_paid` —
    # also vocabulary-only against this frozen seq-7 baseline. Unlike the other
    # four, it stays unused *by design* until seq-14 folds the D12 rule that
    # reads it: this is a deliberately dormant fact, not an accidentally
    # orphaned one — do not "fix" it by bumping the number down.
    assert len(seq7_report.unused_fact_paths) == 13


def test_required_facts_ast_invariant_holds_on_the_real_pack(seq7_report) -> None:
    """The compiler is supposed to enforce
    ``required_facts == collect_fact_paths(when)`` for every rule in a pack
    that compiles at all. If this ever fails on the real active pack, that
    is itself the finding — not a bug in this test."""
    assert seq7_report.required_facts_ast_mismatches == ()


def test_not_asked_facts_are_exactly_the_five_hardcoded_in_the_mapper() -> None:
    assert DEFAULT_FACT_MAPPER_PATH.exists(), (
        "the default fact-mapper path is stale — the live interview moved "
        "and this script's default needs updating"
    )
    text = DEFAULT_FACT_MAPPER_PATH.read_text(encoding="utf-8")
    # Independent extraction: a plain unconditional-assignment regex, not the
    # module's own compiled pattern.
    found = sorted(set(re.findall(r'"([a-z_]+\.[a-z_]+)":\s*unknownFact\(NOT_ASKED\),', text)))
    # `immigration.renewal_paid` used to be a sixth entry here, but 2026-08-24
    # F4 (D12 active-stay-permit exclusion) shipped the real interview
    # question for it (tree.ts, gated in flow.ts's
    # `computeNextNode`/`shouldAskRenewalPaid`), so fact-mapper.ts:591 now
    # maps it through `booleanFact(facts.renewal_paid)` — a real answered
    # fact, not an unconditional NOT_ASKED placeholder. It correctly drops
    # out of this list; this file just hadn't caught up.
    assert found == [
        "commercial.service_fee_budget_idr",
        "commercial.wants_quote",
        "immigration.last_entry_date",
        "intent.desired_entry_date",
        "intent.requested_product_code",
    ]

    report = build_report(SEQ7_PACK)
    assert list(report.not_asked_facts) == found


def test_gold_persona_extraction_is_still_accurate() -> None:
    """Guards the regex extraction in reachability_report.py against the
    gold-persona test file's shape drifting out from under it: import the
    real module (safe — module-level code is just dataclass construction
    plus two cheap asserts, no pytest machinery runs) and compare its
    ``PERSONAS[*].expected_candidates`` against what the regex found."""
    import importlib

    gold_module = importlib.import_module("backend.tests.services.visa_engine.test_evaluator_gold")
    expected_from_import = {
        code for persona in gold_module.PERSONAS for code in persona.expected_candidates
    }

    report = build_report(SEQ7_PACK)
    assert set(report.persona_corpus_product_codes) == expected_from_import


def test_products_without_positive_persona_excludes_covered_codes(seq7_report) -> None:
    covered = set(seq7_report.persona_corpus_product_codes) & {
        p.product_code for p in seq7_report.products
    }
    for code in covered:
        assert code not in seq7_report.products_without_positive_persona
    # E31 is a known fixture-only code (E31A..E31J exist for real, not E31).
    assert "E31" in seq7_report.persona_corpus_codes_absent_from_pack


def test_orphan_rules_none_on_the_real_pack(seq7_report) -> None:
    assert seq7_report.orphan_rules == ()


def test_orphan_rule_detection_guilt(tmp_path: Path, seq7_raw: dict) -> None:
    """Guilt: a rule naming a product_version_id that isn't in `products`
    must be flagged as orphan, and that product must not gain a phantom
    SUPPORT."""
    product = _clone_real_product(seq7_raw, "X1")
    dangling_id = str(uuid.uuid4())
    rule = _support_rule("sup.dangling", [dangling_id])
    payload = _base_payload_skeleton(seq7_raw, [product], [rule])
    pack_file = tmp_path / "synthetic.source.json"
    pack_file.write_text(payload, encoding="utf-8")

    report = build_report(pack_file)
    assert len(report.orphan_rules) == 1
    orphan = report.orphan_rules[0]
    assert orphan.rule_id == "sup.dangling"
    assert len(orphan.dangling_product_version_ids) == 1
    assert "X1" not in report.reachable_product_codes


def test_orphan_rule_detection_innocence(tmp_path: Path, seq7_raw: dict) -> None:
    """Innocence: a pack whose rule points at a real product must NOT be
    flagged orphan, and that product must show up reachable."""
    product = _clone_real_product(seq7_raw, "X2")
    rule = _support_rule("sup.valid", [product["product_version_id"]])
    payload = _base_payload_skeleton(seq7_raw, [product], [rule])
    pack_file = tmp_path / "synthetic.source.json"
    pack_file.write_text(payload, encoding="utf-8")

    report = build_report(pack_file)
    assert report.orphan_rules == ()
    assert "X2" in report.reachable_product_codes


def test_zero_scoped_product_is_not_the_same_claim_as_blocked(
    tmp_path: Path, seq7_raw: dict
) -> None:
    """A product with zero rules naming it at all is blocked (no SUPPORT),
    but "zero scoped rules" is a strictly narrower claim than "blocked" —
    a product excluded by name is blocked but NOT zero-scoped."""
    excluded_product = _clone_real_product(seq7_raw, "X3")
    untouched_product = _clone_real_product(seq7_raw, "X4")
    rule = _exclude_rule("hf.excluded", [excluded_product["product_version_id"]])
    payload = _base_payload_skeleton(seq7_raw, [excluded_product, untouched_product], [rule])
    pack_file = tmp_path / "synthetic.source.json"
    pack_file.write_text(payload, encoding="utf-8")

    report = build_report(pack_file)
    assert "X3" in report.blocked_product_codes
    assert "X3" not in report.products_with_zero_scoped_rules
    assert "X4" in report.blocked_product_codes
    assert "X4" in report.products_with_zero_scoped_rules


def test_global_scope_support_rule_grants_reachability(tmp_path: Path, seq7_raw: dict) -> None:
    """Guilt: a cross-family review found that a GLOBAL-scope SUPPORT rule
    (product_version_ids=None, applying to every product per the real
    evaluator) was being treated as scoping to ZERO products, silently
    under-reporting reachability. No product in this rule's scope names it
    explicitly — GLOBAL is the only source of support here."""
    product = _clone_real_product(seq7_raw, "X5")
    rule = _global_support_rule("sup.global")
    payload = _base_payload_skeleton(seq7_raw, [product], [rule])
    pack_file = tmp_path / "synthetic.source.json"
    pack_file.write_text(payload, encoding="utf-8")

    report = build_report(pack_file)
    assert "X5" in report.reachable_product_codes
    matched = next(p for p in report.products if p.product_code == "X5")
    assert rule["rule_id"] in matched.support_rule_ids


def test_global_scope_rule_is_never_flagged_orphan(tmp_path: Path, seq7_raw: dict) -> None:
    """Innocence: a GLOBAL rule names nothing explicitly, so it can never be
    a dangling reference — it must never appear in orphan_rules."""
    product = _clone_real_product(seq7_raw, "X6")
    rule = _global_support_rule("sup.global2")
    payload = _base_payload_skeleton(seq7_raw, [product], [rule])
    pack_file = tmp_path / "synthetic.source.json"
    pack_file.write_text(payload, encoding="utf-8")

    report = build_report(pack_file)
    assert report.orphan_rules == ()


def test_add_score_rule_counts_as_a_scoped_rule(tmp_path: Path, seq7_raw: dict) -> None:
    """Guilt: a product named only by a RANKING/ADD_SCORE rule (no
    HARD_FILTER/SUPPORT/REQUIRE_REVIEW) must NOT show up in
    products_with_zero_scoped_rules — an earlier draft's
    has_any_scoped_rule ignored ADD_SCORE entirely."""
    product = _clone_real_product(seq7_raw, "X7")
    rule = _add_score_rule("rank.x7", [product["product_version_id"]])
    payload = _base_payload_skeleton(seq7_raw, [product], [rule])
    pack_file = tmp_path / "synthetic.source.json"
    pack_file.write_text(payload, encoding="utf-8")

    report = build_report(pack_file)
    assert "X7" not in report.products_with_zero_scoped_rules
    # ADD_SCORE alone never grants reachability — SUPPORT is the only
    # reachability-granting effect.
    assert "X7" not in report.reachable_product_codes


def test_duplicate_product_code_raises_value_error(tmp_path: Path, seq7_raw: dict) -> None:
    """Guilt: two products sharing one product_code must fail loud, never
    silently collapse into one row (P2 finding — reachability/persona
    coverage are reported per product_code, and the model only guarantees
    product_version_id uniqueness)."""
    product_a = _clone_real_product(seq7_raw, "DUP")
    product_b = _clone_real_product(seq7_raw, "DUP")
    rule = _support_rule("sup.dup", [product_a["product_version_id"]])
    payload = _base_payload_skeleton(seq7_raw, [product_a, product_b], [rule])
    pack_file = tmp_path / "synthetic.source.json"
    pack_file.write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError, match="DUP"):
        build_report(pack_file)


def test_orphan_rule_with_mixed_valid_and_dangling_ids(tmp_path: Path, seq7_raw: dict) -> None:
    """A rule naming BOTH a real product and a dangling one must be flagged
    orphan (naming the dangling id specifically) while still crediting
    SUPPORT to the real product — the orphan finding is about the rule's
    OWN validity, not a license to hide what it does to valid targets."""
    product = _clone_real_product(seq7_raw, "X8")
    dangling_id = str(uuid.uuid4())
    rule = _support_rule("sup.mixed", [product["product_version_id"], dangling_id])
    payload = _base_payload_skeleton(seq7_raw, [product], [rule])
    pack_file = tmp_path / "synthetic.source.json"
    pack_file.write_text(payload, encoding="utf-8")

    report = build_report(pack_file)
    assert len(report.orphan_rules) == 1
    assert report.orphan_rules[0].rule_id == "sup.mixed"
    assert report.orphan_rules[0].dangling_product_version_ids == (dangling_id,)
    assert "X8" in report.reachable_product_codes


def test_products_without_positive_persona_includes_a_known_uncovered_code(
    seq7_report,
) -> None:
    """Guilt (the corpus's own P2 gap): the prior test only checked that
    COVERED codes are excluded from the without-list — an implementation
    that always returned an empty tuple would still pass it. `A1` is not
    among the persona corpus's 5 supported codes, so it must appear here."""
    assert "A1" not in seq7_report.persona_corpus_product_codes
    assert "A1" in seq7_report.products_without_positive_persona


def test_persona_code_regex_accepts_hyphenated_product_codes(tmp_path: Path) -> None:
    """A hyphenated code (schema-legal per PRODUCT_CODE_PATTERN
    ^[A-Z][A-Z0-9-]{0,31}$, e.g. a future 'E-31') must not vanish from the
    persona-corpus extraction — an earlier `[A-Z0-9]+` regex would drop it
    silently."""
    fake_gold_test = tmp_path / "fake_gold.py"
    fake_gold_test.write_text(
        'PERSONAS = []\nX = dict(expected_candidates=("E-31", "A1"))\n',
        encoding="utf-8",
    )
    report = build_report(SEQ7_PACK, gold_persona_test_path=fake_gold_test)
    assert "E-31" in report.persona_corpus_product_codes
    assert "A1" in report.persona_corpus_product_codes


def test_not_asked_extraction_raises_on_missing_data_literal(tmp_path: Path) -> None:
    """If the fact-mapper's shape drifts enough that the data-literal block
    can't be located, this must fail loud, not silently report zero
    NOT_ASKED facts."""
    bogus_mapper = tmp_path / "fact-mapper.ts"
    bogus_mapper.write_text("export const nothing = 1;\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ApplicantFactsDataWire"):
        build_report(SEQ7_PACK, fact_mapper_path=bogus_mapper)


def test_not_asked_extraction_ignores_a_comment_outside_the_data_literal(
    tmp_path: Path,
) -> None:
    """Guilt/innocence for the scoping fix itself: a NOT_ASKED-shaped
    comment BEFORE the data literal must not be picked up, while a real
    entry INSIDE it must be."""
    fake_mapper = tmp_path / "fact-mapper.ts"
    fake_mapper.write_text(
        '// "person.birth_date": unknownFact(NOT_ASKED), <- not real, just a comment\n'
        "export function mapOracleFactsToApplicantFacts() {\n"
        "  const data: ApplicantFactsDataWire = {\n"
        '    "intent.desired_entry_date": unknownFact(NOT_ASKED),\n'
        "  };\n"
        "  return { schema_version: 1, facts: data };\n"
        "}\n",
        encoding="utf-8",
    )
    report = build_report(SEQ7_PACK, fact_mapper_path=fake_mapper)
    assert report.not_asked_facts == ("intent.desired_entry_date",)


def test_report_to_json_round_trips(seq7_report) -> None:
    text = report_to_json(seq7_report)
    parsed = json.loads(text)
    assert parsed["sequence"] == 7
    assert parsed["product_count"] == 38


def test_report_to_markdown_carries_the_exempt_frontmatter(seq7_report) -> None:
    """The generated .md lives under research/**/*.md, in scope of
    scripts/check_adversarial_review.py — it must open with a frontmatter
    block declaring an adversarial_review key, or the R1 gate fails the PR."""
    text = report_to_markdown(seq7_report)
    assert text.startswith("---\n")
    frontmatter, _, _ = text[4:].partition("\n---\n")
    assert "adversarial_review: exempt-generated-artifact" in frontmatter
    assert "sources:" not in frontmatter
    assert "client_case:" not in frontmatter
    assert "discovered_by:" not in frontmatter


def test_main_writes_both_files_and_returns_0(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    rc = main(["--pack", str(SEQ7_PACK), "--out-dir", str(out_dir)])
    assert rc == 0
    json_path = out_dir / "rulepack-prod-007-reachability.json"
    md_path = out_dir / "rulepack-prod-007-reachability.md"
    assert json_path.exists()
    assert md_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["sequence"] == 7


def test_main_returns_1_on_missing_pack(tmp_path: Path) -> None:
    rc = main(["--pack", str(tmp_path / "does-not-exist.json")])
    assert rc == 1


def test_main_returns_1_on_invalid_pack(tmp_path: Path) -> None:
    bad = tmp_path / "bad.source.json"
    bad.write_text(json.dumps({"not": "a rule pack"}), encoding="utf-8")
    rc = main(["--pack", str(bad)])
    assert rc == 1


def test_build_report_raises_on_schema_invalid_pack(tmp_path: Path) -> None:
    bad = tmp_path / "bad.source.json"
    bad.write_text(json.dumps({"not": "a rule pack"}), encoding="utf-8")
    with pytest.raises(ValidationError):
        build_report(bad)


# ---------------------------------------------------------------------------
# Synthetic payload builders for the guilt/innocence tests above. Rather
# than hand-authoring a full VisaProductVersion/SourceRecord from scratch
# (a large, evolving schema — see the real pack's product dict above, which
# has ~15 fields this test file would otherwise have to keep in lockstep
# with every schema change), these CLONE one real product/source record out
# of the actual seq-7 pack and only touch the couple of fields the test
# under test actually cares about (product_version_id, product_code). This
# keeps the fixtures schema-valid for free and future-proof against the
# model gaining new required fields.
# ---------------------------------------------------------------------------

_PACK_ID = str(uuid.uuid4())


def _clone_real_product(seq7_raw: dict, new_code: str) -> dict:
    product = copy.deepcopy(seq7_raw["products"][0])
    product["product_version_id"] = str(uuid.uuid4())
    product["product_code"] = new_code
    return product


def _base_payload_skeleton(seq7_raw: dict, products: list[dict], rules: list[dict]) -> str:
    source_record = copy.deepcopy(seq7_raw["source_records"][0])
    payload = {
        "rule_pack_id": _PACK_ID,
        "sequence": 1,
        "version": "1.0.0",
        "environment": "TEST",
        "jurisdiction": "ID",
        "decision_domain": "IMMIGRATION_VISA",
        "engine_contract_version": "1.0.0",
        "engine_min_version": "1.0.0",
        "engine_max_version": "1.0.0",
        "valid_period": {"from": "2026-01-01T00:00:00Z", "to": None},
        "created_at": "2026-01-01T00:00:00Z",
        "created_by": "test-fixture",
        "previous_payload_sha256": None,
        "rollback_of_payload_sha256": None,
        "hit_policy": {
            "hard_filter": "COLLECT_ALL",
            "eligibility": "COVER_ALL_DECLARED_PURPOSES",
            "human_review": "COLLECT_ALL",
            "ranking": "SUM_TRUE_INTEGER_WEIGHTS",
        },
        "source_records": [source_record],
        "products": products,
        "rules": rules,
    }
    for rule in rules:
        rule["source_refs"] = [source_record["source_record_id"]]
    return json.dumps(payload)


def _support_rule(rule_id: str, product_version_ids: list[str]) -> dict:
    return {
        "rule_id": rule_id,
        "stage": "ELIGIBILITY",
        "scope": "PRODUCTS",
        "product_version_ids": product_version_ids,
        "priority": 1,
        "valid_period": {"from": "2026-01-01T00:00:00Z", "to": None},
        "when": {"op": "known", "fact": "intent.purposes"},
        "effect": {
            "type": "SUPPORT",
            "reason_code": "TEST_SUPPORT",
            "covered_purposes": ["TOURISM"],
        },
        "on_unknown": "NEEDS_INPUT",
        "required_facts": ["intent.purposes"],
        "source_refs": [],  # filled in by _base_payload_skeleton
        "explanation_key": "explain.test",
        "safety_critical": False,
    }


def _global_support_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "stage": "ELIGIBILITY",
        "scope": "GLOBAL",
        "product_version_ids": None,
        "priority": 1,
        "valid_period": {"from": "2026-01-01T00:00:00Z", "to": None},
        "when": {"op": "known", "fact": "intent.purposes"},
        "effect": {
            "type": "SUPPORT",
            "reason_code": "TEST_GLOBAL_SUPPORT",
            "covered_purposes": ["TOURISM"],
        },
        "on_unknown": "NEEDS_INPUT",
        "required_facts": ["intent.purposes"],
        "source_refs": [],  # filled in by _base_payload_skeleton
        "explanation_key": "explain.test",
        "safety_critical": False,
    }


def _add_score_rule(rule_id: str, product_version_ids: list[str]) -> dict:
    return {
        "rule_id": rule_id,
        "stage": "RANKING",
        "scope": "PRODUCTS",
        "product_version_ids": product_version_ids,
        "priority": 1,
        "valid_period": {"from": "2026-01-01T00:00:00Z", "to": None},
        "when": {"op": "known", "fact": "intent.purposes"},
        "effect": {"type": "ADD_SCORE", "reason_code": "TEST_ADD_SCORE", "points": 1},
        "on_unknown": "NO_EFFECT",
        "required_facts": ["intent.purposes"],
        "source_refs": [],  # filled in by _base_payload_skeleton
        "explanation_key": "explain.test",
        "safety_critical": False,
    }


def _exclude_rule(rule_id: str, product_version_ids: list[str]) -> dict:
    return {
        "rule_id": rule_id,
        "stage": "HARD_FILTER",
        "scope": "PRODUCTS",
        "product_version_ids": product_version_ids,
        "priority": 100,
        "valid_period": {"from": "2026-01-01T00:00:00Z", "to": None},
        "when": {"op": "eq", "fact": "derived.has_indonesian_citizenship", "value": True},
        "effect": {"type": "EXCLUDE", "reason_code": "TEST_EXCLUDE"},
        "on_unknown": "NEEDS_INPUT",
        "required_facts": ["derived.has_indonesian_citizenship"],
        "source_refs": [],  # filled in by _base_payload_skeleton
        "explanation_key": "explain.test",
        "safety_critical": True,
    }
