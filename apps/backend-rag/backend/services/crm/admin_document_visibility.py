"""Which documents the TEAM's CRM readers show.

Two kinds of deletion exist on `documents`, written by two different routes:

- ``status = 'deleted'`` — written by the team-side delete route.
- ``deleted_at`` — written by the client's portal soft-delete
  (``DELETE /api/portal/documents/{id}`` -> ``soft_delete_document``), which
  never touches ``status``.

Admin readers used to filter neither, so deleted documents kept showing in
the team's CRM (Antonello, read-only production count 30 Sep 2026: 187 rows,
168 via status and 19 via deleted_at).

This is NOT the portal predicate (``services/portal/_document_visibility.py``):
that one also hides ``client_visible = false`` documents, which are internal
team documents and must stay visible to the team.

Shape (b), chosen by Antonello 1 Oct 2026:
- document list, OCR status poll, evidence dossier -> hide both deletions;
- client profile -> hide only ``status = 'deleted'`` and keep the
  ``deleted_at`` rows, which feed the "Removed" pill and the 30-day restore
  window (portal audit finding F-02).
"""

from __future__ import annotations


def _prefix(alias: str) -> str:
    return f"{alias}." if alias else ""


def admin_document_not_team_deleted_clause(alias: str = "") -> str:
    """SQL predicate: the team has not marked this document deleted.

    Splice in with ``AND`` on both sides. ``alias`` is the table alias used
    by the query (``"d"``), or empty when ``documents`` is unaliased.
    """
    return f"COALESCE({_prefix(alias)}status, '') <> 'deleted'"


def admin_document_not_deleted_clause(alias: str = "") -> str:
    """SQL predicate: neither the team nor the client deleted this document."""
    return f"{_prefix(alias)}deleted_at IS NULL AND {admin_document_not_team_deleted_clause(alias)}"


__all__ = [
    "admin_document_not_deleted_clause",
    "admin_document_not_team_deleted_clause",
]
