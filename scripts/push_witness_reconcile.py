#!/usr/bin/env python3
"""Reconcile agent-branch tips with runtime pre-push witness records.

A tip is witnessed only by an exact ``local_sha`` marker for that branch's
remote ref.  An ancestor or abbreviated SHA is intentionally insufficient.
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BUNDLE_ROOT = re.compile(r"(?:^|/)codex-autofix-trusted-prepush/[0-9a-f]{40}/tree/?$")
SHA = re.compile(r"[0-9a-fA-F]{40,64}")
WITNESS_CODE = "push_witness_write"  # the marker function the hook defines
GRACE = timedelta(days=7)  # after it, a tip whose own hook lacks the witness is judged: that hook is stale

def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp has no UTC offset")
    return parsed.astimezone(timezone.utc)

def normalize_host(raw: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", raw.split(".")[0].lower()).strip("-") or "unknown-host"

def host_token() -> str:
    return normalize_host(socket.gethostname())

def branch_name(value: str) -> str:
    for prefix in ("refs/remotes/origin/", "refs/heads/", "origin/"):
        if value.startswith(prefix):
            return value[len(prefix):]
    return value

def remote_key(url: str) -> str:  # exact URL minus userinfo, the same rewrite the hook applies
    return re.sub(r"^([A-Za-z][A-Za-z0-9+.-]*://)[^/@]*@", r"\1", url.strip())

def observed_time(common: Path, branch: str, sha: str) -> datetime | None:
    """When this checkout's reflog moved the tracking ref to the tip, so a backdated commit cannot hide."""
    try:
        head, _, _ = (common / "logs/refs/remotes/origin" / branch).read_text(
            encoding="utf-8").splitlines()[-1].partition("\t")
        fields = head.split()
        return datetime.fromtimestamp(int(fields[-2]), timezone.utc) if fields[1] == sha else None
    except (OSError, IndexError, ValueError):
        return None

def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=False)
    if proc.returncode:
        raise ValueError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout

def load_refs(repo: Path, host: str, refs_file: Path | None) -> list[tuple[str, str]]:
    if refs_file:
        data = json.loads(refs_file.read_text(encoding="utf-8"))
        data = data.get("refs", []) if isinstance(data, dict) else data
        refs = []
        for item in data:
            if isinstance(item, dict):
                refs.append((str(item["branch"]), str(item["sha"])))
            else:
                refs.append((str(item[0]), str(item[1])))
    else:
        output = git(repo, "for-each-ref", "--format=%(refname:strip=3)%00%(objectname)",
                     f"refs/remotes/origin/agent/{host}/")
        refs = [tuple(line.split("\0", 1)) for line in output.splitlines() if line]
    prefix = f"agent/{host}/"
    return sorted((name, sha.lower()) for raw_name, sha in refs
                  if (name := branch_name(raw_name)).startswith(prefix) and SHA.fullmatch(sha))

def commit_times(repo: Path, shas: list[str], chunk: int = 500) -> dict[str, datetime]:
    """Committer dates for every tip in a few git calls, not one per ref."""
    for sha in shas:
        if not SHA.fullmatch(sha):
            raise ValueError(f"invalid full commit sha: {sha!r}")
    unique, times = sorted(set(shas)), {}
    for start in range(0, len(unique), chunk):
        out = git(repo, "show", "-s", "--no-walk=unsorted", "--format=%H %cI",
                  *unique[start:start + chunk], "--")
        for line in out.splitlines():
            sha, _, stamp = line.partition(" ")
            times[sha.lower()] = parse_time(stamp)
    missing = [sha for sha in unique if sha not in times]
    if missing:
        raise ValueError(f"no committer date for {missing[0]}")
    return times

def load_journal(path: Path) -> tuple[list[dict[str, Any]], int]:
    if not path.exists():
        return [], 0
    entries, malformed = [], 0
    required = ("ts", "host", "local_sha", "remote_ref", "trust_root")
    with path.open(encoding="utf-8", errors="replace") as stream:
        for raw in stream:
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
                if not isinstance(row, dict) or not all(isinstance(row.get(key), str)
                                                        for key in required):
                    raise ValueError("marker schema")
                row["_ts"] = parse_time(row["ts"])
            except (json.JSONDecodeError, TypeError, ValueError):
                malformed += 1
                continue
            entries.append(row)
    return entries, malformed

def carries_witness(repo: Path, sha: str) -> bool:
    proc = subprocess.run(["git", "cat-file", "-p", f"{sha}:.husky/pre-push"], cwd=repo,
                          text=True, capture_output=True, check=False)
    return proc.returncode == 0 and WITNESS_CODE in proc.stdout

def trusted_root(value: str, repo: Path, worktrees: set[Path]) -> bool:
    try:
        root = Path(value).expanduser().resolve()
    except OSError:
        return False
    return (root in worktrees or root.parent == repo / ".worktrees"
            or bool(BUNDLE_ROOT.search(root.as_posix())))

def reconcile(repo: Path, journal: Path, host: str, refs_file: Path | None,
              hours: float) -> dict[str, Any]:
    entries, malformed = load_journal(journal)
    result = {"host": host, "checked": 0, "witnessed": 0, "uncovered": 0, "unobserved": 0, "findings": [],
              "journal_entries": len(entries), "journal_malformed": malformed}
    if not entries:
        return {**result, "note": "no witness epoch yet"}
    epoch = min(row["_ts"] for row in entries)  # the witness covers pushes after it only
    origin = remote_key(git(repo, "remote", "get-url", "--push", "origin"))
    worktrees = {Path(line[9:]).resolve() for line in
                 git(repo, "worktree", "list", "--porcelain").splitlines()
                 if line.startswith("worktree ")} | {repo}
    common = (repo / git(repo, "rev-parse", "--git-common-dir").strip()).resolve()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    findings, checked, witnessed = result["findings"], 0, 0
    refs = load_refs(repo, host, refs_file)
    dates = commit_times(repo, [sha for _, sha in refs])
    for branch, sha in refs:
        committed = dates[sha]
        observed = observed_time(common, branch, sha)
        result["unobserved"] += observed is None  # no reflog: the committer date is the only clock
        seen = max(committed, observed or committed)
        if seen < cutoff:
            continue
        remote_ref = f"refs/heads/{branch}"
        matches = [row for row in entries  # the journal is this host's: no host match to drift
                   if row["local_sha"].lower() == sha and row["remote_ref"] == remote_ref
                   and remote_key(str(row.get("url", ""))) == origin]
        if not matches and (seen < epoch or (seen < epoch + GRACE and not carries_witness(repo, sha))):
            result["uncovered"] += 1
            continue
        checked += 1
        if not matches:
            findings.append({"branch": branch, "sha": sha, "verdict": "NO-WITNESS",
                             "detail": "no exact tip marker for this remote and ref"})
            continue
        valid = [row for row in matches if trusted_root(row["trust_root"], repo, worktrees)]
        if not valid:
            findings.append({"branch": branch, "sha": sha, "verdict": "FOREIGN-ROOT",
                             "detail": f"untrusted marker root: {matches[0]['trust_root']}"})
            continue
        newest = max(row["_ts"] for row in valid)
        if newest < committed:
            findings.append({"branch": branch, "sha": sha, "verdict": "STALE-WITNESS",
                             "detail": f"newest marker {newest.isoformat()} predates commit {committed.isoformat()}"})
            continue
        witnessed += 1
    return {**result, "checked": checked, "witnessed": witnessed}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal", type=Path,
                        default=Path.home() / ".organism/push-witness/journal.jsonl")
    parser.add_argument("--host", default=host_token())
    parser.add_argument("--refs-file", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--since", type=float, default=24.0, metavar="HOURS")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--json", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.since < 0:
        parser.error("--since must be non-negative")
    try:
        result = reconcile(args.repo_root.resolve(), args.journal.expanduser(), args.host,
                           args.refs_file, args.since)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        result = {"host": args.host, "checked": 0, "witnessed": 0, "findings": [
            {"branch": "", "sha": "", "verdict": "RECONCILE-ERROR", "detail": str(exc)[:300]}]}
    if args.json:
        print(json.dumps(result, separators=(",", ":")))
        return 0
    for finding in result["findings"]:
        print(f"{finding['verdict']}: {finding['branch']} {finding['sha']} — {finding['detail']}")
    if not result["findings"]:
        print(f"OK: {result['witnessed']}/{result['checked']} tips witnessed")
    return 1 if args.check and result["findings"] else 0

if __name__ == "__main__":
    raise SystemExit(main())
