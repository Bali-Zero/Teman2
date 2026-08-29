# SPEC — the delivery-guarantee gate

> **Status: SPECIFICATION ONLY. No implementation in this PR.** The clauses below are
> stated so that no future PR has to carry the general cure as a side-effect of fixing its
> own alarm. Implementation is a separate, later PR, adjudicated on its own merits.
>
> **Every number and file reference in this document is re-derived at publication time**,
> not carried from the session that drafted it. Two lanes shipped stale self-counts on
> 2026-08-29, one of them inside a section about unmeasured claims.

---

## 0. What this gate is for, and what it cannot do

An **alarm** is any code path whose job is to tell a human that something is wrong. This
repo has many, and on 2026-08-29 three independent lanes each found the same family of
defect in one: **the alarm was correct and nobody was told.**

The gate has three clauses. They are complementary, not redundant — they catch the same
guarantee at different points, and **none of them is sufficient alone**:

| clause               | question                                                         | when it catches        |
| -------------------- | ---------------------------------------------------------------- | ---------------------- |
| **(a) verdict**      | does the caller honour the delivery answer?                      | mutation, at test time |
| **(a.3) content**    | is the message the wrapper builds deliverable at all?            | mutation, at test time |
| **(b) reachability** | is a success ever reported on a path where the send was refused? | AST, at review time    |

Read that table as a conjunction. A reader who concludes that (b) alone closes the class
has made the same error as the code it polices — and the spec says so here, in the opening,
rather than in a residuals section where a caveat goes to be technically present.

**And the most honest thing this document can say about itself: the founding defect
survives all three clauses as written.** See §4.1 — clause (b) proves _consumption_, not
_provenance_. That gap is named, has a runnable proof, and is not closed here.

---

## 1. The defect class, as measured

Three instances, three subsystems, one shape. All three were found by gates on 2026-08-29;
none was found by the lane that wrote the code.

1. **The WAL-continuity probe (#5205).** No test asserted that a RED verdict was
   _delivered_. Replacing the RED `send_alert(...)` with `pass` left the whole suite, the
   module's selftest and the PR's own CI check green — because the only assertions on the
   alert recorder belonged to the digest path. A second site, the blind-guard p0, had the
   same gap one branch over.
2. **The payments alarm.** Three delivery-arm mutations survived green on a different
   alarm, in a different subsystem.
3. **The payments wiring bug.** `confirm_sent` ran unconditionally on a page that reached
   nobody. Every component was individually correct; the **composition** lied. This is the
   instance that motivates clause (b): it lived in the wiring, outside every class a
   mutation of the alarm would have covered.

The common mechanism is that **an exit code, a return code, or a computed verdict is
treated as delivery**. In this repo that is specifically wrong: `scripts/tg_notify.py`
deliberately never fails its caller. It exits 0 on six outcomes, and three of them mean
_not sent_ — `deduped`, `p0_overflow_spooled`, `p0_unsent_spooled`. Reading
`returncode == 0` therefore reports a refusal as a delivery.

---

## 2. Clause (a) — the caller honours the verdict

For any delivery function `D` whose result gates a confirmation or suppression `C`, **two
mutations are mandatory as a pair**, each requiring a **named** test to go red:

- **a.1** — `D` always reports success → a named test must fail
- **a.2** — `D` always reports failure → a named test must fail

### 2.1 Why the pair is indivisible

Each mutation is precisely the implementation that satisfies the other test alone:

- **a.2 only** → `D` may `return True` unconditionally. The alarm is mute; the confirmation
  fires anyway. This is the payments defect.
- **a.1 only** → `D` may `return False` unconditionally. The alarm spams, the operator
  mutes the channel, and the subsystem goes dark by the second road.

A cure that trains people to ignore the alarm is not a smaller version of the cure. It is
the disease with extra steps. **Neither half may be accepted without the other.**

### 2.2 The red must be NAMED

"Some test failed" is satisfiable by a flake, or by a test failing for the right output and
the wrong reason. If the test whose _name_ states the guarantee is not the one that goes
red, the assertion has drifted off the property. Record which test dies per mutant.

### 2.3 The mutation must alter a code token, never prose

Standard W121. The non-standard part is the inverse, and it must be in the spec **in both
polarities**, because a reader who learns only one will still be fooled by the other:

- **Correct prose over wrong code.** On the payments PR, the call-site comment read _"A page
  that never landed must not silence the next hour"_ — directly above the line that did
  exactly that. Mutating the comment would have produced a **red that proves nothing**. The
  usual scar is a false green from a mutated comment; this is a _true_ comment vouching for
  a defect, which is worse, because the comment is what a reviewer reads instead of the code.
- **Wrong prose over deliberate code.** On #5205 the module docstring listed `FIRST_RUN`
  under a heading reading _"NOT red, but NEVER SILENT"_ while `VOIDING_NOTES` excluded it —
  and a test enshrined the exclusion. A false statement about silence, protected by a test.

Both are one rule: **the prose is not the guarantee.**

**Transmission.** On the payments PR the true comment had been **copied into a second module
along with the bug**, and vouched for it there too. Prose propagates by copy-paste at least
as readily as code, and it carries its endorsement with it.

### 2.4 The tooth

> **A comment that asserts a runtime guarantee must name the test that enforces it, or be
> deleted.**

This is the only clause in the document that constrains prose, and it is mechanically
checkable in the weak form (does a comment containing a guarantee-shaped assertion cite a
test name?) even if the strong form is not.

---

## 3. Clause (a.3) — the payload must be deliverable

a.1/a.2 mutate the delivery **verdict**. They never mutate the delivery **payload**. They
prove the wiring honours the answer; they cannot prove the answer is _achievable_.

A wrapper that faithfully reports `False` forever, for a payload that can never parse,
passes a perfect a.1/a.2 pair with full honours. That is the payments alarm: every page it
produced was rejected — `parse_mode="Markdown"`, unescaped underscores in all four reason
values, `[...]` brackets reserved in their own right, `400 can't parse entities`, treated as
non-retryable.

### 3.1 The mutation

**Break the payload construction (escaper no-op) and require a named test to die.** On the
payments PR that mutation kills four named tests, and it is the only one of the three that
touches the question _can this message be delivered at all_.

### 3.2 The guilt test writes itself, and it is stronger than "the escaper is called"

> An observation containing an **odd number of underscores** must still arrive.

That asserts delivery rather than implementation, so it survives someone later swapping the
escaper. The parity framing matters because the sibling defect
(`_send_outbox_alarm`) is **content-dependent**: an odd count breaks the parse, an even
count delivers. Intermittent and silent is worse than always-broken — a channel that works
most of the time is one nobody audits, and it fails exactly when the failure is unusual.

### 3.3 The check belongs at the SENDER, not at the gateway

A gateway has a security property only for the callers that use it. If the payload check
lives at the gateway, **every direct caller is outside the guarantee by construction** —
so clause (a.3) is a requirement on each sender, not on `tg_notify.py`.

This is not hypothetical. Measured on `origin/main` at `862b92a394`, re-derived at
publication and **not** carried from the session that drafted this:

|                                                                  |                                             |
| ---------------------------------------------------------------- | ------------------------------------------- |
| files containing `parse_mode`                                    | 100 — `apps/` 62, `scripts/` 37, `infra/` 1 |
| known direct senders (`infra/tg-gateway/grandfathered.json`)     | 144                                         |
| files that are **both** a direct sender **and** set a parse mode | **62**                                      |

> The re-derivation earned its keep: the draft said 98 / `apps/` 60, measured a few hours
> earlier. Two files entered `apps/` in between. The `scripts/` 37 and the 62 held. A
> document that had stated its own numbers from memory would have shipped two wrong ones —
> which is §6's whole argument, applied to §3.

Sixty-two senders bypass the gateway _and_ ask Telegram to parse entities — the exact pair
that produced the payments defect. The repo has already been bitten and has already cured
it locally without naming the class: `scripts/sota_fase0_final_check.py` carries the comment
*"Plain text — Markdown parse_mode 400-errors on nested `and emoji"*, and`intake_review_reader_liveness.sh`and`cost_breaker_deadman.sh` each record migrating
**away** from raw-curl-with-parse_mode to the gateway.

The sweep of those 62 is **its own ledger row and its own PR**, not a line in this document.
It gets its worklist for free: `grandfathered.json` already enumerates the direct senders,
and that list's ratchet (§5.1) already prevents new ones being added.

**What is true about the gateway, and only that:** `scripts/tg_notify.py` sets no parse mode
on any of its three roads — `send_telegram` is `urlencode({"chat_id", "text"})`, the relay
forwards `text` as argv to that same function, the digest spool flushes through it.
**Gateway-routed alarms are clean. That is a statement about the gateway, not about the
tree.**

### 3.4 The retracted boundary, kept as the caution

An earlier draft of this section claimed the class was _confined_ to `apps/backend-rag/` and
the ops surface was clean. **That was false**, it was relayed onward as fact, and another
gate was told it could stop hunting siblings on the strength of it. The mechanism is in
§6.2. The rule it earned:

> **A bounded negative is a deliverable only when the boundary itself was measured.
> Otherwise it is a licence to stop looking** — and a false negative _with_ a boundary is
> worse than no measurement at all, because it tells the next lane where not to look.

---

## 4. Clause (b) — reachability

> **No success or confirmation call is reachable on a path where the send was refused or
> skipped.**

This is a property of the **caller**, not of the alarm, and it is cheap AST rather than
dataflow once the wrapper set is declared: an `ast.Expr` node whose value is a `Call` to a
registered name is a discarded return, full stop.

### 4.1 The shape to lift — and its named gap

#5205 shipped the local form of this clause, written from inside the defect, and it should
be lifted rather than re-derived:

```python
discarded = [n.lineno for n in ast.walk(tree)
             if isinstance(n, ast.Expr) and is_send_alert(n.value)]
assert not discarded, ...
total = sum(1 for n in ast.walk(tree) if is_send_alert(n))
assert total >= 6, ...
```

Two properties, both load-bearing:

- **the discard half** catches "nobody read the answer";
- **the count floor** makes it hold under **deletion**, not only under discard — removing a
  call site to satisfy the first half trips the second.

Measured: this assertion killed the blind p0, killed the RED site's discard, **and killed
the deletion of a `recovered` digest — a site the adjudicating gate never named and would
not have thought to enumerate.** That is the argument for clause (b) in one line:
_enumerations cure instances; assertions cure classes._

> #### GAP — (b) proves consumption, not provenance. NOT CLOSED.
>
> The clause asserts the return value is _read_. It does not assert the value was _derived
> from the gateway_. A wrapper that reads a verdict it fabricated itself passes every check
> written so far. Proof, runnable:
>
> ```python
> verdict = extract_gateway_verdict(proc.stderr)   →   "sent" if proc.returncode == 0 else None
> ```
>
> This survives #5205's own class assertion **and** the repo-wide
> `scripts/tests/test_gateway_callers_read_the_verdict.py`, because `gateway_delivered(...)`
> still appears in the return expression, so `_reads_verdict_semantically` classifies the
> function as reading.
>
> And `returncode == 0` is precisely the proxy someone reaches for — on a gateway that
> exits 0 on three not-delivered outcomes. **The founding defect survives both clauses
> written to catch it.**
>
> The third clause this implies: _the consumed value must trace to the gateway's own
> verdict, not to any local proxy for it._ Deliberately NOT specified here — it wants its
> own adjudication, and inventing it in the same document that discovered the gap is the
> fourth-patch reflex Agent PR Contract rule 8 exists to stop.

---

## 5. The registry — LIFT it, do not invent it

An earlier draft of this section proposed designing a fail-closed registry with a ratchet,
a ref-read baseline, named new entries, and silent shrinkage. **That was wrong, and the
error is instructive: all four properties already exist in this repo.** They were asserted
from memory of a cautionary number rather than measured.

### 5.1 Prior art, measured

`scripts/lint_tg_direct_senders.py` with `infra/tg-gateway/grandfathered.json`:

- the baseline is read **from the ref, never the PR tree** —
  `git -C <root> show origin/main:infra/tg-gateway/grandfathered.json`;
- **the list may only shrink**; growth vs `origin/main` is a FAIL;
- the failure **names the added entries** rather than reporting a count;
- shrinkage passes silently, and `--prune` reports entries that no longer need the exemption;
- it degrades gracefully when the base has no list yet (bootstrap).

`infra/organ-conformance/check_organ_conformance.py`, with a dedicated
`infra/organ-conformance/check_baseline_ratchet.py`, goes further: the baseline records
**which genes each grandfathered entry is missing**, so a regression _within_ a
grandfathered entry still fails. That is stronger than a count and is the better model of
the two.

### 5.2 What the delivery registry must therefore do

Reuse both patterns rather than re-implement them:

1. **Fail closed on discovery, not opt-in.** Anything whose name or signature says it
   performs a delivery — the naming families this repo actually uses (`send_*`, `notify_*`,
   `deliver_*`, `_send_*_alarm`) — and which returns something other than `None` must be
   **either registered or explicitly annotated fire-and-forget with a reason**. An
   unregistered new sender fails on the PR that introduces it.
2. **Ratchet against `origin/main`, per `lint_tg_direct_senders.py`.**
3. **Record per-entry detail, per `check_organ_conformance.py`** — not a bare count.
4. **The annotation is checkable, not trusted:** fire-and-forget is legal **only on a
   wrapper whose return type is `-> None`**. A bool return makes "nothing to consume" false
   on its face, and the gate catches the lie rather than reading the reason.
5. **The reason is a closed vocabulary**, so "why are these N exempt" is answerable by
   counting rather than by reading.

### 5.3 The corrected lesson

The grandfathered lists in this repo are **not** evidence that exemption lists grow
unchecked. They are frozen baselines from before their ratchets existed, and both are now
monotonically non-increasing by CI enforcement. The general lesson stands in a different
form: _an escape hatch is the next enumeration presumed complete_ — but the answer here is
to reuse the two mechanisms that already solved it, not to design a third.

---

## 6. Rules for the gate's own instrumentation

A gate spec that ignores its own probes is the disease it polices.

### 6.1 The probe returned nothing, and nothing looks like zero

1. **A probe that can silently return nothing needs a positive control.** `zero` and
   `unreadable` are the same output. Measured instance: `.claude/skills/modus/PENDING-ARMS.md`
   is >2 MB, and the GitHub contents API answers a file that size with `encoding: "none"`
   and an **empty** `content` field, no error. A ledger comparison built on it reported
   ~1082 rows LOST — a catastrophic false finding manufactured entirely by the tool. Use
   `Accept: application/vnd.github.raw` or `git show`. **It was caught only because the
   number was absurd**; a file a tenth that size would have produced a plausible wrong
   number that nobody questioned.

### 6.2 The probe returned SOME, and some looks like all

2. **Never conclude SCOPE from a capped listing.** A positive control proves a probe can
   say _found_. It does not prove the probe said _all_ — that is a different failure and
   needs a different guard. **Count first** (`git grep -l … | wc -l`, or group by path
   prefix), then list. Any `head`, `| head -n`, `[:N]`, or display truncation between the
   probe and the conclusion invalidates a _scope_ claim even when every line shown is true.

   Measured instance, and the reason this rule exists: a scope claim in an earlier draft of
   this very document rested on
   `git grep -n "parse_mode" origin/main -- scripts/ apps/ infra/ | head -10`. `git grep`
   emits path-sorted, `apps/` sorts before `scripts/`, and the cap fell inside
   `apps/backend-rag/`. Ten true lines became the false conclusion _"every occurrence is
   under apps/"_ — while 37 sat under `scripts/`, unseen.

   A second, smaller instance while publishing this document: `git ls-tree origin/main --
docs/specs` returned **1** and `git ls-tree -r origin/main -- docs/specs` returned **5**.
   Without `-r`, `ls-tree` reports the directory as a single entry. Same lesson at a
   different scale — **when two probes of the same question disagree, one of them is broken;
   find out which before believing either.**

   > **This is the strongest argument for this document's own existence, and it is an
   > argument against documents.** The failure is scar **W97** (_display-cap read as
   > complete_). W97 is already catalogued in `.claude/rules/cicatrix-superscar.md`, which
   > is injected into the context of every session and every subagent in this repo. It was
   > in front of the author when the mistake was made, and it did not prevent it. The false
   > boundary was then relayed to another gate as fact and used to narrow its search.
   >
   > **Documentation in context did not prevent this. Only a gate would have.** Every clause
   > in this specification should be read as a claim that the corresponding rule cannot be
   > left to a reader who has already read it.

### 6.3 The probe had nothing to judge, and that looks like a pass

3. **A check whose precondition does not arise reports the same green as a check that
   passed.** Assert the precondition, or report the result as `VACUOUS`, never as `PASS`.
   **Where a precondition can fail to arise, the honest output has three states, not two** —
   `PASS`, `FAIL`, `VACUOUS`. Collapsing the third into the first is not a simplification;
   it is the same conflation the check exists to prevent.

   Two measured instances, one of them in this document's own evidence:

   - On the payments PR the resurrection test was vacuous: `base − main` was empty — main
     had removed zero rows since the merge base — so nothing _could_ resurrect.
   - The #5205 adjudication reported _"ledger clean, checked bidirectionally: LOST 0,
     RESURRECTED 0"_. Re-measured afterwards: merge base 1082 unique rows, main 1082, **rows
     main deleted since the merge base = 0**. The `LOST` half was real and non-vacuous; the
     `RESURRECTED` half was **the hazard never arising**. The conclusion (the ledger is
     clean) still holds — the two added rows were inspected and are the PR's own — but one
     half of a claim posted as verified was untestable at the time it was made.

   Reporting a vacuous zero as a passed check is the same shape as the trap the check was
   written to catch. **A positive control does not help here either**: the probe worked
   perfectly; there was simply nothing for it to find.

4. **Count the rules that RAN, not the verdict.** A suite that skipped everything and a
   suite that passed everything both report success. Same family as rule 3, one level up:
   there the individual check had no precondition, here the whole suite had no subjects.
5. **A textual probe over human-formatted output reads a string nobody guarantees stable.**
   Prefer a structured field; if there is none, pin the format with a test that fails when
   it changes.
6. **Compare sets bidirectionally.** A ledger check must assert _nothing lost_ **and**
   _nothing resurrected_: a union merge restoring a row that main deliberately deleted passes
   a count comparison whenever anything else was added. Per rule 3, assert that main
   actually deleted something before claiming the second half proved anything.
7. **Re-derive every handle bound to a commit at the moment of use** — run ids, check-run
   ids, head SHAs, span numbers. The tell is identical in every instance: _the artifact
   looks authoritative because it is internally consistent._ Self-consistency is not
   evidence; it is what a lie looks like from the inside.

---

## 7. Scope, and what is deliberately not here

- **No implementation.** Not a linter, not a test, not a workflow. A separate PR.
- **The provenance clause (§4.1) is named, not specified.** It wants its own adjudication.
- **No claim that these three clauses close the class.** They close three measured
  instances and leave one measured gap.
- **The `>= 6`-style floor is per-module and must be derived per call site**, not copied as
  a constant.

## 8. Adjudication criteria for this spec

This document should be judged on whether:

1. each clause carries a **runnable** mutation, not a description of one;
2. the indivisibility argument for a.1/a.2 survives an attempt to split it;
3. §4.1's gap is stated as a gap and not softened into a residual;
4. §5 reuses the existing ratchets rather than proposing a third;
5. §3.4's retracted boundary is still present as a retraction — a spec that quietly
   deletes its own wrong claim teaches nothing, and this one was acted on by another lane;
6. the 62-sender sweep is scoped OUT of this document and into its own ledger row;
7. every number in it was re-derived at publication, including the 98 / 37 / 62.
