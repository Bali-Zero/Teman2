"""B12 guilt + innocence: a gate verdict not posted yet is no verdict, and is asked again once it is posted."""
from __future__ import annotations

import sys

import pytest

from . import fixture_repo as fr
from .fixture_repo import runner
from .test_merger import FakeRunner, REPO, mg, pr, world  # noqa: F401 — `world` is the fixture
from .test_service_contexts import HOST_BASE, READER, drive, host_ctx, planned_svc

PEND = "::error::harness_gate_read: PENDING"
CNV = "::error::harness_gate_read: CANNOT-VERIFY"
ERR = "import sys; print({!r}, file=sys.stderr); raise SystemExit(1)"


def reader(tmp_path, body):
    (tmp_path / "r.py").write_text(f"open({str(tmp_path / 'calls')!r}, 'a').write('.')\n{body}\n")
    return [sys.executable, "-I", str(tmp_path / "r.py")]


def calls(tmp_path):
    return len((tmp_path / "calls").read_text())


# ------------------------------------------------------------------ the runner: PENDING is no verdict, asked once, never retried
@pytest.fixture
def waits(monkeypatch):
    slept = []
    monkeypatch.setattr(runner, "READER_RETRY_WAITS", (0, 7, 7))
    monkeypatch.setattr(runner.time, "sleep", slept.append)
    return slept


def test_a_pending_reader_is_no_verdict_and_is_not_retried(tmp_path, waits):
    got = runner.run_host_reader(reader(tmp_path, ERR.format(PEND + " — no harness/fable-gate verdict has been posted yet")), tmp_path, 30, CNV, PEND)
    assert got["rc"] is None and got["reason"].startswith("gate_pending: host, at plan: ") and "asked again once it is" in got["reason"]
    assert calls(tmp_path) == 1 and waits == [0]   # one read; the retry waits of CANNOT-VERIFY were never slept


def test_a_real_verdict_line_stays_a_verdict(tmp_path, waits):
    got = runner.run_host_reader(reader(tmp_path, ERR.format("::error::harness_gate_read: harness/fable-gate verdict = 'failure'")), tmp_path, 30, CNV, PEND)
    assert got["rc"] == 1 and "gate_pending" not in got["reason"] and calls(tmp_path) == 1


def test_cannot_verify_is_still_retried_then_no_verdict(tmp_path, waits):
    got = runner.run_host_reader(reader(tmp_path, ERR.format(CNV + " (read failed)")), tmp_path, 30, CNV, PEND)
    assert got["rc"] is None and "could not read GitHub" in got["reason"] and calls(tmp_path) == 3 and waits == [0, 7, 7]


def test_pending_text_on_stdout_only_cannot_fake_it(tmp_path, waits):
    body = f"print({PEND!r} + ' described'); " + ERR.format("::error::harness_gate_read: harness/fable-gate verdict = 'failure'")
    got = runner.run_host_reader(reader(tmp_path, body), tmp_path, 30, CNV, PEND)
    assert got["rc"] == 1 and calls(tmp_path) == 1


def test_a_pending_line_with_a_zero_exit_is_not_pending(tmp_path, waits):
    got = runner.run_host_reader(reader(tmp_path, f"import sys; print({PEND!r}, file=sys.stderr)"), tmp_path, 30, CNV, PEND)
    assert got["rc"] == 0


def test_no_pending_key_declared_means_the_line_is_a_plain_failure(tmp_path, waits):
    got = runner.run_host_reader(reader(tmp_path, ERR.format(PEND)), tmp_path, 30, CNV)
    assert got["rc"] == 1


def test_the_matrix_declares_the_pending_line_beside_the_cannot_verify_one():
    import yaml
    text = runner.Path(runner.__file__).with_name("contexts_matrix.yaml").read_text()
    contexts = yaml.safe_load(text)["contexts"]
    steps = [s for c in contexts for j in (c.get("local") or {}).get("jobs") or [] for s in j.get("steps") or []]
    steps += [s for c in contexts for s in (c.get("local") or {}).get("steps") or []]
    (host,) = [s for s in steps if s.get("no_verdict_when") == CNV]
    assert host["pending_when"] == PEND and host["side"] == "host"


@pytest.mark.usefixtures("fake_env")
@pytest.mark.parametrize("declared,rc", [(PEND, None), (None, 1)])
def test_the_matrix_key_travels_from_the_step_into_the_plan(tmp_path, monkeypatch, declared, rc):
    base = {**HOST_BASE, READER: "import sys; print(%r, file=sys.stderr); raise SystemExit(1)\n" % PEND}
    ctx = host_ctx(["$PY", READER, "--repo", "${{ github.repository }}"])
    ctx["local"]["steps"][1].update(no_verdict_when=CNV, **({"pending_when": declared} if declared else {}))
    spec = planned_svc(tmp_path, monkeypatch, fr.CANDIDATE_FILES, ctx, base)
    assert spec["jobs"][0]["steps"][1]["precomputed"]["rc"] == rc


# ------------------------------------------------------------------ pending -> step BLOCKED -> context BLOCKED -> overall BLOCKED, never PASS or FAIL
PLAN = {"contexts_status": "ok", "required_contexts": ["Gate"], "contexts_map": {"Gate": {"mapping": "executed", "check": "ctx.harness-floor"}}}


def chain(tmp_path, precomputed):
    steps = [{"name": "Gear >= 2 — read the real gate verdict", "argv": ["true"], "precomputed": precomputed}]
    got, rc = drive(tmp_path, steps)
    status, reason = runner.classify_contained_steps(rc, got, {"steps": [{"name": s["name"]} for s in steps]})
    res = runner.evaluate_contexts({"ctx.harness-floor": {"status": status, "reason": reason}}, PLAN)
    view = {"ctx.harness-floor": {"status": status, "reason": reason}}
    return got, status, res, runner.overall(view, PLAN)


def test_a_pending_reader_blocks_the_step_the_context_and_the_overall(tmp_path):
    pend = runner.run_host_reader(reader(tmp_path, ERR.format(PEND)), tmp_path, 30, CNV, PEND)
    (tmp_path / "w").mkdir()
    got, status, res, overall = chain(tmp_path / "w", pend)
    assert [s["status"] for s in got] == ["BLOCKED"] and status == "BLOCKED"
    assert res["results"]["Gate"]["verdict"] == "BLOCKED" and res["results"]["Gate"]["no_verdict"] == "gate_pending" and res["blocked"] == ["Gate"]
    assert overall == "BLOCKED" and res["red"] == []


def test_a_failed_verdict_is_a_fail_all_the_way_up_and_carries_no_pending_mark(tmp_path):
    (tmp_path / "w").mkdir()
    got, status, res, overall = chain(tmp_path / "w", {"rc": 1, "reason": "host, at plan: BASE harness_gate_read.py rc=1", "log": ""})
    assert status == "FAIL" and "no_verdict" not in res["results"]["Gate"] and res["red"] == ["Gate"] and overall == "FAIL"


def test_another_blocked_context_is_not_marked_pending():
    plan = {**PLAN, "contexts_map": {"Gate": {"mapping": "executed", "check": "c", "coverage": "full"}}}
    res = runner.evaluate_contexts({"c": {"status": "BLOCKED", "reason": "1 step(s) BLOCKED: x (could not start: OSError)"}}, plan)
    assert res["results"]["Gate"]["verdict"] == "BLOCKED" and "no_verdict" not in res["results"]["Gate"]


def test_a_blocked_gate_still_refuses_the_merge_criterion():
    loc = mg.local_side({"contexts": {"status": "ok", "required": ["Gate"], "results": {"Gate": {"verdict": "BLOCKED", "mapping": "executed",
                                                                                             "no_verdict": "gate_pending", "coverage": "full"}}},
                         "checks": {"policy.change_map": {"status": "PASS"}}})
    assert "Gate" in str(loc["why"]["executed_contexts_ok"]) and loc["host_no_verdict"] == {}


# ------------------------------------------------------------------ the merger: triage
H, B1, B2 = "1" * 40, "b" * 40, "c" * 40


def dec(pending, base=B1, **kw):
    return {"kind": "decision", "pr": 1, "head_sha": H, "base_sha": base, "ts": "2026-10-09T10:00:00Z", **({"gate_pending": True} if pending else {}), **kw}


def run_triage(recs, posted, capped=None, base=B1):
    seen = []

    def gate(n, head):
        seen.append((n, head))
        if isinstance(posted, Exception):
            raise posted
        return posted
    todo, _ = mg.triage([pr(1, H)], REPO, recs, base, gate, capped)
    return [p["number"] for p in todo], seen


def test_a_pending_decision_is_decided_again_only_with_the_status_on_the_head():
    assert run_triage([dec(True)], True) == ([1], [(1, H)])


def test_without_the_status_it_is_not_eligible_and_one_read_was_made():
    assert run_triage([dec(True)], False) == ([], [(1, H)])


def test_a_failed_read_is_not_eligible(capsys):
    assert run_triage([dec(True)], mg.hc.CompareError("gh down"))[0] == []
    assert "gate status not read" in capsys.readouterr().err


def test_a_decision_that_was_not_pending_is_never_asked_about():
    assert run_triage([dec(False)], True) == ([], [])


def test_a_new_base_is_a_new_key_and_needs_no_status_read():
    assert run_triage([dec(True)], False, base=B2) == ([1], [])


def test_the_newest_decision_of_the_key_decides_pending_or_settled():
    assert run_triage([dec(True), dec(False)], True)[0] == []


def test_a_replay_line_neither_opens_nor_closes_a_key():
    assert run_triage([dec(True), dec(False, replay=True, merge_commit="d" * 40)], True)[0] == [1]
    assert run_triage([dec(False), dec(True, replay=True, merge_commit="d" * 40)], True) == ([], [])


@pytest.mark.parametrize("n,again", [(1, True), (2, True), (3, False)])
def test_at_most_three_pending_decisions_per_key(n, again):
    capped: list = []
    todo, seen = run_triage([dec(True) for _ in range(n)], True, capped)
    assert (todo == [1]) is again and bool(capped) is (not again) and (seen == []) is (not again)   # past the cap: no read either


# ------------------------------------------------------------------ the merger: ticks
BLOCKED_PENDING = {"contexts": {"status": "ok", "results": {"ctx-a": {"verdict": "BLOCKED", "mapping": "executed", "no_verdict": "gate_pending"}}}}


class Statuses:
    """FakeGH plus the commit-status read: ``posted`` is whether the head carries harness/fable-gate; ``fail`` makes the read raise."""

    def __init__(self, gh):
        self.gh, self.posted, self.fail, self.reads = gh, False, False, []

    def __call__(self, path):
        if "/statuses?" in path:
            self.reads.append(path)
            if self.fail:
                raise mg.hc.CompareError("gh api down")
            return [{"context": "harness/fable-gate", "state": "pending"}] if self.posted else [{"context": "other", "state": "success"}]
        return self.gh(path)


@pytest.fixture
def pending_world(world, monkeypatch):  # noqa: F811
    world.runner.doc = BLOCKED_PENDING
    real, stamps = mg.time.strftime, iter(range(100))
    monkeypatch.setattr(mg.time, "strftime", lambda fmt, *a: f"2026T{next(stamps):04d}" if fmt == "%Y%m%dT%H%M%SZ" else real(fmt, *a))   # ticks within one second
    world.st = Statuses(world.gh)
    monkeypatch.setattr(mg.hc, "gh_get", world.st)
    world.gh.prs = [pr(1, world.head1)]
    world.decisions = lambda: [r for r in world.journal() if r["kind"] == "decision"]
    return world


def test_the_first_decision_journals_gate_pending_and_a_second_follows_the_post(pending_world):
    w = pending_world
    assert w.tick() == 0
    (d,) = w.decisions()
    assert d["gate_pending"] is True and d["overall"] == "BLOCKED" and d["contexts"] == {"ctx-a": "BLOCKED"}
    assert w.tick() == 0 and len(w.decisions()) == 1 and len(w.st.reads) == 1   # nothing posted: not decided again, one GET
    w.st.posted = True
    assert w.tick() == 0
    assert len(w.decisions()) == 2 and {(r["pr"], r["head_sha"], r["base_sha"]) for r in w.decisions()} == {(1, w.head1, w.base)}


def test_a_failed_status_read_decides_nothing(pending_world):
    w = pending_world
    w.tick()
    w.st.posted, w.st.fail = True, True
    assert w.tick() == 0 and len(w.decisions()) == 1


def test_the_cap_stays_decided_and_is_journalled_once(pending_world):
    w = pending_world
    w.st.posted = True
    for _ in range(6):
        assert w.tick() == 0
    assert len(w.decisions()) == mg.GATE_PENDING_CAP
    assert [(r["why"], r["pr"]) for r in w.journal() if r["kind"] == "skipped"] == [("gate_pending_cap", 1)]


def test_a_settled_decision_is_never_decided_again_even_with_the_status(world, monkeypatch):
    st = Statuses(world.gh)
    st.posted = True
    monkeypatch.setattr(mg.hc, "gh_get", st)
    world.gh.prs = [pr(1, world.head1)]
    world.tick()
    world.tick()
    assert len([r for r in world.journal() if r["kind"] == "decision"]) == 1 and st.reads == []
    assert "gate_pending" not in [r for r in world.journal() if r["kind"] == "decision"][0]
