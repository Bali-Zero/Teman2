"""Hypothesis state machine over the real runner + inert stub: the gate's invariants hold under any interleaving."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from unittest import mock

import pytest

pytest.importorskip("hypothesis")
from hypothesis import settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule  # noqa: E402

from . import fixture_repo as fr  # noqa: E402
from .fixture_repo import PY, cmd_check, git, release_stub, runner  # noqa: E402

EXEC_KINDS = ("pytest", "trusted_pytest", "cmd")
BAD_REVIEWS = {"sha": {"reviewed_candidate_sha": "0" * 40}, "tree": {"reviewed_tree_sha": "1" * 40}, "base": {"reviewed_base_sha": "2" * 40},
               "builder": {"reviewer_seat": "builder-a"}, "verdict": {"verdict": "FAIL"}}


class GateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.root = Path(tempfile.mkdtemp(prefix="localci-sm-"))
        self.patch = mock.patch.object(runner, "env_fingerprint", fr.FakeEnv())
        self.patch.start()
        self.fx = fr.make_repo(self.root)
        fr.plan(self.fx, "--contexts-file", str(fr.contexts_file(self.fx, self.root / "contexts.yaml")),
                "--extra-check", cmd_check("x.ok", self.fx["repo"], [PY, "-c", "import sys,pathlib;sys.exit(int(pathlib.Path(sys.argv[1]).exists()))", str(self.root / "switch")]))
        self.switch = self.root / "switch"
        self.plan_path = self.fx["run"] / "state" / "plan.json"
        self.kinds = {n: s["kind"] for n, s in json.loads(self.plan_path.read_text())["checks"].items()}
        self.at_original, self.review_good, self.n = True, False, 0
        fr.run(self.fx)

    def set_switch(self, on: bool):
        # x.ok reads a switch file, so the (integrity-checked) plan is never edited
        if on:
            self.switch.write_text("fail")
        elif self.switch.exists():
            self.switch.unlink()

    @rule()
    def run_check_pass(self):
        self.set_switch(False)
        fr.run(self.fx, "--only", "x.ok")

    @rule()
    def run_check_fail(self):
        self.set_switch(True)
        fr.run(self.fx, "--only", "x.ok")
        self.set_switch(False)

    @rule()
    def move_candidate(self):
        if self.at_original:
            git(self.fx["repo"], "commit", "-q", "--allow-empty", "-m", "moved")
            self.at_original = False

    @rule()
    def restore_candidate(self):
        git(self.fx["repo"], "reset", "-q", "--hard", self.fx["candidate"])
        self.at_original = True

    @rule()
    def import_review_good(self):
        fr.import_review(self.fx, self.root)
        self.review_good = True

    @rule(kind=st.sampled_from(sorted(BAD_REVIEWS)))
    def import_review_bad(self, kind):
        fr.import_review(self.fx, self.root, **BAD_REVIEWS[kind])
        self.review_good = False

    @rule()
    def kill_running(self):
        fr.make_running(self.fx, "x.ok")

    @rule()
    def propose_release(self):
        self.n += 1
        rec = release_stub.propose(self.fx["run"], f"req{self.n}", self.fx["candidate"])
        if rec["verdict"] == "ALLOW_PROPOSED":
            assert self.at_original, "ALLOW on a moved candidate"
            assert self.review_good, "ALLOW without a good review"
            assert rec["overall"] == "PASS" and rec["proposed_action"]["executed"] is False

    @invariant()
    def never_pass_without_receipt_or_with_a_dead_running(self):
        s = fr.status(self.fx)
        for name, c in s["checks"].items():
            if c["status"] == "PASS" and self.kinds.get(name) in EXEC_KINDS:
                assert c["receipt"] and Path(c["receipt"]).exists(), f"{name} PASS without receipt"
        assert not any(c["status"] == "RUNNING" for c in s["checks"].values()), "RUNNING with a dead pid survived status"

    @invariant()
    def moved_candidate_invalidates_every_pass(self):
        if not self.at_original:
            s = fr.status(self.fx)
            assert s["overall"] != "PASS"
            assert [n for n, c in s["checks"].items() if c["status"] == "PASS"] == [], s["checks"]

    @invariant()
    def allow_only_on_pass_and_at_most_once_per_key(self):
        p = self.fx["run"] / "state" / "release_journal.jsonl"
        rows = [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
        allowed = [r for r in rows if r["verdict"] == "ALLOW_PROPOSED"]
        assert len({r["idempotency_key"] for r in allowed}) == len(allowed)
        assert all(r["overall"] == "PASS" and r["reasons"] == [] for r in allowed)

    def teardown(self):
        self.patch.stop()
        shutil.rmtree(self.root, ignore_errors=True)


GateMachine.TestCase.settings = settings(max_examples=30, deadline=None, stateful_step_count=8, print_blob=True)
TestGateMachine = GateMachine.TestCase


def test_the_machine_can_actually_reach_an_allow_and_then_be_invalidated():
    m = GateMachine()
    try:
        m.import_review_good()
        m.propose_release()
        rows = [json.loads(x) for x in (m.fx["run"] / "state" / "release_journal.jsonl").read_text().splitlines()]
        assert [r["verdict"] for r in rows] == ["ALLOW_PROPOSED"]
        m.move_candidate()
        m.propose_release()
        m.never_pass_without_receipt_or_with_a_dead_running()
        m.moved_candidate_invalidates_every_pass()
        m.allow_only_on_pass_and_at_most_once_per_key()
        assert [json.loads(x)["verdict"] for x in (m.fx["run"] / "state" / "release_journal.jsonl").read_text().splitlines()] == ["ALLOW_PROPOSED", "DENY"]
    finally:
        m.teardown()
