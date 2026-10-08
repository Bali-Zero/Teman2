#!/usr/bin/env python3
"""localci merger — phase C, SHADOW: decides what the local gate would merge and merges nothing.

``tick`` holds a per-repo lease pinned to one host (``--node``), takes the open, non-draft, SAME-REPO pull request
on ``--base`` that is armed (auto-merge) or labelled ``localci:merge`` / ``localci:merge-shadow-ok`` and not yet decided at (head sha, origin/<base>
sha), builds the merge candidate as the queue does (origin/<base> + the head squashed into one commit — the live
queue's merge_method is SQUASH — fixed author ``localci-merger``), runs the local gate on it with the runner and the contexts matrix of BASE — never the
candidate's — and sets it beside the hosted verdict of the PR HEAD sha (the queue's verdict lands on a merge-group
commit this process cannot see). One line per decision in ``<state-dir>/decisions.jsonl``; the same (pr, head, base)
is never run twice. A fork PR is journalled ``refused: fork`` and never fetched. ``merge`` refuses: phase E is not armed.

GitHub is read with bare ``gh api`` GETs (``hosted_compare.gh_get``) and one GraphQL query per verdict; the only other traffic
is ``git fetch``. One write exists (C3a-2): after a verdict, ``enqueuePullRequest`` with ``expectedHeadOid`` = the decided head
puts the PR in GitHub's merge queue — only when ``LOCALCI_MERGER_ARMED=1`` AND an admin or maintainer applied
``localci:merge-shadow-ok`` AND every sub-criterion of the enqueue criterion holds; otherwise that same criterion is journalled
``would_enqueue``. Nothing here merges, pushes, labels or comments, and no candidate code is imported — it runs only inside
the BASE runner, contained as the runner does.
"""
from __future__ import annotations

import argparse
import ast
import calendar
from collections import Counter
from statistics import median
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
ARM_LABEL, ARM_ENV, ARM_ROLES = "localci:merge-shadow-ok", "LOCALCI_MERGER_ARMED", ("admin", "maintain")   # the two halves of the arm
AUTHOR = "localci-merger"
PHASE_E = "phase E not armed: see docs/specs/localci-sovereign-2026-10-07.md"
HEAD_NOTE = "hosted verdict read on the PR head sha: the queue's verdict lands on a merge-group commit the merger cannot see"
MATRIX = "scripts/localci/contexts_matrix.yaml"
RUNNER_ENV = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TMPDIR", "DOCKER_HOST", "DOCKER_CONTEXT",
              "LOCALCI_MIN_FREE_GB")  # an allowlist: no token reaches the runner (the last is the runner's free-space floor, B3)
GIT_SAFE = ("-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", "-c", "rerere.enabled=false")  # no hook, signer or recorded resolution acts on a candidate
# no host config either: a filter, merge driver or fsmonitor configured globally would run on candidate paths outside any container
GIT_ISOLATED = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", "GIT_ATTR_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
                "GIT_CONFIG_COUNT": "3", "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": "/dev/null",
                "GIT_CONFIG_KEY_1": "core.fsmonitor", "GIT_CONFIG_VALUE_1": "false",
                "GIT_CONFIG_KEY_2": "core.attributesFile", "GIT_CONFIG_VALUE_2": "/dev/null"}   # the runner's git too
CLASSES = ("AGREE", "FALSE_GREEN", "FALSE_RED", "BLIND", "PENDING")
_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")   # fullmatch only: `$` would let a trailing newline through
_FULL_SHA = re.compile(r"[0-9a-f]{40}")
# A compared merge (spec §2 phase D, ruled 2026-10-08): >= 12 contexts compared on both sides, >= 11 of them full and at most one
# partial, named on the line. The arithmetic the real matrix allows: 14 required - 2 CodeQL (hosted-only, never executed here)
# - 1 E2E (partial: no repository secrets) = 11 full. An unrecorded coverage counts toward none of the three.
MIN_COMPARED_CONTEXTS = 12
MIN_COMPARED_FULL = 11      # implied by the two around it (12 - at most 1 partial); stated because the ruling states it
MAX_COMPARED_PARTIAL = 1
_SINCE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}Z)?$")
SEAL_RE = re.compile(r"^seal=([0-9a-f]{64})\b", re.M)
SECRET_RE = re.compile(r"(gh[opsru]_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{16,}|(?<=://)[^/@\s]+(?=@)|(?i:bearer|token)\s+\S+)")
HOST = platform.node()
CODE_SHA: str | None = None   # the origin/main commit the launchd wrapper extracted this file from; stamped on every journal line


class Stopped(Exception):
    """SIGTERM during a tick: the runner is stopped cleanly, nothing is decided, the key is retried."""


class GraphQLError(RuntimeError):
    """``gh api graphql`` failed or GitHub answered with errors: the message is GitHub's, redacted."""


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
    return sha if is_sha(sha) else ""


def wants_merge(pr: dict) -> bool:
    return bool(pr.get("auto_merge")) or bool({LABEL, ARM_LABEL} & {lb.get("name") for lb in pr.get("labels") or [] if isinstance(lb, dict)})


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


def runner_takes(base_wt: Path, flag: str) -> bool:
    """The BASE runner's own source decides which flags it takes — an `add_argument` call naming the flag, read with ast so a
    comment or another string never counts: a merger ahead of main never breaks an older runner's plan."""
    try:
        tree = ast.parse((base_wt / "scripts" / "localci" / "runner.py").read_text())
    except (OSError, SyntaxError, ValueError):
        return False
    return any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument"
               and any(isinstance(arg, ast.Constant) and arg.value == flag for arg in node.args) for node in ast.walk(tree))


def run_gate(a, base_wt: Path, cand: Path, run_dir: Path, base_sha: str, cand_sha: str, pr: int) -> dict:
    """plan → run → status with the BASE runner and matrix (trusted_base_required applies to the merger too)."""
    env = {k: os.environ[k] for k in RUNNER_ENV if k in os.environ} | GIT_ISOLATED | {"PYTHONPATH": str(base_wt), "PYTHONNOUSERSITE": "1",
                                                                                     "PYTHONDONTWRITEBYTECODE": "1"}
    runner = [a.python, "-m", "scripts.localci.runner"]
    plan = [*runner, "plan", "--run-dir", str(run_dir), "--worktree", str(cand), "--base", base_sha, "--candidate", cand_sha]
    if (base_wt / MATRIX).is_file():
        plan += ["--contexts-file", str(base_wt / MATRIX)]
    if runner_takes(base_wt, "--pr-number"):   # merge_group.head_ref names the PR, as the queue does (Harness floor parses it)
        plan += ["--pr-number", str(pr)]
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


def hosted_summary(repo: str, base: str, status: dict, head: str, run_dir: Path) -> tuple[dict, dict | None]:
    """The comparison journalled beside the verdict, and the hosted document it read (None when the read or the comparison failed)."""
    out = {"sha": head, "note": HEAD_NOTE}
    try:
        live = hc.fetch_live(repo, base, head)
        rep = hc.compare(status, live["required_checks"], live["check_runs"], live["statuses"])
        rep.update(source="live", repo=repo, branch=base, **out)
        atomic_write(run_dir / "hosted_compare.json", json.dumps(rep, indent=2) + "\n")
    except Exception as exc:  # noqa: BLE001 — a failed comparison is recorded beside the gate's verdict, never loses it
        return {**out, "error": redact(f"{type(exc).__name__}: {exc}")}, None
    return {**out, "agreement": rep["agreement"], "counts": rep["counts"], "drift": rep["drift"], "exit": hc.exit_code(rep)}, live


# ------------------------------------------------------------------ the enqueue path (C3a-2): GitHub's queue, only when both gates hold
ENQUEUE_BASE = "main"
_LOGIN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}")
PR_QUERY = ("query($owner: String!, $name: String!, $number: Int!) { repository(owner: $owner, name: $name) { pullRequest(number: $number) {"
            " id state isDraft isCrossRepository baseRefName headRefOid isInMergeQueue mergeQueueEntry { id position state }"
            " labels(first: 100) { nodes { name } } timelineItems(itemTypes: [LABELED_EVENT, UNLABELED_EVENT], last: 100) { nodes {"
            " __typename ... on LabeledEvent { label { name } actor { __typename login } } ... on UnlabeledEvent { label { name } } } } } } }")


def gh_graphql(query: str, **variables) -> dict:
    argv = ["gh", "api", "graphql", "-f", f"query={query}"]
    for k, v in variables.items():
        argv += ["-F" if type(v) is int else "-f", f"{k}={v}"]   # -f is raw: no @file read, no type guess
    res = subprocess.run(argv, capture_output=True, text=True, timeout=120)
    try:
        doc = json.loads(res.stdout or "null")
    except json.JSONDecodeError:
        doc = None
    errors = doc.get("errors") if isinstance(doc, dict) else None
    if res.returncode != 0 or errors or not isinstance(doc, dict) or not isinstance(doc.get("data"), dict):
        msg = "; ".join(str(e.get("message")) for e in errors if isinstance(e, dict)) if isinstance(errors, list) else res.stderr.strip()
        raise GraphQLError(redact(f"gh api graphql rc={res.returncode}: {msg or res.stderr.strip()}"))
    return doc["data"]


def hosted_side(live) -> str | None:
    """None when every context branch protection requires is GREEN on the PR head, red-dominant (skipped/neutral pass, as on GitHub)."""
    if not isinstance(live, dict):
        return "the hosted read on the PR head failed"
    hc.required_names(live.get("required_checks"))
    not_green = {k: v for k, v in required_verdicts(live).items() if v != "GREEN"}
    return f"required contexts not green on the PR head: {not_green}" if not_green else None


def label_arm(repo: str, p: dict) -> tuple[str | None, str | None]:
    """The label half of the arm: ARM_LABEL on the PR, applied last by a user whose role on the repo is admin or maintain."""
    if ARM_LABEL not in {lb.get("name") for lb in (p.get("labels") or {}).get("nodes") or [] if isinstance(lb, dict)}:
        return f"label {ARM_LABEL} absent", None
    actor = None
    for ev in (p.get("timelineItems") or {}).get("nodes") or []:
        if isinstance(ev, dict) and (ev.get("label") or {}).get("name") == ARM_LABEL:
            actor = ev.get("actor") if ev.get("__typename") == "LabeledEvent" else None
    login = actor.get("login") if isinstance(actor, dict) and actor.get("__typename") == "User" else None
    if not isinstance(login, str) or not _LOGIN_RE.fullmatch(login):
        return f"{ARM_LABEL} was not applied last by a user account (actor {actor})", None
    perm = hc.gh_get(f"repos/{repo}/collaborators/{login}/permission")
    role = perm.get("role_name") if isinstance(perm, dict) else None
    return (None if role in ARM_ROLES else f"{ARM_LABEL} applied by {login}, whose role is {role!r}, not admin or maintain"), login


def pr_side(a, state: Path, n: int, head: str, why: dict) -> dict:
    """The PR as GraphQL sees it now (the REST view has no queue state): fills the PR-side sub-criteria and the label in ``why``."""
    owner, name = a.repo.split("/")
    p = (gh_graphql(PR_QUERY, owner=owner, name=name, number=n).get("repository") or {}).get("pullRequest")
    if not isinstance(p, dict):
        raise GraphQLError(f"#{n} is not a pull request of {a.repo}")
    entry, live_head = p.get("mergeQueueEntry"), p.get("headRefOid")
    again = any(r.get("kind") == "enqueued" and r.get("pr") == n and r.get("head_sha") == head for r in read_journal(state))
    why.update(head_unchanged=None if live_head == head else f"the PR head moved to {live_head} since the decision on {head}",
               same_repo=None if p.get("isCrossRepository") is False else "a cross-repository pull request",
               not_draft=None if p.get("isDraft") is False else "a draft",
               base_main=None if p.get("baseRefName") == a.base == ENQUEUE_BASE else f"base {p.get('baseRefName')!r}, not {ENQUEUE_BASE}",
               open=None if p.get("state") == "OPEN" else f"state {p.get('state')}",
               not_in_queue=None if p.get("isInMergeQueue") is False and entry is None else f"already in the merge queue ({entry})",
               first_enqueue="this head was enqueued by an earlier tick" if again else None)
    facts = {"pull_request_id": p.get("id"), "live_head_oid": live_head, "label_actor": None}
    why["label_privileged"], facts["label_actor"] = label_arm(a.repo, p)
    return facts


# the criterion and the one write
CHECK_OK = ("PASS", "NOT_APPLICABLE", "BLOCKED")   # a BLOCKED check backs no executed context here: the contexts below judge those
NON_EXECUTED = ("blocked", "not_implemented")
HOST_NO_VERDICT = ("host_disk_full", "host_disk_below_floor", "host_disk_unmeasured", "host_disk_floor_invalid")   # the host, not the candidate (B3)
GATE = ("local_checks_clean", "review_independent", "executed_contexts_ok", "hosted_required_green", "head_unchanged", "same_repo",
        "not_draft", "base_main", "open", "not_in_queue", "first_enqueue")
CRITERION = (*GATE, "label_privileged")   # the env flag, the arm's other half, is journalled apart
ENQUEUE = ("mutation($pr: ID!, $oid: GitObjectID!) { enqueuePullRequest(input: {pullRequestId: $pr, expectedHeadOid: $oid}) {"
           " mergeQueueEntry { id position state } } }")


def local_side(status: dict) -> dict:
    """The merger's own half, from the BASE runner's vouched status (``{}`` when the gate vouched for none). Total on any JSON."""
    checks = status.get("checks") if isinstance(status.get("checks"), dict) else {}
    states = {k: v.get("status") if isinstance(v, dict) else None for k, v in checks.items()}
    ctx = status.get("contexts") if isinstance(status.get("contexts"), dict) else {}
    results = ctx.get("results") if isinstance(ctx.get("results"), dict) else {}
    required = ctx.get("required") if isinstance(ctx.get("required"), list) else []
    non_executed, not_ok, not_full, host = {}, {}, {}, {}
    for name in required:
        res = results[name] if isinstance(name, str) and isinstance(results.get(name), dict) else {}
        nv = res.get("no_verdict") if isinstance(res.get("no_verdict"), str) else ""
        if res.get("mapping") in NON_EXECUTED and res.get("verdict") == "BLOCKED":
            non_executed[name] = res["mapping"]
        elif res.get("verdict") in ("ERROR", "BLOCKED") and nv.split(" ")[0] in HOST_NO_VERDICT:
            host[str(name)] = nv   # not executed and not a FAIL: an executed mapping without a verdict still refuses (spec §2 C3a-2)
        elif res.get("verdict") != "OK":
            not_ok[str(name)] = f"{res.get('verdict')} ({res.get('mapping')})"
        elif res.get("coverage") != "full":   # executed and OK on a subset of its hosted twin: it passes, and the line names it
            not_full[str(name)] = res["coverage"] if res.get("coverage") in hc.COVERAGES else "unrecorded"
    bad = {k: v for k, v in states.items() if k != "review.independent" and v not in CHECK_OK}
    review = states.get("review.independent")
    why = {"local_checks_clean": "the gate vouched for no check" if not states else f"checks not clean: {bad}" if bad else None,
           "review_independent": None if review in ("QUEUED", "PASS") else f"review.independent is {review}, not QUEUED or PASS",
           "executed_contexts_ok": (f"contexts {ctx.get('status')!r} with {len(required)} required" if ctx.get("status") != "ok" or not required
                                    else "; ".join(x for x in (f"executed required contexts not OK: {not_ok}" if not_ok else "",
                                                               f"required contexts not executed, no verdict on this host (not a FAIL): {host}"
                                                               if host else "") if x) or None)}
    return {"why": why, "executed_required": f"{len(required) - len(non_executed) - len(host)}/{len(required)}" + coverage_suffix(not_full),
            "non_executed": non_executed, "partial": not_full, "host_no_verdict": host}


def coverage_suffix(not_full: dict) -> str:
    """`` (partial: E2E Tests (Playwright))`` beside ``executed_required`` — every executed OK context that is not full, by name."""
    groups = [f"{label}: {', '.join(n for n, c in not_full.items() if c == key)}" for key, label in (("partial", "partial"),
              ("unrecorded", "coverage unrecorded")) if key in not_full.values()]
    return f" ({'; '.join(groups)})" if groups else ""


def enqueue_step(a, state: Path, rec: dict, loc: dict, live) -> dict:
    """After a verdict: enqueue when armed on both sides and every sub-criterion holds, else journal the same criterion. Nothing
    here can turn the decision into ERROR, and a failed mutation is journalled, never retried in this tick."""
    n, head = rec["pr"], rec["head_sha"]
    why, facts = dict(loc["why"]), {}
    try:
        why["hosted_required_green"] = hosted_side(live)
        facts = pr_side(a, state, n, head, why)
    except Stopped:
        raise
    except Exception as exc:  # noqa: BLE001 — an unreadable sub-criterion is a false one, with the read's own message
        facts["read_error"] = redact(f"{type(exc).__name__}: {exc}")
    criterion = {k: k in why and why[k] is None for k in CRITERION}
    armed_env = os.environ.get(ARM_ENV) == "1"
    line = {**rec, **facts, "expected_head_oid": head, "criterion": criterion, "ok": all(criterion.values()), "armed_env": armed_env,
            "refused": [k for k, v in criterion.items() if not v] + ([] if armed_env else ["armed_env"]),
            "why": {k: why.get(k) or facts.get("read_error") or "not evaluated" for k, v in criterion.items() if not v},
            "executed_required": loc["executed_required"], "non_executed": loc["non_executed"], "partial": loc["partial"],
            "host_no_verdict": loc["host_no_verdict"]}
    kind = "would_enqueue" if not (armed_env and criterion["label_privileged"]) else "enqueue_refused" if not line["ok"] else "enqueued"
    if kind == "enqueued":
        try:
            entry = (gh_graphql(ENQUEUE, pr=facts["pull_request_id"], oid=head).get("enqueuePullRequest") or {}).get("mergeQueueEntry")
            if not isinstance(entry, dict) or not entry.get("id"):
                raise GraphQLError(f"enqueuePullRequest returned no merge queue entry: {entry!r}")
            line.update(entry_id=entry["id"], position=entry.get("position"), entry_state=entry.get("state"))
        except Stopped:
            raise
        except Exception as exc:  # noqa: BLE001 — journalled with GitHub's message, redacted
            kind, line["error"] = "enqueue_error", redact(f"{type(exc).__name__}: {exc}")
    out = journal(state, {**line, "kind": kind})
    print(f"merger: #{n} {kind} head={head[:12]} refused={out['refused']} executed_required={loc['executed_required']} non_executed="
          f"{[f'{k} ({v})' for k, v in loc['non_executed'].items()]}"
          + (f" host_no_verdict={[f'{k} ({v})' for k, v in loc['host_no_verdict'].items()]}" if loc["host_no_verdict"] else "")
          + (f" entry={out['entry_id']} position={out['position']}" if kind == "enqueued" else ""))
    return out


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
        gate = run_gate(a, base_wt, cand, run_dir, base_sha, cand_sha, n)
        status = gate["status"]
        ctx = status.get("contexts") if isinstance(status.get("contexts"), dict) and not gate.get("error") else {}   # an unvouched status lends no verdict
        results = ctx.get("results") if isinstance(ctx.get("results"), dict) else {}
        hosted, live = hosted_summary(a.repo, a.base, status, head, run_dir)
        loc = local_side({} if gate.get("error") else status)
        line = journal(state, {**rec, "candidate_sha": cand_sha, "overall": status.get("overall") or "ERROR", "error": gate.get("error"),
                               "contexts_status": ctx.get("status"), "contexts": {k: (v or {}).get("verdict") for k, v in results.items()},
                               "coverage": {k: (v or {}).get("coverage") for k, v in results.items()},
                               "skipped": {k: v["skipped"] for k, v in results.items() if isinstance((v or {}).get("skipped"), str)},
                               "checks": {k: (v or {}).get("status") for k, v in (status.get("checks") or {}).items()},
                               "durations": {k: (v or {}).get("duration_s") for k, v in (status.get("checks") or {}).items()},
                               "seal": gate["seal"], "runner_rc": {k: v for k, v in gate.items() if k.endswith("_rc")},
                               "hosted_compare": hosted, "run_dir": str(run_dir), "executed_required": loc["executed_required"],
                               "non_executed": loc["non_executed"], "partial": loc["partial"], "host_no_verdict": loc["host_no_verdict"],
                               "elapsed_s": round(time.monotonic() - t0, 1)})
        print(f"merger: #{n} {line['overall']} candidate={cand_sha[:12]} base={base_sha[:12]} hosted(head)={line['hosted_compare'].get('agreement', 'n/a')} "
              f"run_dir={run_dir}")
        enqueue_step(a, state, {"repo": a.repo, "pr": n, "head_sha": head, "base_sha": base_sha, "candidate_sha": cand_sha, "lease_id": lease_id},
                     loc, live)
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
    if a.code_sha is not None and not is_sha(a.code_sha):
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
    if a.host_free_gb is not None and a.host_free_gb < a.min_host_free_gb:   # B6: the gate never finishes the job of filling the disk
        journal(state, {"kind": "skipped", "why": "host_below_floor", "free_gb": a.host_free_gb, "floor_gb": a.min_host_free_gb})
        print(f"merger: host_below_floor free_gb={a.host_free_gb:g} floor_gb={a.min_host_free_gb:g} — no run started")
        return 0
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


def required_verdicts(live: dict) -> dict:
    by = hc.hosted_entries(live["check_runs"], live["statuses"])
    return {c["context"]: hc.hosted_verdict(by.get(c["context"], []), c.get("app_id"))["verdict"] for c in live["required_checks"]}


def github_side(live: dict) -> str:
    """The required checks of the judged sha (the merge commit when the queue merged the decided candidate), red-dominant. Merging
    proves nothing: the queue merges a failed entry when a later entry of its group passes (grouping HEADGREEN) — #8026's queue
    commit 2a1e00e0d3 had antidotes red and merged — and it can merge an entry before that entry's own runs report."""
    seen = set(required_verdicts(live).values())
    return "RED" if "RED" in seen else "PENDING" if "PENDING" in seen else "GREEN"


def classify(merger: str, github: str) -> str:
    if github == "PENDING":
        return "PENDING"
    if merger == "BLIND":
        return "BLIND"
    if merger == github:
        return "AGREE"
    return "FALSE_GREEN" if merger == "GREEN" else "FALSE_RED"


def is_sha(x) -> bool:
    return isinstance(x, str) and _FULL_SHA.fullmatch(x) is not None


def is_num(x) -> bool:
    return type(x) in (int, float) and x >= 0


def is_ts(x) -> bool:
    return isinstance(x, str) and _TS_RE.fullmatch(x) is not None


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
        if not isinstance(rec, dict) or not is_ts(rec.get("ts")):
            raise hc.CompareError(f"decisions.jsonl line {i} is not a journal record")
        recs.append(rec)
    return recs


def queue_sha(a, pr: dict, d: dict, parents: dict) -> str:
    """The sha whose hosted verdict judges decision ``d``: the merge commit when the queue merged this head ON THE DECIDED BASE
    (the very candidate, with its merge_group runs), else the head."""
    if not (pr.get("merged") is True and head_of(pr) == d.get("head_sha")):
        return str(d.get("head_sha"))
    mc = pr.get("merge_commit_sha")
    if not is_sha(mc):
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
    check_max_s: dict = {}   # the slowest run of each check in the window: where a tick's time goes
    try:
        if a.since and not _SINCE_RE.fullmatch(a.since):
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
            sha = queue_sha(a, prs[n], d, parents)
            # GitHub merged THIS candidate only when its merge commit sits on the decided base; a decision on another base is
            # judged by the head's own checks like any open PR
            merged_here = sha != head and sha == prs[n].get("merge_commit_sha")
            if sha not in lives:
                lives[sha] = hc.fetch_live(a.repo, a.base, sha)
                hc.required_names(lives[sha]["required_checks"])
            live = lives[sha]
            github = github_side(live)
            # what the tick saw is kept: a red GitHub later re-ran green, or a context it no longer requires, cannot erase it
            recorded_fg += recorded_false_green(d)
            for k, v in (d.get("durations") if isinstance(d.get("durations"), dict) else {}).items():
                if is_num(v):
                    check_max_s[k] = max(check_max_s.get(k, 0), v)
            compared_ctx, not_full, skip_agreed = 0, {"partial": [], "unrecorded": []}, []
            if d.get("contexts_status") is not None:   # the gate ran: set its per-context verdicts beside the hosted ones
                # coverage as the tick journalled it from the BASE runner; a line that predates it carries none: unrecorded, never full
                cov = d.get("coverage") if isinstance(d.get("coverage"), dict) else {}
                skip = d.get("skipped") if isinstance(d.get("skipped"), dict) else {}   # B5; a line before it records none: an execution
                status = {"candidate_sha": d.get("candidate_sha"), "contexts": {"status": d["contexts_status"], "results": {
                    k: {"verdict": v, "coverage": cov.get(k), "skipped": skip.get(k)} for k, v in (d.get("contexts") or {}).items()}}}
                rep = hc.compare(status, live["required_checks"], live["check_runs"], live["statuses"])
                for k, v in rep["counts"].items():
                    ctx_counts[k] += v
                compared_ctx = rep["coverage"]["compared_full"]   # a partial AGREE is an agreement on a subset: shown, never counted
                not_full = {"partial": rep["coverage"]["compared_partial"], "unrecorded": rep["coverage"]["compared_unrecorded"]}
                skip_agreed = rep["coverage"]["compared_skip_agreed"]   # full: the decision compared, counted apart from executions
            # a merge whose hosted side is still PENDING compared nothing yet: N contexts agreeing beside one unreported is no evidence
            merged_at = prs[n].get("merged_at") if merged_here else None
            if merged_here and not is_ts(merged_at):
                raise hc.CompareError(f"#{n} merged at the decided candidate but carries no merged_at")
            rows.append({"ts": d.get("ts"), "pr": n, "head_sha": head, "hosted_sha": sha, "base_sha": d.get("base_sha"), "overall": d.get("overall"),
                         "github": github, "merged": prs[n].get("merged") is True, "class": classify(merger_side(d.get("overall")), github),
                         "compared_contexts": compared_ctx, "compared_partial": not_full["partial"], "compared_unrecorded": not_full["unrecorded"],
                         "compared_skip_agreed": skip_agreed,
                         "merged_at": merged_at, "code_sha": d.get("code_sha"),
                         "elapsed_s": d.get("elapsed_s") if is_num(d.get("elapsed_s")) else None,
                         "compared_merge": merged_here and github != "PENDING" and d.get("contexts_status") == "ok"
                                           and compared_enough(compared_ctx, len(not_full["partial"]))})
        # GitHub merged a red required check: a HOSTED failure, read on every merged PR's own merge commit whichever candidate the
        # merger decided (#8026 was decided on an older base and is judged above on its green head), counted apart, never a class
        hosted_red_merged = []
        for n in sorted(k for k, v in prs.items() if v.get("merged") is True):
            mc = prs[n].get("merge_commit_sha")
            if not is_sha(mc):
                raise hc.CompareError(f"#{n} is merged but carries no merge commit sha")
            if mc not in lives:
                lives[mc] = hc.fetch_live(a.repo, a.base, mc)
                hc.required_names(lives[mc]["required_checks"])
            red = sorted(k for k, v in required_verdicts(lives[mc]).items() if v == "RED")
            if red:
                hosted_red_merged.append({"pr": n, "merge_commit_sha": mc, "red": red})
    except (hc.CompareError, OSError, KeyError, TypeError, AttributeError) as exc:
        print(f"merger report: refusing — {exc}", file=sys.stderr)
        return 2
    counts = {k: sum(1 for r in rows if r["class"] == k) for k in CLASSES}
    first, last = (rows[0]["ts"], rows[-1]["ts"]) if rows else (None, None)
    days = _days(first, last) if rows else 0.0
    silence_h = _longest_gap_h(r["ts"] for r in window)
    decision_gap_h = _longest_gap_h(r["ts"] for r in rows)   # errors and skips keep the journal busy; only decisions age the window
    clock = time.time()
    future_lines = sum(1 for r in window if _epoch(r["ts"]) > clock)   # a host clock that ran ahead: said, never a negative age
    last_line_age_h = round(max(0.0, clock - max(_epoch(r["ts"]) for r in window)) / 3600, 2) if window else None
    without_code_sha = sum(1 for r in rows if not is_sha(r["code_sha"]))   # lines older than provenance are counted, never refused
    # one event per merged PR, at GitHub's merged_at: duplicate decisions of one PR, or the journal's order, cannot widen the span
    merges = sorted({r["pr"]: r["merged_at"] for r in rows if r["compared_merge"]}.values())
    compared_merges = len(merges)
    compared_partial = sum(len(r["compared_partial"]) for r in rows)
    compared_unrecorded = sum(len(r["compared_unrecorded"]) for r in rows)
    partial_names = sorted({n for r in rows for n in r["compared_partial"]})
    with_partial = {r["pr"] for r in rows if r["compared_merge"] and r["compared_partial"]}   # a PR counts once, as with_partial if any of its rows is
    merged_partial_names = sorted({n for r in rows if r["compared_merge"] for n in r["compared_partial"]})
    compared_skip_agreed = sum(len(r["compared_skip_agreed"]) for r in rows)
    merged_skip_agreed = sum({r["pr"]: len(r["compared_skip_agreed"]) for r in rows if r["compared_merge"]}.values())   # a PR counts once
    compared_days = _days(merges[0], merges[-1]) if merges else 0.0
    fg = counts["FALSE_GREEN"] + ctx_counts["FALSE_GREEN"] + recorded_fg
    ready = fg == 0 and compared_merges >= 50 and compared_days >= 14   # lead's ruling 2026-10-07: both, never either
    skipped = dict(sorted(Counter(str(r.get("why")) for r in window if r.get("kind") == "skipped").items()))
    errors = sum(1 for r in window if r.get("kind") == "error")
    enqueue = {k: sum(1 for r in window if r.get("kind") == k) for k in ("enqueued", "enqueue_refused", "enqueue_error")}
    enqueue["would_enqueue"] = sum(1 for r in window if r.get("kind") == "would_enqueue" and r.get("ok") is True)   # every sub-criterion true
    timed = sorted((r["elapsed_s"], r["pr"]) for r in rows if r["elapsed_s"] is not None)
    ticks = {"timed": len(timed), "longest_s": timed[-1][0] if timed else None, "longest_pr": timed[-1][1] if timed else None,
             "median_s": round(median(t for t, _ in timed), 1) if timed else None,
             "check_max_s": dict(sorted(check_max_s.items(), key=lambda kv: -kv[1]))}
    out = {"window": {"first": first, "last": last, "days": days, "decisions": len(rows), "distinct_prs": len({r["pr"] for r in rows}),
                      "merged_prs": len({r["pr"] for r in rows if r["merged"]}), "compared_merges": compared_merges,
                      "compared_partial": compared_partial, "compared_unrecorded": compared_unrecorded, "partial_contexts": partial_names,
                      "compared_merges_full_only": compared_merges - len(with_partial), "compared_merges_with_partial": len(with_partial),
                      "compared_merges_partial_contexts": merged_partial_names, "compared_skip_agreed": compared_skip_agreed,
                      "compared_merges_skip_agreed": merged_skip_agreed,
                      "compared_days": compared_days, "longest_silence_h": silence_h, "longest_decision_gap_h": decision_gap_h,
                      "last_line_age_h": last_line_age_h, "future_lines": future_lines, "errors": errors, "skipped": skipped,
                      "decisions_without_code_sha": without_code_sha, "enqueue": enqueue,
                      "code_shas": sorted({r["code_sha"] for r in rows if is_sha(r["code_sha"])}), "ticks": ticks},
           "counts": counts, "hosted_red_merged": hosted_red_merged, "context_counts": ctx_counts, "recorded_context_false_green": recorded_fg, "phase_e_ready": ready, "rows": rows,
           "since": a.since, "repo": a.repo, "base": a.base, "generated_at": now()}
    atomic_write(state / "report.json", json.dumps(out, indent=2) + "\n")
    print(f"{'PR':7} {'HEAD':12} {'BASE':12} {'MERGER':11} {'GITHUB':7} {'MERGED':6} CLASS")
    for r in rows:
        print(f"#{r['pr']:<6} {r['head_sha'][:12]} {str(r['base_sha'])[:12]} {str(r['overall']):11} {r['github']:7} {'yes' if r['merged'] else 'no':6} {r['class']}")
    w = out["window"]
    print(f"window: {first} .. {last} ({days} days) decisions={w['decisions']} distinct_prs={w['distinct_prs']} merged_prs={w['merged_prs']} "
          f"compared_merges={compared_merges} (full_only={compared_merges - len(with_partial)}, with_partial={len(with_partial)}) "
          f"compared_partial={compared_partial} compared_unrecorded={compared_unrecorded} compared_skip_agreed={compared_skip_agreed} errors={errors} "
          f"skipped={skipped or 0}")
    print(f"gaps: longest between decisions={decision_gap_h}h, longest between any journal lines={silence_h}h, "
          f"last line {last_line_age_h}h ago" + (f", {future_lines} line(s) dated in the future" if future_lines else "")
          + f"; code shas in the window: {[c[:12] for c in w['code_shas']] or 'none recorded'}, "
          f"{without_code_sha} decision(s) without a valid code_sha")
    slow = ", ".join(f"{k}={v}s" for k, v in list(ticks["check_max_s"].items())[:3]) or "none journalled"
    print(f"ticks: {ticks['timed']} timed decisions, longest {ticks['longest_s']}s (#{ticks['longest_pr']}), median {ticks['median_s']}s; "
          f"slowest checks: {slow}")
    print("pr-level: " + " ".join(f"{k.lower()}={v}" for k, v in counts.items()))
    print("context-level (hosted_compare per decision): " + " ".join(f"{k.lower()}={v}" for k, v in ctx_counts.items())
          + f" | false_green recorded at tick time={recorded_fg}")
    for h in hosted_red_merged:
        print(f"hosted_red_merged: #{h['pr']} merged at {h['merge_commit_sha'][:12]} with required red: {', '.join(h['red'])}")
    print(f"phase E {'READY' if ready else 'NOT READY'}: needs 0 FALSE_GREEN and >= 50 compared merges and >= 14 days between the first "
          f"and last compared merge (a merge counts when GitHub merged the decided candidate and >= {MIN_COMPARED_CONTEXTS} contexts were "
          f"compared, >= {MIN_COMPARED_FULL} of them full and at most {MAX_COMPARED_PARTIAL} partial); now false_green={fg}, "
          f"compared_merges={compared_merges} (full_only={compared_merges - len(with_partial)}, with_partial={len(with_partial)}: "
          f"{merged_partial_names}), {merged_skip_agreed} of their full contexts were skip agreements (the classifier's decision compared, "
          f"not an execution), compared_days={compared_days}; of the contexts compared, {compared_partial} were partial "
          f"{partial_names} and {compared_unrecorded} carried no coverage record (a partial one never counts as full, an unrecorded one "
          f"never counts); "
          f"hosted_red_merged={len(hosted_red_merged)} (information: GitHub merged a red required check; the hosted failure itself never "
          f"blocks READY, a local false green on it does); enqueued={enqueue['enqueued']} would_enqueue={enqueue['would_enqueue']} "
          f"enqueue_refused={enqueue['enqueue_refused']} enqueue_error={enqueue['enqueue_error']}")
    return 1 if fg else 0


def compared_enough(full: int, partial: int) -> bool:
    """The ruled threshold of a compared merge: enough contexts compared, enough of them full, at most one partial."""
    return full + partial >= MIN_COMPARED_CONTEXTS and full >= MIN_COMPARED_FULL and partial <= MAX_COMPARED_PARTIAL


def recorded_false_green(d: dict) -> int:
    """The FALSE_GREEN count the tick journalled. A comparison that failed at tick time recorded no counts (0); counts that are
    there must carry an integer, or the input is unusable — never a silent zero."""
    counts = (d.get("hosted_compare") or {}).get("counts")
    if counts is None:
        return 0
    value = counts.get("FALSE_GREEN") if isinstance(counts, dict) else None
    if type(value) is not int or value < 0:
        raise hc.CompareError(f"#{d.get('pr')} at {d.get('ts')}: recorded FALSE_GREEN {value!r} is not a count")
    return value


def _days(first: str, last: str) -> float:
    return (int(_epoch(last) - _epoch(first)) * 1000 // 86400) / 1000   # floored in integers: 13.9999 days is not 14, 14 days is


def _longest_gap_h(stamps) -> float:
    ts = sorted(_epoch(str(t)) for t in stamps)
    return round(max((b - a for a, b in zip(ts, ts[1:])), default=0) / 3600, 2)


def cmd_prune(a) -> int:
    """B6: the gate's own retention, run by the wrapper after the tick (the decision first). Only a merger state dir."""
    global CODE_SHA
    if a.code_sha and not is_sha(a.code_sha):   # the same provenance rule as the tick's
        print(f"merger prune: refusing — --code-sha {a.code_sha!r} is not a full commit sha", file=sys.stderr)
        return 2
    CODE_SHA = a.code_sha or None
    state = Path(a.state_dir).expanduser().resolve()
    if not (state / "repo").is_file():
        print(f"merger prune: refusing — {state} is not a merger state dir (no repo binding written by a tick)", file=sys.stderr)
        return 2
    spec = importlib.util.spec_from_file_location("localci_prune", Path(__file__).resolve().parent / "prune.py")
    pm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pm)
    fh, lease = take_lease(state, (state / "repo").read_text().strip())   # never beside a tick: it may be naming an image right now
    if fh is None:
        journal(state, {"kind": "prune", "dry_run": a.dry_run, "skipped": "lease", "holder": lease})
        print("merger prune: skipped — the lease is held")
        return 0
    try:
        rec = pm.prune(state, a.docker, dry=a.dry_run, fstrim=a.fstrim, colima=a.colima, **({"matrix": Path(a.matrix)} if a.matrix else {}))
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        journal(state, {"kind": "prune", "dry_run": a.dry_run, "error": redact(f"{type(exc).__name__}: {exc}")})
        print(f"merger prune: error — {type(exc).__name__}", file=sys.stderr)
        return 1
    finally:
        drop_lease(state, fh, lease)
    journal(state, rec)
    gone = rec["images"].get("would_remove" if a.dry_run else "removed") or []
    print(f"merger prune: images_{'would_remove' if a.dry_run else 'removed'}={len(gone)} image_errors={len(rec['images']['errors'])} "
          f"failed={rec['failed']} vm_free_gb={rec['vm_free_gb']} host_free_gb={rec['host_free_gb']}")
    return 1 if rec["failed"] else 0


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
    t.add_argument("--host-free-gb", type=float, help="the host's free GB as the launchd wrapper read it before the tick (B6)")
    t.add_argument("--min-host-free-gb", type=float, default=60.0, help="under it no run starts: the skip is journalled (B6)")
    r = sub.add_parser("report", help="phase D: every decision beside what GitHub did with that head")
    r.add_argument("--repo", default=hc.DEFAULT_REPO)
    r.add_argument("--base", default=hc.DEFAULT_BRANCH)
    r.add_argument("--state-dir", default=str(DEFAULT_STATE))
    r.add_argument("--since", help="only decisions whose ts >= this ISO prefix (e.g. 2026-10-07)")
    pr = sub.add_parser("prune", help="B6: remove the gate's unreferenced deps images by tag and trim old run dirs, journalled")
    pr.add_argument("--state-dir", default=str(DEFAULT_STATE))
    pr.add_argument("--docker", default="docker")
    pr.add_argument("--dry-run", action="store_true", help="journal what would go, remove nothing")
    pr.add_argument("--fstrim", action="store_true", help="after an image removal, `colima ssh -- sudo fstrim -av`")
    pr.add_argument("--colima", default="colima")
    pr.add_argument("--matrix", help="the BASE contexts matrix whose service stand-ins are never pruned (default: beside prune.py)")
    pr.add_argument("--code-sha", help="the origin/main commit this merger.py was extracted from (the launchd wrapper passes it)")
    sub.add_parser("merge", help=PHASE_E)
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["merge"]:   # whatever follows: there is no merge path to reach
        return cmd_merge(None)
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.cmd == "report":
        return cmd_report(a)
    if a.cmd == "prune":
        return cmd_prune(a)
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
