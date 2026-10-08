"""B4: the backend shards run two xdist workers under their 6g cgroup, and a leg killed on timeout names a dead xdist worker."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from . import fixture_repo as fr
from .fixture_repo import runner

MATRIX = Path(runner.__file__).with_name("contexts_matrix.yaml")
TESTS_WF = ".github/workflows/tests.yml"
VAR = "PYTEST_XDIST_AUTO_NUM_WORKERS"
GIT_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def _ctx(name: str) -> dict:   # the entry as `plan` hands it over: load_contexts on the real matrix
    return runner.load_contexts(str(MATRIX))["map"][name]


@pytest.fixture
def base_repo(tmp_path):
    """A git repo whose one commit carries the real hosted tests.yml: the BASE the planner reads its jobs from."""
    wt = tmp_path / "wt"
    (wt / ".github" / "workflows").mkdir(parents=True)
    shutil.copy(fr.REAL_REPO / TESTS_WF, wt / TESTS_WF)
    for args in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-qm", "base"]):
        subprocess.run(["git", "-C", str(wt), *args], check=True, capture_output=True, env=GIT_ENV)
    return wt, subprocess.run(["git", "-C", str(wt), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()


ISO = {"mode": "container", "docker": "/nonexistent/docker", "image_id": "sha256:" + "0" * 64, "user": "65534:65534"}


def _plan(monkeypatch, tmp_path, wt, sha, name):
    monkeypatch.setattr(runner, "plan_services", lambda job, images, docker: ([], None))      # no docker: the services are not what is judged
    monkeypatch.setattr(runner, "plan_deps_image", lambda *a, **k: ("sha256:" + "d" * 64, "deps image (faked)"))
    spec = runner.plan_service_context(wt, sha, sha, tmp_path / "trusted", name, _ctx(name), [], {"container": "3.12.15",
                                       "container_extra": {"3.11.17": "/opt/py311/bin"}}, ISO, {}, tmp_path / "run", 8077)
    assert spec["kind"] == "contained_jobs", spec.get("reason")
    return spec


def _step(job: dict, name: str) -> dict:
    return next(s for s in job["steps"] if s["name"] == name)


def test_the_real_backend_plan_gives_every_shard_leg_two_workers_and_no_other_job_any(monkeypatch, tmp_path, base_repo):
    # guilt: before B4 the sharded step ran `-n auto` = 4 workers under the 6g cgroup and the kernel OOM-killed one
    spec = _plan(monkeypatch, tmp_path, *base_repo, "Backend Tests (Python)")
    jobs = {j["job_id"]: j for j in spec["jobs"]}
    shard = jobs["backend-shard"]
    assert [leg.get("shard") for leg in shard["legs"]] == [1, 2, 3] and shard["job_env"][VAR] == "2"
    assert _step(shard, "Run unit tests (sharded)")["env"][VAR] == "2" and "-n auto --dist loadfile" in _step(shard, "Run unit tests (sharded)")["script"]
    for jid in ("backend-static", "backend-tests"):   # innocence: the static job and the fan-in keep xdist's own count
        assert VAR not in jobs[jid]["job_env"] and all(VAR not in (s.get("env") or {}) for s in jobs[jid]["steps"]), jid


def test_the_real_e2e_plan_carries_no_worker_cap(monkeypatch, tmp_path, base_repo):
    spec = _plan(monkeypatch, tmp_path, *base_repo, "E2E Tests (Playwright)")
    assert all(VAR not in j["job_env"] and all(VAR not in (s.get("env") or {}) for s in j["steps"]) for j in spec["jobs"])


def test_the_cap_is_declared_once_on_the_backend_shard_job_and_nowhere_else_in_the_matrix():
    doc = yaml.safe_load(MATRIX.read_text())
    hits = [(c["name"], j.get("job_id"), j["env"]) for c in doc["contexts"] for j in [c["local"], *(c["local"].get("jobs") or [])]
            if VAR in (j.get("env") or {})]
    assert hits == [("Backend Tests (Python)", "backend-shard", {VAR: "2"})]   # a string, as a workflow env value is: 4 x 2.1 GB > 6g, 2 x 2.1 GB fits
    assert MATRIX.read_text().count(VAR) == 2   # the env line and its comment


def test_a_shard_leg_hands_the_cap_to_its_sandbox_and_the_driver_sets_it_on_the_pytest_step(monkeypatch, tmp_path, base_repo):
    spec = _plan(monkeypatch, tmp_path, *base_repo, "Backend Tests (Python)")
    shard = next(j for j in spec["jobs"] if j["job_id"] == "backend-shard")
    spec["isolation"], seen = ISO, {}
    monkeypatch.setenv("LOCALCI_MIN_FREE_GB", "0")   # the B3 free-space floor, where present, reads nothing at 0

    def contained(name, spec, run_dir, plan, inner, overrides, extra, env, log, junit, timeout, workdir="/w", **kw):
        seen.update(cfg=json.loads(extra["cfg/steps.json"]), env=env, inner=inner)
        return 0, None
    monkeypatch.setattr(runner, "start_services", lambda *a, **k: ([], None, None))
    monkeypatch.setattr(runner, "execute_contained", contained)
    run_dir = tmp_path / "run"
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    (run_dir / "receipts").mkdir(exist_ok=True)
    runner._run_leg("ctx.backend-tests", spec, shard, {"shard": 2}, run_dir, {"run_id": "r", "worktree": str(base_repo[0])}, {"changes": {}}, {},
                    runner._gh_expr())
    cfg = seen["cfg"]
    assert cfg["job_env"][VAR] == "2" and _step(cfg, "Run unit tests (sharded)")["env"][VAR] == "2" and cfg["expr"]["matrix"] == {"shard": 2}
    # the cap does not ride `docker create --env=`: the container env stays these two, and the job env travels in steps.json
    assert seen["env"] == {"HOME": "/tmp", "LANG": "C.UTF-8"}
    # the driver, as the sandbox runs it, puts the job env on the step's process environment (the pytest the step starts inherits it)
    probe = {"context": "t", "root": str(tmp_path), "env": {}, "job_env": cfg["job_env"], "expr": cfg["expr"],
             "steps": [{"name": "workers", "argv": ["bash", "-e", "{0}"], "script": f'test "${VAR}" = 2\n'}]}
    for job_env, want in ((cfg["job_env"], "PASS"), ({}, "FAIL")):
        (tmp_path / "steps.json").write_text(json.dumps({**probe, "job_env": job_env}))
        subprocess.run([sys.executable, "-I", str(runner.STEPS_DRIVER), str(tmp_path / "steps.json"), str(tmp_path / "j.xml")], capture_output=True,
                       env={k: v for k, v in os.environ.items() if k != VAR})
        assert runner.parse_expr_junit(tmp_path / "j.xml")[0]["status"] == want, job_env


# ------------------------------------------------------------------ B4-2: a leg killed on timeout names the xdist worker that died
FAKE_DOCKER = """#!/bin/sh
case "$1" in
  create) echo created;;
  cp) if [ "$2" = "-a" ]; then cat >/dev/null; fi;;
  start) cat "$FAKE_LEG_OUT"; if [ "$FAKE_LEG_MODE" = hang ]; then exec sleep 30; fi; exit 0;;
  container) echo "Error: No such container: x" >&2; exit 1;;
  *) exit 0;;
esac
"""
XDIST_OUT = ("============================= test session starts ==============================\n"
             "created: 4/4 workers\n4 workers [812 items]\n\n"
             "........................................................................ [  8%]\n"
             "{marker}"
             "........................................................................ [ 17%]\n")
NODE_DOWN = "[gw1] node down: Not properly terminated"
OLD_REASON = "timeout after 2s (container killed; removal verified below or the run aborts)"


def fake_docker(tmp_path: Path, monkeypatch, out: str, mode: str) -> str:
    exe = tmp_path / "fakebin" / "docker"
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_text(FAKE_DOCKER)
    exe.chmod(0o755)
    (tmp_path / "leg-out.txt").write_text(out)
    monkeypatch.setenv("FAKE_LEG_OUT", str(tmp_path / "leg-out.txt"))
    monkeypatch.setenv("FAKE_LEG_MODE", mode)
    monkeypatch.setattr(runner, "stream_tree_tar", lambda *a, **k: 0)   # no tree to copy: the leg's output is what is judged
    return str(exe)


def contained(tmp_path: Path, monkeypatch, marker: str, mode: str = "hang") -> tuple:
    docker = fake_docker(tmp_path, monkeypatch, XDIST_OUT.format(marker=marker), mode)
    log = tmp_path / "leg.log"
    log.write_text("# leg header\n")
    spec = {"isolation": {"docker": docker, "user": "65534:65534", "image_id": "sha256:" + "0" * 64}}
    plan = {"run_id": "r", "worktree": str(tmp_path), "candidate_sha": "c" * 40}
    rc, err = runner.execute_contained("ctx.backend-tests.backend-shard-2", spec, tmp_path, plan, ["true"], {}, {}, {}, log, tmp_path / "j.xml", 2)
    return rc, err, log.read_text().splitlines()


def test_a_timeout_after_a_dead_xdist_worker_names_the_worker_and_its_log_line_and_is_no_verdict(tmp_path, monkeypatch):
    rc, err, lines = contained(tmp_path, monkeypatch, NODE_DOWN + "\nreplacing crashed worker gw1\n")
    n = lines.index(NODE_DOWN) + 1
    assert rc is None and n == 8 and err == (   # line 1 the leg header, 2 the isolation line
        f"timeout after 2s — an xdist worker died mid-run ('{NODE_DOWN}', log line {n}) and the controller never finished: a memory-cgroup "
        "OOM-kill is the measured cause on Pro (2026-10-07/08); no verdict (container killed; removal verified below or the run aborts)")


@pytest.mark.parametrize("marker,named", [
    ("worker 'gw2' crashed while running 'backend/tests/test_x.py::test_y'\n", "worker 'gw2' crashed"),
    ("worker gw3 crashed and worker restarting disabled\n", "worker gw3 crashed"),
    (f"{NODE_DOWN}\n[gw2] node down: Not properly terminated\n", NODE_DOWN),   # the first one, not the last
])
def test_every_xdist_wording_of_a_dead_worker_is_named_from_its_first_line(tmp_path, monkeypatch, marker, named):
    rc, err, _ = contained(tmp_path, monkeypatch, marker)
    assert rc is None and f"('{named}', log line 8)" in err and err.endswith("no verdict (container killed; removal verified below or the run aborts)")


@pytest.mark.parametrize("marker", ["", "[gw1] node down: keyboard-interrupt\n", "backend/tests/test_worker.py::test_worker_crashed_flag PASSED\n",
                                    "gw1 [ 50%] PASSED backend/tests/test_node_down.py::test_properly_terminated\n"])
def test_a_timeout_without_a_dead_worker_keeps_the_old_reason(tmp_path, monkeypatch, marker):
    rc, err, _ = contained(tmp_path, monkeypatch, marker)
    assert (rc, err) == (None, OLD_REASON)


def test_a_dead_worker_in_a_run_that_finished_changes_nothing(tmp_path, monkeypatch):
    # xdist replaced the worker and the controller finished: the rc and its junit judge, never the marker
    assert contained(tmp_path, monkeypatch, NODE_DOWN + "\n", mode="exit")[:2] == (0, None)


def test_a_backend_shard_leg_killed_after_a_dead_worker_is_an_error_never_a_fail(monkeypatch, tmp_path, base_repo):
    spec = _plan(monkeypatch, tmp_path, *base_repo, "Backend Tests (Python)")
    shard = {**next(j for j in spec["jobs"] if j["job_id"] == "backend-shard"), "timeout_s": 2}
    spec["isolation"] = {**ISO, "docker": fake_docker(tmp_path, monkeypatch, XDIST_OUT.format(marker=NODE_DOWN + "\n"), "hang")}
    monkeypatch.setenv("LOCALCI_MIN_FREE_GB", "0")
    monkeypatch.setattr(runner, "start_services", lambda *a, **k: ([], None, None))
    run_dir = tmp_path / "run"
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    (run_dir / "receipts").mkdir(exist_ok=True)
    out = runner._run_leg("ctx.backend-tests", spec, shard, {"shard": 2}, run_dir, {"run_id": "r", "worktree": str(base_repo[0]), "candidate_sha": "c" * 40},
                          {"changes": {}}, {}, runner._gh_expr())
    status, reason = out["infra"]
    assert status == "ERROR" and "an xdist worker died mid-run ('[gw1] node down: Not properly terminated', log line" in reason
    assert "OOM-kill" in reason and "no verdict" in reason and out["rc"] is None and out["steps"] == []
