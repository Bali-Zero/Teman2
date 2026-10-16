"""B34 P1 - the LocalCI PR shepherd, OBSERVE core (docs/specs/localci-sovereign-2026-10-07.md, B34).

One tick: take the lease, read the rate limits, list the open PRs with one bounded paginated GraphQL query (<= 5 pages), classify each by the stranded
class it belongs to (4 gate missing, 7 label candidate by author class; class 10, the hosted setup-abort, is P2's) and journal what a later
PR would do as ``would_*`` rows. P1 has NO write verb: GitHub is read, nothing else; a static test pins that. The budget is
the account's, shared with the merger and every session: under 1500 core calls left the tick only observes, under 800 it skips,
and a tick never makes more than 60 REST calls.

    python3 shepherd.py tick --node Nuzantara --state-dir ~/.nuzantara-pilots/local-ci/shepherd
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import re
import sys
import time
from pathlib import Path

_here = Path(__file__).resolve().parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"localci_{name}", _here / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


mg = _load("merger")
hc = mg.hc

DEFAULT_STATE = Path.home() / ".nuzantara-pilots" / "local-ci" / "shepherd"
CORE_OBSERVE, CORE_SKIP, GQL_SKIP = 1500, 800, 1000   # S-B1
REST_CAP = 60                                          # S-B2
PAGE, MAX_PAGES, BRIEF_CHUNK = 25, 5, 40
GATE_CONTEXT = "harness/fable-gate"
DEPENDABOT = ("dependabot", "dependabot[bot]")
# docs/rules/RULINGS.md "Off-limits files", as entities: a basename, a basename prefix, an exact path
OFF_LIMITS_BASENAMES = ("zantara_core.py", "fly.toml")
OFF_LIMITS_ENV_PREFIX = ".env"
OFF_LIMITS_PATH = "apps/bali-intel-scraper/backend/db/migrations/env.py"
BRIEF_PATH = re.compile(r"evidence/[^/]+/[^/]+/brief\.yml")
SAFE_PATH = re.compile(r"[\w./@+-]+")

LIST_QUERY = """query($owner:String!,$name:String!,$after:String){repository(owner:$owner,name:$name){pullRequests(states:OPEN,first:%d,after:$after){
pageInfo{hasNextPage endCursor} nodes{number isDraft isCrossRepository baseRefName headRefName headRefOid reviewDecision
author{login __typename} labels(first:30){totalCount nodes{name}} files(first:100){totalCount nodes{path}}
commits(last:1){nodes{commit{statusCheckRollup{contexts(first:100){totalCount nodes{__typename
... on CheckRun{name conclusion status} ... on StatusContext{context state}}}}}}}}}}}""" % PAGE


class BudgetCap(RuntimeError):
    """The call that would cross the per-tick REST cap; it is not made."""


class CallCap:
    def __init__(self, cap: int | None = None):
        self.cap, self.used = REST_CAP if cap is None else cap, 0

    def charge(self, n: int = 1) -> None:
        if self.used + n > self.cap:
            raise BudgetCap(f"{self.used} of {self.cap} REST calls used, {n} more would cross the cap")
        self.used += n


def budget_mode(core: int, graphql: int) -> str:
    """skip | observe | act. Both reads are the account's remaining count from GET rate_limit."""
    if core < CORE_SKIP or graphql < GQL_SKIP:
        return "skip"
    if core < CORE_OBSERVE:
        return "observe"
    return "act"


def off_limits(path: str) -> bool:
    base = path.rsplit("/", 1)[-1]
    return base in OFF_LIMITS_BASENAMES or base.startswith(OFF_LIMITS_ENV_PREFIX) or path == OFF_LIMITS_PATH


def journal(state: Path, rec: dict) -> None:
    line = json.dumps({"ts": mg.now(), "host": mg.HOST, "organ": "pro.localci_shepherd", "armed": False, **rec}, sort_keys=True) + "\n"
    fd = os.open(state / "journal.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, line.encode())
        os.fsync(fd)
    finally:
        os.close(fd)


# ------------------------------------------------------------------ reads
def list_open(repo: str, gql) -> list[dict]:
    owner, name = repo.split("/", 1)
    out: list = []
    after = ""
    for _ in range(MAX_PAGES):
        prs = gql(LIST_QUERY, owner=owner, name=name, **({"after": after} if after else {}))["repository"]["pullRequests"]
        out += [p for p in prs["nodes"] if isinstance(p, dict)]
        if not prs["pageInfo"]["hasNextPage"]:
            return out
        after = prs["pageInfo"]["endCursor"]
    raise mg.MergerError(f"more than {MAX_PAGES} pages of open pull requests: refusing a truncated queue")


def brief_path(pr: dict) -> str | None:
    files = pr.get("files") or {}
    if (files.get("totalCount") or 0) > len(files.get("nodes") or []):
        return None   # a truncated file list cannot show that ONE brief is in the diff
    found = [f["path"] for f in files.get("nodes") or [] if isinstance(f.get("path"), str) and BRIEF_PATH.fullmatch(f["path"])]
    return found[0] if len(found) == 1 else None


def read_briefs(repo: str, prs: list[dict], gql) -> dict[int, dict]:
    """{pr number: parsed brief} for the PRs that carry exactly one brief, in aliased blob reads of BRIEF_CHUNK."""
    import yaml
    owner, name = repo.split("/", 1)
    want = [(p["number"], p["headRefOid"], brief_path(p)) for p in prs if mg.is_sha(p.get("headRefOid")) and brief_path(p)]
    want = [w for w in want if SAFE_PATH.fullmatch(w[2])]
    out: dict[int, dict] = {}
    for i in range(0, len(want), BRIEF_CHUNK):
        chunk = want[i:i + BRIEF_CHUNK]
        body = " ".join(f'b{n}: object(expression: "{sha}:{path}") {{ ... on Blob {{ text }} }}' for n, sha, path in chunk)
        repo_doc = gql("query($owner:String!,$name:String!){repository(owner:$owner,name:$name){" + body + "}}", owner=owner, name=name)["repository"]
        for n, _, _ in chunk:
            text = (repo_doc.get(f"b{n}") or {}).get("text")
            try:
                doc = yaml.safe_load(text) if isinstance(text, str) else None
            except yaml.YAMLError:
                doc = None
            if isinstance(doc, dict):
                out[n] = doc
    return out


# ------------------------------------------------------------------ the classifier
def rollup(pr: dict) -> tuple[list[dict], bool]:
    commits = (pr.get("commits") or {}).get("nodes") or []
    ctx = (((commits[0] if commits else {}).get("commit") or {}).get("statusCheckRollup") or {}).get("contexts") or {}
    nodes = [n for n in ctx.get("nodes") or [] if isinstance(n, dict)]
    return nodes, (ctx.get("totalCount") or 0) > len(nodes)


def author_class(pr: dict, role: str | None) -> str:
    author = pr.get("author") or {}
    if author.get("__typename") == "Bot":
        return "dependabot" if author.get("login") in DEPENDABOT else "bot"
    if str(pr.get("headRefName") or "").startswith("codex/"):
        return "codex"
    if role in mg.ARM_ROLES:
        return "admin"
    return "unknown_role" if role is None else "collaborator"


def label_names(pr: dict) -> tuple[set, bool]:
    labels = pr.get("labels") or {}
    nodes = labels.get("nodes") or []
    return {lb.get("name") for lb in nodes if isinstance(lb, dict)}, (labels.get("totalCount") or 0) > len(nodes)


def classify(pr: dict, brief: dict | None, role: str | None) -> dict:
    """{classes, action, reason, ...} for one open PR. Every NEVER predicate is checked before any would_* action."""
    row = {"pr": pr.get("number"), "head": pr.get("headRefOid"), "classes": [], "actions": [], "reason": None}
    if pr.get("isDraft") or pr.get("baseRefName") != "main":
        return {**row, "reason": "draft" if pr.get("isDraft") else "base_not_main"}
    if pr.get("isCrossRepository"):
        return {**row, "actions": ["never_auto"], "reason": "fork"}
    files = pr.get("files") or {}
    if (files.get("totalCount") or 0) > len(files.get("nodes") or []):
        return {**row, "actions": ["never_auto"], "reason": "files_truncated"}   # a path beyond the first 100 could be off-limits
    paths = [f.get("path") for f in (pr.get("files") or {}).get("nodes") or [] if isinstance(f.get("path"), str)]
    if any(off_limits(p) for p in paths):
        return {**row, "actions": ["never_auto"], "reason": "off_limits"}
    if pr.get("reviewDecision") == "CHANGES_REQUESTED":
        return {**row, "actions": ["never_auto"], "reason": "changes_requested"}
    nodes, truncated = rollup(pr)
    gear = brief.get("gear") if isinstance(brief, dict) else None
    has_gate = any(n.get("context") == GATE_CONTEXT for n in nodes)
    if type(gear) is int and gear >= 2 and not has_gate and not truncated:
        row["classes"].append("gate_missing")
        row["actions"].append("would_gate_manual" if brief.get("gate_class") == "fable" else "would_gate")
        row["gate_class"] = brief.get("gate_class")
    names, labels_cut = label_names(pr)
    if mg.ARM_LABEL in names:
        pass
    elif labels_cut:
        row["classes"].append("labels_truncated")   # the arm label may sit beyond the first 30: absence is not shown, so no label candidate
    else:
        who = author_class(pr, role)
        if who == "admin":
            row["classes"].append("own_lane")
        else:
            row["classes"].append("label_candidate")
            row["author_class"] = who
            row["actions"].append("would_label")
    return row


# ------------------------------------------------------------------ the tick
def roles_for(repo: str, prs: list[dict], rest) -> tuple[dict[str, str | None], bool]:
    """({login: role or None}, capped) for the authors of the open, non-draft, unlabelled User PRs that are not codex heads. Each login is
    one counted call, a failed read is remembered as None (one try per login per tick); the call that would cross the cap ends the loop."""
    roles: dict[str, str | None] = {}
    for p in prs:
        author = p.get("author") or {}
        login = author.get("login")
        labels, labels_cut = label_names(p)
        if (p.get("isDraft") or mg.ARM_LABEL in labels or labels_cut or str(p.get("headRefName") or "").startswith("codex/") or author.get("__typename") != "User"
                or not isinstance(login, str) or login in roles or not mg._LOGIN_RE.fullmatch(login)):
            continue
        try:
            perm = rest(f"repos/{repo}/collaborators/{login}/permission")
        except BudgetCap:
            return roles, True
        except hc.CompareError:
            roles[login] = None
            continue
        role = perm.get("role_name") if isinstance(perm, dict) else None
        roles[login] = role if isinstance(role, str) else None
    return roles, False


class Rest:
    """GETs counted against the per-tick cap; the call that would cross it is not made."""
    def __init__(self, repo: str, get, cap: CallCap):
        self.repo, self.get, self.cap = repo, get, cap

    def __call__(self, path: str):
        self.cap.charge(1)
        return self.get(path)


def tick(state: Path, repo: str, node: str, *, get=None, gql=None) -> dict:
    get, gql = get or hc.gh_get, gql or mg.gh_graphql
    if platform.node() != node:
        return {"status": "disabled", "note": f"host {platform.node()} is not {node}"}
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    fh, lease = mg.take_lease(state, repo)
    if fh is None:
        journal(state, {"event": "skipped_lease", "holder": {k: lease.get(k) for k in ("host", "pid", "ts")}})
        return {"status": "ok", "note": "lease held by a live tick"}
    try:
        rest = Rest(repo, get, CallCap())
        # counted: the 60 REST calls of a tick are every GET, this one first
        res = rest("rate_limit").get("resources") or {}
        core, graphql = ((res.get(k) or {}).get("remaining") for k in ("core", "graphql"))
        if any(type(x) is not int for x in (core, graphql)):
            raise mg.MergerError("rate_limit carries no integer remaining for core and graphql: the budget is unread, so no tick")
        mode = budget_mode(core, graphql)
        if mode == "skip":
            journal(state, {"event": "skipped_quota", "core": core, "graphql": graphql, "reset": (res.get("core") or {}).get("reset")})
            return {"status": "warning", "note": f"skipped_quota core={core} graphql={graphql}"}
        prs = list_open(repo, gql)
        briefs = read_briefs(repo, prs, gql)
        roles, capped = {}, False
        if mode == "act":   # S-B4: the REST lane exists only above the floor
            roles, capped = roles_for(repo, prs, rest)
        rows = [classify(p, briefs.get(p["number"]), roles.get((p.get("author") or {}).get("login"))) for p in prs]
        counts: dict[str, int] = {}
        for r in rows:
            for key in r["classes"] + ([f"never:{r['reason']}"] if "never_auto" in r["actions"] else []):
                counts[key] = counts.get(key, 0) + 1
        if mode == "act":
            for r in rows:
                for action in r["actions"]:
                    journal(state, {"event": action, **{k: v for k, v in r.items() if k != "actions"}})
        if capped:
            journal(state, {"event": "budget_cap", "rest_calls": rest.cap.used, "cap": REST_CAP})
        journal(state, {"event": "observe", "mode": mode, "open": len(prs), "classes": counts,
                        "rest_calls": rest.cap.used, "core": core, "graphql": graphql, "fork": sum(1 for p in prs if p.get("isCrossRepository"))})
        return {"status": "ok", "note": f"{mode} open={len(prs)} rest={rest.cap.used}"}
    finally:
        mg.drop_lease(state, fh, lease)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tick")
    t.add_argument("--node", required=True, help="the only hostname allowed to run (superscar #10)")
    t.add_argument("--repo", default=hc.DEFAULT_REPO)
    t.add_argument("--state-dir", type=Path, default=DEFAULT_STATE)
    a = ap.parse_args(argv)
    try:
        out = tick(a.state_dir, a.repo, a.node)
    except Exception as exc:  # noqa: BLE001 - a failed tick is an error heartbeat and one journal line, never a crash loop
        a.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        journal(a.state_dir, {"event": "error", "error": mg.redact(f"{type(exc).__name__}: {exc}")})
        out = {"status": "error", "note": mg.redact(str(exc))}
    sys.stdout.write(f"status={out['status']} {out['note']}\n")
    return 1 if out["status"] == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
