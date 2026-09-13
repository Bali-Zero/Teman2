#!/usr/bin/env python3
"""Portal Challenge Leaderboard — read-only, spec `spec-portal-launch-kit.md` §9/§12.

Prints per-member standings for the "Portal Champion" challenge (14-29 Sept
2026, Asia/Makassar / WITA window): clients invited, activated, and given a
first action inside the window, plus the derived points and ratio.

Never opens a DB connection directly (Postgres is prod, read-only, reached
only through the Fly proxy). All SQL goes through `scripts/pg.sh -c "<SQL>"`
via subprocess, resolved relative to this file so the script works from any
cwd — same convention as every other `scripts/*.py` read-only report.

Column names (verified on disk 2026-09-12, `scripts/pg.sh -c "\\d <table>"`):
  client_invitations(id, client_id, email, token, expires_at, used_at,
                      created_by, created_at)
  documents(id, client_id, uploaded_source, created_at, deleted_at, ...)
  portal_messages(id, client_id, direction, created_at, ...)
  clients(id, tags, deleted_at, email, ...)

Points (spec §9): invited*1 + activated*3 + first_action*2.
"invited" counts a client only under the member who created that client's
FIRST invitation inside the window (an older, never-used invitation does
not block the client; a client already activated before the window earns
nothing), and a resend is a later row for the same client, never a second point.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

WITA = ZoneInfo("Asia/Makassar")
PG_SH = Path(__file__).resolve().parent / "pg.sh"

DEFAULT_START = "2026-09-14"
DEFAULT_END = "2026-09-29"

SQL_TEMPLATE = """
WITH real_clients AS (
    SELECT c.id
    FROM clients c
    WHERE c.deleted_at IS NULL
      AND NOT (COALESCE(c.tags, ARRAY[]::text[]) && ARRAY['test', 'portal-pilot']::text[])
),
eligible_invites AS (
    SELECT ci.client_id, ci.created_by, ci.created_at, ci.used_at
    FROM client_invitations ci
    JOIN real_clients c ON c.id = ci.client_id
    WHERE lower(ci.email) NOT LIKE '%@balizero.com'
      AND ci.email NOT LIKE '%+%@%'
      -- Only a human staff account competes: bulk jobs and system senders
      -- (e.g. portal_bulk_invite_v1) are not team members.
      AND lower(ci.created_by) LIKE '%@balizero.com'
),
already_active AS (
    -- A client who activated BEFORE the window earns nothing when re-invited.
    SELECT DISTINCT client_id
    FROM client_invitations
    WHERE used_at IS NOT NULL
      AND used_at < TIMESTAMP WITH TIME ZONE '{start_ts}'
),
window_invites AS (
    -- One row per client: the FIRST invitation inside the window, credited to
    -- its sender. A "Send again" is a later row for the same client, so it can
    -- never add a second point.
    SELECT DISTINCT ON (client_id) client_id, created_by, created_at
    FROM eligible_invites
    WHERE created_at >= TIMESTAMP WITH TIME ZONE '{start_ts}'
      AND created_at <  TIMESTAMP WITH TIME ZONE '{end_ts}'
      AND client_id NOT IN (SELECT client_id FROM already_active)
    ORDER BY client_id, created_at
),
activations AS (
    SELECT DISTINCT client_id
    FROM eligible_invites
    WHERE used_at IS NOT NULL
      AND used_at >= TIMESTAMP WITH TIME ZONE '{start_ts}'
      AND used_at <  TIMESTAMP WITH TIME ZONE '{end_ts}'
),
first_actions AS (
    SELECT DISTINCT client_id FROM (
        SELECT client_id FROM documents
        WHERE uploaded_source = 'client' AND deleted_at IS NULL
          AND created_at >= TIMESTAMP WITH TIME ZONE '{start_ts}'
          AND created_at <  TIMESTAMP WITH TIME ZONE '{end_ts}'
        UNION
        SELECT client_id FROM portal_messages
        WHERE direction = 'client_to_team'
          AND created_at >= TIMESTAMP WITH TIME ZONE '{start_ts}'
          AND created_at <  TIMESTAMP WITH TIME ZONE '{end_ts}'
    ) actions
)
SELECT
    split_part(lower(wi.created_by), '@', 1) AS member,
    COUNT(DISTINCT wi.client_id) AS invited,
    COUNT(DISTINCT a.client_id) AS activated,
    COUNT(DISTINCT fa.client_id) AS first_action
FROM window_invites wi
LEFT JOIN activations a ON a.client_id = wi.client_id
LEFT JOIN first_actions fa ON fa.client_id = a.client_id
GROUP BY 1
ORDER BY 1;
""".strip()


def score(invited: int, activated: int, first_action: int) -> int:
    """Pure points function (spec §9): invited*1 + activated*3 + first_action*2."""
    return invited * 1 + activated * 3 + first_action * 2


def _window_bounds(start: str, end: str) -> tuple[str, str]:
    """WITA day-boundary timestamps: start 00:00 WITA, end EXCLUSIVE = (end+1) 00:00 WITA."""
    start_dt = datetime.combine(date.fromisoformat(start), datetime.min.time(), tzinfo=WITA)
    end_exclusive_dt = datetime.combine(
        date.fromisoformat(end) + timedelta(days=1), datetime.min.time(), tzinfo=WITA
    )
    return start_dt.isoformat(), end_exclusive_dt.isoformat()


def _run_sql(sql: str) -> str:
    result = subprocess.run(
        [str(PG_SH), "-t", "-A", "-F", "\t", "-c", sql],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _parse_rows(raw: str) -> list[tuple[str, int, int, int]]:
    rows: list[tuple[str, int, int, int]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        member, invited, activated, first_action = line.split("\t")
        rows.append((member, int(invited), int(activated), int(first_action)))
    return rows


def build_table(start: str, end: str) -> list[dict[str, object]]:
    start_ts, end_ts = _window_bounds(start, end)
    sql = SQL_TEMPLATE.format(start_ts=start_ts, end_ts=end_ts)
    raw = _run_sql(sql)
    rows = []
    for member, invited, activated, first_action in _parse_rows(raw):
        points = score(invited, activated, first_action)
        ratio = activated / invited if invited else 0.0
        rows.append(
            {
                "member": member,
                "invited": invited,
                "activated": activated,
                "first_action": first_action,
                "points": points,
                "ratio": ratio,
            }
        )
    rows.sort(key=lambda r: r["points"], reverse=True)
    return rows


def render_table(rows: list[dict[str, object]], markdown: bool) -> str:
    headers = ["member", "invited", "activated", "first_action", "points", "ratio"]
    lines: list[str] = []
    if markdown:
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join(["---"] * len(headers)) + "|")
        for r in rows:
            lines.append(
                "| {member} | {invited} | {activated} | {first_action} | {points} | {ratio:.2f} |".format(
                    **r
                )
            )
    else:
        widths = {h: len(h) for h in headers}
        str_rows = [
            {**r, "ratio": f"{r['ratio']:.2f}"}  # type: ignore[dict-item]
            for r in rows
        ]
        for r in str_rows:
            for h in headers:
                widths[h] = max(widths[h], len(str(r[h])))
        header_line = "  ".join(h.ljust(widths[h]) for h in headers)
        lines.append(header_line)
        lines.append("  ".join("-" * widths[h] for h in headers))
        for r in str_rows:
            lines.append("  ".join(str(r[h]).ljust(widths[h]) for h in headers))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=DEFAULT_START, help="Window start (YYYY-MM-DD, WITA)")
    parser.add_argument(
        "--end", default=DEFAULT_END, help="Window end, INCLUSIVE (YYYY-MM-DD, WITA)"
    )
    parser.add_argument("--markdown", action="store_true", help="Emit a Markdown table")
    args = parser.parse_args(argv)

    rows = build_table(args.start, args.end)
    sys.stdout.write(render_table(rows, markdown=args.markdown) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
