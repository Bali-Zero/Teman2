"""Seat failure classes in the WR2 IG-metrics wrapper's Claude account loop.

A failed seat is classified as failed and the loop moves on: a disabled
subscription or a session-limit notice is never an answer, on stdout or stderr,
exit 0 or not, while an answer that merely discusses limits or organizations
is still accepted. Every seat token below is invented; the wrapper is copied
into tmp_path so its alert gateway resolves to nothing and no alert can leave.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = REPO_ROOT / "infra/launchagents/wrappers/wr2-ig-metrics-analyst-run.sh"

SESSION_LIMIT_BANNER = "You have hit your session limit · resets 11:20pm (Asia/Makassar)\n"
SESSION_LIMIT_BARE = "You have hit your session limit\n"
SUBSCRIPTION_DISABLED = (
    "Your organization has disabled Claude subscription access for Claude Code"
    " · Use an Anthropic API key instead, or ask your admin to enable access\n"
)

FAKE_CLAUDE = """#!/bin/bash
set -u
seat="${CLAUDE_CODE_OAUTH_TOKEN:-keychain}"
echo "$seat" >> "$FAKE_SEAT_DIR/trace"
[ -f "$FAKE_SEAT_DIR/$seat.out" ] && cat "$FAKE_SEAT_DIR/$seat.out"
[ -f "$FAKE_SEAT_DIR/$seat.err" ] && cat "$FAKE_SEAT_DIR/$seat.err" >&2
if [ -f "$FAKE_SEAT_DIR/$seat.rc" ]; then
  exit "$(cat "$FAKE_SEAT_DIR/$seat.rc")"
fi
[ -f "$FAKE_SEAT_DIR/$seat.out" ] || printf 'Weekly analysis written.\\n/tmp/proposed-amendment.md\\n'
exit 0
"""


def _seat(seat_dir: Path, name: str, out: str | None = None, err: str = "", rc: int = 0) -> None:
    if out is not None:
        (seat_dir / f"{name}.out").write_text(out, encoding="utf-8")
    if err:
        (seat_dir / f"{name}.err").write_text(err, encoding="utf-8")
    (seat_dir / f"{name}.rc").write_text(str(rc), encoding="utf-8")


def _run(tmp_path: Path, slots: dict[int, str]) -> tuple[int, list[str], str, str]:
    seat_dir = tmp_path / "seats"
    seat_dir.mkdir(exist_ok=True)
    fake_claude = tmp_path / "claude"
    fake_claude.write_text(FAKE_CLAUDE, encoding="utf-8")
    fake_claude.chmod(0o700)
    wrapper = tmp_path / "wrapper" / WRAPPER.name
    wrapper.parent.mkdir()
    shutil.copy2(WRAPPER, wrapper)
    home = tmp_path / "home"
    queue_dir = home / "nuzantara/apps/war-room/output/queue"
    queue_dir.mkdir(parents=True)
    items = [{"state": "published", "engagement_metrics": {"likes": i}} for i in range(10)]
    (queue_dir / "human-review-queue.json").write_text(json.dumps({"items": items}), encoding="utf-8")

    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_"))}
    env.update(
        {
            "HOME": str(home),
            "FAKE_SEAT_DIR": str(seat_dir),
            "WR2_IG_CLAUDE_BIN": str(fake_claude),
            "WR2_IG_AGY_BIN": str(tmp_path / "no-agy"),
            "WR2_IG_METRICS_TIMEOUT_SECS": "30",
            "WR2_IG_METRICS_ACCOUNT_TIMEOUT_SECS": "5",
            "WR2_IG_METRICS_POLL_SECS": "1",
        }
    )
    for slot, seat in slots.items():
        env[f"CLAUDE_CODE_OAUTH_TOKEN_{slot}"] = seat
    result = subprocess.run(["bash", str(wrapper)], env=env, capture_output=True, text=True, timeout=60)
    trace_file = seat_dir / "trace"
    trace = trace_file.read_text(encoding="utf-8").splitlines() if trace_file.exists() else []
    log = (home / "logs/wr2-ig-metrics-analyst.log").read_text(encoding="utf-8")
    err_log_path = home / "logs/wr2-ig-metrics-analyst.err.log"
    err_log = err_log_path.read_text(encoding="utf-8") if err_log_path.exists() else ""
    return result.returncode, trace, log, err_log


DISABLED_SHAPES = {
    "stdout-exit-1": {"out": SUBSCRIPTION_DISABLED, "rc": 1},
    "stderr-exit-1": {"out": "", "err": SUBSCRIPTION_DISABLED, "rc": 1},
    "stdout-exit-0": {"out": SUBSCRIPTION_DISABLED, "rc": 0},
}


@pytest.mark.parametrize("shape", sorted(DISABLED_SHAPES))
def test_disabled_subscription_seat_is_passed_and_a_later_seat_answers(tmp_path: Path, shape: str) -> None:
    seat_dir = tmp_path / "seats"
    seat_dir.mkdir()
    _seat(seat_dir, "seat-one", out="", err="quota exhausted\n", rc=1)
    _seat(seat_dir, "seat-three", **DISABLED_SHAPES[shape])

    rc, trace, log, _ = _run(tmp_path, {1: "seat-one", 3: "seat-three", 4: "seat-four"})

    assert trace == ["seat-one", "seat-three", "seat-four"]
    assert rc == 0
    assert "used: CLAUDE_CODE_OAUTH_TOKEN_4" in log
    assert "disabled Claude subscription access" not in log


LIMIT_SHAPES = {
    "banner-stdout-exit-0": {"out": SESSION_LIMIT_BANNER, "rc": 0},
    "bare-stdout-exit-0": {"out": SESSION_LIMIT_BARE, "rc": 0},
    "banner-stdout-exit-1": {"out": SESSION_LIMIT_BANNER, "rc": 1},
    "banner-stderr-exit-1": {"out": "", "err": SESSION_LIMIT_BANNER, "rc": 1},
}


@pytest.mark.parametrize("shape", sorted(LIMIT_SHAPES))
def test_session_limit_notice_is_never_accepted_as_an_answer(tmp_path: Path, shape: str) -> None:
    seat_dir = tmp_path / "seats"
    seat_dir.mkdir()
    _seat(seat_dir, "seat-one", **LIMIT_SHAPES[shape])

    rc, trace, log, _ = _run(tmp_path, {1: "seat-one", 3: "seat-three"})

    assert trace == ["seat-one", "seat-three"]
    assert rc == 0
    assert "used: CLAUDE_CODE_OAUTH_TOKEN_3" in log
    assert "hit your session limit" not in log


LAST_FAILURES = {
    "limit": ({"out": SESSION_LIMIT_BANNER, "rc": 0}, "session_limit"),
    "disabled": ({"out": SUBSCRIPTION_DISABLED, "rc": 1}, "subscription_disabled"),
    "empty": ({"out": "", "rc": 0}, "empty_output"),
}


@pytest.mark.parametrize("case", sorted(LAST_FAILURES))
def test_every_seat_failing_ends_nonzero_and_names_the_last_class(tmp_path: Path, case: str) -> None:
    seat_dir = tmp_path / "seats"
    seat_dir.mkdir()
    _seat(seat_dir, "seat-one", out="quota exhausted\n", rc=0)
    last_shape, last_class = LAST_FAILURES[case]
    _seat(seat_dir, "keychain", **last_shape)

    rc, trace, log, err_log = _run(tmp_path, {1: "seat-one"})

    assert trace == ["seat-one", "keychain"]
    assert rc != 0
    assert "done (exit=0)" not in log
    assert f"all Claude OAuth accounts unavailable (last failure: {last_class})" in err_log
    assert "alert NOT sent" in err_log


ANSWERS = [
    "Carousel 4 explains how an organization can hit your session limit on visa runs.\n/tmp/a.md\n",
    "You have hit your session limit on tourist visa runs: posts with this hook got 2x saves.\n/tmp/a.md\n",
    "Organizations that disabled auto-renewal posted less; quota-themed covers did not matter.\n/tmp/a.md\n",
]


@pytest.mark.parametrize("answer", ANSWERS)
def test_an_answer_that_discusses_limits_or_organizations_is_accepted(tmp_path: Path, answer: str) -> None:
    seat_dir = tmp_path / "seats"
    seat_dir.mkdir()
    _seat(seat_dir, "seat-one", out=answer, rc=0)

    rc, trace, log, _ = _run(tmp_path, {1: "seat-one", 3: "seat-three"})

    assert trace == ["seat-one"]
    assert rc == 0
    assert "used: CLAUDE_CODE_OAUTH_TOKEN_1" in log


def test_an_unclassified_failure_still_stops_the_loop(tmp_path: Path) -> None:
    seat_dir = tmp_path / "seats"
    seat_dir.mkdir()
    _seat(seat_dir, "seat-one", out="", err="Error: agent definition not found\n", rc=2)

    rc, trace, _, _ = _run(tmp_path, {1: "seat-one", 3: "seat-three"})

    assert trace == ["seat-one"]
    assert rc == 2


# Council fixtures (WR2CLASS-20261005, rounds 1-2): each judged by the wrapper's
# own claude_failure_class, extracted from the file rather than copied.
def _classify(tmp_path: Path, out: str, err: str = "", rc: int = 0) -> str:
    function = subprocess.run(
        ["sed", "-n", "/^claude_failure_class()/,/^}/p", str(WRAPPER)],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "claude_failure_class" in function
    out_file, err_file = tmp_path / "out", tmp_path / "err"
    out_file.write_text(out, encoding="utf-8")
    err_file.write_text(err, encoding="utf-8")
    result = subprocess.run(
        ["bash", "-c", function + '\nclaude_failure_class "$1" "$2" "$3"\n', "classify",
         str(out_file), str(err_file), str(rc)],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


NOTICES = [
    (SUBSCRIPTION_DISABLED, "", "subscription_disabled"),
    ("Your organization has disabled Claude subscription access for Claude Code\n"
     "Use an Anthropic API key instead, or ask your admin to enable access\n", "", "subscription_disabled"),
    ("Organization has disabled Claude subscription access.\nResets in 5m.\n", "", "subscription_disabled"),
    ("Error: Your organization has disabled Claude subscription access for Claude Code\n", "", "subscription_disabled"),
    ('{"type":"error","error":{"message":"Your organization has disabled\\nClaude subscription access"}}', "",
     "subscription_disabled"),
    ("", SUBSCRIPTION_DISABLED, "subscription_disabled"),
    ("Claude error: You have hit your session limit · resets 11:20pm (Asia/Makassar)\n", "", "session_limit"),
    ("Claude error: You have hit your session limit.\nResets at 00:00.\n", "", "session_limit"),
    ("You've reached your session limit. Resets 11:20pm (Asia/Makassar).\n", "", "session_limit"),
    ("You've reached your session limit.\nContact your admin.\n", "", "session_limit"),
    ("You have hit your session limit · resets 10pm\nPlease run /login\n", "", "session_limit"),
    ("Out of extra usage · resets 11:20pm (Asia/Makassar)\n", "", "session_limit"),
    ("You have hit your session limit\nPlease try again later.\n", "", "session_limit"),
    ('{"type":"error","error":{"message":"You have hit your session limit"}}', "", "session_limit"),
    ("", SESSION_LIMIT_BANNER, "session_limit"),
    ("quota exhausted\n", "", "quota_or_auth"),
    ("Please run /login.\n", "", "quota_or_auth"),
]


@pytest.mark.parametrize(("out", "err", "expected"), NOTICES)
def test_every_notice_shape_is_classified(tmp_path: Path, out: str, err: str, expected: str) -> None:
    assert _classify(tmp_path, out, err) == expected
    assert _classify(tmp_path, out, err, rc=1) == expected


REAL_ANSWERS = ANSWERS + [
    "Rate limit mitigation: 3 posting windows\n/tmp/ig/amendment.md\n",
    "Quota exhausted is the strongest hook this week.\n/tmp/a.md\n",
    "Authentication required posts earned 2x saves.\n/tmp/a.md\n",
    "Weekly limit planning for the IG carousel\n/tmp/a.md\n",
    "401 audit findings: expired tokens\n/tmp/a.md\n",
    "Rate limit\n/tmp/ig/amendment.md\n",
    "Quota exhausted\nretry.md\n",
    "quota exhausted.md\n",
    "You have hit your session limit: this hook earned 2x saves.\nretry-amendment.md\n",
]


@pytest.mark.parametrize("answer", REAL_ANSWERS)
def test_no_real_answer_is_classified_as_a_seat_failure(tmp_path: Path, answer: str) -> None:
    assert _classify(tmp_path, answer) == ""
