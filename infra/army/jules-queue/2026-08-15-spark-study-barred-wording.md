# Align the Spark study's BARRED wording with its own worktree scoping

File: `research/operations/2026-08-15-gemini-spark-repo-lane-study.md`.

The "Capability verdict for repo work" section ends with a paragraph that
reads: «point Spark (Ultra, Mac) at a **non-code, document-shaped folder** —
sorting/summarizing research PDFs, drafting doc prose — never at
`.git`-tracked source, never unsupervised, never as a git-committing
worker.»

The "## Adversarial review" section of the same file records the one
surviving objection: the "Standing mandate draft — GATED, NOT ARMED"
section scopes Spark to a dedicated `.worktrees/spark-<task-id>/` worktree,
whose contents ARE `.git`-tracked source — so "never at `.git`-tracked
source" contradicts the mandate two sections below it.

The precise change (one sentence, nothing else): in that Capability-verdict
paragraph, replace the fragment

`never at \`.git\`-tracked source, never unsupervised, never as a git-committing worker`

with

`never at repo source outside a dedicated task-scoped worktree (and inside one, only the document-shaped files the task names — per the standing-mandate scoping below), never unsupervised, never as a git-committing worker`

Scope fence: do NOT change anything else — not the frontmatter, not the
"## Adversarial review" section, not the standing-mandate section, no other
file.

Green looks like: `python3 scripts/check_adversarial_review.py --files
research/operations/2026-08-15-gemini-spark-repo-lane-study.md` still
passes, and `git diff` shows exactly one modified region in exactly one
file.
