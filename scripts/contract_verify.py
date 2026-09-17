#!/usr/bin/env python3
"""contract_verify.py — one predicate, run identically by every caller.

The preflight (slice 1, #6701) hard-coded three checks in bash. This is slice 2:
the checks become DATA in scripts/ci/contract_checks.yml — one row per REQUIRED
CI context that has actually killed a PR, each row naming the script CI itself
runs — and this binary runs that table against a tree. Nobody downstream writes
a proof command at grading time: the grader's mistakes were 3 of 6 refutations
in the audited window, and a command that is authored once and frozen cannot be
mis-authored twice.

Modes (mutually exclusive):
  --local            changed files of the current tree over origin/main (or
                     --files-from FILE, '-' = stdin); exit 1 when a check RAN and
                     FAILED. This is what .husky/pre-push consumes through
                     scripts/preflight_pack.sh.
  --head SHA         same predicate, on a detached worktree at SHA, diffed against
                     merge-base(origin/main, SHA).
  --replay PR...     run --head on each PR's head and CLASSIFY every context
                     against what CI actually did (from --expect's fixture, else
                     read live via gh). With --expect, exit 1 on any mismatch —
                     the fixture reds the moment the predicate drifts from CI's.
  --selftest         guilt + innocence for the loader, the matcher and the
                     classifier, offline.

Fail-open on INFRASTRUCTURE (missing binary, missing PyYAML, no git) → INCONCLUSIVE,
exit 0 in --local; fail-closed on VERDICTS (a check ran and failed) → exit 1. Same
posture as preflight_pack.sh, stated there, restated here.

Verdicts a --replay row can carry, and what each one means:
  RED                        local FAIL, CI red  — the preflight would have refused it
  GREEN                      local pass, CI green
  NOT-LOCALLY-PREVENTABLE    local pass or remote_only, CI red — honest: no local
                             run could have seen it (#6673: CI judged from the
                             BASE checkout, the HEAD-only observe script was
                             "malformed" there)
  DRIFT                      local FAIL, CI green — the table is stricter than
                             CI; the fixture reds so nobody ships that
  INCONCLUSIVE               a tool was missing; nothing was proven
  N/A                        remote_only row on a PR CI did not red there
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TABLE_PATH = Path(__file__).resolve().parent / "ci" / "contract_checks.yml"
FILE_MODES = ("append", "each", "none")
BUILTINS = ("floor_brief", "pack_lint")
ORIGIN_MAIN = "origin/main"


# ------------------------------------------------------------------ table

def load_table(path: Path = TABLE_PATH) -> Dict[str, Any]:
    """Load and VALIDATE the table. A malformed table is refused, never guessed at."""
    try:
        import yaml  # noqa: WPS433 — optional on purpose: missing → INCONCLUSIVE upstream
    except ImportError as exc:  # pragma: no cover — exercised by --local's fail-open path
        raise RuntimeError("PyYAML is not importable; the table cannot be read") from exc
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    validate_table(data)
    return data


def validate_table(data: Any) -> None:
    if not isinstance(data, dict) or not isinstance(data.get("contexts"), list):
        raise ValueError("table root must be a mapping with a `contexts:` list")
    seen = set()
    for row in data["contexts"]:
        ctx = row.get("context")
        if not isinstance(ctx, str) or not ctx.strip():
            raise ValueError("every row needs a non-empty `context:` (the exact CI check name)")
        if ctx in seen:
            raise ValueError(f"duplicate context {ctx!r}")
        seen.add(ctx)
        has_checks = bool(isinstance(row.get("checks"), list) and row["checks"])
        has_remote = bool(isinstance(row.get("remote_only"), str) and row["remote_only"].strip())
        if has_checks == has_remote:
            raise ValueError(f"{ctx!r}: exactly one of `checks:` or `remote_only:` — a row is local OR honestly remote, never both, never neither")
        for chk in row.get("checks") or []:
            cid = chk.get("id")
            if not cid:
                raise ValueError(f"{ctx!r}: every check needs an `id:`")
            if not isinstance(chk.get("governs"), list) or not chk["governs"]:
                raise ValueError(f"{ctx!r}/{cid}: `governs:` must list at least one glob")
            if bool(chk.get("argv")) == bool(chk.get("builtin")):
                raise ValueError(f"{ctx!r}/{cid}: exactly one of `argv:` or `builtin:`")
            if chk.get("builtin") and chk["builtin"] not in BUILTINS:
                raise ValueError(f"{ctx!r}/{cid}: unknown builtin {chk['builtin']!r}")
            if chk.get("argv") and chk.get("files", "append") not in FILE_MODES:
                raise ValueError(f"{ctx!r}/{cid}: `files:` must be one of {FILE_MODES}")


# ---------------------------------------------------------------- matching

def glob_to_re(pattern: str) -> "re.Pattern[str]":
    """`**` crosses directories, `*` and `?` never do. Anchored at both ends."""
    out, i = [], 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?"); i += 3; continue
        if pattern.startswith("**", i):
            out.append(".*"); i += 2; continue
        if c == "*":
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def governed(check: Dict[str, Any], files: List[str]) -> List[str]:
    pats = [glob_to_re(g) for g in check["governs"]]
    return [f for f in files if any(p.match(f) for p in pats)]


# ----------------------------------------------------------------- running

class Result:
    __slots__ = ("context", "check", "status", "output", "files", "quiet")

    def __init__(self, context: str, check: str, status: str, output: str = "", files: Optional[List[str]] = None):
        self.context, self.check, self.status, self.output, self.files = context, check, status, output, files or []
        self.quiet = False  # set from the row's `quiet:` — a PASS on a universal row says nothing

    def as_dict(self) -> Dict[str, Any]:
        return {"context": self.context, "check": self.check, "status": self.status, "output": self.output, "files": self.files}


# C4 (found shipping this PR, 2026-09-18): every subprocess this module spawns — git,
# gh, and any argv check (pytest for pending-arms-ledger-shape included) — runs during
# a real `git push`, where git exports these to hook scripts so THEY operate on the
# right repo. Inherited by a nested `git init`/`git add -A` in a pytest tmp-repo
# fixture (scripts/tests/test_pending_arms_ref.py), those same vars point the nested
# git at the OUTER repo instead of the fresh tmp one — `git add -A` there then fails
# (exit 128) or silently touches the wrong tree. Reproduced by setting these vars
# before invoking pytest directly, outside any hook. Scrubbed once here rather than in
# every check that happens to shell out to git.
_GIT_ENV_POLLUTANTS = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_PREFIX",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_QUARANTINE_PATH",
)


def _clean_env() -> Dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in _GIT_ENV_POLLUTANTS}


def _run(argv: List[str], cwd: Path) -> Tuple[Optional[int], str]:
    """(exit code or None when the binary is missing, combined output)."""
    try:
        p = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, env=_clean_env())
    except FileNotFoundError:
        return None, f"{argv[0]}: not found on PATH"
    return p.returncode, (p.stdout + p.stderr).strip()


def _git(cwd: Path, *args: str) -> str:
    p = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, env=_clean_env())
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def run_argv_check(ctx: str, chk: Dict[str, Any], root: Path, files: List[str]) -> Result:
    # C2 (PENDING-ARMS contract-verify-ci-input-parity): the changed-file list carries
    # deletions now, as CI's does. A script that takes FILES gets only the ones that exist
    # in this tree — CI's R1 diffs with --diff-filter=AM for the same reason.
    mode = chk.get("files", "append")
    if mode != "none":
        files = [f for f in files if (root / f).is_file()]
        if not files:
            return Result(ctx, chk["id"], "PASS", "only deletions in the governed set — nothing to run", files)
    runs = [list(chk["argv"]) + files] if mode == "append" else \
           [list(chk["argv"]) + [f] for f in files] if mode == "each" else [list(chk["argv"])]
    outputs, failed = [], False
    for argv in runs:
        rc, out = _run(argv, root)
        if rc is None:
            return Result(ctx, chk["id"], "INCONCLUSIVE", out, files)
        if rc != 0:
            failed = True
            outputs.append(out)
    return Result(ctx, chk["id"], "FAIL" if failed else "PASS", "\n".join(outputs), files)


def _diff_files(root: Path, base: str, head: str) -> Tuple[Path, Path, Path]:
    """Write CI's three inputs exactly as harness-floor.yml does: changed files (no
    filter — a deletion still contributes to the floor, C2), numstat, and the -U0 patch
    of .github/workflows/ that lets the floor exempt a first-party pin-only bump (C1)."""
    tmp = Path(tempfile.mkdtemp(prefix="contract-verify-"))
    (tmp / "changed-files.txt").write_text(_git(root, "diff", "--name-only", base, head), encoding="utf-8")
    (tmp / "numstat.txt").write_text(_git(root, "diff", "--no-renames", "--numstat", base, head), encoding="utf-8")
    (tmp / "workflow-patch.txt").write_text(_git(root, "diff", "--no-renames", "-U0", base, head, "--", ".github/workflows/"), encoding="utf-8")
    return tmp / "changed-files.txt", tmp / "numstat.txt", tmp / "workflow-patch.txt"


def floor_of(root: Path, changed_files: Path, numstat: Optional[Path], patch: Optional[Path]) -> Tuple[Optional[int], str]:
    """evidence_pack_lint --print-floor with CI's argv. (floor or None, raw output)."""
    argv = ["python3", "scripts/evidence_pack_lint.py", "--print-floor", "--changed-files-file", str(changed_files)]
    if numstat is not None:
        argv += ["--numstat-file", str(numstat)]
    if patch is not None and patch.stat().st_size > 0:
        argv += ["--patch-file", str(patch)]
    rc, out = _run(argv, root)
    if rc is None or rc != 0 or not out.strip().isdigit():
        return None, f"--print-floor rc={rc}: {out}"
    return int(out.strip()), out


def run_floor_brief(ctx: str, chk: Dict[str, Any], root: Path, files: List[str], span: Optional[Tuple[str, str]]) -> Result:
    """harness-floor.yml Steps 3+5b+7a: floor >= 2 with no diff-touched brief = FAIL."""
    if not (root / "scripts/evidence_pack_lint.py").is_file() or not (root / "scripts/ci/evidence_paths.py").is_file():
        return Result(ctx, chk["id"], "INCONCLUSIVE", "evidence_pack_lint.py / evidence_paths.py not in this tree", files)
    if span:
        cf, ns, patch = _diff_files(root, *span)
    else:
        tmp = Path(tempfile.mkdtemp(prefix="contract-verify-"))
        cf = tmp / "changed-files.txt"; cf.write_text("\n".join(files) + "\n", encoding="utf-8")
        ns = patch = None  # no diff span → path-only floor, exactly evidence_pack_lint's documented fallback
    floor_n, floor = floor_of(root, cf, ns, patch)
    if floor_n is None:
        return Result(ctx, chk["id"], "INCONCLUSIVE", floor, files)
    rc, brief = _run(["python3", "scripts/ci/evidence_paths.py", "--resolve", "brief", "--changed-files-file", str(cf)], root)
    if rc != 0:
        return Result(ctx, chk["id"], "FAIL", f"evidence_paths --resolve brief: {brief}", files)
    changed = set(cf.read_text(encoding="utf-8").split())
    brief = brief.strip()
    if floor_n >= 2 and brief not in changed:
        return Result(ctx, chk["id"], "FAIL",
                      f"deterministic floor is {floor_n} but this diff carries no {brief} — CI reds 'Harness floor recompute' on exactly this (a floor>=2 diff needs a brief declaring gear>={floor_n})", files)
    return Result(ctx, chk["id"], "PASS", f"floor {floor_n}, brief {'present' if brief in changed else 'not required'}", files)


def run_pack_lint(ctx: str, chk: Dict[str, Any], root: Path, files: List[str], span: Optional[Tuple[str, str]]) -> Result:
    """harness-floor.yml Step 7b: stage THIS diff's pack+brief and lint them with CI's argv."""
    if not (root / "scripts/evidence_pack_lint.py").is_file():
        return Result(ctx, chk["id"], "INCONCLUSIVE", "evidence_pack_lint.py not in this tree", files)
    if span:
        cf, ns, _patch = _diff_files(root, *span)
    else:
        tmp = Path(tempfile.mkdtemp(prefix="contract-verify-")); cf = tmp / "changed-files.txt"; ns = None
        cf.write_text("\n".join(files) + "\n", encoding="utf-8")
    changed = cf.read_text(encoding="utf-8").split()
    paths = {}
    for kind in ("pack", "brief"):
        rc, out = _run(["python3", "scripts/ci/evidence_paths.py", "--resolve", kind, "--changed-files-file", str(cf)], root)
        if rc != 0:
            return Result(ctx, chk["id"], "FAIL", f"evidence_paths --resolve {kind}: {out}", files)
        paths[kind] = out.strip()
    if paths["pack"] not in changed:
        return Result(ctx, chk["id"], "PASS", "no pack authored by this diff — nothing to lint", files)
    stage = Path(tempfile.mkdtemp(prefix="contract-verify-evidence-")); (stage / "evidence").mkdir()
    for kind, path in paths.items():
        src = root / path
        if not src.is_file():
            return Result(ctx, chk["id"], "FAIL", f"{path} is named by this diff but absent from the tree", files)
        shutil.copy(src, stage / "evidence" / f"{kind}.yml")
    argv = ["python3", "scripts/evidence_pack_lint.py", str(stage / "evidence/pack.yml"), "--repo-root", str(stage),
            "--changed-files-file", str(cf), "--source-path", paths["pack"], "--brief-source-path", paths["brief"]]
    if ns is not None:
        argv += ["--numstat-file", str(ns)]
    rc, out = _run(argv, root)
    if rc is None:
        return Result(ctx, chk["id"], "INCONCLUSIVE", out, files)
    return Result(ctx, chk["id"], "PASS" if rc == 0 else "FAIL", out, files)


def verify_tree(table: Dict[str, Any], root: Path, files: List[str], span: Optional[Tuple[str, str]] = None) -> List[Result]:
    """Run every applicable check of every local row against `root`. Rows whose governed
    set is empty in this diff are NOT run — silence is the scoping promise of slice 1."""
    results: List[Result] = []
    for row in table["contexts"]:
        for chk in row.get("checks") or []:
            hit = governed(chk, files)
            if not hit:
                continue
            if chk.get("builtin") == "floor_brief":
                r = run_floor_brief(row["context"], chk, root, hit, span)
            elif chk.get("builtin") == "pack_lint":
                r = run_pack_lint(row["context"], chk, root, hit, span)
            else:
                r = run_argv_check(row["context"], chk, root, hit)
            r.quiet = bool(chk.get("quiet"))
            results.append(r)
    return results


# ------------------------------------------------------------- classifying

def classify(row: Dict[str, Any], results: List[Result], ci_red: bool) -> str:
    if row.get("remote_only"):
        return "NOT-LOCALLY-PREVENTABLE" if ci_red else "N/A"
    statuses = [r.status for r in results if r.context == row["context"]]
    if "FAIL" in statuses:
        local = "FAIL"
    elif "INCONCLUSIVE" in statuses:
        local = "INCONCLUSIVE"  # C3: one tool missing = nothing proven for this context, whatever its siblings said
    else:
        local = "PASS"  # PASS, or silent (nothing governed) — both mean "local sees nothing wrong"
    if local == "INCONCLUSIVE":
        return "INCONCLUSIVE"
    if ci_red:
        return "RED" if local == "FAIL" else "NOT-LOCALLY-PREVENTABLE"
    return "DRIFT" if local == "FAIL" else "GREEN"


# ------------------------------------------------------------------ modes

def changed_over_main(root: Path, head: str = "HEAD") -> Tuple[List[str], Tuple[str, str]]:
    base = _git(root, "merge-base", ORIGIN_MAIN, head).strip()
    files = _git(root, "diff", "--name-only", base, head).split()
    return files, (base, head)


def print_results(results: List[Result], quiet_pass: bool) -> int:
    rc = 0
    for r in results:
        if r.status == "PASS":
            if not (quiet_pass or r.quiet):
                print(f"   ✅ [{r.check}] {r.context}")
        elif r.status == "INCONCLUSIVE":
            print(f"   ⚠️  [{r.check}] INCONCLUSIVE — {r.output}")
        else:
            rc = 1
            print(f"   ❌ [{r.check}] this push would red the REQUIRED check '{r.context}':")
            for line in r.output.splitlines():
                print(f"        {line}")
    return rc


def mode_local(args: argparse.Namespace, root: Path) -> int:
    try:
        table = load_table(args.table)
    except RuntimeError as exc:
        print(f"⚠️  contract_verify INCONCLUSIVE — {exc}")
        return 0
    span: Optional[Tuple[str, str]] = None
    if args.span:
        base, head = args.span
        files, span = _git(root, "diff", "--name-only", base, head).split(), (base, head)
    elif args.files_from:
        text = sys.stdin.read() if args.files_from == "-" else Path(args.files_from).read_text(encoding="utf-8")
        files = sorted({ln.strip() for ln in text.splitlines() if ln.strip()})
    else:
        files, span = changed_over_main(root)
    results = verify_tree(table, root, files, span)
    if args.json:
        print(json.dumps([r.as_dict() for r in results], indent=2)); return 1 if any(r.status == "FAIL" for r in results) else 0
    return print_results(results, quiet_pass=False)


def with_worktree(root: Path, sha: str):
    """Context manager: a detached worktree at `sha`, removed afterwards."""
    class _WT:
        def __enter__(self):
            self.path = Path(tempfile.mkdtemp(prefix="contract-verify-wt-"))
            _git(root, "worktree", "add", "--detach", "--quiet", str(self.path), sha)
            return self.path

        def __exit__(self, *exc):
            subprocess.run(["git", "worktree", "remove", "--force", str(self.path)], cwd=str(root), capture_output=True, env=_clean_env())
    return _WT()


def verify_head(table: Dict[str, Any], root: Path, sha: str) -> List[Result]:
    base = _git(root, "merge-base", ORIGIN_MAIN, sha).strip()
    files = _git(root, "diff", "--name-only", base, sha).split()
    with with_worktree(root, sha) as wt:
        return verify_tree(table, wt, files, (base, sha))


def mode_head(args: argparse.Namespace, root: Path) -> int:
    table = load_table(args.table)
    results = verify_head(table, root, args.head)
    if args.json:
        print(json.dumps([r.as_dict() for r in results], indent=2))
    else:
        print_results(results, quiet_pass=False)
    return 1 if any(r.status == "FAIL" for r in results) else 0


def _ensure_commit(root: Path, pr: int, sha: str) -> None:
    if subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=str(root), capture_output=True, env=_clean_env()).returncode == 0:
        return
    _git(root, "fetch", "--no-tags", "origin", f"refs/pull/{pr}/head")
    if subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=str(root), capture_output=True, env=_clean_env()).returncode != 0:
        raise RuntimeError(f"#{pr}: head {sha} is not reachable even after fetching refs/pull/{pr}/head")


def _gh_json(args: List[str]) -> Any:
    p = subprocess.run(["gh", *args], capture_output=True, text=True, env=_clean_env())
    if p.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)}: {p.stderr.strip()}")
    return json.loads(p.stdout)


def _live_pr(pr: int) -> Tuple[str, List[str]]:
    """(head sha, contexts CI red) read from GitHub — never attested by anyone."""
    view = _gh_json(["pr", "view", str(pr), "--json", "headRefOid,statusCheckRollup"])
    red = []
    for c in view.get("statusCheckRollup") or []:
        concl = (c.get("conclusion") or c.get("state") or "").upper()
        if concl in ("FAILURE", "ERROR"):
            red.append(c.get("name") or c.get("context") or "?")
    return view["headRefOid"], sorted(set(red))


def mode_replay(args: argparse.Namespace, root: Path) -> int:
    table = load_table(args.table)
    expect: Dict[int, Dict[str, Any]] = {}
    if args.expect:
        import yaml
        fx = yaml.safe_load(Path(args.expect).read_text(encoding="utf-8"))
        expect = {int(k): v for k, v in (fx.get("heads") or {}).items()}
    prs = [int(p) for p in args.replay] or sorted(expect)
    mismatches, report = 0, []
    for pr in prs:
        fx = expect.get(pr)
        if fx:
            sha, ci_red = fx["sha"], list(fx.get("ci_red") or [])
        else:
            sha, ci_red = _live_pr(pr)
        _ensure_commit(root, pr, sha)
        results = verify_head(table, root, sha)
        verdicts = {row["context"]: classify(row, results, row["context"] in ci_red) for row in table["contexts"]}
        report.append({"pr": pr, "sha": sha, "ci_red": ci_red, "verdicts": verdicts,
                       "results": [r.as_dict() for r in results if r.status != "PASS"]})
        print(f"#{pr} {sha[:10]}")
        for ctx, v in verdicts.items():
            if v == "N/A" and not (fx and ctx in (fx.get("expect") or {})):
                continue
            want = (fx or {}).get("expect", {}).get(ctx)
            mark = "" if want is None else ("  ✓" if want == v else f"  ✗ expected {want}")
            if want is not None and want != v:
                mismatches += 1
            print(f"   {v:<24} {ctx}{mark}")
        for r in results:
            if r.status == "FAIL":
                lines = r.output.splitlines() or ["(no output)"]
                first = next((ln for ln in lines if "FAIL" in ln or "error" in ln.lower()), lines[0])
                print(f"      └ {r.check}: {first.strip()[:160]}")
    if args.json:
        print(json.dumps(report, indent=2))
    if expect:
        print(f"\n{'OK' if mismatches == 0 else 'MISMATCH'} — {len(prs)} head(s), {mismatches} verdict(s) differ from {args.expect}")
    return 1 if mismatches else 0


# --------------------------------------------------------------- selftest

def selftest() -> int:
    failures = []

    def check(name: str, cond: bool) -> None:
        print(f"  {'✅' if cond else '❌'} {name}")
        if not cond:
            failures.append(name)

    # matcher: guilt + innocence
    check("** crosses directories", bool(glob_to_re("research/**/*.md").match("research/a/b/c.md")))
    check("** also matches zero directories", bool(glob_to_re("research/**/*.md").match("research/c.md")))
    check("* never crosses a directory", not glob_to_re("research/*.md").match("research/a/c.md"))
    check("evidence pack glob hits per-PR packs", bool(glob_to_re("evidence/**/pack.yml").match("evidence/2026-09/x-abc/pack.yml")))
    check("evidence pack glob ignores the brief", not glob_to_re("evidence/**/pack.yml").match("evidence/2026-09/x-abc/brief.yml"))
    # loader refuses malformed tables
    for bad, why in (
        ({"contexts": [{"context": "x"}]}, "a row with neither checks nor remote_only"),
        ({"contexts": [{"context": "x", "remote_only": "r", "checks": [{"id": "a", "governs": ["**"], "argv": ["true"]}]}]}, "a row with both"),
        ({"contexts": [{"context": "x", "checks": [{"id": "a", "governs": ["**"], "argv": ["true"], "files": "sometimes"}]}]}, "an unknown files: mode"),
        ({"contexts": [{"context": "x", "checks": [{"id": "a", "governs": ["**"], "builtin": "magic"}]}]}, "an unknown builtin"),
        ({"contexts": [{"context": "x", "remote_only": "r"}, {"context": "x", "remote_only": "r"}]}, "a duplicate context"),
    ):
        try:
            validate_table(bad); ok = False
        except ValueError:
            ok = True
        check(f"loader refuses {why}", ok)
    # the shipped table itself loads
    try:
        table = load_table(); check("scripts/ci/contract_checks.yml loads and validates", True)
    except Exception as exc:  # noqa: BLE001
        table = {"contexts": []}
        check(f"scripts/ci/contract_checks.yml loads and validates ({exc})", False)
    # classifier matrix
    row = {"context": "c", "checks": [{"id": "k"}]}
    fail, ok_, inc = Result("c", "k", "FAIL"), Result("c", "k", "PASS"), Result("c", "k", "INCONCLUSIVE")
    check("local FAIL + CI red = RED", classify(row, [fail], True) == "RED")
    check("local PASS + CI red = NOT-LOCALLY-PREVENTABLE", classify(row, [ok_], True) == "NOT-LOCALLY-PREVENTABLE")
    check("silent + CI red = NOT-LOCALLY-PREVENTABLE", classify(row, [], True) == "NOT-LOCALLY-PREVENTABLE")
    check("local FAIL + CI green = DRIFT", classify(row, [fail], False) == "DRIFT")
    check("local PASS + CI green = GREEN", classify(row, [ok_], False) == "GREEN")
    check("INCONCLUSIVE never becomes a verdict", classify(row, [inc], True) == "INCONCLUSIVE" and classify(row, [inc], False) == "INCONCLUSIVE")
    check("C3: PASS + INCONCLUSIVE siblings = INCONCLUSIVE, never GREEN", classify(row, [ok_, inc], False) == "INCONCLUSIVE" and classify(row, [ok_, inc], True) == "INCONCLUSIVE")
    # C1/C2 against the REAL floor: the inputs, not a re-implementation
    root = Path(__file__).resolve().parents[1]
    if (root / "scripts/evidence_pack_lint.py").is_file():
        tmp = Path(tempfile.mkdtemp(prefix="contract-verify-selftest-"))
        cf = tmp / "cf.txt"; cf.write_text(".github/workflows/x.yml\n", encoding="utf-8")
        patch = tmp / "patch.txt"; patch.write_text(
            "diff --git a/.github/workflows/x.yml b/.github/workflows/x.yml\n--- a/.github/workflows/x.yml\n+++ b/.github/workflows/x.yml\n"
            "@@ -10 +10 @@\n-      - uses: actions/checkout@v7\n+      - uses: actions/checkout@v8\n", encoding="utf-8")
        check("C1: a pin-only workflow bump floors 1 WITH --patch-file (what CI computes)", floor_of(root, cf, None, patch)[0] == 1)
        check("C1: the same list without the patch floors 3 (the false refusal, now gone)", floor_of(root, cf, None, None)[0] == 3)
        cf2 = tmp / "cf2.txt"; cf2.write_text("apps/backend-rag/backend/db/migrations_v2/000_gone.sql\n", encoding="utf-8")
        check("C2: a deleted hot-zone path still floors 3 (the list is unfiltered)", floor_of(root, cf2, None, None)[0] == 3)
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        check("C1/C2 floor rows need scripts/evidence_pack_lint.py (not in this tree)", False)
    # C4 (found shipping this PR): a subprocess this module spawns must never inherit
    # GIT_DIR/GIT_WORK_TREE/etc. — a real `git push` sets them for hook scripts, and a
    # child that does its own `git init` in a tmp dir (test_pending_arms_ref.py's
    # fixture) would otherwise operate on the OUTER repo instead of its own tmp one.
    check("C4: _clean_env() strips every GIT_* plumbing pollutant", not (set(_clean_env()) & set(_GIT_ENV_POLLUTANTS)))
    _poisoned = dict(os.environ, GIT_DIR="/nonexistent/should-be-stripped")
    _dirty_check = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=str(root), capture_output=True, text=True, env=_poisoned)
    _scrubbed = {k: v for k, v in _poisoned.items() if k not in _GIT_ENV_POLLUTANTS}
    _clean_check = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=str(root), capture_output=True, text=True, env=_scrubbed)
    check("C4: with GIT_DIR poisoned, an unscrubbed env breaks git in this tree", _dirty_check.returncode != 0)
    check("C4: the same command with a scrubbed env still resolves this tree", _clean_check.returncode == 0)
    check("remote_only + CI red = NOT-LOCALLY-PREVENTABLE", classify({"context": "c", "remote_only": "x"}, [], True) == "NOT-LOCALLY-PREVENTABLE")
    check("remote_only + CI green = N/A", classify({"context": "c", "remote_only": "x"}, [], False) == "N/A")
    # a missing binary is INCONCLUSIVE, never PASS and never FAIL
    r = run_argv_check("c", {"id": "k", "argv": ["definitely-not-a-binary-9f3a"], "files": "none"}, Path("."), ["x"])
    check("missing binary = INCONCLUSIVE", r.status == "INCONCLUSIVE")
    # every killed PR in the table is pinned in the replay fixture
    fixture = Path(__file__).resolve().parent / "tests" / "fixtures" / "contract_replay_expected.yml"
    try:
        import yaml
        heads = set(int(k) for k in (yaml.safe_load(fixture.read_text(encoding="utf-8")).get("heads") or {}))
        killed = {int(n) for row in table["contexts"] for n in (row.get("killed") or [])}
        check(f"every `killed:` PR is pinned in the replay fixture (missing: {sorted(killed - heads)})", killed <= heads)
    except Exception as exc:  # noqa: BLE001
        check(f"replay fixture readable ({exc})", False)
    print(f"\n  {len(failures)} failure(s)")
    return 1 if failures else 0


# ------------------------------------------------------------------- main

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="contract_verify.py", description=(__doc__ or "").splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--local", action="store_true", help="verify the current tree's diff over origin/main")
    mode.add_argument("--head", metavar="SHA", help="verify SHA in a detached worktree")
    mode.add_argument("--replay", nargs="*", metavar="PR", help="replay closed heads and classify each context")
    mode.add_argument("--selftest", action="store_true")
    ap.add_argument("--files-from", metavar="FILE", help="with --local: read the changed-file list from FILE ('-' = stdin); path-only floor, no size term")
    ap.add_argument("--span", nargs=2, metavar=("BASE", "HEAD"), help="with --local: diff BASE..HEAD instead of origin/main...HEAD (numstat-bearing)")
    ap.add_argument("--expect", metavar="FIXTURE", help="with --replay: pinned heads + expected verdicts; exit 1 on mismatch")
    ap.add_argument("--table", type=Path, default=TABLE_PATH)
    ap.add_argument("--json", action="store_true")
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(os.environ.get("CONTRACT_VERIFY_ROOT") or subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, env=_clean_env()).stdout.strip() or ".").resolve()
    if args.selftest:
        return selftest()
    if args.local:
        return mode_local(args, root)
    if args.head:
        return mode_head(args, root)
    return mode_replay(args, root)


if __name__ == "__main__":
    sys.exit(main())
