"""Pins the SET of routes that `DEVELOPER_EMAILS` opens — condition C2 of PR #6081.

WHY THIS EXISTS (2026-09-11): the developer grant is per-ADDRESS, not
per-ROUTE-SET. `verify_log_read_access` is wired as the dependency of
`admin_logs.router`, so a sixth route added to that module tomorrow inherits
the allowlist in silence — and a note in a PR body does not turn red when
someone adds it. The grant was declared to the owner as five read-only GETs
over team-activity logs; this test is what makes that declaration binding
instead of descriptive.

It is deliberately a STRUCTURAL test and not a behavioural one: it asserts the
router's own route table, so it fails at collection time for anyone who widens
the perimeter, whatever the new route does. When it goes red the answer is
never "update EXPECTED_ROUTES" — it is to re-declare the surface to the owner
(`operator[business]`, UU PDP) and only then move this set, in the same PR that
adds the route.

Being a guard it ships with GUILT and INNOCENCE
(`.claude/rules/cicatrix-superscar.md` #3): innocence is the real router today;
guilt builds a probe router that adds a sixth route, and another that adds a
POST to a path that already exists, and proves each is caught. Compared as an
ENTITY — the (path, methods) pair — never as a substring of a path, which is
how family #3 bites.
"""

from __future__ import annotations

# The five GETs declared to the owner. `/api-audit` is the only one whose
# table exists in production today (measured 2026-09-11: `activity_logs`,
# `team_interactions`, `v_today_team_activity` and
# `v_team_interactions_summary` are all absent — migration 041b is half
# applied). That is a separate row in the ledger, and it does NOT belong in
# this set: this test pins what the grant REACHES, not what currently answers.
EXPECTED_ROUTES = frozenset(
    {
        ("/api/admin/logs/activity", ("GET",)),
        ("/api/admin/logs/interactions", ("GET",)),
        ("/api/admin/logs/api-audit", ("GET",)),
        ("/api/admin/logs/summary/today", ("GET",)),
        ("/api/admin/logs/summary/interactions", ("GET",)),
    }
)


def _route_set(router) -> frozenset:
    """(path, sorted methods) for every real HTTP route on a router.

    HEAD is dropped: FastAPI/Starlette add it alongside GET for free, and it
    is not a surface anyone grants. Routes without `methods` (mounts,
    websockets) would be a perimeter change of their own and are surfaced by
    being absent from the pairs rather than silently skipped — none exist on
    this router today.
    """
    return frozenset(
        (r.path, tuple(sorted(m for m in r.methods if m != "HEAD")))
        for r in router.routes
        if getattr(r, "methods", None)
    )


def test_the_granted_route_set_is_exactly_the_five_declared_gets() -> None:
    from backend.app.routers import admin_logs

    assert _route_set(admin_logs.router) == EXPECTED_ROUTES


def test_every_granted_route_is_read_only() -> None:
    """No write verb may live behind this grant, whatever the path."""
    from backend.app.routers import admin_logs

    verbs = {m for _, methods in _route_set(admin_logs.router) for m in methods}
    assert verbs == {"GET"}


def _probe_like_the_real_router():
    """A router carrying the same five paths, independent of the real one.

    Built fresh rather than by mutating `admin_logs.router`, which is module
    state shared with every other test in the suite.
    """
    from fastapi import APIRouter

    probe = APIRouter(prefix="/api/admin/logs")
    for path, _ in sorted(EXPECTED_ROUTES):
        probe.add_api_route(
            path.removeprefix("/api/admin/logs"),
            lambda: None,
            methods=["GET"],
        )
    return probe


def test_the_probe_router_is_a_faithful_stand_in() -> None:
    """Innocence for the guilt cases below: the probe must start out equal."""
    assert _route_set(_probe_like_the_real_router()) == EXPECTED_ROUTES


def test_a_sixth_route_is_caught() -> None:
    probe = _probe_like_the_real_router()
    probe.add_api_route("/exports", lambda: None, methods=["GET"])

    assert _route_set(probe) != EXPECTED_ROUTES


def test_a_write_verb_on_an_already_granted_path_is_caught() -> None:
    """The OVER-match case: the path is already in the set, the verb is not."""
    probe = _probe_like_the_real_router()
    probe.add_api_route("/activity", lambda: None, methods=["POST"])

    assert _route_set(probe) != EXPECTED_ROUTES
    assert _route_set(probe) - EXPECTED_ROUTES == frozenset(
        {("/api/admin/logs/activity", ("POST",))}
    )


def test_a_removed_route_is_caught_too() -> None:
    """Narrowing is a declaration change as much as widening is."""
    probe = _probe_like_the_real_router()
    probe.routes = [r for r in probe.routes if r.path.endswith("/api-audit") is False]

    assert _route_set(probe) != EXPECTED_ROUTES
