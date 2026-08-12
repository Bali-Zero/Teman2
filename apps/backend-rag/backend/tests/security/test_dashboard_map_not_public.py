"""The dashboard-map router must never be publicly reachable, and its client
route must never return rows the caller does not own.

THE DEFECT THIS EXISTS TO CATCH (measured live 2026-08-12, not inferred):

`/api/dashboard/map/` was a PREFIX entry in PUBLIC_ENDPOINTS, described as
"Streamlit dashboard — KBLI validation, client geo, risk zones, stats". Every
route the dashboard router mounts therefore inherited public access, and one of
them — `GET /clients/geo` — ran

    SELECT id, full_name, email, phone, status, address
    FROM clients WHERE status = 'active' ORDER BY full_name LIMIT 500

taking only `request: Request`: no principal, no ownership filter. An anonymous
GET against production answered **HTTP 200 with 500 client rows** — 500 names,
274 phones, 164 emails, 110 addresses — from the public internet.

Two properties are pinned here because the fix has two halves and either one
alone leaves a hole:

1. The PREFIX is gone, so no future route on this router is born public. Pinning
   only `/clients/geo` would let the next handler inherit the same exposure —
   the blanket prefix was the defect, not just the one route it exposed. The
   write route `POST /analytics/log-lookup` (which accepted a caller-supplied
   `user_email`, i.e. forgeable attribution) is pinned for the same reason.
2. The ownership filter applies to the AUTHENTICATED caller. Removing the public
   entry alone would still let any team member read all clients from a route
   that exists to draw a map, which is the CRM RBAC rule in CLAUDE.md §13
   ("Team = only assigned_to matches") routed around one layer lower.

INNOCENCE matters as much as guilt here: a test that merely asserted "nothing is
public" would pass on an emptied registry, and a test that asserted "the query
always filters" would pass on a build that blinds admins. Both are checked.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


def _fake_pool_capturing_sql() -> tuple[MagicMock, dict]:
    """A pool whose conn records the SQL and params it was handed."""
    captured: dict = {}

    async def _fetch(sql, *params):
        captured["sql"] = sql
        captured["params"] = params
        return []

    conn = AsyncMock()
    conn.fetch = AsyncMock(side_effect=_fetch)
    acm = MagicMock()
    acm.__aenter__ = AsyncMock(return_value=conn)
    acm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acm)
    return pool, captured


class TestPrefixIsNotPublic:
    """GUILT — the registry must not hand this router out anonymously."""

    def test_clients_geo_is_not_a_public_endpoint(self) -> None:
        from backend.app.auth.public_endpoints import find_entry

        entry = find_entry("/api/dashboard/map/clients/geo")
        assert entry is None, (
            "GET /api/dashboard/map/clients/geo is publicly reachable again. "
            "It returns names, emails, phones and addresses of up to 500 active "
            f"clients. Registry entry that matched: {entry}"
        )

    def test_the_whole_prefix_is_not_public(self) -> None:
        from backend.app.auth.public_endpoints import find_entry

        # The write route: it accepts a caller-supplied `user_email`, so public
        # access means forgeable attribution on top of an unauthenticated write.
        assert find_entry("/api/dashboard/map/analytics/log-lookup") is None
        # And the bare prefix itself, which is how the defect was expressed.
        assert find_entry("/api/dashboard/map/") is None

    def test_a_genuinely_public_endpoint_is_still_public(self) -> None:
        """INNOCENCE — the two assertions above must not be passing because the
        registry was emptied or `find_entry` stopped matching anything."""
        from backend.app.auth.public_endpoints import find_entry

        assert find_entry("/health") is not None


class TestClientsGeoScopesToTheCaller:
    """GUILT + INNOCENCE on the second half of the fix."""

    @pytest.mark.asyncio
    async def test_non_admin_query_is_scoped_to_assigned_to(self) -> None:
        from backend.app.routers.dashboard import get_clients_geo

        pool, captured = _fake_pool_capturing_sql()
        request = MagicMock()
        request.app.state.db_pool = pool

        await get_clients_geo(request, current_user={"email": "Team.Member@balizero.com"})

        assert "assigned_to = $1" in captured["sql"], (
            "a non-admin caller received an unscoped client query — the CRM "
            f"ownership filter is not applied. SQL: {captured['sql']}"
        )
        assert captured["params"] == ("team.member@balizero.com",)

    @pytest.mark.asyncio
    async def test_admin_query_is_not_scoped(self) -> None:
        """INNOCENCE — admins legitimately see the whole book (CLAUDE.md §13);
        a cure that filtered everyone would break the map for its actual users
        and would still pass the guilt test above."""
        from backend.app.routers.dashboard import get_clients_geo

        pool, captured = _fake_pool_capturing_sql()
        request = MagicMock()
        request.app.state.db_pool = pool

        await get_clients_geo(request, current_user={"email": "zero@balizero.com"})

        assert "assigned_to" not in captured["sql"]
        assert captured["params"] == ()

    @pytest.mark.asyncio
    async def test_handler_requires_a_principal(self) -> None:
        """GUILT — the signature must carry a resolved principal, so removing the
        dependency (not just the registry entry) turns this red too."""
        import inspect

        from backend.app.routers.dashboard import get_clients_geo

        params = inspect.signature(get_clients_geo).parameters
        assert "current_user" in params, (
            "get_clients_geo lost its principal — it would answer whoever the "
            "middleware lets through, which is how this became a P0."
        )
