"""Service contexts (runner v0.6.0): job chains, services beside the sandbox, deps images, expressions evaluated as hosted does."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from . import fixture_repo as fr
from .fixture_repo import runner

pytestmark = pytest.mark.usefixtures("fake_env")
X = runner._gh_expr()
MATRIX = Path(runner.__file__).with_name("contexts_matrix.yaml")


# ------------------------------------------------------------------ expressions: the hosted semantics, and refusal outside them
@pytest.mark.parametrize("expr,ctx,want", [
    ("github.event.merge_group.base_sha || github.event.pull_request.base.sha || 'main'", {"github": {"event": {"merge_group": {"base_sha": "b1"}}}}, "b1"),
    ("github.event.pull_request.number", {"github": {"event": {}}}, ""),
    ("github.event_name != 'pull_request'", {"github": {"event_name": "merge_group"}}, "true"),
    ("github.event_name == 'MERGE_GROUP'", {"github": {"event_name": "merge_group"}}, "true"),
    ("needs.changes.outputs.impact_run_all || 'true'", {"needs": {"changes": {"outputs": {"impact_run_all": ""}}}}, "true"),
    ("steps.x.outputs.y != 'true'", {"steps": {}}, "true"),
    ("steps.x.outputs.y == ''", {"steps": {}}, "true"),
    ("github.event_name == 'workflow_dispatch' && github.sha || ''", {"github": {"event_name": "merge_group", "sha": "s"}}, ""),
    ("!(steps.a.outputs.n == '2' && steps.a.outputs.s == 'size')", {"steps": {"a": {"outputs": {"n": "2", "s": "SIZE"}}}}, "false"),
])
def test_expressions_evaluate_as_the_hosted_runner_does(expr, ctx, want):
    assert X.substitute("${{ " + expr + " }}", ctx) == want


@pytest.mark.parametrize("expr", ["secrets.CODECOV_TOKEN != ''", "github.token", "hashFiles('a')", "inputs.x", "format('{0}', 1)", "a[0]"])
def test_a_value_hosted_holds_and_this_run_does_not_is_refused_never_read_as_empty(expr):
    with pytest.raises(X.ExprError):
        X.validate("${{ " + expr + " }}")


@pytest.mark.parametrize("cond,status,want", [
    (None, "success", True), (None, "failure", False), ("steps.a.outcome != 'success'", "failure", False),
    ("always()", "failure", True), ("failure()", "failure", True), ("${{ env.X == 'true' }}", "success", False),
])
def test_a_step_condition_is_decided_with_the_job_status(cond, status, want):
    assert X.step_runs(cond, {"steps": {"a": {"outcome": "failure"}}, "env": {}}, status) is want


# ------------------------------------------------------------------ the driver in expression mode (it runs anywhere: no docker)
def test_the_driver_decides_conditions_reads_outputs_and_honours_continue_on_error(tmp_path):
    sh = ["bash", "-e", "{0}"]
    steps = [
        {"name": "flaky", "id": "a", "argv": sh, "script": 'echo "flag=on" >> "$GITHUB_OUTPUT"\nexit 3\n', "continue_on_error": True},
        {"name": "reads", "argv": sh, "script": 'test "${{ steps.a.outputs.flag }}" = on\n', "if": "steps.a.outcome == 'failure'"},
        {"name": "not taken", "argv": sh, "script": "exit 9\n", "if": "steps.a.outcome == 'success'"},
        {"name": "hangs", "argv": sh, "script": "sleep 5\n", "timeout_s": 1},
        {"name": "after red", "argv": sh, "script": "exit 0\n", "if": "steps.a.outputs.flag == 'on'"},
        {"name": "upload", "if": "always()", "emulate": {"action": "upload", "path": "${{ runner.temp }}/none", "name": "x", "pattern": "",
                                                        "merge": False, "if_no_files_found": "error"}},
    ]
    cfg = {"context": "t", "root": str(tmp_path), "env": {}, "job_env": {}, "expr": {"github": {}, "runner": {"temp": "missing"}}, "steps": steps}
    (tmp_path / "steps.json").write_text(json.dumps(cfg))
    rc = subprocess.run([sys.executable, "-I", str(runner.STEPS_DRIVER), str(tmp_path / "steps.json"), str(tmp_path / "j.xml")],
                        capture_output=True).returncode
    got = runner.parse_expr_junit(tmp_path / "j.xml")
    assert rc == 1 and [s["status"] for s in got] == ["PASS", "PASS", "NOT_APPLICABLE", "FAIL", "NOT_APPLICABLE", "FAIL"]
    assert got[0]["reason"].startswith("continue-on-error") and "-> false" in got[2]["reason"] and "status failure" in got[4]["reason"]


# ------------------------------------------------------------------ services: planned from BASE, pinned, healthy or BLOCKED
SVC = {"image": "ghcr.io/x/ci-mirror/postgres:15", "env": {"POSTGRES_USER": "test", "POSTGRES_PASSWORD": "test"},
       "options": '--health-cmd "pg_isready -q" --health-interval 1s --health-timeout 1s --health-retries 2', "ports": ["5432:5432"],
       "credentials": {"username": "${{ github.actor }}", "password": "${{ secrets.GITHUB_TOKEN }}"}}
IMAGES = {"ghcr.io/x/ci-mirror/postgres:15": "postgres:15"}


def fake_docker(tmp_path: Path, health: str = "healthy") -> Path:
    """A `docker` that knows two images, records every argv, and reports one health state."""
    log, exe = tmp_path / "docker.argv", tmp_path / "bin" / "docker"
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_text(f"""#!/bin/bash
printf '%s\\n' "$*" >> {log}
case "$1 $2" in
  "image inspect") for a; do :; done; case "$a" in postgres:15|redis:7) echo sha256:{"a" * 64};; *) exit 1;; esac;;
  "inspect --format") echo {health};;
  "container inspect") echo "Error: No such container" >&2; exit 1;;
  *) exit 0;;
esac
""")
    exe.chmod(0o755)
    return exe


def test_a_service_runs_as_base_declares_it_on_a_pinned_image(tmp_path):
    svcs, why = runner.plan_services({"services": {"postgres": SVC}}, IMAGES, str(fake_docker(tmp_path)))
    assert why is None and svcs[0]["image_id"] == "sha256:" + "a" * 64 and svcs[0]["health"]["cmd"] == "pg_isready -q"
    assert svcs[0]["env"] == SVC["env"] and "credentials" not in json.dumps(svcs)


@pytest.mark.parametrize("change,needle", [
    ({"image": "ghcr.io/x/ci-mirror/postgres:16"}, "no operator-pinned stand-in"),       # tag drift
    ({"options": "--health-cmd pg_isready --privileged"}, "not emulated"),
    ({"options": "--health-cmd pg_isready"}, "health options incomplete"),
    ({"ports": ["15432:5432"]}, "identity maps"),
    ({"env": {"POSTGRES_PASSWORD": "${{ secrets.PG }}"}}, "expressions"),
])
def test_a_service_the_runner_cannot_reproduce_is_blocked_naming_why(tmp_path, change, needle):
    svcs, why = runner.plan_services({"services": {"postgres": {**SVC, **change}}}, IMAGES, str(fake_docker(tmp_path)))
    assert svcs is None and needle in why


def test_an_unhealthy_service_blocks_the_job_and_is_torn_down(tmp_path):
    docker = str(fake_docker(tmp_path, health="unhealthy"))
    svcs, _ = runner.plan_services({"services": {"postgres": SVC}}, IMAGES, docker)
    names, owner, why = runner.start_services(docker, svcs, "localci-t", "lbl", runner.trusted_env(), tmp_path / "log")
    assert why and "'unhealthy'" in why and names == [owner]
    for n in names:
        runner._remove_verified(docker, n, runner.trusted_env())
    assert f"rm -f {names[0]}" in (tmp_path / "docker.argv").read_text()


def test_no_host_secret_reaches_a_service_or_rides_on_its_argv(tmp_path, monkeypatch):
    for k, v in {"DATABASE_URL": "postgresql://prod:hunter2@db/prod", "GH_TOKEN": "ghp_hostsecret", "POSTGRES_PASSWORD": "hostpw"}.items():
        monkeypatch.setenv(k, v)
    docker = str(fake_docker(tmp_path))
    svcs, _ = runner.plan_services({"services": {"postgres": SVC, "redis": {**SVC, "image": "ghcr.io/x/ci-mirror/redis:7", "env": {}}}},
                                   {**IMAGES, "ghcr.io/x/ci-mirror/redis:7": "redis:7"}, docker)
    names, owner, why = runner.start_services(docker, svcs, "localci-t", "lbl", runner.trusted_env(), tmp_path / "log")
    runs = [ln for ln in (tmp_path / "docker.argv").read_text().splitlines() if ln.startswith("run -d")]
    assert why is None and len(runs) == 2 and f"--network container:{owner}" in runs[1] and "--network none" in runs[0]
    envs = [tok.split("=", 2)[1] for ln in runs for tok in ln.split() if tok.startswith("--env=")]
    assert sorted(envs) == ["POSTGRES_PASSWORD", "POSTGRES_USER"]   # BASE's literal map, nothing else
    assert not any(s in "\n".join(runs) for s in ("hunter2", "ghp_hostsecret", "hostpw"))


# ------------------------------------------------------------------ a fixture context: BASE wins, chains carry results
WF = ".github/workflows/svc.yml"
WORKFLOW = {"name": "svc", "on": {"merge_group": None}, "env": {"COLLECT": "${{ github.event_name != 'pull_request' }}"}, "jobs": {
    "unit": {"runs-on": "ubuntu-latest", "timeout-minutes": 5, "services": {"postgres": SVC}, "steps": [
        {"uses": "actions/checkout@v7"}, {"name": "test", "run": 'test "$COLLECT" = true'}]},
    "fanin": {"name": "Fan In", "needs": ["unit"], "runs-on": "ubuntu-latest", "steps": [
        {"name": "assert", "env": {"R": "${{ needs.unit.result }}"}, "run": 'test "$R" = success'}]}}}


def svc_ctx(**over) -> dict:
    local = {"check": "ctx.fan-in", "where": "container", "expressions": True, "service_images": IMAGES,
             "jobs": [{"job_id": "unit", "steps": [{"workflow_step": "test"}]}], "steps": [{"workflow_step": "assert"}]}
    local.update(over)
    return {"name": "Fan In", "workflow_file": WF, "job_id": "fanin", "mapping": "executed", "local": local}


def planned_svc(tmp_path: Path, monkeypatch, candidate: dict, ctx: dict, base: dict | None = None) -> dict:
    exe = fake_docker(tmp_path)
    exe.write_text(exe.read_text().replace('"image inspect") for a', '"image inspect") case "$4" in *Config.Env*) '
                                           'printf "sha256:%064d\\nPYTHON_VERSION=3.12.15\\n" 1; exit 0;; esac; for a'))
    monkeypatch.setenv("PATH", f"{exe.parent}{os.pathsep}{os.environ['PATH']}")
    fx = fr.make_repo(tmp_path, candidate, base or {WF: yaml.safe_dump(WORKFLOW)})
    fr.plan(fx, "--isolation", "container", "--contexts-file", str(fr.contexts_file(fx, tmp_path / "contexts.yaml", [ctx])))
    return json.loads((fx["run"] / "state" / "plan.json").read_text())["checks"]["ctx.fan-in"]


def test_the_base_service_spec_is_the_one_planned_whatever_the_candidate_writes(tmp_path, monkeypatch):
    evil = {**WORKFLOW, "jobs": {**WORKFLOW["jobs"], "unit": {**WORKFLOW["jobs"]["unit"], "services": {"postgres": {**SVC, "image": "evil:latest"}}}}}
    spec = planned_svc(tmp_path, monkeypatch, {WF: yaml.safe_dump(evil)}, svc_ctx())
    assert spec["kind"] == "contained_jobs" and spec["jobs"][0]["services"][0]["image"] == SVC["image"]
    assert spec["judge_modified"] == [WF]   # and a green won here is BLOCKED: hosted would run the candidate's spec
    assert runner.steps_verdict([{"name": "t", "status": "PASS", "reason": "rc=0"}], spec)[0] == "BLOCKED"


def test_a_chain_is_planned_from_base_with_its_expressions_kept_for_the_driver(tmp_path, monkeypatch):
    spec = planned_svc(tmp_path, monkeypatch, fr.CANDIDATE_FILES, svc_ctx())
    unit, fanin = spec["jobs"]
    assert [unit["job_id"], fanin["job_id"]] == ["unit", "fanin"] and fanin["needs"] == ["unit"] and unit["legs"] == [{}]
    assert unit["job_env"]["COLLECT"].startswith("${{") and fanin["steps"][0]["env"]["R"] == "${{ needs.unit.result }}"
    assert spec["expr"]["github"]["event"]["merge_group"]["base_sha"] == "main" and spec["judge_modified"] == []


@pytest.mark.parametrize("over,needle", [
    ({"steps": [{"workflow_step": "assert", "env": {"R": "${{ secrets.X }}"}}]}, "not modelled"),
    ({"jobs": []}, "needs ['unit']"),
    ({"service_images": {}}, "no operator-pinned stand-in"),
])
def test_a_service_context_that_cannot_be_planned_honestly_is_blocked(tmp_path, monkeypatch, over, needle):
    spec = planned_svc(tmp_path, monkeypatch, fr.CANDIDATE_FILES, svc_ctx(**over))
    assert spec["status"] == "BLOCKED" and needle in spec["reason"]


HOST_WF = {**WORKFLOW, "jobs": {"fanin": {"name": "Fan In", "runs-on": "ubuntu-latest", "steps": [
    {"name": "assert", "run": "true"}, {"name": "verdict", "env": {"GH_TOKEN": "${{ github.token }}"}, "run": "python3 scripts/ci/read.py"}]}}}
READER = "scripts/ci/read.py"
HOST_BASE = {WF: yaml.safe_dump(HOST_WF), READER: "import sys\nsys.exit(3 if sys.argv[1:] == ['--repo', 'Bali-Zero/Teman2'] else 4)\n"}


def host_ctx(argv: list) -> dict:
    return svc_ctx(jobs=[], trusted_files=[READER], steps=[{"workflow_step": "assert"}, {
        "workflow_step": "verdict", "side": "host", "argv": argv, "env": {"GH_TOKEN": ""}}])


def test_a_host_reader_is_the_base_copy_run_at_plan_and_its_answer_is_frozen_in_the_plan(tmp_path, monkeypatch):
    spec = planned_svc(tmp_path, monkeypatch, {**fr.CANDIDATE_FILES, READER: "raise SystemExit(0)\n"},
                       host_ctx(["$PY", READER, "--repo", "${{ github.repository }}"]), HOST_BASE)
    step = spec["jobs"][0]["steps"][1]
    assert step["precomputed"]["rc"] == 3 and step["side"]["argv"][1] == "-I"   # BASE's reader answered; the candidate's exits 0


@pytest.mark.parametrize("argv", [["bash", "-c", "true"], ["$PY", "scripts/ci/other.py"], ["$PY", READER, "${{ secrets.X }}"]])
def test_a_host_step_that_is_not_a_trusted_base_reader_is_blocked(tmp_path, monkeypatch, argv):
    spec = planned_svc(tmp_path, monkeypatch, fr.CANDIDATE_FILES, host_ctx(argv), HOST_BASE)
    assert spec["status"] == "BLOCKED" and "host step" in spec["reason"]


@pytest.mark.parametrize("deps,needle", [
    ({"fetch": [{"url": "http://x/f", "sha256": "a" * 64, "path": "/tmp/f"}]}, "https url"),
    ({"fetch": [{"url": "https://x/f", "sha256": "unpinned", "path": "/tmp/f"}]}, "sha256 pin"),
    ({"fetch": [{"url": "https://x/f", "sha256": "a" * 64, "path": "/w/apps/f"}]}, "outside the tree"),
    ({"fetch": [{"url": "https://x/f", "sha256": "a" * 64, "path": "/tmp/../w/f"}]}, "outside the tree"),
    ({"node": "lts"}, "major version"),
    ({"packages": ["pytest; os_name=='nt'"]}, "bare distribution names"),
])
def test_a_deps_recipe_the_runner_cannot_pin_is_refused_before_anything_is_built(tmp_path, deps, needle):
    image, why = runner.plan_deps_image(tmp_path, "c" * 40, {"image_id": "sha256:" + "a" * 64, "docker": "/nonexistent"}, deps, "", tmp_path, "t")
    assert image is None and needle in why


def test_an_upstream_verdict_reaches_the_fan_in_and_an_upstream_without_one_stops_the_chain(monkeypatch, tmp_path):
    spec = {"jobs": [{"job_id": "unit", "legs": [{"n": 1}, {"n": 2}]}, {"job_id": "fanin", "legs": [{}]}], "needs": {}, "judge_modified": []}
    seen = []

    def leg(name, spec, job, leg, run_dir, plan, needs, arts, X, rc_by={"1": 1, "2": 0}):
        seen.append(dict(needs))
        rc = rc_by.get(str(leg.get("n")), 0)
        st = "FAIL" if rc else "PASS"
        return {"label": job["job_id"], "rc": rc, "steps": [{"name": "s", "status": st, "reason": f"rc={rc}"}], "seconds": 1, "cpu": 1, "infra": None, "log": ""}
    monkeypatch.setattr(runner, "_run_leg", leg)
    out = runner._execute_jobs("ctx.t", spec, tmp_path, {}, tmp_path / "log")
    assert seen[-1]["unit"]["result"] == "failure" and out["status"] == "FAIL"
    monkeypatch.setattr(runner, "_run_leg", lambda *a, **k: {"label": "unit", "rc": None, "steps": [], "seconds": 0, "cpu": 0,
                                                               "infra": ("BLOCKED", "service postgres is 'unhealthy'"), "log": ""})
    out = runner._execute_jobs("ctx.t", spec, tmp_path, {}, tmp_path / "log")
    assert out["status"] == "BLOCKED" and "unhealthy" in out["reason"]


def test_the_real_service_contexts_account_for_every_step_of_every_job():
    doc = yaml.safe_load(MATRIX.read_text())
    svc = [c for c in doc["contexts"] if c["mapping"] == "executed" and c["local"].get("expressions")]
    assert svc
    for c in svc:
        wf = yaml.safe_load((fr.REAL_REPO / c["workflow_file"]).read_text())
        for jl in [*c["local"].get("jobs", []), {**c["local"], "job_id": c["job_id"]}]:
            steps, why = runner.resolve_steps(wf["jobs"][jl["job_id"]], jl, "main", expressions=True)
            assert why is None and steps, (c["name"], jl["job_id"], why)
