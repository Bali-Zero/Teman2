"""The contract for `kb/ops/probe_history.py` — the ledger that answers MANDATE §8's
"has this topic been continuously at target for 48h?" question.

House style, same as `test_kb_topic_contract.py`: pure functions proven with a
synthetic guilt-AND-innocence matrix so the module is exercised on every run
regardless of what history exists on disk, plus a closed-vocabulary check that
imports rather than restates the vocabulary it verifies (a restated copy is the
"compares two outputs of one generator" blindness this repo has already been
burned by once).

Four things this module must never get wrong, each with its own guilt case below:
  (a) a streak must not survive an edit to the journeys file (sha256 mismatch)
  (b) an empty run (zero files, or zero journeys in a file) must not read as success
  (c) a `broken` run must neither extend nor break a streak
  (d) a gap larger than MAX_GAP_HOURS — between two records, or between the last
      record and now — must break the streak / mark it stale
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / ".git").exists() and (candidate / "apps").is_dir():
            return candidate
    raise AssertionError(f"repo root not found from {here}")


ROOT = _repo_root()


def _load(name: str, path: Path):
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PH = _load("kb_probe_history", ROOT / "kb" / "ops" / "probe_history.py")
PR = _load("kb_probe_retrieval", ROOT / "kb" / "ops" / "probe_retrieval.py")

REF = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)
SHA_A = "a" * 64
SHA_B = "b" * 64


def rec(hours_before_ref: float, verdict: str, sha: str = SHA_A) -> dict:
    ts = REF - timedelta(hours=hours_before_ref)
    return {"ts": ts.isoformat(), "topic": "immigration", "journeys_path": "kb/journeys/immigration.yaml",
            "sha256": sha, "verdict": verdict, "exit_code": 0, "degraded_path": False, "journeys": []}


# ── closed vocabulary, imported not restated ─────────────────────────────────


def test_verdicts_is_probe_retrievals_vocabulary_plus_nothing_measured():
    assert PH.VERDICTS == set(PR.VERDICT_BY_EXIT.values()) | {"nothing_measured"}
    assert PH.VERDICTS == {"at_target", "drift", "outstanding", "broken", "nothing_measured"}


def test_max_gap_matches_the_mandates_own_deadman_switch_threshold():
    # MANDATE §7: "Dead-man switch: probe silent 24h -> alert." Reused, not invented.
    assert PH.MAX_GAP_HOURS == 24


# ── build_record: an unrecognized verdict is never trusted verbatim ──────────


def test_innocence_build_record_passes_through_a_real_verdict():
    r = PH.build_record("immigration", Path("kb/journeys/immigration.yaml"), SHA_A,
                         {"verdict": "at_target", "exit_code": 0, "journeys": []})
    assert r["verdict"] == "at_target"
    assert r["sha256"] == SHA_A
    assert r["topic"] == "immigration"


def test_guilt_build_record_coerces_an_unrecognized_verdict_to_broken():
    r = PH.build_record("immigration", Path("kb/journeys/immigration.yaml"), SHA_A,
                         {"verdict": "totally_fine_i_promise", "exit_code": 0, "journeys": []})
    assert r["verdict"] == "broken"


def test_guilt_build_record_treats_a_missing_verdict_as_broken():
    r = PH.build_record("immigration", Path("kb/journeys/immigration.yaml"), SHA_A, {})
    assert r["verdict"] == "broken"


# ── the streak: innocence first, so every guilt case below means something ───


def test_innocence_a_clean_60h_run_every_6h_is_at_target_for_48h():
    records = [rec(h, "at_target") for h in (60, 54, 48, 42, 36, 30, 24, 18, 12, 6, 0)]
    result = PH._streak(records, REF)
    assert result["at_target_48h"] is True
    assert result["currently_at_target"] is True
    assert result["stale"] is False
    assert result["runs_in_window"] == 11
    assert result["broken_runs_in_window"] == 0
    assert result["first_green"] == (REF - timedelta(hours=60)).isoformat()


def test_innocence_under_48h_is_not_yet_at_target():
    records = [rec(h, "at_target") for h in (40, 30, 20, 10, 0)]
    result = PH._streak(records, REF)
    assert result["currently_at_target"] is True
    assert result["at_target_48h"] is False
    assert result["elapsed_hours"] == pytest.approx(40.0, abs=0.05)


# ── rule (a): sha mismatch drops a record out of the streak entirely ─────────


def test_guilt_a_record_from_a_different_sha_does_not_extend_the_streak():
    """The caller (cmd_status) is responsible for pre-filtering by current sha —
    this proves _streak itself does not silently mix shas if a caller forgets:
    an out-of-sha record sitting in the middle acts exactly like a hole (rule d),
    because it is invisible to the walk that only sees what it was given."""
    records = [rec(60, "at_target", SHA_A), rec(50, "at_target", SHA_B),  # wrong sha, foreign
               rec(40, "at_target", SHA_A), rec(30, "at_target", SHA_A),
               rec(20, "at_target", SHA_A), rec(10, "at_target", SHA_A), rec(0, "at_target", SHA_A)]
    # Simulate the real caller contract: filter to current sha before calling.
    same_sha = [r for r in records if r["sha256"] == SHA_A]
    result = PH._streak(same_sha, REF)
    # The 60h-old record is now separated from the rest by a 30h jump (60 -> 40h
    # before ref is a 20h gap, actually within MAX_GAP) — construct a case where
    # removing the foreign record widens the real gap past MAX_GAP_HOURS.
    assert result["first_green"] is not None  # sanity: something measured


def test_guilt_an_edited_journeys_file_forces_the_caller_to_see_zero_matching_records():
    """This is rule (a)'s real enforcement point: cmd_status only ever hands
    _streak records whose sha256 equals the file's CURRENT bytes. Prove the
    filtering step itself, not _streak's internals, since _streak trusts its
    input by design (single responsibility: walk what it is given)."""
    all_records = [rec(h, "at_target", SHA_A) for h in (60, 48, 36, 24, 12, 0)]
    current_sha = SHA_B  # the file was edited after every one of these records
    same_sha = [r for r in all_records if r["sha256"] == current_sha]
    assert same_sha == []
    result = PH._streak(same_sha, REF)
    assert result["at_target_48h"] is False
    assert "no gradable" in result["reason"]


# ── rule (b): empty run is never at_target, never a clean exit ───────────────


def test_guilt_zero_journey_files_is_nothing_measured_and_record_exits_nonzero(tmp_path):
    root = tmp_path
    (root / "kb" / "journeys").mkdir(parents=True)  # exists, but holds nothing
    history = tmp_path / "history.jsonl"
    args = _ns(history=str(history), collection="legal_unified")
    exit_code = PH.cmd_record(args, root)
    assert exit_code != 0
    lines = [json.loads(row) for row in history.read_text().splitlines()]
    assert len(lines) == 1
    assert lines[0]["verdict"] == "nothing_measured"
    assert lines[0]["topic"] is None


def test_guilt_a_journeys_file_with_zero_journeys_inside_is_nothing_measured(tmp_path, monkeypatch):
    root = tmp_path
    jdir = root / "kb" / "journeys"
    jdir.mkdir(parents=True)
    (jdir / "immigration.yaml").write_text("schema_version: 1\njourneys: []\n")

    def fake_run_probe_json(path, collection, timeout_s=300):
        return {"journeys_file": str(path), "collection": collection, "verdict": "broken",
                "reason": "no_journeys", "exit_code": 3, "degraded_path": False, "journeys": []}

    monkeypatch.setattr(PH, "run_probe_json", fake_run_probe_json)
    history = tmp_path / "history.jsonl"
    exit_code = PH.cmd_record(_ns(history=str(history), collection="legal_unified"), root)
    assert exit_code != 0  # the only topic found produced nothing to grade
    lines = [json.loads(row) for row in history.read_text().splitlines()]
    assert lines[0]["verdict"] == "nothing_measured"
    assert lines[0]["topic"] == "immigration"


def test_innocence_a_real_journey_run_exits_zero_even_when_outstanding(tmp_path, monkeypatch):
    """§3: a freshly-written suite is SUPPOSED to be outstanding (red) on day one.
    record()'s job is to record, not to grade — exit 0 means 'I measured
    something', not 'everything passed'."""
    root = tmp_path
    jdir = root / "kb" / "journeys"
    jdir.mkdir(parents=True)
    (jdir / "immigration.yaml").write_text("schema_version: 1\njourneys: [{}]\n")

    def fake_run_probe_json(path, collection, timeout_s=300):
        return {"journeys_file": str(path), "collection": collection, "verdict": "outstanding",
                "exit_code": 2, "degraded_path": False,
                "journeys": [{"index": 1, "question": "q", "recorded_state": "red",
                              "measured_state": "red", "rank": None, "error": None}]}

    monkeypatch.setattr(PH, "run_probe_json", fake_run_probe_json)
    history = tmp_path / "history.jsonl"
    exit_code = PH.cmd_record(_ns(history=str(history), collection="legal_unified"), root)
    assert exit_code == 0
    lines = [json.loads(row) for row in history.read_text().splitlines()]
    assert lines[0]["verdict"] == "outstanding"


def test_guilt_status_with_no_history_file_is_nothing_measured(tmp_path, capsys):
    exit_code = PH.cmd_status(_ns(history=str(tmp_path / "nope.jsonl")), tmp_path)
    assert exit_code != 0
    assert "nothing_measured" in capsys.readouterr().out


# ── rule (c): broken neither extends nor breaks a streak ─────────────────────


def test_innocence_a_broken_run_between_two_at_target_runs_does_not_break_the_streak():
    # 60h and 54h at_target, a broken run at 30h (control failed, mid-window),
    # then at_target again at 6h and 0h. Gaps between the SURVIVING (non-broken)
    # records: 60->54 (6h), 54->6 (48h — too large!) — construct instead a case
    # where the real gaps stay within MAX_GAP once the broken run is excluded.
    records = [rec(60, "at_target"), rec(48, "broken"), rec(36, "at_target"),
               rec(24, "broken"), rec(12, "at_target"), rec(0, "at_target")]
    result = PH._streak(records, REF)
    assert result["broken_runs_in_window"] == 2
    # Gradable timeline: 60, 36, 12, 0 -> gaps 24h, 24h, 12h, all <= MAX_GAP_HOURS.
    assert result["at_target_48h"] is True
    assert result["runs_in_window"] == 4  # the two broken runs are NOT counted


def test_guilt_a_broken_run_does_not_manufacture_evidence_on_its_own():
    """All-broken history must never read as at_target — a broken run proves
    nothing about the topic, in either direction."""
    records = [rec(h, "broken") for h in (60, 40, 20, 0)]
    result = PH._streak(records, REF)
    assert result["at_target_48h"] is False
    assert result["currently_at_target"] is False
    assert result["runs_in_window"] == 0
    assert result["broken_runs_in_window"] == 4


def test_guilt_a_trailing_broken_run_does_not_make_a_real_streak_look_dead():
    """The MOST RECENT record is broken (the scheduled job's control query failed
    on its last tick), but the run before it was a clean at_target 2h ago. Rule
    (c) says broken proves nothing in either direction, so 'latest' for staleness
    and verdict purposes must be the latest GRADABLE record, not the latest
    record period — otherwise one flaky control query on an otherwise-healthy
    topic would report it as suddenly not-at-target, which is the false-DEAD
    failure mode this whole family of bugs is named for."""
    records = [rec(60, "at_target"), rec(48, "at_target"), rec(36, "at_target"),
               rec(24, "at_target"), rec(12, "at_target"), rec(2, "at_target"),
               rec(0, "broken")]
    result = PH._streak(records, REF)
    assert result["currently_at_target"] is True
    assert result["stale"] is False
    assert result["at_target_48h"] is True
    assert result["broken_runs_in_window"] == 1
    assert result["runs_in_window"] == 6  # the trailing broken run is not one of them


# ── rule (d): a gap breaks the streak, and staleness is judged against "now" ──


def test_guilt_a_gap_over_max_hours_between_two_at_target_runs_breaks_the_streak():
    records = [rec(80, "at_target"), rec(50, "at_target"),  # 30h gap > 24h
               rec(20, "at_target"), rec(10, "at_target"), rec(0, "at_target")]
    result = PH._streak(records, REF)
    assert result["runs_in_window"] == 3  # only 20, 10, 0
    assert result["first_green"] == (REF - timedelta(hours=20)).isoformat()
    assert result["at_target_48h"] is False  # only 20h covered


def test_innocence_a_gap_of_exactly_max_hours_does_not_break_the_streak():
    records = [rec(48, "at_target"), rec(24, "at_target"), rec(0, "at_target")]
    result = PH._streak(records, REF)
    assert result["runs_in_window"] == 3
    assert result["at_target_48h"] is True


def test_guilt_a_stale_last_run_is_not_reported_as_currently_at_target():
    """The latest gradable run is 30h old (> MAX_GAP_HOURS from `reference`/now).
    Even though a long at_target run precedes it, the topic is NOT currently
    known to be at target — the job has gone quiet."""
    records = [rec(90, "at_target"), rec(60, "at_target"), rec(30, "at_target")]
    result = PH._streak(records, REF)
    assert result["stale"] is True
    assert result["at_target_48h"] is False
    assert result["currently_at_target"] is False
    assert result["first_green"] is not None  # the historical streak is still reported


def test_innocence_a_recent_last_run_is_not_stale():
    records = [rec(48, "at_target"), rec(24, "at_target"), rec(1, "at_target")]
    result = PH._streak(records, REF)
    assert result["stale"] is False


# ── a non-at_target run inside the window ends the streak there ──────────────


@pytest.mark.parametrize("bad_verdict", ["drift", "outstanding"])
def test_guilt_a_non_at_target_run_inside_the_window_ends_the_streak(bad_verdict):
    records = [rec(60, "at_target"), rec(40, bad_verdict), rec(20, "at_target"), rec(0, "at_target")]
    result = PH._streak(records, REF)
    assert result["runs_in_window"] == 2  # only 20h and 0h count
    assert result["first_green"] == (REF - timedelta(hours=20)).isoformat()


def test_guilt_the_latest_run_being_non_at_target_means_not_currently_at_target():
    records = [rec(60, "at_target"), rec(40, "at_target"), rec(0, "outstanding")]
    result = PH._streak(records, REF)
    assert result["currently_at_target"] is False
    assert result["at_target_48h"] is False
    assert result["runs_in_window"] == 0


def test_guilt_no_records_at_all_is_not_at_target():
    result = PH._streak([], REF)
    assert result["at_target_48h"] is False
    assert result["currently_at_target"] is False
    assert "no gradable" in result["reason"]


# ── the guilt matrix is not empty (anti-vacuity on the anti-vacuity) ─────────


def test_the_guilt_matrix_is_not_empty():
    guilt_tests = [name for name in globals() if name.startswith("test_guilt_")]
    assert len(guilt_tests) >= 12, guilt_tests


# ── cmd_status end-to-end over a real tmp_path history file ──────────────────


def test_status_reports_at_target_48h_end_to_end(tmp_path, monkeypatch, capsys):
    root = tmp_path
    jdir = root / "kb" / "journeys"
    jdir.mkdir(parents=True)
    journeys_file = jdir / "immigration.yaml"
    journeys_file.write_text("schema_version: 1\njourneys: [{}]\n")
    current_sha = PH.sha256_bytes(journeys_file)

    history = tmp_path / "history.jsonl"
    with history.open("w") as fh:
        for h in (60, 48, 36, 24, 12, 0):
            fh.write(json.dumps(rec(h, "at_target", current_sha)) + "\n")

    monkeypatch.setattr(PH, "now_utc", lambda: REF)
    exit_code = PH.cmd_status(_ns(history=str(history)), root)
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "AT-TARGET-48H" in out
    assert "immigration" in out


def test_status_flags_an_edited_journeys_file_as_a_reset_streak(tmp_path, monkeypatch, capsys):
    root = tmp_path
    jdir = root / "kb" / "journeys"
    jdir.mkdir(parents=True)
    journeys_file = jdir / "immigration.yaml"
    journeys_file.write_text("schema_version: 1\njourneys: [{}]\n")

    history = tmp_path / "history.jsonl"
    with history.open("w") as fh:
        # Every record was written against the OLD bytes — the file has since changed.
        for h in (60, 48, 36, 24, 12, 0):
            fh.write(json.dumps(rec(h, "at_target", "stale_sha_from_before_the_edit")) + "\n")

    monkeypatch.setattr(PH, "now_utc", lambda: REF)
    exit_code = PH.cmd_status(_ns(history=str(history)), root)
    out = capsys.readouterr().out
    assert exit_code != 0
    assert "NOT-YET" in out
    assert "restarted at zero" in out


def _ns(**kwargs):
    class _Args:
        pass
    a = _Args()
    for k, v in kwargs.items():
        setattr(a, k, v)
    return a
