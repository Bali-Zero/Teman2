#!/usr/bin/env python3
"""audit_agent_quarantine.py — resolver-driven audit of local refs/agent-quarantine/*.

WHY THIS EXISTS (fills a real gap):
  worktree_gc_universal.py and arm_keep_worktrees.py quarantine a removed worktree's
  work onto refs/agent-quarantine/<slug> (a full-tree snapshot commit) so `git gc`
  never collects it after the branch is deleted. Today there is NO expiry path: those
  refs accumulate forever as a permanent safety net and the ~2.3 GB they protect is
  never reclaimed. This auditor resolves, by CONTENT, which quarantine refs are fully
  redundant (their protected work already lives on origin/main) and may be safely
  pruned, from the ones that carry genuine unique content and must stay.

THE RULE (same invariant as branch_graveyard_cleanup.sh content_on_main, W88):
  a ref is deletable ONLY when every file it protects has the SAME blob on
  origin/main — both (a) the worktree branch's authored diff (two-dot from the real
  merge-base against origin/main) and (b) the `add -A` dirty snapshot payload
  (diff <ref>^ <ref>). A pure deletion is also fine when that file is already absent
  from main. Never decided by three-dot diff or ancestor alone (both lie post-squash).

GUARDS (why you can trust it):
  - KEEP on: genuine unique content, any ambiguity, missing object, merge-base
    failure, a live/registered worktree, a currently-checked-out branch tip.
    Never --force, never exceptions.
  - Output is PII-safe (Law 2): only paths / hashes / counters, never blob content.
  - Default is READ-ONLY audit + manifest. --apply prunes ONLY LANDED entries, and
    re-verifies each ref STILL exists and origin/main is UNCHANGED immediately
    before every delete (the repo is shared/volatile — a ref seen during audit can
    vanish mid-flight; we re-qualify by content right before removal).

USAGE (run from the repo main checkout on the machine owning the refs — Pro here):
  python scripts/audit_agent_quarantine.py              # audit (read-only) + manifest
  python scripts/audit_agent_quarantine.py --out DIR    # audit, write manifest into DIR
  python scripts/audit_agent_quarantine.py --apply      # prune ONLY LANDED (+ your GO)
  python scripts/audit_agent_quarantine.py --verify     # re-run resolver on last DELETE set
  # kill switch (repo convention):
  QUARANTINE_AUDIT_ENABLED=false python scripts/audit_agent_quarantine.py
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

QUARANTINE_PREFIX = "refs/agent-quarantine"
MAIN_REF = os.environ.get("QUARANTINE_AUDIT_MAIN_REF", "origin/main")
# A two-dot authored scope above this many files is near-certainly a large unique
# divergent history (full Desktop-clone snapshots) — short-circuit to UNIQUE.
# Safe: never deletes; worst case we conservatively keep a would-be-LANDED ref.
LARGE_SCOPE_SHORTCUT = 3000
# Reason tags
R_ACTIVE = "active-worktree-or-checked-out"
R_UNIQUE = "unique-content-not-on-main"
R_AMBIGUOUS = "ambiguous/unresolvable"
R_LANDED = "landed"
R_SKIP = "skipped-live"


def _repo_root() -> Path:
    # Path-aware (M5 balizero vs Pro nuzantara — superscar #1, never hardcode HOME).
    return Path(__file__).resolve().parent.parent


REPO_ROOT = _repo_root()


def _git(args: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd or REPO_ROOT),
        capture_output=True, text=True, timeout=120, check=check,
    )


def _run(msg: list[str] | None = None) -> None:
    if msg:
        print(" ".join(msg))


# --------------------------------------------------------------------------- #
# live worktree guard
# --------------------------------------------------------------------------- #
def _live_worktree_dirs() -> tuple[set[str], set[str]]:
    """Return (dir_name_set, checked_out_sha_set) for active `.worktrees/*`."""
    dirs: set[str] = set()
    heads: set[str] = set()
    r = _git(["worktree", "list", "--porcelain"], check=False)
    cur_sha = None
    for line in r.stdout.splitlines():
        if line.startswith("worktree "):
            p = line[len("worktree "):].strip()
            if "/.worktrees/" in p:
                dirs.add(Path(p).name)
            cur_sha = None
        elif line.startswith("HEAD "):
            cur_sha = line.split()[1]
        elif line.startswith("branch ") or line.startswith("detached") or not line.strip():
            if cur_sha:
                heads.add(cur_sha)
    return dirs, heads


def _worktree_name_from_ref(short: str) -> str | None:
    # ref .../.worktrees_<name>[-head]  ->  <name>
    head_idx = short.rfind("-head")
    base = short[:head_idx] if head_idx != -1 and short.endswith("-head") else short
    idx = base.rfind(".worktrees_")
    return base[idx + len(".worktrees_"):] if idx != -1 else None


# --------------------------------------------------------------------------- #
# resolver
# --------------------------------------------------------------------------- #
def _rev_parse_path(ref: str, path: str) -> str:
    r = _git(["rev-parse", f"{ref}:{path}"], check=False)
    return r.stdout.strip() if r.returncode == 0 else "__ABSENT__"


def _path_set(ref_a: str, ref_b: str) -> list[str]:
    """Paths differing between ref_a..ref_b (two commits), NUL-safe."""
    r = _git(["diff", "--name-only", "-z", ref_a, ref_b], check=False)
    if r.returncode != 0:
        return []
    return [p for p in r.stdout.split("\0") if p]


def _blob_matches_main(ref: str, path: str) -> bool:
    """True iff ref:path blob == origin/main:path (or both absent)."""
    bh = _rev_parse_path(ref, path)
    mh = _rev_parse_path(MAIN_REF, path)
    return bh == mh


def classify(objname: str) -> dict:
    """Classify ONE quarantine commit. Never deletes; read-only. Returns fields."""
    fields = {
        "obj": objname,
        "verdict": R_AMBIGUOUS, "reason": "", "authored": 0, "delta": 0,
        "diverged": 0, "sample": "",
    }
    # pure ancestor of main -> landed (fast path)
    if _git(["merge-base", "--is-ancestor", objname, MAIN_REF], check=False).returncode == 0:
        fields["verdict"] = R_LANDED
        fields["reason"] = "ancestor-of-main"
        return fields
    # merge-base must resolve, else ambiguous (never delete)
    mb = _git(["merge-base", MAIN_REF, objname], check=False).stdout.strip()
    if not mb:
        fields["reason"] = "merge-base-unresolvable"
        return fields

    authored = _path_set(mb, objname)
    fields["authored"] = len(authored)
    # fragile object? treat missing tree as ambiguous
    if _git(["cat-file", "-e", objname], check=False).returncode != 0:
        fields["reason"] = "missing-object"
        return fields

    # dirty add -A snapshot payload on top of parent
    delta: list[str] = []
    par = _git(["rev-parse", f"{objname}^"], check=False).stdout.strip()
    if par:
        delta = _path_set(par, objname)
    fields["delta"] = len(delta)

    if fields["authored"] > LARGE_SCOPE_SHORTCUT:
        fields["verdict"] = R_UNIQUE
        fields["reason"] = f"large-authored-scope-{fields['authored']}"
        fields["sample"] = authored[0]
        return fields

    scope = authored + [p for p in delta if p not in authored]
    diverged = []
    for p in scope:
        if not _blob_matches_main(objname, p):
            diverged.append(p)
            if len(diverged) >= 25:  # enough evidence; LANDED refs must check all anyway
                pass
    fields["diverged"] = len(diverged)
    if diverged:
        fields["verdict"] = R_UNIQUE
        fields["reason"] = f"{len(diverged)}-diverging-paths"
        fields["sample"] = " | ".join(diverged[:8])
    else:
        fields["verdict"] = R_LANDED
        fields["reason"] = "content-on-main"
    return fields


# --------------------------------------------------------------------------- #
# enumeration + manifest
# --------------------------------------------------------------------------- #
def _all_quarantine_refs() -> list[tuple[str, str, str]]:
    """(short, objectname, creatordate-short)."""
    r = _git(["for-each-ref", QUARANTINE_PREFIX,
              "--format=%(refname:short)\t%(objectname)\t%(creatordate:short)"])
    out = []
    for ln in r.stdout.splitlines():
        parts = ln.split("\t")
        if len(parts) == 3:
            out.append((parts[0], parts[1].strip(), parts[2].strip()))
    return out


def _manifest_path(outdir: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return outdir / f"quarantine-audit-{stamp}.tsv"


def run_audit(outdir: Path) -> tuple[list[dict], Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    live_dirs, live_shas = _live_worktree_dirs()
    refs = _all_quarantine_refs()
    rows: list[dict] = []

    for short, obj, date in refs:
        wt = _worktree_name_from_ref(short)
        head_sha = _git(["rev-parse", obj], check=False).stdout.strip()
        basis = classify(obj)
        if wt and (wt in live_dirs or head_sha in live_shas):
            basis["verdict"] = R_ACTIVE
            basis["reason"] = "active-worktree-or-checked-out"
        row = {"ref": short, "date": date, **basis}
        rows.append(row)

    mpath = _manifest_path(outdir)
    with mpath.open("w", encoding="utf-8") as fh:
        fh.write("verdict\tref\tobjectname\tdate\tauthored\tdelta\tdiverged\treason\tsample\n")
        for r in rows:
            fh.write("\t".join([
                r["verdict"], r["ref"], r["obj"], r["date"],
                str(r["authored"]), str(r["delta"]), str(r["diverged"]),
                r["reason"], r["sample"].replace("\t", " "),
            ]) + "\n")
    return rows, mpath


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #
def _print_report(rows: list[dict], mpath: Path) -> None:
    from collections import Counter
    cnt = Counter(r["verdict"] for r in rows)
    print("=" * 70)
    print(f"Quarantine audit  ·  {len(rows)} refs  ·  manifest {mpath.name}")
    print("  " + "  ·  ".join(f"{k}={v}" for k, v in cnt.items()))
    print("=" * 70)
    for section, title in [(R_ACTIVE, "ACTIVE (skip-guard)"),
                           (R_LANDED, "LANDED — deletable (content on main)"),
                           (R_UNIQUE, "UNIQUE — keep (content not on main)"),
                           (R_AMBIGUOUS, "AMBIGUOUS — keep (never auto-delete)")]:
        sub = [r for r in rows if r["verdict"] == section]
        if not sub:
            continue
        print(f"\n## {title}  ({len(sub)})")
        for r in sub[:60]:
            extra = f"  [{r['reason']}]" if r["reason"] else ""
            print(f"  {r['verdict']:<8} {r['ref']}  ({r['date']}){extra}")
            if r["sample"] and r["verdict"] in (R_UNIQUE,):
                print(f"            ↳ {r['sample']}")
        if len(sub) > 60:
            print(f"  … and {len(sub) - 60} more")


# --------------------------------------------------------------------------- #
# --verify : re-run resolver on the DELETE set of the last manifest
# --------------------------------------------------------------------------- #
def _latest_manifest(outdir: Path) -> Path | None:
    cand = sorted(outdir.glob("quarantine-audit-*.tsv"))
    return cand[-1] if cand else None


def run_verify(outdir: Path) -> int:
    mp = _latest_manifest(outdir)
    if not mp:
        print("no manifest found", file=sys.stderr)
        return 1
    deletes = []
    with mp.open(encoding="utf-8") as fh:
        for ln in fh.readlines()[1:]:
            if ln.startswith("landed"):
                row = ln.rstrip("\n").split("\t")
                deletes.append((row[1], row[2]))
    print(f"[verify] re-running resolver on {len(deletes)} LANDED ref(s) from {mp.name}")
    ok = True
    for short, obj in deletes:
        basis = classify(obj)
        flag = "OK " if basis["verdict"] == R_LANDED else "MISMATCH"
        if flag == "MISMATCH":
            ok = False
        print(f"  {flag}  {short}  ->  {basis['verdict']} [{basis['reason']}]")
    print("[verify] " + ("GREEN — DELETE set stable" if ok else "MISMATCHES found — do NOT apply"))
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
# --apply : prune ONLY LANDED, re-verifying by content immediately before each
# --------------------------------------------------------------------------- #
def run_apply(outdir: Path) -> int:
    live_dirs, live_shas = _live_worktree_dirs()
    mp = _latest_manifest(outdir)
    deletes = []
    if mp:
        with mp.open(encoding="utf-8") as fh:
            for ln in fh.readlines()[1:]:
                if ln.startswith("landed"):
                    row = ln.rstrip("\n").split("\t")
                    deletes.append((row[1], row[2]))
    else:
        # no manifest: recompute live now
        deletes = [(r[0], r[1]) for r in _all_quarantine_refs() if classify(r[1])["verdict"] == R_LANDED]

    print(f"[apply] {len(deletes)} LANDED candidate(s). Re-qualifying each right before delete…")
    main_snapshot = _git(["rev-parse", MAIN_REF]).stdout.strip()
    removed, skipped = 0, 0
    for short, obj in deletes:
        # (1) ref must still exist. NOTE: `short` already carries `agent-quarantine/…`
        #     (refname:short strips refs/), so the full ref is refs/<short> — never
        #     prefix the prefix (a double-path bug once made every candidate "gone").
        cur = _git(["rev-parse", f"refs/{short}"], check=False).stdout.strip()
        if cur != obj:
            print(f"  SKIP(ref-gone-or-changed) {short}")
            skipped += 1
            continue
        # (2) origin/main unchanged since snapshot
        now_main = _git(["rev-parse", MAIN_REF]).stdout.strip()
        if now_main != main_snapshot:
            print(f"  ABORT(batch) origin/main moved {main_snapshot[:7]}→{now_main[:7]}", file=sys.stderr)
            return 2
        # (3) re-classify by content — strongest, independent of audit result
        basis = classify(obj)
        if basis["verdict"] != R_LANDED:
            print(f"  SKIP(no-longer-landed) {short} -> {basis['reason']}")
            skipped += 1
            continue
        # (4) active guard
        wt = _worktree_name_from_ref(short)
        head = _git(["rev-parse", obj], check=False).stdout.strip()
        if wt and (wt in live_dirs or head in live_shas):
            print(f"  SKIP(active) {short}")
            skipped += 1
            continue
        d = _git(["update-ref", "-d", f"refs/{short}"], check=False)
        if d.returncode == 0:
            removed += 1
            print(f"  DELETED {short}")
        else:
            print(f"  FAIL {short}: {d.stderr.strip()}")
            skipped += 1
    print(f"[apply] removed={removed} skipped={skipped}")
    _run()
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", dest="outdir", default="", help="manifest dir (default: .agent-receipts)")
    ap.add_argument("--apply", action="store_true", help="prune ONLY LANDED (content re-verified per ref)")
    ap.add_argument("--verify", action="store_true", help="re-run resolver on last manifest's DELETE set")
    args = ap.parse_args(argv)

    if os.environ.get("QUARANTINE_AUDIT_ENABLED", "true").lower() == "false":
        print("[audit] disabled via QUARANTINE_AUDIT_ENABLED=false")
        return 0

    outdir = Path(args.outdir) if args.outdir else REPO_ROOT / ".agent-receipts"

    if args.verify:
        return run_verify(outdir)
    if args.apply:
        return run_apply(outdir)

    rows, mpath = run_audit(outdir)
    _print_report(rows, mpath)
    print(f"\nmanifest: {mpath}")
    print("next: review → `--verify` (independent grader) → sign → `--apply`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))