#!/usr/bin/env python3
"""Guilt + innocence corpus for shard_tests.py (the `Backend Shard N` partitioner).

Hermetic: every test builds a small synthetic tree under a temp directory
instead of asserting counts against the live 1425-module repo corpus, which
would drift the moment anyone adds a test file.

The INNOCENCE half proves a sound partition is accepted. The GUILT half is the
load-bearing one: the whole reason this guard exists is that a sharded suite
whose chunks do not tile the corpus looks EXACTLY like a healthy green run
(cicatrix-superscar #2). Each defect below is a way that can happen, and each
must be caught.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import shard_tests as st  # noqa: E402


def _tree(root: Path, rels):
    for rel in rels:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("def test_x():\n    assert True\n")


def _write_chunks(chunk_dir: Path, chunks):
    chunk_dir.mkdir(parents=True, exist_ok=True)
    for shard, files in chunks.items():
        (chunk_dir / ("chunk-%d.txt" % shard)).write_text(
            "".join(f + "\n" for f in files)
        )


class Enumeration(unittest.TestCase):
    def test_finds_only_test_modules_and_is_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _tree(
                root,
                [
                    "backend/tests/test_b.py",
                    "backend/tests/test_a.py",
                    "backend/tests/routers/legacy_test.py",
                    "backend/tests/conftest.py",  # not a test module
                    "backend/tests/helpers.py",  # not a test module
                    "backend/tests/data/test_fixture.json",  # not .py
                ],
            )
            found = st.enumerate_tests(["backend/tests/"], root)
            self.assertEqual(
                found,
                [
                    "backend/tests/routers/legacy_test.py",
                    "backend/tests/test_a.py",
                    "backend/tests/test_b.py",
                ],
            )

    def test_is_deterministic_across_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _tree(root, ["backend/tests/test_%02d.py" % i for i in range(40)])
            self.assertEqual(
                st.enumerate_tests(["backend/tests/"], root),
                st.enumerate_tests(["backend/tests/"], root),
            )

    def test_excluded_directory_is_never_enumerated(self):
        # GUILT: e2e modules must not reach a shard's explicit file list —
        # pytest's --ignore does not reliably suppress an explicitly named file.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _tree(
                root,
                ["backend/tests/test_a.py", "backend/tests/e2e/test_journey.py"],
            )
            found = st.enumerate_tests(["backend/tests/"], root)
            self.assertEqual(found, ["backend/tests/test_a.py"])

    def test_explicit_file_target_is_kept_verbatim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "apps" / "backend-rag"
            _tree(Path(tmp), ["scripts/bot/test_bot.py"])
            root.mkdir(parents=True, exist_ok=True)
            found = st.enumerate_tests(["../../scripts/bot/test_bot.py"], root)
            self.assertEqual(found, ["../../scripts/bot/test_bot.py"])

    def test_missing_target_is_loud_not_silent(self):
        # A vanished target must abort, never quietly shrink the corpus.
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                st.enumerate_tests(["backend/tests/"], Path(tmp))


class TargetResolution(unittest.TestCase):
    def test_unset_env_uses_full_corpus(self):
        self.assertEqual(st.resolve_targets({}), list(st.DEFAULT_TARGETS))

    def test_narrowing_requires_both_the_flag_and_a_selection(self):
        # Fail-open, exactly like the `changes` job: a broken impact map must
        # never be able to shrink what runs.
        self.assertEqual(
            st.resolve_targets({"IMPACT_RUN_ALL": "false", "IMPACT_SELECTED_TESTS": ""}),
            list(st.DEFAULT_TARGETS),
        )
        self.assertEqual(
            st.resolve_targets(
                {
                    "IMPACT_RUN_ALL": "true",
                    "IMPACT_SELECTED_TESTS": "apps/backend-rag/backend/tests/test_a.py",
                }
            ),
            list(st.DEFAULT_TARGETS),
        )
        self.assertEqual(
            st.resolve_targets(
                {"IMPACT_RUN_ALL": "banana", "IMPACT_SELECTED_TESTS": "x"}
            ),
            list(st.DEFAULT_TARGETS),
        )

    def test_scoped_selection_is_stripped_to_the_pytest_cwd(self):
        self.assertEqual(
            st.resolve_targets(
                {
                    "IMPACT_RUN_ALL": "false",
                    "IMPACT_SELECTED_TESTS": (
                        "apps/backend-rag/backend/tests/test_a.py\n"
                        "\n"
                        "scripts/bot/test_bot.py\n"
                    ),
                }
            ),
            # The out-of-prefix path must come back in the pytest cwd's frame
            # (`../../`), the same form DEFAULT_TARGETS uses. Passing it through
            # repo-root-relative — which an earlier cut of this test asserted —
            # makes enumerate_tests abort and every shard go red.
            ["backend/tests/test_a.py", "../../scripts/bot/test_bot.py"],
        )

    def test_an_out_of_prefix_selection_resolves_from_the_pytest_cwd(self):
        # GUILT for the false-red: the repo-root-relative form does not exist
        # from apps/backend-rag, so blessing it would bless an abort.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "apps" / "backend-rag"
            root.mkdir(parents=True, exist_ok=True)
            _tree(Path(tmp), ["scripts/bot/test_bot.py"])
            targets = st.resolve_targets(
                {
                    "IMPACT_RUN_ALL": "false",
                    "IMPACT_SELECTED_TESTS": "scripts/bot/test_bot.py",
                }
            )
            self.assertEqual(targets, ["../../scripts/bot/test_bot.py"])
            self.assertEqual(
                st.enumerate_tests(targets, root), ["../../scripts/bot/test_bot.py"]
            )
            with self.assertRaises(SystemExit):
                st.enumerate_tests(["scripts/bot/test_bot.py"], root)


class VanishedTargets(unittest.TestCase):
    """A target the base ref knew about and the head tree no longer has.

    GUILT for the default: the shards must ABORT, because for them a missing
    target is a real defect. INNOCENCE for the security pass: it must degrade
    loudly instead of turning every future rename of backend/tests/ permanently
    red.
    """

    def test_default_aborts_on_a_missing_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _tree(root, ["backend/tests/test_a.py"])
            with self.assertRaises(SystemExit):
                st.enumerate_tests(["backend/tests/", "gone/"], root)

    def test_tolerant_mode_drops_it_and_keeps_the_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _tree(root, ["backend/tests/test_a.py"])
            found = st.enumerate_tests(
                ["backend/tests/", "gone/"], root, tolerate_missing=True
            )
            self.assertEqual(found, ["backend/tests/test_a.py"])


class PartitionInnocence(unittest.TestCase):
    def test_chunks_tile_the_corpus_exactly(self):
        corpus = ["f%03d.py" % i for i in range(101)]
        chunks = [st.chunk_for(corpus, 3, s) for s in (1, 2, 3)]
        flat = [f for c in chunks for f in c]
        self.assertEqual(sorted(flat), sorted(corpus))
        self.assertEqual(len(flat), len(set(flat)))

    def test_sound_partition_reports_no_problems(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _tree(root, ["backend/tests/test_%02d.py" % i for i in range(10)])
            corpus = st.enumerate_tests(["backend/tests/"], root)
            chunk_dir = root / "chunks"
            _write_chunks(
                chunk_dir, {s: st.chunk_for(corpus, 3, s) for s in (1, 2, 3)}
            )
            self.assertEqual(st.verify(corpus, 3, chunk_dir), [])

    def test_corpus_smaller_than_shard_count_is_still_sound(self):
        # Scoped PR lane: 2 selected modules, 3 shards — shard 3 is legitimately
        # empty and that must not read as a dropped file.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _tree(root, ["backend/tests/test_a.py", "backend/tests/test_b.py"])
            corpus = st.enumerate_tests(["backend/tests/"], root)
            chunk_dir = root / "chunks"
            _write_chunks(
                chunk_dir, {s: st.chunk_for(corpus, 3, s) for s in (1, 2, 3)}
            )
            self.assertEqual(st.chunk_for(corpus, 3, 3), [])
            self.assertEqual(st.verify(corpus, 3, chunk_dir), [])


class PartitionGuilt(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _tree(self.root, ["backend/tests/test_%02d.py" % i for i in range(9)])
        self.corpus = st.enumerate_tests(["backend/tests/"], self.root)
        self.chunk_dir = self.root / "chunks"
        self.sound = {s: st.chunk_for(self.corpus, 3, s) for s in (1, 2, 3)}

    def tearDown(self):
        self._tmp.cleanup()

    def _problems(self, chunks):
        _write_chunks(self.chunk_dir, chunks)
        return st.verify(self.corpus, 3, self.chunk_dir)

    def test_a_dropped_module_is_caught(self):
        chunks = {s: list(v) for s, v in self.sound.items()}
        dropped = chunks[2].pop()
        problems = self._problems(chunks)
        self.assertTrue(problems)
        self.assertTrue(any("ran on NO shard" in p for p in problems), problems)
        self.assertTrue(any(dropped in p for p in problems), problems)

    def test_a_module_running_twice_is_caught(self):
        chunks = {s: list(v) for s, v in self.sound.items()}
        chunks[3].append(chunks[1][0])
        problems = self._problems(chunks)
        self.assertTrue(any("overlap" in p for p in problems), problems)

    def test_a_module_outside_the_corpus_is_caught(self):
        chunks = {s: list(v) for s, v in self.sound.items()}
        chunks[1].append("backend/tests/test_ghost.py")
        problems = self._problems(chunks)
        self.assertTrue(any("not in the corpus" in p for p in problems), problems)

    def test_a_shard_that_never_ran_is_caught(self):
        chunks = {s: list(v) for s, v in self.sound.items()}
        del chunks[2]
        problems = self._problems(chunks)
        self.assertTrue(
            any("published no chunk list" in p for p in problems), problems
        )

    def test_a_shard_running_someone_elses_files_is_caught(self):
        # Same union, wrong ownership: total coverage is intact but the shards
        # disagree with the partition, which means the two derivations drifted.
        chunks = {s: list(v) for s, v in self.sound.items()}
        chunks[1][0], chunks[2][0] = chunks[2][0], chunks[1][0]
        problems = self._problems(chunks)
        self.assertTrue(any("partition says" in p for p in problems), problems)

    def test_a_shard_count_mismatch_is_caught(self):
        chunks = {s: list(v) for s, v in self.sound.items()}
        problems_before = self._problems(chunks)
        self.assertEqual(problems_before, [])
        (self.chunk_dir / "chunk-4.txt").write_text("backend/tests/test_00.py\n")
        problems = st.verify(self.corpus, 3, self.chunk_dir)
        self.assertTrue(
            any("outside shards 1..3" in p for p in problems), problems
        )

    def test_the_empty_partition_is_not_silently_accepted(self):
        # The single worst case: every shard publishes an empty list. The union
        # is empty, so nothing ran, and without this guard the fan-in is green.
        problems = self._problems({1: [], 2: [], 3: []})
        self.assertTrue(any("ran on NO shard" in p for p in problems), problems)


class UnionModeIsTheSecurityCheck(unittest.TestCase):
    """`--union` is what the fan-in runs with the BASE ref's copy.

    It has to keep catching the one defect that matters (a module that ran
    nowhere) while tolerating the two things a legitimate PR is allowed to do:
    change how files are assigned to shards, and add new test modules. If it
    ever stopped tolerating those, this guard would make its own successor
    unmergeable; if it ever stopped catching a dropped module, it would be
    decoration.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _tree(self.root, ["backend/tests/test_%02d.py" % i for i in range(9)])
        self.corpus = st.enumerate_tests(["backend/tests/"], self.root)
        self.chunk_dir = self.root / "chunks"
        self.sound = {s: st.chunk_for(self.corpus, 3, s) for s in (1, 2, 3)}

    def tearDown(self):
        self._tmp.cleanup()

    def _problems(self, chunks, union_only):
        _write_chunks(self.chunk_dir, chunks)
        return st.verify(self.corpus, 3, self.chunk_dir, union_only=union_only)

    def test_guilt_a_dropped_module_is_still_caught(self):
        chunks = {s: list(v) for s, v in self.sound.items()}
        chunks[2].pop()
        problems = self._problems(chunks, union_only=True)
        self.assertTrue(any("ran on NO shard" in p for p in problems), problems)

    def test_guilt_an_overlap_is_still_caught(self):
        chunks = {s: list(v) for s, v in self.sound.items()}
        chunks[3].append(chunks[1][0])
        problems = self._problems(chunks, union_only=True)
        self.assertTrue(any("overlap" in p for p in problems), problems)

    def test_guilt_the_empty_partition_is_still_caught(self):
        problems = self._problems({1: [], 2: [], 3: []}, union_only=True)
        self.assertTrue(any("ran on NO shard" in p for p in problems), problems)

    def test_guilt_a_missing_shard_is_still_caught(self):
        chunks = {s: list(v) for s, v in self.sound.items()}
        del chunks[2]
        problems = self._problems(chunks, union_only=True)
        self.assertTrue(any("published no chunk list" in p for p in problems), problems)

    def test_innocence_a_different_assignment_algorithm_passes(self):
        # What a v2 duration-aware splitter looks like from here: same union,
        # completely different ownership. `--union` must not care.
        flat = [f for s in (1, 2, 3) for f in self.sound[s]]
        chunks = {1: flat[:2], 2: flat[2:7], 3: flat[7:]}
        self.assertEqual(sorted(f for c in chunks.values() for f in c), sorted(self.corpus))
        self.assertEqual(self._problems(chunks, union_only=True), [])
        # ...while the full/drift mode, which the HEAD copy runs, still bites.
        self.assertTrue(self._problems(chunks, union_only=False))

    def test_innocence_running_more_than_the_trusted_corpus_passes(self):
        # A PR that ADDS test modules: the shards run files the base ref's
        # enumeration never heard of. Running MORE is never the defect.
        chunks = {s: list(v) for s, v in self.sound.items()}
        chunks[1].append("backend/tests/test_brand_new.py")
        self.assertEqual(self._problems(chunks, union_only=True), [])
        # The full mode is stricter on purpose and rejects the same input.
        self.assertTrue(
            any("not in the corpus" in p for p in self._problems(chunks, union_only=False))
        )


class CommandLine(unittest.TestCase):
    """The workflow calls this as a subprocess — the exit code IS the guard."""

    def _run(self, argv, cwd):
        # Drive the synthetic corpus through the SCOPED path (IMPACT_*), which
        # is also how the PR lane invokes it — the unscoped defaults point at
        # the real repo tree and do not exist under a temp root.
        env = dict(os.environ)
        env["IMPACT_RUN_ALL"] = "false"
        env["IMPACT_SELECTED_TESTS"] = "\n".join(
            "apps/backend-rag/" + f for f in self.corpus
        )
        return subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent / "shard_tests.py")]
            + argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            env=env,
        )

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _tree(self.root, ["backend/tests/test_%02d.py" % i for i in range(6)])
        self.corpus = st.enumerate_tests(["backend/tests/"], self.root)
        self.chunk_dir = self.root / "chunks"

    def tearDown(self):
        self._tmp.cleanup()

    def test_verify_exits_zero_on_a_sound_partition(self):
        _write_chunks(
            self.chunk_dir, {s: st.chunk_for(self.corpus, 3, s) for s in (1, 2, 3)}
        )
        result = self._run(
            ["verify", "--shards", "3", "--chunk-dir", "chunks"], self.root
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("disjoint and complete", result.stdout)

    def test_verify_exits_nonzero_on_a_broken_partition(self):
        chunks = {s: st.chunk_for(self.corpus, 3, s) for s in (1, 2, 3)}
        chunks[1] = []
        _write_chunks(self.chunk_dir, chunks)
        result = self._run(
            ["verify", "--shards", "3", "--chunk-dir", "chunks"], self.root
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("PARTITION GUARD FAILED", result.stderr)

    def test_union_flag_reaches_the_verifier(self):
        chunks = {s: st.chunk_for(self.corpus, 3, s) for s in (1, 2, 3)}
        flat = [f for s in (1, 2, 3) for f in chunks[s]]
        _write_chunks(self.chunk_dir, {1: flat[:1], 2: flat[1:4], 3: flat[4:]})
        union = self._run(
            ["verify", "--shards", "3", "--chunk-dir", "chunks", "--union"], self.root
        )
        self.assertEqual(union.returncode, 0, union.stderr)
        self.assertIn("union mode", union.stdout)
        full = self._run(
            ["verify", "--shards", "3", "--chunk-dir", "chunks"], self.root
        )
        self.assertEqual(full.returncode, 1, full.stdout)

    def test_chunk_rejects_an_out_of_range_shard(self):
        result = self._run(["chunk", "--shards", "3", "--shard", "4"], self.root)
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
