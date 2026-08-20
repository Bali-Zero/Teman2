"""Canonical "is this document currently visible to the client" predicate.

One definition, reused by every portal-facing read of `documents`:
- the vault (`_mixins/documents.py`: get_documents, download_document,
  soft_delete_document, restore_document)
- the dashboard/visa-tab/company-tab/timeline reads (`_mixins/dashboard.py`)

Migration `db/migrations_v2/236_portal_documents_purpose_softdelete.sql`
introduced client-initiated soft-delete (`deleted_at`) and its own comment
states the intended invariant ("The vault list query filters
`deleted_at IS NULL`") — but only updated the ONE consumer it named. The team
archive flag (`is_archived`, older, pre-dating that migration) was never
backfilled into the dashboard reads either. Both flags left the same fixed
shape of bug: a document archived by the team or trashed by the client
correctly disappeared from the vault and correctly 404'd on download, but
kept counting in the dashboard tile and kept listing in the visa tab, the
company tab, and the activity timeline — a ghost document that 404s if the
client clicks it.

Use `document_visibility_clause()` in every new/edited query instead of
writing the three conditions out by hand, so there is one filter and not a
second dialect that drifts again the next time this table grows a fourth
"is this document currently hidden" flag.
"""

from __future__ import annotations


def document_visibility_clause(alias: str = "") -> str:
    """Return the SQL predicate for "this document is currently visible to
    the client": not team-hidden, not client-hidden, not team-archived.

    Args:
        alias: optional table alias (e.g. "d") used in the query the
            predicate is spliced into. Empty string when the query selects
            from `documents` unaliased.

    Returns:
        A SQL fragment with no leading/trailing "AND" — splice it in with
        " AND " on both sides, or use it as the sole WHERE body.
    """
    prefix = f"{alias}." if alias else ""
    return (
        f"{prefix}client_visible = true"
        f" AND {prefix}deleted_at IS NULL"
        f" AND COALESCE({prefix}is_archived, FALSE) = FALSE"
    )


__all__ = ["document_visibility_clause"]
