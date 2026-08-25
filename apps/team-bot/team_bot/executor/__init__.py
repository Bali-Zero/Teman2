"""Lane B9 — the team-bot executor seam.

Turns a validated ``ProposedToolCall`` (``team_bot.loop.tool_decision``)
into a ``team_bot.registry.envelope.ToolResult`` by calling the Fly
backend's own REST endpoints (RECON domain 4 — never the
``nuzantara-mcp`` server, which exists for a different, cloud consumer).

This is the piece ``apps/team-bot/README.md`` describes as missing
("nothing in this package is imported by any running service") — after
this package exists, that sentence is no longer accurate: ``ToolExecutor``
is real, importable, I/O-carrying code, and one tool
(``get_required_documents``, R0) runs end to end against it.

**What this package does NOT do** (see ``README.md``'s "Definition of
done" for the full statement): implement the other nine tools (each
``ToolKind.READ`` name registered in ``team_bot.registry`` but absent from
``executor/tools/`` returns ``ExecutorErrorCode.NOT_IMPLEMENTED``, never a
crash or a guess); wire F7's real identity/auth material (``auth.py``'s
``NullTokenProvider`` fails every call closed until a real
``TokenProvider`` is supplied); resolve the confirmation-store's
``execute_fn`` contract for mutations (``confirmation/store.py``'s
``SqlitePendingActionStore.execute`` is SYNCHRONOUS — this package's
``BackendClient`` is built on ``httpx.AsyncClient`` and is async
throughout; a mutation-tool lane wiring R1/R2/R3 will need to resolve that
mismatch, most likely with a sync ``httpx.Client`` variant for the
mutation path, not by forcing this async read-path client to serve both).

Author: Claude Sonnet 5 (lane B9 — team-bot executor seam)
"""

from __future__ import annotations

from .auth import AuthMaterial, NullTokenProvider, TokenProvider
from .errors import ExecutorErrorCode
from .http_client import BackendCallResult, BackendClient, BackendClientConfig
from .response_mapping import map_backend_result
from .scope_gate import (
    ScopeGateDenyReason,
    ScopeGateVerdict,
    crm_record_ids_in,
    evaluate_early_deny,
    is_valid_principal_id,
)
from .tool_executor import ToolBinding, ToolExecutor

__all__ = [
    "AuthMaterial",
    "BackendCallResult",
    "BackendClient",
    "BackendClientConfig",
    "ExecutorErrorCode",
    "NullTokenProvider",
    "ScopeGateDenyReason",
    "ScopeGateVerdict",
    "TokenProvider",
    "ToolBinding",
    "ToolExecutor",
    "crm_record_ids_in",
    "evaluate_early_deny",
    "is_valid_principal_id",
    "map_backend_result",
]
