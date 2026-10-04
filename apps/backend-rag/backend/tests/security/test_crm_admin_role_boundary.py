"""Role boundary on the staff CRM and admin APIs, enforced in the hybrid auth layer.

Client-portal accounts (role ``client``) and external partners (role ``partner``)
authenticate with the same JWT secret as staff. Neither portal uses
``/api/crm/*`` or ``/api/admin/*`` except one operation: the client portal's
document upload to its own practice. ``HybridAuthMiddleware`` therefore answers
403 for those roles on those prefixes before any handler runs, and lets every
other caller through unchanged.

The guilt set is enumerated from the mounted routes (``include_routers``, the
full union both Fly processes draw from), never from a hand-written list, so a
route added later is covered without editing this file. Innocence is asserted
for every caller class that legitimately reaches these prefixes: a staff JWT,
the ``X-Internal-Key`` service caller, an ``X-API-Key`` with the default
``user`` role, and the ``monitoring`` probe.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.middleware.hybrid_auth as hybrid_auth
from backend.app.auth.public_endpoints import find_entry
from backend.app.core.config import settings
from backend.app.deps.database import get_database_pool
from backend.app.routers.auth import create_access_token
from backend.app.setup.route_walk import iter_leaf_routes
from backend.app.setup.router_registration import include_routers
from backend.app.utils.cookie_auth import JWT_COOKIE_NAME

STAFF_API_PREFIXES = ("/api/crm/", "/api/admin/")
ADMIN_CRM_KG_PREFIX = "/api/admin/crm-kg/"
PORTAL_UPLOAD_TEMPLATE = "/api/crm/practices/{practice_id}/upload-client-document"
PORTAL_UPLOAD = "/api/crm/practices/7/upload-client-document"
INTERNAL_KEY = "test-internal-key-for-role-boundary"
API_KEY_USER = "test_api_key_1"
_PARAM = re.compile(r"\{[^}]+\}")


class _Conn:
    def __init__(self, log: list[str]) -> None:
        self._log = log

    def __getattr__(self, name: str):
        async def _call(*_args, **_kwargs):
            self._log.append(name)
            return [] if name == "fetch" else None

        return _call


class _Pool:
    """Stands in for asyncpg; records every use so a test can tell whether a handler ran."""

    def __init__(self) -> None:
        self.log: list[str] = []

    def acquire(self):
        pool = self

        class _Ctx:
            async def __aenter__(self_inner):
                pool.log.append("acquire")
                return _Conn(pool.log)

            async def __aexit__(self_inner, *_exc):
                return False

        return _Ctx()

    def __getattr__(self, name: str):
        return getattr(_Conn(self.log), name)


@pytest.fixture(scope="module")
def app_and_pool() -> tuple[FastAPI, _Pool]:
    app = FastAPI()
    include_routers(app)
    app.add_middleware(hybrid_auth.HybridAuthMiddleware)
    pool = _Pool()
    app.dependency_overrides[get_database_pool] = lambda: pool
    app.state.db_pool = pool
    return app, pool


@pytest.fixture
def client(app_and_pool, monkeypatch) -> TestClient:
    async def _not_revoked(_payload) -> bool:
        return False

    monkeypatch.setattr(hybrid_auth, "is_session_revoked", _not_revoked)
    monkeypatch.setattr(settings, "wa_mirror_internal_key", INTERNAL_KEY, raising=False)
    app_and_pool[1].log.clear()
    return TestClient(app_and_pool[0], raise_server_exceptions=False)


@pytest.fixture
def pool(app_and_pool) -> _Pool:
    return app_and_pool[1]


def _token(role: str, **extra) -> str:
    claims = {"sub": f"{role}-1", "email": f"{role}@example.com", "role": role, **extra}
    return create_access_token(claims, expires_delta=timedelta(hours=1))


def _concrete(path: str) -> str:
    return _PARAM.sub("7", path)


def _guarded_routes(app: FastAPI) -> Iterator[tuple[str, str]]:
    """(method, template) for every non-public route under the staff prefixes.

    Public registry entries are excluded: they return before authentication, so
    a credential neither opens nor closes them."""
    seen: set[tuple[str, str]] = set()
    for route in iter_leaf_routes(app):
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or set()
        if not path or not path.startswith(STAFF_API_PREFIXES):
            continue
        if find_entry(_concrete(path)) is not None:
            continue
        for method in sorted(methods - {"HEAD"}):
            if (method, path) not in seen:
                seen.add((method, path))
                yield method, path


def _all_guarded(app_and_pool) -> list[tuple[str, str]]:
    return list(_guarded_routes(app_and_pool[0]))


def test_enumeration_is_not_blind(app_and_pool) -> None:
    routes = _all_guarded(app_and_pool)
    templates = {t for _, t in routes}
    assert len(routes) >= 50, len(routes)
    assert "/api/crm/clients/{client_id}" in templates
    assert any(t.startswith(ADMIN_CRM_KG_PREFIX) for t in templates)


@pytest.mark.parametrize("role", ["client", "partner"])
def test_portal_roles_are_refused_on_every_staff_route_before_any_handler(
    app_and_pool, client, pool, role
) -> None:
    bearer = {"Authorization": f"Bearer {_token(role, client_id=7)}"}
    wrong: list[str] = []
    for method, template in _all_guarded(app_and_pool):
        if role == "client" and (method, template) == ("POST", PORTAL_UPLOAD_TEMPLATE):
            continue
        r = client.request(method, _concrete(template), headers=bearer)
        if r.status_code != 403 or r.json() != {"detail": hybrid_auth.ROLE_BOUNDARY_DETAIL}:
            wrong.append(f"{method} {template} -> {r.status_code}")
    assert not wrong, wrong
    assert pool.log == []


@pytest.mark.parametrize("role", ["client", "partner"])
def test_portal_roles_are_refused_through_the_session_cookie_too(
    app_and_pool, client, pool, role
) -> None:
    # GET only: a cookie session's mutating request fails CSRF and is 401 before this layer.
    client.cookies.set(JWT_COOKIE_NAME, _token(role, client_id=7))
    wrong: list[str] = []
    for method, template in _all_guarded(app_and_pool):
        if method != "GET":
            continue
        r = client.get(_concrete(template))
        if r.status_code != 403:
            wrong.append(f"{method} {template} -> {r.status_code}")
    assert not wrong, wrong
    assert pool.log == []


def test_role_claim_is_normalised_before_the_boundary(client, pool) -> None:
    r = client.get("/api/crm/clients/7", headers={"Authorization": f"Bearer {_token(' Client ')}"})
    assert r.status_code == 403
    assert pool.log == []


def test_portal_upload_operation_still_reaches_its_handler(client, pool) -> None:
    body = {"required_doc_id": 1, "file": "aGVsbG8=", "file_name": "doc.pdf"}
    r = client.post(
        PORTAL_UPLOAD,
        json=body,
        headers={"Authorization": f"Bearer {_token('client', client_id=7)}"},
    )
    assert r.json().get("detail") != hybrid_auth.ROLE_BOUNDARY_DETAIL, r.text[:200]
    assert pool.log, r.status_code


def test_unauthenticated_requests_keep_the_existing_401(client, pool) -> None:
    assert client.get("/api/crm/clients/7").status_code == 401
    assert client.post(PORTAL_UPLOAD, json={}).status_code == 401
    assert pool.log == []


def test_the_upload_exception_is_scoped_to_its_method_and_template(client, pool) -> None:
    bearer = {"Authorization": f"Bearer {_token('client', client_id=7)}"}
    assert client.get(PORTAL_UPLOAD, headers=bearer).status_code == 403
    assert client.post(f"{PORTAL_UPLOAD}/x", json={}, headers=bearer).status_code == 403
    assert client.post("/api/crm/clients/", json={}, headers=bearer).status_code == 403
    assert pool.log == []


def test_partner_portal_api_is_outside_the_boundary(client) -> None:
    r = client.get("/api/partners/me", headers={"Authorization": f"Bearer {_token('partner')}"})
    assert r.json().get("detail") != hybrid_auth.ROLE_BOUNDARY_DETAIL


INNOCENT_CALLERS = {
    "staff": lambda: {"Authorization": f"Bearer {_token('Consultant')}"},
    "internal_key": lambda: {"X-Internal-Key": INTERNAL_KEY},
    "api_key_user": lambda: {"X-API-Key": API_KEY_USER},
    "monitoring": lambda: {"Authorization": f"Bearer {_token('monitoring')}"},
}


@pytest.mark.parametrize("caller", sorted(INNOCENT_CALLERS))
def test_other_callers_reach_the_handler(client, pool, caller) -> None:
    r = client.get("/api/crm/clients/7", headers=INNOCENT_CALLERS[caller]())
    assert r.json().get("detail") != hybrid_auth.ROLE_BOUNDARY_DETAIL, r.text[:200]
    assert pool.log, (caller, r.status_code)


@pytest.mark.parametrize(
    "role", ["Consultant", "admin", "internal", "user", "monitoring", "", None]
)
def test_other_roles_are_never_refused_on_any_staff_route(app_and_pool, role) -> None:
    refused = [
        f"{method} {template}"
        for method, template in _all_guarded(app_and_pool)
        if hybrid_auth.role_boundary_refuses(method, _concrete(template), role)
    ]
    assert refused == []


def test_api_key_fixture_resolves_to_the_default_user_role() -> None:
    from backend.app.services.api_key_auth import APIKeyAuth

    assert APIKeyAuth().validate_api_key(API_KEY_USER)["role"] == "user"


@pytest.mark.parametrize(
    ("method", "path", "role", "refused"),
    [
        ("GET", "/api/crm/clients/7", "client", True),
        ("GET", "/api/crm/clients/7", "partner", True),
        ("GET", "/api/crm/clients/7", "CLIENT", True),
        ("GET", "/api/crm", "client", True),
        ("GET", "/api/admin/anything", "partner", True),
        ("POST", "/api/crm/practices/7/upload-client-document", "partner", True),
        ("POST", "/api/crm/practices/7/upload-client-document", "client", False),
        ("GET", "/api/crm/clients/7", "Consultant", False),
        ("GET", "/api/crm/clients/7", "internal", False),
        ("GET", "/api/crm/clients/7", "user", False),
        ("GET", "/api/crm/clients/7", "monitoring", False),
        ("GET", "/api/crm/clients/7", "admin", False),
        ("GET", "/api/crm/clients/7", "", False),
        ("GET", "/api/crm/clients/7", None, False),
        ("GET", "/api/crmx/clients/7", "client", False),
        ("GET", "/api/administrator", "client", False),
        ("GET", "/api/portal/me", "client", False),
        ("GET", "/api/partners/me", "partner", False),
    ],
)
def test_boundary_decision(method, path, role, refused) -> None:
    assert hybrid_auth.role_boundary_refuses(method, path, role) is refused
