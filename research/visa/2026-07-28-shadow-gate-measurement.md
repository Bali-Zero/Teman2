---
date: 2026-07-28
domain: visa
client_case: none
author: Claude Opus 5 (Air-M5) — ENFORCE-GATE measurement against the live SHADOW substrate
adversarial_review: codex
status: MEASURED — the collecting lane is the one that cannot mature; the lane that can is OFF
sources:
  - prod `visa_decisions` (read-only role `nuzantara_readonly`, queries reproduced below)
  - `fly secrets list -a nuzantara-rag` (run 2026-07-28)
  - apps/backend-rag/backend/services/visa_engine/{shadow,evaluate_path,shadow_evidence}.py
  - apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/fact-mapper.ts
  - apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-001.source.json
---

# SHADOW gate measurement — the collecting lane is not the lane that can pass

The corner's GATE STATUS has said 🔴 RED since 2026-07-21 with the reason "production
collection is still dark". Collection has in fact been writing since 2026-07-25. This is the
first read of *what it wrote*, from the production audit log rather than from the ledger's
narration of it.

The headline is not "the gate is far away". It is that **the surface currently feeding the
audit log structurally cannot satisfy G-a, while the surface that could is switched off.**

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

## 4. The lane that can actually pass the gate is OFF

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

1. **Arm the MATCH lane** (`VISA_ENGINE_MATCH_MODE=SHADOW` + verify pack/HMAC resolution on
   that path). This is the highest-value single step: it is the only lane where nationality,
   per-request fingerprints and organic traffic already coexist.
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
days. "Unmeasured" was hiding "the lane we are measuring cannot pass, and the one that can is
switched off".

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
