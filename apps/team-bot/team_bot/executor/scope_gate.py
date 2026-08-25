"""The B9 executor's local, early-deny-only scope gate.

MANDATE.md F7, verbatim: "The model cannot supply actor or scope; CRM
routes independently enforce ``assigned_to`` (endpoint authorization is
the boundary; the local authorizer is early-deny only)." This module IS
that local authorizer, and it is deliberately narrow about what it claims
to decide — the same discipline
``backend/services/agents/tool_authorizer.py`` documents for its own
scaffolding-vs-real distinction: this gate can refuse a call ONLY on
grounds it can verify without any I/O, and it must never be mistaken for
the real authorization boundary, which lives entirely on the backend
(``backend.app.deps.crm_access.get_crm_user_filter`` and its callers).

Two things this gate can check locally, and only two:

1. **Is a principal attached to this call at all?** F7's identity gate is
   supposed to run upstream of every tool call (an unverified WhatsApp
   number never reaches the LLM in the first place), so by the time
   ``ToolExecutor.execute`` is reached a well-formed ``principal_id``
   should always be present. This is the defense-in-depth check for the
   case where it is NOT — a caller/programmer bug, not a business
   decision — mirroring ``team_crm_tools.py``'s own "even if a future
   refactor registers these tools unconditionally, execute() still
   refuses when the flag is off" posture applied to identity instead of a
   flag.
2. **Does this call's (already-validated) arguments reference a CRM
   record at all** (``crm_record_ids_in``)? Structural, string-pattern
   only — it does NOT and CANNOT decide whether the attached principal
   may see that specific record; that determination is exclusively the
   backend's job (verified by whichever REST endpoint the executor calls,
   via the SAME resolver every other CRM entry point already uses). This
   function exists so every future tool's executor asks the identical
   question the identical way, rather than each tool inventing its own
   ad-hoc scan — and so this lane's own test suite has something concrete
   to run guilt/innocence pairs against even though the ONE tool this
   lane ships (``get_required_documents``) never references a record at
   all (see that module's own docstring for why: it is a static
   practice-type reference lookup, not a per-client/per-practice query).

What this gate explicitly does NOT do, named so a future reader does not
mistake its silence for a decision: it does not maintain a cache of
"which records this principal may see", it does not call the backend, and
an ``allow`` verdict from this gate is never sufficient on its own to
justify a mutation or a scoped read — it only means "nothing checkable
without I/O says to refuse yet."

Author: Claude Sonnet 5 (lane B9 — team-bot executor seam)
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from team_bot.confirmation.models import PRINCIPAL_ID_PATTERN
from team_bot.registry.envelope import CLIENT_ID_PATTERN, PRACTICE_ID_PATTERN, TARGET_ID_PATTERN

__all__ = [
    "ScopeGateDenyReason",
    "ScopeGateVerdict",
    "crm_record_ids_in",
    "evaluate_early_deny",
    "is_valid_principal_id",
]

_PRINCIPAL_ID_RE = re.compile(PRINCIPAL_ID_PATTERN)

# TARGET_ID_PATTERN already unions CL-/PR- (create_reminder's target_id, F5
# tool 8), so it alone would suffice for coverage today — CLIENT_ID_PATTERN
# and PRACTICE_ID_PATTERN are included too, deliberately redundantly, so
# this list keeps working unchanged if a future tool ever narrows to one
# prefix and TARGET_ID_PATTERN's union stops covering it.
_RECORD_ID_RES: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern) for pattern in (CLIENT_ID_PATTERN, PRACTICE_ID_PATTERN, TARGET_ID_PATTERN)
)


def is_valid_principal_id(principal_id: str) -> bool:
    """Structural shape check only (``PRINCIPAL_ID_PATTERN``) — this does
    NOT verify the principal is a real, currently-enrolled team member;
    that is F7's job, not built here."""
    return bool(principal_id) and _PRINCIPAL_ID_RE.fullmatch(principal_id) is not None


def crm_record_ids_in(args: Mapping[str, object]) -> tuple[str, ...]:
    """Which string VALUES in an already-validated args mapping look like a
    CRM record reference (``CL-...``/``PR-...``) — structural pattern match
    only, no DB lookup, no ownership claim. See this module's docstring
    for the full "what this is and is not" statement. Deterministic order
    (dict iteration order of ``args``), deduplicated, so a caller gets a
    stable, testable tuple rather than an unordered set.
    """
    found: list[str] = []
    for value in args.values():
        if isinstance(value, str) and value not in found and any(pat.fullmatch(value) for pat in _RECORD_ID_RES):
            found.append(value)
    return tuple(found)


class ScopeGateDenyReason(StrEnum):
    MISSING_OR_MALFORMED_PRINCIPAL = "missing_or_malformed_principal"


class ScopeGateVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    allow: bool
    deny_reason: ScopeGateDenyReason | None = None


def evaluate_early_deny(*, principal_id: str) -> ScopeGateVerdict:
    """The one local, I/O-free check this executor performs before ever
    attempting a network call: is a well-formed principal attached at
    all? An ``allow`` here is NOT proof of authorization — see module
    docstring — only proof that this one, narrow, checkable-without-I/O
    condition did not fail.
    """
    if not is_valid_principal_id(principal_id):
        return ScopeGateVerdict(allow=False, deny_reason=ScopeGateDenyReason.MISSING_OR_MALFORMED_PRINCIPAL)
    return ScopeGateVerdict(allow=True)
