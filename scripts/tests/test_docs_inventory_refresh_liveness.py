"""Tests for scripts/docs_inventory_refresh_liveness.py — the P3-prime liveness
guardian for the docs-inventory-refresh.yml scheduled organ.

Two layers, matching the script's own I/O-vs-decision split:
  - Pure-function tests on check_liveness()/latest_success() — in-process,
    date-mocked, no subprocess/network (the guilt+innocence discipline this
    repo applies to date-sensitive guards, mirrored from test_docs_audit.py).
  - CLI-level tests via --runs-json (a file, never real `gh`/network) proving
    the exit-code contract: 0 alive, 1 overdue/never-ran, 2 couldn't determine.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "docs_inventory_refresh_liveness.py"

sys.path.insert(0, str(SCRIPT.parent))
import docs_inventory_refresh_liveness as liveness  # noqa: E402


def _run(
    *, tmp_path: Path, runs: list, prs: list | None = None, **extra_args
) -> subprocess.CompletedProcess:
    """`prs=None` defaults to an EMPTY list (--prs-json), never omitted:
    BLOCKER-4 added a second, independent `gh pr list` fetch to main() — if
    this helper didn't pin it to a deterministic file, every test using it
    would silently shell out to the real `gh` CLI against the real repo over
    the network (exactly the "no subprocess/network" property this file's
    own header promises), and would be non-deterministic / environment-
    dependent (no GH_TOKEN in a bare pytest invocation) rather than a unit
    test. `runs`-only callers (all pre-BLOCKER-4 tests) get an implicit "no
    open flip-PRs" baseline, matching the common case.
    """
    runs_json = tmp_path / "runs.json"
    runs_json.write_text(json.dumps(runs), encoding="utf-8")
    prs_json = tmp_path / "prs.json"
    prs_json.write_text(json.dumps(prs if prs is not None else []), encoding="utf-8")
    args = [
        sys.executable,
        str(SCRIPT),
        "--repo",
        "Balizero1987/Teman2",
        "--workflow",
        "docs-inventory-refresh.yml",
        "--runs-json",
        str(runs_json),
        "--prs-json",
        str(prs_json),
    ]
    for k, v in extra_args.items():
        args += [f"--{k.replace('_', '-')}", str(v)]
    return subprocess.run(args, capture_output=True, text=True)


def _run_at(iso: str, conclusion: str = "success", **overrides) -> dict:
    row = {
        "databaseId": 1,
        "status": "completed",
        "conclusion": conclusion,
        "createdAt": iso,
        "updatedAt": iso,
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# Pure decision function — check_liveness() / latest_success()
# ---------------------------------------------------------------------------


def test_never_ran_is_not_alive():
    now = datetime(2026, 7, 18, tzinfo=timezone.utc)
    alive, msg = liveness.check_liveness([], now, timedelta(hours=24))
    assert alive is False
    assert "NEVER completed successfully" in msg


def test_ran_but_never_succeeded_is_not_alive():
    now = datetime(2026, 7, 18, tzinfo=timezone.utc)
    runs = [
        _run_at("2026-07-17T19:00:00Z", conclusion="failure"),
        _run_at("2026-07-17T07:00:00Z", conclusion="failure"),
    ]
    alive, msg = liveness.check_liveness(runs, now, timedelta(hours=24))
    assert alive is False
    assert "NEVER completed successfully" in msg


def test_recent_success_is_alive():
    now = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
    runs = [_run_at("2026-07-18T07:00:00Z")]  # 5h ago
    alive, msg = liveness.check_liveness(runs, now, timedelta(hours=24))
    assert alive is True
    assert "OK" in msg


def test_stale_success_is_not_alive():
    now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    runs = [_run_at("2026-07-17T07:00:00Z")]  # ~3.2 days ago
    alive, msg = liveness.check_liveness(runs, now, timedelta(hours=24))
    assert alive is False
    assert "last succeeded" in msg
    assert "may be silently disarmed" in msg


def test_boundary_exactly_at_max_age_is_still_alive():
    """Strict `>` (not `>=`), matching this repo's general boundary discipline
    (see docs_audit.py's identical strict-vs-inclusive reasoning): exactly AT
    the threshold is not yet overdue.
    """
    now = datetime(2026, 7, 18, 7, 0, tzinfo=timezone.utc)
    runs = [_run_at("2026-07-17T07:00:00Z")]  # exactly 24h ago
    alive, _ = liveness.check_liveness(runs, now, timedelta(hours=24))
    assert alive is True

    now_one_second_later = now + timedelta(seconds=1)
    alive, _ = liveness.check_liveness(runs, now_one_second_later, timedelta(hours=24))
    assert alive is False


def test_picks_the_most_recent_success_not_the_oldest():
    runs = [
        _run_at("2026-06-01T07:00:00Z", databaseId=1),  # old, stale
        _run_at("2026-07-18T07:00:00Z", databaseId=2),  # recent
        _run_at("2026-07-10T07:00:00Z", databaseId=3),  # middle
    ]
    run = liveness.latest_success(runs)
    assert run["databaseId"] == 2


def test_a_more_recent_failure_does_not_mask_an_older_success():
    """The most recent RUN overall might have failed — that must not hide an
    earlier success; liveness cares about the latest SUCCESS specifically.
    """
    now = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
    runs = [
        _run_at("2026-07-18T09:00:00Z", conclusion="failure"),  # newest, failed
        _run_at("2026-07-18T07:00:00Z", conclusion="success"),  # 5h ago, succeeded
    ]
    alive, _ = liveness.check_liveness(runs, now, timedelta(hours=24))
    assert alive is True


def test_unparseable_timestamp_is_not_alive_with_distinct_message():
    now = datetime(2026, 7, 18, tzinfo=timezone.utc)
    runs = [_run_at("not-a-timestamp")]
    alive, msg = liveness.check_liveness(runs, now, timedelta(hours=24))
    assert alive is False
    assert "unparseable timestamp" in msg


# ---------------------------------------------------------------------------
# CLI-level — exit-code contract via --runs-json (no network)
# ---------------------------------------------------------------------------


def test_cli_never_ran_exits_1(tmp_path):
    result = _run(tmp_path=tmp_path, runs=[])
    assert result.returncode == 1
    assert "NEVER completed successfully" in result.stderr


def test_cli_recent_success_exits_0(tmp_path):
    now = datetime.now(tz=timezone.utc)
    recent = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    result = _run(tmp_path=tmp_path, runs=[_run_at(recent)])
    assert result.returncode == 0
    assert "OK" in result.stdout


def test_cli_stale_success_exits_1(tmp_path):
    now = datetime.now(tz=timezone.utc)
    stale = (now - timedelta(days=5)).isoformat().replace("+00:00", "Z")
    result = _run(tmp_path=tmp_path, runs=[_run_at(stale)])
    assert result.returncode == 1
    assert "last succeeded" in result.stderr


def test_cli_custom_max_age_hours_is_honored(tmp_path):
    """A success 2h old is 'alive' under the default 24h threshold but
    'overdue' under a tightened --max-age-hours 1 — proves the CLI actually
    threads the flag through to the decision function, not just accepting it.
    """
    now = datetime.now(tz=timezone.utc)
    two_hours_ago = (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    default_result = _run(tmp_path=tmp_path, runs=[_run_at(two_hours_ago)])
    assert default_result.returncode == 0

    tight_result = _run(
        tmp_path=tmp_path, runs=[_run_at(two_hours_ago)], max_age_hours=1
    )
    assert tight_result.returncode == 1


def test_cli_missing_repo_arg_exits_nonzero(tmp_path):
    runs_json = tmp_path / "runs.json"
    runs_json.write_text("[]", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--runs-json", str(runs_json)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "--repo" in result.stderr


def test_cli_malformed_runs_json_exits_2_not_0_or_1(tmp_path):
    """A file that can't even be parsed is a DIFFERENT failure mode than
    'checked and found overdue' — must be distinguishable (exit 2), never
    silently reported as either 'alive' or a plain 'overdue'.
    """
    bad_file = tmp_path / "not_json.txt"
    bad_file.write_text("this is not json{{{", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo",
            "Balizero1987/Teman2",
            "--runs-json",
            str(bad_file),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "COULD NOT DETERMINE" in result.stderr


def test_cli_missing_runs_json_file_exits_2(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo",
            "Balizero1987/Teman2",
            "--runs-json",
            str(tmp_path / "does_not_exist.json"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "COULD NOT DETERMINE" in result.stderr


# ---------------------------------------------------------------------------
# Red-team round 1 (2026-07-18) BLOCKER-4: EFFECT-check — stuck flip-PRs.
# Mirrors the check_liveness()/CLI split above exactly.
# ---------------------------------------------------------------------------


def _pr_at(iso: str, number: int = 1, branch: str | None = None, **overrides) -> dict:
    row = {
        "number": number,
        "headRefName": branch or "docs/auto-sync-inventory-2026-07-17",
        "createdAt": iso,
        "url": f"https://github.com/Balizero1987/Teman2/pull/{number}",
    }
    row.update(overrides)
    return row


def test_no_open_prs_is_ok():
    now = datetime(2026, 7, 18, tzinfo=timezone.utc)
    ok, msg = liveness.check_stuck_prs([], now, timedelta(hours=48))
    assert ok is True
    assert "no open organ-authored flip-PR" in msg


def test_recent_open_pr_is_ok():
    now = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
    prs = [_pr_at("2026-07-18T07:00:00Z")]  # 5h ago
    ok, msg = liveness.check_stuck_prs(prs, now, timedelta(hours=48))
    assert ok is True
    assert "OK" in msg


def test_stuck_open_pr_is_not_ok():
    """GUILT: a flip-PR open 60h (> 48h threshold) must alarm."""
    now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    prs = [_pr_at("2026-07-18T00:00:00Z", number=42)]  # 60h ago
    ok, msg = liveness.check_stuck_prs(prs, now, timedelta(hours=48))
    assert ok is False
    assert "stuck OPEN" in msg
    assert "#42" in msg


def test_boundary_exactly_at_pr_max_age_is_still_ok():
    """Strict `>`, mirroring check_liveness()'s identical boundary discipline."""
    now = datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc)
    prs = [_pr_at("2026-07-18T00:00:00Z")]  # exactly 48h ago
    ok, _ = liveness.check_stuck_prs(prs, now, timedelta(hours=48))
    assert ok is True

    ok, _ = liveness.check_stuck_prs(
        prs, now + timedelta(seconds=1), timedelta(hours=48)
    )
    assert ok is False


def test_non_organ_pr_is_ignored():
    """INNOCENCE: a PR whose branch does NOT match the organ's prefix must
    never be flagged, even if it's ancient — entity-matched (branch prefix),
    not "any open PR from this author is suspect".
    """
    now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    prs = [_pr_at("2026-01-01T00:00:00Z", branch="some/unrelated-branch")]
    ok, msg = liveness.check_stuck_prs(prs, now, timedelta(hours=48))
    assert ok is True
    assert "no open organ-authored flip-PR" in msg


def test_unparseable_pr_created_at_fails_closed_as_stuck():
    """Fail-closed direction (mirrors run-liveness's identical choice): an
    unparseable date can't be PROVEN young, so it's treated as stuck rather
    than silently OK.
    """
    now = datetime(2026, 7, 18, tzinfo=timezone.utc)
    prs = [_pr_at("not-a-timestamp")]
    ok, msg = liveness.check_stuck_prs(prs, now, timedelta(hours=48))
    assert ok is False
    assert "unparseable" in msg.lower()


def test_multiple_stuck_prs_all_named_in_message():
    now = datetime(2026, 7, 22, 0, 0, tzinfo=timezone.utc)
    prs = [
        _pr_at("2026-07-18T00:00:00Z", number=10),
        _pr_at("2026-07-19T00:00:00Z", number=11),
    ]
    ok, msg = liveness.check_stuck_prs(prs, now, timedelta(hours=48))
    assert ok is False
    assert "#10" in msg and "#11" in msg
    assert "2 flip-PR(s)" in msg


# ---------------------------------------------------------------------------
# CLI-level — the combined exit-code contract via --runs-json + --prs-json
# ---------------------------------------------------------------------------


def test_cli_stuck_pr_alone_makes_an_otherwise_healthy_run_exit_1(tmp_path):
    """The core BLOCKER-4 proof: a perfectly healthy WORKFLOW RUN (recent
    success) must still exit 1 if the organ's own flip-PR is stuck open past
    threshold — "workflow succeeded" is necessary but not sufficient.
    """
    now = datetime.now(tz=timezone.utc)
    recent_run = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    stuck_pr_created = (now - timedelta(hours=60)).isoformat().replace("+00:00", "Z")
    result = _run(
        tmp_path=tmp_path,
        runs=[_run_at(recent_run)],
        prs=[_pr_at(stuck_pr_created)],
    )
    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert "OK — docs-inventory-refresh last succeeded" in combined  # run half: fine
    assert "stuck OPEN" in combined  # PR half: the actual alarm


def test_cli_no_stuck_pr_stays_green(tmp_path):
    now = datetime.now(tz=timezone.utc)
    recent_run = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    result = _run(tmp_path=tmp_path, runs=[_run_at(recent_run)], prs=[])
    assert result.returncode == 0


def test_cli_custom_pr_max_age_hours_is_honored(tmp_path):
    now = datetime.now(tz=timezone.utc)
    recent_run = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    pr_created = (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    default_result = _run(
        tmp_path=tmp_path, runs=[_run_at(recent_run)], prs=[_pr_at(pr_created)]
    )
    assert default_result.returncode == 0  # 2h old, well under default 48h

    tight_result = _run(
        tmp_path=tmp_path,
        runs=[_run_at(recent_run)],
        prs=[_pr_at(pr_created)],
        pr_max_age_hours=1,
    )
    assert tight_result.returncode == 1  # 2h old, over a tightened 1h threshold


def test_cli_malformed_prs_json_exits_2(tmp_path):
    """Same distinct-failure-mode discipline as the runs-json malformed
    case: a PR-list fetch/parse failure is NOT a silent 'no stuck PRs'."""
    runs_json = tmp_path / "runs.json"
    runs_json.write_text("[]", encoding="utf-8")
    bad_prs = tmp_path / "bad_prs.json"
    bad_prs.write_text("not json{{{", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo",
            "Balizero1987/Teman2",
            "--runs-json",
            str(runs_json),
            "--prs-json",
            str(bad_prs),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "COULD NOT DETERMINE stuck-PR status" in result.stderr


def test_real_repo_slug_constant_is_the_correct_one():
    """Regression lock for the exact bug caught during this script's own
    build: a plausible-looking-but-WRONG hardcoded default ('Balizero1987/
    nuzantara') would have made this guardian always 404 against a
    nonexistent repo and permanently report 'never ran'. --repo has no
    default at all (see its --help text) — this test pins that down.
    """
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True
    )
    assert result.returncode == 0
    # argparse reflows/wraps help text at ~79 cols, so a long phrase can be
    # split across lines with different whitespace than the source — collapse
    # all whitespace before substring-matching to be robust to that wrapping.
    collapsed = " ".join(result.stdout.split())
    assert "nuzantara', a name that reads plausible but is wrong" in collapsed
    # argparse marks a required flag "--repo REPO" (no brackets) in the usage
    # summary, vs. an optional one like "[--workflow WORKFLOW]" — pins that
    # --repo really is required, not just documented as such in prose.
    assert "--repo REPO" in result.stdout
    assert "[--repo" not in result.stdout
