---
date: 2026-08-19
domain: operations
client_case: none
adversarial_review: kimi-k3
sources:
  - apps/backend-rag/backend/app/routers/crm_clients.py
  - apps/backend-rag/backend/services/intake/crm_push.py
  - scripts/wa-mirror-auto-promote-leads.py
  - live Fly logs, app nuzantara-rag, machine 1781e5eda03438, ~2026-08-19T14:29Z
  - production Postgres via scripts/pg.sh (role nuzantara_readonly, db nuzantara_rag), read-only counts
---

# `upsert-by-phone`: the same endpoint, two callers, opposite safety postures — and the unsafe one is the one running

Found while chasing something else. A Fly deploy of `nuzantara-rag` returned `RC=0` alongside a
warning that a machine had no listener on `0.0.0.0:8080`. That warning is benign by construction:
`apps/backend-rag/fly.toml` states in its own comment that the `rag` process is reached over 6PN
and *"intentionally has no `[[services]]` Fly Proxy block"*, binding `--host ::`; `drive` is a
worker with no HTTP surface; only `api` sits behind fly-proxy. The advice the warning gives —
bind `0.0.0.0` — would break the design it warns about.

Reading the live log to confirm the rag machine was actually serving surfaced something else.

## What the endpoint does

`POST /api/crm/clients/upsert-by-phone` (`crm_clients.py:1340`) resolves a client by the *core*
of a phone number — the national part, so `0812…` and `62812…` are one identity.
`UPSERT_MATCH_SQL` (`crm_clients.py:91`) deliberately matches across **three** ownership columns
(`phone_normalized`, raw `phone`, `whatsapp`) and orders:

```sql
ORDER BY (deleted_at IS NULL) DESC, updated_at DESC NULLS LAST
FOR UPDATE
```

That breadth is not accidental — the comment above it cites Codex 2026-07-19 rounds 10/12/15
(F15/F21). When more than one row matches, the endpoint acts on `rows[0]` and then logs
(`crm_clients.py:1543-1551`):

> `upsert-by-phone: %s clients share a phone (acted on id=%s) — review for possible duplicate-client merge`

## Two callers, opposite postures

| caller | `reject_ambiguous` | `restore_if_archived` | behaviour on a collision |
|---|---|---|---|
| `services/intake/crm_push.py:157-168` | **`True`** (explicit) | **`False`** (explicit) | refuses; mutates nothing |
| `scripts/wa-mirror-auto-promote-leads.py:819-826` | *(omitted → `False`)* | *(omitted → `True`)* | acts on `rows[0]` |

`crm_push.py` sets both flags with comments naming exactly the hazard:

> *"Resolution must be mutation-safe on shared phones: the endpoint refuses BEFORE any
> restore/rename when >1 rows match (F10)."*
>
> *"NEVER resurrect an archived Fly row during identity resolution — the archived owner of this
> phone may be a DIFFERENT person than the locally-selected client (Codex round 8, F11 archive gap)."*

`wa-mirror-auto-promote-leads.py` sends a payload with **neither flag**, so it takes the model
defaults: `reject_ambiguous: bool = False` (`crm_clients.py:1329`) and
`restore_if_archived: bool = True` (`crm_clients.py:1321`).

**The live log shows which one is running** — for a stronger reason than this note first gave.
`crm_push` can never emit this warning at all: with `reject_ambiguous=True` any `matched_count > 1`
returns at 1396, before the guard at 1543 is reached, and any `matched_count <= 1` fails that
guard's `> 1`. So every `N clients share a phone` line in the log comes from a request whose
`reject_ambiguous` was not `True` — and of the two callers in the repo, that is the defaults path.
(Strictly, the log proves the *flag value*, not the caller; a third caller sending an explicit
`False` would look the same. The launchctl evidence below is what names this one.)
RETRACTED[upsert-by-phone-refusal-branches-reach-the-warning]: the first
version argued this from the printed id instead — *"a `crm_push` collision … would print `acted on
id=None`"* — which is false, because that collision prints nothing at all. The conclusion held; its
premise did not.

That is an inference from log format, so it was checked directly. `com.balizero.wa-mirror-auto-promote`
was **running at the time of measurement** — `launchctl list` gives PID `44281`, exit status `0`,
with a `-selfheal` companion job beside it. Its plist executes
`/Users/nuzantara/scripts/wa-mirror-auto-promote-leads.py` — a `$HOME` path, not the repo file
(cicatrix family #1). That copy was compared: `cmp -s` reports the live file **byte-identical** to
the repo copy, and it contains **zero** occurrences of `reject_ambiguous` and **zero** of
`restore_if_archived`. The two copies do not diverge today, so the reading above holds for the
code that actually executes — but the deployment path means a repo-side fix would not reach the
running job on its own.

## What was measured

Live log, app `nuzantara-rag`, machine `1781e5eda03438`, ~2026-08-19T14:29Z: the warning fired
**4 times in ~40 seconds** of captured log, on 4 distinct client ids — three reporting "2 clients",
one reporting "3 clients". A bulk upsert stream was running.

Production Postgres, read-only via `scripts/pg.sh`, **counts only, no PII extracted**:

| measure | value |
|---|---|
| clients total | 12,118 |
| phone-core collision groups | 849 |
| rows involved | 1,810 |
| … **1 live + N archived** | 412 |
| … **all archived** | 390 |
| … **more than one LIVE row** | 47 |
| max rows sharing one core (live) | 3 |

## What the ORDER BY actually guarantees — and where it stops

Only the **412** groups with exactly one live row are resolved by a *principled* rule: the live
row outranks archived ones. That is 49% of collisions, not the 94% an earlier draft of this note
claimed.

For the other two populations the tiebreak is `updated_at DESC` — recency standing in for truth:

- **47 groups (>1 live)**: the write lands on whichever live client card was touched most
  recently. Two real, distinct, current clients; the more recent one absorbs the update.
- **390 groups (all archived)**: `rows[0]` is archived, and under the defaults path line 1427
  runs `deleted_at = NULL` — it **un-deletes** an archived card chosen by recency, then may
  rename it and append notes. This is precisely the F11 hazard `crm_push.py` refuses to take,
  taken by its sibling caller against a population of 390.

`matched_count = len(rows)` (`crm_clients.py:1391`) and `UPSERT_MATCH_SQL` carries no
`deleted_at` filter, so the warning fires for all 849 groups without distinguishing which of the
three populations it is in. The 412 benign firings are indistinguishable, in the same words, from
the 437 that are not.

## The advisory has no review surface

A repo-wide grep for `duplicate-client|duplicate_client|possible duplicate|merge_clients|merge-clients`
across `apps/`, excluding tests and `.venv`, returns the log line itself and nothing else.
Two near-misses that are not it: `_find_duplicate_client`
(`backend/services/crm/client_core.py:1196`) is dedup at *creation* time, and
`apps/backend-rag/scripts/analyze_duplicates.py` counts duplicate **files**.

Two things do consume the *resolution outcome*, and neither is a review surface: `crm_push.py`
consumes it to decide its own delivery, and `wa-mirror-auto-promote-leads.py:845-850` records
`action` and `matched_count` into its audit record. Nothing surfaces the collision to a human on
`kita.balizero.com`. The sentence asks for a review that no surface offers.

## The log can assert an action that did not happen — right finding, wrong branches

The first version of this section was **right in its headline and wrong in its mechanism**, and the
first attempt to correct it made things worse by retracting the headline too. Both errors are
recorded below because the sequence is the lesson.

**RETRACTED[upsert-by-phone-refusal-branches-reach-the-warning]** — what is withdrawn is the
attribution, not the finding. The note asserted that the two *refusal* branches, `rejected_ambiguous`
and `skipped_archived`, *"both reach the log line at 1543, which prints `acted on id=…`"*. They do
not. `upsert_client_by_phone` runs from `crm_clients.py:1341` to its last statement at 1552 with no
nested function; its early exits return at 1396 (16 spaces, `rejected_ambiguous`), 1415 (20,
`skipped_archived`) and 1491 (20, `skipped_not_found`), all nested inside the transaction block,
while the guard `if result.get("matched_count", 0) > 1:` sits at 1543 (indentation 4) and the
`logger.warning(` it protects spans 1546-1551. A branch that returned cannot arrive there. One run
of `pytest backend/tests/routers/test_crm_clients_upsert_by_phone.py --log-cli-level=WARNING` (14
passed) shows it: `test_reject_ambiguous_refuses_before_any_mutation`, which asserts
`matched_count: 2` with `action: "rejected_ambiguous"`, emits **nothing**. For the same reason a
`crm_push` collision does not print `acted on id=None` — it prints nothing at all.

**But the headline is true, by a path neither version named.** At 1461 an empty `set_parts` skips
the UPDATE entirely and 1475 sets `action = "skipped_no_change"` — and `result` is still bound at
1477, carrying the real `matched_count`. So 1543 passes and 1546 prints `acted on id=<cid>` for a
row nothing was written to.

Reproduced, not argued. A throwaway probe on the router's own test harness — two rows sharing a
phone, nothing to write:

```
action= skipped_no_change   matched= 2   UPDATE statements executed= 0
WARNING crm_clients.py:1546 upsert-by-phone: 2 clients share a phone (acted on id=7)
```

This sits on the **production** path, not a hypothetical one. `wa-mirror-auto-promote-leads.py`
omits `reject_ambiguous`, and re-promoting an already-promoted lead — same name, notes not stale,
no recap — is exactly how `set_parts` comes out empty. The four warnings seen in ~40 seconds of live
log during a bulk upsert stream are, on this evidence, as likely to be no-ops as writes, and the
line cannot tell you which. That is the original finding, and it stands.

The only combination not covered by the test suite is precisely this one: a test asserts
`skipped_no_change` (`test_crm_clients_upsert_by_phone.py:183`) and another asserts the multi-match
warning, but nothing exercises the two together.

**A second, independent gap in the same lane.** The ambiguous refusal *is* logged in `crm_push.py`,
by a warning written for exactly this case:

```python
# crm_push.py:204-214
matched_count = data.get("matched_count") if isinstance(data, dict) else None
if isinstance(matched_count, int) and matched_count > 1:
    logger.warning("intake.crm_push.upsert_ambiguous matched=%s — refusing delivery ...")
```

**That warning cannot fire.** `crm_push` hardcodes `reject_ambiguous: True` (`crm_push.py:163`, the
only occurrence in the file, against the only URL construction at 171), so on a shared phone the
endpoint refuses first and answers `client_id: None` — asserted exactly, field for field, by
`test_reject_ambiguous_refuses_before_any_mutation`. `crm_push` reads that at 190, and at **191-192**
does a bare `return None` with no log, twelve lines before the `matched_count > 1` check it would
have tripped. Two guards were added for one hazard in different review rounds; the later one at the
server made the earlier one at the client unreachable — and the unreachable one is the only one that
speaks.

Its guilt test passes anyway. `test_shared_phone_ambiguity_fails_closed`
(`test_crm_push.py:433-451`) hands the client `{"client_id": 777, "was_created": False,
"matched_count": 3}` — a response the endpoint cannot produce for the body this caller sends — and
asserts the request body **zero** times. Its sibling twenty lines down,
`test_archived_fly_match_fails_closed`, asserts it **twice** (`restore_if_archived is False`,
`reject_ambiguous is True`). The neighbouring test performs the precise check that would have
exposed the impossibility.

The refusal is not invisible, though — a second draft of this paragraph claimed that too, and the
refuters killed it. It surfaces one layer up, at `crm_delivery.py:391-397`, as
`intake.delivery.identity_unresolved … detail=…`. What it cannot tell you is **why**: when
`_ensure_client_on_fly` returns `None`, `crm_push.py:345-350` attaches one fixed string —
`"phone-upsert could not resolve an UNAMBIGUOUS Fly client id"` — to *every* cause.

There are seven of them (`_ensure_client_on_fly` spans 132-221; a third draft of this paragraph said
five, and a second seat produced the two it had missed):

| exit | cause | preceding line of its own |
|---|---|---|
| `:156` | phone digits outside 6-20 | — **silent** |
| `:178` | transport error / timeout | `upsert_unreachable` (:177) |
| `:185` | HTTP ≥ 400 | `upsert_failed` (:180) |
| `:189` | unparseable JSON body | — **silent** |
| `:192` | 2xx carrying no `client_id` | — **silent** |
| `:202` | archived sole match | `upsert_archived_match` (:198) |
| `:214` | `matched_count > 1` with an id | `upsert_ambiguous` (:209) — **unreachable** |

**The shared phone lands on `:192`, the silent one.** That is the whole point: because the endpoint
answers `client_id: None`, the refusal arrives at the caller as an unremarkable "no id" and exits
without a word, while the warning written to name it sits two exits further down (`:214`, guarded at
`:209`) waiting for a response shape this caller can never receive.

So a shared-phone refusal produces exactly **one** line in the entire system, and it is the line
seven causes share. Both warnings written to name this cause are unreachable: the server's `N
clients share a phone` (it returned at 1396, never reaching the guard at 1543) and the client's
`upsert_ambiguous`. The observability is inverted for a demonstrable reason — the risky writes
announce themselves, the protective refusal arrives anonymous. "How often does a shared phone stop a
delivery?" is unanswerable from the logs, not because nobody wrote the line but because both lines
that were written can never run.

**The `action` field is never logged, and that is now the whole fix.** `result["action"]` is the one
value that separates `enriched` from `skipped_no_change` — the difference between a write and a
no-op — and it is the value the line drops. Adding it to the warning costs one format argument and
turns a sentence that can lie into one that cannot.

**Why the false version survived review.** The adversarial seat was pointed at the claims it was
handed — file:line accuracy, the 802/849 inference, the "no in-repo caller" assertion — and it
answered all three. Nobody asked whether control flow reaches 1543, so nobody looked. The failure
mode is that the claim was *structural*: every `file:line` in it was correct, and only the assertion
that control arrives at one of them was wrong. Citation-checking passes cleanly over that shape.

## Meta-pattern

Same shape as `research/operations/2026-08-19-crm-portal-handoff-sim/`: a mechanism that
**exists** but does not **participate**. The guard is written, the risk is named, the sentence
tells you what to do — and no surface exists on which anyone does it.

Two sharper edges underneath:

**The cure went to one caller of two.** Fifteen rounds of adversarial review hardened
`crm_push.py`, and the reasoning is preserved verbatim in its comments. The sibling caller was
never brought along, and it is the one in production. This is the class-audit lesson: a
pattern-fix that stops at the call site that bit you does not reduce the risk, it only moves
which caller carries it.

**An alarm that mostly fires on correct outcomes.** 412 benign firings arrive in the same words
as the 437 that are not, so whoever reads the stream learns to stop reading — which is how the
next real one is missed.

**And the same shape one level up, in this document.** The advisory line drops `action`, the one
field that separates a write from a no-op, so it cannot be wrong in a way anyone notices. The first
correction to this note dropped the *mechanism* and kept the confidence, and would have deleted a
true finding to fix a wrong citation. In both cases the defect is not a false statement but a
missing distinction, and in both cases it took an outside party — a refuter, a lint — to name it.
Rounds 2-4 below are the record: four drafts, three seats, and the most dangerous version was not
the original error but the over-confident repair of it.

## Open questions (human decision — `operator[business]`)

1. Should the 47 live collisions be merged at all? In this business a shared number is often
   **legitimate** — spouses on one handset, a reused office line, an agent fronting for a
   client. "Duplicate" may be the wrong word for many of them, and a merge would destroy a real
   distinction.
2. Should `wa-mirror-auto-promote-leads.py` adopt `crm_push.py`'s posture? That is the smallest
   change with the largest effect, but it converts ~849 silent writes into refusals — a
   behaviour change on a live lead pipeline, not a bug fix.
3. Is resurrecting an archived card ever the intent on the auto-promote path? `crm_push.py` says
   no, in writing, for identity resolution. Whether the lead-promotion path has a different and
   legitimate answer is a business call, not a code call.

## Adversarial review

Seat: **Codex `gpt-5.6-terra`** (`model_reasoning_effort=medium`, `--sandbox read-only`), run
against the first draft with instructions to verify every file:line against the code on disk and
report only defects. It returned `VERDICT: FIX` with three objections. All three were verified
independently on disk before being accepted; all three were real, and two were load-bearing.

1. **"802 of 849 resolve deterministically" — overstated.** The live-outranks-archived rationale
   covers only the 412 mixed groups; the 390 all-archived groups have no live row and fall to the
   same recency tiebreak. Corrected above — the split is 412/437, not 802/47.
2. **"No in-repo caller" — wrong.** `crm_push.py` exists and sets both flags explicitly. This
   objection is the origin of the entire two-callers section, which is now the note's main
   finding. **My own error, and its cause is worth recording**: the grep that produced the false
   claim ended in `| head`, and `crm_push.py` fell past the ten-line cut. Reading absence from a
   truncated list as proof of non-existence is W97, committed while the scar file that names it
   was loaded in context.
3. **"No consumer" — wrong.** Narrowed above: two consumers of the resolution outcome exist;
   neither is an operator review surface, which is the claim that survives.

One correction to the seat, verified on disk: it reported both no-action paths as reachable via
`crm_push.py`. Only `rejected_ambiguous` is — with `reject_ambiguous=True` the guard at 1393 returns
at 1396, before the `if rows:` block at 1405 (and the archived branch at 1409) can be reached.

### Round 2 — the branch attribution retracted, 2026-08-20

Re-reading the code to plan a follow-up fix, one day after this note merged in #4374, the branch
attribution did not add up: `rejected_ambiguous` and `skipped_archived` `return`, and the log line
is below them. Measured, confirmed false, and registered as
`RETRACTED[upsert-by-phone-refusal-branches-reach-the-warning]`.

Two things about how it got through. The seat answered the questions it was handed, and this was
not one of them — a refuter that verifies the claims you give it cannot catch the claim you never
doubted. And the claim was *structural*, not numeric: every `file:line` in it was right, so a
citation check passes straight over it.

Then the correction went wrong three separate ways, each caught by a different mechanism:

1. **Two wrong figures inside the correction itself** — the `logger.warning(` call put at 1543 (that
   is the *guard*; the call is at 1546) and its indentation given as 4 (it is 8). Caught by
   re-measuring on disk in the same turn the paragraph was written.
2. **A second home for the same false claim, in this same file.** The lint added in this PR flagged
   line 62, where the identical premise supported a *different* conclusion. Having corrected the
   section I remembered writing, I never searched for the claim elsewhere; the class-audit was done
   by the machine, not by me. (The conclusion survives on a stronger argument: a `crm_push`
   collision prints nothing at all.)
3. **And the retraction over-reached** — see Round 3. It withdrew the headline along with the
   branches, which would have deleted a true finding about production behaviour.

### Round 3 — the refuter, pointed at the replacement (Kimi K3, cross-family)

An independent seat from a different training family (`kimi -m kimi-code/k3`) was given the *new*
sentences, not the retracted ones, with instructions to re-derive every line number and attack the
strongest claim hardest. It confirmed the control-flow findings and refuted the replacement **three
times**, all three real:

- **The headline was true after all.** Against *"the warning is reachable only from a path that
  acted, so `acted on id=X` is always true"*, it produced `skipped_no_change` (`crm_clients.py:1475`,
  reached when `set_parts` is empty at 1461) — bound into `result` at 1477 with the real
  `matched_count`, therefore reaching 1543. Reproduced on the router's own harness: two rows,
  **zero UPDATEs**, and the log says `acted on id=7`. **This is the objection that mattered**: the
  correction was about to retract a true statement about production, which is a strictly worse
  outcome than the original mis-citation.
- **A dedicated log exists for the ambiguous refusal** (`crm_push.py:209-213`) — against the
  redraft's *"nothing is logged anywhere"*. It exists and cannot fire.
- **And the refusal is logged one layer up** (`crm_delivery.py:391-397`) — against the *next*
  redraft's "dropped silently". The defect is not silence but collapse: every cause, one string.
  (How many causes that is took a third seat — see Round 4.)

Three drafts of one correction, three refutations. The retraction was the easy part; **every**
sentence written to replace it was wrong on first attempt, and the most dangerous one was the
correction that went too far. The seat also caught the function-span figure (`1341-1554` counted two
trailing blank lines; the last statement is at 1552) and a loose claim that the log identifies the
*caller* when it can only identify the *flag value*.

### Round 4 — a second seat on the numbers (GLM)

GLM was dispatched independently on the `crm_push` half and **refuted the taxonomy**: the function
has **seven** `return None` sites, not five — `:156` (phone digits outside 6-20, reachable because
the caller's guard at `:320` tests only `not sender_phone`) and `:192` (a 2xx with no `client_id`)
were both missing — and the split is four-that-log / three-silent, not three/two. Re-derived on
disk before accepting it; both additions are real, and `:192` turns out to be *the* exit a
shared-phone refusal actually takes, which sharpens the finding rather than denting it.

Worth recording how my own check failed: the probe I wrote looked back twelve lines from each
`return` for a `logger.` call, and duly attributed the `upsert_failed` warning to the two silent
exits below it — a *proximity* proxy standing in for a *branch* relationship. GLM read the branch
structure. A probe that measures nearness will report a relationship that isn't there.

Seat note: the intended first refuter, Codex `gpt-5.6-terra`, was quota-dead (`usage limit … try
again Aug 22`) and the cascade moved to Kimi, then GLM. GLM's transport printed
`unrecognized_model` for `glm-5.2[1m]` and `glm-4.7` while still returning a full verdict — an
error line above a usable answer, which is worth naming because the first draft of this paragraph
read the error and declared the seat mute **without opening its output**. Same failure as
everything else on this page: a claim about something I had not looked at.
