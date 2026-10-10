#!/usr/bin/env python3
"""pro.janitor payload — a free-space keeper for Pro (docs/specs/pro-janitor-2026-10-10.md).

Run every 10 minutes by ~/scripts/pro-janitor.sh as `/usr/bin/python3 -I` (Python 3.9, stdlib only).
Reads free space on the Data volume, moves between tiers with hysteresis and runs ONLY the three allowlisted rules.
Nothing else is ever removed. Dry-run unless PRO_JANITOR_APPLY=true.

Exit codes (the wrapper maps them to the heartbeat): 0 ran clean; 10 warning (final tier BLACK, any rule error, an
invalid state.json that forced a dry-run, or a free-space read that failed after an action); 2 bad config; 1 state dir,
lock or free space unusable; 11 another run holds the lock.
"""
from __future__ import annotations

import fcntl
import json
import math
import os
import re
import select
import signal
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone

TIERS = ["GREEN", "AMBER", "RED", "BLACK"]
ENTER = {1: 130.0, 2: 115.0, 3: 105.0}   # a tier is entered when free falls under this mark
EXIT = {1: 140.0, 2: 125.0, 3: 112.0}    # and left only at or above this one
SEVEN_DAYS = 7 * 86400
H = 3600

TOOL_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
# id, tier index, cooldown seconds, kind; tools carry the cache dir (relative to HOME) they are pinned to
RULES = [
    {"id": "uv-prune", "tier": 1, "cooldown": 6 * H, "kind": "tool", "tool": "uv", "cache": ".cache/uv"},
    {"id": "npm-verify", "tier": 1, "cooldown": 24 * H, "kind": "tool", "tool": "npm", "cache": ".npm"},
    {"id": "playwright-old", "tier": 2, "cooldown": 24 * H, "kind": "dir", "root": "Library/Caches/ms-playwright"},
]
RULE_IDS = set(r["id"] for r in RULES)

# the Playwright browser families this organ knows; any other name in the root is never a candidate
FAMILIES = ("chromium", "chromium_headless_shell", "chromium_tip_of_tree", "firefox", "firefox_beta", "webkit", "ffmpeg",
            "winldd")
PW_RE = re.compile(r"(?P<family>[a-z_]+)-(?P<rev>[0-9]{1,12})", re.ASCII)
NAME_RE = re.compile(r"[a-z][a-z0-9-]*", re.ASCII)
DIGITS_RE = re.compile(r"[0-9]+", re.ASCII)
LINK_CAP = 64 * 1024
JSON_CAP = 1024 * 1024
LSOF_CAP = 16 * 1024 * 1024
LSOF_ERR_CAP = 64 * 1024


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
            self.timeout = float(e.get("PRO_JANITOR_TOOL_TIMEOUT", "300"))
        except ValueError:
            raise ConfigError("PRO_JANITOR_NOW / PRO_JANITOR_TOOL_TIMEOUT is not a number")
        if not math.isfinite(self.now):
            raise ConfigError("PRO_JANITOR_NOW is not finite")
        if not math.isfinite(self.timeout) or self.timeout <= 0:
            raise ConfigError("PRO_JANITOR_TOOL_TIMEOUT must be positive and finite")
        self.tools = {"uv": e.get("PRO_JANITOR_UV", "/opt/homebrew/bin/uv"),
                      "npm": e.get("PRO_JANITOR_NPM", "/opt/homebrew/bin/npm")}
        self.lsof = e.get("PRO_JANITOR_LSOF", "/usr/sbin/lsof")
        self.apply = e.get("PRO_JANITOR_APPLY", "").strip().lower() == "true"
        seq = e.get("PRO_JANITOR_FREE_GB_SEQ")   # test hook: the free-space readings in order, the last one repeats
        self.seq = None
        if seq:
            try:
                self.seq = [None if x.strip() == "ERR" else float(x) for x in seq.split(",")]   # ERR: a failed reading
            except ValueError:
                raise ConfigError("PRO_JANITOR_FREE_GB_SEQ is not a list of numbers")
            if not all(x is None or math.isfinite(x) for x in self.seq):
                raise ConfigError("PRO_JANITOR_FREE_GB_SEQ is not finite")
        self._i = 0

    def free_gb(self):
        if self.seq is not None:
            v = self.seq[min(self._i, len(self.seq) - 1)]
            self._i += 1
            if v is None:
                raise OSError("free space reading failed")
            return v
        st = os.statvfs(self.df_path)
        v = (st.f_bavail * st.f_frsize) / 1e9
        if not math.isfinite(v):
            raise OSError("free space is not finite")
        return v


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

def is_num(x):
    """A timestamp: a real finite number in [0, 4e9]. 10**400 (JSON ints are unbounded) must not raise out of here."""
    if not isinstance(x, (int, float)) or isinstance(x, bool):
        return False
    try:
        return math.isfinite(x) and 0 <= x <= 4e9
    except OverflowError:
        return False


def load_state(env):
    """(state, invalid). A missing file is a fresh GREEN state. An existing file that is not valid is `invalid`: the caller
    forces this tick to dry-run and the state is rewritten valid. Cooldown stamps in the future (> 60 s) are dropped."""
    fresh = {"tier": "GREEN", "rules": {}}
    path = os.path.join(env.state_dir, "state.json")
    if not os.path.lexists(path):
        return fresh, False
    try:
        with open(path) as f:
            s = json.load(f)
        if not (isinstance(s, dict) and s.get("tier") in TIERS and isinstance(s.get("rules"), dict)):
            return fresh, True
        rules = {}
        for k, v in s["rules"].items():
            if not isinstance(k, str) or not is_num(v):
                return fresh, True
            if k in RULE_IDS and v <= env.now + 60:
                rules[k] = v
        return {"tier": s["tier"], "rules": rules}, False
    except (OSError, ValueError, RecursionError, OverflowError):
        return fresh, True


class StateDirError(Exception):
    pass


def ensure_state_dir(env):
    """The state dir must be a real directory under HOME (no symlink anywhere on the way); it is created if missing."""
    sd = os.path.abspath(env.state_dir)
    rel = os.path.relpath(sd, env.home)
    if rel.startswith("..") or os.path.isabs(rel) or rel == ".":
        raise StateDirError("outside HOME")
    try:
        os.makedirs(sd, mode=0o700, exist_ok=True)
    except OSError:
        raise StateDirError("not creatable")
    if real_root(env, rel) is None:
        raise StateDirError("symlinked or not a directory")


def save_state(env, state):
    """Temp file created O_EXCL|O_NOFOLLOW under a random name (a planted symlink or file is never followed or reused),
    fsynced, renamed over state.json, then the directory is fsynced."""
    sd = env.state_dir
    path = os.path.join(sd, "state.json")
    tmp = os.path.join(sd, ".state.%s" % os.urandom(8).hex())
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        data = json.dumps(state, sort_keys=True).encode("utf-8")
        while data:
            data = data[os.write(fd, data):]
        os.fsync(fd)
    except BaseException:
        os.close(fd)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    os.close(fd)
    os.replace(tmp, path)
    dfd = os.open(sd, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def append_journal(env, line):
    os.makedirs(os.path.dirname(env.journal), exist_ok=True)
    with open(env.journal, "a") as f:
        f.write(json.dumps(line, sort_keys=True) + "\n")


# ---------------------------------------------------------------- subprocess with a real deadline

def run_deadline(argv, timeout, env, cap=None, err_cap=None):
    """-> (rc, status, stdout, stderr); status ok|timeout|overflow|spawn. Stdout/stderr go to DEVNULL unless a cap asks for a
    pipe (lsof), read with the deadline and capped; stderr is only ever tested for emptiness, never journaled or printed.
    The child leads its own process group; on the deadline or an overflow: TERM the group, wait 5 s, KILL the group, reap.
    A grandchild that left the group (setsid) is not ours to kill."""
    try:
        p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE if cap else subprocess.DEVNULL,
                             stderr=subprocess.PIPE if err_cap else subprocess.DEVNULL, start_new_session=True, env=env)
    except OSError:
        return None, "spawn", b"", b""
    deadline = time.monotonic() + timeout
    status = "ok"
    bufs = {}
    if cap or err_cap:
        open_fds = {}
        if cap:
            open_fds[p.stdout.fileno()] = ("out", cap)
        if err_cap:
            open_fds[p.stderr.fileno()] = ("err", err_cap)
        bufs = {"out": [], "err": []}
        sizes = {"out": 0, "err": 0}
        while open_fds and status == "ok":
            left = deadline - time.monotonic()
            if left <= 0:
                status = "timeout"
                break
            for fd in select.select(list(open_fds), [], [], min(left, 1.0))[0]:
                kind, limit = open_fds[fd]
                b = os.read(fd, 65536)
                if not b:
                    del open_fds[fd]
                    continue
                sizes[kind] += len(b)
                if sizes[kind] > limit:
                    status = "overflow"
                    break
                bufs[kind].append(b)
    if status == "ok":
        try:
            p.wait(timeout=max(deadline - time.monotonic(), 0.01))
        except subprocess.TimeoutExpired:
            status = "timeout"
    if status != "ok":
        try:
            os.killpg(p.pid, signal.SIGTERM)
        except OSError:
            pass
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            pass
        p.wait()
    for f in (p.stdout, p.stderr):
        if f:
            f.close()
    out = b"".join(bufs.get("out", []))
    err = b"".join(bufs.get("err", []))
    return (p.returncode if status == "ok" else None), status, out, err


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
            if it.name.casefold() == ".git":
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
    return st if stat.S_ISDIR(st.st_mode) else None


def families(root):
    """{family: [(rev, name, path)]} — real directories whose name is <allowlisted family>-<ASCII digits>."""
    fam = {}
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return fam
    for n in names:
        m = PW_RE.fullmatch(n)
        p = os.path.join(root, n)
        if m and m.group("family") in FAMILIES and lstat_dir(p) is not None:
            fam.setdefault(m.group("family"), []).append((int(m.group("rev")), n, p))
    return fam


class LinksUnreadable(Exception):
    pass


def read_regular(path, cap):
    """Bytes of a regular file of at most `cap` bytes, opened without following a symlink or blocking on a fifo."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > cap:
            raise LinksUnreadable("not a small regular file")
        data = b""
        while len(data) <= cap:
            b = os.read(fd, cap + 1 - len(data))
            if not b:
                break
            data += b
        if len(data) > cap:
            raise LinksUnreadable("too big")
        return data
    finally:
        os.close(fd)


def pinned_revisions(root):
    """Playwright's own registry: <root>/.links/* name package dirs whose browsers.json pins revisions. A link whose dir
    is gone (FileNotFoundError) is stale and pins nothing; an empty .links is no live install (Playwright's own GC view).
    Everything else that is not exactly well-formed raises LinksUnreadable: the caller fails closed."""
    links = os.path.join(root, ".links")
    if lstat_dir(links) is None:
        raise LinksUnreadable("no .links")
    pins = set()
    try:
        for n in sorted(os.listdir(links)):
            pkg = read_regular(os.path.join(links, n), LINK_CAP).decode("utf-8").strip()
            if not pkg or not os.path.isabs(pkg) or "\0" in pkg:
                raise LinksUnreadable("bad link")
            try:
                st = os.stat(pkg)
            except FileNotFoundError:
                continue
            if not stat.S_ISDIR(st.st_mode):
                raise LinksUnreadable("link target is not a directory")
            data = json.loads(read_regular(os.path.join(pkg, "browsers.json"), JSON_CAP).decode("utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("browsers"), list) or not data["browsers"]:
                raise LinksUnreadable("bad browsers.json")
            for b in data["browsers"]:
                if not isinstance(b, dict):
                    raise LinksUnreadable("bad browser")
                name, rev = b.get("name"), b.get("revision")
                if not (isinstance(name, str) and NAME_RE.fullmatch(name) and isinstance(rev, str)
                        and DIGITS_RE.fullmatch(rev)):
                    raise LinksUnreadable("bad browser")
                fam = name.replace("-", "_")
                pins.add((fam, int(rev)))   # numeric: "0123" and "123" are the same revision
                ov = b.get("revisionOverrides", {})
                if not isinstance(ov, dict):
                    raise LinksUnreadable("bad overrides")
                for k, v in ov.items():
                    if not (isinstance(k, str) and isinstance(v, str) and DIGITS_RE.fullmatch(v)):
                        raise LinksUnreadable("bad overrides")
                    pins.add((fam, int(v)))
    except (OSError, ValueError, UnicodeError, RecursionError):
        raise LinksUnreadable("unreadable")
    return pins


def lsof_probe(env, root):
    """Open paths under root, or an error status. Measured on Pro (2026-10-10, lsof 4.91): with +D every file under the dir
    is a search target and any file that is not open makes lsof exit 1, so rc 1 is the normal healthy result; an incomplete
    scan shows on stderr, and only when -w is not given. The scan is complete iff rc is 0 or 1 AND the canary we hold open
    is in the output AND stderr is empty (stderr carries paths: it is tested, never kept)."""
    canary = os.path.join(root, ".pro-janitor-canary-%d" % os.getpid())
    try:
        fd = os.open(canary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    except OSError:
        return "error:lsof-incomplete", None
    try:
        rc, st, out, err = run_deadline([env.lsof, "-F", "n", "+D", root], env.timeout, tool_env(env),
                                        cap=LSOF_CAP, err_cap=LSOF_ERR_CAP)
    finally:
        os.close(fd)
        try:
            os.unlink(canary)
        except OSError:
            pass
    if st == "spawn":
        return "error:lsof-unreadable", None
    if st != "ok" or rc not in (0, 1) or err:
        return "error:lsof-incomplete", None
    opened = [ln[1:] for ln in out.decode("utf-8", "replace").splitlines() if ln.startswith("n")]
    if canary not in opened:
        return "error:lsof-incomplete", None
    return None, [os.path.realpath(o) for o in opened]


DIRFLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
MAX_DEPTH = 64
CANARY_RE = re.compile(r"\.pro-janitor-canary-(?P<pid>[0-9]{1,10})", re.ASCII)


def fd_supported():
    return (all(f in os.supports_dir_fd for f in (os.open, os.stat, os.unlink, os.rmdir))
            and os.scandir in os.supports_fd and os.stat in os.supports_follow_symlinks)


def open_anchored(path):
    """Open an absolute directory by walking from "/" one component at a time with O_NOFOLLOW: no ancestor can be a symlink
    at open time, and nothing is resolved by pathname afterwards."""
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for comp in [c for c in path.split("/") if c]:
            nfd = os.open(comp, DIRFLAGS, dir_fd=fd)
            os.close(fd)
            fd = nfd
        return fd
    except BaseException:
        os.close(fd)
        raise


def audit_fd(fd, root_dev, depth=0):
    """(ok, reason, youngest_mtime, bytes) of the tree under an open directory fd, walked fd-relative, symlinks never followed."""
    if depth > MAX_DEPTH:
        return False, "too-deep", 0, 0
    youngest = os.fstat(fd).st_mtime
    total = 0
    with os.scandir(fd) as it:
        names = [e.name for e in it]
    for n in names:
        if n.casefold() == ".git":
            return False, "has-git", 0, 0
        s = os.stat(n, dir_fd=fd, follow_symlinks=False)
        youngest = max(youngest, s.st_mtime)
        total += s.st_size
        if stat.S_ISDIR(s.st_mode):
            if s.st_dev != root_dev:
                return False, "other-filesystem", 0, 0
            cfd = os.open(n, DIRFLAGS, dir_fd=fd)
            try:
                c = os.fstat(cfd)
                if (c.st_dev, c.st_ino) != (s.st_dev, s.st_ino):
                    return False, "changed", 0, 0
                ok, why, y, t = audit_fd(cfd, root_dev, depth + 1)
            finally:
                os.close(cfd)
            if not ok:
                return False, why, 0, 0
            youngest = max(youngest, y)
            total += t
    return True, "", youngest, total


def remove_children(fd, root_dev, depth=0):
    """Remove everything under the open directory fd, fd-relative. A symlink is unlinked itself, never its target; a
    directory on another device is never entered. Returns the number of failures (0 = all gone)."""
    if depth > MAX_DEPTH:
        return 1
    fails = 0
    with os.scandir(fd) as it:
        names = [e.name for e in it]
    for n in names:
        try:
            s = os.stat(n, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(s.st_mode):
                if s.st_dev != root_dev:
                    fails += 1
                    continue
                cfd = os.open(n, DIRFLAGS, dir_fd=fd)
                try:
                    c = os.fstat(cfd)
                    if (c.st_dev, c.st_ino) != (s.st_dev, s.st_ino):
                        fails += 1
                        continue
                    sub = remove_children(cfd, root_dev, depth + 1)
                finally:
                    os.close(cfd)
                if sub:
                    fails += sub
                    continue
                os.rmdir(n, dir_fd=fd)
            else:
                os.unlink(n, dir_fd=fd)
        except OSError:
            fails += 1
    return fails


def remove_candidate(root_fd, name, rec, root_dev, now):
    """(state, bytes). The candidate is opened relative to the verified root fd and must be the very inode recorded at plan
    time, on the root's device; it is audited and emptied through that fd and removed with rmdir(dir_fd): no pathname is
    resolved after the plan."""
    cfd = os.open(name, DIRFLAGS, dir_fd=root_fd)
    try:
        st = os.fstat(cfd)
        if (st.st_dev, st.st_ino) != rec or st.st_dev != root_dev:
            return "failed", 0
        ok, why, youngest, size = audit_fd(cfd, root_dev)
        if not ok or now - youngest <= SEVEN_DAYS:
            return "failed", 0
        if remove_children(cfd, root_dev):
            return "failed", 0
    finally:
        os.close(cfd)
    os.rmdir(name, dir_fd=root_fd)
    return "removed", size


def sweep_stale_canaries(root):
    """Remove our own leftover canaries: regular, zero-byte, exactly .pro-janitor-canary-<pid>, with a pid that is gone.
    `kill(pid, 0)` only asks; nothing is ever signalled."""
    try:
        names = os.listdir(root)
    except OSError:
        return
    for n in names:
        m = CANARY_RE.fullmatch(n)
        if not m or int(m.group("pid")) == os.getpid():
            continue
        try:
            os.kill(int(m.group("pid")), 0)
            continue   # alive
        except ProcessLookupError:
            pass
        except OSError:
            continue   # EPERM: alive, someone else's
        p = os.path.join(root, n)
        try:
            st = os.lstat(p)
            if stat.S_ISREG(st.st_mode) and st.st_size == 0:
                os.unlink(p)
        except OSError:
            pass


def dir_rule(env, rule, apply_):
    """Returns (status, entries). Entries are tool revision names + bytes only."""
    if not fd_supported():
        return "skipped:no-fd-support", []
    root = real_root(env, rule["root"])
    if root is None:
        return "skipped:root-missing-or-symlinked", []
    try:
        rst = os.lstat(root)
    except OSError:
        return "error:root-unreadable", []
    root_dev, root_id = rst.st_dev, (rst.st_dev, rst.st_ino)
    if apply_:
        sweep_stale_canaries(root)
    if os.path.lexists(os.path.join(root, "__dirlock")):
        return "skipped:install-in-progress", []
    try:
        pins = pinned_revisions(root)
    except LinksUnreadable:
        return "skipped:link-registry-unreadable", []
    cands = []
    for fam, items in sorted(families(root).items()):
        newest = max(k for k, _, _ in items)
        for k, name, path in sorted(items):
            if k == newest or (fam, k) in pins:
                continue
            try:
                ls = os.lstat(path)
            except OSError:
                continue
            ok, why, youngest, size = audit_tree(path, root_dev, env.now)
            if not ok or env.now - youngest <= SEVEN_DAYS:
                continue
            cands.append((name, path, size, (ls.st_dev, ls.st_ino)))
    if not cands:
        return "skipped:no-candidates", []
    bad, opened = lsof_probe(env, root)   # the plan's probe
    if bad:
        return bad, []
    free_cands = [c for c in cands if not any(o == c[1] or o.startswith(c[1] + os.sep) for o in opened)]
    if not free_cands:
        return "skipped:in-use", []
    if not apply_:
        return "dry-run", [{"name": n, "bytes": sz} for n, _, sz, _ in free_cands]
    # the registry and the install lock are read again at the last moment: an install may have started since
    if os.path.lexists(os.path.join(root, "__dirlock")):
        return "skipped:install-in-progress", []
    try:
        if pinned_revisions(root) != pins:
            return "skipped:registry-changed", []
    except LinksUnreadable:
        return "skipped:link-registry-unreadable", []
    entries = []
    for name, path, _, rec in free_cands:
        ent = {"name": name, "bytes": 0, "state": "failed"}
        entries.append(ent)
        try:
            # per candidate, the last look: lsof again, then the lock and the pins, then fd-anchored removal
            bad, opened2 = lsof_probe(env, root)
            if bad:
                continue
            if any(o == path or o.startswith(path + os.sep) for o in opened2):
                ent["state"] = "skipped:open"
                continue
            if os.path.lexists(os.path.join(root, "__dirlock")):
                ent["state"] = "skipped:install-in-progress"
                continue
            m = PW_RE.fullmatch(name)
            if (m.group("family"), int(m.group("rev"))) in pinned_revisions(root):
                ent["state"] = "skipped:pinned-late"
                continue
            rfd = open_anchored(root)
            try:
                st = os.fstat(rfd)
                if (st.st_dev, st.st_ino) != root_id:
                    continue
                ent["state"], ent["bytes"] = remove_candidate(rfd, name, rec, root_dev, env.now)
            finally:
                os.close(rfd)
        except (OSError, LinksUnreadable):
            pass
    if any(e["state"] == "failed" for e in entries):
        return "error:rmtree-partial", entries
    if any(e["state"] == "removed" for e in entries):
        return "done", entries
    return entries[0]["state"], entries


def tool_env(env):
    return {"HOME": env.home, "PATH": TOOL_PATH, "LANG": "C"}


def tool_rule(env, rule, apply_):
    cache = real_root(env, rule["cache"])
    if cache is None:
        return "skipped:root-missing-or-symlinked", []
    exe = env.tools[rule["tool"]]
    tenv = tool_env(env)
    if rule["tool"] == "uv":
        argv = [exe, "--no-config", "cache", "prune", "--cache-dir", cache]
    else:
        argv = [exe, "cache", "verify", "--cache", cache]
        tenv["npm_config_userconfig"] = "/dev/null"
        tenv["npm_config_globalconfig"] = "/dev/null"
    if not apply_:
        return "dry-run", []
    if not (os.path.isfile(exe) and os.access(exe, os.X_OK)):
        return "error:tool-missing", []
    rc, st, _, _ = run_deadline(argv, env.timeout, tenv)
    if st == "timeout":
        return "error:timeout", []
    if st != "ok":
        return "error:spawn", []
    if rc != 0:
        return "error:rc=%s" % rc, []
    return "done", []


# ---------------------------------------------------------------- main

def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    try:
        env = Env()
    except ConfigError as e:
        print("pro_janitor: bad config: %s" % e)
        return 2
    try:
        ensure_state_dir(env)
    except StateDirError as e:
        print("pro_janitor: state dir unusable: %s" % e)
        return 1
    try:
        lock = os.open(os.path.join(env.state_dir, "lock"), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("pro_janitor: previous run alive")
        return 11
    except OSError:
        print("pro_janitor: lock unusable")
        return 1
    try:
        state, invalid = load_state(env)
        free0 = env.free_gb()
    except OSError as e:
        print("pro_janitor: free space unreadable: %s" % e.__class__.__name__)
        return 1
    apply_ = env.apply and not invalid   # an invalid state.json forces this tick to dry-run
    prev = state["tier"]
    cur = next_tier(TIERS.index(prev), free0)
    seen = [TIERS[cur]]
    results = []
    free = free0
    stopped = False
    free_failed = False
    for rule in RULES:
        if cur < rule["tier"]:
            continue
        last = state["rules"].get(rule["id"])
        if is_num(last) and env.now - last < rule["cooldown"]:
            continue
        if rule["kind"] == "tool":
            status, entries = tool_rule(env, rule, apply_)
        else:
            status, entries = dir_rule(env, rule, apply_)
        res = {"id": rule["id"], "status": status}
        if entries or rule["kind"] == "dir":
            res["entries"] = entries
        attempted = apply_ and (status == "done" or status.startswith("error:rc=") or status in
                                ("error:timeout", "error:rmtree-partial"))
        results.append(res)
        if attempted:
            state["rules"][rule["id"]] = env.now
            try:
                after = env.free_gb()
            except OSError:
                free_failed = True   # no reading, no further action: stop here and say so
                break
            res["delta_gb"] = round(after - free, 3)
            free = after
            before = cur
            cur = next_tier(cur, free)   # the tier follows every reading: up when space collapses, down once it recovers
            if TIERS[cur] != seen[-1]:
                seen.append(TIERS[cur])
            if free >= EXIT[before]:
                stopped = True
                break
    tier = TIERS[cur]
    state["tier"] = tier
    save_state(env, state)
    line = {"ts": iso(env.now), "mode": "apply" if apply_ else "dry-run", "free_gb_before": round(free0, 3),
            "free_gb_after": None if free_failed else round(free, 3), "tier_prev": prev, "tier": tier, "rules": results}
    if tier != prev:
        line["transition"] = "%s->%s" % (prev, tier)
    if len(seen) > 1:
        line["tiers_seen"] = seen
    if stopped:
        line["stopped_at_exit_mark"] = True
    if invalid:
        line["state_invalid"] = True
    if free_failed:
        line["free_read_failed"] = True
    append_journal(env, line)
    errs = [r for r in results if r["status"].startswith("error")]
    print("pro_janitor: tier=%s mode=%s free=%.1fGB%s%s rules=%s" % (
        tier, line["mode"], free0, "" if free == free0 else "->%.1fGB" % free,
        (" state_invalid" if invalid else "") + (" free_read_failed" if free_failed else ""),
        ",".join("%s:%s" % (r["id"], r["status"]) for r in results) or "none"))
    return 10 if (tier == "BLACK" or errs or invalid or free_failed) else 0


if __name__ == "__main__":
    sys.exit(main())
