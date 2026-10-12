"""B12 guilt + innocence: a gate verdict not posted yet is no verdict, and is asked again once it is posted."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys

import pytest

from . import fixture_repo as fr
from .fixture_repo import runner
from .test_merger import FakeRunner, REPO, mg, pr, world  # noqa: F401 — `world` is the fixture
from .test_service_contexts import HOST_BASE, READER, host_ctx, planned_svc

PEND = "::error::harness_gate_read: PENDING"
CNV = "::error::harness_gate_read: CANNOT-VERIFY"
ERR = "import sys; print({!r}, file=sys.stderr); raise SystemExit(1)"


def reader(tmp_path, body):
    (tmp_path / "r.py").write_text(f"open({str(tmp_path / 'calls')!r}, 'a').write('.')\n{body}\n")
    return [sys.executable, "-I", str(tmp_path / "r.py")]


def calls(tmp_path):
    return len((tmp_path / "calls").read_text())


# ------------------------------------------------------------------ the runner: PENDING is no verdict, asked once, never retried
class _RunnerClock:
    """The runner's own ``time``, with ``sleep`` recorded: patching ``time.sleep`` itself also records any other thread's sleep."""

    def __init__(self, real, slept):
        self.real, self.sleep = real, slept.append

    def __getattr__(self, name):
        return getattr(self.real, name)


@pytest.fixture
def waits(monkeypatch):
    slept = []
    monkeypatch.setattr(runner, "READER_RETRY_WAITS", (0, 7, 7))
    monkeypatch.setattr(runner, "time", _RunnerClock(runner.time, slept))
    return slept


def test_a_pending_reader_is_no_verdict_and_is_not_retried(tmp_path, waits):
    got = runner.run_host_reader(reader(tmp_path, ERR.format(PEND + " — no harness/fable-gate verdict has been posted yet")), tmp_path, 30, CNV, PEND)
    assert got["rc"] is None and got["reason"].startswith("gate_pending: host, at plan: ") and "asked again once it is" in got["reason"]
    assert got["gate_pending"] is True   # the structured flag the plan freezes, what marks the context
    assert calls(tmp_path) == 1 and waits == [0]   # one read; the retry waits of CANNOT-VERIFY were never slept


def test_a_real_verdict_line_stays_a_verdict(tmp_path, waits):
    got = runner.run_host_reader(reader(tmp_path, ERR.format("::error::harness_gate_read: harness/fable-gate verdict = 'failure'")), tmp_path, 30, CNV, PEND)
    assert got["rc"] == 1 and "gate_pending" not in got["reason"] and "gate_pending" not in got and calls(tmp_path) == 1


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


def gate_reader_lines(monkeypatch, capsys, state):
    """The BASE harness_gate_read.py's own stderr for a head whose harness/fable-gate state is ``state`` (None: never posted)."""
    path = runner.Path(runner.__file__).resolve().parents[2] / "scripts" / "ci" / "harness_gate_read.py"
    spec = importlib.util.spec_from_file_location("b12_harness_gate_read", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "resolve_real_head_sha", lambda **kw: ("a" * 40, "fixture"))
    monkeypatch.setattr(mod, "read_fable_gate_state", lambda **kw: (state, None))
    capsys.readouterr()
    rc = mod.main(["--event-name", "pull_request", "--repo", "o/r", "--pr-head-sha", "a" * 40])
    code, _ = mod.decide(state)
    return rc, code, capsys.readouterr().err.splitlines()


@pytest.mark.parametrize("state,pending", [(None, True), ("pending", False), ("failure", False), ("error", False)])
def test_the_matrix_pending_line_is_the_base_readers_own_not_posted_line_and_never_a_posted_states(monkeypatch, capsys, state, pending):
    import yaml
    doc = yaml.safe_load(runner.Path(runner.__file__).with_name("contexts_matrix.yaml").read_text())
    (when,) = [s["pending_when"] for c in doc["contexts"] for s in (c.get("local") or {}).get("steps") or [] if "pending_when" in s]
    rc, code, err = gate_reader_lines(monkeypatch, capsys, state)
    assert rc == code == 1 and err   # every one of them is a non-zero exit with a stderr line: only the line tells them apart
    assert any(ln.startswith(when) for ln in err) is pending


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
GATE_STEP = "Gear >= 2 — read the real gate verdict"


@pytest.fixture
def leg_world(tmp_path, monkeypatch):
    """_run_leg as the runner drives it, with the sandbox replaced by the real steps driver run on the host on the same steps.json."""
    work = tmp_path / "w"
    work.mkdir()
    for d in ("receipts", "logs"):
        (tmp_path / d).mkdir()

    def fake_exec(name, spec, run_dir, plan, inner, overrides, extra, env, log, junit, *a, **k):
        cfg = {**json.loads(extra["cfg/steps.json"]), "root": str(work), "git_index": False, "checkout": None}
        (tmp_path / "steps.json").write_text(json.dumps(cfg))
        rc = subprocess.run([sys.executable, "-I", str(runner.STEPS_DRIVER), str(tmp_path / "steps.json"), str(junit)], capture_output=True).returncode
        return rc, None
    monkeypatch.setattr(runner, "execute_contained", fake_exec)
    monkeypatch.setattr(runner, "disk_floor_refusal", lambda *a: None)
    monkeypatch.setattr(runner, "start_services", lambda *a: ([], None, None))

    def run(steps):
        job = {"job_id": "harness-floor", "legs": [{}], "needs": [], "steps": steps, "path_prefix": "", "venv": False, "job_env": {}, "services": [],
               "image_id": "sha256:img", "timeout_s": 60}
        spec = {"context": "t", "jobs": [job], "needs": {}, "judge_modified": [], "history": None, "expr": {"github": {}, "runner": {"temp": "missing"}},
                "isolation": {"mode": "container", "docker": "docker", "image_id": "sha256:img"},
                "driver_sha256": runner.sha256_bytes(runner.STEPS_DRIVER.read_bytes()), "expr_sha256": runner.sha256_bytes(runner.GH_EXPR.read_bytes())}
        res = runner._execute_jobs("ctx.harness-floor", spec, tmp_path, {"run_id": "r", "worktree": str(work)}, tmp_path / "ctx.log")
        view = {"ctx.harness-floor": res}
        return res, runner.evaluate_contexts(view, PLAN), runner.overall(view, PLAN)
    return run


def test_a_pending_reader_blocks_the_step_the_context_and_the_overall(tmp_path, leg_world):
    pend = runner.run_host_reader(reader(tmp_path, ERR.format(PEND)), tmp_path, 30, CNV, PEND)
    res, ctx, overall = leg_world([{"name": GATE_STEP, "argv": ["true"], "precomputed": pend}])
    assert [(s["status"], s.get("gate_pending")) for s in res["steps"]] == [("BLOCKED", True)] and res["status"] == "BLOCKED"
    assert res["gate_pending"] is True
    assert ctx["results"]["Gate"]["verdict"] == "BLOCKED" and ctx["results"]["Gate"]["no_verdict"] == "gate_pending" and ctx["blocked"] == ["Gate"]
    assert overall == "BLOCKED" and ctx["red"] == []


def test_a_failed_verdict_is_a_fail_all_the_way_up_and_carries_no_pending_mark(leg_world):
    res, ctx, overall = leg_world([{"name": GATE_STEP, "argv": ["true"], "precomputed": {"rc": 1, "reason": "host, at plan: BASE r.py rc=1", "log": ""}}])
    assert res["status"] == "FAIL" and "gate_pending" not in res and "no_verdict" not in ctx["results"]["Gate"] and ctx["red"] == ["Gate"]
    assert overall == "FAIL"


def test_the_mark_is_the_plan_frozen_flag_however_long_the_reason_and_never_a_second_blocked_steps(tmp_path, leg_world):
    pend = runner.run_host_reader(reader(tmp_path, ERR.format(PEND)), tmp_path, 30, CNV, PEND)
    long_name = "Gear >= 2 — " + "x" * 700   # the joined reason is cut at 600 characters: the old text mark fell off the end
    res, ctx, _ = leg_world([{"name": long_name, "argv": ["true"], "precomputed": pend}])
    assert "gate_pending: host" not in res["reason"] and res["gate_pending"] is True and ctx["results"]["Gate"]["no_verdict"] == "gate_pending"
    other = {"name": "Another host read", "if": "always()", "argv": ["true"], "precomputed": {"rc": None, "reason": "host reader could not run: OSError"}}
    res, ctx, overall = leg_world([{"name": GATE_STEP, "argv": ["true"], "precomputed": pend}, other])
    assert [s["status"] for s in res["steps"]] == ["BLOCKED", "BLOCKED"] and "gate_pending: host" in res["reason"]   # the text is there ...
    assert "gate_pending" not in res and "no_verdict" not in ctx["results"]["Gate"] and overall == "BLOCKED"        # ... and marks nothing


def test_a_pending_text_in_the_candidate_produced_junit_marks_nothing(leg_world):
    fake = {"rc": None, "reason": "gate_pending: host, at plan: BASE r.py — no harness/fable-gate verdict posted on the head yet"}
    res, ctx, _ = leg_world([{"name": GATE_STEP, "argv": ["true"], "precomputed": fake}])   # the text without the plan's flag
    assert res["status"] == "BLOCKED" and "gate_pending" not in res and "no_verdict" not in ctx["results"]["Gate"]


@pytest.mark.parametrize("view,marked", [
    ({"status": "BLOCKED", "reason": "1 step(s) BLOCKED: g (gate_pending: host, at plan: BASE r.py)"}, False),   # the text, no flag
    ({"status": "BLOCKED", "reason": "1 step(s) BLOCKED: x (could not start: OSError)"}, False),
    ({"status": "BLOCKED", "reason": "1 step(s) BLOCKED: g (a reason)", "gate_pending": True}, True),
    ({"status": "FAIL", "reason": "1 step(s) FAIL: g (rc=1)", "gate_pending": True}, False),
])
def test_evaluate_contexts_marks_a_blocked_context_from_its_flag_only(view, marked):
    plan = {**PLAN, "contexts_map": {"Gate": {"mapping": "executed", "check": "c", "coverage": "full"}}}
    res = runner.evaluate_contexts({"c": view}, plan)
    assert (res["results"]["Gate"].get("no_verdict") == "gate_pending") is marked


@pytest.mark.parametrize("steps,want", [
    ([("BLOCKED", True)], True),
    ([("BLOCKED", True), ("PASS", None), ("NOT_APPLICABLE", None)], True),
    ([("BLOCKED", True), ("BLOCKED", None)], False),
    ([("BLOCKED", True), ("FAIL", None)], False),   # a red read with a rewritten judge is BLOCKED too, and stays so after the post
    ([("PASS", None)], False),
])
def test_a_context_is_pending_only_when_every_step_that_did_not_pass_is_a_pending_read(steps, want):
    got = [{"name": f"s{i}", "status": st, "reason": "", **({"gate_pending": True} if gp else {})} for i, (st, gp) in enumerate(steps)]
    assert runner.gate_pending_of("BLOCKED", got) is want
    assert runner.gate_pending_of("ERROR", got) is False


def test_the_run_keeps_this_attempts_flag_on_the_check_and_never_an_earlier_ones(fx, monkeypatch):
    fr.plan(fx, "--extra-check", fr.cmd_check("c.gate", fx["repo"], ["true"]))
    answer = {"status": "BLOCKED", "reason": "1 step(s) BLOCKED", "rc": None, "counts": None, "gate_pending": True}
    monkeypatch.setattr(runner, "execute", lambda *a, **k: dict(answer))
    fr.run(fx, "--only", "c.gate")
    assert fr.load_state(fx)["checks"]["c.gate"]["gate_pending"] is True
    st = fr.load_state(fx)
    st["checks"]["c.gate"]["status"] = "QUEUED"
    fr.save_state(fx, st)
    answer.pop("gate_pending")
    fr.run(fx, "--only", "c.gate")
    c = fr.load_state(fx)["checks"]["c.gate"]
    assert c["status"] == "BLOCKED" and "gate_pending" not in c


def test_a_check_blocked_because_the_worktree_moved_drops_an_earlier_flag(fx, monkeypatch):
    fr.plan(fx, "--extra-check", fr.cmd_check("c.gate", fx["repo"], ["true"]))
    monkeypatch.setattr(runner, "execute", lambda *a, **k: {"status": "BLOCKED", "reason": "x", "rc": None, "counts": None, "gate_pending": True})
    fr.run(fx, "--only", "c.gate")
    st = fr.load_state(fx)
    st["checks"]["c.gate"]["status"] = "QUEUED"
    fr.save_state(fx, st)
    (fx["repo"] / "moved.txt").write_text("x\n")
    fr.run(fx, "--only", "c.gate")
    c = fr.load_state(fx)["checks"]["c.gate"]
    assert c["status"] == "BLOCKED" and c["reason"].startswith("worktree moved") and "gate_pending" not in c


def test_a_blocked_gate_still_refuses_the_merge_criterion():
    loc = mg.local_side({"contexts": {"status": "ok", "required": ["Gate"], "results": {"Gate": {"verdict": "BLOCKED", "mapping": "executed",
                                                                                             "no_verdict": "gate_pending", "coverage": "full"}}},
                         "checks": {"policy.change_map": {"status": "PASS"}}})
    assert "Gate" in str(loc["why"]["executed_contexts_ok"]) and loc["host_no_verdict"] == {}


# ------------------------------------------------------------------ the merger: triage
H, B1, B2 = "1" * 40, "b" * 40, "c" * 40


GATE = "Harness floor recompute"


def dec(pending, base=B1, overall="BLOCKED", **kw):
    mark = {"gate_pending": True, "gate_pending_contexts": [GATE]} if pending else {}
    return {"kind": "decision", "pr": 1, "head_sha": H, "base_sha": base, "ts": "2026-10-09T10:00:00Z", "overall": overall, **mark, **kw}


def run_triage(recs, posted, capped=None, base=B1):
    seen = []

    def gate(n, head, names):
        seen.append((n, head, tuple(names)))
        if isinstance(posted, Exception):
            raise posted
        return posted
    todo, _ = mg.triage([pr(1, H)], REPO, recs, base, gate, capped)
    return [p["number"] for p in todo], [s[:2] for s in seen]


def test_a_pending_decision_is_decided_again_only_when_the_gate_is_ready_and_is_asked_with_its_pending_contexts():
    seen = []
    todo, _ = mg.triage([pr(1, H)], REPO, [dec(True)], B1, lambda n, head, names: seen.append(names) or True)
    assert [p["number"] for p in todo] == [1] and seen == [[GATE]]


def test_without_the_status_it_is_not_eligible_and_one_read_was_made():
    assert run_triage([dec(True)], False) == ([], [(1, H)])


def test_a_failed_read_is_not_eligible(capsys):
    assert run_triage([dec(True)], mg.hc.CompareError("gh down"))[0] == []
    assert "gate status or hosted re-run not read" in capsys.readouterr().err


@pytest.mark.parametrize("overall", ["FAIL", "ERROR", "PASS"])
def test_a_pending_mark_on_a_decision_that_is_not_blocked_never_reopens_its_key(overall):
    assert run_triage([dec(True, overall=overall)], True) == ([], [])


@pytest.mark.parametrize("names", [None, [], "Harness floor recompute", [3]])
def test_a_pending_mark_without_readable_contexts_never_reopens_its_key(names):
    rec = {**dec(True), "gate_pending_contexts": names}
    if names is None:
        rec.pop("gate_pending_contexts")
    assert run_triage([rec], True) == ([], [])


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


# ------------------------------------------------------------------ the merger: is the gate ready? the post, then the hosted re-run after it
POSTED = "2026-10-09T10:05:00Z"


def crun(status="completed", completed=None, rid=1, suite=7, name=GATE, conclusion="success"):
    return {"id": rid, "name": name, "status": status, "conclusion": conclusion if status == "completed" else None,
            "completed_at": completed if status == "completed" else None, "check_suite": {"id": suite}}


class GH:
    """hc.gh_get for the two B12 reads: the head's commit statuses (a bare list) and its check runs by name (an object)."""

    def __init__(self, statuses=(), runs=(), fail=None):
        self.statuses, self.runs, self.fail, self.paths = list(statuses), list(runs), fail, []

    def __call__(self, path):
        self.paths.append(path)
        if self.fail and self.fail in path:
            raise mg.hc.CompareError("gh api down")
        if "/statuses?" in path:
            return self.statuses
        if "/check-runs?check_name=" in path:
            return {"total_count": len(self.runs), "check_runs": self.runs}
        raise AssertionError(path)


def ready(monkeypatch, gh, names=(GATE,)):
    monkeypatch.setattr(mg.hc, "gh_get", gh)
    return mg.gate_ready(REPO, H, list(names))


POST = {"context": "harness/fable-gate", "state": "success", "updated_at": POSTED, "created_at": POSTED}


def test_a_hosted_run_completed_before_the_post_is_not_ready(monkeypatch):
    assert ready(monkeypatch, GH([POST], [crun(completed="2026-10-09T10:01:00Z")])) is False


def test_a_hosted_run_still_in_progress_after_the_post_is_not_ready(monkeypatch):
    assert ready(monkeypatch, GH([POST], [crun(status="in_progress")])) is False
    assert ready(monkeypatch, GH([POST], [crun(status="queued", rid=2), crun(completed="2026-10-09T10:09:00Z", suite=8)])) is False


def test_a_hosted_run_completed_after_the_post_is_ready_and_both_reads_are_bounded_gets(monkeypatch):
    gh = GH([POST], [crun(completed="2026-10-09T10:09:00Z")])
    assert ready(monkeypatch, gh) is True
    assert gh.paths == [f"repos/{REPO}/commits/{H}/statuses?per_page=100&page=1",
                        f"repos/{REPO}/commits/{H}/check-runs?check_name=Harness%20floor%20recompute&filter=latest&per_page=100&page=1"]


def test_the_latest_attempt_of_a_check_counts_and_an_older_one_it_replaced_does_not(monkeypatch):
    runs = [crun(completed="2026-10-09T10:01:00Z", rid=5, conclusion="failure"), crun(completed="2026-10-09T10:09:00Z", rid=9)]
    assert ready(monkeypatch, GH([POST], runs)) is True
    assert ready(monkeypatch, GH([POST], list(reversed(runs)))) is True
    assert ready(monkeypatch, GH([POST], [crun(completed="2026-10-09T10:09:00Z", rid=5), crun(status="in_progress", rid=9)])) is False


def test_every_check_suite_must_have_run_again_after_the_post(monkeypatch):
    runs = [crun(completed="2026-10-09T10:09:00Z", suite=7), crun(completed="2026-10-09T10:01:00Z", rid=2, suite=8)]
    assert ready(monkeypatch, GH([POST], runs)) is False


@pytest.mark.parametrize("statuses,runs", [
    ([], [crun(completed="2026-10-09T10:09:00Z")]),                                                   # nothing posted
    ([{"context": "other", "state": "success", "updated_at": POSTED}], [crun(completed="2026-10-09T10:09:00Z")]),
    ([POST], []),                                                                                      # no hosted run at all
    ([POST], [crun(completed="2026-10-09T10:09:00Z", name="Harness floor recompute (other)")]),     # another check's name
    ([POST], [crun(completed=POSTED)]),                                                               # at the post, not after it
])
def test_not_ready_without_a_post_or_without_a_run_of_that_name_after_it(monkeypatch, statuses, runs):
    assert ready(monkeypatch, GH(statuses, runs)) is False


def test_the_newest_post_is_the_one_the_rerun_must_follow(monkeypatch):
    older = {**POST, "state": "pending", "updated_at": "2026-10-09T10:00:00Z"}
    newer = {**POST, "updated_at": "2026-10-09T10:20:00Z"}
    assert ready(monkeypatch, GH([older, newer], [crun(completed="2026-10-09T10:09:00Z")])) is False
    assert ready(monkeypatch, GH([newer, older], [crun(completed="2026-10-09T10:21:00Z")])) is True


@pytest.mark.parametrize("gh", [GH([POST], [], fail="/check-runs?"), GH([POST], [], fail="/statuses?"),
                                GH([{**POST, "updated_at": "yesterday", "created_at": None}], [crun(completed="2026-10-09T10:09:00Z")])])
def test_a_failed_or_unorderable_read_raises_and_triage_reads_that_as_not_eligible(monkeypatch, gh):
    with pytest.raises(mg.hc.CompareError):
        ready(monkeypatch, gh)


# ------------------------------------------------------------------ the merger: ticks
BLOCKED_PENDING = {"contexts": {"status": "ok", "results": {"ctx-a": {"verdict": "BLOCKED", "mapping": "executed", "no_verdict": "gate_pending"}}}}


class Statuses:
    """FakeGH plus the two B12 reads: ``posted`` is whether the head carries harness/fable-gate (posted at 10:05), ``rerun`` when the
    hosted ctx-a run completed (None: still in progress); ``fail`` makes the status read raise."""

    def __init__(self, gh):
        self.gh, self.posted, self.fail, self.reads, self.rerun = gh, False, False, [], "2026-10-09T10:09:00Z"

    def __call__(self, path):
        if "/statuses?" in path:
            self.reads.append(path)
            if self.fail:
                raise mg.hc.CompareError("gh api down")
            return [{"context": "harness/fable-gate", "state": "pending", "updated_at": POSTED}] if self.posted else \
                [{"context": "other", "state": "success", "updated_at": POSTED}]
        if "/check-runs?check_name=" in path:
            self.reads.append(path)
            return {"check_runs": [crun(name="ctx-a", status="completed" if self.rerun else "in_progress", completed=self.rerun)]}
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


def test_the_first_decision_journals_gate_pending_and_the_next_follows_the_post_and_the_hosted_rerun(pending_world):
    w = pending_world
    assert w.tick() == 0
    (d,) = w.decisions()
    assert d["gate_pending"] is True and d["gate_pending_contexts"] == ["ctx-a"] and d["overall"] == "BLOCKED" and d["contexts"] == {"ctx-a": "BLOCKED"}
    assert w.tick() == 0 and len(w.decisions()) == 1 and len(w.st.reads) == 1   # nothing posted: not decided again, one GET
    w.st.posted, w.st.rerun = True, "2026-10-09T10:01:00Z"   # posted, but hosted still holds the run from before the post
    assert w.tick() == 0 and len(w.decisions()) == 1
    w.st.rerun = None   # `gh run rerun`: in progress
    assert w.tick() == 0 and len(w.decisions()) == 1
    w.st.rerun = "2026-10-09T10:09:00Z"
    assert w.tick() == 0
    assert len(w.decisions()) == 2 and {(r["pr"], r["head_sha"], r["base_sha"]) for r in w.decisions()} == {(1, w.head1, w.base)}


def test_a_red_decision_with_a_pending_gate_journals_no_pending_mark_and_is_never_decided_again(pending_world):
    w = pending_world
    w.runner.overall, w.st.posted = "FAIL", True
    assert w.tick() == 0 and w.tick() == 0
    (d,) = w.decisions()
    assert d["overall"] == "FAIL" and "gate_pending" not in d and "gate_pending_contexts" not in d and w.st.reads == []


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


def test_a_settled_decision_is_never_decided_again_even_with_the_status(world, monkeypatch):  # noqa: F811
    st = Statuses(world.gh)
    st.posted = True
    monkeypatch.setattr(mg.hc, "gh_get", st)
    world.gh.prs = [pr(1, world.head1)]
    world.tick()
    world.tick()
    assert len([r for r in world.journal() if r["kind"] == "decision"]) == 1 and st.reads == []
    assert "gate_pending" not in [r for r in world.journal() if r["kind"] == "decision"][0]
