"""Tests for `admin_logs._query_failure` — the error surface of the log endpoints.

WHY THIS EXISTS (2026-09-11): all five endpoints in `admin_logs.py` ended in
`raise HTTPException(status_code=500, detail=str(e))`, returning the raw
Postgres message to the CALLER. That is the one router whose whole purpose is
to be narrower than admin (`DEVELOPER_EMAILS`), and the leak was not
hypothetical — measured on production the same day, four of its five endpoints
read relations that do not exist, so `relation "activity_logs" does not exist`
WAS the normal response body.

The cure distinguishes three outcomes because they mean three different things,
and each has a test below: a deliberate `HTTPException` from inside the `try`
must survive (the bare `except Exception` relabelled it 500), a missing
relation is 501 (not provisioned — not a fault, and not retryable, which is
why not 503), and everything else is a 500 naming the OPERATION only.

The load-bearing assertion is the last group: the response body must never
carry the exception text. Written so it fails if someone reintroduces
`str(e)` into a detail — including via an f-string, which is how it would come
back.
"""

from __future__ import annotations

import pytest


def _q():
    from backend.app.routers.admin_logs import _query_failure

    return _query_failure


def _undefined_table(message: str):
    """A real asyncpg UndefinedTableError, not a stand-in.

    Built through asyncpg's own constructor so the test breaks if the class
    moves or its hierarchy changes, rather than passing against a fake that
    only looks like it.
    """
    import asyncpg

    return asyncpg.exceptions.UndefinedTableError(message)


# The shape of the real message, quoted from production on 2026-09-11.
PG_TEXT = 'relation "activity_logs" does not exist'


def test_a_missing_relation_is_501_not_provisioned() -> None:
    exc = _q()("fetch activity logs", _undefined_table(PG_TEXT))

    assert exc.status_code == 501
    assert "not provisioned" in exc.detail


def test_a_missing_view_is_also_501() -> None:
    """Postgres reports a missing VIEW with the same SQLSTATE (42P01)."""
    exc = _q()(
        "fetch today's activity summary",
        _undefined_table('relation "v_today_team_activity" does not exist'),
    )

    assert exc.status_code == 501


def test_any_other_failure_is_500_naming_only_the_operation() -> None:
    exc = _q()("fetch API audit trail", RuntimeError("connection reset by peer"))

    assert exc.status_code == 500
    assert exc.detail == "fetch API audit trail failed"


def test_an_http_exception_from_inside_the_try_survives_unchanged() -> None:
    """INNOCENCE: the bare `except Exception` used to relabel a 4xx as 500."""
    from fastapi import HTTPException

    original = HTTPException(status_code=422, detail="limit must be positive")
    returned = _q()("fetch activity logs", original)

    assert returned is original
    assert returned.status_code == 422
    assert returned.detail == "limit must be positive"


@pytest.mark.parametrize(
    "exc",
    [
        _undefined_table(PG_TEXT),
        RuntimeError(PG_TEXT),
        ValueError("password=hunter2 in a connection string"),
    ],
)
def test_the_response_body_never_carries_the_exception_text(exc) -> None:
    """The load-bearing one: nothing the database said reaches the caller.

    Asserted as a CLOSED SET rather than by searching the detail for bad
    substrings: the detail must be one of exactly two fixed strings, so ANY
    interpolation of the exception — f-string, concatenation, `%s` — fails
    this, including forms nobody thought to blacklist.
    """
    from backend.app.routers.admin_logs import _UNPROVISIONED_DETAIL

    detail = str(_q()("fetch activity logs", exc).detail)

    assert detail in {_UNPROVISIONED_DETAIL, "fetch activity logs failed"}
    assert str(exc) not in detail


def test_the_server_log_still_gets_the_full_exception(caplog) -> None:
    """The detail is narrowed for the caller, NOT lost for the operator."""
    import logging

    with caplog.at_level(logging.ERROR):
        _q()("fetch activity logs", _undefined_table(PG_TEXT))

    assert any(PG_TEXT in r.getMessage() for r in caplog.records)


def test_a_passed_through_http_exception_is_not_logged_as_a_failure(caplog) -> None:
    """A deliberate 4xx is not a server fault and must not look like one."""
    import logging

    from fastapi import HTTPException

    with caplog.at_level(logging.ERROR):
        _q()("fetch activity logs", HTTPException(status_code=422, detail="bad limit"))

    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_every_endpoint_routes_its_failures_through_the_helper() -> None:
    """W107: five identical sites existed; curing one would cure nothing.

    Reads the module source rather than each endpoint's behaviour, because the
    defect was textual and repeated — the point is that no site was left behind
    and none grows back.
    """
    import ast
    import inspect as _inspect

    from backend.app.routers import admin_logs

    source = _inspect.getsource(admin_logs)
    tree = ast.parse(source)

    # Parsed, not grepped: this module's own docstring quotes the old bad line
    # to explain itself, and a substring search cannot tell prose from code.
    leaks = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "HTTPException"
        for kw in node.keywords
        if kw.arg == "detail"
        and isinstance(kw.value, ast.Call)
        and getattr(kw.value.func, "id", None) == "str"
    ]

    assert leaks == [], f"{len(leaks)} endpoint(s) still return str(exception)"
    assert source.count("raise _query_failure(") == 5


class _RaisingConn:
    """A connection whose every read fails the way production fails today."""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    async def fetchval(self, *_a, **_k):
        raise self._exc

    async def fetch(self, *_a, **_k):
        raise self._exc

    async def fetchrow(self, *_a, **_k):
        raise self._exc


class _RaisingAcquire:
    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    async def __aenter__(self):
        return _RaisingConn(self._exc)

    async def __aexit__(self, *_a):
        return False


class _RaisingPool:
    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    def acquire(self):
        return _RaisingAcquire(self._exc)


def _client(exc: BaseException):
    """A client wired to a failing pool, with the auth gate overridden.

    The grant itself is covered by `test_admin_logs_developer_allowlist.py`;
    overriding it here keeps this file about the ERROR surface and avoids two
    files asserting the same authentication.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.app.dependencies import get_database_pool
    from backend.app.routers import admin_logs

    app = FastAPI()
    app.include_router(admin_logs.router)
    app.dependency_overrides[get_database_pool] = lambda: _RaisingPool(exc)
    app.dependency_overrides[admin_logs.verify_log_read_access] = lambda: True
    return TestClient(app, raise_server_exceptions=False)


ALL_FIVE = [
    "/api/admin/logs/activity",
    "/api/admin/logs/interactions",
    "/api/admin/logs/api-audit",
    "/api/admin/logs/summary/today",
    "/api/admin/logs/summary/interactions",
]


@pytest.mark.parametrize("path", ALL_FIVE)
def test_over_http_a_missing_relation_is_501_on_every_endpoint(path) -> None:
    """GUILT over HTTP, on all five — the shape production is in right now."""
    from backend.app.routers.admin_logs import _UNPROVISIONED_DETAIL

    response = _client(_undefined_table(PG_TEXT)).get(path)

    assert response.status_code == 501, response.text
    assert response.json()["detail"] == _UNPROVISIONED_DETAIL
    assert PG_TEXT not in response.text


@pytest.mark.parametrize("path", ALL_FIVE)
def test_over_http_any_other_failure_leaks_nothing(path) -> None:
    response = _client(RuntimeError("password=hunter2 host=10.0.0.1")).get(path)

    assert response.status_code == 500, response.text
    assert "hunter2" not in response.text
    assert "10.0.0.1" not in response.text
