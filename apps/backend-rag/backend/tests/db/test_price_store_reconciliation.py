"""Bali Zero holds every price in TWO stores, and nothing reconciles them.

This is the test that was missing on 2026-06-09, and its absence cost two
months. Migration 221 seeded `practice_types.visa_b1_voa` at 750.000. On
2026-07-24 the owner moved the e-VOA price to 790.000 and the JSON sheet was
updated; the database row was not, because the commit that made the change
checked a code (`visa_voa`) that does not exist in this database instead of the
one that does. From then until 2026-08-31 the CRM defaulted VOA quotes to
750.000 while GARUDA VOA and the public site quoted 790.000. Two live surfaces,
one service, two prices, and no red anywhere.

WHAT EACH STORE IS
    - `backend/data/bali_zero_official_prices_2026.json` — loaded by
      PricingService, resolved per request. Feeds GARUDA VOA, the visa_engine
      pricing adapter, the WhatsApp bot, and (via a generated snapshot) the
      public site and its JSON-LD.
    - `practice_types.base_price` in Postgres — read by crm_practices.py as the
      DEFAULT quote when a practice carries no explicit price, and billed by
      the invoice service. Only a migration can change it.

WHY NAME-MATCHING ALONE WOULD NOT HAVE CAUGHT IT
    Measured 2026-09-01 against the production catalogue: of 112 priced rows,
    79 match a sheet label by name and ZERO of those disagree. The VOA row is
    NOT among the 79 — the database calls it "B1 - VOA" and the sheet calls it
    "B1 Visa on Arrival (VOA)". So a reconciliation that only joined on name
    would have been green through the entire divergence. That is why the
    explicit mapping below exists and why it is the load-bearing part of this
    file: the pairs whose NAMES differ are exactly the pairs nothing else can
    see.

WHAT THIS TEST DOES NOT DO
    It does not assert a row count. The local developer database and CI's
    freshly-migrated one hold different numbers of rows, and a frozen count
    would be red on one and meaningless on the other. It reconciles whatever
    priced rows the database in front of it actually has.
"""

from __future__ import annotations

import json
import pathlib
import re
from typing import Any

import asyncpg
import pytest

pytestmark = pytest.mark.integration

_SHEET = (
    pathlib.Path(__file__).resolve().parents[2]
    / "data"
    / "bali_zero_official_prices_2026.json"
)

#: practice_types.code -> the label carrying its price in the JSON sheet.
#: ONLY pairs verified to be the same service. A guess here is worse than an
#: omission: a wrong mapping asserts equality between two different services
#: and would redden on a legitimate price change to either one.
CODE_TO_SHEET_LABEL: dict[str, str] = {
    "visa_b1_voa": "B1 Visa on Arrival (VOA)",
    "ext_b1_voa": "B1 Visa on Arrival Extension",
    "visa_c1_tourism": "C1 Tourism",
    "visa_c2_business": "C2 Business",
    "visa_c18_work_trial": "C18 Work Trial",
    "other_create_molina_express": "Created Molina Express",
}

#: Priced rows that reconcile against NOTHING, each with the reason. This is a
#: declared hole, not a silent one: a new unmatched row is a FAILURE until
#: somebody either maps it above or adds it here with a reason.
UNRECONCILED: dict[str, str] = {
    "visa_c8_journalism": (
        "NAME CONFLICT, deliberately not mapped: the row is 'C8A,B Journalism "
        "Visa' and the sheet's C8A,B entry is 'C8A,B Sports Events'. Same code "
        "family, same 4.000.000 price, incompatible descriptions — one of the "
        "two names is wrong and mapping them would freeze the error in place."
    ),
    "visa_c7_music_art": (
        "The row says 'C7A&B' and the sheet says 'C7A,B,C' — the sheet covers "
        "one more sub-category. Same price today; not asserted equal, because "
        "they may not be the same product."
    ),
    "other_born_report": (
        "AMBIGUOUS: the sheet splits this into 'Lapor Lahir (Under)' at "
        "2.000.000 and '(Up)' at 4.000.000. The row is a single 4.000.000 "
        "entry, so it corresponds to at most one of the two."
    ),
    "other_create_user_rptka": "No sheet entry — process step, not a sold service.",
    "company_dissolving": (
        "The sheet prices closure as a RANGE ('Close PMA Company', 6.0-7.5M) "
        "and the row is a single 13.000.000 figure. A range and a scalar "
        "cannot be reconciled by equality."
    ),
    "kitap_dependent_merp": "No sheet entry.",
    "tax_annual_reporting": "Superseded by the itemised tax_annual_* rows; no sheet entry.",
    "tax_annual_company": "Sheet label differs ('Annual Tax Company'); not verified same scope.",
    "tax_annual_personal": "Sheet label differs ('Annual Tax Personal'); not verified same scope.",
    "tax_monthly_bundled_0_50": "Sheet keys these by tier ('Tier 0-50'); mapping not verified.",
    "tax_monthly_bundled_50_100": "Sheet keys these by tier ('Tier 50-100'); mapping not verified.",
    "tax_monthly_bundled_100_200": "Sheet keys these by tier ('Tier 100-200'); mapping not verified.",
    "tax_monthly_bundled_200_plus": "Sheet keys these by tier ('Tier 200+'); mapping not verified.",
    "tax_monthly_basic_200_plus": "Unbundled variant; no sheet entry.",
}

#: Inactive rows carrying implausible prices (1.000-3.000 IDR). They cannot
#: default a quote, and changing them would be a pricing decision nobody has
#: made — so they are excluded rather than reconciled or "tidied".
_INACTIVE_ONLY = frozenset(
    {
        "tax_consulting",
        "property_purchase",
        "pt_pma_setup",
        "kitas_application",
        "kitap_application",
    }
)


def _sheet_prices() -> dict[str, str]:
    """label -> raw price string, walking the sheet RECURSIVELY.

    The tax block nests its rows one level deeper than the visa blocks. A flat
    two-level walk silently misses them — measured: it reported 41 unreconciled
    rows where the real number is 33, and every one of the phantom 8 was a tax
    row the walk never reached. An index that quietly under-collects makes this
    whole test weaker while looking like it passed.
    """
    doc = json.loads(_SHEET.read_text(encoding="utf-8"))
    index: dict[str, str] = {}

    def walk(node: Any, path: list[str]) -> None:
        if not isinstance(node, dict):
            return
        price = node.get("price")
        if isinstance(price, str) and price.strip():
            for label in (node.get("name"), path[-1] if path else None):
                if isinstance(label, str) and label:
                    index.setdefault(label, price)
            return
        for key, value in node.items():
            walk(value, path + [key])

    walk(doc["services"], [])
    return index


def _to_idr(price: str) -> int | None:
    """'750.000 IDR' -> 750000. None when the entry is not a single amount."""
    digits = re.sub(r"[^\d]", "", price or "")
    return int(digits) if digits else None


async def _priced_rows(conn: asyncpg.Connection) -> list[asyncpg.Record]:
    return await conn.fetch(
        "SELECT code, name, base_price, is_active FROM practice_types "
        "WHERE base_price IS NOT NULL ORDER BY code"
    )


@pytest.mark.asyncio
async def test_no_priced_row_disagrees_with_the_official_sheet(
    db_tx: asyncpg.Connection,
) -> None:
    """The invariant the two-month divergence violated, for EVERY service.

    A row reconciles either by exact name or through CODE_TO_SHEET_LABEL. Where
    it reconciles, the two stores must say the same number.
    """
    sheet = _sheet_prices()
    assert sheet, "the sheet index is empty — the walk is reading nothing"

    disagreements: list[str] = []
    reconciled = 0
    for row in await _priced_rows(db_tx):
        label = CODE_TO_SHEET_LABEL.get(row["code"], row["name"])
        raw = sheet.get(label)
        if raw is None:
            continue
        expected = _to_idr(raw)
        if expected is None:
            continue
        reconciled += 1
        actual = int(row["base_price"])
        if actual != expected:
            disagreements.append(
                f"{row['code']} ({row['name']!r} -> sheet {label!r}): "
                f"practice_types.base_price={actual:,} but the sheet says "
                f"{expected:,}"
            )

    assert reconciled, (
        "not one row reconciled against the sheet. Either this database has no "
        "catalogue (run `python -m backend.db.migrate apply-all`) or the sheet "
        "walk has stopped finding prices — both are failures, not a reason to "
        "pass quietly."
    )
    assert not disagreements, (
        "the two price stores disagree, which is exactly the state that went "
        "unnoticed from 2026-06-09 to 2026-08-31:\n  "
        + "\n  ".join(disagreements)
        + "\nA price lives in both stores and nothing syncs them: fix whichever "
        "is wrong with a migration (for the database) or an edit to the sheet, "
        "in the same commit."
    )


@pytest.mark.asyncio
async def test_every_priced_row_is_either_reconciled_or_declared(
    db_tx: asyncpg.Connection,
) -> None:
    """No priced row may quietly reconcile against nothing.

    Without this, the first test's coverage can shrink to zero one unmatched
    row at a time and still report success — the reconciliation would be
    watching fewer and fewer prices while staying green. A row that cannot be
    reconciled has to be DECLARED, with a reason, in UNRECONCILED.

    Deliberately NOT asserted: that every UNRECONCILED entry is used. The local
    developer database is migrated further behind than CI's, so the set of rows
    present differs by environment, and an exhaustiveness check would be red on
    one machine and vacuous on the other.
    """
    sheet = _sheet_prices()
    undeclared: list[str] = []
    for row in await _priced_rows(db_tx):
        code = row["code"]
        if code in UNRECONCILED or code in _INACTIVE_ONLY:
            continue
        if code in CODE_TO_SHEET_LABEL or row["name"] in sheet:
            continue
        undeclared.append(f"{code} ({row['name']!r}, {int(row['base_price']):,} IDR)")

    assert not undeclared, (
        "these priced practice_types rows reconcile against nothing in the "
        "official sheet, and are not declared:\n  "
        + "\n  ".join(undeclared)
        + "\nAdd each to CODE_TO_SHEET_LABEL if the sheet carries the same "
        "service under a different label, or to UNRECONCILED with the reason "
        "it cannot be reconciled. Do not guess a mapping: a wrong one asserts "
        "equality between two different services."
    )
