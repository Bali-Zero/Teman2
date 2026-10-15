"""B33 S1: a tick that bore a verdict starts the next at once — the predicate (tick_chain.py) and the launchd wrapper that re-execs."""
from __future__ import annotations

import importlib.util
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from .test_merger import BASH, HB_LIB, WRAPPER, GIT_ENV, commit, g, mg, world  # noqa: F401 — `world` is the merger's fixture, reused for the lease test

_SRC = Path(__file__).resolve().parent.parent / "tick_chain.py"
_spec = importlib.util.spec_from_file_location("tick_chain_under_test", _SRC)
tc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tc)

SEAL = "ab" * 32


def row(kind, **kw):
    return {"kind": kind, "ts": "2026-10-15T10:00:00Z", **kw}


SEALED = row("decision", error=None, seal=SEAL, overall="PASS")


def run_predicate(tmp_path, before, after, rc=0, raw_after=None):
    j = tmp_path / "decisions.jsonl"
    head = "".join(json.dumps(r) + "\n" for r in before).encode()
    tail = raw_after if raw_after is not None else "".join(json.dumps(r) + "\n" for r in after).encode()
    j.write_bytes(head + tail)
    return tc.verdict(j, len(head), rc)


# ---------------------------------------------------------------- the predicate: guilt and innocence per term
@pytest.mark.parametrize("rows", [
    [SEALED],
    [row("ready_refreshed", result="ok")],
    [row("ready_refresh_failed", error="x")],
    [row("pushed", pr=1)],
    [row("lease_reclaimed"), SEALED, row("would_enqueue"), row("would_merge")],
    [row("skipped", why="head_moved"), SEALED],
], ids=["sealed-decision", "ready-refreshed", "ready-refresh-failed", "pushed", "decision-among-neutral-rows", "skip-then-decision"])
def test_each_verdict_kind_chains(tmp_path, rows):
    ok, why = run_predicate(tmp_path, [], rows)
    assert ok, why


@pytest.mark.parametrize("rows", [
    [row("decision", error="boom", seal=SEAL, overall="ERROR")],
    [row("decision", error=None, seal=None, overall="ERROR")],
    [row("decision", error=None, seal=SEAL[:63])],
    [row("decision", error=None, seal=SEAL.upper())],
    [row("decision", error=None, seal=SEAL + "0")],
    [row("decision", error=None, seal=SEAL + "\n")],
    [row("decision", error=None)],
    [row("evicted", why="host_below_floor_during_run")],
    [row("merge_error", error="x")],
    [row("push_unlanded")],
    [row("push_refused")],
    [row("storage_diverged")],
    [row("error", error="fetch")],
    [SEALED, row("evicted")],
    [row("pushed"), row("push_unlanded")],
    [row("skipped", why="lease")],
    [row("skipped", why="host_below_floor"), row("refused", why="fork")],
    [],
], ids=["error-set", "seal-null", "seal-63-hex", "seal-uppercase", "seal-65-hex", "seal-trailing-newline", "seal-absent", "evicted", "merge_error", "push_unlanded", "push_refused",
        "storage_diverged", "error-row", "evicted-beside-sealed", "stop-beside-pushed", "skip-lease", "only-skips", "nothing-appended"])
def test_each_non_verdict_does_not_chain(tmp_path, rows):
    ok, why = run_predicate(tmp_path, [], rows)
    assert not ok and why


def test_rc_not_zero_never_chains_even_beside_a_sealed_decision(tmp_path):
    assert run_predicate(tmp_path, [], [SEALED], rc=0)[0]
    assert not run_predicate(tmp_path, [], [SEALED], rc=1)[0]
    assert not run_predicate(tmp_path, [], [SEALED], rc=-9)[0]


def test_only_the_appended_bytes_are_read(tmp_path):
    assert not run_predicate(tmp_path, [SEALED], [])[0]                                  # a verdict before the offset is not this tick's
    assert run_predicate(tmp_path, [row("evicted")], [SEALED])[0]                         # nor is a stop before it


def test_an_unreadable_journal_does_not_chain(tmp_path):
    j = tmp_path / "decisions.jsonl"
    assert not tc.verdict(j, 0, 0)[0]                                                    # absent
    j.write_text(json.dumps(SEALED) + "\n")
    assert not tc.verdict(j, 10_000, 0)[0]                                               # shrank below the offset
    assert tc.verdict(j, 0, 0)[0]
    assert not tc.verdict(j, -1, 0)[0]
    assert not tc.verdict(tmp_path, 0, 0)[0]                                             # a directory
    assert not run_predicate(tmp_path, [], [], raw_after=b"{not json\n")[0]
    assert not run_predicate(tmp_path, [], [], raw_after=b"[1, 2]\n")[0]
    assert not run_predicate(tmp_path, [], [], raw_after=json.dumps(SEALED).encode() + b"\n{torn")[0]
    assert run_predicate(tmp_path, [], [], raw_after=b"\n" + json.dumps(SEALED).encode() + b"\n")[0]   # journal() opens a torn tail with "\n"


def test_the_cli_always_exits_0_and_names_the_decision(tmp_path):
    j = tmp_path / "decisions.jsonl"
    j.write_text(json.dumps(SEALED) + "\n")
    out = subprocess.run([sys.executable, "-I", str(_SRC), str(j), "0", "0"], capture_output=True, text=True)
    assert out.returncode == 0 and out.stdout.split()[0] == "chain"
    for argv in ([], [str(j)], [str(j), "x", "0"], [str(j), "0", "x"], [str(tmp_path / "none"), "0", "0"]):
        bad = subprocess.run([sys.executable, "-I", str(_SRC), *argv], capture_output=True, text=True)
        assert bad.returncode == 0 and bad.stdout.split()[0] == "stop", argv


# ---------------------------------------------------------------- the wrapper
def chain_world(tmp_path, *, predicate=True, journal_rows=None):
    """A mirror whose merger.py is a shell stand-in: every invocation of the 'tick' appends the rows named by FAKE_ROWS, logs itself."""
    src = tmp_path / "src"
    src.mkdir()
    g(src, "init", "-q", "-b", "main")
    files = {"scripts/localci/merger.py": "v1 --code-sha --host-free-gb\n", "scripts/localci/hosted_compare.py": "hc\n", "scripts/lib/heartbeat.sh": HB_LIB.read_text()}
    if predicate:
        files["scripts/localci/tick_chain.py"] = _SRC.read_text()
    commit(src, files, "v1")
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(src), str(origin)], check=True, env=GIT_ENV)
    state = tmp_path / "state"
    state.mkdir()
    if journal_rows:
        (state / "decisions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in journal_rows))
    log = tmp_path / "ticks.log"
    fake_py = tmp_path / "py"
    # python for tick_chain.py (the real one); anything else is the merger tick: log, run the test's hook, append the rows, exit FAKE_RC
    fake_py.write_text(f"""#!/bin/sh
case "$2" in
  */tick_chain.py) exec {sys.executable} "$@" ;;
esac
n=$(($(wc -l < "$TICK_LOG" 2>/dev/null || echo 0) + 1))
echo "$n depth=${{MERGER_CHAIN_DEPTH:-0}} pid=$PPID $* code=$(tr -d '\\n' < "$2")" >> "$TICK_LOG"
if [ -n "${{FAKE_HOOK:-}}" ]; then FAKE_N=$n sh -c "$FAKE_HOOK"; fi
if [ -n "${{FAKE_ROWS:-}}" ]; then cat "$FAKE_ROWS" >> "$STATE_DIR/decisions.jsonl"; fi
exit "${{FAKE_RC:-0}}"
""")
    fake_py.chmod(0o755)
    rows = tmp_path / "rows.jsonl"
    rows.write_text(json.dumps(SEALED) + "\n")
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "df").write_text(f"""#!/bin/sh
c=$(($(cat {tmp_path}/df.n 2>/dev/null || echo 0) + 1)); echo $c > {tmp_path}/df.n
echo "Filesystem 1024-blocks Used Available Capacity iused ifree %iused Mounted"
echo "/dev/x 1 1 $((200000000 + c * 10000000)) 1% 1 1 1% /"
""")
    (bin_ / "df").chmod(0o755)
    hb = tmp_path / "hb.log"
    hb_lib = tmp_path / "hb_lib.sh"
    hb_lib.write_text(f'echo "$2 $3" >> {hb}\n')
    env = {"HOME": str(tmp_path), "PATH": f"{bin_}:{os.environ['PATH']}", "MERGER_PYTHON": str(fake_py), "MERGER_NODE": "n1", "MERGER_STATE_DIR": str(state),
           "STATE_DIR": str(state), "MERGER_SEED": str(origin), "MERGER_REMOTE_URL": str(origin), "MERGER_HEARTBEAT_LIB": str(hb_lib),
           "TICK_LOG": str(log), "FAKE_ROWS": str(rows), "MERGER_MIN_HOST_FREE_GB": "0"}
    return type("CW", (), {"src": src, "origin": origin, "state": state, "log": log, "rows": rows, "env": env, "hb": hb, "tmp": tmp_path})()


def wrap(cw, **extra):
    return subprocess.run([BASH, str(WRAPPER)], env={**cw.env, **extra}, capture_output=True, text=True, timeout=120)


def ticks(cw):
    return cw.log.read_text().splitlines() if cw.log.exists() else []


def heartbeats(cw):
    return cw.hb.read_text().splitlines() if cw.hb.exists() else []


def test_a_tick_with_a_verdict_chains_whole_ticks_up_to_the_cap_and_each_leaves_its_heartbeat(tmp_path):
    cw = chain_world(tmp_path)
    r = wrap(cw, MERGER_CHAIN_MAX="3")
    assert r.returncode == 0, r.stderr
    t = ticks(cw)
    assert len(t) == 4 and [x.split()[1] for x in t] == ["depth=0", "depth=1", "depth=2", "depth=3"]
    assert r.stdout.count("merger_tick: chain depth=") == 3 and "chain stop: depth cap 3 reached" in r.stdout
    hb = heartbeats(cw)
    assert len(hb) == 4 and all(h.startswith("ok tick rc=0") for h in hb) and [h.rsplit(" ", 1)[1] for h in hb] == ["depth=0", "depth=1", "depth=2", "depth=3"]


def test_the_default_cap_is_twelve_chained_ticks_then_the_normal_interval_resumes(tmp_path):
    cw = chain_world(tmp_path)
    r = wrap(cw)
    assert r.returncode == 0 and len(ticks(cw)) == 13 and "chain stop: depth cap 12 reached" in r.stdout
    again = wrap(cw)   # the counter resets on a non-chained (launchd) start: 13 more
    assert again.returncode == 0 and len(ticks(cw)) == 26


def test_the_chained_wrapper_is_the_same_process_so_launchd_sees_one_instance(tmp_path):
    cw = chain_world(tmp_path)
    cw.rows.write_text(json.dumps(SEALED) + "\n")
    r = wrap(cw, MERGER_CHAIN_MAX="2")
    assert r.returncode == 0
    pids = {x.split()[2] for x in ticks(cw)}
    assert len(ticks(cw)) == 3 and len(pids) == 1   # $PPID of the tick = the wrapper: exec kept the pid, no sibling and no nested shell


def test_every_chained_tick_is_a_whole_tick_new_code_new_floor_reading(tmp_path):
    cw = chain_world(tmp_path)
    hook = (f"if [ \"$FAKE_N\" = 1 ]; then cd {cw.src} && echo 'v2 --code-sha --host-free-gb' > scripts/localci/merger.py && git add -A && "
            f"git -c user.name=t -c user.email=t@t commit -qm v2 && git push -q {cw.origin} main; fi")
    r = wrap(cw, MERGER_CHAIN_MAX="1", FAKE_HOOK=hook)
    assert r.returncode == 0, r.stderr
    t = ticks(cw)
    assert len(t) == 2 and "code=v1 --code-sha --host-free-gb" in t[0] and "code=v2 --code-sha --host-free-gb" in t[1]
    free = [x.split("--host-free-gb=")[1].split()[0] for x in t]
    assert free[0] != free[1], free   # df read again at each start


def test_a_chained_tick_still_meets_the_lease_a_parallel_manual_tick_took(world):  # noqa: F811
    # the wrapper holds no lock across the exec: the lease is taken and dropped inside merger.py tick. A tick holding it makes the
    # next one journal `skipped: lease`, and that row is no verdict: the chain stops and the cadence falls back to launchd's.
    import fcntl
    world.state.mkdir()
    jr = world.state / "decisions.jsonl"
    before = jr.stat().st_size if jr.exists() else 0
    with open(world.state / "lease.lock", "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        world.gh.prs = [{"number": 1}]
        assert world.tick() == 0
    ok, why = tc.verdict(jr, before, 0)
    assert not ok and "no verdict" in why
    assert [r["why"] for r in world.journal()] == ["lease"]


@pytest.mark.parametrize("kind", ["env", "file", "garbage-depth"])
def test_each_switch_keeps_todays_single_tick(tmp_path, kind):
    cw = chain_world(tmp_path)
    extra = {}
    if kind == "env":
        extra["LOCALCI_MERGER_CHAIN"] = "0"
    elif kind == "file":
        (cw.state / "chain_off").write_text("")
    else:
        extra["MERGER_CHAIN_DEPTH"] = "x1"
    r = wrap(cw, **extra)
    assert r.returncode == 0 and len(ticks(cw)) == 1 and "chain stop:" in r.stdout


def test_the_switch_file_created_by_a_running_chain_stops_it_at_once(tmp_path):
    cw = chain_world(tmp_path)
    r = wrap(cw, FAKE_HOOK=f"if [ \"$FAKE_N\" = 2 ]; then touch {cw.state}/chain_off; fi")
    assert r.returncode == 0 and len(ticks(cw)) == 2 and "chain_off exists" in r.stdout


def test_the_env_switch_set_to_anything_else_does_not_stop_the_chain(tmp_path):
    cw = chain_world(tmp_path)
    assert wrap(cw, LOCALCI_MERGER_CHAIN="1", MERGER_CHAIN_MAX="1").returncode == 0 and len(ticks(cw)) == 2


def test_the_kill_switch_of_the_organ_still_means_no_tick(tmp_path):
    cw = chain_world(tmp_path)
    r = wrap(cw, LOCALCI_MERGER_ENABLED="false")
    assert r.returncode == 0 and ticks(cw) == [] and heartbeats(cw) == ["disabled kill switch LOCALCI_MERGER_ENABLED=false"]


@pytest.mark.parametrize("why,rows,rc", [
    ("rc", [SEALED], "1"),
    ("evicted", [row("evicted")], "0"),
    ("merge_error", [row("merge_error", error="x")], "0"),
    ("error_row", [SEALED, row("error", error="x")], "0"),
    ("error_decision", [row("decision", error="boom", seal=SEAL)], "0"),
    ("idle", [row("skipped", why="head_moved")], "0"),
    ("nothing", [], "0"),
    ("garbage", None, "0"),
])
def test_a_tick_without_a_verdict_does_not_chain(tmp_path, why, rows, rc):
    cw = chain_world(tmp_path)
    if rows is None:
        cw.rows.write_text("{torn\n")
    else:
        cw.rows.write_text("".join(json.dumps(r) + "\n" for r in rows))
    r = wrap(cw, FAKE_RC=rc)
    assert r.returncode == int(rc) and len(ticks(cw)) == 1 and "chain stop:" in r.stdout and "chain depth=" not in r.stdout
    assert heartbeats(cw)[-1].split()[0] == ("error" if rc == "1" else "ok")


def test_a_journal_that_shrank_during_the_tick_does_not_chain(tmp_path):
    cw = chain_world(tmp_path, journal_rows=[SEALED] * 5)
    r = wrap(cw, FAKE_HOOK=f": > {cw.state}/decisions.jsonl", FAKE_ROWS="")
    assert r.returncode == 0 and len(ticks(cw)) == 1 and "shorter than the offset" in r.stdout


def test_old_journal_rows_are_not_this_ticks_verdict(tmp_path):
    cw = chain_world(tmp_path, journal_rows=[SEALED] * 5)
    r = wrap(cw, FAKE_ROWS="")
    assert r.returncode == 0 and len(ticks(cw)) == 1 and "no verdict row appended" in r.stdout


def test_a_main_without_the_predicate_never_chains_and_says_why(tmp_path):
    cw = chain_world(tmp_path, predicate=False)
    r = wrap(cw)
    assert r.returncode == 0 and len(ticks(cw)) == 1 and "no tick_chain.py at" in r.stdout


def test_a_warned_tick_does_not_chain(tmp_path):
    cw = chain_world(tmp_path)
    r = wrap(cw, MERGER_MIN_HOST_FREE_GB="100000")   # df says ~200 GB: the host is under the (huge) floor, the stand-in tick still bears a verdict
    assert r.returncode == 0 and len(ticks(cw)) == 1 and "the tick warned: host_below_floor" in r.stdout
    assert heartbeats(cw)[-1].startswith("warning host_below_floor")


def test_a_sigterm_while_the_tick_runs_never_reaches_the_exec(tmp_path):
    cw = chain_world(tmp_path)
    pidfile = tmp_path / "tick.pid"
    # the stand-in appends its verdict first, then the test stops the wrapper while the tick is still running
    slow = tmp_path / "slow_py"
    slow.write_text(f"""#!/bin/sh
case "$2" in
  */tick_chain.py) exec {sys.executable} "$@" ;;
esac
echo "$PPID" > {pidfile}
echo "$$" > {tmp_path}/child.pid
cat "$FAKE_ROWS" >> "$STATE_DIR/decisions.jsonl"
echo 1 >> "$TICK_LOG"
exec sleep 60
""")
    slow.chmod(0o755)
    proc = subprocess.Popen([BASH, str(WRAPPER)], env={**cw.env, "MERGER_PYTHON": str(slow)}, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    child = tmp_path / "child.pid"
    try:
        deadline = time.time() + 60
        while not child.exists() and time.time() < deadline:
            time.sleep(0.1)
        assert child.exists() and pidfile.read_text().strip() == str(proc.pid)
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=20) == -signal.SIGTERM
    finally:
        if child.exists():
            try:
                os.kill(int(child.read_text()), signal.SIGTERM)   # the stand-in tick this test started, nothing else
            except ProcessLookupError:
                pass
        if proc.poll() is None:
            proc.kill()
    time.sleep(0.5)
    assert len(ticks(cw)) == 1
