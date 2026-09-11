"""Guard for the nine tripwire pipeline variants (B1.2, spec §3, G1-G10).

Purely static/pure-function checks: parses the four original tripwire test files with `ast`
(paths resolved relative to THIS file's own location, never a hardcoded absolute path) and
exercises the pure `pipeline_sources`/`format_search_results` functions. No network, no app
init.

The nine `_pipeline_variant` functions ship in the same PR, each beside its preserved original.
G1-G3 pin the registry (shape, live-transform values, key set, original existence); G4/G5 pin
the variants (existence, their `pipeline_sources(...)` call, no unlabelled score literal, assert
parity with the original). A variant that disappears or a re-introduced unlabelled value is red.

Added in the B1.2 round-1 cure (Codex BLOCK, 5 findings):
  * G6 — whole-body AST parity between a variant and its original (finding 2: G4 only checked
    that a correct call existed SOMEWHERE, so a variant could add extra statements after it).
  * G7 — no duplicate `def` of a protected name in a class body (finding 3a: Python binds the
    LAST same-named definition; `_find_function`'s first-match semantics could inspect a
    definition pytest never runs).
  * G8 — each ORIGINAL pinned against an independent sha256 snapshot of its own AST (finding
    3b: G5 only compared the variant to whatever the original currently says, so weakening
    both identically stayed green).
  * G9 — every registry field pinned against an independent literal EXPECTED table (finding 4:
    G1/G2 only checked score/score_kind/score_raw, leaving rank/collection/fusion/carried_keys
    etc. unpinned).
  * G10 — the registry and `carried_keys` are actually immutable at runtime, and
    `pipeline_sources` still returns fresh, independently-mutable plain dicts (finding 5:
    `frozen=True` alone does not stop `PIPELINE_TRIPWIRE_FIXTURES.clear()` or
    `spec.carried_keys["k"] = 1`).
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
from pathlib import Path
from typing import Any, Final

import pytest

from backend.core import score_provenance
from backend.services.misc.result_formatter import format_search_results
from backend.tests.fixtures.pipeline_score_fixtures import (
    PIPELINE_TRIPWIRE_FIXTURES,
    DenseSourceSpec,
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
# `format_search_results` transform produces from the spec's cosine, AND match
# an independently recomputed `1/(1+(1-cosine))` — three ways to derive the
# same number must agree, not just two.
# ============================================================================


@pytest.mark.parametrize("node_id", NODE_IDS)
def test_g2_pinned_values_match_live_formatter(node_id: str) -> None:
    specs = PIPELINE_TRIPWIRE_FIXTURES[node_id]
    for i, spec in enumerate(specs):
        recomputed = round(1 / (1 + (1 - spec.cosine)), spec.rounding_digits)
        assert recomputed == spec.score, (
            f"{node_id}[{i}]: recomputed transform {recomputed!r} != pinned score {spec.score!r}"
        )

        raw_results = {
            "ids": ["probe"],
            "documents": ["probe"],
            "metadatas": [{}],
            "distances": [1 - spec.cosine],
            "scores": [spec.cosine],
        }
        formatted = format_search_results(
            raw_results,
            spec.formatter_collection,
            score_kind=spec.score_kind,
        )
        assert len(formatted) == 1, f"{node_id}[{i}]: formatter did not return one result"
        entry = formatted[0]
        assert entry["score"] == spec.score == recomputed, (
            f"{node_id}[{i}]: pinned score {spec.score!r} != live formatter {entry['score']!r} "
            f"!= recomputed {recomputed!r}"
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


# ============================================================================
# G6 — whole-body AST parity between a variant and its original.
#
# Finding 2 (Codex round 1): G4 only required that SOME correct
# `pipeline_sources(...)` call exist and that no unlabelled dict literal be
# introduced anywhere in the variant. A variant can satisfy both while adding
# extra statements after the call — e.g. `sources[0].pop("score_kind")` —
# because that statement is neither the call itself nor a dict literal.
#
# G6 normalizes both bodies (docstring dropped from both; the variant's
# `from ... import pipeline_sources` line dropped once; the original's
# all-dicts-with-"score" sources list literal AND the variant's own
# `pipeline_sources("<node id>")` call each replaced by the SAME placeholder
# name) and then requires the two statement lists — and the decorator lists,
# unnormalized — to be identical by `ast.dump`. Anything the variant adds,
# removes or reorders beyond that one substitution goes red.
# ============================================================================

_G6_PLACEHOLDER_ID: Final = "__g6_sources_placeholder__"


def _g6_placeholder() -> ast.Name:
    return ast.Name(id=_G6_PLACEHOLDER_ID, ctx=ast.Load())


def _is_all_dicts_with_score_key(node: ast.List) -> bool:
    if not node.elts:
        return False
    for elt in node.elts:
        if not isinstance(elt, ast.Dict):
            return False
        if not any(_string_value(key) == "score" for key in elt.keys):
            return False
    return True


class _SourcesListReplacer(ast.NodeTransformer):
    """Replace the list literal whose elements are all dicts carrying a "score" key."""

    def __init__(self) -> None:
        self.count = 0

    def visit_List(self, node: ast.List) -> ast.AST:  # noqa: N802 - ast.NodeTransformer API
        self.generic_visit(node)
        if _is_all_dicts_with_score_key(node):
            self.count += 1
            return _g6_placeholder()
        return node


class _PipelineSourcesCallReplacer(ast.NodeTransformer):
    """Replace ONLY a `pipeline_sources("<node_id>")` call with the same placeholder."""

    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        self.count = 0

    def visit_Call(self, node: ast.Call) -> ast.AST:  # noqa: N802 - ast.NodeTransformer API
        self.generic_visit(node)
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "pipeline_sources"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == self.node_id
        ):
            self.count += 1
            return _g6_placeholder()
        return node


def _strip_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        return body[1:]
    return body


def _drop_one_pipeline_sources_import(body: list[ast.stmt]) -> tuple[list[ast.stmt], int]:
    """Drop exactly one `from ...pipeline_score_fixtures import pipeline_sources` line.

    Returns the new body and how many were dropped (0 or 1) — the caller asserts on the
    count so a missing or duplicated import is legible instead of silently skipped.
    """
    result: list[ast.stmt] = []
    dropped = 0
    for stmt in body:
        if (
            not dropped
            and isinstance(stmt, ast.ImportFrom)
            and stmt.module == "backend.tests.fixtures.pipeline_score_fixtures"
            and any(alias.name == "pipeline_sources" for alias in stmt.names)
        ):
            dropped += 1
            continue
        result.append(stmt)
    return result, dropped


@pytest.mark.parametrize("node_id", NODE_IDS)
def test_g6_variant_whole_body_matches_original_except_the_sources_line(node_id: str) -> None:
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
        f"{node_id}: variant {variant_name!r} does not exist — cannot compare its body "
        "to the original's"
    )

    original_decorators = [ast.dump(d) for d in original_node.decorator_list]
    variant_decorators = [ast.dump(d) for d in variant_node.decorator_list]
    assert variant_decorators == original_decorators, (
        f"{node_id}: {variant_name!r} decorators diverge from {func_name!r}"
    )

    original_body = _strip_docstring(original_node.body)
    variant_body = _strip_docstring(variant_node.body)
    variant_body, dropped = _drop_one_pipeline_sources_import(variant_body)
    assert dropped == 1, (
        f"{node_id}: {variant_name!r} must import pipeline_sources exactly once (found {dropped})"
    )

    list_replacer = _SourcesListReplacer()
    original_body = [list_replacer.visit(copy.deepcopy(stmt)) for stmt in original_body]
    assert list_replacer.count == 1, (
        f"{node_id}: original {func_name!r} does not contain exactly one all-dicts-with-"
        f"'score' sources list literal (found {list_replacer.count})"
    )

    call_replacer = _PipelineSourcesCallReplacer(node_id)
    variant_body = [call_replacer.visit(copy.deepcopy(stmt)) for stmt in variant_body]
    assert call_replacer.count == 1, (
        f"{node_id}: variant {variant_name!r} does not contain exactly one "
        f"pipeline_sources({node_id!r}) call (found {call_replacer.count})"
    )

    original_dumps = [ast.dump(stmt) for stmt in original_body]
    variant_dumps = [ast.dump(stmt) for stmt in variant_body]
    assert variant_dumps == original_dumps, (
        f"{node_id}: {variant_name!r} body diverges from {func_name!r} beyond the sources "
        "line — normalized statement lists differ"
    )


# ============================================================================
# G7 — no duplicate `def` of a protected name in a class body.
#
# Finding 3a (Codex round 1): `_find_function` returns the FIRST same-named
# definition in the class body, but Python binds (and pytest collects and
# runs) the LAST one. A weakened definition appended after a valid one passes
# every AST-based check above while pytest actually executes the weak copy.
# ============================================================================


@pytest.mark.parametrize("node_id", NODE_IDS)
def test_g7_no_duplicate_definitions_of_protected_names(node_id: str) -> None:
    rel_path, class_name, func_name, _module, class_node = _locate_original(node_id)
    assert class_node is not None, f"{node_id}: class {class_name!r} not found in {rel_path}"

    variant_name = f"{func_name}_pipeline_variant"
    for protected_name in (func_name, variant_name):
        count = sum(
            1
            for stmt in class_node.body
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
            and stmt.name == protected_name
        )
        assert count == 1, (
            f"{node_id}: class {class_name!r} of {rel_path} defines {protected_name!r} "
            f"{count} times — Python binds the LAST one, so a duplicate can run a "
            "definition this guard never inspects"
        )


# ============================================================================
# G8 — each ORIGINAL function pinned against an independent sha256 snapshot.
#
# Finding 3b (Codex round 1): G5 compares the variant's asserts to whatever
# the original CURRENTLY says — weakening both identically stays green. The
# hashes below were computed once, on the frozen files, by
# `hashlib.sha256(ast.dump(func_node, include_attributes=False).encode()).hexdigest()`
# under the project's `.venv` (Python 3.11) interpreter — independent of
# anything this module re-derives at test time.
# ============================================================================

_ORIGINAL_AST_SHA256: Final[dict[str, str]] = {
    "unit/services/rag/agentic/test_abstain_bypass_policy.py::TestTrustedToolDetection::"
    "test_successful_but_irrelevant_vector_hit_stays_below_abstain_gate": (
        "5eb8384b63b52deb9d5ac2bb070f1f344d4baf19bc7fa7ca9b97d50f71fdb81e"
    ),
    "unit/services/rag/agentic/test_reasoning.py::TestCalculateEvidenceScore::"
    "test_no_keyword_overlap": ("cb2cfcf367aaa5c419aab75db983a3ecf1da8723c2c8bc338e33d22de89d18fb"),
    "services/rag/agentic/test_reasoning_utils.py::TestCalculateEvidenceScore::"
    "test_stop_words_only_query_keyword_ratio_zero": (
        "1837919a07adbfe189a06f41c36c9b0768eab44223e4eb280fd28804a2a0f89a"
    ),
    "services/rag/agentic/test_reasoning_utils.py::TestCalculateEvidenceScore::"
    "test_short_words_only_yields_near_zero": (
        "bfd44e3ebb5a5e611a66a2341b6977c1da82ddd4b69b3bf0c500a74ee0ebf879"
    ),
    "services/rag/agentic/test_reasoning_utils.py::TestCalculateEvidenceScore::"
    "test_entity_mismatch_company_vs_visa": (
        "3b3fe4f71f9732b9c20684d6ac12f391b76caa9fd39d5d2d8f9ba9f328f25fa1"
    ),
    "services/rag/agentic/test_reasoning_utils.py::TestCalculateEvidenceScore::"
    "test_semantic_penalty_not_applied_when_final_score_at_or_below_015": (
        "3fe3a9ab02d55fd6ea09b12e3b00b5d273a6a16863d2a85db4b5785fd1015455"
    ),
    "services/rag/test_evidence_scoring_abstain.py::TestEvidenceScoringFixed::"
    "test_kitas_query_with_kbli_results_low_score": (
        "c79ce8a80f90a2844390f4d989dc7875918160c2e8514e5d4cbe00bfe25b6c60"
    ),
    "services/rag/test_evidence_scoring_abstain.py::TestEvidenceScoringFixed::"
    "test_nonsense_query_zero_score": (
        "448ce2b784edc4b0920e962151f2f182da6a8bc1829df57856d88eaa4503e08e"
    ),
    "services/rag/test_evidence_scoring_abstain.py::TestEvidenceScoringFixed::"
    "test_entity_type_mismatch_detection": (
        "fc369d3fd7d88e162431765a768be8205b6d14da5f37cbc768cbb82b0512324c"
    ),
}


@pytest.mark.parametrize("node_id", NODE_IDS)
def test_g8_original_function_matches_pinned_snapshot(node_id: str) -> None:
    rel_path, class_name, func_name, _module, class_node = _locate_original(node_id)
    assert class_node is not None, f"{node_id}: class {class_name!r} not found in {rel_path}"
    original_node = _find_function(class_node, func_name)
    assert original_node is not None, (
        f"{node_id}: original function {func_name!r} not found in class "
        f"{class_name!r} of {rel_path}"
    )

    digest = hashlib.sha256(
        ast.dump(original_node, include_attributes=False).encode(),
    ).hexdigest()
    expected = _ORIGINAL_AST_SHA256[node_id]
    assert digest == expected, (
        f"{node_id}: original {func_name!r} in {rel_path} no longer matches its pinned "
        f"AST snapshot (got {digest}, expected {expected}) — the frozen original was edited"
    )


# ============================================================================
# G9 — every registry field pinned against an independent literal EXPECTED
# table (finding 4: G1/G2 only checked score/score_kind/score_raw).
#
# All ten specs below share every field except cosine/score/carried_keys/
# unsourced_context_cosines/source_chunk_association — `_G9_SHARED_FIELDS`
# names the shared values once, `_G9_PER_SPEC` re-transcribes the varying
# ones per node id, in registry order, independently of the registry module.
# ============================================================================

_G9_SHARED_FIELDS: Final[dict[str, Any]] = {
    "inventory_row": 2,
    "score_kind": score_provenance.DENSE_FORMATTED,
    "provider": "openai",
    "model": "text-embedding-3-small",
    "measured_at": "2026-09-10T18:03Z",
    "measurement_ref": "rc1a 92f40801235cf33b32a8d71f241b6400cad64536 measured_cosines.py",
    "qdrant_server": None,
    "fallback_path": "search_service dense branch / core/qdrant_db.py:1362 internal fallback",
    "fusion": None,
    "lists": ("dense",),
    "dense_rank0": None,
    "formatter_collection": "kbli_2025_final_hybrid",
    "primary_collection": None,
    "boosts": (),
    "transform": "distance = 1 - cosine; score = 1/(1+distance)",
    "rounding_digits": 4,
    "simulated": ("formatter_collection", "lists", "fallback_path"),
}

_G9_PER_SPEC: Final[dict[str, tuple[dict[str, Any], ...]]] = {
    NODE_IDS[0]: (
        {
            "cosine": 0.16,
            "score": 0.5435,
            "carried_keys": {},
            "unsourced_context_cosines": (),
            "source_chunk_association": None,
        },
    ),
    NODE_IDS[1]: (
        {
            "cosine": 0.04,
            "score": 0.5102,
            "carried_keys": {},
            "unsourced_context_cosines": (),
            "source_chunk_association": None,
        },
    ),
    NODE_IDS[2]: (
        {
            "cosine": 0.14,
            "score": 0.5376,
            "carried_keys": {},
            "unsourced_context_cosines": (),
            "source_chunk_association": None,
        },
    ),
    NODE_IDS[3]: (
        {
            "cosine": 0.16,
            "score": 0.5435,
            "carried_keys": {},
            "unsourced_context_cosines": (),
            "source_chunk_association": None,
        },
    ),
    NODE_IDS[4]: (
        {
            "cosine": 0.30,
            "score": 0.5882,
            "carried_keys": {},
            "unsourced_context_cosines": (),
            "source_chunk_association": None,
        },
    ),
    NODE_IDS[5]: (
        {
            "cosine": 0.20,
            "score": 0.5556,
            "carried_keys": {},
            "unsourced_context_cosines": (),
            "source_chunk_association": None,
        },
    ),
    NODE_IDS[6]: (
        {
            "cosine": 0.35,
            "score": 0.6061,
            "carried_keys": {"id": 1, "title": "KBLI 2025"},
            "unsourced_context_cosines": (),
            "source_chunk_association": None,
        },
        {
            "cosine": 0.51,
            "score": 0.6711,
            "carried_keys": {"id": 2, "title": "Business Classification"},
            "unsourced_context_cosines": (),
            "source_chunk_association": None,
        },
    ),
    NODE_IDS[7]: (
        {
            "cosine": 0.22,
            "score": 0.5618,
            "carried_keys": {"id": 1, "title": "Random Doc"},
            "unsourced_context_cosines": (),
            "source_chunk_association": None,
        },
    ),
    NODE_IDS[8]: (
        {
            "cosine": 0.40,
            "score": 0.625,
            "carried_keys": {"id": 1},
            "unsourced_context_cosines": (0.32,),
            "source_chunk_association": (
                "unresolved — the single source carries the max of the two measured "
                "chunk cosines (0.40); the other is unsourced_context_cosines"
            ),
        },
    ),
}


def _spec_field_map(spec: DenseSourceSpec) -> dict[str, Any]:
    """A shallow field-name -> value map for `spec`.

    Deliberately NOT `dataclasses.asdict(spec)`: that function's fallback for a field type
    it doesn't special-case is `copy.deepcopy`, which raises
    `TypeError: cannot pickle 'mappingproxy' object` on `carried_keys` now that G10/finding
    5 makes it a `MappingProxyType` (verified empirically against this project's `.venv`
    interpreter). None of `DenseSourceSpec`'s fields nest another dataclass, so a shallow
    map is comparison-equivalent to what a non-crashing `asdict` would have produced.
    """
    return {f.name: getattr(spec, f.name) for f in dataclasses.fields(spec)}


def test_g9_every_field_is_pinned_against_an_independent_expected_table() -> None:
    for node_id in NODE_IDS:
        specs = PIPELINE_TRIPWIRE_FIXTURES[node_id]
        expected_rows = _G9_PER_SPEC[node_id]
        assert len(specs) == len(expected_rows), (
            f"{node_id}: registry has {len(specs)} spec(s), EXPECTED table has {len(expected_rows)}"
        )
        for i, (spec, expected_row) in enumerate(zip(specs, expected_rows, strict=True)):
            actual = _spec_field_map(spec)
            expected = {**_G9_SHARED_FIELDS, **expected_row}
            assert set(actual) == set(expected), (
                f"{node_id}[{i}]: dataclass field set {sorted(actual)} != "
                f"EXPECTED field set {sorted(expected)}"
            )
            for field_name, expected_value in expected.items():
                actual_value = actual[field_name]
                if field_name == "carried_keys":
                    assert dict(actual_value) == expected_value, (
                        f"{node_id}[{i}].carried_keys: {dict(actual_value)!r} != {expected_value!r}"
                    )
                else:
                    assert actual_value == expected_value, (
                        f"{node_id}[{i}].{field_name}: {actual_value!r} != {expected_value!r}"
                    )


# ============================================================================
# G10 — the registry and `carried_keys` are actually immutable at runtime;
# `pipeline_sources` still returns fresh, independently-mutable plain dicts.
# ============================================================================


def test_g10_registry_is_immutable() -> None:
    with pytest.raises(TypeError):
        PIPELINE_TRIPWIRE_FIXTURES["x"] = ()  # type: ignore[index]


def test_g10_carried_keys_is_immutable() -> None:
    spec = PIPELINE_TRIPWIRE_FIXTURES[NODE_IDS[6]][0]
    with pytest.raises(TypeError):
        spec.carried_keys["k"] = 1  # type: ignore[index]


def test_g10_pipeline_sources_still_returns_fresh_mutable_dicts() -> None:
    first_call = pipeline_sources(NODE_IDS[6])
    second_call = pipeline_sources(NODE_IDS[6])
    first_call[0]["mutated"] = True
    assert "mutated" not in second_call[0], (
        "pipeline_sources must return a fresh dict per call — mutating one call's "
        "result leaked into another"
    )
