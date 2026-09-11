---
date: 2026-08-30
domain: compliance
client_case: none
sources:
  - PR #5218 (SUSPENDED draft, head a1799989d) — the lint this spec replaces
  - ~/.claude/projects/-Users-nuzantara-nuzantara/memory/MEMORY_MERGE_QUEUE_TRAPS.md — the PR #5036 receipt
  - scripts/mq_state_verdict.py (origin/main @ 5066d7a8d) — attestation order, no NOT_ARMED verdict
  - scripts/queue_shepherd.py (origin/main @ 5066d7a8d) — is_rearm_candidate, run_rearm_pass
  - .claude/rules/cicatrix-scars.md:1279 — W123 GOTCHA (b), the stale line
adversarial_review: codex
---

# L06-PR2b successor — the doctrine was settled by measurement and never propagated

> **Status: SPEC — no code changed by this document.** It discharges the Rule-8 suspension of
> PR #5218 (`ci(queue): a regression guard with zero catches today`), stopped because its rule's
> PREMISE was false rather than its implementation. Rule 8: *if the correction is itself wrong,
> the surface is under-specified — write the spec, do not open the third PR.*
>
> Date: 2026-08-30 · Author: Squad W (workflow track), Opus 5 · Base: `origin/main` @ `5066d7a8d`
> · Lineage: L06 lane, `docs/plans/2026-08-29-beyond-sota-craft-wave/`
>
> **Two adversarial rounds, two rewrites.** Round 1 (Codex GPT-5.6 sol) killed the first draft's
> direction and its harm model. Round 2 (Kimi K3) killed the second draft's central premise by
> following a citation the author had quoted but not opened. Both are recorded in
> §Adversarial review rather than deleted, because both errors are the class this spec is about.

---

## TL;DR

1. **The suspended lint is genuinely broken** — both blockers reproduced this turn (§1). It stays
   suspended. Do not re-open it in any lexical form.
2. **The question the lint was built around is already ANSWERED.** `auto=null AND queue=null` does
   **not** prove disarmed — measured on PR #5036 on 2026-08-26, with the refusal text
   `! Pull request #5036 is already queued to merge` obtained while both fields read "not armed"
   (§2). The receipt exists. The second draft of this spec claimed it did not.
3. **The defect is PROPAGATION, not doctrine.** The measurement corrected an earlier rule by the
   same author and never reached the two places that still carry the old one:
   `cicatrix-scars.md:1279` and `queue_shepherd.py:233-236` (§3).
4. **The live consequence is a false human-escalation P0**, not a bad merge and not a spurious
   re-arm (§4) — `rearm_pr` is unreachable on that path.
5. **The refusal-parsing convention already exists at three sites** (§5). `queue_shepherd` is the
   outlier, which makes this a one-organ job.

---

## 1. The suspended lint: both blockers reproduced on disk (2026-08-30)

PR #5218 shipped `scripts/ci/lint_queue_field_verdict.py`: for any tracked file containing a
null-comparison on `autoMergeRequest`, require the SAME file to also mention `mergeQueueEntry`,
`isInMergeQueue`, `"already queued"`, `"mq state"`, or an explicit waiver.

Head tree `a1799989d` extracted with `git archive | tar -x` and `git init`-ed — the tool exits
**3 (CANNOT VERIFY)** without a repo, correctly fail-closed, which was confirmed before trusting
any later rc.

**BLOCKER 1 — the rule absolves the disease.**

```python
def verdict(pr):
    if pr.get("autoMergeRequest") is None:
        if pr.get("mergeQueueEntry") is None:
            return "AUTO-MERGE DISARMED — re-arm needed"
    return "armed"
```

→ **rc=0**, probe file appears **0 times**. It reads both fields, so it clears the rule, while being
exactly the shape the rule exists to catch.

**BLOCKER 2 — the allowlist tripwire is form, not entity.** Appending an unconditional
`gh pr merge --auto "$PR" || true` to the orchestrator whose awareness the waiver rests on leaves
the scan **rc=0** and the tripwire still printing `still carries: mergeQueue(, already in the queue`.
It asserts the words are PRESENT, never that the guard is EFFECTIVE.

Both reproductions restored the tree and re-ran clean.

**The obvious replacement fails too.** Switching to *"the file emits a disarm verdict"*
(`grep -icE "DISARMED|re-?arm needed|not[ _]armed"`) returns **9** on `scripts/mq_state_verdict.py`
— and those nine are its docstring *explaining why the verdict must not exist*. A guard firing on
the prose that warns against the disease, hit on the second attempt.

## 2. The question is answered — the receipt exists, and this spec had to be told twice

`scripts/mq_state_verdict.py:11` opens *"WHAT THE QUEUE ACTUALLY LIES ABOUT (measured,
MEMORY_MERGE_QUEUE_TRAPS.md)"*. **Following that citation** to
`~/.claude/projects/-Users-nuzantara-nuzantara/memory/MEMORY_MERGE_QUEUE_TRAPS.md` yields the
primary record, verbatim (translated inline, original Italian):

> **CORRECTS the rule I wrote myself on 26/8: there is a WINDOW in which `autoMergeRequest` is
> already `null` and `mergeQueueEntry` has not yet appeared — both say "not armed" while the PR is
> perfectly fine.** Measured on PR #5036 … afterwards there were 32 runs on
> `gh-readonly-queue/main/pr-5036-…`, so it really had entered the queue. … **The decisive proof is
> not a field: it is the command's REFUSAL.** Re-arming I got
> `! Pull request #5036 is already queued to merge` while BOTH fields said "not armed".

That is attestation rank #1 — the refusal text — captured against the exact PR, alongside the
32-run count. **The transient is measured, not hypothesised.**

**The second draft of this spec asserted the opposite** — that no primary receipt existed and that
everything downstream was therefore blocked. It searched in-tree, found only the oracle's docstring
and a *synthetic* fixture (`scripts/tests/test_mq_state_oracle.sh:79`, which fabricates the shape it
is cited to corroborate), and stopped — **without opening the file the docstring it was quoting
names as its source.** The blocking prerequisite it invented was manufactured by an unfollowed
citation. That is the same defect as the lint's: judging by what a text *contains* rather than by
what it *points at*.

**Consequence for the doctrine.** There is no symmetric three-way split. The record explicitly
**corrects** the earlier rule, so:

| position | site | standing |
|---|---|---|
| `auto=null ∧ queue=null` ⇒ disarmed | `.claude/rules/cicatrix-scars.md:1279` (W123 GOTCHA b, 23/8) | **stale — self-refuted by the same author on 26/8**, correction never propagated |
| no instantaneous joint read can prove not-armed | `scripts/mq_state_verdict.py:11-24` | **established** by the #5036 receipt |
| *"Only BOTH null means truly disarmed"* | `scripts/queue_shepherd.py:233-236` | **wrong, and written 2026-08-27 — after the correction** |

## 3. The deliverable: propagate the correction, in three places

- **P1.** Commit the #5036 receipt in-tree so the next session does not have to find it in a memory
  file. `mq_state_verdict.py`'s own attestation order is the natural home.
- **P2.** Correct `cicatrix-scars.md:1279`. It is auto-loaded project instructions, so a stale line
  there is read by every session — the mechanism by which position C got written *after* the
  correction is most plausibly exactly this.
- **P3.** Correct `queue_shepherd.py:233-236`, whose docstring asserts the refuted rule under a
  `W111 guard` label that makes it read as the cure.

**Ordering matters: P2 before P3.** Fixing the organ while the scar file still teaches the old rule
invites the next author to re-derive it.

## 4. The live consequence, traced rather than inferred

`queue_shepherd.py` — LaunchAgent `com.nuzantara.queue-shepherd.10min.plist`, every 10 minutes:

| step | site | in the #5036 window |
|---|---|---|
| candidate gate | `:238-250` | BOTH-null **passes** — the only state the organ acts on |
| last ejection event | `:515-536` | last item is `Added` (or none) → **`None`** |
| classify | `:176-196` | `None` → **`UNKNOWN`** |
| decide | `:914-922` | not allowed → **P0: *"PR #N looks disarmed … Needs a human look"*** → `continue` |

**`rearm_pr` is never reached** — that path needs a prior `Removed` event still last AND classified
`INFRA`. The first draft claimed the organ "attempts a re-arm and GitHub refuses", having modelled
the candidate gate and inferred the rest.

Severity inputs, none of them yet counted: the alert consumes a shared Telegram budget that
`scripts/tg_notify.py:519-540` documents as exhausted 8 days of 21; `alerted_state` dedups only a
**delivered** alert (`:921-922`), so a failed send retries every tick; re-arm and janitor passes are
serial (`:1048-1049`), so false candidates delay `cancel_run`. **Severity: undetermined pending
measurement (A1).** The first draft's confident "P3" was asserted without any of these numbers.

## 5. The refusal-text convention exists at THREE sites — the outlier is one organ

- `scripts/mq.sh:196` — the origin (`already queued|auto-merge enabled|already enabled`)
- `scripts/lane_ship.sh:235` — same grep, and its comment names `mq.sh cmd_arm` as precedent
- `scripts/ci/queue_rearm.sh:228-230` — *"Judge the REPLY, not only the exit code (W104): 'already
  queued' is success, and a zero rc on an unexpected message is not."*

The first draft "proposed" this as a novel cure and named a five-file population. Both were wrong:
`scripts/queue_unstick.py:29-37` states it never reads `autoMergeRequest`, and
`scripts/queue_doctor.py:71-107` reports populations rather than deciding a re-arm.

**Caveat, measured and not glossed:** `scripts/ci/queue_rearm_population.sh:58` selects orphan
candidates on `autoMergeRequest == null` **alone** — a single-field read, weaker than
`queue_shepherd`'s joint one. Its downstream gate (`queue_rearm.sh` requires a `merge_group` run to
exist) means the transient produces "leave alone" rather than an action, so the pipeline
self-corrects. The "siblings keep the convention" framing is therefore true of the *arming* step and
not of the *selection* step, and is stated that way here rather than as a blanket claim.

## 6. Acceptance criteria

- **A1.** Measure before fixing: transient frequency, `UNKNOWN`-vs-`INFRA` split, P0s per week
  attributable to this branch, janitor delay. Severity is then stated from numbers.
- **A2.** P1/P2/P3 land, P2 before P3. Each cites the #5036 receipt rather than restating it.
- **A3.** The `UNKNOWN`-branch P0 gains a disambiguating step before alerting. Guilt — the transient
  shape produces **no** alert; innocence — a genuinely disarmed PR with no ejection event **still**
  alerts. Neither may be satisfied by prose.
- **A4.** Mutation-verified: inverting the disambiguator turns A3's guilt case red. Run with
  `PYTHONDONTWRITEBYTECODE=1` (W121 — a same-length mutation written in the same second is judged
  against a cached `.pyc`, and the verdict is manufactured by the filesystem).
- **A5.** If the disambiguator is refusal-parsing, it needs a fresh positive read of the queued entry
  after the refusal, unknown wording **fail-closed**, and a `gh`-version-bound adapter. A bare string
  match is form-not-entity and brittle to locale, stream, and rephrasing.

## 7. What this spec explicitly does NOT recommend

**Do not re-open the lint.** Two lexical discriminators were measured and both fail: "reads both
fields" absolves the disease (§1); "emits a disarm verdict" convicts the oracle's own warning prose
(§1). That refutes **those two heuristics** — it does not prove no guard is possible. An AST/dataflow
check, a structural delegation rule, or a behavioural gate remain open designs. But the population is
one organ, so a repo-wide guard is disproportionate to the surface either way.

## 8. Evidence provenance

| claim | how |
|---|---|
| #5218 BLOCKER 1 + 2 | reproduced on `a1799989d`, this turn, rc=0 both |
| "emits a disarm verdict" flags the oracle 9× | `grep -icE "DISARMED\|re-?arm needed\|not[ _]armed" scripts/mq_state_verdict.py` → **9**, this turn |
| **the #5036 receipt + verbatim refusal text** | `MEMORY_MERGE_QUEUE_TRAPS.md`, read this turn after round 2 named it |
| A is stale / self-corrected | same record: *"CORRECTS the rule I wrote myself on 26/8"* |
| `queue_shepherd` control flow to the P0 | four sites read in sequence on `origin/main`, this turn |
| refusal convention at three sites | `mq.sh:196`, `lane_ship.sh:235`, `queue_rearm.sh:228-230`, this turn |
| `queue_rearm_population.sh:58` single-field read | read this turn after round 2 raised it |
| Telegram budget exhausted 8/21 days | `tg_notify.py:519-540` — **refuter's measurement, not independently re-measured by me** |

## Adversarial review

**Two blind rounds, both non-Anthropic, both cross-family (generator ≠ grader). Neither returned
SHIP; both rewrote the document.**

### Round 1 — Codex GPT-5.6 sol (xhigh) on draft 1: DO-NOT-SHIP, 3 BLOCKER + 3 HIGH

| # | finding | disposition |
|---|---|---|
| B1 | the BOTH-null premise is laundered from a docstring; `cicatrix-scars.md:1279` says the opposite | **CONFIRMED on disk.** Draft 1 had the direction backwards. |
| B2 | the harm model is invented — `rearm_pr` is unreachable in the disputed window | **CONFIRMED on disk** (four sites). §4 rewritten; the proposed cure targeted an unreachable path and was deleted. |
| B3 | the refusal string is mis-cited to W126 (it is W123) and carries no rc; refusal-parsing is itself form-not-entity | **CONFIRMED.** Citation fixed; conditions moved to A5. |
| H4 | P3 severity ignores P0 budget, retry-on-failed-send, janitor serialization | **ACCEPTED.** Severity → undetermined, numbers made A1. |
| H5 | the cross-tab is semantically false; two files already parse the refusal; `queue_unstick` does not read the field | **CONFIRMED on disk.** Inverted draft 1's headline. |
| H6 | "not lintable in any form" overreaches | **ACCEPTED on argument.** §7 narrowed. |

### Round 2 — Kimi K3 on draft 2 (the REWRITTEN bytes): DO-NOT-SHIP, 1 BLOCKER + 2 HIGH + 2 MEDIUM

| # | finding | disposition |
|---|---|---|
| B1 | **A0's premise is false — the #5036 receipt IS preserved**, in the file the oracle's docstring names, carrying the verbatim refusal text and the 32-run count | **CONFIRMED by opening the file.** Dispositive. Draft 2's entire "everything is blocked, saying so is the deliverable" posture was manufactured by not following a citation it had quoted. §2/§3 rewritten; the deliverable became propagation. |
| H3 | the three-way split's symmetry is manufactured — A was self-refuted by its own author days later and simply never propagated | **CONFIRMED** in the same record. The table in §2 now states standing rather than pretending to neutrality. |
| H2 | "auto-loaded into every session" is false — the file is ~296 KB against a 40 KB threshold, no hook loads it, and W123 sits at line 1234/1517 | **REFUTED by direct observation, and the rhetoric removed anyway.** `cicatrix-scars.md` is present in this session's context as project instructions, W123 GOTCHA (b) included — the mechanism is the harness's `.claude/rules/*.md` injection, not a hook or a CLAUDE.md import, which is what round 2 searched. The 40 KB line it cites is the archive file's *stated intent*, not an enforced truncation. But the "widest reach" weighting it objected to was load-bearing only for draft 2's symmetry argument, which B1 removed — so §2 no longer argues from reach at all. |
| M4 | line citations off by one: `queue_rearm.sh` 229-231 → **228-230**; `queue_shepherd.py` 920-921 → **921-922** | **CONFIRMED on disk. Both corrected** (§5, §4). |
| M5 | the convention has a THIRD site (`mq.sh:196`, the origin) and `queue_rearm_population.sh:58` is a single-field read the "siblings" framing glosses | **CONFIRMED on disk. Both added** to §5, including the caveat against this spec's own framing. |

**Nothing was deferred or argued away.** Round 2's BLOCKER inverted the conclusion of round 1's
rewrite — which is the strongest argument in this document for why the two-seat, two-round rule is
not ceremony: a single round would have shipped a confident, well-cited, wrong spec.
