# Owner decision 8 — may we calibrate OCR confidence on the specimens already on M5?

> Prepared for Zero. One yes/no. Not "pick a number" — the number cannot be honestly chosen
> without this answer first.

## What this is actually about

When a customer uploads their passport, two independent local OCR passes (`qwen2.5vl:7b`, never
cloud — guardrail G-OCR-LOCAL) read it, and the system has to decide, per field, whether to trust
what it read or ask the customer to confirm/retake. That decision point is a single constant,
`CONFIDENCE_THRESHOLD = 0.80` in `apps/backend-rag/backend/services/garuda_documents/confidence.py`.

Right now that number is **picked, not measured** — the module's own docstring says so explicitly:
it is "a conservative PROPOSED default, not a measured one." DECISIONS.md Q7 requires the real
number to be set by running the actual model over genuine passport photographs (good ones, dim
ones, glare, angled, partially cropped) and finding the cut where the _false-confident_ rate — the
model says it's sure and it's wrong — goes to zero. That is deliberately a stricter bar than "the
model is usually right": the expensive failure mode here is not "we asked the customer to confirm
again," it is "we filed a wrong passport number with the immigration authority."

The lane that owns this (L5) correctly refused to do that measurement itself. Its mandate is
synthetic-only under the PII boundary this product is built under, and a fabricated specimen
cannot honestly stand in for the false-confident rate a genuine document produces — a synthetic
passport photo does not reproduce real glare, real motion blur, or a real off-angle phone camera
the way an actual photograph does. Refusing to fake the measurement was the right call, not a gap
in L5's work.

## What was measured (2026-08-25, on M5, counts only — no file opened, no filename recorded)

A corpus of genuine passport-style photographs already exists on the owner's own machine, at a
path **outside this repository**. Measured in aggregate only: a small number of specimen entries,
several dozen image files in total, covering a range of photo-quality conditions consistent with
what a real calibration pass would need. The directory was found with **world-readable
permissions** (any local account on that machine could have read it); the orchestrator tightened
it to owner-only access on the spot as a straightforward permissions fix. That fix is not an
answer to this decision — it only stops the exposure from getting worse while the decision is
pending.

**Nothing about this corpus — its path, its file names, its contents, or any single specimen — is
in this packet or anywhere in this repository, and nothing here asks you to look at it.** If
answering this decision required reading or sampling the corpus to describe it further, that
would be the wrong way to answer it; the aggregate counts above are the extent of what should ever
leave that machine as a description.

## The proposal

**Calibrate entirely on M5, and let only the resulting number leave the machine.**

1. The local model (`qwen2.5vl:7b`, no cloud endpoint — the same model and the same locality
   guarantee G-OCR-LOCAL already requires for real customer documents) reads each specimen.
2. The run produces **one aggregate table**: per confidence band, how many reads were correct and
   how many were confidently wrong. Nothing per-specimen is written anywhere.
3. No image, filename, extracted field value, or per-specimen row is written to disk, logged,
   committed, or included in any report, chat message, or artifact — on M5 or anywhere else.
4. The threshold is set at the point where the confidently-wrong count reaches zero.
5. The **only** artifact that ever enters this repository is the resulting integer in
   `confidence.py` plus the aggregate table (band → correct/wrong counts) in the commit message
   that changes it. The corpus itself never enters the repo, a shared artifact, a chat log, or any
   cloud service.

## What you are actually being asked to agree to

Two separate things, both needed before this can run:

- **(a)** That these specimens — whatever their origin — may be used for this purpose: measuring
  OCR confidence calibration for this product, once, locally.
- **(b)** That a local read of them by the organism's own model, on your own machine, under the
  no-export protocol above, is processing you are content to authorize. This is narrower than
  the general cloud-processing question this repo's other guardrails govern — everything here
  stays on M5, nothing crosses to any third party — but it is still processing of what may be
  real personal documents, and it should not proceed on an assumption.

**If the answer to (a) is no**, the fallback named in the original question stands: build a
corpus from consenting staff or personal documents instead, and this decision reverts to being a
sourcing question rather than a yes/no.

## Why this is not blocking the dark build

A human confirms every field before submission regardless of where the threshold sits (Q7's frozen
contract: the customer sees exactly one of three outcomes — verified fields, `LOW_CONFIDENCE`, or
`UNREADABLE_DOCUMENT` — never a raw number). An uncalibrated 0.80 costs friction if it is too
strict (more retakes/confirmations than necessary) or a pre-filled wrong value a tired customer
might wave through if it is too loose — real costs, but bounded ones, not a go-live blocker on
their own. It should still be resolved before go-live, because "measured to zero false-confident"
is precisely the bar this product set for itself, and 0.80-by-argument does not clear it.

## What the owner must personally do

Answer yes or no on using the specimens already on M5 under the local-only protocol above. If yes,
no further action is needed from you — the calibration run and the resulting commit are L5's to
execute under this authorization. If no, say whether Bali Zero can source consenting
staff/personal documents instead, and who would coordinate that.

## Your gesture

- [ ] Yes — use the specimens on M5, under the local-only protocol above (aggregate table only
      ever leaves the machine)
- [ ] No — do not use them; source a consenting-document corpus instead
