"""Interview-walk decisiveness census: what the PUBLIC funnel actually answers.

``test_gold_coverage_floor.py`` proves the pack can support a product when
every fact arrives. This file proves the opposite half, and it is the half
the user lives in: replay the **67 real interview walks** — every distinct
path through ``flow.ts``'s two-arm spine and ``getCategoryQuestionIds``'
eleven categories, each answered through the real ``fact-mapper.ts`` —
against the highest signed PRODUCTION pack, and pin the outcome census.

Measured 2026-09-07 on ``rulepack-prod-020.signed.json``, with PR-3's
interview on top and PR-5's age dimension on top of that: **2 NEEDS_INPUT /
10 NO_SUPPORTED_PATH / 55 SUPPORTED_CANDIDATES — at ENGINE level, with no
disclosure flags supplied.** That qualifier is load-bearing and is spelled
out under "WHAT THIS CENSUS DOES NOT SEE" below; 55 is not the number of
applicants who see a recommendation without human review. Almost no walk
asks the applicant for a fact the interview has no question for any more —
the two exceptions are PR-5's own, and the module carries their allowlist
rows below
(research/visa/2026-09-06-visa-oracle-decisiveness-investigation.md §1-§2).

Four hops got here, and this file has been re-derived at each one — never
hand-edited:

1. **seq-19 → seq-20 (the signed fold, #5867): 36/0/7 → 21/0/22.** Fold edit
   1 raised ``el.c1.tourism-family``'s stay-day bound 60 → 180, so the
   corpus's 121-stay-day walks satisfy C1 and the whole tourism/family arm
   answers. The same widening on ``el.c2.business`` made C2 reachable for the
   business/investment arm, and C2's own ``family.sponsor_confirmed == true``
   premise became the smallest missing-fact set — so 9 walks MOVED their
   block onto a fact no invest/business/other branch asks. Edits 2 and 3
   retired ``review.e33g.income-evidence`` and the eight
   ``family.sponsor_status_code`` rules.
2. **seq-20 → seq-20 + PR-2's reorder (#5853): 21/0/22 → 11/10/22.** Ten dead
   ends became the honest ``NO_SUPPORTED_PATH``: seven blocked on
   ``process.wants_onshore_conversion``, two on
   ``investment.{investment,paid_up}_capital_idr`` and one on ``sponsor.type``
   — every one of them on behalf of a product whose ELIGIBILITY rules cannot
   cover the declared purposes under ANY fact resolution, which is exactly the
   class the reorder stops from choosing the global question.
3. **PR-3, this PR — the INTERVIEW moves, not the pack: 11/10/22 → 0/10/51
   over a corpus that grows 43 → 61.** The pack is byte-identical; every
   number below moved because ``flow.ts`` now asks facts it used to skip.
   Eleven dead ends were cured and eighteen walks are NEW:

   - ``family_sponsor_confirmed`` joined the ``invest`` and ``other``
     branches, so the nine walks that blocked on ``family.sponsor_confirmed``
     answer: the six ``offshore/invest/*`` and ``onshore/invest`` on C2,
     ``offshore/other`` and ``onshore/other`` on C6.
   - ``diaspora`` maps to the ``FAMILY`` purpose and serves the family
     question set, so ``intent.purposes`` is KNOWN on that tile: the two
     diaspora dead ends are gone and the tile is enumerated like the family
     one, 7 relations × 2 sponsor nationalities.
   - ``second_home`` is its own tile with two documented bases, adding three
     walks that all reach E33.
   - ``STEPCHILD`` became a reachable option, adding four walks (family and
     diaspora × 2 nationalities) that all reach E31D — a product no
     interview could name before.
   - ``work_payer`` joined the ``remote`` branch. It changes no state: both
     remote walks were already NO_SUPPORTED_PATH, and they now carry
     ``INDONESIAN_EMPLOYER_NOT_ALLOWED`` alongside the compensation reason
     instead of reaching that verdict with the employer fact UNKNOWN.
   - ``work_role`` was deleted. Its removal is invisible to this census by
     construction: the corpus carries a walk's wire FACTS, and ``work_role``
     was ``HUMAN_CONTEXT`` — it mapped to no FactPath, only to a disclosure
     flag. Both work walks still answer E23 with the same candidates.
4. **PR-5, THIS PR — the AGE dimension: 0/10/51 → 2/10/55 over a corpus that
   grows 61 → 67.** Neither the pack nor the interview tree moved; only the
   corpus did. ``birth_date`` is a spine question no branch reads, so every
   walk before this PR answers it with a fixed 25-year-old identity — and
   every one of the six ``retirement`` walks is excluded by
   ``hf.e33e.age-below-55`` / ``hf.e33f.age-below-55`` before either
   product's own eligibility rule is ever exercised. This PR adds 6 walks —
   the same 5 offshore retirement bases plus the onshore retirement walk,
   replayed at age 64 (birth date ``1961-11-11``, deliberately outside
   ``el.e33e.age-55-59-disputed-band``) — so E33E/E33F get exercised on the
   facts for the first time:

   - ``bank_deposit``, ``passive_income`` and ``family_sponsor`` (offshore)
     and the onshore neutral walk all reach ``SUPPORTED_CANDIDATES`` — four
     new answers.
   - ``property`` and ``undecided`` (offshore) end ``NEEDS_INPUT`` on
     ``family.sponsor_confirmed``: honest dead ends, not a defect. The
     question exists in the ``retirement`` category (the ``passive_income``
     and ``family_sponsor`` bases both ask it) but neither the ``property``
     nor the ``undecided`` branch reaches it — see
     ``WALK_DEAD_END_ALLOWLIST`` below, which is why the invariant this file
     arms is no longer unconditional.

**No EXISTING walk moved.** Every one of the 61 pre-PR-5 walks keeps its
exact state and candidate list — the 6 new walks are the only entries this
PR adds to the census, and 2 of them are the first ``NEEDS_INPUT`` this file
has ever pinned.

The invariant this file exists to arm is one sentence:

    no walk may end in NEEDS_INPUT on a fact for which the interview has no
    reachable question in that walk's own history.

**It is CONDITIONAL again, on exactly two named rows.** PR-3 made
``WALK_DEAD_END_ALLOWLIST`` empty; PR-5 adds back the two rows above,
each with its own anchor checked against the walk's own ``asked`` history
(``test_every_allowlisted_dead_end_is_genuinely_unaskable_in_its_own_walk``).
Curing ``flow.ts`` so ``retirement/property`` and ``retirement/undecided``
also ask ``family_sponsor_confirmed`` — restoring the unconditional
invariant — is a second concern and a follow-up, not this PR: it would
rewrite the *young* ``offshore/retirement/property`` fixture that
``test_the_retirement_walk_merges_age_below_55_keeping_both_rules_and_both_refs``
pins. The allowlist machinery otherwise stays because a future signed pack
can raise a new ``on_unknown: NEEDS_INPUT`` rule on an unaskable fact, and
the guilt tests below keep every branch of it exercised against a
fabricated row.

WHAT THIS CENSUS DOES NOT SEE — read the numbers with these two bounds, both
raised by independent review on 2026-09-06 (codex) and both PRE-EXISTING, not
introduced by this PR. Both bounds and the two measurements below them
(**51**, **10/15/36**, **21/35/5**) were taken on the pre-PR-5, 61-walk
corpus — PR-5 adds no disclosure-flag interaction of its own to replay, and
none of its 6 new walks carries a disclosure flag either, so the bound's
shape is unchanged; only the raw SUPPORTED_CANDIDATES/NEEDS_INPUT counts
below move, per the invariant section above:

1. **Disclosure flags are not carried, so this file proves LESS than it
   looks like it proves.** A fixture stores a walk's ``facts`` only, so every
   walk is evaluated with ``disclosed_review_flags = ()`` — while the live
   funnel sends whatever ``mapDisclosureFlags`` computed (``ACTIVITY_BOUNDARY``
   on the whole diaspora tile, for one). Read every number above with this
   attached:

   - **51 SUPPORTED_CANDIDATES means 51 walks reach candidates AT ENGINE
     LEVEL, with no disclosure flags supplied.** It does NOT mean 51
     applicants see a recommendation without human review.
   - **``census.get("HUMAN_REVIEW_REQUIRED", 0) == 0`` below is a property of
     these fixtures, not of production.** The review-flag arm of
     ``apply_public_policy_adapters`` is not exercised by any walk here.
   - **A regression that ADDS a disclosure flag — or fails to REMOVE one —
     passes this census invisibly.** That is not hypothetical: it is exactly
     what ``work_role`` did, and it is why the E23 claim in this PR rests on
     a separate replay rather than on this table.

   What IS sound as stated: the allowlist invariant (conditional, since
   PR-5, on the two named rows below — never unconditionally "0
   NEEDS_INPUT" again) and the candidate lists. A review flag can only
   LOWER a result to HUMAN_REVIEW_REQUIRED; it cannot create a missing
   fact.

   MEASURED by this seat, 2026-09-07, replaying this same corpus through
   ``evaluator.evaluate`` + ``apply_public_policy_adapters`` with
   ``ACTIVITY_BOUNDARY`` supplied on the diaspora tile ALONE: **10/15/36** —
   fifteen diaspora walks move SUPPORTED_CANDIDATES → HUMAN_REVIEW_REQUIRED,
   NEEDS_INPUT stays 0 either way, and no NO_SUPPORTED_PATH walk moves. The
   real flag set is wider than that one tile: the independent reviewer
   (codex, 2026-09-06) reports 21/35/5 for the FULL flag set — that figure is
   theirs and was NOT independently reproduced here, and note it moves
   NO_SUPPORTED_PATH walks too, so 10 is not flag-invariant in general
   either.

   Carrying the flags is a corpus-SCHEMA change: the fixtures gain a field,
   every one of them changes bytes, and the census can no longer share
   ``_evaluate`` with ``gold_coverage_eval`` unchanged — which is the
   coverage-floor gate. It belongs to its own PR, and until it lands this
   bound stands.
2. **The enumeration is a chosen sample, not a cover.** Every question is
   answered with its FIRST option and no walk ever answers ``unsure``, and
   the onshore arm is ONE neutral walk per category — its sub-branches
   (``onshore/second_home/property``, ``onshore/diaspora/STEPCHILD/...``)
   are deliberately not enumerated, as they never were for invest,
   retirement or family. Byte-for-byte reproducibility is proven; coverage
   of every reachable path is not claimed.

The corpus under ``gold_coverage/fixtures/walks/`` is DATA, generated by driving the
real ``computeNextNode``/``getCategoryQuestionIds``/``mapOracleFactsToApplicantFacts``
(first option answered at every question, 121 stay-days), never hand-written:
each file carries the walk's ``asked`` question ids and the exact wire
``overrides`` that walk produced. The expectations live HERE, in one
reviewable table, so a wave PR that moves an outcome must state which
outcome it moved.

Regenerate the corpus with ``npm run visa-oracle:walk-corpus -w apps/mouth``
(``apps/mouth/scripts/visa-oracle/generate-walk-corpus.ts``, proved byte-for-byte
reproducible by ``walk-corpus-determinism.test.ts``): a PR that changes the
interview tree MUST regenerate it and update ``EXPECTED_OUTCOME`` /
``WALK_DEAD_END_ALLOWLIST`` below in that same PR.
"""

from __future__ import annotations

import copy
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine import gold_coverage_eval
from backend.scripts.visa_engine.gold_coverage_eval import _evaluate
from backend.scripts.visa_engine.gold_replay_driver import (
    PACKS_DIR,
    _parse_utc,
    build_persona_request,
    select_highest_repository_pack,
)
from backend.services.visa_engine import evaluate_path, evaluator
from backend.services.visa_engine.enums import DecisionState
from backend.tests.services.visa_engine.test_evaluator_gold import Persona

CORPUS_DIR = Path(__file__).resolve().parent / "gold_coverage" / "fixtures" / "walks"

# PINNED to the highest signed pack's own `signed_at`, never the wall clock —
# same clock bomb `test_gold_coverage_floor.py` documents at length: the
# selected pack's source_records carry a freshness_policy with as little as a
# 604800s (7-day) window, so evaluating at `datetime.now(UTC)` is guaranteed
# to turn this whole census into HUMAN_REVIEW_REQUIRED seven days after the
# newest source's verified_at, with zero code change. `signed_at` (not
# `payload.created_at`) because the same instant drives `verify_rule_pack`'s
# `observed_at`, which rejects a signature dated after the observation.
_, _HIGHEST_SIGNED_PACK = select_highest_repository_pack(PACKS_DIR)
_AS_OF = _parse_utc(_HIGHEST_SIGNED_PACK["protected"]["signed_at"])

#: Why an allowlisted NEEDS_INPUT is a DEAD END and not a question the funnel
#: could ask. Each value is checked against the walk's own `asked` history.
NO_QUESTION_IN_TREE = "no question in tree.ts can ever set this fact"
QUESTION_NOT_IN_THIS_WALK = "the question exists but this walk's branch never asks it"
ANSWER_NEVER_CERTIFIED = "the question IS asked, and the mapper refuses to certify the answer"


@dataclass(frozen=True)
class DeadEnd:
    """One allowlisted dead end: the blocking fact, its source question in
    ``tree.ts`` (``None`` when no question emits it at all), and the reason
    the funnel cannot supply it."""

    fact: str
    source_question: str | None
    why_unaskable: str


#: Was EMPTY between PR-3 and PR-5: the invariant below was UNCONDITIONAL for
#: that stretch. A row here says "this walk may end NEEDS_INPUT on this fact
#: because the funnel genuinely cannot ask for it" — PR-5 is the first PR
#: since PR-3 for which that is true again, on exactly 2 walks.
#:
#: History (every shape before PR-5 was retired by CURING it, never by
#: loosening a count):
#:
#: - seq-20's fold: `family.sponsor_status_code` (its eight rules made
#:   NO_EFFECT) and `intent.requested_product_code` (the four BRIDGING rules
#:   guarded on a `known` premise).
#: - PR-2's reorder: `process.wants_onshore_conversion` (7 rows),
#:   `investment.{investment,paid_up}_capital_idr` (2 rows, always paired) and
#:   `sponsor.type` (1 row) — each raised on behalf of a product that could
#:   not cover the walk's declared purposes under ANY fact resolution.
#: - PR-3: `family.sponsor_confirmed` (9 rows) by adding
#:   `family_sponsor_confirmed` to the `invest` and `other` branches, and
#:   `intent.purposes` (2 rows) by giving the `diaspora` tile the `FAMILY`
#:   purpose instead of `unknownFact(NOT_APPLICABLE)`.
#: - THIS PR (PR-5): `family.sponsor_confirmed` (2 rows) on
#:   `offshore/retirement/property/age64` and
#:   `offshore/retirement/undecided/age64` — the age-64 walks are the first
#:   to clear `hf.e33e.age-below-55` / `hf.e33f.age-below-55` and exercise
#:   `el.e33e.retirement` / `el.e33f.retirement` on the facts, and neither the
#:   `property` nor the `undecided` retirement branch (`flow.ts`,
#:   `getCategoryQuestionIds`) ever asks `family_sponsor_confirmed` — only the
#:   `passive_income` and `family_sponsor` bases do. Curing that (making
#:   `property`/`undecided` ask it too) is a follow-up, not this PR: it would
#:   also rewrite the *young* `offshore/retirement/property` fixture pinned by
#:   `test_the_retirement_walk_merges_age_below_55_keeping_both_rules_and_both_refs`.
#:
#: Never add a row without an anchor showing the fact is genuinely unaskable
#: in that walk — and prefer curing it, which is what every row before THIS
#: PR became.
#: PR-D3 (D3-3) cures BOTH rows above by making `property` and `undecided`
#: ask `family_sponsor_confirmed` too (flow.ts) — measured 2026-09-13,
#: `offshore/retirement/property/age64` now answers `SUPPORTED_CANDIDATES
#: [E33F]` and `offshore/retirement/undecided/age64` answers
#: `SUPPORTED_CANDIDATES [E33E, E33F]`.
#:
#: A first pass of D3-3 landed with 5 rows: `family_sponsor_confirmed`'s
#: cure exposed a TWIN pattern on `offshore/invest/property/below_threshold`,
#: `offshore/invest/bank_deposit/below_threshold` and `offshore/retirement/
#: property/age64/sponsor_no` — once the CHOSEN basis fails, `el.e33.
#: property-basis` / `el.e33.deposit-basis` / `el.e33e.retirement`
#: (`on_unknown: NEEDS_INPUT`, verified against rulepack-prod-020.
#: source.json) surface the TWIN, unasked basis's facts as still-missing,
#: because "unknown AND known" does not short-circuit the way "known-false
#: AND known" does. Owner ruling 2026-09-13: closed, not allowlisted — a
#: below-threshold answer on a Second Home base is a definitive negative
#: ("I did not claim a deposit/property via this route"), not an unresolved
#: one, so `mapOracleFactsToApplicantFacts` (fact-mapper.ts,
#: `depositBasisDecisivelyNotChosen` / `propertyBasisDecisivelyNotChosen`)
#: now emits the twin basis's facts as KNOWN(0)/KNOWN(false) whenever the
#: interview has decisively routed to the OTHER basis — turning the rule's
#: own AND definitively false instead of leaving it unknown. Measured
#: 2026-09-13: all three now answer `NO_SUPPORTED_PATH` with `missing_facts
#: == []`. The two `invest` walks reach `OPERATIONAL_NO_PRODUCT_MATCHES_
#: DECLARED_PURPOSES` (the pack has no EXCLUDE-type reason naming this
#: threshold — a SUPPORT rule that fails to fire emits no reason_code of its
#: own), which `engine-adapter.ts`'s `secondHomeBelowThresholdReason` now
#: renders naming the applicant's declared value and the exact USD
#: threshold instead of the generic catalogue sentence. The retirement walk
#: reaches the pre-existing, now-reachable-for-the-first-time
#: `SPONSOR_REQUIRED` (`hf.e33f.sponsor-required`), given real copy in the
#: same PR. Two rows remain, neither this pattern:
#:
#: - `offshore/other/paid/sponsor_unsure`: `work_sponsor_confirmed` IS asked
#:   on this walk (D3-2's employment route) and the mapper refuses to
#:   certify "unsure" — `ANSWER_NEVER_CERTIFIED`, correctly nameable as a
#:   follow-up since the question is already in this walk's own history.
#: - `offshore/retirement/undecided/age64/still_unsure`: the honest
#:   non-answer D3-3 asks for — no evidence question follows a genuine "I
#:   still can't say", so `family.sponsor_confirmed` stays unknown exactly
#:   as it did pre-cure, but `family_sponsor_confirmed` IS nameable as a
#:   follow-up (asked unconditionally by the `family`/`diaspora`/`invest`/
#:   `other` categories, which is what `followUpPrerequisitesMet` checks).
WALK_DEAD_END_ALLOWLIST: dict[str, tuple[DeadEnd, ...]] = {
    "offshore/other/paid/sponsor_unsure": (
        DeadEnd(
            fact="work.indonesian_work_sponsor_confirmed",
            source_question="work_sponsor_confirmed",
            why_unaskable=ANSWER_NEVER_CERTIFIED,
        ),
    ),
    "offshore/retirement/undecided/age64/still_unsure": (
        DeadEnd(
            fact="family.sponsor_confirmed",
            source_question="family_sponsor_confirmed",
            why_unaskable=QUESTION_NOT_IN_THIS_WALK,
        ),
    ),
}

#: Per-walk outcome pin: state plus the candidate products, in rank order.
#: Candidates are pinned too — a pack edit that adds or drops a product for a
#: walk that already had an answer is exactly as much of a shift as a state
#: change, and this table is the only place either becomes visible.
EXPECTED_OUTCOME: dict[str, tuple[str, tuple[str, ...]]] = {
    "offshore/business": ("NO_SUPPORTED_PATH", ()),
    "offshore/diaspora/CHILD/spNat=ID": ("SUPPORTED_CANDIDATES", ("C1", "E31G")),
    # D4a (owner ruling SHWEB-20260911, 2026-09-13): `family_sponsor_status_
    # code` is now a closed-catalogue FACT instead of always-UNVERIFIED — the
    # foreign-sponsor (`spNat=IT`) SPOUSE/CHILD/SIBLING relation walks below
    # now name E31B/E31H/E31J alongside C1 (`el.e31{b,h,j}-*-itas-itap`,
    # `on_unknown: NO_EFFECT`, previously silent). PARENT/DEPENDENT/OTHER
    # stay unchanged: their sibling rules require facts (age < 18, a
    # different relation value) this corpus's default identity does not
    # clear, unaffected by this fix. E31E needs the same age < 18 gate — no
    # existing walk here exercises a minor identity; verified separately
    # (report only, not a new pinned walk — see the D4a PR body).
    "offshore/diaspora/CHILD/spNat=IT": ("SUPPORTED_CANDIDATES", ("C1", "E31H")),
    "offshore/diaspora/DEPENDENT/spNat=ID": ("SUPPORTED_CANDIDATES", ("C1",)),
    "offshore/diaspora/DEPENDENT/spNat=IT": ("SUPPORTED_CANDIDATES", ("C1",)),
    "offshore/diaspora/OTHER/spNat=ID": ("SUPPORTED_CANDIDATES", ("C1",)),
    "offshore/diaspora/OTHER/spNat=IT": ("SUPPORTED_CANDIDATES", ("C1",)),
    "offshore/diaspora/PARENT/spNat=ID": ("SUPPORTED_CANDIDATES", ("C1", "E31C", "E31F")),
    "offshore/diaspora/PARENT/spNat=IT": ("SUPPORTED_CANDIDATES", ("C1",)),
    "offshore/diaspora/SIBLING/spNat=ID": ("SUPPORTED_CANDIDATES", ("C1",)),
    "offshore/diaspora/SIBLING/spNat=IT": ("SUPPORTED_CANDIDATES", ("C1", "E31J")),
    "offshore/diaspora/SPOUSE/spNat=ID": ("SUPPORTED_CANDIDATES", ("C1", "E31A")),
    "offshore/diaspora/SPOUSE/spNat=IT": ("SUPPORTED_CANDIDATES", ("C1", "E31B")),
    "offshore/diaspora/STEPCHILD/spNat=ID": ("SUPPORTED_CANDIDATES", ("C1", "E31D")),
    "offshore/diaspora/STEPCHILD/spNat=IT": ("SUPPORTED_CANDIDATES", ("C1", "E31D")),
    "offshore/family/CHILD/spNat=ID": ("SUPPORTED_CANDIDATES", ("C1", "E31G")),
    "offshore/family/CHILD/spNat=IT": ("SUPPORTED_CANDIDATES", ("C1", "E31H")),
    "offshore/family/DEPENDENT/spNat=ID": ("SUPPORTED_CANDIDATES", ("C1",)),
    "offshore/family/DEPENDENT/spNat=IT": ("SUPPORTED_CANDIDATES", ("C1",)),
    "offshore/family/OTHER/spNat=ID": ("SUPPORTED_CANDIDATES", ("C1",)),
    "offshore/family/OTHER/spNat=IT": ("SUPPORTED_CANDIDATES", ("C1",)),
    "offshore/family/PARENT/spNat=ID": ("SUPPORTED_CANDIDATES", ("C1", "E31C", "E31F")),
    "offshore/family/PARENT/spNat=IT": ("SUPPORTED_CANDIDATES", ("C1",)),
    "offshore/family/SIBLING/spNat=ID": ("SUPPORTED_CANDIDATES", ("C1",)),
    "offshore/family/SIBLING/spNat=IT": ("SUPPORTED_CANDIDATES", ("C1", "E31J")),
    "offshore/family/SPOUSE/spNat=ID": ("SUPPORTED_CANDIDATES", ("C1", "E31A")),
    "offshore/family/SPOUSE/spNat=IT": ("SUPPORTED_CANDIDATES", ("C1", "E31B")),
    "offshore/family/STEPCHILD/spNat=ID": ("SUPPORTED_CANDIDATES", ("C1", "E31D")),
    "offshore/family/STEPCHILD/spNat=IT": ("SUPPORTED_CANDIDATES", ("C1", "E31D")),
    # D3-4's `sponsor_permit_no`/`sponsor_permit_unsure` walks (and the
    # question/hold they exercised) were REMOVED (owner ruling
    # SHWEB-20260911, 2026-09-13, fresh grader review): no pack requirement
    # for the sponsor's own permit exists for E31D — see fact-mapper.ts's
    # `mapDisclosedReviewFlags` and tree.ts. The corpus shrinks 78 -> 76.
    "offshore/holdsPermit/current/tourism": ("SUPPORTED_CANDIDATES", ("C1",)),
    # D3-1 (PR-D3, owner ruling SHWEB-20260911): `property`/`bank_deposit`
    # now route to Second Home — `mapPurposes` emits SECOND_HOME alone, never
    # joined with INVESTMENT (owner ruling 3) — and the corpus's canned
    # numeric answer (1_000_000_000, `generate-walk-corpus.ts::answerFor`)
    # clears both E33 thresholds (USD 1,000,000 property / USD 130,000
    # deposit), so both walks answer E33 instead of C2.
    "offshore/invest/bank_deposit": ("SUPPORTED_CANDIDATES", ("E33",)),
    "offshore/invest/family": ("SUPPORTED_CANDIDATES", ("C2",)),
    "offshore/invest/merit": ("SUPPORTED_CANDIDATES", ("C2",)),
    # PR-D4c-2 (owner ruling SHWEB-20260911): the currency-bound
    # `investment.investment_amount_usd` fact, asked only on the
    # `merit`/`family`/`undecided` vehicles (`pt_pma` untouched — E28A's IDR-
    # bound rules). An explicit USD answer is a silent extra fact under the
    # pack signed today (no rule reads it yet — seq-22, unsigned): this walk
    # answers exactly like its unmodified `merit` sibling above, C2, off the
    # same `family.sponsor_confirmed == true` default.
    "offshore/invest/merit/currency_usd": ("SUPPORTED_CANDIDATES", ("C2",)),
    "offshore/invest/property": ("SUPPORTED_CANDIDATES", ("E33",)),
    "offshore/invest/pt_pma": ("SUPPORTED_CANDIDATES", ("C2",)),
    # PR-D4d (seq-21 corpus prep, unsigned — activation caveat in the PR
    # body): `el.e33c.world-figure-invitation` needs INVESTMENT purpose +
    # `sponsor.type eq GOVERNMENT`, so this is the `invest` walk that would
    # exercise it once seq-21 activates. Under the pack ACTUALLY signed
    # today (rulepack-prod-020, which reads no sponsor.type condition for
    # any INVESTMENT-purpose product), `sponsor.type` is a silent extra fact
    # and the walk answers exactly like its `pt_pma` sibling: C2.
    "offshore/invest/pt_pma/sponsor_government": ("SUPPORTED_CANDIDATES", ("C2",)),
    "offshore/invest/undecided": ("SUPPORTED_CANDIDATES", ("C2",)),
    # PR-D4c-2: the "I can't say yet" currency answer — the walk measuring
    # this PR's zero-review-cost claim (see the PR body's NOT_CERTAIN proof;
    # this census does not carry disclosure flags at all, bound 1 above, so
    # it cannot witness that claim itself — only that the ENGINE-level
    # verdict does not move). Neither amount fact is ever populated
    # (`still_unsure` asks no further question), and this branch's
    # verdict is decided by `family.sponsor_confirmed` alone, unaffected:
    # C2, same as its unmodified `undecided` sibling above.
    "offshore/invest/undecided/currency_still_unsure": (
        "SUPPORTED_CANDIDATES",
        ("C2",),
    ),
    # C1 gate (PR-D3): below-threshold walks for D3-1's re-route. Owner
    # ruling 2026-09-13 CLOSED the twin-base dead end this pattern first
    # produced (see WALK_DEAD_END_ALLOWLIST above) — `fact-mapper.ts` now
    # emits the twin basis's facts as KNOWN(0)/KNOWN(false), which resolves
    # `el.e33.property-basis`/`el.e33.deposit-basis` decisively instead of
    # leaving them unknown. `birth_date` is overridden past 55 on both so the
    # reason is the actual threshold story, not an unrelated AGE_BELOW_55.
    "offshore/invest/property/below_threshold": ("NO_SUPPORTED_PATH", ()),
    "offshore/invest/bank_deposit/below_threshold": ("NO_SUPPORTED_PATH", ()),
    # D3-2 (PR-D3): `other_paid_activity`'s first option is `yes`, so this
    # walk now routes to the two employment facts `el.e23-employment-support`
    # reads and `mapPurposes` emits EMPLOYMENT alone; both facts default to
    # `yes`/true (`answerFor`'s first-option rule), so E23 answers instead of
    # C6.
    # C2 gate (PR-D3): the `paid = no` walk that used to prove C6 was
    # deliverable — `offshore/other`'s own default now answers `yes` (D3-2,
    # EMPLOYMENT/E23, comment above).
    #
    # D4a (owner ruling SHWEB-20260911): this IS the corpus's transit walk.
    # `other_purpose`'s first option is `transit` (tree.ts), and `mapPurposes`
    # now maps it to the TRANSIT purpose instead of OTHER — so this walk no
    # longer reaches `el.c6.social` (`intent.purposes ∩ OTHER`) at all.
    # NO_SUPPORTED_PATH, not a regression: this synthetic identity's
    # nationality is not in `el.a1.tourism`'s ASEAN-adjacent list and its
    # `entry_pattern` is SINGLE, not `el.d1-multi-entry-support`'s required
    # MULTIPLE — so neither TRANSIT-covering product fires for THESE
    # answers. A1/D1 reachability under TRANSIT for an identity that DOES
    # clear those gates is verified separately (report only, not a new
    # pinned walk here).
    "offshore/other/no_paid_activity": ("NO_SUPPORTED_PATH", ()),
    # C6 regression walk (PR-D4d, coordinator-authorised scope addition):
    # PR-D4a repurposed `offshore/other/no_paid_activity` (above) to prove
    # the TRANSIT route instead, which silently dropped C6 from this
    # census — the rule itself never moved. `other_purpose = "medical"` (no
    # special-case mapping anywhere in fact-mapper.ts) plus
    # `other_paid_activity = "no"` keeps the purpose OTHER, so
    # `el.c6.social` answers again.
    "offshore/other/no_paid_activity/medical": ("SUPPORTED_CANDIDATES", ("C6",)),
    # C1 gate (PR-D3): the two negative D3-2 facts.
    "offshore/other": ("SUPPORTED_CANDIDATES", ("E23",)),
    "offshore/other/paid/employer_no": ("NO_SUPPORTED_PATH", ()),
    "offshore/other/paid/sponsor_unsure": ("NEEDS_INPUT", ()),
    # PR-D4d, work item 1 end to end: `other_paid_activity === "yes"` could
    # not answer `sponsor.type` at all before this PR. This walk answers
    # GOVERNMENT down that newly-added question — the second reachable path
    # (besides `work`) into seq-21's `el.e33a/b.government-*`/
    # `el.e23v.trade-office` (unsigned — activation caveat in the PR body).
    # Under the pack signed today, no EMPLOYMENT-purpose rule reads
    # sponsor.type, so the walk answers exactly like its `employer_no`
    # sibling's purpose-mate: E23.
    "offshore/other/paid/sponsor_government": ("SUPPORTED_CANDIDATES", ("E23",)),
    "offshore/remote": ("NO_SUPPORTED_PATH", ()),
    "offshore/retirement/bank_deposit": ("NO_SUPPORTED_PATH", ()),
    # D3-3 (PR-D3): now ALSO asks `family_sponsor_confirmed` (default "yes"),
    # and the corpus's canned passive-income default clears E33F's own
    # USD 3,000 floor too, so both products answer together.
    "offshore/retirement/bank_deposit/age64": (
        "SUPPORTED_CANDIDATES",
        ("E33E", "E33F"),
    ),
    # D3-3 (PR-D3): the funnel census's LARGEST dead end (30 production
    # walks) — below both E33 thresholds, cured only by the family-sponsor
    # fallback `property`/`bank_deposit`/`undecided` now all ask.
    "offshore/retirement/bank_deposit/age64/below_threshold": (
        "SUPPORTED_CANDIDATES",
        ("E33F",),
    ),
    "offshore/retirement/family_sponsor": ("NO_SUPPORTED_PATH", ()),
    "offshore/retirement/family_sponsor/age64": ("SUPPORTED_CANDIDATES", ("E33F",)),
    "offshore/retirement/passive_income": ("NO_SUPPORTED_PATH", ()),
    "offshore/retirement/passive_income/age64": ("SUPPORTED_CANDIDATES", ("E33F",)),
    "offshore/retirement/property": ("NO_SUPPORTED_PATH", ()),
    # D3-3 (PR-D3): CURED — `property` now asks `family_sponsor_confirmed`
    # (default "yes"), so this walk answers E33F instead of dead-ending.
    "offshore/retirement/property/age64": ("SUPPORTED_CANDIDATES", ("E33F",)),
    # C1 gate (PR-D3): the negative sponsor sub-branch. Owner ruling
    # 2026-09-13 CLOSED this (same twin-base fix as the invest walks above)
    # — `SPONSOR_REQUIRED` (`hf.e33f.sponsor-required`) now decides it, given
    # real copy in the same PR (previously unreachable, would have fallen
    # through to a raw code dump).
    "offshore/retirement/property/age64/sponsor_no": ("NO_SUPPORTED_PATH", ()),
    "offshore/retirement/undecided": ("NO_SUPPORTED_PATH", ()),
    # D3-3 (PR-D3): CURED — `undecided` now asks `retirement_undecided_basis`
    # first; its default "deposit_or_income" answer routes through the full
    # deposit-basis evidence set, clearing E33E, AND `family_sponsor_confirmed`
    # (default "yes") clears E33F too — both answer.
    "offshore/retirement/undecided/age64": (
        "SUPPORTED_CANDIDATES",
        ("E33E", "E33F"),
    ),
    "offshore/retirement/undecided/age64/family_sponsor": (
        "SUPPORTED_CANDIDATES",
        ("E33F",),
    ),
    "offshore/retirement/undecided/age64/still_unsure": ("NEEDS_INPUT", ()),
    "offshore/second_home/bank_deposit": ("SUPPORTED_CANDIDATES", ("E33",)),
    "offshore/second_home/property": ("SUPPORTED_CANDIDATES", ("E33",)),
    "offshore/study": ("SUPPORTED_CANDIDATES", ("E30", "E30A")),
    "offshore/tourism": ("SUPPORTED_CANDIDATES", ("C1",)),
    "offshore/work": ("SUPPORTED_CANDIDATES", ("E23",)),
    # PR-D4d (seq-21 corpus prep, unsigned — activation caveat in the PR
    # body). `el.e33a/b.government-*`/`el.e23v.trade-office` share an
    # IDENTICAL condition (EMPLOYMENT + sponsor.type eq GOVERNMENT), so this
    # one walk is the reachability proof for all three at once; the sibling
    # walk right below swaps in INDIVIDUAL for `el.e23u.diplomatic-
    # household` (E23U is the diplomat's household assistant — the sponsor
    # is an INDIVIDUAL, there is no `DIPLOMATIC` sponsor value). Under the
    # pack signed today, neither value is read by any rule, so both answer
    # exactly like the unmodified `offshore/work` walk above: E23.
    "offshore/work/sponsor_government": ("SUPPORTED_CANDIDATES", ("E23",)),
    "offshore/work/sponsor_individual": ("SUPPORTED_CANDIDATES", ("E23",)),
    # Work item 2, fourth bullet: leaving `sponsor.type` genuinely
    # UNRESOLVED (`unsure` -> UNVERIFIED) on a reaching tile must be
    # silence, never a hold — `offshore/work` above already proves the
    # honest-negative half (`NONE`, the question's first option). Under the
    # pack signed today this is a non-event (no EMPLOYMENT-purpose rule
    # reads sponsor.type yet), and it answers identically: E23.
    "offshore/work/sponsor_unsure": ("SUPPORTED_CANDIDATES", ("E23",)),
    "onshore/business": ("NO_SUPPORTED_PATH", ()),
    # D4a: the onshore family/diaspora walks default to SPOUSE — same
    # `family_sponsor_status_code` fix as the offshore SPOUSE/=IT walks
    # above.
    "onshore/diaspora": ("SUPPORTED_CANDIDATES", ("C1", "E31B")),
    "onshore/family": ("SUPPORTED_CANDIDATES", ("C1", "E31B")),
    "onshore/holdsPermit/current/tourism": ("SUPPORTED_CANDIDATES", ("C1",)),
    "onshore/holdsPermit/expired/tourism": ("SUPPORTED_CANDIDATES", ("C1",)),
    "onshore/invest": ("SUPPORTED_CANDIDATES", ("C2",)),
    # D3-2 (PR-D3): same route change as `offshore/other` above.
    "onshore/other": ("SUPPORTED_CANDIDATES", ("E23",)),
    "onshore/remote": ("NO_SUPPORTED_PATH", ()),
    "onshore/retirement": ("NO_SUPPORTED_PATH", ()),
    # D3-3 (PR-D3): this walk never overrides `retirement_basis`, so it
    # answers via the tree's own first-option default ("bank_deposit") —
    # same shape and same fix as `offshore/retirement/bank_deposit/age64`
    # above.
    "onshore/retirement/age64": ("SUPPORTED_CANDIDATES", ("E33E", "E33F")),
    "onshore/second_home": ("SUPPORTED_CANDIDATES", ("E33",)),
    "onshore/study": ("SUPPORTED_CANDIDATES", ("E30", "E30A")),
    "onshore/tourism": ("SUPPORTED_CANDIDATES", ("C1",)),
    "onshore/work": ("SUPPORTED_CANDIDATES", ("E23",)),
}

#: The state distribution, restated as a total so a reviewer sees the shape of
#: the funnel in one line. Derived from EXPECTED_OUTCOME on purpose: the two
#: can never disagree, and the wave PRs edit one table, not two.
EXPECTED_STATE_CENSUS: dict[str, int] = dict(
    Counter(state for state, _ in EXPECTED_OUTCOME.values())
)

#: Which fact blocks how many walks — the §2.2 table, EMPTY between PR-3 and
#: PR-5. A cure that moves walks between blocking facts instead of removing
#: the block goes red here even if the total happens to stay the same, and so
#: does the first fact that starts blocking again — which is exactly what
#: THIS PR does: 2 age-64 retirement walks (`property`, `undecided`) block on
#: `family.sponsor_confirmed`, the same fact PR-3 retired for 9 OTHER walks by
#: adding the question to the `invest`/`other` branches (see
#: `WALK_DEAD_END_ALLOWLIST` above) — this pack's rules still ask for it, the
#: `retirement` branch just doesn't route these two bases to the question
#: that supplies it.
#: PR-D3: the old `family.sponsor_confirmed: 2` (property/undecided age64)
#: is cured. The twin-base dead ends (below-threshold invest × 2,
#: retirement/property/sponsor_no) are CLOSED (owner ruling 2026-09-13, see
#: WALK_DEAD_END_ALLOWLIST above) rather than allowlisted, so they never
#: reach NEEDS_INPUT and never appear here. Two facts remain, one each.
EXPECTED_DEAD_END_FACT_CENSUS: dict[str, int] = {
    "work.indonesian_work_sponsor_confirmed": 1,
    "family.sponsor_confirmed": 1,
}


def _load_walks() -> dict[str, dict[str, Any]]:
    """Read the walk corpus, keyed by label (which must match the file stem
    modulo the ``/``→``_`` filename encoding, so a renamed file cannot smuggle
    another walk's expectations in)."""

    walks: dict[str, dict[str, Any]] = {}
    for path in sorted(CORPUS_DIR.glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        label = str(spec["label"])
        assert label.replace("/", "_").replace("=", "_") == path.stem.replace("=", "_"), (
            f"{path.name}: file name does not encode its own label {label!r}"
        )
        walks[label] = spec
    return walks


def _evaluate_walks(walks: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Evaluate every walk through ``gold_coverage_eval._evaluate`` — the same
    verify → compile → evaluate → apply_public_policy_adapters path the gold
    replay and the coverage floor use. Never re-implemented here, so this
    census and those gates cannot drift on what "evaluate" means."""

    return {
        label: _evaluate(spec["overrides"], label, as_of=_AS_OF)["actual"]
        for label, spec in sorted(walks.items())
    }


def _outcome_violations(
    outcomes: dict[str, dict[str, Any]],
    expected: dict[str, tuple[str, tuple[str, ...]]] | None = None,
) -> list[str]:
    """Every walk whose (state, candidates) differ from the pinned pair."""

    pins = EXPECTED_OUTCOME if expected is None else expected
    violations: list[str] = []
    for label in sorted(set(outcomes) | set(pins)):
        actual = outcomes.get(label)
        if actual is None:
            violations.append(f"{label}: pinned but absent from the corpus")
            continue
        if label not in pins:
            violations.append(f"{label}: evaluated but not pinned in EXPECTED_OUTCOME")
            continue
        want_state, want_candidates = pins[label]
        got = (actual["state"], tuple(actual["candidates"]))
        if got != (want_state, want_candidates):
            violations.append(
                f"{label}: expected {want_state} {list(want_candidates)}, got {got[0]} {list(got[1])}"
            )
    return violations


def _dead_end_violations(
    outcomes: dict[str, dict[str, Any]],
    allowlist: dict[str, tuple[DeadEnd, ...]] | None = None,
) -> list[str]:
    """The invariant, both ways.

    A NEEDS_INPUT walk must be allowlisted and must block on EXACTLY the
    allowlisted facts (a new blocking fact is a new dead end, not a variant of
    an old one), and an allowlisted walk that no longer dead-ends is a STALE
    row that the curing PR must delete — otherwise the allowlist would outlive
    the defect and quietly re-authorise it.
    """

    rows = WALK_DEAD_END_ALLOWLIST if allowlist is None else allowlist
    violations: list[str] = []
    for label in sorted(outcomes):
        actual = outcomes[label]
        allowed = tuple(sorted(dead_end.fact for dead_end in rows.get(label, ())))
        missing = tuple(actual["missing_facts"])
        if actual["state"] == "NEEDS_INPUT":
            if not allowed:
                violations.append(
                    f"{label}: NEEDS_INPUT on {list(missing)} with no allowlist row — "
                    "the interview cannot ask for a fact it has no reachable question for"
                )
            elif missing != allowed:
                violations.append(
                    f"{label}: dead-ends on {list(missing)}, allowlist says {list(allowed)}"
                )
        elif allowed:
            violations.append(
                f"{label}: allowlisted for {list(allowed)} but now ends {actual['state']} — "
                "stale allowlist row, delete it in the PR that cured it"
            )
    for label in sorted(set(rows) - set(outcomes)):
        violations.append(f"{label}: allowlisted but absent from the corpus")
    return violations


def _decide(overrides: dict[str, Any], label: str) -> tuple[Any, Any, Any]:
    """``(raw_decision, compiled, request)``.

    ``_evaluate`` returns the flattened ``actual`` view (codes only), which
    cannot witness ``rule_ids``/``source_refs``. This reuses that module's own
    verified-pack loader and identity provider so the two never diverge on
    which pack, or which instant, is under test.
    """

    _pack_path, compiled = gold_coverage_eval._verified_compiled_pack(_AS_OF)
    persona = Persona(
        id=0, label=label, overrides=overrides, expected_state=DecisionState.NEEDS_INPUT
    )
    request = build_persona_request(persona)
    decision = evaluator.evaluate(
        request.applicant_facts(),
        compiled,
        effective_at=_AS_OF,
        observed_at=_AS_OF,
        identity_provider=gold_coverage_eval._offline_identity_provider,
    )
    return decision, compiled, request


def _engine_decision(overrides: dict[str, Any], label: str) -> Any:
    """The RAW ``Decision`` — ``evaluator.evaluate``, no public shaping."""

    decision, _compiled, _request = _decide(overrides, label)
    return decision


def _public_decision(overrides: dict[str, Any], label: str) -> Any:
    """The applicant-facing ``Decision`` — the same verify → compile →
    evaluate → ``apply_public_policy_adapters`` path ``_evaluate`` walks."""

    decision, compiled, request = _decide(overrides, label)
    return evaluate_path.apply_public_policy_adapters(
        decision,
        request.applicant_facts(),
        compiled,
        disclosed_review_flags=request.effective_review_flags(),
    )


def _scoped_allowlist(*labels: str) -> dict[str, tuple[DeadEnd, ...]]:
    """``WALK_DEAD_END_ALLOWLIST`` restricted to ``labels`` — what a
    single-walk assertion MUST be graded against.

    PR-0 gate finding, 2026-09-06: grading one mutated walk against the whole
    table made ``_dead_end_violations``' trailing "allowlisted but absent from
    the corpus" loop fire once per OTHER row, unconditionally, so the guilt
    assertions below were non-empty no matter what the mutation did — they
    would have passed against an engine that ignored the mutation entirely.
    Same shape for ``_outcome_violations`` and its "pinned but absent" loop.
    Scoping is what restores the guilt: with it, the ONLY thing that can put a
    violation in the list is the walk under test.
    """

    return {
        label: WALK_DEAD_END_ALLOWLIST[label]
        for label in labels
        if label in WALK_DEAD_END_ALLOWLIST
    }


def _scoped_expectation(*labels: str) -> dict[str, tuple[str, tuple[str, ...]]]:
    """``EXPECTED_OUTCOME`` restricted to ``labels`` — see ``_scoped_allowlist``."""

    return {label: EXPECTED_OUTCOME[label] for label in labels if label in EXPECTED_OUTCOME}


@pytest.fixture(scope="module")
def walks() -> dict[str, dict[str, Any]]:
    return _load_walks()


@pytest.fixture(scope="module")
def outcomes(walks: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return _evaluate_walks(walks)


def test_corpus_is_the_84_real_interview_walks(walks: dict[str, dict[str, Any]]) -> None:
    """An empty or shrunken corpus fails loudly: a census that passes because
    nobody fed it any walks is the green-but-dead shape (cicatrix #2).

    43 before PR-3, 61 before PR-5, 67 before PR-D3, 78 before D4a, 76 before
    PR-D4d, 82 before PR-D4c-2. PR-5's 6 new walks are the 5 offshore `retirement` bases plus the
    onshore neutral `retirement` walk, each replayed with `birth_date`
    overridden to `RETIREMENT_AGE_64_BIRTH_DATE` (age 64 on `CORPUS_TODAY`)
    instead of the corpus-wide default 25 — the generator's own age
    dimension, not a new tree branch. PR-D3's 11 new walks are real new
    branches: the two invest-vehicle below-threshold routes, the three
    declared-paid-activity branches, the retirement
    property/bank_deposit/undecided branches that used to dead-end, and the
    two STEPCHILD sponsor-permit answers — see `generate-walk-corpus.ts`.
    D4a REMOVES those same two STEPCHILD sponsor-permit walks: the D3-4 hold
    and the question they exercised had no pack requirement behind them for
    E31D (fresh grader review) and were retired, so the corpus shrinks
    78 -> 76. PR-D4d (THIS PR) adds 6: one walk per seq-21 product with the
    `sponsor.type` value that product's rule requires (`offshore/work/
    sponsor_government` covers E33A/E33B/E23V at once — identical
    condition; `offshore/work/sponsor_individual` covers E23U;
    `offshore/invest/pt_pma/sponsor_government` covers E33C, INVESTMENT
    purpose), one proving work item 1's new `other`+paid question end to
    end (`offshore/other/paid/sponsor_government`), one proving an
    unresolved answer is silence not a hold (`offshore/work/
    sponsor_unsure`), and the C6 regression walk
    (`offshore/other/no_paid_activity/medical`, coordinator-authorised scope
    addition) — corpus grows 76 -> 82. Every OTHER walk in the corpus is
    unchanged, byte-for-byte, EXCEPT the four `other`-tile walks whose
    `other_paid_activity` already resolves (`offshore/other`,
    `onshore/other`, `offshore/other/paid/employer_no`, `offshore/other/
    paid/sponsor_unsure`): work item 1 makes their branch ask
    `sponsor_category` for the first time, so their wire `sponsor.type`
    moves UNKNOWN(NOT_ASKED) -> KNOWN(NONE) — a byte change with no state
    change, verified by `test_every_walk_ends_in_its_pinned_outcome` staying
    green on their unmoved EXPECTED_OUTCOME entries.

    PR-D4c-2 (THIS PR, owner ruling SHWEB-20260911) adds 2: an explicit USD
    answer (`offshore/invest/merit/currency_usd`) and the explicit "I can't
    say yet" answer (`offshore/invest/undecided/currency_still_unsure`) for
    the new currency-bound `investment.investment_amount_usd` fact — corpus
    grows 82 -> 84. Three more walks change BYTES only, not count or state:
    `offshore/invest/merit`/`family`/`undecided` (unmodified) now also ask
    `investment_currency` as their branch's new first question, and its
    first OPTION is `idr` (tree.ts), so the untouched default answers it and
    the now-reachable `investment_capital_idr` too — that fact moves
    UNKNOWN(NOT_ASKED) -> KNOWN(1000000000) on all three, verified by
    `test_every_walk_ends_in_its_pinned_outcome` staying green on their
    unmoved EXPECTED_OUTCOME entries. `pt_pma`/`property`/`bank_deposit` are
    untouched, byte-for-byte — that branch, and the E28A rules that read it,
    are deliberately out of this PR's scope."""

    assert len(walks) == 84, f"expected 84 interview walks, found {len(walks)}"
    assert sorted(walks) == sorted(EXPECTED_OUTCOME), "corpus and EXPECTED_OUTCOME disagree"
    for label, spec in walks.items():
        assert spec["asked"], f"{label}: walk carries no asked-question history"
        assert spec["overrides"], f"{label}: walk carries no wire facts"


def test_every_walk_ends_in_its_pinned_outcome(outcomes: dict[str, dict[str, Any]]) -> None:
    violations = _outcome_violations(outcomes)
    assert not violations, "interview-walk outcomes moved:\n  " + "\n  ".join(violations)


def test_walk_state_census_is_2_dead_ends_15_no_paths_and_67_answers(
    outcomes: dict[str, dict[str, Any]],
) -> None:
    """The headline number of the decisiveness wave. Every PR that changes it
    updates this literal and says which walks moved, in its own body.

    36/0/7 on seq-19; 21/0/22 once the signed seq-20 bundle's stay-day
    widening landed; 11/10/22 with PR-2's reorder on top; 0/10/51 over a
    43 → 61 corpus with PR-3's interview; 2/10/55 over a 61 → 67 corpus with
    PR-5's age dimension on top; 2/14/62 over a 67 → 78 corpus with PR-D3
    (module docstring); 2/15/59 over a 78 → 76 corpus with D4a. PR-D4d adds 6
    new walks, all SUPPORTED_CANDIDATES on the pack signed TODAY
    (rulepack-prod-020 — none of them exercise a rule that reads
    `sponsor.type` yet; that is seq-21, unsigned): 2/15/59 -> 2/15/65 over a
    76 -> 82 corpus. No existing walk's STATE moves — the four `other`-tile
    walks whose wire `sponsor.type` changes bytes (see the corpus-count
    test above) keep their pinned (state, candidates) exactly, which is
    what `test_every_walk_ends_in_its_pinned_outcome` proves.

    PR-D4c-2 (THIS PR) adds 2, both SUPPORTED_CANDIDATES [C2] on the pack
    signed today (no seq-22 rule reads `investment.investment_amount_usd`
    yet — the activation dependency stated in this PR's body): the explicit
    USD answer and the explicit "I can't say yet" answer, both decided by
    `family.sponsor_confirmed == true` alone, unaffected: 2/15/65 -> 2/15/67
    over an 82 -> 84 corpus. No existing walk's STATE moves here either —
    the three `offshore/invest/merit`/`family`/`undecided` walks whose wire
    `investment.investment_capital_idr` changes bytes (see the corpus-count
    test above) keep their pinned (state, candidates) exactly. D4a (owner
    ruling SHWEB-20260911) had two parts:

    1. The sponsor-status fix: one walk's STATE moves —
       `offshore/other/no_paid_activity` was SUPPORTED_CANDIDATES [C6]
       because `other_purpose = "transit"` was mapped to the OTHER purpose;
       it now correctly maps to TRANSIT (`el.a1.tourism`/`el.d1-*`), and
       this synthetic identity clears neither rule's other conditions
       (nationality for A1, MULTIPLE entry for D1), so it becomes
       NO_SUPPORTED_PATH — an honest answer, not a defect (see
       EXPECTED_OUTCOME's own comment on this walk). Eight more SUPPORTED_
       CANDIDATES walks gain an extra named product (E31B/E31H/E31J —
       `family_sponsor_status_code` is now a real FACT) but keep their
       STATE. Over the unchanged 78-walk corpus this alone would move
       2/14/62 → 2/15/61.
    2. The STEPCHILD/E31D hold removal: no pack requirement for the
       sponsor's own permit exists for E31D (fresh grader review), so
       `generate-walk-corpus.ts`'s two `sponsor_permit_no`/
       `sponsor_permit_unsure` walks — both SUPPORTED_CANDIDATES
       [C1, E31D] — are retired along with the question and hold they
       exercised. Corpus 78 → 76, SUPPORTED_CANDIDATES 61 → 59.

    D4a net over both parts: 2/14/62 → 2/15/59. PR-D4d adds 6: 2/15/59 →
    2/15/65. PR-D4c-2 (THIS PR) adds 2: 2/15/65 → 2/15/67."""

    census = dict(Counter(outcome["state"] for outcome in outcomes.values()))
    assert (
        census
        == EXPECTED_STATE_CENSUS
        == {
            "NEEDS_INPUT": 2,
            "NO_SUPPORTED_PATH": 15,
            "SUPPORTED_CANDIDATES": 67,
        }
    )
    assert census["NEEDS_INPUT"] == 2
    # NOT a claim about production. The corpus carries no disclosure flags, so
    # the review arm of `apply_public_policy_adapters` is unreachable from
    # here by construction: this line says the FIXTURES trigger no review, and
    # a regression that adds a disclosure flag passes it invisibly. Bound 1 of
    # the module docstring, with the measurement.
    assert census.get("HUMAN_REVIEW_REQUIRED", 0) == 0
    assert census["NO_SUPPORTED_PATH"] == 15


def test_dead_end_fact_census_matches_the_blocking_fact_table(
    outcomes: dict[str, dict[str, Any]],
) -> None:
    census = Counter(
        fact
        for outcome in outcomes.values()
        if outcome["state"] == "NEEDS_INPUT"
        for fact in outcome["missing_facts"]
    )
    assert dict(census) == EXPECTED_DEAD_END_FACT_CENSUS


def test_no_walk_renders_the_same_reason_code_twice(
    outcomes: dict[str, dict[str, Any]],
) -> None:
    """A NO_SUPPORTED_PATH sheet must not print one sentence twice.

    ``engine-adapter.ts`` maps ``no_path_reasons`` 1:1 and looks the copy up by
    CODE alone (``SUPPORT_REASON_COPY``), so two entries sharing a code are two
    identical paragraphs in front of a real person. This PR is what makes that
    reachable — before the reorder ZERO walks reached NO_SUPPORTED_PATH — so
    the guard ships with it.

    Measured 2026-09-07 on seq-20 BEFORE ``_merge_reasons_by_code``: six walks
    (the five ``offshore/retirement/*`` and ``onshore/retirement``) rendered
    ``['AGE_BELOW_55', 'AGE_BELOW_55']``, one entry for
    ``hf.e33e.age-below-55`` and one for ``hf.e33f.age-below-55``. Reverting
    that helper to ``_dedupe_reasons`` turns this test red on all six.

    Stated over EVERY walk and every reason list rather than over the six
    known ones: a new pack that gives two products one code anywhere is the
    same defect, and this catches it without being re-pinned.
    """

    violations = []
    for label, actual in sorted(outcomes.items()):
        for field in ("no_path_reason_codes", "review_reason_codes"):
            codes = list(actual.get(field, ()))
            repeated = sorted({code for code in codes if codes.count(code) > 1})
            if repeated:
                violations.append(f"{label}: {field} repeats {repeated} — rendered as {codes}")
    assert not violations, "a reason code is rendered more than once:\n  " + "\n  ".join(violations)


def test_the_retirement_walk_merges_age_below_55_keeping_both_rules_and_both_refs(
    walks: dict[str, dict[str, Any]],
) -> None:
    """The real-pack witness for the merge, on the walk it was measured on.

    ``offshore/retirement/property`` is excluded by TWO products for the same
    legal reason — E33E and E33F both say the applicant is under 55 — and
    before ``_collapse_reader_reasons`` the sheet carried the code twice.

    All three assertions matter, and the last two are the ones that forbid the
    WRONG fix. A naive dedupe on the code would satisfy the first and fail
    these: ``_dedupe_reasons`` uses ``setdefault``, so it would have kept
    ``hf.e33e``'s entry and silently dropped both ``hf.e33f`` and the source
    record only ``hf.e33f`` cites. Measured 2026-09-07 on
    ``rulepack-prod-020.signed.json``:

        [0] AGE_BELOW_55  ('hf.e33e.age-below-55',)  (9248b1d7,)
        [1] AGE_BELOW_55  ('hf.e33f.age-below-55',)  (6f5135f2, 9248b1d7)

    One ref set happens to be a subset of the other in THIS pair; nothing in
    the contract guarantees that for the next one, which is why the union is
    asserted as a union rather than as 'the longer entry wins'.
    """

    label = "offshore/retirement/property"
    decision = _public_decision(walks[label]["overrides"], label)
    assert decision.state.value == "NO_SUPPORTED_PATH"

    age_reasons = [reason for reason in decision.no_path_reasons if reason.code == "AGE_BELOW_55"]
    assert len(age_reasons) == 1, (
        f"AGE_BELOW_55 must render exactly once, got {len(age_reasons)} entries — "
        f"{[list(reason.rule_ids) for reason in age_reasons]}"
    )

    merged = age_reasons[0]
    assert set(merged.rule_ids) == {"hf.e33e.age-below-55", "hf.e33f.age-below-55"}, (
        "the merge dropped a rule id — both excluding rules must survive the collapse"
    )

    raw = _engine_decision(walks[label]["overrides"], label)
    every_ref = {
        ref
        for reason in raw.no_path_reasons
        if reason.code == "AGE_BELOW_55"
        for ref in reason.source_refs
    }
    assert len(every_ref) == 2, f"expected two distinct citations upstream, got {every_ref}"
    assert set(merged.source_refs) == every_ref, (
        "the merge dropped a citation — the union of every AGE_BELOW_55 source_ref "
        "the ENGINE produced must survive onto the single merged reason"
    )


def test_no_walk_dead_ends_outside_the_allowlist(outcomes: dict[str, dict[str, Any]]) -> None:
    violations = _dead_end_violations(outcomes)
    assert not violations, "walk-census invariant broken:\n  " + "\n  ".join(violations)


def test_allowlist_has_exactly_the_two_pr_d3_rows() -> None:
    """PR-3's deliverable — ``len(...) == 0`` — held for exactly one wave;
    PR-5 reopened it with 2 rows; THIS PR (PR-D3) CURES both of PR-5's rows
    (both retirement age64 walks now answer). A first pass opened it again
    with 5 new rows; owner ruling 2026-09-13 CLOSED 3 of them (the
    below-threshold twin-base pattern) rather than allowlist them — see
    `WALK_DEAD_END_ALLOWLIST`'s module-level comment. 2 rows remain, neither
    a re-hash of PR-5's shape.

    An equality against a named 2-row dict is still not a loosened count in
    the sense PR-3 warned about: it names every row explicitly, and any
    additional row — however well argued — still has to move this literal in
    the PR that adds it."""

    assert set(WALK_DEAD_END_ALLOWLIST) == {
        "offshore/other/paid/sponsor_unsure",
        "offshore/retirement/undecided/age64/still_unsure",
    }
    assert len(WALK_DEAD_END_ALLOWLIST) == 2


def _unaskable_violations(
    walks: dict[str, dict[str, Any]],
    rows: dict[str, tuple[DeadEnd, ...]],
) -> list[str]:
    """Every allowlist row whose stated REASON is contradicted by the walk's
    own ``asked`` history — the claim checked, not taken on trust.

    Returns violations instead of asserting so the guilt test below can drive
    it with a fabricated row. That indirection is what keeps this machinery
    honest now that ``WALK_DEAD_END_ALLOWLIST`` is empty: iterating an empty
    table proves nothing, and a validator nobody exercises is a validator that
    has quietly stopped working by the time the next row needs it.
    """

    violations: list[str] = []
    for label, dead_ends in sorted(rows.items()):
        asked = set(walks[label]["asked"])
        for dead_end in dead_ends:
            if dead_end.why_unaskable == NO_QUESTION_IN_TREE:
                if dead_end.source_question is not None:
                    violations.append(
                        f"{label}: {dead_end.fact} claims no question emits it, "
                        f"yet names {dead_end.source_question!r}"
                    )
            elif dead_end.why_unaskable == QUESTION_NOT_IN_THIS_WALK:
                if dead_end.source_question in asked:
                    violations.append(
                        f"{label}: {dead_end.source_question!r} IS asked in this walk — "
                        f"{dead_end.fact} is no longer unaskable here"
                    )
            elif dead_end.why_unaskable == ANSWER_NEVER_CERTIFIED:
                if dead_end.source_question not in asked:
                    violations.append(
                        f"{label}: {dead_end.source_question!r} is not asked in this walk, "
                        "so the mapper never gets an answer to refuse"
                    )
            else:
                violations.append(f"{label}: unknown reason {dead_end.why_unaskable!r}")
    return violations


def test_every_allowlisted_dead_end_is_genuinely_unaskable_in_its_own_walk(
    walks: dict[str, dict[str, Any]],
) -> None:
    """The allowlist's REASON, checked against the walk's own history."""

    violations = _unaskable_violations(walks, WALK_DEAD_END_ALLOWLIST)
    assert not violations, "an allowlist row's reason is false:\n  " + "\n  ".join(violations)


def test_guilt_a_row_whose_question_this_walk_now_asks_is_caught(
    walks: dict[str, dict[str, Any]],
) -> None:
    """GUILT, and PR-3's own cure is the witness.

    Re-anchored: this test used to be the assertion loop above, and that loop
    is vacuous now that the allowlist is empty. What it claimed — "the moment
    the invest branch starts asking ``family_sponsor_confirmed``, that row's
    ``QUESTION_NOT_IN_THIS_WALK`` reason is false" — is exactly what happened,
    so it is restated here as a fabricated row over the REAL corpus rather
    than deleted with the row it graded.

    Both branches of the reason vocabulary are driven, in the two directions
    this PR moved: ``offshore/invest/pt_pma`` now DOES ask
    ``family_sponsor_confirmed`` (so a ``QUESTION_NOT_IN_THIS_WALK`` claim is
    a lie), and ``offshore/tourism`` does NOT ask it (so an
    ``ANSWER_NEVER_CERTIFIED`` claim, which asserts the mapper refused an
    answer it was given, is equally a lie).
    """

    asks_it = "offshore/invest/pt_pma"
    assert "family_sponsor_confirmed" in walks[asks_it]["asked"], (
        "the cure this test is anchored on is gone — re-anchor it onto a walk "
        "that DOES ask the question"
    )
    stale_row = DeadEnd(
        "family.sponsor_confirmed", "family_sponsor_confirmed", QUESTION_NOT_IN_THIS_WALK
    )
    violations = _unaskable_violations(walks, {asks_it: (stale_row,)})
    assert violations and "IS asked in this walk" in violations[0]

    never_asks_it = "offshore/tourism"
    assert "family_sponsor_confirmed" not in walks[never_asks_it]["asked"]
    fabricated_row = DeadEnd(
        "family.sponsor_confirmed", "family_sponsor_confirmed", ANSWER_NEVER_CERTIFIED
    )
    assert _unaskable_violations(walks, {never_asks_it: (fabricated_row,)})

    # A row that names a source question while claiming NO question emits the
    # fact contradicts itself, and a typo in the reason string must not pass
    # silently either.
    assert _unaskable_violations(
        walks,
        {
            asks_it: (
                DeadEnd(
                    "family.sponsor_confirmed", "family_sponsor_confirmed", NO_QUESTION_IN_TREE
                ),
            )
        },
    )
    assert _unaskable_violations(walks, {asks_it: (DeadEnd("x", None, "typo"),)})


def test_guilt_withdrawing_the_newly_asked_fact_restores_the_dead_end(
    walks: dict[str, dict[str, Any]],
) -> None:
    """GUILT, on the real engine, and the direct witness that PR-3's cure is
    the QUESTION and not a pack edit or a corpus artefact.

    Re-anchored a third time. Seq-19's anchor (``onshore/tourism``) answers on
    seq-20; seq-20's (``onshore/business``) ends NO_SUPPORTED_PATH under PR-2;
    and PR-2's shape — hand ``offshore/invest/pt_pma`` its blocking fact and
    watch the block MOVE to ``process.wants_onshore_conversion`` rather than
    lift — cannot be reproduced here either, because this PR asks BOTH facts:
    there is nothing left for the block to move onto. So the mutation is
    inverted. Instead of supplying the fact, WITHDRAW it, and the walk falls
    straight back into the dead end this PR cured.

    Measured 2026-09-07 on ``rulepack-prod-020.signed.json``:

    - ``family.sponsor_confirmed`` UNKNOWN → NEEDS_INPUT on exactly
      ``['family.sponsor_confirmed']`` — byte for byte the pre-PR row.
    - the same fact KNOWN ``false`` → NO_SUPPORTED_PATH, an ANSWER. Denying
      C2's sponsor premise is decisive now precisely because
      ``wants_onshore_conversion`` is answered too, so D12 has no missing fact
      left to bid with.

    With the allowlist empty, the first mutation is graded against ``{}`` —
    the permanent form of the invariant, with no excuse available."""

    label = "offshore/invest/pt_pma"
    assert "family_sponsor_confirmed" in walks[label]["asked"], (
        "this walk no longer asks the fact the test withdraws — re-anchor"
    )

    withdrawn = dict(walks[label]["overrides"])
    withdrawn["family.sponsor_confirmed"] = {"status": "UNKNOWN", "reason": "NOT_ASKED"}
    actual = _evaluate(withdrawn, label, as_of=_AS_OF)["actual"]
    assert actual["state"] == "NEEDS_INPUT", (
        "withdrawing the fact no longer dead-ends this walk — the cure is no "
        "longer attributable to the question and this test proves nothing"
    )
    assert actual["missing_facts"] == ["family.sponsor_confirmed"]
    assert _dead_end_violations({label: actual}, allowlist=_scoped_allowlist(label))

    denied = dict(walks[label]["overrides"])
    denied["family.sponsor_confirmed"] = {"status": "KNOWN", "value": False}
    denied_actual = _evaluate(denied, label, as_of=_AS_OF)["actual"]
    assert denied_actual["state"] == "NO_SUPPORTED_PATH"
    assert not _dead_end_violations({label: denied_actual}, allowlist=_scoped_allowlist(label))


def test_guilt_a_walk_that_loses_its_answer_is_caught(
    walks: dict[str, dict[str, Any]],
) -> None:
    """GUILT: ``offshore/work`` is one of the 55 walks that DO answer (E23).
    Take its ``work.indonesian_work_sponsor_confirmed`` away and the outcome
    pin must fire.

    Measured 2026-09-07 on seq-20 with PR-2's reorder, and RE-MEASURED under
    this PR's corpus — ``work_role`` left the walk, so its fixture changed —
    with the same result. The mutated walk
    lands on NO_SUPPORTED_PATH, not NEEDS_INPUT — E23 is the only product whose
    ELIGIBILITY rules cover EMPLOYMENT, and denying its sponsor gate leaves
    nothing that could ever cover the purpose. Without the reorder this same
    mutation produced a dead end, which is why the seq-20 version of this test
    also asserted ``_dead_end_violations``. It no longer can: a
    NO_SUPPORTED_PATH walk is an ANSWER, and the invariant deliberately says
    nothing about it. That second assertion is therefore not dropped but
    REPLACED by the two things this mutation actually witnesses — the exact
    state and the invariant's silence — rather than kept as an assertion that
    only passed because it was graded against the whole table (the PR-0 gate's
    vacuity finding)."""

    mutated = dict(walks["offshore/work"]["overrides"])
    mutated["work.indonesian_work_sponsor_confirmed"] = {"status": "KNOWN", "value": False}
    actual = _evaluate(mutated, "offshore/work", as_of=_AS_OF)["actual"]

    assert actual["state"] == "NO_SUPPORTED_PATH"
    assert actual["candidates"] == []
    assert _outcome_violations(
        {"offshore/work": actual}, expected=_scoped_expectation("offshore/work")
    )
    # ...and the invariant stays SILENT, because losing an answer this way is
    # not a dead end. Scoped, so the silence is about this walk only.
    assert not _dead_end_violations(
        {"offshore/work": actual}, allowlist=_scoped_allowlist("offshore/work")
    )


def test_guilt_a_dead_end_on_an_unlisted_fact_is_caught() -> None:
    """GUILT: a NEEDS_INPUT on a fact nobody allowlisted — the shape a new
    signed rule with ``on_unknown: NEEDS_INPUT`` on an unaskable fact would
    produce — is a violation, and stays one when the allowlist is EMPTY, which
    is no longer a hypothetical: it is the live table this PR ships."""

    # `offshore/work` is one of the 55 ANSWERING walks, so it carries no
    # allowlist row — which is exactly the branch under test here.
    fabricated = {
        "offshore/work": {
            "state": "NEEDS_INPUT",
            "candidates": [],
            "missing_facts": ["work.employer_is_indonesian_entity"],
        }
    }
    assert _dead_end_violations(fabricated, allowlist=_scoped_allowlist("offshore/work"))
    assert _dead_end_violations(
        {"offshore/work": {"state": "NEEDS_INPUT", "candidates": [], "missing_facts": []}},
        allowlist={},
    )


def test_guilt_an_allowlisted_walk_that_blocks_on_a_DIFFERENT_fact_is_caught() -> None:
    """GUILT for ``_dead_end_violations``' ``elif missing != allowed`` branch —
    the one that compares FACTS instead of counting states.

    Independent review 2026-09-06 (codex, MEDIUM) measured the hole this
    fills: with ``WALK_DEAD_END_ALLOWLIST`` empty, that branch is unreachable
    from the live table, so deleting it left all 14 tests in this file green.
    An empty allowlist cannot exercise a rule about what a row PERMITS, so the
    row is fabricated — but the rule is the load-bearing one: it is what stops
    a "cure" that merely moves the block from reading as a no-op.

    Both directions, because the equality has to bite both ways: a walk
    blocking on a fact its row does not name is a violation, and the same walk
    blocking on exactly the named fact is not.
    """

    label = "offshore/invest/pt_pma"
    row = DeadEnd("family.sponsor_confirmed", "family_sponsor_confirmed", QUESTION_NOT_IN_THIS_WALK)
    allowlist = {label: (row,)}

    moved = {
        label: {
            "state": "NEEDS_INPUT",
            "candidates": [],
            "missing_facts": ["process.wants_onshore_conversion"],
        }
    }
    violations = _dead_end_violations(moved, allowlist=allowlist)
    assert violations and "allowlist says" in violations[0]
    assert len(violations) == 1, f"only the moved block may be reported here: {violations}"

    unmoved = {
        label: {
            "state": "NEEDS_INPUT",
            "candidates": [],
            "missing_facts": ["family.sponsor_confirmed"],
        }
    }
    assert not _dead_end_violations(unmoved, allowlist=allowlist)


def test_guilt_a_stale_allowlist_row_is_caught() -> None:
    """GUILT: the cure lands, the walk answers, and the allowlist row stays —
    the way an allowlist normally outlives its defect. Must be red.

    Re-anchored onto a FABRICATED row, and it had to be: this test was graded
    against the live ``offshore/invest/pt_pma`` row, and PR-3 deleted that row
    by curing the walk — which is precisely the transition the previous
    docstring said would turn it red. There is no live row left to anchor on
    (``WALK_DEAD_END_ALLOWLIST`` is empty and the test above pins that), so
    the choice is a fabricated row or no coverage at all for the branch of
    ``_dead_end_violations`` that reports a row outliving its defect. The
    branch is what a FUTURE row will depend on, so it keeps its test.

    The anchor is still the real cure: the state and candidate list fed in are
    the ones ``offshore/invest/pt_pma`` actually reaches now (pinned in
    ``EXPECTED_OUTCOME``), so if that walk ever stops answering C2 this test's
    premise is visibly stale rather than quietly fictional."""

    label = "offshore/invest/pt_pma"
    assert EXPECTED_OUTCOME[label] == ("SUPPORTED_CANDIDATES", ("C2",)), (
        "the cured outcome this fabricated row is built on moved — re-anchor"
    )
    stale_row = DeadEnd(
        "family.sponsor_confirmed", "family_sponsor_confirmed", QUESTION_NOT_IN_THIS_WALK
    )
    cured = {
        label: {
            "state": "SUPPORTED_CANDIDATES",
            "candidates": ["C2"],
            "missing_facts": [],
        }
    }
    violations = _dead_end_violations(cured, allowlist={label: (stale_row,)})
    assert violations and "stale allowlist row" in violations[0]
    assert len(violations) == 1, f"only the stale row may be reported here: {violations}"


def test_d4a_e31e_minor_named_at_engine_level_privacy_held_at_public_level(
    walks: dict[str, dict[str, Any]],
) -> None:
    """D4a (owner ruling SHWEB-20260911) proof for E31E specifically.

    No EXISTING corpus walk exercises a minor identity: every family/diaspora
    walk uses the corpus's default 25-year-old birth date, so
    `el.e31e-child-itas-support`'s `derived.age_years < 18` gate fails
    regardless of this PR's fix. This test overrides ONLY `person.birth_date`
    on the real `offshore/family/PARENT/spNat=IT` walk — relation PARENT,
    foreign sponsor, `family.sponsor_status_code` already KNOWN via this PR's
    `mapFamilySponsorStatus` fix, `person.marital_status` already SINGLE —
    every OTHER E31E condition already holds in that walk's own answers.

    Proves both halves the brief required in one measurement:
      * ENGINE level: E31E is now NAMED (this fix's entire point).
      * PUBLIC level: `evaluate_path._apply_minor_privacy_hold` (untouched by
        this PR) still empties candidates and forces
        HUMAN_REVIEW_REQUIRED — a minor applicant neither gains a review
        (already unconditional for any known minor) nor loses the privacy
        protection (it holds on `derived.is_minor` alone, independent of
        `family.sponsor_status_code`).
    """
    overrides = copy.deepcopy(walks["offshore/family/PARENT/spNat=IT"]["overrides"])
    overrides["person.birth_date"] = {"status": "KNOWN", "value": "2015-01-01"}

    engine = _engine_decision(overrides, "adhoc/d4a-e31e-minor")
    assert engine.state is DecisionState.SUPPORTED_CANDIDATES
    assert "E31E" in [c.product_code for c in engine.candidates]

    public = _public_decision(overrides, "adhoc/d4a-e31e-minor")
    assert public.state is DecisionState.HUMAN_REVIEW_REQUIRED
    assert public.candidates == ()
    assert [r.code for r in public.review_reasons] == ["MINOR_GUARDIAN_PRIVACY_REVIEW"]


def test_d4a_transit_purpose_positively_reaches_d1(
    walks: dict[str, dict[str, Any]],
) -> None:
    """D4a: `EXPECTED_OUTCOME["offshore/other/no_paid_activity"]` proves the
    ROUTE changed (`other_purpose = "transit"` now maps to TRANSIT, not
    OTHER) but, on that walk's own answers (SINGLE entry, non-ASEAN
    nationality), the result is an honest NO_SUPPORTED_PATH — neither
    `el.a1.tourism` nor `el.d1-multi-entry-support` fires for THIS identity.

    This proves the route is positively reachable, not merely re-labelled:
    overriding only `intent.entry_pattern` to MULTIPLE — D1's own gate,
    `el.d1-multi-entry-support`, needs nothing else this walk doesn't already
    have (TRANSIT purpose, 121 stay days, under the 180-day cap) — is enough
    for D1 to answer SUPPORTED.
    """
    overrides = copy.deepcopy(walks["offshore/other/no_paid_activity"]["overrides"])
    overrides["intent.entry_pattern"] = {"status": "KNOWN", "value": "MULTIPLE"}

    engine = _engine_decision(overrides, "adhoc/d4a-transit-positive")
    assert engine.state is DecisionState.SUPPORTED_CANDIDATES
    assert "D1" in [c.product_code for c in engine.candidates]
