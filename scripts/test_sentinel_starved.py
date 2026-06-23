#!/usr/bin/env python3
"""Innocence+guilt test for the A2 Heartbeat-Semantico 'starved' classification
in sentinel-aggregate.py.

A2 adds the missing axis to the sentinel: not "did the organ RUN?" (ts fresh,
status ok, launchctl PID) but "did the organ's OUTPUT ADVANCE?". An organ that
runs green on schedule yet whose registry-declared progress field is byte-identical
across N consecutive ticks is STARVED (superscar #2 at the output level).

A component merged with only happy-path checks is the W83/84/85/86 family. So this
proves BOTH directions:
  INNOCENCE — a healthy advancing organ is NOT flagged; an organ that doesn't opt in
              (no progress_field) is NEVER touched; the first run never flags; the
              starved logic NEVER overrides a real stale/dead.
  GUILT     — an organ green-but-frozen across STARVED_TICKS IS flagged 'starved',
              and one advance resets the streak.

    python3 scripts/test_sentinel_starved.py
Exit 0 = all pass.
"""
from __future__ import annotations
import importlib.util
import os
import pathlib
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("sentinel_aggregate", str(HERE / "sentinel-aggregate.py"))
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

NOW = 1_000_000.0  # fixed epoch "now" so freshness is deterministic


def _hb(ts_age: float, status: str = "ok", **extra):
    """Heartbeat dict with ts `ts_age` seconds in the past (fresh by default)."""
    from datetime import datetime, timezone
    ts = datetime.fromtimestamp(NOW - ts_age, tz=timezone.utc).isoformat()
    return {"ts": ts, "status": status, **extra}


def _organ(progress_field: str | None = "cursor", **extra):
    o = {"id": "demo.organ", "runtime": "cron", "type": "cron",
         "expected_hb_seconds": 3600, "severity_on_silence": "warning", **extra}
    if progress_field is not None:
        o["progress_field"] = progress_field
    return o


def _classify(organ, hb, prior):
    return S._classify(organ, hb, None, NOW, prior)


def main() -> int:
    fails = 0

    def check(name: str, cond: bool) -> None:
        nonlocal fails
        if not cond:
            fails += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    # ---- INNOCENCE 1: first observation never flags (fail-open, no prior) ----
    r = _classify(_organ(), _hb(60, cursor=10), prior=None)
    check("innocence: first run (no prior) is ok, never starved", r["status"] == "ok")
    check("innocence: first run records progress_value + streak=0",
          r.get("progress_value") == 10 and r.get("starved_streak") == 0)

    # ---- INNOCENCE 2: output ADVANCING resets/keeps streak at 0 ----
    prior_adv = {"progress_value": 10, "starved_streak": 2}
    r = _classify(_organ(), _hb(60, cursor=11), prior=prior_adv)  # 10 -> 11
    check("innocence: advancing output -> streak resets to 0, stays ok",
          r["status"] == "ok" and r.get("starved_streak") == 0)

    # ---- INNOCENCE 3: organ that does NOT opt in (no progress_field) untouched ----
    r = _classify(_organ(progress_field=None), _hb(60, cursor=99),
                  prior={"progress_value": 99, "starved_streak": 5})
    check("innocence: no progress_field declared -> classic ok, never starved",
          r["status"] == "ok" and "progress_value" not in r)

    # ---- INNOCENCE 4: starved logic NEVER overrides a real stale/dead ----
    # ts is OLD (> DEAD_MULTIPLIER * expected) -> dead; even with frozen output the
    # downgrade is ok->starved only, so a dead organ must STAY dead.
    r = _classify(_organ(), _hb(3600 * 5, cursor=10),  # 5h old, expected 1h -> dead
                  prior={"progress_value": 10, "starved_streak": 10})
    check("innocence: a DEAD organ with frozen output stays dead (no ok->starved on non-ok)",
          r["status"] == "dead")

    # ---- INNOCENCE 5: just-below-threshold frozen run is NOT yet starved ----
    # streak would become STARVED_TICKS-1 -> still ok (the alarm must not fire early).
    prior_near = {"progress_value": 10, "starved_streak": S.STARVED_TICKS - 2}
    r = _classify(_organ(), _hb(60, cursor=10), prior=prior_near)
    check(f"innocence: frozen streak below STARVED_TICKS={S.STARVED_TICKS} stays ok",
          r["status"] == "ok" and r.get("starved_streak") == S.STARVED_TICKS - 1)

    # ---- GUILT 1: green + frozen across STARVED_TICKS -> starved ----
    # prior streak == STARVED_TICKS-1, this tick frozen -> streak hits STARVED_TICKS.
    prior_hot = {"progress_value": 10, "starved_streak": S.STARVED_TICKS - 1}
    r = _classify(_organ(), _hb(60, cursor=10), prior=prior_hot)
    check(f"guilt: green-but-frozen output for STARVED_TICKS={S.STARVED_TICKS} ticks -> starved",
          r["status"] == "starved")
    check("guilt: a starved organ carries non-info severity (visible to the operator)",
          r.get("severity") != "info")

    # ---- GUILT 2: streak accumulates over a real tick-loop, flips at exactly N ----
    # Feed the prior result back in each tick, exactly as main() does via aggregate.json:
    # the FIRST observation can't compare (no prior) so it's ok with streak 0; each
    # subsequent frozen tick +1; 'starved' must first appear at index STARVED_TICKS.
    prior = None
    statuses = []
    for _ in range(S.STARVED_TICKS + 2):
        r = _classify(_organ(), _hb(60, cursor=42), prior=prior)
        statuses.append(r["status"])
        prior = r  # next tick reads THIS result, exactly as main() does via aggregate.json
    first_starved = statuses.index("starved") if "starved" in statuses else -1
    check("guilt: tick-loop flips to starved at exactly index STARVED_TICKS",
          first_starved == S.STARVED_TICKS)

    # ---- GUILT 3: ONE advance mid-starvation clears it back to ok ----
    r = _classify(_organ(), _hb(60, cursor=43), prior=r)  # 42 -> 43 after starvation
    check("guilt-recovery: a single output advance clears starved back to ok",
          r["status"] == "ok" and r.get("starved_streak") == 0)

    # ======================================================================
    # ARTIFACT-MTIME mode — the honest opt-in for organs whose payload has NO
    # monotone field: A2 observes the OUTPUT ARTIFACT on disk (mtime_ns,size),
    # zero writer-change. Same innocence+guilt discipline.
    # ======================================================================
    tmp = pathlib.Path(tempfile.mkdtemp())
    art = tmp / "scraped.json"
    art.write_text("[]")

    def _art_organ():
        # NO progress_field; declares output_artifact instead.
        return {"id": "demo.scraper", "runtime": "cron", "type": "cron",
                "expected_hb_seconds": 3600, "severity_on_silence": "warning",
                "output_artifact": str(art)}

    # INNOCENCE A: missing artifact → opt out (None), never starved even with prior.
    miss = {"id": "x", "runtime": "cron", "type": "cron", "expected_hb_seconds": 3600,
            "severity_on_silence": "warning", "output_artifact": str(tmp / "nope.json")}
    r = _classify(miss, _hb(60), prior={"progress_value": [1, 2], "starved_streak": 9})
    check("artifact innocence: missing artifact opts out (ok, no progress_value, never starved)",
          r["status"] == "ok" and "progress_value" not in r)

    # INNOCENCE B: artifact CHANGED on disk between ticks → advance → streak stays 0.
    r1 = _classify(_art_organ(), _hb(60), prior=None)
    pv1 = r1.get("progress_value")
    check("artifact innocence: first observation records [mtime_ns,size], streak 0",
          isinstance(pv1, list) and len(pv1) == 2 and r1.get("starved_streak") == 0)
    time.sleep(0.01)
    art.write_text('[{"id":1}]')  # real work: artifact rewritten (mtime + size change)
    r2 = _classify(_art_organ(), _hb(60), prior={"progress_value": pv1, "starved_streak": 2})
    check("artifact innocence: artifact rewrite (output advanced) -> streak resets to 0, ok",
          r2["status"] == "ok" and r2.get("starved_streak") == 0 and r2.get("progress_value") != pv1)

    # GUILT: artifact UNCHANGED on disk across STARVED_TICKS ticks -> starved.
    pv = r2.get("progress_value")  # current on-disk signal; we now freeze the file
    prior = {"progress_value": pv, "starved_streak": S.STARVED_TICKS - 1}
    r = _classify(_art_organ(), _hb(60), prior=prior)  # file untouched since pv captured
    check(f"artifact guilt: frozen artifact for STARVED_TICKS={S.STARVED_TICKS} ticks -> starved",
          r["status"] == "starved")

    total = 14
    print(f"\n=== {'ALL ' + str(total) + ' PASS' if not fails else str(fails) + ' FAIL'} ===")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
