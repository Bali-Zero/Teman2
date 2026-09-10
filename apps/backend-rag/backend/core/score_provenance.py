"""The score contract: what the number a source carries IS, and where it came from.

B1.1. Every `score` that can reach `calculate_evidence_score` is produced by one of a
small number of writers, and until this module existed none of them said which. The
scorer's own comment (`services/rag/agentic/reasoning_utils.py:650`) calls the field
"Qdrant's per-source cosine similarity"; on the hybrid path it is a Reciprocal Rank
Fusion output put through `1/(1+distance)`, which is a ranking transform and not a
cosine. This module names the difference so a consumer can read it instead of guessing.

MEASURED, not assumed (prod Qdrant 1.16.3, read-only probe, base sha 1d726045c9 —
`evidence/2026-09/agent-nuzantara-backend-rag-b1-score-contract-107e45b6/measured-fusion-table.md`):
server-side RRF returns `sum over contributing lists of 1/(2 + rank0)`, zero-based, ranking
constant 2 — exact on all ten measured rows, with the k=60/1-based alternative refuted on
all ten. With the production `prefetch_limit = limit * 3`, that is bounded below by 1/31,
so `result_formatter.format_search_results` maps every hybrid result into [0.508, 1.000]
before any collection boost, and the dense fallback into [0.5, 1.000] for any non-negative
cosine. Consequences a reader needs before touching a threshold:

  * a `hybrid_rrf_formatted` value near 0.5 means "last of a long list", NOT "half similar";
  * `reasoning_utils.py:665`'s `0 < top < 0.5` guard cannot be entered from any live path;
  * two of these kinds carry no retrieval behind them at all (`curated_synthetic`,
    `trusted_tool_bypass`), so comparing them numerically to a retrieved value is
    comparing a label with a measurement.

TWO RULES, and they are the point of the module:

1.  A kind is DECLARED by the writer that mints the value. It is NEVER inferred from the
    number's magnitude — magnitudes overlap across kinds by construction (a rank-1-in-both
    fusion hit and a curated block both arrive at 1.0), so any inference is a coin flip
    wearing a heuristic's clothes.
2.  A value whose writer did not declare a kind is `UNKNOWN`, and `UNKNOWN` is a fact about
    our knowledge, not a low grade. A legacy cache entry written before this module existed
    is `UNKNOWN`; so is anything reconstructed from a projection that dropped the key.
"""

from __future__ import annotations

from typing import Any, Final

#: The key a source/chunk dict carries its declared kind under.
SCORE_KIND_KEY: Final = "score_kind"

#: The key a source/chunk dict carries its pre-transform value under. Definition, and it
#: is deliberately narrow: `score_raw` is the number THIS writer consumed to produce
#: `score`. It is `None` when the value is synthetic (nothing was consumed) or when the
#: producing step is not recoverable. It is never a second opinion about `score`.
SCORE_RAW_KEY: Final = "score_raw"

#: Server-side Reciprocal Rank Fusion (`core/qdrant_db.py:1308`) put through
#: `result_formatter.py:89`. `score_raw` is the fusion output, in (0, 2].
HYBRID_RRF_FORMATTED: Final = "hybrid_rrf_formatted"

#: A dense-only cosine put through the same formatter — either the explicit dense branch
#: of `search_service` or the internal fallback at `core/qdrant_db.py:1362`. `score_raw`
#: is the cosine.
DENSE_FORMATTED: Final = "dense_formatted"

#: A reranker overwrote `score` with its own relevance score (`core/reranker.py:169-180`,
#: `services/rag/reranker.py:345-352`). `score_raw` is the value it replaced, which those
#: writers also keep under `vector_score`.
RERANKED: Final = "reranked"

#: The curated-QA block minted at a literal 1.0 by `wa_package_builder.py:529`. Nothing was
#: retrieved and nothing was scored, so `score_raw` is `None`.
CURATED_SYNTHETIC: Final = "curated_synthetic"

#: A knowledge-graph entity source from the KG fast path. Not a similarity.
KG_ENTITY: Final = "kg_entity"

#: The flat `EVIDENCE_SCORE_TRUSTED_TOOL` (`_reasoning_evidence.py:40`). This is a
#: whole-package label rather than a per-source score, and it bypasses the ordinary
#: scorer entirely; it is named here so the bypass is legible in the same vocabulary.
TRUSTED_TOOL_BYPASS: Final = "trusted_tool_bypass"

#: No writer declared a kind. Legacy cache entries and values that survived a projection
#: which dropped the key land here. Never a synonym for "bad".
UNKNOWN: Final = "unknown"

SCORE_KINDS: Final[frozenset[str]] = frozenset(
    {
        HYBRID_RRF_FORMATTED,
        DENSE_FORMATTED,
        RERANKED,
        CURATED_SYNTHETIC,
        KG_ENTITY,
        TRUSTED_TOOL_BYPASS,
        UNKNOWN,
    },
)

#: The kinds that have real retrieval behind them, so a numeric comparison between two of
#: them means something. `CURATED_SYNTHETIC` and `TRUSTED_TOOL_BYPASS` are deliberately
#: absent: they are labels, not measurements.
RETRIEVED_KINDS: Final[frozenset[str]] = frozenset(
    {HYBRID_RRF_FORMATTED, DENSE_FORMATTED, RERANKED},
)


def kind_of(source: Any) -> str:
    """Read a source's declared kind, defaulting to `UNKNOWN`.

    Accepts anything, because the projections this travels through are typed `list[Any]`
    and a non-dict source has, by definition, declared nothing.
    """
    if not isinstance(source, dict):
        return UNKNOWN
    kind = source.get(SCORE_KIND_KEY)
    return kind if kind in SCORE_KINDS else UNKNOWN


def raw_of(source: Any) -> float | None:
    """Read a source's pre-transform value, or `None` when it has none or is unreadable."""
    if not isinstance(source, dict):
        return None
    raw = source.get(SCORE_RAW_KEY)
    return float(raw) if isinstance(raw, (int, float)) else None


def stamp(
    target: dict[str, Any],
    kind: str,
    raw: float | None = None,
) -> dict[str, Any]:
    """Declare a kind on a dict IN PLACE, additively, and return it.

    Raises on an unknown kind: a writer that invents a spelling is a writer whose value the
    consumers cannot read, and failing at the mint is cheaper than an `UNKNOWN` appearing
    three layers downstream with nothing to trace it to.
    """
    if kind not in SCORE_KINDS:
        raise ValueError(
            f"unknown score_kind {kind!r}; the vocabulary is {sorted(SCORE_KINDS)}",
        )
    target[SCORE_KIND_KEY] = kind
    if raw is not None:
        target[SCORE_RAW_KEY] = float(raw)
    return target
