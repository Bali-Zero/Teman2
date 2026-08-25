"""map_backend_result — the ONE place an HTTP outcome becomes a
``ToolResult``, reused across every tool this executor ever wires.

This is the "tool results are untrusted input" boundary MANDATE.md F4
names ("Tool results are marked untrusted; the action lane never reads
free-text CRM fields"). A ``BackendCallResult`` with ``status_code=200``
is NOT trusted just because the transport succeeded — its JSON body is
validated against the CALLING tool's own declared ``result_model``
(a pydantic model living in ``executor/tools/<tool_name>.py``) before a
single field of it is allowed into ``ToolResult.data``. A 200 whose body
fails that validation is ``INVALID_RESPONSE``, not success — the backend
being reachable says nothing about whether what it sent back is the
shape this executor promised the model.

Author: Claude Sonnet 5 (lane B9 — team-bot executor seam)
"""

from __future__ import annotations

from pydantic import BaseModel, ValidationError

from team_bot.registry.envelope import ToolError, ToolResult

from .errors import ExecutorErrorCode
from .http_client import BackendCallResult

__all__ = ["map_backend_result"]

# Whether a given ExecutorErrorCode is safe to retry — a caller-facing
# signal (``ToolError.retryable``), not a suggestion this module acts on
# itself. NOT_FOUND/NOT_AUTHORIZED/INVALID_RESPONSE/INVALID_ARGUMENTS/
# NOT_IMPLEMENTED/FEATURE_DISABLED/INTERNAL are all "retrying with the
# identical request will not help" by construction; UPSTREAM_UNAVAILABLE/
# UPSTREAM_TIMEOUT are transient-network classes where a retry genuinely
# might succeed.
_RETRYABLE: frozenset[ExecutorErrorCode] = frozenset(
    {ExecutorErrorCode.UPSTREAM_UNAVAILABLE, ExecutorErrorCode.UPSTREAM_TIMEOUT}
)

_MESSAGES: dict[ExecutorErrorCode, str] = {
    ExecutorErrorCode.NOT_AUTHORIZED: "The backend refused this request (authorization).",
    ExecutorErrorCode.NOT_FOUND: "The requested resource was not found.",
    ExecutorErrorCode.UPSTREAM_UNAVAILABLE: "The backend is currently unreachable.",
    ExecutorErrorCode.UPSTREAM_TIMEOUT: "The backend did not respond in time.",
    ExecutorErrorCode.INVALID_RESPONSE: "The backend's response did not match the expected shape.",
    ExecutorErrorCode.INTERNAL: "An unexpected internal error occurred.",
}


def _error_result(code: ExecutorErrorCode) -> ToolResult:
    return ToolResult(
        ok=False,
        error=ToolError(code=code.value, message=_MESSAGES[code], retryable=code in _RETRYABLE),
    )


def map_backend_result(result: BackendCallResult, *, result_model: type[BaseModel]) -> ToolResult:
    """Turn one transport-layer outcome into one ``ToolResult``.

    Status-code mapping (deliberately conservative — anything not
    explicitly named below is ``INTERNAL``, never guessed into a more
    specific bucket): 200 with a body that validates against
    ``result_model`` -> success. 200 with a body that does NOT validate,
    or an empty/non-JSON 200 body -> ``INVALID_RESPONSE``. 401/403 ->
    ``NOT_AUTHORIZED``. 404 -> ``NOT_FOUND``. 502/503/504 (and any other
    5xx) -> ``UPSTREAM_UNAVAILABLE``. Any other status (400/409/422/an
    unexpected 2xx like 201, ...) -> ``INTERNAL``: this executor validates
    its own outbound arguments before ever sending them
    (``tool_executor.py``), so a 4xx from a request it built correctly
    signals an API-contract surprise, not a caller/scope problem the
    closed vocabulary already has a more specific bucket for.
    """
    if result.network_error == "timeout":
        return _error_result(ExecutorErrorCode.UPSTREAM_TIMEOUT)
    if result.network_error is not None:
        return _error_result(ExecutorErrorCode.UPSTREAM_UNAVAILABLE)

    status = result.status_code
    if status in (401, 403):
        return _error_result(ExecutorErrorCode.NOT_AUTHORIZED)
    if status == 404:
        return _error_result(ExecutorErrorCode.NOT_FOUND)
    if status is not None and 500 <= status < 600:
        return _error_result(ExecutorErrorCode.UPSTREAM_UNAVAILABLE)

    if status == 200:
        if not isinstance(result.json_body, dict):
            # Empty body, non-JSON body, or a JSON body that isn't even an
            # object (e.g. a bare list/string) — never a partial success.
            return _error_result(ExecutorErrorCode.INVALID_RESPONSE)
        try:
            validated = result_model.model_validate(result.json_body)
        except ValidationError:
            return _error_result(ExecutorErrorCode.INVALID_RESPONSE)
        return ToolResult(ok=True, data=validated.model_dump(mode="json"))

    return _error_result(ExecutorErrorCode.INTERNAL)
