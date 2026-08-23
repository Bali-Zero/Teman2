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


# Enough for CPython to start and for the gate to read/write files. Anything
# absent here is absent from the child by construction, so a new WR3_* toggle
# cannot leak into these tests by default; a test that wants one sets it below.
_ENV_WHITELIST = ("PATH", "TMPDIR", "LANG", "LC_ALL")


def _run_gate(
    ep: Path,
    tmp_path: Path,
    *,
    ledger_path: Path | None = None,
    quota_path: Path | None = None,
    zero_spend: bool = False,
    business_tz: str | None = None,
    ambient_tz: str | None = None,
) -> subprocess.CompletedProcess:
    # WHITELIST, not blacklist. `dict(os.environ)` inherits every WR3_* toggle
    # the operator happens to have exported — and this gate reads several. A
    # stray `WR3_ZERO_SPEND=1` in the parent shell would send EVERY test in this
    # file down the zero-spend short circuit, where the cost block is skipped
    # entirely: ten green tests proving nothing. Blacklisting the toggles known
    # today (as this helper used to) does not survive the next toggle being
    # added, and that is exactly the shape that fails silently.
    env = {k: os.environ[k] for k in _ENV_WHITELIST if k in os.environ}
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env["HOME"] = str(home)
    env["WR3_CREDIT_LEDGER"] = str(ledger_path if ledger_path is not None else tmp_path / "ledger.jsonl")
    env["WR3_SPEND_DECISION_LOG"] = str(tmp_path / "decisions.jsonl")
    # No `env.pop(...)` guards: on a whitelisted dict they are no-ops, and a
    # no-op that reads as a protection is worse than no protection at all.
    if quota_path is not None:
        env["WR3_FLOW_QUOTA"] = str(quota_path)
    if zero_spend:
        env["WR3_ZERO_SPEND"] = "1"
    if business_tz is not None:
        env["WR3_BUSINESS_TZ"] = business_tz
    if ambient_tz is not None:
        # `TZ` is deliberately absent from the whitelist, so the child inherits
        # nothing and a test that cares must say so. Setting it is not
        # incidental: the defect under test is a window that FOLLOWS the
        # ambient zone, and on a machine whose local zone already IS the
        # business zone the broken and the fixed code agree exactly. The test
        # has to run somewhere else to see the difference, so it picks where.
        env["TZ"] = ambient_tz
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


# WITA is a fixed UTC+8 with no DST — Indonesia has never observed it — so this
# offset is instant-for-instant identical to ZoneInfo("Asia/Makassar"). Using
# the offset for the SEEDS keeps the test independent of the machine's tz
# database; the gate's own resolution is asserted separately, via the stamp.
_WITA = timezone(timedelta(hours=8))


def test_business_day_window_is_wita_not_the_utc_date(tmp_path):
    """The daily ceiling window must be the OPERATOR's day, not the UTC day.

    Ledger timestamps are UTC, correctly. But a DAILY CEILING is a business
    quantity and this business runs on WITA (UTC+8), so bucketing by UTC date
    slides the reset to 08:00 local, in the dangerous direction.

    TWO seeded rows, and both are load-bearing. Measured, hour by hour: ONE row
    inside today's business day cannot tell the conventions apart between 00:00
    and 08:00 WITA, because in that window every elapsed business-day instant is
    also inside the current UTC day — the two windows agree, and the earlier
    version of this test skipped itself for those eight hours. So it carries a
    second row that belongs to YESTERDAY's business day but to TODAY's UTC day.
    Whichever way the clock falls, exactly one of the two rows is misclassified
    by UTC bucketing:

      * from 08:00 WITA on: X drops out    -> 0   instead of 150
      * before 08:00 WITA:  Y is pulled in -> 220 instead of 150

    Both diverge from 150, so the assertion below is a real gate at every hour
    of the day and needs no skip. Seeding at "now" — as the tests above do —
    cannot distinguish them, because both conventions agree about now.

    `WR3_BUSINESS_TZ` is pinned rather than inherited, and `TZ=UTC` is pinned
    too. Both matter. The defect is a window that follows the ambient zone, so
    on a machine whose local zone already IS WITA the broken code and the fixed
    code produce identical answers and this test would pass over the bug. Under
    `TZ=UTC` — which is also what cron, launchd and containers usually give it —
    the two diverge every time.
    """
    now_wita = datetime.now(_WITA)
    inside_today = now_wita.replace(hour=3, minute=0, second=0, microsecond=0)
    yesterday_evening = (now_wita - timedelta(days=1)).replace(
        hour=20, minute=0, second=0, microsecond=0
    )

    ep = _episode(tmp_path, n_shots=3)  # projects 60cr
    quota_path = tmp_path / "flow-quota.json"
    _write_quota(quota_path, daily_ceiling_cr=190, balance_remaining_cr=2400)
    ledger_path = tmp_path / "ledger.jsonl"
    for label, ts, credits in (
        ("today-early", inside_today, 150),
        ("yesterday-evening", yesterday_evening, 70),
    ):
        record_spend(
            episode_id=f"{label}-episode",
            shot_index=0,
            credits=credits,
            mode="real",
            veo_job_id=f"wf-{label}",
            source="test-seed",
            clip_cost_cr=20,
            ledger_path=ledger_path,
            ts=ts.isoformat(),
        )

    res = _run_gate(
        ep, tmp_path, ledger_path=ledger_path, quota_path=quota_path,
        business_tz="Asia/Makassar", ambient_tz="UTC",
    )
    assert res.returncode == 0, res.stderr
    cost = _verdict(ep)["checks"]["cost"]
    assert cost["spent_today_cr"] == 150, (
        "today's total is neither 150: the window is not the WITA business day. "
        "0 means an early-local-morning charge was dropped (UTC bucketing, seen "
        "from 08:00 WITA on); 220 means yesterday evening was counted as today "
        "(UTC bucketing, seen before 08:00 WITA)"
    )
    # The resolved zone is stamped so that a silent fallback to the fixed offset
    # is visible in the verdict rather than inferred; assert it, or the stamp is
    # itself untested.
    assert cost["business_tz"] == "Asia/Makassar", cost["business_tz"]
    assert cost["passed"] is False
    assert "daily ceiling" in " ".join(cost["reasons"])


# ---------------------------------------------------------------------------
# 5b. An UNREADABLE ledger must fail closed, never read as a clean zero
# ---------------------------------------------------------------------------


def test_unreadable_ledger_directory_fails_closed_instead_of_reading_zero(tmp_path):
    """The silent half of the unreadable-ledger defect: nothing raises.

    `Path.exists()` answers False both for a file that is absent and for one
    whose directory cannot be read. `read_integrity()` then reports "ok", the
    malformed scan returns 0 and `read_records()` returns [] — so the cost block
    reads a clean "0 spent today" and the gate PASSES with its whole daily
    budget restored. No exception handler can ever see this: there is no
    exception. Under-count is the direction that burns credits.

    150cr are really on today's ledger and the ceiling is 190 with 60 projected.
    Before the fix the gate reads 0 and passes; after it, it refuses.
    """
    if os.geteuid() == 0:
        pytest.skip(
            "running as root: the OS will not make a directory unreadable to "
            "uid 0, so this test's precondition cannot exist here. Distinct "
            "from a test that skips because it cannot TELL two behaviours "
            "apart — the sibling below constructs the same branch without "
            "relying on permission bits, and never skips"
        )

    vault = tmp_path / "vault"
    vault.mkdir()
    ledger_path = vault / "ledger.jsonl"
    record_spend(
        episode_id="hidden-episode", shot_index=0, credits=150, mode="real",
        veo_job_id="wf-hidden", source="test-seed", clip_cost_cr=20,
        ledger_path=ledger_path, ts=datetime.now(timezone.utc).isoformat(),
    )
    ep = _episode(tmp_path, n_shots=3)  # projects 60cr
    quota_path = tmp_path / "flow-quota.json"
    _write_quota(quota_path, daily_ceiling_cr=190, balance_remaining_cr=2400)

    vault.chmod(0o000)
    try:
        res = _run_gate(ep, tmp_path, ledger_path=ledger_path, quota_path=quota_path)
    finally:
        vault.chmod(0o755)  # or tmp_path teardown fails and masks the result

    assert res.returncode == 0, res.stderr
    cost = _verdict(ep)["checks"]["cost"]
    assert cost["passed"] is False, (
        "the gate passed while it could not read the ledger — it read the "
        "unreachable ledger as '0 spent today'"
    )
    assert "not readable" in " ".join(cost["reasons"]), cost["reasons"]


def test_unreachable_ledger_is_caught_without_relying_on_permission_bits(tmp_path):
    """Same branch as above, constructed so no uid can be privileged past it.

    The ledger's parent is a regular FILE. That is not a directory for anyone,
    root included, so the check cannot be satisfied by privilege the way a
    chmod can. Kept as a sibling rather than a replacement: the chmod case is
    the one that actually happens in production, this one is the one that
    always runs.
    """
    not_a_dir = tmp_path / "notadir"
    not_a_dir.write_text("this is a file, not a directory\n")
    ledger_path = not_a_dir / "ledger.jsonl"
    ep = _episode(tmp_path, n_shots=3)
    quota_path = tmp_path / "flow-quota.json"
    _write_quota(quota_path, daily_ceiling_cr=190, balance_remaining_cr=2400)

    res = _run_gate(ep, tmp_path, ledger_path=ledger_path, quota_path=quota_path)

    assert res.returncode == 0, res.stderr
    cost = _verdict(ep)["checks"]["cost"]
    assert cost["passed"] is False, cost
    assert "not readable" in " ".join(cost["reasons"]), cost["reasons"]


def test_unreadable_failures_sidecar_still_produces_a_verdict(tmp_path):
    """The loud half: `read_integrity()` opens the sidecar with no handler.

    It also runs FIRST, before either ledger guard, so an unreadable sidecar
    killed the process before `gate-verdict.json` was written at all — breaking
    the invariant this file states about itself, in the one situation where an
    operator most needs to read a verdict.
    """
    if os.geteuid() == 0:
        pytest.skip("running as root: mode 000 does not deny uid 0")

    ledger_path = tmp_path / "ledger.jsonl"
    record_spend(
        episode_id="ok-episode", shot_index=0, credits=10, mode="real",
        veo_job_id="wf-ok", source="test-seed", clip_cost_cr=20,
        ledger_path=ledger_path, ts=datetime.now(timezone.utc).isoformat(),
    )
    sidecar = tmp_path / "ledger.jsonl.failures"
    sidecar.write_text('{"ts": "2026-08-23T00:00:00+00:00"}\n')
    ep = _episode(tmp_path, n_shots=3)
    quota_path = tmp_path / "flow-quota.json"
    _write_quota(quota_path, daily_ceiling_cr=190, balance_remaining_cr=2400)

    sidecar.chmod(0o000)
    try:
        res = _run_gate(ep, tmp_path, ledger_path=ledger_path, quota_path=quota_path)
    finally:
        sidecar.chmod(0o644)

    assert res.returncode == 0, res.stderr
    assert (ep / "gate-verdict.json").exists(), (
        "no verdict was written: the gate died on the sidecar before reaching "
        "the point where it records why"
    )
    cost = _verdict(ep)["checks"]["cost"]
    assert cost["passed"] is False
    assert "sidecar unreadable" in " ".join(cost["reasons"]), cost["reasons"]


def test_unreadable_ledger_file_in_a_readable_directory_fails_closed(tmp_path):
    """The case `os.access` on the DIRECTORY cannot see, so the handlers must.

    Directory readable, ledger file at mode 000. `_ledger_unreachable_reason`
    correctly says nothing is wrong with the path, and then two separate
    readers open the file anyway: the malformed scan and `read_records()`.
    Both had no handler. Without them the gate dies here rather than reporting
    that it cannot certify the total — and this is the shape a botched `chmod`
    or a restore-from-backup actually produces, far more often than an
    unreadable directory.
    """
    if os.geteuid() == 0:
        pytest.skip("running as root: mode 000 does not deny uid 0")

    ledger_path = tmp_path / "ledger.jsonl"
    record_spend(
        episode_id="unreadable-episode", shot_index=0, credits=150, mode="real",
        veo_job_id="wf-unreadable", source="test-seed", clip_cost_cr=20,
        ledger_path=ledger_path, ts=datetime.now(timezone.utc).isoformat(),
    )
    ep = _episode(tmp_path, n_shots=3)  # projects 60cr, ceiling 190
    quota_path = tmp_path / "flow-quota.json"
    _write_quota(quota_path, daily_ceiling_cr=190, balance_remaining_cr=2400)

    ledger_path.chmod(0o000)
    try:
        res = _run_gate(ep, tmp_path, ledger_path=ledger_path, quota_path=quota_path)
    finally:
        ledger_path.chmod(0o644)

    assert res.returncode == 0, res.stderr
    assert (ep / "gate-verdict.json").exists(), "the gate died before writing a verdict"
    cost = _verdict(ep)["checks"]["cost"]
    assert cost["passed"] is False, cost
    joined = " ".join(cost["reasons"])
    assert "unreadable" in joined, cost["reasons"]


def test_absent_ledger_is_not_mistaken_for_an_unreachable_one(tmp_path):
    """INNOCENCE. Absence is a real, believable zero and must still pass.

    The whole point of the check above is that absent and unreachable answer
    the same from `exists()` but mean opposite things. A guard that refused on
    both would block every first-ever episode — which is how a fail-closed fix
    turns into an outage.
    """
    ledger_path = tmp_path / "never-written" / "ledger.jsonl"  # dir absent too
    ep = _episode(tmp_path, n_shots=3)  # projects 60cr, ceiling 190
    quota_path = tmp_path / "flow-quota.json"
    _write_quota(quota_path, daily_ceiling_cr=190, balance_remaining_cr=2400)

    res = _run_gate(ep, tmp_path, ledger_path=ledger_path, quota_path=quota_path)

    assert res.returncode == 0, res.stderr
    cost = _verdict(ep)["checks"]["cost"]
    assert cost["spent_today_cr"] == 0
    assert cost["passed"] is True, cost["reasons"]
    assert "not readable" not in " ".join(cost["reasons"]), cost["reasons"]


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
