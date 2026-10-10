"""pro.janitor — tiers with hysteresis, a four-rule allowlist, dry-run first (docs/specs/pro-janitor-2026-10-10.md)."""
from __future__ import annotations

import importlib.util
import json
import os
import plistlib
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = ROOT / "scripts" / "ops" / "pro_janitor.py"
WRAPPER = ROOT / "infra" / "launchagents" / "wrappers" / "pro-janitor.sh"
PLIST = ROOT / "infra" / "launchagents" / "com.nuzantara.janitor.plist"
NOW = 1_800_000_000
DAY = 86400

spec = importlib.util.spec_from_file_location("pro_janitor", PAYLOAD)
pj = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pj)


# ---------------------------------------------------------------- tier math

@pytest.mark.parametrize("cur,free,want", [
    (0, 130.0, 0), (0, 129.99, 1), (0, 115.0, 1), (0, 114.99, 2), (0, 105.0, 2), (0, 104.99, 3), (0, 50, 3),
    (1, 139.99, 1), (1, 140.0, 0), (1, 129.99, 1), (1, 114.0, 2), (1, 100, 3),
    # the way down passes each exit mark: RED at 130 or 132 is AMBER until 140, BLACK at 115 is RED until 125
    (2, 124.99, 2), (2, 125.0, 1), (2, 130.0, 1), (2, 132.0, 1), (2, 129.99, 1), (2, 140.0, 0), (2, 104.0, 3),
    (3, 111.99, 3), (3, 112.0, 2), (3, 114.99, 2), (3, 115.0, 2), (3, 124.99, 2), (3, 125.0, 1), (3, 139.99, 1),
    (3, 140.0, 0),
])
def test_tiers_escalate_at_once_and_leave_only_at_the_exit_mark(cur, free, want):
    assert pj.next_tier(cur, free) == want


def test_the_marks_are_the_spec_table():
    assert pj.ENTER == {1: 130.0, 2: 115.0, 3: 105.0} and pj.EXIT == {1: 140.0, 2: 125.0, 3: 112.0}
    assert [(r["id"], r["tier"], r["cooldown"]) for r in pj.RULES] == [
        ("uv-prune", 1, 21600), ("npm-verify", 1, 86400), ("playwright-old", 2, 86400),
        ("uv-clean", 3, 21600)]


# ---------------------------------------------------------------- harness

class Box:
    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.home = tmp / "home"
        self.home.mkdir()
        self.state = tmp / "state"
        self.journal = tmp / "journal.jsonl"
        self.bin = tmp / "bin"
        self.bin.mkdir()
        self.rec = tmp / "calls.txt"
        self.uv = self.tool("uv")
        self.npm = self.tool("npm")
        self.lsof = self.tool("lsof", rc=1, record=False)

    def tool(self, name, rc=0, body="", record=True):
        p = self.bin / name
        rec = f'echo "{name} $*" >> {self.rec}\n' if record else ""
        p.write_text(f"#!/bin/sh\n{rec}{body}\nexit {rc}\n")
        p.chmod(0o755)
        return p

    def calls(self):
        return self.rec.read_text().splitlines() if self.rec.exists() else []

    nolinks = False

    def run(self, seq, apply=False, now=NOW, **env):
        r = pw_root(self)
        if r.is_dir() and not r.is_symlink() and not (r / ".links").exists() and not self.nolinks:
            links(self)   # an empty registry: pins nothing, so the older-revision logic is what the test sees
        e = {"PATH": "/usr/bin:/bin", "PRO_JANITOR_HOME": str(self.home), "PRO_JANITOR_STATE_DIR": str(self.state),
             "PRO_JANITOR_JOURNAL": str(self.journal), "PRO_JANITOR_NOW": str(now),
             "PRO_JANITOR_UV": str(self.uv), "PRO_JANITOR_NPM": str(self.npm), "PRO_JANITOR_LSOF": str(self.lsof),
             "PRO_JANITOR_FREE_GB_SEQ": seq, "PRO_JANITOR_TOOL_TIMEOUT": "20"}
        if apply:
            e["PRO_JANITOR_APPLY"] = "true"
        e.update(env)
        return subprocess.run([sys.executable, str(PAYLOAD)], env=e, capture_output=True, text=True, timeout=60)

    def lines(self):
        return [json.loads(x) for x in self.journal.read_text().splitlines()]

    def last(self):
        return self.lines()[-1]

    def rules(self):
        return {r["id"]: r for r in self.last()["rules"]}

    def cooldowns(self):
        return json.loads((self.state / "state.json").read_text())["rules"]


@pytest.fixture
def box(tmp_path):
    return Box(tmp_path)


def mk(path: Path, age_days: float, files=("data.bin",), now=NOW, size=10):
    path.mkdir(parents=True, exist_ok=True)
    for f in files:
        (path / f).write_bytes(b"x" * size)
    t = now - age_days * DAY
    for dirpath, dirs, fs in os.walk(path, topdown=False):
        for n in fs:
            os.utime(os.path.join(dirpath, n), (t, t), follow_symlinks=False)
        os.utime(dirpath, (t, t))


def pw_root(box):
    return box.home / "Library" / "Caches" / "ms-playwright"


def links(box, browsers=(), name="pkg1", live=True):
    """A Playwright registry link: <root>/.links/<name> holds the path of a package dir whose browsers.json pins revisions."""
    root = pw_root(box)
    (root / ".links").mkdir(parents=True, exist_ok=True)
    pkg = box.tmp / "pkgs" / name
    if live:
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "browsers.json").write_text(json.dumps({"browsers": list(browsers)}))
    (root / ".links" / name).write_text(str(pkg) + "\n")
    return pkg


# ---------------------------------------------------------------- tiers in the run

def test_green_does_nothing_but_journal(box):
    r = box.run("200", apply=True)
    assert r.returncode == 0 and "tier=GREEN" in r.stdout
    assert box.calls() == [] and box.last()["rules"] == [] and box.last()["tier"] == "GREEN"
    assert "transition" not in box.last()


@pytest.mark.parametrize("free,tier,ids,rc", [
    ("125", "AMBER", ["uv-prune", "npm-verify"], 0),
    ("110", "RED", ["uv-prune", "npm-verify", "playwright-old"], 0),
    ("100", "BLACK", ["uv-prune", "npm-verify", "playwright-old", "uv-clean"], 10),
])
def test_each_rule_acts_only_at_or_past_its_tier(box, free, tier, ids, rc):
    r = box.run(free, apply=True)
    assert r.returncode == rc and box.last()["tier"] == tier
    assert [x["id"] for x in box.last()["rules"]] == ids
    assert box.last()["transition"] == f"GREEN->{tier}"


def test_uv_prune_never_passes_force_and_runs_the_tools_with_the_expected_argv(box):
    box.run("100", apply=True)
    assert box.calls() == ["uv cache prune", "npm cache verify", "uv cache clean"]
    assert not any("--force" in c for c in box.calls())


def test_cooldowns_hold_and_expire(box):
    box.state.mkdir()
    (box.state / "state.json").write_text(json.dumps({"tier": "AMBER", "rules": {
        "uv-prune": NOW - 6 * 3600 + 1, "npm-verify": NOW - 24 * 3600 + 1}}))
    box.run("125", apply=True)
    assert box.calls() == [] and box.last()["rules"] == []
    box.run("125", apply=True, now=NOW + 2)   # both cooldowns have now passed exactly
    assert box.calls() == ["uv cache prune", "npm cache verify"]
    assert box.cooldowns() == {"uv-prune": NOW + 2, "npm-verify": NOW + 2}


def test_stop_at_the_exit_mark_after_the_first_action(box):
    r = box.run("125,141", apply=True)   # uv-prune frees enough: free 141 >= AMBER exit 140
    assert r.returncode == 0 and box.calls() == ["uv cache prune"]
    assert box.last()["stopped_at_exit_mark"] is True and box.last()["free_gb_after"] == 141
    assert box.rules()["uv-prune"]["delta_gb"] == 16
    assert "npm-verify" not in box.rules() and "npm-verify" not in box.cooldowns()


def test_no_stop_when_free_space_stays_under_the_exit_mark(box):
    box.run("125,139.99,139.99", apply=True)
    assert box.calls() == ["uv cache prune", "npm cache verify"] and "stopped_at_exit_mark" not in box.last()


def test_black_is_exit_10_and_a_clean_amber_is_0(box):
    assert box.run("100").returncode == 10
    assert box.run("125", now=NOW + 99 * DAY).returncode == 0


def test_hysteresis_holds_the_tier_between_the_marks_across_runs(box):
    box.run("125")                        # GREEN -> AMBER
    box.run("135")                        # still AMBER: under the exit mark 140
    assert box.last()["tier"] == "AMBER" and "transition" not in box.last()
    box.run("140")                        # leaves exactly at the exit mark
    assert box.last()["tier"] == "GREEN" and box.last()["transition"] == "AMBER->GREEN"
    box.run("100")
    box.run("113")                        # BLACK leaves at its exit mark 112; 113 implies RED
    assert box.last()["tier"] == "RED" and box.last()["transition"] == "BLACK->RED"


def test_journal_line_schema(box):
    box.run("125,126", apply=True)
    ln = box.last()
    assert set(ln) >= {"ts", "mode", "free_gb_before", "free_gb_after", "tier_prev", "tier", "rules", "transition"}
    assert ln["mode"] == "apply" and ln["ts"].endswith("Z") and ln["tier_prev"] == "GREEN"
    assert ln["rules"][0] == {"id": "uv-prune", "status": "done", "delta_gb": 1.0}


# ---------------------------------------------------------------- dry-run

def test_dry_run_decides_removes_nothing_and_leaves_cooldowns_alone(box):
    mk(pw_root(box) / "chromium-999", 30, size=7)
    mk(pw_root(box) / "chromium-1000", 30)
    r = box.run("110")
    assert r.returncode == 0 and box.calls() == []
    assert (pw_root(box) / "chromium-999").is_dir()
    rules = box.rules()
    assert rules["uv-prune"]["status"] == "dry-run" and rules["playwright-old"]["status"] == "dry-run"
    assert rules["playwright-old"]["entries"] == [{"name": "chromium-999", "bytes": 7}]
    assert box.last()["mode"] == "dry-run" and box.cooldowns() == {}


@pytest.mark.parametrize("val", ["", "false", "1", "yes"])
def test_only_true_arms(box, val):
    box.run("125", **{"PRO_JANITOR_APPLY": val})
    assert box.calls() == []


# ---------------------------------------------------------------- directory rules

def test_apply_removes_only_old_non_newest_and_keeps_the_newest_even_when_old(box):
    root = pw_root(box)
    mk(root / "chromium-999", 30)
    mk(root / "chromium-1000", 400)         # old and not the newest: goes
    mk(root / "ffmpeg-1011", 400)           # only one of its family: kept
    mk(root / "chromium-1001", 3)           # the newest chromium: young, kept; 999 and 1000 go
    mk(root / "firefox-1500", 30)
    mk(root / "firefox-1499", 2)            # younger than 7 days: kept
    r = box.run("110", apply=True)
    assert r.returncode == 0
    assert sorted(p.name for p in root.iterdir() if p.name != ".links") == ["chromium-1001", "ffmpeg-1011", "firefox-1499", "firefox-1500"]
    got = {e["name"] for e in box.rules()["playwright-old"]["entries"]}
    assert got == {"chromium-999", "chromium-1000"} and box.rules()["playwright-old"]["status"] == "done"
    assert "playwright-old" in box.cooldowns()


def test_numeric_revision_order_not_string_order(box):
    root = pw_root(box)
    mk(root / "chromium-999", 30)
    mk(root / "chromium-1000", 30)
    box.run("110", apply=True)
    assert (root / "chromium-1000").is_dir() and not (root / "chromium-999").exists()


def pb(name, rev, **ov):
    d = {"name": name, "revision": str(rev), "installByDefault": True}
    if ov:
        d["revisionOverrides"] = ov
    return d


def test_pinned_revisions_survive_and_unpinned_older_ones_of_the_same_family_go(box):
    root = pw_root(box)
    for rev in (1208, 1217, 1243, 1100):
        mk(root / f"chromium-{rev}", 30)
    links(box, [pb("chromium", 1208)])
    links(box, [pb("chromium", 1217)], name="pkg2")
    r = box.run("110", apply=True)
    assert sorted(p.name for p in root.iterdir() if not p.name.startswith(".")) == [
        "chromium-1208", "chromium-1217", "chromium-1243"]
    assert box.rules()["playwright-old"]["entries"] == [{"name": "chromium-1100", "bytes": 10}] and r.returncode == 0


def test_a_stale_link_pins_nothing(box):
    root = pw_root(box)
    mk(root / "chromium-1100", 30)
    mk(root / "chromium-1243", 30)
    links(box, [pb("chromium", 1100)], live=False)   # the package dir is gone
    box.run("110", apply=True)
    assert not (root / "chromium-1100").exists() and (root / "chromium-1243").is_dir()


def test_a_missing_links_dir_skips_the_rule(box):
    root = pw_root(box)
    mk(root / "chromium-1100", 30)
    mk(root / "chromium-1243", 30)
    box.nolinks = True
    r = box.run("110", apply=True)
    assert box.rules()["playwright-old"]["status"] == "skipped:link-registry-unreadable"
    assert (root / "chromium-1100").is_dir() and "playwright-old" not in box.cooldowns() and r.returncode == 0


@pytest.mark.parametrize("bad", ["not json", "[]", '{"browsers": 3}', '{"browsers":[{"name":"chromium"}]}', None])
def test_an_unreadable_or_malformed_browsers_json_of_a_live_link_skips_the_rule(box, bad):
    root = pw_root(box)
    mk(root / "chromium-1100", 30)
    mk(root / "chromium-1243", 30)
    pkg = links(box, [])
    if bad is None:
        (pkg / "browsers.json").unlink()
    else:
        (pkg / "browsers.json").write_text(bad)
    box.run("110", apply=True)
    assert box.rules()["playwright-old"]["status"] == "skipped:link-registry-unreadable"
    assert (root / "chromium-1100").is_dir()


def test_an_unreadable_link_file_skips_the_rule(box):
    root = pw_root(box)
    mk(root / "chromium-1100", 30)
    mk(root / "chromium-1243", 30)
    links(box, [])
    (root / ".links" / "dirlink").mkdir()   # a link entry that cannot be read as a file
    box.run("110", apply=True)
    assert box.rules()["playwright-old"]["status"] == "skipped:link-registry-unreadable"
    assert (root / "chromium-1100").is_dir()


def test_revision_overrides_are_pinned(box):
    root = pw_root(box)
    mk(root / "chromium-1100", 30)
    mk(root / "chromium-1050", 30)
    mk(root / "chromium-1243", 30)
    links(box, [pb("chromium", 1243, **{"mac14": "1100", "mac15": 1243})])
    box.run("110", apply=True)
    assert (root / "chromium-1100").is_dir() and not (root / "chromium-1050").exists()


def test_hyphenated_browser_names_pin_the_underscored_dir(box):
    root = pw_root(box)
    mk(root / "chromium_headless_shell-1100", 30)
    mk(root / "chromium_headless_shell-1050", 30)
    mk(root / "chromium_headless_shell-1243", 30)
    links(box, [pb("chromium-headless-shell", 1100)])
    box.run("110", apply=True)
    assert (root / "chromium_headless_shell-1100").is_dir() and not (root / "chromium_headless_shell-1050").exists()


def test_pros_real_layout_loses_nothing_at_red(box):
    root = pw_root(box)
    pins = {1: [("chromium", 1208), ("chromium-headless-shell", 1208), ("ffmpeg", 1011)],
            2: [("chromium", 1217), ("chromium-headless-shell", 1217)],
            3: [("chromium", 1243), ("chromium-headless-shell", 1243), ("webkit", 2359)]}
    for i, bl in pins.items():
        links(box, [pb(n, r) for n, r in bl], name=f"pkg{i}")
    names = ["chromium-1208", "chromium_headless_shell-1208", "ffmpeg-1011", "chromium-1217", "chromium_headless_shell-1217",
             "chromium-1243", "chromium_headless_shell-1243", "webkit-2359"]
    for n in names:
        mk(root / n, 40)
    r = box.run("110", apply=True)
    assert r.returncode == 0 and sorted(p.name for p in root.iterdir() if not p.name.startswith(".")) == sorted(names)
    assert box.rules()["playwright-old"]["status"] == "skipped:no-candidates"


def blocked_case(box, how):
    root = pw_root(box)
    mk(root / "chromium-1000", 30)
    outside = box.tmp / "outside"
    mk(outside, 30)
    if how == "symlinked-entry":
        root.joinpath("chromium-999").symlink_to(outside)
    else:
        mk(root / "chromium-999", 30)
    victim = root / "chromium-999"
    if how == "git":
        (victim / "sub").mkdir()
        (victim / "sub" / ".git").mkdir()
    elif how == "young-deep":
        mk(victim / "a" / "b" / "c", 1, files=("fresh",))
        os.utime(victim, (NOW - 30 * DAY,) * 2)
    elif how == "symlink-leaves":
        (victim / "link").symlink_to(outside)
    elif how == "open":
        box.lsof = box.tool("lsof", rc=0, body=f'echo "p123"; echo "n{victim}/data.bin"', record=False)
    elif how == "lsof-fails":
        box.lsof = box.tool("lsof", rc=2, record=False)
    elif how == "lsof-missing":
        box.lsof = box.bin / "nope"
    return victim, outside


@pytest.mark.parametrize("how,status", [
    ("symlinked-entry", "skipped:no-candidates"), ("git", "skipped:no-candidates"),
    ("young-deep", "skipped:no-candidates"), ("symlink-leaves", "skipped:no-candidates"),
    ("open", "skipped:in-use"), ("lsof-fails", "error:lsof-unreadable"), ("lsof-missing", "error:lsof-unreadable"),
])
def test_unsafe_entries_are_never_removed(box, how, status):
    victim, outside = blocked_case(box, how)
    r = box.run("110", apply=True)
    assert os.path.lexists(victim) and (outside / "data.bin").exists()
    assert box.rules()["playwright-old"]["status"] == status
    assert r.returncode == (10 if status.startswith("error") else 0)
    assert "playwright-old" not in box.cooldowns()


def test_a_symlink_that_stays_inside_the_entry_is_fine(box):
    root = pw_root(box)
    mk(root / "chromium-1000", 30)
    mk(root / "chromium-999", 30)
    (root / "chromium-999" / "alias").symlink_to(root / "chromium-999" / "data.bin")
    box.run("110", apply=True)
    assert not (root / "chromium-999").exists()


def test_a_symlinked_root_is_skipped_and_its_target_survives(box):
    real = box.tmp / "real-playwright"
    mk(real / "chromium-999", 30)
    mk(real / "chromium-1000", 30)
    pw_root(box).parent.mkdir(parents=True)
    pw_root(box).symlink_to(real)
    box.run("110", apply=True)
    assert box.rules()["playwright-old"]["status"] == "skipped:root-missing-or-symlinked"
    assert (real / "chromium-999").is_dir()


def test_a_file_matching_the_pattern_is_ignored(box):
    root = pw_root(box)
    mk(root / "chromium-1000", 30)
    root.joinpath("chromium-500").write_text("not a dir")
    os.utime(root / "chromium-500", (NOW - 30 * DAY,) * 2)
    box.run("110", apply=True)
    assert (root / "chromium-500").is_file() and box.rules()["playwright-old"]["status"] == "skipped:no-candidates"


def test_nothing_outside_the_rule_roots_is_ever_touched(box):
    mk(pw_root(box) / "chromium-999", 30)
    mk(pw_root(box) / "chromium-1000", 30)
    sib = box.home / "Library" / "Caches" / "other-playwright"
    mk(sib / "chromium-1", 30)
    mk(sib / "chromium-2", 30)
    mk(box.home / "ms-playwright" / "chromium-1", 30)
    mk(box.home / "ms-playwright" / "chromium-2", 30)
    mk(box.home / "nuzantara" / "x-1", 30)
    box.run("100", apply=True)
    assert not (pw_root(box) / "chromium-999").exists()
    for p in (sib / "chromium-1", box.home / "ms-playwright" / "chromium-1", box.home / "nuzantara" / "x-1"):
        assert p.is_dir()


def test_journal_and_stdout_name_only_revision_entries(box):
    mk(pw_root(box) / "chromium-999", 30)
    mk(pw_root(box) / "chromium-1000", 30)
    r = box.run("110", apply=True)
    text = box.journal.read_text() + r.stdout
    assert str(box.home) not in text and str(box.tmp) not in text


# ---------------------------------------------------------------- tools: deadline, errors

def test_a_tool_timeout_kills_its_process_group_and_later_rules_still_run(box):
    pidfile = box.tmp / "child.pid"
    box.uv = box.tool("uv", body=f"sleep 300 &\necho $! > {pidfile}\nwait")
    r = box.run("100", apply=True, PRO_JANITOR_TOOL_TIMEOUT="1")
    assert r.returncode == 10
    rules = box.rules()
    assert rules["uv-prune"]["status"] == "error:timeout" and rules["npm-verify"]["status"] == "done"
    assert rules["uv-clean"]["status"] == "error:timeout"
    pid = int(pidfile.read_text())
    for _ in range(50):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        os.kill(pid, 9)
        pytest.fail("the tool's child survived the group kill")


def test_a_failing_tool_is_an_error_and_the_next_rule_runs(box):
    box.uv = box.tool("uv", rc=3)
    r = box.run("125", apply=True)
    assert r.returncode == 10 and box.rules()["uv-prune"]["status"] == "error:rc=3"
    assert box.rules()["npm-verify"]["status"] == "done"


def test_a_missing_tool_is_an_error(box):
    r = box.run("125", apply=True, PRO_JANITOR_UV=str(box.bin / "nope"))
    assert r.returncode == 10 and box.rules()["uv-prune"]["status"] == "error:tool-missing"


# ---------------------------------------------------------------- config

@pytest.mark.parametrize("env", [{"PRO_JANITOR_NOW": "abc"}, {"PRO_JANITOR_FREE_GB_SEQ": "1,x"},
                                 {"PRO_JANITOR_HOME": "/nonexistent-dir-xyz"}, {"PRO_JANITOR_TOOL_TIMEOUT": "0"}])
def test_bad_config_is_exit_2(box, env):
    assert box.run("200", **env).returncode == 2


def test_python39_syntax_only_no_match_or_union_types():
    src = PAYLOAD.read_text()
    assert "from __future__ import annotations" in src and "match " not in src.replace("matches", "")


# ---------------------------------------------------------------- wrapper + plist

def wrap(tmp: Path, host="Nuzantara", seq="200", **env):
    home = tmp / "whome"
    (home / ".nuzantara-cron").mkdir(parents=True, exist_ok=True)
    (home / ".nuzantara-cron" / "pro_janitor.py").write_text(PAYLOAD.read_text())
    b = tmp / "wbin"
    b.mkdir(exist_ok=True)
    (b / "hostname").write_text(f"#!/bin/sh\necho {host}\n")
    (b / "hostname").chmod(0o755)
    e = {"HOME": str(home), "TMPDIR": str(tmp), "PATH": f"{b}:/usr/bin:/bin", "PRO_JANITOR_FREE_GB_SEQ": seq}
    e.update(env)
    res = subprocess.run(["/bin/bash", str(WRAPPER)], env=e, capture_output=True, text=True, timeout=60)
    hb = json.loads((home / ".organism" / "last_seen" / "pro.janitor.json").read_text())
    return res, hb, home


def test_wrapper_maps_exit_codes_to_the_heartbeat(tmp_path):
    _, hb, home = wrap(tmp_path, seq="200")
    assert hb["status"] == "ok" and "tier=GREEN" in hb["note"]
    assert (home / "logs" / "pro-janitor" / "journal.jsonl").exists()
    _, hb, _ = wrap(tmp_path, seq="100")
    assert hb["status"] == "warning" and "tier=BLACK" in hb["note"]
    _, hb, _ = wrap(tmp_path, seq="1,x")
    assert hb["status"] == "error" and hb["note"].startswith("rc=2")


@pytest.mark.parametrize("host,env,note", [("Air-M5", {}, "wrong-node Air-M5"),
                                           ("Nuzantara", {"PRO_JANITOR_ENABLED": "false"}, "kill switch")])
def test_wrapper_node_guard_and_kill_switch_are_visible_disabled(tmp_path, host, env, note):
    res, hb, home = wrap(tmp_path, host=host, **env)
    assert hb["status"] == "disabled" and hb["note"] == note
    assert not (home / "logs" / "pro-janitor" / "journal.jsonl").exists()


def test_wrapper_second_instance_exits_without_running(tmp_path):
    alive = subprocess.Popen(["sleep", "30"])
    (tmp_path / "nuzantara-pro-janitor.pid").write_text(str(alive.pid))
    try:
        _, hb, home = wrap(tmp_path)
    finally:
        alive.kill()
        alive.wait()
    assert hb["status"] == "ok" and hb["note"].startswith("skipped")
    assert not (home / "logs" / "pro-janitor" / "journal.jsonl").exists()


def test_plist_is_a_dry_run_one_shot_with_no_keepalive():
    pl = plistlib.loads(PLIST.read_bytes())
    assert pl["StartInterval"] == 600 and pl["RunAtLoad"] is True and "KeepAlive" not in pl
    assert pl["EnvironmentVariables"]["PRO_JANITOR_APPLY"] == "false"
    assert pl["EnvironmentVariables"]["PATH"] == "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    assert pl["ProgramArguments"] == ["/bin/bash", "/Users/nuzantara/scripts/pro-janitor.sh"]
    assert pl["StandardOutPath"].startswith("/Users/nuzantara/logs/pro-janitor/")
    pairs = json.loads((ROOT / "infra" / "home-fork" / "declared-pairs.json").read_text())["pairs"]
    live = {p["live"] for p in pairs if p["repo"] in (
        "scripts/ops/pro_janitor.py", "infra/launchagents/wrappers/pro-janitor.sh",
        "infra/launchagents/com.nuzantara.janitor.plist")}
    assert live == {"~/.nuzantara-cron/pro_janitor.py", "~/scripts/pro-janitor.sh",
                    "~/Library/LaunchAgents/com.nuzantara.janitor.plist"}
