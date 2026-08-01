#!/usr/bin/env python3
"""fleet_dispatch corpus — guilt AND innocence on every decision it makes.

The two decisions under test are the two the tool exists to make: WHERE a lane
may go (capacity) and WHETHER it may go there at all (collision). Both fail
closed, so each has a guilt case (it must refuse) and an innocence case (it
must NOT refuse a legitimate neighbour) — a refuser that refuses everything is
as useless as one that refuses nothing, and only the pair pins the behaviour.

The probe snippets are exercised by a REAL execution, not just parsed. A parser
test proves the parser; it proves nothing about the shell that feeds it. That is
not a stylistic preference: executing the snippet is what caught the comma-locale
defect, and a second execution-level test now pins the scan-completion sentinel.

Several tests below carry a `# ADVERSARIAL 2026-08-01` marker: they exist because
an independent red-team seat (Codex, generator != grader) reproduced a defect in
the first draft. Each was reproduced by hand before being fixed, and each of
these tests fails if the fix is reverted.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
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

CAP_LINE = ("FLEET_CAP host={h} cores=12 load1={l} avail_mb=9000 lock=free "
            "lock_pid=none head=abc123 worktrees=2 dirty=0 behind=0")


def cap(name, load_norm=0.2, avail_mb=8000, lock="free", worktrees=1, head="abc"):
    """A probed-node record, pre-classified like probe_node() leaves it."""
    record = {
        "name": name, "load_norm": load_norm, "avail_mb": avail_mb,
        "lock": lock, "lock_pid": "none", "worktrees": worktrees, "head": head,
        "cores": 10, "load1": load_norm * 10, "_missing": [],
    }
    record["verdict"], record["reason"] = fd.classify(record)
    return record


def lane(node, name, files=(), declared=(), scope="known", branch=None):
    return {"node": node, "worktree": name, "branch": branch or f"agent/{name}",
            "files": set(files), "declared": set(declared), "scope": scope,
            "opaque": scope == "opaque", "diff_ok": True, "wip_ok": True,
            "decl_ok": bool(declared)}


class FakeRun:
    """Stands in for subprocess, keyed by (node, probe kind).

    Keying on an ssh-alias substring was wrong and silently so: the LOCAL node
    is invoked as `sh -c <script>` with no alias anywhere in the command, so a
    reply registered under "air" never reached M5 and the node read DARK. The
    test then measured its own fake instead of the code. Alias `"LOCAL"` now
    addresses the local node explicitly, and a per-kind dict distinguishes the
    capacity probe from the lane scan — which the same node answers differently.

    replies: {alias: (stdout, rc)} — same answer for every probe — or
             {alias: {"capacity"|"lanes"|"other": (stdout, rc)}}.
    """

    def __init__(self, replies):
        self.replies = replies
        self.calls: list[list[str]] = []

    @staticmethod
    def _address(cmd) -> tuple[str, str]:
        alias = cmd[-2] if cmd and cmd[0] == "ssh" else "LOCAL"
        script = cmd[-1] if cmd else ""
        if "vm.loadavg" in script:
            kind = "capacity"
        elif "FLEET_LANES_DONE" in script:
            kind = "lanes"
        else:
            kind = "other"
        return alias, kind

    def __call__(self, cmd, timeout):
        self.calls.append(cmd)
        alias, kind = self._address(cmd)
        entry = self.replies.get(alias, ("", 0))
        if isinstance(entry, dict):
            entry = entry.get(kind, ("", 0))
        stdout, rc = entry
        return subprocess.CompletedProcess(cmd, rc, stdout=stdout, stderr="")


# --------------------------------------------------------------------------
# classify — the capacity verdict
# --------------------------------------------------------------------------

def test_classify_idle_node_is_ready():
    """INNOCENCE: a genuinely free machine must be usable, or the tool is a
    no-op that always says 'nowhere'."""
    verdict, _ = fd.classify(
        {"load_norm": 0.19, "avail_mb": 9000, "lock": "free", "_missing": []}
    )
    assert verdict == fd.VERDICT_READY


def test_classify_loaded_node_is_busy_not_ready():
    verdict, why = fd.classify(
        {"load_norm": 0.78, "avail_mb": 9000, "lock": "free", "_missing": []}
    )
    assert verdict == fd.VERDICT_BUSY
    assert "0.78" in why


def test_classify_held_suite_lock_is_busy_even_when_idle():
    """A held lock means a full backend suite is mid-flight: the load average
    has not caught up yet, and that lag is exactly when a second lane lands."""
    verdict, why = fd.classify({"load_norm": 0.05, "avail_mb": 9000,
                                "lock": "held", "lock_pid": "4242", "_missing": []})
    assert verdict == fd.VERDICT_BUSY
    assert "4242" in why


def test_classify_stale_lock_does_not_make_a_node_busy():
    """INNOCENCE: prepush_suite_lock.sh reclaims a dead holder's lock on the
    next poll, so a stale directory must not withhold a whole machine."""
    verdict, _ = fd.classify({"load_norm": 0.1, "avail_mb": 9000,
                              "lock": "stale", "_missing": []})
    assert verdict == fd.VERDICT_READY


def test_classify_low_memory_is_saturated():
    verdict, why = fd.classify({"load_norm": 0.1, "avail_mb": 512,
                                "lock": "free", "_missing": []})
    assert verdict == fd.VERDICT_SATURATED
    assert "512" in why


def test_classify_unreadable_signals_fail_closed_to_saturated():
    """The core property: an unknown reading withholds work, never invites it."""
    verdict, why = fd.classify({"load_norm": -1.0, "avail_mb": -1,
                                "lock": "free", "_missing": []})
    assert verdict == fd.VERDICT_SATURATED
    assert "fail-closed" in why


def test_classify_truncated_reply_is_saturated_not_ready():
    """ADVERSARIAL 2026-08-01 — reproduced before fixing.

    A FLEET_CAP line cut short after avail_mb carries a healthy load and no
    `lock` key. `cap.get("lock") == "held"` is False for a MISSING field exactly
    as it is for a free one, so the truncated reply classified READY: a machine
    running a full suite could be handed another lane on the strength of a line
    that never mentioned the lock.
    """
    parsed = fd.parse_capacity_line("FLEET_CAP cores=10 load1=1.0 avail_mb=9000")
    parsed["load_norm"] = 0.1
    verdict, why = fd.classify(parsed)
    assert verdict == fd.VERDICT_SATURATED
    assert "truncated" in why and "lock" in why


def test_classify_complete_reply_is_not_called_truncated():
    """INNOCENCE for the check above: a full line must not be rejected."""
    parsed = fd.parse_capacity_line(CAP_LINE.format(h="mini-pro2", l="1.2"))
    parsed["load_norm"] = 0.1
    assert parsed["_missing"] == []
    assert fd.classify(parsed)[0] == fd.VERDICT_READY


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
    assert fd.choose(caps)[0]["name"] == "mini"


def test_choose_falls_back_to_busy_when_nothing_is_ready():
    """Degraded-but-declared beats refusing: BUSY is slow, not unsafe."""
    winner, why = fd.choose([cap("m5", 0.78), cap("pro", 0.65)])
    assert winner["name"] == "pro"
    assert "no READY node" in why


def test_choose_refuses_when_every_node_is_saturated():
    winner, why = fd.choose([cap("m5", 1.4), cap("pro", 1.2), cap("mini", 1.1)])
    assert winner is None
    assert "no node is placeable" in why


def test_choose_honours_prefer():
    winner, why = fd.choose([cap("m5", 0.78), cap("mini", 0.19)], prefer="m5")
    assert winner["name"] == "m5"
    assert "--prefer" in why


def test_choose_refuses_prefer_on_a_saturated_node():
    """--prefer selects a node; it does not overrule the machine's condition."""
    winner, why = fd.choose([cap("m5", 1.5), cap("mini", 0.19)], prefer="m5")
    assert winner is None
    assert "SATURATED" in why


def test_choose_refuses_prefer_on_an_unknown_node():
    winner, why = fd.choose([cap("mini", 0.1)], prefer="typo")
    assert winner is None
    assert "no such node" in why


# --------------------------------------------------------------------------
# path handling — the false negatives an adversarial pass found
# --------------------------------------------------------------------------

def test_normalize_path_makes_equivalent_spellings_equal():
    """ADVERSARIAL 2026-08-01 — `./scripts/x.py` did not collide with
    `scripts/x.py`, verified live. A set intersection on raw strings compares
    spellings, not files."""
    for spelling in ("./scripts/x.py", "scripts/./x.py", "scripts/x.py",
                     f"{REPO}/scripts/x.py", "/scripts/x.py"):
        assert fd.normalize_path(spelling) == "scripts/x.py", spelling


def test_normalize_path_drops_empty_and_dot():
    assert fd.normalize_path(".") == ""
    assert fd.normalize_path("   ") == ""


def test_paths_conflict_on_containment_not_only_equality():
    """A lane holding a directory owns the files inside it."""
    assert fd.paths_conflict("apps/mouth/page.tsx", "apps/mouth")
    assert fd.paths_conflict("apps/mouth", "apps/mouth/page.tsx")
    assert fd.paths_conflict("a/b.py", "a/b.py")


def test_paths_conflict_innocence_on_a_shared_prefix_that_is_not_a_parent():
    """INNOCENCE: `apps/mouth2` is not inside `apps/mouth`. A bare startswith
    without the separator would make every sibling collide (superscar #3)."""
    assert not fd.paths_conflict("apps/mouth2/page.tsx", "apps/mouth")
    assert not fd.paths_conflict("scripts/foo.py", "scripts/foobar.py")


def test_porcelain_rename_yields_BOTH_sides():
    """ADVERSARIAL 2026-08-01 — `awk '{print $NF}'` kept only the destination of
    `R  old -> new`, so a lane asking for `old` was waved through while another
    lane was actively moving it."""
    paths, opaque = fd.parse_porcelain_paths("R  scripts/old.py -> scripts/new.py")
    assert set(paths) == {"scripts/old.py", "scripts/new.py"}
    assert opaque is False


def test_porcelain_plain_entry_and_quoted_entry():
    assert fd.parse_porcelain_paths(" M scripts/a.py") == (["scripts/a.py"], False)
    # A git-quoted path is reported opaque rather than guessed at.
    assert fd.parse_porcelain_paths('?? "scripts/a b.py"') == ([], True)


# --------------------------------------------------------------------------
# find_collisions — the quality half
# --------------------------------------------------------------------------

def test_collision_guilt_same_file_on_another_machine_blocks():
    """The whole point: a lane on Mini editing a file a lane on M5 also edits
    is the ~70%-degradation case (federation_parallelize §4 cond. 2)."""
    lanes = [lane("m5", "mouth-restyle", ["apps/mouth/page.tsx", "README.md"])]
    blocking, _ = fd.find_collisions({"apps/mouth/page.tsx"}, lanes)
    assert len(blocking) == 1
    assert blocking[0]["why"] == "overlap"
    assert blocking[0]["shared"] == ["apps/mouth/page.tsx"]


def test_collision_innocence_disjoint_lanes_do_not_block():
    """INNOCENCE, and the reason the tool is worth having: disjoint lanes are
    the three FREE kinds of parallelism. Blocking them would make the fleet
    slower than one machine."""
    lanes = [lane("m5", "a", ["apps/mouth/page.tsx"]),
             lane("pro", "b", ["scripts/lint.py"])]
    assert fd.find_collisions({"docs/runbooks/new.md"}, lanes) == ([], [])


def test_collision_blocks_on_a_lanes_DECLARED_scope():
    """A lane created by `place` has recorded what it intends to touch, before
    it has written a byte. That declaration must collide."""
    lanes = [lane("mini", "fresh", files=(), declared=["scripts/x.py"],
                  scope="declared")]
    blocking, _ = fd.find_collisions({"scripts/x.py"}, lanes)
    assert blocking[0]["why"] == "overlap"


def test_a_declared_lane_does_not_block_a_disjoint_request():
    """ADVERSARIAL 2026-08-01 — the usability half of the same defect. A freshly
    created lane has no files, so strict fail-closed made the SECOND `place` in
    a row always refuse: the tool could not be used twice, which is how a guard
    gets switched off entirely (superscar #3's endgame). Recording the declared
    scope is what makes a fresh lane knowable instead of merely empty."""
    lanes = [lane("mini", "fresh", files=(), declared=["scripts/x.py"],
                  scope="declared")]
    assert fd.find_collisions({"docs/other.md"}, lanes) == ([], [])


def test_unreadable_scopes_block_but_a_measured_empty_lane_does_not():
    """ADVERSARIAL 2026-08-01, the second half of the usability defect — and the
    distinction the first draft got wrong.

    `opaque` (a path git quoted, which we refuse to guess at) and `partial` (a
    scan that never confirmed a step) are FAILURES TO MEASURE: non-overlap
    cannot be proven, so they refuse. `empty` is a COMPLETED measurement that
    found nothing, which is evidence rather than ignorance. Blocking on it was
    not theoretical: two long-idle empty worktrees on Pro refused EVERY
    placement across the whole fleet the first time this ran for real.
    """
    for scope in ("opaque", "partial"):
        blocking, advisory = fd.find_collisions({"a.py"}, [lane("mini", "l", scope=scope)])
        assert [b["why"] for b in blocking] == [f"scope-{scope}"], scope
        assert advisory == []

    blocking, advisory = fd.find_collisions({"a.py"}, [lane("mini", "l", scope="empty")])
    assert blocking == []
    assert [a["why"] for a in advisory] == ["scope-empty"]


def test_collision_overlap_wins_over_scope_for_the_same_lane():
    """A lane that provably overlaps is reported as an overlap (with the file
    named), not as a vague scope complaint — the message has to be actionable."""
    lanes = [lane("m5", "l", ["a.py"], scope="empty")]
    assert fd.find_collisions({"a.py"}, lanes)[0][0]["why"] == "overlap"


# --------------------------------------------------------------------------
# cmd_place — the fail-closed contract
# --------------------------------------------------------------------------

def _place(monkeypatch, run, **kw):
    monkeypatch.setattr(fd, "load_nodes", lambda *a, **k: NODES)
    monkeypatch.setattr(fd, "local_hostname", lambda: "air-m5")
    params = dict(lane="infra", task_id="t", files=["scripts/x.py"], prefer=None,
                  dry_run=True, allow_unknown_scope=False, no_collision_check=False)
    params.update(kw)
    return fd.cmd_place(run=run, **params)


def test_place_refuses_when_a_node_is_dark(monkeypatch, capsys):
    """ADVERSARIAL 2026-08-01, P0 — reproduced before fixing. The first draft
    printed a warning and placed the lane. Scenario it broke on: Pro holds a
    lane on scripts/x.py, Pro's ssh is down, M5 answers — and a second lane on
    the same file was created. 'I could not look' is not 'nothing is there'."""
    good = CAP_LINE.format(h="air-m5", l="1.0")
    run = FakeRun({"LOCAL": {"capacity": (good + "\n", 0),
                             "lanes": ("FLEET_LANES_DONE\n", 0)}})  # pro/mini silent
    assert _place(monkeypatch, run) == 1
    assert "could not be verified" in capsys.readouterr().err


def test_place_proceeds_past_a_dark_node_only_with_the_override(monkeypatch, capsys):
    """INNOCENCE for the refusal above: the escape hatch exists and is loud."""
    good = CAP_LINE.format(h="air-m5", l="1.0")
    run = FakeRun({"LOCAL": {"capacity": (good + "\n", 0),
                             "lanes": ("FLEET_LANES_DONE\n", 0)}})
    assert _place(monkeypatch, run, allow_unknown_scope=True) == 0
    assert "unverifiable" in capsys.readouterr().out


def test_place_requires_files_unless_the_check_is_waived_out_loud():
    """ADVERSARIAL 2026-08-01 — `--files` was optional and its absence silently
    skipped the only check that makes parallel lanes safe."""
    with pytest.raises(SystemExit):
        fd.main(["place", "--lane", "infra", "--task-id", "t"])
    with pytest.raises(SystemExit):
        fd.main(["place", "--lane", "infra", "--task-id", "t",
                 "--files", "a.py", "--no-collision-check"])


# --------------------------------------------------------------------------
# probe hygiene — W104 (judge the reply), W84 (blind != clean), family #3
# --------------------------------------------------------------------------

def test_probe_without_sentinel_is_dark_even_on_exit_zero():
    """W104: `redis-cli` exits 0 while putting NOAUTH on stdout. An ssh that
    returns 0 having printed nothing useful has told us nothing."""
    run = FakeRun({"pro": ("some unrelated chatter\n", 0)})
    result = fd.probe_node(NODES[1], "air-m5", False, run)
    assert result["verdict"] == fd.VERDICT_DARK
    assert "no FLEET_CAP sentinel" in result["reason"]


def test_probe_with_sentinel_but_nonzero_rc_is_still_read():
    """The mirror of the above: the reply is the authority, so a noisy shell
    that still answered must not be discarded as dark."""
    run = FakeRun({"mini": (CAP_LINE.format(h="mini-pro2", l="2.28") + "\n", 1)})
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


def test_lane_scan_without_the_done_sentinel_is_not_an_empty_fleet():
    """ADVERSARIAL 2026-08-01, P0 — reproduced before fixing, and the most
    embarrassing of the set: this module's own docstring quotes W84 ('a blind
    sweep is not a clean sweep') while `git ... | awk | while` returned the
    status of the `while`, so a missing repo produced rc=0 and empty stdout —
    byte-identical to 'this node has no lanes'. The cure had the disease."""
    run = FakeRun({"pro": ("", 0)})
    lanes, answered = fd.probe_lanes(NODES[1], "air-m5", run)
    assert lanes == [] and answered is False


def test_lane_scan_error_sentinel_is_not_answered():
    run = FakeRun({"pro": ("FLEET_LANES_ERR no-repo-at /x\n", 0)})
    assert fd.probe_lanes(NODES[1], "air-m5", run) == ([], False)


def test_a_node_with_genuinely_no_lanes_IS_answered():
    """INNOCENCE: a machine with only its main checkout completes the scan and
    must read as verified-empty, not as unverifiable."""
    run = FakeRun({"pro": ("FLEET_LANES_DONE\n", 0)})
    lanes, answered = fd.probe_lanes(NODES[1], "air-m5", run)
    assert lanes == [] and answered is True


def test_capacity_exits_4_when_no_node_answers(monkeypatch, capsys):
    """W84: a sweep that probed nothing must not print a clean bill of health."""
    monkeypatch.setattr(fd, "load_nodes", lambda *a, **k: NODES)
    assert fd.cmd_capacity(False, False, FakeRun({})) == 4
    assert "BLIND" in capsys.readouterr().err


def test_capacity_json_states_how_many_nodes_actually_answered(monkeypatch, capsys):
    """ADVERSARIAL 2026-08-01 — this test used to assert only `rc == 0`, so it
    would have passed with `answered` and `total` deleted outright. A partial
    sweep must SAY it is partial: that is the difference between 'the fleet is
    fine' and 'two machines are unreachable'."""
    monkeypatch.setattr(fd, "load_nodes", lambda *a, **k: NODES)
    monkeypatch.setattr(fd, "local_hostname", lambda: "air-m5")
    run = FakeRun({"mini": (CAP_LINE.format(h="mini-pro2", l="1.2") + "\n", 0)})
    assert fd.cmd_capacity(True, False, run) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["answered"] == 1 and payload["total"] == 3
    dark = [n for n in payload["nodes"] if n["verdict"] == fd.VERDICT_DARK]
    assert {n["name"] for n in dark} == {"m5", "pro"}


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
    parsed = fd.parse_capacity_line("FLEET_CAP cores=x load1=y avail_mb=z lock=free")
    assert parsed["cores"] == -1 and parsed["load1"] == -1.0
    assert fd.classify({**parsed, "load_norm": -1.0})[0] == fd.VERDICT_SATURATED


def test_parse_lane_lines_groups_and_classifies_scope():
    lanes, completed = fd.parse_lane_lines(
        [
            "FLEET_LANE_BEGIN wt-a agent/a",
            "FLEET_LANE_DIFF wt-a ./scripts/x.py",
            "FLEET_LANE_WIP wt-a  M scripts/y.py",
            "FLEET_LANE_DIFFOK wt-a",
            "FLEET_LANE_WIPOK wt-a",
            "FLEET_LANE_BEGIN wt-b agent/b",
            "FLEET_LANE_DIFFOK wt-b",
            "FLEET_LANE_WIPOK wt-b",
            "FLEET_LANES_DONE",
        ],
        "mini",
    )
    assert completed is True
    by_name = {l["worktree"]: l for l in lanes}
    # normalize_path applied: './scripts/x.py' stored as 'scripts/x.py'
    assert by_name["wt-a"]["files"] == {"scripts/x.py", "scripts/y.py"}
    assert by_name["wt-a"]["scope"] == "known"
    assert by_name["wt-b"]["scope"] == "empty"
    assert all(l["node"] == "mini" for l in lanes)


def test_a_stale_sidecar_is_not_treated_as_a_declaration():
    """Nothing reaps the scope sidecar, so a reused task-id would inherit the
    PREVIOUS lane's declaration and be refused for files it never touches. The
    scan reports DECLSTALE when the recorded branch does not match, and the lane
    falls back to what its files actually say — `empty`, i.e. advisory."""
    lanes, _ = fd.parse_lane_lines(
        ["FLEET_LANE_BEGIN wt agent/new", "FLEET_LANE_DECLSTALE wt",
         "FLEET_LANE_DIFFOK wt", "FLEET_LANE_WIPOK wt", "FLEET_LANES_DONE"],
        "mini",
    )
    assert lanes[0]["declared"] == set()
    assert lanes[0]["scope"] == "empty"
    blocking, advisory = fd.find_collisions({"whatever.py"}, lanes)
    assert blocking == [] and [a["why"] for a in advisory] == ["scope-empty"]


def test_a_matching_sidecar_IS_treated_as_a_declaration():
    """INNOCENCE for the binding above: the current branch's own declaration
    must still be honoured, or the sidecar buys nothing."""
    lanes, _ = fd.parse_lane_lines(
        ["FLEET_LANE_BEGIN wt agent/x", "FLEET_LANE_DECL wt scripts/a.py",
         "FLEET_LANE_DECLOK wt", "FLEET_LANE_DIFFOK wt", "FLEET_LANE_WIPOK wt",
         "FLEET_LANES_DONE"],
        "mini",
    )
    assert lanes[0]["declared"] == {"scripts/a.py"}
    assert fd.find_collisions({"scripts/a.py"}, lanes)[0][0]["why"] == "overlap"


def test_a_lane_whose_diff_step_never_confirmed_is_partial_not_empty():
    """A half-finished scan prints a PREFIX of the truth, which is exactly the
    shape that reads as 'no files here'."""
    lanes, completed = fd.parse_lane_lines(
        ["FLEET_LANE_BEGIN wt agent/x", "FLEET_LANE_WIPOK wt", "FLEET_LANES_DONE"],
        "m5",
    )
    assert completed is True
    assert lanes[0]["scope"] == "partial"


# --------------------------------------------------------------------------
# POSITIVE CONTROL — the snippets are executed, not merely parsed
# --------------------------------------------------------------------------

def _run_capacity(lockfile="/tmp/nx-nonexistent.lock", env=None):
    script = fd.CAPACITY_SH.replace("__SUITE_LOCKFILE__", str(lockfile)).replace(
        "__FETCH__", ""
    )
    return subprocess.run(["sh", "-c", script], capture_output=True, text=True,
                          timeout=120, check=False, env=env)


def test_capacity_snippet_really_runs_and_emits_its_sentinel():
    """Executes CAPACITY_SH in a real shell. On macOS it yields true readings;
    on a Linux runner `sysctl`/`vm_stat` are absent and it MUST still emit the
    sentinel with degraded values — a probe that dies silently on an unexpected
    platform is the W108 shape (the reporting path never runs)."""
    proc = _run_capacity()
    line = next(
        (l for l in proc.stdout.splitlines() if l.startswith("FLEET_CAP ")), None
    )
    assert line is not None, f"no sentinel. stdout={proc.stdout!r} stderr={proc.stderr!r}"
    parsed = fd.parse_capacity_line(line)
    assert parsed["lock"] == "free"  # the lockfile we named does not exist
    assert parsed["_missing"] == [], "the snippet must emit every field classify() reads"

    if sys.platform == "darwin":
        assert parsed["cores"] > 0
        assert parsed["load1"] >= 0
        assert parsed["avail_mb"] > 0
    else:
        assert fd.classify({**parsed, "load_norm": -1.0})[0] == fd.VERDICT_SATURATED


def test_capacity_snippet_is_immune_to_a_comma_decimal_locale():
    """GUILT for the defect the positive control caught on 2026-08-01.

    Under Zero's LANG=it_IT.UTF-8, `sysctl -n vm.loadavg` prints `{ 3,38 ... }`.
    float('3,38') raises, load1 degrades to -1, and classify() then calls EVERY
    machine SATURATED — a tool that fail-closes into refusing all work is not
    wrong, it is dead. The snippet must produce a dot-decimal reading no matter
    what locale its caller runs in.
    """
    proc = _run_capacity(env={**os.environ, "LANG": "it_IT.UTF-8",
                              "LC_ALL": "it_IT.UTF-8"})
    line = next(l for l in proc.stdout.splitlines() if l.startswith("FLEET_CAP "))
    assert "," not in line.split("load1=")[1].split()[0], f"comma survived: {line}"
    if sys.platform == "darwin":
        assert fd.parse_capacity_line(line)["load1"] >= 0


def test_capacity_snippet_reports_a_held_lock_as_held(tmp_path):
    """Guilt for the lock branch, against a REAL lock directory holding a live
    PID (this process) — the same shape prepush_suite_lock.sh writes."""
    lock = tmp_path / "suite.lock"
    lock.mkdir()
    (lock / "pid").write_text(str(os.getpid()))
    proc = _run_capacity(lockfile=lock)
    line = next(l for l in proc.stdout.splitlines() if l.startswith("FLEET_CAP "))
    assert fd.parse_capacity_line(line)["lock"] == "held"


def test_capacity_snippet_reports_a_dead_holders_lock_as_stale(tmp_path):
    """Innocence for the same branch: a corpse must not read as a live suite,
    or one killed push wedges a machine out of the fleet forever."""
    lock = tmp_path / "suite.lock"
    lock.mkdir()
    (lock / "pid").write_text("999999")  # not a live pid
    proc = _run_capacity(lockfile=lock)
    line = next(l for l in proc.stdout.splitlines() if l.startswith("FLEET_CAP "))
    assert fd.parse_capacity_line(line)["lock"] == "stale"


def _run_lanes(env=None, cwd=None):
    script = fd.LANES_SH.replace("__SCOPE_DIR__", "$HOME/.organism/fleet_dispatch/lanes")
    return subprocess.run(["sh", "-c", script], capture_output=True, text=True,
                          timeout=180, check=False, env=env, cwd=cwd)


def test_lanes_snippet_completes_and_says_so_in_a_real_repo():
    """ADVERSARIAL 2026-08-01 — this test used to iterate stdout and assert that
    each line was well-formed, which is VACUOUSLY green when stdout is empty:
    precisely the P0 failure it was supposed to cover. It now asserts the
    terminal sentinel, which is the one thing an aborted scan cannot print."""
    # A symlinked HOME rather than `REPO.parent`, because REPO.parent is only
    # right when the checkout is literally named `nuzantara`. Every agent runs
    # from `.worktrees/<lane>-<task>`, so the earlier guard skipped this test in
    # exactly the environment it has to hold in — a test that abstains where it
    # matters is armed to nothing (superscar #2).
    with tempfile.TemporaryDirectory() as tmp:
        os.symlink(REPO, Path(tmp) / "nuzantara")
        proc = _run_lanes(env={**os.environ, "HOME": tmp})
    assert "FLEET_LANES_DONE" in proc.stdout, (
        f"scan did not complete. stdout={proc.stdout[:400]!r} "
        f"stderr={proc.stderr[:200]!r}"
    )
    lanes, completed = fd.parse_lane_lines(proc.stdout.splitlines(), "local")
    assert completed is True
    for entry in lanes:
        assert entry["scope"] in ("known", "declared", "empty", "opaque", "partial")


def test_lanes_snippet_on_a_home_without_a_repo_reports_an_ERROR_not_silence():
    """GUILT for the P0. A missing repo must be distinguishable from a machine
    that genuinely has no lanes — the two were byte-identical before the fix."""
    with tempfile.TemporaryDirectory() as tmp:
        proc = _run_lanes(env={**os.environ, "HOME": tmp})
    assert "FLEET_LANES_ERR" in proc.stdout, f"stdout={proc.stdout!r}"
    assert "FLEET_LANES_DONE" not in proc.stdout
    assert fd.parse_lane_lines(proc.stdout.splitlines(), "x") == ([], False)


def test_lanes_snippet_sees_inside_a_wholly_untracked_directory(tmp_path):
    """ADVERSARIAL 2026-08-01 — without `-uall`, git reports a wholly-untracked
    directory as `?? newdir/`, so a request for `newdir/a.py` did not collide
    with a lane that was actively creating it."""
    home = tmp_path / "home"
    repo = home / "nuzantara"
    repo.mkdir(parents=True)
    env = {**os.environ, "HOME": str(home), "GIT_CONFIG_GLOBAL": "/dev/null"}
    run = lambda *a: subprocess.run(a, cwd=repo, capture_output=True, text=True,
                                    check=True, env=env)
    run("git", "init", "-q", "-b", "main")
    run("git", "config", "user.email", "t@t"); run("git", "config", "user.name", "t")
    (repo / "seed.txt").write_text("x")
    run("git", "add", "-A"); run("git", "commit", "-qm", "seed")
    wt = repo / ".worktrees" / "lane-a"
    run("git", "worktree", "add", "-q", "-b", "lane-a", str(wt))
    (wt / "newdir").mkdir()
    (wt / "newdir" / "a.py").write_text("x")

    proc = _run_lanes(env=env)
    assert "FLEET_LANES_DONE" in proc.stdout, proc.stdout
    lanes, _ = fd.parse_lane_lines(proc.stdout.splitlines(), "t")
    files = set().union(*(l["files"] for l in lanes)) if lanes else set()
    assert "newdir/a.py" in files, f"got {files}"
    assert fd.find_collisions({"newdir/a.py"}, lanes)[0][0]["why"] == "overlap"


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
    grepped the raw text and failed on the `_doc` field, which explains the rule
    by quoting the very path shape it forbids — the probe had the disease it was
    measuring (W107). Prose may name a path; a node entry may not carry one.
    """
    raw = json.loads((REPO / "infra" / "fleet" / "nodes.json").read_text())
    for node in raw["nodes"]:
        for key, value in node.items():
            assert "/Users/" not in str(value), f"{node['name']}.{key} pins a home path"
    assert "$HOME/nuzantara" in fd.CAPACITY_SH
    assert "$HOME/nuzantara" in fd.LANES_SH


def test_kill_switch_short_circuits(monkeypatch, capsys):
    monkeypatch.setenv("FLEET_DISPATCH_ENABLED", "false")
    assert fd.main(["capacity"]) == 0
    assert "kill switch" in capsys.readouterr().out


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
