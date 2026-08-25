"""``get_required_documents`` executor — the one tool this lane wires end
to end (F5, R0, ``team_bot.registry.tools._GET_REQUIRED_DOCUMENTS``).

Args/result shapes below are transcribed verbatim from research capture
``research/operations/2026-08-25-due-bot-7-lens-research.md`` §4, "5.
``get_required_documents``" — the SAME source ``registry/tools.py``'s
``parameters_schema`` transcribes, so this module's ``args_model``/
``result_model`` stay byte-compatible with the frozen registry entry by
construction rather than by hand-checked convention: ``practice_type`` in,
``{practice_type, required_docs, optional_docs}`` out, both doc lists
drawn from ``DocumentType``. This is a STATIC reference lookup ("standard
document checklist for a practice type") — it never names a client, a
practice, or a staff member, and its answer is the same for every caller.

--------------------------------------------------------------------
DISCOVERY — the backing-data seam mismatch (found building this module,
reported here rather than silently resolved one way or the other)
--------------------------------------------------------------------

The task brief that assigned this lane picked ``get_required_documents``
"because domain 2's 'missing: X' is the thinnest real slice and the CRM
side already exists: table ``practice_required_documents``,
``crm_practices.py`` ``get_required_documents`` ~line 2122" — quoting
``RECON-domains-2-4.md``'s own domain-2 section, which says the same
thing: "it needs an executor, not a schema."

Both of those are wrong about the SAME point, verified against the actual
files rather than assumed from either document's prose:

- ``apps/backend-rag/backend/app/routers/crm_practices.py:2122``'s
  ``get_required_documents`` is ``GET /api/crm/practices/{practice_id}
  /required-documents`` — keyed by an integer ``practice_id`` (a specific
  CRM record), reading the ``practice_required_documents`` table, whose
  rows are entered PER PRACTICE by a team member via
  ``POST /{practice_id}/required-documents`` (``RequiredDocumentCreate``)
  and carry a per-document upload/verification STATUS
  (``pending``/``uploaded``/``verified``/``rejected``). This answers a
  genuinely different question — "what's still missing on THIS practice"
  — and needs the ``assigned_to`` scoping RECON itself says the team bot
  must reuse, not derive a third time.
- The F5 registry's frozen ``get_required_documents`` ToolSpec (and the
  Qwen §4 schema it transcribes) takes ONLY ``practice_type`` — a
  ``PracticeType`` enum, never a record id — and its worked "Returns"
  example is a flat ``required_docs``/``optional_docs`` list of
  ``DocumentType`` values with no status field at all. No per-client
  scoping question even arises for this shape: the answer is the same for
  every caller.
- No backend surface answers the registry tool's actual question. Checked
  directly, not assumed absent: ``practice_types`` (the table
  ``crm_practices.py`` itself reads client/practice records against) has
  no document-requirements column in any migration that created or
  altered it; ``services/journey/journey_templates.py``'s
  ``JOURNEY_TEMPLATES`` carries per-STEP, free-text document labels (e.g.
  "Proposed company names (3 options)") keyed by journey slugs
  (``pt_pma_setup``, ...) that do not 1:1 match ``PracticeType``'s seven
  values, and its strings do not 1:1 match ``DocumentType``'s eleven —
  mapping one onto the other would mean this lane INVENTING which
  document types a KITAS/work-permit/company-setup application requires,
  which is exactly the class of fabricated regulatory content CLAUDE.md
  §9 ("Verify Sources") and this repo's own KBLI-corpus incident history
  exist to prevent. Building that mapping is a content decision for a
  domain lane with the standing to verify it against a real source, not
  an executor-seam lane.

**Resolution taken** (not escalated silently, not smuggled past the
frozen schema either): this module stays faithful to the FROZEN registry
schema (``practice_type`` in, doc-type lists out) — renaming/resplitting
it to accept a ``practice_id`` instead would silently disconnect the
registry from the B4 golden-suite evidence the registry's own README
already protects against doing. It targets a plausible, clearly-scoped,
sibling REST path next to the real per-practice endpoint —
``GET /api/crm/practice-types/{practice_type}/required-documents`` —
which **does not exist in the backend today**. This module is fully
exercised end to end against a fake transport (``BackendCallResult``
built directly, per the lane's own testing constraint: no test touches a
real network) and proves the CLIENT-side machinery completely: arg
validation, the (structurally-inapplicable-here) scope gate, auth
attachment, status-code mapping, untrusted-response validation. It does
NOT prove a live backend round trip, because there is nothing live to
round-trip against yet. Wiring a REAL backend route for this tool needs
one of two decisions this lane does not make: (a) a domain-2 lane adds
``GET /api/crm/practice-types/{practice_type}/required-documents`` backed
by real, sourced reference data, or (b) an F5-owner decision widens the
frozen registry tool to accept ``practice_id`` instead and this executor
is rewired to call the REAL, LIVE endpoint at
``crm_practices.py:2122`` (which DOES need the ``assigned_to`` scope this
module's own ``scope_gate.py`` was built to support — see that module's
docstring for the record-reference check it already carries for exactly
this future).

Author: Claude Sonnet 5 (lane B9 — team-bot executor seam)
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from team_bot.registry.envelope import DocumentType, PracticeType

from ..http_client import BackendCallResult, BackendClient

__all__ = ["GetRequiredDocumentsArgs", "GetRequiredDocumentsResult", "call"]

_MAX_DOC_TYPES = len(DocumentType)  # a result can never list more distinct doc types than the enum has


class GetRequiredDocumentsArgs(BaseModel):
    """The tool's OWN outbound arguments — this package authors both ends
    of this shape (the model that proposes the call, and this module that
    executes it), so ``extra="forbid"`` is the right default, matching
    ``registry/tools.py``'s ``additionalProperties: false``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    practice_type: PracticeType


class GetRequiredDocumentsResult(BaseModel):
    """The backend's response shape — UNTRUSTED external input (MANDATE.md
    F4: "Tool results are marked untrusted"), validated here before a
    single field reaches ``ToolResult.data``.

    ``extra="ignore"``, deliberately DIFFERENT from this module's own
    ``GetRequiredDocumentsArgs`` above: the backend is a separately
    deployed service this package does not control the release cadence
    of, and forbidding an extra field here would make every already-shipped
    team-bot process start rejecting an otherwise-fine 200 response the
    moment the backend adds a field for its OWN reasons (mirrors
    ``backend/services/client_bot/contracts.py``'s ``PricingSnapshot.items``
    framing: "the concrete per-item pydantic model belongs to [the other
    system] itself" — here the response CONTRACT belongs to whichever
    backend route eventually implements it, not to this executor).
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    practice_type: PracticeType
    required_docs: tuple[DocumentType, ...] = Field(default=(), max_length=_MAX_DOC_TYPES)
    optional_docs: tuple[DocumentType, ...] = Field(default=(), max_length=_MAX_DOC_TYPES)

    @model_validator(mode="after")
    def _no_overlap_between_required_and_optional(self) -> GetRequiredDocumentsResult:
        overlap = set(self.required_docs) & set(self.optional_docs)
        if overlap:
            raise ValueError(
                "backend response lists the same document type(s) as both required and "
                f"optional: {sorted(d.value for d in overlap)}"
            )
        return self


def _path_for(practice_type: PracticeType) -> str:
    # NOT a live backend route today — see this module's docstring
    # "DISCOVERY" section for the full reasoning. Kept as one small,
    # named function (rather than inlined in `call`) so a future rewire
    # onto the real per-practice endpoint touches exactly one line.
    return f"/api/crm/practice-types/{practice_type.value}/required-documents"


async def call(
    client: BackendClient,
    *,
    headers: Mapping[str, str],
    args: GetRequiredDocumentsArgs,
) -> BackendCallResult:
    """The one network call this tool makes. Pure pass-through to
    ``BackendClient.get`` — no retry, no caching, no PII in the request
    (``practice_type`` is a closed enum, never a client identifier)."""
    return await client.get(_path_for(args.practice_type), headers=headers)
