#!/usr/bin/env python3
"""cost_ledger_export.py — read-only bridge: Fly PG ``llm_cost_events`` -> Pro JSONL.

THE PROBLEM THIS SOLVES
-----------------------
``scripts/cost_breaker.py`` (P9 GOVERN) reads spend from the JSONL fallback at
``${LLM_COST_JSONL_ROOT:-/data}/llm_cost_log.{UTC-date}.jsonl``. On the Pro,
``/data`` does NOT exist and no agent writes that JSONL, so EVERY guarded
provider resolves to UNKNOWN -> fail-closed DEGRADE every tick (no real
governance, just noise). The real ledger lives in Fly Postgres table
``llm_cost_events`` (migration 117).

This exporter is the missing READ-ONLY bridge. It connects to the Fly PG ledger
(via the local read-only proxy the postgres-nuzantara MCP uses), SELECTs the
recent window of ``(provider, cost_usd, ts_utc)`` rows, and writes them to daily
JSONL files on the Pro in EXACTLY the schema ``cost_breaker.py`` expects (see
``cost_breaker.sum_rows_in_window`` / ``_iter_jsonl_rows``): one JSON object per
line with keys ``provider`` (str), ``ts_utc`` (ISO-8601 str), ``cost_usd``
(number). Files are named ``llm_cost_log.{YYYY-MM-DD}.jsonl`` and partitioned by
the UTC date of each row's ``ts_utc`` (mirroring
``backend/services/observability/llm_cost_recorder.py`` — the producer the
breaker's fallback was designed around).

After this runs, ``LLM_COST_JSONL_ROOT=<export-dir> python3 cost_breaker.py``
reads KNOWN spend instead of UNKNOWN.

SECURITY / GOLDEN RULES
-----------------------
- READ-ONLY: a single ``SELECT`` against the ledger. ZERO writes to Fly PG.
- NO paid API: this only reads Postgres; it never calls an LLM.
- NO hardcoded secret: the DSN comes from env ``COST_LEDGER_DSN`` if set;
  otherwise it is BUILT from the Keychain password
  (``security find-generic-password -s nuzantara-postgres-readonly -a
  nuzantara_readonly -w``) at runtime. The password is NEVER logged and NEVER
  written to the JSONL.
- Async I/O via ``asyncpg`` (already a backend dep — see
  ``llm_cost_recorder._write_postgres``), per repo golden rule #4.
- Idempotent: each daily file is fully REWRITTEN on every run (overwrite, not
  append) so re-running never double-counts and today's file always reflects the
  current window snapshot.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cost_ledger_export")

# --- Defaults --------------------------------------------------------------

# Default Pro export dir (kept off /data, which does not exist on the Pro). The
# breaker is pointed here via LLM_COST_JSONL_ROOT in its LaunchAgent plist.
_DEFAULT_EXPORT_ROOT: Path = Path.home() / ".agent" / "cost-ledger"

# Default lookback window. 48h gives the breaker's 24h window full headroom plus
# a margin for clock skew / a missed export tick.
_DEFAULT_WINDOW_HOURS: int = 48

# File naming MUST match cost_breaker._iter_jsonl_rows / llm_cost_recorder.
_JSONL_FILENAME_TEMPLATE: str = "llm_cost_log.{date}.jsonl"

# Keychain coordinates for the read-only role (T3.2 defense-in-depth pattern).
_KEYCHAIN_SERVICE: str = "nuzantara-postgres-readonly"
_KEYCHAIN_ACCOUNT: str = "nuzantara_readonly"

# The local read-only proxy the postgres-nuzantara MCP uses (Fly PG, read-only
# role). The password is injected from the Keychain — never in this string.
_DEFAULT_DSN_TEMPLATE: str = (
    "postgresql://nuzantara_readonly:{password}@localhost:15432/"
    "nuzantara_rag?sslmode=disable"
)


# ---------------------------------------------------------------------------
# DSN resolution (no secret in repo / logs)
# ---------------------------------------------------------------------------


def _keychain_password() -> str:
    """Fetch the read-only PG password from the macOS Keychain.

    Mirrors the T3.2 postgres-nuzantara MCP pattern. The value is returned for
    immediate use in the DSN and is NEVER logged. Raises RuntimeError (with NO
    secret in the message) if the entry is absent.
    """
    try:
        result = subprocess.run(  # noqa: S603 — fixed argv, no shell
            [
                "security",
                "find-generic-password",
                "-s",
                _KEYCHAIN_SERVICE,
                "-a",
                _KEYCHAIN_ACCOUNT,
                "-w",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:  # `security` not on PATH (non-macOS)
        raise RuntimeError(
            "cost_ledger_export: `security` CLI not found — set COST_LEDGER_DSN "
            "explicitly on this host",
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "cost_ledger_export: Keychain item "
            f"{_KEYCHAIN_SERVICE}/{_KEYCHAIN_ACCOUNT} not found "
            "(set COST_LEDGER_DSN or add the Keychain entry)",
        ) from exc
    password = result.stdout.strip()
    if not password:
        raise RuntimeError(
            "cost_ledger_export: empty Keychain password for "
            f"{_KEYCHAIN_SERVICE}/{_KEYCHAIN_ACCOUNT}",
        )
    return password


def resolve_dsn() -> str:
    """Return the read-only ledger DSN.

    Priority:
      1. ``COST_LEDGER_DSN`` env (the LaunchAgent wrapper injects it with the
         Keychain password already substituted) — used verbatim.
      2. Built from the Keychain password + the default localhost proxy DSN.

    The returned DSN contains the password; callers MUST NOT log it.
    """
    env_dsn = os.environ.get("COST_LEDGER_DSN")
    if env_dsn:
        return env_dsn
    return _DEFAULT_DSN_TEMPLATE.format(password=_keychain_password())


def _redact_dsn(dsn: str) -> str:
    """Return a log-safe DSN with the password masked."""
    # postgresql://user:PASSWORD@host/... -> postgresql://user:***@host/...
    if "://" not in dsn or "@" not in dsn:
        return "<dsn>"
    scheme, rest = dsn.split("://", 1)
    creds, hostpart = rest.split("@", 1)
    user = creds.split(":", 1)[0] if ":" in creds else creds
    return f"{scheme}://{user}:***@{hostpart}"


# ---------------------------------------------------------------------------
# Ledger read (READ-ONLY) -> rows in the breaker's JSONL schema
# ---------------------------------------------------------------------------


async def fetch_recent_rows(dsn: str, window_hours: int) -> list[dict[str, Any]]:
    """SELECT (provider, cost_usd, ts_utc) over the trailing ``window_hours``.

    READ-ONLY single SELECT riding ``idx_llm_cost_ts``. Returns a list of dicts
    in the EXACT schema ``cost_breaker.sum_rows_in_window`` consumes:
    ``{"provider": str, "ts_utc": ISO-8601 str, "cost_usd": float}``.

    ``cost_usd`` is NUMERIC in PG (asyncpg -> ``decimal.Decimal``); rendered as a
    JSON number via ``float()`` at the JSON boundary (the breaker re-parses with
    ``Decimal(str(value))``, so precision survives). Matches the recorder's
    ``cost_usd: float``.
    """
    import asyncpg  # local import: no DB dep at module import time

    sql = """
        SELECT provider, cost_usd, ts_utc
        FROM llm_cost_events
        WHERE ts_utc >= $1
        ORDER BY ts_utc ASC
    """
    window_start = datetime.now(timezone.utc) - timedelta(hours=window_hours)

    conn = await asyncpg.connect(dsn)
    try:
        records = await conn.fetch(sql, window_start)
    finally:
        await conn.close()

    rows: list[dict[str, Any]] = []
    for rec in records:
        ts = rec["ts_utc"]
        # asyncpg returns an aware datetime for `timestamptz`.
        ts_iso = (
            ts.astimezone(timezone.utc).isoformat()
            if isinstance(ts, datetime)
            else str(ts)
        )
        rows.append(
            {
                "provider": rec["provider"],
                "ts_utc": ts_iso,
                "cost_usd": float(rec["cost_usd"]),
            },
        )
    return rows


# ---------------------------------------------------------------------------
# Write -> daily JSONL files (idempotent overwrite, UTC-date partitioned)
# ---------------------------------------------------------------------------


def _utc_date_of(ts_iso: str) -> str:
    """UTC ``YYYY-MM-DD`` for an ISO-8601 ts string (matches the recorder)."""
    text = ts_iso.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")


def write_daily_jsonl(rows: list[dict[str, Any]], export_root: Path) -> dict[str, int]:
    """Write rows to per-UTC-date JSONL files under ``export_root`` (overwrite).

    Returns ``{date: row_count}`` for the files written. Idempotent: every daily
    file overlapping the window is fully rewritten, so re-running produces the
    same content and never double-counts. A date present in a prior export but
    NOT in this window's rows is NOT cleared here (a stale older day's file ages
    out naturally as the breaker's window slides past it).
    """
    export_root.mkdir(parents=True, exist_ok=True)
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_date[_utc_date_of(row["ts_utc"])].append(row)

    written: dict[str, int] = {}
    for date_str, day_rows in by_date.items():
        path = export_root / _JSONL_FILENAME_TEMPLATE.format(date=date_str)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            for row in day_rows:
                fh.write(json.dumps(row, separators=(",", ":")) + "\n")
        tmp.replace(path)  # atomic overwrite
        written[date_str] = len(day_rows)
    return written


# ---------------------------------------------------------------------------
# Orchestration / CLI
# ---------------------------------------------------------------------------


async def run_export(export_root: Path, window_hours: int) -> int:
    """Read the ledger and write the JSONL bridge. Returns the row count.

    Fail-LOUD on connect/read errors (exit non-zero) so the LaunchAgent log and
    the deadman/verify layer can see the bridge is down — a SILENT empty export
    would re-create the exact UNKNOWN-spend blind spot this bridge closes.
    """
    dsn = resolve_dsn()
    logger.info(
        "cost_ledger_export: connecting %s (read-only, window=%dh)",
        _redact_dsn(dsn),
        window_hours,
    )
    rows = await fetch_recent_rows(dsn, window_hours)
    written = write_daily_jsonl(rows, export_root)
    logger.info(
        "cost_ledger_export: wrote %d rows across %d daily file(s) under %s: %s",
        len(rows),
        len(written),
        export_root,
        ", ".join(f"{d}={n}" for d, n in sorted(written.items())) or "(none)",
    )
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    """CLI: export the recent ledger window to Pro JSONL for the cost-breaker."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--export-root",
        type=Path,
        default=Path(
            os.environ.get("LLM_COST_JSONL_ROOT", str(_DEFAULT_EXPORT_ROOT)),
        ),
        help="Dir for daily JSONL files (default $LLM_COST_JSONL_ROOT or "
        "~/.agent/cost-ledger/).",
    )
    parser.add_argument(
        "--window-hours",
        type=int,
        default=int(
            os.environ.get("COST_LEDGER_WINDOW_HOURS", _DEFAULT_WINDOW_HOURS),
        ),
        help="Lookback window in hours (default 48).",
    )
    args = parser.parse_args(argv)
    if args.window_hours <= 0:
        parser.error("--window-hours must be positive")

    try:
        asyncio.run(run_export(args.export_root, args.window_hours))
    except Exception as exc:  # noqa: BLE001 — surface any failure as exit 1
        # NB: never let a secret reach the log. resolve_dsn() raises with no
        # secret in the message; asyncpg errors do not include the password.
        logger.error("cost_ledger_export: FAILED: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
