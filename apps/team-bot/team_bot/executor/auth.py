"""AuthMaterial / TokenProvider — the seam between this executor and F7
(``wa_id -> HMAC -> enrolled team mapping -> 60s principal ticket``),
which is NOT built in this lane.

F7's own frozen text ("the model cannot supply actor or scope; CRM routes
independently enforce ``assigned_to``") tells this executor WHAT it must
do: attach the resolved principal's identity to every outbound backend
call so the SAME server-side resolver the REST routers and
``services/agents/tool_authorizer.py``'s ``_check_client_scope`` already
use (``backend.app.deps.crm_access.get_crm_user_filter``) does the actual
scoping, unmodified. It does NOT tell this executor HOW a WhatsApp
identity becomes something the backend's auth layer accepts — that is a
genuine open question this package does not resolve (a WhatsApp principal
has no portal login, so whether the backend ends up trusting a Bearer JWT
compatible with ``get_current_user``, or a service-token + on-behalf-of
header pair the backend needs a NEW auth path for, is F7's decision to
make, not one this lane invents on its behalf).

``AuthMaterial`` is therefore deliberately a bag of HTTP headers rather
than a single named "bearer token" string — whichever shape F7 lands on,
it reduces to "these headers go on the request" without this module
having to be rewritten. ``TokenProvider`` is the pluggable resolver;
``NullTokenProvider`` is the safe default this package ships with today —
it resolves nothing, which makes every real call fail closed
(``ExecutorErrorCode.NOT_AUTHORIZED``) until a real F7 implementation is
wired in. This mirrors ``services/rag/agentic/team_crm_tools.py``'s own
"hard-absence when the flag is off" discipline: an executor with no wired
identity source behaves as if no one is authenticated, never as if
everyone is.

Author: Claude Sonnet 5 (lane B9 — team-bot executor seam)
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

__all__ = ["AuthMaterial", "NullTokenProvider", "TokenProvider"]


class AuthMaterial(BaseModel):
    """The HTTP headers one outbound backend call needs to authenticate as
    one principal. Frozen and forbid-extra because THIS package authors
    both sides of this shape (unlike a backend response, which is
    untrusted external input — see ``executor/tools/*.py``'s deliberately
    different ``extra="ignore"`` choice for that reason)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    headers: dict[str, str]


class TokenProvider(Protocol):
    """Resolves a ``principal_id`` (F7's opaque, non-PII token — see
    ``team_bot.confirmation.models.PRINCIPAL_ID_PATTERN``) into the
    ``AuthMaterial`` an outbound backend call needs, or ``None`` when no
    credential is available for that principal (fail closed, never fall
    back to an anonymous/unscoped call)."""

    def resolve(self, principal_id: str) -> AuthMaterial | None: ...


class NullTokenProvider:
    """The reference/default ``TokenProvider``: resolves nothing, for
    anyone. Constructing a ``ToolExecutor`` without an explicit real
    provider uses this — every call then fails closed at the auth-resolve
    step (``NOT_AUTHORIZED``) rather than silently calling the backend
    with no identity attached, which ``crm_access.get_crm_user_filter``
    would otherwise be free to treat as an anonymous/admin caller
    depending on how the eventual auth middleware is configured. Fail
    closed is the only safe default when F7 has not wired a real one in.
    """

    def resolve(self, principal_id: str) -> AuthMaterial | None:
        return None
