"""B33 S2: per-container phase times, peak memory and layer size land in the receipt as DATA; no verdict reads them, a sampler failure
is a null and a string, and the same fixture run gives the same verdict with the sampler on and off."""
from __future__ import annotations

import ast
import json
import signal
import threading
from pathlib import Path

import pytest

from .fixture_repo import runner
from scripts.localci import capacity_report

# stats: 50MiB, 90MiB, 20MiB, then 20MiB again — the peak is the max, not the last; `ps` answers only while the container still exists
FAKE_DOCKER = """#!/bin/sh
echo "$@" >> "$FAKE_DIR/calls"
case "$1" in
  create) [ "$FAKE_CREATE" = fail ] && { echo "no space" >&2; exit 1; }; echo created;;
  cp) if [ "$2" = "-a" ]; then cat >/dev/null; else COPYFILE_DISABLE=1 tar -cf - -C "$FAKE_DIR" junit.xml; fi;;
  start) sleep "$FAKE_RUN_S"; echo "run output"; exit 0;;
  stats) [ "$FAKE_STATS" = fail ] && exit 1
         [ "$FAKE_STATS" = hang ] && exec sleep 3
         [ "$FAKE_STATS" = zero ] && { echo "0B / 0B"; exit 0; }
         [ -n "$FAKE_STATS_SLOW" ] && sleep 0.6
         n=$(cat "$FAKE_DIR/n" 2>/dev/null || echo 0); echo $((n+1)) > "$FAKE_DIR/n"
         case "$n" in 0) echo "50MiB / 4GiB";; 1) echo "90MiB / 4GiB";; *) echo "20MiB / 4GiB";; esac;;
  ps) [ -n "$FAKE_PS_SIGNAL" ] && { kill -INT $PPID; sleep 1; }
      [ "$FAKE_PS" = hang ] && exec sleep 3
      [ -e "$FAKE_DIR/removed" ] && exit 0; [ "$FAKE_STATS" = fail ] && exit 1; echo "2.5MB (virtual 1.1GB)";;
  rm) touch "$FAKE_DIR/removed";;
  kill) exit 0;;
  container) echo "Error: No such container: x" >&2; exit 1;;
  *) exit 0;;
esac
"""
JUNIT = '<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase classname="a" name="t"/></testsuite>'


@pytest.fixture
def world(tmp_path, monkeypatch):
    d = tmp_path / "fake"
    d.mkdir()
    exe = d / "docker"
    exe.write_text(FAKE_DOCKER)
    exe.chmod(0o755)
    (d / "junit.xml").write_text(JUNIT)
    for k, v in (("FAKE_DIR", d), ("FAKE_RUN_S", "0.4"), ("FAKE_CREATE", "ok"), ("FAKE_STATS", "ok")):
        monkeypatch.setenv(k, str(v))
    monkeypatch.setattr(runner, "stream_tree_tar", lambda *a, **k: 0)
    monkeypatch.setattr(runner, "SANDBOX_SAMPLE_EVERY_S", 0.1)
    spec = {"isolation": {"docker": str(exe), "user": "65534:65534", "image_id": "sha256:" + "0" * 64}}
    plan = {"run_id": "r", "worktree": str(tmp_path), "candidate_sha": "c" * 40}

    def run(timeout: int = 20, probe: bool = True, tag: str = "x"):
        p = runner.new_probe("ctx.t") if probe else None
        log, junit = tmp_path / f"{tag}.log", tmp_path / f"{tag}.xml"
        log.write_text("# header\n")
        rc, err = runner.execute_contained("ctx.t", spec, tmp_path, plan, ["true"], {}, {}, {}, log, junit, timeout, probe=p)
        return rc, err, p, log.read_text(), junit.read_text() if junit.exists() else None

    run.calls = lambda: (d / "calls").read_text().splitlines() if (d / "calls").exists() else []
    run.reset = lambda: [(d / f).unlink(missing_ok=True) for f in ("calls", "n", "removed")]
    return run


def test_every_phase_the_peak_and_the_layer_are_recorded_and_the_peak_is_the_max_not_the_last(world):
    rc, err, p, _, _ = world()
    assert (rc, err) == (0, None)
    for k in ("t_create", "t_copy_in", "t_start_to_exit", "t_junit", "t_remove"):
        assert isinstance(p[k], float) and p[k] >= 0, k
    assert p["t_start_to_exit"] >= 0.3
    assert p["mem_peak_bytes"] == 90 * 2**20 and p["disk_rw_bytes"] == 2_500_000 and p["sampler_error"] is None and p["sampler"] == "on"


def test_the_sampler_thread_is_gone_when_the_container_call_returns(world, monkeypatch):
    monkeypatch.setenv("FAKE_STATS_SLOW", "1")   # a sample in flight when the container exits: the call waits for it
    world()
    assert not [t for t in threading.enumerate() if t.name == "localci-mem-sampler"]


def test_the_layer_is_read_before_the_container_is_removed(world):
    calls = [c.split()[0] for c in (world(), world.calls())[1]]
    assert calls.index("ps") < calls.index("rm")


def test_a_timeout_still_records_the_run_phase_the_peak_and_the_layer(world, monkeypatch):
    monkeypatch.setenv("FAKE_RUN_S", "5")
    rc, err, p, _, _ = world(timeout=1)
    assert rc is None and err.startswith("timeout after 1s") and p["t_start_to_exit"] >= 1 and p["mem_peak_bytes"] and p["disk_rw_bytes"] == 2_500_000


def test_sampler_off_runs_no_stats_and_no_ps_and_keeps_the_host_times(world, monkeypatch):
    monkeypatch.setenv(runner.SANDBOX_SAMPLER_ENV, "0")
    _, _, p, _, _ = world()
    assert p["sampler"] == "off" and p["mem_peak_bytes"] is None and p["disk_rw_bytes"] is None and p["sampler_error"] is None
    assert p["t_create"] is not None and p["t_remove"] is not None
    assert not [c for c in world.calls() if c.split()[0] in ("stats", "ps")]


def test_a_failed_create_leaves_the_later_phases_null_and_never_asks_for_a_layer(world, monkeypatch):
    monkeypatch.setenv("FAKE_CREATE", "fail")
    rc, err, p, _, _ = world()
    assert rc is None and err.startswith("container create failed")
    assert p["t_create"] is not None and p["t_copy_in"] is None and p["t_start_to_exit"] is None and p["t_junit"] is None
    assert p["mem_peak_bytes"] is None and p["disk_rw_bytes"] is None
    assert not [c for c in world.calls() if c.split()[0] in ("stats", "ps")]


def test_the_verdict_of_a_run_is_identical_with_the_sampler_on_off_and_failing(world, monkeypatch, tmp_path):
    def verdict(tag):
        rc, err, _, log, junit = world(tag=tag)
        return rc, err, log, junit, runner.classify_pytest(rc, runner.parse_junit(tmp_path / f"{tag}.xml"))

    on = verdict("on")
    monkeypatch.setenv(runner.SANDBOX_SAMPLER_ENV, "0")
    off = verdict("off")
    monkeypatch.delenv(runner.SANDBOX_SAMPLER_ENV)
    monkeypatch.setenv("FAKE_STATS", "fail")
    boom = verdict("boom")
    assert on == off == boom and on[4][0] == "PASS"


def test_a_sampler_failure_is_null_plus_a_string_and_changes_nothing(world, monkeypatch):
    monkeypatch.setenv("FAKE_STATS", "fail")
    rc, err, p, _, _ = world()
    assert (rc, err) == (0, None) and p["mem_peak_bytes"] is None and p["disk_rw_bytes"] is None
    assert "docker stats" in p["sampler_error"] and "docker ps -s" in p["sampler_error"] and len(p["sampler_error"]) <= 200


def test_an_exception_inside_the_sampler_and_the_layer_probe_is_swallowed_into_the_receipt(world, monkeypatch):
    def boom(_):
        raise RuntimeError("parser exploded")
    monkeypatch.setattr(runner, "parse_size_bytes", boom)
    rc, err, p, _, _ = world()
    assert (rc, err) == (0, None) and p["mem_peak_bytes"] is None and p["disk_rw_bytes"] is None
    assert "docker stats RuntimeError" in p["sampler_error"] and "docker ps -s RuntimeError" in p["sampler_error"]


def test_no_probe_is_the_old_call(world):
    rc, err, p, _, junit = world(probe=False)
    assert (rc, err, p) == (0, None, None) and junit == JUNIT


@pytest.mark.parametrize("text,want", [("12.3MB", 12_300_000), ("1.5GiB", 1_610_612_736), ("0B", 0), ("  90MiB ", 94_371_840), ("2kB", 2000),
                                       ("", None), (None, None), ("abc", None), ("5 parsecs", None)])
def test_docker_sizes_parse_to_bytes_or_none(text, want):
    assert runner.parse_size_bytes(text) == want


# ------------------------------------------------------------------ nothing that decides reads the new fields
KEYS = {"sandbox", "mem_peak_bytes", "disk_rw_bytes", "sampler", "sampler_error", "t_create", "t_copy_in", "t_start_to_exit", "t_junit", "t_remove"}
DECIDERS = ("steps_verdict", "classify_pytest", "classify_contained_steps", "evaluate_contexts", "overall", "gate_pending_of", "host_disk_full",
            "parse_junit", "parse_step_junit", "parse_expr_junit")


def _mentions(node: ast.AST) -> set:
    return {n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in KEYS} | \
           {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute) and n.attr in KEYS} | {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and n.id in KEYS}


def test_no_verdict_function_of_the_runner_names_a_probe_field():
    tree = ast.parse(Path(runner.__file__).read_text())
    fns = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert all(d in fns for d in DECIDERS), [d for d in DECIDERS if d not in fns]
    assert {d: _mentions(fns[d]) for d in DECIDERS if _mentions(fns[d])} == {}


def test_the_merger_and_the_hosted_compare_never_name_a_probe_field():
    base = Path(runner.__file__).parent
    assert {f: _mentions(ast.parse((base / f).read_text())) for f in ("merger.py", "hosted_compare.py", "tick_chain.py", "prune.py")
            if _mentions(ast.parse((base / f).read_text()))} == {}


# ------------------------------------------------------------------ where the probes land, and the reader
def test_job_rows_carry_the_leg_probes_beside_the_old_keys():
    legs = [{"label": "a", "rc": 0, "seconds": 1.0, "cpu": 0.5, "sandbox": [{"name": "x"}], "steps": []}, {"label": "b", "rc": 1, "seconds": 2.0, "cpu": 0.0}]
    assert runner._job_rows(legs) == [{"label": "a", "rc": 0, "seconds": 1.0, "cpu": 0.5, "sandbox": [{"name": "x"}]},
                                      {"label": "b", "rc": 1, "seconds": 2.0, "cpu": 0.0, "sandbox": []}]


def _probe(mem=None, disk=None, create=1.0, copy=10.0, junit=1.0, remove=2.0):
    return {"name": "n", "sampler": "on", "t_create": create, "t_copy_in": copy, "t_start_to_exit": 100.0, "t_junit": junit, "t_remove": remove,
            "mem_peak_bytes": mem, "disk_rw_bytes": disk, "sampler_error": None}


def _receipt(root: Path, run: str, check: str, result: dict):
    (root / run / "receipts").mkdir(parents=True, exist_ok=True)
    (root / run / "receipts" / f"{check}.json").write_text(json.dumps({"check": check, "result": result}))


def test_the_report_prints_p95_per_context_from_both_receipt_shapes_and_ignores_nulls(tmp_path, capsys):
    for i in range(1, 21):   # 20 containers of one jobs context: p95 by nearest rank is the 19th
        _receipt(tmp_path, f"run{i}", "ctx.backend-tests", {"jobs": [{"label": "shard", "sandbox": [_probe(mem=i * 2**30, disk=i * 2**20, copy=float(i))]}]})
    _receipt(tmp_path, "run1", "ctx.antidotes", {"sandbox": [_probe(mem=None, disk=3 * 2**20), _probe(mem=2**30, disk=None)]})
    _receipt(tmp_path, "run1", "ctx.bad", {"status": "ERROR"})
    (tmp_path / "run1" / "receipts" / "junk.json").write_text("{not json")
    rows = {r["context"]: r for r in capacity_report.table(capacity_report.collect([tmp_path]))}
    assert set(rows) == {"ctx.backend-tests", "ctx.antidotes"}
    b = rows["ctx.backend-tests"]
    assert (b["n"], b["p95_mem_gib"], b["p95_disk_mib"], b["p95_copy_in_s"], b["p95_setup_s"]) == (20, 19.0, 19.0, 19.0, 19.0 + 4.0)
    a = rows["ctx.antidotes"]
    assert (a["n"], a["p95_mem_gib"], a["p95_disk_mib"]) == (2, 1.0, 3.0)
    assert capacity_report.main([str(tmp_path)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].split() == ["context", "n", "p95_mem_gib", "p95_disk_mib", "p95_setup_s", "p95_copy_in_s"] and len(out) == 3


def test_a_context_with_no_numbers_prints_dashes(tmp_path, capsys):
    _receipt(tmp_path, "r", "ctx.x", {"sandbox": [{"name": "n", "sampler": "off"}]})
    assert capacity_report.main([str(tmp_path)]) == 0
    assert capsys.readouterr().out.splitlines()[1].split() == ["ctx.x", "1", "-", "-", "-", "-"]


# ------------------------------------------------------------------ the gate's findings: cleanup, clock, timeouts, zero samples
@pytest.fixture
def sigint_raises():
    old = signal.signal(signal.SIGINT, signal.default_int_handler)   # a background launch (nohup, &) leaves SIGINT ignored
    yield
    signal.signal(signal.SIGINT, old)


def test_a_signal_during_the_layer_read_still_removes_the_container(world, monkeypatch, sigint_raises):
    monkeypatch.setenv("FAKE_PS_SIGNAL", "1")   # SIGINT to the runner while `docker ps -s` runs: cmd_run turns SIGTERM into this
    with pytest.raises(KeyboardInterrupt):
        world()
    calls = [c.split()[0] for c in world.calls()]
    assert "ps" in calls and "rm" in calls and calls.index("ps") < calls.index("rm")


def test_the_samplers_last_sample_is_not_counted_in_the_run_phase(world, monkeypatch):
    monkeypatch.setenv("FAKE_STATS_SLOW", "1")
    monkeypatch.setattr(runner, "SANDBOX_SAMPLE_EVERY_S", 0.05)
    monkeypatch.setenv("FAKE_RUN_S", "0.3")
    monkeypatch.setattr(runner, "SANDBOX_STATS_TIMEOUT_S", 20)
    _, _, p, _, _ = world()   # a sample (0.6 s) is still in flight when the container exits at 0.3 s: the join waits for it, the clock does not
    assert 0.3 <= p["t_start_to_exit"] < 0.55, p["t_start_to_exit"]


def test_a_pre_start_zero_reading_is_no_sample(world, monkeypatch):
    monkeypatch.setenv("FAKE_STATS", "zero")
    rc, err, p, _, _ = world()
    assert (rc, err) == (0, None) and p["mem_peak_bytes"] is None and p["sampler_error"] is None


def test_a_stats_call_that_hangs_is_cut_at_its_timeout_and_recorded(world, monkeypatch):
    monkeypatch.setenv("FAKE_STATS", "hang")
    monkeypatch.setattr(runner, "SANDBOX_STATS_TIMEOUT_S", 0.3)
    rc, err, p, _, _ = world()
    assert (rc, err) == (0, None) and p["mem_peak_bytes"] is None and "docker stats TimeoutExpired" in p["sampler_error"]


def test_a_layer_read_that_hangs_is_cut_at_its_timeout_and_recorded(world, monkeypatch):
    monkeypatch.setenv("FAKE_PS", "hang")
    monkeypatch.setattr(runner, "SANDBOX_PS_TIMEOUT_S", 0.3)
    rc, err, p, _, _ = world()
    assert (rc, err) == (0, None) and p["disk_rw_bytes"] is None and "docker ps -s TimeoutExpired" in p["sampler_error"] and p["t_remove"] is not None


# ------------------------------------------------------------------ where the probe lands: candidate checks, legs, egress, jobs rows, receipts
LOUD = {"sampler": "on", "t_create": None, "t_copy_in": None, "t_start_to_exit": None, "t_junit": None, "t_remove": None, "mem_peak_bytes": None,
        "disk_rw_bytes": None, "sampler_error": "docker stats RuntimeError; docker ps -s RuntimeError"}
CLEAN = {"sampler": "on", "t_create": 1.0, "t_copy_in": 2.0, "t_start_to_exit": 3.0, "t_junit": 0.5, "t_remove": 0.7, "mem_peak_bytes": 2**30,
         "disk_rw_bytes": 2**20, "sampler_error": None}


def _write_junit(junit: Path, names: list) -> None:
    suite = runner.ET.Element("testsuite")
    for n in names:
        runner.ET.SubElement(suite, "testcase", name=n, time="0.1")
    runner.ET.ElementTree(suite).write(junit)


def _candidate(tmp_path, monkeypatch, kind: str, probe_values: dict, failing: bool = False) -> dict:
    wt = tmp_path / "wt"
    wt.mkdir(exist_ok=True)
    monkeypatch.setattr(runner, "history_delta", lambda *a: {"added": [], "base": []})
    monkeypatch.setattr(runner, "tree_pack_ship_safe", lambda run_dir, plan: (None, {}, None))

    def fake(name, spec, run_dir, plan, inner, overrides, extra, env, log, junit, *a, probe=None, **k):
        probe.update(probe_values)
        if failing:
            return None, "container create failed (the test)"
        if kind == "pytest":
            junit.write_text('<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase classname="a" name="t"/></testsuite>')
        else:
            _write_junit(junit, ["s"])
        return 0, None
    monkeypatch.setattr(runner, "execute_contained", fake)
    iso = {"docker": "docker", "user": "1:1", "image_id": "sha256:" + "a" * 64, "pythons": {}}
    spec = ({"kind": "pytest", "cwd": str(wt), "modules": ["t.py"], "isolation": iso} if kind == "pytest" else
            {"kind": "contained_steps", "context": "t", "cwd": str(wt), "isolation": iso, "git_index": False, "history": {"added": [], "base": []},
             "path_prefix": "", "venv": False, "env": {}, "steps": [{"name": "s", "argv": ["true"]}],
             "driver_sha256": runner.sha256_bytes(runner.STEPS_DRIVER.read_bytes())})
    plan = {"worktree": str(wt), "base_sha": "b" * 40, "candidate_sha": "c" * 40, "run_id": "r"}
    return runner._execute_candidate_contained("ctx.t", spec, tmp_path, plan, 60, tmp_path / "log", tmp_path / "junit.xml")


@pytest.mark.parametrize("kind", ["pytest", "contained_steps"])
@pytest.mark.parametrize("failing", [False, True], ids=["ran", "no-verdict"])
def test_every_return_of_a_candidate_check_carries_its_probe_and_a_loud_probe_changes_no_verdict(tmp_path, monkeypatch, kind, failing):
    for d in ("a", "b"):
        (tmp_path / d).mkdir()
    clean, loud = _candidate(tmp_path / "a", monkeypatch, kind, CLEAN, failing), _candidate(tmp_path / "b", monkeypatch, kind, LOUD, failing)
    assert [x["sandbox"][0]["name"] for x in (clean, loud)] == ["ctx.t", "ctx.t"]
    assert loud["sandbox"][0]["sampler_error"] and clean["sandbox"][0]["mem_peak_bytes"] == 2**30
    strip = lambda r: {k: r.get(k) for k in ("status", "reason", "rc", "isolation")}   # noqa: E731
    assert strip(clean) == strip(loud) and clean["status"] == ("ERROR" if failing else "PASS")


def _leg_spec_job(steps: list):
    job = {"job_id": "j", "legs": [{}], "needs": [], "steps": steps, "path_prefix": "", "venv": False, "job_env": {}, "services": [], "checkout": None,
           "image_id": "sha256:img", "timeout_s": 60}
    spec = {"context": "t", "jobs": [job], "needs": {}, "judge_modified": [], "history": None, "expr": {"github": {}, "runner": {"temp": "missing"}},
            "isolation": {"mode": "container", "docker": "docker", "image_id": "sha256:img"},
            "driver_sha256": runner.sha256_bytes(runner.STEPS_DRIVER.read_bytes()), "expr_sha256": runner.sha256_bytes(runner.GH_EXPR.read_bytes())}
    return spec


def _jobs(tmp_path, monkeypatch, probe_values: dict) -> dict:
    for d in ("receipts", "logs"):
        (tmp_path / d).mkdir(exist_ok=True)
    monkeypatch.setattr(runner, "tree_pack_ship_safe", lambda run_dir, plan: (None, {}, ""))
    monkeypatch.setattr(runner, "disk_floor_refusal", lambda *a: None)
    monkeypatch.setattr(runner, "start_services", lambda *a: ([], None, None))

    def fake(name, spec, run_dir, plan, inner, overrides, extra, env, log, junit, *a, probe=None, **k):
        probe.update(probe_values)
        _write_junit(junit, ["audit"] if name.endswith(".egress") else ["s", "audit"])
        return 0, None
    monkeypatch.setattr(runner, "execute_contained", fake)
    steps = [{"name": "s", "argv": ["true"]}, {"name": "audit", "argv": ["true"], "side": {"where": "egress", "inputs": ["a.txt"], "rewrite": []}}]
    return runner._execute_jobs("ctx.t", _leg_spec_job(steps), tmp_path, {"run_id": "r", "worktree": str(tmp_path)}, tmp_path / "ctx.log")


def test_a_leg_and_its_egress_sandbox_each_leave_a_probe_on_the_jobs_row_and_a_loud_one_changes_no_verdict(tmp_path, monkeypatch):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    clean, loud = _jobs(tmp_path / "a", monkeypatch, CLEAN), _jobs(tmp_path / "b", monkeypatch, LOUD)
    for res in (clean, loud):
        assert [p["name"] for p in res["jobs"][0]["sandbox"]] == ["ctx.t.j.egress", "ctx.t.j"], res
    assert clean["jobs"][0]["sandbox"][0]["mem_peak_bytes"] == 2**30 and loud["jobs"][0]["sandbox"][1]["sampler_error"]
    strip = lambda r: {**{k: v for k, v in r.items() if k not in ("jobs", "duration_s", "log", "steps")}, "steps": [(s["name"], s["status"]) for s in r["steps"]],
                       "rows": [{k: v for k, v in j.items() if k not in ("sandbox", "seconds")} for j in r["jobs"]]}   # noqa: E731
    assert strip(clean) == strip(loud) and clean["status"] == "PASS"


@pytest.mark.usefixtures("fake_env")
def test_a_run_stores_the_probe_in_the_receipt_and_no_status_reads_it(tmp_path, monkeypatch):
    from .test_contexts_exec import host_ctx, planned
    loud = [dict(LOUD, name="ctx.judge"), dict(CLEAN, name="ctx.judge.egress")]
    seen, real = {}, runner.execute

    def execute(name, spec, run_dir, plan, timeout):
        res = real(name, spec, run_dir, plan, timeout)
        return {**res, "sandbox": loud} if name == "ctx.judge" and seen.get("on") else res
    monkeypatch.setattr(runner, "execute", execute)
    out = {}
    for tag, on in (("plain", False), ("loud", True)):
        seen["on"] = on
        (tmp_path / tag).mkdir()
        fx = planned(tmp_path / tag, {"docs/new.md": "clean\n"}, host_ctx())
        runner.main(["run", "--run-dir", str(fx["run"])])
        s = runner.compute_status(fx["run"])
        out[tag] = ({n: (c["status"], c["reason"]) for n, c in s["checks"].items()}, s["overall"], s["contexts"]["results"], s["checks"]["ctx.judge"]["receipt"])
    assert out["plain"][:3] == out["loud"][:3] and out["loud"][0]["ctx.judge"][0] == "PASS"
    rec = json.loads(Path(out["loud"][3]).read_text())
    assert rec["result"]["sandbox"] == loud and "sandbox" not in json.loads(Path(out["plain"][3]).read_text())["result"]
