---
date: 2026-07-28
domain: visa
client_case: none
author: Claude Opus 5 (Air-M5) — ENFORCE-GATE measurement against the live SHADOW substrate
adversarial_review: codex
status: MEASURED — NEITHER lane can currently mature G-a, for two different reasons
sources:
  - prod `visa_decisions` (read-only role `nuzantara_readonly`, queries reproduced below)
  - `fly secrets list -a nuzantara-rag` (run 2026-07-28)
  - apps/backend-rag/backend/services/visa_engine/{shadow,evaluate_path,shadow_evidence}.py
  - apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/fact-mapper.ts
  - apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-001.source.json
---

# SHADOW gate measurement — neither lane can currently mature G-a

The corner's GATE STATUS has said 🔴 RED since 2026-07-21 with the reason "production
collection is still dark". Collection has in fact been writing since 2026-07-25. This is the
first read of *what it wrote*, from the production audit log rather than from the ledger's
narration of it.

The headline is not "the gate is far away". It is that **neither of the two surfaces the
collector counts can currently mature G-a**, for two unrelated reasons: the one that is
collecting abstains by construction (§2), and the one that has the right facts and the right
traffic does not label its rows, so they would be discarded from both G-a gates (§7).

## 1. What the audit log contains (measured 2026-07-28)

Every query is re-runnable against the read-only role; each was run in this turn. The two
counts below are minutes apart — the writer was live between them, which is itself a finding
(§3).

```sql
-- volume, distinctness, window            [run at 1483 rows]
SELECT traffic_source, engine_mode, count(*) AS rows,
       count(DISTINCT request_fingerprint) AS distinct_fp,
       count(DISTINCT date_trunc('day', created_at)) AS days,
       min(created_at), max(created_at)
FROM visa_decisions GROUP BY 1,2;
-- => real | SHADOW | 1483 | 14 | 4 | 2026-07-25T04:18Z | 2026-07-28T00:04Z

-- breadth: how many rows carry a candidate at all   [run at 1476 rows]
SELECT count(*) AS totale,
       count(*) FILTER (WHERE jsonb_array_length(candidate_summary) > 0) AS con_candidati,
       count(DISTINCT c->>'product_code') AS codici_distinti
FROM visa_decisions
LEFT JOIN LATERAL jsonb_array_elements(candidate_summary) c ON true;
-- => 1476 | 0 | 0     (both columns kept: 'no candidates' vs 'candidates without the key')

-- which surface is writing
SELECT engine_surface, count(*) FROM visa_decisions GROUP BY 1;
-- => RECOMMEND | 1483     (MATCH: zero rows)
```

Against `shadow_evidence.py` (`MIN_DISTINCT_REQUESTS=1_000`, `MIN_CONSECUTIVE_DAYS=7`,
`MIN_DISTINCT_VISA_CODES=30`, plus a ≥7-day window and zero malformed
fingerprints/categories/summaries/bindings at `shadow_evidence.py:183`):

| G-a component | Required | Measured |
| --- | --- | --- |
| distinct requests | 1,000 | **14** |
| consecutive days | 7 | 4 |
| interview categories | 7 | 3 |
| distinct visa codes | 30 | **0** |

Every row carries the same verdict, `HUMAN_REVIEW_REQUIRED` / `CALLING_VISA_REVIEW`, with an
empty `candidate_summary`.

## 2. Why the RECOMMEND lane can only abstain

`fact-mapper.ts:360` sends, unconditionally:

```ts
"person.nationalities": unknownFact(NOT_ASKED),
```

The pack meets that with a deliberate fail-safe. Rule `review.calling-visa`
(`rulepack-prod-001.source.json:1826-1845`) is `scope: GLOBAL`, matches
`person.nationalities` against the eight calling-visa states, and carries
`on_unknown: "HUMAN_REVIEW"`. So an unknown nationality routes every request to human review —
correct policy, meeting an interview that never asks the question.

This is a **RECOMMEND-lane** property, not a property of the engine. The engine, the substrate
and the pack all behave as designed; the pack is causally in the chain, and rightly so. The
defect is that the v2 interview collects ~8 of the 40 wire facts and nationality is not one of
them.

Consequence for the gate, scoped honestly: **on this lane** breadth cannot move off 0 (no
candidates ⇒ no product codes), and repeated visitors collapse onto few fingerprints because
`request_fingerprint` here is an HMAC over the canonical facts with `assessment_id` and
`collected_at` excluded (`evaluator.py:802,837`). Fourteen distinct fingerprints in four days
is an observation, not a proof of a hard ceiling — `permit_expiry` is a free date field and
does enter the fingerprint, so the reachable cardinality is not formally bounded below 1,000.
What is certain is that on this lane the rows are worthless as breadth evidence.

## 3. The volume is a machine, and it is labelled `real`

1,464 of the rows come from **three** byte-identical payloads repeating from 2026-07-26T17:40Z.
Inter-arrival gaps on the dominant fingerprint cluster at 3s (317×), 4s (117×) and ~20s (151×).
The loop was still running during this measurement (+7 rows between two queries minutes apart).

A sweep of the repo (`scripts/`, `infra/`, `.github/`) and of M5's crontab and LaunchAgents
found no caller; that sweep does not cover Pro, Mini, or anything external, so the origin is
open. What is not open is the label: these rows carry `traffic_source='real'`, the class
`shadow_evidence.py:292` reserves for G-a-vol. The collector would count this loop as
production adoption. Same defect class as the one flagged on 2026-07-27, three orders of
magnitude larger.

## 4. The other lane has the right facts and the right traffic — and is OFF

The MATCH shadow twin (STEP-6c, #2916) is a different story on every axis that blocks
RECOMMEND:

- **It collects nationality.** `shadow.build_shadow_facts()` takes `nationality` and sets
  `person.nationalities` to a `KnownCountrySet` when resolvable (`shadow.py:242-268`); the
  4-field Match submission supplies nationality/purpose/duration. The calling-visa overlay
  therefore does not fire indiscriminately, and candidates can be produced.
- **Its fingerprints are per-request.** `shadow._request_fingerprint()` is
  `SHA-256(match_hash)` (`shadow.py:399`) and `match_hash` is a fresh random token per
  submission (`visa_check/repository.py:115`, `new_visa_hash()`). Two users with identical
  answers produce *distinct* fingerprints — so on this lane the 1,000 threshold is bounded by
  traffic, not by the interview.
- **The collector counts it.** `EVIDENCE_ENGINE_SURFACES = {"MATCH", "RECOMMEND"}`
  (`shadow_evidence.py:87`).
- **It is the surface with real users.** `/visa` was resurrected in #3032; `/visa-oracle`
  serves HTTP 200 with `<meta name="robots" content="noindex, nofollow">` and is linked from
  nowhere.

It has zero rows because it is off: `fly secrets list -a nuzantara-rag` (run today) shows
`VISA_ENGINE_TRUST_STORE_KEYS_JSON`, `VISA_ENGINE_DRIVER_TOKEN`, `VISA_ENGINE_EVALUATE_MODE`
and `VISA_ENGINE_FACTS_FINGERPRINT_KEYS_JSON` deployed — and **no `VISA_ENGINE_MATCH_MODE`**,
which `shadow.py:207` defaults to `OFF`. (Zero rows alone would not have proven this: a missing
pack, a malformed HMAC key or an evaluation failure also yield zero rows. The secret list is
the evidence; the row count was only the symptom.)

## 5. What G-d actually needs — and what it does not

An earlier draft of this document claimed G-d was unfalsifiable because ENFORCE is not
implemented. That was wrong, and the adversarial pass caught it.

`resolve_response_mode()` does return the literal `"CURATED"` and cannot return `"ENGINE"`
(`evaluate_path.py:197`), so the *authoritative render* is genuinely unbuilt — that is a real
prerequisite of the flip, and no gate criterion names it. But the **kill-switch is not inert**:
`run_evaluation()` returns `EVALUATE_SURFACE_DISABLED` before resolving the environment,
the pack, or the engine when the mode is OFF (`evaluate_path.py:554-556`), while ENFORCE
evaluates and persists. "Flip the flag, confirm the surface stops consulting the engine" is
therefore a real, falsifiable drill that can be run today.

So G-d is *drillable now*; what is missing is the ENGINE render path the flip would switch on.

## 6. Ordering that follows from the measurement

1. **Decide the MATCH question (owner call — see §7, this step was mis-stated in the first
   version of this document).** MATCH is the only lane where nationality, per-request
   fingerprints and organic traffic already coexist — but arming it alone is a gate no-op,
   and keeping it dark is a recorded plan decision.
2. **Separate the probe/synthetic label from `real`** and decide the fate of the 1,464
   contaminated rows (relabel vs restart the window). Until then G-a-vol is not measuring
   adoption.
3. **Identify and stop the external loop.**
4. **Fix the RECOMMEND interview** (nationality + the facts the active rules discriminate on)
   if `/visa-oracle` is meant to be a gate-evidence surface rather than a prototype.
5. **Build the ENGINE render path + its DB lever** — the flip's unnamed prerequisite.
6. **Point the G-b replay at the ACTIVE pack** `446ee4ee`: `gold_replay.build_report()` calls
   `gf.build_gold_compiled_pack()` (`gold_replay.py:160-170`), the fixture, so today's green
   certifies the evaluator's mechanics, not the legal content being served.
7. Only then open the ≥7-day window and measure with `visa_shadow_evidence.py`.

GATE STATUS stays 🔴 RED — but for a different reason than the one recorded for the last seven
days. "Unmeasured" was hiding a two-sided problem: the lane we are measuring cannot produce
breadth, and the lane that could is both switched off and, as written, unable to have its rows
counted.

## 7. Correction — "arm MATCH" was wrong (found while executing it)

The first version of this document made arming MATCH its headline recommendation. That was
wrong on two counts, both caught before the `fly secrets set` was run.

**(a) The rows would not count.** `shadow.py`'s MATCH writer does not include
`traffic_source` in its INSERT column list (`shadow.py:538-547`), and the column has **no
default and is nullable** — verified against the live production schema, not merely the
migration:

```sql
SELECT column_name, column_default, is_nullable FROM information_schema.columns
WHERE table_name='visa_decisions' AND column_name='traffic_source';
-- => traffic_source | NULL | YES
```

`shadow_evidence.py:296-303` classifies a NULL marker as **legacy** and counts it toward
*neither* G-a gate, fail-closed. So arming MATCH as it stands is a **G-a no-op**.

Precisely, because the overstatement matters: those rows are not inert. G-c is deliberately
**not** split by provenance — "grounding quality is a property of the engine's output and
applies to every audited row regardless of provenance" (`shadow_evidence.py:28-29`) — so
unlabelled MATCH rows still flow into the grounding analysis and can move G-c green or red,
and they still increment the legacy/total/per-surface counts. The accurate claim is: *arming
MATCH alone cannot advance G-a and therefore cannot make the gate ready* — not that its rows
"satisfy nothing".

**(b) There was already a decision on record.**
`research/visa/2026-07-24-shadow-arming-runbook.md:40` states: *"Leave `VISA_ENGINE_MATCH_MODE`
**OFF**: the v1 thin-fact path stays dark so the window's evidence is full-fact only."* MATCH
carries 3 of the 40 facts. Whether a 3-fact corpus may certify an engine that ENFORCE would arm
on 40 is a plan question, not an implementation detail — the runbook's author called it "a plan
decision, not a code requirement", which is precisely why a session should not flip it silently.

**The fork.** That the choice is the owner's is this author's governance inference, not
something the runbook states: the runbook records the decision and calls it "a plan decision,
not a code requirement". It is escalated because it changes what a green gate would certify,
not because a rule forbids a session from deciding it.

- **(A) Keep MATCH dark, fix the RECOMMEND interview.** Slower; matches the recorded plan.
  Note the runbook's phrase "full-fact" describes the 40-key *contract*, not the collection:
  RECOMMEND currently supplies ~8 of those 40 keys, so option A only becomes genuinely
  wider-fact once the interview is extended.
- **(B) Teach the MATCH writer to label rows `real`, then arm.** Faster volume from a funnel
  that already has users; evidence is thin-fact (3/40), so the gate would certify less than it
  appears to.

**Why no test caught it.** The MATCH writer's integration fixtures layer only migrations
252+255 onto the shared schema (`test_shadow_match.py:505-518`) — migration 256 is never
applied there, so `traffic_source` is not even a column in the schema those tests run against,
and the row assertions (`test_shadow_match.py:668`) could not have checked it. A regression
test for this defect has to start by applying 256.

**Method note.** The error came from reading the COLLECTOR's surface allow-list
(`EVIDENCE_ENGINE_SURFACES = {"MATCH", "RECOMMEND"}`) and concluding MATCH rows would count. A
row is counted only if the **writer** labels it: reader-accepts-the-surface ≠
writer-emits-the-label. Check the INSERT column list and the column default on the live schema
before calling any lane "evidence" — and grep the runbooks for a recorded decision before
executing a step, because this one was a single file away.

## Adversarial review

Codex `gpt-5.6-sol` at xhigh, instructed to refute rather than confirm, with read access to the
tree. It attacked five load-bearing claims; **three were refuted and the document was rewritten
around them.** Every refutation below was then re-verified by the author directly on disk before
being accepted — the refuter is not trusted on its word either (W65).

- **"The 1,000-distinct threshold is interview-bounded" — REFUTED, claim withdrawn.** True only
  of RECOMMEND. MATCH fingerprints are `SHA-256` of a per-submission random token
  (`shadow.py:399`, `repository.py:115`), and the collector counts MATCH
  (`shadow_evidence.py:87`). Verified on disk. This inverted the document's conclusion: §4 and
  the step ordering in §6 are consequences of this refutation.
- **"G-d is unfalsifiable / the flag is inert in both positions" — REFUTED, claim withdrawn.**
  OFF short-circuits before the engine (`evaluate_path.py:554-556`); ENFORCE evaluates and
  persists. Verified on disk. §5 now separates the working kill-switch from the unbuilt ENGINE
  render.
- **"The engine can never recommend / nationality is never known" — REFUTED as a universal.**
  `build_shadow_facts()` sets nationality on the MATCH path (`shadow.py:242-268`). Verified.
  The claim now carries its lane scope everywhere it appears.
- **"`VISA_ENGINE_MATCH_MODE` was never set" — SUSTAINED as a methodology objection.** It was
  an inference from a zero row-count, which several other faults would also produce. Replaced
  with direct evidence: the Fly secret list, run today.
- **"14 fingerprints is the size of the fact space" — SUSTAINED, overstatement removed.**
  `permit_expiry` is a free date entering the fingerprint, so no hard ceiling below 1,000 is
  demonstrated. Kept as an observation only.
- **"'The engine, pack and substrate are not implicated' is too absolute" — SUSTAINED.** The
  pack's `on_unknown: HUMAN_REVIEW` on `review.calling-visa` is causally in the chain (verified
  at `rulepack-prod-001.source.json:1826-1845`); §2 now says so and defends it as correct
  fail-safe policy rather than denying the link.
- **"The four G-a numbers are not the whole gate" — SUSTAINED**, the window and the
  zero-malformed conditions (`shadow_evidence.py:183`) are now named in §1.
- **Not sustained:** nothing. Every objection raised either changed the document or was
  answered with new evidence.

### Second round — adversarial review of the §7 correction

Same seat, same posture, run on the correction diff itself. It refuted the correction's own
overstatement, which is why §7 now reads "G-a no-op" rather than "satisfies nothing":

- **"'Gate no-op / satisfies nothing / only adds noise' is false for the gate as a whole" —
  SUSTAINED, wording fixed.** NULL rows are excluded from both G-a accumulators
  (`shadow_evidence.py:296-303`) but G-c is deliberately not split by provenance
  (`shadow_evidence.py:28-29`), so they do flow into grounding and into the legacy/total counts.
  Verified on disk.
- **"The document still headlines 'the lane that can pass is OFF', which §7 disproves" —
  SUSTAINED.** Title, `status`, the opening paragraph, §4's heading and the §6 conclusion were
  all rewritten: neither lane can currently mature G-a, for two different reasons.
- **"'Full-fact evidence' is misleading when RECOMMEND collects ~8 of 40" — SUSTAINED**, option
  A now says so explicitly and attributes the phrase to the runbook's contract, not to the
  collection.
- **"'Owner call' is a governance inference, not something the runbook states" — SUSTAINED**,
  now declared as the author's inference with its reason.
- **"No regression test could have caught the missing label" — SUSTAINED and added** as a
  finding: the writer's tests never apply migration 256.
- **K1 (writer omits the label; no trigger/default/backfill sets it) and K3 (the runbook
  recorded the decision) — could not be refuted**, and K1 was strengthened: the only other
  production writer, RECOMMEND, sets it explicitly (`evaluate_path.py:459-483`), and migration
  257 touches only `request_category`.
