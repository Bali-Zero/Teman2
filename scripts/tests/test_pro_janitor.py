"""pro.janitor — tiers with hysteresis, a three-rule allowlist, dry-run first (docs/specs/pro-janitor-2026-10-10.md)."""
from __future__ import annotations

import importlib.util
import json
import os
import plistlib
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
# PJ_PAYLOAD / PJ_WRAPPER point the suite at a scratch copy: that is how a guilt mutation proves a test bites
PAYLOAD = Path(os.environ.get("PJ_PAYLOAD", ROOT / "scripts" / "ops" / "pro_janitor.py"))
WRAPPER = Path(os.environ.get("PJ_WRAPPER", ROOT / "infra" / "launchagents" / "wrappers" / "pro-janitor.sh"))
PLIST = Path(os.environ.get("PJ_PLIST", ROOT / "infra" / "launchagents" / "com.nuzantara.janitor.plist"))
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
        ("uv-prune", 1, 21600), ("npm-verify", 1, 86400), ("playwright-old", 2, 86400)]


# ---------------------------------------------------------------- harness

class Box:
    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.home = tmp / "home"
        self.home.mkdir()
        self.state = self.home / ".state-jt"
        self.journal = tmp / "journal.jsonl"
        self.bin = tmp / "bin"
        self.bin.mkdir()
        self.rec = tmp / "calls.txt"
        (self.home / ".cache" / "uv").mkdir(parents=True)
        (self.home / ".npm").mkdir()
        self.uv = self.tool("uv")
        self.npm = self.tool("npm")
        self.lsof = self.fake_lsof()

    def tool(self, name, rc=0, body="", record=True):
        p = self.bin / name
        rec = f'echo "{name} $*" >> {self.rec}\n' if record else ""
        p.write_text(f"#!/bin/sh\n{rec}{body}\nexit {rc}\n")
        p.chmod(0o755)
        return p

    def fake_lsof(self, extra="", canary=True, rc=1, pre="", err=""):
        """lsof -F n +D <root>: lists the canary the janitor holds open (unless `canary` is False), plus `extra`; `err` is
        shell run with stdout going to stderr; `pre` runs first and may change the tree, as a concurrent process would.
        The default exit code is 1: with +D that is the healthy result (Pro, lsof 4.91, 2026-10-10). Argv is recorded."""
        body = (f'echo "$*" >> "{self.tmp}/lsof.argv"\nfor a; do R="$a"; done\n'
                'CAN=$(ls -A "$R" 2>/dev/null | grep "^[.]pro-janitor-canary-$PPID-")\n' + pre + "\n")   # read before `pre` moves things
        if err:
            body += f"( {err} ) >&2\n"
        if canary:
            body += 'for c in $CAN; do echo "n$R/$c"; done\n'
        return self.tool("lsof", rc=rc, body=body + extra, record=False)

    def verbs(self):
        """The calls without the pinned flags: 'uv cache prune', 'npm cache verify'."""
        return [c.replace(" --no-config", "").split(" --cache")[0] for c in self.calls()]

    def calls(self):
        return self.rec.read_text().splitlines() if self.rec.exists() else []

    nolinks = False

    def run(self, seq, apply=False, now=NOW, **env):
        r = pw_root(self)
        if r.is_dir() and not r.is_symlink() and not (r / ".links").exists() and not self.nolinks:
            links(self, [pb("winldd", 1)])   # a valid manifest that pins nothing the tests create
        e = {"PATH": "/usr/bin:/bin", "PRO_JANITOR_HOME": str(self.home), "PRO_JANITOR_STATE_DIR": str(self.state),
             "PRO_JANITOR_JOURNAL": str(self.journal), "PRO_JANITOR_NOW": str(now),
             "PRO_JANITOR_UV": str(self.uv), "PRO_JANITOR_NPM": str(self.npm), "PRO_JANITOR_LSOF": str(self.lsof),
             "PRO_JANITOR_FREE_GB_SEQ": seq, "PRO_JANITOR_TOOL_TIMEOUT": "20", "PRO_JANITOR_TMP": str(self.tmp)}
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


def links(box, browsers=None, name="pkg1", live=True):
    """A Playwright registry link: <root>/.links/<name> holds the path of a package dir whose browsers.json pins revisions."""
    root = pw_root(box)
    if browsers is None:
        browsers = [pb("winldd", 1)]
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
    ("100", "BLACK", ["uv-prune", "npm-verify", "playwright-old"], 10),
])
def test_each_rule_acts_only_at_or_past_its_tier(box, free, tier, ids, rc):
    r = box.run(free, apply=True)
    assert r.returncode == rc and box.last()["tier"] == tier
    assert [x["id"] for x in box.last()["rules"]] == ids
    assert box.last()["transition"] == f"GREEN->{tier}"


def test_uv_prune_never_passes_force_and_both_tools_are_pinned_to_the_cache_under_home(box):
    box.run("100", apply=True)
    home = os.path.realpath(box.home)
    assert box.calls() == [f"uv --no-config cache prune --cache-dir {home}/.cache/uv",
                           f"npm cache verify --cache {home}/.npm"]
    assert not any("--force" in c or "clean" in c for c in box.calls())


def test_tools_get_exactly_the_minimal_env_never_the_parents(box):
    for name in ("uv", "npm"):
        setattr(box, name, box.tool(name, body=f'env | sort > "{box.tmp}/env.{name}"', record=False))
    box.run("125", apply=True, UV_CACHE_DIR="/decoy/uv", XDG_CACHE_HOME="/decoy/xdg", npm_config_cache="/decoy/npm",
            NPM_CONFIG_USERCONFIG="/decoy/rc", SECRET_TOKEN="leak")
    noise = {"PWD", "SHLVL", "_", "OLDPWD", "__CF_USER_TEXT_ENCODING"}
    envs = {}
    for name in ("uv", "npm"):
        envs[name] = dict(ln.split("=", 1) for ln in (box.tmp / f"env.{name}").read_text().splitlines() if "=" in ln)
        envs[name] = {k: v for k, v in envs[name].items() if k not in noise}
    base = {"HOME": str(box.home), "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin", "LANG": "C"}
    assert envs["uv"] == base
    assert envs["npm"] == dict(base, npm_config_userconfig="/dev/null", npm_config_globalconfig="/dev/null")


@pytest.mark.parametrize("rel", [".cache/uv", ".npm"])
def test_a_symlinked_or_missing_cache_dir_skips_the_tool(box, rel):
    import shutil as _sh
    real = box.tmp / "elsewhere"
    real.mkdir()
    _sh.rmtree(box.home / rel)
    (box.home / rel).symlink_to(real)
    r = box.run("125", apply=True)
    assert box.calls() == [c for c in box.calls() if rel not in c]
    want = "uv-prune" if rel == ".cache/uv" else "npm-verify"
    assert box.rules()[want]["status"] == "skipped:root-missing-or-symlinked" and r.returncode == 0
    (box.home / rel).unlink()
    box.run("125", apply=True, now=NOW + 99 * DAY)
    assert box.rules()[want]["status"] == "skipped:root-missing-or-symlinked"


def test_cooldowns_hold_and_expire(box):
    box.state.mkdir()
    (box.state / "state.json").write_text(json.dumps({"tier": "AMBER", "rules": {
        "uv-prune": NOW - 6 * 3600 + 1, "npm-verify": NOW - 24 * 3600 + 1}}))
    box.run("125", apply=True)
    assert box.verbs() == [] and box.last()["rules"] == []
    box.run("125", apply=True, now=NOW + 2)   # both cooldowns have now passed exactly
    assert box.verbs() == ["uv cache prune", "npm cache verify"]
    assert box.cooldowns() == {"uv-prune": NOW + 2, "npm-verify": NOW + 2}


def test_stop_at_the_exit_mark_after_the_first_action(box):
    r = box.run("125,141", apply=True)   # uv-prune frees enough: free 141 >= AMBER exit 140
    assert r.returncode == 0 and box.verbs() == ["uv cache prune"]
    assert box.last()["stopped_at_exit_mark"] is True and box.last()["free_gb_after"] == 141
    assert box.rules()["uv-prune"]["delta_gb"] == 16
    assert "npm-verify" not in box.rules() and "npm-verify" not in box.cooldowns()


def test_no_stop_when_free_space_stays_under_the_exit_mark(box):
    box.run("125,139.99,139.99", apply=True)
    assert box.verbs() == ["uv cache prune", "npm cache verify"] and "stopped_at_exit_mark" not in box.last()


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


def test_the_tier_follows_every_reading_mid_run_up(box):
    r = box.run("125,100,100", apply=True)   # AMBER, uv-prune frees nothing and space collapses: BLACK, RED rules run
    assert r.returncode == 10 and box.last()["tier"] == "BLACK" and box.last()["tiers_seen"] == ["AMBER", "BLACK"]
    assert [x["id"] for x in box.last()["rules"]] == ["uv-prune", "npm-verify", "playwright-old"]
    assert box.last()["transition"] == "GREEN->BLACK"


def test_the_tier_follows_every_reading_mid_run_down(box):
    r = box.run("100,113", apply=True)   # BLACK, uv-prune recovers to 113: RED, the run stops at BLACK's exit mark
    assert r.returncode == 0 and box.last()["tier"] == "RED" and box.last()["tiers_seen"] == ["BLACK", "RED"]
    assert box.last()["stopped_at_exit_mark"] is True and box.calls() and len(box.calls()) == 1
    assert box.cooldowns() and json.loads((box.state / "state.json").read_text())["tier"] == "RED"
    assert "tiers_seen" not in box.run("200").stdout and "tiers_seen" not in box.last()


# ---------------------------------------------------------------- state, lock, config


def state_file(box, text):
    box.state.mkdir(exist_ok=True)
    (box.state / "state.json").write_text(text)


@pytest.mark.parametrize("bad", ["garbage", "[]", '{"tier":"PURPLE","rules":{}}', '{"tier":"GREEN"}',
                                 '{"tier":"GREEN","rules":{"uv-prune":NaN}}', '{"tier":"GREEN","rules":{"uv-prune":true}}',
                                 '{"tier":"GREEN","rules":{"uv-prune":"x"}}', '{"tier":"GREEN","rules":[]}', "",
                                 '{"tier":"GREEN","rules":{"uv-prune":1' + "0" * 400 + '}}',   # 10**400: float() overflows
                                 '{"tier":"GREEN","rules":{"uv-prune":-1}}', '{"tier":"GREEN","rules":{"uv-prune":5000000000}}',
                                 '{"tier":"GREEN","rules":{"uv-prune":1e999}}'])
def test_an_invalid_state_forces_dry_run_warns_and_is_rewritten_valid(box, bad):
    state_file(box, bad)
    r = box.run("125", apply=True)
    assert r.returncode == 10 and box.calls() == [] and box.last()["state_invalid"] is True
    assert box.last()["mode"] == "dry-run" and box.rules()["uv-prune"]["status"] == "dry-run"
    assert json.loads((box.state / "state.json").read_text())["tier"] == "AMBER"
    r = box.run("125", apply=True)   # valid now: acts again
    assert r.returncode == 0 and len(box.calls()) == 2 and "state_invalid" not in box.last()


def test_cooldown_stamps_in_the_future_are_dropped_and_small_skew_is_kept(box):
    state_file(box, json.dumps({"tier": "AMBER", "rules": {"uv-prune": NOW + 3600, "npm-verify": NOW + 30}}))
    box.run("125", apply=True)
    assert box.verbs() == ["uv cache prune"]   # the far-future uv-prune stamp is dropped; npm's small skew is kept
    assert box.cooldowns()["uv-prune"] == NOW


def test_state_is_written_atomically_exclusively_and_fsynced_with_its_directory(box, monkeypatch):
    fsyncs, opens = [], []
    real_fsync, real_open = os.fsync, os.open
    monkeypatch.setattr(os, "fsync", lambda fd: (fsyncs.append(fd), real_fsync(fd))[1])
    monkeypatch.setattr(os, "open", lambda path, flags, *a, **k: (opens.append((str(path), flags)), real_open(path, flags, *a, **k))[1])
    box.state.mkdir()
    env = pj.Env.__new__(pj.Env)
    env.state_dir = str(box.state)
    pj.save_state(env, {"tier": "GREEN", "rules": {}})
    tmp = [f for p_, f in opens if os.path.basename(p_).startswith(".state.")]
    want = os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_WRONLY
    assert len(tmp) == 1 and tmp[0] & want == want
    assert len(fsyncs) == 2   # the file, then the directory
    assert any(f & os.O_DIRECTORY for p_, f in opens if p_ == str(box.state))
    assert sorted(os.listdir(box.state)) == ["state.json"]


def test_a_second_run_while_the_lock_is_held_exits_11_touching_nothing(box):
    import fcntl
    box.state.mkdir()
    fd = os.open(box.state / "lock", os.O_RDWR | os.O_CREAT)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        r = box.run("100", apply=True)
    finally:
        os.close(fd)
    assert r.returncode == 11 and not box.journal.exists() and not (box.state / "state.json").exists()
    assert box.calls() == [] and box.run("200").returncode == 0


def test_journal_line_schema(box):
    box.run("125,126", apply=True)
    ln = box.last()
    assert set(ln) >= {"ts", "mode", "free_gb_before", "free_gb_after", "tier_prev", "tier", "rules", "transition"}
    assert ln["mode"] == "apply" and ln["ts"].endswith("Z") and ln["tier_prev"] == "GREEN"
    first = dict(ln["rules"][0])
    assert isinstance(first.pop("freed_fs_bytes"), int)   # the filesystem's word, beside the reading
    assert first == {"id": "uv-prune", "status": "done", "delta_gb": 1.0}


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
    assert box.rules()["playwright-old"]["entries"] == [{"name": "chromium-1100", "bytes": 10, "state": "removed"}]
    assert r.returncode == 0


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
    links(box, [pb("chromium", 1243, **{"mac14": "1100", "mac15": "1243"})])
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


def two_chromiums(box):
    root = pw_root(box)
    mk(root / "chromium-1100", 30)
    mk(root / "chromium-1243", 30)
    return root


def untouched(box, root, status="skipped:link-registry-unreadable"):
    """None when the rule skipped with `status`, removed nothing and stamped no cooldown; else what went wrong."""
    got = box.rules()["playwright-old"]["status"]
    if got != status:
        return "status %r, want %r" % (got, status)
    if not (root / "chromium-1100").is_dir():
        return "chromium-1100 was removed"
    if "playwright-old" in box.cooldowns():
        return "a cooldown was stamped"
    return None


MANIFESTS = {
    "empty-browsers": '{"browsers": []}',
    "uppercase-name": '{"browsers":[{"name":"Chromium","revision":"1"}]}',
    "unicode-name": '{"browsers":[{"name":"chromium\\u00e9","revision":"1"}]}',
    "trailing-newline-name": '{"browsers":[{"name":"chromium\\n","revision":"1"}]}',
    "int-revision": '{"browsers":[{"name":"chromium","revision":1100}]}',
    "alpha-revision": '{"browsers":[{"name":"chromium","revision":"12a"}]}',
    "unicode-digit-revision": '{"browsers":[{"name":"chromium","revision":"\\u0661\\u0662"}]}',
    "newline-revision": '{"browsers":[{"name":"chromium","revision":"12\\n"}]}',
    "override-not-digits": '{"browsers":[{"name":"chromium","revision":"1","revisionOverrides":{"a":"x"}}]}',
    "override-not-dict": '{"browsers":[{"name":"chromium","revision":"1","revisionOverrides":[]}]}',
    "item-not-dict": '{"browsers":["chromium"]}',
    "top-level-list": "[]",
}


@pytest.mark.parametrize("which", sorted(MANIFESTS))
def test_a_manifest_that_is_not_exactly_well_formed_skips_the_rule(box, which):
    root = two_chromiums(box)
    pkg = links(box)
    (pkg / "browsers.json").write_text(MANIFESTS[which])
    box.run("110", apply=True)
    assert untouched(box, root) is None
def test_a_non_utf8_or_oversized_manifest_skips_the_rule(box):
    root = two_chromiums(box)
    pkg = links(box)
    (pkg / "browsers.json").write_bytes(b"\xff\xfe{")
    box.run("110", apply=True)
    assert untouched(box, root) is None
    (pkg / "browsers.json").write_text('{"browsers":[{"name":"winldd","revision":"1"}],"pad":"' + "x" * (1024 * 1024) + '"}')
    box.run("110", apply=True, now=NOW + 99 * DAY)
    assert untouched(box, root) is None
def test_a_link_file_that_is_a_symlink_a_fifo_or_oversized_skips_the_rule(box):
    root = two_chromiums(box)
    pkg = links(box)
    lk = root / ".links"
    real = box.tmp / "real-link"
    real.write_text(str(pkg))
    (lk / "sym").symlink_to(real)
    box.run("110", apply=True)
    assert untouched(box, root) is None
    (lk / "sym").unlink()
    os.mkfifo(lk / "fifo")
    box.run("110", apply=True, now=NOW + 99 * DAY)
    assert untouched(box, root) is None
    (lk / "fifo").unlink()
    (lk / "big").write_text(str(pkg) + "\n" + " " * (64 * 1024))
    box.run("110", apply=True, now=NOW + 199 * DAY)
    assert untouched(box, root) is None
def test_a_relative_or_empty_link_content_skips_the_rule(box):
    root = two_chromiums(box)
    links(box)
    (root / ".links" / "rel").write_text("relative/dir\n")
    box.run("110", apply=True)
    assert untouched(box, root) is None
def test_an_unstatable_package_dir_other_than_not_found_skips_the_rule(box):
    root = two_chromiums(box)
    links(box)
    locked = box.tmp / "locked"
    (locked / "pkg").mkdir(parents=True)
    (root / ".links" / "eacces").write_text(str(locked / "pkg") + "\n")
    locked.chmod(0)
    try:
        box.run("110", apply=True)
    finally:
        locked.chmod(0o755)
    assert untouched(box, root) is None
def test_an_empty_links_dir_is_no_live_install_and_the_older_revision_goes(box):
    root = two_chromiums(box)
    (root / ".links").mkdir()
    box.nolinks = True
    box.run("110", apply=True)
    assert box.rules()["playwright-old"]["status"] == "done" and not (root / "chromium-1100").exists()


@pytest.mark.parametrize("apply", [True, False])
def test_an_install_lock_skips_the_rule(box, apply):
    root = two_chromiums(box)
    (root / "__dirlock").write_text("")
    box.run("110", apply=apply)
    assert untouched(box, root, "skipped:install-in-progress") is None
def test_an_install_lock_that_appears_during_the_run_removes_nothing(box):
    root = two_chromiums(box)
    box.lsof = box.fake_lsof(pre=f'touch "{root}/__dirlock"')   # runs between the plan and the removal
    box.run("110", apply=True)
    assert untouched(box, root, "skipped:install-in-progress") is None
def test_a_registry_that_changes_during_the_run_removes_nothing(box):
    root = two_chromiums(box)
    links(box)
    newpkg = box.tmp / "pkgs" / "late"
    newpkg.mkdir(parents=True)
    (newpkg / "browsers.json").write_text(json.dumps({"browsers": [pb("chromium", 1100)]}))
    box.lsof = box.fake_lsof(pre=f'echo "{newpkg}" > "{root}/.links/late"')
    box.run("110", apply=True)
    assert untouched(box, root, "skipped:registry-changed") is None
def test_only_allowlisted_families_with_ascii_digit_revisions_are_ever_candidates(box):
    root = pw_root(box)
    mk(root / "chromium-1243", 30)
    mk(root / "chromium-1100", 30)
    for n in ("backup-1", "backup-2", "foo_bar-1", "foo_bar-2", "chromium-\u0661\u0662\u0663", "chromium-\uff11\uff12",
              "chromium-12345678901234", "Chromium-1"):
        mk(root / n, 30)
    box.run("110", apply=True)
    left = sorted(p.name for p in root.iterdir() if p.name != ".links")
    assert "chromium-1100" not in left and len(left) == 9
    assert box.rules()["playwright-old"]["entries"] == [{"name": "chromium-1100", "bytes": 10, "state": "removed"}]


def raced(box, how):
    root = pw_root(box)
    mk(root / "chromium-1243", 30)
    victim = root / "chromium-999"
    mk(victim, 30)
    outside = box.tmp / "outside"
    mk(outside, 30)
    if how == "young-file":
        box.lsof = box.fake_lsof(pre=f'echo fresh > "{victim}/fresh"; touch -t 202701140000 "{victim}/fresh"')   # a day before the fake NOW
    elif how == "swapped-for-symlink":
        box.lsof = box.fake_lsof(pre=f'rm -rf "{victim}"; ln -s "{outside}" "{victim}"')
    elif how == "git-appears":
        box.lsof = box.fake_lsof(pre=f'mkdir "{victim}/.git" 2>/dev/null')
    return victim, outside


@pytest.mark.parametrize("how", ["young-file", "swapped-for-symlink", "git-appears"])
def test_every_entry_is_audited_again_at_the_moment_of_removal(box, how):
    victim, outside = raced(box, how)
    r = box.run("110", apply=True)
    assert os.path.lexists(victim) and (outside / "data.bin").exists()
    res = box.rules()["playwright-old"]
    assert res["status"] == "error:rmtree-partial" and r.returncode == 10
    assert res["entries"] == [{"name": "chromium-999", "bytes": 0, "state": "failed:changed"}]


def test_a_failed_rmtree_is_journaled_failed_never_removed(box):
    root = pw_root(box)
    mk(root / "chromium-1243", 30)
    bad = root / "chromium-999"
    mk(bad / "sub", 30)
    mk(root / "chromium-998", 30)
    os.chmod(bad / "sub", 0o555)   # its file cannot be unlinked
    try:
        r = box.run("110", apply=True)
    finally:
        os.chmod(bad / "sub", 0o755)
    res = box.rules()["playwright-old"]
    states = {e["name"]: e["state"] for e in res["entries"]}
    assert states == {"chromium-998": "removed", "chromium-999": "failed:eperm"} and res["status"] == "error:rmtree-partial"
    assert r.returncode == 10 and not (root / "chromium-998").exists() and "playwright-old" in box.cooldowns()


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
        box.lsof = box.fake_lsof(extra=f'echo "p123"; echo "n{victim}/data.bin"')
    elif how == "lsof-fails":
        box.lsof = box.tool("lsof", rc=2, record=False)
    elif how == "lsof-no-canary":
        box.lsof = box.fake_lsof(canary=False, extra=f'echo "n{root}/other"')
    elif how == "lsof-rc1-empty":
        box.lsof = box.tool("lsof", rc=1, record=False)
    elif how == "lsof-huge":
        box.lsof = box.fake_lsof(extra="yes n/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa | head -c 17000000")
    elif how == "git-upper":
        (victim / "sub").mkdir()
        (victim / "sub" / ".GIT").mkdir()
    elif how == "lsof-missing":
        box.lsof = box.bin / "nope"
    return victim, outside


@pytest.mark.parametrize("how,status", [
    ("symlinked-entry", "skipped:no-candidates"), ("git", "skipped:no-candidates"),
    ("young-deep", "skipped:no-candidates"), ("symlink-leaves", "skipped:no-candidates"),
    ("open", "skipped:in-use"), ("lsof-fails", "error:lsof-incomplete"), ("lsof-missing", "error:lsof-unreadable"),
    ("lsof-no-canary", "error:lsof-incomplete"), ("lsof-rc1-empty", "error:lsof-incomplete"),
    ("lsof-huge", "error:lsof-incomplete"), ("git-upper", "skipped:no-candidates"),
])
def test_unsafe_entries_are_never_removed(box, how, status):
    victim, outside = blocked_case(box, how)
    r = box.run("110", apply=True)
    assert os.path.lexists(victim) and (outside / "data.bin").exists()
    assert box.rules()["playwright-old"]["status"] == status
    assert r.returncode == (10 if status.startswith("error") else 0)
    assert "playwright-old" not in box.cooldowns()
    assert not list(pw_root(box).glob(".pro-janitor-canary-*"))   # the canary never outlives the probe


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

def test_a_tool_timeout_kills_its_group_not_a_setsid_grandchild_and_the_run_ends_in_time(box):
    ingroup, outside = box.tmp / "in.pid", box.tmp / "out.pid"
    t = box.bin / "uv"
    t.write_text(f"""#!/usr/bin/python3
import subprocess, time
a = subprocess.Popen(["/bin/sh", "-c", "trap '' TERM; exec sleep 300"])   # ignores TERM: only a group KILL ends it
b = subprocess.Popen(["/bin/sleep", "300"], start_new_session=True)
open("{ingroup}", "w").write(str(a.pid))
open("{outside}", "w").write(str(b.pid))
time.sleep(300)
""")
    t.chmod(0o755)
    t0 = time.monotonic()
    try:
        r = box.run("100", apply=True, PRO_JANITOR_TOOL_TIMEOUT="3")   # only the hanging uv is slow; npm has room under load
        took = time.monotonic() - t0
        assert took < 3 + 10 + 5 and r.returncode == 10
        rules = box.rules()
        assert rules["uv-prune"]["status"] == "error:timeout" and rules["npm-verify"]["status"] == "done"
        assert "playwright-old" in rules   # later rules still run

        def alive(pid):
            try:
                os.kill(pid, 0)
                return True
            except ProcessLookupError:
                return False
        for _ in range(50):
            if not alive(int(ingroup.read_text())):
                break
            time.sleep(0.1)
        assert not alive(int(ingroup.read_text())), "the tool's own group child survived"
        assert alive(int(outside.read_text())), "the janitor must not kill outside its group"
    finally:
        for f in (ingroup, outside):
            if f.exists():
                try:
                    os.kill(int(f.read_text()), 9)
                except (ProcessLookupError, ValueError):
                    pass


def test_a_tool_with_a_lot_of_output_does_not_block_on_a_pipe(box):
    box.uv = box.tool("uv", body="yes | head -c 5000000")
    r = box.run("125", apply=True, PRO_JANITOR_TOOL_TIMEOUT="10")
    assert box.rules()["uv-prune"]["status"] == "done" and r.returncode == 0


def test_a_failing_tool_is_an_error_and_the_next_rule_runs(box):
    box.uv = box.tool("uv", rc=3)
    r = box.run("125", apply=True)
    assert r.returncode == 10 and box.rules()["uv-prune"]["status"] == "error:rc=3"
    assert box.rules()["npm-verify"]["status"] == "done"


def test_a_missing_tool_is_an_error(box):
    r = box.run("125", apply=True, PRO_JANITOR_UV=str(box.bin / "nope"))
    assert r.returncode == 10 and box.rules()["uv-prune"]["status"] == "error:tool-missing"


# ---------------------------------------------------------------- config

@pytest.mark.parametrize("env", [{"PRO_JANITOR_NOW": "abc"}, {"PRO_JANITOR_NOW": "nan"}, {"PRO_JANITOR_NOW": "inf"},
                                 {"PRO_JANITOR_TOOL_TIMEOUT": "nan"}, {"PRO_JANITOR_FREE_GB_SEQ": "nan"}, {"PRO_JANITOR_FREE_GB_SEQ": "1,x"},
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
    assert hb["status"] == "error" and hb["note"].startswith("pro_janitor: bad config")


def test_wrapper_strips_control_characters_from_the_note(tmp_path):
    _, hb, _ = wrap(tmp_path, host="Air\x01-M5")
    assert hb["status"] == "disabled" and hb["note"] == "wrong-node Air-M5"


@pytest.mark.parametrize("host,env,note", [("Air-M5", {}, "wrong-node Air-M5"),
                                           ("Nuzantara", {"PRO_JANITOR_ENABLED": "false"}, "kill switch")])
def test_wrapper_node_guard_and_kill_switch_are_visible_disabled(tmp_path, host, env, note):
    res, hb, home = wrap(tmp_path, host=host, **env)
    assert hb["status"] == "disabled" and hb["note"] == note
    assert not (home / "logs" / "pro-janitor" / "journal.jsonl").exists()


def janitor_lookalike():
    """A live process whose command line contains `pro-janitor`, as the wrapper's own would."""
    return subprocess.Popen(["/usr/bin/python3", "-c", "import time; time.sleep(30)", "pro-janitor"])


def test_wrapper_second_instance_exits_without_running(tmp_path):
    alive = janitor_lookalike()
    (tmp_path / "nuzantara-pro-janitor.pid").write_text(str(alive.pid))
    try:
        _, hb, home = wrap(tmp_path)
    finally:
        alive.kill()
        alive.wait()
    assert hb["status"] == "warning" and hb["note"] == "skipped: previous run alive"
    assert not (home / "logs" / "pro-janitor" / "journal.jsonl").exists()


def test_wrapper_ignores_a_pidfile_whose_live_pid_is_not_a_janitor(tmp_path):
    other = subprocess.Popen(["sleep", "30"])   # a recycled pid: alive, but not ours
    (tmp_path / "nuzantara-pro-janitor.pid").write_text(str(other.pid))
    try:
        _, hb, home = wrap(tmp_path)
    finally:
        other.kill()
        other.wait()
    assert hb["status"] == "ok" and "tier=GREEN" in hb["note"]


def test_plist_is_a_dry_run_one_shot_with_no_keepalive():
    pl = plistlib.loads(PLIST.read_bytes())
    assert pl["StartInterval"] == 600 and pl["RunAtLoad"] is True and "KeepAlive" not in pl
    assert pl["ProcessType"] == "Background" and pl["LowPriorityIO"] is True   # a 10-minute I/O scanner on a workstation
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


def test_wrapper_pidfile_with_non_digit_content_is_not_a_live_run(tmp_path):
    (tmp_path / "nuzantara-pro-janitor.pid").write_text("-1")   # `kill -0 -1` would succeed: it signals everyone
    _, hb, _ = wrap(tmp_path)
    assert hb["status"] == "ok" and "tier=GREEN" in hb["note"]


def test_wrapper_maps_the_payload_lock_exit_11_to_a_warning(tmp_path):
    import fcntl
    state = tmp_path / "whome" / ".local/state/nuzantara/pro-janitor"
    state.mkdir(parents=True)
    fd = os.open(state / "lock", os.O_RDWR | os.O_CREAT)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        _, hb, home = wrap(tmp_path, seq="100")
    finally:
        os.close(fd)
    assert hb["status"] == "warning" and hb["note"] == "skipped: previous run alive"
    assert not (home / "logs" / "pro-janitor" / "journal.jsonl").exists()


@pytest.mark.parametrize("payload,rc,status,note", [
    ('import sys\nprint("Traceback (most recent call last):\\n  File \\"/Users/nuzantara/x.py\\", line 3", file=sys.stderr)\nsys.exit(1)', 1, "error", "payload rc=1"),
    ('print("pro_janitor: caf\\u00e9 ok")', 0, "ok", "payload rc=0"),
    ('print("pro_janitor: a\\x01b")', 0, "ok", "payload rc=0"),
    ('import sys\nprint("File /Users/nuzantara/secret", file=sys.stderr)\nprint("pro_janitor: tier=RED fine")\nsys.exit(10)', 10, "warning", "pro_janitor: tier=RED fine"),
])
def test_the_heartbeat_note_is_the_payloads_summary_line_or_the_rc_never_a_traceback(tmp_path, payload, rc, status, note):
    wrap(tmp_path)
    home = tmp_path / "whome"
    (home / ".nuzantara-cron" / "pro_janitor.py").write_text(payload + "\n")
    b = tmp_path / "wbin"
    res = subprocess.run(["/bin/bash", str(WRAPPER)], env={"HOME": str(home), "TMPDIR": str(tmp_path), "PATH": f"{b}:/usr/bin:/bin"},
                         capture_output=True, text=True, timeout=60)
    raw = (home / ".organism" / "last_seen" / "pro.janitor.json").read_text()
    hb = json.loads(raw)
    assert hb["status"] == status and hb["note"] == note and "/Users" not in raw and "Traceback" not in raw
    assert sorted(os.listdir(home / ".organism" / "last_seen")) == ["pro.janitor.json"]   # atomic: no tmp left behind


# ---------------------------------------------------------------- round 3: fd-anchored removal and the last look

def nth(box, n, cmd):
    """A lsof `pre` hook that runs `cmd` only on the n-th lsof call (1 = the plan's probe, 2 = the first candidate's
    last look, ...)."""
    cnt = box.tmp / "cnt"
    return (f'c=$(cat "{cnt}" 2>/dev/null || echo 0); c=$((c+1)); echo $c > "{cnt}"; '
            f'if [ "$c" = "{n}" ]; then {cmd}; fi')


def counted(box):
    cnt = box.tmp / "cnt"
    return f'c=$(cat "{cnt}" 2>/dev/null || echo 0); c=$((c+1)); echo $c > "{cnt}"'


def test_a_swapped_ancestor_of_the_root_is_never_followed_and_the_decoy_survives(box):
    import shutil as _sh
    root = pw_root(box)
    mk(root / "chromium-1243", 30)
    mk(root / "chromium-999", 30)
    links(box)
    caches = root.parent
    decoy = box.tmp / "decoy"
    _sh.copytree(caches, decoy, symlinks=True)
    box.lsof = box.fake_lsof(pre=nth(box, 1, f'mv "{caches}" "{caches}.orig" && ln -s "{decoy}" "{caches}"'))   # before the root is opened
    r = box.run("110", apply=True)
    res = box.rules()["playwright-old"]
    assert (decoy / "ms-playwright" / "chromium-999" / "data.bin").exists()
    assert (Path(str(caches) + ".orig") / "ms-playwright" / "chromium-999" / "data.bin").exists()
    assert res["entries"] == [{"name": "chromium-999", "bytes": 0, "state": "failed:root-changed"}] and r.returncode == 10


def test_open_anchored_refuses_a_symlinked_ancestor_and_returns_the_real_directory(tmp_path):
    real = tmp_path / "real" / "a"
    real.mkdir(parents=True)
    (tmp_path / "link").symlink_to(tmp_path / "real")
    with pytest.raises(OSError):
        pj.open_anchored(str(tmp_path / "link" / "a"))
    fd = pj.open_anchored(str(real))
    try:
        assert os.fstat(fd).st_ino == os.stat(real).st_ino
    finally:
        os.close(fd)


def test_a_candidate_replaced_by_a_different_real_dir_of_the_same_name_survives(box):
    root = pw_root(box)
    mk(root / "chromium-1243", 30)
    victim = root / "chromium-999"
    mk(victim, 30)
    box.lsof = box.fake_lsof(pre=nth(box, 2, f'mv "{victim}" "{victim}.orig"; mkdir "{victim}"; echo new > "{victim}/new.bin"'))
    r = box.run("110", apply=True)
    assert (victim / "new.bin").exists() and (Path(str(victim) + ".orig") / "data.bin").exists()
    assert box.rules()["playwright-old"]["entries"] == [{"name": "chromium-999", "bytes": 0, "state": "failed:changed"}] and r.returncode == 10


def fake_mount_stat(monkeypatch, name):
    """No unprivileged real mount exists in a test, so the mount is simulated: for the directory entry `name`, os.stat (by
    dir_fd) AND os.fstat of the fd opened on it both report another st_dev, exactly as a mounted filesystem would."""
    real_stat, real_open, real_fstat = os.stat, os.open, os.fstat
    mnt_fds = set()

    def bump(r):
        vals = list(r)[:10]
        vals[2] += 1
        return os.stat_result(vals)

    def fstat(fd):
        r = real_fstat(fd)
        return bump(r) if fd in mnt_fds else r

    def op(path, flags, *a, **k):
        fd = real_open(path, flags, *a, **k)
        if k.get("dir_fd") is not None and path == name:
            mnt_fds.add(fd)
        return fd

    def stat_(path, *a, **k):
        r = real_stat(path, *a, **k)
        return bump(r) if k.get("dir_fd") is not None and path == name else r
    monkeypatch.setattr(os, "stat", stat_)
    monkeypatch.setattr(os, "open", op)
    monkeypatch.setattr(os, "fstat", fstat)


def deep_tree(tmp_path):
    top = tmp_path / "victim"
    mk(top / "a" / "mnt", 30, files=("inner.bin",))
    mk(top / "a", 30, files=("sibling.bin",))
    return top


def test_remove_children_never_descends_into_another_device(tmp_path, monkeypatch):
    top = deep_tree(tmp_path)
    fd = os.open(top, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with monkeypatch.context() as m:
            fake_mount_stat(m, "mnt")
            w = pj.Walk(os.stat(top).st_dev, NOW)
            pj.remove_children(fd, w)
    finally:
        os.close(fd)
    assert w.cause == "changed" and w.failures >= 1 and (top / "a" / "mnt" / "inner.bin").exists() and not (top / "a" / "sibling.bin").exists()


def test_a_device_change_deep_inside_a_candidate_fails_the_audit_and_removes_nothing(tmp_path, monkeypatch):
    top = deep_tree(tmp_path)
    root_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        st = os.stat(top)
        with monkeypatch.context() as m:
            fake_mount_stat(m, "mnt")
            got = pj.remove_candidate(root_fd, "victim", (st.st_dev, st.st_ino), st.st_dev, NOW)
    finally:
        os.close(root_fd)
    assert got == ("failed:changed", 0) and (top / "a" / "mnt" / "inner.bin").exists() and (top / "a" / "sibling.bin").exists()


def test_a_symlink_inside_a_candidate_is_unlinked_never_its_target(tmp_path):
    top = tmp_path / "victim"
    mk(top, 30)
    outside = tmp_path / "outside"
    mk(outside, 30)
    (top / "link").symlink_to(outside)
    root_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        st = os.stat(top)
        got = pj.remove_candidate(root_fd, "victim", (st.st_dev, st.st_ino), st.st_dev, NOW)
    finally:
        os.close(root_fd)
    assert got[0] == "removed" and not top.exists() and (outside / "data.bin").exists()


def test_without_fd_support_the_dir_rule_is_skipped(box, monkeypatch):
    mk(pw_root(box) / "chromium-999", 30)
    mk(pw_root(box) / "chromium-1243", 30)
    monkeypatch.setenv("PRO_JANITOR_HOME", str(box.home))
    monkeypatch.setattr(pj, "fd_supported", lambda: False)
    assert pj.dir_rule(pj.Env(), pj.RULES[2], True) == ("skipped:no-fd-support", [])
    assert (pw_root(box) / "chromium-999").is_dir()


def two_old(box):
    root = pw_root(box)
    mk(root / "chromium-1243", 30)
    mk(root / "chromium-998", 30)
    mk(root / "chromium-999", 30)
    pkg = box.tmp / "pkgs" / "late"
    pkg.mkdir(parents=True)
    (pkg / "browsers.json").write_text(json.dumps({"browsers": [pb("chromium", 999)]}))
    return root, pkg


def states(box):
    return [(e["name"], e["state"]) for e in box.rules()["playwright-old"]["entries"]]


def test_a_candidate_pinned_after_the_first_removal_is_skipped_pinned_late(box):
    root, pkg = two_old(box)
    box.lsof = box.fake_lsof(pre=nth(box, 3, f'echo "{pkg}" > "{root}/.links/late"'))
    r = box.run("110", apply=True)
    assert states(box) == [("chromium-998", "removed"), ("chromium-999", "skipped:pinned-late")]
    assert not (root / "chromium-998").exists() and (root / "chromium-999").is_dir()
    assert box.rules()["playwright-old"]["status"] == "done" and r.returncode == 0


def test_a_candidate_opened_after_the_first_removal_is_skipped_open(box):
    root, _ = two_old(box)
    box.lsof = box.fake_lsof(pre=counted(box), extra=f'[ "$(cat "{box.tmp}/cnt")" = 3 ] && echo "n{root}/chromium-999/data.bin"')
    box.run("110", apply=True)
    assert states(box) == [("chromium-998", "removed"), ("chromium-999", "skipped:open")] and (root / "chromium-999").is_dir()


def test_an_installer_that_takes_the_lock_between_candidates_makes_the_next_one_skip(box, monkeypatch):
    root, _ = two_old(box)
    links(box)
    for k, v in {"PRO_JANITOR_HOME": str(box.home), "PRO_JANITOR_LSOF": str(box.lsof), "PRO_JANITOR_NOW": str(NOW),
                 "PRO_JANITOR_TOOL_TIMEOUT": "20"}.items():
        monkeypatch.setenv(k, v)
    real, calls = os.mkdir, []

    def mkdir(path, mode=0o777, *, dir_fd=None):
        if path == "__dirlock":
            calls.append(1)
            if len(calls) == 2:   # an installer got there first
                raise FileExistsError(17, "File exists")
        return real(path, mode, dir_fd=dir_fd)
    monkeypatch.setattr(os, "mkdir", mkdir)
    monkeypatch.setattr(os, "supports_dir_fd", os.supports_dir_fd | {mkdir})
    status, entries = pj.dir_rule(pj.Env(), pj.RULES[2], True)
    assert [(e["name"], e["state"]) for e in entries] == [("chromium-998", "removed"), ("chromium-999", "skipped:install-in-progress")]
    assert status == "done" and (root / "chromium-999").is_dir() and not (root / "__dirlock").exists()


def test_a_root_that_vanishes_mid_loop_still_journals_the_first_removal(box):
    root, _ = two_old(box)
    box.lsof = box.fake_lsof(pre=nth(box, 3, f'mv "{root}" "{root}.gone"'))
    r = box.run("110", apply=True)
    assert states(box) == [("chromium-998", "removed"), ("chromium-999", "failed:changed")]
    assert box.rules()["playwright-old"]["status"] == "error:rmtree-partial" and r.returncode == 10
    assert not (Path(str(root) + ".gone") / "chromium-998").exists() and (Path(str(root) + ".gone") / "chromium-999").is_dir()


@pytest.mark.parametrize("rc,canary,err,status", [
    (1, True, "", "done"),                                     # +D: rc 1 is the normal healthy result
    (0, True, "", "done"),
    (1, True, "echo \"lsof: WARNING: can't opendir(/x): Permission denied\"", "error:lsof-incomplete"),
    (1, False, "", "error:lsof-incomplete"),
    (2, True, "", "error:lsof-incomplete"),
    (1, True, "head -c 70000 /dev/zero | tr '\\0' x", "error:lsof-incomplete"),   # stderr over its 64 KiB cap
])
def test_the_lsof_scan_is_complete_iff_rc_0_or_1_and_the_canary_and_empty_stderr(box, rc, canary, err, status):
    root = two_chromiums(box)
    box.lsof = box.fake_lsof(rc=rc, canary=canary, err=err)
    r = box.run("110", apply=True)
    assert box.rules()["playwright-old"]["status"] == status
    assert (not (root / "chromium-1100").exists()) == (status == "done") and r.returncode == (0 if status == "done" else 10)
    assert "Permission denied" not in box.journal.read_text() + r.stdout   # stderr is tested, never kept


def test_lsof_is_run_without_w_so_that_warnings_reach_stderr(box):
    two_chromiums(box)
    box.run("110", apply=True)
    argv = (box.tmp / "lsof.argv").read_text().splitlines()
    assert argv and all(a.split()[:3] == ["-F", "n", "+D"] and "-w" not in a.split() for a in argv)


def test_a_failed_free_space_read_after_an_action_stops_everything_and_warns(box):
    r = box.run("125,ERR", apply=True)
    ln = box.last()
    assert r.returncode == 10 and ln["free_read_failed"] is True and ln["free_gb_after"] is None
    assert box.verbs() == ["uv cache prune"] and [x["id"] for x in ln["rules"]] == ["uv-prune"]
    assert box.cooldowns() == {"uv-prune": NOW}


def test_a_failed_first_free_space_read_is_exit_1(box):
    assert box.run("ERR").returncode == 1


def test_a_symlinked_state_dir_is_unusable_exit_1(box):
    other = box.tmp / "elsewhere"
    other.mkdir()
    box.state.symlink_to(other)
    r = box.run("125", apply=True)
    assert r.returncode == 1 and "state dir unusable" in r.stdout and not box.journal.exists()
    assert list(other.iterdir()) == []


def test_a_state_dir_outside_home_is_unusable_exit_1(box):
    r = box.run("125", PRO_JANITOR_STATE_DIR=str(box.tmp / "st-out"))
    assert r.returncode == 1 and "state dir unusable" in r.stdout and not (box.tmp / "st-out").exists()


def test_a_lock_that_cannot_be_opened_is_unusable_not_alive(box):
    box.state.mkdir()
    (box.state / "lock").symlink_to(box.tmp / "nowhere")   # O_NOFOLLOW refuses it
    r = box.run("125")
    assert r.returncode == 1 and "lock unusable" in r.stdout


def test_a_flock_error_other_than_contention_is_exit_1_not_11(box, monkeypatch, capsys):
    import fcntl
    for k, v in {"PRO_JANITOR_HOME": str(box.home), "PRO_JANITOR_STATE_DIR": str(box.state),
                 "PRO_JANITOR_JOURNAL": str(box.journal), "PRO_JANITOR_FREE_GB_SEQ": "200"}.items():
        monkeypatch.setenv(k, v)

    def boom(fd, op):
        raise PermissionError(13, "denied")
    monkeypatch.setattr(fcntl, "flock", boom)
    assert pj.main() == 1 and "lock unusable" in capsys.readouterr().out


def stale_setup(box):
    root = pw_root(box)
    root.mkdir(parents=True)
    dead = []
    for _ in range(3):
        p = subprocess.Popen(["true"])
        p.wait()
        dead.append(p.pid)
    live = subprocess.Popen(["sleep", "30"])
    h = "0123456789abcdef"
    files = {"dead": root / f".pro-janitor-canary-{dead[0]}-{h}", "live": root / f".pro-janitor-canary-{live.pid}-{h}",
             "full": root / f".pro-janitor-canary-{dead[1]}-{h}", "link": root / f".pro-janitor-canary-{dead[2]}-{h}",
             "alpha": root / ".pro-janitor-canary-abc", "old-format": root / f".pro-janitor-canary-{dead[0]}"}
    files["dead"].write_bytes(b"")
    files["live"].write_bytes(b"")
    files["full"].write_bytes(b"x")
    files["link"].symlink_to(box.tmp / "target")
    files["alpha"].write_bytes(b"")
    files["old-format"].write_bytes(b"")
    return files, live


def test_stale_canaries_of_dead_pids_are_swept_and_nothing_else(box):
    files, live = stale_setup(box)
    try:
        box.run("110", apply=True)
    finally:
        live.kill()
        live.wait()
    assert {k: os.path.lexists(v) for k, v in files.items()} == {
        "dead": False, "live": True, "full": True, "link": True, "alpha": True, "old-format": True}


def test_dry_run_sweeps_nothing(box):
    files, live = stale_setup(box)
    try:
        box.run("110")
    finally:
        live.kill()
        live.wait()
    assert files["dead"].exists()


def test_a_pin_with_leading_zeros_protects_the_numerically_equal_dir(box):
    root = pw_root(box)
    mk(root / "chromium-1243", 30)
    mk(root / "chromium-1100", 30)
    mk(root / "chromium-1050", 30)
    links(box, [pb("chromium", "01100")])
    box.run("110", apply=True)
    assert (root / "chromium-1100").is_dir() and not (root / "chromium-1050").exists()


def test_an_oserror_in_the_removal_loop_is_contained_and_the_first_removal_is_still_returned(box, monkeypatch):
    root, _ = two_old(box)
    links(box)
    for k, v in {"PRO_JANITOR_HOME": str(box.home), "PRO_JANITOR_LSOF": str(box.lsof), "PRO_JANITOR_NOW": str(NOW),
                 "PRO_JANITOR_TOOL_TIMEOUT": "20"}.items():
        monkeypatch.setenv(k, v)
    real, calls = pj.open_anchored, []

    def flaky(path):
        calls.append(path)
        if len(calls) == 4:   # sweep, the plan probe, candidate 1, candidate 2
            raise FileNotFoundError(2, "the root vanished")
        return real(path)
    monkeypatch.setattr(pj, "open_anchored", flaky)
    status, entries = pj.dir_rule(pj.Env(), pj.RULES[2], True)
    assert [(e["name"], e["state"]) for e in entries] == [("chromium-998", "removed"), ("chromium-999", "failed:vanished")]
    assert status == "error:rmtree-partial" and not (root / "chromium-998").exists() and (root / "chromium-999").is_dir()


# ---------------------------------------------------------------- spec conformance: the threat model's invariants

class Stat(object):
    """A stat result with a few fields replaced (os.stat_result cannot carry a different ctime)."""

    def __init__(self, real, **over):
        for k in ("st_mode", "st_dev", "st_ino", "st_size", "st_mtime", "st_ctime"):
            setattr(self, k, getattr(real, k))
        for k, v in over.items():
            setattr(self, k, v)


def patch_stat(monkeypatch, name, **over):
    real = os.stat

    def stat_(path, *a, **k):
        r = real(path, *a, **k)
        if k.get("dir_fd") is not None and path == name:
            return Stat(r, **{key: (val(r) if callable(val) else val) for key, val in over.items()})
        return r
    monkeypatch.setattr(os, "stat", stat_)


def plain_tree(tmp_path, files=("a.bin", "b.bin")):
    root = tmp_path / "root"
    victim = root / "victim"
    mk(victim / "sub", 30, files=files)
    mk(victim, 30, files=("top.bin",))
    st = os.stat(victim)
    return root, victim, (st.st_dev, st.st_ino), st.st_dev


def candidate(root, victim_rec, root_dev, name="victim", **kw):
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        return pj.remove_candidate(fd, name, victim_rec, root_dev, NOW, **kw)
    finally:
        os.close(fd)


def after_audit(monkeypatch, fn):
    """Run `fn` once, right after the candidate's audit and before its walk: the window the removal-time checks close."""
    real = pj.audit_fd

    def wrapped(fd, root_dev, depth=0):
        r = real(fd, root_dev, depth)
        if depth == 0:
            fn()
        return r
    monkeypatch.setattr(pj, "audit_fd", wrapped)


def test_a_dot_git_renamed_into_the_candidate_after_the_audit_is_left_in_place(tmp_path, monkeypatch):
    root, victim, rec, dev = plain_tree(tmp_path)
    newgit = tmp_path / "newgit"
    mk(newgit, 30)
    after_audit(monkeypatch, lambda: os.rename(newgit, victim / "sub" / ".GIT"))
    got = candidate(root, rec, dev)
    assert got[0] == "failed:changed" and (victim / "sub" / ".GIT" / "data.bin").exists() and (victim / "sub").is_dir()


def test_a_young_file_moved_into_the_candidate_after_the_audit_is_left_in_place(tmp_path, monkeypatch):
    root, victim, rec, dev = plain_tree(tmp_path)

    def young():
        f = victim / "sub" / "fresh.bin"
        f.write_bytes(b"x")
        os.utime(f, (NOW - DAY, NOW - DAY))   # younger than 7 days against the fake NOW
    after_audit(monkeypatch, young)
    got = candidate(root, rec, dev)
    assert got[0] == "failed:changed" and (victim / "sub" / "fresh.bin").exists() and victim.is_dir()


def test_a_young_ctime_alone_is_enough_to_leave_an_object(tmp_path, monkeypatch):
    root, victim, rec, dev = plain_tree(tmp_path)
    (victim / "sub" / "young.bin").write_bytes(b"x")
    os.utime(victim / "sub" / "young.bin", (NOW - 30 * DAY,) * 2)   # old mtime
    patch_stat(monkeypatch, "young.bin", st_ctime=NOW - DAY)         # young ctime
    fd = os.open(victim / "sub", os.O_RDONLY | os.O_DIRECTORY)
    try:
        w = pj.Walk(os.stat(victim).st_dev, NOW)
        pj.remove_children(fd, w)
    finally:
        os.close(fd)
    assert w.cause == "changed" and (victim / "sub" / "young.bin").exists() and not (victim / "sub" / "a.bin").exists()


def test_a_directory_that_is_not_the_inode_it_was_opened_as_is_left_in_place(tmp_path, monkeypatch):
    root, victim, rec, dev = plain_tree(tmp_path)
    patch_stat(monkeypatch, "sub", st_ino=lambda r: r.st_ino + 1)
    fd = os.open(victim, os.O_RDONLY | os.O_DIRECTORY)
    try:
        w = pj.Walk(dev, NOW)
        pj.remove_children(fd, w)
    finally:
        os.close(fd)
    assert w.cause == "changed" and (victim / "sub" / "a.bin").exists() and not (victim / "top.bin").exists()


def test_our_own_unlinks_do_not_make_a_directory_look_young(tmp_path):
    root, victim, rec, dev = plain_tree(tmp_path)
    assert candidate(root, rec, dev)[0] == "removed" and not victim.exists()


def test_an_n_record_that_is_not_an_absolute_path_makes_the_scan_incomplete(box):
    root = two_chromiums(box)
    box.lsof = box.fake_lsof(extra='echo "nFD info error: Operation not permitted"')
    box.run("110", apply=True)
    assert box.rules()["playwright-old"]["status"] == "error:lsof-incomplete" and (root / "chromium-1100").is_dir()
    box.lsof = box.fake_lsof(extra='echo "n/some/other/file"')
    box.run("110", apply=True, now=NOW + 99 * DAY)
    assert box.rules()["playwright-old"]["status"] == "done"


def test_a_planted_canary_with_a_huge_pid_cannot_crash_the_run(box):
    root = two_chromiums(box)
    planted = root / ".pro-janitor-canary-9999999999-0123456789abcdef"
    planted.write_bytes(b"")
    r = box.run("110", apply=True)
    assert r.returncode == 0 and planted.exists() and box.rules()["playwright-old"]["status"] == "done"


def one_old(box, nfiles=5, size=10):
    root = pw_root(box)
    mk(root / "chromium-1243", 30)
    mk(root / "chromium-998", 30, files=tuple(f"f{i}.bin" for i in range(nfiles)), size=size)
    mk(root / "chromium-999", 30)
    return root


@pytest.mark.parametrize("env,left", [({"PRO_JANITOR_MAX_OBJECTS": "2"}, 3), ({"PRO_JANITOR_MAX_BYTES": "15"}, 4)])
def test_a_run_stops_at_its_blast_radius_cap_and_says_so(box, env, left):
    root = one_old(box)
    r = box.run("110", apply=True, **env)
    res = box.rules()["playwright-old"]
    assert res["capped"] is True and [(e["name"], e["state"]) for e in res["entries"]] == [("chromium-998", "failed:capped")]
    assert len(list((root / "chromium-998").iterdir())) == left and (root / "chromium-999").is_dir() and r.returncode == 10
    assert not (root / "__dirlock").exists()


def test_the_caps_default_to_10_gb_and_200000_objects(box, monkeypatch):
    monkeypatch.setenv("PRO_JANITOR_HOME", str(box.home))
    e = pj.Env()
    assert (e.max_bytes, e.max_objects) == (10 * 10**9, 200000)


@pytest.mark.parametrize("how", ["env", "file"])
def test_the_kill_switch_at_start_does_nothing_and_exits_12(box, how):
    if how == "file":
        box.state.mkdir()
        (box.state / "disabled").write_text("")
    r = box.run("100", apply=True, **({"PRO_JANITOR_ENABLED": "false"} if how == "env" else {}))
    assert r.returncode == 12 and box.calls() == [] and box.last()["disabled"] is True and "rules" not in box.last()


def test_the_kill_switch_file_created_during_candidate_1_stops_it_and_leaves_candidate_2_untouched(box):
    root, _ = two_old(box)
    box.lsof = box.fake_lsof(pre=nth(box, 2, f'touch "{box.state}/disabled"'))
    r = box.run("110", apply=True)
    res = box.rules()["playwright-old"]
    assert [(e["name"], e["state"]) for e in res["entries"]] == [("chromium-998", "failed:stopped")] and res["stopped"] == "kill-switch"
    assert (root / "chromium-999").is_dir() and (root / "chromium-998" / "data.bin").exists() and r.returncode == 10
    assert not (root / "__dirlock").exists()


def test_the_kill_switch_is_read_while_a_candidate_is_walked_at_most_once_a_second(tmp_path, monkeypatch):
    root, victim, rec, dev = plain_tree(tmp_path, files=tuple(f"f{i}" for i in range(6)))
    for k, v in {"PRO_JANITOR_HOME": str(tmp_path), "PRO_JANITOR_STATE_DIR": str(tmp_path / "st")}.items():
        monkeypatch.setenv(k, v)
    (tmp_path / "st").mkdir()
    env = pj.Env()
    t = {"now": 0.0}
    monkeypatch.setattr(pj, "mono", lambda: t["now"])
    reads, real_killed = [], env.killed
    env.killed = lambda: (reads.append(t["now"]), real_killed())[1]
    real_unlink, n = os.unlink, [0]

    def unlink(path, *a, **k):
        n[0] += 1
        t["now"] += 0.4   # three unlinks per second of walk
        if n[0] == 2:
            (tmp_path / "st" / "disabled").write_text("")
        return real_unlink(path, *a, **k)
    monkeypatch.setattr(os, "unlink", unlink)
    got = candidate(root, rec, dev, env=env)
    assert got[0] == "failed:stopped" and n[0] >= 3 and len(list((victim / "sub").iterdir())) >= 2 and victim.is_dir()
    assert all(b - a >= 1.0 for a, b in zip(reads, reads[1:]))   # throttled: never twice within a second


def test_the_lock_is_held_around_each_candidate_and_gone_afterwards(box):
    root, _ = two_old(box)
    rec = box.tmp / "lock.rec"
    box.lsof = box.fake_lsof(pre=f'if [ -d "{root}/__dirlock" ]; then echo held >> "{rec}"; else echo free >> "{rec}"; fi')
    box.run("110", apply=True)
    assert rec.read_text().split() == ["free", "held", "held"]   # the plan's probe, then one per candidate
    assert not (root / "__dirlock").exists() and not (root / "chromium-998").exists() and not (root / "chromium-999").exists()


def test_dry_run_never_takes_the_lock(box):
    root, _ = two_old(box)
    rec = box.tmp / "lock.rec"
    box.lsof = box.fake_lsof(pre=f'if [ -d "{root}/__dirlock" ]; then echo held >> "{rec}"; else echo free >> "{rec}"; fi')
    box.run("110")
    assert rec.read_text().split() == ["free"] and not (root / "__dirlock").exists() and (root / "chromium-998").is_dir()


def test_an_existing_lock_dir_skips_and_a_stale_one_is_journaled(box):
    root = two_chromiums(box)
    (root / "__dirlock").mkdir()
    os.utime(root / "__dirlock", (NOW - 7200, NOW - 7200))
    box.run("110", apply=True)
    res = box.rules()["playwright-old"]
    assert res["status"] == "skipped:install-in-progress" and res["stale_dirlock"] is True and (root / "chromium-1100").is_dir()
    assert (root / "__dirlock").is_dir()   # not ours: left alone


def test_a_fresh_lock_is_not_journaled_stale(box):
    root = two_chromiums(box)
    (root / "__dirlock").mkdir()
    os.utime(root / "__dirlock", (NOW - 60, NOW - 60))
    box.run("110", apply=True)
    res = box.rules()["playwright-old"]
    assert res["status"] == "skipped:install-in-progress" and "stale_dirlock" not in res


def test_a_lock_whose_identity_changes_mid_walk_fails_the_candidate_and_leaves_the_other_lock(tmp_path, monkeypatch):
    root, victim, rec, dev = plain_tree(tmp_path)
    rfd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    lock = pj.Lock(rfd, 0)
    lock.take()

    def swap():
        os.rename(root / "__dirlock", root / "lock.old")
        os.mkdir(root / "__dirlock")   # another process's lock
    after_audit(monkeypatch, swap)
    try:
        got = pj.remove_candidate(rfd, "victim", rec, dev, NOW, None, lock)
        lock.release()
    finally:
        os.close(rfd)
    assert got[0] == "failed:lock-lost" and (root / "__dirlock").is_dir() and (root / "lock.old").is_dir() and victim.is_dir()


def test_the_keepalive_thread_refreshes_the_lock_mtime_on_its_own(tmp_path):
    root, victim, rec, dev = plain_tree(tmp_path)
    rfd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    lock = pj.Lock(rfd, 0.05)
    lock.take()
    try:
        os.utime(root / "__dirlock", (1000, 1000))
        for _ in range(100):
            time.sleep(0.05)
            if os.stat(root / "__dirlock").st_mtime > 1000 + 3600:
                break
        mtime = os.stat(root / "__dirlock").st_mtime
        thread = lock._thread
    finally:
        lock.release()
        os.close(rfd)
    assert mtime > 1000 + 3600 and not thread.is_alive() and thread.daemon and not (root / "__dirlock").exists()


def test_the_lock_is_refreshed_during_a_slow_lsof(box):
    root, _ = two_old(box)
    rec = box.tmp / "mtimes.rec"
    box.lsof = box.fake_lsof(pre=f'if [ -d "{root}/__dirlock" ]; then stat -f %m "{root}/__dirlock" >> "{rec}"; sleep 2.5; '
                                 f'stat -f %m "{root}/__dirlock" >> "{rec}"; fi')
    box.run("110", apply=True, PRO_JANITOR_LOCK_REFRESH="0.3")
    m = [int(x) for x in rec.read_text().split()]
    assert len(m) == 4 and m[1] >= m[0] + 2 and m[3] >= m[2] + 2   # each held-lock lsof call: start, then 2.5 s later
    assert states(box) == [("chromium-998", "removed"), ("chromium-999", "removed")]


class Clock(object):
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def lock_tree(tmp_path, files):
    root, victim, rec, dev = plain_tree(tmp_path, files=files)
    rfd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    return root, victim, rec, dev, rfd


def leased(tmp_path, files=("o1", "o2", "o3", "o4", "o5"), interval=2, wall_clock=None):
    """A taken lock on a fake monotonic clock; the real thread never fires inside a test (interval 2 s) unless asked."""
    clk = Clock()
    root, victim, rec, dev, rfd = lock_tree(tmp_path, files)
    lock = pj.Lock(rfd, interval, mono_clock=clk, wall_clock=wall_clock or clk)
    lock.take()
    return clk, root, victim, rec, dev, rfd, lock


def sub_left(victim):
    return sorted(p.name for p in (victim / "sub").iterdir())


def test_a_stall_longer_than_8_seconds_before_an_unlink_refuses_it_and_every_later_one(tmp_path, monkeypatch):
    clk, root, victim, rec, dev, rfd, lock = leased(tmp_path)
    real, seen = os.stat, []

    def stat_(path, *a, **k):
        if k.get("dir_fd") is not None and path == "o3":
            seen.append(1)
            if len(seen) == 2:   # the walk's stat (the first was the audit's)
                clk.t += 9   # a stat that stalls 9 s: the lock may have been taken over by an installer meanwhile
        return real(path, *a, **k)
    monkeypatch.setattr(os, "stat", stat_)
    try:
        got = pj.remove_candidate(rfd, "victim", rec, dev, NOW, None, lock)
    finally:
        monkeypatch.undo()
        lock.release()
        os.close(rfd)
    assert got[0] == "failed:lock-stale" and sub_left(victim) == ["o3", "o4", "o5"]
    assert (root / "__dirlock").is_dir()   # the lease ran out: left to go stale, never rmdir'd


def test_the_acquire_stat_returning_4_seconds_after_t0_is_lock_uncertain(tmp_path, monkeypatch):
    clk = Clock()
    root, victim, rec, dev, rfd = lock_tree(tmp_path, ("o1",))
    real = os.stat

    def slow(path, *a, **k):
        if path == "__dirlock":
            clk.t += 4
        return real(path, *a, **k)
    monkeypatch.setattr(os, "stat", slow)
    lock = pj.Lock(rfd, 2, mono_clock=clk, wall_clock=clk)
    try:
        with pytest.raises(pj.LockUncertain):
            lock.take()
        monkeypatch.undo()
        lock.release()
    finally:
        os.close(rfd)
    assert lock.id is None and lock._thread is None
    assert (root / "__dirlock").is_dir() and (victim / "sub" / "o1").exists()   # never rmdir'd, nothing removed


def test_the_acquire_stat_just_under_4_seconds_takes_the_lease_at_t0_plus_8(tmp_path, monkeypatch):
    clk = Clock()
    root, victim, rec, dev, rfd = lock_tree(tmp_path, ("o1",))
    real = os.stat

    def slow(path, *a, **k):
        if path == "__dirlock":
            clk.t += 3.9
        return real(path, *a, **k)
    monkeypatch.setattr(os, "stat", slow)
    lock = pj.Lock(rfd, 2, mono_clock=clk, wall_clock=clk)
    try:
        lock.take()
        monkeypatch.undo()
        until = lock.lease_until()
        lock.release()
    finally:
        os.close(rfd)
    assert until == 1000.0 + 8 and not (root / "__dirlock").exists()


def test_t0_is_read_before_the_mkdir(tmp_path, monkeypatch):
    clk = Clock()
    root, victim, rec, dev, rfd = lock_tree(tmp_path, ("o1",))
    real = os.mkdir

    def slow_mkdir(path, *a, **k):
        if path == "__dirlock":
            clk.t += 3   # a slow mkdir: the mtime it sets is at or after t0, so the lease must count from t0
        return real(path, *a, **k)
    monkeypatch.setattr(os, "mkdir", slow_mkdir)
    lock = pj.Lock(rfd, 2, mono_clock=clk, wall_clock=clk)
    try:
        lock.take()
        monkeypatch.undo()
        until = lock.lease_until()
        lock.release()
    finally:
        os.close(rfd)
    assert until == 1000.0 + 8   # not 1003 + 8


def inproc(box, monkeypatch, seq, **env):
    """box.run, but in this process so a test can move the clocks or patch os; returns the payload's exit code."""
    r = pw_root(box)
    if r.is_dir() and not (r / ".links").exists():
        links(box, [pb("winldd", 1)])
    e = {"PRO_JANITOR_HOME": str(box.home), "PRO_JANITOR_STATE_DIR": str(box.state), "PRO_JANITOR_JOURNAL": str(box.journal),
         "PRO_JANITOR_NOW": str(NOW), "PRO_JANITOR_UV": str(box.uv), "PRO_JANITOR_NPM": str(box.npm),
         "PRO_JANITOR_LSOF": str(box.lsof), "PRO_JANITOR_FREE_GB_SEQ": seq, "PRO_JANITOR_TOOL_TIMEOUT": "20",
         "PRO_JANITOR_TMP": str(box.tmp), "PRO_JANITOR_APPLY": "true"}
    e.update(env)
    for k, v in e.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(pj, "fd_supported", lambda: True)   # a patched os.stat/os.utime is no longer in os.supports_*
    return pj.main()


def test_an_uncertain_lock_stops_the_rule_with_nothing_removed_and_the_lock_not_rmdird(box, monkeypatch):
    root, _ = two_old(box)
    real, t = os.stat, {"jump": 0.0}
    monkeypatch.setattr(pj, "mono", lambda: time.monotonic() + t["jump"])

    def slow(path, *a, **k):
        if path == "__dirlock":
            t["jump"] += 5   # the acquire stat returns 5 s after t0
        return real(path, *a, **k)
    monkeypatch.setattr(os, "stat", slow)
    inproc(box, monkeypatch, "110")
    monkeypatch.undo()
    res = box.rules()["playwright-old"]
    assert res["status"] == "skipped:lock-uncertain" and [e["state"] for e in res["entries"]] == ["skipped:lock-uncertain"]
    assert (root / "__dirlock").is_dir() and (root / "chromium-998").is_dir() and (root / "chromium-999").is_dir()


def test_a_dead_keepalive_thread_lets_the_lease_run_out_and_the_next_unlink_is_refused(tmp_path, monkeypatch):
    clk = Clock()
    root, victim, rec, dev, rfd = lock_tree(tmp_path, ("o1", "o2", "o3"))
    lock = pj.Lock(rfd, 0.05, mono_clock=clk, wall_clock=clk)
    lock.take()

    def boom(*a, **k):
        raise RuntimeError("the keepalive blew up")   # not even an OSError
    monkeypatch.setattr(os, "utime", boom)
    for _ in range(100):
        if not lock._thread.is_alive():
            break
        time.sleep(0.02)
    monkeypatch.undo()
    clk.t += 9   # the lease runs out; nothing extends it any more
    try:
        dead = not lock._thread.is_alive() and lock.failed
        got = pj.remove_candidate(rfd, "victim", rec, dev, NOW, None, lock)
        lock.release()
    finally:
        os.close(rfd)
    assert dead and got[0] == "failed:lock-stale" and (victim / "sub" / "o1").exists() and (root / "__dirlock").is_dir()


def test_a_stopped_keepalive_is_not_assumed_alive(tmp_path):
    clk, root, victim, rec, dev, rfd, lock = leased(tmp_path, ("o1",))
    lock._stop.set()
    lock._thread.join(timeout=5)
    clk.t += 8   # at lease_until exactly the lease is over
    try:
        got = pj.remove_candidate(rfd, "victim", rec, dev, NOW, None, lock)
    finally:
        lock.release()
        os.close(rfd)
    assert got[0] == "failed:lock-stale" and (victim / "sub" / "o1").exists()


def test_a_refresh_extends_the_lease_to_t1_plus_8_after_a_fresh_stat_and_utime(tmp_path):
    clk, root, victim, rec, dev, rfd, lock = leased(tmp_path)
    try:
        os.utime(root / "__dirlock", (1000, 1000))
        clk.t += 2
        assert lock._refresh() is True
        until = lock.lease_until()
        mtime = os.stat(root / "__dirlock").st_mtime
    finally:
        lock.release()
        os.close(rfd)
    assert until == 1002.0 + 8 and mtime > 1000 + 3600


def test_a_utime_that_returns_after_the_lease_does_not_extend_it_and_ends_the_thread(tmp_path, monkeypatch):
    clk, root, victim, rec, dev, rfd, lock = leased(tmp_path)
    real = os.utime

    def late(*a, **k):
        r = real(*a, **k)
        clk.t += 9   # the utime returned after lease_until
        return r
    monkeypatch.setattr(os, "utime", late)
    try:
        clk.t += 2
        assert lock._refresh() is False
        monkeypatch.undo()
        until = lock.lease_until()
        got = pj.remove_candidate(rfd, "victim", rec, dev, NOW, None, lock)
    finally:
        lock.release()
        os.close(rfd)
    assert until == 1000.0 + 8 and got[0] == "failed:lock-stale"


def test_a_refresh_whose_identity_stat_shows_another_inode_ends_the_thread(tmp_path):
    clk, root, victim, rec, dev, rfd, lock = leased(tmp_path)
    try:
        os.rename(root / "__dirlock", root / "lock.old")
        os.mkdir(root / "__dirlock")
        clk.t += 2
        assert lock._refresh() is False and lock.lease_until() == 1000.0 + 8
    finally:
        lock.release()
        os.close(rfd)
    assert (root / "__dirlock").is_dir()   # the foreign directory is never rmdir'd


@pytest.mark.parametrize("skew,extends", [(1.5, False), (-1.5, False), (0.9, True)])
def test_wall_and_monotonic_drift_over_a_second_ends_the_thread(tmp_path, skew, extends):
    wall_clk = Clock()
    clk, root, victim, rec, dev, rfd, lock = leased(tmp_path, wall_clock=wall_clk)
    try:
        clk.t += 2
        wall_clk.t += 2 + skew
        ok = lock._refresh()
        until = lock.lease_until()
    finally:
        lock.release()
        os.close(rfd)
    assert ok is extends and until == (1002.0 + 8 if extends else 1000.0 + 8)


def test_a_drifting_thread_really_ends_and_the_lease_runs_out(tmp_path):
    wall_clk, clk = Clock(), Clock()
    root, victim, rec, dev, rfd = lock_tree(tmp_path, ("o1",))
    lock = pj.Lock(rfd, 0.05, mono_clock=clk, wall_clock=wall_clk)
    lock.take()
    wall_clk.t += 5   # the wall clock jumped, the monotonic one did not
    for _ in range(100):
        if not lock._thread.is_alive():
            break
        time.sleep(0.02)
    clk.t += 9
    try:
        dead = not lock._thread.is_alive() and lock.failed
        got = pj.remove_candidate(rfd, "victim", rec, dev, NOW, None, lock)
        lock.release()
    finally:
        os.close(rfd)
    assert dead and got[0] == "failed:lock-stale" and (victim / "sub" / "o1").exists()


def test_a_lock_replaced_by_another_dirlock_fails_lock_lost_and_release_never_rmdirs_it(tmp_path, monkeypatch):
    clk, root, victim, rec, dev, rfd, lock = leased(tmp_path)

    def swap():
        os.rename(root / "__dirlock", root / "lock.old")
        os.mkdir(root / "__dirlock")   # another process's lock, with a valid lease on our side
    after_audit(monkeypatch, swap)
    try:
        got = pj.remove_candidate(rfd, "victim", rec, dev, NOW, None, lock)
        monkeypatch.undo()
        lock.release()
    finally:
        os.close(rfd)
    assert got[0] == "failed:lock-lost" and (root / "__dirlock").is_dir() and (root / "lock.old").is_dir() and victim.is_dir()


def test_a_keepalive_stuck_after_the_join_is_journaled_and_ends_the_rule(box, monkeypatch):
    root, _ = two_old(box)
    gate = threading.Event()
    real_utime = os.utime

    def blocked(*a, **k):
        gate.wait(10)
        return real_utime(*a, **k)
    monkeypatch.setattr(pj.Lock, "JOIN_TIMEOUT", 0.2)
    monkeypatch.setattr(os, "utime", blocked)
    try:
        inproc(box, monkeypatch, "110", PRO_JANITOR_LOCK_REFRESH="0.01")
        time.sleep(0.3)   # let the thread reach the blocked utime before the join gives up
    finally:
        gate.set()
    res = box.rules()["playwright-old"]
    assert res["lock_thread_stuck"] is True and len(res["entries"]) == 1   # the second candidate was never started


def test_a_long_walk_with_refreshes_keeps_the_lease_and_the_candidate_is_removed(tmp_path):
    names = tuple("f%02d" % i for i in range(30))
    clk, root, victim, rec, dev, rfd, lock = leased(tmp_path, names)
    seen = []
    orig = pj.Walk.guard

    def guard(self):
        clk.t += 1   # 30 s of walking in all, far past one lease
        if int(clk.t) % 2 == 0:
            assert lock._refresh() is True
        seen.append(lock.lease_until() - clk.t)
        return orig(self)
    pj.Walk.guard = guard
    try:
        got = pj.remove_candidate(rfd, "victim", rec, dev, NOW, None, lock)
    finally:
        pj.Walk.guard = orig
        lock.release()
        os.close(rfd)
    assert got[0] == "removed" and not victim.exists() and min(seen) > 0
    assert not (root / "__dirlock").exists()


def test_release_rmdirs_our_own_valid_lock_and_only_then(tmp_path):
    clk, root, victim, rec, dev, rfd, lock = leased(tmp_path, ("o1",))
    try:
        lock.release()
        gone = not (root / "__dirlock").exists()
        assert gone and lock._thread is not None and not lock._thread.is_alive()
    finally:
        os.close(rfd)


def test_release_leaves_a_lock_whose_lease_has_run_out(tmp_path):
    clk, root, victim, rec, dev, rfd, lock = leased(tmp_path, ("o1",))
    clk.t += 8
    try:
        lock.release()
    finally:
        os.close(rfd)
    assert (root / "__dirlock").is_dir()


# Mutants: scripts/mutation_incremental.py is a generic diff-driven mutmut driver with no per-module rule files, so each
# edit of invariant 8 that a mutation run could make is pinned by the test named here instead.
#   check removed ................................ test_a_stall_longer_than_8_seconds_before_an_unlink_refuses_it_and_every_later_one
#                                                  test_a_lock_replaced_by_another_dirlock_fails_lock_lost_and_release_never_rmdirs_it
#   lease extended without the utime-before-lease  test_a_utime_that_returns_after_the_lease_does_not_extend_it_and_ends_the_thread
#   t0 read after the mkdir ...................... test_t0_is_read_before_the_mkdir


def test_our_lock_is_gone_after_success_and_after_failure(box):
    root, _ = two_old(box)
    box.lsof = box.fake_lsof(pre=nth(box, 3, f'echo fresh > "{root}/chromium-999/fresh.bin"; touch -t 202701140000 "{root}/chromium-999/fresh.bin"'))
    box.run("110", apply=True)
    assert states(box) == [("chromium-998", "removed"), ("chromium-999", "failed:changed")]
    assert not (root / "__dirlock").exists()


def test_a_free_space_delta_of_the_filesystem_is_journaled_beside_the_unlinked_bytes(box):
    root = two_chromiums(box)
    box.run("110", apply=True)
    res = box.rules()["playwright-old"]
    assert isinstance(res["freed_fs_bytes"], int) and res["unlinked_bytes"] == 10
    assert isinstance(box.rules()["uv-prune"]["freed_fs_bytes"], int)
    box.run("110", now=NOW + 99 * DAY)
    assert "freed_fs_bytes" not in box.rules()["uv-prune"]   # dry-run: nothing was done


def test_the_root_identity_check_alone_stops_a_replaced_root_that_holds_the_candidate_inode(box):
    root = pw_root(box)
    mk(root / "chromium-1243", 30)
    mk(root / "chromium-999", 30)
    links(box)
    box.lsof = box.fake_lsof(pre=nth(box, 1, f'mv "{root}" "{root}.old"; mkdir "{root}"; cp -R "{root}.old/.links" "{root}/.links"; '
                                            f'mv "{root}.old/chromium-999" "{root}/chromium-999"; mv "{root}.old/chromium-1243" "{root}/chromium-1243"'))
    r = box.run("110", apply=True)
    assert states(box) == [("chromium-999", "failed:root-changed")] and (root / "chromium-999" / "data.bin").exists()
    assert r.returncode == 10


def test_a_last_look_lsof_failure_is_journaled_failed_lsof_incomplete(box):
    root = two_chromiums(box)
    box.lsof = box.fake_lsof(pre=nth(box, 2, 'echo "lsof: WARNING: can\'t opendir" >&2'))
    box.run("110", apply=True)
    assert states(box) == [("chromium-1100", "failed:lsof-incomplete")] and (root / "chromium-1100").is_dir()
    assert not (root / "__dirlock").exists()


def test_enotempty_on_the_final_rmdir_reports_the_bytes_already_unlinked(tmp_path, monkeypatch):
    root, victim, rec, dev = plain_tree(tmp_path)
    real = pj.remove_children

    def then_a_newcomer(fd, w, depth=0):
        real(fd, w, depth)
        if depth == 0:
            (victim / "late.bin").write_bytes(b"x")   # lands after the walk, before the final rmdir
    monkeypatch.setattr(pj, "remove_children", then_a_newcomer)
    state, nbytes = candidate(root, rec, dev)
    assert state == "failed:enotempty" and nbytes == 10 + 10 + 10 and (victim / "late.bin").exists()


def test_the_tip_of_tree_headless_shell_family_is_an_allowlisted_family(box):
    root = pw_root(box)
    mk(root / "chromium_tip_of_tree_headless_shell-1243", 30)
    mk(root / "chromium_tip_of_tree_headless_shell-1100", 30)
    box.run("110", apply=True)
    assert not (root / "chromium_tip_of_tree_headless_shell-1100").exists() and (root / "chromium_tip_of_tree_headless_shell-1243").is_dir()


@pytest.mark.parametrize("now", ["1e300", "4000000001", "-1"])
def test_an_absurd_now_is_a_config_error_before_any_action(box, now):
    r = box.run("125", apply=True, PRO_JANITOR_NOW=now)
    assert r.returncode == 2 and box.calls() == [] and not box.journal.exists()


def test_a_child_that_cannot_be_reaped_after_the_kill_is_abandoned_not_waited_on(monkeypatch):
    holder = []

    class Stuck(subprocess.Popen):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            holder.append(self)

        def wait(self, timeout=None):
            if timeout == 5:   # the post-TERM and the post-KILL waits: the child sits in uninterruptible sleep
                raise subprocess.TimeoutExpired("x", 5)
            return super().wait(timeout)
    monkeypatch.setattr(pj.subprocess, "Popen", Stuck)
    t0 = time.monotonic()
    try:
        rc, status, _, _ = pj.run_deadline(["/bin/sh", "-c", "trap '' TERM; sleep 30"], 0.5, {"PATH": "/usr/bin:/bin"})
    finally:
        for p in holder:
            try:
                os.killpg(p.pid, 9)
            except OSError:
                pass   # already a zombie: macOS answers EPERM for a group with no live member
            subprocess.Popen.wait(p)
    assert status == "timeout-unreaped" and rc is None and time.monotonic() - t0 < 5


def test_an_unreaped_tool_is_journaled_as_error_timeout_unreaped(box, monkeypatch):
    monkeypatch.setattr(pj, "run_deadline", lambda *a, **k: (None, "timeout-unreaped", b"", b""))
    monkeypatch.setenv("PRO_JANITOR_HOME", str(box.home))
    monkeypatch.setenv("PRO_JANITOR_UV", str(box.uv))
    assert pj.tool_rule(pj.Env(), pj.RULES[0], True) == ("error:timeout-unreaped", [])


def test_wrapper_checks_the_kill_switch_file_and_reports_disabled(tmp_path):
    state = tmp_path / "whome" / ".local/state/nuzantara/pro-janitor"
    state.mkdir(parents=True)
    (state / "disabled").write_text("")
    _, hb, home = wrap(tmp_path, seq="100")
    assert hb["status"] == "disabled" and hb["note"] == "kill switch file"
    assert not (home / "logs" / "pro-janitor" / "journal.jsonl").exists()


def test_wrapper_appends_the_payload_raw_output_capped_to_run_log_only(tmp_path):
    wrap(tmp_path)
    home = tmp_path / "whome"
    (home / ".nuzantara-cron" / "pro_janitor.py").write_text(
        'import sys\nprint("Traceback secret-path /Users/x/y")\nprint("A" * 200000)\nprint("pro_janitor: tier=GREEN fine")\n')
    b = tmp_path / "wbin"
    subprocess.run(["/bin/bash", str(WRAPPER)], env={"HOME": str(home), "TMPDIR": str(tmp_path), "PATH": f"{b}:/usr/bin:/bin"},
                   capture_output=True, text=True, timeout=60)
    log = (home / "logs" / "pro-janitor" / "run.log").read_text()
    raw = (home / ".organism" / "last_seen" / "pro.janitor.json").read_text()
    assert "Traceback secret-path" in log and log.count("A") <= 64 * 1024 and "Traceback" not in raw and "/Users" not in raw


# ---------------------------------------------------------------- the last conformance pass

def test_the_installation_marker_goes_first_then_a_cap_leaves_a_half_deleted_revision(box):
    root = pw_root(box)
    mk(root / "chromium-1243", 30)
    mk(root / "chromium-998", 30, files=("INSTALLATION_COMPLETE", "0.bin", "1.bin", "2.bin", "3.bin"))   # the marker sorts after the digits
    box.run("110", apply=True, PRO_JANITOR_MAX_OBJECTS="2")
    left = sorted(p.name for p in (root / "chromium-998").iterdir())
    assert states(box) == [("chromium-998", "failed:capped")] and "INSTALLATION_COMPLETE" not in left and len(left) == 3


def test_the_installation_marker_is_the_first_object_unlinked(tmp_path, monkeypatch):
    root, victim, rec, dev = plain_tree(tmp_path)
    for n in ("INSTALLATION_COMPLETE", "0first.bin"):   # plain name order would put 0first.bin before the marker
        (victim / n).write_bytes(b"")
        os.utime(victim / n, (NOW - 30 * DAY,) * 2)
    order, real = [], os.unlink
    monkeypatch.setattr(os, "unlink", lambda path, *a, **k: (order.append(path), real(path, *a, **k))[1])
    got = candidate(root, rec, dev)
    assert got[0] == "removed" and order[0] == "INSTALLATION_COMPLETE" and len(order) == 5


def test_the_wrapper_maps_the_payload_exit_12_to_disabled(tmp_path):
    wrap(tmp_path)
    home = tmp_path / "whome"
    (home / ".nuzantara-cron" / "pro_janitor.py").write_text('print("pro_janitor: disabled by the kill switch")\nimport sys\nsys.exit(12)\n')
    b = tmp_path / "wbin"
    subprocess.run(["/bin/bash", str(WRAPPER)], env={"HOME": str(home), "TMPDIR": str(tmp_path), "PATH": f"{b}:/usr/bin:/bin"},
                   capture_output=True, text=True, timeout=60)
    hb = json.loads((home / ".organism" / "last_seen" / "pro.janitor.json").read_text())
    assert hb["status"] == "disabled" and hb["note"] == "kill switch"


def test_canary_names_are_unique_per_probe_and_a_live_pid_canary_blocks_nothing(box):
    root = two_chromiums(box)
    live = subprocess.Popen(["sleep", "30"])
    planted = root / f".pro-janitor-canary-{live.pid}-0123456789abcdef"
    planted.write_bytes(b"")
    seen = box.tmp / "canaries.rec"
    box.lsof = box.fake_lsof(pre=f'ls -A "$R" | grep "^[.]pro-janitor-canary-" >> "{seen}"')
    try:
        box.run("110", apply=True)
        box.run("110", apply=True, now=NOW + 99 * DAY)
    finally:
        live.kill()
        live.wait()
    import re as _re
    names = [n for n in seen.read_text().split() if str(live.pid) not in n]
    assert planted.exists() and box.rules()["playwright-old"]["status"] in ("done", "skipped:no-candidates")
    assert names and all(_re.fullmatch(r"\.pro-janitor-canary-\d+-[0-9a-f]{16}", n) for n in names) and len(set(names)) == len(names)
    assert not [p for p in root.iterdir() if p.name.startswith(".pro-janitor-canary-") and str(live.pid) not in p.name]


def test_a_directory_at_state_json_is_invalid_and_unwritable_it_warns_and_leaves_no_temp_file(box):
    box.state.mkdir()
    (box.state / "state.json").mkdir()
    r = box.run("125", apply=True)
    ln = box.last()
    assert r.returncode == 10 and ln["state_invalid"] is True and ln["state_unwritable"] is True and box.calls() == []
    assert sorted(os.listdir(box.state)) == ["lock", "state.json"] and (box.state / "state.json").is_dir()


def test_an_oversized_state_json_is_invalid_not_read(box):
    box.state.mkdir()
    (box.state / "state.json").write_text('{"tier":"GREEN","rules":{},"pad":"' + "x" * (1024 * 1024) + '"}')
    r = box.run("125", apply=True)
    assert r.returncode == 10 and box.last()["state_invalid"] is True and box.calls() == []
    assert json.loads((box.state / "state.json").read_text())["tier"] == "AMBER"


def test_a_directory_at_the_journal_path_exits_1_with_a_clean_note_and_no_traceback(box):
    box.journal.mkdir()
    r = box.run("125")
    assert r.returncode == 1 and r.stdout.strip() == "pro_janitor: journal unwritable" and "Traceback" not in r.stderr


def test_the_wrapper_reports_an_unwritable_journal_as_error_without_a_traceback(tmp_path):
    wrap(tmp_path)
    home = tmp_path / "whome"
    jp = home / "logs" / "pro-janitor" / "journal.jsonl"
    if jp.exists():
        jp.unlink()   # the first (priming) run wrote one
    jp.mkdir(parents=True)
    b = tmp_path / "wbin"
    subprocess.run(["/bin/bash", str(WRAPPER)], env={"HOME": str(home), "TMPDIR": str(tmp_path), "PATH": f"{b}:/usr/bin:/bin",
                                                     "PRO_JANITOR_FREE_GB_SEQ": "200"}, capture_output=True, text=True, timeout=60)
    raw = (home / ".organism" / "last_seen" / "pro.janitor.json").read_text()
    hb = json.loads(raw)
    assert hb["status"] == "error" and hb["note"] == "pro_janitor: journal unwritable" and "Traceback" not in raw


def test_the_name_must_still_be_the_directory_we_emptied_when_the_final_rmdir_comes(tmp_path, monkeypatch):
    root, victim, rec, dev = plain_tree(tmp_path)
    real = pj.remove_children

    def then_a_swap(fd, w, depth=0):
        real(fd, w, depth)
        if depth == 0:   # the emptied directory is moved away and an empty one of the same name takes its place
            os.rename(victim, tmp_path / "moved")
            os.mkdir(victim)
    monkeypatch.setattr(pj, "remove_children", then_a_swap)
    state, _ = candidate(root, rec, dev)
    assert state == "failed:changed" and victim.is_dir() and (tmp_path / "moved").is_dir()


def test_a_subdirectory_swapped_before_its_rmdir_is_left_in_place(tmp_path, monkeypatch):
    root, victim, rec, dev = plain_tree(tmp_path)
    real, done = pj.remove_children, []

    def then_a_swap(fd, w, depth=0):
        real(fd, w, depth)
        if depth == 1 and not done:
            done.append(1)
            os.rename(victim / "sub", tmp_path / "moved-sub")
            os.mkdir(victim / "sub")
    monkeypatch.setattr(pj, "remove_children", then_a_swap)
    state, _ = candidate(root, rec, dev)
    assert state == "failed:changed" and (victim / "sub").is_dir()


def test_candidates_found_open_at_plan_time_are_journaled_skipped_open(box):
    root = pw_root(box)
    mk(root / "chromium-1243", 30)
    mk(root / "chromium-998", 30)
    mk(root / "chromium-999", 30)
    box.lsof = box.fake_lsof(extra=f'echo "n{root}/chromium-998/data.bin"')
    box.run("110", apply=True)
    assert states(box) == [("chromium-998", "skipped:open"), ("chromium-999", "removed")] and (root / "chromium-998").is_dir()


def test_a_dry_run_also_lists_the_open_ones_as_skipped_open(box):
    root = pw_root(box)
    mk(root / "chromium-1243", 30)
    mk(root / "chromium-998", 30)
    box.lsof = box.fake_lsof(extra=f'echo "n{root}/chromium-998/data.bin"')
    box.run("110")
    assert box.rules()["playwright-old"]["status"] == "skipped:in-use" and states(box) == [("chromium-998", "skipped:open")]


def test_a_dirlock_older_than_an_hour_makes_the_run_exit_10(box):
    root = two_chromiums(box)
    (root / "__dirlock").mkdir()
    os.utime(root / "__dirlock", (NOW - 7200, NOW - 7200))
    r = box.run("110", apply=True)
    assert r.returncode == 10 and box.rules()["playwright-old"]["stale_dirlock"] is True


def test_each_rule_journals_its_own_freed_fs_bytes_apart_from_the_directory_rules_unlinked_bytes(box, monkeypatch):
    root = two_chromiums(box)
    links(box)
    for k, v in {"PRO_JANITOR_HOME": str(box.home), "PRO_JANITOR_STATE_DIR": str(box.state), "PRO_JANITOR_JOURNAL": str(box.journal),
                 "PRO_JANITOR_NOW": str(NOW), "PRO_JANITOR_UV": str(box.uv), "PRO_JANITOR_NPM": str(box.npm),
                 "PRO_JANITOR_LSOF": str(box.lsof), "PRO_JANITOR_FREE_GB_SEQ": "110", "PRO_JANITOR_APPLY": "true",
                 "PRO_JANITOR_TOOL_TIMEOUT": "20"}.items():
        monkeypatch.setenv(k, v)
    readings = iter([1000, 1500,   # uv-prune: before, after  (+500)
                     1500, 1500,   # npm-verify               (0)
                     1500, 1520])  # playwright-old           (+20)
    monkeypatch.setattr(pj.Env, "fs_free_bytes", lambda self: next(readings))
    assert pj.main() == 0
    rules = {r["id"]: r for r in box.lines()[-1]["rules"]}
    assert (rules["uv-prune"]["freed_fs_bytes"], rules["npm-verify"]["freed_fs_bytes"], rules["playwright-old"]["freed_fs_bytes"]) == (500, 0, 20)
    assert "unlinked_bytes" not in rules["uv-prune"] and rules["playwright-old"]["unlinked_bytes"] == 10


@pytest.mark.parametrize("name,nth_stat,left", [("sub", 3, ("sub",)), ("victim", 1, ())])
def test_a_stall_before_an_rmdir_is_refused_too(tmp_path, monkeypatch, name, nth_stat, left):
    clk, root, victim, rec, dev, rfd, lock = leased(tmp_path, ("o1", "o2"))
    real, seen = os.stat, []

    def stat_(path, *a, **k):
        if k.get("dir_fd") is not None and path == name:
            seen.append(1)
            if len(seen) == nth_stat:   # the stat that re-checks the name just before its rmdir
                clk.t += 9
        return real(path, *a, **k)
    monkeypatch.setattr(os, "stat", stat_)
    try:
        got = pj.remove_candidate(rfd, "victim", rec, dev, NOW, None, lock)
    finally:
        monkeypatch.undo()
        lock.release()
        os.close(rfd)
    assert got[0] == "failed:lock-stale" and victim.is_dir() and (victim / "sub").exists() == bool(left)
    assert not (victim / "sub" / "o1").exists() and (root / "__dirlock").is_dir()   # the lease ran out: left to go stale
