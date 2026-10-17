"""Real, isolated PostgreSQL proof; never connects to an existing database."""

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

from backend.services.visa_engine.families import importer

MIGRATIONS = Path(importer.__file__).parents[3] / "db" / "migrations_v2"
FILES = (
    "330_visa_types_law_projection.sql",
    "331_visa_types_law_family_c.sql",
    "332_visa_types_stay_options.sql",
    "333_visa_types_law_family_e30.sql",
)


class Cluster:
    """psql is pinned to the throwaway socket, port, user and database."""

    def __init__(self, base: Path) -> None:
        self.base = base
        self.data = base / "data"

    def sql(self, sql: str, *, succeeds: bool = True) -> str:
        result = subprocess.run(
            [
                "psql",
                "-X",
                "-h",
                str(self.base),
                "-p",
                "55483",
                "-U",
                "e30_test",
                "-d",
                "postgres",
                "-v",
                "ON_ERROR_STOP=1",
                "-At",
            ],
            input=sql,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
            env={key: value for key, value in os.environ.items() if not key.startswith("PG")},
        )
        if succeeds:
            assert result.returncode == 0, result.stderr
        else:
            assert result.returncode != 0, "Invalid data unexpectedly accepted"
        return result.stdout.strip() if succeeds else result.stderr


@pytest.fixture(scope="module")
def pg() -> Iterator[Cluster]:
    for binary in ("initdb", "pg_ctl", "psql"):
        if not shutil.which(binary):
            pytest.skip(f"Throwaway PostgreSQL unavailable: {binary} missing")
    # Short socket path, independent of pytest's potentially long temporary paths.
    with tempfile.TemporaryDirectory(prefix="pg", dir="/tmp") as directory:
        cluster = Cluster(Path(directory))
        initialized = subprocess.run(
            [
                "initdb",
                "-D",
                str(cluster.data),
                "-A",
                "trust",
                "-U",
                "e30_test",
                "--no-locale",
                "--encoding=UTF8",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if initialized.returncode and "Operation not permitted" in initialized.stderr:
            pytest.skip(f"Throwaway PostgreSQL blocked by sandbox: {initialized.stderr.strip()}")
        assert initialized.returncode == 0, initialized.stderr
        start = subprocess.run(
            [
                "pg_ctl",
                "-D",
                str(cluster.data),
                "-l",
                str(cluster.base / "server.log"),
                "-o",
                f"-F -k {cluster.base} -h '' -p 55483",
                "-w",
                "start",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert start.returncode == 0, start.stderr + (cluster.base / "server.log").read_text()
        try:
            version = cluster.sql("SHOW server_version_num;")
            assert int(version) >= 160000
            yield cluster
        finally:
            subprocess.run(
                ["pg_ctl", "-D", str(cluster.data), "-m", "immediate", "-w", "stop"],
                capture_output=True,
                check=True,
                timeout=30,
            )


def test_forward_twice_rollback_and_reapply_preserve_all_legacy_columns(pg: Cluster) -> None:
    parts = [(MIGRATIONS / name).read_text().split("-- === ROLLBACK ===", 1) for name in FILES]
    # Use exactly the production 24-column shape, before any Law columns exist.
    legacy_ddl = parts[0][0].split("ALTER TABLE visa_types", 1)[0]
    pg.sql(legacy_ddl)
    assert (
        pg.sql("SELECT count(*) FROM information_schema.columns WHERE table_name='visa_types';")
        == "24"
    )
    codes = sorted(r["code"] for family in ("C", "E30") for r in importer.build_rows(family))
    pg.sql(
        "\n".join(
            "INSERT INTO visa_types (code, name, category, duration, extensions, total_stay, renewable, "
            "processing_time_normal, processing_time_express, processing_timeline, cost_visa, cost_extension, "
            "cost_details, requirements, restrictions, allowed_activities, benefits, process_steps, tips, "
            "foreign_eligible, metadata, last_updated, created_at) "
            f"VALUES ('{code}', 'legacy {code}', 'legacy category', 'original duration', 'original extensions', "
            "'original total', true, 'normal', 'express', '{\"normal\": 5}', 'original cost', 'extension cost', "
            "'{\"currency\": \"IDR\"}', ARRAY['document'], ARRAY['restriction'], ARRAY['activity'], "
            "ARRAY['benefit'], ARRAY['step'], ARRAY['tip'], false, '{\"synthetic\": true}', "
            "'2026-01-01T00:00:00Z', '2025-01-01T00:00:00Z');"
            for code in codes
        )
    )
    legacy_columns = pg.sql(
        "SELECT string_agg(quote_ident(column_name), ', ' ORDER BY ordinal_position) "
        "FROM information_schema.columns WHERE table_name='visa_types';"
    )
    legacy_query = f"SELECT jsonb_agg(to_jsonb(v) ORDER BY code) FROM (SELECT {legacy_columns} FROM visa_types) v;"
    before = pg.sql(legacy_query)
    for _ in range(2):
        for forward, _rollback in parts:
            pg.sql(forward)
        assert pg.sql(legacy_query) == before
    projected = pg.sql("SELECT jsonb_agg(to_jsonb(v) ORDER BY code) FROM visa_types v;")
    rows = json.loads(projected)
    assert len(rows) == 18
    for family in ("C", "E30"):
        for expected in importer.build_rows(family):
            actual = next(r for r in rows if r["code"] == expected["code"])
            for column in (*importer.LAW_COLUMNS, "stay_options"):
                if column == "retrieved_at":
                    assert datetime.fromisoformat(actual[column]) == datetime.fromisoformat(
                        expected[column]
                    )
                else:
                    assert actual[column] == expected.get(column), (expected["code"], column)
    c_before = pg.sql(
        "SELECT jsonb_agg(to_jsonb(v) ORDER BY code) FROM visa_types v WHERE family='C';"
    )
    pg.sql(parts[3][1])
    assert (
        pg.sql(
            "SELECT count(*) FROM visa_types WHERE code LIKE 'E30%' AND family IS NULL AND stay_options IS NULL AND verification_status='TO_VERIFY';"
        )
        == "5"
    )
    assert (
        pg.sql("SELECT jsonb_agg(to_jsonb(v) ORDER BY code) FROM visa_types v WHERE family='C';")
        == c_before
    )
    pg.sql(parts[2][1])
    assert (
        pg.sql(
            "SELECT count(*) FROM information_schema.columns WHERE table_name='visa_types' AND column_name='stay_options';"
        )
        == "0"
    )
    assert (
        pg.sql("SELECT count(*) FROM pg_proc WHERE proname='visa_types_stay_options_valid';") == "0"
    )
    assert pg.sql(legacy_query) == before
    pg.sql(parts[2][0])
    pg.sql(parts[3][0])
    assert pg.sql("SELECT jsonb_agg(to_jsonb(v) ORDER BY code) FROM visa_types v;") == projected
    assert pg.sql(legacy_query) == before
    # A casing collision must fail before the first upsert can modify any row.
    pg.sql("UPDATE visa_types SET code='e30a' WHERE code='E30A';")
    assert "non-uppercase duplicate" in pg.sql(parts[3][0], succeeds=False)
    pg.sql("UPDATE visa_types SET code='E30A' WHERE code='e30a';")
    # Fresh rows receive the seed category; conflicts above kept the legacy one.
    pg.sql("DELETE FROM visa_types WHERE code LIKE 'E30%';")
    pg.sql(parts[3][0])
    assert (
        pg.sql(
            "SELECT count(*) FROM visa_types WHERE family='E30' AND category='KITAS/Limited Stay';"
        )
        == "5"
    )


@pytest.mark.parametrize(
    "options",
    [
        [],
        [{"value": 1, "unit": "DAY"}],
        [{"value": 2, "unit": "MONTH"}, {"value": 4, "unit": "YEAR"}],
        None,
    ],
)
def test_stay_options_accepts_valid_shapes(pg: Cluster, options: object) -> None:
    value = "NULL" if options is None else "'" + json.dumps(options) + "'::jsonb"
    pg.sql(f"UPDATE visa_types SET stay_options={value} WHERE code='E30A';")
    stored = pg.sql(
        "SELECT coalesce(stay_options::text, 'NULL') FROM visa_types WHERE code='E30A';"
    )
    if options is None:
        assert stored == "NULL"
    else:
        assert json.loads(stored) == options


@pytest.mark.parametrize(
    "options",
    [
        {},
        "null",
        [None],
        [1],
        [True],
        [{}],
        [{"unit": "YEAR"}],
        [{"value": 1}],
        [{"value": None, "unit": "YEAR"}],
        [{"value": 0, "unit": "YEAR"}],
        [{"value": -1, "unit": "YEAR"}],
        [{"value": 1.5, "unit": "YEAR"}],
        [{"value": "1", "unit": "YEAR"}],
        [{"value": True, "unit": "YEAR"}],
        [{"value": 1, "unit": "year"}],
        [{"value": 1, "unit": None}],
        [{"value": 1, "unit": "WEEK"}],
        [{"value": 1, "unit": "YEAR", "extra": 1}],
        [{"value": 1, "unit": "YEAR"}, {"value": 0, "unit": "YEAR"}],
    ],
)
def test_stay_options_rejects_invalid_shapes(pg: Cluster, options: object) -> None:
    value = "'null'::jsonb" if options == "null" else "'" + json.dumps(options) + "'::jsonb"
    assert "vt_stay_options_chk" in pg.sql(
        f"UPDATE visa_types SET stay_options={value} WHERE code='E30A';", succeeds=False
    )
