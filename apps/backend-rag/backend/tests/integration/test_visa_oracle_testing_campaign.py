"""Real PostgreSQL checks against isolated QA sockets or declared local CI databases."""

import asyncio
import base64
import io
import os
import re
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
        and parsed.scheme in {"postgres", "postgresql"}
        and parsed.hostname in {"localhost", "127.0.0.1", "postgres"}
        and re.fullmatch(r"/nuzantara_test(?:_gw[0-9]+)?", parsed.path)
        and not parsed.query
        and not parsed.fragment
    ):
        return {"dsn": dsn}
    pytest.skip("Requires isolated QA socket or declared local CI base/worker test database")


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "postgres"])
@pytest.mark.parametrize(
    "database", ["nuzantara_test", "nuzantara_test_gw0", "nuzantara_test_gw12"]
)
def test_qa_connection_accepts_local_ci_base_and_worker_databases(monkeypatch, host, database):
    monkeypatch.delenv("ORACLE_TEST_SOCKET", raising=False)
    monkeypatch.setenv("CI", "true")
    dsn = f"postgresql://{host}:49433/{database}"
    monkeypatch.setenv("TEST_DATABASE_URL", dsn)
    try:
        connection = qa_connection()
    except pytest.skip.Exception:
        pytest.fail("The declared CI base/worker database must execute, never skip")
    assert connection == {"dsn": dsn}


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://localhost/nuzantara",
        "postgresql://localhost/nuzantara_dev",
        "postgresql://localhost/nuzantara_test_gw0_prod",
        "postgresql://localhost/nuzantara_test_gw",
        "postgresql://localhost/nuzantara_test_gw-1",
        "postgresql://localhost/nuzantara_test_gw0_gw1",
        "postgresql://localhost/nuzantara_test_xdist_template",
        "postgresql://remote.example.invalid/nuzantara_test_gw0",
        "postgresql://localhost.example.invalid/nuzantara_test",
        "https://localhost/nuzantara_test",
        "postgresql://localhost/nuzantara_test?host=remote.example.invalid",
        "postgresql://localhost/nuzantara_test?dbname=production",
        "postgresql://localhost/nuzantara_test?database=production",
        "postgresql://localhost/nuzantara_test#production",
    ],
)
def test_qa_connection_rejects_undeclared_or_overridden_ci_database(monkeypatch, dsn):
    monkeypatch.delenv("ORACLE_TEST_SOCKET", raising=False)
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("TEST_DATABASE_URL", dsn)
    with pytest.raises(pytest.skip.Exception):
        qa_connection()


def test_qa_connection_requires_ci_for_tcp_database(monkeypatch):
    monkeypatch.delenv("ORACLE_TEST_SOCKET", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://localhost/nuzantara_test_gw0")
    with pytest.raises(pytest.skip.Exception):
        qa_connection()


@pytest_asyncio.fixture
async def setup(monkeypatch):
    connection = qa_connection()
    monkeypatch.setattr(campaign_router, "bali_today", lambda: "2026-09-30")
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


async def lock_personal_day(client, slot="T01"):
    for index in range(5):
        response = await client.post(
            f"/api/visa-oracle/testing/D1-{slot}-{index}/start", json=expected()
        )
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_connection_targets_declared_isolated_database(setup):
    _, pool, _ = setup
    connection = qa_connection()
    async with pool.acquire() as conn:
        actual_database = await conn.fetchval("SELECT current_database()")
    if "dsn" in connection:
        assert actual_database == urlparse(connection["dsn"]).path.lstrip("/")
        worker = os.getenv("PYTEST_XDIST_WORKER")
        if worker:
            assert actual_database == f"nuzantara_test_{worker}"
    else:
        assert actual_database == "oracle_testing_qa"


@pytest.mark.asyncio
@pytest.mark.parametrize("submit", [False, True])
async def test_results_wait_for_all_five_personal_expectations(setup, submit):
    _, pool, make_client = setup
    path = "/api/visa-oracle/testing/D1-T01-0"
    async with make_client() as c:
        for index in range(4):
            assert (
                await c.post(f"/api/visa-oracle/testing/D1-T01-{index}/start", json=expected())
            ).status_code == 200
        before = (await c.get("/api/visa-oracle/testing")).json()
        assert not any(a["can_record_results"] for a in before["assignments"])
        assert (await c.put(path + "/result", json=result(submit=submit))).status_code == 409
        async with pool.acquire() as conn:
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM visa_oracle_test_runs WHERE result IS NOT NULL"
                )
                == 0
            )
        assert (
            await c.post("/api/visa-oracle/testing/D1-T01-4/start", json=expected())
        ).status_code == 200
        after = (await c.get("/api/visa-oracle/testing")).json()
        for case in after["assignments"]:
            assert case["can_record_results"] is (
                case["slot"] == "T01" and case["day"] == "2026-09-30"
            )
        assert (await c.put(path + "/result", json=result(submit=submit))).status_code == 200


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
async def test_durable_draft_submission_idempotency_and_self_review(setup):
    """Owner decision 2026-09-30: the tester who ran a case also reviews it.

    Cross-member review is not wanted, so `b` reviewing `a`'s test is now a guilt
    case (403) instead of the old peer-review flow, and `a` self-reviewing their
    own submitted test is the innocence case (200).
    """
    _, pool, make_client = setup
    path = "/api/visa-oracle/testing/D1-T01-0"
    async with make_client() as c:
        assert (await c.put(path + "/result", json=result())).status_code == 409
        await lock_personal_day(c)
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
        # Innocence: `a` holds a slot, so self-review is available (export requires it).
        assert (await c.get("/api/visa-oracle/testing/export")).status_code == 200
        bad = {
            "verdict": "confirmed_issue",
            "comment": "Self-reviewed finding checked",
            "reproduced": True,
        }
        assert (await c.patch(path + "/review", json=bad)).status_code == 422
        good = {
            **bad,
            "reproduction_evidence": "Repeated same fixture on browser two; capture qa-02",
        }
        assert (await c.patch(path + "/review", json=good)).status_code == 200
        data = (await c.get("/api/visa-oracle/testing/export")).json()
        first_review = data["assignments"][0]["record"]["review"]
        assert (await c.patch(path + "/review", json=good)).status_code == 200
        retry = (await c.get("/api/visa-oracle/testing/export")).json()
        assert retry["assignments"][0]["record"]["review"] == first_review
        assert retry["counts"]["reviewed"] == 1
        assert (
            await c.patch(
                path + "/review", json={**good, "comment": "Changed review after acceptance"}
            )
        ).status_code == 409
        assert data["counts"] == {
            "planned": 90,
            "started": 5,
            "submitted": 1,
            "reproduced": 1,
            "reviewed": 1,
            "reached": 0,
            "blocked": 1,
        }
        assert "staff_candidates" not in data
        assert "reviewer_member_id" not in data["assignments"][0]["record"]["review"]
    async with make_client("b") as c:
        # Guilt: `b` cannot write `a`'s record, nor review it — cross-member review
        # is rejected even though `b` also holds a slot and can review their OWN.
        assert (await c.put(path + "/result", json=result())).status_code == 403
        assert (
            await c.patch(
                path + "/review",
                json={"verdict": "not_issue", "comment": "Cross-member review attempt"},
            )
        ).status_code == 403
        blind = (await c.get("/api/visa-oracle/testing")).json()
        assert "expected" not in blind["assignments"][0]["record"]
        assert (await c.get(path + "/screenshot")).status_code == 404
        # `b` can still reach export (their own slot grants can_review), but the
        # peer record stays blind: no leaked review/expected content for `a`.
        blind_export = (await c.get("/api/visa-oracle/testing/export")).json()
        assert "expected" not in blind_export["assignments"][0]["record"]
        assert "review" not in blind_export["assignments"][0]["record"]
    async with make_client("o", "admin") as c:
        assert (
            await c.put("/api/visa-oracle/testing/slots/T01", json={"member_id": "b"})
        ).status_code == 409
        assert (
            await c.put("/api/visa-oracle/testing/slots/T03", json={"member_id": "c"})
        ).status_code == 422


@pytest.mark.asyncio
async def test_self_review_ignores_the_reviewer_slot_flag(setup):
    """The `reviewer` slot column is vestigial under self-review (owner decision
    2026-09-30, ignored rather than repurposed — see visa_oracle_testing.py's
    `actor()`). Set it to TRUE on both the owner's and the outsider's slot and
    confirm authorization still tracks record ownership only, never this column.
    """
    _, pool, make_client = setup
    path = "/api/visa-oracle/testing/D1-T01-0"
    async with make_client() as c:
        await lock_personal_day(c)
        assert (await c.put(path + "/result", json=result())).status_code == 200
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE visa_oracle_test_slots SET reviewer=true WHERE slot IN ('T01','T02')"
        )
    async with make_client("b") as c:
        # Guilt: reviewer=true on `b`'s own slot still does not grant cross-member
        # review of `a`'s test — the flag was never what gated this.
        assert (
            await c.patch(
                path + "/review",
                json={"verdict": "not_issue", "comment": "Cross-member review attempt"},
            )
        ).status_code == 403
    async with make_client() as c:
        # Innocence: reviewer=true on `a`'s own slot is not required either —
        # self-review works the same regardless of this column's value.
        response = await c.patch(
            path + "/review",
            json={"verdict": "not_issue", "comment": "Reviewing my own submitted test"},
        )
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_private_evidence_is_separate_removable_and_not_loaded_in_lists(setup):
    _, pool, make_client = setup
    image = io.BytesIO()
    metadata = Image.Exif()
    metadata[0x010E] = "Synthetic QA image metadata must not survive"
    Image.new("RGB", (4, 4), color="white").save(image, format="JPEG", exif=metadata)
    raw = image.getvalue()
    encoded = base64.b64encode(raw).decode()
    path = "/api/visa-oracle/testing/D1-T01-0"
    async with make_client() as c:
        await lock_personal_day(c)
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
        assert picture.status_code == 200
        assert picture.headers["content-type"] == "image/png"
        with (
            Image.open(io.BytesIO(raw)) as original,
            Image.open(io.BytesIO(picture.content)) as clean,
        ):
            assert clean.format == "PNG" and clean.size == original.size
            assert clean.convert("RGB").tobytes() == original.convert("RGB").tobytes()
            assert not clean.getexif()
        assert b"Synthetic QA image metadata" not in picture.content
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
    monkeypatch.setattr(campaign_router, "bali_today", lambda: "2026-10-01")
    async with make_client() as c:
        assert (
            await c.post("/api/visa-oracle/testing/D3-T01-1/start", json=expected())
        ).status_code == 409
        data = (await c.get("/api/visa-oracle/testing")).json()
        assert not any(a["can_start"] for a in data["assignments"] if a["day"] == "2026-10-02")
