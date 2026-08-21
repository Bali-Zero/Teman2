#!/usr/bin/env python3
"""qwen_quota_watch.py — fleet-wide Qwen Token-Plan 7-day window estimator + alert.

WHY THIS EXISTS (Zero, 2026-08-21: "dovete farlo voi in automatico"): Alibaba
Model Studio exposes NO credits/usage API — probed and closed on 2026-08-14
(`research/operations/2026-08-14-probe1-tp1-burn-rate.md` Part 2: /usage,
/credits, /quota, /billing all silent). The console dashboard is the only
exact source and it is GUI-only. What CAN be automated is the qwen CLI's own
per-call log (`~/.qwen/usage/token-usage-YYYY-MM.jsonl`), which the same doc
cross-validated against the console counter to within ~2.5% (Part 4).

WHAT IT DOES: sums `totalTokens` over the trailing 7 days across the fleet
(local log + `ssh <host> cat` for the others), converts to a window
percentage via a console-calibrated capacity constant, and alerts through
`tg_notify.py` at WARN/CRIT thresholds. Coverage is DECLARED per host — an
unreachable host makes the estimate a declared UNDERCOUNT, never silently
"complete" (W97: no silent caps).

CALIBRATION IS A FROZEN MEASURE (W106): the capacity constant was derived
once (2026-08-14 console read: 56.31% used with a 211,699,042-token local
week → capacity ≈ 375.9M tokens/7d) and assumes the plan weighs all models
equally — an ASSUMPTION, stated in every report line. When the calibration
is older than CALIBRATION_STALE_DAYS the report says so and asks for a fresh
console read; it never pretends the constant is current truth.

Usage:
  python3 scripts/qwen_quota_watch.py                  # report to stdout
  python3 scripts/qwen_quota_watch.py --alert          # + tg_notify at thresholds
  python3 scripts/qwen_quota_watch.py --hosts pro,air  # explicit remote list
  python3 scripts/qwen_quota_watch.py --selftest       # offline unit checks

Exit codes: 0 ok/below-warn · 1 WARN threshold crossed · 2 CRIT crossed ·
4 CANNOT-MEASURE (no log readable anywhere — never reported as "0% used").
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from scripts.tg_gateway_verdict import extract_gateway_verdict, gateway_delivered  # noqa: E402

# --- calibration (console read 2026-08-14, Part 4 of the burn-rate doc) ----
CALIBRATION = {
    "date": "2026-08-14",
    "console_pct": 56.31,
    "local_week_tokens": 211_699_042,
}
CAPACITY_TOKENS_7D = int(CALIBRATION["local_week_tokens"] / (CALIBRATION["console_pct"] / 100.0))
CALIBRATION_STALE_DAYS = 21

WARN_PCT = 70.0
CRIT_PCT = 85.0
WINDOW_DAYS = 7

# Remote hosts and where their qwen CLI writes usage. Keys are ssh aliases as
# seen FROM THE MACHINE THIS RUNS ON (designed for Pro: `air` = M5, `mini`).
DEFAULT_REMOTE_LOG = ".qwen/usage/token-usage-{month}.jsonl"
SSH_TIMEOUT_S = 15


@dataclass
class HostReading:
    host: str
    tokens: int = 0
    calls: int = 0
    per_model: dict[str, int] = field(default_factory=dict)
    ok: bool = False
    note: str = ""


def _months_covering_window(now: dt.datetime) -> list[str]:
    """The trailing window can straddle a month boundary — read both files."""
    months = {now.strftime("%Y-%m")}
    months.add((now - dt.timedelta(days=WINDOW_DAYS)).strftime("%Y-%m"))
    return sorted(months)


def _sum_rows(lines: list[str], cutoff: dt.datetime) -> tuple[int, int, dict[str, int]]:
    tokens = 0
    calls = 0
    per_model: dict[str, int] = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            ts = dt.datetime.fromisoformat(str(row["timestamp"]).replace("Z", "+00:00"))
            n = int(row["totalTokens"])
            model = str(row.get("model", "?"))
        except (ValueError, KeyError, TypeError):
            continue  # malformed row: skipped, not fatal (log is CLI-owned)
        if ts >= cutoff:
            tokens += n
            calls += 1
            per_model[model] = per_model.get(model, 0) + n
    return tokens, calls, per_model


def read_local(now: dt.datetime) -> HostReading:
    r = HostReading(host="local")
    cutoff = now - dt.timedelta(days=WINDOW_DAYS)
    found = False
    for month in _months_covering_window(now):
        p = Path.home() / DEFAULT_REMOTE_LOG.format(month=month)
        if not p.is_file():
            continue
        found = True
        t, c, pm = _sum_rows(p.read_text(encoding="utf-8", errors="replace").splitlines(), cutoff)
        r.tokens += t
        r.calls += c
        for m, v in pm.items():
            r.per_model[m] = r.per_model.get(m, 0) + v
    r.ok = found
    r.note = "ok" if found else "no usage log on this host"
    return r


def read_remote(host: str, now: dt.datetime) -> HostReading:
    r = HostReading(host=host)
    cutoff = now - dt.timedelta(days=WINDOW_DAYS)
    found = False
    for month in _months_covering_window(now):
        rel = DEFAULT_REMOTE_LOG.format(month=month)
        try:
            proc = subprocess.run(
                ["ssh", "-o", f"ConnectTimeout={SSH_TIMEOUT_S}", "-o", "BatchMode=yes",
                 host, f"cat ~/{rel} 2>/dev/null"],
                capture_output=True, text=True, timeout=SSH_TIMEOUT_S + 30,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            r.note = f"ssh failed: {type(exc).__name__}"
            return r
        if proc.returncode != 0:
            # ssh itself failed (unreachable/auth) vs file-missing both land
            # here; distinguish by stderr so coverage reporting is honest.
            if proc.stderr.strip():
                r.note = f"ssh rc={proc.returncode}: {proc.stderr.strip()[:120]}"
                return r
            continue  # file missing for that month — not an error by itself
        if proc.stdout:
            found = True
            t, c, pm = _sum_rows(proc.stdout.splitlines(), cutoff)
            r.tokens += t
            r.calls += c
            for m, v in pm.items():
                r.per_model[m] = r.per_model.get(m, 0) + v
    r.ok = found
    if not r.note:
        r.note = "ok" if found else "reachable, no usage log"
        r.ok = True  # reachable counts as covered even with an empty log
    return r


def calibration_age_days(now: dt.datetime) -> int:
    cal = dt.datetime.strptime(CALIBRATION["date"], "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
    return (now - cal).days


def build_report(readings: list[HostReading], now: dt.datetime) -> tuple[str, float, int]:
    total = sum(r.tokens for r in readings)
    pct = total / CAPACITY_TOKENS_7D * 100.0
    covered = [r.host for r in readings if r.ok]
    missed = [f"{r.host}({r.note})" for r in readings if not r.ok]
    per_model: dict[str, int] = {}
    for r in readings:
        for m, v in r.per_model.items():
            per_model[m] = per_model.get(m, 0) + v
    top = " · ".join(f"{m} {v/1e6:.1f}M" for m, v in sorted(per_model.items(), key=lambda kv: -kv[1])[:4])
    age = calibration_age_days(now)
    stale = age > CALIBRATION_STALE_DAYS
    lines = [
        f"Qwen TP window 7d: ~{pct:.1f}% (est., {total:,} tok / capacity {CAPACITY_TOKENS_7D:,})",
        f"hosts covered: {','.join(covered) or 'NONE'}"
        + (f" — MISSED: {','.join(missed)} (estimate is an UNDERCOUNT)" if missed else ""),
        f"top models: {top or 'none in window'}",
        f"calibration: console {CALIBRATION['date']} ({age}d old"
        + (f" — STALE >{CALIBRATION_STALE_DAYS}d, redo the console read and update CALIBRATION" if stale else "")
        + "; assumes equal per-model weighting)",
    ]
    if pct >= CRIT_PCT:
        exit_code = 2
    elif pct >= WARN_PCT:
        exit_code = 1
    else:
        exit_code = 0
    return "\n".join(lines), pct, exit_code


def send_alert(report: str, pct: float, repo_root: Path) -> bool:
    """Send via tg_notify.py and judge the gateway's VERDICT, not its survival.

    Contract enforced by scripts/tests/test_gateway_callers_read_the_verdict.py:
    tg_notify exits 0 even on refusal, printing `tg_notify: <verdict>` to
    stderr — a caller trusting returncode reads a refusal as a delivery
    (W104). The returned bool comes from the parsed verdict.
    """
    tier = "P0" if pct >= CRIT_PCT else "P1"
    tg = repo_root / "scripts" / "tg_notify.py"
    proc = subprocess.run(
        [sys.executable, str(tg), "--tier", tier, "--source", "qwen-quota-watch",
         "--dedup-key", f"qwen-quota-{dt.date.today().isoformat()}", report],
        capture_output=True, text=True,
    )
    verdict = extract_gateway_verdict(proc.stderr)
    delivered = False if verdict is None else gateway_delivered(verdict)
    sys.stderr.write(
        f"tg_notify rc={proc.returncode} verdict={verdict or 'MISSING'} delivered={delivered}\n"
    )
    if not delivered:
        sys.stderr.write("ALERT NOT DELIVERED — the quota warning above reached nobody\n")
    return delivered


def selftest() -> int:
    now = dt.datetime(2026, 8, 21, 12, 0, tzinfo=dt.timezone.utc)
    cutoff = now - dt.timedelta(days=WINDOW_DAYS)
    rows = [
        json.dumps({"timestamp": "2026-08-20T10:00:00.000Z", "totalTokens": 100, "model": "a"}),
        json.dumps({"timestamp": "2026-08-01T10:00:00.000Z", "totalTokens": 999, "model": "a"}),  # outside window
        "not-json",
        json.dumps({"timestamp": "2026-08-19T10:00:00.000Z", "model": "b"}),  # missing totalTokens
        json.dumps({"timestamp": "2026-08-19T10:00:00.000Z", "totalTokens": 50, "model": "b"}),
    ]
    t, c, pm = _sum_rows(rows, cutoff)
    assert (t, c) == (150, 2), f"window sum wrong: {(t, c)}"
    assert pm == {"a": 100, "b": 50}, pm
    # month straddle: window crossing a month boundary reads both files
    assert _months_covering_window(dt.datetime(2026, 9, 3, tzinfo=dt.timezone.utc)) == ["2026-08", "2026-09"]
    assert _months_covering_window(now) == ["2026-08"]
    # capacity derivation sanity (calibration constants, not re-derived elsewhere)
    assert 370_000_000 < CAPACITY_TOKENS_7D < 382_000_000, CAPACITY_TOKENS_7D
    # thresholds: guilt AND innocence
    r_ok = [HostReading(host="x", tokens=int(CAPACITY_TOKENS_7D * 0.10), ok=True, note="ok")]
    _, pct, code = build_report(r_ok, now)
    assert code == 0 and pct < WARN_PCT
    r_warn = [HostReading(host="x", tokens=int(CAPACITY_TOKENS_7D * 0.75), ok=True, note="ok")]
    _, _, code = build_report(r_warn, now)
    assert code == 1
    r_crit = [HostReading(host="x", tokens=int(CAPACITY_TOKENS_7D * 0.90), ok=True, note="ok")]
    rep, _, code = build_report(r_crit, now)
    assert code == 2
    # missed host is DECLARED in the text
    r_miss = [HostReading(host="x", tokens=10, ok=True, note="ok"),
              HostReading(host="pro", ok=False, note="ssh failed: TimeoutExpired")]
    rep, _, _ = build_report(r_miss, now)
    assert "MISSED: pro" in rep and "UNDERCOUNT" in rep
    # stale calibration is DECLARED
    later = dt.datetime(2026, 9, 20, tzinfo=dt.timezone.utc)
    rep, _, _ = build_report(r_ok, later)
    assert "STALE" in rep
    print("selftest OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--hosts", default="pro,mini,air",
                    help="comma-separated ssh aliases to pull in addition to the local log; "
                         "'' for local-only. Aliases are resolved from THIS machine's ssh config.")
    ap.add_argument("--alert", action="store_true", help="send tg_notify at WARN/CRIT")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    now = dt.datetime.now(dt.timezone.utc)
    local_host = os.uname().nodename.split(".")[0].lower()
    readings = [read_local(now)]
    for h in [h.strip() for h in args.hosts.split(",") if h.strip()]:
        # skip the alias that is THIS machine (Air-M5 runs with --hosts pro,mini)
        if h == "air" and "air" in local_host:
            continue
        if h == "pro" and local_host == "nuzantara":
            continue
        if h == "mini" and "mini" in local_host:
            continue
        readings.append(read_remote(h, now))

    if not any(r.ok for r in readings):
        print("CANNOT-MEASURE: no usage log readable on any host — NOT 0% used", file=sys.stderr)
        return 4

    report, pct, exit_code = build_report(readings, now)
    print(report)
    if args.alert and exit_code in (1, 2):
        if not send_alert(report, pct, Path(__file__).resolve().parent.parent):
            # threshold crossed AND nobody was told: CANNOT-DELIVER dominates
            return 4
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
