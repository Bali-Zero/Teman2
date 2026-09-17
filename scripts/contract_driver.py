#!/usr/bin/env python3
"""contract_driver.py — the three facts no agent may attest, READ from the host.

Slice 3 of the SAETTA successor (research/operations sota-workflow-scan 2026-09-16).
SAETTA's scheduler has no filesystem and no GitHub access, so a seat returning
`{"merged": true, "live_receipt": "/tmp/x"}` for a PR that never merged passes it
today. Here every one of these facts is read from `gh`/git and the seat's claim, if
any, is only ever COMPARED against the read — never believed.

  collide    scope ∩ files of every OPEN PR and every PR merged in the last N hours.
             Non-empty → exit 1 (refuse the brief). This is the miss that discarded
             2 of 4 S1 tasks on 2026-09-16: built against files another lane had
             already merged.
  merged     mergedAt + mergeCommit from `gh pr view`. With --claim JSON, a claim of
             merged:true on an unmerged PR → BLOCK, exit 1. Prints the read-back.
  post-merge run the PR's executable `bites:` observe from a checkout that CONTAINS
             the merge commit (#6673: CI judged the pack from the BASE checkout,
             where the observe script did not exist yet; from the merge checkout it
             exits 0). --at REF lets a closed head's pack be observed from any ref.
             INCONCLUSIVE (exit 3) when this checkout does not contain the ref —
             the observer needs the real tree (venvs, fixtures), not a bare worktree.

Exit codes: 0 fact holds · 1 fact refutes the claim / collision / observe failed ·
2 usage · 3 INCONCLUSIVE (gh/git unavailable, checkout does not contain the ref).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent / "ci"))


def _gh_json(args: Sequence[str]) -> Any:
    p = subprocess.run(["gh", *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)}: {p.stderr.strip()}")
    return json.loads(p.stdout or "null")


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    p = subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p


# ------------------------------------------------------------------ collide

def collisions(scope: Sequence[str], prs: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Pure: which of `prs` ({number, state, files:[path]}) touch a path in `scope`.
    Literal paths, never globs — Next.js brackets do not expand and a glob hides a miss."""
    want = set(scope)
    out = []
    for pr in prs:
        hit = sorted(want & {f for f in pr.get("files") or []})
        if hit:
            out.append({"number": pr["number"], "state": pr.get("state"), "files": hit})
    return out


def fetch_prs(hours: int) -> List[Dict[str, Any]]:
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    open_prs = _gh_json(["pr", "list", "--state", "open", "--limit", "200", "--json", "number,files,state"])
    merged = _gh_json(["pr", "list", "--state", "merged", "--search", f"merged:>={since}", "--limit", "200",
                       "--json", "number,files,state"])
    norm = lambda rows: [{"number": r["number"], "state": r.get("state"), "files": [f["path"] for f in r.get("files") or []]} for r in rows]
    return norm(open_prs) + norm(merged)


def cmd_collide(args: argparse.Namespace) -> int:
    try:
        prs = fetch_prs(args.hours)
    except (RuntimeError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"INCONCLUSIVE — cannot read PRs: {exc}"); return 3
    hits = collisions(args.scope, prs)
    if args.json:
        print(json.dumps({"scope": list(args.scope), "collisions": hits}, indent=2))
    elif hits:
        print(f"COLLISION — {len(hits)} PR(s) touch this scope (open, or merged in the last {args.hours}h):")
        for h in hits:
            print(f"   #{h['number']} [{h['state']}] " + ", ".join(h["files"]))
    else:
        print(f"clear — no open or {args.hours}h-merged PR touches {len(args.scope)} scoped path(s)")
    return 1 if hits else 0


# ------------------------------------------------------------------- merged

def judge_merge(read: Dict[str, Any], claim: Optional[Dict[str, Any]]) -> str:
    """Pure: the host's read vs a seat's claim. 'OK' when they agree or there is no
    claim; 'BLOCK' when the seat claims merged and the host says otherwise (or the
    claimed merge commit is not the real one). A seat that under-claims is not blocked."""
    if not claim:
        return "OK"
    if claim.get("merged") and not read.get("mergedAt"):
        return "BLOCK"
    if claim.get("merged") and claim.get("merge_commit") and not str(read.get("mergeCommit") or "").startswith(str(claim["merge_commit"])):
        return "BLOCK"
    return "OK"


def read_merge(pr: int) -> Dict[str, Any]:
    v = _gh_json(["pr", "view", str(pr), "--json", "number,state,mergedAt,mergeCommit,headRefOid"])
    return {"number": v["number"], "state": v["state"], "mergedAt": v.get("mergedAt"),
            "mergeCommit": (v.get("mergeCommit") or {}).get("oid"), "headRefOid": v.get("headRefOid")}


def cmd_merged(args: argparse.Namespace) -> int:
    claim = None
    if args.claim:
        try:
            claim = json.loads(args.claim)
        except json.JSONDecodeError as exc:
            print(f"usage: --claim is not JSON: {exc}"); return 2
    try:
        read = read_merge(args.pr)
    except (RuntimeError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"INCONCLUSIVE — cannot read #{args.pr}: {exc}"); return 3
    verdict = judge_merge(read, claim)
    out = {"read": read, "claim": claim, "verdict": verdict}
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"#{read['number']} {read['state']} mergedAt={read['mergedAt'] or '-'} mergeCommit={(read['mergeCommit'] or '-')[:10]}")
        if claim is not None:
            print(f"   seat claimed {json.dumps(claim)} → {verdict}" + ("" if verdict == "OK" else "  (the host read says otherwise; the claim is not a fact)"))
    return 0 if verdict == "OK" else 1


# --------------------------------------------------------------- post-merge

def _pack_path(pr: int) -> Optional[str]:
    files = [f["path"] for f in _gh_json(["pr", "view", str(pr), "--json", "files"]).get("files") or []]
    import evidence_paths  # scripts/ci — the same resolver CI uses
    path = evidence_paths.resolve_evidence_path("pack", files)
    return path if path in files else None


def cmd_post_merge(args: argparse.Namespace) -> int:
    root = Path(_git(Path.cwd(), "rev-parse", "--show-toplevel").stdout.strip())
    try:
        read = read_merge(args.pr)
        pack = _pack_path(args.pr)
    except (RuntimeError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"INCONCLUSIVE — cannot read #{args.pr}: {exc}"); return 3
    ref = args.at or read["mergeCommit"]
    if not ref:
        print(f"#{args.pr} is not merged and no --at given — nothing to observe from a merge checkout"); return 1
    if not pack:
        print(f"#{args.pr} authored no evidence/**/pack.yml — no bites: to observe"); return 1
    if _git(root, "merge-base", "--is-ancestor", ref, "HEAD", check=False).returncode != 0:
        print(f"INCONCLUSIVE — this checkout ({root}) does not contain {ref[:10]}; pull it first, the observer needs the real tree"); return 3
    head_ref = read["headRefOid"] if not args.at_pack else args.at_pack
    # The pack is what the PR authored (read at its HEAD). The PARSER is judged at REF —
    # bites_parse's allow-list needs the observe script to exist in the checkout it is
    # asked from, which is exactly how #6673 died (BASE lacked the script) — so it runs in
    # a detached worktree at REF. The OBSERVE runs in THIS tree (venvs, fixtures), which
    # contains REF by the check above.
    import bites_parse  # scripts/ci — classify() only; the parser itself runs at REF
    import tempfile
    wt = Path(tempfile.mkdtemp(prefix="contract-driver-wt-"))
    _git(root, "worktree", "add", "--detach", "--quiet", str(wt), ref)
    try:
        stage = wt / "evidence" / "_post_merge_tmp"
        stage.mkdir(parents=True, exist_ok=True)
        (stage / "pack.yml").write_text(_git(root, "show", f"{head_ref}:{pack}").stdout, encoding="utf-8")
        p = subprocess.run([sys.executable, "scripts/ci/bites_parse.py", "--pack", "evidence/_post_merge_tmp/pack.yml"],
                           cwd=str(wt), capture_output=True, text=True)
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=str(root), capture_output=True)
    if p.returncode not in (0, 2):
        print(f"INCONCLUSIVE — bites_parse exited {p.returncode} at {ref[:10]}: {p.stderr.strip()}"); return 3
    parsed = json.loads(p.stdout or "{}")
    cls = bites_parse.classify(parsed)
    if cls != "executable":
        print(f"#{args.pr} bites: parsed at {ref[:10]} is {cls} — nothing executable to observe" + (f": {parsed.get('errors')}" if cls == "malformed" else "")); return 1
    import shlex
    argv = shlex.split(parsed["observe"])
    print(f"#{args.pr} bites: parsed at {ref[:10]} is executable; observe in this tree (HEAD {_git(root, 'rev-parse', '--short', 'HEAD').stdout.strip()} ⊇ {ref[:10]}; pack at {head_ref[:10]}): {' '.join(argv)}")
    r = subprocess.run(argv, cwd=str(root), capture_output=True, text=True)
    tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
    for line in tail:
        print(f"   {line[:200]}")
    print(f"   observe exit {r.returncode} (expect {parsed.get('expect')})")
    return 0 if r.returncode == 0 else 1


# ---------------------------------------------------------------- selftest

def selftest() -> int:
    fails = []

    def check(name: str, cond: bool) -> None:
        print(f"  {'✅' if cond else '❌'} {name}")
        if not cond:
            fails.append(name)

    prs = [{"number": 1, "state": "OPEN", "files": ["a.py", "b/c.ts"]}, {"number": 2, "state": "MERGED", "files": ["z.md"]}]
    check("collide: a scoped path in an open PR is a collision", collisions(["a.py"], prs) == [{"number": 1, "state": "OPEN", "files": ["a.py"]}])
    check("collide: disjoint scope is clear", collisions(["q.py"], prs) == [])
    check("collide: literal, not glob — 'b/*' matches nothing", collisions(["b/*"], prs) == [])
    unmerged = {"mergedAt": None, "mergeCommit": None}
    merged = {"mergedAt": "2026-09-17T05:54:57Z", "mergeCommit": "03516ea404f7c5370c4ec624fe223d2f832b3330"}  # pragma: allowlist secret — #6704's real merge commit, a public git SHA, not a credential
    check("merged: {merged:true, live_receipt:/tmp/x} on an unmerged PR = BLOCK", judge_merge(unmerged, {"merged": True, "live_receipt": "/tmp/x"}) == "BLOCK")
    check("merged: the same claim on a merged PR = OK", judge_merge(merged, {"merged": True, "live_receipt": "/tmp/x"}) == "OK")
    check("merged: claimed merge_commit that is not the real one = BLOCK", judge_merge(merged, {"merged": True, "merge_commit": "deadbeef"}) == "BLOCK")
    check("merged: claimed merge_commit prefix of the real one = OK", judge_merge(merged, {"merged": True, "merge_commit": "03516ea404"}) == "OK")
    check("merged: no claim = OK (a read, not a verdict)", judge_merge(unmerged, None) == "OK")
    check("merged: under-claim (merged:false on a merged PR) is not blocked", judge_merge(merged, {"merged": False}) == "OK")
    print(f"\n  {len(fails)} failure(s)")
    return 1 if fails else 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="contract_driver.py", description=(__doc__ or "").splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collide", help="scope ∩ open + recently merged PR files")
    c.add_argument("--scope", nargs="+", required=True, metavar="PATH", help="literal repo-relative paths")
    c.add_argument("--hours", type=int, default=24)
    c.add_argument("--json", action="store_true")
    m = sub.add_parser("merged", help="read mergedAt/mergeCommit; compare a seat's claim")
    m.add_argument("--pr", type=int, required=True)
    m.add_argument("--claim", metavar="JSON", help='e.g. \'{"merged": true, "live_receipt": "/tmp/x"}\'')
    m.add_argument("--json", action="store_true")
    p = sub.add_parser("post-merge", help="run the PR's bites: observe from a checkout containing the merge commit")
    p.add_argument("--pr", type=int, required=True)
    p.add_argument("--at", metavar="REF", help="judge the parser at REF instead of the merge commit (closed heads); this checkout must contain REF")
    p.add_argument("--at-pack", metavar="SHA", help="read the pack at SHA instead of the PR head")
    sub.add_parser("selftest")
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "selftest":
        return selftest()
    return {"collide": cmd_collide, "merged": cmd_merged, "post-merge": cmd_post_merge}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
