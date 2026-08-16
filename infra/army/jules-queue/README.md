# Jules lane queue

Task backlog for `scripts/army/jules_lane.py --dispatch` — the standing lane
that turns Jules (Google's async cloud implementer, armed 2026-07-06 and
dormant since) into a queued, capped dispatcher.

Unlike the Spark lane's queue, this one is **deliberately not seeded**. A
Jules task produces a real diff against this repo, and per the existing
contract ("Jules generates; Fable grades" —
`docs/runbooks/jules-dispatch.md`) every diff gets independently verified
by an interactive session before landing. Seeding this queue with
speculative tasks would just pile up unverified diffs faster than the
verification lane can absorb them — the opposite of the point. Tasks land
here only when a session has already scoped one with real anchors.

## Format

One file per task, `*.md`, flat in this directory. The lane picks the
**oldest not-yet-dispatched** files by mtime, up to `ARMY_JULES_DAILY_CAP`
(default 3) per day, and passes the file's full content verbatim as the
`--prompt` to `jules_dispatch.py new`. Dispatch state (which files have
already been sent, and the resulting session id) lives locally on the
runner in `~/army/jules/state/` — this directory is git-tracked and the
lane never commits to it, matching the Spark lane's convention.

```markdown
# <short imperative title — becomes the session title>

<the task prompt, following the authoring discipline below>
```

## Task-authoring discipline (verbatim from `docs/runbooks/jules-dispatch.md`)

> A Jules prompt must carry: exact file + line anchor · the precise change
> · the repo rule/scar that motivates it · explicit scope fence ("do NOT
> change anything else") · what green looks like. Under-specified prompts
> produce plausible-but-wrong diffs that waste the verification lane.

Concretely, every task file here should answer:

1. **Where** — exact `file:line` (or a small enumerated set of them), not
   "somewhere in this module".
2. **What** — the precise change, described unambiguously enough that two
   different readers would write the same diff.
3. **Why** — which repo rule, invariant, or scar (cicatrix-superscar.md
   family, a CLAUDE.md §, a specific test) motivates the change.
4. **Scope fence** — an explicit "do NOT touch X/Y/Z" for anything adjacent
   that a plausible-but-wrong diff might also grab.
5. **Acceptance** — what a reviewer checks to call the diff correct (a
   specific test to run, an exact string that should/shouldn't appear, a
   behavior to reproduce).

## Landing

The lane's `--harvest` mode never lands anything. On a COMPLETED session it
downloads the evidence to `~/army/jules/inbox/<session-id>/` and appends
ONE row to `shared/escalations_pro.jsonl` (via
`scripts/sentinel_lib/escalations.py`, the repo's existing single-writer
module) so the next interactive session picks it up, re-reads the diff
line-by-line against the task spec, re-runs the touched tests, checks
scope + reward-hacking, and lands via its own branch + PR + auto-merge
(CLAUDE.md §2, §5's Jules seat rules).
