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

import errno
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
import threading
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
FAMILIES = ("chromium", "chromium_headless_shell", "chromium_tip_of_tree", "chromium_tip_of_tree_headless_shell", "firefox", "firefox_beta", "webkit", "ffmpeg",
            "winldd")
PW_RE = re.compile(r"(?P<family>[a-z_]+)-(?P<rev>[0-9]{1,12})", re.ASCII)
NAME_RE = re.compile(r"[a-z][a-z0-9-]*", re.ASCII)
DIGITS_RE = re.compile(r"[0-9]+", re.ASCII)
LINK_CAP = 64 * 1024
JSON_CAP = 1024 * 1024
LSOF_CAP = 16 * 1024 * 1024
LSOF_ERR_CAP = 64 * 1024
STATE_CAP = 1024 * 1024
MARKER = "INSTALLATION_COMPLETE"   # Playwright: marker present = revision installed


def mono():
    """The monotonic clock every timing decision reads: one place for a test to move time."""
    return time.monotonic()


def wall():
    """The wall clock Playwright judges the lock by: injectable beside mono()."""
    return time.time()


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
        if not (math.isfinite(self.now) and 0 <= self.now <= 4e9):
            raise ConfigError("PRO_JANITOR_NOW is not a finite timestamp in [0, 4e9]")
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
        try:   # invariant 6: the blast radius of one run, injectable for tests
            self.max_bytes = int(e.get("PRO_JANITOR_MAX_BYTES", str(10 * 10**9)))
            self.max_objects = int(e.get("PRO_JANITOR_MAX_OBJECTS", "200000"))
            self.lock_interval = float(e.get("PRO_JANITOR_LOCK_REFRESH", "2"))
        except ValueError:
            raise ConfigError("PRO_JANITOR_MAX_BYTES / _MAX_OBJECTS / _LOCK_REFRESH is not a number")
        if self.max_bytes < 0 or self.max_objects < 0 or not (0 <= self.lock_interval <= 2):
            raise ConfigError("PRO_JANITOR_MAX_BYTES / _MAX_OBJECTS / _LOCK_REFRESH out of range")
        self.used_bytes = 0
        self.used_objects = 0
        self.notes = {}   # extras a rule leaves for its journal entry

    def killed(self):
        """Invariant 7: the kill switch, from the environment or from a file the operator can create."""
        return os.environ.get("PRO_JANITOR_ENABLED") == "false" or os.path.lexists(os.path.join(self.state_dir, "disabled"))

    def fs_free_bytes(self):
        try:
            st = os.statvfs(self.df_path)
            return st.f_bavail * st.f_frsize
        except OSError:
            return None

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
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_size > STATE_CAP:
                return fresh, True   # a directory, a fifo, a huge file: invalid, not a crash
            raw = os.read(fd, STATE_CAP + 1)
        finally:
            os.close(fd)
        if len(raw) > STATE_CAP:
            return fresh, True
        s = json.loads(raw.decode("utf-8"))
        if not (isinstance(s, dict) and s.get("tier") in TIERS and isinstance(s.get("rules"), dict)):
            return fresh, True
        rules = {}
        for k, v in s["rules"].items():
            if not isinstance(k, str) or not is_num(v):
                return fresh, True
            if k in RULE_IDS and v <= env.now + 60:
                rules[k] = v
        return {"tier": s["tier"], "rules": rules}, False
    except (OSError, ValueError, RecursionError, OverflowError, UnicodeError):
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
    try:
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    dfd = os.open(sd, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def safe_journal(env, line):
    try:
        append_journal(env, line)
        return True
    except OSError:
        return False


def append_journal(env, line):
    os.makedirs(os.path.dirname(env.journal), exist_ok=True)
    with open(env.journal, "a") as f:
        f.write(json.dumps(line, sort_keys=True) + "\n")


# ---------------------------------------------------------------- subprocess with a real deadline

def group_gone(pgid):
    """True once no process of the group is left to signal. On macOS an un-reaped zombie leader alone answers EPERM, like ESRCH."""
    try:
        os.killpg(pgid, 0)
    except (ProcessLookupError, PermissionError):
        return True
    except OSError:
        return True
    return False


def run_deadline(argv, timeout, env, cap=None, err_cap=None):
    """-> (rc, status, stdout, stderr); status ok|timeout|timeout-unreaped|overflow|spawn. Stdout/stderr go to DEVNULL unless a cap asks for a
    pipe (lsof), read with the deadline and capped; stderr is only ever tested for emptiness, never journaled or printed.
    The child leads its own process group; on the deadline or an overflow: TERM the group, give the whole group 5 s, KILL the
    group, and only then reap the leader: its un-reaped zombie holds the pid and so the group id until the last killpg.
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
        pgid = p.pid   # no poll, wait or send_signal on p until after the last killpg
        try:
            os.killpg(pgid, signal.SIGTERM)
        except OSError:
            pass
        end = time.monotonic() + 5
        while not group_gone(pgid) and time.monotonic() < end:
            time.sleep(0.02)
        try:
            os.killpg(pgid, signal.SIGKILL)
        except OSError:
            pass
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            status = "timeout-unreaped"   # uninterruptible sleep: abandon the child rather than hang while holding the lock
    for f in (p.stdout, p.stderr):
        if f:
            f.close()
    out = b"".join(bufs.get("out", []))
    err = b"".join(bufs.get("err", []))
    return (p.returncode if status == "ok" else None), status, out, err


# ---------------------------------------------------------------- directory rules

def safe_realpath(path):
    """os.path.realpath, or None when it cannot resolve: a symlink chain deep enough to exhaust the stack, a link that vanished
    mid-resolution, a path the OS rejects. An input like that is a skip with a cause, never a crash."""
    try:
        return os.path.realpath(path)
    except (OSError, RecursionError, ValueError):
        return None


def real_root(env, rel):
    """The rule root, only if it is a real directory under HOME with no symlink in the way."""
    home_real = safe_realpath(env.home)
    root = os.path.join(env.home, rel)
    if home_real is None:
        return None
    try:
        if not os.path.isdir(root) or os.path.islink(root):
            return None
        if safe_realpath(root) != os.path.join(home_real, rel):
            return None
        return os.path.join(home_real, rel)
    except (OSError, ValueError):
        return None


def audit_tree(entry, root_dev, now):
    """(ok, reason, youngest_mtime, bytes). Walks without following symlinks. A path that cannot be resolved is reason
    "audit-error"."""
    entry_real = safe_realpath(entry)
    if entry_real is None:
        return False, "audit-error", 0, 0
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
            try:
                is_link = it.is_symlink()
                is_dir = not is_link and it.is_dir(follow_symlinks=False)
            except OSError:
                return False, "unreadable", 0, 0
            if is_link:
                tgt = safe_realpath(it.path)
                if tgt is None:
                    return False, "audit-error", 0, 0
                if tgt != entry_real and not tgt.startswith(entry_real + os.sep):
                    return False, "symlink-leaves", 0, 0
            elif is_dir:
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


def lsof_probe(env, root, root_id=None, rfd=None):
    """Open paths under root, or an error status. Measured on Pro (2026-10-10, lsof 4.91): with +D every file under the dir
    is a search target and any file that is not open makes lsof exit 1, so rc 1 is the normal healthy result; an incomplete
    scan shows on stderr, and only when -w is not given. The scan is complete iff rc is 0 or 1 AND the canary we hold open
    is in the output AND stderr is empty (stderr carries paths: it is tested, never kept). The canary has a name unique to
    this run and is created, stat'ed and unlinked through the anchored root fd, never by pathname."""
    own = rfd is None
    try:
        if own:
            rfd = open_anchored(root)
            st0 = os.fstat(rfd)
            if root_id is not None and (st0.st_dev, st0.st_ino) != root_id:
                os.close(rfd)
                return "error:lsof-incomplete", None
    except OSError:
        return "error:lsof-incomplete", None
    name = ".pro-janitor-canary-%d-%s" % (os.getpid(), os.urandom(8).hex())
    canary = os.path.join(root, name)
    try:
        try:
            fd = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600, dir_fd=rfd)
        except OSError:
            return "error:lsof-incomplete", None
        try:
            rc, st, out, err = run_deadline([env.lsof, "-F", "n", "+D", root], env.timeout, tool_env(env),
                                            cap=LSOF_CAP, err_cap=LSOF_ERR_CAP)
        finally:
            os.close(fd)
            try:
                os.unlink(name, dir_fd=rfd)
            except OSError:
                pass
    finally:
        if own:
            os.close(rfd)
    if st == "spawn":
        return "error:lsof-unreadable", None
    if st != "ok" or rc not in (0, 1) or err:
        return "error:lsof-incomplete", None
    opened = [ln[1:] for ln in out.decode("utf-8", "replace").splitlines() if ln.startswith("n")]
    if any(not o.startswith("/") for o in opened):   # e.g. "FD info error: ..." is a process lsof could not inspect
        return "error:lsof-incomplete", None
    if canary not in opened:
        return "error:lsof-incomplete", None
    real = [safe_realpath(o) for o in opened]
    if any(r is None for r in real):
        return "error:lsof-unreadable", None
    return None, real


DIRFLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
MAX_DEPTH = 64
CANARY_RE = re.compile(r"\.pro-janitor-canary-(?P<pid>[0-9]{1,7})-(?P<rnd>[0-9a-f]{16})", re.ASCII)


class Capped(Exception):
    pass


class LockLost(Exception):
    """The lock is no longer the inode we made."""


class LockStale(Exception):
    """We cannot prove the lock is still being kept alive (the keepalive died or starved): never assume it is held."""


class LockUncertain(Exception):
    """The identity stat after the mkdir was too slow to prove the directory is ours."""


class Stopped(Exception):
    """The kill switch was thrown while a candidate was being walked."""


def fd_supported():
    return (all(f in os.supports_dir_fd for f in (os.open, os.stat, os.unlink, os.rmdir, os.mkdir, os.utime))
            and os.scandir in os.supports_fd and os.stat in os.supports_follow_symlinks
            and os.utime in os.supports_follow_symlinks)


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
    """(ok, reason, youngest, bytes) of the tree under an open directory fd, walked fd-relative, symlinks never followed.
    `youngest` is the latest mtime OR ctime (a rename into the tree refreshes the moved object's ctime)."""
    if depth > MAX_DEPTH:
        return False, "too-deep", 0, 0
    st = os.fstat(fd)
    youngest = max(st.st_mtime, st.st_ctime)
    total = 0
    with os.scandir(fd) as it:
        names = [e.name for e in it]
    for n in names:
        if n.casefold() == ".git":
            return False, "has-git", 0, 0
        s = os.stat(n, dir_fd=fd, follow_symlinks=False)
        youngest = max(youngest, s.st_mtime, s.st_ctime)
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


class Lock(object):
    """Invariant 8: Playwright's own install lock, `<root>/__dirlock`, taken the way proper-lockfile takes it (an atomic
    mkdir) and held by a LEASE on the monotonic clock. take() reads t0 before the mkdir and, if the identity stat does not
    return within 4 s of t0, proves nothing (LockUncertain). The lease is `t0 + 8 s`; a keepalive thread, holding its own dup
    of the root fd, extends it to `t1 + 8 s` only after a fresh identity stat and a utime that returned before the lease ran
    out, and ends on anything else (including wall/monotonic drift: Playwright judges staleness by the wall clock). check()
    runs right before every unlink and rmdir: lease valid (else LockStale), inode ours (else LockLost). `_lease_until` is
    guarded by a threading.Lock, since the walk reads it while the thread writes it."""
    NAME = "__dirlock"
    LEASE = 8.0
    UNCERTAIN = 4.0
    DRIFT = 1.0
    JOIN_TIMEOUT = 5.0

    def __init__(self, root_fd, interval, mono_clock=None, wall_clock=None):
        self.fd, self.interval = root_fd, interval
        self.mono = mono_clock or (lambda: mono())
        self.wall = wall_clock or (lambda: wall())
        self.id, self.failed, self.stuck = None, False, False
        self._lease_until = 0.0
        self._mu = threading.Lock()
        self._stop = threading.Event()
        self._thread, self._tfd, self._prev = None, None, None

    def lease_until(self):
        with self._mu:
            return self._lease_until

    def take(self):
        t0 = self.mono()   # BEFORE the mkdir: our mkdir sets an mtime at or after t0
        w0 = self.wall()
        os.mkdir(self.NAME, 0o755, dir_fd=self.fd)   # FileExistsError: an installer holds it
        st = os.stat(self.NAME, dir_fd=self.fd, follow_symlinks=False)
        if self.mono() >= t0 + self.UNCERTAIN:
            raise LockUncertain()   # we cannot prove that directory is ours: record nothing, remove nothing
        self.id = (st.st_dev, st.st_ino)
        self._lease_until = t0 + self.LEASE
        self._prev = (t0, w0)   # the last (mono, wall) pair at which the lock was provably ours
        self._tfd = os.dup(self.fd)   # the thread's own descriptor; the thread closes it
        self._thread = threading.Thread(target=self._keepalive, name="pro-janitor-lock", daemon=True)
        try:
            self._thread.start()
        except BaseException:   # no keepalive: the lock just taken is released within its lease and the caller sees the failure
            os.close(self._tfd)
            self._tfd, self._thread = None, None
            self._rmdir_if_ours()
            self.id = None
            raise

    def _keepalive(self):
        step = self.interval if self.interval > 0 else 0.05
        try:
            while not self._stop.wait(step):
                if not self._refresh():
                    self.failed = True
                    return
        except BaseException:   # whatever it was: end the thread, the lease simply runs out
            self.failed = True
        finally:
            os.close(self._tfd)

    def _refresh(self):
        """One refresh; False ends the thread and the lease is no longer extended."""
        t1, w1 = self.mono(), self.wall()   # BEFORE the identity stat
        if self._drifted(t1, w1):
            return False
        st = os.stat(self.NAME, dir_fd=self._tfd, follow_symlinks=False)
        if not stat.S_ISDIR(st.st_mode) or (st.st_dev, st.st_ino) != self.id:
            return False
        os.utime(self.NAME, None, dir_fd=self._tfd, follow_symlinks=False)
        with self._mu:
            if self.mono() >= self._lease_until:   # the utime returned too late: an installer may already own the lock
                return False
            self._lease_until = t1 + self.LEASE
            self._prev = (t1, w1)
        return True

    def _drifted(self, t, w):
        """True if the wall clock moved more than DRIFT apart from the monotonic one since the last successful refresh (or the
        take): Playwright judges staleness by the wall clock, so a step of it can make the lock stale while the lease still reads valid."""
        with self._mu:
            pt, pw = self._prev
        return abs((w - pw) - (t - pt)) > self.DRIFT

    def _valid(self):
        return self.mono() < self.lease_until() and not self._drifted(self.mono(), self.wall())

    def _ours(self):
        try:
            st = os.stat(self.NAME, dir_fd=self.fd, follow_symlinks=False)
        except OSError:
            return False
        return stat.S_ISDIR(st.st_mode) and (st.st_dev, st.st_ino) == self.id

    def check(self):
        if self.id is None or not self._valid():
            raise LockStale()
        if not self._ours():
            raise LockLost()
        if not self._valid():   # the stat itself may have stalled
            raise LockStale()

    def release(self):
        self._stop.set()
        if self._thread is not None and self._thread.ident is not None:   # a thread that never started has nothing to join
            self._thread.join(timeout=self.JOIN_TIMEOUT)   # the root fd stays open until after this join (the caller closes it)
            if self._thread.is_alive():
                self.stuck = True
                return   # it holds its own fd; the lock is left to go stale
        self._rmdir_if_ours()

    def _rmdir_if_ours(self):
        if self.id is None or not self._valid() or not self._ours() or not self._valid():   # the same sequence as check()
            return   # not provably ours and fresh: leave it, Playwright judges it stale after 10 s
        try:
            os.rmdir(self.NAME, dir_fd=self.fd)
        except OSError:
            pass


class Walk(object):
    """State of one candidate's removal: the first failure cause, the bytes unlinked, the run's budget and the lock."""

    def __init__(self, root_dev, now, env=None, lock=None):
        self.root_dev, self.now, self.env, self.lock = root_dev, now, env, lock
        self.cause, self.bytes, self.failures = None, 0, 0
        self.last_kill = None

    def fail(self, cause):
        self.failures += 1
        if self.cause is None:
            self.cause = cause

    def tick(self):
        """Invariant 7: the kill switch is read at most once a second while a candidate is walked."""
        if self.env is None:
            return
        t = mono()
        if self.last_kill is None or t - self.last_kill >= 1.0:
            self.last_kill = t
            if self.env.killed():
                raise Stopped()

    def guard(self):
        """Right before an unlink or rmdir, after that object's own checks: the lock must provably still be ours."""
        if self.lock is not None:
            self.lock.check()

    def account(self, size):
        """Invariant 6: called before each unlink; raises Capped when the run's budget would be exceeded. The reservation is
        conservative (made before the syscall); `self.bytes` is not touched here, see done()."""
        e = self.env
        if e is not None:
            if e.used_objects + 1 > e.max_objects or e.used_bytes + size > e.max_bytes:
                raise Capped()
            e.used_objects += 1
            e.used_bytes += size

    def done(self, size):
        """Called only after the unlink or rmdir returned success: `bytes` counts what is really gone."""
        self.bytes += size


def cause_of(exc):
    if isinstance(exc, FileNotFoundError):
        return "vanished"
    if isinstance(exc, PermissionError):
        return "eperm"
    return "changed"


def remove_children(fd, w, depth=0):
    """Remove everything under the open directory fd, fd-relative. Invariant 2: each object is lstat'ed through the fd right
    before it is unlinked and left in place (the candidate fails `changed`) if it is a .git in any case, younger than 7 days by
    mtime or ctime, on another device, or a directory that is not the inode it was opened as. A symlink is unlinked itself,
    never its target. Directories are checked when reached, before their children are touched (our own unlinks refresh their
    times), and again by name right before their rmdir. Invariant 9: INSTALLATION_COMPLETE goes first. Invariant 8: the lock is
    verified right before every unlink and rmdir. EPERM/EACCES is a skip with its cause."""
    if depth > MAX_DEPTH:
        w.fail("changed")
        return
    with os.scandir(fd) as it:
        names = sorted(e.name for e in it)
    if depth == 0:
        names.sort(key=lambda n: n != MARKER)   # stable: the marker first, so a partial removal never looks installed
    marker_first = depth == 0 and bool(names) and names[0] == MARKER
    for n in names:
        if marker_first and w.failures:
            return   # invariant 9: with the marker present, ANY top-level failure so far (not only the marker's own) stops the walk: conservative
        w.tick()
        try:
            s = os.stat(n, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            continue   # already gone: nothing to remove
        except OSError as exc:
            w.fail(cause_of(exc))
            continue
        if n.casefold() == ".git" or w.now - max(s.st_mtime, s.st_ctime) <= SEVEN_DAYS or s.st_dev != w.root_dev:
            w.fail("changed")
            continue
        try:
            if stat.S_ISDIR(s.st_mode):
                cfd = os.open(n, DIRFLAGS, dir_fd=fd)
                try:
                    c = os.fstat(cfd)
                    if (c.st_dev, c.st_ino) != (s.st_dev, s.st_ino):
                        w.fail("changed")
                        continue
                    before = w.failures
                    remove_children(cfd, w, depth + 1)
                finally:
                    os.close(cfd)
                if w.failures != before:
                    continue
                s2 = os.stat(n, dir_fd=fd, follow_symlinks=False)   # the name must still be the directory we emptied
                if (s2.st_dev, s2.st_ino) != (c.st_dev, c.st_ino):
                    w.fail("changed")
                    continue
                w.account(0)
                w.guard()
                os.rmdir(n, dir_fd=fd)
                w.done(0)
            else:
                w.account(s.st_size)
                w.guard()
                os.unlink(n, dir_fd=fd)
                w.done(s.st_size)
        except FileNotFoundError:
            continue
        except OSError as exc:
            w.fail("enotempty" if exc.errno == errno.ENOTEMPTY else cause_of(exc))


def remove_candidate(root_fd, name, rec, root_dev, now, env=None, lock=None):
    """(state, bytes_unlinked); state is "removed" or "failed:<cause>". The candidate is opened relative to the verified root
    fd and must be the very inode recorded at plan time, on the root's device; it is audited and emptied through that fd and
    removed with rmdir(dir_fd): no pathname is resolved after the plan."""
    w = Walk(root_dev, now, env, lock)
    try:
        cfd = os.open(name, DIRFLAGS, dir_fd=root_fd)
    except OSError as exc:
        return "failed:" + cause_of(exc), 0
    try:
        st = os.fstat(cfd)
        if (st.st_dev, st.st_ino) != rec or st.st_dev != root_dev:
            return "failed:changed", 0
        ok, why, youngest, size = audit_fd(cfd, root_dev)
        if not ok or now - youngest <= SEVEN_DAYS:
            return "failed:changed", 0
        remove_children(cfd, w)
        if w.cause:
            return "failed:" + w.cause, w.bytes
        w.tick()
        s2 = os.stat(name, dir_fd=root_fd, follow_symlinks=False)   # the name must still be the directory we emptied
        if (s2.st_dev, s2.st_ino) != (st.st_dev, st.st_ino):
            return "failed:changed", w.bytes
        w.account(0)
        w.guard()
        os.rmdir(name, dir_fd=root_fd)
        w.done(0)
        return "removed", w.bytes
    except Capped:
        return "failed:capped", w.bytes
    except LockLost:
        return "failed:lock-lost", w.bytes
    except LockStale:
        return "failed:lock-stale", w.bytes
    except Stopped:
        return "failed:stopped", w.bytes
    except OSError as exc:
        return "failed:" + ("enotempty" if exc.errno == errno.ENOTEMPTY else cause_of(exc)), w.bytes
    finally:
        os.close(cfd)


def sweep_stale_canaries(root_fd):
    """Remove our own leftover canaries, through the anchored root fd: regular, zero-byte, exactly
    .pro-janitor-canary-<pid>-<16 hex>, with a pid that is gone. `kill(pid, 0)` only asks; nothing is ever signalled. A
    canary whose pid is alive is left; names are unique per run, so a stale one can never block a later run."""
    try:
        with os.scandir(root_fd) as it:
            names = [e.name for e in it]
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
        except (OverflowError, ValueError):
            continue
        except OSError:
            continue   # EPERM: alive, someone else's
        try:
            st = os.stat(n, dir_fd=root_fd, follow_symlinks=False)
            if stat.S_ISREG(st.st_mode) and st.st_size == 0:
                os.unlink(n, dir_fd=root_fd)
        except OSError:
            pass


def dirlock_present(env, root):
    """True if the install lock exists; notes `stale_dirlock` when it is older than an hour (we still skip)."""
    p = os.path.join(root, Lock.NAME)
    if not os.path.lexists(p):
        return False
    try:
        if env.now - os.lstat(p).st_mtime > 3600:
            env.notes["stale_dirlock"] = True
    except OSError:
        pass
    return True


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
        try:
            sfd = open_anchored(root)
            try:
                st0 = os.fstat(sfd)
                if (st0.st_dev, st0.st_ino) == root_id:
                    sweep_stale_canaries(sfd)
            finally:
                os.close(sfd)
        except OSError:
            pass
    if dirlock_present(env, root):
        return "skipped:install-in-progress", []
    try:
        pins = pinned_revisions(root)
    except LinksUnreadable:
        return "skipped:link-registry-unreadable", []
    cands = []
    unauditable = []   # candidates whose audit could not resolve a path: ineligible, and journaled with the cause
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
            if why == "audit-error":
                unauditable.append({"name": name, "bytes": 0, "state": "skipped:audit-error"})
                continue
            if not ok or env.now - youngest <= SEVEN_DAYS:
                continue
            cands.append((name, path, size, (ls.st_dev, ls.st_ino)))
    if not cands:
        return "skipped:no-candidates", unauditable
    bad, opened = lsof_probe(env, root, root_id)   # the plan's probe
    if bad:
        return bad, unauditable
    is_open = [any(o == c[1] or o.startswith(c[1] + os.sep) for o in opened) for c in cands]
    if all(is_open):
        return "skipped:in-use", [{"name": c[0], "bytes": 0, "state": "skipped:open"} for c in cands] + unauditable
    if not apply_:   # dry-run never takes the lock
        return "dry-run", [({"name": c[0], "bytes": 0, "state": "skipped:open"} if o else {"name": c[0], "bytes": c[2]})
                           for c, o in zip(cands, is_open)] + unauditable
    # the registry and the install lock are read again at the last moment: an install may have started since
    if dirlock_present(env, root):
        return "skipped:install-in-progress", unauditable
    try:
        if pinned_revisions(root) != pins:
            return "skipped:registry-changed", unauditable
    except LinksUnreadable:
        return "skipped:link-registry-unreadable", unauditable
    entries = []
    internal = False
    for (name, path, _, rec), was_open in zip(cands, is_open):
        if was_open:
            entries.append({"name": name, "bytes": 0, "state": "skipped:open"})
            continue
        if env.killed():   # invariant 7: a stop takes effect before the next candidate
            env.notes["stopped"] = "kill-switch"
            break
        if env.used_objects >= env.max_objects or env.used_bytes >= env.max_bytes:
            env.notes["capped"] = True
            break
        ent = {"name": name, "bytes": 0, "state": "failed:changed"}
        entries.append(ent)
        rfd, lock = None, None
        try:
            rfd = open_anchored(root)
            st = os.fstat(rfd)
            if (st.st_dev, st.st_ino) != root_id:
                ent["state"] = "failed:root-changed"
                continue
            lock = Lock(rfd, env.lock_interval)   # its keepalive thread starts in take()
            try:
                lock.take()   # invariant 8: Playwright waits for us; if it already holds the lock, we skip
            except FileExistsError:
                lock = None
                ent["state"] = "skipped:install-in-progress"
                dirlock_present(env, root)
                continue
            except LockUncertain:
                lock = None
                ent["state"] = "skipped:lock-uncertain"
                break   # stops the rule; the finally closes the root fd
            # per candidate, the last look, under the lock: lsof again, then the pins
            bad, opened2 = lsof_probe(env, root, root_id, rfd)
            if bad:
                ent["state"] = "failed:lsof-incomplete"
                continue
            if any(o == path or o.startswith(path + os.sep) for o in opened2):
                ent["state"] = "skipped:open"
                continue
            m = PW_RE.fullmatch(name)
            if (m.group("family"), int(m.group("rev"))) in pinned_revisions(root):
                ent["state"] = "skipped:pinned-late"
                continue
            ent["state"], ent["bytes"] = remove_candidate(rfd, name, rec, root_dev, env.now, env, lock)
        except LinksUnreadable:
            ent["state"] = "failed:changed"
        except OSError as exc:
            ent["state"] = "failed:" + ("root-changed" if not isinstance(exc, (FileNotFoundError, PermissionError))
                                        else cause_of(exc))
        except Exception:   # never BaseException; no traceback, no path: this candidate ends and the loop stops, what was decided stays journaled
            ent["state"] = "failed:internal"
            internal = True
        finally:
            if lock is not None:
                lock.release()
                if lock.stuck:
                    env.notes["lock_thread_stuck"] = True
            if rfd is not None:
                os.close(rfd)
        if internal:
            break
        if ent["state"] == "failed:capped":
            env.notes["capped"] = True
            break
        if ent["state"] == "failed:stopped":
            env.notes["stopped"] = "kill-switch"
            break
        if env.notes.get("lock_thread_stuck"):
            break   # invariant 8: a keepalive that outlived its join ends the rule
    env.notes["unlinked_bytes"] = sum(e["bytes"] for e in entries)
    if internal:
        return ("error:rmtree-partial" if any(e["state"] == "removed" for e in entries) else "error:internal"), entries + unauditable
    if any(e["state"].startswith("failed") for e in entries):
        return "error:rmtree-partial", entries + unauditable
    if any(e["state"] == "removed" for e in entries):
        return "done", entries + unauditable
    if entries:
        return ("skipped:in-use" if all(e["state"] == "skipped:open" for e in entries) else entries[0]["state"]), entries + unauditable
    return "skipped:kill-switch" if env.notes.get("stopped") else "skipped:capped", unauditable


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
    if st == "timeout-unreaped":
        return "error:timeout-unreaped", []
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
    if env.killed():   # invariant 7, at the start: no action, one journal line
        if not safe_journal(env, {"ts": iso(env.now), "disabled": True}):
            print("pro_janitor: journal unwritable")
            return 1
        print("pro_janitor: disabled by the kill switch")
        return 12
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
        fs0 = env.fs_free_bytes() if apply_ else None
        try:
            if rule["kind"] == "tool":
                status, entries = tool_rule(env, rule, apply_)
            else:
                status, entries = dir_rule(env, rule, apply_)
        except Exception:   # last resort: one rule's unexpected failure is its own error:internal (no traceback, no path), the others still run
            status, entries = "error:internal", []
        res = {"id": rule["id"], "status": status}
        if entries or rule["kind"] == "dir":
            res["entries"] = entries
        res.update(env.notes)
        env.notes.clear()
        attempted = apply_ and (status == "done" or status.startswith("error:rc=") or status in
                                ("error:timeout", "error:timeout-unreaped", "error:rmtree-partial", "error:internal"))
        results.append(res)
        if attempted:
            state["rules"][rule["id"]] = env.now
            try:
                after = env.free_gb()
            except OSError:
                free_failed = True   # no reading, no further action: stop here and say so
                break
            res["delta_gb"] = round(after - free, 3)
            fs1 = env.fs_free_bytes()
            if fs0 is not None and fs1 is not None:
                res["freed_fs_bytes"] = fs1 - fs0   # the filesystem's word: APFS snapshots can hold unlinked blocks
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
    unwritable = False
    try:
        save_state(env, state)
    except OSError:
        unwritable = True   # a directory in place of state.json, a failed rename: say so, exit 10
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
    if unwritable:
        line["state_unwritable"] = True
    if not safe_journal(env, line):
        print("pro_janitor: journal unwritable")
        return 1
    errs = [r for r in results if r["status"].startswith("error")]
    page = ""
    if tier == "BLACK":   # the page: free GB (above), freed GB (the df delta), and whose trough this is; printable ASCII, so the wrapper copies it
        page = " freed=%s the VM-side trough is localci's" % ("unknown" if free_failed else "%.1fGB" % (free - free0))
    print("pro_janitor: tier=%s mode=%s free=%.1fGB%s%s%s rules=%s" % (
        tier, line["mode"], free0, "" if free == free0 else "->%.1fGB" % free,
        (" state_invalid" if invalid else "") + (" free_read_failed" if free_failed else ""), page,
        ",".join("%s:%s" % (r["id"], r["status"]) for r in results) or "none"))
    stale = any(r.get("stale_dirlock") or r.get("lock_thread_stuck") for r in results)   # a lock older than an hour, or a keepalive that would not stop: the heartbeat must show it
    return 10 if (tier == "BLACK" or errs or invalid or free_failed or unwritable or stale) else 0


if __name__ == "__main__":
    sys.exit(main())
