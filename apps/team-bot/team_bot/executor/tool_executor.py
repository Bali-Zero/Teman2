"""ToolExecutor — the seam this whole package exists for.

``apps/team-bot/README.md`` says of itself: "No server, no CRM client, no
I/O — nothing in this package is imported by any running service ... the
ten-tool registry is pure Pydantic specification with no executors." This
class is the executor: it turns one validated ``ProposedToolCall`` (a
parsed, but UNVALIDATED-against-schema, model turn — see
``team_bot.loop.tool_decision``) into a ``ToolResult``
(``team_bot.registry.envelope``) by chaining, in order:

1. **Feature flags** (``team_bot.flags`` — ``is_team_bot_enabled()``,
   ``is_team_bot_read_tools_enabled()`` for a read tool). Cheapest, no
   I/O, checked first — a flipped-off flag never reaches any of the steps
   below.
2. **Registry + binding lookup** (``get_tool`` from the F5 registry, then
   this module's own ``_BINDINGS`` — which tool NAMES this package
   actually has executor code for; today, exactly one:
   ``get_required_documents``). A name the F5 registry does not know at
   all is ``INTERNAL`` (the loop's own ``classify_step``/
   ``UnknownToolError`` is supposed to have already caught a hallucinated
   tool name before this class is ever called); a name the registry DOES
   know but this package has no ``executor/tools/<name>.py`` for yet is
   ``NOT_IMPLEMENTED`` — true, by design, for 9 of the 10 tools.
3. **The local, early-deny-only scope gate** (``scope_gate.py``) — is a
   well-formed ``principal_id`` even attached to this call? See that
   module's docstring for exactly what this step does and does not
   decide; it is never the authorization boundary.
4. **Argument re-validation** against the tool's own ``args_model`` — the
   model's ``raw_arguments`` is a JSON *string* B4 measured is only
   grammar-constrained on a SUBSET of JSON Schema (F4), so this step
   re-checks pattern/enum/min-max/additionalProperties for real.
5. **Auth resolution** (``auth.py``'s ``TokenProvider``) — turns
   ``principal_id`` into the HTTP headers the backend needs to
   authenticate this call AS that principal, so the backend's OWN
   ``assigned_to`` resolver (``crm_access.get_crm_user_filter``, reused
   unmodified — this class derives no filtering logic of its own) is what
   actually scopes the request, per F7.
6. **The network call** (``http_client.py``'s ``BackendClient``, via the
   tool's own ``call`` coroutine) and **response mapping**
   (``response_mapping.py``) into the final ``ToolResult``.

``ToolExecutor.execute`` NEVER raises for a business-outcome failure — any
step above that fails returns a ``ToolResult(ok=False, error=...)`` with
one of ``ExecutorErrorCode``'s closed vocabulary values. A single
try/except around the tool's own ``call`` coroutine (step 6) is this
class's one deliberate exception to "never swallow broadly" — an
unexpected exception THERE (a bug in this package, not a documented
failure mode any step above already names) becomes ``INTERNAL`` rather
than propagating into whatever calls this class, exactly because nothing
downstream of a tool executor should ever crash on account of a single
tool call.

Author: Claude Sonnet 5 (lane B9 — team-bot executor seam)
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from team_bot.flags import is_team_bot_enabled, is_team_bot_read_tools_enabled
from team_bot.loop.tool_decision import ProposedToolCall
from team_bot.registry import ToolKind, get_tool
from team_bot.registry.envelope import ToolError, ToolResult

from .auth import NullTokenProvider, TokenProvider
from .errors import ExecutorErrorCode
from .http_client import BackendCallResult, BackendClient
from .response_mapping import map_backend_result
from .scope_gate import evaluate_early_deny
from .tools import get_required_documents

logger = logging.getLogger(__name__)

__all__ = ["ToolBinding", "ToolExecutor"]


@dataclass(frozen=True)
class ToolBinding:
    """Everything ``ToolExecutor`` needs to run ONE tool name — the args
    model to re-validate against, the result model to validate the
    backend's response against, and the coroutine that actually makes the
    call. One instance per implemented tool in ``_BINDINGS`` below;
    wiring tool #2 of the ten is purely additive (one more entry, one more
    ``executor/tools/<name>.py`` module), never a change to this class."""

    args_model: type[BaseModel]
    result_model: type[BaseModel]
    call: Callable[[BackendClient, dict[str, str], BaseModel], Awaitable[BackendCallResult]]


def _bind_get_required_documents() -> ToolBinding:
    async def _call(client: BackendClient, headers: dict[str, str], args: BaseModel) -> BackendCallResult:
        assert isinstance(args, get_required_documents.GetRequiredDocumentsArgs)
        return await get_required_documents.call(client, headers=headers, args=args)

    return ToolBinding(
        args_model=get_required_documents.GetRequiredDocumentsArgs,
        result_model=get_required_documents.GetRequiredDocumentsResult,
        call=_call,
    )


# Only tool names this package has an executor/tools/<name>.py module for.
# A name registered in team_bot.registry but ABSENT here is a real,
# expected, NOT_IMPLEMENTED state today (see module docstring, step 2).
_BINDINGS: dict[str, ToolBinding] = {
    "get_required_documents": _bind_get_required_documents(),
}


def _error(code: ExecutorErrorCode, message: str) -> ToolResult:
    return ToolResult(ok=False, error=ToolError(code=code.value, message=message, retryable=False))


class ToolExecutor:
    """Construct once per process (it owns no per-call mutable state
    beyond what's passed in), share across every tool call. Takes a
    ``BackendClient`` (one persistent ``httpx.AsyncClient``, see that
    module) and a ``TokenProvider`` (defaults to ``NullTokenProvider`` —
    fail closed until F7 wires a real one in — see ``auth.py``)."""

    def __init__(self, client: BackendClient, *, token_provider: TokenProvider | None = None) -> None:
        self._client = client
        self._token_provider = token_provider if token_provider is not None else NullTokenProvider()

    async def execute(self, call: ProposedToolCall, *, principal_id: str) -> ToolResult:
        # 1. Feature flags — cheapest, checked first, no I/O.
        if not is_team_bot_enabled():
            return _error(ExecutorErrorCode.FEATURE_DISABLED, "The team bot is currently disabled.")

        spec = get_tool(call.tool_name)
        if spec is None:
            # A hallucinated tool name should never reach this class (the
            # loop's classify_step/UnknownToolError is supposed to catch
            # it first) — this is defense-in-depth for a caller/dispatch
            # bug, not a business outcome a 14B model can steer into.
            logger.warning("team_bot.executor.tool_executor: unregistered tool_name %r", call.tool_name)
            return _error(ExecutorErrorCode.INTERNAL, "This tool is not registered.")

        if spec.kind is ToolKind.READ and not is_team_bot_read_tools_enabled():
            return _error(ExecutorErrorCode.FEATURE_DISABLED, "Read tools are currently disabled.")
        # Mutation tools (R1/R2/R3) are out of this lane's scope entirely —
        # see this class's docstring and README's own "Do NOT implement
        # all ten tools" scope. A mutation binding, if one is ever added
        # to _BINDINGS by a future lane, must gate on
        # TEAM_BOT_MUTATIONS_ENABLED there, not here — this class does not
        # special-case a ToolKind it has never actually executed.

        binding = _BINDINGS.get(call.tool_name)
        if binding is None:
            return _error(
                ExecutorErrorCode.NOT_IMPLEMENTED,
                f"'{call.tool_name}' is registered but has no executor yet.",
            )

        # 3. Local, early-deny-only scope gate (scope_gate.py) — see that
        # module's docstring for exactly what this does and does not
        # decide.
        gate_verdict = evaluate_early_deny(principal_id=principal_id)
        if not gate_verdict.allow:
            return _error(ExecutorErrorCode.NOT_AUTHORIZED, "No valid principal is attached to this call.")

        # 4. Argument re-validation — raw_arguments is a JSON string only
        # grammar-constrained on a SUBSET of JSON Schema (F4).
        parsed_args = call.parsed_arguments()
        if parsed_args is None:
            return _error(ExecutorErrorCode.INVALID_ARGUMENTS, "Could not parse the tool call's arguments as JSON.")
        try:
            validated_args = binding.args_model.model_validate(parsed_args)
        except ValidationError:
            return _error(
                ExecutorErrorCode.INVALID_ARGUMENTS,
                "The tool call's arguments did not match the tool's schema.",
            )

        # 5. Auth resolution — turns principal_id into the headers the
        # backend needs to enforce its OWN assigned_to scope (F7).
        auth_material = self._token_provider.resolve(principal_id)
        if auth_material is None:
            return _error(ExecutorErrorCode.NOT_AUTHORIZED, "No credential is available for this principal.")

        # 6. The network call + response mapping. The one broad
        # try/except this class allows — see module docstring for why.
        try:
            backend_result = await binding.call(self._client, auth_material.headers, validated_args)
        except Exception:  # noqa: BLE001 — see module docstring: an unexpected bug becomes INTERNAL, never propagates.
            logger.exception(
                "team_bot.executor.tool_executor: unexpected exception executing %r", call.tool_name
            )
            return _error(ExecutorErrorCode.INTERNAL, "An unexpected internal error occurred.")

        return map_backend_result(backend_result, result_model=binding.result_model)
