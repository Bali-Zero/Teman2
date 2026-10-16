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


def test_a_new_base_is_a_new_key_but_a_gate_pending_head_waits_for_its_gate_first():   # B23 T2
    assert run_triage([dec(True)], False, base=B2) == ([], [(1, H)])
    assert run_triage([dec(True)], True, base=B2) == ([1], [(1, H)])
    assert run_triage([dec(False)], False, base=B2) == ([1], [])   # T4: a head that was not gate_pending is a new key as before


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


# ------------------------------------------------------------------ B25-prime P4: matrix argv, runner $GATE_LEDGER / $HEAD, container spy, merger run_gate
def _write_pro_ledger(path, entries, mode=0o600):
    path.write_text("".join(json.dumps(e, separators=(",", ":")) + "\n" for e in entries), encoding="utf-8")
    path.chmod(mode)
    return path


def _pro_entry(sha, verdict="success", repo="Bali-Zero/Teman2", pr_num=42):
    return {
        "v": 1, "ts": "2026-10-16T12:00:00Z", "repo": repo, "pr": pr_num, "head_sha": sha,
        "verdict": verdict, "gate_session": "s1", "evidence_sha256": "e" * 64, "supersedes": None, "via": "local",
    }


def test_b25p4_matrix_declares_ledger_and_head_and_gate_ledger_trusted_file():
    import yaml
    doc = yaml.safe_load(runner.Path(runner.__file__).with_name("contexts_matrix.yaml").read_text())
    (hf,) = [c for c in doc["contexts"] if c["name"] == "Harness floor recompute"]
    assert hf["local"]["trusted_files"] == ["scripts/ci/harness_gate_read.py", "scripts/localci/gate_ledger.py"]
    (host,) = [s for s in hf["local"]["steps"] if s.get("side") == "host"]
    assert host["argv"][-4:] == ["--ledger", "$GATE_LEDGER", "--head", "$HEAD"]


@pytest.mark.usefixtures("fake_env")
def test_b25p4_plan_expands_gate_ledger_and_head_and_ignores_github_status_when_ledger_given(tmp_path, monkeypatch):
    """Guilt + innocence (P4 spec §2b.5):
    - GitHub commit status says 'success', but an empty ledger at $GATE_LEDGER reads PENDING locally (rc=None, gate_pending=True).
    - A ledger with 'success' for $HEAD reads rc=0, and the planned host step shows --ledger <path> --head <decided_head>.
    - A live head different from $HEAD reads rc=1 (not gate_pending)."""
    import os
    import yaml
    from .test_service_contexts import WORKFLOW, WF, svc_ctx

    real_hgr = (runner.Path(runner.__file__).resolve().parents[2] / "scripts" / "ci" / "harness_gate_read.py").read_text()
    real_gl = (runner.Path(runner.__file__).resolve().parents[2] / "scripts" / "localci" / "gate_ledger.py").read_text()
    decided_head = "a" * 40
    live_head_file = tmp_path / "live_head"
    live_head_file.write_text(decided_head)

    # Fake `gh` in PATH: returns live_head for `pr view` and ALWAYS returns `success` for commit status!
    gh_bin = tmp_path / "bin" / "gh"
    gh_bin.parent.mkdir(parents=True, exist_ok=True)
    gh_bin.write_text(
        f'#!/bin/sh\n'
        f'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
        f'  printf \'{{"headRefOid": "%s"}}\\n\' "$(cat {live_head_file})"\n'
        f'  exit 0\n'
        f'fi\n'
        f'printf \'{{"statuses": [{{"context": "harness/fable-gate", "state": "success", "description": "PASS"}}]}}\\n\'\n'
    )
    gh_bin.chmod(0o755)
    monkeypatch.setenv("PATH", f"{gh_bin.parent}{os.pathsep}{os.environ['PATH']}")

    wf = {**WORKFLOW, "jobs": {"fanin": {"name": "Fan In", "runs-on": "ubuntu-latest", "steps": [
        {"name": "assert", "run": "true"},
        {"name": "verdict", "env": {"GH_TOKEN": "${{ github.token }}"}, "run": "python3 scripts/ci/harness_gate_read.py"},
    ]}}}
    base_files = {
        WF: yaml.safe_dump(wf),
        "scripts/ci/harness_gate_read.py": real_hgr,
        "scripts/localci/gate_ledger.py": real_gl,
    }
    ctx = svc_ctx(
        jobs=[],
        trusted_files=["scripts/ci/harness_gate_read.py", "scripts/localci/gate_ledger.py"],
        steps=[
            {"workflow_step": "assert"},
            {
                "workflow_step": "verdict",
                "side": "host",
                "argv": [
                    "$PY", "scripts/ci/harness_gate_read.py",
                    "--event-name", "merge_group",
                    "--repo", "${{ github.repository }}",
                    "--pr-head-sha", "",
                    "--merge-group-head-ref", "${{ github.event.merge_group.head_ref }}",
                    "--dispatch-sha", "",
                    "--ledger", "$GATE_LEDGER",
                    "--head", "$HEAD",
                ],
                "env": {"GH_TOKEN": ""},
                "no_verdict_when": CNV,
                "pending_when": PEND,
            },
        ],
    )

    # 1. Empty ledger + GitHub status=success -> PENDING locally (rc=None, gate_pending=True)
    empty_ledger = _write_pro_ledger(tmp_path / "empty.jsonl", [])
    spec_pend = planned_svc(
        tmp_path / "pend", monkeypatch, fr.CANDIDATE_FILES, ctx, base_files,
        "--pr-number", "42", "--gate-ledger", str(empty_ledger), "--head", decided_head,
    )
    step_pend = spec_pend["jobs"][0]["steps"][1]
    assert step_pend["precomputed"]["rc"] is None and step_pend["precomputed"].get("gate_pending") is True
    assert step_pend["side"]["argv"][-4:] == ["--ledger", str(empty_ledger), "--head", decided_head]
    tdir = tmp_path / "pend" / "run" / "state" / "trusted" / "ctx" / "ctx.fan-in"
    assert (tdir / "scripts/ci/harness_gate_read.py").is_file() and (tdir / "scripts/localci/gate_ledger.py").is_file()

    # 2. Ledger success -> rc=0
    ok_ledger = _write_pro_ledger(tmp_path / "ok.jsonl", [_pro_entry(decided_head, "success")])
    spec_ok = planned_svc(
        tmp_path / "ok", monkeypatch, fr.CANDIDATE_FILES, ctx, base_files,
        "--pr-number", "42", "--gate-ledger", str(ok_ledger), "--head", decided_head,
    )
    step_ok = spec_ok["jobs"][0]["steps"][1]
    assert step_ok["precomputed"]["rc"] == 0 and "gate_pending" not in step_ok["precomputed"]
    assert step_ok["side"]["argv"][-4:] == ["--ledger", str(ok_ledger), "--head", decided_head]

    # 3. Live head != decided head -> rc=1 (false, not PENDING)
    live_head_file.write_text("b" * 40)
    both_ledger = _write_pro_ledger(tmp_path / "both.jsonl", [_pro_entry(decided_head, "success"), _pro_entry("b" * 40, "success")])
    spec_mismatch = planned_svc(
        tmp_path / "mismatch", monkeypatch, fr.CANDIDATE_FILES, ctx, base_files,
        "--pr-number", "42", "--gate-ledger", str(both_ledger), "--head", decided_head,
    )
    step_mismatch = spec_mismatch["jobs"][0]["steps"][1]
    assert step_mismatch["precomputed"]["rc"] == 1 and "gate_pending" not in step_mismatch["precomputed"]


@pytest.mark.usefixtures("fake_env")
def test_b25p4_plan_blocks_when_trusted_helper_missing_or_ledger_or_head_invalid(tmp_path, monkeypatch):
    """Guilt: if a secondary file in `trusted_files` is absent at BASE, or `$GATE_LEDGER` / `$HEAD`
    receives an empty/non-hex value, `plan_service_context` returns BLOCKED."""
    import yaml
    from .test_service_contexts import WORKFLOW, WF, svc_ctx

    wf = {**WORKFLOW, "jobs": {"fanin": {"name": "Fan In", "runs-on": "ubuntu-latest", "steps": [
        {"name": "assert", "run": "true"}, {"name": "verdict", "run": "python3 scripts/ci/read.py"}]}}}
    base_missing_helper = {WF: yaml.safe_dump(wf), READER: "raise SystemExit(0)\n"}
    ctx = svc_ctx(
        jobs=[],
        trusted_files=[READER, "scripts/localci/gate_ledger.py"],
        steps=[{"workflow_step": "assert"}, {"workflow_step": "verdict", "side": "host", "argv": ["$PY", READER, "$GATE_LEDGER", "$HEAD"]}],
    )
    spec = planned_svc(tmp_path / "missing_tf", monkeypatch, fr.CANDIDATE_FILES, ctx, base_missing_helper)
    assert spec["status"] == "BLOCKED" and "trusted file present at BASE" in spec["reason"]

    base_both = {**base_missing_helper, "scripts/localci/gate_ledger.py": "# stub\n"}
    spec_empty_ledger = planned_svc(tmp_path / "empty_l", monkeypatch, fr.CANDIDATE_FILES, ctx, base_both, "--gate-ledger", "")
    assert spec_empty_ledger["status"] == "BLOCKED" and "$GATE_LEDGER" in spec_empty_ledger["reason"]

    with pytest.raises(SystemExit):
        planned_svc(tmp_path / "bad_h", monkeypatch, fr.CANDIDATE_FILES, ctx, base_both, "--head", "not-a-sha")


def test_b25p4_container_argv_env_and_steps_json_never_contain_the_ledger_path(tmp_path, monkeypatch):
    """Guilt (P4 spec §2b.5): spy on `docker create` and container inputs — the runner's container
    argv, env, and `/cfg/steps.json` never contain the host ledger path."""
    from .test_service_contexts import fake_docker

    secret_ledger = "/Users/pro-secret/.nuzantara-pilots/local-ci-gate/verdicts.jsonl"
    docker_exe = fake_docker(tmp_path)
    docker_env_log = tmp_path / "docker.env"
    docker_exe.write_text(
        docker_exe.read_text().replace(
            'printf \'%s\\n\' "$*" >>',
            f'env >> {docker_env_log}\nprintf \'%s\\n\' "$*" >>',
        )
    )
    for d in ("receipts", "logs", "work"):
        (tmp_path / d).mkdir(exist_ok=True)
    (tmp_path / "work" / "a.txt").write_text("hi\n")

    captured_contained = {}
    real_exec_contained = runner.execute_contained

    def spy_execute_contained(name, spec, run_dir, plan, inner, overrides, extra, env, log, junit, *a, **kw):
        captured_contained["inner"] = list(inner)
        captured_contained["env"] = dict(env)
        captured_contained["steps_json"] = extra["cfg/steps.json"].decode("utf-8")
        # Also invoke the real `execute_contained` against `fake_docker` so `docker create` is actually called and logged!
        suite = runner.ET.Element("testsuite")
        runner.ET.SubElement(suite, "testcase", name= GATE_STEP)
        (tmp_path / "seed.xml").write_bytes(runner.ET.tostring(suite))
        return real_exec_contained(name, spec, run_dir, plan, inner, overrides, extra, env, log, junit, *a, **kw)

    monkeypatch.setattr(runner, "execute_contained", spy_execute_contained)
    monkeypatch.setattr(runner, "stream_tree_tar", lambda *a, **k: 0)
    monkeypatch.setattr(runner, "disk_floor_refusal", lambda *a: None)
    monkeypatch.setattr(runner, "start_services", lambda *a: ([], None, None))

    host_step = {
        "name": GATE_STEP,
        "argv": ["$PY", "scripts/ci/harness_gate_read.py", "--ledger", "$GATE_LEDGER", "--head", "$HEAD"],
        "side": {"where": "host", "argv": [sys.executable, "-I", "/trusted/harness_gate_read.py", "--ledger", secret_ledger, "--head", "a" * 40], "base_sha256": "0" * 64},
        "precomputed": {"rc": 0, "reason": "host, at plan: BASE harness_gate_read.py rc=0", "log": ""},
    }
    job = {
        "job_id": "harness-floor", "legs": [{}], "needs": [], "steps": [host_step],
        "path_prefix": "", "venv": False, "job_env": {}, "services": [],
        "image_id": "sha256:" + "a" * 64, "timeout_s": 60, "git_index": False, "checkout": None,
    }
    spec = {
        "context": "Harness floor recompute", "jobs": [job], "needs": {}, "judge_modified": [],
        "history": None, "expr": {"github": {}, "runner": {"temp": "/tmp"}},
        "isolation": {"mode": "container", "docker": str(docker_exe), "image_id": "sha256:" + "a" * 64, "user": "65534:65534"},
        "driver_sha256": runner.sha256_bytes(runner.STEPS_DRIVER.read_bytes()),
        "expr_sha256": runner.sha256_bytes(runner.GH_EXPR.read_bytes()),
    }
    plan = {"run_id": "r1", "worktree": str(tmp_path / "work"), "candidate_sha": "c" * 40}
    runner._run_leg("ctx.harness-floor", spec, job, {}, tmp_path, plan, {}, {}, runner._gh_expr())

    docker_calls = (tmp_path / "docker.argv").read_text()
    create_calls = [ln for ln in docker_calls.splitlines() if ln.startswith("create ")]
    assert create_calls, f"expected at least one `docker create` call, got: {docker_calls}"
    assert secret_ledger not in docker_calls
    assert secret_ledger not in docker_env_log.read_text()
    assert secret_ledger not in " ".join(captured_contained["inner"])
    assert secret_ledger not in json.dumps(captured_contained["env"])
    assert secret_ledger not in captured_contained["steps_json"]
    assert '"side"' not in captured_contained["steps_json"]
    # And the original step in `job["steps"]` (which lives in plan.json on the host) still holds `side.argv` with the ledger path:
    assert host_step["side"]["argv"][-3] == secret_ledger


def test_b25p4_merger_run_gate_passes_gate_ledger_and_head_only_when_base_runner_takes_them(tmp_path, monkeypatch):
    """Innocence + guilt: `mg.run_gate` passes `--gate-ledger` and `--head` to `runner plan` when
    the BASE runner declares them, and omits them when the BASE runner does not."""
    base_wt, cand, run_dir = tmp_path / "base", tmp_path / "cand", tmp_path / "run"
    (base_wt / "scripts" / "localci").mkdir(parents=True)
    cand.mkdir()
    (base_wt / "scripts" / "localci" / "runner.py").write_text(
        'p.add_argument("--pr-number")\np.add_argument("--gate-ledger")\np.add_argument("--head")\n'
    )
    seen_plans = []

    def fake_exec(argv, cwd, env, timeout, **kw):
        if argv[3] == "plan":
            seen_plans.append(list(argv))
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[3] == "run":
            (run_dir / "status.json").write_text(json.dumps({
                "candidate_sha": "c" * 40, "base_sha": "b" * 40, "seal": "f" * 64, "overall": "PASS",
            }))
            return subprocess.CompletedProcess(argv, 0, f"seal={'f' * 64}\n", "")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(mg, "runner_exec", fake_exec)
    a = mg.argparse.Namespace(
        python=sys.executable, host_floor_gb=0, docker="docker",
        plan_timeout=60, run_timeout=60, gate_ledger=str(tmp_path / "custom-ledger.jsonl"),
    )
    out = mg.run_gate(a, base_wt, cand, run_dir, "b" * 40, "c" * 40, 42, "d" * 40)
    assert out["status"]["overall"] == "PASS"
    assert "--gate-ledger" in seen_plans[-1] and str(tmp_path / "custom-ledger.jsonl") in seen_plans[-1]
    assert "--head" in seen_plans[-1] and "d" * 40 in seen_plans[-1]

    # Legacy BASE runner without --gate-ledger / --head: neither flag is passed
    (base_wt / "scripts" / "localci" / "runner.py").write_text('p.add_argument("--pr-number")\n')
    run_dir2 = tmp_path / "run2"

    def fake_exec2(argv, cwd, env, timeout, **kw):
        if argv[3] == "plan":
            seen_plans.append(list(argv))
        return subprocess.CompletedProcess(argv, 1, "", "stop")

    monkeypatch.setattr(mg, "runner_exec", fake_exec2)
    mg.run_gate(a, base_wt, cand, run_dir2, "b" * 40, "c" * 40, 42, "d" * 40)
    assert "--gate-ledger" not in seen_plans[-1] and "--head" not in seen_plans[-1]

