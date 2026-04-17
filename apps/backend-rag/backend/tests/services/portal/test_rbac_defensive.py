"""
Defensive RBAC tests for backend.services.portal._rbac.

Audit 2026-04-18 HIGH-6.

These tests exercise the `require_client_access` decorator in isolation —
they do not go through FastAPI, so the "did the router pass current_user?"
invariant is verified directly on the service layer, which is the point
of the defence-in-depth check.
"""

from __future__ import annotations

import pytest

from backend.core.exceptions import PortalAccessDenied
from backend.services.portal._rbac import (
    ClientContext,
    PortalAuthRequired,
    require_client_access,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class FakePortalMixin:
    """
    Minimal stand-in for the real PortalService mixins: the decorator only
    looks at `client_id` and `current_user`, so we can test behaviour
    without touching asyncpg.
    """

    @require_client_access
    async def get_dashboard(
        self,
        client_id: int,
        *,
        current_user: ClientContext,
    ) -> dict[str, int]:
        return {"client_id": client_id}

    @require_client_access
    async def send_message(
        self,
        client_id: int,
        content: str,
        *,
        current_user: ClientContext,
    ) -> dict[str, str]:
        return {"client_id": str(client_id), "content": content}


@pytest.fixture
def service() -> FakePortalMixin:
    return FakePortalMixin()


# ---------------------------------------------------------------------------
# Scenario 1 — client acting on its own data: allowed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_accessing_own_data_is_allowed(service: FakePortalMixin) -> None:
    ctx: ClientContext = {
        "client_id": 42,
        "email": "client-42@example.com",
    }
    result = await service.get_dashboard(42, current_user=ctx)
    assert result == {"client_id": 42}


# ---------------------------------------------------------------------------
# Scenario 2 — client trying to read a different client's data: DENIED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_accessing_other_client_is_denied(
    service: FakePortalMixin,
) -> None:
    ctx: ClientContext = {
        "client_id": 42,
        "email": "client-42@example.com",
    }
    with pytest.raises(PortalAccessDenied) as exc_info:
        await service.get_dashboard(99, current_user=ctx)

    exc = exc_info.value
    assert exc.client_id == 99
    assert exc.actor_client_id == 42
    assert exc.actor_email == "client-42@example.com"
    assert "get_dashboard" in (exc.method or "")


# ---------------------------------------------------------------------------
# Scenario 3 — superuser impersonating a client (router already vetted): allowed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_superuser_impersonation_is_allowed_when_target_matches(
    service: FakePortalMixin,
) -> None:
    ctx: ClientContext = {
        "client_id": 77,
        "email": "zero@balizero.com",
        "impersonating": True,
    }
    result = await service.get_dashboard(77, current_user=ctx)
    assert result == {"client_id": 77}


@pytest.mark.asyncio
async def test_superuser_impersonation_cannot_pivot_to_another_client(
    service: FakePortalMixin,
) -> None:
    """
    Even with impersonating=True, the service refuses if the method's
    client_id diverges from the impersonation target. This stops an attacker
    who got `?as_client=A` past the router from pivoting to client B in the
    same request.
    """
    ctx: ClientContext = {
        "client_id": 77,
        "email": "zero@balizero.com",
        "impersonating": True,
    }
    with pytest.raises(PortalAccessDenied) as exc_info:
        await service.get_dashboard(99, current_user=ctx)

    assert exc_info.value.client_id == 99
    assert exc_info.value.actor_client_id == 77


# ---------------------------------------------------------------------------
# Scenario 4 — missing current_user: PortalAuthRequired (programming error)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_current_user_raises_auth_required(
    service: FakePortalMixin,
) -> None:
    """
    Calling without current_user at all hits the decorator's partial bind,
    where current_user is absent → treated as None → PortalAuthRequired.
    (The inner function, if ever reached, would also fail with TypeError
    because current_user is a keyword-only required parameter; but we want
    the decorator's defensive path to fire first so that the error is
    unambiguous and auditable.)
    """
    with pytest.raises(PortalAuthRequired):
        await service.get_dashboard(42)  # type: ignore[call-arg]


@pytest.mark.asyncio
async def test_explicit_none_current_user_raises_portal_auth_required(
    service: FakePortalMixin,
) -> None:
    """
    If the router explicitly passes current_user=None (e.g. a caller tries
    to bypass the gate by passing a null), the decorator rejects at the
    service layer — never silently allows.
    """
    with pytest.raises(PortalAuthRequired) as exc_info:
        await service.get_dashboard(42, current_user=None)  # type: ignore[arg-type]
    assert "get_dashboard" in exc_info.value.method


@pytest.mark.asyncio
async def test_current_user_without_client_id_raises_portal_auth_required(
    service: FakePortalMixin,
) -> None:
    """
    A context that passes the kwarg but has no `client_id` key is still a
    programming error — we raise PortalAuthRequired to surface the mistake
    loudly instead of permitting a mismatch lookup.
    """
    bad_ctx: ClientContext = {"email": "nobody@example.com"}  # type: ignore[typeddict-item]
    with pytest.raises(PortalAuthRequired):
        await service.get_dashboard(42, current_user=bad_ctx)


# ---------------------------------------------------------------------------
# Scenario 5 — extra positional args don't confuse the decorator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decorator_handles_methods_with_extra_positional_args(
    service: FakePortalMixin,
) -> None:
    """
    `send_message` takes (client_id, content). The decorator must still
    extract client_id correctly when more positionals exist.
    """
    ctx: ClientContext = {"client_id": 42, "email": "c@x.com"}
    result = await service.send_message(42, "hello", current_user=ctx)
    assert result == {"client_id": "42", "content": "hello"}

    # mismatch still denies, regardless of the extra arg
    with pytest.raises(PortalAccessDenied):
        await service.send_message(99, "hello", current_user=ctx)


@pytest.mark.asyncio
async def test_non_int_client_id_is_rejected_as_type_error(
    service: FakePortalMixin,
) -> None:
    """
    If route parsing regressed and passed a string client_id, the decorator
    fails loudly with TypeError instead of doing int/str comparisons that
    might silently deny or silently allow.
    """
    ctx: ClientContext = {"client_id": 42, "email": "c@x.com"}
    with pytest.raises(TypeError):
        await service.get_dashboard("42", current_user=ctx)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Bonus — PortalAccessDenied hierarchy is correct
# ---------------------------------------------------------------------------


def test_portal_access_denied_is_a_forbidden_error() -> None:
    """
    PortalAccessDenied must be a ForbiddenError so existing global
    exception handlers (mapping ForbiddenError → 403) keep working.
    """
    from backend.core.exceptions import ForbiddenError

    exc = PortalAccessDenied(42, actor_email="x@y.com")
    assert isinstance(exc, ForbiddenError)
    assert exc.client_id == 42
    assert exc.details["client_id"] == 42
    assert exc.details["actor_email"] == "x@y.com"
