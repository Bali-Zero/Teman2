#!/usr/bin/env python3
"""Portal Challenge Leaderboard — read-only.

Round 1 (September, FROZEN): activation-count scheme decided by Zero on
2026-09-14. Window: 2026-09-14 00:00 WITA (Asia/Makassar) inclusive →
2026-09-29 00:00 WITA exclusive — fixed, no CLI override.

Round 2 (October, "Lascia o raddoppia"): carry + registration + document
bonus - penalty scheme decided by Zero on 2026-09-29. Window: 2026-09-29
00:00 WITA inclusive → 2026-10-30 00:00 WITA exclusive.

`--round {1,2}` forces a round; the default is whichever round is active
right now, so this report and the live `GET /api/dashboard/portal-challenge`
widget can never disagree about "when" or "which".

Scoring, SQL and award logic are NOT duplicated here: both live in
`backend.services.portal.challenge_leaderboard` (R1) and
`backend.services.portal.challenge_round2` (R2), the single sources the
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
# scripts/. Both imported modules have no asyncpg/FastAPI import at module
# level, so this works with a plain system python3.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_DIR = _REPO_ROOT / "apps" / "backend-rag"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from backend.services.portal import challenge_round2 as r2  # noqa: E402
from backend.services.portal.challenge_leaderboard import (  # noqa: E402
    ROSTER_SQL,
    WINDOW_END,
    WINDOW_START,
    AwardedEntry,
    build_aggregates_sql,
    build_recent_activations_sql,
    build_team_total_activations_sql,
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


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _parse_int(value: str | None) -> int:
    return int(value) if value not in (None, "") else 0


def _parse_optional_int(value: str | None) -> int | None:
    return int(value) if value not in (None, "") else None


_ROSTER_COLUMNS = ["email", "display_name", "department", "role", "active"]
_AGGREGATES_COLUMNS = ["creator_email", "activations", "invited", "last_activation_at"]
_RECENT_COLUMNS = ["creator_email", "used_at"]
_FIRST_DOCUMENT_COLUMNS = [
    "practice_id",
    "first_doc_at",
    "client_id",
    "practice_assignee",
    "client_assignee",
]
_REQUEST_COLUMNS = [
    "id",
    "client_id",
    "practice_id",
    "created_at",
    "reply_at",
    "client_assignee",
    "practice_assignee",
]
_REVIEW_COLUMNS = [
    "id",
    "practice_id",
    "client_id",
    "uploaded_at",
    "review_at",
    "practice_assignee",
    "client_assignee",
]
_ASYA_REQUEST_COLUMNS = ["client_id", "created_at"]
_ASYA_EVENT_COLUMNS = ["client_id", "practice_id", "created_at"]


def _parse_activity_rows(raw: list[dict[str, str]]) -> list[dict]:
    """Shared parser for the `_AGGREGATES_COLUMNS` shape — used by both
    rounds' registration/activation aggregates."""
    return [
        {
            "creator_email": r["creator_email"],
            "activations": _parse_int(r["activations"]),
            "invited": _parse_int(r["invited"]),
            "last_activation_at": _parse_ts(r.get("last_activation_at")),
        }
        for r in raw
    ]


# ── Round 1 (frozen) ─────────────────────────────────────────────────────


def fetch_members() -> list:
    roster_raw = _run_sql(ROSTER_SQL, _ROSTER_COLUMNS)
    activity_rows = _parse_activity_rows(_run_sql(build_aggregates_sql(), _AGGREGATES_COLUMNS))
    return merge_roster_and_activity(roster_raw, activity_rows)


def fetch_recent_activations() -> list[dict[str, str]]:
    return _run_sql(build_recent_activations_sql(), _RECENT_COLUMNS)


def fetch_team_total_activations() -> int:
    """DISTINCT client_id across the whole window — NOT sum(activations)
    across members, which would double-count a client credited to two
    different creators. Same query the endpoint uses."""
    rows = _run_sql(build_team_total_activations_sql(), ["team_total_activations"])
    return _parse_int(rows[0]["team_total_activations"]) if rows else 0


def _render_rows(headers: list[str], rows: list[dict], markdown: bool) -> str:
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
    return _render_rows(headers, rows, markdown)


def _main_round1(args: argparse.Namespace, now: datetime) -> int:
    members = fetch_members()
    awarded = compute_awards(members)
    status = compute_status(now)
    team_total = fetch_team_total_activations()

    sys.stdout.write(
        f"Round 1 (September) window: {WINDOW_START.isoformat()} -> {WINDOW_END.isoformat()} "
        f"(status: {status})\n"
        f"Team total activations (distinct clients): {team_total}\n\n"
    )
    sys.stdout.write(render_table(awarded, markdown=args.markdown) + "\n")
    return 0


# ── Round 2 ("Lascia o raddoppia") ───────────────────────────────────────


def fetch_round2_snapshot(now: datetime) -> r2.Round2Snapshot:
    roster_raw = _run_sql(ROSTER_SQL, _ROSTER_COLUMNS)
    r1_activity_rows = _parse_activity_rows(_run_sql(build_aggregates_sql(), _AGGREGATES_COLUMNS))
    r1_awarded = compute_awards(merge_roster_and_activity(roster_raw, r1_activity_rows))

    registration_rows = _parse_activity_rows(
        _run_sql(r2.build_registration_aggregates_sql(), _AGGREGATES_COLUMNS)
    )

    first_document_rows = [
        {
            "practice_id": _parse_int(r["practice_id"]),
            "first_doc_at": _parse_ts(r["first_doc_at"]),
            "client_id": _parse_int(r["client_id"]),
            "practice_assignee": r.get("practice_assignee") or None,
            "client_assignee": r.get("client_assignee") or None,
        }
        for r in _run_sql(r2.build_first_documents_sql(), _FIRST_DOCUMENT_COLUMNS)
    ]

    request_rows = [
        {
            "client_id": _parse_int(r["client_id"]),
            "practice_id": _parse_optional_int(r["practice_id"]),
            "created_at": _parse_ts(r["created_at"]),
            "reply_at": _parse_ts(r.get("reply_at")),
            "client_assignee": r.get("client_assignee") or None,
            "practice_assignee": r.get("practice_assignee") or None,
        }
        for r in _run_sql(r2.build_client_requests_sql(), _REQUEST_COLUMNS)
    ]

    review_rows = [
        {
            "id": _parse_int(r["id"]),
            "practice_id": _parse_int(r["practice_id"]),
            "client_id": _parse_int(r["client_id"]),
            "uploaded_at": _parse_ts(r["uploaded_at"]),
            "review_at": _parse_ts(r.get("review_at")),
            "practice_assignee": r.get("practice_assignee") or None,
            "client_assignee": r.get("client_assignee") or None,
        }
        for r in _run_sql(r2.build_required_document_reviews_sql(), _REVIEW_COLUMNS)
    ]

    asya_request_rows = [
        {"client_id": _parse_int(r["client_id"]), "created_at": _parse_ts(r["created_at"])}
        for r in _run_sql(r2.build_asya_requests_sql(), _ASYA_REQUEST_COLUMNS)
    ]

    asya_client_event_rows = [
        {
            "client_id": _parse_int(r["client_id"]),
            "practice_id": _parse_optional_int(r["practice_id"]),
            "created_at": _parse_ts(r["created_at"]),
        }
        for r in _run_sql(r2.build_asya_client_events_sql(), _ASYA_EVENT_COLUMNS)
    ]

    return r2.score_round2(
        roster_raw,
        r1_awarded,
        registration_rows,
        first_document_rows,
        request_rows,
        review_rows,
        asya_request_rows,
        asya_client_event_rows,
        now,
    )


def render_round2_table(entries: list[r2.Round2Entry], markdown: bool) -> str:
    headers = [
        "rank",
        "member",
        "display_name",
        "points",
        "carry",
        "reg",
        "docs",
        "unans",
        "unrev",
        "penalty",
        "slot",
        "prize_idr",
        "choice",
    ]
    rows = [
        {
            "rank": e.rank,
            "member": e.member,
            "display_name": e.display_name,
            "points": e.points,
            "carry": e.carry_points,
            "reg": e.registrations,
            "docs": e.document_bonuses,
            "unans": e.unanswered_requests,
            "unrev": e.unreviewed_documents,
            "penalty": e.penalty_points,
            "slot": e.prize_slot if e.prize_slot is not None else "-",
            "prize_idr": e.prize_idr,
            "choice": e.september_choice or "-",
        }
        for e in entries
    ]
    return _render_rows(headers, rows, markdown)


def _main_round2(args: argparse.Namespace, now: datetime) -> int:
    snapshot = fetch_round2_snapshot(now)
    status = r2.compute_round_status(now, 2)

    sys.stdout.write(
        f"Round 2 (Lascia o raddoppia) window: {r2.ROUND2_START.isoformat()} -> "
        f"{r2.ROUND2_END.isoformat()} (status: {status})\n"
        f"Team total points: {snapshot.team_total_points}\n\n"
    )
    sys.stdout.write(render_round2_table(snapshot.entries, markdown=args.markdown) + "\n\n")

    mission = snapshot.asya_mission
    sys.stdout.write(
        f"Asya mission: {mission.points}/{mission.target_points} points "
        f"({'REACHED' if mission.reached else 'in progress'}) — "
        f"{mission.mission_bonuses} bonuses, {mission.penalty_points} penalty points\n"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--markdown", action="store_true", help="Emit a Markdown table")
    parser.add_argument(
        "--round",
        type=int,
        choices=(1, 2),
        default=None,
        help="Force a round; default is whichever round is active right now",
    )
    args = parser.parse_args(argv)

    now = datetime.now(WINDOW_START.tzinfo)
    round_number = args.round or r2.active_round(now)

    if round_number == 1:
        return _main_round1(args, now)
    return _main_round2(args, now)


if __name__ == "__main__":
    sys.exit(main())
