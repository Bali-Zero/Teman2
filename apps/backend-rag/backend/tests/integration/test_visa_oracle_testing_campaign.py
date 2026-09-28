"""Real PostgreSQL concurrency/ownership checks; only an isolated local QA socket."""

import asyncio
import base64
import io
import os
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import asyncpg
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from PIL import Image

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.routers import visa_oracle_testing as campaign_router
from backend.app.routers.visa_oracle_testing import router


def qa_connection():
    socket = os.getenv("ORACLE_TEST_SOCKET", "")
    if Path(socket).name.startswith("oracle-testing-qa-"):
        return {"host": socket, "database": "oracle_testing_qa"}
    dsn = os.getenv("TEST_DATABASE_URL", "")
    parsed = urlparse(dsn)
    # Explicit CI service only, never a production/Fly database by accident.
    if (
        os.getenv("CI")
        and parsed.hostname in {"localhost", "127.0.0.1", "postgres"}
        and parsed.path == "/nuzantara_test"
    ):
        return {"dsn": dsn}
    pytest.skip("Requires isolated QA socket or the declared CI nuzantara_test database")


@pytest_asyncio.fixture
async def setup(monkeypatch):
    connection = qa_connection()
    monkeypatch.setattr(campaign_router, "bali_today", lambda: "2026-09-28")
    schema = "oracle_qa_" + uuid4().hex
    admin = await asyncpg.connect(**connection)
    await admin.execute(f'CREATE SCHEMA "{schema}"')
    pool = await asyncpg.create_pool(**connection, server_settings={"search_path": schema})
    async with pool.acquire() as conn:
        await conn.execute(
            "CREATE TABLE team_members(id TEXT PRIMARY KEY,email TEXT,role TEXT,active BOOLEAN,full_name TEXT,name TEXT)"
        )
        await conn.executemany(
            "INSERT INTO team_members VALUES($1,$2,$3,true,$1,$1)",
            [
                ("a", "tester-a@example.invalid", "team"),
                ("b", "tester-b@example.invalid", "team"),
                ("o", "zero@balizero.com", "admin"),
                ("c", "fixture-client@example.invalid", "client"),
            ],
        )
        migration = Path(__file__).parents[2] / "db/migrations_v2/323_visa_oracle_team_testing.sql"
        await conn.execute(migration.read_text().split("-- === ROLLBACK ===")[0])
        await conn.execute("UPDATE visa_oracle_test_slots SET member_id='a' WHERE slot='T01'")
        await conn.execute(
            "UPDATE visa_oracle_test_slots SET member_id='b',reviewer=true WHERE slot='T02'"
        )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_database_pool] = lambda: pool

    def client(member="a", role="team"):
        addresses = {
            "a": "tester-a@example.invalid",
            "b": "tester-b@example.invalid",
            "o": "zero@balizero.com",
            "c": "fixture-client@example.invalid",
        }
        app.dependency_overrides[get_current_user] = lambda: {
            "email": addresses[member],
            "role": role,
        }
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://qa.invalid"
        )

    yield app, pool, client
    await pool.close()
    await admin.execute(f'DROP SCHEMA "{schema}" CASCADE')
    await admin.close()


def expected(text="Needs expert assessment before a conclusion"):
    return {
        "text": text,
        "basis": "needs_review",
        "reference": "",
        "browser": "Firefox",
        "device": "desktop",
        "displayed_version": "unknown",
        "synthetic_only": True,
    }


def result(**changes):
    return {
        "steps": "Entered the assigned synthetic facts in order",
        "actual_state": "blocked",
        "actual": "Next step unavailable after the stated selection",
        "comment": "Inspect required field validation on this step",
        "source_notes": "No reference shown",
        "uncertainty": "Unknown option not shown",
        "category": "navigation",
        "severity": "medium",
        "certainty": "observation",
        "reproducibility": "not_retried",
        "synthetic_only": True,
        "submit": True,
        **changes,
    }


@pytest.mark.asyncio
async def test_authentication_and_real_staff_membership(setup):
    app, pool, make_client = setup
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://qa.invalid"
    ) as c:
        assert (await c.get("/api/visa-oracle/testing")).status_code == 401
    for role in ("client", "monitoring", "partner", "user"):
        async with make_client("a", role) as c:
            assert (await c.get("/api/visa-oracle/testing")).status_code == 403
    async with pool.acquire() as conn:
        await conn.execute("UPDATE team_members SET active=false WHERE id='a'")
    async with make_client() as c:
        assert (await c.get("/api/visa-oracle/testing")).status_code == 403


@pytest.mark.asyncio
async def test_competing_expectations_cannot_replace_each_other(setup):
    _, pool, make_client = setup
    async with make_client() as c:
        replies = await asyncio.gather(
            *[
                c.post("/api/visa-oracle/testing/D1-T01-0/start", json=expected(t))
                for t in ("First preregistered expectation", "Different preregistered expectation")
            ]
        )
        assert sorted(r.status_code for r in replies) == [200, 409]
        page = (await c.get("/api/visa-oracle/testing")).json()
        record = page["assignments"][0]["record"]
        assert record["expected"]["text"] in {
            "First preregistered expectation",
            "Different preregistered expectation",
        }
        assert page["counts"]["started"] == 1
        assert (
            await c.post("/api/visa-oracle/testing/D1-T02-0/start", json=expected())
        ).status_code == 403
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM visa_oracle_test_runs") == 1


@pytest.mark.asyncio
async def test_durable_draft_submission_idempotency_and_independent_review(setup):
    _, pool, make_client = setup
    path = "/api/visa-oracle/testing/D1-T01-0"
    async with make_client() as c:
        assert (await c.put(path + "/result", json=result())).status_code == 409
        assert (await c.post(path + "/start", json=expected())).status_code == 200
        assert (await c.put(path + "/result", json=result(submit=False))).status_code == 200
        data = (await c.get("/api/visa-oracle/testing")).json()
        assert data["assignments"][0]["record"]["result"]["actual"] == result()["actual"]
        assert data["counts"]["submitted"] == 0
        assert (await c.put(path + "/result", json=result())).status_code == 200
        first_time = (await c.get("/api/visa-oracle/testing")).json()["assignments"][0]["record"][
            "submitted_at"
        ]
        assert (await c.put(path + "/result", json=result())).status_code == 200
        assert (await c.get("/api/visa-oracle/testing")).json()["assignments"][0]["record"][
            "submitted_at"
        ] == first_time
        assert (
            await c.put(path + "/result", json=result(actual="Conflicting later result"))
        ).status_code == 409
        assert (await c.get("/api/visa-oracle/testing/export")).status_code == 403
    async with make_client("b") as c:
        assert (await c.put(path + "/result", json=result())).status_code == 403
        blind = (await c.get("/api/visa-oracle/testing")).json()
        assert "expected" not in blind["assignments"][0]["record"]
        assert (await c.get(path + "/screenshot")).status_code == 404
        assert (
            await c.patch(
                path + "/review",
                json={"verdict": "not_issue", "comment": "Premature peer review attempt"},
            )
        ).status_code == 409
        for index in range(5):
            assert (
                await c.post(f"/api/visa-oracle/testing/D1-T02-{index}/start", json=expected())
            ).status_code == 200
        bad = {
            "verdict": "confirmed_issue",
            "comment": "Independent finding checked",
            "reproduced": True,
        }
        assert (await c.patch(path + "/review", json=bad)).status_code == 422
        good = {
            **bad,
            "reproduction_evidence": "Repeated same fixture on browser two; capture qa-02",
        }
        assert (await c.patch(path + "/review", json=good)).status_code == 200
        data = (await c.get("/api/visa-oracle/testing/export")).json()
        assert data["counts"] == {
            "planned": 150,
            "started": 6,
            "submitted": 1,
            "reproduced": 1,
            "reviewed": 1,
            "reached": 0,
            "blocked": 1,
        }
        assert "staff_candidates" not in data
        assert "reviewer_member_id" not in data["assignments"][0]["record"]["review"]
    async with make_client("o", "admin") as c:
        assert (
            await c.put("/api/visa-oracle/testing/slots/T01", json={"member_id": "b"})
        ).status_code == 409
        assert (
            await c.put("/api/visa-oracle/testing/slots/T03", json={"member_id": "c"})
        ).status_code == 422


@pytest.mark.asyncio
async def test_blind_results_and_self_review(setup):
    _, pool, make_client = setup
    path = "/api/visa-oracle/testing/D1-T01-0"
    async with make_client() as c:
        await c.post(path + "/start", json=expected())
        await c.put(path + "/result", json=result())
    async with pool.acquire() as conn:
        await conn.execute("UPDATE visa_oracle_test_slots SET reviewer=false WHERE slot='T02'")
        await conn.execute("UPDATE visa_oracle_test_slots SET reviewer=true WHERE slot='T01'")
    async with make_client("b") as c:
        data = (await c.get("/api/visa-oracle/testing")).json()
        assert "expected" not in data["assignments"][0]["record"]
        assert (await c.get(path + "/screenshot")).status_code == 404
    async with make_client() as c:
        response = await c.patch(
            path + "/review",
            json={"verdict": "not_issue", "comment": "Trying to approve my own test"},
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_private_evidence_is_separate_removable_and_not_loaded_in_lists(setup):
    _, pool, make_client = setup
    image = io.BytesIO()
    Image.new("RGB", (4, 4), color="white").save(image, format="JPEG")
    raw = image.getvalue()
    encoded = base64.b64encode(raw).decode()
    path = "/api/visa-oracle/testing/D1-T01-0"
    async with make_client() as c:
        assert (await c.post(path + "/start", json=expected())).status_code == 200
        assert (
            await c.put(
                path + "/result",
                json=result(screenshot_base64=encoded, submit=False, reproducibility="same"),
            )
        ).status_code == 200
        assert (
            await c.put(path + "/result", json=result(reproducibility="same"))
        ).status_code == 200
        picture = await c.get(path + "/screenshot")
        assert picture.status_code == 200 and picture.content == raw
        assert picture.headers["content-type"] == "image/jpeg"
        assert picture.headers["cache-control"] == "no-store"
        page = await c.get("/api/visa-oracle/testing")
        assert encoded not in page.text
        assert page.json()["assignments"][0]["record"]["result"]["screenshot_available"] is True
    async with pool.acquire() as conn:
        assert await conn.fetchval(
            "SELECT NOT (result ? 'screenshot_base64') FROM visa_oracle_test_runs WHERE assignment_id='D1-T01-0'"
        )
    async with make_client("b") as c:
        assert (await c.get(path + "/screenshot")).status_code == 404
        assert (await c.delete(path + "/screenshot")).status_code == 404
    async with make_client() as c:
        assert (await c.delete(path + "/screenshot")).status_code == 200
        assert (await c.get(path + "/screenshot")).status_code == 404
        page = (await c.get("/api/visa-oracle/testing")).json()
        record = page["assignments"][0]["record"]
        assert record["status"] == "submitted" and record["result"]["evidence_removed_at"]
        assert "evidence_removed_by" not in record["result"]


@pytest.mark.asyncio
async def test_date_sensitive_cases_cannot_be_started_on_a_different_day(setup, monkeypatch):
    _, _, make_client = setup
    monkeypatch.setattr(campaign_router, "bali_today", lambda: "2026-10-02")
    async with make_client() as c:
        assert (
            await c.post("/api/visa-oracle/testing/D3-T01-1/start", json=expected())
        ).status_code == 409
        data = (await c.get("/api/visa-oracle/testing")).json()
        assert not any(a["can_start"] for a in data["assignments"] if a["day"] == "2026-09-30")
