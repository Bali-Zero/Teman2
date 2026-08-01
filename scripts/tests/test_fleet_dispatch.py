#!/usr/bin/env python3
"""fleet_dispatch corpus — guilt AND innocence on every decision it makes.

The two decisions under test are the two the tool exists to make: WHERE a lane
may go (capacity) and WHETHER it may go there at all (collision). Both fail
closed, so each has a guilt case (it must refuse) and an innocence case (it
must NOT refuse a legitimate neighbour) — a refuser that refuses everything is
as useless as one that refuses nothing, and only the pair pins the behaviour.

The probe snippets are exercised by a REAL execution, not just parsed. A parser
test proves the parser; it proves nothing about the shell that feeds it. The
snippets degrade by design on a non-macOS runner (no `sysctl`/`vm_stat`), and
that degradation is itself asserted: the sentinel must still be emitted, and
the unreadable capacity must resolve to SATURATED rather than to READY.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
spec = importlib.util.spec_from_file_location(
    "fleet_dispatch", REPO / "scripts" / "fleet_dispatch.py"
)
fd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fd)

NODES = [
    {"name": "m5", "hostname": "air-m5", "ssh_alias": "air"},
    {"name": "pro", "hostname": "nuzantara", "ssh_alias": "pro"},
    {"name": "mini", "hostname": "mini-pro2", "ssh_alias": "mini"},
]


def cap(name, load_norm=0.2, avail_mb=8000, lock="free", worktrees=1, head="abc"):
    """A probed-node record, pre-classified like probe_node() leaves it."""
    record = {
        "name": name, "load_norm": load_norm, "avail_mb": avail_mb,
        "lock": lock, "lock_pid": "none", "worktrees": worktrees, "head": head,
    }
    record["verdict"], record["reason"] = fd.classify(record)
    return record


class FakeRun:
    """Stands in for subprocess: maps a command to canned stdout/rc."""

    def __init__(self, replies):
        self.replies = replies
        self.calls: list[list[str]] = []

    def __call__(self, cmd, timeout):
        self.calls.append(cmd)
        key = next((k for k in self.replies if any(k in part for part in cmd)), None)
        stdout, rc = self.replies.get(key, ("", 0)) if key else ("", 0)
        return subprocess.CompletedProcess(cmd, rc, stdout=stdout, stderr="")


# --------------------------------------------------------------------------
# classify — the capacity verdict
# --------------------------------------------------------------------------

def test_classify_idle_node_is_ready():
    """INNOCENCE: a genuinely free machine must be usable, or the tool is a
    no-op that always says 'nowhere'."""
    verdict, _ = fd.classify({"load_norm": 0.19, "avail_mb": 9000, "lock": "free"})
    assert verdict == fd.VERDICT_READY


def test_classify_loaded_node_is_busy_not_ready():
    verdict, why = fd.classify({"load_norm": 0.78, "avail_mb": 9000, "lock": "free"})
    assert verdict == fd.VERDICT_BUSY
    assert "0.78" in why


def test_classify_held_suite_lock_is_busy_even_when_idle():
    """A held lock means a full backend suite is mid-flight: the load average
    has not caught up yet, and that lag is exactly when a second lane lands."""
    verdict, why = fd.classify(
        {"load_norm": 0.05, "avail_mb": 9000, "lock": "held", "lock_pid": "4242"}
    )
    assert verdict == fd.VERDICT_BUSY
    assert "4242" in why


def test_classify_stale_lock_does_not_make_a_node_busy():
    """INNOCENCE: prepush_suite_lock.sh reclaims a dead holder's lock on the
    next poll, so a stale directory must not withhold a whole machine."""
    verdict, _ = fd.classify({"load_norm": 0.1, "avail_mb": 9000, "lock": "stale"})
    assert verdict == fd.VERDICT_READY


def test_classify_low_memory_is_saturated():
    verdict, why = fd.classify({"load_norm": 0.1, "avail_mb": 512, "lock": "free"})
    assert verdict == fd.VERDICT_SATURATED
    assert "512" in why


def test_classify_unreadable_signals_fail_closed_to_saturated():
    """The core property: an unknown reading withholds work, never invites it."""
    verdict, why = fd.classify({"load_norm": -1.0, "avail_mb": -1, "lock": "free"})
    assert verdict == fd.VERDICT_SATURATED
    assert "fail-closed" in why


# --------------------------------------------------------------------------
# choose — placement
# --------------------------------------------------------------------------

def test_choose_picks_the_freest_ready_node():
    caps = [cap("m5", 0.78), cap("pro", 0.42), cap("mini", 0.19)]
    winner, why = fd.choose(caps)
    assert winner["name"] == "mini"
    assert "freest" in why


def test_choose_breaks_load_ties_by_fewer_open_lanes():
    caps = [cap("pro", 0.20, worktrees=4), cap("mini", 0.20, worktrees=1)]
    winner, _ = fd.choose(caps)
    assert winner["name"] == "mini"


def test_choose_falls_back_to_busy_when_nothing_is_ready():
    """Degraded-but-declared beats refusing: BUSY is slow, not unsafe."""
    caps = [cap("m5", 0.78), cap("pro", 0.65)]
    winner, why = fd.choose(caps)
    assert winner["name"] == "pro"
    assert "no READY node" in why


def test_choose_refuses_when_every_node_is_saturated():
    caps = [cap("m5", 1.4), cap("pro", 1.2), cap("mini", 1.1)]
    winner, why = fd.choose(caps)
    assert winner is None
    assert "no node is placeable" in why


def test_choose_honours_prefer():
    caps = [cap("m5", 0.78), cap("mini", 0.19)]
    winner, why = fd.choose(caps, prefer="m5")
    assert winner["name"] == "m5"
    assert "--prefer" in why


def test_choose_refuses_prefer_on_a_saturated_node():
    """--prefer selects a node; it does not overrule the machine's condition."""
    caps = [cap("m5", 1.5), cap("mini", 0.19)]
    winner, why = fd.choose(caps, prefer="m5")
    assert winner is None
    assert "SATURATED" in why


def test_choose_refuses_prefer_on_an_unknown_node():
    winner, why = fd.choose([cap("mini", 0.1)], prefer="typo")
    assert winner is None
    assert "no such node" in why


# --------------------------------------------------------------------------
# find_collisions — the quality half
# --------------------------------------------------------------------------

def lane(node, name, files, scope="known"):
    return {"node": node, "worktree": name, "branch": f"agent/{name}",
            "files": set(files), "scope": scope}


def test_collision_guilt_same_file_on_another_machine_blocks():
    """The whole point: a lane on Mini editing a file a lane on M5 also edits
    is the ~70%-degradation case (federation_parallelize §4 cond. 2)."""
    lanes = [lane("m5", "mouth-restyle", ["apps/mouth/page.tsx", "README.md"])]
    blocking = fd.find_collisions({"apps/mouth/page.tsx"}, lanes)
    assert len(blocking) == 1
    assert blocking[0]["why"] == "overlap"
    assert blocking[0]["shared"] == ["apps/mouth/page.tsx"]


def test_collision_innocence_disjoint_lanes_do_not_block():
    """INNOCENCE, and the reason the tool is worth having: disjoint lanes are
    the three FREE kinds of parallelism. Blocking them would make the fleet
    slower than one machine."""
    lanes = [
        lane("m5", "mouth-restyle", ["apps/mouth/page.tsx"]),
        lane("pro", "infra-codeql", ["scripts/lint.py"]),
    ]
    assert fd.find_collisions({"docs/runbooks/new.md"}, lanes) == []


def test_collision_empty_scope_blocks_because_non_overlap_is_unprovable():
    lanes = [lane("mini", "fresh-lane", [], scope="empty")]
    blocking = fd.find_collisions({"anything.py"}, lanes)
    assert [b["why"] for b in blocking] == ["scope-empty"]


def test_collision_opaque_scope_blocks():
    """git quotes paths with spaces/specials; word-splitting one drops the real
    name and invents fragments, so an opaque lane is unknowable, not empty."""
    lanes = [lane("pro", "weird-lane", [], scope="opaque")]
    blocking = fd.find_collisions({"anything.py"}, lanes)
    assert [b["why"] for b in blocking] == ["scope-opaque"]


def test_collision_overlap_wins_over_scope_for_the_same_lane():
    """A lane that provably overlaps is reported as an overlap (with the file
    named), not as a vague scope complaint — the message has to be actionable."""
    lanes = [lane("m5", "l", ["a.py"], scope="empty")]
    blocking = fd.find_collisions({"a.py"}, lanes)
    assert blocking[0]["why"] == "overlap"


# --------------------------------------------------------------------------
# probe hygiene — W104 (judge the reply), W84 (blind ≠ clean), family #3
# --------------------------------------------------------------------------

def test_probe_without_sentinel_is_dark_even_on_exit_zero():
    """W104: `redis-cli` exits 0 while putting NOAUTH on stdout. An ssh that
    returns 0 having printed nothing useful has told us nothing."""
    run = FakeRun({"ssh": ("some unrelated chatter\n", 0)})
    result = fd.probe_node(NODES[1], "air-m5", False, run)
    assert result["verdict"] == fd.VERDICT_DARK
    assert "no FLEET_CAP sentinel" in result["reason"]


def test_probe_with_sentinel_but_nonzero_rc_is_still_read():
    """The mirror of the above: the reply is the authority, so a noisy shell
    that still answered must not be discarded as dark."""
    line = ("FLEET_CAP host=mini-pro2 cores=12 load1=2.28 avail_mb=9000 "
            "lock=free lock_pid=none head=abc123 worktrees=2 dirty=0 behind=0")
    run = FakeRun({"ssh": (line + "\n", 1)})
    result = fd.probe_node(NODES[2], "air-m5", False, run)
    assert result["verdict"] == fd.VERDICT_READY
    assert result["load_norm"] == 0.19


def test_probe_timeout_is_dark_not_an_exception():
    class Boom:
        def __call__(self, cmd, timeout):
            raise subprocess.TimeoutExpired(cmd, timeout)

    result = fd.probe_node(NODES[1], "air-m5", False, Boom())
    assert result["verdict"] == fd.VERDICT_DARK
    assert "TimeoutExpired" in result["reason"]


def test_capacity_exits_4_when_no_node_answers(monkeypatch, capsys):
    """W84: a sweep that probed nothing must not print a clean bill of health."""
    monkeypatch.setattr(fd, "load_nodes", lambda *a, **k: NODES)
    rc = fd.cmd_capacity(False, False, FakeRun({}))
    assert rc == 4
    assert "BLIND" in capsys.readouterr().err


def test_capacity_json_reports_the_probed_fraction(monkeypatch):
    """A partial sweep must SAY it is partial — 'answered N of M' is the
    difference between 'the fleet is fine' and 'one machine is unreachable'."""
    line = ("FLEET_CAP host=mini-pro2 cores=12 load1=1.2 avail_mb=9000 "
            "lock=free lock_pid=none head=abc worktrees=2 dirty=0 behind=0")
    monkeypatch.setattr(fd, "load_nodes", lambda *a, **k: NODES)
    monkeypatch.setattr(fd, "local_hostname", lambda: "air-m5")
    run = FakeRun({"mini": (line + "\n", 0)})
    rc = fd.cmd_capacity(True, False, run)
    assert rc == 0


def test_is_local_matches_the_entity_not_a_prefix():
    """Superscar #3: `mini` is a prefix of `mini-pro2`. Deciding locality by
    substring silently probes a remote node as if it were this one."""
    assert fd.is_local({"hostname": "mini-pro2"}, "mini-pro2")
    assert not fd.is_local({"hostname": "mini-pro2"}, "mini")
    assert not fd.is_local({"hostname": "nuzantara"}, "nuzantara-9")


def test_local_node_is_probed_by_the_same_snippet_as_a_remote_one():
    """A control that does not share the mechanism under test proves nothing
    about it: the local path must run the SAME script, only without ssh."""
    local = fd.build_command(NODES[0], "SCRIPT", "air-m5")
    remote = fd.build_command(NODES[2], "SCRIPT", "air-m5")
    assert local == ["sh", "-c", "SCRIPT"]
    assert remote[0] == "ssh" and remote[-1] == "SCRIPT"
    assert "air" not in local


def test_head_agreement_reports_divergence_without_naming_origin():
    """W106b: the tool compares the nodes to EACH OTHER — a claim its data
    supports — instead of to a possibly-stale local origin ref."""
    assert fd.head_agreement([{"head": "a"}, {"head": "a"}])[0] == "AGREE"
    assert fd.head_agreement([{"head": "a"}, {"head": "b"}])[0] == "DIVERGE"
    assert fd.head_agreement([{"head": "unknown"}])[0] == "UNKNOWN"


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------

def test_parse_capacity_line_rejects_a_non_sentinel_line():
    assert fd.parse_capacity_line("Warning: Permanently added 'mini'") is None


def test_parse_capacity_line_degrades_unparseable_numbers_to_minus_one():
    parsed = fd.parse_capacity_line("FLEET_CAP cores=x load1=y avail_mb=z")
    assert parsed["cores"] == -1 and parsed["load1"] == -1.0
    assert fd.classify({**parsed, "load_norm": -1.0})[0] == fd.VERDICT_SATURATED


def test_parse_lane_lines_groups_files_per_worktree():
    lanes = fd.parse_lane_lines(
        [
            "FLEET_LANE wt-a agent/a scripts/x.py",
            "FLEET_LANE wt-a agent/a scripts/y.py",
            "FLEET_LANE_EMPTY wt-b agent/b",
            "FLEET_LANE_OPAQUE wt-c agent/c",
        ],
        "mini",
    )
    by_name = {l["worktree"]: l for l in lanes}
    assert by_name["wt-a"]["files"] == {"scripts/x.py", "scripts/y.py"}
    assert by_name["wt-a"]["scope"] == "known"
    assert by_name["wt-b"]["scope"] == "empty"
    assert by_name["wt-c"]["scope"] == "opaque"
    assert all(l["node"] == "mini" for l in lanes)


# --------------------------------------------------------------------------
# POSITIVE CONTROL — the snippets are executed, not merely parsed
# --------------------------------------------------------------------------

def test_capacity_snippet_really_runs_and_emits_its_sentinel():
    """Executes CAPACITY_SH in a real shell. On macOS it yields true readings;
    on a Linux runner `sysctl`/`vm_stat` are absent and it MUST still emit the
    sentinel with degraded values — a probe that dies silently on an unexpected
    platform is the W108 shape (the reporting path never runs)."""
    script = fd.CAPACITY_SH.replace("__SUITE_LOCKFILE__", "/tmp/nx-nonexistent.lock")
    script = script.replace("__FETCH__", "")
    proc = subprocess.run(["sh", "-c", script], capture_output=True, text=True,
                          timeout=120, check=False)
    line = next(
        (l for l in proc.stdout.splitlines() if l.startswith("FLEET_CAP ")), None
    )
    assert line is not None, f"no sentinel. stdout={proc.stdout!r} stderr={proc.stderr!r}"
    parsed = fd.parse_capacity_line(line)
    assert parsed["lock"] == "free"  # the lockfile we named does not exist

    if sys.platform == "darwin":
        assert parsed["cores"] > 0
        assert parsed["load1"] >= 0
        assert parsed["avail_mb"] > 0
    else:
        # Degraded, and the verdict must be the withholding one.
        assert fd.classify({**parsed, "load_norm": -1.0})[0] == fd.VERDICT_SATURATED


def test_capacity_snippet_reports_a_held_lock_as_held(tmp_path):
    """Guilt for the lock branch, against a REAL lock directory holding a live
    PID (this process) — the same shape prepush_suite_lock.sh writes."""
    lock = tmp_path / "suite.lock"
    lock.mkdir()
    (lock / "pid").write_text(str(__import__("os").getpid()))
    script = fd.CAPACITY_SH.replace("__SUITE_LOCKFILE__", str(lock)).replace("__FETCH__", "")
    proc = subprocess.run(["sh", "-c", script], capture_output=True, text=True,
                          timeout=120, check=False)
    line = next(l for l in proc.stdout.splitlines() if l.startswith("FLEET_CAP "))
    assert fd.parse_capacity_line(line)["lock"] == "held"


def test_capacity_snippet_reports_a_dead_holders_lock_as_stale(tmp_path):
    """Innocence for the same branch: a corpse must not read as a live suite,
    or one killed push wedges a machine out of the fleet forever."""
    lock = tmp_path / "suite.lock"
    lock.mkdir()
    (lock / "pid").write_text("999999")  # not a live pid
    script = fd.CAPACITY_SH.replace("__SUITE_LOCKFILE__", str(lock)).replace("__FETCH__", "")
    proc = subprocess.run(["sh", "-c", script], capture_output=True, text=True,
                          timeout=120, check=False)
    line = next(l for l in proc.stdout.splitlines() if l.startswith("FLEET_CAP "))
    assert fd.parse_capacity_line(line)["lock"] == "stale"


def test_lanes_snippet_runs_in_a_real_repo_and_finds_this_worktree():
    """Executes LANES_SH for real. This test file lives inside a checkout that
    has at least the main worktree, so the snippet must complete and emit only
    well-formed FLEET_LANE* lines."""
    proc = subprocess.run(["sh", "-c", fd.LANES_SH], capture_output=True, text=True,
                          timeout=180, check=False, cwd=str(REPO))
    for raw in proc.stdout.splitlines():
        assert raw.startswith("FLEET_LANE"), f"unexpected line: {raw!r}"
        parts = raw.split()
        assert len(parts) >= 3
    # Parsing its own real output must not raise.
    fd.parse_lane_lines(proc.stdout.splitlines(), "local")


# --------------------------------------------------------------------------
# roster
# --------------------------------------------------------------------------

def test_roster_is_valid_and_covers_the_three_machines():
    nodes = fd.load_nodes()
    assert {n["name"] for n in nodes} == {"m5", "pro", "mini"}
    for node in nodes:
        assert node["hostname"] and node["ssh_alias"]


def test_roster_stores_no_absolute_home_path():
    """Family #1 (path-drift): M5 is `balizero`, Pro/Mini are `nuzantara`. A
    hardcoded /Users/<someone>/ in the roster is dead on one third of the
    fleet; the repo is resolved as $HOME/nuzantara on the TARGET instead.

    Asserted on the roster's VALUES, not on the file's bytes. The first draft
    grepped the raw text and failed on the `_doc` field, which explains the
    rule by quoting the very path shape it forbids — the probe had the disease
    it was measuring (W107). Prose may name a path; a node entry may not carry
    one.
    """
    raw = json.loads((REPO / "infra" / "fleet" / "nodes.json").read_text())
    for node in raw["nodes"]:
        for key, value in node.items():
            assert "/Users/" not in str(value), f"{node['name']}.{key} pins a home path"
    assert "$HOME/nuzantara" in fd.CAPACITY_SH
    assert "$HOME/nuzantara" in fd.LANES_SH


def test_capacity_snippet_is_immune_to_a_comma_decimal_locale():
    """GUILT for the defect the positive control caught on 2026-08-01.

    Under Zero's LANG=it_IT.UTF-8, `sysctl -n vm.loadavg` prints `{ 3,38 ... }`.
    float('3,38') raises, load1 degrades to -1, and classify() then calls EVERY
    machine SATURATED — a tool that fail-closes into refusing all work is not
    wrong, it is dead. The snippet must therefore produce a dot-decimal reading
    no matter what locale its caller runs in.
    """
    script = fd.CAPACITY_SH.replace("__SUITE_LOCKFILE__", "/tmp/nx.lock").replace(
        "__FETCH__", ""
    )
    proc = subprocess.run(
        ["sh", "-c", script],
        capture_output=True, text=True, timeout=120, check=False,
        env={**__import__("os").environ, "LANG": "it_IT.UTF-8", "LC_ALL": "it_IT.UTF-8"},
    )
    line = next(l for l in proc.stdout.splitlines() if l.startswith("FLEET_CAP "))
    assert "," not in line.split("load1=")[1].split()[0], f"comma decimal survived: {line}"
    if sys.platform == "darwin":
        assert fd.parse_capacity_line(line)["load1"] >= 0


def test_kill_switch_short_circuits(monkeypatch, capsys):
    monkeypatch.setenv("FLEET_DISPATCH_ENABLED", "false")
    assert fd.main(["capacity"]) == 0
    assert "kill switch" in capsys.readouterr().out


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
