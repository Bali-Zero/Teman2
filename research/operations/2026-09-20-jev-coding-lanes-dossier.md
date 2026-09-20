---
date: 2026-09-20
domain: operations
client_case: none
adversarial_review: codex
sources:
  - infra/guard-conformance/registry.json
  - infra/guard-conformance/check_guard_conformance.py
  - scripts/guardrails_static_core.py
  - scripts/ci/bites_parse.py
  - scripts/memory/mos_recall_sessionstart.py
  - scripts/memory/recall_eval.py
  - https://docs.typesafe.ai/primitives/noul.md
  - https://docs.typesafe.ai/model-jaggedness/jev-1.13.md
---

# Jev on the CODING side — eight lanes inside the harness

Date: 2026-09-20 · Machine: M5 · Companion to
`2026-09-20-jev-typesafe-arsenal-dossier.md` (PR #6909), which covered the client-facing side.

Every repo claim carries the file and line it was read from. The first draft of this dossier
carried four that did not survive a refuter checking them — they are recorded in
**§8**, not quietly patched, because three of the four were the same error: *reading a file
quickly and then quoting it from memory*.

---

## 1. Why this side is cheaper, and where that claim stops

The client-side dossier is gated on §4, the PII boundary: every lane there carries a
user-supplied half needing redaction. Source code, a CI log and `registry.json` do not carry a
client's passport number, so the expensive precondition is mostly absent.

**Mostly, not entirely, and the first draft overstated it.** Its rule was "send diff hunks and
guard source, never fixtures" — while C1's own label set is *extracted from tests*, which are
fixtures. The rule contradicted the lane it was written to protect. Three corrections:

- A diff can carry a secret. That is the entire premise of `detect_secrets` and of cicatrix #4.
  Anything sent externally passes the same `redact_for_external()` the client lanes use — the
  boundary is an OUTPUT boundary and does not care that the output is a code review.
- A CI log can carry a secret for the same reason, plus client data when the failing test is a
  fixture built from a real case.
- Extracting guard test inputs is allowed **because each extracted case is read once by a human
  before it enters a label set** — that human pass is the redaction, and it is the difference
  between "we send fixtures" and "we send 70 reviewed strings".

So: cheaper, because the volume is low and the review is one-time. Not exempt.

---

## 2. The thing this repo cannot currently do

`cicatrix-superscar.md` #3: *«su entità mai substring»*. One of four dominant families,
65-75% of incidents.

The first draft said a Python guard "has exactly one instrument: pattern matching". **That is
false**, and the refuter caught it with the repo's own counter-example:
`check_guard_conformance.py:84-92` parses an AST precisely so that "strings and comments cannot
create phantom guards or hide real ones".

The accurate statement is narrower and survives:

> A regex judges **spelling**. An AST judges **structure**. Neither judges **meaning** — an AST
> can tell you this line calls `client.create()`; it cannot tell you whether that client reaches
> a paid Anthropic endpoint.

And the family persists under the better instrument. From `guardrails_static_core.py` (comment
above the force-push rule):

> `git push --force origin feature/redesign-main-nav` is NOT a force-push to main — the old
> `.*\bmain\b` blocked it (over-match, superscar #3, vaccine 2026-06-16).

The cure applied was a more careful regex. It works for `main`. It is the same instrument with a
steadier hand, which is why #3 is a *family* and not a bug: each entity gets its own incident.

---

## 3. Where the gap is provable in two lines

Builder Contract §3 insists on a semantic reading:

> …an alias, a renamed env var, a wrapper library or a Bedrock/Vertex route reaches the same
> endpoint without either literal, and is equally banned.

What enforces it (`scripts/guardrails_static_core.py:108-116`) is two regexes:

```python
(re.compile(r"\bANTHROPIC_API_KEY\s*=\s*['\"]?sk-", re.IGNORECASE), ...)
(re.compile(r"\bANTHROPIC_API_KEY\s*=\s*['\"]?ant-", re.IGNORECASE), ...)
```

The literal spelling **plus a key prefix**. A renamed env var passes. `LLM_KEY =
os.environ["UPSTREAM_TOKEN"]` passes. The contract states an entity; the machine enforces a
spelling.

### 3bis. The consumer is not what the first draft said — and this reframes two lanes

`is_dangerous()` (`:343-351`) takes **the PreToolUse JSON payload**: `{"tool_name",
"tool_input"}`. It classifies *a command an agent is about to run*. It never sees a diff.

Worse, and the module's own docstring says it (`:18-32`):

> There are **three independent copies** — this repo-vendored/CI-tested core, the HOME hook, and
> the HOME daemon — kept in sync by discipline (`scripts/guardrails_sync_check.py`), not by a
> shared import. A fix landed here does NOT reach the two HOME copies automatically; propagating
> it is a separate, operator-gated step.

This is cicatrix #1 (HOME-fork drift) documented inside the file the lane was going to modify.
Consequences, both binding:

1. **C1/C2 split in two.** Judging *a command before it runs* (PreToolUse) and judging *a diff
   before it merges* (CI) are different lanes with different consumers. The first draft merged
   them and named the wrong consumer for both.
2. **A green CI run proves nothing about the live guard.** Landing an adjudicator in the repo
   core leaves the HOME hook and the HOME daemon untouched — cicatrix #2, exactly the failure
   this dossier's client-side sibling warns about in its §7. Any PreToolUse lane's prove-live is
   an observation **on the HOME copy after operator-gated propagation**, or it is not one.

The CI-side lane (diff adjudication) has no such problem: CI runs the repo copy by definition.
**That is now the reason the diff lane goes first** — not its value, its provability.

---

## 4. The label sets — corrected count

The first draft claimed the registry gives 70 guards each with guilt and innocence proofs. Read
properly (`json.load`, counting entries carrying both keys):

| | |
|---|---|
| Guards registered | **70**, across 15 surfaces |
| Carrying **explicit** `guilt` + `innocence` | **55**, across **9** surfaces |
| The rest | carry `tests`, `delegated_to` or `symbols: {}` — a test file is named, the two roles are not separated in the registry |
| **`guardrails_static`** — the surface of the main lane | `{"source": ..., "tests": [two files]}`. **No guilt/innocence split.** |

So the asset is real but smaller than claimed, and it is **absent exactly where the flagship
lane wanted it**. The 55 are in `evidence_pack_lint` (18), `bridge_reply_guards` (10),
`bites_parse_observe_allowlist` (9), `wr2_editorial_pregate` (7), `required_workflow_conformance`
(6) and four singletons.

What survives of the original argument: the registry is a **by-product of a merge rule** — no
guard merges without its proofs — so where it is complete it stays complete without anyone
maintaining it for this lane's sake. It is still the best label asset here. It is not 70.

Other assets, verified: `scripts/ci/bites_corpus.yaml` (573 lines, ~138 entries, already data);
`scripts/memory/recall_eval.py` — a real harness, "a fixed 12-scenario query → expected-file set,
plus a baseline comparison against the existing `mem recall` CLI". *That* is the baseline. The
first draft called the 0.35 relevance threshold a baseline; it is a threshold (`:43`).

---

## 5. The eight lanes

Three rules govern every one. The first two are inherited; the third is new and is the most
important thing the refuter produced.

1. **Agreement is not correctness** — a comparative run needs a third independent label.
2. **A benchmark is not a deploy** — and per §3bis, for anything touching the guardrails, a
   merge is not a deploy either.
3. **The adjudicator may only ADD blocks, never remove one.** See below.

### Rule 3, stated properly, because the first draft got it backwards

The first draft wrote: *"A guard fires only on both"* — regex AND Jev — and called it additive.
It is the opposite. `regex AND Jev` fires **less** than `regex` alone, so a single false
negative from the model silently authorises a violation the repo blocks today. Calling the
timeout fallback a safety net compounded it: the fallback covers the API being *absent*, not the
model being *wrong*, and wrong is the likelier failure.

The correct shape is one-directional:

```
block  if  regex_fires  OR  jev_says_violation
```

Jev can only make the guard stricter. A model failure, a hallucination, an injected diff that
steers it — every one of those produces at most a false alarm costing a human ten seconds, never
an unblocked violation. This makes the under-match half of cicatrix #3 (the half nothing
currently addresses) the first thing to attack, and it leaves the over-match half — *relaxing* a
guard on Jev's word — explicitly out of scope until there is calibration evidence and a human in
the loop. **Over-match relief is the lane this dossier declines to design.**

### C1 · Diff-side entity adjudication (CI)
**Shape:** on each PR, hunks touching LLM-client or dependency code go to Jev as `Noul`s, one per
route named in §3 (direct / wrapper / Bedrock-Vertex / renamed variable). Fires in addition to
the existing checks, never instead.
**Known limit, from the refuter and not resolved by design:** a diff can call a *pre-existing*
wrapper without showing that wrapper's endpoint anywhere in the diff. Single-hunk state cannot
see it. Mitigation is to include the imported module's source when the import is local — and to
state plainly that **cross-file indirection at depth >1 is outside this lane's reach**.
**Consumer:** a CI check on PRs. **Prove-live:** a PR blocked with no `ANTHROPIC_API_KEY` string
in its diff. Bench: ~20 constructed routes today's regexes miss, ~40 innocent LLM-client diffs,
both rates reported; the constructed set must include deliberately obfuscated forms, since a
diff is attacker-controlled text in the threat model where the attacker is a confused agent.

### C2 · PreToolUse command adjudication — **blocked on propagation, not on code**
Same idea against `is_dangerous()`'s payload: judge what the command *does*, not how it is
spelled. The 55 registered guilt/innocence cases are the natural bench for the surfaces that
have them.
**This lane cannot prove itself by merging.** Three copies; the live ones are in `$HOME` behind
an operator-gated propagation step. Its prove-live is an observation on the HOME daemon after
propagation, and the lane should not open until that step is scheduled. Listed second because it
is blocked, not because it is weaker.

### C3 · `Bites:` — judge the consumer, not the shape
`bites_parse.py` validates form and extracts `consumer` as a string (`:851`) without ever
judging it, while the contract's rule is semantic: *"A future job will run it is not a
consumer"*. The module's docstring (`:4-5`) states the scale: **"110 of the 177 PRs merged since
2026-09-01 carry a `Bites:` line, and nothing reads any of them."** (The first draft quoted this
as "177 PRs carry a Bites line" — a number changed inside quotation marks. See §8.)
**Shape:** `Choice` over {live consumer named / future job promised / vague}, state = the block
plus the diff, so "ships in the same PR" is checkable.
**Prove-live:** rejecting a form-valid line proves the gate fires, not that it is right — so the
bench is ~60 of the 110 historical lines, labelled by hand first, precision and recall reported
against that.

### C4 · CI red triage
*"Never rerun a red check before you know WHY it is red."* Today that "why" is entirely human.
`Choice` over {real failure / stale merge ref / flake / infra / pre-existing red}.
**Honest limit:** a log tail plus changed paths often cannot separate flake from regression —
that distinction frequently needs a re-run, which is the very thing the rule forbids doing
blindly. The lane's realistic output is **"safe to rerun / do not rerun / needs a human"**, which
is the decision actually being made, rather than a root cause it cannot see.
**Labels do not exist:** start by recording the cause of the next ~50 reds as they are diagnosed
by hand. Fourth wave by evidence.

### C5 · Gear triage for `modus`
`Score` on scope + `Score` on blast radius, composed in code; gear becomes a function of two
stored numbers with movable thresholds. Code counts files and lines — §3 jaggedness forbids
asking Jev to count. **No live consumer is proposed here yet**, so this stays a benchmark until
one is: the natural one is the skill itself printing a suggested gear.

### C6 · Subagent report vs boilerplate
On 2026-09-20 three subagents out of three closed with leave-dirty boilerplate instead of a
report. `Noul`: *"does this report state findings specific to this task, or would it fit any
task?"* plus `Noul` on whether claimed verifications name a command.
**Consumer:** `infra/claude-hooks/subagent_stop_verify.py`. **Limit the refuter found:** that
hook permits continuation after it fires, so the lane makes the failure *visible*, not
*impossible* — which is the honest claim and still worth having.

### C7 · Memory recall re-ranking
`mos_recall_sessionstart.py` scores `recency × importance × BM25`. BM25 is lexical: a memory
phrased differently from the prompt is invisible to it.
**The refuter's correction, which changes the design:** re-ranking cannot recover what the
shortlist excluded. If BM25 never surfaces the memory, re-ordering the top-20 does nothing. So
the lane must **widen the shortlist first** (top-50 at a lower threshold, which costs nothing —
it is a local score) and let Jev re-rank that. A narrow shortlist re-ranked is theatre.
**Prove-live:** `recall_eval.py`'s 12 scenarios against its `mem recall` baseline — and because
those 12 were used to tune the current threshold, reusing them alone is not independent
validation: add scenarios drawn from sessions after the tuning date.

### C8 · Skill suggestion
Carried from the client-side dossier's L8, unchanged.

---

## 6. Sequence

| Wave | Lane | Why here |
|---|---|---|
| 1 | **C1** (diff-side) | CI runs the repo copy, so it can actually prove itself |
| 2 | C7 | harness + baseline exist; needs the shortlist widened first |
| 2 | C3 | corpus exists; 60 hand labels needed |
| 3 | C6 | small; makes every later delegation cheaper |
| 3 | **C2** (PreToolUse) | blocked on operator-gated HOME propagation, not on code |
| 4 | C5 | needs a live consumer defined |
| 4 | C4 | needs ~50 hand-diagnosed reds recorded first |
| — | C8 | inherited; no new evidence since PR #6909 |

C1 ships with the shared `typesafe_client.py` + `redact_for_external()` from the client-side
dossier's wave 1, whichever lands first.

---

## 7. What would make this a bad idea

- **A guard that calls the network can hang.** Hard timeout; on timeout the existing verdict
  stands unchanged. Cicatrix #8.
- **Two systems to reason about.** Log both verdicts always, never only the composed one.
- **Jev can be steered by the text it judges** (§3 jaggedness) and a diff is agent-authored
  text. Rule 3 is what makes this survivable: steering it produces a false alarm, not a bypass.
- **A new external dependency near the push path** — first consumer is CI, not the local hook,
  and disabled-without-key is the default.
- **Cost and quota are not modelled here.** At $0.042/Mtok the spend is trivial, but a CI check
  that fails closed on a 429 blocks merges. Retry with backoff, then fail *open* to the existing
  verdict — the one place where degrading to today's behaviour is correct, because Rule 3 means
  today's behaviour is the stricter of the two.

## Adversarial review

Codex reviewed the first draft as non-author, with file:line citations, and produced eight
objections. **Seven survived verification and rewrote this dossier**; the eighth was partly
right and is recorded as such. Each was re-checked against the file before being accepted — the
point of §8 is that the refuter was right about *what was on disk*, which is checkable, not
about a matter of taste.

### The four factual errors, all the same error

1. **A number changed inside quotation marks.** The draft quoted `bites_parse.py` as *"177 PRs
   merged since 2026-09-01 carry a `Bites:` line"*. The file says **110 of the 177**. Quoting
   from memory a file read minutes earlier, with quotation marks around it — the exact shape
   W113 exists to name.
2. **Wrong consumer.** C1/C2 named `guardrails_static_core.py` as a diff-judging guard. It takes
   a **PreToolUse payload** (`:343-351`). Two lanes were merged that have different inputs.
3. **Three copies missed.** The same file's docstring (`:18-32`) says a fix there does **not**
   reach the live HOME hook and HOME daemon. The draft's prove-live was a CI log — cicatrix #2
   in a dossier that cites cicatrix #2.
4. **Registry overcounted.** "70 guards each with guilt and innocence" → **55 across 9 of 15
   surfaces**, and `guardrails_static` — the flagship lane's own surface — has none. Also:
   `0.35` is a threshold, not a baseline; the baseline lives in `recall_eval.py`.

### The design error, which was worse than the factual ones

5. **`regex AND Jev` is not additive — it is a relaxation.** The draft wrote "a guard fires only
   on both", called it additive, and called the timeout fallback a safety net. AND fires *less*
   than regex alone: one model false negative authorises a violation the repo blocks today, and
   the fallback covers absence, not wrongness. Now Rule 3 (§5): **OR, never AND**; Jev may only
   add blocks. This also moved over-match relief out of scope entirely.

### Three limits now stated instead of assumed

6. **C1 cannot see cross-file indirection** — a diff can call a pre-existing wrapper without
   revealing its endpoint. Stated as a boundary of the lane.
7. **C7's re-rank cannot recover what the shortlist dropped** — so the shortlist widens first.
8. **C6's hook permits continuation** after firing, so the lane makes boilerplate visible, not
   impossible. Partly conceded: visible is still the fix for a failure nobody currently sees.

### The one not fully accepted

The refuter called C1/C2 a **BLOCKER — "non pronti per l'implementazione"**. Correct for C2,
which is why it moved to wave 3 behind HOME propagation. For C1 the objections were about the
*bench* and the *composition rule*, both now specified — so C1 is not blocked, it is specified.
That is a disagreement about readiness, recorded rather than resolved, and the next reader is
better placed to judge it than either party.

**Generator was not grader, twice in one day, and both times it changed the plan.**
