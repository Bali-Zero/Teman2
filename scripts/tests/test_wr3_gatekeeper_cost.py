"""P03 "cost truth" — scripts/wr3_gatekeeper_check.py's cost gate is not a gate.

Five measured defects (verified on disk, 2026-08-23) before this fix:
  1. The gate read `~/.cache/wr3/flow-quota.json` unconditionally at module
     scope; nothing in the repo writes that file, and a missing file crashed
     with an uncaught traceback — NO gate-verdict.json was ever written.
  2. `CR_PER_CLIP = 10` disagreed with the real charge site's
     `DEFAULT_CLIP_COST_CR = 20` (wr3_flowkit_client.py) — projected spend
     was under-counted by 2x.
  3. The daily-ceiling check computed its condition and then `pass`ed.
  4. `hard_ceiling` was emitted into the verdict JSON and never compared
     against anything.
  5. The gate could not run under zero-spend mode without projecting a real
     (and possibly FAILING) cost for a pipeline that provably spends 0.

These tests drive the real entry point as a SUBPROCESS (the script is
top-level code keyed off `sys.argv[1]`, not importable) — the exact command
the orchestrator runs. HOME, WR3_CREDIT_LEDGER, and WR3_SPEND_DECISION_LOG
are all redirected into tmp_path so this suite can never read or write the
real `~/.cache/wr3/flow-quota.json` / `~/.cache/wr3/credit-ledger.jsonl`.
No FlowKit/Veo network call is reachable from anything this script imports
(wr3_credit_ledger and wr3_spend_authority are both stdlib-only).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_SCRIPTS = Path(__file__).resolve().parents[1]
GATEKEEPER = REPO_SCRIPTS / "wr3_gatekeeper_check.py"

sys.path.insert(0, str(REPO_SCRIPTS))

from wr3_credit_ledger import record_spend  # noqa: E402

CLIP_COST_CR = 20  # the real per-clip cost (SSOT) — asserted against, not imported,
                    # so a regression in the import wiring can't hide from these tests


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------


def _shot(i: int) -> dict:
    return {
        "shot_id": f"s{i:03d}",
        "prompt_positive": f"a calm office interior, shot number {i}",
        "shot_type": "b-roll",
    }


def _episode(tmp_path: Path, *, n_shots: int, name: str = "EP-COST") -> Path:
    ep = tmp_path / name
    ep.mkdir(parents=True, exist_ok=True)
    duration = 8.0 * n_shots
    (ep / "shot-pack.json").write_text(json.dumps({
        "shots": [_shot(i) for i in range(1, n_shots + 1)],
        "total_duration_s": duration,
    }))
    (ep / "brief.json").write_text(json.dumps({"target_duration_s": duration}))
    return ep


def _write_quota(
    path: Path,
    *,
    balance_remaining_cr: int = 2400,
    daily_ceiling_cr: int = 190,
    as_of: str | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if as_of is None:
        as_of = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps({
        "plan": "flow_pro",
        "daily_ceiling_cr": daily_ceiling_cr,
        "daily_spent_cr": 0,  # deliberately never trusted by the gate anymore
        "balance_remaining_cr": balance_remaining_cr,
        "as_of": as_of,
    }))


def _run_gate(
    ep: Path,
    tmp_path: Path,
    *,
    ledger_path: Path | None = None,
    quota_path: Path | None = None,
    zero_spend: bool = False,
) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env["HOME"] = str(home)
    env["WR3_CREDIT_LEDGER"] = str(ledger_path if ledger_path is not None else tmp_path / "ledger.jsonl")
    env["WR3_SPEND_DECISION_LOG"] = str(tmp_path / "decisions.jsonl")
    env.pop("WR3_SPEND_DECISION", None)
    env.pop("WR3_FLOWKIT_CLIP_COST", None)
    env.pop("WR3_FLOW_QUOTA_MAX_AGE_H", None)
    if quota_path is not None:
        env["WR3_FLOW_QUOTA"] = str(quota_path)
    else:
        env.pop("WR3_FLOW_QUOTA", None)
    if zero_spend:
        env["WR3_ZERO_SPEND"] = "1"
    else:
        env.pop("WR3_ZERO_SPEND", None)
    return subprocess.run(
        [sys.executable, str(GATEKEEPER), str(ep)],
        capture_output=True, text=True, env=env, timeout=60,
    )


def _verdict(ep: Path) -> dict:
    return json.loads((ep / "gate-verdict.json").read_text())


# ---------------------------------------------------------------------------
# 1. missing quota file -> FAIL verdict with a named reason, file still written
# ---------------------------------------------------------------------------


def test_missing_quota_file_fails_closed_and_still_writes_verdict(tmp_path):
    ep = _episode(tmp_path, n_shots=3)
    # No quota_path given, and HOME is redirected to an empty tmp dir, so the
    # default ~/.cache/wr3/flow-quota.json cannot exist.
    res = _run_gate(ep, tmp_path)
    assert res.returncode == 0, f"gate must exit 0 and emit a FAIL verdict, not crash: {res.stderr}"
    assert "Traceback" not in res.stderr, res.stderr
    assert (ep / "gate-verdict.json").exists(), "today: crash, no verdict file at all"
    v = _verdict(ep)
    assert v["verdict"] == "FAIL"
    assert v["checks"]["cost"]["passed"] is False
    reasons = " ".join(v["checks"]["cost"]["reasons"])
    assert "unreadable" in reasons or "missing" in reasons.lower()


# ---------------------------------------------------------------------------
# 2. stale quota file -> FAIL with staleness reason
# ---------------------------------------------------------------------------


def test_stale_quota_file_fails_with_staleness_reason(tmp_path):
    ep = _episode(tmp_path, n_shots=3)
    quota_path = tmp_path / "flow-quota.json"
    stale_as_of = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    _write_quota(quota_path, as_of=stale_as_of)
    res = _run_gate(ep, tmp_path, quota_path=quota_path)
    assert res.returncode == 0, res.stderr
    v = _verdict(ep)
    assert v["verdict"] == "FAIL"
    reasons = " ".join(v["checks"]["cost"]["reasons"])
    assert "STALE" in reasons or "stale" in reasons


# ---------------------------------------------------------------------------
# 3. fresh valid quota + affordable pack -> cost passes
# ---------------------------------------------------------------------------


def test_fresh_quota_and_affordable_pack_passes_cost_check(tmp_path):
    ep = _episode(tmp_path, n_shots=5)
    quota_path = tmp_path / "flow-quota.json"
    _write_quota(quota_path)
    res = _run_gate(ep, tmp_path, quota_path=quota_path)
    assert res.returncode == 0, res.stderr
    v = _verdict(ep)
    assert v["checks"]["cost"]["passed"] is True, v["checks"]["cost"]
    assert v["checks"]["cost"]["mode"] == "real"


# ---------------------------------------------------------------------------
# 4. the 2x fix — N shots project N*20, not N*10
# ---------------------------------------------------------------------------


def test_projection_uses_the_real_20cr_per_clip_not_10(tmp_path):
    ep = _episode(tmp_path, n_shots=7)
    quota_path = tmp_path / "flow-quota.json"
    _write_quota(quota_path)
    res = _run_gate(ep, tmp_path, quota_path=quota_path)
    assert res.returncode == 0, res.stderr
    v = _verdict(ep)
    assert v["checks"]["cost"]["projected_cr"] == 7 * CLIP_COST_CR == 140
    assert v["checks"]["cost"]["projected_cr"] != 7 * 10


# ---------------------------------------------------------------------------
# 5. daily ceiling armed — proves the check is ENFORCED, not merely present
# ---------------------------------------------------------------------------


def test_daily_ceiling_fails_when_todays_ledger_spend_leaves_no_headroom(tmp_path):
    ep = _episode(tmp_path, n_shots=3)  # projects 60cr
    quota_path = tmp_path / "flow-quota.json"
    _write_quota(quota_path, daily_ceiling_cr=190, balance_remaining_cr=2400)
    ledger_path = tmp_path / "ledger.jsonl"
    # Seed 150cr of REAL spend dated "now" (today) — 150 + 60 > 190.
    record_spend(
        episode_id="other-episode",
        shot_index=0,
        credits=150,
        mode="real",
        veo_job_id="wf-seed",
        source="test-seed",
        clip_cost_cr=20,
        ledger_path=ledger_path,
    )
    res = _run_gate(ep, tmp_path, ledger_path=ledger_path, quota_path=quota_path)
    assert res.returncode == 0, res.stderr
    v = _verdict(ep)
    assert v["checks"]["cost"]["passed"] is False
    assert v["checks"]["cost"]["spent_today_cr"] == 150
    reasons = " ".join(v["checks"]["cost"]["reasons"])
    assert "daily ceiling" in reasons or "daily_ceiling" in reasons


def test_daily_ceiling_passes_when_seed_rows_absent(tmp_path):
    """Falsification pair for the test above — same episode/quota, no ledger
    seed. If this also failed, the FAIL above would prove nothing about the
    check being armed (it would just always fail).
    """
    ep = _episode(tmp_path, n_shots=3)
    quota_path = tmp_path / "flow-quota.json"
    _write_quota(quota_path, daily_ceiling_cr=190, balance_remaining_cr=2400)
    ledger_path = tmp_path / "ledger-empty.jsonl"
    res = _run_gate(ep, tmp_path, ledger_path=ledger_path, quota_path=quota_path)
    assert res.returncode == 0, res.stderr
    v = _verdict(ep)
    assert v["checks"]["cost"]["passed"] is True, v["checks"]["cost"]
    assert v["checks"]["cost"]["spent_today_cr"] == 0


def test_early_local_morning_spend_still_counts_against_todays_ceiling(tmp_path):
    """The daily window must be the OPERATOR's day, not the UTC day.

    Ledger timestamps are UTC, correctly. But a DAILY CEILING is a business
    quantity and this business runs on WITA (UTC+8), so bucketing by UTC date
    slides the reset to 08:00 local — in the dangerous direction. A charge made
    at 03:00 WITA carries YESTERDAY's UTC date, so under UTC bucketing it stops
    counting from 08:00 that same local morning and the ceiling silently
    regains headroom it never had. Under-counting in a spend gate is the
    failure mode that burns credits.

    The seeded row below is deliberately "early this local morning": for any
    positive UTC offset that instant falls on the previous UTC date, so the two
    conventions give different answers and this test can tell them apart. Under
    UTC bucketing `spent_today_cr` is 0 and the gate PASSES; under the local-day
    window it is 150 and the gate FAILS. Seeding at "now" — as the tests above
    do — cannot distinguish them, because both agree about now.
    """
    local_tz = datetime.now(timezone.utc).astimezone().tzinfo
    now_local = datetime.now(local_tz)
    early_local = now_local.replace(hour=3, minute=0, second=0, microsecond=0)
    if early_local.astimezone(timezone.utc).date() == now_local.date():
        pytest.skip(
            "this machine's UTC offset does not put 03:00 local on a different "
            "UTC date, so the two conventions cannot be told apart here"
        )

    ep = _episode(tmp_path, n_shots=3)  # projects 60cr
    quota_path = tmp_path / "flow-quota.json"
    _write_quota(quota_path, daily_ceiling_cr=190, balance_remaining_cr=2400)
    ledger_path = tmp_path / "ledger.jsonl"
    record_spend(
        episode_id="early-morning-episode",
        shot_index=0,
        credits=150,
        mode="real",
        veo_job_id="wf-early",
        source="test-seed",
        clip_cost_cr=20,
        ledger_path=ledger_path,
        ts=early_local.isoformat(),
    )

    res = _run_gate(ep, tmp_path, ledger_path=ledger_path, quota_path=quota_path)
    assert res.returncode == 0, res.stderr
    cost = _verdict(ep)["checks"]["cost"]
    assert cost["spent_today_cr"] == 150, (
        "an early-local-morning charge was dropped from today's total — the "
        "window is bucketing by UTC date, not by the operator's day"
    )
    assert cost["passed"] is False
    assert "daily ceiling" in " ".join(cost["reasons"])


# ---------------------------------------------------------------------------
# 6. WR3_ZERO_SPEND -> projected 0, cost passes, no quota file needed at all
# ---------------------------------------------------------------------------


def test_zero_spend_short_circuits_with_no_quota_file_present(tmp_path):
    ep = _episode(tmp_path, n_shots=25)  # would be unaffordable/over-count under real mode
    res = _run_gate(ep, tmp_path, zero_spend=True)  # no quota_path -> none exists
    assert res.returncode == 0, res.stderr
    v = _verdict(ep)
    assert v["checks"]["cost"]["projected_cr"] == 0
    assert v["checks"]["cost"]["passed"] is True
    assert v["checks"]["cost"]["mode"] == "placeholder"


# ---------------------------------------------------------------------------
# 7. hard ceiling enforced
# ---------------------------------------------------------------------------


def test_hard_ceiling_fails_when_projection_exceeds_it(tmp_path):
    ep = _episode(tmp_path, n_shots=11)  # 220cr > hard_ceiling 209cr
    quota_path = tmp_path / "flow-quota.json"
    # Large daily ceiling / balance so the hard-ceiling reason is guaranteed
    # present (expected_cr*1.10 == hard_ceiling numerically for this gate's
    # single hardcoded envelope, so both legitimately fire together).
    _write_quota(quota_path, daily_ceiling_cr=1000, balance_remaining_cr=100000)
    res = _run_gate(ep, tmp_path, quota_path=quota_path)
    assert res.returncode == 0, res.stderr
    v = _verdict(ep)
    assert v["checks"]["cost"]["passed"] is False
    assert v["checks"]["cost"]["projected_cr"] == 220
    reasons = " ".join(v["checks"]["cost"]["reasons"])
    assert "hard_ceiling" in reasons


# ---------------------------------------------------------------------------
# 8. malformed ledger line -> FAIL, never silently read as 0 spent today
# ---------------------------------------------------------------------------


def test_malformed_ledger_line_fails_rather_than_reading_as_zero_spent(tmp_path):
    ep = _episode(tmp_path, n_shots=3)
    quota_path = tmp_path / "flow-quota.json"
    _write_quota(quota_path)
    ledger_path = tmp_path / "ledger.jsonl"
    record_spend(
        episode_id="ep-a",
        shot_index=0,
        credits=20,
        mode="real",
        veo_job_id="wf-1",
        source="test-seed",
        clip_cost_cr=20,
        ledger_path=ledger_path,
    )
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write("{this is not valid json,,,\n")

    res = _run_gate(ep, tmp_path, ledger_path=ledger_path, quota_path=quota_path)
    assert res.returncode == 0, res.stderr
    v = _verdict(ep)
    assert v["checks"]["cost"]["passed"] is False
    assert v["checks"]["cost"]["spent_today_cr"] is None
    reasons = " ".join(v["checks"]["cost"]["reasons"])
    assert "malformed" in reasons.lower()
