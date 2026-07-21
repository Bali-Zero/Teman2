"""CLI safety tests for the aggregate-only Visa Oracle SHADOW report."""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone

import pytest

from scripts import visa_shadow_evidence as cli


class _Pool:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def test_parser_rejects_naive_timestamp(capsys: pytest.CaptureFixture[str]) -> None:
    parser = cli._parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(
            [
                "--start",
                "2026-07-21T00:00:00",
                "--end",
                "2026-07-22T00:00:00Z",
            ]
        )

    assert exc_info.value.code == 2
    assert "timestamp must include a timezone" in capsys.readouterr().err


def test_main_rejects_missing_database_url_environment(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    variable = "VISA_SHADOW_TEST_DATABASE_URL"
    monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "visa_shadow_evidence.py",
            "--start",
            "2026-07-21T00:00:00Z",
            "--end",
            "2026-07-22T00:00:00Z",
            "--database-url-env",
            variable,
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2
    assert f"missing database URL environment variable: {variable}" in capsys.readouterr().err


@pytest.mark.parametrize(
    "error",
    (
        cli.asyncpg.PostgresError("database rejected the query"),
        cli.asyncpg.InterfaceError("database connection is closed"),
        OSError("database socket is unavailable"),
        asyncio.TimeoutError("database query timed out"),
    ),
    ids=("postgres", "interface", "os", "timeout"),
)
def test_main_reports_operational_errors_without_using_report(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: Exception,
) -> None:
    async def fail_run(_args: argparse.Namespace) -> dict[str, object]:
        raise error

    monkeypatch.setattr(cli, "_run", fail_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "visa_shadow_evidence.py",
            "--start",
            "2026-07-21T00:00:00Z",
            "--end",
            "2026-07-22T00:00:00Z",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert str(error) in captured.err
    assert captured.out == ""


@pytest.mark.asyncio
async def test_run_forces_read_only_transactions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    variable = "VISA_SHADOW_TEST_DATABASE_URL"
    monkeypatch.setenv(variable, "postgresql://unused-local-test.invalid/visa")
    pool = _Pool()
    create_pool_call: dict[str, object] = {}

    async def fake_create_pool(database_url: str, **kwargs: object) -> _Pool:
        create_pool_call["database_url"] = database_url
        create_pool_call.update(kwargs)
        return pool

    async def fake_collect(
        db_pool: object,
        *,
        window_start: datetime,
        window_end: datetime,
        environment: str,
    ) -> dict[str, object]:
        assert db_pool is pool
        assert window_start.tzinfo is not None
        assert window_end > window_start
        assert environment == "TEST"
        return {"gate_status": "RED", "enforce_ready": False}

    monkeypatch.setattr(cli.asyncpg, "create_pool", fake_create_pool)
    monkeypatch.setattr(cli, "collect_shadow_evidence", fake_collect)
    start = datetime(2026, 7, 21, tzinfo=timezone.utc)
    args = argparse.Namespace(
        start=start,
        end=start + timedelta(days=1),
        environment="TEST",
        database_url_env=variable,
    )

    report = await cli._run(args)

    assert report == {"gate_status": "RED", "enforce_ready": False}
    assert create_pool_call == {
        "database_url": "postgresql://unused-local-test.invalid/visa",
        "min_size": 1,
        "max_size": 2,
        "server_settings": {"default_transaction_read_only": "on"},
    }
    assert pool.closed is True
