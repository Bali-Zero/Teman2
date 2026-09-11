"""Registry of dense-path score fixtures for the nine tripwire pipeline variants (B1.2).

Every value below is MEASURED, not invented: the one real number that exists for each
(query, context) pair is rc1a's `text-embedding-3-small` cosine, taken from a single prod
Qdrant read-only probe (`rag` container, 2026-09-10T18:03Z, 20 texts, 216 prompt tokens;
`measurement_ref` on each spec names the commit and script). No hybrid-path rank was ever
measured for these texts, so every variant here declares the DENSE path
(`score_provenance.DENSE_FORMATTED`) and nothing else — a `score_kind` is always DECLARED
by the writer that mints it, never inferred from the number's magnitude (`core/score_provenance.py`).

The originals these variants sit beside are PRESERVED byte-for-byte (D3/D5): this module only
supplies the replacement sources literal, `pipeline_sources(node_id)`, so a variant's diff
against its original is the sources line and nothing else.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from backend.core import score_provenance


@dataclass(frozen=True)
class DenseSourceSpec:
    """One measured dense-path source, pinned to the live `format_search_results` transform.

    Every field is explicit per B1.1 decision D3: a kind is declared, never inferred, and
    nothing here is a default standing in for a measurement that was never taken.
    """

    inventory_row: int
    score_kind: str
    provider: str
    model: str
    measured_at: str
    measurement_ref: str
    qdrant_server: str
    fallback_path: str
    fusion: None
    lists: tuple[str, ...]
    dense_rank0: int
    cosine: float
    collection: str
    primary_collection: None
    boosts: tuple[str, ...]
    transform: str
    rounding_digits: int
    score: float
    carried_keys: Mapping[str, Any]
    unsourced_context_cosines: tuple[float, ...]


#: Common provenance shared by every spec below — pinned once so nine call sites don't drift.
_MEASUREMENT_REF: Final = "rc1a 92f40801235cf33b32a8d71f241b6400cad64536 measured_cosines.py"
_MEASURED_AT: Final = "2026-09-10T18:03Z"
_QDRANT_SERVER: Final = "1.16.3"
_FALLBACK_PATH: Final = "search_service dense branch / core/qdrant_db.py:1362 internal fallback"
_COLLECTION: Final = "kbli_2025_final_hybrid"
_TRANSFORM: Final = "distance = 1 - cosine; score = 1/(1+distance)"


PIPELINE_TRIPWIRE_FIXTURES: Final[Mapping[str, tuple[DenseSourceSpec, ...]]] = {
    # Row 1
    "unit/services/rag/agentic/test_abstain_bypass_policy.py::TestTrustedToolDetection::"
    "test_successful_but_irrelevant_vector_hit_stays_below_abstain_gate": (
        DenseSourceSpec(
            inventory_row=2,
            score_kind=score_provenance.DENSE_FORMATTED,
            provider="openai",
            model="text-embedding-3-small",
            measured_at=_MEASURED_AT,
            measurement_ref=_MEASUREMENT_REF,
            qdrant_server=_QDRANT_SERVER,
            fallback_path=_FALLBACK_PATH,
            fusion=None,
            lists=("dense",),
            dense_rank0=0,
            cosine=0.16,
            collection=_COLLECTION,
            primary_collection=None,
            boosts=(),
            transform=_TRANSFORM,
            rounding_digits=4,
            score=0.5435,
            carried_keys={},
            unsourced_context_cosines=(),
        ),
    ),
    # Row 2
    "unit/services/rag/agentic/test_reasoning.py::TestCalculateEvidenceScore::"
    "test_no_keyword_overlap": (
        DenseSourceSpec(
            inventory_row=2,
            score_kind=score_provenance.DENSE_FORMATTED,
            provider="openai",
            model="text-embedding-3-small",
            measured_at=_MEASURED_AT,
            measurement_ref=_MEASUREMENT_REF,
            qdrant_server=_QDRANT_SERVER,
            fallback_path=_FALLBACK_PATH,
            fusion=None,
            lists=("dense",),
            dense_rank0=0,
            cosine=0.04,
            collection=_COLLECTION,
            primary_collection=None,
            boosts=(),
            transform=_TRANSFORM,
            rounding_digits=4,
            score=0.5102,
            carried_keys={},
            unsourced_context_cosines=(),
        ),
    ),
    # Row 3
    "services/rag/agentic/test_reasoning_utils.py::TestCalculateEvidenceScore::"
    "test_stop_words_only_query_keyword_ratio_zero": (
        DenseSourceSpec(
            inventory_row=2,
            score_kind=score_provenance.DENSE_FORMATTED,
            provider="openai",
            model="text-embedding-3-small",
            measured_at=_MEASURED_AT,
            measurement_ref=_MEASUREMENT_REF,
            qdrant_server=_QDRANT_SERVER,
            fallback_path=_FALLBACK_PATH,
            fusion=None,
            lists=("dense",),
            dense_rank0=0,
            cosine=0.14,
            collection=_COLLECTION,
            primary_collection=None,
            boosts=(),
            transform=_TRANSFORM,
            rounding_digits=4,
            score=0.5376,
            carried_keys={},
            unsourced_context_cosines=(),
        ),
    ),
    # Row 4
    "services/rag/agentic/test_reasoning_utils.py::TestCalculateEvidenceScore::"
    "test_short_words_only_yields_near_zero": (
        DenseSourceSpec(
            inventory_row=2,
            score_kind=score_provenance.DENSE_FORMATTED,
            provider="openai",
            model="text-embedding-3-small",
            measured_at=_MEASURED_AT,
            measurement_ref=_MEASUREMENT_REF,
            qdrant_server=_QDRANT_SERVER,
            fallback_path=_FALLBACK_PATH,
            fusion=None,
            lists=("dense",),
            dense_rank0=0,
            cosine=0.16,
            collection=_COLLECTION,
            primary_collection=None,
            boosts=(),
            transform=_TRANSFORM,
            rounding_digits=4,
            score=0.5435,
            carried_keys={},
            unsourced_context_cosines=(),
        ),
    ),
    # Row 5
    "services/rag/agentic/test_reasoning_utils.py::TestCalculateEvidenceScore::"
    "test_entity_mismatch_company_vs_visa": (
        DenseSourceSpec(
            inventory_row=2,
            score_kind=score_provenance.DENSE_FORMATTED,
            provider="openai",
            model="text-embedding-3-small",
            measured_at=_MEASURED_AT,
            measurement_ref=_MEASUREMENT_REF,
            qdrant_server=_QDRANT_SERVER,
            fallback_path=_FALLBACK_PATH,
            fusion=None,
            lists=("dense",),
            dense_rank0=0,
            cosine=0.30,
            collection=_COLLECTION,
            primary_collection=None,
            boosts=(),
            transform=_TRANSFORM,
            rounding_digits=4,
            score=0.5882,
            carried_keys={},
            unsourced_context_cosines=(),
        ),
    ),
    # Row 6
    "services/rag/agentic/test_reasoning_utils.py::TestCalculateEvidenceScore::"
    "test_semantic_penalty_not_applied_when_final_score_at_or_below_015": (
        DenseSourceSpec(
            inventory_row=2,
            score_kind=score_provenance.DENSE_FORMATTED,
            provider="openai",
            model="text-embedding-3-small",
            measured_at=_MEASURED_AT,
            measurement_ref=_MEASUREMENT_REF,
            qdrant_server=_QDRANT_SERVER,
            fallback_path=_FALLBACK_PATH,
            fusion=None,
            lists=("dense",),
            dense_rank0=0,
            cosine=0.20,
            collection=_COLLECTION,
            primary_collection=None,
            boosts=(),
            transform=_TRANSFORM,
            rounding_digits=4,
            score=0.5556,
            carried_keys={},
            unsourced_context_cosines=(),
        ),
    ),
    # Row 7 — two sources, original order (id 1 then id 2); ranks per the spec table.
    "services/rag/test_evidence_scoring_abstain.py::TestEvidenceScoringFixed::"
    "test_kitas_query_with_kbli_results_low_score": (
        DenseSourceSpec(
            inventory_row=2,
            score_kind=score_provenance.DENSE_FORMATTED,
            provider="openai",
            model="text-embedding-3-small",
            measured_at=_MEASURED_AT,
            measurement_ref=_MEASUREMENT_REF,
            qdrant_server=_QDRANT_SERVER,
            fallback_path=_FALLBACK_PATH,
            fusion=None,
            lists=("dense",),
            dense_rank0=1,
            cosine=0.35,
            collection=_COLLECTION,
            primary_collection=None,
            boosts=(),
            transform=_TRANSFORM,
            rounding_digits=4,
            score=0.6061,
            carried_keys={"id": 1, "title": "KBLI 2025"},
            unsourced_context_cosines=(),
        ),
        DenseSourceSpec(
            inventory_row=2,
            score_kind=score_provenance.DENSE_FORMATTED,
            provider="openai",
            model="text-embedding-3-small",
            measured_at=_MEASURED_AT,
            measurement_ref=_MEASUREMENT_REF,
            qdrant_server=_QDRANT_SERVER,
            fallback_path=_FALLBACK_PATH,
            fusion=None,
            lists=("dense",),
            dense_rank0=0,
            cosine=0.51,
            collection=_COLLECTION,
            primary_collection=None,
            boosts=(),
            transform=_TRANSFORM,
            rounding_digits=4,
            score=0.6711,
            carried_keys={"id": 2, "title": "Business Classification"},
            unsourced_context_cosines=(),
        ),
    ),
    # Row 8
    "services/rag/test_evidence_scoring_abstain.py::TestEvidenceScoringFixed::"
    "test_nonsense_query_zero_score": (
        DenseSourceSpec(
            inventory_row=2,
            score_kind=score_provenance.DENSE_FORMATTED,
            provider="openai",
            model="text-embedding-3-small",
            measured_at=_MEASURED_AT,
            measurement_ref=_MEASUREMENT_REF,
            qdrant_server=_QDRANT_SERVER,
            fallback_path=_FALLBACK_PATH,
            fusion=None,
            lists=("dense",),
            dense_rank0=0,
            cosine=0.22,
            collection=_COLLECTION,
            primary_collection=None,
            boosts=(),
            transform=_TRANSFORM,
            rounding_digits=4,
            score=0.5618,
            carried_keys={"id": 1, "title": "Random Doc"},
            unsourced_context_cosines=(),
        ),
    ),
    # Row 9 — single source: the top dense hit (max of the two measured chunk cosines); the
    # other chunk's cosine is carried separately as `unsourced_context_cosines`.
    "services/rag/test_evidence_scoring_abstain.py::TestEvidenceScoringFixed::"
    "test_entity_type_mismatch_detection": (
        DenseSourceSpec(
            inventory_row=2,
            score_kind=score_provenance.DENSE_FORMATTED,
            provider="openai",
            model="text-embedding-3-small",
            measured_at=_MEASURED_AT,
            measurement_ref=_MEASUREMENT_REF,
            qdrant_server=_QDRANT_SERVER,
            fallback_path=_FALLBACK_PATH,
            fusion=None,
            lists=("dense",),
            dense_rank0=0,
            cosine=0.40,
            collection=_COLLECTION,
            primary_collection=None,
            boosts=(),
            transform=_TRANSFORM,
            rounding_digits=4,
            score=0.625,
            carried_keys={"id": 1},
            unsourced_context_cosines=(0.32,),
        ),
    ),
}


def pipeline_sources(node_id: str) -> list[dict[str, Any]]:
    """Return a FRESH list of formatted-style source dicts for `node_id`.

    Each dict is `{**carried_keys, "score": score, "score_kind": score_kind, "score_raw":
    cosine}`, in the original list order. A new list and new dicts are built on every call, so
    a caller mutating its result never leaks into the registry or into another caller.

    Raises `KeyError` naming this registry on an unknown id — never a silent default.
    """
    try:
        specs = PIPELINE_TRIPWIRE_FIXTURES[node_id]
    except KeyError:
        raise KeyError(
            f"{node_id!r} is not registered in "
            "backend.tests.fixtures.pipeline_score_fixtures.PIPELINE_TRIPWIRE_FIXTURES",
        ) from None

    return [
        {
            **spec.carried_keys,
            "score": spec.score,
            "score_kind": spec.score_kind,
            "score_raw": spec.cosine,
        }
        for spec in specs
    ]
