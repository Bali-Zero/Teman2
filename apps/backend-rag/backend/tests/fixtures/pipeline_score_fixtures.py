"""Registry of dense-path score fixtures for the nine tripwire pipeline variants (B1.2).

Only the COSINE on each spec is a measurement: rc1a's `text-embedding-3-small` cosine for
one (query, context) pair, taken from a single prod Qdrant read-only probe (`rag`
container, 2026-09-10T18:03Z, 20 texts, 216 prompt tokens; `measurement_ref` names the
commit and script that took it). `score` is the REAL transform of that cosine through
`format_search_results` — also a real computation, not a guess — and `score_kind` is
DECLARED by the writer that mints it, never inferred from the number's magnitude
(`core/score_provenance.py`).

Everything else on a spec is a declared SIMULATION INPUT handed to
`format_search_results` to reproduce that transform, not an observed retrieval fact —
`simulated` names those fields per spec (`formatter_collection`, `lists`, `fallback_path`
at minimum). No hybrid-path rank, list membership or fusion configuration was ever
measured for these (query, context) texts: the (query, context) measurement this
registry rests on cannot express any of the three
(`evidence/2026-09/agent-nuzantara-backend-rag-b1-score-contract-107e45b6/B1-2-inventory.md:95-109`),
so `dense_rank0` and `qdrant_server` are `None` on every spec rather than an invented
value standing in for a measurement that was never taken. Row 9's single source is
likewise an association the writer chose, not an observation — see its own
`source_chunk_association`.

The originals these variants sit beside are PRESERVED byte-for-byte (D3/D5): this module
only supplies the replacement sources literal, `pipeline_sources(node_id)`, so a variant's
diff against its original is the sources line and nothing else.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

from backend.core import score_provenance


@dataclass(frozen=True)
class DenseSourceSpec:
    """One dense-path source: a measured cosine, a real transform, and declared inputs.

    Per B1.1 decision D3, a kind is declared, never inferred, and nothing here stands in
    for a measurement that was never taken: `cosine` is the one measured number; `score`
    is what the live formatter computes from it; every field named in `simulated` is a
    declared input to that computation, not an observed retrieval fact; `dense_rank0` and
    `qdrant_server` are `None` because no rank or server receipt was ever measured for
    these texts. `carried_keys` is frozen into a `MappingProxyType` in `__post_init__` so
    a caller cannot mutate the registry's own source dicts (B1.2 round-1 finding 5).
    """

    inventory_row: int
    score_kind: str
    provider: str
    model: str
    measured_at: str
    measurement_ref: str
    #: No receipt was ever observed for these texts — declared `None`, never invented.
    qdrant_server: str | None
    fallback_path: str
    fusion: None
    lists: tuple[str, ...]
    #: No rank was ever measured for these texts (B1-2-inventory.md:95-109) — declared
    #: `None`, never invented.
    dense_rank0: int | None
    cosine: float
    #: Simulation input to `format_search_results` that selects no boost (matches
    #: neither `bali_zero_pricing_hybrid` nor `bali_zero_team`) — NOT an observed
    #: retrieval collection.
    formatter_collection: str
    primary_collection: None
    boosts: tuple[str, ...]
    transform: str
    rounding_digits: int
    score: float
    carried_keys: Mapping[str, Any]
    unsourced_context_cosines: tuple[float, ...]
    #: Every field on this spec whose value is a declared simulation input rather than an
    #: observed retrieval fact — at least `formatter_collection`, `lists`, `fallback_path`.
    simulated: tuple[str, ...]
    #: `None` unless the single source's association with its context chunk is itself
    #: unresolved (row 9) — see that spec's own value for what "unresolved" means here.
    source_chunk_association: str | None

    def __post_init__(self) -> None:
        """Freeze `carried_keys` into a `MappingProxyType`.

        Every call site below still passes a plain dict literal; this is the one place
        that turns it immutable. `object.__setattr__` is required because the dataclass
        itself is frozen.
        """
        object.__setattr__(self, "carried_keys", MappingProxyType(dict(self.carried_keys)))


#: Common provenance shared by every spec below — pinned once so nine call sites don't drift.
_MEASUREMENT_REF: Final = "rc1a 92f40801235cf33b32a8d71f241b6400cad64536 measured_cosines.py"
_MEASURED_AT: Final = "2026-09-10T18:03Z"
_FALLBACK_PATH: Final = "search_service dense branch / core/qdrant_db.py:1362 internal fallback"
_FORMATTER_COLLECTION: Final = "kbli_2025_final_hybrid"
_TRANSFORM: Final = "distance = 1 - cosine; score = 1/(1+distance)"
#: Fields whose value on every spec below is a declared simulation input, not an observed
#: retrieval fact (finding 1) — shared because every spec below declares the same three.
_SIMULATED_FIELDS: Final[tuple[str, ...]] = ("formatter_collection", "lists", "fallback_path")


PIPELINE_TRIPWIRE_FIXTURES: Final[Mapping[str, tuple[DenseSourceSpec, ...]]] = MappingProxyType(
    {
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
                qdrant_server=None,
                fallback_path=_FALLBACK_PATH,
                fusion=None,
                lists=("dense",),
                dense_rank0=None,
                cosine=0.16,
                formatter_collection=_FORMATTER_COLLECTION,
                primary_collection=None,
                boosts=(),
                transform=_TRANSFORM,
                rounding_digits=4,
                score=0.5435,
                carried_keys={},
                unsourced_context_cosines=(),
                simulated=_SIMULATED_FIELDS,
                source_chunk_association=None,
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
                qdrant_server=None,
                fallback_path=_FALLBACK_PATH,
                fusion=None,
                lists=("dense",),
                dense_rank0=None,
                cosine=0.04,
                formatter_collection=_FORMATTER_COLLECTION,
                primary_collection=None,
                boosts=(),
                transform=_TRANSFORM,
                rounding_digits=4,
                score=0.5102,
                carried_keys={},
                unsourced_context_cosines=(),
                simulated=_SIMULATED_FIELDS,
                source_chunk_association=None,
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
                qdrant_server=None,
                fallback_path=_FALLBACK_PATH,
                fusion=None,
                lists=("dense",),
                dense_rank0=None,
                cosine=0.14,
                formatter_collection=_FORMATTER_COLLECTION,
                primary_collection=None,
                boosts=(),
                transform=_TRANSFORM,
                rounding_digits=4,
                score=0.5376,
                carried_keys={},
                unsourced_context_cosines=(),
                simulated=_SIMULATED_FIELDS,
                source_chunk_association=None,
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
                qdrant_server=None,
                fallback_path=_FALLBACK_PATH,
                fusion=None,
                lists=("dense",),
                dense_rank0=None,
                cosine=0.16,
                formatter_collection=_FORMATTER_COLLECTION,
                primary_collection=None,
                boosts=(),
                transform=_TRANSFORM,
                rounding_digits=4,
                score=0.5435,
                carried_keys={},
                unsourced_context_cosines=(),
                simulated=_SIMULATED_FIELDS,
                source_chunk_association=None,
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
                qdrant_server=None,
                fallback_path=_FALLBACK_PATH,
                fusion=None,
                lists=("dense",),
                dense_rank0=None,
                cosine=0.30,
                formatter_collection=_FORMATTER_COLLECTION,
                primary_collection=None,
                boosts=(),
                transform=_TRANSFORM,
                rounding_digits=4,
                score=0.5882,
                carried_keys={},
                unsourced_context_cosines=(),
                simulated=_SIMULATED_FIELDS,
                source_chunk_association=None,
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
                qdrant_server=None,
                fallback_path=_FALLBACK_PATH,
                fusion=None,
                lists=("dense",),
                dense_rank0=None,
                cosine=0.20,
                formatter_collection=_FORMATTER_COLLECTION,
                primary_collection=None,
                boosts=(),
                transform=_TRANSFORM,
                rounding_digits=4,
                score=0.5556,
                carried_keys={},
                unsourced_context_cosines=(),
                simulated=_SIMULATED_FIELDS,
                source_chunk_association=None,
            ),
        ),
        # Row 7 — two sources, original order (id 1 then id 2); ranks unmeasured for both.
        "services/rag/test_evidence_scoring_abstain.py::TestEvidenceScoringFixed::"
        "test_kitas_query_with_kbli_results_low_score": (
            DenseSourceSpec(
                inventory_row=2,
                score_kind=score_provenance.DENSE_FORMATTED,
                provider="openai",
                model="text-embedding-3-small",
                measured_at=_MEASURED_AT,
                measurement_ref=_MEASUREMENT_REF,
                qdrant_server=None,
                fallback_path=_FALLBACK_PATH,
                fusion=None,
                lists=("dense",),
                dense_rank0=None,
                cosine=0.35,
                formatter_collection=_FORMATTER_COLLECTION,
                primary_collection=None,
                boosts=(),
                transform=_TRANSFORM,
                rounding_digits=4,
                score=0.6061,
                carried_keys={"id": 1, "title": "KBLI 2025"},
                unsourced_context_cosines=(),
                simulated=_SIMULATED_FIELDS,
                source_chunk_association=None,
            ),
            DenseSourceSpec(
                inventory_row=2,
                score_kind=score_provenance.DENSE_FORMATTED,
                provider="openai",
                model="text-embedding-3-small",
                measured_at=_MEASURED_AT,
                measurement_ref=_MEASUREMENT_REF,
                qdrant_server=None,
                fallback_path=_FALLBACK_PATH,
                fusion=None,
                lists=("dense",),
                dense_rank0=None,
                cosine=0.51,
                formatter_collection=_FORMATTER_COLLECTION,
                primary_collection=None,
                boosts=(),
                transform=_TRANSFORM,
                rounding_digits=4,
                score=0.6711,
                carried_keys={"id": 2, "title": "Business Classification"},
                unsourced_context_cosines=(),
                simulated=_SIMULATED_FIELDS,
                source_chunk_association=None,
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
                qdrant_server=None,
                fallback_path=_FALLBACK_PATH,
                fusion=None,
                lists=("dense",),
                dense_rank0=None,
                cosine=0.22,
                formatter_collection=_FORMATTER_COLLECTION,
                primary_collection=None,
                boosts=(),
                transform=_TRANSFORM,
                rounding_digits=4,
                score=0.5618,
                carried_keys={"id": 1, "title": "Random Doc"},
                unsourced_context_cosines=(),
                simulated=_SIMULATED_FIELDS,
                source_chunk_association=None,
            ),
        ),
        # Row 9 — single source: the top dense hit (max of the two measured chunk cosines); the
        # other chunk's cosine is carried separately as `unsourced_context_cosines`. Which chunk
        # the single source "is" was never observed — that association is itself unresolved.
        "services/rag/test_evidence_scoring_abstain.py::TestEvidenceScoringFixed::"
        "test_entity_type_mismatch_detection": (
            DenseSourceSpec(
                inventory_row=2,
                score_kind=score_provenance.DENSE_FORMATTED,
                provider="openai",
                model="text-embedding-3-small",
                measured_at=_MEASURED_AT,
                measurement_ref=_MEASUREMENT_REF,
                qdrant_server=None,
                fallback_path=_FALLBACK_PATH,
                fusion=None,
                lists=("dense",),
                dense_rank0=None,
                cosine=0.40,
                formatter_collection=_FORMATTER_COLLECTION,
                primary_collection=None,
                boosts=(),
                transform=_TRANSFORM,
                rounding_digits=4,
                score=0.625,
                carried_keys={"id": 1},
                unsourced_context_cosines=(0.32,),
                simulated=_SIMULATED_FIELDS,
                source_chunk_association=(
                    "unresolved — the single source carries the max of the two measured "
                    "chunk cosines (0.40); the other is unsourced_context_cosines"
                ),
            ),
        ),
    },
)


def pipeline_sources(node_id: str) -> list[dict[str, Any]]:
    """Return a FRESH list of formatted-style source dicts for `node_id`.

    Each dict is `{**carried_keys, "score": score, "score_kind": score_kind, "score_raw":
    cosine}`, in the original list order. A new list and new plain dicts are built on
    every call — `carried_keys` is a `MappingProxyType` on the spec, but `**`-unpacking it
    here always yields a fresh mutable `dict` — so a caller mutating its result never
    leaks into the registry or into another caller.

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
