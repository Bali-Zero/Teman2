"""
Retrieval-side pasal-supersession guard — the second half of the PENDING-ARMS
2026-08-25 minimal arm.

The writer (backend/core/legal/supersession.py) stamps superseded chunks with
flat payload keys (superseded_by_document, superseded_pasal_number,
superseded_action, superseded_by_label). This module reads them AFTER
retrieval and:

1. ANNOTATES every result chunk that carries the keys AND whose superseding
   instrument is itself present in the result set — the replacement wording is
   available to the reader, so the stale chunk gets an explicit
   ``superseded_marker`` in its metadata.
2. DE-RANKS those chunks below every non-superseded result (stable: internal
   score order is preserved, so this never invents a ranking — it only
   demotes chunks that advertise themselves as superseded).

WHEN THE SUPERSEDING TEXT IS NOT IN THE RESULT SET the chunk is left alone.
A lone pre-amendment chunk cannot be silently dropped: with the replacement
text absent, demoting it would trade a stale answer for NO answer, and the
downstream evidence gates already treat thin evidence as a reason to abstain.

NO-OP GUARANTEE. Chunks without the supersession keys — i.e. the entire
corpus until the backfill runs — pass through unchanged. The guard is pure
Python over formatted results and never touches Qdrant.

NOT COVERED HERE (stated, not papered over): the guard applies to the
SearchService paths that call it (search(), _single_query_search() — and
therefore search_with_reranking(), which delegates to search()). Other
retrieval entry points (hybrid search service, citation service direct
scrolls) do not apply it yet.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _chunk_metadata(result: dict[str, Any]) -> dict[str, Any]:
    metadata = result.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def apply_supersession_guard(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Annotate and de-rank superseded chunks whose replacement is in the set.

    Args:
        results: Formatted search results (result_formatter output order —
            already score-sorted by the caller).

    Returns:
        The same list, reordered (superseded-and-replaced chunks moved to the
        tail) with ``is_superseded`` / ``superseded_marker`` set on their
        metadata. Mutates result metadata dicts in place (they are per-call
        copies made by format_search_results).
    """
    if not results:
        return results

    present_document_ids = {
        str(_chunk_metadata(result).get("document_id"))
        for result in results
        if _chunk_metadata(result).get("document_id")
    }

    kept: list[dict[str, Any]] = []
    demoted: list[dict[str, Any]] = []
    for result in results:
        metadata = _chunk_metadata(result)
        superseding_doc = metadata.get("superseded_by_document")
        if superseding_doc and str(superseding_doc) in present_document_ids:
            label = metadata.get("superseded_by_label") or str(superseding_doc)
            action = metadata.get("superseded_action") or "diubah"
            metadata["is_superseded"] = True
            metadata["superseded_marker"] = (
                f"Superseded ({action}) by {label}; the amendment's wording "
                "in this result set is the current text for this pasal."
            )
            demoted.append(result)
        else:
            kept.append(result)

    if demoted:
        logger.info(
            "Supersession guard: demoted %d superseded chunk(s) whose replacement is in the result set",
            len(demoted),
        )
    return kept + demoted
