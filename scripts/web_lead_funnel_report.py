#!/usr/bin/env python3
"""Web-lead funnel report: how many leads our own surfaces actually deliver.

Every WhatsApp CTA on balizero.com mints a `lead_intents` row and opens the chat
with a prefilled message carrying a `li_<nanoid>` token. That token is the only
distinctive mark a lead carries into an inbox that also serves its owner's
private traffic, which is what makes this report possible at all.

THE TWO NUMBERS ARE NOT INTERCHANGEABLE, and this is the whole point:

    clicks  = rows in `lead_intents`      -> a CEILING. Somebody pressed the
              button; whether they ever sent the message is unknown here.
    arrived = tokens seen in the mirror   -> a FLOOR. A lead who deleted the
              prefill and typed their own words is invisible to us, forever.

A surface that shows one without the other invites a false read in whichever
direction flatters it, so both always travel together and are named in words.

The two halves live in two different databases and that is deliberate, not an
accident to be tidied away: `lead_intents` is on Fly, while the live wa-mirror
exists only on the Pro (the cloud copy froze on 2026-05-25 when the mirror was
cut off from the cloud on purpose -- Symbiosis Law 2 / UU PDP). This report
therefore reads two DSNs, the same two the matcher already reads, and carries
NOTHING out of the mirror except the token (a nanoid we minted ourselves) and
the surface label (our own prefill wording). Message bodies are read inside the
query and discarded there.

Usage:
    python scripts/web_lead_funnel_report.py            # text report
    python scripts/web_lead_funnel_report.py --json     # machine-readable
    python scripts/web_lead_funnel_report.py --telegram # + gateway digest
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lead_intent_matcher import extract_lead_ids  # noqa: E402  (shared token grammar)

# Postgres spelling of the SAME grammar `_LEAD_ID_RE` enforces in Python.
# It must stay a word-bounded match: `strpos(body, 'li_') > 0` -- the cheap
# prefilter the matcher uses before handing the text to the regex -- also fires
# on ordinary prose that merely contains those three characters. Measured on
# the live mirror 2026-08-06: the loose predicate returns 7 rows, the strict one
# returns the 4 real tokens. Counting the 7 would have invented three leads out
# of Italian and Indonesian words (scar family #3, guard-over-match).
TOKEN_REGEX_SQL = r"\mli_[a-z0-9]{6,20}\M"

# Two shapes of prefill are live in the historical data, so the surface name is
# read from the sentence every one of them carries, and the finer CTA position
# ("Source: Homepage Hero") is treated as a bonus -- it appears on 1 of the 4
# real tokens. A reader that REQUIRED it would report the other three as
# sourceless and quietly drop them.
SURFACE_REGEX_SQL = r"I just used the ([a-zA-Z ]+) on your site"
SOURCE_REGEX_SQL = r"Source: ([^\r\n]+)"

WINDOWS: tuple[tuple[str, int | None], ...] = (("7d", 7), ("30d", 30), ("all", None))

UNKNOWN = "UNKNOWN"


@dataclass
class SurfaceRow:
    surface: str
    clicks: int = 0
    matched: int = 0
    arrived: int | None = None  # None == not measurable (mirror unreachable)
    forwarded: int = 0


@dataclass
class WindowReport:
    label: str
    days: int | None
    clicks: int = 0
    matched: int = 0
    arrived: int | None = None
    # Tokens seen in a GROUP rather than a direct chat: somebody on the team
    # relayed a lead internally. Not an arrival, and counting it as one is the
    # mistake this field exists to prevent -- measured 2026-08-06, all four
    # tokens the system has ever seen are of this kind.
    forwarded: int = 0
    surfaces: list[SurfaceRow] = field(default_factory=list)
    mirror_status: str = "ok"


def _cutoff(days: int | None) -> datetime | None:
    if days is None:
        return None
    return datetime.now(timezone.utc) - timedelta(days=days)


def _normalise_surface(raw: str | None) -> str:
    """Fold a surface label to something both sides of the funnel can share.

    The two sides genuinely speak different dialects, measured 2026-08-06:
    `lead_intents.source` on Fly emits slugs (`homepage_hero`, `kbli_decoder`)
    while the prefill sentence yields prose (`homepage hero`, `pricing page`).
    Separators are folded so the mechanical half of that gap closes.

    What is deliberately NOT done here is inventing a dictionary between the
    two vocabularies. `pricing_modal` and `pricing page` may well be the same
    CTA, but nothing in the data says so, and a hand-written mapping would
    silently answer a question we never actually measured. They stay apart and
    the report marks them as one-sided — a visible gap beats a fabricated join.
    """
    if not raw:
        return "(unlabelled)"
    folded = raw.strip().lower().replace("_", " ").replace("-", " ")
    return " ".join(folded.split()) or "(unlabelled)"


async def _fetch_intents(conn: asyncpg.Connection, days: int | None) -> list[dict[str, Any]]:
    """Clicks and matches from Fly. `source` is the surface the CTA declared."""
    if days is None:
        rows = await conn.fetch(
            """
            SELECT source, matched_client_id
              FROM lead_intents
            """
        )
    else:
        rows = await conn.fetch(
            """
            SELECT source, matched_client_id
              FROM lead_intents
             WHERE created_at >= $1
            """,
            _cutoff(days),
        )
    return [dict(r) for r in rows]


async def _fetch_arrivals(conn: asyncpg.Connection, days: int | None) -> list[dict[str, Any]]:
    """Tokens that actually reached an inbox, from the wa-mirror.

    Only three values leave this query: the token, the surface label and the
    date. The body is matched against inside Postgres and never selected, so no
    message text -- ours or the lead's -- travels into this process.
    """
    # NB: built by concatenation, never `str.format`/`%`. The token grammar
    # contains `{6,20}`, which those two read as a format field and blow up on
    # -- and the failure surfaces as "the mirror is unreadable", i.e. pointing
    # at the healthy half of the system. Caught by the test suite, kept here as
    # a warning to the next person who reaches for .format().
    window_clause = "" if days is None else "AND COALESCE(message_date, created_at) >= $1"
    query = (
        "WITH t AS ("
        "  SELECT COALESCE(NULLIF(body, ''), message_text) AS txt,"
        "         CASE WHEN chat_type = 'direct' THEN 'direct' ELSE 'forwarded' END AS landed,"
        "         COALESCE(message_date, created_at)       AS at"
        "    FROM whatsapp_message_context"
        "   WHERE direction IN ('inbound', 'received')"
        "     AND COALESCE(NULLIF(body, ''), message_text, '') ~ '" + TOKEN_REGEX_SQL + "'"
        "     " + window_clause +
        ") "
        "SELECT DISTINCT"
        "  substring(txt from '" + TOKEN_REGEX_SQL + "') AS token,"
        "  landed,"
        "  COALESCE(substring(txt from '" + SOURCE_REGEX_SQL + "'),"
        "           substring(txt from '" + SURFACE_REGEX_SQL + "')) AS surface "
        "FROM t"
    )
    if days is None:
        rows = await conn.fetch(query)
    else:
        rows = await conn.fetch(query, _cutoff(days))
    out: list[dict[str, Any]] = []
    for r in rows:
        token = r["token"]
        # Belt and braces: the Python grammar is the authority on what counts
        # as a token, exactly as it is for the matcher. If the two ever drift,
        # this drops the row rather than inventing a lead.
        if not token or not extract_lead_ids(token):
            continue
        # .get so a row without the column degrades to "not a direct arrival"
        # rather than raising -- the conservative direction, since the number
        # this protects is the one nobody may inflate.
        out.append(
            {"token": token, "surface": r["surface"], "landed": r.get("landed")}
        )
    return out


async def build_report(dsn: str, mirror_dsn: str | None) -> list[WindowReport]:
    reports: list[WindowReport] = []

    fly = await asyncpg.connect(dsn)
    try:
        intents_by_window = {
            label: await _fetch_intents(fly, days) for label, days in WINDOWS
        }
    finally:
        await fly.close()

    # An absent or unreachable mirror must never read as "zero leads arrived":
    # that is the same sentence as "nobody came", and it is the one thing this
    # report exists to distinguish (scar family #2 -- a silent zero is how a
    # dead organ passes for a healthy one).
    arrivals_by_window: dict[str, list[dict[str, Any]]] = {}
    mirror_status = "ok"
    if not mirror_dsn:
        mirror_status = "WA_MIRROR_DATABASE_URL not set"
    else:
        try:
            mirror = await asyncpg.connect(mirror_dsn)
            try:
                for label, days in WINDOWS:
                    arrivals_by_window[label] = await _fetch_arrivals(mirror, days)
            finally:
                await mirror.close()
        except Exception as exc:  # noqa: BLE001 -- reported, never swallowed
            # Deliberately NOT phrased as "unreachable": this also catches bugs
            # in our own query, and a message that names a cause it did not
            # measure sends the reader to the wrong half of the system (W106).
            # The exception type is carried so the reader can tell a network
            # failure from a defect in this file.
            mirror_status = f"mirror read failed: {type(exc).__name__}: {exc}"
            arrivals_by_window = {}

    for label, days in WINDOWS:
        intents = intents_by_window[label]
        arrivals = arrivals_by_window.get(label)

        per_surface: dict[str, SurfaceRow] = {}
        for row in intents:
            key = _normalise_surface(row["source"])
            entry = per_surface.setdefault(key, SurfaceRow(surface=key))
            entry.clicks += 1
            if row["matched_client_id"]:
                entry.matched += 1

        if arrivals is not None:
            # The mirror WAS read, so every surface now has a measured arrival
            # count -- zero included. Leaving them at None would print UNKNOWN
            # next to a number we actually have, collapsing "not measurable"
            # and "nobody came through here" into one symbol; the whole report
            # exists to keep those two apart.
            for entry in per_surface.values():
                entry.arrived = 0
            for row in arrivals:
                key = _normalise_surface(row["surface"])
                entry = per_surface.setdefault(key, SurfaceRow(surface=key, arrived=0))
                if row.get("landed") == "direct":
                    entry.arrived = (entry.arrived or 0) + 1
                else:
                    entry.forwarded += 1

        rep = WindowReport(
            label=label,
            days=days,
            clicks=len(intents),
            matched=sum(1 for r in intents if r["matched_client_id"]),
            arrived=(
                None
                if arrivals is None
                else sum(1 for a in arrivals if a.get("landed") == "direct")
            ),
            forwarded=(
                0
                if arrivals is None
                else sum(1 for a in arrivals if a.get("landed") != "direct")
            ),
            surfaces=sorted(
                per_surface.values(), key=lambda s: (-s.clicks, s.surface)
            ),
            mirror_status=mirror_status,
        )
        reports.append(rep)
    return reports


def _fmt_arrived(value: int | None) -> str:
    return UNKNOWN if value is None else str(value)


def render_text(reports: list[WindowReport]) -> str:
    lines: list[str] = ["WEB LEAD FUNNEL — leads reaching us from our own surfaces", ""]
    for rep in reports:
        lines.append(f"── {rep.label} " + "─" * 40)
        lines.append(
            f"   clicks {rep.clicks} (ceiling)   "
            f"arrived {_fmt_arrived(rep.arrived)} (floor)   "
            f"matched to a client {rep.matched}"
        )
        if rep.forwarded:
            lines.append(
                f"   + {rep.forwarded} token(s) seen only in a GROUP — a team member"
                " relayed them internally. Not arrivals."
            )
        if rep.mirror_status != "ok":
            lines.append(f"   ⚠ arrived is {UNKNOWN}, not zero — {rep.mirror_status}")
        one_sided = False
        if rep.surfaces:
            for s in rep.surfaces:
                # A group relay is not an arrival; a label no CTA ever emitted
                # means the two sides name the same surface differently and we
                # refused to guess a mapping between them.
                if s.forwarded:
                    mark = f" ←{s.forwarded} relayed in a group, not arrivals"
                elif s.clicks == 0 and (s.arrived or 0) > 0:
                    mark = " ←label only on the arrival side"
                else:
                    mark = ""
                one_sided = one_sided or bool(mark)
                lines.append(
                    f"     · {s.surface:<28} clicks {s.clicks:>4}  "
                    f"arrived {_fmt_arrived(s.arrived):>4}  matched {s.matched:>3}{mark}"
                )
        else:
            lines.append("     (no activity in this window)")
        if one_sided:
            lines.append(
                "     note: the CTA emits slugs and the prefill emits prose, so some\n"
                "     surfaces appear on one side only. The window totals above are\n"
                "     unaffected — they count rows, not labels."
            )
        lines.append("")
    lines.append(
        "clicks counts button presses; arrived counts leads who actually SENT the\n"
        "prefilled message. A lead who retyped it in their own words is counted in\n"
        "neither arrived nor matched — the gap between the two is expected, not a bug."
    )
    return "\n".join(lines)


def send_telegram(text: str) -> None:
    gateway = Path(__file__).resolve().parent / "tg_notify.py"
    cmd = [
        sys.executable,
        str(gateway),
        "--tier",
        "digest",
        "--source",
        "web-lead-funnel",
        "--dedup-key",
        "web-lead-funnel:daily",
        "--",
        f"📈 Web leads | {text}",
    ]
    subprocess.run(cmd, capture_output=True, timeout=30, check=False)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--telegram", action="store_true", help="also send a digest")
    args = ap.parse_args()

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("FATAL: DATABASE_URL not set", file=sys.stderr)
        return 74
    mirror_dsn = os.environ.get("WA_MIRROR_DATABASE_URL")

    reports = asyncio.run(build_report(dsn, mirror_dsn))

    if args.json:
        print(
            json.dumps(
                [
                    {
                        "window": r.label,
                        "clicks": r.clicks,
                        "arrived": r.arrived,
                        "matched": r.matched,
                        "mirror_status": r.mirror_status,
                        "surfaces": [
                            {
                                "surface": s.surface,
                                "clicks": s.clicks,
                                "arrived": s.arrived,
                                "matched": s.matched,
                            }
                            for s in r.surfaces
                        ],
                    }
                    for r in reports
                ],
                indent=2,
            )
        )
    else:
        text = render_text(reports)
        print(text)
        if args.telegram:
            summary = next((r for r in reports if r.label == "7d"), reports[0])
            send_telegram(
                f"7d: {summary.clicks} clicks (ceiling), "
                f"{_fmt_arrived(summary.arrived)} arrived (floor), "
                f"{summary.matched} matched"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
