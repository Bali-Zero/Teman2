---
id: branch-graveyard-content-on-main-coverage
title: Add real-git-repo test coverage for branch_graveyard_cleanup.sh's content_on_main()
seat: luna
scope: scripts/branch_graveyard_cleanup.sh (read-only, do not edit), scripts/tests/test_branch_graveyard_content_on_main.sh (new file)
acceptance: sh scripts/tests/test_branch_graveyard_content_on_main.sh
status: pending
---

## Where

`scripts/branch_graveyard_cleanup.sh:205-218`, function `content_on_main()`
— the executable the repo's own cicatrix-superscar.md family #9
("State-schema mutation drift") names as ANTIDOTO:
`scripts/branch_graveyard_cleanup.sh::content_on_main()`.

```bash
content_on_main() {
    local branch="$1" mb f bh mh
    mb=$(git merge-base "$MAIN_REF" "$branch" 2>/dev/null) || return 1
    while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        bh=$(git rev-parse "$branch:$f" 2>/dev/null || echo __ABSENT_BRANCH__)
        mh=$(git rev-parse "$MAIN_REF:$f" 2>/dev/null || echo __ABSENT_MAIN__)
        [[ "$bh" != "$mh" ]] && return 1
    done < <(git diff --name-only "$mb" "$branch" 2>/dev/null)
    return 0
}
```

## What

`content_on_main()` has ZERO test coverage today — verified by grep across
the whole `scripts/tests/` directory (`grep -rn content_on_main
scripts/tests/` returns nothing). Its sibling function in the same file,
`pr_merged_match()` (category 5), already has a dedicated test:
`scripts/tests/test_branch_graveyard_prmerged.sh`. That file's own header
explains why: the LIVE script "is not sourceable — it runs top-level
git/gh calls immediately", so it reproduces the matcher logic verbatim
inside the test and carries a tripwire section (grep the live file's
function body and fail loudly if it has drifted from the copy under
test) to keep the reproduction honest.

Write `scripts/tests/test_branch_graveyard_content_on_main.sh` following
that EXACT same pattern (verbatim function reproduction + tripwire against
the live file — do not just "test the idea", test the real bash logic),
but unlike `pr_merged_match()` (pure text/awk matching, no git needed),
`content_on_main()` calls `git merge-base`, `git diff --name-only`, and
`git rev-parse <ref>:<path>` — so the test must build a REAL temporary git
repository (`git init` in a `mktemp -d`, `trap ... EXIT` cleanup, matching
this repo's own "verify against real content, never a proxy" discipline —
cicatrix-superscar.md family #9's own antidote line: "'già su main/stale'
si verifica per CONTENUTO ... mai patch-equivalenza/SHA-ancestor/
timestamp"). `MAIN_REF` is a plain shell variable the function reads from
its caller's scope (`scripts/branch_graveyard_cleanup.sh:112`) — set it in
the test to whatever ref name you give the "main" branch in the fixture
repo (e.g. `main`).

At minimum cover these cases (guilt = `content_on_main` returns 1, i.e.
genuinely unmerged; innocence = returns 0, safe to delete):

- **G1** branch adds a NEW file with content that never landed on main —
  must return 1.
- **G2** branch's version of an EXISTING file differs from main's
  (different blob, same path) — must return 1.
- **I1** branch squash-merged: every file the branch touched (per
  `git diff --name-only <merge-base> <branch>`) is now byte-identical on
  main (this is the real-world case the function's own header comment
  says three-dot diff gets wrong post-squash) — must return 0.
- **I2** branch DELETED a file, and that file is ALSO absent on main
  (deletion landed too) — must return 0 (the function's own comment: "A
  file the branch DELETED (absent on branch) must also be absent on
  main").
- **I3** branch and main point at the exact same commit (no diff at all)
  — must return 0.
- **G3** branch deleted a file that main STILL HAS (the deletion itself
  never landed) — must return 1 (this is the inverse of I2 and the case
  most likely to regress silently if someone "fixes" the absent-branch
  case carelessly).

## Why

Cicatrix-superscar.md family #9 (State-schema mutation drift) names this
exact function as its own antidote for "already on main / stale" claims —
a function with that role and zero coverage is the family's own disease
pattern applied to its own cure. Family #6 (anti-hallucination blindness)
also applies: a branch-deletion script deciding "safe to delete" from an
untested content-comparison path is a real-data-loss surface, not an
audit-only one.

## Scope fence

Do NOT edit `scripts/branch_graveyard_cleanup.sh` itself — this chore is
test-coverage only, on a script whose own header already documents a
deliberate DRY-RUN-by-default posture; changing its logic is a separate,
riskier chore. Do NOT touch `scripts/tests/test_branch_graveyard_prmerged.sh`
except to read it as a pattern reference. Do not add a `pytest`
dependency — this repo's existing sibling test for the same file is a
plain POSIX `sh` script (`#!/bin/sh`, no bashisms it doesn't need), keep
the new one the same shape and runnable with `sh`, not `bash`-only syntax
unless `content_on_main()` itself requires bash (it does use `[[ ]]` and
process substitution `< <(...)` — the reproduction inside the test may
need `#!/bin/bash` for that reason; if so, say so in a comment the way
the existing test's header explains its own choices).

## Acceptance

`sh scripts/tests/test_branch_graveyard_content_on_main.sh` (or
`bash scripts/tests/...sh` if the reproduction needs bash — the acceptance
command should match whatever shebang the new file actually uses) prints a
PASS/FAIL line per case (same `note_pass`/`note_fail` convention as
`test_branch_graveyard_prmerged.sh`) and exits 0 only when every case
above passes. A first run with all-green-because-nothing-was-asserted is
not acceptable — each case must genuinely call `content_on_main` inside
the fixture repo and check its real exit code.
