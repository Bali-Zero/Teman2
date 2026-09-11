# SPEC — the PENDING-ARMS owner field is a tag slot, not a sentence

> **Status: SPECIFICATION ONLY. No implementation in this PR.** This document does not
> touch `scripts/pending_arms_report.py`, does not open a classifier fix PR, does not
> revert PR #5273, and does not touch PR #5233 or its ledger row. It was originally
> mandated because that classifier's `PHANTOM-OPERATOR` detector had been patched once
> (PR #5273, 2026-08-29) and defeated again within hours by the very next real row
> (PR #5233), read at the time as CLAUDE.md's Agent PR Contract Rule 8 forbidding a third
> patch on the same surface.
>
> **CORRECTED same day, before this PR merged.** That reading of Rule 8 was itself wrong:
> the rule stops a fix-of-a-fix chain "at depth 1" — it _permits_ depth 1, which is exactly
> what the classifier fix (PR #5281, closed under the original misreading) was. Team-lead
> re-read the rule, independently re-exercised PR #5281's code with two additional probes
> neither of us had run, confirmed both fail in the guard's safe direction (over-flagging,
> never under-flagging), and reopened it — it is merged or merging as this document ships.
> **This document is therefore NOT an active recommendation superseding a broken fix.** It
> is preserved, at team-lead's explicit request, as the reserved fallback for if a further
> real production phrasing ever defeats PR #5281 the way PR #5233 defeated PR #5273 — so
> whoever hits that case inherits this reasoning instead of reaching for a fourth regex.
> §1's forensic account of the four incidents and §3's census are unaffected by the
> correction; §1's characterization of PR #5281 as "closed" and §5's "one aborted
> third-attempt PR" are the two claims the correction supersedes, and are fixed in place
> below rather than silently removed — a document that quietly deletes its own overtaken
> claim teaches the next reader nothing (`docs/specs/delivery-guarantee-gate-v1.md` §7
> names this same discipline).
>
> **Every number below was re-derived against `origin/main` at publication time**
> (2026-08-30, worktree `docs-pending-arms-ownership-spec`), not carried from the mandate
> that requested this document — including the total row count, which that mandate stated
> as 643 and which is corrected below to 659. The re-derivation ran `pending_arms_report.py`
> itself plus one standalone script against `.claude/skills/modus/PENDING-ARMS.md` and
> `git log` over the same file — both are named at each figure so the boundary travels with
> the number (`docs/specs/delivery-guarantee-gate-v1.md` §6.4 names exactly this failure
> mode: a re-run that inherits the wrong boundary is not a re-derivation).

---

## 0. What is actually being decided here

`scripts/pending_arms_report.py`'s `--strict-phantom` gate (wired into
`immune-enforcement.yml`, unconditional on every `pull_request` — no path filter, unlike
its neighbouring steps) reads the `owner:` segment of every open PENDING-ARMS row and
classifies it `OPERATOR-GATED` if it carries a well-formed `operator[<cat>]` tag,
`PHANTOM-OPERATOR` (hard fail) if it mentions "operator" without one. The mention check is
a deliberately loose bare substring match — the code comment names why: it exists to catch
Italian "operatore" and genuinely bare untagged claims (cicatrix family #3, W82
under-match). A single narrow exception, `NEGATED_OPERATOR_RE = r"\bnot\s+operator\b"`
(PR #5273), tries to rescue owner text that _denies_ operator ownership in prose.

The question this spec answers is narrow: **when an owner field needs to say "not an
operator lane," should that continue to be expressed as English prose the classifier
parses, or as a second machine-readable token the classifier reads directly?** Sections 1–4
below are the four things the dispatching mandate required this document to establish, in
its order. Section 5 is the falsifier it also required. This spec does not re-litigate
whether the _positive_ claim (`operator[business]`, etc.) is well-designed — that half
already works, and §3 shows why it isn't the surface with the problem.

---

## 1. The defect class, as measured

Four dated, PR-numbered instances, all inside a 7-day window, none recalled from memory —
each re-confirmed against `git log --all` this session:

1. **2026-08-23, PR #4603** (`4fcd31a4c6`) — first observation. Two rows written honestly
   the same day in the visaoracle truth-first ledger backfill each used "operator" once
   inside a negation to correctly state _no_ operator-gated category applied. The tool's
   phantom count went 0→2 the moment both landed. The only available fix in the moment was
   to reword both owner fields by hand — "a convention nowhere documented, nowhere
   enforced," in the row's own words, "that the next honest writer will hit again."
2. **2026-08-25, PR #4864** (`86cf513fd9`) — a `docs(spec)` PR had to change its content
   specifically to, in its own commit title, "stop tripping the phantom-operator guard"
   before its required checks would pass.
3. **2026-08-29T23:06:34Z, PR #5273** (`45181ad4c2`) — the one fix attempt made in this
   window. Its own commit message names the live case: PR #5269's healer-tick row, owner
   field `"next BUILD session (repo-side; not operator-gated — this is a real code fix,
just not a healer-tick-safe one)"`, blocked by `test_real_ledger_has_zero_phantom_operator`.
   Fixed with `NEGATED_OPERATOR_RE = r"\bnot\s+operator\b"` — deliberately narrow, "not"
   immediately adjacent to "operator."
4. **Hours later, same day, PR #5233** (`999e23079e`) — the fix from (3) is defeated by the
   very next real phrasing. Owner field read `"...— NOT this implementer session, NOT a
bare operator"`. `\bnot\s+operator\b` requires zero-gap adjacency; `NOT a bare operator`
   has two words between "not" and "operator," so the row still failed
   `test_real_ledger_has_zero_phantom_operator`. Unblocked, again, by a manual reword — this
   time to `"NOT a human"` — with the commit message explicitly deferring the underlying
   defect: "the classifier's substring-without-negation matching is a real defect
   (cicatrix family #3) but is out of scope for this PR — reported separately for a
   dedicated fix." That deferral is the mandate this document answers.

**The shape across all four is identical and none of it is prose that failed to _express_
ownership** — every one of these rows had already correctly decided who owned the row. The
defect is entirely in getting that decision _past a classifier reading English sentences_.
Three different real phrasings ("not operator-gated," "NOT a bare operator," the original
2026-08-23 pair) defeated the loose match, and the one dedicated fix attempt (§1.3) closed
exactly one of those phrasings and left the door open for the next, which arrived the same
day. That is not one anecdote and a hunch — it is a fix that was falsified by production
traffic before its own PR had finished being talked about.

**PR #5281** (`88a076b8f6`, later `08544d22e7`) is the depth-1 correction: it widened the
negation regex to a closed hedge-word vocabulary, verified against the real PR #5233 text,
and shipped guilt+innocence tests. It was briefly closed under a misreading of Rule 8 (as a
forbidden third attempt rather than a permitted fix-of-a-fix) and reopened the same day once
that was corrected — see the status block above. Team-lead's independent re-verification
found two further false positives the vocabulary produces (`"not a completely unrelated
distant operator"`, a gap wider than the closed vocabulary; `"NOT a human, operator"`, a
trailing bare mention after a negated one) and confirmed both fail in the guard's safe
direction rather than letting a real phantom row through — both are now pinned as guilt
tests. PR #5281 is the live fix as of this document's publication; a hedge-word vocabulary
is still, structurally, exactly the kind of boundary a sufficiently different future
phrasing can walk around — that observation motivates §2–§5 as a reserved contingency, not
as a claim that #5281 is currently insufficient.

---

## 2. Why prose-parsing is the wrong surface, not just an under-tuned one

The pattern across §1 is not "the regex was too narrow, tune it." Each fix closed the
_specific_ phrasing that had just been observed and left the _general_ case — an owner
field containing the word "operator" for expository purposes rather than as a claim — as
open as before. `\bnot\s+operator\b` → defeated by an intervening "a bare". The next
plausible fix, `\bnot\b(?:\s+\w+){0,3}\s+operator\b` or a closed hedge-word list (what PR
#5281 shipped, and which currently holds — see §1), is defeated by anything with a longer
gap than its vocabulary covers, a clause boundary ("operator? no — this is a session task"),
a different negator ("never," "hardly," "far from"), or Italian prose (this ledger is
bilingual by convention — see `owner: n/a` rows and CLAUDE.md §4). Every widening buys
exactly one more phrasing — including #5281's, which is why it is the current live fix
and not the closing move.

This is a general property of the task, not a property of any one regex: **deciding
whether a clause of English prose negates a word requires parsing the clause**, and a
`re.compile` pattern is not a parser — it is a fixed-width window over the token stream. A
classifier built this way has an unbounded number of true phrasings on one side and a
finite pattern on the other; it can only ever be current with what has already been
observed to fail, which is exactly the ordering CLAUDE.md's Rule 8 exists to stop — three
rounds of "found a new phrasing, patch the pattern" is not convergence, it is the same
defect being re-discovered on a delay. The fix that actually worked, every single time in
§1, was not a smarter pattern — it was a human shortening the owner field until the
trigger word was gone (§1.1's manual reword, §1.4's `"NOT a human"`). That is the tag
solution already being executed by hand, without being named as a rule. §3 names it.

---

## 3. The structured alternative, worked out against the real ledger

### 3.1 The owner field is already isolated — the defect is inside it, not around it

A PENDING-ARMS row is already pipe-delimited into five segments (opened/context, artifact,
missing-arming-step, `owner:`, `proof-of-armed:`), and the classifier already reads only
the fourth. Team-lead's framing — "the owner field carries a tag; prose lives elsewhere in
the row; the classifier reads the tag and never the prose" — is therefore not a new
document structure. **It already exists at the row level.** The gap is one level down: the
_owner segment's own grammar_ is unconstrained free English, so a writer can put
justificatory prose inside the one slot the classifier reads, including the word
"operator" used descriptively rather than as a claim.

### 3.2 Census of the 659 open rows, today

Re-derived via `pending_arms_report.py`'s own `load_entries` against
`.claude/skills/modus/PENDING-ARMS.md` on `origin/main`:

| population                                              | count                                                                                                                                                              |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| total open rows                                         | 659                                                                                                                                                                |
| owner field mentions "operator" in any form             | 201                                                                                                                                                                |
| — of those, carries a well-formed `operator[<cat>]` tag | 198 (98.5%)                                                                                                                                                        |
| — of those, no bracket tag at all                       | 3 (all dated 2026-07-02/07-05, pre-dating the tag convention's maturity, currently shielded from `PHANTOM-OPERATOR` by `FIREBREAK` precedence, not by correctness) |
| owner field never mentions "operator"                   | 458                                                                                                                                                                |

**This is the finding that reframes the migration question.** The rows that _assert_
operator ownership are already, overwhelmingly, in the exact structured form the classifier
wants — 198 of 201. The defect that has bitten four times in seven days is confined to rows
that _deny_ operator ownership in passing prose, and there is currently no well-formed way
to say that at all — a writer reaches for English because no tag exists for "explicitly not
this," and every reach has produced a different phrasing.

One further finding, found while building this census and not asked for: one row's owner
field reads `operator[credential]` — not a member of `TRUE_OPERATOR_CATEGORIES` (the seven
are `physical, gui, tcc, consent, secret, control-plane, business`; the intended tag was
almost certainly `secret`, whose own code comment reads "credentials/keychain material
only the human holds"). Under the classifier's own logic this should read
`PHANTOM-OPERATOR` (a tag exists but fails `all(t in TRUE_OPERATOR_CATEGORIES ...)`) — it
currently doesn't, because the row is separately caught by `FIREBREAK` precedence and never
reaches the operator-tag branch. That is a second, smaller instance of the same underlying
problem: **the bracketed form is validated only at classify-time, and only when reached —
never at write-time** — so even the "compliant" 198 are compliant by convention, not by
enforcement.

### 3.3 What the fix actually is, and it is not a migration

Given 3.2, "migrate 659 rows" is the wrong description of the work, and re-stating the
mandate's own 643 as 659 does not change that: **the 198 compliant rows need nothing done
to them; the 3 old bare-`operator` rows are pre-existing, currently-inert debt that can be
reworded opportunistically and are not urgent; and the entire live defect surface is the
practice of writing the word "operator" as English prose inside the owner segment at all.**
The concrete proposal:

1. **A write-time check, not a read-time parser, and not inside
   `pending_arms_report.py`.** A new, small, standalone gate (its own script or a rule
   inside an existing ledger-touching workflow — `check-ledger-no-silent-loss.yml` or a
   sibling) rejects any _new or changed_ owner-segment text that contains the literal
   token "operator" (or "operatore") **outside** a well-formed `operator[<cat>]` bracket.
   This is a binary lexical check — "does this literal substring appear outside this other
   literal pattern" — not a negation parser, and it has no unbounded phrasing space to
   chase: there is exactly one legal way to write the word, and everything else is
   rejected at the moment it is written, before it can ever reach the read-time classifier.
2. **A designated token for the negative claim**, so a writer who genuinely needs to say
   "considered and rejected as an operator lane" has somewhere structured to put it instead
   of prose — `operator[none]` is the cheapest option (extends the existing bracket
   grammar by one entry, requires the smallest classifier change of any option here, though
   that change is out of scope for this document per its own constraints) or, cheaper
   still, no new token at all: the reword pattern already used twice in §1 ("NOT a human,"
   dropping the trigger word) becomes the _documented_ convention rather than a discovered
   workaround, and the write-time check in (1) is what enforces it.
3. **Dual-form transition is nearly free.** 198 of 201 operator-mentioning rows need no
   change under either option. The 3 old bare rows and any future "not an operator" case
   get reworded on next touch, not backfilled in bulk — PENDING-ARMS rows are already
   append/close, not batch-edited, so a backfill sweep would itself be new, unusual,
   diff-heavy activity on a file already prone to `merge=union` resurrection risk (see the
   PR #5233 row's own resolution history in this same ledger). No transition window is
   needed where both forms must be accepted simultaneously by the _read-time_ classifier —
   the read-time classifier does not change at all under option (1)+reword; only the
   write-time gate is new.
4. **The old loose bare-substring detector stops needing a negation exception.** Once (1)
   is enforcing that "operator" only ever appears inside a well-formed tag, a bare mention
   found by the read-time classifier is unambiguous: either a genuine untagged claim (a
   real phantom, correctly flagged — this is the case the detector was built for) or a
   write-time-gate escape that should not have been possible. `NEGATED_OPERATOR_RE`
   becomes unnecessary rather than needing to be smarter. This is the concrete form of "fix
   it upstream, not downstream": the read side was never going to be reliably fixable
   because it depends on a write side nobody is constraining today.

---

## 4. What breaks if we do nothing

This gate runs unconditionally on every `pull_request` in `immune-enforcement.yml` — no
path filter, unlike the tailnet check immediately above it in the same job — so a phantom
row anywhere in the 1657-line ledger can in principle block a PR that never touched
PENDING-ARMS.md at all, if that PR's merge ref carries the offending row `(unverified —
no observed instance of this cross-PR blast radius; all four §1 incidents were self-
inflicted by the PR that had just added the row)`.

**Counted, not estimated, over the same 7-day window as §1**: `git log --since=2026-08-23`
against `origin/main`'s `.claude/skills/modus/PENDING-ARMS.md` shows 194 commits touching
the file and 320 new `- opened` rows added. Against that, 4 rows were actually caught by
`PHANTOM-OPERATOR` and required a defensive edit before merge — roughly **1 in 80 new
rows**, or one blocked PR every ~1.75 days once the pattern started recurring. Every one of
the 4 was caught and fixed within the same PR (nothing has yet slipped through to merge
mis-tagged); the cost per incident so far has been small — one extra commit, a few minutes
— but constant, recurring, and, per §1.3–1.4, immune to the one fix already attempted. If
nothing changes: every honest owner-field disclaimer remains a coin flip against whatever
phrasing the last patch happened to cover, at a measured rate of roughly 1 in 80 new rows
and climbing in absolute terms as the ledger's row-creation rate (320 in 7 days here) is
itself accelerating with fleet size, and every future occurrence still costs a live PR a
manual, undocumented reword under time pressure rather than a check catching it before the
PR was even opened.

---

## 5. The falsifier

Two conditions would make the structured approach in §3 the wrong call, stated as honestly
as they can be rather than as a formality:

1. **If the write-time gate in §3.3(1) cannot itself stay a simple lexical check.** The
   whole argument for moving the fix upstream is that "does this row contain the literal
   substring 'operator' outside a well-formed bracket" has no unbounded phrasing space —
   unlike negation, there is exactly one legal spelling of the tag. If it turns out writers
   have a real, recurring need to use the word "operator" inside the owner segment for
   reasons other than a tag or a bare disclaimer — discussing a different system's operator
   concept, quoting another row, cross-referencing — such that the write-time gate needs
   its own growing exception list to stop blocking legitimate text, then the defect has
   only been relocated one step upstream and dressed in different clothes, and §2's
   argument against prose-parsing applies to the new gate exactly as it applied to the old
   one. **Nothing in the 201-row census in §3.2 shows this happening today** — every
   observed non-tag "operator" mention (the 3 old bare rows, and the 4 incidents in §1) was
   either a genuine bare claim or a disclaimer, never a third use — but that is 7 days and
   201 rows of history, not proof it cannot occur.
2. **If the friction the new gate imposes exceeds the disease.** §4 measured the current
   cost at roughly 1 blocked PR per 80 new rows, each fixed in one extra commit. If, after
   shipping §3.3(1), the write-time gate's own false-positive rate — legitimate owner text
   rejected for reasons unrelated to a real ownership ambiguity — turns out higher than
   that, the cure is worse than the disease and the right move is to revert the gate, not
   patch it a second time (the same Rule 8 that stopped PR #5281 would apply to a second
   patch of this gate too). This is measurable only after rollout, which is why it belongs
   in this section rather than as a precondition to writing the spec.

**Where I land, and why it isn't advocacy**: the four measured incidents in §1 already show
this is a recurring, mechanically-defeated pattern rather than an unlucky sample, and the
census in §3.2 shows the "migration" the structured approach requires is nearly free (198
of 201 rows already comply) — so on the evidence gathered here, the structured approach
would be the better call **if and when** the read-time approach is defeated a third time.
It is not because prose-parsing is philosophically wrong; it is because this specific
instance of it (unbounded English negation, checked by a fixed-width regex, on a gate that
hard-fails CI) has already cost four real incidents in a week and one dedicated fix
attempt (PR #5273) that was defeated hours later, and the structured alternative costs
approximately nothing to adopt for the 198 rows that already work. PR #5281's closed
hedge-word vocabulary is the live fix today, correctly reopened once the "no third patch"
reading of Rule 8 was itself corrected (see the status block) — this document does not
argue #5281 should be reverted or that it is currently insufficient. It argues that
`_all_operator_mentions_negated` is a bounded patch on an unbounded problem, and names in
advance what should happen the day that bound is found: not a fifth attempt at the same
regex, but this structured field. If a future session observes condition (1) or (2) above
instead — the write-time gate would itself need an unbounded exception list, or its
friction would exceed today's ~1-in-80 rate — that is the signal this document was wrong,
not the signal to patch the write-time gate the way `pending_arms_report.py`'s read-time
classifier was patched in §1.

---

## 6. Scope, and what is deliberately not here

- **No implementation.** No new script, no workflow change, no edit to
  `pending_arms_report.py`. A separate PR, adjudicated on its own merits.
- **No touch to PR #5233, its ledger row, or PR #5273.** #5273 is a real, correct
  improvement for the one phrasing it covers; it is not reverted here.
- **Does not supersede, block, or argue against PR #5281.** #5281 (the closed
  hedge-word negation fix) is the live guard as of this document's publication — see the
  status block's correction. This document is a reserved contingency for a future third
  defeat of the read-time approach, not a case that the current fix is broken.
- **No `operator[none]` (or any other new tag) is chosen here.** §3.3(2) names two options
  and states a preference for the cheaper one (documented reword over a new tag) but leaves
  the final choice to the implementation PR, which should re-check whether a fifth
  incident has occurred in the interim before picking.
- **No claim that this closes every phantom-operator-adjacent risk.** §3.2's
  `operator[credential]` finding is a second, narrower defect (an unvalidated tag,
  currently masked by `FIREBREAK` precedence) named because it was found while building the
  census, not because this document proposes to fix it — it would need its own row and its
  own guilt/innocence pair.

---

## 7. Adjudication criteria for this spec

This document should be judged on whether:

1. every number in §1, §3.2 and §4 is re-derivable against `origin/main` at review time —
   none of them should be taken on trust from this text, and re-deriving them should not
   require inheriting a boundary this document didn't state (§4's page-vs-population
   caveat is stated for exactly this reason);
2. §2's claim — that this is a general property of prose-negation-matching, not a
   under-tuned pattern — is judged against whether a bounded regex genuinely could have
   covered all four §1 phrasings without also covering the next one, not against whether
   PR #5281's specific fix was competent (it was, and it is the live guard as of this
   document's publication — see the status-block correction);
3. §3's proposal is judged on the census in §3.2, not on the shape of the fix alone — a
   structured-field proposal that required migrating 400+ rows would be a much weaker case
   than one that requires migrating effectively zero;
4. §5 is read as a real falsifier and not a formality — a spec that names a falsifier it
   does not believe could ever trigger has not really named one;
5. the constraints stated in the status block at the top (no implementation, no touching
   #5233/#5273/`pending_arms_report.py`) held for the entire document, not just its opening
   paragraph.
