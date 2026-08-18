# Spark lane queue

Task backlog for `scripts/army/spark_lane.sh` — the standing lane that spends
the otherwise-idle `gpt-5.3-codex-spark` weekly bucket (separate from the
main Codex bucket, PONG-verified 2026-08-14) on **read-only** analysis of
this repo, ticking every 2h on Pro.

## Format

One file per task, `*.md`, flat in this directory (no subfolders — the
`done/` idea from the first draft was dropped: this directory is
git-tracked and the lane never commits, so "done" state lives locally on
the runner in `~/army/spark/state/done-list.txt`, keyed by
`<filename>:<sha256-of-content>`. Editing a task file's content makes it
eligible again — that is intentional, it lets a session refine a stale
prompt in place instead of renaming the file).

```markdown
# <short imperative title — becomes the report slug>

<the full prompt handed to codex verbatim. State the scope, the acceptance
shape (e.g. "file:line + one-sentence reason per item"), and make it
explicit this is READ-ONLY analysis — no plan to edit/commit/push. The
--sandbox read-only flag enforces this at the tool level; the prompt text
should not imply otherwise, so a plausible-looking diff never gets
half-written into the output.>
```

The lane picks the **oldest not-yet-done** file by mtime, processes exactly
**one per tick**, and writes its report to
`~/army/spark/reports/<date>-<slug>.md`. It never edits this directory,
never opens a PR, never merges — output is an artifact on disk plus a daily
Telegram digest (07:00 WITA). Landing anything the report finds useful is
always the job of an interactive session (CLAUDE.md §2 — the session owns
the full ship lifecycle, not a standing cron).

## Adding a task

Just drop a new `*.md` file here following the format above and commit it
through the normal PR flow — same discipline as any other repo change. Keep
each task scoped to one question; a task that tries to do too much produces
a report too broad to act on.

## Task-authoring discipline (borrowed from `docs/runbooks/jules-dispatch.md`)

A good task carries: the exact subsystem/path to look at, the shape of
answer you want (a table, a ranked list, file:line anchors), and the "why"
— which scar or invariant motivates asking. Under-specified prompts burn a
Spark run on a vague essay nobody acts on.
