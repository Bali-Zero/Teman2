"""Importer: rows must satisfy migration 328 rules, price keys must exist, and the newest family-C migration must not drift.

When a card changes, generate a NEW migration (next free number, same `_visa_types_law_family_c` suffix);
never edit an applied one (its checksum is in the production ledger).
"""

import hashlib
import re
from pathlib import Path

import pytest

from backend.services.visa_engine.families import importer

ROWS = importer.build_rows("C")
BY_CODE = {r["code"]: r for r in ROWS}
MIGRATIONS_DIR = Path(importer.__file__).parents[3] / "db" / "migrations_v2"
MIGRATION = max(
    MIGRATIONS_DIR.glob("*_visa_types_law_family_c*.sql"),
    key=lambda p: int(p.name.split("_", 1)[0]),
)
SHA = re.compile(r"^[0-9a-f]{64}$")


def test_thirteen_codes():
    assert len(ROWS) == 13


@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["code"])
def test_row_satisfies_328_rules(row):
    assert re.match(r"^(A|B|C|D|F|E[0-9]{2}|BRIDGING|SERVICE)$", row["family"])
    assert row["permit_class"] in {"VISIT_SINGLE"}
    assert row["entry_type"] in {"SINGLE", "MULTIPLE"}
    assert row["sponsor"] in {"REQUIRED", "NOT_REQUIRED", "CONDITIONAL"}
    assert row["apply_channel"] in {None, "OFFSHORE", "ONSHORE", "BOTH"}
    assert isinstance(row["price_keys"], list)
    assert row["max_total_days"] is None or row["max_total_months"] is None
    assert (row["max_total_days"] or row["max_total_months"]) is not None
    for key in ("initial_stay_days", "max_total_days", "max_total_months"):
        assert row[key] is None or row[key] > 0
    assert row["itap"] is None
    assert isinstance(row["law_card"], dict)
    assert SHA.match(row["page_sha256"]) and SHA.match(row["card_sha256"])
    assert row["verification_status"] == "VERIFIED"
    for key in (
        "law_card",
        "family",
        "permit_class",
        "source_url",
        "page_sha256",
        "retrieved_at",
        "card_sha256",
    ):
        assert row[key]


def test_sponsor_conditional_only_c1_c2():
    assert {c for c, r in BY_CODE.items() if r["sponsor"] == "CONDITIONAL"} == {"C1", "C2"}


def test_price_keys_exist_in_price_list():
    prices = importer.load_prices()
    for row in ROWS:
        for pk in row["price_keys"]:
            assert pk["item_key"] in prices[pk["category"]], (row["code"], pk)


def test_c12_has_no_price_and_all_sold():
    assert BY_CODE["C12"]["price_keys"] == []
    assert all(r["is_sold"] for r in ROWS)
    assert all(r["price_keys"] for c, r in BY_CODE.items() if c != "C12")


def test_bad_price_key_fails_loudly():
    with pytest.raises(ValueError):
        importer._check_price_keys(
            "CX", [{"category": "single_entry_visas", "item_key": "nope"}], importer.load_prices()
        )


def test_card_sha256_matches_file():
    for row in ROWS:
        path = importer.HERE / "law" / "C" / f"{row['code']}.json"
        assert row["card_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_newest_family_c_migration_equals_emit_sql():
    assert MIGRATION.read_text() == importer.emit_sql("C")


def test_sql_never_overwrites_legacy_columns():
    sql = importer.emit_sql("C")
    for col in (
        "name",
        "category",
        "description",
        "duration",
        "cost_visa",
        "requirements",
        "metadata",
    ):
        assert f"    {col} = EXCLUDED" not in sql
