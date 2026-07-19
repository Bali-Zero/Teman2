"""FASE-4 person-npwp strong-id matching (m248).

Runs against the LOCAL nuzantara_test DB (same harness as test_intake_routing).
Seeds SYNTHETIC, clearly-tagged CRM rows (torn down per-test).

Covers guilt AND innocence (cicatrix #3 — no guard ships without both):
- a full 15/16-digit doc npwp equal to a client's npwp → strong candidate;
- duplicate npwp across clients → AMBIGUOUS, never a single-winner guess
  (the live book holds 49 duplicate-npwp groups — measured 2026-07-18);
- a partial OCR fragment (<15 digits) must NEVER strong-match, even as an
  exact prefix of a real npwp;
- a company npwp still resolves the COMPANY first (person fallback only
  when the company side found nothing — resolve_entity ordering).

PII / Law 2: synthetic values only, 100% local Postgres.
"""

from __future__ import annotations

import os

import asyncpg
import pytest_asyncio

from backend.services.intake import routing as intake_routing
from backend.services.intake.routing import resolve_entity

_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_test",
)

TAG = "NPWPPYTEST"

# 15-digit legacy-format npwp, stored formatted in CRM, extracted raw from docs.
NPWP_FMT = "01.234.567.8-901.234"
NPWP_DIGITS = "012345678901234"
NPWP_DUP_DIGITS = "998877665544332"
NPWP_COMPANY_DIGITS = "556677889900112"


@pytest_asyncio.fixture
async def pool():
    p = await asyncpg.create_pool(_DB_URL, min_size=1, max_size=4)
    try:
        yield p
    finally:
        await p.close()


@pytest_asyncio.fixture
async def seeded(pool):
    async with pool.acquire() as c:
        ids = {}
        ids["c_unique"] = await c.fetchval(
            "INSERT INTO clients (full_name, npwp, notes) VALUES ($1,$2,$3) RETURNING id",
            f"{TAG} Nina Npwp",
            NPWP_FMT,
            TAG,
        )
        ids["c_dup1"] = await c.fetchval(
            "INSERT INTO clients (full_name, npwp, notes) VALUES ($1,$2,$3) RETURNING id",
            f"{TAG} Dup One",
            NPWP_DUP_DIGITS,
            TAG,
        )
        ids["c_dup2"] = await c.fetchval(
            "INSERT INTO clients (full_name, npwp, notes) VALUES ($1,$2,$3) RETURNING id",
            f"{TAG} Dup Two",
            NPWP_DUP_DIGITS,
            TAG,
        )
        ids["c_shadow"] = await c.fetchval(
            "INSERT INTO clients (full_name, npwp, notes) VALUES ($1,$2,$3) RETURNING id",
            f"{TAG} Shadow Person",
            NPWP_COMPANY_DIGITS,
            TAG,
        )
        ids["co_npwp"] = await c.fetchval(
            "INSERT INTO companies (company_name, npwp_company) VALUES ($1,$2) RETURNING id",
            f"{TAG} PT Pajak Jaya",
            NPWP_COMPANY_DIGITS,
        )
    try:
        yield ids
    finally:
        async with pool.acquire() as c:
            await c.execute("DELETE FROM clients WHERE notes = $1", TAG)
            await c.execute(
                "DELETE FROM companies WHERE company_name LIKE $1", f"{TAG}%"
            )


async def test_npwp_unique_match_is_strong_person_candidate(pool, seeded):
    entity = await resolve_entity(
        {"npwp_number": {"value": NPWP_DIGITS, "confidence": 0.9}}, "npwp", pool
    )
    cands = [c for c in entity["candidates"] if c["method"] == "npwp"]
    assert len(cands) == 1
    assert cands[0]["table"] == "clients"
    assert cands[0]["id"] == seeded["c_unique"]
    assert cands[0]["score"] == intake_routing.CONF_STRONG_EXACT
    assert cands[0]["matched_value"] == NPWP_DIGITS
    assert entity["subject_kind"] == "person"


async def test_npwp_matches_formatted_crm_value(pool, seeded):
    """Doc carries the FORMATTED npwp; CRM stores it formatted too — the
    digits-normalized comparison must still hit."""
    entity = await resolve_entity({"npwp_number": NPWP_FMT}, "npwp", pool)
    cands = [c for c in entity["candidates"] if c["method"] == "npwp"]
    assert [c["id"] for c in cands] == [seeded["c_unique"]]


async def test_npwp_duplicate_clients_degrade_to_ambiguous(pool, seeded):
    entity = await resolve_entity(
        {"npwp_number": NPWP_DUP_DIGITS}, "npwp", pool
    )
    cands = [c for c in entity["candidates"] if c["method"] == "npwp"]
    assert {c["id"] for c in cands} == {seeded["c_dup1"], seeded["c_dup2"]}
    assert entity["decision"] == "AMBIGUOUS"


async def test_npwp_fragment_never_strong_matches(pool, seeded):
    """A 10-digit OCR fragment that is an exact PREFIX of a real npwp must not
    produce a strong candidate (innocence: partial reads are not identity)."""
    entity = await resolve_entity(
        {"npwp_number": NPWP_DIGITS[:10]}, "npwp", pool
    )
    assert [c for c in entity["candidates"] if c["method"] == "npwp"] == []


async def test_npwp_overlong_garble_never_strong_matches(pool, seeded):
    """17+ digits = concatenated/garbled OCR, not a valid NPWP (which is
    exactly 15 or 16 digits) — even when a CRM row stores the same malformed
    17-digit value, no strong match may form (Codex round-2)."""
    garble = NPWP_DIGITS + "99"  # 17 digits
    async with pool.acquire() as c:
        await c.execute(
            "INSERT INTO clients (full_name, npwp, notes) VALUES ($1,$2,$3)",
            f"{TAG} Garble Holder",
            garble,
            TAG,
        )
    entity = await resolve_entity({"npwp_number": garble}, "npwp", pool)
    assert [c for c in entity["candidates"] if c["method"] == "npwp"] == []


async def test_cross_table_npwp_collision_degrades_to_ambiguous(pool, seeded):
    """The same digits exist as a client npwp AND a company npwp_company —
    a data error (one tax number cannot belong to both books). Company-first
    must NOT silently crown the company: both hits surface and the matrix
    degrades to AMBIGUOUS (Codex round-2 on the m248 diff)."""
    entity = await resolve_entity(
        {"npwp_number": NPWP_COMPANY_DIGITS}, "npwp", pool
    )
    tables = {c["table"] for c in entity["candidates"]}
    assert tables == {"companies", "clients"}
    assert entity["decision"] == "AMBIGUOUS"
    assert entity["subject_kind"] == "unknown"


async def test_company_only_npwp_still_resolves_company(pool, seeded):
    """No person collision: a company-held npwp resolves the company alone
    (the person probe finds nothing, ordering unchanged)."""
    async with pool.acquire() as c:
        await c.execute(
            "UPDATE clients SET npwp = NULL WHERE notes = $1 AND npwp = $2",
            TAG,
            NPWP_COMPANY_DIGITS,
        )
    entity = await resolve_entity(
        {"npwp_number": NPWP_COMPANY_DIGITS}, "npwp", pool
    )
    assert entity["subject_kind"] == "company"
    assert {c["table"] for c in entity["candidates"]} == {"companies"}


async def test_company_npwp_fragment_never_matches(pool, seeded):
    """An 11-digit doc value must not strong-match, even when a company row
    stores exactly that 11-digit npwp_company (same >=15 gate as the person
    side — 14 live companies carry 11-14-digit values)."""
    short_digits = "11223344556"
    async with pool.acquire() as c:
        await c.execute(
            "INSERT INTO companies (company_name, npwp_company) VALUES ($1,$2)",
            f"{TAG} PT Frammento",
            short_digits,
        )
    entity = await resolve_entity({"npwp_number": short_digits}, "npwp", pool)
    assert [c for c in entity["candidates"] if c["score"] >= 0.99] == []


async def test_unknown_doc_with_company_id_probes_company_book(pool, seeded):
    """dt='unknown' must not be person-only: a doc carrying a company
    strong-id (npwp matching a company) finds the company book too."""
    async with pool.acquire() as c:
        await c.execute(
            "UPDATE clients SET npwp = NULL WHERE notes = $1 AND npwp = $2",
            TAG,
            NPWP_COMPANY_DIGITS,
        )
    entity = await resolve_entity(
        {"npwp_number": NPWP_COMPANY_DIGITS}, "unknown", pool
    )
    assert {c["table"] for c in entity["candidates"]} == {"companies"}
