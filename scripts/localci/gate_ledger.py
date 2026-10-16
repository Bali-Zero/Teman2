"""B25-prime P1: the Pro ledger of gate verdicts (docs/specs/localci-sovereign-2026-10-07.md, section 2b.2).

`gate_verdict(path, repo, head)` is the one reader rule; `append`, `verify` and `quarantine` are the writer side. Run on Pro through the tick
wrapper's `gate-append` mode, so the writer and the reader are the code the tick runs. Stdlib only, no syntax newer than 3.9: M5's
/usr/bin/python3 may import it, Pro runs it.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import fcntl
import hashlib
import json
import os
import re
import stat
import sys
import time

DEFAULT_PATH = os.path.join("~", ".nuzantara-pilots", "local-ci-gate", "verdicts.jsonl")
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")
REPO_RE = re.compile(r"[A-Za-z0-9._-]{1,100}/[A-Za-z0-9._-]{1,100}")
TS_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
VIA_RE = re.compile(r"[0-9A-Za-z.:%_-]{1,64}")
KEYS = ("v", "ts", "repo", "pr", "head_sha", "verdict", "gate_session", "evidence_sha256", "supersedes", "via")
CLIENT_KEYS = ("repo", "pr", "head_sha", "verdict", "gate_session", "evidence_sha256", "supersedes")   # v, ts and via are the appender's
MAX_ENTRY_B64 = 4096


class LedgerFile(Exception):
    """The file itself is not trustworthy: missing, not a regular file, a symlink, group/other mode bits, another owner, unreadable."""


class LedgerMissing(LedgerFile):
    pass


class LedgerLine(Exception):
    def __init__(self, line: int, why: str):
        super().__init__(f"ledger unreadable at line {line}: {why}")
        self.line = line


def _pairs(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"duplicate key {k!r}")
        out[k] = v
    return out


def _const(name):
    raise ValueError(f"constant {name}")


def _loads(raw: bytes):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_const)
    except RecursionError as exc:
        raise ValueError("deeply nested JSON") from exc


def digest(line: bytes) -> str:
    return hashlib.sha256(line).hexdigest()


def _is_int(x) -> bool:
    return type(x) is int


def validate(e) -> "str | None":
    """The schema alone (2b.2): the reason an entry is not one, or None. A supersedes naming no line is valid."""
    if not isinstance(e, dict) or set(e) != set(KEYS):
        return "not an object with exactly the ten keys"
    ok = (e["v"] == 1 and _is_int(e["v"])
          and isinstance(e["ts"], str) and TS_RE.fullmatch(e["ts"])
          and isinstance(e["repo"], str) and REPO_RE.fullmatch(e["repo"])
          and (e["pr"] is None or (_is_int(e["pr"]) and e["pr"] > 0))
          and isinstance(e["head_sha"], str) and HEX40.fullmatch(e["head_sha"])
          and e["verdict"] in ("success", "failure") and isinstance(e["verdict"], str)
          and isinstance(e["gate_session"], str) and len(e["gate_session"]) <= 80
          and (e["evidence_sha256"] is None or (isinstance(e["evidence_sha256"], str) and HEX64.fullmatch(e["evidence_sha256"])))
          and (e["supersedes"] is None or (isinstance(e["supersedes"], str) and HEX64.fullmatch(e["supersedes"])))
          and isinstance(e["via"], str) and VIA_RE.fullmatch(e["via"]))
    return None if ok else "a field is out of its schema"


def _check_state(st) -> None:
    if not stat.S_ISREG(st.st_mode):
        raise LedgerFile("ledger is not a regular file")
    if st.st_mode & 0o077 or st.st_uid != os.geteuid():
        raise LedgerFile(f"ledger mode {stat.S_IMODE(st.st_mode):04o} or owner is not 0600 and the running user")


def _split(data: bytes):
    """The raw lines of the ledger; a tail without a newline is the last, torn, line."""
    lines = data.split(b"\n")
    if lines[-1] == b"":
        lines.pop()
    return lines, bool(data) and not data.endswith(b"\n")


def _parse(data: bytes):
    """-> [(digest, entry)]; raises LedgerLine at the first line that does not parse or validate."""
    lines, torn_tail = _split(data)
    out = []
    for n, raw in enumerate(lines, 1):
        if torn_tail and n == len(lines):
            raise LedgerLine(n, "no trailing newline")
        try:
            e = _loads(raw)
        except ValueError as exc:
            raise LedgerLine(n, f"does not parse ({str(exc)[:60]})")
        if (why := validate(e)) is not None:
            raise LedgerLine(n, why)
        out.append((digest(raw), e))
    return out


def read_entries(path: str):
    """lstat checks, then the file under LOCK_SH: -> [(digest, entry)] or raises LedgerFile / LedgerLine."""
    try:
        st = os.lstat(path)
        _check_state(st)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        raise LedgerMissing("ledger missing")
    except OSError as exc:
        raise LedgerFile(f"ledger unreadable: {exc.strerror}")
    try:
        fst = os.fstat(fd)
        if (fst.st_dev, fst.st_ino) != (st.st_dev, st.st_ino):
            raise LedgerFile("ledger replaced between lstat and open")
        fcntl.flock(fd, fcntl.LOCK_SH)
        with os.fdopen(os.dup(fd), "rb") as f:
            data = f.read()
    except OSError as exc:
        raise LedgerFile(f"ledger unreadable: {exc.strerror}")
    finally:
        os.close(fd)
    return _parse(data)


def _unsuperseded(mine):
    """The non-success entries of `mine` (file order) that no later entry of `mine` names."""
    return [d for i, (d, e) in enumerate(mine) if e["verdict"] != "success" and not any(l["supersedes"] == d for _, l in mine[i + 1:])]


def gate_verdict(path, repo, head):
    """The reader, one rule (2b.2): -> (ok, why). Never raises."""
    if not (isinstance(repo, str) and repo and isinstance(head, str) and HEX40.fullmatch(head)):
        return False, "bad argument"
    try:
        entries = read_entries(path)
    except LedgerMissing:
        return False, "ledger missing"
    except LedgerFile as exc:
        return False, str(exc)
    except LedgerLine as exc:
        return False, str(exc)
    mine = [(d, e) for d, e in entries if e["repo"] == repo and e["head_sha"] == head]
    if not mine:
        return False, "no entry for this head"
    if mine[-1][1]["verdict"] != "success":
        return False, "the newest entry for this head is not a success"
    for i, (d, e) in enumerate(mine[:-1]):
        if e["verdict"] != "success" and not any(l["supersedes"] == d for _, l in mine[i + 1:]):
            return False, f"entry {d[:12]} is a failure no later entry supersedes"
    return True, "ok"


def _client_entry(b64: str) -> dict:
    if not isinstance(b64, str) or not b64 or len(b64) > MAX_ENTRY_B64:
        raise ValueError("entry: empty or too long")
    try:
        obj = _loads(base64.b64decode(b64, validate=True))
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"entry: not base64 JSON ({str(exc)[:60]})")
    if not isinstance(obj, dict) or set(obj) != set(CLIENT_KEYS):
        raise ValueError(f"entry: keys must be exactly {', '.join(CLIENT_KEYS)} (v, ts and via are the appender's)")
    return obj


def _via() -> str:
    conn = os.environ.get("SSH_CONNECTION")
    if conn is None:
        return "local"
    parts = conn.split()
    if len(parts) != 4 or not VIA_RE.fullmatch(parts[0]):
        raise ValueError("SSH_CONNECTION is set and malformed: refusing to guess where the entry came from")
    return parts[0]


def _same(a: dict, b: dict) -> bool:
    return all(a[k] == b[k] for k in ("repo", "head_sha", "verdict", "evidence_sha256", "supersedes"))


def append(path: str, b64: str, supersede: bool = False, now: "float | None" = None) -> "list[str]":
    """Validate, stamp ts and via, and append under LOCK_EX with one write(); -> the digests, last one the entry's. Idempotent."""
    client = _client_entry(b64)
    via = _via()
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() if now is None else now))
    full = dict(v=1, ts=ts, via=via, **client)
    if (why := validate(dict((k, full[k]) for k in KEYS))) is not None:
        raise ValueError(f"entry: {why}")
    if supersede and client["supersedes"] is not None:
        raise ValueError("entry: --supersede and a supplied supersedes are exclusive")
    path = os.path.expanduser(path)
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        st, on_disk = os.fstat(fd), os.lstat(path)
        _check_state(st)
        if (st.st_dev, st.st_ino) != (on_disk.st_dev, on_disk.st_ino):
            raise OSError("ledger was replaced while waiting for the lock; retry")
        with os.fdopen(os.dup(fd), "rb") as f:
            data = f.read()
        if data and not data.endswith(b"\n"):
            raise OSError("ledger does not end with a newline: refusing to append to a torn tail (gate_ledger.py verify, quarantine)")
        have = []
        for raw in _split(data)[0]:
            try:
                e = _loads(raw)
            except ValueError:
                continue
            if validate(e) is None:
                have.append((digest(raw), e))
        mine = [(d, e) for d, e in have if e["repo"] == full["repo"] and e["head_sha"] == full["head_sha"]]
        todo = [full]
        if supersede and client["verdict"] == "success":
            todo = [dict(full, supersedes=d) for d in reversed(_unsuperseded(mine))]
        out = []
        for entry in todo or [full]:
            # a re-run changes nothing only while the head's NEWEST entry already says it (an older twin behind a later verdict would
            # leave the newer verdict in force); a --supersede with nothing left to name is satisfied by a newest success of the same evidence
            newest = mine[-1] if mine else None
            if newest is not None and (_same(newest[1], entry) or (not todo and newest[1]["verdict"] == entry["verdict"] == "success"
                                                                   and newest[1]["evidence_sha256"] == entry["evidence_sha256"])):
                out.append(newest[0])
                continue
            line = json.dumps(dict((k, entry[k]) for k in KEYS), separators=(",", ":")).encode("ascii")
            size = os.fstat(fd).st_size
            try:
                if os.write(fd, line + b"\n") != len(line) + 1:
                    raise OSError("short write")
                os.fsync(fd)
            except OSError:
                os.ftruncate(fd, size)
                raise
            have.append((digest(line), dict(entry)))
            mine.append(have[-1])
            out.append(digest(line))
        return out
    finally:
        os.close(fd)


def verify(path: str) -> "tuple[int, str]":
    path = os.path.expanduser(path)
    try:
        n = len(read_entries(path))
    except (LedgerFile, LedgerLine) as exc:
        return 1, str(exc)
    dmode = stat.S_IMODE(os.stat(os.path.dirname(path)).st_mode)
    if dmode & 0o077:
        return 1, f"directory mode {dmode:04o} has group or other bits"
    return 0, f"ok: {n} entries, file mode {stat.S_IMODE(os.lstat(path).st_mode):04o}, directory mode {dmode:04o}"


def quarantine(path: str, line_no: int, now: "float | None" = None) -> "tuple[int, str]":
    """Move ONE line that does not validate to verdicts.quarantine.jsonl, journalled; a line that validates is refused (else it is an override)."""
    path = os.path.expanduser(path)
    fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        qst, qdisk = os.fstat(fd), os.lstat(path)
        _check_state(qst)
        if (qst.st_dev, qst.st_ino) != (qdisk.st_dev, qdisk.st_ino):
            raise OSError("ledger was replaced while quarantine waited for the lock; retry")
        with os.fdopen(os.dup(fd), "rb") as f:
            data = f.read()
        lines, torn_tail = _split(data)
        if not 1 <= line_no <= len(lines):
            return 2, f"line {line_no} does not exist ({len(lines)} lines)"
        raw = lines[line_no - 1]
        try:
            valid = validate(_loads(raw)) is None and not (torn_tail and line_no == len(lines))
        except ValueError:
            valid = False
        if valid:
            return 2, f"line {line_no} validates: refusing to move a valid verdict"
        kept = [x for i, x in enumerate(lines, 1) if i != line_no]
        rest = b"\n".join(kept) + (b"\n" if kept else b"")
        if torn_tail and line_no != len(lines):
            rest = rest[:-1]   # the torn tail stays torn: another line's removal must not complete it into a verdict
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() if now is None else now))
        rec = json.dumps({"ts": ts, "line": line_no, "sha256": digest(raw), "raw_b64": base64.b64encode(raw).decode("ascii")}, separators=(",", ":"))
        qline = rec.encode("ascii") + b"\n"
        qfd = os.open(os.path.join(os.path.dirname(path), "verdicts.quarantine.jsonl"), os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        qsize = os.fstat(qfd).st_size
        try:
            if os.write(qfd, qline) != len(qline):
                raise OSError("short write on quarantine journal")
            os.fsync(qfd)
        except OSError:
            os.ftruncate(qfd, qsize)
            raise
        finally:
            os.close(qfd)
        tmp = f"{path}.tmp-{os.getpid()}"
        tfd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            if os.write(tfd, rest) != len(rest):
                raise OSError("short write on replacement ledger")
            os.fsync(tfd)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        finally:
            os.close(tfd)
        os.replace(tmp, path)
        return 0, f"line {line_no} moved to verdicts.quarantine.jsonl ({digest(raw)[:12]})"
    finally:
        os.close(fd)


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ledger", default=DEFAULT_PATH)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pa = sub.add_parser("append")
    pa.add_argument("entry_b64")
    pa.add_argument("--supersede", action="store_true")
    sub.add_parser("verify")
    pq = sub.add_parser("quarantine")
    pq.add_argument("--line", type=int, required=True)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "append":
            sys.stdout.write("\n".join(append(a.ledger, a.entry_b64, a.supersede)) + "\n")
            return 0
        rc, msg = verify(a.ledger) if a.cmd == "verify" else quarantine(a.ledger, a.line)
    except (ValueError, OSError, LedgerFile, LedgerLine) as exc:
        sys.stderr.write(f"gate_ledger {a.cmd}: {exc}\n")
        return 1
    (sys.stdout if rc == 0 else sys.stderr).write(msg + "\n")
    return rc


if __name__ == "__main__":
    sys.exit(main())
