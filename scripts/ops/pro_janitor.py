#!/usr/bin/env python3
"""pro.janitor payload — a free-space keeper for Pro (docs/specs/pro-janitor-2026-10-10.md).

Run every 10 minutes by ~/scripts/pro-janitor.sh as `/usr/bin/python3 -I` (Python 3.9, stdlib only).
Reads free space on the Data volume, moves between tiers with hysteresis and runs ONLY the four allowlisted rules.
Nothing else is ever removed. Dry-run unless PRO_JANITOR_APPLY=true.

Exit codes (the wrapper maps them to the heartbeat): 0 ran clean; 10 warning (BLACK tier or any rule error);
2 bad config; 1 free space unreadable.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

TIERS = ["GREEN", "AMBER", "RED", "BLACK"]
ENTER = {1: 130.0, 2: 115.0, 3: 105.0}   # a tier is entered when free falls under this mark
EXIT = {1: 140.0, 2: 125.0, 3: 112.0}    # and left only at or above this one
SEVEN_DAYS = 7 * 86400
H = 3600

# id, tier index, cooldown seconds, kind, argv-or-root
RULES = [
    {"id": "uv-prune", "tier": 1, "cooldown": 6 * H, "kind": "tool", "tool": "uv", "args": ["cache", "prune"]},
    {"id": "npm-verify", "tier": 1, "cooldown": 24 * H, "kind": "tool", "tool": "npm", "args": ["cache", "verify"]},
    {"id": "playwright-old", "tier": 2, "cooldown": 24 * H, "kind": "dir", "root": "Library/Caches/ms-playwright"},
    {"id": "uv-clean", "tier": 3, "cooldown": 6 * H, "kind": "tool", "tool": "uv", "args": ["cache", "clean"]},
]

PW_RE = re.compile(r"^(?P<family>[a-z_]+)-(?P<rev>\d+)$")


class ConfigError(Exception):
    pass


class Env(object):
    def __init__(self):
        e = os.environ
        self.home = e.get("PRO_JANITOR_HOME") or os.path.expanduser("~")
        if not os.path.isabs(self.home) or not os.path.isdir(self.home):
            raise ConfigError("PRO_JANITOR_HOME is not an absolute directory")
        self.df_path = e.get("PRO_JANITOR_DF_PATH", "/System/Volumes/Data")
        self.state_dir = e.get("PRO_JANITOR_STATE_DIR") or os.path.join(self.home, ".local/state/nuzantara/pro-janitor")
        self.journal = e.get("PRO_JANITOR_JOURNAL") or os.path.join(self.home, "logs/pro-janitor/journal.jsonl")
        try:
            self.now = float(e["PRO_JANITOR_NOW"]) if e.get("PRO_JANITOR_NOW") else time.time()
            self.timeout = float(e.get("PRO_JANITOR_TOOL_TIMEOUT", "600"))
        except ValueError:
            raise ConfigError("PRO_JANITOR_NOW / PRO_JANITOR_TOOL_TIMEOUT is not a number")
        if self.timeout <= 0:
            raise ConfigError("PRO_JANITOR_TOOL_TIMEOUT must be positive")
        self.tools = {"uv": e.get("PRO_JANITOR_UV", "/opt/homebrew/bin/uv"),
                      "npm": e.get("PRO_JANITOR_NPM", "/opt/homebrew/bin/npm")}
        self.lsof = e.get("PRO_JANITOR_LSOF", "/usr/sbin/lsof")
        self.apply = e.get("PRO_JANITOR_APPLY", "").strip().lower() == "true"
        seq = e.get("PRO_JANITOR_FREE_GB_SEQ")   # test hook: the free-space readings in order, the last one repeats
        self.seq = None
        if seq:
            try:
                self.seq = [float(x) for x in seq.split(",")]
            except ValueError:
                raise ConfigError("PRO_JANITOR_FREE_GB_SEQ is not a list of numbers")
        self._i = 0

    def free_gb(self):
        if self.seq is not None:
            v = self.seq[min(self._i, len(self.seq) - 1)]
            self._i += 1
            return v
        st = os.statvfs(self.df_path)
        return (st.f_bavail * st.f_frsize) / 1e9


# ---------------------------------------------------------------- tiers

def implied_tier(free):
    t = 0
    for i in (1, 2, 3):
        if free < ENTER[i]:
            t = i
    return t


def next_tier(current, free):
    """Escalation is immediate; the way down passes each exit mark: a tier is left only at or above its own exit mark, one
    band at a time (RED at 132 GB is AMBER until 140), and never below what the reading implies."""
    while current > 0 and free >= EXIT[current]:
        current -= 1
    return max(current, implied_tier(free))


# ---------------------------------------------------------------- state / journal

def load_state(env):
    try:
        with open(os.path.join(env.state_dir, "state.json")) as f:
            s = json.load(f)
        if isinstance(s, dict) and s.get("tier") in TIERS and isinstance(s.get("rules"), dict):
            return s
    except (OSError, ValueError):
        pass
    return {"tier": "GREEN", "rules": {}}


def save_state(env, state):
    os.makedirs(env.state_dir, exist_ok=True)
    path = os.path.join(env.state_dir, "state.json")
    tmp = path + ".tmp.%d" % os.getpid()
    with open(tmp, "w") as f:
        json.dump(state, f, sort_keys=True)
    os.replace(tmp, path)


def append_journal(env, line):
    os.makedirs(os.path.dirname(env.journal), exist_ok=True)
    with open(env.journal, "a") as f:
        f.write(json.dumps(line, sort_keys=True) + "\n")


# ---------------------------------------------------------------- subprocess with a real deadline

def run_deadline(argv, timeout, env_extra):
    """Returns (rc, timed_out, stdout). The child leads its own process group; on the deadline: TERM, then KILL the group."""
    env = dict(os.environ)
    env.update(env_extra)
    try:
        p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             start_new_session=True, env=env)
    except OSError:
        return None, False, b""
    try:
        out, _ = p.communicate(timeout=timeout)
        return p.returncode, False, out
    except subprocess.TimeoutExpired:
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(p.pid, sig)
            except OSError:
                pass
            try:
                p.communicate(timeout=5)
                break
            except subprocess.TimeoutExpired:
                continue
        try:
            os.killpg(p.pid, signal.SIGKILL)   # stragglers that ignored TERM in the group
        except OSError:
            pass
        return None, True, b""


# ---------------------------------------------------------------- directory rules

def real_root(env, rel):
    """The rule root, only if it is a real directory under HOME with no symlink in the way."""
    home_real = os.path.realpath(env.home)
    root = os.path.join(env.home, rel)
    try:
        if not os.path.isdir(root) or os.path.islink(root):
            return None
        if os.path.realpath(root) != os.path.join(home_real, rel):
            return None
        return os.path.join(home_real, rel)
    except OSError:
        return None


def audit_tree(entry, root_dev, now):
    """(ok, reason, youngest_mtime, bytes). Walks without following symlinks."""
    entry_real = os.path.realpath(entry)
    youngest = 0.0
    total = 0
    stack = [entry]
    while stack:
        d = stack.pop()
        try:
            st = os.lstat(d)
            youngest = max(youngest, st.st_mtime)
            if st.st_dev != root_dev:
                return False, "other-filesystem", 0, 0
            with os.scandir(d) as it:
                items = list(it)
        except OSError:
            return False, "unreadable", 0, 0
        for it in items:
            if it.name == ".git":
                return False, "has-git", 0, 0
            try:
                s = it.stat(follow_symlinks=False)
            except OSError:
                return False, "unreadable", 0, 0
            youngest = max(youngest, s.st_mtime)
            total += s.st_size
            if it.is_symlink():
                tgt = os.path.realpath(it.path)
                if tgt != entry_real and not tgt.startswith(entry_real + os.sep):
                    return False, "symlink-leaves", 0, 0
            elif it.is_dir(follow_symlinks=False):
                stack.append(it.path)
    return True, "", youngest, total


def lstat_dir(path):
    try:
        st = os.lstat(path)
    except OSError:
        return None
    import stat as _s
    return st if _s.S_ISDIR(st.st_mode) else None


def families(root):
    """{family: [(rev, name, path)]} — only real directories matching the playwright pattern."""
    fam = {}
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return fam
    for n in names:
        m = PW_RE.match(n)
        p = os.path.join(root, n)
        if m and lstat_dir(p) is not None:
            fam.setdefault(m.group("family"), []).append((int(m.group("rev")), n, p))
    return fam


class LinksUnreadable(Exception):
    pass


def pinned_revisions(root):
    """Playwright's own registry: <root>/.links/* name package dirs whose browsers.json pin revisions.
    A stale link (its dir is gone) pins nothing. Anything unreadable or malformed raises: the caller fails closed."""
    links = os.path.join(root, ".links")
    if lstat_dir(links) is None:
        raise LinksUnreadable("no .links")
    pins = set()
    try:
        names = sorted(os.listdir(links))
        for n in names:
            with open(os.path.join(links, n)) as f:
                pkg = f.read().strip()
            if not pkg or not os.path.isdir(pkg):
                continue
            with open(os.path.join(pkg, "browsers.json")) as f:
                data = json.load(f)
            for b in data["browsers"]:
                name = b["name"].replace("-", "_")
                pins.add("%s-%s" % (name, b["revision"]))
                for v in (b.get("revisionOverrides") or {}).values():
                    pins.add("%s-%s" % (name, v))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise LinksUnreadable("unreadable")
    return pins


def dir_rule(env, rule, apply_):
    """Returns (status, entries). Entries are tool revision names + bytes only."""
    root = real_root(env, rule["root"])
    if root is None:
        return "skipped:root-missing-or-symlinked", []
    try:
        root_dev = os.lstat(root).st_dev
    except OSError:
        return "error:root-unreadable", []
    try:
        pins = pinned_revisions(root)
    except LinksUnreadable:
        return "skipped:link-registry-unreadable", []
    cands = []
    for fam, items in sorted(families(root).items()):
        newest = max(k for k, _, _ in items)
        for k, name, path in sorted(items):
            if k == newest or name in pins:
                continue
            ok, why, youngest, size = audit_tree(path, root_dev, env.now)
            if not ok:
                continue
            if env.now - youngest <= SEVEN_DAYS:
                continue
            cands.append((name, path, size))
    if not cands:
        return "skipped:no-candidates", []
    # one lsof probe per rule root; a probe that cannot be read skips the rule
    rc, to, out = run_deadline([env.lsof, "-w", "-F", "n", "+D", root], env.timeout, {})
    if to or rc is None or rc not in (0, 1) or (rc == 1 and out.strip()):
        return "error:lsof-unreadable", []
    opened = [ln[1:] for ln in out.decode("utf-8", "replace").splitlines() if ln.startswith("n")]
    free_cands = []
    for name, path, size in cands:
        if any(o == path or o.startswith(path + os.sep) for o in opened):
            continue
        free_cands.append((name, path, size))
    if not free_cands:
        return "skipped:in-use", []
    entries = [{"name": n, "bytes": s} for n, _, s in free_cands]
    if not apply_:
        return "dry-run", entries
    errors = []

    def onerr(func, p, exc):
        errors.append(1)

    removed = []
    for (name, path, size), ent in zip(free_cands, entries):
        # re-verify at the moment of removal: still a real directory, still directly under the root
        if lstat_dir(path) is None or os.path.islink(path) or os.path.realpath(path) != path:
            errors.append(1)
            continue
        shutil.rmtree(path, onerror=onerr)
        removed.append(ent)
    if errors:
        return "error:rmtree-failed", removed
    return "done", removed


def tool_rule(env, rule, apply_):
    exe = env.tools[rule["tool"]]
    argv = [exe] + rule["args"]
    if not apply_:
        return "dry-run", []
    if not (os.path.isfile(exe) and os.access(exe, os.X_OK)):
        return "error:tool-missing", []
    rc, to, _ = run_deadline(argv, env.timeout, {"HOME": env.home})
    if to:
        return "error:timeout", []
    if rc != 0:
        return "error:rc=%s" % rc, []
    return "done", []


# ---------------------------------------------------------------- main

def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    try:
        env = Env()
        state = load_state(env)
        free0 = env.free_gb()
    except ConfigError as e:
        print("pro_janitor: bad config: %s" % e)
        return 2
    except OSError as e:
        print("pro_janitor: free space unreadable: %s" % e.__class__.__name__)
        return 1
    prev = state["tier"]
    cur_i = next_tier(TIERS.index(prev), free0)
    tier = TIERS[cur_i]
    results = []
    free = free0
    stopped = False
    for rule in RULES:
        if cur_i < rule["tier"]:
            continue
        last = state["rules"].get(rule["id"])
        if isinstance(last, (int, float)) and env.now - last < rule["cooldown"]:
            continue
        if rule["kind"] == "tool":
            status, entries = tool_rule(env, rule, env.apply)
        else:
            status, entries = dir_rule(env, rule, env.apply)
        res = {"id": rule["id"], "status": status}
        if entries or rule["kind"] == "dir":
            res["entries"] = entries
        attempted = env.apply and (status == "done" or status.startswith("error:rc=") or status in
                                   ("error:timeout", "error:rmtree-failed"))
        if attempted:
            state["rules"][rule["id"]] = env.now
            after = env.free_gb()
            res["delta_gb"] = round(after - free, 3)
            free = after
        results.append(res)
        if attempted and free >= EXIT[cur_i]:
            stopped = True
            break
    state["tier"] = tier
    save_state(env, state)
    line = {"ts": iso(env.now), "mode": "apply" if env.apply else "dry-run", "free_gb_before": round(free0, 3),
            "free_gb_after": round(free, 3), "tier_prev": prev, "tier": tier, "rules": results}
    if tier != prev:
        line["transition"] = "%s->%s" % (prev, tier)
    if stopped:
        line["stopped_at_exit_mark"] = True
    append_journal(env, line)
    errs = [r for r in results if r["status"].startswith("error")]
    print("pro_janitor: tier=%s mode=%s free=%.1fGB%s rules=%s" % (
        tier, line["mode"], free0, "" if free == free0 else "->%.1fGB" % free,
        ",".join("%s:%s" % (r["id"], r["status"]) for r in results) or "none"))
    return 10 if (tier == "BLACK" or errs) else 0


if __name__ == "__main__":
    sys.exit(main())
