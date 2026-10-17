"""Personal duties use the live source records and never create a second state."""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.core.config import settings
from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.routers import crm_enhanced_alerts, crm_practices

URL = "/api/crm/member-obligations"
MEMBER = {"email": "member-a@example.test", "role": "Consultant"}
ADMIN = {"email": "administrator@example.test", "role": "admin"}
SUPERVISOR = {"email": "supervisor@example.test", "role": "Tax Manager"}
ITEM_KEYS = {
    "kind",
    "client_id",
    "client_name",
    "practice_id",
    "practice_type_name",
    "status",
    "created_at",
    "age_days",
    "passport_expiry",
    "days_left",
    "assigned_to",
    "can_open_process",
}


def client(pool=None, user=None):
    app = FastAPI()
    app.include_router(crm_enhanced_alerts.router)
    app.include_router(crm_practices.router)
    app.dependency_overrides[get_current_user] = lambda: MEMBER if user is None else user
    app.dependency_overrides[get_database_pool] = lambda: pool
    return AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    )


@pytest.fixture(autouse=True)
def explicit_supervisor_grant(monkeypatch):
    monkeypatch.setattr(settings, "member_obligations_supervisor_emails", "supervisor@example.test")


@pytest_asyncio.fixture
async def db():
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL required for real PostgreSQL duties proof")
    conn = await asyncpg.connect(dsn)
    name = await conn.fetchval("SELECT current_database()")
    if not re.search(r"_test(?:_run_[0-9]+_[0-9]+)?(?:_gw[0-9]+)?$", name):
        await conn.close()
        pytest.fail("A test database or isolated test worker is required")
    schema = "member_duties_" + uuid4().hex
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    pool = await asyncpg.create_pool(
        dsn, min_size=1, max_size=2, server_settings={"search_path": schema}
    )
    try:
        async with pool.acquire() as c:
            await c.execute("""
                CREATE TABLE clients (
                    id integer PRIMARY KEY, full_name text, assigned_to text,
                    created_by text, passport_expiry date, deleted_at timestamptz,
                    email text DEFAULT 'private@example.test', phone text DEFAULT 'private-fixture',
                    passport_number text DEFAULT 'private-passport-fixture'
                );
                CREATE TABLE practice_types (
                    id integer PRIMARY KEY, name text, code text, category text,
                    required_documents jsonb DEFAULT '[]'
                );
                CREATE TABLE practices (
                    id integer PRIMARY KEY, client_id integer REFERENCES clients(id),
                    practice_type_id integer REFERENCES practice_types(id), status text,
                    assigned_to text, created_by text, created_at timestamptz,
                    notes text DEFAULT 'private fixture note', quoted_price numeric DEFAULT 123
                );
                CREATE TABLE team_members (
                    id integer PRIMARY KEY, email text, full_name text, name text, active boolean
                );
                INSERT INTO team_members VALUES
                    (1,'member-a@example.test','Member A','Member A',true),
                    (2,'member-b@example.test','Member B','Member B',true);
                INSERT INTO practice_types (id,name,code,category) VALUES (1,'Fixture service','fixture','visa');
                INSERT INTO clients (id,full_name,assigned_to,passport_expiry,deleted_at) VALUES
                    (1,'Client fixture A','member-a@example.test',CURRENT_DATE+30,NULL),
                    (2,'Client fixture B','member-b@example.test',CURRENT_DATE-1,NULL),
                    (3,'Unassigned fixture',NULL,CURRENT_DATE+40,NULL),
                    (4,'Deleted fixture','member-a@example.test',CURRENT_DATE-10,NOW()),
                    (5,'Outside window','member-a@example.test',CURRENT_DATE+91,NULL),
                    (6,'Boundary fixture','member-a@example.test',CURRENT_DATE+90,NULL),
                    (7,'No date fixture','member-a@example.test',NULL,NULL),
                    (8,'Today fixture','member-a@example.test',CURRENT_DATE,NULL),
                    (9,NULL,'member-a@example.test',CURRENT_DATE-3,NULL);
                INSERT INTO practices
                    (id,client_id,practice_type_id,status,assigned_to,created_by,created_at) VALUES
                    (101,1,1,'on_process','member-a@example.test','member-a@example.test',NOW()-INTERVAL '15 days'),
                    (102,2,1,'waiting_documents','member-b@example.test','member-b@example.test',NOW()-INTERVAL '20 days'),
                    (103,3,1,'inquiry',NULL,NULL,NOW()-INTERVAL '30 days'),
                    (104,4,1,'inquiry','member-a@example.test',NULL,NOW()-INTERVAL '20 days'),
                    (105,1,1,'completed','member-a@example.test',NULL,NOW()-INTERVAL '20 days'),
                    (106,1,1,'cancelled','member-a@example.test',NULL,NOW()-INTERVAL '20 days'),
                    (107,1,1,'on_process','member-a@example.test',NULL,NOW()-INTERVAL '13 days'),
                    (108,2,1,'waiting_documents','MEMBER-A@example.test','member-b@example.test',NOW()-INTERVAL '16 days'),
                    (109,1,1,'on_process','member-b@example.test',NULL,NOW()-INTERVAL '17 days'),
                    (110,1,1,'in_progress','member-a@example.test',NULL,NOW()-INTERVAL '15 days'),
                    (111,1,1,'inquiry','member-a@example.test',NULL,NOW()-INTERVAL '14 days'+INTERVAL '1 minute'),
                    (112,1,1,'inquiry','member-a@example.test',NULL,NOW()-INTERVAL '14 days'-INTERVAL '1 minute');
            """)
        yield pool
    finally:
        await pool.close()
        await conn.execute(f'DROP SCHEMA "{schema}" CASCADE')
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query", ["?scope=team", "?assigned_to=member-b%40example.test", "?assigned_to=__unassigned__"]
)
async def test_member_cannot_override_ownership(query):
    async with client() as http:
        response = await http.get(URL + query)
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["client", "partner", "monitoring", "internal", "public", ""])
async def test_allowlisted_non_team_identity_is_still_rejected(role):
    async with client(user={**SUPERVISOR, "role": role}) as http:
        response = await http.get(URL + "?scope=team")
    assert response.status_code == 403


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, frozenset()),
        (" ,  ", frozenset()),
        (
            " A@example.test, a@EXAMPLE.test ,b@example.test ",
            frozenset({"a@example.test", "b@example.test"}),
        ),
    ],
)
def test_supervisor_grant_has_no_fallback_and_normalizes(raw, expected, monkeypatch):
    monkeypatch.setattr(settings, "member_obligations_supervisor_emails", raw)
    assert settings.member_obligations_supervisor_emails_set == expected


def test_additional_grant_is_confined_to_one_read_only_endpoint():
    backend = Path(__file__).resolve().parents[3]
    consumers = []
    for path in (backend / "app").rglob("*.py"):
        source = path.read_text()
        if "member_obligations_supervisor_emails_set" not in source:
            continue
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                isinstance(child, ast.Attribute)
                and child.attr == "member_obligations_supervisor_emails_set"
                for child in ast.walk(node)
            ):
                consumers.append((str(path.relative_to(backend)), node.name))
    assert consumers == [("app/routers/crm_enhanced_alerts.py", "get_member_obligations")]
    routes = [
        route
        for route in crm_enhanced_alerts.router.routes
        if route.endpoint is crm_enhanced_alerts.get_member_obligations
    ]
    assert [(route.path, route.methods) for route in routes] == [(URL, {"GET"})]


@pytest.mark.asyncio
async def test_personal_rules_use_source_ownership_boundaries_and_fixed_fields(db):
    async with client(db) as http:
        response = await http.get(URL)
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["total"], body["passport_count"], body["process_count"]) == (8, 4, 4)
    assert body["can_view_team"] is False
    assert body["can_view_register"] is False
    assert {row["client_id"] for row in body["items"] if row["kind"] == "passport"} == {1, 6, 8, 9}
    assert {row["practice_id"] for row in body["items"] if row["kind"] == "process"} == {
        101,
        108,
        110,
        112,
    }
    assert all(set(row) == ITEM_KEYS for row in body["items"])
    assert all(row["assigned_to"] == MEMBER["email"] for row in body["items"])
    assert all(row["can_open_process"] for row in body["items"] if row["kind"] == "process")
    assert body["owners"] == [{"email": MEMBER["email"], "name": "Member A", "total": 8}]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["passport", "process"])
@pytest.mark.parametrize("sentinel", ["-infinity", "infinity"])
async def test_nonfinite_source_dates_do_not_break_scopes_or_pagination(db, kind, sentinel):
    async with db.acquire() as conn:
        if kind == "passport":
            await conn.execute(
                "INSERT INTO clients (id,full_name,assigned_to,passport_expiry) "
                "VALUES (20,'Nonfinite date fixture',$1,$2::text::date)",
                MEMBER["email"],
                sentinel,
            )
        else:
            await conn.execute(
                "INSERT INTO practices "
                "(id,client_id,practice_type_id,status,assigned_to,created_by,created_at) "
                "VALUES (120,1,1,'on_process',$1,$1,$2::text::timestamptz)",
                MEMBER["email"],
                sentinel,
            )
    async with client(db) as http:
        personal = await http.get(URL)
    async with client(db, ADMIN) as http:
        team = await http.get(URL + "?scope=team")
        page = await http.get(URL + "?scope=team&limit=1&offset=1")
        filtered = await http.get(URL + "?scope=team&assigned_to=member-a%40example.test")
    for response, expected in [(personal, (8, 4, 4)), (team, (13, 6, 7))]:
        assert response.status_code == 200, response.text
        body = response.json()
        assert (body["total"], body["passport_count"], body["process_count"]) == expected
        assert sum(owner["total"] for owner in body["owners"]) == body["total"]
    assert page.status_code == filtered.status_code == 200
    assert page.json()["total"] == 13 and len(page.json()["items"]) == 1
    assert filtered.json()["total"] == 8


@pytest.mark.asyncio
async def test_admin_defaults_to_personal_and_team_counts_paginate(db):
    async with client(db, ADMIN) as http:
        personal = (await http.get(URL)).json()
        first = (await http.get(URL + "?scope=team&limit=3")).json()
        second = (await http.get(URL + "?scope=team&limit=3&offset=3")).json()
        beyond = (await http.get(URL + "?scope=team&offset=100")).json()
    assert personal["total"] == 0
    assert personal["can_view_team"] is True
    assert personal["can_view_register"] is True
    assert (first["total"], first["passport_count"], first["process_count"]) == (13, 6, 7)
    assert len(first["items"]) == len(second["items"]) == 3

    def key(row):
        return row["kind"], row["practice_id"] or row["client_id"]

    assert {key(row) for row in first["items"]}.isdisjoint({key(row) for row in second["items"]})
    assert beyond["items"] == [] and beyond["total"] == 13


@pytest.mark.asyncio
async def test_read_only_supervisor_has_overview_not_extra_detail_access(db):
    async with client(db, SUPERVISOR) as http:
        body = (await http.get(URL + "?scope=team")).json()
        detail = await http.get("/api/crm/practices/108")
        unassigned = (await http.get(URL + "?scope=team&assigned_to=__unassigned__")).json()
        member_b = (await http.get(URL + "?scope=team&assigned_to=member-b%40example.test")).json()
    assert body["can_view_team"] is True and body["can_view_register"] is False
    assert body["total"] == 13
    assert all(row["can_open_process"] is False for row in body["items"])
    assert detail.status_code == 404
    assert unassigned["total"] == 2 and all(
        row["assigned_to"] is None for row in unassigned["items"]
    )
    assert member_b["total"] == 3
    assert sum(owner["total"] for owner in member_b["owners"]) == 13


@pytest.mark.asyncio
async def test_source_changes_clear_items_without_another_completion_write(db):
    async with db.acquire() as conn:
        await conn.execute("UPDATE clients SET passport_expiry = CURRENT_DATE + 400 WHERE id=1")
        await conn.execute("UPDATE practices SET status='completed' WHERE id=101")
        await conn.execute("UPDATE practices SET status='cancelled' WHERE id=108")
    async with client(db) as http:
        body = (await http.get(URL)).json()
    assert body["total"] == 5
    assert all(not (row["kind"] == "passport" and row["client_id"] == 1) for row in body["items"])
    assert all(row["practice_id"] not in {101, 108} for row in body["items"])


@pytest.mark.asyncio
async def test_assignee_can_open_reassigned_practice_without_contact_leak(db):
    async with client(db) as http:
        response = await http.get("/api/crm/practices/108")
    assert response.status_code == 200, response.text
    assert response.json()["id"] == 108
    assert not set(crm_practices.PRACTICE_CLIENT_CONTACT_FIELDS).intersection(response.json())


@pytest.mark.asyncio
async def test_unrelated_member_still_cannot_open_practice(db):
    async with client(db, {"email": "unrelated@example.test", "role": "Consultant"}) as http:
        response = await http.get("/api/crm/practices/108")
    assert response.status_code == 404
