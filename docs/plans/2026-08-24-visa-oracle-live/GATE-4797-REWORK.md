# Gate verdict — PR #4797 (E23U/E23V eligibility): REWORK

Issued 2026-08-24 by the Visa Oracle orchestrator session on Pro, per mandate §4 ("full
adversarial always on engine rules") and the ship-lifecycle rule that the session reviews and
merges. Generator ≠ grader: the diff was authored by a session on M5; neither this session nor its
model wrote it.

**Not armed. The PR stays alive and belongs to its lane.**

## What the PR does, once the +10,483 lines are reduced to their delta

```
REMOVED    review.e23u.requested-product, review.e23v.requested-product
ADDED      el.e23u.diplomatic-household-support, el.e23v.trade-office-support
MODIFIED   0                      (products 38 -> 38, rules 111 -> 111)
```

## The half that is right

Removing the two `REQUIRE_REVIEW` rules is correct and not in question. Each was keyed solely on
`intent.requested_product_code`, which `fact-mapper.ts:596` hard-codes to `unknownFact(NOT_ASKED)`
forever. At `on_unknown=NEEDS_INPUT` such a rule does not merely fail to fire — it demotes the
product to `BLOCKED_UNKNOWN`, which loses to any SUPPORTED product, making E23U/E23V invisible.

The three facts the new rules require are genuinely askable — verified against the mapper, not
recalled: `intent.purposes` → `mapPurposes`, `sponsor.type` → `mapSponsorType`,
`work.employer_is_indonesian_entity` → `mapEmployerIsIndonesianEntity`. None is in the NOT_ASKED
block. On that point the PR is sound.

## The half that is blocked

Both new rules constrain the sponsor's **category** and never the attribute that **defines the
product**.

```
el.e23u.diplomatic-household-support   ->  product "Foreign Diplomat House Assistant (E23U)"
  when: intent.purposes INTERSECTS [EMPLOYMENT]
    AND sponsor.type EQ INDIVIDUAL
    AND work.employer_is_indonesian_entity EQ false
```

Nothing in that condition is diplomatic. A concrete case entirely inside the path the interview
actually collects: a Filipina nanny employed by a **French expat family** in Canggu. Category
`work`, purpose EMPLOYMENT, sponsor "an individual person", payer non-Indonesian. The engine tells
her she qualifies for the **diplomatic household staff visa**. Neither employer holds diplomatic
accreditation. The same set includes a private chef for a foreign villa owner, a driver for a
foreign retiree, a tutor for an expat household.

`el.e23v.trade-office-support` has the identical shape with `sponsor.type EQ GOVERNMENT`. Nothing
requires the office to be trade or economic: an embassy's _political_-section administrator, a
foreign cultural institute, a foreign chamber of commerce, a UN agency — all match.

## The repository had already written this down

Two comments in the engine's own source, read verbatim on disk during this gate:

- `enums.py:439-443` (`SponsorType.GOVERNMENT`) — _"Confirming the value here does not by itself
  license a SUPPORT/ELIGIBILITY rule keyed on it alone."_
- `enums.py:626-629` (CORRECTED 2026-08-11, W3 sponsor-rules factbase) — _"E23U/E23V have no
  dedicated Permenkumham Pasal at all (confirmed by full-text search of 22/2023 and 11/2024);
  their `sponsor_types` values in the pack are Bali Zero working hypotheses, not statutory
  readings, and remain UNRESOLVED."_

And both new rules cite `9248b1d7` — Permenkumham 22/2023 jo. 11/2024 — the very source that
factbase reports, by full-text search, contains no E23U/E23V article. The other citation
(`6f5135f2`) is the Kepmen index catalogue: it lists codes, not eligibility conditions.

**The change converts a recorded uncertainty into a positive answer to a customer, with no new
grounding.** That is precisely what the mandate forbids at T3: _"products whose rules are
incomplete are never sold solo — the Oracle recognizes them and routes straight to the consultant.
Never an invented answer."_

Both rules also carry `safety_critical: false`. A rule deciding whether to tell a person they
qualify for a visa they cannot obtain is not non-safety-critical.

## The minimum cure

**Keep the removals. Drop the additions.** Without the two SUPPORT rules, E23U/E23V have no rules,
are not offered, and sit at **T3** in the tier map alongside the other ten products with no
`pricing_key`. That is the honest outcome and it costs nothing: the visitor meets a consultant
instead of a wrong visa.

Making them automatic instead needs facts that do not exist. Counted by importing the enum, not by
grepping it: **49 `FactPath` members, none expresses diplomatic status or office type.** It would
take `sponsor.is_foreign_diplomat` and `sponsor.is_trade_economic_office` plus a primary-source
extraction superseding the W3 verdict — its own mandate, not a line in this PR.

## The two CI reds are not the lane's, and one is not a real red

- **`Backend Shard 2`** (`test_main_api_imports_cleanly`, `AttributeError` on
  `backend.app.routers.analytics`) — **not their code.** Merged their head with `origin/main` in a
  throwaway worktree and ran the test: it **passes**. The CI run is from 14:13Z and main moved
  afterwards (`d4d11debc`). Stale merge ref — the cure is `gh pr update-branch`, never
  `gh run rerun`, which replays the same stale ref (W111).
- **`Backend Shard 1`** (`test_not_asked_facts_are_exactly_the_six_hardcoded_in_the_mapper`) — a
  real failure but **pre-existing on main**: the mapper now has five NOT_ASKED facts, not six,
  since `renewal_paid` was promoted to a real question. Another session is curing it.

## Provenance, so the verdict can be contested

A cross-family refuter (Kimi K3 — a different family from both the diff's author and this gate)
was instructed to falsify the change. It returned REFUTED on over-admission. Its load-bearing
citations were then re-read on disk by this session, because **a refuter is a lead, not a verdict**
(W65 — refuters hallucinate too). They hold verbatim.

Two of the refuter's points did **not** hold, recorded here because they favour the PR: there is no
E23U/E23V collision (`sponsor.type` is single-valued, and INDIVIDUAL vs GOVERNMENT are mutually
exclusive), and no collision with E23 (which requires `employer_is_indonesian_entity=true` while
these require `false`).

**The most attackable part of this verdict:** the pack's own product record already declares
`sponsor_types: [INDIVIDUAL]` for E23U, so the rule is consistent with the model. The answer is
that this value is exactly what `enums.py` records as an unresolved hypothesis — but a primary
source resolving it would change the verdict and the PR would pass.
