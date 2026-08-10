#!/usr/bin/env python3
"""imigrasi-mirror SELF-HEALTH check — does the mirror still RUN?

The mirror (run.py) alerts on content DIFFS. It is structurally blind to its
own death: if the cron is unloaded, the venv breaks, WireGuard is down, or the
site 5xxs every page, run.py either never executes or writes an empty capture —
and in both cases NO diff fires, so the channel stays silent while the sentinel
is dead. That silence is the exact failure a mirror exists to prevent, turned
on the mirror itself (scar family #2 "Esiste ≠ Armato").

This checker is deliberately SEPARATE from run.py and shares none of its
failure surface (scar W108 — "the alarm must not share the failure mode of the
thing it reports"): it is pure stdlib (no venv, no httpx, no network to the
mirrored site), it runs on its OWN LaunchAgent schedule (after the mirror
should have run), and it reads a heartbeat file the mirror writes OUTSIDE its
own data repo. If the mirror is dead, this is still alive to say so.

The decision is a pure function (`evaluate_health`) tested in `--selftest`
without any network — the classifier's OUTCOME is asserted, not merely that it
ran (scar W110/W116).

Usage:
    healthcheck.py                       # read heartbeat, alert if unhealthy
    healthcheck.py --max-age-hours 26    # staleness threshold (daily → 26h)
    healthcheck.py --no-alert            # print verdict only, never send TG
    healthcheck.py --selftest            # no network — guilt+innocence pairs
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# The heartbeat lives OUTSIDE the mirror's git data repo (so it never pollutes
# the "nothing_to_commit" clean signal) and alongside the launchd logs. run.py
# writes it; this checker reads it. Same default on both sides — keep in sync.
DEFAULT_HEARTBEAT = os.environ.get("IMIGRASI_MIRROR_HEARTBEAT") or str(
    Path.home() / "logs" / "imigrasi-mirror-heartbeat.json"
)


def read_heartbeat(path: str) -> dict | None:
    """Returns the parsed heartbeat, or None if absent/unreadable (an absent
    heartbeat is itself a CRITICAL verdict, not an error to swallow)."""
    p = Path(path).expanduser()
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"__malformed__": True}


def evaluate_health(
    hb: dict | None, now_epoch: float, max_age_hours: float, max_failed: int
) -> tuple[str, str] | None:
    """Pure decision function. Returns (severity, message) if unhealthy, or
    None if healthy. No I/O, no network — the whole verdict is derivable from
    its arguments, which is what makes `--selftest` able to assert OUTCOMES.

    Order matters: absence/staleness (the mirror didn't run) outranks in-run
    failures (it ran but stumbled), because a stale heartbeat's captured/failed
    counts describe an OLD run and must not be read as today's health."""
    if hb is None:
        return ("CRITICAL", "heartbeat ABSENT — the mirror may never have run, or its log dir was wiped")
    if hb.get("__malformed__"):
        return ("CRITICAL", "heartbeat MALFORMED — unreadable JSON where a run summary should be")
    last = hb.get("last_run_epoch")
    if not isinstance(last, (int, float)):
        return ("CRITICAL", "heartbeat has no numeric last_run_epoch — cannot judge staleness")

    age_h = (now_epoch - last) / 3600.0
    if age_h > max_age_hours:
        return (
            "CRITICAL",
            f"STALE — last run {hb.get('last_run_iso', '?')} was {age_h:.1f}h ago "
            f"(> {max_age_hours:g}h); tier={hb.get('tier', '?')}. The cron/LaunchAgent "
            f"may be unloaded or the machine was off.",
        )

    requested = hb.get("pages_requested", 0) or 0
    captured = hb.get("captured", 0) or 0
    failed = hb.get("failed", 0) or 0
    if requested and captured == 0:
        return (
            "CRITICAL",
            f"ran {hb.get('last_run_iso', '?')} but captured 0/{requested} pages — "
            f"network down, WireGuard/proxy dead, or the site is 5xx'ing everything.",
        )
    if failed > max_failed:
        return (
            "WARN",
            f"ran {hb.get('last_run_iso', '?')} but {failed}/{requested} pages FAILED "
            f"({', '.join(hb.get('failed_ids', [])[:6])}{'…' if len(hb.get('failed_ids', [])) > 6 else ''}); "
            f"age {age_h:.1f}h.",
        )
    return None


def _summarize(hb: dict | None) -> str:
    if not hb or hb.get("__malformed__"):
        return "no valid heartbeat"
    return (
        f"last_run={hb.get('last_run_iso', '?')} tier={hb.get('tier', '?')} "
        f"captured={hb.get('captured', '?')}/{hb.get('pages_requested', '?')} "
        f"failed={hb.get('failed', '?')} diffs={hb.get('diffs', '?')}"
    )


def selftest() -> int:
    """No-network: assert the OUTCOME of evaluate_health on guilt+innocence
    pairs (never just that it ran — scar W110/W116)."""
    now = 1_000_000.0
    H = 3600.0
    base = {
        "last_run_epoch": now - 1 * H,
        "last_run_iso": "2026-08-08T06:30:00+0800",
        "tier": "daily",
        "pages_requested": 9,
        "captured": 9,
        "failed": 0,
        "failed_ids": [],
    }
    failures: list[str] = []

    def check(name: str, cond: bool) -> None:
        print(("  ok  " if cond else "  FAIL") + f" {name}")
        if not cond:
            failures.append(name)

    def sev(hb, max_age=26.0, max_failed=0):
        v = evaluate_health(hb, now, max_age, max_failed)
        return v[0] if v else None

    # innocence
    check("healthy fresh full-capture run -> no alert", evaluate_health(base, now, 26, 0) is None)
    check("exactly at max-age boundary -> still healthy (age == max, not >)",
          evaluate_health({**base, "last_run_epoch": now - 26 * H}, now, 26, 0) is None)
    # guilt — liveness
    check("absent heartbeat -> CRITICAL", sev(None) == "CRITICAL")
    check("malformed heartbeat -> CRITICAL", sev({"__malformed__": True}) == "CRITICAL")
    check("no numeric last_run_epoch -> CRITICAL", sev({"last_run_epoch": None}) == "CRITICAL")
    check("stale beyond max-age -> CRITICAL", sev({**base, "last_run_epoch": now - 30 * H}) == "CRITICAL")
    # guilt — in-run
    check("ran but captured 0 of N -> CRITICAL", sev({**base, "captured": 0}) == "CRITICAL")
    check("partial page failures -> WARN", sev({**base, "captured": 7, "failed": 2, "failed_ids": ["voa", "bvk"]}) == "WARN")
    # innocence — a first-ever weekly with 0 requested must not false-CRITICAL on captured==0
    check("0 requested pages -> not a captured-0 CRITICAL (vacuous, healthy)",
          evaluate_health({**base, "pages_requested": 0, "captured": 0}, now, 26, 0) is None)
    # liveness outranks in-run: a STALE run with failures reads CRITICAL(stale), not WARN
    check("stale AND failed -> CRITICAL (liveness outranks in-run failures)",
          sev({**base, "last_run_epoch": now - 40 * H, "failed": 3}) == "CRITICAL")

    print("SELFTEST", "PASS" if not failures else f"FAIL ({failures})")
    return 0 if not failures else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--heartbeat", default=DEFAULT_HEARTBEAT)
    ap.add_argument("--max-age-hours", type=float, default=26.0,
                    help="staleness threshold; daily run at 06:30 + buffer → 26h")
    ap.add_argument("--max-failed", type=int, default=0,
                    help="failed-page count above which to WARN (0 = any failure warns)")
    ap.add_argument("--no-alert", action="store_true", help="print verdict only, never send Telegram")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    hb = read_heartbeat(args.heartbeat)
    verdict = evaluate_health(hb, time.time(), args.max_age_hours, args.max_failed)

    if verdict is None:
        print(f"[imigrasi-health] OK — {_summarize(hb)}")
        return 0

    severity, message = verdict
    print(f"[imigrasi-health] {severity}: {message}")
    if not args.no_alert:
        # Import here so --selftest and --no-alert never even load the gateway
        # module (keeps the pure path pure).
        from diff_alert import send_health_alert

        date = time.strftime("%Y-%m-%d", time.localtime())
        status = send_health_alert(severity, message, date)
        print(f"  ALERT: {status}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
