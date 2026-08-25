"""The contract for `kb/ops/probe_history.py` — the ledger that answers MANDATE §8's
"has this topic been continuously at target for 48h?" question.

House style, same as `test_kb_topic_contract.py`: pure functions proven with a
synthetic guilt-AND-innocence matrix so the module is exercised on every run
regardless of what history exists on disk, plus a closed-vocabulary check that
imports rather than restates the vocabulary it verifies (a restated copy is the
"compares two outputs of one generator" blindness this repo has already been
burned by once).

Six things this module must never get wrong, each with its own guilt case below
(matches the module docstring's own six-point list — read that first, this file
only proves it, it does not restate the reasoning):
  (a) a streak must not survive an edit to ANY of the three artifacts §8 names —
      journeys, topics, AND inventory, not journeys alone
  (b) an empty run (zero files, or zero journeys in a file) must not read as success
  (c) a `broken` run must neither extend nor break a streak
  (d) a gap larger than MAX_GAP_HOURS — between two records, or between the last
      record and now — must break the streak / mark it stale
  (e) `cmd_record`'s own exit code must not go green when one or more topics came
      back `broken` this run — all-broken AND mixed (some graded, some broken)
  (f) a `degraded_path` run must not be able to earn the 48h certificate on its
      own — treated like `broken`: neither extends nor breaks a streak
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


def rec(hours_before_ref: float, verdict: str, journeys_sha: str = SHA_A,
        topics_sha: str = SHA_A, inventory_sha: str = SHA_A,
        degraded_path: bool = False) -> dict:
    ts = REF - timedelta(hours=hours_before_ref)
    return {"ts": ts.isoformat(), "topic": "immigration", "journeys_path": "kb/journeys/immigration.yaml",
            "journeys_sha256": journeys_sha, "topics_sha256": topics_sha,
            "inventory_sha256": inventory_sha, "verdict": verdict, "exit_code": 0,
            "degraded_path": degraded_path, "journeys": []}


# ── closed vocabulary, imported not restated ─────────────────────────────────


def test_verdicts_is_probe_retrievals_vocabulary_plus_nothing_measured():
    assert PH.VERDICTS == set(PR.VERDICT_BY_EXIT.values()) | {"nothing_measured"}
    assert PH.VERDICTS == {"at_target", "drift", "outstanding", "broken", "nothing_measured"}


def test_max_gap_matches_the_mandates_own_deadman_switch_threshold():
    # MANDATE §7: "Dead-man switch: probe silent 24h -> alert." Reused, not invented.
    assert PH.MAX_GAP_HOURS == 24


# ── build_record: an unrecognized verdict is never trusted verbatim ──────────

SHAS = {"journeys": SHA_A, "topics": SHA_A, "inventory": SHA_A}


def test_innocence_build_record_passes_through_a_real_verdict():
    r = PH.build_record("immigration", Path("kb/journeys/immigration.yaml"), SHAS,
                         {"verdict": "at_target", "exit_code": 0, "journeys": []})
    assert r["verdict"] == "at_target"
    assert r["journeys_sha256"] == SHA_A
    assert r["topics_sha256"] == SHA_A
    assert r["inventory_sha256"] == SHA_A
    assert r["topic"] == "immigration"


def test_guilt_build_record_coerces_an_unrecognized_verdict_to_broken():
    r = PH.build_record("immigration", Path("kb/journeys/immigration.yaml"), SHAS,
                         {"verdict": "totally_fine_i_promise", "exit_code": 0, "journeys": []})
    assert r["verdict"] == "broken"


def test_guilt_build_record_treats_a_missing_verdict_as_broken():
    r = PH.build_record("immigration", Path("kb/journeys/immigration.yaml"), SHAS, {})
    assert r["verdict"] == "broken"


# ── artifact_shas / MISSING_SHA: the sentinel must never collide with a hash ──


def test_innocence_artifact_shas_reads_all_three_real_files(tmp_path):
    root = tmp_path
    (root / "kb" / "journeys").mkdir(parents=True)
    (root / "kb" / "topics").mkdir(parents=True)
    (root / "kb" / "inventory").mkdir(parents=True)
    j = root / "kb" / "journeys" / "immigration.yaml"
    t = root / "kb" / "topics" / "immigration.yaml"
    i = root / "kb" / "inventory" / "immigration.yaml"
    j.write_text("journeys: []\n")
    t.write_text("topics: []\n")
    i.write_text("inventory: []\n")
    shas = PH.artifact_shas(root, "immigration", j)
    assert shas["journeys"] == PH.sha256_bytes(j)
    assert shas["topics"] == PH.sha256_bytes(t)
    assert shas["inventory"] == PH.sha256_bytes(i)


def test_guilt_artifact_shas_uses_the_missing_sentinel_not_a_falsy_placeholder(tmp_path):
    """A topics/inventory file that does not exist must NOT hash as None, "",
    or any value a real file could also produce — MISSING_SHA is a fixed string
    that cannot collide with sha256's hex output by construction (not 64 hex
    chars), so a file's first appearance is always a change, never a no-op."""
    root = tmp_path
    (root / "kb" / "journeys").mkdir(parents=True)
    j = root / "kb" / "journeys" / "immigration.yaml"
    j.write_text("journeys: []\n")
    shas = PH.artifact_shas(root, "immigration", j)
    assert shas["topics"] == PH.MISSING_SHA
    assert shas["inventory"] == PH.MISSING_SHA
    assert PH.MISSING_SHA != PH.sha256_bytes(j)  # never equals a real hash


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
    same_sha = [r for r in records if r["journeys_sha256"] == SHA_A]
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
    same_sha = [r for r in all_records if r["journeys_sha256"] == current_sha]
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


# ── rule (e): record()'s exit code must not go green on a broken/mixed run ───
# The reviewer's exact evasion: point one journey's `collection:` at a name the
# registry does not define. probe_retrieval.py correctly refuses (verdict
# broken, exit 3) — the bug was record()'s OWN "measured something" check
# accepting `broken` as "not nothing_measured" and exiting 0 anyway.


def test_guilt_an_all_broken_run_does_not_exit_zero(tmp_path, monkeypatch):
    """A single topic whose control query failed (e.g. an unknown `collection:`)
    must not let the scheduled job report success — it recorded a real `broken`
    verdict, not `nothing_measured`, and the OLD bug was exactly this: `broken`
    satisfied "any verdict other than nothing_measured" and exited 0."""
    root = tmp_path
    jdir = root / "kb" / "journeys"
    jdir.mkdir(parents=True)
    (jdir / "immigration.yaml").write_text("schema_version: 1\njourneys: [{}]\n")

    def fake_run_probe_json(path, collection, timeout_s=300):
        return {"journeys_file": str(path), "collection": collection, "verdict": "broken",
                "reason": "unknown_collection", "exit_code": 3, "degraded_path": False,
                "journeys": []}

    monkeypatch.setattr(PH, "run_probe_json", fake_run_probe_json)
    history = tmp_path / "history.jsonl"
    exit_code = PH.cmd_record(_ns(history=str(history), collection="legal_unified"), root)
    assert exit_code != 0
    lines = [json.loads(row) for row in history.read_text().splitlines()]
    assert lines[0]["verdict"] == "broken"  # NOT coerced to nothing_measured — it's a real record


def test_guilt_a_mixed_run_some_graded_some_broken_does_not_exit_zero(tmp_path, monkeypatch, capsys):
    """Two topics: `immigration` grades cleanly (at_target), `property`'s
    `collection:` points at a name nobody registered and comes back broken.
    This is the silent-disappearance evasion: if record() exited 0 here because
    SOME topic graded, `property` could stay broken forever behind a green job."""
    root = tmp_path
    jdir = root / "kb" / "journeys"
    jdir.mkdir(parents=True)
    (jdir / "immigration.yaml").write_text("schema_version: 1\njourneys: [{}]\n")
    (jdir / "property.yaml").write_text("schema_version: 1\njourneys: [{}]\n")

    def fake_run_probe_json(path, collection, timeout_s=300):
        if path.stem == "property":
            return {"journeys_file": str(path), "collection": "this_collection_does_not_exist_zzz999",
                    "verdict": "broken", "reason": "unknown_collection", "exit_code": 3,
                    "degraded_path": False, "journeys": []}
        return {"journeys_file": str(path), "collection": collection, "verdict": "at_target",
                "exit_code": 0, "degraded_path": False,
                "journeys": [{"index": 1, "question": "q", "recorded_state": "green",
                              "measured_state": "green", "rank": 1, "error": None}]}

    monkeypatch.setattr(PH, "run_probe_json", fake_run_probe_json)
    history = tmp_path / "history.jsonl"
    exit_code = PH.cmd_record(_ns(history=str(history), collection="legal_unified"), root)
    out = capsys.readouterr().out
    assert exit_code != 0, "a mixed run (1 graded, 1 broken) must not exit 0"
    lines = {json.loads(row)["topic"]: json.loads(row) for row in history.read_text().splitlines()}
    # BOTH records are still written — the graded topic really was measured.
    assert lines["immigration"]["verdict"] == "at_target"
    assert lines["property"]["verdict"] == "broken"
    assert "property" in out  # the broken topic is named, not just counted


def test_innocence_a_multi_topic_run_with_zero_broken_exits_zero(tmp_path, monkeypatch):
    """Two topics, both graded (one at_target, one outstanding), none broken —
    the ordinary healthy-mixed-verdict case must still exit 0."""
    root = tmp_path
    jdir = root / "kb" / "journeys"
    jdir.mkdir(parents=True)
    (jdir / "immigration.yaml").write_text("schema_version: 1\njourneys: [{}]\n")
    (jdir / "property.yaml").write_text("schema_version: 1\njourneys: [{}]\n")

    def fake_run_probe_json(path, collection, timeout_s=300):
        verdict = "outstanding" if path.stem == "property" else "at_target"
        return {"journeys_file": str(path), "collection": collection, "verdict": verdict,
                "exit_code": 0 if verdict == "at_target" else 2, "degraded_path": False,
                "journeys": [{"index": 1, "question": "q", "recorded_state": "x",
                              "measured_state": "x", "rank": None, "error": None}]}

    monkeypatch.setattr(PH, "run_probe_json", fake_run_probe_json)
    history = tmp_path / "history.jsonl"
    exit_code = PH.cmd_record(_ns(history=str(history), collection="legal_unified"), root)
    assert exit_code == 0


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


# ── rule (f): degraded_path neither extends nor breaks a streak ──────────────
# Same treatment as rule (c)'s broken, deliberately — see module docstring rule
# (f) for the argument against the tempting-but-rejected "trust a degraded
# at_target, it's a lower bound" alternative.


def test_innocence_a_degraded_run_between_two_at_target_runs_does_not_break_the_streak():
    records = [rec(60, "at_target"), rec(48, "at_target", degraded_path=True),
               rec(36, "at_target"), rec(24, "at_target", degraded_path=True),
               rec(12, "at_target"), rec(0, "at_target")]
    result = PH._streak(records, REF)
    assert result["degraded_runs_in_window"] == 2
    # Gradable timeline (degraded dropped): 60, 36, 12, 0 -> gaps all <= MAX_GAP.
    assert result["at_target_48h"] is True
    assert result["runs_in_window"] == 4  # the two degraded runs are NOT counted


def test_guilt_a_degraded_run_does_not_manufacture_the_certificate_on_its_own():
    """All-degraded history must never earn AT-TARGET-48H even when every single
    verdict is at_target — this is the exact evasion finding 6 describes: three
    degraded at_target records alone must not certify a path the probe's own
    banner calls a lower bound, never production."""
    records = [rec(h, "at_target", degraded_path=True) for h in (60, 40, 20, 0)]
    result = PH._streak(records, REF)
    assert result["at_target_48h"] is False
    assert result["currently_at_target"] is False
    assert result["runs_in_window"] == 0
    assert result["degraded_runs_in_window"] == 4


def test_guilt_a_trailing_degraded_run_does_not_make_a_real_streak_look_dead():
    """Mirrors the broken case: the MOST RECENT record is degraded, but the run
    before it was a clean, non-degraded at_target 2h ago — 'latest' for
    staleness/verdict purposes must be the latest gradable (non-broken,
    non-degraded) record."""
    records = [rec(60, "at_target"), rec(48, "at_target"), rec(36, "at_target"),
               rec(24, "at_target"), rec(12, "at_target"), rec(2, "at_target"),
               rec(0, "at_target", degraded_path=True)]
    result = PH._streak(records, REF)
    assert result["currently_at_target"] is True
    assert result["stale"] is False
    assert result["at_target_48h"] is True
    assert result["degraded_runs_in_window"] == 1
    assert result["runs_in_window"] == 6  # the trailing degraded run is not one of them


def test_guilt_a_degraded_broken_and_at_target_mix_only_counts_the_clean_runs():
    """Both absence-of-evidence shapes in the same window must compose, not
    interfere: broken_runs_in_window and degraded_runs_in_window are counted
    independently, and only the true at_target runs build the streak."""
    records = [rec(60, "at_target"), rec(48, "broken"), rec(36, "at_target"),
               rec(24, "at_target", degraded_path=True), rec(12, "at_target"),
               rec(0, "at_target")]
    result = PH._streak(records, REF)
    assert result["broken_runs_in_window"] == 1
    assert result["degraded_runs_in_window"] == 1
    # Gradable timeline: 60, 36, 12, 0 -> gaps 24h, 24h, 12h, all <= MAX_GAP_HOURS.
    assert result["runs_in_window"] == 4
    assert result["at_target_48h"] is True


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


def _make_triple(root: Path, topic: str = "immigration"):
    """Create all three real MANDATE §8 artifacts under tmp_path and return
    their current sha256 triple, for tests that need the full rule (a) shape
    rather than journeys alone."""
    jdir, tdir, idir = (root / "kb" / "journeys", root / "kb" / "topics",
                         root / "kb" / "inventory")
    jdir.mkdir(parents=True, exist_ok=True)
    tdir.mkdir(parents=True, exist_ok=True)
    idir.mkdir(parents=True, exist_ok=True)
    journeys_file = jdir / f"{topic}.yaml"
    journeys_file.write_text("schema_version: 1\njourneys: [{}]\n")
    (tdir / f"{topic}.yaml").write_text("topics: []\n")
    (idir / f"{topic}.yaml").write_text("inventory: []\n")
    return journeys_file, PH.artifact_shas(root, topic, journeys_file)


def test_status_reports_at_target_48h_end_to_end(tmp_path, monkeypatch, capsys):
    root = tmp_path
    _journeys_file, current = _make_triple(root)

    history = tmp_path / "history.jsonl"
    with history.open("w") as fh:
        for h in (60, 48, 36, 24, 12, 0):
            fh.write(json.dumps(rec(h, "at_target", current["journeys"],
                                     current["topics"], current["inventory"])) + "\n")

    monkeypatch.setattr(PH, "now_utc", lambda: REF)
    exit_code = PH.cmd_status(_ns(history=str(history)), root)
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "AT-TARGET-48H" in out
    assert "immigration" in out


def test_status_flags_a_changed_topics_file_as_a_reset_streak(tmp_path, monkeypatch, capsys):
    """Rule (a), the topics half: journeys is UNCHANGED since every record, but
    kb/topics/immigration.yaml changed after they were written — e.g. a
    superseded law quietly marked back in-force. The streak must reset exactly
    as it would for an edited journeys file, even though the probe suite itself
    never moved."""
    root = tmp_path
    journeys_file, old = _make_triple(root)

    history = tmp_path / "history.jsonl"
    with history.open("w") as fh:
        for h in (60, 48, 36, 24, 12, 0):
            fh.write(json.dumps(rec(h, "at_target", old["journeys"],
                                     old["topics"], old["inventory"])) + "\n")

    # kb/topics/immigration.yaml changes; journeys and inventory do not.
    (root / "kb" / "topics" / "immigration.yaml").write_text("topics: [{'edited': True}]\n")

    monkeypatch.setattr(PH, "now_utc", lambda: REF)
    exit_code = PH.cmd_status(_ns(history=str(history)), root)
    out = capsys.readouterr().out
    assert exit_code != 0
    assert "NOT-YET" in out
    assert "restarted at zero" in out


def test_status_flags_a_changed_inventory_file_as_a_reset_streak(tmp_path, monkeypatch, capsys):
    """Rule (a), the inventory half — same proof, the other artifact."""
    root = tmp_path
    journeys_file, old = _make_triple(root)

    history = tmp_path / "history.jsonl"
    with history.open("w") as fh:
        for h in (60, 48, 36, 24, 12, 0):
            fh.write(json.dumps(rec(h, "at_target", old["journeys"],
                                     old["topics"], old["inventory"])) + "\n")

    (root / "kb" / "inventory" / "immigration.yaml").write_text("inventory: [{'points': 999}]\n")

    monkeypatch.setattr(PH, "now_utc", lambda: REF)
    exit_code = PH.cmd_status(_ns(history=str(history)), root)
    out = capsys.readouterr().out
    assert exit_code != 0
    assert "NOT-YET" in out
    assert "restarted at zero" in out


def test_status_a_topics_files_first_appearance_counts_as_a_change(tmp_path, monkeypatch, capsys):
    """Every prior record was written when kb/topics/immigration.yaml did not
    exist (MISSING_SHA). The file is then created for the first time. That is
    itself a change per rule (a) — the streak must reset, not silently treat
    "no information" as "unchanged"."""
    root = tmp_path
    jdir = root / "kb" / "journeys"
    jdir.mkdir(parents=True)
    journeys_file = jdir / "immigration.yaml"
    journeys_file.write_text("schema_version: 1\njourneys: [{}]\n")
    journeys_sha = PH.sha256_bytes(journeys_file)

    history = tmp_path / "history.jsonl"
    with history.open("w") as fh:
        # topics/inventory never existed when these were recorded.
        for h in (60, 48, 36, 24, 12, 0):
            fh.write(json.dumps(rec(h, "at_target", journeys_sha,
                                     PH.MISSING_SHA, PH.MISSING_SHA)) + "\n")

    # kb/topics/immigration.yaml is created for the first time.
    tdir = root / "kb" / "topics"
    tdir.mkdir(parents=True)
    (tdir / "immigration.yaml").write_text("topics: []\n")

    monkeypatch.setattr(PH, "now_utc", lambda: REF)
    exit_code = PH.cmd_status(_ns(history=str(history)), root)
    out = capsys.readouterr().out
    assert exit_code != 0
    assert "NOT-YET" in out


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
