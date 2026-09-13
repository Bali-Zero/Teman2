#!/usr/bin/env python3
"""Portal Challenge Leaderboard — read-only, NEW rules decided by Zero on
2026-09-14 (replaces the earlier invited/activated/first_action points
scheme).

Window: 2026-09-14 00:00 WITA (Asia/Makassar) inclusive → 2026-09-30 00:00
WITA exclusive — fixed, no CLI override, so this report and the live
`GET /api/dashboard/portal-challenge` widget can never disagree about "when".

Scoring, SQL and tier-award logic are NOT duplicated here: both live in
`backend.services.portal.challenge_leaderboard`, the single source the
dashboard router also imports. This script only adds the sys.path bootstrap
(mirrors `scripts/backfill_avatar_data_uris.py`) and the pg.sh/subprocess
plumbing — Postgres is prod, read-only, reached only through the Fly proxy,
never a direct connection.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ── path bootstrap (mirrors scripts/backfill_avatar_data_uris.py) ──────────
# `backend` is NOT editable-installed outside its own venv, so put
# apps/backend-rag on sys.path explicitly, derived from this file's location
# so the script is invocation-agnostic. Repo root = one parent up from
# scripts/. The imported module has no asyncpg/FastAPI import at module
# level, so this works with a plain system python3.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_DIR = _REPO_ROOT / "apps" / "backend-rag"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from backend.services.portal.challenge_leaderboard import (  # noqa: E402
    ROSTER_SQL,
    WINDOW_END,
    WINDOW_START,
    AwardedEntry,
    build_aggregates_sql,
    build_recent_activations_sql,
    compute_awards,
    compute_status,
    merge_roster_and_activity,
)

PG_SH = Path(__file__).resolve().parent / "pg.sh"


def _run_sql(sql: str, columns: list[str]) -> list[dict[str, str]]:
    """Run SQL via `pg.sh` in tuples-only mode (`-t`, no header/footer — the
    footer text is locale-dependent, e.g. "(0 righe)" vs "(0 rows)", so we
    suppress it rather than parse it) and zip each row against the caller-
    supplied column order, which must match the SELECT list exactly."""
    result = subprocess.run(
        [str(PG_SH), "-t", "-A", "-F", "\t", "-c", sql],
        capture_output=True,
        text=True,
        check=True,
    )
    rows = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        values = line.split("\t")
        rows.append(dict(zip(columns, values, strict=False)))
    return rows


def _parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _parse_int(value: str) -> int:
    return int(value) if value not in (None, "") else 0


_ROSTER_COLUMNS = ["email", "display_name", "department", "role", "active"]
_AGGREGATES_COLUMNS = ["creator_email", "activations", "invited", "last_activation_at"]
_RECENT_COLUMNS = ["creator_email", "used_at"]


def fetch_members() -> list:
    roster_raw = _run_sql(ROSTER_SQL, _ROSTER_COLUMNS)
    activity_raw = _run_sql(build_aggregates_sql(), _AGGREGATES_COLUMNS)
    activity_rows = [
        {
            "creator_email": r["creator_email"],
            "activations": _parse_int(r["activations"]),
            "invited": _parse_int(r["invited"]),
            "last_activation_at": _parse_ts(r.get("last_activation_at", "")),
        }
        for r in activity_raw
    ]
    return merge_roster_and_activity(roster_raw, activity_rows)


def fetch_recent_activations() -> list[dict[str, str]]:
    return _run_sql(build_recent_activations_sql(), _RECENT_COLUMNS)


def render_table(awarded: list[AwardedEntry], markdown: bool) -> str:
    headers = [
        "rank",
        "member",
        "display_name",
        "activations",
        "invited",
        "award_tier",
        "prize_idr",
        "tax_bonus_idr",
        "total_prize_idr",
    ]
    rows = [
        {
            "rank": e.rank,
            "member": e.member,
            "display_name": e.display_name,
            "activations": e.activations,
            "invited": e.invited,
            "award_tier": e.award_tier if e.award_tier is not None else "-",
            "prize_idr": e.prize_idr,
            "tax_bonus_idr": e.tax_bonus_idr,
            "total_prize_idr": e.total_prize_idr,
        }
        for e in awarded
    ]
    lines: list[str] = []
    if markdown:
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join(["---"] * len(headers)) + "|")
        for r in rows:
            lines.append("| " + " | ".join(str(r[h]) for h in headers) + " |")
    else:
        widths = {h: len(h) for h in headers}
        for r in rows:
            for h in headers:
                widths[h] = max(widths[h], len(str(r[h])))
        lines.append("  ".join(h.ljust(widths[h]) for h in headers))
        lines.append("  ".join("-" * widths[h] for h in headers))
        for r in rows:
            lines.append("  ".join(str(r[h]).ljust(widths[h]) for h in headers))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--markdown", action="store_true", help="Emit a Markdown table")
    args = parser.parse_args(argv)

    members = fetch_members()
    awarded = compute_awards(members)
    status = compute_status(datetime.now(WINDOW_START.tzinfo))

    sys.stdout.write(
        f"Window: {WINDOW_START.isoformat()} -> {WINDOW_END.isoformat()} "
        f"(status: {status})\n\n"
    )
    sys.stdout.write(render_table(awarded, markdown=args.markdown) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
