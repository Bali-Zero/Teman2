#!/usr/bin/env python3
"""Guilt-and-innocence suite for scripts/session_declaration.py.

Hermetic: no ssh, no network, no real process spawning, no wall-clock waits.
Every time is injected; every liveness answer is injected or comes from a pid
this test itself owns.

WHY THE INNOCENCE HALF IS THE IMPORTANT HALF HERE. The verdict this module
replaces (DECLARED-SPAN-UNMET, PR #4646) was not wrong because it missed
things — it was wrong because it ACCUSED ten healthy healer ticks out of ten.
So the shapes that must never be flagged are pinned first, with the real
measured numbers (cap 3300s, cadence 14400s, an 11-minute tick), not with
constants read back out of the module under test: a test that derives its
expectation from its subject agrees by construction and proves nothing.
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_MODULE_PATH = os.path.join(os.path.dirname(_HERE), "session_declaration.py")


def _load():
    spec = importlib.util.spec_from_file_location("session_declaration", _MODULE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sd = _load()

# The real healer numbers, written out literally on purpose (see docstring).
HEALER_CAP_SEC = 3300      # MAX_WALL_S in infra/healer/healer-run.sh
HEALER_CADENCE_SEC = 14400 # StartInterval in com.nuzantara.healer.4h.plist
HEALTHY_TICK_SEC = 671     # measured tick: spawn 15:12:12 -> exit=0 15:23:16
T0 = 1_000_000.0


class StoreCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._prev = os.environ.get("SESSION_DECLARATION_DIR")
        os.environ["SESSION_DECLARATION_DIR"] = self._tmp.name

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("SESSION_DECLARATION_DIR", None)
        else:
            os.environ["SESSION_DECLARATION_DIR"] = self._prev
        self._tmp.cleanup()

    def open_run(self, spawner="healer-run.sh", cap=HEALER_CAP_SEC, cadence=None, now=T0):
        return sd.open_declaration(
            spawner, cap_sec=cap, cadence_sec=cadence, pid=os.getpid(), now=now
        )


# ------------------------------------------------------------------ INNOCENCE

class TestInnocence(StoreCase):
    """Shapes that must NEVER be flagged. These encode the 10/10 false positives."""

    def test_the_exact_shape_that_produced_ten_false_positives(self):
        # A healer tick: 11 minutes of real work, a 55-minute cap, a 4-hour
        # cadence. The retired detector called this DEAD-BUT-DECLARED-LONG.
        d = self.open_run(cadence=HEALER_CADENCE_SEC)
        sd.close_declaration(d["run_id"], "completed", 0, now=T0 + HEALTHY_TICK_SEC)
        stored = sd.read_all()[0][0]
        # Still CLOSED an arbitrarily long time later — closing is permanent.
        self.assertEqual(sd.classify(stored, T0 + 10_000_000), sd.CLOSED)

    def test_a_closed_run_is_never_reopened_by_the_passage_of_time(self):
        d = self.open_run()
        sd.close_declaration(d["run_id"], "completed", 0, now=T0 + 5)
        stored = sd.read_all()[0][0]
        for offset in (T0 + 10, T0 + HEALER_CAP_SEC * 100, T0 + 10**9):
            self.assertEqual(sd.classify(stored, offset, alive=False), sd.CLOSED)

    def test_run_still_inside_its_own_cap_is_open_not_abandoned(self):
        d = self.open_run()
        # Deliberately assert with the runner DEAD: inside the cap, liveness
        # must not even be consulted, or a slow-starting child would be accused.
        self.assertEqual(sd.classify(d, T0 + HEALER_CAP_SEC - 1, alive=False), sd.OPEN)

    def test_just_past_the_cap_but_alive_is_open_not_hung(self):
        # The wrapper is shutting down. Naming that a hang would be the same
        # impatience that produced the retired detector's false positives.
        d = self.open_run()
        self.assertEqual(sd.classify(d, T0 + HEALER_CAP_SEC + 60, alive=True), sd.OPEN)

    def test_a_hang_is_never_reported_as_an_abandonment(self):
        # Different disease, different cure: abandonment means nobody is there,
        # a hang means somebody is stuck. Folding them loses which one it is.
        d = self.open_run()
        far = T0 + HEALER_CAP_SEC + sd.DEFAULT_HUNG_MARGIN_SEC + 1
        self.assertEqual(sd.classify(d, far, alive=True), sd.HUNG)
        self.assertEqual(sd.classify(d, far, alive=False), sd.ABANDONED)

    def test_an_abandonment_stops_driving_the_alarm_after_the_window(self):
        # Without this, ONE dead run keeps the healer permanently non-idle and
        # spawns a paid LLM session every 4h forever over an already-reported
        # fact. The record stays on disk; it just stops being actionable.
        d = self.open_run()
        fresh = T0 + HEALER_CAP_SEC + sd.DEFAULT_GRACE_SEC + 1
        stale = T0 + sd.DEFAULT_REPORT_WINDOW_SEC + 1
        self.assertEqual(sd.classify(d, fresh, alive=False), sd.ABANDONED)
        self.assertEqual(sd.classify(d, stale, alive=False), sd.ABANDONED_STALE)

    def test_scan_never_spawns_ps_for_records_that_cannot_need_it(self):
        # A CLOSED record and one still inside its cap must not cost a probe.
        calls = []
        self.open_run(cap=10**6)                      # inside cap
        c = self.open_run(cap=10)
        sd.close_declaration(c["run_id"], "completed", 0, now=T0 + 1)
        sd.scan(now=T0 + 100, alive_fn=lambda d: calls.append(d) or False)
        self.assertEqual(calls, [], "liveness must be resolved lazily, never eagerly")

    def test_hung_is_actionable_and_moves_the_exit_code(self):
        self.open_run(cap=10)
        rep = sd.scan(now=T0 + 10 + sd.DEFAULT_HUNG_MARGIN_SEC + 1, alive_fn=lambda _d: True)
        self.assertEqual(rep["summary"]["hung"], 1)
        self.assertEqual(rep["summary"]["abandoned"], 0)

    def test_a_run_with_no_open_timestamp_is_never_accused(self):
        # Cannot be aged, therefore cannot be proven abandoned. Never guess.
        broken = {"run_id": "x", "spawner": "y", "closed_at": None}
        self.assertEqual(sd.classify(broken, T0 + 10**9, alive=False), sd.OPEN)

    def test_grace_window_covers_the_watchdog_stamp(self):
        # The wrapper stamps AFTER its cap elapses in the kill path; the grace
        # exists so that ordinary sequence is not read as an abandonment.
        d = self.open_run()
        just_past_cap = T0 + HEALER_CAP_SEC + 1
        self.assertEqual(sd.classify(d, just_past_cap, alive=False), sd.OPEN)


# ---------------------------------------------------------------------- GUILT

class TestGuilt(StoreCase):
    def test_open_past_cap_with_dead_runner_is_abandoned(self):
        d = self.open_run()
        past = T0 + HEALER_CAP_SEC + sd.DEFAULT_GRACE_SEC + 1
        self.assertEqual(sd.classify(d, past, alive=False), sd.ABANDONED)

    def test_the_build_lane_class_exit_zero_having_done_nothing(self):
        # A spawned tool that returns 0 without doing the work never stamps.
        # Measured 2026-08-23: codex exited 0 with zero files written.
        d = self.open_run(spawner="codex-builder", cap=60)
        self.assertEqual(
            sd.classify(d, T0 + 60 + sd.DEFAULT_GRACE_SEC + 1, alive=False), sd.ABANDONED
        )

    def test_scan_reports_and_names_the_spawner(self):
        d = self.open_run(spawner="wr3-supervisor", cap=10)
        rep = sd.scan(now=T0 + 10 + sd.DEFAULT_GRACE_SEC + 1, alive_fn=lambda _d: False)
        self.assertEqual(rep["summary"]["abandoned"], 1)
        self.assertEqual(rep["summary"]["abandoned_spawners"], ["wr3-supervisor"])
        self.assertEqual(rep["rows"][0]["run_id"], d["run_id"])

    def test_abandoned_rows_sort_first(self):
        self.open_run(spawner="zzz-healthy", cap=10**6)
        self.open_run(spawner="aaa-dead", cap=1)
        rep = sd.scan(now=T0 + 10**5, alive_fn=lambda _d: False)
        self.assertEqual(rep["rows"][0]["state"], sd.ABANDONED)
        self.assertEqual(rep["rows"][0]["spawner"], "aaa-dead")


# ------------------------------------------------------------- PID IDENTITY

class TestPidIdentity(StoreCase):
    def test_a_recycled_pid_cannot_resurrect_a_dead_run(self):
        # Same pid, different start time: the process at that pid today is NOT
        # the one that opened this declaration. Must read as dead.
        d = self.open_run()
        d["pid_start"] = "Mon Jan  1 00:00:00 1990"
        self.assertFalse(sd.runner_alive(d))

    def test_the_live_process_that_opened_it_reads_alive(self):
        # This test's own pid, with the start time the module itself recorded.
        d = self.open_run()
        self.assertTrue(sd.runner_alive(d))

    def test_a_missing_pid_reads_dead_not_alive(self):
        # Unverifiable must not be silently treated as healthy.
        for bad in ({}, {"pid": None}, {"pid": 0}, {"pid": -1}, {"pid": "x"}):
            self.assertFalse(sd.runner_alive(bad), bad)

    def test_declaration_without_start_stamp_degrades_to_bare_existence(self):
        # Declared narrowing: can only MISS an abandonment, never invent one.
        d = self.open_run()
        d.pop("pid_start", None)
        self.assertTrue(sd.runner_alive(d))


# ---------------------------------------------------------------- ROBUSTNESS

class TestRobustness(StoreCase):
    def test_close_is_idempotent_and_the_first_outcome_wins(self):
        # The healer closes explicitly AND from an EXIT trap. The precise
        # outcome must survive the generic one that follows it.
        d = self.open_run(cap=10)
        sd.close_declaration(d["run_id"], "killed-by-watchdog", 143, now=T0 + 1)
        again = sd.close_declaration(d["run_id"], "failed", 1, now=T0 + 2)
        self.assertEqual(again["outcome"], "killed-by-watchdog")
        self.assertEqual(again["exit_code"], 143)

    def test_unknown_outcome_is_refused(self):
        d = self.open_run()
        with self.assertRaises(ValueError):
            sd.close_declaration(d["run_id"], "probably-fine")

    def test_malformed_file_is_surfaced_not_swallowed(self):
        # "the store had a file I could not parse" and "the store was empty"
        # must not produce the same clean-looking answer.
        self.open_run()
        with open(os.path.join(os.environ["SESSION_DECLARATION_DIR"], "torn.json"), "w") as fh:
            fh.write('{"run_id": "hal')
        decls, malformed, readable = sd.read_all()
        self.assertEqual(len(decls), 1)
        self.assertEqual(malformed, ["torn.json"])
        self.assertTrue(readable)

    def test_a_json_file_that_is_not_a_declaration_is_malformed_not_a_row(self):
        with open(os.path.join(os.environ["SESSION_DECLARATION_DIR"], "other.json"), "w") as fh:
            json.dump({"hello": "world"}, fh)
        decls, malformed, _ = sd.read_all()
        self.assertEqual(decls, [])
        self.assertEqual(malformed, ["other.json"])

    def test_absent_store_is_empty_not_blind(self):
        os.environ["SESSION_DECLARATION_DIR"] = os.path.join(self._tmp.name, "never-created")
        decls, malformed, readable = sd.read_all()
        self.assertEqual((decls, malformed), ([], []))
        self.assertTrue(readable, "an absent store is a legitimate empty state")

    def test_tmp_files_from_a_concurrent_write_are_not_read_as_rows(self):
        self.open_run()
        with open(os.path.join(os.environ["SESSION_DECLARATION_DIR"], "x.json.tmp.999"), "w") as fh:
            fh.write("garbage")
        decls, malformed, _ = sd.read_all()
        self.assertEqual(len(decls), 1)
        self.assertEqual(malformed, [], "a .tmp partial write must be ignored, not alarmed on")

    def test_open_refuses_a_declaration_that_could_never_become_abandoned(self):
        with self.assertRaises(ValueError):
            sd.open_declaration("x", cap_sec=0)
        with self.assertRaises(ValueError):
            sd.open_declaration("", cap_sec=10)


# ------------------------------------------------- THE ORIGINAL DEFECT ITSELF

class TestCapAndCadenceNeverCollapse(StoreCase):
    """The bug was one number doing two jobs. These pin them apart."""

    def test_cap_and_cadence_are_separate_persisted_fields(self):
        d = self.open_run(cap=HEALER_CAP_SEC, cadence=HEALER_CADENCE_SEC)
        stored = sd.read_all()[0][0]
        self.assertEqual(stored["cap_sec"], HEALER_CAP_SEC)
        self.assertEqual(stored["cadence_sec"], HEALER_CADENCE_SEC)
        self.assertNotEqual(stored["cap_sec"], stored["cadence_sec"])

    def test_abandonment_is_judged_against_the_cap_never_the_cadence(self):
        # At cadence-scale age the run would look "short" against 14400s, but
        # what matters is only whether it outlived its own 3300s cap.
        d = self.open_run(cap=HEALER_CAP_SEC, cadence=HEALER_CADENCE_SEC)
        between = T0 + HEALER_CAP_SEC + sd.DEFAULT_GRACE_SEC + 1
        self.assertLess(between - T0, HEALER_CADENCE_SEC, "fixture must sit between cap and cadence")
        self.assertEqual(sd.classify(d, between, alive=False), sd.ABANDONED)

    def test_a_declaration_with_no_cadence_still_works(self):
        # Not every spawner is a cron; cadence is optional metadata.
        d = self.open_run(cadence=None)
        self.assertIsNone(sd.read_all()[0][0]["cadence_sec"])
        self.assertEqual(sd.classify(d, T0 + 1, alive=False), sd.OPEN)


# ------------------------------------------------------------ CLI / CONTRACT

class TestCli(StoreCase):
    def test_exit_codes_are_the_contract_the_healer_routes_on(self):
        # 0 clean, 1 abandoned, 2 blind. The receptor branches on exactly these.
        self.assertEqual(sd.main(["scan", "--json"]), 0)
        self.open_run(cap=1)
        import time as _t
        # Age it past cap+grace by rewriting opened_at rather than sleeping.
        path = os.path.join(os.environ["SESSION_DECLARATION_DIR"], os.listdir(os.environ["SESSION_DECLARATION_DIR"])[0])
        with open(path) as fh:
            obj = json.load(fh)
        obj["opened_at"] = _t.time() - (1 + sd.DEFAULT_GRACE_SEC + 60)
        obj["pid_start"] = "Mon Jan  1 00:00:00 1990"  # force dead
        with open(path, "w") as fh:
            json.dump(obj, fh)
        self.assertEqual(sd.main(["scan", "--json"]), 1)

    def test_blind_store_exits_two_and_is_not_reported_as_clean(self):
        rep = {"rows": [], "summary": {"store_readable": False, "abandoned": 0,
                                       "open": 0, "closed": 0, "malformed": [], "total": 0}}
        rendered = sd.render_table(rep)
        self.assertIn("BLIND", rendered)
        self.assertNotIn("0 abandoned", rendered.split("\n")[0])

    def test_open_prints_only_the_run_id_so_shell_capture_is_safe(self):
        # The wrapper does RUN_ID=$(... open ...). Any extra chatter on stdout
        # would silently corrupt the id and orphan every later close.
        from io import StringIO
        buf, real = StringIO(), sys.stdout
        sys.stdout = buf
        try:
            rc = sd.main(["open", "--spawner", "t", "--cap-sec", "10"])
        finally:
            sys.stdout = real
        self.assertEqual(rc, 0)
        out = buf.getvalue().strip()
        self.assertEqual(len(out.split()), 1, f"stdout must be exactly the run_id, got {out!r}")
        self.assertEqual(len(out), 36, "run_id must be a bare uuid4")

    def test_closing_an_unknown_run_warns_and_does_not_raise(self):
        # Called from an EXIT trap: it must never take the wrapper down with it.
        self.assertEqual(sd.main(["close", "--run-id", "no-such-run", "--outcome", "failed"]), 1)

    def test_module_selftest_passes(self):
        self.assertEqual(sd._selftest(), 0)


class TestCrossFamilyReviewFindings(StoreCase):
    """Every one of these pins a defect a cross-family refuter found in the
    FIRST cured version — i.e. one my own tests had already passed over."""

    def test_prune_never_deletes_a_record_that_is_not_provably_dead(self):
        # The bug: `not closed and age > 30d -> delete` also deleted a LIVE
        # long-running job and every unread abandonment, while the docstring
        # promised open records are never pruned. Code contradicted its own doc.
        d = self.open_run(cap=10**7, now=T0)          # cap longer than retention
        very_old = T0 + sd.RETAIN_ABANDONED_SEC + 10_000
        removed = sd.prune(now=very_old)
        self.assertEqual(removed, 0, "a still-live long run must survive retention")
        self.assertEqual(len(sd.read_all()[0]), 1)

    def test_prune_does_remove_a_closed_record_past_retention(self):
        d = self.open_run(cap=10)
        sd.close_declaration(d["run_id"], "completed", 0, now=T0 + 1)
        self.assertEqual(sd.prune(now=T0 + sd.RETAIN_CLOSED_SEC + 1), 1)
        self.assertEqual(sd.read_all()[0], [])

    def test_scan_for_pid_answers_about_that_run_not_the_whole_store(self):
        # The bug: the lock check counted hung runs of EVERY spawner, then
        # blamed "the previous healer run" — accusing a healthy run by name.
        mine = self.open_run(spawner="healer-run.sh", cap=10**6)   # healthy, inside cap
        other = sd.open_declaration("other-organ", cap_sec=10, pid=999_999, now=T0)
        rep = sd.scan(now=T0 + 10**5, alive_fn=lambda _d: True, for_pid=mine["pid"])
        self.assertEqual(len(rep["rows"]), 1)
        self.assertEqual(rep["rows"][0]["spawner"], "healer-run.sh")
        self.assertEqual(rep["summary"]["hung"], 0, "my healthy run must not inherit another's hang")

    def test_a_record_we_cannot_parse_makes_the_scan_blind_not_clean(self):
        # It was reported in summary.malformed and consumed by nothing — a
        # cosmetic field. An unparseable declaration is a run we cannot
        # classify, which is indistinguishable from an abandonment we missed.
        self.open_run()
        with open(os.path.join(os.environ["SESSION_DECLARATION_DIR"], "torn.json"), "w") as fh:
            fh.write("{oops")
        self.assertEqual(sd.main(["scan", "--json"]), 2)

    def test_row_carries_the_pid_so_a_consumer_can_correlate_a_lock(self):
        d = self.open_run()
        rep = sd.scan(now=T0 + 1, alive_fn=lambda _d: True)
        self.assertEqual(rep["rows"][0]["pid"], d["pid"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
