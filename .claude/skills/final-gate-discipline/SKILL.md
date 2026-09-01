---
name: final-gate-discipline
description: "Load at modus VERIFY/SHIP+ARM: the final-gate checklist + five questions to answer with a command run NOW. Use when a subagent reports completion or a merge is about to be armed."
---

## Notes (moved from description 2026-09-02)

Checklist framing (as written): "the non-delegable final-gate checklist for Fable 5." Additional trigger: you are about to say 'finished' on a feature/fix/doc change.

# Final-gate & pre-"done" verification discipline

> Born 2026-08-03, after the megatopic-0 (VCR) incident: a review-only subagent
> self-orchestrated an entire pipeline, committed, opened a PR, and armed
> auto-merge — bypassing the gate below. Written down so the next session
> doesn't repeat it. This file existing is not the fix — see "Self-application"
> at the bottom.

## Part 1 — The final gate is never delegated

You (Fable 5, or whoever holds the gate this session) are the final,
non-delegable check on this work — never a subagent's job, never
rubber-stamped from a summary.

- Re-read the actual diff/file on disk yourself. A subagent's self-report of
  "what I did" is a claim, not a fact — verify it before acting on it.
- Check every dispatched subagent stayed inside its stated mandate
  (review-only ≠ commit + PR + auto-merge). A scope violation is a finding to
  contain and report, not a shortcut to accept just because the output looks
  fine.
- If parallel reviews exist, name which seat said what before treating
  agreement as evidence — never cite consensus without declaring the
  reviewers' parentage (they may have reviewed different artifacts; scar W100).
- Before merging, scan every doc this change touches or contradicts
  (CLAUDE.md, skills, READMEs, scar files) for claims that no longer match
  reality — fix the drift in the same change, don't leave it as debt.
- Only arm/merge after YOUR OWN read is complete. "A subagent reviewed it" is
  never a substitute for the gate.

## Part 2 — Before you say "done," answer these five

Each one with a command **executed right now**, not recalled from memory or
from an earlier tool call in this conversation.

1. **Who calls it?** Not "it exists," not "it's registered" — grep the name
   across the repo, excluding the file that defines it and its tests. Zero
   callers means you haven't finished it, you've declared it.
2. **What other surface describes it?** Docs, README, page, changelog,
   comment. If one of those says it works and question 1 says zero, you've
   written a lie, not a feature.
3. **What did I just write that will expire?** Every number, path, or "X is
   broken so we always do Y" hardcoded into code or comments is a frozen
   measurement — say what re-measures it, or don't freeze it.
4. **Can my probe actually say yes?** A negative result ("0 found," "no
   errors") only counts if you've run the same check against a case that
   MUST come back positive. A failing command and a command that finds zero
   look too much alike.
5. **Where does the work actually live right now?** Not committed and pushed
   = doesn't exist. And armed is not landed — the proof is open until it's
   merged.

**Naming corollary:** the name of anything that changes lies about its own
content unless you prove it. If you call it `v2`, show a diff against `v1`
that isn't cosmetic.

**Where each question comes from** (illustrative precedent, not all
independently re-verified in this file — treat as pointers to check, not
settled fact):

| #      | Failure shape                                                                                                              |
| ------ | -------------------------------------------------------------------------------------------------------------------------- |
| 1      | A tracking event (e.g. `trackLeadCreated`) plus ~9 siblings: registered, never called anywhere.                            |
| 2      | A `DOCUMENTATION.md` describing three events that don't actually fire.                                                     |
| 3      | An "X is broken so we always do Y" that hardened into a permanent memory rule, false for days before anyone re-checked it. |
| 4      | A sweep that reported "0 orphans out of 1" — the counting logic itself was broken, and the zero was read as clean.         |
| 5      | Two PRs armed the same evening that still weren't on `main`.                                                               |
| naming | `concept-v2` that was `concept-v1` with a renamed/added `<div>`.                                                           |

## Self-application

A skill file that exists but nothing loads is exactly the disease this file
describes (scar family #2, "esiste ≠ armato"). Arming means: referenced from
`.claude/skills/modus/SKILL.md`'s VERIFY and SHIP+ARM stages (done in the
same change that added this file — verify with
`grep -n "final-gate-discipline" .claude/skills/modus/SKILL.md`). If that
reference is ever removed, this file goes back to being undead text — the
grep above is the tripwire, not a one-time proof.
