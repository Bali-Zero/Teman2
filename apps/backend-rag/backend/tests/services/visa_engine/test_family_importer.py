"""Importer: rows must satisfy migration 330 rules, price keys must exist, and the newest family-C migration must not drift.

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
def test_row_satisfies_330_rules(row):
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


def test_migration_starts_with_case_duplicate_guard():
    from backend.services.visa_engine.families import importer

    sql = importer.emit_sql("C")
    guard = sql.index("DO $guard$")
    assert guard < sql.index("INSERT INTO visa_types")
    assert "code <> upper(code)" in sql[guard : sql.index("$guard$;")]
    assert "'C1'" in sql[guard : sql.index("$guard$;")]


E30_ROWS = importer.build_rows("E30")
E30_BY_CODE = {r["code"]: r for r in E30_ROWS}
E30_MIGRATION = MIGRATIONS_DIR / "333_visa_types_law_family_e30.sql"


@pytest.mark.parametrize("row", E30_ROWS, ids=lambda r: r["code"])
def test_e30_row_satisfies_330_rules(row: dict) -> None:
    assert row["family"] == "E30"
    assert row["permit_class"] == "ITAS"
    assert row["category"] == "KITAS/Limited Stay"
    assert row["entry_type"] in {None, "MULTIPLE"}
    assert row["sponsor"] in {None, "REQUIRED"}
    assert row["apply_channel"] is None
    assert row["initial_stay_days"] is None
    assert row["max_total_days"] is None and row["max_total_months"] is None
    assert row["itap"] is None
    assert isinstance(row["price_keys"], list)
    for key in ("page_sha256", "card_sha256"):
        assert SHA.fullmatch(row[key])
    for key in ("law_card", "source_url", "retrieved_at"):
        assert row[key]
    card = row["law_card"]
    assert row["page_sha256"] == card["page_sha256"]
    assert row["official_name_id"] == card["official_name_id"]
    path = importer.HERE / "law" / "E30" / f"{row['code']}.json"
    assert row["card_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert row["verification_status"] == (
        "TO_VERIFY" if card["status"] == "NOT_FOUND" else "VERIFIED"
    )


def test_e30_secondary_codes_remain_unknown() -> None:
    assert set(E30_BY_CODE) == {"E30", "E30A", "E30B", "E30E", "E30F"}
    for code in ("E30", "E30E", "E30F"):
        row = E30_BY_CODE[code]
        assert row["verification_status"] == "TO_VERIFY"
        for key in ("sponsor", "entry_type", "extendable", "stay_options", "is_sold"):
            assert row[key] is None
        assert row["price_keys"] == []


def test_e30_discrete_year_options_and_exact_price_keys() -> None:
    expected = {
        "E30A": ("E30A Education Visa", [1, 2]),
        "E30B": ("E30B Higher Education", [1, 2, 4]),
    }
    prices = importer.load_prices()
    for code, (label, years) in expected.items():
        row = E30_BY_CODE[code]
        assert row["is_sold"] is True
        assert row["stay_options"] == [{"value": year, "unit": "YEAR"} for year in years]
        assert row["price_keys"] == [
            {
                "category": "kitas_permits",
                "item_key": f"{label} ({year} {'Year' if year == 1 else 'Years'})",
            }
            for year in years
        ]
        for pk in row["price_keys"]:
            assert pk["item_key"] in prices[pk["category"]]


def test_e30_migration_matches_importer_and_preserves_legacy() -> None:
    sql = importer.emit_sql("E30")
    assert E30_MIGRATION.read_text() == sql
    guard = sql[sql.index("DO $guard$") : sql.index("$guard$;")]
    assert all(f"'{code}'" in guard for code in E30_BY_CODE)
    assert sql.index("DO $guard$") < sql.index("INSERT INTO visa_types")
    assert "stay_options = EXCLUDED.stay_options" in sql
    rollback = sql.split("-- === ROLLBACK ===", 1)[1]
    assert "stay_options = NULL" in rollback
    for column in ("name", "category", "duration", "requirements", "metadata", "cost_visa"):
        assert f"{column} = EXCLUDED" not in sql
    assert "stay_options" not in importer.emit_sql("C")


def test_e30_importer_cli_check() -> None:
    assert importer.main(["--family", "E30", "--check", str(E30_MIGRATION)]) == 0
