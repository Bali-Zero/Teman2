"""Guard for the nine tripwire pipeline variants (B1.2, spec §3, G1-G5).

Purely static/pure-function checks: parses the four original tripwire test files with `ast`
(paths resolved relative to THIS file's own location, never a hardcoded absolute path) and
exercises the pure `pipeline_sources`/`format_search_results` functions. No network, no app
init.

The nine `_pipeline_variant` functions ship in the same PR, each beside its preserved original.
G1-G3 pin the registry (shape, live-transform values, key set, original existence); G4/G5 pin
the variants (existence, their `pipeline_sources(...)` call, no unlabelled score literal, assert
parity with the original). A variant that disappears or a re-introduced unlabelled value is red.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest

from backend.core import score_provenance
from backend.services.misc.result_formatter import format_search_results
from backend.tests.fixtures.pipeline_score_fixtures import (
    PIPELINE_TRIPWIRE_FIXTURES,
    pipeline_sources,
)

# ============================================================================
# The nine node ids, independent of the registry's own keys — G3 checks the
# registry against THIS list, not against itself.
# ============================================================================

NODE_IDS: Final[tuple[str, ...]] = (
    "unit/services/rag/agentic/test_abstain_bypass_policy.py::TestTrustedToolDetection::"
    "test_successful_but_irrelevant_vector_hit_stays_below_abstain_gate",
    "unit/services/rag/agentic/test_reasoning.py::TestCalculateEvidenceScore::"
    "test_no_keyword_overlap",
    "services/rag/agentic/test_reasoning_utils.py::TestCalculateEvidenceScore::"
    "test_stop_words_only_query_keyword_ratio_zero",
    "services/rag/agentic/test_reasoning_utils.py::TestCalculateEvidenceScore::"
    "test_short_words_only_yields_near_zero",
    "services/rag/agentic/test_reasoning_utils.py::TestCalculateEvidenceScore::"
    "test_entity_mismatch_company_vs_visa",
    "services/rag/agentic/test_reasoning_utils.py::TestCalculateEvidenceScore::"
    "test_semantic_penalty_not_applied_when_final_score_at_or_below_015",
    "services/rag/test_evidence_scoring_abstain.py::TestEvidenceScoringFixed::"
    "test_kitas_query_with_kbli_results_low_score",
    "services/rag/test_evidence_scoring_abstain.py::TestEvidenceScoringFixed::"
    "test_nonsense_query_zero_score",
    "services/rag/test_evidence_scoring_abstain.py::TestEvidenceScoringFixed::"
    "test_entity_type_mismatch_detection",
)


# ============================================================================
# AST helpers — files are located relative to THIS file's own __file__, tests
# root = the `tests` directory that contains this guard.
# ============================================================================


def _tests_root() -> Path:
    """Walk up from this file until the `tests` directory is found."""
    path = Path(__file__).resolve().parent
    while path.name != "tests":
        if path.parent == path:  # pragma: no cover - filesystem root guard
            raise RuntimeError(
                f"could not locate a 'tests' directory above {__file__!r}",
            )
        path = path.parent
    return path


def _parse_module(rel_path: str) -> ast.Module:
    file_path = _tests_root() / rel_path
    source = file_path.read_text()
    return ast.parse(source, filename=str(file_path))


def _find_class(module: ast.Module, class_name: str) -> ast.ClassDef | None:
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    return None


FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def _find_function(class_node: ast.ClassDef, func_name: str) -> FunctionNode | None:
    for node in class_node.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            return node
    return None


def _locate_original(node_id: str) -> tuple[str, str, str, ast.Module, ast.ClassDef | None]:
    """Split a node id and parse its module + class. Function lookup is the caller's job."""
    rel_path, class_name, func_name = node_id.split("::")
    module = _parse_module(rel_path)
    class_node = _find_class(module, class_name)
    return rel_path, class_name, func_name, module, class_node


def _assert_dumps(func_node: ast.AST) -> list[str]:
    return [ast.dump(node) for node in ast.walk(func_node) if isinstance(node, ast.Assert)]


def _calls_pipeline_sources(func_node: ast.AST, node_id: str) -> bool:
    for node in ast.walk(func_node):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "pipeline_sources"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == node_id
        ):
            return True
    return False


def _string_value(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _dict_score_kind_ok(node: ast.Dict) -> bool:
    """A dict literal carrying a "score" key must also carry a "score_kind" key whose value
    names a member of `score_provenance.SCORE_KINDS` — a re-introduced unlabelled "score"
    (the shape every original's sources literal uses) is a regression.
    """
    pairs = list(zip(node.keys, node.values, strict=True))
    has_score_key = any(_string_value(key) == "score" for key, _ in pairs)
    if not has_score_key:
        return True

    for key, value in pairs:
        if _string_value(key) != "score_kind":
            continue
        literal = _string_value(value)
        if literal is not None:
            return literal in score_provenance.SCORE_KINDS
        attr_name: str | None = None
        if isinstance(value, ast.Attribute):
            attr_name = value.attr
        elif isinstance(value, ast.Name):
            attr_name = value.id
        if attr_name is not None:
            resolved = getattr(score_provenance, attr_name, None)
            return isinstance(resolved, str) and resolved in score_provenance.SCORE_KINDS
        return False
    return False  # has "score" but no "score_kind" key at all


def _first_unlabelled_score_dict_line(func_node: ast.AST) -> int | None:
    for node in ast.walk(func_node):
        if isinstance(node, ast.Dict) and not _dict_score_kind_ok(node):
            return node.lineno
    return None


# ============================================================================
# G1 — every source `pipeline_sources` returns has a valid, non-UNKNOWN
# score_kind and float score/score_raw.
# ============================================================================


@pytest.mark.parametrize("node_id", NODE_IDS)
def test_g1_sources_carry_valid_score_kind_and_float_scores(node_id: str) -> None:
    sources = pipeline_sources(node_id)
    assert sources, f"{node_id}: pipeline_sources returned no sources"
    for source in sources:
        score_kind = source.get("score_kind")
        assert score_kind in score_provenance.SCORE_KINDS, (
            f"{node_id}: score_kind {score_kind!r} is not a member of SCORE_KINDS"
        )
        assert score_kind != score_provenance.UNKNOWN, f"{node_id}: score_kind must not be UNKNOWN"
        assert isinstance(source.get("score_raw"), float), (
            f"{node_id}: score_raw must be a float, got {source.get('score_raw')!r}"
        )
        assert isinstance(source.get("score"), float), (
            f"{node_id}: score must be a float, got {source.get('score')!r}"
        )


# ============================================================================
# G2 — the pinned score/score_kind/score_raw match what the LIVE
# `format_search_results` transform produces from the spec's cosine.
# ============================================================================


@pytest.mark.parametrize("node_id", NODE_IDS)
def test_g2_pinned_values_match_live_formatter(node_id: str) -> None:
    specs = PIPELINE_TRIPWIRE_FIXTURES[node_id]
    for i, spec in enumerate(specs):
        raw_results = {
            "ids": ["probe"],
            "documents": ["probe"],
            "metadatas": [{}],
            "distances": [1 - spec.cosine],
            "scores": [spec.cosine],
        }
        formatted = format_search_results(
            raw_results,
            spec.collection,
            score_kind=spec.score_kind,
        )
        assert len(formatted) == 1, f"{node_id}[{i}]: formatter did not return one result"
        entry = formatted[0]
        assert entry["score"] == spec.score, (
            f"{node_id}[{i}]: pinned score {spec.score!r} != live formatter {entry['score']!r}"
        )
        assert entry["score_kind"] == spec.score_kind, (
            f"{node_id}[{i}]: pinned score_kind {spec.score_kind!r} != "
            f"live formatter {entry['score_kind']!r}"
        )
        assert entry["score_raw"] == spec.cosine, (
            f"{node_id}[{i}]: pinned cosine {spec.cosine!r} != "
            f"live formatter score_raw {entry['score_raw']!r}"
        )


# ============================================================================
# G3 — registry key set is EXACTLY the nine node ids, and each names a
# function that exists (AST) in its original file/class.
# ============================================================================


def test_g3_registry_key_set_is_exactly_the_nine_node_ids() -> None:
    assert set(PIPELINE_TRIPWIRE_FIXTURES.keys()) == set(NODE_IDS)


@pytest.mark.parametrize("node_id", NODE_IDS)
def test_g3_original_function_exists(node_id: str) -> None:
    rel_path, class_name, func_name, _module, class_node = _locate_original(node_id)
    assert class_node is not None, f"{node_id}: class {class_name!r} not found in {rel_path}"
    func_node = _find_function(class_node, func_name)
    assert func_node is not None, (
        f"{node_id}: original function {func_name!r} not found in class "
        f"{class_name!r} of {rel_path}"
    )


# ============================================================================
# G4 — for each original, its `_pipeline_variant` exists in the same class;
# it calls `pipeline_sources("<its node id>")`; and it carries no dict literal
# with an unlabelled "score" key.
# ============================================================================


@pytest.mark.parametrize("node_id", NODE_IDS)
def test_g4_variant_exists_calls_pipeline_sources_and_is_clean(node_id: str) -> None:
    rel_path, class_name, func_name, _module, class_node = _locate_original(node_id)
    assert class_node is not None, f"{node_id}: class {class_name!r} not found in {rel_path}"

    variant_name = f"{func_name}_pipeline_variant"
    variant_node = _find_function(class_node, variant_name)
    assert variant_node is not None, (
        f"{node_id}: variant {variant_name!r} does not exist in class {class_name!r} of {rel_path}"
    )

    assert _calls_pipeline_sources(variant_node, node_id), (
        f"{node_id}: variant {variant_name!r} does not call pipeline_sources({node_id!r})"
    )

    violation_line = _first_unlabelled_score_dict_line(variant_node)
    assert violation_line is None, (
        f"{node_id}: variant {variant_name!r} contains a dict literal with an unlabelled "
        f"'score' key at line {violation_line} — every 'score' key needs a sibling "
        "'score_kind' constant from SCORE_KINDS"
    )


# ============================================================================
# G5 — the variant's `assert` statements equal the original's, in order
# (`ast.dump` comparison).
# ============================================================================


@pytest.mark.parametrize("node_id", NODE_IDS)
def test_g5_variant_asserts_match_original_asserts(node_id: str) -> None:
    rel_path, class_name, func_name, _module, class_node = _locate_original(node_id)
    assert class_node is not None, f"{node_id}: class {class_name!r} not found in {rel_path}"

    original_node = _find_function(class_node, func_name)
    assert original_node is not None, (
        f"{node_id}: original function {func_name!r} not found in class "
        f"{class_name!r} of {rel_path}"
    )

    variant_name = f"{func_name}_pipeline_variant"
    variant_node = _find_function(class_node, variant_name)
    assert variant_node is not None, (
        f"{node_id}: variant {variant_name!r} does not exist — cannot compare "
        "its assert statements to the original's"
    )

    original_asserts = _assert_dumps(original_node)
    variant_asserts = _assert_dumps(variant_node)
    assert variant_asserts == original_asserts, (
        f"{node_id}: assert statements in {variant_name!r} diverge from "
        f"{func_name!r} (ast.dump comparison, in order)"
    )
