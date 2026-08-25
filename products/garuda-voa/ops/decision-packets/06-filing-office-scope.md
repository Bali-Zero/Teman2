# Owner decision 6 — does the published deadline hold for every buyer?

> Prepared for Zero. This is an operations fact only you or ops can answer — not a design choice,
> and not something the code can infer. Answer (a) or (b); the build already matches (a).

## What this is actually about

The one date this funnel is allowed to show a customer — the D-7 extension filing deadline
(packet-3-adjacent Safe Clock checkpoint, `PUBLISHED_FILING_DEADLINE_DAYS = 7`) — is sourced
**verbatim from the Ngurah Rai (Denpasar) immigration office's own published page**, verified
2026-07-24 and re-checked 2026-08-23. Every place that number appears in the engine names Ngurah
Rai explicitly: the code comment on the constant reads "verify per office," and the internal
checkpoint carries the same caveat word-for-word.

The question this raises: **does every buyer who goes through this funnel actually file their
extension at Ngurah Rai, or can the filing office vary?**

## What was measured (2026-08-24/25, on disk in this worktree)

- `constants.py:55` — the D-7 constant's own comment names Ngurah Rai and says "verify per
  office."
- `safe_clock.py:151` — the same caveat, repeated at the checkpoint that computes it.
- `grep -n "office\|kanim" intake.py` — **zero hits.** The nine-field intake the funnel actually
  collects (case type, nationality, entry date, passport expiry, purpose, travellers, self-pay,
  eVOA expiry, prior-extension flag) has no office field, no kanim field, no Indonesian address —
  nothing that could tell the system where a given buyer is filing.
- The customer-facing journeys mention "deadline" eight times and never mention an office.
- A parallel finding from the Visa Oracle session (their own read of the Ditjen Imigrasi pages,
  not re-verified by this packet): Ngurah Rai itself publishes two incompatible formulations of
  the deadline on the same page, and Yogyakarta's kanim publishes a third, different rule
  (D-1 working day, not D-7). That is a **lead**, not confirmed ground truth for this packet — it
  is named here because it is exactly the kind of divergence that would make branch (b) below the
  real answer.

## The consequence, so the choice is concrete

`submit_by_date` is emitted for **every** buyer today, unconditionally, from the Ngurah Rai
constant — regardless of where they actually end up filing. So right now, whether or not branch
(a) below is true, every buyer already gets the Ngurah Rai number. The question is whether that is
correct for all of them or only some.

- **(a) Every buyer who comes through this funnel files at Ngurah Rai / Denpasar.** Then the
  current behavior is already right, the constant's provenance matches every real buyer, and
  there is nothing to build. Ship as-is.
- **(b) A buyer can file somewhere else.** Then the deadline we show is unsourced for that buyer —
  we would be stating a Ngurah Rai rule to someone whose actual office may run a different
  schedule (as Yogyakarta's kanim reportedly does). The honest fix is additive, not a rewrite: one
  more intake question (where in Indonesia is the buyer staying / filing), and the deadline must
  be **suppressed, not guessed**, for any answer outside Ngurah Rai's jurisdiction, until that
  office's own published deadline is sourced with the same rigor D-7 was. Cost: one intake field,
  one branch in the verdict logic, and a per-office truth source carrying the same freshness
  attestation the price rows carry (decision 7).

Neither branch blocks the dark build — (a) is what is already built, and (b) is additive on top
of it. **(b) does block go-live**, because a wrong filing deadline on a client-facing page is
exactly the class of error this product is built to never make (see the freshness guardrail
G-FRESHNESS-FAIL-CLOSED, decision 7).

## Recommendation

We do not have the operational knowledge to answer this from inside the engineering audit — it
depends on how Bali Zero actually handles filing for self-purchase VOA-extension customers, which
is an ops fact, not something in the codebase. If, in practice, every VOA-extension customer this
funnel serves files through the Bali/Ngurah Rai office (which is plausible if the funnel is
explicitly Bali-focused or if Bali Zero always files centrally through Denpasar regardless of
where the traveller is staying), **answer (a) and ship as-is.** If there is any real possibility a
buyer files elsewhere, **answer (b)** and treat the one intake field as a small, bounded addition
before go-live — it is cheap relative to the cost of a wrong date reaching a client.

## What the owner must personally do

Answer (a) or (b). If (b), confirm whether L3/L5 should pick this up as a small follow-on lane or
whether it waits for a dedicated per-office truth-sourcing pass.

## Your gesture

- [ ] (a) — every buyer files at Ngurah Rai / Denpasar. Ship as-is.
- [ ] (b) — it can vary. Add the intake question and suppress the date outside Ngurah Rai's
      jurisdiction until sourced.
