---
date: 2026-08-10
domain: infra
adversarial_review: agy
reviewed_base_sha: 7e833cfaa787b7e15cae85d35c4a3bfbc179a9ec
reviewed_head_sha: cf0e38076a80ba1c65ba269a2fb1e71298cfcab3
reviewed_code_patch_sha256: 11de0d13f38988cad4029392235f6d2275ae6d110c9631f62a8daa76026fe633
review_input_report_blob_sha256: 8c827dbc2697d08fe0852e86bbfc6154dfd077899b544f9998d56fcc713c2e8f
---

# Differential Review: PR #3965 Exact-Path Follow-Up

## Executive Summary

This stacked change fixes one correctness defect in parent revision
`7e833cfaa787b7e15cae85d35c4a3bfbc179a9ec`: file-shaped allowlist entries
shared directory-prefix semantics, so descendants of an intended exact file
could incorrectly return `skip-backend`. The fix separates exact files from
directory rules and adds four regression tests that were observed RED before
the implementation.

Code-review verdict: **PASS after the recorded gates and the byte-bound
independent review below**. The reviewer found two low-severity report/gate
defects; both are corrected in this follow-up. No blocker survives in the child
code diff. The required CI backend suite remains independent of this local
optimization.

## Adversarial review

The reviewing seat was `agy` (Gemini 3.1 Pro through the Antigravity CLI),
independent from the Codex authoring seat. It received only the exact diff from
base `7e833cfaa787b7e15cae85d35c4a3bfbc179a9ec` through reviewed head
`cf0e38076a80ba1c65ba269a2fb1e71298cfcab3`. The code-only binary patch supplied
to it had SHA-256
`11de0d13f38988cad4029392235f6d2275ae6d110c9631f62a8daa76026fe633`; the
committed pre-follow-up report blob in that input had SHA-256
`8c827dbc2697d08fe0852e86bbfc6154dfd077899b544f9998d56fcc713c2e8f`.
Those hashes bind the review to bytes rather than a moving branch name.

The reviewer returned **PASS** on the implementation with two low-severity
documentation/gate findings:

1. This report lacked the R1 frontmatter and `adversarial_review` declaration.
   The frontmatter and this section resolve that finding.
2. The F-1 fixed-location citations were imprecise. The reviewer correctly
   challenged them, although its proposed replacement numbers were
   diff-relative rather than full-file lines. A direct numbered reread of the
   reviewed blob established the exact locations now recorded below:
   `scripts/prepush_classify.py:323`, `scripts/prepush_classify.py:747`, and
   `scripts/prepush_classify.py:752`.

The review independently verified the path-boundary defect, the separation of
exact and directory matching, fail-closed precedence, test structure, and hook
protection. It did **not** execute the tests; the RED/GREEN and full-suite counts
in this report remain execution evidence from the authoring lane, not output
attributed to the reviewer.

Two objections survive by design: the classifier remains path-string-only and
does not inspect Git file modes or symlink targets, while required PR CI still
runs independently; and the two Python files retain pre-existing Ruff-format
debt so this stacked cure does not hide its semantic change inside a bulk
reformat.

### Stacked-CI baseline drift (not introduced by this child)

The child CI also exposed an inherited `gateway (anti-regrowth lint)` failure.
The child and exact parent carry the same `grandfathered.json` blob
(`02ef47ecd9db708de8c9bd690d29c8ffa10be284`), while current `main` carries
`7624b44e772de6b31709d3bb9bfdc4cfaa6da8c3` after PR #3924 migrated both healer
senders to the Telegram gateway. On the exact parent snapshot, both healer
scripts still call `api.telegram.org` directly, so deleting only their two
grandfather entries would create two genuine anti-regrowth offenders. Importing
#3924 would touch five unrelated runtime/registry/test files (+166/-75) and
change parent semantics. This child therefore does not mask the failure; the
parent/base must be refreshed through its own owner before terminal CI can be
green.

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
- Fixed locations: `scripts/prepush_classify.py:323`,
  `scripts/prepush_classify.py:747`, and `scripts/prepush_classify.py:752`
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
