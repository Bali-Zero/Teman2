#!/usr/bin/env python3
"""Ask Google what we spent, not our own ledger.

WHY THIS EXISTS (2026-08-12, measured — not a hypothesis). A dev API key created
on M5 for a verifier A/B made **5,344 successful billable Gemini calls** over
three days. The cost ledger (``llm_cost_events``) held **zero** rows for them,
because the ledger only ever sees what passes through ``record_llm_call``. That
traffic drained the prepay balance the production WhatsApp bot spends from, and
the bot went silent. Every cost check in this repo reads the ledger:
``cost_breaker.py`` sums it, ``check_llm_cost_tracking.py`` lints a fixed list of
repo directories. Both were green throughout. **They share the blindness they are
meant to cover** — a ledger cannot report a call that never reached it, and a
repo lint cannot see a harness that is not in the repo.

Cloud Monitoring is the independent observer: it counts requests at Google's
edge, per API credential, whether or not our code chose to write a row.

Corrects a stated belief while it is at it: ``cost_breaker.py``'s HONEST LIMIT
says the provider's real quota "is not machine-readable". For Gemini that is no
longer true — ``serviceruntime.googleapis.com/api/request_count`` is readable and
carries ``credential_id``. (Token counts still are not: the quota metrics on this
project expose ``api_requests`` / ``generate_content_requests`` only, so this
organ counts CALLS and never claims dollars.)

THE PRIMARY CHECK IS AN ENTITY CHECK, NOT A THRESHOLD. The set of credentials
making successful Gemini calls must equal what ``infra/llm-credentials/declared.json``
declares. A second key alarms on day one at any volume — on 2026-08-09 the new key
made 457 calls against the ledger's 52, and a volume threshold tuned to be quiet
would have had to be set below that to catch it. Entity checks do not need tuning
and do not drift.

Exit code is a BIT FIELD, and the bits never merge (W106b: an organ that reports
"there is drift" when the truth is "I could not look" spends someone's session on
a false premise):

    0  clean
    1  FOREIGN CREDENTIAL — an undeclared credential made successful calls
    2  UNSEEN CALLS       — Google counted more billable calls than the ledger has rows
    4  CANNOT-VERIFY      — could not read Monitoring (or the ledger, when asked to compare)

Usage:
    python3 scripts/llm_provider_reconcile.py --day 2026-08-11
    python3 scripts/llm_provider_reconcile.py --day 2026-08-11 --no-ledger
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DECLARED_PATH = REPO_ROOT / "infra" / "llm-credentials" / "declared.json"
PG_HELPER = REPO_ROOT / "scripts" / "pg.sh"

PROJECT = "nuzantara"
SERVICE = "generativelanguage.googleapis.com"
MONITORING_URL = "https://monitoring.googleapis.com/v3/projects/{project}/timeSeries"

# WITA is UTC+8: a local day is [D-1 16:00Z, D 16:00Z).
WITA_OFFSET_HOURS = 8

EXIT_FOREIGN = 1
EXIT_UNSEEN = 2
EXIT_CANNOT_VERIFY = 4

# The ledger writes its row after the call returns, so a call straddling the
# window edge can land on either side. Anything at or under this is timing, not
# a missing writer.
UNSEEN_TOLERANCE = 25


def credential_fingerprint(uid: str) -> str:
    """sha256(uid)[:16] — what the declared file carries instead of the uid.

    The uid authenticates nothing, so this is minimisation (a public repo does
    not need to carry infrastructure identifiers), not secrecy.
    """
    return hashlib.sha256(uid.encode()).hexdigest()[:16]


@dataclass
class Observation:
    """What Google saw, per credential, in the window."""

    successful: dict[str, int] = field(default_factory=dict)  # uid -> billable OK calls
    rejected: dict[str, int] = field(default_factory=dict)  # uid -> non-2xx calls
    series_seen: int = 0

    @property
    def total_successful(self) -> int:
        return sum(self.successful.values())


@dataclass
class Verdict:
    day: str
    observation: Observation
    foreign: list[tuple[str, int]]  # (uid, successful calls)
    ledger_rows: int | None
    unseen: int | None
    cannot_verify: list[str]

    @property
    def exit_code(self) -> int:
        code = 0
        if self.foreign:
            code |= EXIT_FOREIGN
        if self.unseen is not None and self.unseen > UNSEEN_TOLERANCE:
            code |= EXIT_UNSEEN
        if self.cannot_verify:
            code |= EXIT_CANNOT_VERIFY
        return code


def wita_day_bounds(day: date) -> tuple[str, str]:
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc) - timedelta(
        hours=WITA_OFFSET_HOURS
    )
    return (
        start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        (start + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def _access_token() -> str:
    proc = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(
            f"gcloud auth print-access-token failed (rc={proc.returncode})"
        )
    return proc.stdout.strip()


def fetch_observation(
    start: str, end: str, *, project: str = PROJECT, token: str | None = None
) -> Observation:
    """Read per-credential request counts from Cloud Monitoring.

    Raises on any failure — the caller turns that into CANNOT-VERIFY. It must
    never degrade to an empty Observation: zero series read as "nobody called
    Gemini today", which on a live product is a lie shaped exactly like health.
    """
    token = token or _access_token()
    query = urllib.parse.urlencode(
        {
            "filter": (
                'metric.type="serviceruntime.googleapis.com/api/request_count" '
                'AND resource.type="consumed_api" '
                f'AND resource.labels.service="{SERVICE}"'
            ),
            "interval.startTime": start,
            "interval.endTime": end,
            "aggregation.alignmentPeriod": "86400s",
            "aggregation.perSeriesAligner": "ALIGN_SUM",
            "pageSize": "2000",
        }
    )
    request = urllib.request.Request(
        f"{MONITORING_URL.format(project=project)}?{query}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:  # noqa: S310 - fixed host
        payload = json.load(response)

    if payload.get("nextPageToken"):
        # A truncated list read as complete is how a capped probe reports health
        # it never measured (W97). Refuse rather than under-report.
        raise RuntimeError(
            "Monitoring paginated the series list; refusing a partial read"
        )

    return _parse_observation(payload)


def _parse_observation(payload: dict) -> Observation:
    series = payload.get("timeSeries", [])
    obs = Observation(series_seen=len(series))
    for entry in series:
        uid = entry.get("resource", {}).get("labels", {}).get("credential_id", "")
        uid = uid.replace("apikey:", "") or "UNKNOWN"
        code = entry.get("metric", {}).get("labels", {}).get("response_code", "")
        method = entry.get("resource", {}).get("labels", {}).get("method", "")
        total = sum(int(p["value"]["int64Value"]) for p in entry.get("points", []))
        if not total:
            continue
        # Only GenerateContent 2xx is billable. 429/404/400 cost nothing, and
        # counting them as spend would manufacture a gap that is not money.
        if code.startswith("2") and method.endswith("GenerateContent"):
            obs.successful[uid] = obs.successful.get(uid, 0) + total
        else:
            obs.rejected[uid] = obs.rejected.get(uid, 0) + total
    return obs


def load_declared(path: Path = DECLARED_PATH) -> dict[str, str]:
    data = json.loads(path.read_text())
    return {c["sha256_16"]: c["label"] for c in data["credentials"]}


def fetch_ledger_rows(start: str, end: str) -> int:
    """Count gemini rows the ledger wrote in the same window."""
    sql = (
        "SELECT count(*) FROM llm_cost_events WHERE provider='gemini' "
        f"AND ts_utc >= '{start}' AND ts_utc < '{end}';"
    )
    proc = subprocess.run(
        ["bash", str(PG_HELPER), "-tAc", sql],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(REPO_ROOT),
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"ledger query failed (rc={proc.returncode}): {proc.stderr[:200]}"
        )
    for line in proc.stdout.splitlines():
        if line.strip().isdigit():
            return int(line.strip())
    raise RuntimeError(f"ledger query returned no count: {proc.stdout[:200]!r}")


def reconcile(day: date, *, compare_ledger: bool = True) -> Verdict:
    start, end = wita_day_bounds(day)
    cannot: list[str] = []

    try:
        observation = fetch_observation(start, end)
    except Exception as exc:  # noqa: BLE001 - every failure is CANNOT-VERIFY, by design
        return Verdict(
            day=day.isoformat(),
            observation=Observation(),
            foreign=[],
            ledger_rows=None,
            unseen=None,
            cannot_verify=[f"Monitoring unreadable: {exc}"],
        )

    if observation.series_seen == 0:
        # Distinguish "nobody called" from "I could not look". A live product
        # with a scheduled credit probe is never at zero series.
        cannot.append(
            "Monitoring returned 0 series — treated as unread, not as silence"
        )

    declared = load_declared()
    foreign = [
        (uid, count)
        for uid, count in sorted(observation.successful.items(), key=lambda kv: -kv[1])
        if credential_fingerprint(uid) not in declared
    ]

    ledger_rows: int | None = None
    unseen: int | None = None
    if compare_ledger:
        try:
            ledger_rows = fetch_ledger_rows(start, end)
            unseen = observation.total_successful - ledger_rows
        except Exception as exc:  # noqa: BLE001
            cannot.append(f"Ledger unreadable: {exc}")

    return Verdict(
        day=day.isoformat(),
        observation=observation,
        foreign=foreign,
        ledger_rows=ledger_rows,
        unseen=unseen,
        cannot_verify=cannot,
    )


def render(verdict: Verdict) -> str:
    obs = verdict.observation
    lines = [f"LLM provider reconcile — WITA day {verdict.day}", ""]
    lines.append(f"  Google billable calls : {obs.total_successful}")
    lines.append(
        f"  ledger gemini rows    : {verdict.ledger_rows if verdict.ledger_rows is not None else 'not compared'}"
    )
    if verdict.unseen is not None:
        lines.append(
            f"  unseen by the ledger  : {verdict.unseen} (tolerance {UNSEEN_TOLERANCE})"
        )
    lines.append("")
    lines.append("  credentials with successful calls:")
    declared = load_declared()
    for uid, count in sorted(obs.successful.items(), key=lambda kv: -kv[1]):
        fp = credential_fingerprint(uid)
        label = declared.get(fp)
        mark = "  declared" if label else "  UNDECLARED"
        lines.append(f"    {uid[:8]}…  {count:>6} calls {mark}  {label or ''}")
    if obs.rejected:
        lines.append("")
        lines.append("  (rejected, unbilled — informational)")
        for uid, count in sorted(obs.rejected.items(), key=lambda kv: -kv[1]):
            lines.append(f"    {uid[:8]}…  {count:>6}")

    if verdict.foreign:
        lines += ["", "FOREIGN CREDENTIAL — spending outside the ledger's sight:"]
        for uid, count in verdict.foreign:
            lines.append(
                f"    {uid[:8]}…  {count} successful calls. Name it in "
                f"{DECLARED_PATH.relative_to(REPO_ROOT)} if it is legitimate, or restrict it."
            )
    if verdict.unseen is not None and verdict.unseen > UNSEEN_TOLERANCE:
        lines += [
            "",
            f"UNSEEN CALLS — {verdict.unseen} billable calls Google counted and the ledger did not.",
            "    Either a call site skips record_llm_call, or it runs outside this backend.",
        ]
    for reason in verdict.cannot_verify:
        lines += ["", f"CANNOT-VERIFY — {reason}"]
    if verdict.exit_code == 0:
        lines += [
            "",
            "clean: every successful call came from a declared credential and the ledger saw it.",
        ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--day",
        default=(datetime.now(timezone.utc) + timedelta(hours=WITA_OFFSET_HOURS))
        .date()
        .isoformat(),
        help="WITA day to reconcile (YYYY-MM-DD, default today WITA)",
    )
    parser.add_argument(
        "--no-ledger",
        action="store_true",
        help="skip the ledger comparison (credential check only)",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit machine-readable output"
    )
    args = parser.parse_args(argv)

    verdict = reconcile(date.fromisoformat(args.day), compare_ledger=not args.no_ledger)
    if args.json:
        print(
            json.dumps(
                {
                    "day": verdict.day,
                    "google_billable": verdict.observation.total_successful,
                    "ledger_rows": verdict.ledger_rows,
                    "unseen": verdict.unseen,
                    "foreign": [
                        {"uid_prefix": u[:8], "calls": c} for u, c in verdict.foreign
                    ],
                    "cannot_verify": verdict.cannot_verify,
                    "exit_code": verdict.exit_code,
                },
                indent=2,
            )
        )
    else:
        print(render(verdict))
    return verdict.exit_code


if __name__ == "__main__":
    sys.exit(main())
