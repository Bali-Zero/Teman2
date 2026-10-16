"""B5-1 / B25-prime P2: a rewritten BASE judge is no verdict; a green BASE read records judge_rewritten_base_ok from structure (TR, TC)."""
from __future__ import annotations

import importlib.util
import itertools
from pathlib import Path

import pytest

from . import test_contexts_exec as ce
from .fixture_repo import runner
from .test_merger import pr, world  # noqa: F401

pytestmark = pytest.mark.usefixtures("fake_env")


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_b5_under_test", Path(runner.__file__).with_name(f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hc, mg = _load("hosted_compare"), _load("merger")
LINT = "scripts/lint.py"
SPEC = {"judge_modified": [ce.JUDGE], "steps": [{"name": "selftest", "trusted": [ce.JUDGE]}, {"name": "judge", "trusted": [ce.JUDGE]},
                                                {"name": "lint", "trusted": [LINT]}]}
TAIL = "; hosted judges with the candidate's copy, which this run did not execute — no verdict (never FAIL, never OK)"


def st(name: str, status: str = "PASS", reason: str = "rc=0") -> dict:
    return {"name": name, "status": status, "reason": reason}


@pytest.mark.parametrize("red", ["FAIL", "ERROR"])
def test_a_red_step_whose_own_judge_is_rewritten_is_blocked_judge_rewritten_never_fail(red):
    got = runner.steps_verdict([st("selftest"), st("judge", red, "rc=1"), st("lint")], SPEC)
    assert got == ("BLOCKED", f"judge_rewritten: judge read red with the BASE judge while the candidate rewrites ['{ce.JUDGE}']{TAIL}")


def test_a_red_step_whose_judge_is_not_rewritten_stays_fail_beside_a_rewritten_one():
    assert runner.steps_verdict([st("selftest"), st("judge"), st("lint", "FAIL", "rc=1")], SPEC) == ("FAIL", "1 step(s) FAIL: lint (rc=1)")
    # both red: the genuine one decides, and only it is named
    assert runner.steps_verdict([st("selftest"), st("judge", "FAIL", "rc=1"), st("lint", "FAIL", "rc=1")], SPEC) == ("FAIL", "1 step(s) FAIL: lint (rc=1)")


def test_without_a_rewritten_judge_a_red_is_a_fail_and_a_green_with_one_is_blocked_as_before():
    clean = {**SPEC, "judge_modified": []}
    assert runner.steps_verdict([st("selftest"), st("judge", "FAIL", "rc=1"), st("lint")], clean) == ("FAIL", "1 step(s) FAIL: judge (rc=1)")
    status, reason = runner.steps_verdict([st("selftest"), st("judge"), st("lint")], SPEC)
    assert status == "BLOCKED" and reason.startswith("3 step(s) rc=0 with the BASE judge") and "no green claimed" in reason


def test_a_rewritten_file_no_step_names_reaches_every_step_and_says_context_scope():
    wf = {**SPEC, "judge_modified": [ce.WF]}   # the workflow itself: every step is defined by it
    assert runner.steps_verdict([st("selftest"), st("judge"), st("lint", "FAIL", "rc=1")], wf) == (
        "BLOCKED", f"judge_rewritten: lint read red with the BASE judge while the candidate rewrites ['{ce.WF}'] "
                   f"(context scope: ['{ce.WF}'] named by no step){TAIL}")
    jobs = {"judge_modified": [ce.WF], "jobs": []}   # a service context's job steps carry no per-step attribution
    status, reason = runner.steps_verdict([st("backend-shard[1] › Run unit tests (sharded)", "FAIL", "rc=1")], jobs)
    assert status == "BLOCKED" and "(context scope: the plan attributes no judge to this step)" in reason


def test_the_plan_names_the_judges_of_each_step(tmp_path):
    spec = ce.plan_spec(ce.planned(tmp_path, {"docs/new.md": "x\n"}, ce.host_ctx()))
    assert [(s["name"], s.get("trusted")) for s in spec["steps"]] == [("selftest", [ce.JUDGE]), ("judge", [ce.JUDGE]), ("guilt control", []),
                                                                       ("pr sentinel", [])]


GH_SUCCESS = [{"name": "Gate", "status": "completed", "conclusion": "success", "app": {"id": 15368, "slug": "github-actions"}}]


@pytest.mark.parametrize("rewrite,klass", [(True, "LOCAL_BLIND"), (False, "FALSE_RED")])
def test_end_to_end_a_red_with_a_rewritten_judge_is_local_blind_and_refused_never_false_red(tmp_path, rewrite, klass):
    # #8076's shape: the candidate rewrites the judge and the surface it judges; the BASE judge reads red, hosted ran the candidate's: green
    cand = {"docs/bad.md": "VIOLATION\n", **({ce.JUDGE: ce.JUDGE_SRC + "# the candidate's contract\n"} if rewrite else {})}
    _, s = ce.ran(tmp_path, cand, ce.host_ctx())
    res = s["contexts"]["results"]["Gate"]
    rep = hc.compare(s, [{"context": "Gate", "app_id": 15368}], GH_SUCCESS, [])
    assert rep["rows"][0]["class"] == klass and rep["counts"]["FALSE_RED"] == (0 if rewrite else 1)
    why = mg.local_side(s)["why"]["executed_contexts_ok"]
    assert why and "Gate" in why   # the C3a-2 criterion refuses both: a no-verdict is not OK, a FAIL is not OK
    if rewrite:
        assert s["checks"]["ctx.judge"]["status"] == "BLOCKED" and res["verdict"] == "BLOCKED" and res["no_verdict"] == "judge_rewritten"
        assert rep["rows"][0]["local_detail"] == "BLOCKED (executed) judge_rewritten" and "Gate" not in s["contexts"]["red"]
    else:
        assert s["checks"]["ctx.judge"]["status"] == "FAIL" and "no_verdict" not in res


# ------------------------------------------------------------------ B25-prime P2: structured no_verdict, TR and TC
TJ = "scripts/tests/test_judge.py"
yaml, fr = ce.yaml, ce.fr
PLAN = {"contexts_status": "ok", "required_contexts": ["Gate"], "contexts_map": {"Gate": {"mapping": "executed", "check": "c"}}}
FORGED = "3 step(s) rc=0 with the BASE judge, but the candidate rewrites ['scripts/judge.py']: hosted judges"


def ran_tj(tmp_path, candidate):
    """ce.ran with the judge living at scripts/tests/test_judge.py (workflow, steps and trusted file all name it)."""
    wf = yaml.safe_dump(ce.WORKFLOW).replace(ce.JUDGE, TJ)
    ctx = ce.host_ctx(trusted_files=[TJ], steps=[
        {"workflow_step": "selftest", "argv": ["$PY", TJ, "--selftest"]}, {"workflow_step": "judge", "argv": ["$PY", TJ], "env": {"BASE_SHA": "$BASE_SHA"}},
        {"workflow_step": "guilt control", "not_applicable": "covered by the contained twin"},
        {"workflow_step": "pr sentinel", "not_applicable": "merge_group runs everything"}])
    fx = fr.make_repo(tmp_path, candidate, {ce.WF: wf, TJ: ce.JUDGE_SRC, "docs/ok.md": "fine\n"})
    fr.plan(fx, "--contexts-file", str(fr.contexts_file(fx, tmp_path / "contexts.yaml", [ctx])))
    fr.run(fx)
    return fr.status(fx)["contexts"]["results"]["Gate"], wf


def test_b25_a_green_read_with_a_rewritten_judge_test_records_judge_rewritten_base_ok(tmp_path):
    res, _ = ran_tj(tmp_path, {"docs/new.md": "clean\n", TJ: ce.JUDGE_SRC + "# the candidate's contract\n"})
    assert (res["verdict"], res.get("no_verdict")) == ("BLOCKED", "judge_rewritten_base_ok")


def test_b25_a_rewritten_workflow_or_judge_script_with_a_green_base_read_is_base_ok_too(tmp_path):
    wf = yaml.safe_dump(ce.WORKFLOW).replace(ce.JUDGE, TJ)
    res, _ = ran_tj(tmp_path, {"docs/new.md": "clean\n", ce.WF: wf + "# the candidate's workflow\n"})
    assert (res["verdict"], res.get("no_verdict")) == ("BLOCKED", "judge_rewritten_base_ok")
    _, s = ce.ran(tmp_path / "j", {"docs/new.md": "clean\n", ce.JUDGE: ce.JUDGE_SRC + "# the candidate's contract\n"}, ce.host_ctx())
    res = s["contexts"]["results"]["Gate"]
    assert (res["verdict"], res.get("no_verdict")) == ("BLOCKED", "judge_rewritten_base_ok")


def test_b25_a_rewritten_workflow_with_a_red_base_read_is_judge_rewritten_never_base_ok(tmp_path):
    wf = yaml.safe_dump(ce.WORKFLOW).replace(ce.JUDGE, TJ)
    res, _ = ran_tj(tmp_path, {"docs/bad.md": "VIOLATION\n", ce.WF: wf + "# the candidate's workflow\n"})
    assert (res["verdict"], res.get("no_verdict")) == ("BLOCKED", "judge_rewritten")


def test_b25_a_red_read_with_a_rewritten_judge_keeps_judge_rewritten_and_is_never_base_ok(tmp_path):
    cand = {"docs/bad.md": "VIOLATION\n", ce.JUDGE: ce.JUDGE_SRC + "# the candidate's contract\n"}
    _, s = ce.ran(tmp_path, cand, ce.host_ctx())
    res = s["contexts"]["results"]["Gate"]
    assert (res["verdict"], res.get("no_verdict")) == ("BLOCKED", "judge_rewritten")


def test_b25_an_untouched_judge_records_no_judge_verdict(tmp_path):
    _, s = ce.ran(tmp_path, {"docs/new.md": "clean\n"}, ce.host_ctx())
    res = s["contexts"]["results"]["Gate"]
    assert res["verdict"] == "OK" and "no_verdict" not in res


@pytest.mark.parametrize("forge", ["blocked_step", "no_steps"])
def test_b25_cmd_run_takes_the_flag_from_the_steps_never_from_any_blocked_or_its_text(tmp_path, monkeypatch, forge):
    real = runner.execute

    def forged(name, spec, run_dir, plan, timeout):
        res = real(name, spec, run_dir, plan, timeout)
        if name != "ctx.judge":
            return res
        if forge == "blocked_step":
            steps = [{"name": "selftest", "status": "PASS", "reason": "rc=0"}, {"name": "judge", "status": "BLOCKED", "reason": FORGED}]
            return {**res, "status": "BLOCKED", "reason": f"1 step(s) BLOCKED: judge ({FORGED})", "steps": steps}
        return {**{k: v for k, v in res.items() if k != "steps"}, "status": "BLOCKED", "reason": f"Gate: service s answered 0 (needs >= 1): {FORGED}"}
    monkeypatch.setattr(runner, "execute", forged)
    fx, s = ce.ran(tmp_path, {"docs/new.md": "clean\n", ce.JUDGE: ce.JUDGE_SRC + "# the candidate's contract\n"}, ce.host_ctx())
    c = ce.fr.load_state(fx)["checks"]["ctx.judge"]
    assert c["status"] == "BLOCKED" and "judge_no_verdict" not in c
    assert "no_verdict" not in s["contexts"]["results"]["Gate"] and mg.local_side(s).get("judge_rewritten_base_ok", []) == []


def test_b25_decision_row_journals_no_verdict_and_leaves_the_context_not_ok(world):  # noqa: F811
    world.runner.doc = {"overall": "BLOCKED", "contexts": {"status": "ok", "required": ["ctx-a", "ctx-b"], "results": {
        "ctx-a": {"verdict": "BLOCKED", "mapping": "executed", "coverage": "full", "no_verdict": "judge_rewritten_base_ok"},
        "ctx-b": {"verdict": "OK", "mapping": "executed", "coverage": "full"}}}}
    world.gh.prs = [pr(1, world.head1), pr(2, world.head2)]
    assert world.tick() == 0
    d1, e1 = [r for r in world.journal() if r["kind"] == "decision"][-1], [r for r in world.journal() if r["kind"] == "would_enqueue"][-1]
    assert d1.get("no_verdict") == {"ctx-a": "judge_rewritten_base_ok"} and e1["criterion"]["executed_contexts_ok"] is False
    world.runner.doc = {"overall": "PASS", "contexts": {"status": "ok", "required": ["ctx-a", "ctx-b"], "results": {
        "ctx-a": {"verdict": "OK", "mapping": "executed", "coverage": "full"},
        "ctx-b": {"verdict": "OK", "mapping": "executed", "coverage": "full"}}}}
    assert world.tick() == 0
    d2 = [r for r in world.journal() if r["kind"] == "decision"][-1]
    assert "no_verdict" not in d2


# ------------------------------------------------------------------ TR: pure runner products against the J2'' oracle
TR_STATUSES = ("PASS", "FAIL", "ERROR", "BLOCKED", "NOT_APPLICABLE", "INTERRUPTED")
TR_STEP_STATUSES = ("PASS", "NOT_APPLICABLE", "FAIL", "ERROR", "BLOCKED", "INTERRUPTED", "STALE", None)
TR_MODS = ((), (TJ,), (ce.WF, ".gitattributes"))
TR_REASONS = ("rc=0", FORGED)


def _oracle_judge_rc0(status: str, step_sts: tuple, mod: tuple) -> str | None:
    if status == "BLOCKED" and mod and step_sts and "PASS" in step_sts and all(x in ("PASS", "NOT_APPLICABLE") for x in step_sts):
        return "judge_rewritten_base_ok"
    return None


def test_tr_judge_rc0_of_product():
    step_lists = [()] + [(a,) for a in TR_STEP_STATUSES] + list(itertools.product(TR_STEP_STATUSES, repeat=2))
    assert len(step_lists) == 73
    mismatches, total = [], 0
    for status in TR_STATUSES:
        for step_sts in step_lists:
            for mod in TR_MODS:
                for reason in TR_REASONS:
                    total += 1
                    steps = [{"name": f"s{i}", **({"status": x} if x is not None else {}), "reason": reason} for i, x in enumerate(step_sts)]
                    got = runner.judge_rc0_of(status, steps, {"judge_modified": list(mod)})
                    want = _oracle_judge_rc0(status, step_sts, mod)
                    if got != want:
                        mismatches.append(f"{status}|{step_sts}|{len(mod)}|{'forged' if reason == FORGED else 'plain'}: got={got!r} want={want!r}")
    assert total == 2628
    assert not mismatches, f"{len(mismatches)}/{total} TR judge_rc0_of mismatches:\n" + "\n".join(mismatches[:25])


EVAL_STATUSES = ("PASS", "NOT_APPLICABLE", "FAIL", "ERROR", "BLOCKED", "STALE", "INTERRUPTED")
EVAL_REASONS = (
    ("plain", "1 step(s) rc=0"),
    ("jr_prefix", f"judge_rewritten: judge read red with the BASE judge{TAIL}"),
    ("host", "host_disk_full: 1 line(s) in log"),
    ("forged", f"1 step(s) BLOCKED: judge (judge_rewritten: {FORGED})"),
)
EVAL_FLAGS = (None, "judge_rewritten_base_ok", "judge_rewritten", "other")


def _oracle_eval(s: str, rkind: str, flag: str | None, gp: bool) -> tuple[str, str | None]:
    verdict = "OK" if s in ("PASS", "NOT_APPLICABLE") else s
    if s in ("ERROR", "BLOCKED") and rkind == "host":
        nv = "host_disk_full"
    elif s == "BLOCKED" and rkind == "jr_prefix":
        nv = "judge_rewritten"
    elif s == "BLOCKED" and flag in ("judge_rewritten_base_ok", "judge_rewritten"):
        nv = flag
    elif s == "BLOCKED" and gp is True:
        nv = "gate_pending"
    else:
        nv = None
    return verdict, nv


def test_tr_evaluate_contexts_product():
    mismatches, total = [], 0
    for s in EVAL_STATUSES:
        for rkind, reason in EVAL_REASONS:
            for flag in EVAL_FLAGS:
                for gp in (False, True):
                    total += 1
                    chk = {"status": s, "reason": reason, **({"judge_no_verdict": flag} if flag is not None else {}),
                           **({"gate_pending": True} if gp else {})}
                    res = runner.evaluate_contexts({"c": chk}, PLAN)["results"]["Gate"]
                    got = (res["verdict"], res.get("no_verdict"))
                    want = _oracle_eval(s, rkind, flag, gp)
                    if got != want:
                        mismatches.append(f"{s}|{rkind}|{flag}|{gp}: got={got!r} want={want!r}")
    assert total == 224
    assert not mismatches, f"{len(mismatches)}/{total} TR evaluate_contexts mismatches:\n" + "\n".join(mismatches[:25])


# ------------------------------------------------------------------ TC: steps_verdict -> judge_rc0_of -> evaluate_contexts -> local_side
TC_MODS = (("judge_test", [TJ]), ("workflow", [ce.WF]), ("gitattributes", [".gitattributes"]), ("none", []))
TC_STEPS = (
    ("PASS", ("PASS", "rc=0")),
    ("FAIL", ("FAIL", "rc=1")),
    ("ERROR", ("ERROR", "crashed")),
    ("BLOCKED_FORGED", ("BLOCKED", FORGED)),
    ("NA_WRITTEN", ("NOT_APPLICABLE", "if: false -> false")),
    ("NA_EMPTY", ("NOT_APPLICABLE", "")),
)


def test_tc_runner_to_merger_chain_product():
    step_seqs = [(a,) for a in TC_STEPS] + list(itertools.product(TC_STEPS, repeat=2))
    assert len(step_seqs) == 42
    mismatches, total = [], 0
    for mname, mod in TC_MODS:
        spec = {"judge_modified": mod, "steps": [{"name": "s0", "trusted": [TJ]}, {"name": "s1", "trusted": []}]}
        for seq in step_seqs:
            total += 1
            kinds = [k for k, _ in seq]
            steps = [{"name": f"s{i}", "status": st_val, "reason": r_val} for i, (_, (st_val, r_val)) in enumerate(seq)]
            status, reason = runner.steps_verdict(steps, spec)
            flag = runner.judge_rc0_of(status, steps, spec)
            view = {"c": {"status": status, "reason": reason, **({"judge_no_verdict": flag} if flag else {})}}
            res = runner.evaluate_contexts(view, PLAN)["results"]["Gate"]
            loc = mg.local_side({"checks": {"c": {"status": status}, "review.independent": {"status": "QUEUED"}},
                                 "contexts": {"status": "ok", "required": ["Gate"], "results": {"Gate": {**res, "coverage": "full"}}}})
            green_steps = all(k in ("PASS", "NA_WRITTEN") for k in kinds) and ("PASS" in kinds)
            want_base_ok = bool(mod) and green_steps
            want_ok = (not mod) and green_steps
            got = (
                flag == "judge_rewritten_base_ok",
                res.get("no_verdict") == "judge_rewritten_base_ok",
                res["verdict"] == "OK",
                loc["why"]["executed_contexts_ok"] is None,
            )
            want = (want_base_ok, want_base_ok, want_ok, want_ok)
            if got != want:
                mismatches.append(f"{mname}|{'+'.join(kinds)}: got={got!r} want={want!r} (status={status!r}, flag={flag!r}, res={res!r})")
    assert total == 168
    assert not mismatches, f"{len(mismatches)}/{total} TC chain mismatches:\n" + "\n".join(mismatches[:25])
