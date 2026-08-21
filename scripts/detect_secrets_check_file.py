#!/usr/bin/env python3
"""Verify ONE (or a few) specific file(s) locally against `detect-secrets`
— fail LOUD when the scan didn't actually cover the file you asked about,
never silently report "clean".

WHY THIS EXISTS
---------------
2026-08-21 (PR #4484 follow-up): local ad-hoc verification of a single
file's `detect-secrets` findings did `results.get('scripts/foo.py', [])`
— a fixed key ASSUMED to match. `detect-secrets` keys a finding by a path
relative to the invoking PROCESS's CWD, not to `--baseline`'s location and
not to the repo root. Scanning via an absolute path from a CWD that isn't
the file's own root (exactly what this repo's worktree-isolation hook
forces on compound `cd &&` commands) files the finding under a DIFFERENT
key (e.g. `.worktrees/<name>/scripts/foo.py`), and `.get(<wrong-key>, [])`
silently returns `[]` — a false "clean" read on a file that has a REAL,
unaudited finding. Proven by a controlled A/B (only the CWD varied, same
file, same freshly-verified baseline): both runs found the same 2 real
findings, only the dict key differed.

That specific mechanism is one symptom of a GENERAL disease, not the
disease itself: `results.get(<key>, default)` (or, per this tool's own
first draft, `key in results` / a single `samefile` sweep with nothing to
fall back on) makes "I looked and found nothing" and "I never actually
looked" produce the IDENTICAL observable value. An absent key is not
data — it's a missing measurement wearing the costume of an empty one.
`detect-secrets`' own `results` dict is structurally sparse (a file with
zero plugin matches gets NO entry — there is no separate "files examined"
manifest anywhere in its output), so a naive fix that only patches the
*known* failure modes (wrong CWD, wrong key) leaves the tool unable to
tell "genuinely clean" from "silently skipped for a reason nobody has
found yet" — precisely the shape CLAUDE.md's cicatrix superscar #2
("Esiste ≠ Armato") and #9 ("proxy che mente") both name. CI never hits
the wrong-CWD variant specifically — `actions/checkout` always sets CWD to
the repo root and this workflow has zero `working-directory` overrides
(verified 2026-08-21 by reading `.github/workflows/security.yml` end to
end, not assumed) — but that only closes ONE door; it says nothing about
the others. Full repro of the CWD mechanism: memory
`discovery_detect_secrets_keys_findings_by_invocation_cwd_2026_08_21`.

Class-audit (2026-08-21, same mandate — cures target the CLASS of
consumers, not the instance that broke): grepped every tracked consumer of
`.secrets.baseline` (`detect_secrets_check_unaudited.py`,
`detect_secrets_auto_triage.py`, `root_guard.py` — the last only lists the
filename as a protected string, doesn't parse `results`) and all 43
`scripts/{lint,check,verify}_*.py` + `*_audit.py` + `*_guard.py` files for
the same disease shape (a path/identifier-keyed lookup with a default that
silently reads as "clean"): ZERO other instances found. Both sanctioned
`detect-secrets` consumers already iterate `results.items()` — the disease
was isolated to this session's throwaway, never-committed verification
snippet, not to any shipped script.

WHAT IT DOES
------------
Runs `detect-secrets scan` on the given file(s) PLUS a synthetic canary
file against a SCRATCH COPY of the tracked baseline (`.secrets.baseline`
is never mutated), CWD pinned to the repo root — matching what CI's
`actions/checkout` always does. The canary is a positive control: a
secret-shaped literal, freshly written to a scratch dir inside the repo,
scanned in the exact same `detect-secrets` invocation as your real target
file(s). If detect-secrets doesn't flag the canary, NOTHING this
invocation reports as "clean" can be trusted — the whole scan is treated
as CANNOT-VERIFY, because a lookup that silently misses its target proves
nothing by being empty. Only once the canary IS found does an absent key
for one of YOUR files become trustworthy evidence of "scanned, genuinely
clean" rather than "silently never examined" — this is the same
guilt/innocence discipline this repo's other guards apply in `--selftest`,
run instead at RUNTIME, on every real invocation, because the failure
modes that matter here (wrong CWD today, something undiscovered tomorrow)
are exactly the ones a static test suite can't anticipate. The one gap the
canary itself cannot close: a file physically OUTSIDE the git repo being
scanned is invisible to `detect-secrets` with no error (proven directly —
see `selftest`), and the canary is always placed inside the repo, so it
can't probe that specific door; this tool checks for it separately and
still reports CANNOT-VERIFY rather than trusting an absent key there.

Exit codes: 0 clean+verified · 1 unaudited finding(s) · 2 CANNOT-VERIFY
(canary missed — this invocation's own detection proven unreliable — or a
target file is outside the repo, or doesn't exist) · 3 `detect-secrets`
itself failed to run.

This is a LOCAL PRE-FLIGHT convenience for the file(s) you're about to
commit — not a substitute for the real CI gate (`.github/workflows/
security.yml`'s `detect-secrets` job), which scans the whole tree with
`--exclude-files` patterns this tool doesn't apply.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(out.stdout.strip())


def find_results_for_file(
    results: dict[str, list[dict]], target: Path, scan_cwd: Path
) -> tuple[bool, list[dict]]:
    """Match `target` against every key in `results` by real filesystem
    identity (`os.path.samefile`, resolving each key against `scan_cwd`)
    — never by trusting a single assumed key string.

    Returns `(found, hits)`. `found=False` means NO key in `results`
    resolves to this file: the scan's own dict never actually covered it
    by this matcher's evidence alone. Callers must NOT read that as
    "clean" on its own — see `_evaluate`, which only trusts an absent key
    once a positive-control canary proves this invocation's detection
    actually works.
    """
    target_str = str(target)
    if not os.path.exists(target_str):
        return False, []
    for key, hits in results.items():
        candidate = str(scan_cwd / key)
        if not os.path.exists(candidate):
            continue
        try:
            if os.path.samefile(candidate, target_str):
                return True, hits
        except OSError:
            continue
    return False, []


_CANARY_SECRET_BODY = "kQ4tX8" + "cH2wL9dR6pS3" + "vN5u"  # synthetic, 22 chars, never a real credential — same shape as the GOCSPX guilt fixture below so it reliably trips the same plugins


def _write_canary(scratch_dir: Path) -> Path:
    """A synthetic, unambiguous secret-shaped literal, scanned in the SAME
    detect-secrets invocation as the caller's real target files. Its role
    is a positive control (same guilt/innocence discipline this repo's
    other guards apply in `--selftest`, applied here at RUNTIME instead):
    if detect-secrets doesn't flag THIS on a given invocation, nothing
    else it reports "clean" on that invocation can be trusted either —
    see `_evaluate`.
    """
    canary = scratch_dir / "_canary.py"
    canary.write_text(
        'OAUTH_CLIENT_SECRET = "GOCSPX-' + _CANARY_SECRET_BODY + '"\n', encoding="utf-8"
    )
    return canary


def _evaluate(
    results: dict[str, list[dict]],
    files: list[Path],
    canary: Path,
    repo_root: Path,
) -> int:
    """Pure decision logic given an already-produced `results` dict from a
    single `detect-secrets scan` invocation that included `canary`
    alongside `files`. Split out from `check_files` so the canary-gating
    behavior (selftest-covered below) can be unit-tested without a
    subprocess for every case.
    """
    # Resolve once up front: comparing an unresolved repo_root against a
    # resolved file path silently misjudges "inside" as "outside" whenever
    # a symlink sits in the prefix (e.g. macOS `/var` -> `/private/var`) —
    # caught live by this file's own selftest, not reasoned out in advance.
    repo_root = repo_root.resolve()

    canary_found, canary_hits = find_results_for_file(results, canary, repo_root)
    if not canary_found or not canary_hits:
        print(
            "❌ CANNOT-VERIFY (all files): this invocation's positive-control "
            "canary — a synthetic secret-shaped literal scanned in the SAME "
            "detect-secrets call as your file(s) — produced NO finding. That "
            "means this invocation cannot be trusted to report ANY finding, so "
            "an absent key for your file(s) is NOT evidence of clean: it may "
            "equally be evidence that detect-secrets silently skipped them. "
            "Investigate why the canary was missed (CWD? plugin config? a "
            "detect-secrets version regression?) before trusting this tool "
            "again.",
            file=sys.stderr,
        )
        return 2

    exit_code = 0
    for f in files:
        resolved = f.resolve()
        outside_repo = repo_root not in resolved.parents and resolved != repo_root
        if outside_repo:
            print(
                f"⚠️  {f}: CANNOT-VERIFY — the file is OUTSIDE the git repo "
                "detect-secrets scanned from (detect-secrets silently reports "
                "nothing for out-of-repo targets, no error — verified, not "
                "assumed: see this script's own selftest. A working canary "
                "cannot rule this out — the canary is always placed INSIDE "
                "the repo). This is NOT a clean result."
            )
            exit_code = max(exit_code, 2)
            continue

        found, hits = find_results_for_file(results, f, repo_root)
        if not found:
            # The canary already proved THIS invocation reports findings
            # when they exist. An absent key for an in-repo file is now
            # genuine evidence of "scanned, clean" — not a failed lookup
            # wearing the costume of one.
            print(f"✅ {f}: clean (0 findings — canary-verified this scan actually examined it)")
            continue

        unaudited = [h for h in hits if "is_secret" not in h]
        if unaudited:
            print(f"❌ {f}: {len(unaudited)} unaudited finding(s):")
            for h in unaudited:
                print(f"   line {h.get('line_number')}: {h.get('type')}")
            exit_code = max(exit_code, 1)
        else:
            print(f"✅ {f}: clean ({len(hits)} pre-audited finding(s) carried from baseline)")
    return exit_code


def check_files(files: list[Path], repo_root: Path | None = None) -> int:
    repo_root = repo_root or _repo_root()
    missing = [f for f in files if not f.exists()]
    if missing:
        for f in missing:
            print(f"❌ {f}: does not exist — cannot verify", file=sys.stderr)
        return 2

    real_baseline = repo_root / ".secrets.baseline"
    canary_dir = repo_root / f".detect_secrets_check_file_canary_{os.getpid()}"
    if canary_dir.exists():
        shutil.rmtree(canary_dir)
    canary_dir.mkdir()
    try:
        canary = _write_canary(canary_dir)

        with tempfile.TemporaryDirectory() as td:
            scratch_baseline = Path(td) / "baseline.json"
            scratch_baseline.write_text(
                real_baseline.read_text(encoding="utf-8"), encoding="utf-8"
            )

            proc = subprocess.run(
                ["detect-secrets", "scan", "--baseline", str(scratch_baseline)]
                + [str(f.resolve()) for f in files]
                + [str(canary.resolve())],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                print(
                    f"❌ detect-secrets itself failed (rc={proc.returncode}): "
                    f"{proc.stderr.strip()[:500]}",
                    file=sys.stderr,
                )
                return 3

            data = json.loads(scratch_baseline.read_text(encoding="utf-8"))

        results = data.get("results", {})
        return _evaluate(results, files, canary, repo_root)
    finally:
        shutil.rmtree(canary_dir, ignore_errors=True)


def selftest() -> int:
    """Guilt+innocence (real `detect-secrets`, including the canary path)
    plus pure unit cases for the matcher and the canary gate,
    mutation-verifiable.

    GOTCHA fixed while writing this (measured, not assumed): the scratch
    fixtures for the guilt/innocence pair CANNOT live under the system temp
    dir (`tempfile.TemporaryDirectory()`'s default) — `detect-secrets scan`
    silently returns ZERO results for a target file outside the git repo
    it's scanning from, no error, no warning. Verified directly: the exact
    same guilty literal produced a result keyed `.tmp_dsc_debug/guilty.py`
    when placed inside this repo's tree, and an EMPTY results dict when
    placed in `/tmp`. First draft of this selftest used system temp and
    both fixtures silently read CANNOT-VERIFY instead of GUILT/INNOCENCE —
    this tool's own test suite almost shipped with the same disease it
    exists to catch. Fixture dir is therefore a scratch subdirectory INSIDE
    the repo, removed in a `finally`.

    Second gap fixed while writing this: `find_results_for_file` reporting
    `found=False` was, on its own, indistinguishable between "this file is
    genuinely clean" and "this scan silently never covered it" —
    `detect-secrets`' `results` dict has NO separate manifest of files
    examined, only the sparse dict of files with matches. Patching only
    the two known failure modes (wrong CWD, wrong key) would have left
    every OTHER unknown silent-skip mode reading as false-clean. The
    canary in `_evaluate` closes this generally: it doesn't ask "did I
    correctly look up this ONE file", it asks "does this scan report
    findings AT ALL, proven live, this run" — the CANARY-GATE cases below
    are the mutation-relevant tests for that mechanism.
    """
    failures: list[str] = []
    repo_root = _repo_root()

    scratch = repo_root / ".detect_secrets_check_file_selftest_scratch"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir()
    try:
        guilty_body = "aZ3xQ9" + "mR7bN2kP5vT8" + "wY1c"  # synthetic, 22 chars
        guilty_file = scratch / "guilty.py"
        guilty_file.write_text(
            'OAUTH_CLIENT_SECRET = "GOCSPX-' + guilty_body + '"\n', encoding="utf-8"
        )

        innocent_file = scratch / "innocent.py"
        innocent_file.write_text(
            'OAUTH_CLIENT_SECRET = os.environ["GOOGLE_OAUTH_CLIENT_SECRET_RCLONE"]\n',
            encoding="utf-8",
        )

        rc_guilty = check_files([guilty_file], repo_root=repo_root)
        if rc_guilty != 1:
            failures.append(f"GUILT   miss: expected exit 1, got {rc_guilty}")

        rc_innocent = check_files([innocent_file], repo_root=repo_root)
        if rc_innocent != 0:
            failures.append(f"INNOCENCE false positive: expected exit 0, got {rc_innocent}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    # Pure matcher cases: does find_results_for_file itself correctly
    # report not-found for a dict that doesn't cover the target?
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "unrelated.py"
        target.write_text("x = 1\n", encoding="utf-8")
        empty_results: dict[str, list[dict]] = {}
        found, _hits = find_results_for_file(empty_results, target, Path(td))
        if found:
            failures.append("MATCHER miss: empty results dict reported found=True")

        wrong_key_results = {"some/other/file.py": [{"line_number": 1, "type": "X"}]}
        found2, _hits2 = find_results_for_file(wrong_key_results, target, Path(td))
        if found2:
            failures.append("MATCHER miss: unrelated key in results reported found=True")

        rel_key = "unrelated.py"
        correct_results = {rel_key: [{"line_number": 1, "type": "X", "is_secret": False}]}
        found3, hits3 = find_results_for_file(correct_results, target, Path(td))
        if not found3 or hits3 != correct_results[rel_key]:
            failures.append("MATCHER false negative: correctly-keyed entry not found")

    # CANARY-GATE cases: the mutation-relevant tests for _evaluate. These
    # are pure (hand-built `results` dicts) because the property under
    # test — does a MISSING canary poison trust in every other "not
    # found", and does a WORKING canary correctly grant that trust — does
    # not depend on what produced the dict.
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        clean_target = td_path / "clean_target.py"
        clean_target.write_text("x = 1\n", encoding="utf-8")
        canary_stub = td_path / "_canary.py"
        canary_stub.write_text("y = 2\n", encoding="utf-8")

        # Canary MISSING from results (simulates a broken/silently-skipping
        # invocation). clean_target is ALSO absent from results — on its
        # own that's the same evidence as "genuinely clean" — but the
        # missing canary must poison the whole verdict: CANNOT-VERIFY (2),
        # never 0. This is the actual bug this tool exists to prevent.
        rc_broken = _evaluate({}, [clean_target], canary_stub, td_path)
        if rc_broken != 2:
            failures.append(
                f"CANARY-GATE miss: broken-canary invocation reported exit {rc_broken}, "
                "expected 2 (CANNOT-VERIFY) — a missing canary must poison trust "
                "in every absent key from the same scan"
            )

        # Canary FOUND (mechanism proven working THIS invocation) + target
        # genuinely has no key → NOW trust it as clean (exit 0). Innocence
        # case for the gate itself: a working canary must not itself cause
        # a false CANNOT-VERIFY on a file that really is clean.
        results_working_canary = {"_canary.py": [{"line_number": 1, "type": "Secret Keyword"}]}
        rc_working = _evaluate(results_working_canary, [clean_target], canary_stub, td_path)
        if rc_working != 0:
            failures.append(
                f"CANARY-GATE false positive: working-canary + genuinely-clean target "
                f"reported exit {rc_working}, expected 0"
            )

        # A working canary cannot vouch for a file OUTSIDE the repo it was
        # scanned from — that specific blind spot is a separate, known,
        # permanent gap (see selftest docstring), not something the canary
        # probes. Must still be CANNOT-VERIFY even with the canary found.
        outside_dir = tempfile.mkdtemp()
        try:
            outside_target = Path(outside_dir) / "outside.py"
            outside_target.write_text("x = 1\n", encoding="utf-8")
            rc_outside = _evaluate(results_working_canary, [outside_target], canary_stub, td_path)
            if rc_outside != 2:
                failures.append(
                    f"OUTSIDE-REPO miss: file outside repo_root reported exit {rc_outside}, "
                    "expected 2 (CANNOT-VERIFY) even with a working canary"
                )
        finally:
            shutil.rmtree(outside_dir, ignore_errors=True)

    for line in failures:
        print(f"  ✗ {line}")
    if failures:
        print(f"selftest FAILED ({len(failures)} of 8)")
        return 1
    print(
        "selftest OK — 2 guilt/innocence (real detect-secrets, canary path included) "
        "+ 3 matcher unit cases + 3 canary-gate unit cases"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--selftest", action="store_true", help="run guilt+innocence+canary-gate fixtures and exit")
    parser.add_argument("files", nargs="*", type=Path, help="file(s) to check")
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    if not args.files:
        print("nothing to check: pass at least one file, or --selftest", file=sys.stderr)
        return 2

    return check_files(args.files)


if __name__ == "__main__":
    sys.exit(main())
