"""Required contexts the runner EXECUTES (v0.4.0): every BASE workflow step accounted for, BASE judges, guilt and innocence."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml

from . import fixture_repo as fr
from .fixture_repo import runner

pytestmark = pytest.mark.usefixtures("fake_env")
needs_docker = pytest.mark.skipif(not fr.docker_image_ready(), reason=f"docker image {fr.ISOLATION_IMAGE} unavailable — contained steps are proven live on Pro")

WF = ".github/workflows/gate.yml"
JUDGE = "scripts/judge.py"
JUDGE_SRC = ("import pathlib, sys\n"
             "if '--selftest' in sys.argv:\n    sys.exit(0)\n"
             "bad = [str(p) for p in pathlib.Path('docs').rglob('*.md') if 'VIOLATION' in p.read_text()]\n"
             "print('violations:', bad)\nsys.exit(1 if bad else 0)\n")
GUILT = ("set -euo pipefail\ncp docs/ok.md /tmp/ok.orig\necho VIOLATION >> docs/ok.md\n"
         "if python scripts/judge.py; then echo 'guard stayed green'; exit 1; fi\n"
         "cp /tmp/ok.orig docs/ok.md\ngit diff --exit-code -- docs/ok.md\npython scripts/judge.py\n")
WORKFLOW = {"name": "gate", "on": {"pull_request": None}, "jobs": {"gate": {"name": "Gate", "runs-on": "ubuntu-latest", "env": {"TOOL_VERSION": "1.2.3"}, "steps": [
    {"uses": "actions/checkout@v7"},
    {"name": "selftest", "run": "python scripts/judge.py --selftest"},
    {"name": "judge", "run": "python scripts/judge.py", "env": {"BASE_SHA": "${{ github.event.pull_request.base.sha }}"}},
    {"name": "guilt control", "run": GUILT},
    {"name": "pr sentinel", "run": "echo ${{ github.event_name }}"}]}}}
BASE_EXTRA = {WF: yaml.safe_dump(WORKFLOW), JUDGE: JUDGE_SRC, "docs/ok.md": "fine\n"}


def host_ctx(**over) -> dict:
    local = {"check": "ctx.judge", "where": "host", "trusted_files": [JUDGE], "steps": [
        {"workflow_step": "selftest", "argv": ["$PY", JUDGE, "--selftest"]},
        {"workflow_step": "judge", "argv": ["$PY", JUDGE], "env": {"BASE_SHA": "$BASE_SHA"}},
        {"workflow_step": "guilt control", "not_applicable": "covered by the contained twin"},
        {"workflow_step": "pr sentinel", "not_applicable": "merge_group runs everything"}]}
    local.update(over)
    return {"name": "Gate", "workflow_file": WF, "job_id": "gate", "mapping": "executed", "local": local}


def contained_ctx(**over) -> dict:
    local = {"check": "ctx.judge", "where": "container", "git_index": True, "trusted_files": [JUDGE], "steps": [
        {"workflow_step": "selftest"}, {"workflow_step": "judge", "env": {"BASE_SHA": "$BASE_SHA"}}, {"workflow_step": "guilt control"},
        {"workflow_step": "pr sentinel", "not_applicable": "merge_group runs everything"}]}
    local.update(over)
    return {"name": "Gate", "workflow_file": WF, "job_id": "gate", "mapping": "executed", "local": local}


def planned(tmp_path: Path, candidate: dict, ctx: dict, *extra: str) -> dict:
    fx = fr.make_repo(tmp_path, candidate, BASE_EXTRA)
    fr.plan(fx, "--contexts-file", str(fr.contexts_file(fx, tmp_path / "contexts.yaml", [ctx])), *extra)
    return fx


def ran(tmp_path: Path, candidate: dict, ctx: dict, *extra: str) -> tuple[dict, dict]:
    fx = planned(tmp_path, candidate, ctx, *extra)
    fr.run(fx)
    return fx, fr.status(fx)


def plan_spec(fx: dict) -> dict:
    return json.loads((fx["run"] / "state" / "plan.json").read_text())["checks"]["ctx.judge"]


# --------------------------------------------------------------- host: BASE judge, candidate tree as data
def test_a_host_context_runs_every_step_from_base_and_passes_a_clean_candidate(tmp_path):
    fx, s = ran(tmp_path, {"docs/new.md": "clean\n"}, host_ctx())
    c = s["checks"]["ctx.judge"]
    assert c["status"] == "PASS" and s["contexts"]["results"]["Gate"] == {"mapping": "executed", "check": "ctx.judge", "verdict": "OK"}
    assert [x["status"] for x in c["steps"]] == ["PASS", "PASS", "NOT_APPLICABLE", "NOT_APPLICABLE"]
    spec = plan_spec(fx)
    assert spec["kind"] == "trusted_steps" and runner.is_trusted_check(spec) and "trusted_steps" in runner.SEALED_KINDS
    assert spec["steps"][1]["argv"][1:] == ["-I", str(fx["run"].resolve() / "state" / "trusted" / "ctx" / "ctx.judge" / JUDGE)]
    assert spec["steps"][1]["env"]["BASE_SHA"] == fx["base"]


def test_a_violation_turns_the_context_red(tmp_path):
    _, s = ran(tmp_path, {"docs/bad.md": "VIOLATION\n"}, host_ctx())
    assert s["checks"]["ctx.judge"]["status"] == "FAIL" and s["contexts"]["red"] == ["Gate"] and s["overall"] == "FAIL"


def test_a_candidate_cannot_swap_the_judge_that_runs_on_the_host(tmp_path):
    _, s = ran(tmp_path, {JUDGE: "import sys\nsys.exit(0)\n", "docs/bad.md": "VIOLATION\n"}, host_ctx())
    assert s["checks"]["ctx.judge"]["status"] == "FAIL"


def test_a_green_won_while_the_candidate_rewrites_its_judge_is_blocked_not_pass(tmp_path):
    _, s = ran(tmp_path, {JUDGE: JUDGE_SRC + "# tweak\n"}, host_ctx())
    c = s["checks"]["ctx.judge"]
    assert c["status"] == "BLOCKED" and JUDGE in c["reason"] and "Gate" in s["contexts"]["blocked"]


def test_a_rewritten_workflow_counts_as_a_rewritten_judge(tmp_path):
    _, s = ran(tmp_path, {WF: yaml.safe_dump(WORKFLOW) + "# tweak\n"}, host_ctx())
    assert s["checks"]["ctx.judge"]["status"] == "BLOCKED" and WF in s["checks"]["ctx.judge"]["reason"]


@pytest.mark.parametrize("steps,needle", [
    ([{"workflow_step": "judge", "argv": ["$PY", JUDGE], "env": {"BASE_SHA": "$BASE_SHA"}}], "not mapped"),
    ([{"workflow_step": "selftest", "not_run": "no tool here"}, {"workflow_step": "judge", "argv": ["$PY", JUDGE], "env": {"BASE_SHA": "x"}},
      {"workflow_step": "guilt control", "not_applicable": "x"}, {"workflow_step": "pr sentinel", "not_applicable": "x"}], "not run locally"),
    ([{"workflow_step": "selftest", "argv": ["$PY", JUDGE]}, {"workflow_step": "judge", "argv": ["$PY", JUDGE]},
      {"workflow_step": "guilt control", "not_applicable": "x"}, {"workflow_step": "pr sentinel", "not_applicable": "x"}], "expressions"),
    ([{"workflow_step": "no such step", "argv": ["$PY", JUDGE]}], "absent from the BASE job"),
    ([{"workflow_step": "selftest", "argv": ["$PY", "scripts/candidate_owned.py"]}, {"workflow_step": "judge", "argv": ["$PY", JUDGE], "env": {"BASE_SHA": "x"}},
      {"workflow_step": "guilt control", "not_applicable": "x"}, {"workflow_step": "pr sentinel", "not_applicable": "x"}], "only `$PY <trusted file>`"),
    ([{"workflow_step": "selftest"}, {"workflow_step": "judge", "argv": ["$PY", JUDGE], "env": {"BASE_SHA": "x"}},
      {"workflow_step": "guilt control", "not_applicable": "x"}, {"workflow_step": "pr sentinel", "not_applicable": "x"}], "only `$PY <trusted file>`"),
])
def test_a_context_that_cannot_be_planned_honestly_is_blocked_with_its_reason(tmp_path, steps, needle):
    fx = planned(tmp_path, {"docs/new.md": "clean\n"}, host_ctx(steps=steps))
    spec = plan_spec(fx)
    assert spec["kind"] == "record" and spec["status"] == "BLOCKED" and needle in spec["reason"], spec


@pytest.mark.parametrize("files,needle", [([JUDGE, "scripts/new_judge.py"], "missing at base"), ([JUDGE, "../outside.py"], "unsafe tree entry path")])
def test_a_trusted_file_missing_at_base_or_outside_the_tree_is_blocked(tmp_path, files, needle):
    fx = planned(tmp_path, {"scripts/new_judge.py": "pass\n"}, host_ctx(trusted_files=files))
    assert plan_spec(fx)["status"] == "BLOCKED" and needle in plan_spec(fx)["reason"]


def _tool(tmp_path: Path, monkeypatch, version: str) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    tool = bindir / "localci-faketool"
    tool.write_text(f"#!/bin/sh\n[ \"$1\" = -version ] && echo {version}\nexit 0\n")
    tool.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    return tool


def tool_ctx() -> dict:
    return host_ctx(tool_pins={"localci-faketool": "TOOL_VERSION"}, steps=[
        {"workflow_step": "selftest", "argv": ["localci-faketool", "--check"]},
        {"workflow_step": "judge", "argv": ["$PY", JUDGE], "env": {"BASE_SHA": "$BASE_SHA"}},
        {"workflow_step": "guilt control", "not_applicable": "x"}, {"workflow_step": "pr sentinel", "not_applicable": "x"}])


@pytest.mark.parametrize("version,want", [("1.2.3", "PASS"), ("9.9.9", "BLOCKED"), (None, "BLOCKED")])
def test_a_host_tool_runs_only_at_the_version_the_base_workflow_pins(tmp_path, monkeypatch, version, want):
    if version:
        _tool(tmp_path, monkeypatch, version)
    _, s = ran(tmp_path, {"docs/new.md": "clean\n"}, tool_ctx())
    c = s["checks"]["ctx.judge"]
    assert c["status"] == want, c
    if want == "BLOCKED":
        assert "TOOL_VERSION='1.2.3'" in c["reason"]


def test_a_step_that_cannot_start_is_blocked_never_pass(tmp_path, monkeypatch):
    tool = _tool(tmp_path, monkeypatch, "1.2.3")
    fx = planned(tmp_path, {"docs/new.md": "clean\n"}, tool_ctx())
    tool.unlink()
    fr.run(fx)
    c = fr.status(fx)["checks"]["ctx.judge"]
    assert c["status"] == "BLOCKED" and "could not start" in c["reason"]


def test_a_tampered_trusted_dir_is_error(tmp_path):
    fx = planned(tmp_path, {"docs/bad.md": "VIOLATION\n"}, host_ctx())
    (fx["run"] / "state" / "trusted" / "ctx" / "ctx.judge" / JUDGE).write_text("import sys\nsys.exit(0)\n")
    fr.run(fx)
    c = fr.status(fx)["checks"]["ctx.judge"]
    assert c["status"] == "ERROR" and "tampered" in c["reason"]


def test_an_executed_context_without_a_valid_check_name_refuses_the_plan(tmp_path):
    with pytest.raises(SystemExit, match="local.check"):
        planned(tmp_path, {"docs/new.md": "clean\n"}, host_ctx(check="policy.forged"))


def test_contained_steps_never_run_without_a_container(tmp_path):
    fx = planned(tmp_path, {"docs/new.md": "clean\n"}, contained_ctx())
    assert plan_spec(fx)["status"] == "BLOCKED" and "--isolation container" in plan_spec(fx)["reason"]


@pytest.mark.parametrize("rc,junit,want", [
    (0, [("selftest", "PASS"), ("judge", "PASS"), ("guilt control", "PASS"), ("pr sentinel", "NOT_APPLICABLE")], "PASS"),
    (1, [("selftest", "PASS"), ("judge", "FAIL"), ("guilt control", "PASS"), ("pr sentinel", "NOT_APPLICABLE")], "FAIL"),
    (3, [("selftest", "BLOCKED"), ("judge", "PASS"), ("guilt control", "PASS"), ("pr sentinel", "NOT_APPLICABLE")], "BLOCKED"),
    (4, [("selftest", "BLOCKED"), ("judge", "ERROR"), ("guilt control", "PASS"), ("pr sentinel", "NOT_APPLICABLE")], "ERROR"),   # killed by a signal
    (1, [("selftest", "PASS"), ("judge", "ERROR"), ("guilt control", "PASS"), ("pr sentinel", "NOT_APPLICABLE")], "ERROR"),
    (0, [("selftest", "PASS"), ("judge", "FAIL"), ("guilt control", "PASS"), ("pr sentinel", "NOT_APPLICABLE")], "ERROR"),   # rc contradicts junit
    (0, [("selftest", "PASS"), ("judge", "PASS")], "ERROR"),                                                                   # a step went missing
    (0, [("selftest", "PASS"), ("judge", "PASS"), ("guilt control", "PASS"), ("pr sentinel", "PASS")], "ERROR"),             # N/A step reported as run
    (2, None, "ERROR"), (0, None, "ERROR"), (None, None, "ERROR"),
])
def test_the_driver_exit_code_and_its_junit_must_agree(rc, junit, want):
    spec = runner.resolve_steps(WORKFLOW["jobs"]["gate"], contained_ctx()["local"], "b" * 40)[0]
    steps = None if junit is None else [{"name": n, "status": st, "reason": "r"} for n, st in junit]
    assert runner.classify_contained_steps(rc, steps, {"steps": spec, "judge_modified": []})[0] == want


def _job(**over) -> dict:
    job = json.loads(json.dumps(WORKFLOW["jobs"]["gate"]))
    job.update(over)
    return job


def test_duplicate_step_names_are_refused_rather_than_collapsed():
    job = _job(steps=WORKFLOW["jobs"]["gate"]["steps"] + [{"name": "selftest", "run": "exit 1"}])
    steps, why = runner.resolve_steps(job, contained_ctx()["local"], "b" * 40)
    assert steps is None and "duplicate step names ['selftest']" in why


@pytest.mark.parametrize("shell,argv", [(None, ["bash", "-e", "{0}"]), ("bash", ["bash", "--noprofile", "--norc", "-eo", "pipefail", "{0}"]), ("sh", None)])
def test_a_verbatim_body_runs_from_a_file_under_githubs_own_shell_template(shell, argv):
    job = _job(defaults={"run": {"shell": shell}} if shell else {})
    steps, why = runner.resolve_steps(job, contained_ctx()["local"], "b" * 40)
    if argv is None:
        assert steps is None and "shell='sh'" in why
    else:
        assert steps[0]["argv"] == argv and steps[0]["script"] == "python scripts/judge.py --selftest" and "-c" not in steps[0]["argv"]


def test_working_directory_comes_from_the_step_or_the_job_default_and_stays_in_the_tree():
    steps, _ = runner.resolve_steps(_job(defaults={"run": {"working-directory": "docs"}}), contained_ctx()["local"], "b" * 40)
    assert {s.get("cwd") for s in steps if "argv" in s} == {"docs"}
    steps, why = runner.resolve_steps(_job(defaults={"run": {"working-directory": "../up"}}), contained_ctx()["local"], "b" * 40)
    assert steps is None and "working-directory" in why


def test_a_step_condition_is_recorded_not_evaluated():
    job = _job(steps=[dict(s, **({"if": "always()"} if s.get("name") == "judge" else {})) for s in WORKFLOW["jobs"]["gate"]["steps"]])
    steps, _ = runner.resolve_steps(job, contained_ctx()["local"], "b" * 40)
    assert steps[1]["if_not_evaluated"] == "always()"


def test_a_host_job_runs_its_steps_in_the_job_default_working_directory(tmp_path):
    wf = dict(WORKFLOW, jobs={"gate": _job(defaults={"run": {"working-directory": "docs"}})})
    judge = "import pathlib, sys\nsys.exit(0 if pathlib.Path('ok.md').is_file() else 1)\n"
    fx = fr.make_repo(tmp_path, {"docs/new.md": "x\n"}, {**BASE_EXTRA, WF: yaml.safe_dump(wf), JUDGE: judge})
    fr.plan(fx, "--contexts-file", str(fr.contexts_file(fx, tmp_path / "contexts.yaml", [host_ctx()])))
    fr.run(fx)
    assert fr.status(fx)["checks"]["ctx.judge"]["status"] == "PASS"


def test_injection_variables_a_workflow_sets_never_reach_a_host_step(tmp_path):
    wf = dict(WORKFLOW, jobs={"gate": _job(env={"TOOL_VERSION": "1.2.3", "PYTHONPATH": ".", "PYTHONSTARTUP": "x.py"})})
    judge = "import os, sys\nsys.exit(1 if {'PYTHONPATH', 'PYTHONSTARTUP'} & set(os.environ) else 0)\n"
    fx = fr.make_repo(tmp_path, {"docs/new.md": "x\n"}, {**BASE_EXTRA, WF: yaml.safe_dump(wf), JUDGE: judge})
    fr.plan(fx, "--contexts-file", str(fr.contexts_file(fx, tmp_path / "contexts.yaml", [host_ctx()])))
    assert plan_spec(fx)["steps"][1]["env"]["PYTHONPATH"] == "."        # planned as the workflow says ...
    fr.run(fx)
    assert fr.status(fx)["checks"]["ctx.judge"]["status"] == "PASS"    # ... and stripped before a host process starts


@pytest.mark.parametrize("pin,want", [("3.0", "BLOCKED"), (None, "PASS")])
def test_a_setup_python_pin_must_name_the_interpreter_that_runs_the_steps(tmp_path, pin, want):
    steps = [{"uses": "actions/setup-python@v7", "with": {"python-version": pin or ".".join(runner.platform.python_version().split(".")[:2])}}]
    wf = dict(WORKFLOW, jobs={"gate": _job(steps=steps + WORKFLOW["jobs"]["gate"]["steps"])})
    fx = fr.make_repo(tmp_path, {"docs/new.md": "x\n"}, {**BASE_EXTRA, WF: yaml.safe_dump(wf)})
    fr.plan(fx, "--contexts-file", str(fr.contexts_file(fx, tmp_path / "contexts.yaml", [host_ctx()])))
    fr.run(fx)
    c = fr.status(fx)["checks"]["ctx.judge"]
    assert c["status"] == want and (want == "PASS" or "python-version '3.0'" in c["reason"])


def test_a_pinned_tool_that_resolves_inside_the_candidate_is_never_probed(tmp_path, monkeypatch):
    fx = fr.make_repo(tmp_path, {"bin/localci-faketool": "#!/bin/sh\necho 1.2.3\n"}, BASE_EXTRA)
    (fx["repo"] / "bin" / "localci-faketool").chmod(0o755)
    monkeypatch.setenv("PATH", f"{fx['repo'] / 'bin'}{os.pathsep}{os.environ['PATH']}")
    fr.plan(fx, "--contexts-file", str(fr.contexts_file(fx, tmp_path / "contexts.yaml", [tool_ctx()])))
    spec = plan_spec(fx)
    assert spec["status"] == "BLOCKED" and "inside the candidate worktree" in spec["reason"]


def test_a_changed_gitattributes_keeps_a_contained_green_from_being_claimed(fx):
    fr.git(fx["repo"], "checkout", "-q", fx["base"])
    for rel, body in BASE_EXTRA.items():
        fr.write(fx["repo"], {rel: body})
    fr.git(fx["repo"], "add", "-A")
    fr.git(fx["repo"], "commit", "-q", "-m", "base+gate")
    base = fr.git(fx["repo"], "rev-parse", "HEAD")
    fr.write(fx["repo"], {"docs/.gitattributes": "*.md text eol=crlf\n"})
    fr.git(fx["repo"], "add", "-A")
    fr.git(fx["repo"], "commit", "-q", "-m", "attrs")
    cand = fr.git(fx["repo"], "rev-parse", "HEAD")
    ctx = dict(contained_ctx(), check="ctx.judge")
    spec = runner.plan_context_check(fx["repo"], base, cand, fx["run"], "Gate", ctx, {}, ["docs/.gitattributes"], {"container": "3.11.0"})
    assert spec["kind"] == "contained_steps" and spec["judge_modified"] == ["docs/.gitattributes"]
    assert runner.steps_verdict([{"name": "x", "status": "PASS", "reason": "rc=0"}], spec)[0] == "BLOCKED"


# --------------------------------------------------------------- container: BASE steps verbatim, in the candidate sandbox
@needs_docker
@pytest.mark.parametrize("candidate,want", [
    ({"docs/new.md": "clean\n"}, "PASS"),
    ({"docs/bad.md": "VIOLATION\n"}, "FAIL"),
    ({JUDGE: "import sys\nsys.exit(0)\n", "docs/bad.md": "VIOLATION\n"}, "FAIL"),   # the BASE judge is laid over the candidate's
])
def test_a_contained_context_runs_base_steps_verbatim_with_its_guilt_control(tmp_path, capsys, candidate, want):
    fx, s = ran(tmp_path, candidate, contained_ctx(), "--isolation", "container", "--isolation-image", fr.ISOLATION_IMAGE)
    c = s["checks"]["ctx.judge"]
    assert c["status"] == want, (c, (fx["run"] / "logs" / "ctx.judge.log").read_text()[-2000:])
    assert [x["name"] for x in c["steps"]] == ["selftest", "judge", "guilt control", "pr sentinel"]
    assert c["steps"][3]["status"] == "NOT_APPLICABLE" and (c["steps"][2]["status"] == "PASS") == (want == "PASS")
    st = fr.load_state(fx)
    assert st["seal_first"]["why"].startswith("trusted checks done") and f"seal={st['seal_first']['seal']}" in capsys.readouterr().out
    runner.main(["status", "--run-dir", str(fx["run"]), "--seal", st["seal_first"]["seal"]])
    assert "seal mismatch" not in (json.loads((fx["run"] / "status.json").read_text())["freshness"]["stale_reason"] or "")


# --------------------------------------------------------------- the real matrix
MATRIX = fr.REAL_REPO / "scripts" / "localci" / "contexts_matrix.yaml"


def test_the_real_matrix_accounts_for_every_step_of_every_executed_context_and_names_the_rest():
    """Catches a matrix authoring error in the PR that makes it. It reads the workflows from outside scripts/localci, which the
    hosted path filter does not watch: a later workflow change is caught by `plan` (the context goes BLOCKED), not here."""
    doc = yaml.safe_load(MATRIX.read_text())
    executed = [c for c in doc["contexts"] if c["mapping"] == "executed"]
    assert executed and all(c["local"].get("check", "").startswith("ctx.") and c["local"]["where"] in ("host", "container") for c in executed)
    for c in executed:
        job = yaml.safe_load((fr.REAL_REPO / c["workflow_file"]).read_text())["jobs"][c["job_id"]]
        steps, why = runner.resolve_steps(job, c["local"], "b" * 40)
        assert why is None and steps, (c["name"], why)
        assert all((fr.REAL_REPO / f).is_file() for f in c["local"].get("trusted_files", [])), c["name"]
    assert sorted(doc["summary"]["never_claim_parity_for"]) == sorted(c["name"] for c in doc["contexts"] if c["mapping"] != "executed")
    assert doc["summary"]["executed"] == len(executed)
