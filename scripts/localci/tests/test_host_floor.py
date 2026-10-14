"""B15: Pro's host floor of 90 GB, held through the run — the start floor, the mid-run eviction and its no-verdict."""
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


def test_the_floor_is_90_and_a_run_starts_at_100_by_default(world):   # noqa: F811
    assert (mg.HOST_FLOOR_GB, mg.START_MARGIN_GB, mg.EVICT_MARGIN_GB) == (90.0, 10.0, 1.5)
    world.gh.prs = [pr(1, world.head1)]
    args = ["tick", "--node", mg.HOST, "--repo", REPO, "--state-dir", str(world.state), "--remote-url", str(world.origin), "--python", "py"]
    assert mg.main([*args, "--host-free-gb", "99.9"]) == 0
    assert world.journal()[-1]["why"] == "host_below_floor" and world.journal()[-1]["start_floor_gb"] == 100.0
    assert not [r for r in world.journal() if r["kind"] == "decision"]
    assert mg.main([*args, "--host-free-gb", "100"]) == 0 and [r for r in world.journal() if r["kind"] == "decision"]


def test_the_runner_is_guarded_in_plan_and_run_and_the_status_read_is_not(world):   # noqa: F811
    world.gh.prs = [pr(1, world.head1)]
    assert world.tick() == 0
    by = {c["sub"]: c["guard"] for c in world.runner.calls}
    assert by["status"] is None
    for sub in ("plan", "run"):
        assert by[sub].floor_gb == 90.0 and by[sub].evict_gb == 91.5


def test_a_guard_off_flag_runs_the_runner_unguarded(world):   # noqa: F811
    world.gh.prs = [pr(1, world.head1)]
    assert mg.main(["tick", "--node", mg.HOST, "--repo", REPO, "--state-dir", str(world.state), "--remote-url", str(world.origin),
                    "--python", "py", "--host-floor-gb", "0"]) == 0
    assert {c["guard"] for c in world.runner.calls} == {None}


@pytest.mark.parametrize("free,low", [(91.5, False), (91.49, True), (140.0, False), (89.6, True)])
def test_the_eviction_floor_is_the_floor_plus_one_and_a_half(free, low):
    assert mg.HostGuard(90.0, Path("/x"), measure=lambda: free).breach() == (low, free)


def test_a_statvfs_that_fails_three_times_in_a_row_is_below_the_floor(tmp_path):
    reads = iter([None, None, None])
    guard = mg.HostGuard(90.0, tmp_path, measure=lambda: next(reads))
    assert [guard.breach()[0] for _ in range(3)] == [False, False, True]


def test_a_good_reading_resets_the_blind_count(tmp_path):
    reads = iter([None, None, 150.0, None, None])
    guard = mg.HostGuard(90.0, tmp_path, measure=lambda: next(reads))
    assert [guard.breach()[0] for _ in range(5)] == [False] * 5


def test_a_sample_under_the_eviction_floor_stops_the_group_and_removes_exactly_this_runs_containers(tmp_path, fast):
    run_a, run_b = tmp_path / "run-a", tmp_path / "run-b"
    docker, log, ctrs = fake_docker(tmp_path, {"mine1": mg.run_label(run_a), "mine2": mg.run_label(run_a), "theirs": mg.run_label(run_b),
                                               "other": "unrelated"})
    pidfile = tmp_path / "child.pid"
    argv = ["sh", "-c", f"sleep 60 & echo $! > {pidfile}; wait"]
    t0 = time.monotonic()
    with pytest.raises(mg.HostEvicted) as ev:
        mg.runner_exec(argv, tmp_path, dict(os.environ), 120, guard=mg.HostGuard(90.0, run_a, docker, measure=lambda: 88.0))
    assert time.monotonic() - t0 < 30 and ev.value.free_gb == 88.0 and ev.value.floor_gb == 90.0 and ev.value.removed == 2
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
                         guard=mg.HostGuard(90.0, tmp_path, "/bin/false", measure=lambda: 300.0))
    assert res.returncode == 0 and res.stdout.strip() == "done"


def test_an_eviction_reads_the_checks_in_flight_from_the_run_state(tmp_path):
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "state.json").write_text(json.dumps({"checks": {"ctx.b": {"status": "RUNNING"}, "ctx.a": {"status": "RUNNING"},
                                                                          "ctx.c": {"status": "PASS"}}}))
    assert mg.HostGuard(90.0, tmp_path).in_flight() == ["ctx.a", "ctx.b"]
    assert mg.HostGuard(90.0, tmp_path / "none").in_flight() == []


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
            raise mg.HostEvicted(89.2, 90.0, ["ctx.backend-tests"], 3)
        return inner(argv, cwd, env, timeout, guard)
    return run, state, inner


def test_an_eviction_is_the_hosts_no_verdict_never_a_decision_and_the_pr_is_decided_again(world, monkeypatch, capsys):   # noqa: F811
    run, state, _ = evicting()
    monkeypatch.setattr(mg, "runner_exec", run)
    world.gh.prs = [pr(1, world.head1)]
    assert world.tick() == 0
    (ev,) = [r for r in world.journal() if r["kind"] == "evicted"]
    assert ev["why"] == "host_below_floor_during_run" and (ev["free_gb"], ev["floor_gb"], ev["context_in_flight"]) == (89.2, 90.0, ["ctx.backend-tests"])
    assert ev["pr"] == 1 and ev["head_sha"] == world.head1 and ev["containers_removed"] == 3
    assert not [r for r in world.journal() if r["kind"] in ("decision", "would_enqueue", "would_merge")]
    assert world.gql.mutations() == [] and not (world.state / "lease.json").exists() and not list((world.state / "cand").glob("*"))
    assert "evicted" in capsys.readouterr().out
    state["evict"] = False   # the next tick: the same (pr, head, base) is run again, not skipped as decided
    time.sleep(1.1)   # run dirs are named to the second
    assert world.tick() == 0
    (d,) = [r for r in world.journal() if r["kind"] == "decision"]
    assert d["pr"] == 1 and d["overall"] == "BLOCKED"


def eviction(pr_n, head, base, ts):
    return {"kind": "evicted", "pr": pr_n, "head_sha": head, "base_sha": base, "ts": ts}


def test_an_evicted_head_rotates_behind_the_others_and_is_never_decided(world):   # noqa: F811
    prs = [pr(1, world.head1, created="2026-01-01"), pr(3, "3" * 40, created="2026-10-01")]
    todo, _ = mg.triage(prs, REPO, [], world.base)
    assert [p["number"] for p in todo] == [1, 3]   # nothing journalled: the oldest first
    todo, _ = mg.triage(prs, REPO, [eviction(1, world.head1, world.base, "2026-10-11T10:00:00Z")], world.base)
    assert [p["number"] for p in todo] == [3, 1]   # the evicted head is an attempt for ORDER: behind a head never tried; still undecided


def test_after_evict_cap_evictions_the_key_is_skipped_and_journalled_once_until_the_base_moves(world, monkeypatch):   # noqa: F811
    world.gh.prs = [pr(1, world.head1)]
    recs = [eviction(1, world.head1, world.base, f"2026-10-11T10:0{i}:00Z") for i in range(mg.EVICT_CAP)]
    capped: list = []
    now = mg._epoch("2026-10-11T11:00:00Z")
    todo, _ = mg.triage(world.gh.prs, REPO, recs[:-1], world.base, evict_capped=capped, now_s=now)
    assert [p["number"] for p in todo] == [1] and capped == []   # one short of the cap: still tried
    todo, _ = mg.triage(world.gh.prs, REPO, recs, world.base, evict_capped=capped, now_s=now)
    assert todo == [] and [p["number"] for p in capped] == [1]
    todo, _ = mg.triage(world.gh.prs, REPO, recs, "f" * 40, evict_capped=[], now_s=now)
    assert [p["number"] for p in todo] == [1]   # the base moved: a fresh key
    world.state.mkdir(parents=True, exist_ok=True)
    for line in recs:
        mg.journal(world.state, {**line, "ts": mg.now()})
    assert world.tick() == 0 and world.tick() == 0
    skips = [r for r in world.journal() if r["kind"] == "skipped" and r["why"] == "evicted_cap"]
    assert len(skips) == 1 and skips[0]["pr"] == 1 and not [r for r in world.journal() if r["kind"] == "decision"]


def window_world(world, stamps, now="2026-10-12T12:00:00Z"):
    world.gh.prs = [pr(1, world.head1)]
    recs = [eviction(1, world.head1, world.base, t) for t in stamps]
    capped: list = []
    todo, _ = mg.triage(world.gh.prs, REPO, recs, world.base, evict_capped=capped, now_s=mg._epoch(now))
    return [p["number"] for p in todo], [p["number"] for p in capped]


OLD = "2026-10-10T10:00:00Z"
NEW = "2026-10-12T11:00:00Z"


def test_three_evictions_older_than_the_window_do_not_cap_the_key(world):   # noqa: F811
    assert window_world(world, [OLD] * 3) == ([1], [])


def test_three_evictions_inside_the_window_cap_the_key(world):   # noqa: F811
    assert window_world(world, [NEW] * 3) == ([], [1])


def test_two_old_and_one_recent_eviction_do_not_cap_the_key(world):   # noqa: F811
    assert window_world(world, [OLD, OLD, NEW]) == ([1], [])


def test_an_eviction_with_an_unreadable_ts_counts_toward_the_cap(world):   # noqa: F811
    assert window_world(world, [OLD, "garbage", None]) == ([1], [])   # one counted: not capped
    assert window_world(world, ["garbage", None, "x"]) == ([], [1])


def test_the_window_edge_is_inside(world):   # noqa: F811
    assert window_world(world, ["2026-10-12T06:00:00Z"] * 3) == ([], [1])   # exactly EVICT_WINDOW_S old
    assert window_world(world, ["2026-10-12T05:59:59Z"] * 3) == ([1], [])


def test_an_old_eviction_still_orders_the_head_behind_the_others(world):   # noqa: F811
    prs = [pr(1, world.head1, created="2026-01-01"), pr(3, "3" * 40, created="2026-10-01")]
    todo, _ = mg.triage(prs, REPO, [eviction(1, world.head1, world.base, OLD)], world.base, now_s=mg._epoch("2026-10-12T12:00:00Z"))
    assert [p["number"] for p in todo] == [3, 1]


def test_a_tick_reads_the_clock_when_it_counts_evictions(world):   # noqa: F811
    world.gh.prs = [pr(1, world.head1), pr(2, world.head2)]
    world.state.mkdir(parents=True, exist_ok=True)
    stamp = lambda ago_s: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - ago_s))
    for n, head, ago in ((1, world.head1, 7 * 3600), (2, world.head2, 3600)):
        for _ in range(mg.EVICT_CAP):
            mg.journal(world.state, {**eviction(n, head, world.base, stamp(ago))})
    world.tick()
    skipped = {r["pr"] for r in world.journal() if r["kind"] == "skipped" and r["why"] == "evicted_cap"}
    assert skipped == {2}   # 7 h old: history; 1 h old: a cap


def test_the_floor_print_names_both_floors(world, capsys):   # noqa: F811
    world.gh.prs = [pr(1, world.head1)]
    args = ["tick", "--node", mg.HOST, "--repo", REPO, "--state-dir", str(world.state), "--remote-url", str(world.origin), "--python", "py"]
    assert mg.main([*args, "--host-free-gb", "50"]) == 0
    assert "floor_gb=90 start_floor_gb=100" in capsys.readouterr().out


@pytest.mark.parametrize("raw,watched", [("", False), ("abc", False), ("1", False), ("0", False), ("4242", True)])
def test_the_runner_watches_the_merger_pid_only_when_it_is_named(raw, watched, monkeypatch):
    started = []
    monkeypatch.setattr(runner.threading.Thread, "start", lambda self: started.append(self))
    assert (runner.watch_parent(environ={runner.PARENT_PID_ENV: raw}) is not None) is watched and bool(started) is watched


def test_a_gone_merger_makes_the_runner_term_its_own_group(monkeypatch):
    sent = []
    monkeypatch.setattr(runner, "parent_gone", lambda pid: True)
    monkeypatch.setattr(runner.os, "getpgrp", lambda: os.getpid())
    monkeypatch.setattr(runner.os, "killpg", lambda pg, sig: sent.append((pg, sig)))
    runner.watch_parent(poll_s=0.01, environ={runner.PARENT_PID_ENV: "4242"}).join(5)
    assert sent == [(os.getpid(), runner.signal.SIGTERM)]


def test_parent_gone_reads_a_dead_pid_as_gone_and_a_live_one_as_here():
    import subprocess
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    assert runner.parent_gone(dead.pid) is True and runner.parent_gone(os.getpid()) is False


def test_the_merger_hands_its_pid_to_the_runner_it_starts(world):   # noqa: F811
    world.gh.prs = [pr(1, world.head1)]
    assert world.tick() == 0
    assert world.runner.calls and all(c["env"]["LOCALCI_PARENT_PID"] == str(os.getpid()) for c in world.runner.calls)


def test_the_runner_starts_the_parent_watch_for_plan_and_run_only(monkeypatch, tmp_path):
    started = []
    monkeypatch.setattr(runner, "watch_parent", lambda *a, **k: started.append(1))
    monkeypatch.setattr(runner, "cmd_run", lambda a: 0)
    monkeypatch.setattr(runner, "cmd_status", lambda a: 0)
    assert runner.main(["status", "--run-dir", str(tmp_path)]) == 0 and started == []
    assert runner.main(["run", "--run-dir", str(tmp_path)]) == 0 and started == [1]
