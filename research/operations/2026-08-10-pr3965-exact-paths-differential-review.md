# Differential Review: PR #3965 Exact-Path Follow-Up

## Executive Summary

This stacked change fixes one correctness defect in parent revision
`7e833cfaa787b7e15cae85d35c4a3bfbc179a9ec`: file-shaped allowlist entries
shared directory-prefix semantics, so descendants of an intended exact file
could incorrectly return `skip-backend`. The fix separates exact files from
directory rules and adds four regression tests that were observed RED before
the implementation.

Review verdict: **PASS after the recorded gates**. No unresolved blocker was
found in the child diff. The required CI backend suite remains independent of
this local optimization.

## What Changed

- `scripts/prepush_classify.py`
  - Bumps the logged allowlist version from 7 to 8.
  - Adds `ALLOWLIST_EXACT_PATHS`, containing only the root `.gitignore`, the
    two wa-mirror package files, and the organism registry file.
  - Removes those file-shaped entries from
    `ALLOWLIST_PREFIX_SUFFIX_PAIRS`.
  - Matches exact files with string equality and directory entries only with
    `path.startswith(prefix + "/")` plus their existing suffix constraint.
  - Preserves the precedence of `NEVER_INNOCENT_EXACT_PATHS`, newline and
    traversal rejection, and `NEVER_INNOCENT_BASENAMES`.
- `scripts/tests/test_prepush_classify.py`
  - Adds guilt tests for descendants of all four exact files.
  - Migrates structural assertions to the dedicated exact-path set.
  - Keeps the existing innocence, mixed-backend, lookalike, reason-label,
    traversal, and fail-closed corpus.

The implementation diff against the exact parent is 61 additions / 62
deletions in the classifier and 66 additions / 55 deletions in its tests,
before this report. Most classifier churn updates the extensive embedded
design record so it no longer recommends the defective shared matcher.

## Critical Findings

### F-1 — Fixed: exact-file entries admitted descendants

- Severity: Medium
- Location in parent: `scripts/prepush_classify.py`, old shared match branch
- Fixed locations: `scripts/prepush_classify.py:317`,
  `scripts/prepush_classify.py:747`, and `scripts/prepush_classify.py:751`
- Root cause: the parent evaluated every entry with
  `path == prefix or path.startswith(prefix + "/")`. The second arm is valid
  for a directory prefix but invalid for a file-shaped prefix.
- Concrete counterexamples observed RED:
  - `.gitignore/probe.gitignore`
  - `apps/wa-mirror/package.json/probe.json`
  - `apps/wa-mirror/package-lock.json/probe.json`
  - `apps/organism/organism/organs_registry.yaml/probe.yaml`
- Impact: each path returned `skip-backend` under the parent. Git can validly
  delete a file and add a directory with the same name, so this is a real path
  boundary, not a filesystem-impossible string. A contributor could therefore
  suppress the local full backend pre-push suite for such a diff. Required PR
  CI still runs independently, limiting the defect to the local early-warning
  layer.
- Resolution: exact files now use equality in an immutable set; directory
  rules retain boundary-safe descendant matching and suffix scoping.

No remaining critical or high-severity finding was identified in the child
diff.

## Test Coverage

TDD evidence:

1. RED, before production changes:
   `pytest ... -k 'root_gitignore_descendant or package_json_descendant or package_lock_json_descendant or organs_registry_yaml_descendant'`
   returned **4 failed, 136 deselected**. Every failure was the same expected
   mismatch: parent verdict `skip-backend`, required verdict `full`.
2. GREEN, after the exact/directory split: the same command returned
   **4 passed, 136 deselected**.
3. Full focused classifier suite: **140 passed**.
4. Shell fail-closed regression suite: **19 passed, 0 failed**.
5. CLI innocence proof: the four literal exact paths together returned
   `skip-backend` and reported four `(exact match)` reasons.
6. CLI guilt proof: the four descendants together returned `full` and listed
   all four as not allowlisted.
7. `.husky/pre-commit` CLI proof: returned `full`; its existing guilt test is
   also included in the 140-test pass.
8. `ruff check` on the two Python files: passed.
9. `py_compile` on the two Python files: passed.
10. `git diff --check` against the exact parent: passed.

`ruff format --check` reports both files would be reformatted. The exact parent
reports the same two-file result, so this is baseline formatting debt rather
than a regression; bulk-reformatting the 1,700-line test corpus is intentionally
outside this tightly scoped stacked fix.

## Blast Radius

- Direct behavior surface: `_innocent_reason()` and the version printed in
  classifier diagnostics.
- Public behavior surface: `classify(files)` and the script CLI keep the same
  input/output contracts (`full` or `skip-backend`).
- Search for `ALLOWLIST_EXACT_PATHS`, `ALLOWLIST_PREFIX_SUFFIX_PAIRS`, and
  `_innocent_reason(` outside the classifier and its test file returned no
  consumers.
- Directory rules are unchanged semantically: they still require a path below
  the prefix and an approved suffix.
- Exact-file innocence is unchanged for the four intended literal paths.
- Unknown paths remain fail-closed to `full`.
- The never-innocent pre-commit hook remains checked before every allowlist
  mechanism.

## Historical Context

The matcher originated in `bdb4415614` (path-aware pre-push), followed by
suffix hardening and measured allowlist expansions. Exact-file semantics were
introduced for `.gitignore` in `e4237ddfd7`; `6a57e5ba37` corrected its reason
label while retaining the shared matcher. Parent `7e833cfaa7` added three more
file-shaped rules, expanding the existing boundary defect from one exact file
to four. The stacked fix changes the representation rather than adding another
special case to the shared branch.

Relevant recent history reviewed:

- `7e833cfaa7` — v7 allowlist expansion
- `6a57e5ba37` — exact-match reason label
- `e4237ddfd7` — v6 `.gitignore` exact intent
- `bdb4415614` — original path-aware classifier

## Recommendations

1. Merge this child before merging the parent stack, so v7 never lands with
   file prefixes interpreted as directory prefixes.
2. Keep future literal files in `ALLOWLIST_EXACT_PATHS`; add only real
   directories to `ALLOWLIST_PREFIX_SUFFIX_PAIRS`.
3. Require an innocence test for the literal path and a guilt test for a
   same-suffix descendant whenever an exact-file rule is added.
4. Keep `.husky/pre-commit`, `.husky/pre-push`, the classifier, and the CI test
   workflow in `NEVER_INNOCENT_EXACT_PATHS`.

## Analysis Methodology

The review used the exact parent SHA as baseline and followed a differential,
history-aware workflow:

1. Revalidated the parent head and created a broker-managed isolated worktree.
2. Read the parent diff and traced the common matcher used by all four
   file-shaped entries.
3. Constructed valid same-suffix descendants and executed them against the
   parent implementation.
4. Added only the four regression tests and observed the required RED state.
5. Implemented the smallest representation change that makes exact and
   directory semantics unambiguous.
6. Re-ran focused, full, CLI, shell fail-closed, lint, compile, and whitespace
   gates.
7. Reviewed call sites with repository search and reviewed origin/history with
   `git log` and `git blame`.
8. Re-read the final diff for path-boundary, traversal, precedence, diagnostic,
   and fail-closed behavior.

## Appendices

### Baseline and branch

- Baseline SHA: `7e833cfaa787b7e15cae85d35c4a3bfbc179a9ec`
- Baseline branch: `agent/air-m5/infra/l5-allowlist-v7`
- Child branch: `agent/air-m5/infra/l5-v7-exact-paths`

### Exact-path invariant

For every `p` in `ALLOWLIST_EXACT_PATHS`:

- `classify([p]) == (skip-backend, [])`, unless a never-innocent rule is
  deliberately added for `p` later.
- `classify([p + "/probe" + suffix]) == (full, [descendant])`.

For every `(directory, suffixes)` in `ALLOWLIST_PREFIX_SUFFIX_PAIRS`, only
`directory + "/" + descendant` with an allowed suffix can match. Equality with
the directory string is not treated as a file rule.
