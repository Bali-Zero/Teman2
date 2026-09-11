# SPEC — SHELL-ROUTE block v1: what delimits the block a guard must check

date: 2026-08-29 · owner: me (M5, infra/acl-guard lane) · status: normative, pre-implementation
origin: PR #5199 → #5201 → gate PASS-WITH-CONDITIONS; Agent PR Contract rule 8 (depth 1) routed
this surface to a specification rather than a fourth parser patch.

**Status: normative.** A guard may be built from this file without inference. Where an
implementation and this file disagree, this file is wrong or the implementation is — say which,
in a PR, rather than resolving it silently in code.

Constrains `infra/tailscale/policy.hujson`. The guard that must satisfy this spec is
`scripts/tests/test_tailnet_acl_deny_by_default.py`; the apply and enrolment runbooks live in
`docs/runbooks/tailnet-acl-apply.md` and `infra/tailscale/enroll-team-device.md`.

**Implementation is a separate PR, after this spec is adjudicated.** Landing both together would
mean the spec was never a spec, only a commit message.

## Why this file exists

The `policy.hujson` header carries a block, marked `SHELL-ROUTE:`, documenting the one exposure
the whole policy was written to contain: `tailscale serve` on Pro publishing `/term` ->
`127.0.0.1:7681`, an unauthenticated writable `ttyd` shell, tailnet-wide over port 443. A CI check
asserts that block still says so, because a policy whose reason has been deleted from it is a
policy the next reader will "simplify".

That check has now been wrong three times, each time in a different direction:

1. It scanned the **whole file** for the tokens `7681`, `/term`, `ttyd`. Gutting the block while
   the tokens survived anywhere else in the file passed.
2. Scoped to the block (PR #5199), it inferred the block's end from a decorative `// ====` fence
   and, finding none, silently ran to end-of-file. Deleting the fence restored bug 1.
3. Made strict (PR #5201), it terminated on the first non-comment line. Deleting the fence became
   fatal — but **relocating** it did not, and neither did supplying a fresh one.

Each fix closed one instance and left the class open. The class is this:

> **"Are these tokens somewhere inside this window?" is answerable by anyone who controls either
> the window or the tokens.** Hardening the window moves the bypass; it never closes it.

The block had no **identity**. It was found by a substring search any line can satisfy and bounded
by a fence any line can supply. This spec gives it one.

### The self-satisfying check

Bug 1 was worse than "the tokens might survive elsewhere in the file". Measured on `origin/main`,
`policy.hujson:105-106` reads:

```
//   FILE-WIDE: no unknown top-level key; the SHELL-ROUTE block below must still contain `7681`,
//   `/term` and `ttyd` — checked WITHIN the block, not anywhere in the file, which is what it
```

All three tokens, sitting in the sentence that explains the check is restricted to the block. With
the span running to end-of-file, **the sentence asserting the restriction is what defeats it.**
Delete the entire SHELL-ROUTE block, fabricate nothing anywhere, and the check still passes.

**A check whose evidence includes its own explanation cannot fail, and every green it ever emitted
was uninformative.** Four adversarial rounds, two adjudicators and a mutation harness went past
this, because all of them asked whether the check was _tight_ and none asked what was _satisfying_
it. Rule R6 exists to stop it recurring.

**This predates the fixes.** On `main` the check has been decorative for its entire life. PR #5199
and PR #5201 did not create this; #5201 narrowed the span enough to make the check _capable_ of
firing at all. Anyone reading the history needs that stated, or this spec reads as a fix for a bug
those PRs introduced, which is not what happened.

### The generalisation, which is bigger than this block

> **A wrong comment provokes suspicion; a right-sounding one grants permission to stop. The
> artifact that should trigger scrutiny is instead what satisfies it.**

That is the parent formulation. Everything below is an instance of it, and it explains _why_ these
defects are hard rather than merely cataloguing that they are: each one produces an artifact that
looks like evidence of correctness, so the reviewer's search terminates on contact.

R5 and R6 are two faces of one disease, and it is not confined to this guard. **Every instance
below was measured directly by this lane** on the night of 2026-08-29, in unrelated places — some
in checkers, some in the transport and the ref that feed them — **except where a bullet says
otherwise on its own line.** Anything marked second-hand is listed because the shape matches,
never as evidence, and should be re-measured before it is built on.

(Provenance is carried per bullet rather than as a total, per the corollary below. An earlier
draft of this paragraph counted them, and the count was false two paragraphs later.)

- the ACL token check, satisfied by the sentence explaining the ACL token check;
- two `PENDING-ARMS.md` rows written as `- REOPENS …` and `- NOTE …`, which look exactly like
  ledger rows to a reader and are invisible to `ENTRY_START_RE` (`^-\s*open(?:ed)?\s+DATE`), so
  the alarm that exists to catch unarmed conditions could never have fired on them;
- a `grep -n "^- open"` used to decide whether rows existed at given lines, which structurally
  could not see the `- CLOSED` rows that were there;
- **the transport layer.** `.claude/skills/modus/PENDING-ARMS.md` is 2.25 MB, and the GitHub
  contents API answers a file that size with `encoding: "none"` and an **empty** `content` field —
  measured: `encoding='none'`, `content` length **0**, `size` 2250307, **no error and no warning**.
  A gate base64-decoded that nothing and reported **1082 rows lost**, i.e. "this branch destroyed
  the ledger" — an artefact of its own probe. It was caught only because the number was absurd; on
  a smaller file the same bug yields a _plausible_ wrong number that nobody questions. Cure:
  `Accept: application/vnd.github.raw` (returns the full 2250307 bytes) or `git show`;
- **the stale ref.** `git show main:<path>` returned 1453389 bytes for that same file while
  `git show origin/main:<path>` returned 2250307 — because the local `main` in that worktree is
  **516 commits behind**. Same command shape, same file, a 0.8 MB difference, no error. Always
  `origin/main`, never `main`.
- and — **reported by another lane, not measured here** — the `confirm_sent` defect. It is listed
  because the shape matches, not as evidence; anyone building on it should re-measure it first.

The shared shape: **a probe answers a narrower question than the one asked of it, and the narrow
answer is indistinguishable from the broad one.** Every one of these reported _nothing_, and
**nothing reads exactly like absence.**

Hence the rule the last two force, which is mechanical and cheap: **a probe that can silently
return nothing needs a positive control.** Show it producing a NON-empty, KNOWN answer on the same
call path, in the same run, before believing an empty one — because "zero" and "unreadable" are
the same output, and so are "no rows" and "no file".

So the operative question is never _"is the check tight?"_ and never _"is the row there?"_ It is:

> **"What would make this probe report RED — and would the alarm actually fire?"**

Answer it by reading the checker, not by reading the checked. Grep the parser; do not trust the
shape of the data. That question is what finally caught **every instance listed above**, in each
case after review had already passed over it. (Phrased without a number on purpose: this list has
already grown twice while being written, and a hard-coded count beside a rule about unmeasured
claims is the corollary below waiting to happen.)

#### A deleted claim is a decision, not an absence

The union-merge check in this repo guards against a row that was deliberately deleted being
revived by a merge driver. **The same hazard arrives through a person, and nothing guards that
path.** Measured on the night of 2026-08-29: the claim _"an armed PR that goes CONFLICTING gets
disarmed"_ was generalised from a single observation, someone correctly deleted it as
over-generalised — and this lane then produced a second measurement that agreed with it and came
within one message of restoring it. The second measurement was wrong; the deletion was right.

So: **re-adding a deleted claim requires the same evidence bar as adding it the first time, not
merely a fresh measurement that agrees with it.** A deletion carries information — someone judged
the claim unsupported — and a new observation consistent with the deleted claim is evidence about
the claim, never evidence about the judgement that removed it. Before restoring one, find out why
it was deleted.

**And the answer was already written down, in context, unread.** The fleet memory index carries
_«nessun campo singolo dice "è armata"» — `mergeQueueEntry.state`, solo GraphQL_. That line is
injected into every session. Four agents, including two who had read it, spent an hour
re-deriving it from scratch. It is the second instance the same night of a documented fact failing
to prevent the thing it documents (the other: a W97 admission on a different scar), which makes it
a pattern rather than an anecdote: **documentation in context does not prevent the error it
describes.** Only an executable check does — which is the entire argument for putting R1-R6 in a
test rather than in a comment, and the reason this spec's own rules must end up as assertions.

> **CORRECTED 2026-08-29, hours after this file first landed.** The paragraph that stood here
> recommended _"prefer the event log to the rendered field"_ and justified it with a specific
> claim: that `autoMergeRequest` **reads NULL while a PR is CONFLICTING**. That claim has since
> been measured false — #5227, live and genuinely `CONFLICTING`/`DIRTY`, carried the field **SET**
> — and the recommendation it supported does not survive either, because the timeline emits **no
> event at all** for the transition that actually nulls the field. Consulting the event log would
> have returned silence and been read as "nothing happened". The correction is kept in place of
> the original rather than quietly swapped, because this document's own rule is that a deleted
> claim is a decision: the next reader is entitled to see that this passage was wrong and how.

What actually happens, measured end to end on #5228: the field was **non-null** at 09:58:10Z and
09:58:28Z while `mergeStateStatus` was `BLOCKED`, unqueued, with checks still running; the PR was
enqueued at 10:02:59Z; the field read **NULL** at 10:03:00Z — with exactly one
`AutoMergeEnabledEvent`, zero `AutoMergeDisabledEvent`, and no re-arm. **The queue consumes the
auto-merge request on entry.** Nothing was lost; a different subsystem took ownership.

So the durable lesson is not about event logs versus fields. It is about the **polarity of the
instrument**:

> **When every probe you have can only report an ABSENCE, you are measuring your instruments, not
> the system. Go and find the field that some subsystem populates on purpose.**

Every probe tried here — the field, the disable event, the refusal of `gh pr merge --auto` —
reported absences, and absence is exactly what _fulfilment_ and _revocation_ have in common. The
instrument that settled it asserts instead: **`mergeQueueEntry` present is positive proof the arm
was live**, because GitHub enqueues on the strength of that very request. Note the corollary,
which the three-state reading in the fleet memory already had: **NULL alone is ambiguous** — a
never-armed PR and an armed-then-queued PR both read NULL, and only the _pair_ of fields
separates them. A single field was never going to answer this, in either direction.

#### The insight sometimes comes from thinking; the detection never does

The subsections that follow were found separately, in unrelated subsystems, on one night. State
the common thread precisely, because the loose version is false and the precise one is stronger:
reflection is perfectly capable of producing a _principle_ — someone noticing that "merge and
re-arm" contradicts "read before you touch" needs no tool. But **nobody would have known three
subjects were burned** without a timeline query returning enables at 09:05:00Z, 09:16:10Z and
09:48:47Z; nobody would have known a completeness claim was bounded by its own instrument without
grepping the reporter; nobody would have known a parser design blessed the exact row it was built
to catch without running it against the real corpus.

That concedes what an opponent would say — _yes, you can reason your way to the principle_ — and
shows it does not help. In the third case below the principle was not merely available: it had
been **applied by the same person an hour earlier, in this very document**, and it still did not
fire. Availability was never the bottleneck; detection was. Hence: **reviewing tells you whether
something sounds right; running it tells you whether it is.** A specification that has not been
executed against the real data is a hypothesis wearing a schema.

#### When the state is itself under investigation, the repair must come second

The standing instruction for a branch whose base has moved is to merge and re-arm in one motion.
It is correct for every ordinary case, and it destroys the one case where the arm state is the
thing being measured — because re-arming makes _"the arm survived"_ and _"it was dropped and I
restored it"_ produce identical observations.

Measured 2026-08-29: three lanes each burned an observation by repairing before reading — #5210 at
09:05:00Z, #5207 at 09:16:10Z, #5213 at 09:48:47Z. Three independent agents, one instruction, the
same loss. **Before repairing a state you are also trying to measure, take the reading first.** The
repair is never urgent on the scale of one API call; the observation is destroyed permanently. This
covers every probe that mutates what it inspects — a restart that clears the log you were about to
read, a re-run that replaces the artifact that failed, a `--fix` that erases its own evidence. The
failure is not carelessness: the instruction and the investigation are each correct and jointly
incompatible, and only the investigation knows it.

#### Two observers disagreeing about a live system are usually disagreeing about sampling

Every cross-lane contradiction that night — three of them, each of which killed the previous
explanation — turned out to be two agents sampling a _moving_ system at different moments and
comparing the answers as though they were commensurable. None of the systems were inconsistent.
The readings were.

What settled it was **one simultaneous read across eight PRs**, not more readings over time. So:
**when two observers disagree about a live system, suspect the sampling before the system** — and
prefer one wide simultaneous snapshot to any number of sequential ones, because sequential reads
of a moving target cannot be differenced.

#### A PR can outrun its own adjudication

Measured on this document's own PR (#5228): opened and armed 09:54:25Z, checks green ~10:02Z,
entered the merge queue 10:02:59Z — **before an independent adjudicator had been dispatched**. Once
the queue entry existed, arm-means-freeze made the branch read-only, so the gate could no longer be
applied without dequeuing a healthy transit.

This is a process hole, not bad luck, and it recurs by construction whenever **checks are fast and
the gate is dispatched second**. Neither rule is wrong alone: freeze protects a judged SHA from
drifting under the judgement, and fast checks are the point of fast checks. Composed, they open a
window in which a PR reaches an irreversible state before the review meant to precede it has begun.
The remedy is ordering, not speed: **dispatch the adjudicator at PR-open, in the same motion as the
arm.** A gate scheduled second is a gate that races, and races are decided by CI latency rather
than by risk. Note the shape of the wrong fix — dequeuing a healthy transit to formalise a verdict
that would have been given anyway spends a real merge to satisfy a procedure; the failure is
upstream, in the ordering.

#### When the primitive is wrong, another term will not save it

A check comparing two documents by **set of lines** cannot distinguish _a row was edited_ from
_a row was deleted and an unrelated row was added_. Measured twice in one hour on a ledger under
`merge=union`, in mirror images:

- a row **`main`** deliberately deleted, still carried by a branch that merely inherited it →
  reported LOST, when the merge had correctly honoured the deletion;
- a row a **branch** deliberately closed in place (`- opened … STILL LIVE` → `- CLOSED …`) → read
  as delete-plus-add, so the old line is in `main`, absent from the merge, reported LOST again.

Each was patched with another set term (`authored = branch − base`, then `deleted = base − branch`,
giving `expected = (main − deleted) ∪ authored`). Both patches are correct and neither addresses
the cause. **Two mirror-image false positives in one hour is the signal that the primitive is
wrong, not that the formula needs a third term** — and the failure direction is dangerous: a
correct merge is reported as a loss, and the repair a reader reaches for is to restore the row,
which is exactly the resurrection the other half of the check exists to prevent. **The instrument
argues its user into committing the defect it was written to catch.**

The structural fix, if this is ever armed rather than run by hand: key on the identity every row
already carries — its `(date, lane)` header — and compare **bodies within an identity**. Then
"edited" is a body change under a stable key, "deleted" is a key that disappears, and "added" is a
key that appears; none of the three can impersonate another. **Every lane that closes a row it
opened trips the line-set version**, which is to say the check fails on the single most common
legitimate edit.

Generalises: when a check's false positives come in mirror-image pairs, the fault is in the
identity model, not the predicate.

#### Red for the wrong reason is not red

**A test that is red by accident passes review and fails silently the day the accident stops
holding.** This is why every counter-example in this spec names the finding it must produce, and
why "the suite is red" is not evidence that a rule is enforced.

Measured on this guard: counter-example F (a second `SHELL-ROUTE:` marker) is red today — with
`SHELL_ROUTE_BLOCK_INCOMPLETE`, because the duplicated marker happens to disturb the span, not
because anything checks marker uniqueness. R1 is unimplemented. The day the span logic changes, F
goes green and nothing announces it. A reviewer who saw only "F: red" would have signed off on a
rule that does not exist.

The same shape, one level up, in how instruments get trusted:

> **Re-deriving a number does not re-derive its boundary; exercising an instrument does not
> exercise the path you need it on.**

Both halves were measured the same night. A spec criterion demanded every number be re-derived,
the numbers _were_ re-derived, and the boundary they were derived inside was not. And a positive
control on the `AutoMergeDisabledEvent` log confirmed "the instrument works" — while every
observed event read `reason: "Manually disabled by user"`, so the control exercised the manual
path and said nothing about the automatic one it was invoked to license. **"The instrument works"
was true and irrelevant, which is harder to catch than an instrument that plainly does not work.**

So a control must exercise _the path the conclusion rests on_, and an assertion must fail _for the
reason it claims_. Neither is satisfied by a green run or a red one.

#### The same disease in the prose layer, in both polarities

**Reported by the gate lanes on PR #5204 and PR #5205; not measured here, and listed for their
shape rather than as evidence.** They matter because they are mirror images, and knowing only one
half leaves you defenceless against the other:

- **#5204 — the comment is CORRECT and the code is wrong.** _"A page that never landed must not
  silence the next hour"_ sits directly above the line that does exactly that. True as intent,
  false as description — which is worse than a plainly wrong comment, because it **terminates the
  reviewer's search at precisely the point the search needed to continue.**
- **#5205 — the docstring is WRONG and the code is deliberate.** It lists `FIRST_RUN` under
  "NEVER SILENT" while `VOIDING_NOTES` excludes it.

Both are one rule: **the prose is not the guarantee.** A reader who internalises only the first
direction will still trust a docstring that lies in the second.

The checkable tooth, and the reason this belongs in a spec rather than in a lesson file: **a
comment asserting a runtime guarantee must name the test that enforces it, or be deleted.** That
is mechanically reviewable, unlike "write accurate comments". It applies to this spec's own
subject directly — R5's route row is a _documentation_ line that a _test_ enforces, which is what
makes it a guarantee rather than a claim.

One corollary, learned by committing the error inside this very section — and stated in its
strong form, because the weak form schedules the next failure:

> **A number that will keep drifting should not be stated at all.** Where it must be stated,
> re-derive it at the moment of publication, never carry it.

Updating a drifting count is not a fix; it is the same bug with a later due date. This section
opened "three measured, a fourth second-hand" — true when written, false two paragraphs later once
more cases were appended — and a sentence further down said "every one of the four" for the same
reason. The first was corrected by re-deriving; **the second was corrected by deleting the number**,
which is why it cannot break again. Prefer the second wherever the list is open-ended. A stale
self-count sitting beside a rule about unmeasured claims is the disease writing its signature into
the cure.

## Definitions

Applied line by line to the raw file text. No JSON parsing; this is a property of the document.

- **comment line** — after stripping leading and trailing whitespace, begins with `//`.
- **blank line** — contains no non-whitespace characters. **Formatting, not a boundary.**
- **fence line** — a comment line whose content, after stripping `/`, spaces and tabs, is one or
  more `=` and nothing else. Length is not significant; trailing whitespace is not significant.
- **marker line** — a comment line containing `SHELL-ROUTE:`.
- **route row** — a single line matching, in this order on that one line: `/term`, an arrow, the
  literal `127.0.0.1:7681`, and `ttyd`. The shipped form is
  `//     https://nuzantara.tail461666.ts.net/term    -> 127.0.0.1:7681    ttyd -p 7681 -W zsh`.

## The rules

**R1 — Anchor. Exactly one marker line in the file.** Zero or two or more is
`SHELL_ROUTE_MARKER_NOT_UNIQUE`. A search that takes the first of several matches lets anyone
prepend their own block; the guard must not have to guess which marker is the real one.

**R2 — Extent. The block runs from the marker to the first fence line that follows at least one
line of comment _content_.** The banner's own opening fence sits immediately after the marker and
must be skipped, not treated as the end. (This off-by-one has now bitten two implementations; it
is the single most likely mistake when building from this spec.)

**R3 — Cap. That closing fence must occur within `MAX_SPAN` lines of the marker.** No fence, a
boundary reached first, or a fence beyond the cap is `SHELL_ROUTE_BLOCK_UNTERMINATED` — the block
is **malformed, not permissive**. The cap is what makes the terminator non-relocatable: an editor
may move the fence, but not far enough to matter. `MAX_SPAN = 40`; the shipped block is 33 lines.
A test must assert the real block fits strictly inside the cap, so the constant cannot drift
upward to accommodate a widening block.

**R4 — Boundary. A blank or whitespace-only line does NOT end the block.** Any line that is
neither a comment nor blank does. A non-`//` line carrying content is the JSON body beginning;
formatting whitespace is not a structural signal, and treating it as one produces a false RED on
an innocent edit. (Measured on the shipped guard: a single blank line inside an intact block
turned it red. That is how guards get deleted by whoever hits them.)

**R5 — Content. The block must contain the route row.** Absent, that is
`SHELL_ROUTE_ROW_MISSING`. This replaces the three-token containment test entirely.

R5 is the rule that closes the class, and it is worth being explicit about why. R1–R4 harden the
window; alone they would move the bypass again, exactly as the three previous fixes did. R5 stops
asking a containment question. There is no window to widen: the only way to satisfy it is to write
the true documentation back. Generalise it to any guard of this shape — when a check asks _"is X
present in region R"_, an editor who owns R defeats it; when it asks _"does this exact statement
exist"_, there is nothing to widen.

**R6 — Non-self-reference. The asserted form must be one the file's own prose about the check
cannot contain.** This is a property of the _assertion_, not of the block, and it must be
preserved by every future revision of this guard.

Three bare tokens fail R6 by construction: any sentence that names what the check looks for
thereby satisfies it. The route row passes, because prose discussing the check refers to `/term`
and `7681` in flowing text and does not reproduce `/term -> 127.0.0.1:7681 ttyd` as an ordered
row on one line. This is measured, not assumed — the prototype returns `SHELL_ROUTE_ROW_MISSING`
on the gutted-body and scattered-token cases while lines 105-106 sit inside the span.

The practical consequence, which is the part that will bite someone: **the next person to write
documentation near a check can re-create this without noticing.** Adding a comment that quotes the
required form verbatim would re-arm the self-reference. When documenting an assertion, describe
its shape; do not reproduce an instance of it inside the region the check reads.

## Scope: two audits, not one

The block rules are a property of **the shipped policy document**, not of arbitrary policy text.
They must live in an audit applied to `policy.hujson` and to fixtures **derived from it by
mutation** — not in the general `audit_policy()` that hand-written minimal fixtures pass through.

This is not tidiness; it is a correctness property that the current arrangement violates. Measured
on the shipped guard: **29 of 31 guilt fixtures emit `SHELL_ROUTE_BLOCK_UNTERMINATED`** as noise,
because they are 12–29 line files that were never meant to carry a 422-line policy's banner. A
finding that fires on 94% of fixtures has stopped discriminating — it is indistinguishable from
background, and the two fixtures that legitimately exercise the block are buried in it.

Consequence for the implementer: **block fixtures are generated by mutating the real policy, not
hand-authored.** A hand-written minimal file cannot exercise a rule about a real document's
structure, and pretending otherwise is what produced the noise.

## Counter-examples the implementation MUST reject

Every one of these is a measured false GREEN on at least one shipped guard, not a hypothetical.
Reproduce each by mutating a copy of `policy.hujson`; never mutate the file in place.

| #   | Mutation                                                                                         | Must yield              |
| --- | ------------------------------------------------------------------------------------------------ | ----------------------- |
| A   | Delete the closing fence; gut the body; park the tokens in comments below                        | `..._UNTERMINATED`      |
| B   | Relocate the closing fence ~50 lines down; gut the body; park the tokens inside the widened span | `..._UNTERMINATED`      |
| C   | Delete the real fence, gut the body, park the tokens, then supply a **fresh** fence after them   | `..._ROW_MISSING`       |
| D   | Prepend a decoy `SHELL-ROUTE:` header with the tokens; delete the real block entirely            | `..._ROW_MISSING`       |
| E   | Gut the body, leaving the fence in place                                                         | `..._ROW_MISSING`       |
| F   | Add a second real marker line                                                                    | `..._MARKER_NOT_UNIQUE` |
| G   | Delete the route row but scatter `7681`, `/term`, `ttyd` in nearby comments                      | `..._ROW_MISSING`       |

Note on D: **R1 does not catch it** — deleting the real block leaves exactly one marker, the
decoy's. R5 catches it. Identity comes from the row, not from the marker; R1 exists for F.

## Cases that MUST stay green

A guard that goes red on an innocent edit is deleted by the person who hits it, so these carry
equal weight and belong in the same suite:

1. The shipped `policy.hujson`, unmodified.
2. Fences of a different length.
3. Trailing whitespace on a fence.
4. An extra `//` line inside the block.
5. A **truly blank** line inside the block.
6. A whitespace-only line inside the block.
7. The whole block relocated to a different offset in the file.

Each innocence test must assert its own mutation actually applied. A reformat test that silently
fails to reformat passes forever and proves nothing.

## Declared residual

**An editor may relocate the fence _within_ `MAX_SPAN` and delete surrounding prose while keeping
the route row intact, and this spec permits it.** The row is the load-bearing sentence; the rest of
the block is exposition that may legitimately be rewritten.

**This is a judgement, not a proof.** It is recorded here rather than left implicit so a future
reader knows the case was considered and allowed, and can overturn it deliberately. If the
exposition is later judged load-bearing too, the fix is to name additional required statements in
R5 — not to re-harden the window, which is the move that failed three times.

## Verifying a candidate implementation

1. All seven green cases green, each asserting its mutation applied.
2. All seven counter-examples red, with the finding named in the table.
3. The real block measured strictly inside `MAX_SPAN`.
4. Block findings absent from the general fixture corpus (the noise property above).
5. Each finding emitted **once**, not once per missing token. The shipped guard emits
   `SHELL_ROUTE_BLOCK_INCOMPLETE` three times for one defect; a findings list that counts is one
   somebody will eventually assert a length on.
6. **The self-reference probe (R6), which costs one command and is not optional:** delete the
   thing the check protects and **fabricate nothing**. If the guard stays green, ask _which lines
   satisfied it_ — and look at whether they are yours. That question is what finally caught the
   bug above, after four adversarial rounds had missed it. Run it against any new assertion before
   trusting a green from it.

A prototype satisfying rules R1–R6 was measured against all fourteen cases in items 1–2 (seven
green, seven red, each counter-example yielding the finding named in its table row) before this
spec was written. The spec describes something that has been run, not something that ought
to work.
