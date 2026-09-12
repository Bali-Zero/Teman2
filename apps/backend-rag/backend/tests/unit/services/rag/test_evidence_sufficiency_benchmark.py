"""B1.3 — structural assertions on the frozen evidence-sufficiency benchmark.

Nothing here asserts anything NEW about the scorer: these tests pin the
MANIFEST's shape and freeze it (sha256), and prove the harness's `decide()`
reads only (query, context, sources) — never a label field. The scorer's
actual behaviour on this manifest is a REPORT (`harness.report()`), not an
assertion; B1 is behaviour-preserving by design (README D5).
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path

import pytest

from backend.tests.benchmarks.evidence_sufficiency import harness

_BENCH_DIR = Path(harness.__file__).resolve().parent
_MANDATORY_PATH = _BENCH_DIR / "manifest_mandatory.json"
_SUPPLEMENT_PATH = _BENCH_DIR / "manifest_supplement_b2.json"
_VALIDATION_PATH = _BENCH_DIR / "validation_codex.json"
_GOLDEN_TEST_PATH = Path(__file__).resolve().parent / "agentic" / "test_evidence_cross_language.py"

# Pinned on the manifest's bytes as frozen for B1.3. A change to the file
# after the freeze — a re-labelled case, a reworded span, anything — makes
# this red. That is the point: the mandatory set is frozen, and B2
# supplements live in a SEPARATE file (`manifest_supplement_b2.json`).
#
# RE-PINNED (RULED I30/I31, provenance-fixture PR): this is the ONE
# sanctioned exception to the freeze above — the only PR allowed to touch
# the frozen manifest. Case bs-17806bb4's `provenance_fixture` moved from a
# legacy literal (score 0.72, score_kind unknown) to a declared dense source
# (score 0.6146, score_kind dense_formatted, score_raw the one measured
# cosine on disk for that (query, chunk) pair — 0.373, 2026-09-03); nothing
# else in the manifest changed. Old pin (until this PR):
# 9d7ea833b52bdcb9cf4fcc09c7e608f7edcc8bf2d50c5df86c4fd9849142e48f.
MANDATORY_MANIFEST_SHA256 = "d23a66ca27f48d2bf186f941e902a99c6991803ae53c651fedbab201772da745"

_CELLS = ("EN>EN", "EN>ID", "ID>EN", "ID>ID")
_NEGATIVE_STRATA = (
    "relevant_insufficient",
    "irrelevant",
    "generic_overlap",
    "company_prefix_chunk",
)


@pytest.fixture(scope="module")
def manifest() -> dict:
    return harness.load(_MANDATORY_PATH)


@pytest.fixture(scope="module")
def supplement() -> dict:
    return harness.load(_SUPPLEMENT_PATH)


def test_manifest_sha256_is_frozen() -> None:
    digest = hashlib.sha256(_MANDATORY_PATH.read_bytes()).hexdigest()
    assert digest == MANDATORY_MANIFEST_SHA256, (
        "manifest_mandatory.json changed after the B1.3 freeze — re-pin only "
        "after independent label review, per B1-design.md §4 B1.3"
    )


def test_validate_returns_no_error_on_the_mandatory_manifest(manifest: dict) -> None:
    errors = harness.validate(manifest)
    assert errors == [], errors


class TestSupplementIsWellFormedAndNeverPooledWithMandatory:
    """B2.1 populated `manifest_supplement_b2.json` with Set B (ruling I26's
    4 mandatory distractor pairs, 8 cases) and Set C (the 12 D-SETC
    hard-case pairs, 24 cases). This class REPLACES the old
    `test_supplement_file_exists_and_is_empty`, which pinned the pre-B2.1
    stub shape `{"schema_version": 1, "cases": []}` — that assertion could
    only ever describe the state before B2.1's Task 1 filled the file in, so
    it went stale the moment the task succeeded rather than the moment
    something broke. This pins the shape B2.1 actually produced instead.

    Two labelling notes belong here because a reader of the supplement will
    hit them directly, not just the PR that introduced them:

    - `company_prefix` is NOT pinned as a literal string anywhere in the
      manifest header the way `generic_word_definition` is. It was
      reverse-engineered for the supplement (identifier-token overlap
      between query and context, using the same vocabulary as
      `generic_word_identifiers`) and independently VERIFIED to reproduce
      all 58 `company_prefix` labels in the frozen mandatory manifest with
      zero mismatches before the supplement trusted it as a computable
      rule. Frozen-and-pinned and reconstructed-and-verified are different
      guarantees — the next reader should not assume this one is written
      down anywhere but here.
    - `fee_policy` has NO mechanical rule, pinned or reconstructable. Every
      lexical hypothesis tried while building the supplement (token overlap
      on query only / context only / both, an 18-word bilingual
      fee/price/capital lexicon) fails to reproduce the mandatory
      manifest's own 8 `fee_policy=true` labels, which turn out to be a
      hand-picked subgroup rather than a function of the visible text —
      e.g. "Harga PT PMA berapa all in?" is labelled False while "How much
      is a PT PMA company, all in?" is labelled True, same topic, same
      requested fact. The supplement therefore does NOT try to match that
      hidden rule: it applies its own explicit, documented one instead (a
      keyword match against `requested_fact`) and says so here rather than
      presenting a guess as ground truth.
    """

    def test_parses_and_validates_clean_under_the_harness(self, supplement: dict) -> None:
        errors = harness.validate(supplement)
        assert errors == [], errors

    def test_set_b_and_set_c_have_their_declared_case_counts(self, supplement: dict) -> None:
        by_set: dict[str, int] = {}
        for case in supplement["cases"]:
            assert "set" in case, f"{case.get('case_id')}: missing 'set' field"
            by_set[case["set"]] = by_set.get(case["set"], 0) + 1

        assert by_set.get("B") == 8, by_set  # ruling I26 mandatory distractors: 4 pairs
        assert by_set.get("C") == 24, by_set  # D-SETC hard-case pairs: 12 pairs
        # Set D: the cross-language cell of 6 of those hard pairs — English
        # query, Indonesian context and label unchanged. It is the cell where
        # a support-driven relevance RAISE would fire, and the only one Set C
        # (monolingual by construction) never measured.
        assert by_set.get("D") == 12, by_set
        assert sum(by_set.values()) == len(supplement["cases"]) == 44

    def test_every_pair_has_one_sufficient_and_one_relevant_insufficient_with_identical_provenance(
        self, supplement: dict
    ) -> None:
        pairs: dict[str, list[dict]] = {}
        for case in supplement["cases"]:
            pairs.setdefault(case["pair_id"], []).append(case)

        assert len(pairs) == 22, sorted(pairs)  # 4 (Set B) + 12 (Set C) + 6 (Set D)
        for pair_id, members in pairs.items():
            assert len(members) == 2, (pair_id, len(members))
            strata = sorted(m["stratum"] for m in members)
            assert strata == ["relevant_insufficient", "sufficient"], (pair_id, strata)
            sets = {m["set"] for m in members}
            assert len(sets) == 1, (pair_id, sets)  # never mixes Set B with Set C

            a, b = members
            assert json.dumps(a["provenance_fixture"], sort_keys=True) == json.dumps(
                b["provenance_fixture"], sort_keys=True
            ), f"pair {pair_id}: provenance differs between members"

    def test_no_supplement_case_leaks_into_the_mandatory_report(
        self, manifest: dict, supplement: dict
    ) -> None:
        mandatory_ids = {c["case_id"] for c in manifest["cases"]}
        supplement_ids = {c["case_id"] for c in supplement["cases"]}
        assert mandatory_ids.isdisjoint(supplement_ids)

        # report() only ever iterates whatever manifest dict it is handed —
        # this is a regression guard against a future wiring mistake that
        # concatenates the two case lists before calling it.
        result = harness.report(manifest)
        assert result["mandatory"]["case_count"] == len(manifest["cases"])

        decided_ids = set()
        for pair in result["mandatory"]["spec_pairs"].values():
            decided_ids.add(pair["sufficient_case_id"])
            decided_ids.add(pair["relevant_insufficient_case_id"])
        assert decided_ids.isdisjoint(supplement_ids)


class TestBalancePerCell:
    """Balance contract (B1-3-build-spec.md): per cell >= 3 sufficient and
    >= 1 of each of the four negative strata."""

    def _counts(self, manifest: dict) -> dict[str, dict[str, int]]:
        counts: dict[str, dict[str, int]] = {c: {} for c in _CELLS}
        for case in manifest["cases"]:
            cell = f"{case['query_lang']}>{case['context_lang']}"
            counts[cell][case["stratum"]] = counts[cell].get(case["stratum"], 0) + 1
        return counts

    @pytest.mark.parametrize("cell", _CELLS)
    def test_at_least_three_sufficient(self, manifest: dict, cell: str) -> None:
        counts = self._counts(manifest)
        assert counts[cell].get("sufficient", 0) >= 3, counts[cell]

    @pytest.mark.parametrize("cell", _CELLS)
    @pytest.mark.parametrize("stratum", _NEGATIVE_STRATA)
    def test_at_least_one_of_each_negative_stratum(
        self, manifest: dict, cell: str, stratum: str
    ) -> None:
        counts = self._counts(manifest)
        assert counts[cell].get(stratum, 0) >= 1, (cell, stratum, counts[cell])


class TestEveryCellByGateByMetricHasAPositiveDenominator:
    @pytest.mark.parametrize("cell", _CELLS)
    @pytest.mark.parametrize("gate", ("generation", "label"))
    @pytest.mark.parametrize("metric", ("false_abstention", "false_acceptance"))
    def test_denominator_is_positive(
        self, manifest: dict, cell: str, gate: str, metric: str
    ) -> None:
        result = harness.report(manifest)
        denominator = result["mandatory"]["by_cell"][cell][gate][metric]["denominator"]
        assert denominator > 0, (cell, gate, metric, denominator)


def test_every_topic_in_spec_pair_covers_all_four_cells(manifest: dict) -> None:
    topics: dict[str, set[str]] = {}
    for case in manifest["cases"]:
        topic = case.get("spec_pair")
        if topic:
            cell = f"{case['query_lang']}>{case['context_lang']}"
            topics.setdefault(topic, set()).add(cell)

    assert set(topics) == {
        "all_in_price",
        "nib_oss_requirements",
        "minimum_paid_up_capital",
        "registration_duration",
    }
    for topic, cells in topics.items():
        assert cells == set(_CELLS), (topic, cells)


def test_the_three_golden_corrections_carry_activates_in_b2_1(manifest: dict) -> None:
    """The original D5 set: :183, :186, :187. Distinguished from the label
    -review round's two ADDITIONAL corrections (:182, :185, below) by the
    absence of an `adjudication` field — these three were never contested."""
    corrected = [
        c
        for c in manifest["cases"]
        if c.get("recorded_golden_expectation") is True and "adjudication" not in c
    ]
    assert len(corrected) == 3, corrected
    for case in corrected:
        assert case["activates_in"] == "B2.1", case
        assert case["stratum"] == "relevant_insufficient", case
    origins = {c["origin"] for c in corrected}
    assert origins == {
        "golden:test_evidence_cross_language.py:183",
        "golden:test_evidence_cross_language.py:186",
        "golden:test_evidence_cross_language.py:187",
    }, origins


def test_two_more_golden_corrections_carry_adjudication(manifest: dict) -> None:
    """Label-review round (2026-09-11): :182 and :185 were relabelled from
    `sufficient` to `relevant_insufficient` on Gemini 3.1 Pro + Codex
    gpt-5.6-sol agreement, ratified by the staff room (decision I13,
    2026-09-12 02:05 WITA) as a D5 extension from three named corrections to
    five. Distinguished from the original three by carrying an
    `adjudication` field that records the ruling."""
    adjudicated = [
        c
        for c in manifest["cases"]
        if c.get("recorded_golden_expectation") is True and "adjudication" in c
    ]
    assert len(adjudicated) == 2, adjudicated
    for case in adjudicated:
        assert case["activates_in"] == "B2.1", case
        assert case["stratum"] == "relevant_insufficient", case
        assert case["adjudication"].startswith("RULED staff room"), case["adjudication"]
    origins = {c["origin"] for c in adjudicated}
    assert origins == {
        "golden:test_evidence_cross_language.py:182",
        "golden:test_evidence_cross_language.py:185",
    }, origins


def test_the_xfail_and_cured_ref_names_exist_and_carry_the_right_marker(manifest: dict) -> None:
    """One name per state, and the STATE is asserted, not just the name.

    Before the provenance-fixture PR both golden references were `xfail_ref`.
    bs-17806bb4 is now CURED — its test passes because the fixture declares
    real provenance — so it moved to `cured_ref`, and this test is the
    tripwire that notices if anyone puts the marker back or lets the other
    one quietly become a pass.
    """
    xfail_refs = {c["xfail_ref"] for c in manifest["cases"] if c.get("xfail_ref")}
    cured_refs = {c["cured_ref"] for c in manifest["cases"] if c.get("cured_ref")}
    assert xfail_refs == {"test_one_generic_word_should_not_be_evidence"}, xfail_refs
    assert cured_refs == {
        "test_a_question_naming_no_identifier_is_still_language_blind"
    }, cured_refs
    assert not (xfail_refs & cured_refs), "a case cannot be both xfail and cured"

    tree = ast.parse(_GOLDEN_TEST_PATH.read_text(encoding="utf-8"))
    functions = {
        node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }
    for ref in xfail_refs | cured_refs:
        assert ref in functions, f"{ref!r} not found in {_GOLDEN_TEST_PATH}"

    def _is_xfail(node: ast.FunctionDef) -> bool:
        for decorator in node.decorator_list:
            for sub in ast.walk(decorator):
                if isinstance(sub, ast.Attribute) and sub.attr == "xfail":
                    return True
        return False

    for ref in xfail_refs:
        assert _is_xfail(functions[ref]), f"{ref!r} is declared xfail_ref but carries no xfail marker"
    for ref in cured_refs:
        assert not _is_xfail(functions[ref]), (
            f"{ref!r} is declared CURED but still carries an xfail marker — "
            "either the cure was reverted or the manifest is lying"
        )


class TestLabelsNeverSelectInputs:
    """`decide()` reads ONLY query, context and provenance sources. Flipping
    every stratum/expected_*/span field in a deep copy must not change a
    single `decide()` output."""

    @staticmethod
    def _flip_strata(manifest: dict) -> dict:
        mutated = copy.deepcopy(manifest)
        strata_cycle = (
            "sufficient",
            "relevant_insufficient",
            "irrelevant",
            "generic_overlap",
            "company_prefix_chunk",
        )
        for case in mutated["cases"]:
            current = case["stratum"]
            new_stratum = strata_cycle[(strata_cycle.index(current) + 1) % len(strata_cycle)]
            case["stratum"] = new_stratum

            case["expected_generation_gate"] = (
                "abstain" if case["expected_generation_gate"] == "pass" else "pass"
            )
            case["expected_label_gate"] = (
                "abstain" if case["expected_label_gate"] == "pass" else "pass"
            )

            # swap span <-> missing-fact-explanation content so a decide()
            # that (incorrectly) read either would see garbage
            if "supporting_span" in case:
                case["missing_fact_explanation"] = case.pop("supporting_span")[::-1]
            elif "missing_fact_explanation" in case:
                case["supporting_span"] = case.pop("missing_fact_explanation")[::-1]

            case["generic_overlap"] = not case["generic_overlap"]
            case["company_prefix"] = not case["company_prefix"]
            case["fee_policy"] = not case["fee_policy"]
        return mutated

    def test_decide_output_is_identical_under_label_mutation(self, manifest: dict) -> None:
        mutated = self._flip_strata(manifest)
        # sanity: the mutation actually changed something, or this test proves nothing
        assert mutated != manifest

        for original_case, mutated_case in zip(manifest["cases"], mutated["cases"], strict=True):
            assert original_case["case_id"] == mutated_case["case_id"]
            original_decision = harness.decide(original_case)
            mutated_decision = harness.decide(mutated_case)
            assert original_decision == mutated_decision, original_case["case_id"]


def test_run_the_harness_cli_once(manifest: dict) -> None:
    """The one behaviour test of this module: the harness computes a report
    without raising, on the frozen manifest, end to end."""
    errors = harness.validate(manifest)
    assert errors == []
    result = harness.report(manifest)
    mandatory = result["mandatory"]
    assert mandatory["case_count"] == len(manifest["cases"])
    assert set(mandatory["by_cell"]) == set(_CELLS)
    assert mandatory["spec_pairs_summary"]["total"] == 16


class TestMandatoryAndValidationReportsAreNeverPooled:
    """Codex finding 5: `report()` used to accept one manifest and return one
    undifferentiated aggregate. It now takes an optional second (validation)
    manifest and reports it SEPARATELY — a validation case can never inflate
    or dilute a mandatory denominator, and vice versa."""

    def test_report_without_validation_has_a_null_validation_section(self, manifest: dict) -> None:
        result = harness.report(manifest)
        assert set(result) == {"mandatory", "validation"}
        assert result["validation"] is None
        assert result["mandatory"]["case_count"] == len(manifest["cases"])

    def test_a_validation_manifest_with_no_cases_reports_as_null(self, manifest: dict) -> None:
        empty_validation = {"schema_version": 1, "drawn_by": None, "cases": []}
        result = harness.report(manifest, empty_validation)
        assert result["validation"] is None

    def test_validation_cases_never_change_the_mandatory_report(self, manifest: dict) -> None:
        baseline = harness.report(manifest)
        validation = harness.load(_VALIDATION_PATH)
        pooled_check = harness.report(manifest, validation)
        assert pooled_check["mandatory"] == baseline["mandatory"]

    def test_the_validation_set_is_reported_on_its_own_case_count(self, manifest: dict) -> None:
        validation = harness.load(_VALIDATION_PATH)
        result = harness.report(manifest, validation)
        assert result["validation"] is not None
        assert result["validation"]["case_count"] == len(validation["cases"])
        # the mandatory and validation case counts are disjoint sets of ids
        mandatory_ids = {c["case_id"] for c in manifest["cases"]}
        validation_ids = {c["case_id"] for c in validation["cases"]}
        assert mandatory_ids.isdisjoint(validation_ids)


class TestValidateRejectsMalformedNuisanceBooleansAndProvenance:
    """Codex finding 7: `validate()` used to silently accept a case missing
    the nuisance booleans, or a `provenance_fixture` with a malformed
    `inventory_row` or an incomplete source."""

    @pytest.mark.parametrize("field", ("generic_overlap", "company_prefix", "fee_policy"))
    def test_missing_nuisance_boolean_is_rejected(self, manifest: dict, field: str) -> None:
        mutated = copy.deepcopy(manifest)
        del mutated["cases"][0][field]
        errors = harness.validate(mutated)
        assert any(field in e for e in errors), errors

    @pytest.mark.parametrize("field", ("generic_overlap", "company_prefix", "fee_policy"))
    def test_non_bool_nuisance_value_is_rejected(self, manifest: dict, field: str) -> None:
        mutated = copy.deepcopy(manifest)
        mutated["cases"][0][field] = "true"
        errors = harness.validate(mutated)
        assert any(field in e for e in errors), errors

    def test_non_int_inventory_row_is_rejected(self, manifest: dict) -> None:
        mutated = copy.deepcopy(manifest)
        mutated["cases"][0]["provenance_fixture"]["inventory_row"] = "5"
        errors = harness.validate(mutated)
        assert any("inventory_row" in e for e in errors), errors

    @pytest.mark.parametrize("field", ("score", "score_kind", "score_raw"))
    def test_source_missing_a_required_field_is_rejected(self, manifest: dict, field: str) -> None:
        mutated = copy.deepcopy(manifest)
        del mutated["cases"][0]["provenance_fixture"]["sources"][0][field]
        errors = harness.validate(mutated)
        assert any(field in e for e in errors), errors

    @pytest.mark.parametrize("bad_sources", (None, [], ["not-an-object"]))
    def test_missing_empty_or_non_object_sources_are_rejected(
        self, manifest: dict, bad_sources: object
    ) -> None:
        mutated = copy.deepcopy(manifest)
        if bad_sources is None:
            del mutated["cases"][0]["provenance_fixture"]["sources"]
        else:
            mutated["cases"][0]["provenance_fixture"]["sources"] = bad_sources
        errors = harness.validate(mutated)
        assert any("provenance_fixture" in e and "source" in e for e in errors), errors

    @pytest.mark.parametrize("bad_note", (None, "", 5))
    def test_missing_or_empty_note_is_rejected(self, manifest: dict, bad_note: object) -> None:
        mutated = copy.deepcopy(manifest)
        if bad_note is None:
            del mutated["cases"][0]["provenance_fixture"]["note"]
        else:
            mutated["cases"][0]["provenance_fixture"]["note"] = bad_note
        errors = harness.validate(mutated)
        assert any("provenance_fixture.note" in e for e in errors), errors


class TestValidateRejectsMalformedQueryOrContextTypes:
    """Dux ruling K5: `validate()` now type-checks `query` (must be a str)
    and `context` (must be a list whose every element is a str). Before
    this check existed, a bare-string `context` (e.g. "foo" instead of
    ["foo"]) still iterated and `" ".join()`d downstream — one character at
    a time — and a list `query` still `.lower()`d nowhere near validate(),
    so both silently passed."""

    def test_bare_string_context_is_rejected(self, manifest: dict) -> None:
        mutated = copy.deepcopy(manifest)
        mutated["cases"][0]["context"] = "this is a bare string, not a list"
        errors = harness.validate(mutated)
        assert any("context" in e for e in errors), errors

    def test_list_query_is_rejected(self, manifest: dict) -> None:
        mutated = copy.deepcopy(manifest)
        mutated["cases"][0]["query"] = ["not", "a", "string"]
        errors = harness.validate(mutated)
        assert any("query" in e for e in errors), errors

    def test_checked_in_manifest_validates_clean_under_the_new_type_checks(
        self, manifest: dict
    ) -> None:
        errors = harness.validate(manifest)
        assert not any("query must be" in e or "context must be" in e for e in errors), errors


def test_the_replay_key_is_injective_over_query_and_context() -> None:
    """Round-1 adversarial finding (codex-gpt-5.6-sol), reproduced then cured.

    The first key was `query + "\\x00" + "\\n".join(context)`, under which a
    two-chunk context and a one-chunk context carrying a newline hash
    identically. `decide()` raises on a MISSING key, so an uncovered case is
    safe; a COLLIDING case is not — it reads a verdict measured on different
    text, silently. The collision was LATENT, never active: the 114 recorded
    cases produced 114 distinct keys under both derivations, which is why the
    cure re-keys the record without re-measuring one verdict.
    """
    a = harness.support_record_key("a", ["b", "c"])
    b = harness.support_record_key("a", ["b\nc"])
    assert a != b

    c = harness.support_record_key("a\x00b", [])
    d = harness.support_record_key("a", ["b"])
    assert c != d

    # The frozen record's keys are exactly the keys the current derivation
    # produces for the cases it covers — no stale key survives the re-keying.
    record = harness.load_support_record(
        Path(harness.__file__).resolve().parent / "support_verdicts_b2.json",
    )
    manifests = ["manifest_mandatory.json", "manifest_supplement_b2.json", "validation_codex.json"]
    bench = Path(harness.__file__).resolve().parent
    keys = {
        harness.support_record_key(case["query"], case["context"])
        for name in manifests
        for case in harness.load(bench / name)["cases"]
    }
    assert set(record) == keys, "record keys and manifest-derived keys diverge"
