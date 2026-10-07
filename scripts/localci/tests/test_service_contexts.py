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
    # actions/runner ParseNumber / OrdinalIgnoreCase / identity, as the refuters reproduced them
    ("'   ' == 0", {}, "true"), ("'0x10' == 16", {}, "true"), ("'0o10' == 8", {}, "true"), ("'1_0' == 10", {}, "false"),
    ("github.REF == 'refs/heads/main'", {"github": {"ref": "refs/heads/main"}}, "true"),
    ("'STRASSE' == 'straße'", {}, "false"), ("matrix == job", {"matrix": {}, "job": {}}, "false"),
    ("steps.absent.outputs.x == 0", {"steps": {}}, "true"), ("null == false", {}, "true"), ("'abc' == 0", {}, "false"),
])
def test_expressions_evaluate_as_the_hosted_runner_does(expr, ctx, want):
    assert X.substitute("${{ " + expr + " }}", ctx) == want


@pytest.mark.parametrize("text,want", [("  ", 0.0), ("0x10", 16.0), ("+0x10", None), ("0xffffffff", -1.0), ("0x100000000", None),
                                       ("0o37777777777", -1.0), ("1_0", None), ("1e3", 1000.0), (".5", 0.5), ("Infinity", float("inf"))])
def test_strings_become_numbers_as_actions_runner_parse_number_reads_them(text, want):
    got = X._num(text)
    assert (got != got) if want is None else got == want   # None: NaN, which equals nothing


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
        {"name": "unconditioned", "argv": sh, "script": "exit 0\n"},                        # implicit success(): skipped after a red
        {"name": "status", "argv": sh, "script": 'test "${{ job.status }}" = failure\n', "if": "always()"},
    ]
    got, rc = drive(tmp_path, steps)
    assert rc == 1 and [s["status"] for s in got] == ["PASS", "PASS", "NOT_APPLICABLE", "FAIL", "NOT_APPLICABLE", "FAIL", "NOT_APPLICABLE", "PASS"]
    assert got[0]["reason"] == "continue-on-error: rc=3" and "-> false" in got[2]["reason"] and "status failure" in got[4]["reason"]
    assert "success()" in got[6]["reason"]


def drive(tmp_path: Path, steps: list) -> tuple[list, int]:
    cfg = {"context": "t", "root": str(tmp_path), "env": {}, "job_env": {}, "expr": {"github": {}, "runner": {"temp": "missing"}}, "steps": steps}
    (tmp_path / "steps.json").write_text(json.dumps(cfg))
    rc = subprocess.run([sys.executable, "-I", str(runner.STEPS_DRIVER), str(tmp_path / "steps.json"), str(tmp_path / "j.xml")],
                        capture_output=True).returncode
    return runner.parse_expr_junit(tmp_path / "j.xml"), rc


def _driver():
    import importlib.util
    spec = importlib.util.spec_from_file_location("localci_steps_driver", runner.STEPS_DRIVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("raw,want", [(b"k=v\r\n", {"k": "v\r"}), (b"k<<E\na\r\nb\r\nE\n", {"k": "a\r\nb\r"}), (b"\xef\xbb\xbfk=v\n", {"k": "v"}),
                                     (b"k<<E\nv\nE", {"k": "v"}), (b"\n\nk=1\nk=2\n", {"k": "2"}), (b"k<<E\r\nv\nE\n", None), (b"k<<E\nv", None)])
def test_github_output_is_read_back_as_the_hosted_linux_runner_reads_it(tmp_path, raw, want):
    (tmp_path / "o").write_bytes(raw)
    got, err = _driver().read_kv_file(tmp_path / "o")
    assert (err is not None) if want is None else (got, err) == (want, None)


def test_continue_on_error_covers_a_signal_as_hosted_but_the_step_still_has_no_verdict(tmp_path):
    sh = ["bash", "-e", "{0}"]
    got, rc = drive(tmp_path, [{"name": "dies", "id": "a", "argv": sh, "script": "kill -TERM $$\n", "continue_on_error": True},
                               {"name": "next", "argv": sh, "script": 'test "${{ steps.a.conclusion }}" = success\n'}])
    assert [s["status"] for s in got] == ["ERROR", "PASS"]


def test_the_merge_group_shas_are_the_hex_ids_of_base_and_of_the_candidate_built_on_it(tmp_path):
    (tmp_path / "f.txt").write_text("x\n")
    gh = runner.github_ctx("b" * 40, 1, "o/r")
    script = 'test "$(git rev-parse main)" = "${{ github.event.merge_group.base_sha }}"\ntest "$(git rev-parse HEAD)" = "${{ github.sha }}"\n' \
             'echo "${{ github.event.merge_group.head_sha }}" | grep -qxE "[0-9a-f]{40}"\n'
    cfg = {"context": "t", "root": str(tmp_path), "env": {}, "job_env": {}, "git_index": True, "history": {"added": [], "base": []},
           "expr": {"github": gh, "runner": {}}, "steps": [{"name": "ids", "argv": ["bash", "-e", "{0}"], "script": script}]}
    (tmp_path / "cfg").mkdir()
    (tmp_path / "cfg" / "steps.json").write_text(json.dumps(cfg))
    rc = subprocess.run([sys.executable, "-I", str(runner.STEPS_DRIVER), str(tmp_path / "cfg" / "steps.json"), str(tmp_path / "j.xml")],
                        capture_output=True).returncode
    assert rc == 0 and runner.parse_expr_junit(tmp_path / "j.xml")[0]["status"] == "PASS"


@pytest.mark.parametrize("body", ['echo "k<<END" >> "$GITHUB_OUTPUT"; echo v >> "$GITHUB_OUTPUT"', 'echo "garbage" >> "$GITHUB_OUTPUT"',
                                  'echo "k<<" >> "$GITHUB_OUTPUT"'])
def test_a_malformed_github_output_fails_its_step_as_hosted(tmp_path, body):
    got, rc = drive(tmp_path, [{"name": "w", "id": "w", "argv": ["bash", "-e", "{0}"], "script": body + "\n"}])
    assert rc == 1 and got[0]["status"] == "FAIL" and "GITHUB_OUTPUT" in got[0]["reason"]


def test_a_step_killed_by_a_signal_turns_the_job_status_to_failure(tmp_path):
    sh = ["bash", "-e", "{0}"]
    got, rc = drive(tmp_path, [{"name": "dies", "argv": sh, "script": "kill -TERM $$\n"},
                               {"name": "on success", "argv": sh, "script": "exit 0\n", "if": "success()"},
                               {"name": "on failure", "argv": sh, "script": "exit 0\n", "if": "failure()"}])
    assert [s["status"] for s in got] == ["ERROR", "NOT_APPLICABLE", "PASS"]


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
    ({"steps": [{"workflow_step": "assert", "env": {"R": "${{ github.run_id }}"}}]}, "github property this run does not model"),
    ({"steps": [{"workflow_step": "assert", "env": {"R": "${{ job.container.id }}"}}]}, "only job.status is"),
    ({"steps": [{"workflow_step": "assert", "env": {"R": "${{ strategy.job-total }}"}}]}, "strategy is not modelled"),
    ({"steps": [{"workflow_step": "assert", "env": {"R": "${{ github.event.repository.name }}"}}]}, "merge_group payload"),
    ({"steps": [{"workflow_step": "assert", "env": {"R": "${{ github.event.merge_group.head_commit.id }}"}}]}, "merge_group field"),
    ({"steps": [{"workflow_step": "assert", "env": {"R": "${{ needs.unit.outputs.n }}"}}]}, "upstream output"),
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


MARK = "::error::r: CANNOT-VERIFY"
ERR = "import sys; print({!r}, file=sys.stderr); raise SystemExit(1)"


@pytest.mark.parametrize("body,marker,rc,tries", [
    (ERR.format(MARK + " (read failed) gh: HTTP 500"), MARK, None, 3),                                   # GitHub failed: no verdict
    (ERR.format("::error::r: no gate verdict"), MARK, 1, 1),                                              # the reader judged: a verdict
    ("print('r: posted description = ' + repr('" + MARK + "')); " + ERR.format("::error::r: red"), MARK, 1, 1),  # echoed text: still a verdict
    (ERR.format(MARK), None, 1, 1),                                                                       # no marker declared: as before
])
def test_a_host_reader_that_could_not_read_github_is_asked_again_then_gives_no_verdict(tmp_path, monkeypatch, body, marker, rc, tries):
    monkeypatch.setattr(runner, "READER_RETRY_WAITS", (0, 0, 0))
    calls = tmp_path / "calls"
    (tmp_path / "r.py").write_text(f"open({str(calls)!r}, 'a').write('.')\n{body}\n")
    got = runner.run_host_reader([sys.executable, "-I", str(tmp_path / "r.py")], tmp_path, 30, marker)
    assert got["rc"] == rc and len(calls.read_text()) == tries and ("no verdict" in got["reason"]) is (rc is None)


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


def test_a_commit_id_the_sandbox_rebuilds_is_refused_wherever_the_runner_evaluates_the_text_itself(tmp_path, monkeypatch):
    spec = planned_svc(tmp_path, monkeypatch, fr.CANDIDATE_FILES, host_ctx(["$PY", READER, "--sha", "${{ github.SHA }}"]), HOST_BASE)
    assert spec["status"] == "BLOCKED" and "github.SHA" in spec["reason"] and "only the driver knows" in spec["reason"]
    assert runner.rebuilt_id(["${{ github.event.merge_group }}"]) == "github.event.merge_group"
    assert runner.rebuilt_id(["${{ github.event.merge_group.head_ref }} github.sha", "${{ github.repository }}"]) is None
    up = {"name": "up", "uses": "actions/upload-artifact@v4", "with": {"name": "cov-${{ github.event.merge_group.head_sha }}", "path": "out"}}
    wf = {**WORKFLOW, "jobs": {**WORKFLOW["jobs"], "unit": {**WORKFLOW["jobs"]["unit"], "steps": [*WORKFLOW["jobs"]["unit"]["steps"], up]}}}
    ctx = svc_ctx(jobs=[{"job_id": "unit", "steps": [{"workflow_step": "test"}, {"workflow_step": "up", "emulate": True}]}])
    spec = planned_svc(tmp_path / "art", monkeypatch, fr.CANDIDATE_FILES, ctx, {WF: yaml.safe_dump(wf)})
    assert spec["status"] == "BLOCKED" and "artifact name or path" in spec["reason"]
    up["with"]["name"] = "cov"
    assert planned_svc(tmp_path / "ok", monkeypatch, fr.CANDIDATE_FILES, ctx, {WF: yaml.safe_dump(wf)}).get("status") != "BLOCKED"


@pytest.mark.parametrize("expressions,tm,needle", [(False, 5, "only in a service context"), (True, 0, "must be literals"),
                                                    (True, "${{ env.T }}", "must be literals"), (True, -1, "must be literals")])
def test_a_step_timeout_is_emulated_in_a_service_context_and_blocked_elsewhere(expressions, tm, needle):
    job = {"runs-on": "ubuntu-latest", "steps": [{"name": "s", "run": "true", "timeout-minutes": tm}]}
    steps, why = runner.resolve_steps(job, {"steps": [{"workflow_step": "s"}]}, "main", expressions=expressions)
    assert steps is None and needle in why
    if expressions:
        ok, _ = runner.resolve_steps({**job, "steps": [{**job["steps"][0], "timeout-minutes": 5}]}, {"steps": [{"workflow_step": "s"}]}, "main",
                                     expressions=True)
        assert ok[0]["timeout_s"] == 300


def test_a_job_timeout_given_as_an_expression_is_blocked_not_read_as_the_default(tmp_path, monkeypatch):
    wf = {**WORKFLOW, "jobs": {**WORKFLOW["jobs"], "fanin": {**WORKFLOW["jobs"]["fanin"], "timeout-minutes": "${{ fromJSON(env.T) }}"}}}
    spec = planned_svc(tmp_path, monkeypatch, fr.CANDIDATE_FILES, svc_ctx(), {WF: yaml.safe_dump(wf)})
    assert spec["status"] == "BLOCKED" and "timeout-minutes" in spec["reason"]


def test_steps_listed_out_of_base_order_are_blocked_because_outputs_and_status_flow_in_order(tmp_path, monkeypatch):
    ctx = host_ctx(["$PY", READER, "--repo", "${{ github.repository }}"])
    ctx["local"]["steps"].reverse()
    spec = planned_svc(tmp_path, monkeypatch, fr.CANDIDATE_FILES, ctx, HOST_BASE)
    assert spec["status"] == "BLOCKED" and "out of BASE order" in spec["reason"]


@pytest.mark.parametrize("line,kept", [
    ('demo==1.0; python_version >= "3" --no-binary=:all:', False),   # pip reads ` --...` as an option: it would lift --only-binary
    ("demo==1.0 --no-binary=:all:", False), ('x==1; extra == "a --no-binary"', False), ("x==1 @ https://e/x.whl", False),
    ("--index-url https://e/simple", False), ("-e ../../packages/cell-core", False), ("x>=1", False),
    ('pywin32==306 ; sys_platform == "win32" \\', True), ("a[b,c]==1.2.3", True), ('x==1; platform_release == "5.15-generic"', True),
    ('x==1; platform_machine == "x86_64" and (python_version < "3.12" or os_name != "nt")', True),
])
def test_only_a_plain_pin_reaches_the_networked_download(line, kept):
    keep, dropped = runner._pin_lines((line + "\n").encode())
    assert bool(keep) is kept and bool(dropped) is not kept


def test_a_service_whose_start_times_out_is_still_handed_back_for_removal(tmp_path, monkeypatch):
    docker = str(fake_docker(tmp_path))
    svcs, _ = runner.plan_services({"services": {"postgres": SVC, "redis": {**SVC, "image": "ghcr.io/x/ci-mirror/redis:7", "env": {}}}},
                                   {**IMAGES, "ghcr.io/x/ci-mirror/redis:7": "redis:7"}, docker)
    real, calls = subprocess.run, []

    def run(argv, **kw):
        calls.append(argv)
        if argv[1:3] == ["run", "-d"] and len([c for c in calls if c[1:3] == ["run", "-d"]]) == 2:
            raise subprocess.TimeoutExpired(argv, 120)
        return real(argv, **kw)
    monkeypatch.setattr(runner.subprocess, "run", run)
    names, owner, why = runner.start_services(docker, svcs, "localci-t", "lbl", runner.trusted_env(), tmp_path / "log")
    assert len(names) == 2 and why and "TimeoutExpired" in why


@pytest.mark.parametrize("rc,cases", [(1, [("WRONG-STEP", "PASS")]), (1, [("audit", "PASS")]), (0, [("audit", "FAIL")]),
                                      (0, [("audit", "PASS"), ("extra", "PASS")]), (3, [("audit", "BLOCKED")])])
def test_an_egress_verdict_that_does_not_match_its_exit_code_is_no_verdict(tmp_path, monkeypatch, rc, cases):
    def fake_exec(name, spec, run_dir, plan, inner, a, extra, env, log, junit, *rest, **kw):
        suite = runner.ET.Element("testsuite")
        for n, st in cases:
            tc = runner.ET.SubElement(suite, "testcase", name=n)
            if st == "FAIL":
                runner.ET.SubElement(tc, "failure", message="rc=1")
            elif st == "BLOCKED":
                runner.ET.SubElement(tc, "error", type="not-started", message="x")
        runner.ET.ElementTree(suite).write(junit)
        return rc, None
    monkeypatch.setattr(runner, "execute_contained", fake_exec)
    for d in ("receipts", "logs"):
        (tmp_path / d).mkdir(exist_ok=True)
    st = {"name": "audit", "side": {"where": "egress", "inputs": [], "rewrite": []}}
    got = runner._run_egress("ctx.t", {"context": "t"}, {"timeout_s": 60, "image_id": "i"}, st, "s", {}, {}, {}, [], tmp_path, {})
    assert got["rc"] is None and "no consistent verdict" in got["reason"]


def npm_repo(tmp_path: Path, lock_entries: dict, workspaces: list) -> tuple[Path, str]:
    lock = {"lockfileVersion": 3, "packages": {"": {"workspaces": workspaces}, **lock_entries}}
    files = {"package.json": json.dumps({"name": "r", "workspaces": workspaces}), "package-lock.json": json.dumps(lock),
             **{f"{w}/package.json": json.dumps({"name": w}) for w in workspaces if "*" not in w}}
    fx = fr.make_repo(tmp_path, {**fr.CANDIDATE_FILES, **files})
    return fx["repo"], fx["candidate"]


REG = {"resolved": "https://registry.npmjs.org/playwright-core/-/playwright-core-1.63.0.tgz", "integrity": "sha512-x", "version": "1.63.0"}


def test_a_github_dependency_pinned_to_a_full_commit_is_fetched_and_a_moving_one_is_refused(tmp_path):
    pinned = {"resolved": "git+ssh://git@github.com/whiskeysockets/libsignal-node.git#" + "b" * 40}
    repo, cand = npm_repo(tmp_path / "a", {"node_modules/libsignal": pinned}, [])
    assert runner.npm_inputs(repo, cand, {"npm": "package-lock.json"})[2] is None
    repo, cand = npm_repo(tmp_path / "b", {"node_modules/libsignal": {"resolved": "git+ssh://git@github.com/w/l.git#main"}}, [])
    assert "full commit id" in runner.npm_inputs(repo, cand, {"npm": "package-lock.json"})[2]


@pytest.mark.parametrize("matrix,leg,want", [
    ({"include": [{"app": "mouth", "coverage": True}, {"app": "admin", "coverage": False}]}, {"app": "mouth", "coverage": True},
     [{"app": "mouth", "coverage": True}]),
    ({"include": [{"app": "mouth"}], "exclude": [{"app": "x"}]}, None, None),
])
def test_an_include_only_matrix_expands_as_hosted_and_a_context_can_be_one_leg(matrix, leg, want):
    legs, why = runner.matrix_legs({"strategy": {"matrix": matrix}})
    if want is None:
        assert legs is None and "not emulated" in why
    else:
        assert [g for g in legs if g == leg] == want and len(legs) == 2


@pytest.mark.parametrize("name,leg,ok", [
    ("Fan In (a, true)", {"app": "a", "cov": True}, True),
    ("Fan In (a, true)", {"app": "a", "cov": 1}, False),        # 1 is not true: hosted would name that leg "(a, 1)"
    ("Fan In (a, true)", {"app": "a", "cov": "true"}, False),
    ("Fan In (b, false)", {"app": "a", "cov": True}, False),   # the leg run must be the one the required context names
    ("Fan In (a, true)", {"app": "a"}, False),
])
def test_a_leg_selector_takes_exactly_the_leg_the_required_context_names(tmp_path, monkeypatch, name, leg, ok):
    matrix = {"include": [{"app": "a", "cov": True}, {"app": "b", "cov": False}]}
    wf = {**WORKFLOW, "jobs": {**WORKFLOW["jobs"], "fanin": {**WORKFLOW["jobs"]["fanin"], "strategy": {"matrix": matrix}}}}
    spec = planned_svc(tmp_path, monkeypatch, fr.CANDIDATE_FILES, {**svc_ctx(leg=leg), "name": name}, {WF: yaml.safe_dump(wf)})
    if ok:
        assert spec.get("status") != "BLOCKED" and spec["jobs"][1]["legs"] == [{"app": "a", "cov": True}]
    else:
        assert spec["status"] == "BLOCKED" and "exactly one leg" in spec["reason"]


def test_the_npm_stage_renders_one_offline_install_per_declared_lock():
    stage = runner.DEPS_NPM_STAGE.format(v="24")   # str.format: the shell's own braces must survive it
    assert "FROM node:24-bookworm-slim" in stage and '"/src/${lock%/package-lock.json}"' in stage and "--ignore-scripts" in stage
    assert runner.DEPS_BARE.count("\nFROM ${BASE}\n") == 1 and "chown" not in runner.DEPS_BARE   # node-only: no interpreter handed over


def test_the_npm_closure_is_the_locks_registry_entries_and_its_workspace_manifests(tmp_path):
    repo, cand = npm_repo(tmp_path, {"node_modules/playwright-core": REG, "node_modules/w": {"resolved": "apps/w", "link": True}}, ["apps/w"])
    files, pw, why = runner.npm_inputs(repo, cand, {"npm": "package-lock.json"})
    assert why is None and pw == "1.63.0" and sorted(files) == ["apps/w/package.json", "package-lock.json", "package.json"]


@pytest.mark.parametrize("entries,workspaces,needle", [
    ({"node_modules/x": {"resolved": "https://evil.example/x.tgz", "integrity": "sha512-x"}}, [], "only the public registry"),
    ({"node_modules/x": {"resolved": "git+ssh://git@github.com/e/x.git#abc"}}, [], "only the public registry"),
    ({"node_modules/x": {"resolved": "https://registry.npmjs.org/x/-/x-1.tgz"}}, [], "only the public registry"),   # no integrity
    ({"node_modules/x": {"resolved": "../outside", "link": True}}, [], "only the public registry"),                  # not a workspace
    ({}, ["apps/*"], "no globs"),
])
def test_an_npm_lock_that_fetches_outside_the_registry_is_refused(tmp_path, entries, workspaces, needle):
    repo, cand = npm_repo(tmp_path, entries, workspaces)
    _, _, why = runner.npm_inputs(repo, cand, {"npm": "package-lock.json"})
    assert why and needle in why


def test_a_setup_node_pin_the_deps_image_does_not_carry_is_blocked(tmp_path, monkeypatch):
    unit = WORKFLOW["jobs"]["unit"]
    wf = {**WORKFLOW, "jobs": {**WORKFLOW["jobs"], "unit": {**unit, "steps": [
        unit["steps"][0], {"name": "node", "uses": "actions/setup-node@v7", "with": {"node-version": "26"}}, *unit["steps"][1:]]}}}
    ctx = svc_ctx(deps={"node": "24"}, jobs=[{"job_id": "unit", "steps": [{"workflow_step": "node", "not_applicable": "stood in"},
                                                                         {"workflow_step": "test"}]}])
    spec = planned_svc(tmp_path, monkeypatch, fr.CANDIDATE_FILES, ctx, {WF: yaml.safe_dump(wf)})
    assert spec["status"] == "BLOCKED" and "setup-node pins ['26']" in spec["reason"]


def test_a_network_failure_in_the_egress_sandbox_is_no_verdict_on_the_candidate(tmp_path, monkeypatch):
    def fake_exec(name, spec, run_dir, plan, inner, a, extra, env, log, junit, *rest, **kw):
        log.write_text("urllib3.exceptions.ReadTimeoutError: HTTPSConnectionPool(host='pypi.org', port=443): Read timed out.\n")
        suite = runner.ET.Element("testsuite")
        runner.ET.SubElement(runner.ET.SubElement(suite, "testcase", name="audit"), "failure", message="rc=1")
        runner.ET.ElementTree(suite).write(junit)
        return 1, None
    monkeypatch.setattr(runner, "execute_contained", fake_exec)
    for d in ("receipts", "logs"):
        (tmp_path / d).mkdir(exist_ok=True)
    st = {"name": "audit", "side": {"where": "egress", "inputs": [], "rewrite": []}}
    got = runner._run_egress("ctx.t", {"context": "t"}, {"timeout_s": 60, "image_id": "i"}, st, "s", {}, {}, {}, [], tmp_path, {})
    assert got["rc"] is None and "the network failed" in got["reason"]
    finding = "Found 1 known vulnerability in 1 package\nName Version ID\nx 1.0 CVE-1\n"   # a finding beside a timeout stays a verdict
    monkeypatch.setattr(runner, "execute_contained", lambda *a, **k: (fake_exec(*a, **k), a[8].write_text(a[8].read_text() + finding))[0])
    got = runner._run_egress("ctx.t", {"context": "t"}, {"timeout_s": 60, "image_id": "i"}, st, "s", {}, {}, {}, [], tmp_path, {})
    assert got["rc"] == 1


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
