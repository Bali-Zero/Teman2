---
date: 2026-08-27
domain: operations
client_case: none
sources: 3
---

# Retro corrections after dispatch

> Sibling to `research/operations/2026-08-26-retro-fleet-sessions-25-26.md`. That file lives on PR
> #5046's branch (`agent/nuzantara/docs/retro-capture-0826`), not yet on `origin/main` at the time
> this file was written — so these corrections are captured here rather than appended to a file
> this branch's base does not contain. Once #5046 merges, fold this section into that file's own
> "Corrections after dispatch" section if one exists, or link it from there.

## Corrections after dispatch

### (1) Q0 skills canonicity — the "21 dirs / 11 divergent" picture was untracked working-tree noise, not a repo defect

On `origin/main`, `.agents/skills/` legitimately has 8 directories by design: it is the Tier-A
cross-agent skill store (README, PR #3019). The 11 skills that are Claude-Code-only live only in
`.claude/skills/`; 5 of the shared ones under `.agents/skills/` are symlinks back into
`.claude/skills/`. That is the intended architecture, not drift.

The dispatched picture — "21 dirs / 11 divergent / `.agents/skills/modus/SKILL.md:149` routes to
Fable" — was never a measurement of `origin/main`. It was 12 **untracked** working-tree copies
created 2026-08-19 00:26 on Pro and on M5 (Mini's checkout was clean). One of those untracked
copies — the `modus` one — did in fact say "Fable 5 first, rotating", which is where the
Fable-routing claim came from; it was true of that stray file and false of the repo.

Cure already landed: PR #5041 (a tripwire test plus the `NUZ_SKILLS_ROOT` local door), proven RED
on the Pro main checkout before the fix (2 failed / 9 passed) and green after. The remaining step
is an operator one-liner cleanup, not a code change:

```
git -C ~/nuzantara clean -fd -- .agents/skills/{agent-session-discipline,final-gate-discipline,intake,karpathy-discipline,modus,pipeline-ship,reuse-first,skill-catalog,slhs,sota-architecture-loop,workflow}
```

on both Pro and M5. Deliberately **excluded** from that cleanup: `source-command-resume` — an
untracked Mnemos post-compact skill with no tracked twin, which needs triage (is it wanted?), not
a blind delete. M5 separately carries a **modified tracked** `subhi/SKILL.md`, which is a distinct
decision (a real edit to a real file, not stray untracked noise) and is not covered by this
cleanup line.

**Lesson**: when reporting a count of divergent/duplicated files, state which tree the count was
measured on (`git status` working tree vs. `origin/main` vs. a specific branch). A number that is
true of an uncommitted working copy reads, unqualified, as a claim about the repo.

### (2) GitHub Actions major outage, 2026-08-26 — read githubstatus before diagnosing the repo

Facts, as captured in `.claude/skills/modus/PENDING-ARMS.md` (post-outage sweep row, opened
2026-08-27): the githubstatus incident was posted at 16:14Z, but the first `merge_group` runs
ending `startup_failure` are timestamped 15:06Z — roughly 68 minutes before the public incident
post. In that window, 99 runs sat queued with 0 jobs assigned, and no Actions check-suite was
created at all on some new PR heads.

**Lesson**: a wave of `startup_failure`/missing-check-suite symptoms across many unrelated PRs at
once is a strong prior for an upstream Actions outage, not a fleet-wide code or config regression.
Check `https://www.githubstatus.com` first. And per the Agent PR Contract's rule 3
(`docs/runbooks/merge-queue-discipline.md`): when the cause is external and the head SHA is
unchanged, the correct instrument is `gh run rerun` on the affected runs — never `gh pr
update-branch` or a fresh push, both of which would invalidate a Gear-3 gate verdict tied to that
commit for no reason.

### (3) Dispatch burst: 14 parallel `Agent` spawns → 13 `fork failed`, not a quota problem

Dispatching 14 subagents in one burst on Pro produced 13 failures of the shape `fork failed:
Device not configured` — a macOS pty-allocation race (measured against a pool of 511 ptys, with
file descriptors themselves not exhausted), not a model-quota exhaustion. The same class of
failure has been observed independently on Mini under similar burst load.

**Lesson**: cap parallel `Agent`/subagent dispatch at roughly 3 per message on this fleet's current
hardware. Burst higher than that and the loss is not "some agents ran out of quota" — it is pty
exhaustion, and the fix is to stagger the dispatch, not to add cascade fallback.
