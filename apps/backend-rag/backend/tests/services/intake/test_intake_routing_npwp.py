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


async def test_company_npwp_still_resolves_company_first(pool, seeded):
    """The same digits exist as a client npwp AND a company npwp_company:
    resolve_entity must keep the company-first ordering — the person fallback
    only fires when the company side found nothing."""
    entity = await resolve_entity(
        {"npwp_number": NPWP_COMPANY_DIGITS}, "npwp", pool
    )
    assert entity["subject_kind"] == "company"
    tables = {c["table"] for c in entity["candidates"]}
    assert "companies" in tables
    assert "clients" not in tables
