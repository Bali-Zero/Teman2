"""Shared test doubles for lane B9's executor suite.

``fake_transport`` is the ONE place a test fakes the network — an
``httpx.MockTransport``, injected via ``BackendClient(transport=...)``.
Every test in this suite that exercises ``BackendClient``/
``ToolExecutor`` goes through this, never a live socket (this repo's B6
law: "No test may touch graph.facebook.com or any real network" — the
same discipline applied here to the team-bot's own backend).
"""

from __future__ import annotations

from collections.abc import Callable

import httpx

__all__ = ["StaticTokenProvider", "fake_transport", "json_response", "network_error", "timeout"]


def fake_transport(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def json_response(status_code: int, body: object) -> Callable[[httpx.Request], httpx.Response]:
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=body)

    return _handler


def timeout() -> Callable[[httpx.Request], httpx.Response]:
    def _handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated read timeout", request=request)

    return _handler


def network_error() -> Callable[[httpx.Request], httpx.Response]:
    def _handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated connection refused", request=request)

    return _handler


class StaticTokenProvider:
    """A ``TokenProvider`` test double: one fixed principal_id resolves to
    one fixed header set; every other principal_id resolves to ``None``
    (fail closed, matching ``NullTokenProvider``'s default posture for
    anyone this provider was not explicitly told about)."""

    def __init__(self, principal_id: str, headers: dict[str, str]) -> None:
        self._principal_id = principal_id
        self._headers = headers

    def resolve(self, principal_id: str):  # noqa: ANN201 — matches TokenProvider.resolve's return type
        if principal_id != self._principal_id:
            return None
        from team_bot.executor.auth import AuthMaterial

        return AuthMaterial(headers=dict(self._headers))
