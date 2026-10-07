#!/usr/bin/env python3
"""localci merger — phase C, SHADOW: decides what the local gate would merge and merges nothing.

``tick`` holds a per-repo lease pinned to one host (``--node``), takes the open, non-draft, SAME-REPO pull request
on ``--base`` that is armed (auto-merge) or labelled ``localci:merge`` and not yet decided at (head sha, origin/<base>
sha), builds the merge candidate as the queue does (origin/<base> + the head squashed into one commit — the live
queue's merge_method is SQUASH — fixed author ``localci-merger``), runs the local gate on it with the runner and the contexts matrix of BASE — never the
candidate's — and sets it beside the hosted verdict of the PR HEAD sha (the queue's verdict lands on a merge-group
commit this process cannot see). One line per decision in ``<state-dir>/decisions.jsonl``; the same (pr, head, base)
is never run twice. A fork PR is journalled ``refused: fork`` and never fetched. ``merge`` refuses: phase E is not armed.

Every GitHub API call is a bare ``gh api`` GET (``hosted_compare.gh_get``) and the only other traffic is ``git fetch``:
nothing here merges, posts, labels or comments, and no candidate code is imported — it runs only inside the BASE
runner, contained as the runner does.
"""
from __future__ import annotations

import argparse
import calendar
from collections import Counter
import fcntl
import importlib.util
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

_spec = importlib.util.spec_from_file_location("localci_hosted_compare", Path(__file__).resolve().parent / "hosted_compare.py")
hc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hc)

DEFAULT_STATE = Path.home() / ".nuzantara-pilots" / "local-ci" / "merger"
LABEL = "localci:merge"
AUTHOR = "localci-merger"
PHASE_E = "phase E not armed: see docs/specs/localci-sovereign-2026-10-07.md"
HEAD_NOTE = "hosted verdict read on the PR head sha: the queue's verdict lands on a merge-group commit the merger cannot see"
MATRIX = "scripts/localci/contexts_matrix.yaml"
RUNNER_ENV = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TMPDIR", "DOCKER_HOST", "DOCKER_CONTEXT")  # an allowlist: no token reaches the runner
GIT_SAFE = ("-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", "-c", "rerere.enabled=false")  # no hook, signer or recorded resolution acts on a candidate
# no host config either: a filter, merge driver or fsmonitor configured globally would run on candidate paths outside any container
GIT_ISOLATED = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", "GIT_ATTR_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
                "GIT_CONFIG_COUNT": "3", "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": "/dev/null",
                "GIT_CONFIG_KEY_1": "core.fsmonitor", "GIT_CONFIG_VALUE_1": "false",
                "GIT_CONFIG_KEY_2": "core.attributesFile", "GIT_CONFIG_VALUE_2": "/dev/null"}   # the runner's git too
CLASSES = ("AGREE", "FALSE_GREEN", "FALSE_RED", "BLIND", "PENDING")
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_SINCE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}Z)?$")
SEAL_RE = re.compile(r"^seal=([0-9a-f]{64})\b", re.M)
SECRET_RE = re.compile(r"(gh[opsru]_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{16,}|(?<=://)[^/@\s]+(?=@)|(?i:bearer|token)\s+\S+)")
HOST = platform.node()
CODE_SHA: str | None = None   # the origin/main commit the launchd wrapper extracted this file from; stamped on every journal line


class Stopped(Exception):
    """SIGTERM during a tick: the runner is stopped cleanly, nothing is decided, the key is retried."""


class MergerError(RuntimeError):
    """No verdict: before a PR is picked it is an `error` line (the next tick retries); after, an ERROR decision for
    that (pr, head, base) — retried at the next base, so one poisoned PR cannot hold the queue — which reads as blind."""


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def atomic_write(p: Path, data: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=p.name + ".", suffix=".tmp")
    with os.fdopen(fd, "w") as fh:
        fh.write(data)
    os.replace(tmp, p)


def redact(text) -> str:
    return SECRET_RE.sub("[REDACTED]", str(text))[-500:]


def journal(state: Path, rec: dict) -> dict:
    line = {"ts": now(), "host": HOST, **({"code_sha": CODE_SHA} if CODE_SHA else {}), **rec}
    data = (json.dumps(line, sort_keys=True) + "\n").encode()
    fd = os.open(state / "decisions.jsonl", os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        size = os.fstat(fd).st_size
        if size and os.pread(fd, 1, size - 1) != b"\n":
            data = b"\n" + data   # a torn tail stays its own unreadable line instead of swallowing this one
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)
    return line


def read_journal(state: Path) -> list[dict]:
    p = state / "decisions.jsonl"
    recs = []
    for raw in (p.read_text().splitlines() if p.exists() else []):
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            continue   # a torn line decided nothing: its key is run again
        if isinstance(rec, dict):
            recs.append(rec)
    return recs


def git(cwd: Path | None, *args: str, env: dict | None = None, check: bool = True, timeout: int = 1800) -> subprocess.CompletedProcess:
    argv = ["git", *(["-C", str(cwd)] if cwd else []), *GIT_SAFE, *args]
    inherited = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}   # no caller GIT_DIR, index or env-scope config
    res = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env={**inherited, **(env or {}), **GIT_ISOLATED})
    if check and res.returncode != 0:
        raise MergerError(f"git {' '.join(args[:2])} failed (rc={res.returncode}): {redact(res.stderr.strip()[-300:])}")
    return res


# ------------------------------------------------------------------ lease (superscar #10)
def proc_start(pid: int) -> str | None:
    return subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True,
                          env={**os.environ, "LC_ALL": "C"}).stdout.strip() or None   # one spelling whatever the caller's locale


def pid_alive(pid, started: str | None) -> bool:
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    return not started or proc_start(pid) in (None, started)   # a recycled pid is not the holder


def read_lease(state: Path) -> dict | None:
    try:
        lease = json.loads((state / "lease.json").read_text())
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        return {}
    return lease if isinstance(lease, dict) else {}


def take_lease(state: Path, repo: str):
    """(lock, lease) when taken — ``lease['reclaimed']`` is a dead holder's record it replaced — else (None, holder).

    The flock excludes a second tick on this host; the file names the holder. A holder on another host, or a live pid
    with the same start time, is respected even when the flock is free (the lock file may have been replaced)."""
    fh = open(state / "lease.lock", "a+")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if os.fstat(fh.fileno()).st_ino != os.stat(state / "lease.lock").st_ino:
            raise BlockingIOError("lease.lock was replaced while it was being taken")
    except (BlockingIOError, FileNotFoundError) as exc:
        fh.close()
        return None, read_lease(state) or {"why": str(exc) or "lease.lock is held"}
    prev = read_lease(state)
    if prev and prev.get("host") and (prev["host"] != HOST or pid_alive(prev.get("pid"), prev.get("pid_start"))):
        fh.close()
        return None, prev
    lease = {"lease_id": uuid.uuid4().hex[:16], "host": HOST, "pid": os.getpid(), "pid_start": proc_start(os.getpid()), "ts": now(), "repo": repo}
    atomic_write(state / "lease.json", json.dumps(lease))
    return fh, {**lease, "reclaimed": prev}


def drop_lease(state: Path, fh, lease: dict) -> None:
    if (read_lease(state) or {}).get("lease_id") == lease["lease_id"]:
        (state / "lease.json").unlink(missing_ok=True)
    fh.close()


# ------------------------------------------------------------------ the queue, read with GETs
def open_prs(repo: str, base: str) -> list[dict]:
    out: list = []
    for page in range(1, hc.MAX_PAGES + 1):
        batch = hc.gh_get(f"repos/{repo}/pulls?state=open&base={base}&per_page=100&page={page}")
        if not isinstance(batch, list) or any(not isinstance(p, dict) for p in batch):
            raise hc.CompareError(f"pulls page {page} is not a list of objects")
        out += batch
        if len(batch) < 100:
            return out
    raise hc.CompareError(f"more than {hc.MAX_PAGES} pages of open pull requests — refusing a truncated queue")


def repo_of(side) -> str:
    r = side.get("repo") if isinstance(side, dict) else None
    return str(r.get("full_name") or "").lower() if isinstance(r, dict) else ""


def head_of(pr: dict) -> str:
    sha = (pr.get("head") or {}).get("sha") if isinstance(pr.get("head"), dict) else None
    return sha if isinstance(sha, str) and hc._SHA_RE.match(sha) else ""


def wants_merge(pr: dict) -> bool:
    return bool(pr.get("auto_merge")) or LABEL in {lb.get("name") for lb in pr.get("labels") or [] if isinstance(lb, dict)}


def triage(prs: list[dict], repo: str, recs: list[dict], base_sha: str) -> tuple[list[dict], list[dict]]:
    """(same-repo PRs to decide, in order; fork PRs to journal). Drafts and PRs that ask for no merge are not the merger's.

    Order: a head never decided at any base first, then the head whose last decision is oldest, then created_at —
    `main` moves on every merge, so oldest-first alone would re-decide one PR at each new base and starve the rest."""
    decided = {(r.get("pr"), r.get("head_sha"), r.get("base_sha")) for r in recs if r.get("kind") == "decision" or r.get("why") == "head_in_base"}
    refused = {(r.get("pr"), r.get("head_sha")) for r in recs if r.get("kind") == "refused"}
    last: dict = {}
    for r in recs:
        if r.get("kind") == "decision":
            last[(r.get("pr"), r.get("head_sha"))] = max(last.get((r.get("pr"), r.get("head_sha")), ""), str(r.get("ts")))
    todo, forks = [], []
    for pr in prs:
        n, head = pr.get("number"), head_of(pr)
        if pr.get("draft") is not False or not wants_merge(pr) or not isinstance(n, int) or not head:
            continue
        if repo_of(pr.get("head")) != repo.lower() or repo_of(pr.get("base")) != repo.lower():
            if (n, head) not in refused:
                forks.append(pr)
        elif (n, head, base_sha) not in decided:
            todo.append(pr)
    todo.sort(key=lambda p: ((p["number"], head_of(p)) in last, last.get((p["number"], head_of(p)), ""), str(p.get("created_at")), p["number"]))
    return todo, forks


# ------------------------------------------------------------------ candidate + gate
def ensure_mirror(state: Path, url: str, seed: str | None) -> Path:
    """A bare clone owned by the merger (seeded by a local hardlink clone when given), fetched from ``url``."""
    repo = state / "repo.git"
    if not (repo / "HEAD").exists():
        shutil.rmtree(repo, ignore_errors=True)
        git(None, "clone", "--bare", "--quiet", "--no-tags", seed or url, str(repo), timeout=7200)
    if git(repo, "remote", "get-url", "origin").stdout.strip() != url:
        git(repo, "remote", "set-url", "origin", url)
    return repo


def fresh_worktree(repo: Path, path: Path, sha: str) -> Path:
    if path.exists():
        cur = git(path, "rev-parse", "HEAD", check=False).stdout.strip()
        if cur == sha and not git(path, "status", "--porcelain", "--untracked-files=all", check=False).stdout.strip():
            return path
        drop_worktree(repo, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    git(repo, "worktree", "add", "--detach", "--quiet", str(path), sha)
    return path


def drop_worktree(repo: Path, path: Path) -> None:
    git(repo, "worktree", "remove", "--force", str(path), check=False)
    shutil.rmtree(path, ignore_errors=True)
    git(repo, "worktree", "prune", check=False)


def runner_exec(argv: list[str], cwd: Path, env: dict, timeout: int) -> subprocess.CompletedProcess:
    """On a timeout, the watchdog or a stop, the runner gets SIGTERM first — it marks its checks INTERRUPTED and removes its
    container in a `finally` — and SIGKILL only 60 s later."""
    with subprocess.Popen(argv, cwd=str(cwd), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as proc:
        try:
            out, err = proc.communicate(timeout=timeout)
        except BaseException as exc:
            proc.terminate()
            try:
                out, err = proc.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill()
                out, err = proc.communicate()
            if not isinstance(exc, subprocess.TimeoutExpired):
                raise
            return subprocess.CompletedProcess(argv, 124, out, f"{err}\ntimed out after {timeout}s")
        return subprocess.CompletedProcess(argv, proc.returncode, out, err)


def run_gate(a, base_wt: Path, cand: Path, run_dir: Path, base_sha: str, cand_sha: str) -> dict:
    """plan → run → status with the BASE runner and matrix (trusted_base_required applies to the merger too)."""
    env = {k: os.environ[k] for k in RUNNER_ENV if k in os.environ} | GIT_ISOLATED | {"PYTHONPATH": str(base_wt), "PYTHONNOUSERSITE": "1",
                                                                                     "PYTHONDONTWRITEBYTECODE": "1"}
    runner = [a.python, "-m", "scripts.localci.runner"]
    plan = [*runner, "plan", "--run-dir", str(run_dir), "--worktree", str(cand), "--base", base_sha, "--candidate", cand_sha]
    if (base_wt / MATRIX).is_file():
        plan += ["--contexts-file", str(base_wt / MATRIX)]
    run_dir.mkdir(parents=True)
    out: dict = {"seal": None}

    def step(name: str, argv: list[str], timeout: int) -> subprocess.CompletedProcess:
        res = runner_exec(argv, base_wt, env, timeout)
        with open(run_dir / "merger.log", "a") as fh:
            fh.write(f"$ {' '.join(argv[2:])}\n# rc={res.returncode}\n{res.stdout}{res.stderr}\n")
        out[f"{name}_rc"] = res.returncode
        return res

    if step("plan", plan, 900).returncode != 0:
        return {**out, "status": {"overall": "ERROR"}, "error": "runner plan failed (merger.log)"}
    seal = SEAL_RE.search(step("run", [*runner, "run", "--run-dir", str(run_dir)], a.run_timeout).stdout)   # the first: printed before candidate code runs
    out["seal"] = seal.group(1) if seal else None
    if not seal:
        return {**out, "status": {"overall": "ERROR"}, "error": "the runner printed no seal (merger.log): nothing vouches for its status"}
    if step("status", [*runner, "status", "--run-dir", str(run_dir), "--quiet", "--seal", out["seal"]], 900).returncode != 0:
        return {**out, "status": {"overall": "ERROR"}, "error": "runner status failed (merger.log)"}
    try:
        status = json.loads((run_dir / "status.json").read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return {**out, "status": {"overall": "ERROR"}, "error": f"status.json unreadable: {exc}"}
    binding = (status.get("candidate_sha"), status.get("base_sha"), status.get("seal")) if isinstance(status, dict) else None
    if binding != (cand_sha, base_sha, out["seal"]):
        return {**out, "status": {"overall": "ERROR"}, "error": f"status.json is bound to {binding}, not to this candidate, base and seal"}
    return {**out, "status": status}


def hosted_summary(repo: str, base: str, status: dict, head: str, run_dir: Path) -> dict:
    out = {"sha": head, "note": HEAD_NOTE}
    try:
        live = hc.fetch_live(repo, base, head)
        rep = hc.compare(status, live["required_checks"], live["check_runs"], live["statuses"])
        rep.update(source="live", repo=repo, branch=base, **out)
        atomic_write(run_dir / "hosted_compare.json", json.dumps(rep, indent=2) + "\n")
    except Exception as exc:  # noqa: BLE001 — a failed comparison is recorded beside the gate's verdict, never loses it
        return {**out, "error": redact(f"{type(exc).__name__}: {exc}")}
    return {**out, "agreement": rep["agreement"], "counts": rep["counts"], "drift": rep["drift"], "exit": hc.exit_code(rep)}


def decide(a, state: Path, repo_dir: Path, lease_id: str, n: int, head: str, base_sha: str) -> int:
    t0 = time.monotonic()
    rec = {"kind": "decision", "mode": "shadow", "repo": a.repo, "pr": n, "head_sha": head, "base_sha": base_sha, "lease_id": lease_id}
    if git(repo_dir, "merge-base", "--is-ancestor", head, base_sha, check=False).returncode == 0:
        journal(state, {**rec, "kind": "skipped", "why": "head_in_base"})
        return 0
    key = f"pr{n}-{head[:12]}-{base_sha[:12]}"
    cand = state / "cand" / key
    try:
        fresh_worktree(repo_dir, cand, base_sha)
        when = git(repo_dir, "show", "-s", "--format=%cI", base_sha).stdout.strip()   # fixed identity and date: same (head, base) → same candidate sha
        ident = {f"GIT_{who}_{what}": val for who in ("AUTHOR", "COMMITTER") for what, val in (("NAME", AUTHOR), ("EMAIL", f"{AUTHOR}@localhost"), ("DATE", when))}
        if git(cand, "merge", "--squash", head, check=False, env=ident).returncode != 0:
            conflicts = git(cand, "diff", "--name-only", "--diff-filter=U", check=False).stdout.split()
            if not conflicts:
                raise MergerError(f"merge of #{n} {head[:12]} failed without a conflicted path")
            journal(state, {**rec, "overall": "CONFLICT", "candidate_sha": None, "conflicts": conflicts[:50], "run_dir": None,
                            "elapsed_s": round(time.monotonic() - t0, 1)})
            print(f"merger: #{n} CONFLICT on {base_sha[:12]} ({len(conflicts)} paths) — journalled, no run")
            return 0
        git(cand, "commit", "--quiet", "--allow-empty", "-m", f"localci-merger: candidate of #{n} ({head[:12]}) on {a.base} {base_sha[:12]}",
            env=ident)
        cand_sha = git(cand, "rev-parse", "HEAD").stdout.strip()
        for old in (state / "base").glob("*") if (state / "base").is_dir() else []:
            if old.name != base_sha:
                drop_worktree(repo_dir, old)
        base_wt = fresh_worktree(repo_dir, state / "base" / base_sha, base_sha)
        run_dir = state / "runs" / f"{key}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
        gate = run_gate(a, base_wt, cand, run_dir, base_sha, cand_sha)
        status = gate["status"]
        ctx = status.get("contexts") if isinstance(status.get("contexts"), dict) and not gate.get("error") else {}   # an unvouched status lends no verdict
        results = ctx.get("results") if isinstance(ctx.get("results"), dict) else {}
        line = journal(state, {**rec, "candidate_sha": cand_sha, "overall": status.get("overall") or "ERROR", "error": gate.get("error"),
                               "contexts_status": ctx.get("status"), "contexts": {k: (v or {}).get("verdict") for k, v in results.items()},
                               "checks": {k: (v or {}).get("status") for k, v in (status.get("checks") or {}).items()},
                               "seal": gate["seal"], "runner_rc": {k: v for k, v in gate.items() if k.endswith("_rc")},
                               "hosted_compare": hosted_summary(a.repo, a.base, status, head, run_dir), "run_dir": str(run_dir),
                               "elapsed_s": round(time.monotonic() - t0, 1)})
        print(f"merger: #{n} {line['overall']} candidate={cand_sha[:12]} base={base_sha[:12]} hosted(head)={line['hosted_compare'].get('agreement', 'n/a')} "
              f"run_dir={run_dir}")
        return 0
    except (MergerError, OSError) as exc:   # a decision with no verdict: this (pr, head, base) is not retried, the next base is
        journal(state, {**rec, "overall": "ERROR", "error": redact(exc), "candidate_sha": None, "run_dir": None,
                        "elapsed_s": round(time.monotonic() - t0, 1)})
        print(f"merger: #{n} ERROR — {redact(exc)}", file=sys.stderr)
        return 1
    finally:
        drop_worktree(repo_dir, cand)


def tick(a, state: Path, lease_id: str) -> int:
    repo_dir = ensure_mirror(state, a.remote_url or f"https://github.com/{a.repo}.git", a.seed)
    shutil.rmtree(state / "cand", ignore_errors=True)   # a killed tick's leftovers: nothing else uses them while the lease is ours
    git(repo_dir, "worktree", "prune", check=False)
    git(repo_dir, "fetch", "--no-tags", "--quiet", "origin", f"+refs/heads/{a.base}:refs/merger/base")
    base_sha = git(repo_dir, "rev-parse", "refs/merger/base^{commit}").stdout.strip()
    todo, forks = triage(open_prs(a.repo, a.base), a.repo, read_journal(state), base_sha)
    for pr in forks:
        journal(state, {"kind": "refused", "why": "fork", "pr": pr["number"], "head_sha": head_of(pr), "base_sha": base_sha, "lease_id": lease_id})
    if not todo:
        print(f"merger: nothing to decide on {a.base} {base_sha[:12]} ({len(forks)} fork PR(s) refused)")
        return 0
    n, head = todo[0]["number"], head_of(todo[0])
    git(repo_dir, "fetch", "--no-tags", "--quiet", "origin", f"+refs/pull/{n}/head:refs/merger/pr/{n}")
    fetched = git(repo_dir, "rev-parse", f"refs/merger/pr/{n}^{{commit}}").stdout.strip()
    if fetched != head:
        journal(state, {"kind": "skipped", "why": "head_moved", "pr": n, "head_sha": head, "fetched_sha": fetched, "base_sha": base_sha, "lease_id": lease_id})
        return 0
    return decide(a, state, repo_dir, lease_id, n, head, base_sha)


def _raise(exc_type, why: str):
    def handler(signum, _frame):
        raise exc_type(f"{why} (signal {signum})")
    return handler


def cmd_tick(a) -> int:
    global CODE_SHA
    if a.code_sha is not None and not hc._SHA_RE.match(a.code_sha):
        print(f"merger: refusing — --code-sha {a.code_sha!r} is not a full commit sha", file=sys.stderr)
        return 2
    CODE_SHA = a.code_sha
    state = Path(a.state_dir).expanduser().resolve()
    state.mkdir(parents=True, exist_ok=True)
    if HOST != a.node:   # superscar #10: one host decides; any other exits clean and leaves the lease alone
        journal(state, {"kind": "skipped", "why": "node", "node": a.node})
        print(f"merger: host {HOST!r} is not the pinned node {a.node!r} — nothing done")
        return 0
    bound = state / "repo"   # one state dir, one repo: a journal never answers for another repository's keys
    if not bound.exists():
        bound.write_text(a.repo.lower() + "\n")
    if bound.read_text().strip() != a.repo.lower():
        print(f"merger: refusing — {state} belongs to {bound.read_text().strip()!r}, not {a.repo!r}", file=sys.stderr)
        return 2
    fh, lease = take_lease(state, a.repo)
    if fh is None:
        journal(state, {"kind": "skipped", "why": "lease", "holder": lease})
        print("merger: the lease is held — nothing done")
        return 0
    # superscar #2: a hung tick holds the lease and looks alive — the watchdog turns it into an ERROR decision; a stop is no verdict
    old = {s: signal.signal(s, h) for s, h in ((signal.SIGALRM, _raise(MergerError, f"tick exceeded --tick-timeout {a.tick_timeout}s")),
                                               (signal.SIGTERM, _raise(Stopped, "stopped")))}
    signal.alarm(a.tick_timeout)
    try:
        if lease["reclaimed"] is not None:
            journal(state, {"kind": "lease_reclaimed", "stale": lease["reclaimed"], "lease_id": lease["lease_id"]})
        return tick(a, state, lease["lease_id"])
    except (MergerError, Stopped, hc.CompareError, subprocess.TimeoutExpired, OSError) as exc:   # OSError: `gh` or `git` missing from PATH
        journal(state, {"kind": "error", "error": redact(exc), "lease_id": lease["lease_id"]})
        print(f"merger: error — {redact(exc)}", file=sys.stderr)
        return 1
    finally:
        signal.alarm(0)
        for s, h in old.items():
            signal.signal(s, h)
        drop_lease(state, fh, lease)


# ------------------------------------------------------------------ report: phase D's instrument
def merger_side(overall) -> str:
    return "GREEN" if overall == "PASS" else "RED" if overall == "FAIL" else "BLIND"


def github_side(merged_here: bool, live: dict) -> str:
    """GREEN when GitHub merged the PR at this very head (its queue let it through); else the required checks of the head, red-dominant."""
    if merged_here:
        return "GREEN"
    by = hc.hosted_entries(live["check_runs"], live["statuses"])
    seen = {hc.hosted_verdict(by.get(c["context"], []), c.get("app_id"))["verdict"] for c in live["required_checks"]}
    return "RED" if "RED" in seen else "PENDING" if "PENDING" in seen else "GREEN"


def classify(merger: str, github: str) -> str:
    if github == "PENDING":
        return "PENDING"
    if merger == "BLIND":
        return "BLIND"
    if merger == github:
        return "AGREE"
    return "FALSE_GREEN" if merger == "GREEN" else "FALSE_RED"


def _epoch(ts: str) -> float:
    return calendar.timegm(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"))


def strict_journal(state: Path) -> list[dict]:
    """The report's reader: an unreadable line is refused, never skipped — a dropped decision would be a dropped red."""
    p = state / "decisions.jsonl"
    recs = []
    for i, raw in enumerate(p.read_text().splitlines() if p.exists() else [], 1):
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            raise hc.CompareError(f"decisions.jsonl line {i} is unreadable — look at it and repair the journal before counting") from None
        if not isinstance(rec, dict) or not _TS_RE.match(str(rec.get("ts"))):
            raise hc.CompareError(f"decisions.jsonl line {i} is not a journal record")
        recs.append(rec)
    return recs


def queue_sha(a, pr: dict, d: dict, parents: dict) -> str:
    """The sha whose hosted verdict judges decision ``d``: the merge commit when the queue merged this head ON THE DECIDED BASE
    (the very candidate, with its merge_group runs), else the head."""
    if not (pr.get("merged") is True and head_of(pr) == d.get("head_sha")):
        return str(d.get("head_sha"))
    mc = pr.get("merge_commit_sha")
    if not hc._SHA_RE.match(str(mc)):
        raise hc.CompareError(f"#{d.get('pr')} merged at the decided head but carries no merge_commit_sha")
    if mc not in parents:
        commit = hc.gh_get(f"repos/{a.repo}/commits/{mc}")
        parents[mc] = [x.get("sha") for x in commit.get("parents") or []] if isinstance(commit, dict) else []
    return mc if parents[mc] == [d.get("base_sha")] else str(d.get("head_sha"))


def cmd_report(a) -> int:
    state = Path(a.state_dir).expanduser().resolve()
    prs: dict = {}
    lives: dict = {}
    parents: dict = {}
    rows = []
    ctx_counts = dict.fromkeys(hc.CLASSES, 0)
    recorded_fg = 0
    try:
        if a.since and not _SINCE_RE.match(a.since):
            raise hc.CompareError(f"--since {a.since!r}: give YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ")
        bound = (state / "repo").read_text().strip() if (state / "repo").exists() else None
        if bound not in (None, a.repo.lower()):
            raise hc.CompareError(f"{state} belongs to {bound!r}, not {a.repo!r}")
        window = [r for r in strict_journal(state) if str(r["ts"]) >= (a.since or "")]
        decisions = [r for r in window if r.get("kind") == "decision"]
        if any(str(d.get("repo", a.repo)).lower() != a.repo.lower() for d in decisions):
            raise hc.CompareError("a decision in the window belongs to another repository")
        for d in decisions:
            n, head = d.get("pr"), str(d.get("head_sha"))
            if n not in prs:
                prs[n] = hc.gh_get(f"repos/{a.repo}/pulls/{n}")
            merged_here = prs[n].get("merged") is True and head_of(prs[n]) == head
            sha = queue_sha(a, prs[n], d, parents)
            if sha not in lives:
                lives[sha] = hc.fetch_live(a.repo, a.base, sha)
                hc.required_names(lives[sha]["required_checks"])
            live = lives[sha]
            github = github_side(merged_here, live)
            # what the tick saw is kept: a red GitHub later re-ran green, or a context it no longer requires, cannot erase it
            recorded = ((d.get("hosted_compare") or {}).get("counts") or {}).get("FALSE_GREEN") or 0
            if type(recorded) is not int or recorded < 0:   # a count that is not a count is an unusable input, never a zero
                raise hc.CompareError(f"#{n} at {d.get('ts')}: recorded FALSE_GREEN {recorded!r} is not a count")
            recorded_fg += recorded
            if d.get("contexts_status") is not None:   # the gate ran: set its per-context verdicts beside the hosted ones
                status = {"candidate_sha": d.get("candidate_sha"), "contexts": {"status": d["contexts_status"],
                                                                                 "results": {k: {"verdict": v} for k, v in (d.get("contexts") or {}).items()}}}
                for k, v in hc.compare(status, live["required_checks"], live["check_runs"], live["statuses"])["counts"].items():
                    ctx_counts[k] += v
            rows.append({"ts": d.get("ts"), "pr": n, "head_sha": head, "hosted_sha": sha, "base_sha": d.get("base_sha"), "overall": d.get("overall"),
                         "github": github, "merged": prs[n].get("merged") is True, "class": classify(merger_side(d.get("overall")), github),
                         "compared_merge": merged_here and d.get("contexts_status") == "ok"})
    except (hc.CompareError, OSError, KeyError, TypeError, AttributeError) as exc:
        print(f"merger report: refusing — {exc}", file=sys.stderr)
        return 2
    counts = {k: sum(1 for r in rows if r["class"] == k) for k in CLASSES}
    first, last = (rows[0]["ts"], rows[-1]["ts"]) if rows else (None, None)
    days = _days(first, last) if rows else 0.0
    silence_h = _longest_gap_h(r["ts"] for r in window)
    decision_gap_h = _longest_gap_h(r["ts"] for r in rows)   # errors and skips keep the journal busy; only decisions age the window
    compared = [r for r in rows if r["compared_merge"]]
    compared_merges = len({r["pr"] for r in compared})
    compared_days = _days(compared[0]["ts"], compared[-1]["ts"]) if compared else 0.0
    fg = counts["FALSE_GREEN"] + ctx_counts["FALSE_GREEN"] + recorded_fg
    ready = fg == 0 and (compared_merges >= 50 or compared_days >= 14)   # days count only between compared merges, never alone
    skipped = dict(sorted(Counter(str(r.get("why")) for r in window if r.get("kind") == "skipped").items()))
    errors = sum(1 for r in window if r.get("kind") == "error")
    out = {"window": {"first": first, "last": last, "days": days, "decisions": len(rows), "distinct_prs": len({r["pr"] for r in rows}),
                      "merged_prs": len({r["pr"] for r in rows if r["merged"]}), "compared_merges": compared_merges,
                      "compared_days": compared_days, "longest_silence_h": silence_h, "longest_decision_gap_h": decision_gap_h,
                      "errors": errors, "skipped": skipped},
           "counts": counts, "context_counts": ctx_counts, "recorded_context_false_green": recorded_fg, "phase_e_ready": ready, "rows": rows,
           "since": a.since, "repo": a.repo, "base": a.base, "generated_at": now()}
    atomic_write(state / "report.json", json.dumps(out, indent=2) + "\n")
    print(f"{'PR':7} {'HEAD':12} {'BASE':12} {'MERGER':11} {'GITHUB':7} {'MERGED':6} CLASS")
    for r in rows:
        print(f"#{r['pr']:<6} {r['head_sha'][:12]} {str(r['base_sha'])[:12]} {str(r['overall']):11} {r['github']:7} {'yes' if r['merged'] else 'no':6} {r['class']}")
    w = out["window"]
    print(f"window: {first} .. {last} ({days} days) decisions={w['decisions']} distinct_prs={w['distinct_prs']} merged_prs={w['merged_prs']} "
          f"compared_merges={compared_merges} errors={errors} skipped={skipped or 0}")
    print(f"gaps: longest between decisions={decision_gap_h}h, longest between any journal lines={silence_h}h")
    print("pr-level: " + " ".join(f"{k.lower()}={v}" for k, v in counts.items()))
    print("context-level (hosted_compare per decision): " + " ".join(f"{k.lower()}={v}" for k, v in ctx_counts.items())
          + f" | false_green recorded at tick time={recorded_fg}")
    print(f"phase E {'READY' if ready else 'NOT READY'}: needs 0 FALSE_GREEN and >= 50 compared merges or 14 days between the first and "
          f"last compared merge; now false_green={fg}, compared_merges={compared_merges}, compared_days={compared_days}")
    return 1 if fg else 0


def _days(first: str, last: str) -> float:
    return (int(_epoch(last) - _epoch(first)) * 1000 // 86400) / 1000   # floored in integers: 13.9999 days is not 14, 14 days is


def _longest_gap_h(stamps) -> float:
    ts = sorted(_epoch(str(t)) for t in stamps)
    return round(max((b - a for a, b in zip(ts, ts[1:])), default=0) / 3600, 2)


def cmd_merge(_a) -> int:
    print(f"merger: refusing — {PHASE_E}", file=sys.stderr)
    return 2


def selftest() -> int:
    """Guilt + innocence for the pure decisions: queue triage, the lease and the merge refusal."""
    repo, base = "o/r", "b" * 40

    def pr(n, sha, **kw):
        head_repo = "x/fork" if kw.get("fork") else repo
        return {"number": n, "draft": kw.get("draft", False), "auto_merge": {"merge_method": "merge"} if kw.get("armed", True) else None, "created_at": f"2026-10-0{n}",
                "labels": [{"name": lb} for lb in kw.get("labels", ())], "head": {"sha": sha, "repo": {"full_name": head_repo}},
                "base": {"repo": {"full_name": repo}}}

    prs = [pr(1, "1" * 40, fork=True), pr(2, "2" * 40, draft=True), pr(3, "3" * 40, armed=False), pr(4, "4" * 40, armed=False, labels=[LABEL]),
           pr(5, "5" * 40), pr(6, "6" * 40)]
    recs = [{"kind": "decision", "pr": 5, "head_sha": "5" * 40, "base_sha": base, "ts": "t"}, {"kind": "decision", "pr": 6, "head_sha": "6" * 40,
            "base_sha": "c" * 40, "ts": "t"}]
    todo, forks = triage(prs, repo, recs, base)
    checks = {"fork refused, never queued": [f["number"] for f in forks] == [1],
              "draft, unarmed and decided (pr, head, base) skipped; a never-decided head first": [p["number"] for p in todo] == [4, 6],
              "a refused fork head is journalled once": triage(prs, repo, [{"kind": "refused", "pr": 1, "head_sha": "1" * 40}], base)[1] == []}
    with tempfile.TemporaryDirectory() as td:
        st = Path(td)
        dead = subprocess.Popen(["true"])
        dead.wait()
        (st / "lease.json").write_text(json.dumps({"host": HOST, "pid": dead.pid, "pid_start": "gone"}))
        fh, lease = take_lease(st, repo)
        checks["a dead holder's lease is reclaimed"] = fh is not None and lease["reclaimed"]["pid"] == dead.pid
        if fh:
            fh.close()
        (st / "lease.json").write_text(json.dumps({"host": HOST, "pid": os.getpid(), "pid_start": proc_start(os.getpid())}))
        checks["a live holder's lease is respected"] = take_lease(st, repo)[0] is None
        (st / "lease.json").write_text(json.dumps({"host": "elsewhere", "pid": dead.pid}))
        checks["another host's lease is respected"] = take_lease(st, repo)[0] is None
    checks["merge refuses with exit 2"] = cmd_merge(None) == 2
    for name, ok in checks.items():
        print(f"{'ok  ' if ok else 'FAIL'} {name}")
    return 0 if all(checks.values()) else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="localci merger, phase C (shadow): decides, journals, never merges.")
    ap.add_argument("--selftest", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    t = sub.add_parser("tick", help="decide one pending PR under the lease")
    t.add_argument("--node", required=True, help="the only hostname allowed to decide (superscar #10)")
    t.add_argument("--repo", default=hc.DEFAULT_REPO)
    t.add_argument("--base", default=hc.DEFAULT_BRANCH)
    t.add_argument("--state-dir", default=str(DEFAULT_STATE))
    t.add_argument("--seed", help="local clone to hardlink objects from when the mirror is first created")
    t.add_argument("--remote-url", help="fetch URL (default https://github.com/<repo>.git)")
    t.add_argument("--python", default=sys.executable, help="interpreter that runs the BASE runner")
    t.add_argument("--run-timeout", type=int, default=5400, help="seconds for the runner's `run` step")
    t.add_argument("--tick-timeout", type=int, default=9000, help="watchdog for the whole tick; past it the decision is ERROR")
    t.add_argument("--code-sha", help="the origin/main commit this merger.py was extracted from (the launchd wrapper passes it)")
    r = sub.add_parser("report", help="phase D: every decision beside what GitHub did with that head")
    r.add_argument("--repo", default=hc.DEFAULT_REPO)
    r.add_argument("--base", default=hc.DEFAULT_BRANCH)
    r.add_argument("--state-dir", default=str(DEFAULT_STATE))
    r.add_argument("--since", help="only decisions whose ts >= this ISO prefix (e.g. 2026-10-07)")
    sub.add_parser("merge", help=PHASE_E)
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["merge"]:   # whatever follows: there is no merge path to reach
        return cmd_merge(None)
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.cmd == "report":
        return cmd_report(a)
    if a.cmd == "tick":
        if not re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", a.repo) or not re.match(r"^[A-Za-z0-9_./-]+$", a.base) or ".." in a.base:
            print(f"merger: refusing repo {a.repo!r} / base {a.base!r}", file=sys.stderr)
            return 2
        if a.remote_url and re.match(r"^[a-z+]+://[^/]*@", a.remote_url):
            print("merger: refusing a --remote-url that carries credentials: they would be stored in the mirror's config", file=sys.stderr)
            return 2
        return cmd_tick(a)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
