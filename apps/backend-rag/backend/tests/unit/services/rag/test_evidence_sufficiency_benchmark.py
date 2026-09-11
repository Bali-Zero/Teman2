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
from pathlib import Path

import pytest

from backend.tests.benchmarks.evidence_sufficiency import harness

_BENCH_DIR = Path(harness.__file__).resolve().parent
_MANDATORY_PATH = _BENCH_DIR / "manifest_mandatory.json"
_SUPPLEMENT_PATH = _BENCH_DIR / "manifest_supplement_b2.json"
_GOLDEN_TEST_PATH = Path(__file__).resolve().parent / "agentic" / "test_evidence_cross_language.py"

# Pinned on the manifest's bytes as frozen for B1.3. A change to the file
# after the freeze — a re-labelled case, a reworded span, anything — makes
# this red. That is the point: the mandatory set is frozen, and B2
# supplements live in a SEPARATE file (`manifest_supplement_b2.json`).
MANDATORY_MANIFEST_SHA256 = "53fa143e5eaae714c109f7f2d931ef16bce3c97e7838b6a526eeb0261ca00c5d"

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


def test_manifest_sha256_is_frozen() -> None:
    digest = hashlib.sha256(_MANDATORY_PATH.read_bytes()).hexdigest()
    assert digest == MANDATORY_MANIFEST_SHA256, (
        "manifest_mandatory.json changed after the B1.3 freeze — re-pin only "
        "after independent label review, per B1-design.md §4 B1.3"
    )


def test_validate_returns_no_error_on_the_mandatory_manifest(manifest: dict) -> None:
    errors = harness.validate(manifest)
    assert errors == [], errors


def test_supplement_file_exists_and_is_empty() -> None:
    supplement = harness.load(_SUPPLEMENT_PATH)
    assert supplement == {"schema_version": 1, "cases": []}


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
        denominator = result["by_cell"][cell][gate][metric]["denominator"]
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
    corrected = [c for c in manifest["cases"] if c.get("recorded_golden_expectation") is True]
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


def test_the_two_xfail_ref_names_exist_in_the_golden_test_file(manifest: dict) -> None:
    xfail_refs = {c["xfail_ref"] for c in manifest["cases"] if c.get("xfail_ref")}
    assert xfail_refs == {
        "test_a_question_naming_no_identifier_is_still_language_blind",
        "test_one_generic_word_should_not_be_evidence",
    }, xfail_refs

    tree = ast.parse(_GOLDEN_TEST_PATH.read_text(encoding="utf-8"))
    defined_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    for ref in xfail_refs:
        assert ref in defined_names, f"{ref!r} not found in {_GOLDEN_TEST_PATH}"


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
    assert result["case_count"] == len(manifest["cases"])
    assert set(result["by_cell"]) == set(_CELLS)
    assert result["spec_pairs_summary"]["total"] == 16
