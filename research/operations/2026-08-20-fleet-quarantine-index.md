---
date: 2026-08-20
domain: operations
client_case: none
adversarial_review: kimi-k3
sources:
  - research/operations/2026-08-20-fleet-quarantine-index.tsv
  - scripts/worktree_gc_universal.py
---

# The fleet's quarantine store, indexed for the first time

`refs/agent-quarantine/` is where `scripts/worktree_gc_universal.py` puts a
worktree's uncommitted work right before it removes the worktree directory
that held it. Two things land there: a stash-style commit capturing the
working tree's modified and untracked files, and — separately — a preserved
pointer for any worktree that was checked out at a detached HEAD, so that
commit chain isn't stranded once the worktree directory it lived in is gone
(a detached HEAD has no branch name to fall back on). Both are ordinary git
refs under a non-standard namespace: `git branch` never lists them, they
have no TTL or expiry mechanism, and until this index was built today,
nobody on the fleet had ever enumerated what was sitting in there across
all three machines.

## The numbers, as measured 2026-08-20

These will drift — the nightly GC run adds to this store every night on
every machine, so treat every count below as a photograph, not a fact:

- M5: 361 refs
- Pro: 121 refs (after removing 8 provable duplicates of `main`)
- Mini: 130 refs (0 removed — nothing there duplicated `main`)
- **Total: 612 refs**, after removing 13 fleet-wide whose content was
  provably already on `origin/main` (blob-identical, not just
  ancestor-equal — see the sibling PRs from today's cleanup for method).
- Oldest surviving ref: **2026-05-31**. Sum of `uniq_files` across all
  numeric rows: **roughly 5,100** files of content that is not on `main`.

## How to read a row, and how to recover one

Each row is one ref: `machine`, its short name (the quarantined worktree
path, sanitized), the commit `sha`, `committer_date`, `uniq_files` (files
that differ from `origin/main` by blob, or the literal `NO_MERGEBASE` when
the commit shares no history with `main`), and up to three `top_paths` — a
sample, not a full manifest. To look without touching anything: `git show
<sha>`. To get a full working tree back: `git worktree add <path> <sha>`.

## The honest caveat

`uniq_files > 0` means "not a duplicate of `main`" — not "the only copy of
this work in existence." The GC preserves on two tracks: this quarantine
ref for the raw commit, and (when the branch had a name) the branch ref
itself, left untouched by the same GC run. So the *committed* part of a
piece of work usually still lives on an ordinary, findable branch. What
this store uniquely holds is the *uncommitted* part — whatever was modified
or untracked in the working tree at the moment it was reaped.

One more thing worth naming so it isn't mistaken for a finding: `git diff
--name-only` reports a changed `node_modules` tree as a single path. On
rows where that consumes one of the three sampled `top_paths`, it tells you
nothing about the actual work — expect it, don't read into it.

## What this is not

A snapshot, current as of the moment it was generated. It goes stale
starting with the very next nightly GC run, which will add more refs than
this document lists. Not a live view, and it doesn't attempt to be one.

## Adversarial review

Reviewed by Kimi K3 (`kimi -m kimi-code/k3`), a different model family than
the author — Codex was tried first but returned a usage-limit error (quota
exhausted until 2026-08-22), so the review fell through to Kimi.

Kimi independently re-derived every number from the tsv on disk rather than
trusting the prose, and confirmed all of them (361/121/130/612, oldest
2026-05-31, uniq_files sum 5,126). It flagged two things: (1) the original
wording said a detached HEAD's commit was preserved "once the branch name
it lived under is gone" — a detached HEAD has no branch name, fixed above;
(2) it questioned whether the nightly-GC-on-every-machine claim actually
holds for M5, given M5 is elsewhere documented as no-daemon/no-cron —
checked directly on M5, the LaunchAgent plist is present and registered via
`launchctl print`, so the claim stands. It also correctly noted the "13
removed" figure isn't verifiable from this tsv alone (a post-removal
snapshot) — it rests on the sibling per-machine deletion manifests the
prose already points to. The run itself was cut off by a 5-minute timeout
mid a self-initiated broader scan (a known K3 trait); the verification
above completed before the cutoff.
