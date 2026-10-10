#!/usr/bin/env python3
"""zero_sync.py - one-way mirror of the canonical monorepo main into FastLabsNet/zero main.

Zero is a product-only, history-less export of canonical. This tool rebuilds zero's tree from
canonical's (keep paths minus cut paths, zero-owned paths overlaid, root package.json pruned,
root package-lock.json regenerated), and pushes ONE fast-forward commit when it differs.
All git work is plumbing against a bare partial-clone repo: no working tree is ever checked out.

Exit codes: 0 synced / no-op / already running, 1 unexpected error, 2 bad usage (equal URLs),
3 divergence refused (zero was changed directly), 4 push rejected (zero main moved).
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ORGAN_ID = "mini.zero_sync"
DEFAULT_CANONICAL = "https://github.com/Bali-Zero/Teman2.git"
DEFAULT_ZERO = "https://github.com/FastLabsNet/zero.git"
ZERO_OWNED_PREFIXES = (".github", ".slim")
ROOT_FILES = ("package.json", "package-lock.json")
TRAILER = "Zero-Sync-Canonical"
TRAILER_RE = re.compile(rf"^{TRAILER}: ([0-9a-f]{{40}})[ \t]*$", re.M)
DEEPEN_DEPTH = 200
NPM_TIMEOUT = 600
NET_TIMEOUT = 1800  # the first full zero fetch took ~10 min on M5; a hung fetch/push must still end the run, or it holds the lock and every later tick no-ops

EXIT_OK, EXIT_ERROR, EXIT_USAGE, EXIT_DIVERGED, EXIT_REJECTED = 0, 1, 2, 3, 4


class SyncError(Exception):
    """An expected, explainable failure (exit 1 unless a code is given)."""

    def __init__(self, msg: str, code: int = EXIT_ERROR):
        super().__init__(msg)
        self.code = code


def _load_heartbeat():
    root = Path(__file__).resolve().parents[2]
    lib = root / "scripts" / "lib"
    try:
        if str(lib) not in sys.path:
            sys.path.insert(0, str(lib))
        from heartbeat import organism_heartbeat  # type: ignore

        return organism_heartbeat
    except Exception:  # never let the reporter break the run
        return lambda *a, **k: False


class Repo:
    def __init__(self, git_dir: Path):
        self.git_dir = str(git_dir)

    def run(self, *args, input=None, env=None, check=True, raw=False, timeout=None):
        e = dict(os.environ)
        e["GIT_TERMINAL_PROMPT"] = "0"
        if env:
            e.update(env)
        try:
            p = subprocess.run(
                ["git", "--git-dir", self.git_dir, *args],
                input=input if isinstance(input, bytes) or input is None else input.encode(),
                capture_output=True,
                env=e,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise SyncError(f"git {args[0]} timed out after {timeout}s") from None
        if check and p.returncode != 0:
            tail = p.stderr.decode(errors="replace").strip()[-600:]
            raise SyncError(f"git {args[0]} failed (rc={p.returncode}): {tail}")
        if raw:
            return p
        out = p.stdout.decode(errors="replace")
        return out if not check else out.rstrip("\n")

    def ls_tree(self, ref: str, paths=None) -> dict[str, tuple[str, str]]:
        args = ["ls-tree", "-r", "-z", "--full-tree", ref]
        if paths:
            args += ["--", *paths]
        out = self.run(*args, raw=True).stdout.decode(errors="surrogateescape")
        res = {}
        for rec in out.split("\0"):
            if not rec:
                continue
            meta, path = rec.split("\t", 1)
            mode, _type, oid = meta.split(" ")
            res[path] = (mode, oid)
        return res

    def _blob(self, oid: str) -> bytes:
        p = self.run("cat-file", "blob", oid, raw=True)
        if p.returncode != 0:
            raise SyncError(f"cannot read blob {oid}: {p.stderr.decode(errors='replace')[-300:]}")
        return p.stdout

    def hash_blob(self, data: bytes) -> str:
        return self.run("hash-object", "-w", "--stdin", input=data)


def norm_url(u: str) -> str:
    u = u.strip().rstrip("/").lower()
    return u[:-4] if u.endswith(".git") else u


def read_manifest(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line.rstrip("/"))
    return out


def is_owned(path: str, local: list[str]) -> bool:
    for o in (*ZERO_OWNED_PREFIXES, *local):
        if path == o or path.startswith(o + "/"):
            return True
    return False


def prune_workspaces(text: str, exists) -> tuple[str, list[str]]:
    """Remove workspace entries whose <entry>/package.json is absent, editing the text in place
    so the rest of the file keeps its byte layout. Returns (new_text, kept_entries)."""
    data = json.loads(text)
    ws = data.get("workspaces")
    if ws is None:
        return text, []
    if not isinstance(ws, list):
        raise SyncError("root package.json workspaces is not a literal array")
    for w in ws:
        if not isinstance(w, str) or any(c in w for c in "*?[]{}!"):
            raise SyncError(f"workspace glob/odd entry not supported: {w!r}")
    kept = [w for w in ws if exists(posixpath.normpath(w))]
    m = re.search(r'("workspaces"\s*:\s*\[)(.*?)(\])', text, re.S)
    if not m:
        raise SyncError("cannot locate the workspaces array in package.json text")
    body = m.group(2)
    closing = re.search(r"\n([ \t]*)$", body)
    close_indent = closing.group(1) if closing else ""
    first = re.search(r"\n([ \t]*)\"", body)
    indent = first.group(1) if first else close_indent + "  "
    if kept:
        new_body = "\n" + ",\n".join(indent + json.dumps(w) for w in kept) + "\n" + close_indent
    else:
        new_body = ""
    return text[: m.start(2)] + new_body + text[m.end(2):], kept


def regen_lock(repo: Repo, state: Path, npm_cmd: str, pruned: bytes, lock_oid: str,
               ws_entries: dict[str, str]) -> bytes:
    """Regenerate package-lock.json (npm --package-lock-only), cached by input hash."""
    try:
        ver = subprocess.run([npm_cmd, "--version"], capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SyncError(f"npm unavailable: {exc}")
    if ver.returncode != 0:
        raise SyncError("npm --version failed")
    h = hashlib.sha256()
    h.update(ver.stdout.strip() + b"\0" + hashlib.sha256(pruned).digest() + lock_oid.encode())
    for p in sorted(ws_entries):
        h.update(b"\0" + p.encode() + b"=" + ws_entries[p].encode())
    cache = state / "lock_cache" / f"{h.hexdigest()}.json"
    if cache.is_file():
        return cache.read_bytes()
    with tempfile.TemporaryDirectory(prefix="zero-sync-lock-") as tmp:
        t = Path(tmp)
        (t / "package.json").write_bytes(pruned)
        (t / "package-lock.json").write_bytes(repo._blob(lock_oid))
        for p, oid in ws_entries.items():
            (t / p).parent.mkdir(parents=True, exist_ok=True)
            (t / p).write_bytes(repo._blob(oid))
        try:
            r = subprocess.run(
                [npm_cmd, "install", "--package-lock-only", "--ignore-scripts", "--no-audit", "--no-fund"],
                cwd=tmp, capture_output=True, timeout=NPM_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            raise SyncError(f"npm install timed out after {NPM_TIMEOUT}s")
        if r.returncode != 0:
            raise SyncError("npm lock regeneration failed: " + r.stderr.decode(errors="replace")[-400:])
        out = (t / "package-lock.json").read_bytes()
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmpc = cache.with_suffix(f".tmp{os.getpid()}")
    tmpc.write_bytes(out)
    os.replace(tmpc, cache)
    return out


def build_tree(repo: Repo, state: Path, canon_ref: str, zero_ref: str, npm_cmd: str):
    """Returns (tree_oid, entries dict)."""
    def manifest(name):
        p = repo.run("cat-file", "blob", f"{zero_ref}:.slim/{name}", raw=True)
        if p.returncode != 0:
            raise SyncError(f"zero has no .slim/{name}")
        return read_manifest(p.stdout.decode())

    keep, cut, local = manifest("keep_paths.txt"), manifest("cut_paths.txt"), manifest("local_paths.txt")
    canon = repo.ls_tree(canon_ref, [*keep, *ROOT_FILES])
    for k in keep:
        if not any(p == k or p.startswith(k + "/") for p in canon):
            raise SyncError(f"keep path absent from canonical: {k} (maintain .slim/keep_paths.txt)")
    entries = {p: v for p, v in canon.items() if p not in ROOT_FILES}
    entries = {p: v for p, v in entries.items()
               if not any(p == c or p.startswith(c + "/") for c in cut)}
    zero_all = repo.ls_tree(zero_ref)
    entries = {p: v for p, v in entries.items() if not is_owned(p, local)}
    for lp in local:
        if not any(p == lp or p.startswith(lp + "/") for p in zero_all):
            raise SyncError(f"local path listed but absent in zero: {lp}")
    for p, v in zero_all.items():
        if is_owned(p, local):
            entries[p] = v

    if "package.json" in canon:
        mode, oid = canon["package.json"]
        text = repo._blob(oid).decode()
        pruned_text, kept_ws = prune_workspaces(text, lambda w: f"{w}/package.json" in entries)
        pruned = pruned_text.encode()
        entries["package.json"] = (mode, repo.hash_blob(pruned))
        if "package-lock.json" in canon:
            lmode, loid = canon["package-lock.json"]
            ws = {f"{posixpath.normpath(w)}/package.json": entries[f"{posixpath.normpath(w)}/package.json"][1]
                  for w in kept_ws}
            lock = regen_lock(repo, state, npm_cmd, pruned, loid, ws)
            entries["package-lock.json"] = (lmode, repo.hash_blob(lock))

    idx = state / f"index.{os.getpid()}"
    env = {"GIT_INDEX_FILE": str(idx)}
    try:
        repo.run("read-tree", "--empty", env=env)
        blob = "".join(f"{m} {o}\t{p}\0" for p, (m, o) in sorted(entries.items()))
        repo.run("update-index", "-z", "--index-info", input=blob.encode(errors="surrogateescape"), env=env)
        tree = repo.run("write-tree", "--missing-ok", env=env)
    finally:
        idx.unlink(missing_ok=True)
    return tree, entries


def walk_unsynced(repo: Repo, zero_ref: str):
    """Non-sync commits on zero's first-parent chain newer than the last sync commit.
    Returns (commits, prev_canonical_sha or None, tip_is_sync). The root commit is the import
    baseline and is never counted as a direct change."""
    out = repo.run("log", "--first-parent", "--format=%H%x1f%P%x1f%B%x1e", zero_ref)
    commits, prev, tip_sync = [], None, False
    for i, rec in enumerate(r for r in out.split("\x1e") if r.strip()):
        sha, parents, body = rec.strip("\n").split("\x1f", 2)
        m = TRAILER_RE.search(body)
        if m:
            prev, tip_sync = m.group(1), i == 0
            break
        if parents.strip():
            commits.append((sha.strip(), parents.split()[0]))
    return commits, prev, tip_sync


def divergence(repo: Repo, zero_ref: str, built: dict, local: list[str]):
    zero = repo.ls_tree(zero_ref)
    commits, prev, tip_sync = walk_unsynced(repo, zero_ref)
    bad = []
    seen = set()
    for sha, parent in commits:
        out = repo.run("diff-tree", "-r", "--no-renames", "--name-only", "-z", parent, sha, raw=True)
        for p in out.stdout.decode(errors="surrogateescape").split("\0"):
            if not p or p in seen or is_owned(p, local):
                continue
            seen.add(p)
            if built.get(p) != zero.get(p):
                bad.append(p)
    return sorted(bad), prev, tip_sync


def prior_subjects(repo: Repo, prev: str | None, canon_sha: str, keep: list[str], canon_ref: str, remote_ref: str):
    short = canon_sha[:10]
    fallback = [f"- snapshot of canonical {short}"]
    if not prev:
        return fallback
    try:
        def reachable():
            return repo.run("merge-base", "--is-ancestor", prev, canon_sha, check=False, raw=True).returncode == 0

        if not reachable():
            # depth-1 left the tip as a shallow boundary: deepen (bounded) only to list subjects
            repo.run("fetch", "--no-tags", f"--depth={DEEPEN_DEPTH}", "--filter=blob:none", "canonical",
                     f"+{remote_ref}:{canon_ref}", check=False, timeout=NET_TIMEOUT)
            if not reachable():
                return fallback
        out = repo.run("log", "--format=%h %s", "-n", "50", f"{prev}..{canon_sha}", "--", *keep, check=False)
        lines = [f"- {l}" for l in out.splitlines() if l.strip()]
        return lines or ["- no canonical commit touched the perimeter (manifest or lockfile change)"]
    except SyncError:
        return fallback


def ci_red(zero_url: str, sha: str) -> bool:
    m = re.search(r"github\.com[:/]([^/]+/[^/.]+?)(?:\.git)?/?$", zero_url)
    if not m:
        return False
    try:
        r = subprocess.run(
            ["gh", "api", f"repos/{m.group(1)}/commits/{sha}/check-runs", "--jq",
             '[.check_runs[]|select(.status=="completed" and .conclusion=="failure")]|length'],
            capture_output=True, timeout=60)
        return r.returncode == 0 and int(r.stdout.strip() or 0) > 0
    except Exception:
        return False


def sync(a, hb) -> int:
    state = Path(a.state_dir).expanduser()
    state.mkdir(parents=True, exist_ok=True)
    repo = Repo(state / "repo.git")
    if not (state / "repo.git").exists():
        subprocess.run(["git", "init", "--bare", "-q", str(state / "repo.git")], check=True)
    repo.run("config", "remote.canonical.url", a.canonical_url)
    repo.run("config", "remote.canonical.promisor", "true")
    repo.run("config", "remote.canonical.partialclonefilter", "blob:none")
    canon_ref, zero_ref = "refs/canonical/main", "refs/zero/main"
    repo.run("fetch", "--no-tags", "--depth=1", "--filter=blob:none", "canonical",
             f"+{a.canonical_ref}:{canon_ref}", timeout=NET_TIMEOUT)
    repo.run("fetch", "--no-tags", a.zero_url, f"+refs/heads/main:{zero_ref}", timeout=NET_TIMEOUT)
    canon_sha = repo.run("rev-parse", f"{canon_ref}^{{commit}}")
    zero_tip = repo.run("rev-parse", f"{zero_ref}^{{commit}}")
    short = canon_sha[:10]

    red = False
    if not a.no_ci_check and TRAILER_RE.search(repo.run("show", "-s", "--format=%B", zero_tip)):
        red = ci_red(a.zero_url, zero_tip)
    ci_note = f"; zero CI red on {zero_tip[:10]}" if red else ""
    status_ok = "warning" if red else "ok"

    tree, entries = build_tree(repo, state, canon_ref, zero_ref, a.npm_cmd)
    if tree == repo.run("rev-parse", f"{zero_ref}^{{tree}}"):
        msg = f"zero-sync: up to date (canonical {short}){ci_note}"
        print(msg); hb(status_ok, f"up to date (canonical {short}){ci_note}")
        return EXIT_OK

    local = read_manifest(repo.run("cat-file", "blob", f"{zero_ref}:.slim/local_paths.txt"))
    keep = read_manifest(repo.run("cat-file", "blob", f"{zero_ref}:.slim/keep_paths.txt"))
    bad, prev, _ = divergence(repo, zero_ref, entries, local)
    names = repo.run("diff-tree", "-r", "--no-renames", "--name-only", zero_ref, tree, check=False)
    nfiles = len([l for l in names.splitlines() if l.strip()])

    if a.dry_run:
        print(repo.run("diff", "--stat", "--no-renames", zero_ref, tree, check=False))
        if bad:
            print(f"DIVERGENCE: would REFUSE, {len(bad)} path(s) changed directly on zero and not in canonical:")
            for p in bad[:10]:
                print(f"  {p}")
            return EXIT_DIVERGED
        print(f"DIVERGENCE: none; would sync canonical {short} ({nfiles} files changed)")
        return EXIT_OK

    if bad:
        note = f"divergence refused: {len(bad)} path(s) changed on zero: " + ", ".join(bad[:10])
        print("zero-sync: " + note); hb("error", note)
        return EXIT_DIVERGED

    subjects = prior_subjects(repo, prev, canon_sha, keep, canon_ref, a.canonical_ref)
    message = f"sync: canonical {short}\n\n" + "\n".join(subjects) + f"\n{nfiles} files changed\n\n{TRAILER}: {canon_sha}\n"
    email = subprocess.run(["git", "config", "--get", "user.email"], capture_output=True, text=True).stdout.strip() \
        or "zero-sync@localhost"
    ident = {"GIT_AUTHOR_NAME": "zero-sync", "GIT_COMMITTER_NAME": "zero-sync",
             "GIT_AUTHOR_EMAIL": email, "GIT_COMMITTER_EMAIL": email}
    new = repo.run("commit-tree", tree, "-p", zero_tip, input=message.encode(), env=ident)

    missing = [l[1:] for l in repo.run("rev-list", "--objects", "--missing=print", new, "--not", zero_ref,
                                       check=False).splitlines() if l.startswith("?")]
    prefetch(repo, missing)
    p = repo.run("push", a.zero_url, f"{new}:refs/heads/main", check=False, raw=True, timeout=NET_TIMEOUT)
    if p.returncode != 0:
        err = p.stderr.decode(errors="replace")
        # Only a lost race is retryable. A "[remote rejected]" (ruleset, GH006, hook declined) is permanent.
        if re.search(r"non-fast-forward|fetch first|stale info", err):
            note = "push rejected: zero main moved, retry next tick"
            print("zero-sync: " + note); hb("warning", note)
            return EXIT_REJECTED
        raise SyncError("push failed: " + err.strip()[-500:])
    msg = f"synced canonical {short} -> zero {new[:10]} ({nfiles} files){ci_note}"
    print("zero-sync: " + msg); hb(status_ok, msg)
    return EXIT_OK


def prefetch(repo: Repo, oids: list[str]):
    if not oids:
        return
    repo.run("-c", "fetch.negotiationAlgorithm=noop", "fetch", "canonical", "--no-tags",
             "--no-write-fetch-head", "--recurse-submodules=no", "--filter=blob:none", "--stdin",
             input=("\n".join(oids) + "\n").encode(), timeout=NET_TIMEOUT)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--state-dir", default="~/.nuzantara-pilots/zero-sync")
    ap.add_argument("--canonical-url", default=os.environ.get("ZERO_SYNC_CANONICAL_URL", DEFAULT_CANONICAL))
    ap.add_argument("--canonical-ref", default="main")
    ap.add_argument("--zero-url", default=os.environ.get("ZERO_SYNC_ZERO_URL", DEFAULT_ZERO))
    ap.add_argument("--npm-cmd", default="npm")
    ap.add_argument("--no-ci-check", action="store_true")
    a = ap.parse_args(argv)
    heartbeat = _load_heartbeat()
    hb = (lambda *x, **k: None) if a.dry_run else (lambda s, n="": heartbeat(ORGAN_ID, s, n))

    if norm_url(a.canonical_url) == norm_url(a.zero_url):
        print("zero-sync: refusing: canonical and zero URLs are equal (never push to canonical)")
        hb("error", "canonical and zero URLs are equal")
        return EXIT_USAGE
    state = Path(a.state_dir).expanduser()
    try:
        state.mkdir(parents=True, exist_ok=True)
        lockf = open(state / "lock", "w")
        try:
            fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # Bounded by NET_TIMEOUT/NPM_TIMEOUT, a run never spans a tick for long; say so anyway.
            print("zero-sync: already running")
            hb("warning", "previous run still holds the lock")
            return EXIT_OK
        try:
            return sync(a, hb)
        finally:
            fcntl.flock(lockf, fcntl.LOCK_UN)
            lockf.close()
    except SyncError as exc:
        print(f"zero-sync: ERROR {exc}")
        hb("error", str(exc)[:300])
        return exc.code
    except Exception as exc:  # noqa: BLE001 - last resort, must be visible
        print(f"zero-sync: UNEXPECTED {type(exc).__name__}: {exc}")
        hb("error", f"unexpected {type(exc).__name__}: {exc}"[:300])
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
