#!/usr/bin/env python3
"""observe_visa_freshness_sentinel.py — bites: observation for the sentinel re-alert (W141).

# bites-observable — this script takes NO arguments: the pack read and the sender are
# stubbed in-process, the state lives in a private temp directory, and nothing an invoker
# types can name a program to run, a file to write, or a database to reach — the bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets.

Drives the real decision and state code of ``scripts/visa_freshness_sentinel.py`` over a
simulated STALE snapshot (pack 25, 18 stale portal ids) with an injected clock:

1. first STALE run            -> would_send true
2. one hour later             -> would_send false (inside the 23 h gate)
3. twenty-four hours later    -> would_send true (the re-alert)
4. sender returns undelivered -> the delivered streak does not move
5. corrupt state file         -> a send, never a crash and never `not-due-yet`
6. ticks every 6.1 h, 3 days  -> every delivery gap is at most 24 h
7. gateway answers `spooled`  -> a board delivery only; Telegram is retried
8. spooled, then sent 10 min  -> the second attempt is made and delivered
9. stale `next_due_ts`        -> never trusted: last delivery 24 h ago sends now

Exit 0 only if all four assertions hold.
"""

from __future__ import annotations

import dataclasses
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import visa_freshness_sentinel as vfs  # noqa: E402

VERIFIED_AT = datetime(2026, 8, 30, 13, 18, tzinfo=timezone.utc)
T0 = VERIFIED_AT + timedelta(days=33)  # one day past the 32-day boundary


def _stale_verdict() -> vfs.Verdict:
    records = [
        {
            "source_record_id": f"portal-{i:02d}",
            "title": f"Portal source {i}",
            "authority_type": "OFFICIAL_PORTAL",
            "verified_at": VERIFIED_AT.isoformat(),
            "freshness_policy": {
                "kind": "MAX_AGE_SINCE_VERIFIED_AT",
                "max_age_seconds": 32 * 86400,
            },
        }
        for i in range(18)
    ]
    verdict = vfs.classify_freshness(records, T0)
    return dataclasses.replace(verdict, pack_sequence=25, pack_version="2026.10.7")


def main() -> int:
    verdict = _stale_verdict()
    assert verdict.outcome == vfs.OUTCOME_STALE and len(verdict.stale) == 18

    answers = iter(["sent", "sent", "p0_unsent_spooled"])
    vfs._send = lambda v, gw, key=None: (next(answers), "")
    vfs._escalation_open = lambda v, now_ts, count, force: False
    vfs._escalation_resolve = lambda: None

    with tempfile.TemporaryDirectory() as tmp:
        state = Path(tmp) / "state.json"
        clock = [T0, T0 + timedelta(hours=1), T0 + timedelta(hours=24), T0 + timedelta(hours=48)]
        decisions = []
        for at in clock:
            verdict_at = dataclasses.replace(verdict, now=at)
            decisions.append(
                vfs.run_alert_cycle(
                    verdict_at, dry_run=False, now_ts=at.timestamp(), state_path=state
                )
            )
        streak = json.loads(state.read_text())["delivered_streak"]

    for decision in decisions:
        print(json.dumps({"alert_decision": decision}, sort_keys=True))

    checks = (
        decisions[0]["would_send"] is True,
        decisions[1]["would_send"] is False,
        decisions[2]["would_send"] is True,
        decisions[3].get("delivered") is False and streak == 2,
    )
    vfs._send = lambda v, gw, key=None: ("sent", "")
    with tempfile.TemporaryDirectory() as tmp:
        state = Path(tmp) / "state.json"
        state.write_text('{"condition": "STALE:25", "delivered_streak": null, "next_due_ts": NaN}')
        corrupt = vfs.run_alert_cycle(
            verdict, dry_run=False, now_ts=T0.timestamp(), state_path=state
        )
        print(json.dumps({"alert_decision": corrupt}, sort_keys=True))

        cadence = Path(tmp) / "cadence.json"
        delivered = []
        for tick in range(int(72 / 6.1) + 1):
            at = T0.timestamp() + tick * 6.1 * 3600
            out = vfs.run_alert_cycle(verdict, dry_run=False, now_ts=at, state_path=cadence)
            if out.get("delivered"):
                delivered.append(at)
        gaps = [(b - a) / 3600 for a, b in zip(delivered, delivered[1:])]
        print(json.dumps({"delivery_gaps_hours": [round(g, 1) for g in gaps]}))

        seq = iter(["spooled", "sent"])
        vfs._send = lambda v, gw, key=None: (next(seq), "")
        board_path = Path(tmp) / "board.json"
        spooled = vfs.run_alert_cycle(
            verdict, dry_run=False, now_ts=T0.timestamp(), state_path=board_path
        )
        retried = vfs.run_alert_cycle(
            verdict, dry_run=False, now_ts=T0.timestamp() + 600, state_path=board_path
        )
        print(json.dumps({"alert_decision": spooled}, sort_keys=True))
        print(json.dumps({"alert_decision": retried}, sort_keys=True))

        vfs._send = lambda v, gw, key=None: ("sent", "")
        clamped_path = Path(tmp) / "clamped.json"
        clamped_path.write_text(json.dumps({
            "condition": "STALE:25",
            "telegram_last_delivered_ts": T0.timestamp() - 86400,
            "next_due_ts": T0.timestamp() + 86400,
        }))
        clamped = vfs.run_alert_cycle(
            verdict, dry_run=False, now_ts=T0.timestamp(), state_path=clamped_path
        )

    checks += (
        corrupt["would_send"] is True and corrupt.get("delivered") is True,
        len(gaps) >= 3 and max(gaps) <= 24,
        spooled.get("board_delivery") is True and spooled.get("delivered") is False,
        retried.get("delivered") is True,
        clamped.get("delivered") is True,
    )
    if not all(checks):
        print(f"observe_visa_freshness_sentinel: FAILED checks={checks} streak={streak}")
        return 1
    print(
        "observe_visa_freshness_sentinel: a persistent STALE re-alerts daily "
        "and an undelivered send never counts"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
