"""B15: Pro's host floor of 100 GB, held through the run — the start floor, the mid-run eviction and its no-verdict."""
from __future__ import annotations

import json
import os
import sys
import textwrap
import time
from pathlib import Path

import pytest

from .fixture_repo import runner
from .test_merger import REPO, FakeRunner, mg, pr, world  # noqa: F401 — `world` is a fixture

# a docker that knows containers by label: `ps -aq --filter label=K[=V]` lists the matching ids, `rm -f -v ids` forgets them
FAKE_DOCKER = textwrap.dedent('''\
    #!{py}
    import json, sys
    a = sys.argv[1:]
    open({log!r}, "a").write(" ".join(a) + "\\n")
    ctrs = json.load(open({ctrs!r}))
    if a[:2] == ["ps", "-aq"]:
        want = a[a.index("--filter") + 1].removeprefix("label=")
        key, _, val = want.partition("=")
        print("\\n".join(i for i, v in ctrs.items() if (v == val if "=" in want else True)))
    elif a[:3] == ["rm", "-f", "-v"]:
        json.dump({{i: v for i, v in ctrs.items() if i not in a[3:]}}, open({ctrs!r}, "w"))
''')


def fake_docker(tmp_path: Path, containers: dict) -> tuple[str, Path, Path]:
    log, ctrs, exe = tmp_path / "docker.log", tmp_path / "ctrs.json", tmp_path / "docker"
    ctrs.write_text(json.dumps(containers))
    exe.write_text(FAKE_DOCKER.format(py=sys.executable, log=str(log), ctrs=str(ctrs)))
    exe.chmod(0o755)
    return str(exe), log, ctrs


@pytest.fixture
def fast(monkeypatch):
    monkeypatch.setattr(mg, "EVICT_SAMPLE_S", 0.2)


def test_the_floor_is_100_and_a_run_starts_at_110_by_default(world):   # noqa: F811
    assert (mg.HOST_FLOOR_GB, mg.START_MARGIN_GB, mg.EVICT_MARGIN_GB) == (100.0, 10.0, 1.5)
    world.gh.prs = [pr(1, world.head1)]
    args = ["tick", "--node", mg.HOST, "--repo", REPO, "--state-dir", str(world.state), "--remote-url", str(world.origin), "--python", "py"]
    assert mg.main([*args, "--host-free-gb", "109.9"]) == 0
    assert world.journal()[-1]["why"] == "host_below_floor" and world.journal()[-1]["start_floor_gb"] == 110.0
    assert not [r for r in world.journal() if r["kind"] == "decision"]
    assert mg.main([*args, "--host-free-gb", "110"]) == 0 and [r for r in world.journal() if r["kind"] == "decision"]


def test_the_runner_is_guarded_in_plan_and_run_and_the_status_read_is_not(world):   # noqa: F811
    world.gh.prs = [pr(1, world.head1)]
    assert world.tick() == 0
    by = {c["sub"]: c["guard"] for c in world.runner.calls}
    assert by["status"] is None
    for sub in ("plan", "run"):
        assert by[sub].floor_gb == 100.0 and by[sub].evict_gb == 101.5


def test_a_guard_off_flag_runs_the_runner_unguarded(world):   # noqa: F811
    world.gh.prs = [pr(1, world.head1)]
    assert mg.main(["tick", "--node", mg.HOST, "--repo", REPO, "--state-dir", str(world.state), "--remote-url", str(world.origin),
                    "--python", "py", "--host-floor-gb", "0"]) == 0
    assert {c["guard"] for c in world.runner.calls} == {None}


@pytest.mark.parametrize("free,low", [(101.5, False), (101.49, True), (140.0, False), (99.6, True)])
def test_the_eviction_floor_is_the_floor_plus_one_and_a_half(free, low):
    assert mg.HostGuard(100.0, Path("/x"), measure=lambda: free).breach() == (low, free)


def test_a_statvfs_that_fails_three_times_in_a_row_is_below_the_floor(tmp_path):
    reads = iter([None, None, None])
    guard = mg.HostGuard(100.0, tmp_path, measure=lambda: next(reads))
    assert [guard.breach()[0] for _ in range(3)] == [False, False, True]


def test_a_good_reading_resets_the_blind_count(tmp_path):
    reads = iter([None, None, 150.0, None, None])
    guard = mg.HostGuard(100.0, tmp_path, measure=lambda: next(reads))
    assert [guard.breach()[0] for _ in range(5)] == [False] * 5


def test_a_sample_under_the_eviction_floor_stops_the_group_and_removes_exactly_this_runs_containers(tmp_path, fast):
    run_a, run_b = tmp_path / "run-a", tmp_path / "run-b"
    docker, log, ctrs = fake_docker(tmp_path, {"mine1": mg.run_label(run_a), "mine2": mg.run_label(run_a), "theirs": mg.run_label(run_b),
                                               "other": "unrelated"})
    pidfile = tmp_path / "child.pid"
    argv = ["sh", "-c", f"sleep 60 & echo $! > {pidfile}; wait"]
    t0 = time.monotonic()
    with pytest.raises(mg.HostEvicted) as ev:
        mg.runner_exec(argv, tmp_path, dict(os.environ), 120, guard=mg.HostGuard(100.0, run_a, docker, measure=lambda: 98.0))
    assert time.monotonic() - t0 < 30 and ev.value.free_gb == 98.0 and ev.value.floor_gb == 100.0 and ev.value.removed == 2
    child = int(pidfile.read_text())
    for _ in range(50):   # the whole process group went, the sleep the shell started included
        try:
            os.kill(child, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        pytest.fail("the runner's child survived the eviction")
    assert set(json.loads(ctrs.read_text())) == {"theirs", "other"}   # another run's containers, and strangers, stay
    lines = log.read_text().splitlines()
    assert lines[0] == f"ps -aq --filter label=org.nuzantara.localci.run={mg.run_label(run_a)}" and lines[1].startswith("rm -f -v mine")
    assert not [ln for ln in lines if "theirs" in ln or "other" in ln]


def test_a_host_above_the_floor_never_evicts_and_the_runner_finishes(tmp_path, fast):
    res = mg.runner_exec([sys.executable, "-c", "import time; time.sleep(1); print('done')"], tmp_path, dict(os.environ), 30,
                         guard=mg.HostGuard(100.0, tmp_path, "/bin/false", measure=lambda: 300.0))
    assert res.returncode == 0 and res.stdout.strip() == "done"


def test_an_eviction_reads_the_checks_in_flight_from_the_run_state(tmp_path):
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "state.json").write_text(json.dumps({"checks": {"ctx.b": {"status": "RUNNING"}, "ctx.a": {"status": "RUNNING"},
                                                                          "ctx.c": {"status": "PASS"}}}))
    assert mg.HostGuard(100.0, tmp_path).in_flight() == ["ctx.a", "ctx.b"]
    assert mg.HostGuard(100.0, tmp_path / "none").in_flight() == []


def test_the_merger_label_is_the_runners(tmp_path):
    for d in (tmp_path, tmp_path / "a" / ".." / "b", Path("relative/run")):
        assert mg.run_label(d) == runner.run_label(d)


def evicting(overall_run_rc=0):
    """A runner that is evicted during `run` and runs normally on the next tick."""
    state = {"evict": True}
    inner = FakeRunner()

    def run(argv, cwd, env, timeout, guard=None):
        if argv[3] == "run" and state["evict"]:
            inner(argv, cwd, env, timeout, guard)   # plan was seen; the run is cut
            raise mg.HostEvicted(99.2, 100.0, ["ctx.backend-tests"], 3)
        return inner(argv, cwd, env, timeout, guard)
    return run, state, inner


def test_an_eviction_is_the_hosts_no_verdict_never_a_decision_and_the_pr_is_decided_again(world, monkeypatch, capsys):   # noqa: F811
    run, state, _ = evicting()
    monkeypatch.setattr(mg, "runner_exec", run)
    world.gh.prs = [pr(1, world.head1)]
    assert world.tick() == 0
    (ev,) = [r for r in world.journal() if r["kind"] == "evicted"]
    assert ev["why"] == "host_below_floor_during_run" and (ev["free_gb"], ev["floor_gb"], ev["context_in_flight"]) == (99.2, 100.0, ["ctx.backend-tests"])
    assert ev["pr"] == 1 and ev["head_sha"] == world.head1 and ev["containers_removed"] == 3
    assert not [r for r in world.journal() if r["kind"] in ("decision", "would_enqueue", "would_merge")]
    assert world.gql.mutations() == [] and not (world.state / "lease.json").exists() and not list((world.state / "cand").glob("*"))
    assert "evicted" in capsys.readouterr().out
    state["evict"] = False   # the next tick: the same (pr, head, base) is run again, not skipped as decided
    time.sleep(1.1)   # run dirs are named to the second
    assert world.tick() == 0
    (d,) = [r for r in world.journal() if r["kind"] == "decision"]
    assert d["pr"] == 1 and d["overall"] == "BLOCKED"
