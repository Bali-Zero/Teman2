# Chore queue for cheap seats

Generic backlog for `scripts/chore_dispatch.py` — a session (or the daily
`--dispatch-next` cron tick) hands a scoped, well-anchored task off to a
cheap seat instead of spending an interactive session's own turn on it.
This is receptor-live PART B; PART A is the Spark harvester (#5053).

Unlike the standing Armata H24 lanes (`infra/army/jules-queue/`,
`infra/army/spark-queue/`), which are each ONE seat's own queue, this
directory is seat-agnostic — `chore_dispatch.py --dispatch <id> --seat
<seat>` REUSES the existing per-seat mechanics rather than reinventing
them: a `jules` chore shells out to `scripts/jules_dispatch.py new`
directly (the same call `scripts/army/jules_lane.py` makes); a `spark`
chore is written into `infra/army/spark-queue/<id>.md` in that lane's own
file format, so `scripts/army/spark_lane.sh`'s existing tick consumes it —
still read-only, still never opens a PR, per that lane's contract.

## Format

One file per chore, `*.md`, flat in this directory, filename == `<id>.md`.

```markdown
---
id: <slug, matches the filename stem>
title: <short imperative — becomes the session/report title>
seat: jules | spark | haiku | luna
scope: <path(s) the change may touch>
acceptance: <exact command a verifier runs to call the diff correct>
status: pending | dispatched | queued-spark | in-progress | completed | failed
---

<task body — same authoring discipline as infra/army/jules-queue/README.md:
where (file:line), what, why (rule/scar/test), scope fence, acceptance>
```

`--dispatch` adds `session:` (jules) and `dispatched_at:` to the header —
never hand-author those. `haiku`/`luna` are catalog-only today: neither has
a cheap-seat CLI wired into this repo yet (see `scripts/arsenal_probe.py`),
so `--dispatch --seat haiku|luna` is a clean, visible refusal (exit 3), not
a silent no-op — a chore never looks dispatched when nothing ran. Hand
those to the matching Agent subagent (`docs-sync`, `catalog-meta`,
`lint-fixer`, ...) by hand until a seat exists.

## Commands

```bash
python3 scripts/chore_dispatch.py --list
python3 scripts/chore_dispatch.py --dispatch <id> --seat jules|spark [--dry-run]
python3 scripts/chore_dispatch.py --harvest          # polls dispatched jules chores only
python3 scripts/chore_dispatch.py --dispatch-next    # oldest status=pending chore, its own seat
```

## Landing

Same contract as every cheap-seat arm in this repo (CLAUDE.md §5, §2): a
chore GENERATES, it never lands anything. `--harvest` never merges — on a
completed jules session it only flips the chore's `status` to `completed`
so an interactive session knows to re-read the diff line-by-line against
the chore's `acceptance` command, re-run it, check scope + reward-hacking,
and land via its own branch + PR + auto-merge.
