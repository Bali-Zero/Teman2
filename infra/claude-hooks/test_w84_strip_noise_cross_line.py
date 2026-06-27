#!/usr/bin/env python3
"""W84 regression test — _strip_noise cross-line quote bug (sibling of W83).

Superscar #3 (guard-over-match), command-guard variant. The quote-stripping in
`_strip_noise` used `'[^']*'` / `"[^"]*"`, whose char-class MATCHES newlines —
so in a multi-line command a stray quote on one line pairs with a quote on
another, collapsing several commands into one mangled string. A grep pattern
like `grep "a\|b" 2>&1` then leaks into the redirect scan and `_write_hits_main`
reports a phantom write-target (e.g. `warm_models_extra\`) inside main → a
legitimate read-only `ssh ... grep ...` diagnostic is falsely BLOCKED.

Lived 3x in the 2026-06-16 session (the trigger was an apostrophe in an Italian
comment — `dell'insurance` — opening a quote that paired with an `ssh '...'`).

Fix: (a) `[^'\n]*` / `[^"\n]*` confine each quote to one line; (b) the classifier
drops any target carrying a backslash or pipe (escape/alternation residue, never
a real path). This test asserts the phantom is gone WITHOUT weakening detection
of genuine writes into main (the W79 duty).

    python3 infra/claude-hooks/test_w84_strip_noise_cross_line.py

Exit 0 = all pass, exit 1 = at least one mismatch.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent


def _load_mod():
    spec = importlib.util.spec_from_file_location("wi", str(HERE / "worktree_isolation.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    mod = _load_mod()
    tmp = pathlib.Path(tempfile.mkdtemp())
    main_checkout = tmp / "nuzantara"
    worktree = main_checkout / ".worktrees" / "lane-x"
    (main_checkout / "apps").mkdir(parents=True)
    worktree.mkdir(parents=True)
    mod.REPO_ROOT = str(main_checkout)

    wt_root = (main_checkout / ".worktrees").resolve()

    def _fake_allowed(path_str: str) -> bool:
        if not path_str:
            return False
        try:
            p = pathlib.Path(mod.os.path.expanduser(path_str))
            if not p.is_absolute():
                return False
            p = p.resolve()
        except Exception:
            return False
        try:
            return p.is_relative_to(wt_root)
        except Exception:
            return False

    mod._is_path_in_allowed_worktree = _fake_allowed

    M = str(main_checkout)
    W = str(worktree)

    # The reproduction of the real false-positive: a multi-line ssh+grep diagnostic
    # whose first line carries an apostrophe (here a plain comment) and whose grep
    # patterns use `\|` alternation + `2>&1`. Pre-W84 this collapsed cross-line and
    # surfaced a phantom `MODEL_TOPOLOGY...warm_models_extra\` write into main.
    REAL_FP = (
        "cd " + M + " 2>/dev/null\n"
        "echo \"=== verify: dell'insurance files ===\"\n"
        "ssh pro 'grep -n \"options.*think\\|num_predict\" "
        "~/Desktop/nuzantara/apps/x/simple.py 2>&1 | head -4' 2>&1\n"
        "echo \"\"\n"
        "ssh pro 'grep -n \"warm_models_extra\\|warm_model\\|SEA-LION\" "
        "~/Desktop/nuzantara/MODEL_TOPOLOGY.json 2>&1 | head -8' 2>&1"
    )

    # (command, cwd, expect_block) — expect_block True == _write_hits_main returns a path
    CASES = [
        # THE bug — must NOT block (it's a read-only ssh grep diagnostic)
        (REAL_FP, M, False),
        # smaller shapes of the same class — must NOT block
        ("ssh pro 'grep \"a\\|b\" f 2>&1 | head' 2>&1", M, False),
        ("echo \"x\ny\" && ssh pro 'grep \"c\\|d\" f' 2>&1", M, False),
        ("cmd 2>&1", M, False),
        ("cmd 2>/dev/null", M, False),
        ("grep '2>&1 needle' file.txt", M, False),
        ("git commit -m \"see redirect > here\"", M, False),
        # GENUINE writes into main — must STILL block (no regression of the W79 duty)
        ("echo x > apps/f.py", M, True),
        ("echo x >> CLAUDE.md", M, True),
        ("cp /tmp/src apps/dest.py", M, True),
        ("sed -i 's/a/b/' apps/f.py", M, True),
        ("dd if=/tmp/x of=apps/img", M, True),
        ("echo x | tee CLAUDE.md", M, True),
        # write into a worktree — must NOT block
        ("echo x > " + W + "/f.py", M, False),
        # write outside repo — must NOT block
        ("echo x > /tmp/scratch", "/tmp", False),
        # --- superscar #3 STRUCTURAL CURE (path-plausibility) — 2026-06-23 ---
        # The W83/84/85 treadmill: each over-match was a new way code-residue leaked a
        # bare `>` past the noise-stripper. Instead of patch-per-shape, a target now
        # survives only if it is a PLAUSIBLE PATH. These are the new shapes (python -c
        # multiline + awk/perl/jq bodies) that a 4th puntual patch would have missed:
        ('python3 -c "\nfor s in vals:\n  if s>=0.9: b[0]+=1\n"', M, False),
        ('python3 -c "\nx=0.6\nif x>=0.5: pass\n"', M, False),
        ("awk '{if ($1 > 5) print}' file.txt", M, False),
        ('perl -e "print 1 if 2>1"', M, False),
        ("cat f | jq 'select(.n > 5)'", M, False),
        ('echo "score >= threshold"', M, False),
        # genuine writes with NO extension but a dir separator — must STILL block
        ("echo x > apps/build/Makefile", M, True),
    ]

    fails = 0
    for cmd, cwd, expect in CASES:
        got = mod._write_hits_main(cmd, cwd) is not None
        if got != expect:
            fails += 1
            label = cmd.splitlines()[0][:48] if "\n" in cmd else cmd[:48]
            print(f"  [FAIL] block={got!s:5} expect={expect!s:5}  {label}")

    total = len(CASES)
    if fails:
        print(f"\n=== {fails}/{total} FAIL ===")
        return 1
    print(f"=== ALL {total} PASS ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
