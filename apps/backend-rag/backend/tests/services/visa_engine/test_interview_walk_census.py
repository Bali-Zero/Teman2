"""Interview-walk decisiveness census: what the PUBLIC funnel actually answers.

``test_gold_coverage_floor.py`` proves the pack can support a product when
every fact arrives. This file proves the opposite half, and it is the half
the user lives in: replay the **112 real interview walks** — every distinct
path through ``flow.ts``'s two-arm spine and ``getCategoryQuestionIds``'
eleven categories, each answered through the real ``fact-mapper.ts`` —
against the highest signed PRODUCTION pack, and pin the outcome census.
Current ENGINE census (E23V-DEFECT, mission seq-22, 2026-09-15), on signed
seq-20: **1 HUMAN_REVIEW_REQUIRED / 2 NEEDS_INPUT / 17 NO_SUPPORTED_PATH /
92 SUPPORTED_CANDIDATES** (W-VO-E's 94-walk figure was 76; W-VO-Q's 111-walk
figure was 16 NO_SUPPORTED_PATH); on signed seq-21 **1 / 1 / 17 / 93**; on
the seq-22 fold that actually CURES the E23V defect (``fold_pack_seq22.py``),
now carrying D23 "OPTION B-STUDIO" (2026-09-16) — the highest candidate
source above signed seq-20 today, seq-21 having been signed (2026-09-15) but
stopped before ACTIVATION, its bundle never entering this repo — **3 / 1 /
14 / 94** — the pins are kept per candidate/signed sequence
(``EXPECTED_OUTCOME_BY_SEQUENCE``), so the census stays green on both sides
of a signature. The FUNNEL
census the applicant actually meets is the second column of the table under
"THE DISCLOSURE-FLAG LAYER" below. The paragraphs below are the historical
record of how it got here, each keeping the count that was true when it was
written.

W-VO-E adds a THIRD question to the two this file already answered ("where
does each walk end" and "what does the applicant meet"): **which products
can the interview name at all.** Twelve of the 29 products carrying a
SUPPORT rule in the signed pack were named by ZERO of the 84 walks — a gap
no test in the repository could see, because a census grades the walks that
exist and a coverage floor grades the pack, and neither notices a product
the funnel never offers. ``test_every_support_bearing_product_is_named_by_
some_walk`` reads the universe from the COMPILED pack (not from a list
maintained here) and fails when a SUPPORT-bearing product is named on no
walk; ``UNREACHABLE_BY_RULING`` is the one documented, self-invalidating
excuse table. Eleven of the twelve needed NO tree change — only new answers
to questions ``tree.ts`` already asks — and the twelfth (BRIDGING) is
unreachable by ruling, not by accident. ENGINE-named distinct products:
**17 -> 28**; public ones **17 -> 27** (E31E is named at engine level and
held by the minor-privacy adapter at public level — see
``PRIVACY_HELD_WALKS``).

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

THE DISCLOSURE-FLAG LAYER, carried since 2026-09-13 (W-VO-H schema half).
The bound this section used to carry — "disclosure flags are not carried, so
this file proves LESS than it looks like it proves" — is RETIRED, and the
file now measures BOTH halves of the wire request. Read the two censuses as
two different questions:

- **ENGINE level** (``outcomes``, no flags): what the pack decides on the
  facts alone. This is the census every table above pins, and it is the
  right instrument for a pack or interview change.
- **FUNNEL level** (``flagged_outcomes``, the flags each walk actually
  raises, straight from its own fixture): what the applicant meets.
  ``evaluate_path.py::_apply_disclosed_review_flags`` is monotone and,
  for any decision the engine actually produces, unconditional — ONE flag
  rewrites the whole decision to HUMAN_REVIEW_REQUIRED with
  ``candidates=()``, ``missing_facts=()``, ``no_path_reasons=()``,
  ``quotes=()`` — so a flag DELETES a verdict the signed pack had already
  proven. ("For any decision the engine actually produces" is the exact
  qualifier: the adapter returns early when ``decision_id`` or ``public_id``
  is ``None``, which no evaluated decision is — council round 1
  (council/journal.jsonl), on the word "unconditional".)

MEASURED 2026-09-13 on ``rulepack-prod-020.signed.json`` over all 94 walks
(re-measured 2026-09-14 over W-VO-Q's 111 — see below the table),
both censuses in the same run (``test_the_flagged_census_is_the_funnel_the_
applicant_meets``):
   - **92 SUPPORTED_CANDIDATES means 92 walks reach candidates AT ENGINE
     LEVEL, with no disclosure flags supplied.** It does NOT mean 92
     applicants see a recommendation without human review — the FUNNEL
     column, 85, is the one an applicant meets.
   - **The hold counts are a property of these fixtures, not of
     production.** The ENGINE column's single hold was ``== 0`` until
     W-VO-E; it now allows exactly one and pins its walk and its reason code
     (``MINOR_GUARDIAN_PRIVACY_REVIEW``). The FUNNEL column's nine are that
     same one plus the eight walks that raise a disclosure flag.
   - **Both arms of ``apply_public_policy_adapters`` are now exercised, and
     the two sentences that used to stand here are retired.** They said the
     review-FLAG arm was untouched by any walk and that "a regression which
     ADDS a disclosure flag — or fails to REMOVE one — passes this census
     invisibly"; both stopped being true when the disclosure-flag layer
     landed. ``test_guilt_a_walk_that_gains_a_flag_is_caught`` and
     ``test_guilt_a_walk_that_loses_its_flag_is_caught`` are what stopped it
     (council round 4 (council/journal.jsonl), on exactly this
     contradiction).
     The ``work_role`` episode the old text cited remains the reason the
     layer exists at all.

===========================  ======  =======
state                        ENGINE  FUNNEL
===========================  ======  =======
SUPPORTED_CANDIDATES             92       85
NO_SUPPORTED_PATH                16       16
NEEDS_INPUT                       2        1
HUMAN_REVIEW_REQUIRED             1        9
===========================  ======  =======

W-VO-Q (mission SAETTA-VO3) moved the corpus 94 -> 111 and the table
above is re-measured on it (2026-09-14, signed seq-20): ENGINE and FUNNEL
both +16 SUPPORTED_CANDIDATES (76 -> 92, 69 -> 85) and +1
NO_SUPPORTED_PATH (the business explorer who converts onshore with no
investor route, on the named cause ``D12_NOT_CONVERTIBLE``), and no new
hold — none of its seventeen walks raises a disclosure flag, so the per-flag
table below is unchanged. With the signed seq-21 bundle as the highest pack
the ENGINE column reads 93/16/1/1 (``offshore/other/paid/sponsor_unsure``
moves NEEDS_INPUT -> SUPPORTED_CANDIDATES [E33B]) and the FUNNEL column is
identical, because that walk is held by its NOT_CERTAIN flag on both. (Its
capital-market walk first answered the `undecided` vehicle and was held by
ACTIVITY_BOUNDARY; council round 1 (council/journal.jsonl) caught that the
funnel then named E28C to nobody, and the tree gained the
``capital_market`` vehicle the pack decides.) The history of the 94-walk
columns follows unchanged.

W-VO-E moved both columns by the same +9/+1 shape — +9
SUPPORTED_CANDIDATES and +1 HUMAN_REVIEW_REQUIRED, i.e. ENGINE 67/15/2/0 ->
76/15/2/1 and FUNNEL 60/15/1/8 -> 69/15/1/9 (an earlier draft of this
sentence said "+9/-1", which sums to eight walks, not ten — council round 6,
reserve seat (council/journal.jsonl)): nine of its ten new walks answer at both levels, and
the tenth — the minor — is the single ENGINE hold. The FUNNEL column keeps its 8 flag-driven holds and gains
that same one: no new walk raises a disclosure flag (the per-flag table
below is unchanged from the 84-walk corpus, measured, not derived).

Per flag — ``test_every_disclosure_flag_reports_the_walks_it_rewrites``
prints this table on every run:

=================  ========  ==================================================
flag               rewrites  from-state -> to-state
=================  ========  ==================================================
ACTIVITY_BOUNDARY         6  SUPPORTED_CANDIDATES -> HUMAN_REVIEW_REQUIRED (×6)
NOT_CERTAIN               2  SUPPORTED_CANDIDATES -> HUMAN_REVIEW_REQUIRED (×1)
                             NEEDS_INPUT -> HUMAN_REVIEW_REQUIRED (×1)
=================  ========  ==================================================

(On signed seq-21 the NOT_CERTAIN row reads SUPPORTED_CANDIDATES ->
HUMAN_REVIEW_REQUIRED ×2: the sponsor_unsure walk is answered at engine
level there, and its flag still rewrote it — PRE-A1.)

**PLAN VISA-ORACLE-DW-20260919 slice A1 (owner ruling 2026-09-13), landed
2026-09-19: neither ``ACTIVITY_BOUNDARY`` nor ``NOT_CERTAIN`` "rewrites" a
walk any more.** ``_apply_disclosed_review_flags`` now holds ONLY a flag in
``evaluate_path.HOLDING_DISCLOSED_FLAGS`` (``CRIMINAL_RECORD``, today) —
every other flag, including both this corpus raises, adds a named
``notices`` condition and keeps the pack's own state and candidates. On
signed seq-22 (94/14/1/3 ENGINE, W-VO-Q's 111-walk corpus, re-measured
2026-09-19), the FUNNEL census is now IDENTICAL to the ENGINE census —
94/14/1/3 — because zero of this corpus's flagged walks raise
``CRIMINAL_RECORD``. The two rows in the table above read "rewrites" for
the historical (pre-A1) run only; ``test_every_disclosure_flag_reports_the_
walks_it_rewrites`` now asserts the opposite property — that engine state
and candidates survive untouched and only a ``*_CONDITION`` notice is
added — against ``EXPECTED_CONDITION_REASON_FOR_FLAG``, not
``EXPECTED_REVIEW_REASON_FOR_FLAG`` (retired). The fleet-wide kill switch
``VISA_ORACLE_HOLDING_FLAGS`` can restore any flag's pre-A1 hold without a
redeploy — see ``test_guilt_the_holding_env_var_restores_a_deleted_
verdict``.

The other nine flags in ``DisclosedReviewFlag`` rewrite ZERO walks: no
corpus walk answers ``trip_scope = "multiple"`` (``MULTI_PURPOSE_TRIP``),
none discloses a ``review_gate`` item (the seven compliance disclosures —
the generator answers that question with its first option, ``none``), and
none answers ``unsure`` to either of the two questions ``AMBIGUOUS_SPONSOR``
actually reads, ``family_sponsor_status_code`` / ``family_sponsor_confirmed``.
Two walks DO answer ``unsure`` to a sponsor question —
``offshore/other/paid/sponsor_unsure`` on ``work_sponsor_confirmed`` and
``offshore/work/sponsor_unsure`` on ``sponsor_category`` — but neither is a
FAMILY sponsor fact, so what they raise is the generic ``NOT_CERTAIN``, the
two rows already counted above (council round 1, council/journal.jsonl: this
sentence used to say "a sponsor question" flatly and contradicted the
table 470 lines below it).
That zero is a property of THIS enumeration, never of production: every
real visitor with two purposes is held, and no walk here measures it.

The six ``ACTIVITY_BOUNDARY`` rewrites are the ones a derivation misses,
and one did: reasoning from "the generator answers every question with its
FIRST option" predicts 2 flagged walks, because the first option of every
question in ``ACTIVITY_BOUNDARY_DECIDABLE_ANSWERS`` is decidable. The
SCENARIO OVERRIDES are what break it — ``investment_vehicle`` answered
``merit``/``family``/``undecided`` (only ``pt_pma``/``property``/
``bank_deposit`` are decidable) and ``other_purpose`` answered ``medical``
(only ``transit`` is). Executed, not derived: 8.

WHAT THIS CENSUS STILL DOES NOT SEE:

1. **The enumeration is a chosen sample, not a cover.** Every question is
   answered with its FIRST option unless the scenario overrides it, only
   TWO of the 94 walks ever answer the literal ``unsure`` (the two
   ``NOT_CERTAIN`` rows of ``EXPECTED_DISCLOSED_REVIEW_FLAGS`` below — this
   sentence used to say "no walk ever answers ``unsure``", which stopped
   being true when PR-D3/PR-D4d added them and was caught by council round 2
   (council/journal.jsonl)), and
   the onshore arm is ONE neutral walk per category — its sub-branches
   (``onshore/second_home/property``, ``onshore/diaspora/STEPCHILD/...``)
   are deliberately not enumerated, as they never were for invest,
   retirement or family. Byte-for-byte reproducibility is proven; coverage
   of every reachable path is not claimed.

The corpus under ``gold_coverage/fixtures/walks/`` is DATA, generated by driving the
real ``computeNextNode``/``getCategoryQuestionIds``/``mapOracleFactsToApplicantFacts``
(first option answered at every question a scenario does not override, 121
stay-days), never hand-written:
each file carries the walk's ``asked`` question ids, the exact wire
``overrides`` that walk produced, and — when the walk raises any — the
``disclosed_review_flags`` the same mapper computed for it. The expectations
live HERE, in one reviewable table, so a wave PR that moves an outcome must
state which outcome it moved.

Regenerate the corpus with ``npm run visa-oracle:walk-corpus -w apps/mouth``
(``apps/mouth/scripts/visa-oracle/generate-walk-corpus.ts``, proved byte-for-byte
reproducible by ``walk-corpus-determinism.test.ts``): a PR that changes the
interview tree MUST regenerate it and update ``EXPECTED_OUTCOME`` /
``WALK_DEAD_END_ALLOWLIST`` / ``EXPECTED_DISCLOSED_REVIEW_FLAGS`` below in
that same PR.
"""

from __future__ import annotations

import copy
import functools
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine import gold_coverage_eval
from backend.scripts.visa_engine.compile_pack import load_rule_pack_payload, wrap_as_unsigned_pack
from backend.scripts.visa_engine.gold_coverage_eval import _evaluate
from backend.scripts.visa_engine.gold_replay_driver import (
    PACKS_DIR,
    _parse_utc,
    build_persona_request,
    select_highest_repository_pack,
)
from backend.services.visa_engine import ast as ast_module
from backend.services.visa_engine import compiler, evaluate_path, evaluator
from backend.services.visa_engine.api_models import VisaOracleEvaluateRequest
from backend.services.visa_engine.ast import KnownFact, UnknownFact
from backend.services.visa_engine.enums import (
    DecisionState,
    FactPath,
    RuleEffectType,
    TruthValue,
    UnknownReason,
    VisaProductStatus,
)
from backend.tests.services.visa_engine.gold_replay import _decision_actual
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

#: The sequence every per-walk pin below is read for. W-VO-Q (mission
#: SAETTA-VO3): the pins are kept PER SIGNED SEQUENCE, because the census has
#: to stay green on both sides of a signature — on main while seq-20 is the
#: highest signed pack, and in the PR that lands the next fold's signed
#: bundle (seq-22 today; seq-21 was signed but stopped before activation and
#: never entered this repo — see `fold_pack_seq22.py`), which changes no walk's
#: facts but does change what the engine answers. A signed sequence with no
#: pins fails `test_the_census_pins_the_signed_sequence` by name instead of
#: quietly grading against the previous one.
_SIGNED_SEQUENCE = int(_HIGHEST_SIGNED_PACK["payload"]["sequence"])


@dataclass(frozen=True)
class PackUnderTest:
    """A compiled pack and the instant the reachability guard grades it at."""

    compiled: Any
    as_of: datetime


def _signed_pack() -> PackUnderTest:
    """The default: the highest SIGNED pack, verified, at its own ``signed_at``."""

    _pack_path, compiled = gold_coverage_eval._verified_compiled_pack(_AS_OF)
    return PackUnderTest(compiled=compiled, as_of=_AS_OF)


def _candidate_source_pack_path() -> Path | None:
    """The highest-sequence UNSIGNED production source pack above the highest
    signed one, or ``None`` when every source pack on disk is already signed.

    W-VO-Q (mission SAETTA-VO3): the CANDIDATE mode of the reachability guard.
    A tree change that exists to make an unsigned pack's products reachable
    has to be proven against THAT pack before the owner signs it — the signed
    default above cannot see a rule that is not signed yet. Once the candidate
    is signed it stops being "above the signed one", this returns ``None``,
    and the candidate tests skip: the signed guard covers it from then on."""

    signed_sequence = int(_HIGHEST_SIGNED_PACK["payload"]["sequence"])
    above: list[tuple[int, Path]] = []
    for path in sorted(PACKS_DIR.glob("rulepack-prod-*.source.json")):
        sequence = int(json.loads(path.read_text(encoding="utf-8"))["sequence"])
        if sequence > signed_sequence:
            above.append((sequence, path))
    return max(above)[1] if above else None


@functools.lru_cache(maxsize=1)
def _candidate_pack() -> PackUnderTest | None:
    """The candidate compiled through ``wrap_as_unsigned_pack`` — a placeholder
    envelope, never a trust claim (the same path ``test_seq21_pack.py`` uses
    to exercise the real evaluator on an unsigned pack).

    Graded 12 hours after the LATEST ``valid_period.from`` among its rules, so
    every rule the candidate inserts is in force — evaluating a candidate at
    the INCUMBENT's ``signed_at`` reports "nothing moved" for rules that are
    not effective yet, the mistake the first seq-21 census made. For seq-21
    (every new rule valid from 2026-09-13T00:00Z since #6479) this is
    2026-09-13T12:00Z."""

    path = _candidate_source_pack_path()
    if path is None:
        return None
    payload = load_rule_pack_payload(path)
    compiled = compiler.build_compiled_pack(wrap_as_unsigned_pack(payload))
    latest = max(rule.valid_period.from_ for rule in payload.rules)
    return PackUnderTest(compiled=compiled, as_of=latest + timedelta(hours=12))


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
#:
#: W-VO-Q: on seq-21 the first row is CURED, not excused. The walk answers
#: `sponsor_category`'s first option (NONE), so the tree now asks it the
#: government-collaboration question (`el.e33b.government-collaboration`),
#: and its "yes" names E33B whatever the uncertified E23 sponsor answer is —
#: SUPPORTED_CANDIDATES [E33B], nothing left to ask. The row stays on seq-20,
#: which reads none of the ten facts.
_STILL_UNSURE_RETIREMENT_ROW: tuple[DeadEnd, ...] = (
    DeadEnd(
        fact="family.sponsor_confirmed",
        source_question="family_sponsor_confirmed",
        why_unaskable=QUESTION_NOT_IN_THIS_WALK,
    ),
)
WALK_DEAD_END_ALLOWLIST_BY_SEQUENCE: dict[int, dict[str, tuple[DeadEnd, ...]]] = {
    20: {
        "offshore/other/paid/sponsor_unsure": (
            DeadEnd(
                fact="work.indonesian_work_sponsor_confirmed",
                source_question="work_sponsor_confirmed",
                why_unaskable=ANSWER_NEVER_CERTIFIED,
            ),
        ),
        "offshore/retirement/undecided/age64/still_unsure": _STILL_UNSURE_RETIREMENT_ROW,
    },
    21: {"offshore/retirement/undecided/age64/still_unsure": _STILL_UNSURE_RETIREMENT_ROW},
    # E23V-DEFECT (mission seq-22): unchanged from seq-21 — the walk this
    # fold cures was never allowlisted (it dead-ended on NO_SUPPORTED_PATH,
    # an ANSWER, not a NEEDS_INPUT this table would need to excuse).
    22: {"offshore/retirement/undecided/age64/still_unsure": _STILL_UNSURE_RETIREMENT_ROW},
}
WALK_DEAD_END_ALLOWLIST: dict[str, tuple[DeadEnd, ...]] = WALK_DEAD_END_ALLOWLIST_BY_SEQUENCE.get(
    _SIGNED_SEQUENCE, {}
)


#: Products the highest signed pack gives a SUPPORT rule and NO interview
#: walk can name — the class `test_every_support_bearing_product_is_named_by_
#: some_walk` below exists to keep at zero. A row may only be a RULING; an
#: omission is a bug and gets a walk, not a row. Each row states the fact the
#: product's own rules need, and why the funnel may not collect it.
#:
#: Measured 2026-09-13 on rulepack-prod-020.signed.json: 29 products carry a
#: SUPPORT rule, 17 were named by some walk, and the 12 that were not are
#: this window's subject. Eleven of them needed no code at all — every fact
#: their rules read was already collected, and what kept them dark was the
#: corpus's own answering convention: its first-option default for choice
#: questions, and its ONE fixed synthetic identity for typed ones (a 25-year
#: -old, 121 stay-days, IDR 1,000,000,000 for every amount), which is what
#: hid A1/B1 (stay-day bounds), E28A (both capital bounds) and E31E (age).
#: The twelfth is below.
#: The excuse is STRUCTURED, not prose, on the first council round's finding
#: (council round 1 (council/journal.jsonl)): a row that only carried a
#: sentence would go on silencing this product even if a FUTURE pack gave it a
#: SUPPORT route that does not read the forbidden fact at all. Naming the fact
#: lets `test_every_ruled_unreachable_product_still_depends_on_its_forbidden_fact`
#: re-derive the excuse from the pack on every run.
@dataclass(frozen=True)
class RuledUnreachable:
    """One excused product: the fact its SUPPORT rules need, which the funnel
    is forbidden to collect, and the ruling that forbids collecting it."""

    forbidden_fact: str
    ruling: str


UNREACHABLE_BY_RULING: dict[str, RuledUnreachable] = {
    "BRIDGING": RuledUnreachable(
        forbidden_fact="intent.requested_product_code",
        ruling=(
            "All four BRIDGING SUPPORT rules (`el.bridging.destination-stated`, "
            "`.t3-window-manual`, `.overstay-shield-payment`, "
            "`.source-status-verify`) require `intent.requested_product_code` to "
            "be KNOWN — the permit the applicant wants to switch TO. "
            "`fact-mapper.ts` hard-codes that fact to UNKNOWN(NOT_ASKED), and the "
            "owner's D4 ruling quoted in `tree.ts` is explicit: the Oracle says "
            "the product, it never asks which visa the applicant wants. Asking it "
            "is the ONLY route to this product, so the row is a ruling and not an "
            "omission — verified 2026-09-13 by supplying the fact on an onshore "
            "OTHER-purpose walk whose `immigration.current_status_code` is "
            "outside `hf.bridging.from-visit-itk`'s visit-class list: the engine "
            "answers SUPPORTED_CANDIDATES [BRIDGING, C6]. BRIDGING is also one of "
            "the two products in this pack with `public_catalog: false` (the "
            "other, E30, the funnel already names), so surfacing it publicly is "
            "Zero's call twice over."
        ),
    ),
}

#: Per-walk outcome pin: state plus the candidate products, in rank order.
#: Candidates are pinned too — a pack edit that adds or drops a product for a
#: walk that already had an answer is exactly as much of a shift as a state
#: change, and this table is the only place either becomes visible.
#:
#: This literal is the seq-20 table; `EXPECTED_OUTCOME` (below it) is the one
#: for the signed sequence under test, built from it and the seq-21 changes.
_EXPECTED_OUTCOME_ON_SEQ20: dict[str, tuple[str, tuple[str, ...]]] = {
    "offshore/business": ("NO_SUPPORTED_PATH", ()),
    # W-VO-E: the business visitor who is NOT paid from inside Indonesia —
    # `el.d2-*`, the multiple-entry business visa. The walk above answers
    # `work_indonesia_compensation`'s first option (`yes`) and is excluded
    # on BUSINESS_LOCAL_COMPENSATION_NOT_ALLOWED, which is a correct answer
    # to a different question; D2 had no walk at all.
    "offshore/business/no_local_compensation": ("SUPPORTED_CANDIDATES", ("D2",)),
    # W-VO-Q item 7 (owner ruling 2026-09-14): the business explorer,
    # INVESTMENT purpose. The default walk answers the conversion question
    # `yes` (D12 excluded, the investor facts asked) and is decided by C2's
    # sponsor; the two offshore-application walks name D12 with and without a
    # sponsor; the explorer who converts onshore with no sponsor and no
    # investor route ends on the named cause `D12_NOT_CONVERTIBLE`, never on
    # a question.
    "offshore/business/exploring": ("SUPPORTED_CANDIDATES", ("C2",)),
    "offshore/business/exploring/offshore_application": ("SUPPORTED_CANDIDATES", ("C2", "D12")),
    "offshore/business/exploring/offshore_application/sponsor_no": (
        "SUPPORTED_CANDIDATES",
        ("D12",),
    ),
    "offshore/business/exploring/sponsor_no/no_route": ("NO_SUPPORTED_PATH", ()),
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
    # W-VO-E: the SAME walk with a minor's birth date — the only corpus walk
    # whose PUBLIC outcome is a hold, and deliberately so. The ENGINE names
    # C1 and E31E (`el.e31e-child-itas-support`, whose `derived.age_years <
    # 18` gate no adult walk can clear); `evaluate_path.
    # _apply_minor_privacy_hold` then empties the candidates of ANY known
    # minor, unconditionally, because the public contract has no
    # guardian-consent fact. That is Privacy Policy V1, a product control,
    # not engine incompleteness — and it is the reason the reachability
    # guard below reads the engine decision rather than this table.
    "offshore/family/PARENT/spNat=IT/minor": ("HUMAN_REVIEW_REQUIRED", ()),
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
    # W-VO-E: the investor applying from abroad with the capital figures
    # `el.e28a.investment` actually reads. `full_capital` differs from
    # `offshore_application` in exactly the two amounts (the rule's own
    # bounds), which is what separates D12 from the Investor KITAS itself.
    "offshore/invest/pt_pma/full_capital": (
        "SUPPORTED_CANDIDATES",
        ("C2", "D12", "E28A"),
    ),
    # W-VO-E: `hf.d12-onshore-conversion-excluded` is why D12 had no walk —
    # `wants_onshore_conversion`'s first option is `yes`, which excludes the
    # multiple-entry investment visa by regulation. Answering `no` is the
    # ordinary offshore applicant this product exists for.
    "offshore/invest/pt_pma/offshore_application": (
        "SUPPORTED_CANDIDATES",
        ("C2", "D12"),
    ),
    # PR-D4d (seq-21 corpus prep, unsigned — activation caveat in the PR
    # body): `el.e33c.world-figure-invitation` needs INVESTMENT purpose +
    # `sponsor.type eq GOVERNMENT`, so this is the `invest` walk that would
    # exercise it once seq-21 activates. Under the pack ACTUALLY signed
    # today (rulepack-prod-020, which reads no sponsor.type condition for
    # any INVESTMENT-purpose product), `sponsor.type` is a silent extra fact
    # and the walk answers exactly like its `pt_pma` sibling: C2.
    "offshore/invest/pt_pma/sponsor_government": ("SUPPORTED_CANDIDATES", ("C2",)),
    "offshore/invest/undecided": ("SUPPORTED_CANDIDATES", ("C2",)),
    # PR-D4c-2: the "I can't say yet" currency answer — the walk that used to
    # rest its zero-review-cost claim on a PR body, because the census could
    # not carry disclosure flags and so could only witness that the
    # ENGINE-level verdict does not move. It carries them now: this walk's own
    # fixture is pinned in `EXPECTED_DISCLOSED_REVIEW_FLAGS` below, and the
    # claim it proves is narrower than the PR body's — `still_unsure` costs no
    # NOT_CERTAIN flag (its literal is not `unsure`), but the walk raises
    # ACTIVITY_BOUNDARY anyway on `investment_vehicle = undecided`. Since PLAN
    # slice A1 (owner ruling 2026-09-13) ACTIVITY_BOUNDARY conditions rather
    # than holds, so at FUNNEL level this walk keeps C2 with a
    # DISCLOSED_ACTIVITY_BOUNDARY_CONDITION notice, not a hold. Neither amount
    # fact is ever populated
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
    # W-VO-E: the digital nomad the remote branch was built for —
    # `el.e33g.remote-work` plus `hf.e33g`'s local-ownership exclusion,
    # answered the way a genuinely offshore-paid remote worker answers them.
    # Three of the four facts had to move: `remote_clients` already defaults
    # to `foreign`, but `work_payer`, `remote_compensation` and
    # `remote_pt_pma` all default to `yes`, and each alone excludes the
    # product — which left the highest-demand public product named by no walk
    # in the corpus.
    "offshore/remote/foreign_only": ("SUPPORTED_CANDIDATES", ("E33G",)),
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
    # W-VO-E: `el.e30e-*`/`el.e30f-*` both read `sponsor.type`, which the
    # study branch has asked all along — the corpus only ever answered its
    # first option (NONE), so two student products were unreachable through
    # the corpus while being one click away in the interview.
    "offshore/study/education_sponsor": (
        "SUPPORTED_CANDIDATES",
        ("E30", "E30A", "E30E", "E30F"),
    ),
    # W-VO-E: E30B shares the student SUPPORT rule with E30/E30A but carries
    # its own `hf.e30b-level-band` HARD FILTER (VOCATIONAL/UNDERGRADUATE/
    # POSTGRADUATE only). `study_level`'s first option is PRIMARY, so E30B
    # was excluded on every study walk — and E30A drops out here for the
    # mirror reason, its own level band.
    "offshore/study/vocational/education_sponsor": (
        "SUPPORTED_CANDIDATES",
        ("E30", "E30B", "E30E", "E30F"),
    ),
    "offshore/tourism": ("SUPPORTED_CANDIDATES", ("C1",)),
    # W-VO-E: `el.d1-multi-entry-support`. `entry_pattern` is on the tourism
    # branch already; every walk answered SINGLE, its first option.
    "offshore/tourism/multiple_entry": ("SUPPORTED_CANDIDATES", ("C1", "D1")),
    # W-VO-E: `el.a1.tourism` — a visa-free nationality and a stay inside
    # the 30-day bound. The corpus default identity (IT, 121 days) clears
    # neither, so both visa-free arms were dark; `el.b1.tourism` rides the
    # same answers.
    "offshore/tourism/visa_free_30d": ("SUPPORTED_CANDIDATES", ("A1", "B1", "C1")),
    # W-VO-E: `el.b1.tourism` alone — Visa on Arrival's own 60-day bound,
    # with the corpus's default nationality.
    "offshore/tourism/voa_60d": ("SUPPORTED_CANDIDATES", ("B1", "C1")),
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
    # W-VO-Q (mission SAETTA-VO3): thirteen walks — the `capital_market`
    # vehicle's default walk and twelve over the ten seq-21 qualification
    # questions. On the pack signed TODAY (seq-20) none of the ten facts is
    # read by any rule, so every one of them answers exactly what its
    # branch's default walk answers — E23 on `work`, C2 on `invest`. What
    # they change is the CANDIDATE pack's answer, pinned per walk in
    # `test_seq21_pack.py`'s `EXPECTED_SEQ21_GAINS` and bound here by
    # `test_every_support_bearing_product_of_the_candidate_pack_is_named_by_some_walk`.
    "offshore/invest/pt_pma/below_published_threshold": ("SUPPORTED_CANDIDATES", ("C2",)),
    "offshore/invest/pt_pma/company_only": ("SUPPORTED_CANDIDATES", ("C2",)),
    "offshore/invest/pt_pma/foreign_branch_only": ("SUPPORTED_CANDIDATES", ("C2",)),
    "offshore/invest/pt_pma/ikn_subsidiary": ("SUPPORTED_CANDIDATES", ("C2",)),
    "offshore/invest/pt_pma/no_route": ("SUPPORTED_CANDIDATES", ("C2",)),
    "offshore/invest/pt_pma/sponsor_government/not_world_figure": (
        "SUPPORTED_CANDIDATES",
        ("C2",),
    ),
    "offshore/invest/capital_market": ("SUPPORTED_CANDIDATES", ("C2",)),
    "offshore/invest/capital_market/capital_market_only": ("SUPPORTED_CANDIDATES", ("C2",)),
    "offshore/work/no_government_collaboration": ("SUPPORTED_CANDIDATES", ("E23",)),
    "offshore/work/sponsor_government/invitation_only": ("SUPPORTED_CANDIDATES", ("E23",)),
    "offshore/work/sponsor_government/neither": ("SUPPORTED_CANDIDATES", ("E23",)),
    "offshore/work/sponsor_government/trade_office_only": ("SUPPORTED_CANDIDATES", ("E23",)),
    # E23V-DEFECT (seq-22): the trade-office applicant whose employer is
    # genuinely NOT an Indonesian entity — el.e23-employment-support already
    # requires `work.employer_is_indonesian_entity == true` on seq-20, so
    # this walk dead-ends on the generic cause. Measured
    # (`_decide` against `_signed_pack()`): NO_SUPPORTED_PATH, candidates
    # (), reason OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES.
    "offshore/work/sponsor_government/trade_office_only/employer_no": (
        "NO_SUPPORTED_PATH",
        (),
    ),
    "offshore/work/sponsor_individual/not_diplomatic": ("SUPPORTED_CANDIDATES", ("E23",)),
}

#: W-VO-Q (mission SAETTA-VO3): the walks whose outcome seq-21 changes, and
#: nothing else — every walk absent here answers on seq-21 exactly what it
#: answers on seq-20. Measured 2026-09-14 with the owner-signed
#: `rulepack-prod-021.signed.json` (payload fda8c312…98c7) as the highest
#: signed pack, at its own `signed_at`, and again against the unsigned
#: candidate source through `test_every_walk_ends_in_its_pinned_outcome_on_
#: the_candidate_pack` (identical payload, so identical answers).
#:
#: Every change ADDS one of the nine products seq-21 makes supportable, on
#: the answer that product's own rule reads (FACTS-FOR-THE-TREE.md), and no
#: walk loses a candidate. The corpus answers each new yes/no question with
#: its first option, "yes", which is why the default `work`, paid `other`
#: and INVESTMENT-purpose walks gain E33B or E28B/D/F; the one-product walks
#: and the honest "no" walks are the scenarios in `generate-walk-corpus.ts`.
#: One STATE moves: `offshore/other/paid/sponsor_unsure` was NEEDS_INPUT on
#: the uncertified E23 sponsor answer and is now answered by E33B, whose
#: government-collaboration question the walk's NONE sponsor now asks.
_SEQ21_OUTCOME_CHANGES: dict[str, tuple[str, tuple[str, ...]]] = {
    "offshore/business/exploring": ("SUPPORTED_CANDIDATES", ("C2", "E28B", "E28D", "E28F")),
    "offshore/invest/capital_market": ("SUPPORTED_CANDIDATES", ("C2", "E28B", "E28D", "E28F")),
    "offshore/invest/capital_market/capital_market_only": ("SUPPORTED_CANDIDATES", ("C2", "E28C")),
    "offshore/invest/family": ("SUPPORTED_CANDIDATES", ("C2", "E28B", "E28D", "E28F")),
    "offshore/invest/merit": ("SUPPORTED_CANDIDATES", ("C2", "E28B", "E28D", "E28F")),
    "offshore/invest/merit/currency_usd": ("SUPPORTED_CANDIDATES", ("C2", "E28B", "E28D", "E28F")),
    "offshore/invest/pt_pma": ("SUPPORTED_CANDIDATES", ("C2", "E28B", "E28D", "E28F")),
    "offshore/invest/pt_pma/company_only": ("SUPPORTED_CANDIDATES", ("C2", "E28B")),
    "offshore/invest/pt_pma/foreign_branch_only": ("SUPPORTED_CANDIDATES", ("C2", "E28D")),
    "offshore/invest/pt_pma/full_capital": (
        "SUPPORTED_CANDIDATES",
        ("C2", "D12", "E28A", "E28B", "E28D", "E28F"),
    ),
    "offshore/invest/pt_pma/ikn_subsidiary": ("SUPPORTED_CANDIDATES", ("C2", "E28B", "E28F")),
    "offshore/invest/pt_pma/offshore_application": (
        "SUPPORTED_CANDIDATES",
        ("C2", "D12", "E28B", "E28D", "E28F"),
    ),
    "offshore/invest/pt_pma/sponsor_government": (
        "SUPPORTED_CANDIDATES",
        ("C2", "E28B", "E28D", "E28F", "E33C"),
    ),
    "offshore/invest/pt_pma/sponsor_government/not_world_figure": (
        "SUPPORTED_CANDIDATES",
        ("C2", "E28B", "E28D", "E28F"),
    ),
    "offshore/invest/undecided": ("SUPPORTED_CANDIDATES", ("C2", "E28B", "E28D", "E28F")),
    "offshore/invest/undecided/currency_still_unsure": (
        "SUPPORTED_CANDIDATES",
        ("C2", "E28B", "E28D", "E28F"),
    ),
    "offshore/other": ("SUPPORTED_CANDIDATES", ("E23", "E33B")),
    "offshore/other/paid/sponsor_government": ("SUPPORTED_CANDIDATES", ("E23", "E23V", "E33A")),
    "offshore/other/paid/sponsor_unsure": ("SUPPORTED_CANDIDATES", ("E33B",)),
    "offshore/work": ("SUPPORTED_CANDIDATES", ("E23", "E33B")),
    "offshore/work/sponsor_government": ("SUPPORTED_CANDIDATES", ("E23", "E23V", "E33A")),
    "offshore/work/sponsor_government/invitation_only": ("SUPPORTED_CANDIDATES", ("E23", "E33A")),
    "offshore/work/sponsor_government/trade_office_only": ("SUPPORTED_CANDIDATES", ("E23", "E23V")),
    "offshore/work/sponsor_individual": ("SUPPORTED_CANDIDATES", ("E23", "E23U")),
    "onshore/invest": ("SUPPORTED_CANDIDATES", ("C2", "E28B", "E28D", "E28F")),
    "onshore/other": ("SUPPORTED_CANDIDATES", ("E23", "E33B")),
    "onshore/work": ("SUPPORTED_CANDIDATES", ("E23", "E33B")),
}

#: E23V-DEFECT (mission seq-22): seq-22's changes over seq-20, identical to
#: `_SEQ21_OUTCOME_CHANGES` with three additions.
#:
#: 1. The walk seq-21 added AFTER it (mission seq-22, corpus 111 -> 112) and
#:    never itself moved on seq-21. `fold_pack_seq22.py` scopes
#:    `hf.employment-without-indonesian-sponsor` to `("E23", "E33B")` only
#:    (E23V removed, DEFECT 1 cured), so this trade-office applicant's
#:    honest `work.employer_is_indonesian_entity == false` no longer
#:    excludes E23V — the walk answers instead of dead-ending.
#: 2. and 3. D23 "OPTION B-STUDIO" (2026-09-16, DEFECT 3's redesign): the two
#:    `offshore/invest/{property,bank_deposit}/below_threshold` walks move
#:    from `NO_SUPPORTED_PATH` to `HUMAN_REVIEW_REQUIRED`, held by
#:    `review.e33.below-threshold-studio` (`SECOND_HOME_BELOW_THRESHOLD_
#:    STUDIO`) — each walk's own DECLARED figure (property 500_000 <
#:    1_000_000; deposit 50_000 < 130_000) is below its own threshold, and
#:    the twin basis's SYNTHESISED `known(0)` conjunct is along for the ride,
#:    never the cause (see `fold_pack_seq22.py`'s DEFECT 3). Neither walk had
#:    a candidate to lose. Measured against `rulepack-prod-022.source.json`.
_SEQ22_OUTCOME_CHANGES: dict[str, tuple[str, tuple[str, ...]]] = {
    **_SEQ21_OUTCOME_CHANGES,
    "offshore/work/sponsor_government/trade_office_only/employer_no": (
        "SUPPORTED_CANDIDATES",
        ("E23V",),
    ),
    "offshore/invest/property/below_threshold": ("HUMAN_REVIEW_REQUIRED", ()),
    "offshore/invest/bank_deposit/below_threshold": ("HUMAN_REVIEW_REQUIRED", ()),
}

EXPECTED_OUTCOME_BY_SEQUENCE: dict[int, dict[str, tuple[str, tuple[str, ...]]]] = {
    20: _EXPECTED_OUTCOME_ON_SEQ20,
    21: {**_EXPECTED_OUTCOME_ON_SEQ20, **_SEQ21_OUTCOME_CHANGES},
    22: {**_EXPECTED_OUTCOME_ON_SEQ20, **_SEQ22_OUTCOME_CHANGES},
}
EXPECTED_OUTCOME: dict[str, tuple[str, tuple[str, ...]]] = EXPECTED_OUTCOME_BY_SEQUENCE.get(
    _SIGNED_SEQUENCE, {}
)

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
#: W-VO-Q: one on seq-21, where the E23 sponsor row is cured (see
#: `WALK_DEAD_END_ALLOWLIST_BY_SEQUENCE`). E23V-DEFECT (mission seq-22): the
#: employer_no walk this fold cures was never a dead end on seq-21 either
#: (it was NO_SUPPORTED_PATH, not NEEDS_INPUT), so it drops out of neither
#: table — seq-22 reads identically to seq-21 here.
EXPECTED_DEAD_END_FACT_CENSUS_BY_SEQUENCE: dict[int, dict[str, int]] = {
    20: {"work.indonesian_work_sponsor_confirmed": 1, "family.sponsor_confirmed": 1},
    21: {"family.sponsor_confirmed": 1},
    22: {"family.sponsor_confirmed": 1},
}
EXPECTED_DEAD_END_FACT_CENSUS: dict[str, int] = EXPECTED_DEAD_END_FACT_CENSUS_BY_SEQUENCE.get(
    _SIGNED_SEQUENCE, {}
)

#: Which walks raise which disclosure flags — the OTHER half of the wire
#: request, carried by the corpus since 2026-09-13 (W-VO-H schema half) and
#: pinned here so the layer cannot move without a red.
#:
#: Read the reach of that claim exactly (council round 2, council/journal.jsonl):
#: this table is compared against the COMMITTED FIXTURES, never re-derived from
#: `mapDisclosedReviewFlags`. A mapper regression that stops raising a flag
#: therefore goes red in the FRONTEND lane — `walk-corpus-determinism.test.ts`,
#: which regenerates the corpus and compares bytes — and only reaches this
#: table once someone commits the regenerated fixture. Same shape as
#: `overrides`, which this file has always read the same way.
#:
#: A walk ABSENT from this table must carry no flag at all, and a walk present
#: must carry exactly these: `test_the_corpus_carries_the_disclosure_flag_layer`
#: compares the table against the fixtures in BOTH directions. That is what
#: keeps the fixtures' omit-when-empty encoding honest — a fixture without the
#: key means the empty tuple (mirroring `api_models.py`'s own default), and it
#: is this table, not the absence, that says so.
#:
#: Every row is produced by `mapDisclosedReviewFlags` (fact-mapper.ts) from the
#: walk's own answers, never chosen here:
#:   - ACTIVITY_BOUNDARY on 6 walks: `investment_vehicle` answered `merit` /
#:     `family` / `undecided` (the table in fact-mapper.ts lists only `pt_pma` /
#:     `property` / `bank_deposit` / `capital_market` as answers the pack
#:     decides), and
#:     `other_purpose` answered `medical` (only `transit` is decidable).
#:   - NOT_CERTAIN on 2 walks: the two scenarios that answer a sponsor question
#:     with the literal string `unsure`. The `still_unsure` walks deliberately
#:     use a DIFFERENT literal and therefore cost zero NOT_CERTAIN holds —
#:     which is ALL they cost zero of: `offshore/invest/undecided/
#:     currency_still_unsure` is held anyway, by ACTIVITY_BOUNDARY on its
#:     `investment_vehicle = undecided` answer. Both halves are now MEASURED by
#:     this table rather than asserted in a PR body.
EXPECTED_DISCLOSED_REVIEW_FLAGS: dict[str, tuple[str, ...]] = {
    "offshore/invest/family": ("ACTIVITY_BOUNDARY",),
    "offshore/invest/merit": ("ACTIVITY_BOUNDARY",),
    "offshore/invest/merit/currency_usd": ("ACTIVITY_BOUNDARY",),
    "offshore/invest/undecided": ("ACTIVITY_BOUNDARY",),
    "offshore/invest/undecided/currency_still_unsure": ("ACTIVITY_BOUNDARY",),
    "offshore/other/no_paid_activity/medical": ("ACTIVITY_BOUNDARY",),
    "offshore/other/paid/sponsor_unsure": ("NOT_CERTAIN",),
    "offshore/work/sponsor_unsure": ("NOT_CERTAIN",),
}

#: The walks held by a PUBLIC adapter that is not the disclosure layer — one,
#: and it is the minor-privacy control (`evaluate_path._apply_minor_privacy_
#: hold`, Privacy Policy V1: the public contract has no guardian-consent fact,
#: so a known minor's candidates are emptied unconditionally). W-VO-E's minor
#: walk is the first corpus walk to exercise it.
#:
#: Its own table because the two causes must not be summed: a flag DELETES a
#: proven verdict and is the subject of `EXPECTED_DISCLOSED_REVIEW_FLAGS`,
#: while this hold fires on `derived.is_minor` alone, on BOTH censuses, with
#: or without flags. Counting them together would let a new flag-driven hold
#: hide behind the privacy one, or the reverse.
PRIVACY_HELD_WALKS: set[str] = {"offshore/family/PARENT/spNat=IT/minor"}

#: Walks the highest signed pack ITSELF holds — a `REQUIRE_REVIEW` rule in the
#: pack, so neither a disclosure flag nor the minor-privacy adapter. Empty
#: through seq-21. seq-22 (D23 "OPTION B-STUDIO", `review.e33.below-threshold-
#: studio`, see `_SEQ22_OUTCOME_CHANGES`) routes the two below-threshold
#: Second Home walks to the Studio with the one named reason
#: `SECOND_HOME_BELOW_THRESHOLD_STUDIO`. Its own per-sequence table, NAMED
#: like `PRIVACY_HELD_WALKS` rather than counted, for the same reason: a
#: third engine hold, a different walk holding, or one of these two held for
#: another reason must still go red. Landing the signed seq-22 bundle
#: (SAETTA-20260916) moved this pin; no walk's facts moved.
STUDIO_HELD_WALKS_BY_SEQUENCE: dict[int, frozenset[str]] = {
    20: frozenset(),
    21: frozenset(),
    22: frozenset(
        {
            "offshore/invest/bank_deposit/below_threshold",
            "offshore/invest/property/below_threshold",
        }
    ),
}
STUDIO_HELD_WALKS: frozenset[str] = STUDIO_HELD_WALKS_BY_SEQUENCE.get(_SIGNED_SEQUENCE, frozenset())
STUDIO_REVIEW_REASON = "SECOND_HOME_BELOW_THRESHOLD_STUDIO"

#: The FUNNEL-level state census, DERIVED from the two tables above rather
#: than pinned as a third one — and the derivation is itself the claim under
#: test. Since PLAN VISA-ORACLE-DW-20260919 slice A1 (owner ruling
#: 2026-09-13), `_apply_disclosed_review_flags` is monotone but no longer
#: unconditional: only a flag in `evaluate_path.HOLDING_DISCLOSED_FLAGS`
#: (`CRIMINAL_RECORD`, today) rewrites the decision to a hold — every other
#: flag becomes a named `notices` condition and keeps the pack's own verdict.
#: This corpus raises only `ACTIVITY_BOUNDARY` and `NOT_CERTAIN`, neither
#: holding, so the FUNNEL census below collapses to the ENGINE census
#: exactly: the 8 flagged walks return to their engine state. If that stops
#: being true — a flag starts holding, or a new corpus walk raises
#: `CRIMINAL_RECORD` — `test_the_flagged_census_is_the_funnel_the_applicant_
#: meets` goes red without anyone having to re-pin a number.
#:
#: Re-measured 2026-09-19 (A1, signed seq-22, 111-walk corpus): 94
#: SUPPORTED_CANDIDATES / 14 NO_SUPPORTED_PATH / 1 NEEDS_INPUT / 3
#: HUMAN_REVIEW_REQUIRED on BOTH the ENGINE and the FUNNEL side — FUNNEL
#: HUMAN_REVIEW_REQUIRED moved 11 -> 3 (PRIVACY_HELD_WALKS + STUDIO_HELD_
#: WALKS only; the pre-A1 count also folded in the corpus's 8
#: ACTIVITY_BOUNDARY/NOT_CERTAIN holds, which A1 releases). Before A1: 85 /
#: 16 / 1 / 9 ENGINE, 77 / 16 / 1 / 17 FUNNEL (W-VO-Q's 111-walk corpus,
#: measured 2026-09-14).
_HOLDING_DISCLOSED_FLAG_NAMES: frozenset[str] = frozenset(
    flag.value for flag in evaluate_path.HOLDING_DISCLOSED_FLAGS
)
EXPECTED_FLAGGED_STATE_CENSUS: dict[str, int] = dict(
    Counter(
        "HUMAN_REVIEW_REQUIRED"
        if set(EXPECTED_DISCLOSED_REVIEW_FLAGS.get(label, ())) & _HOLDING_DISCLOSED_FLAG_NAMES
        else state
        for label, (state, _candidates) in EXPECTED_OUTCOME.items()
    )
)

#: The condition reason code `_apply_disclosed_review_flags` emits per
#: NON-holding flag (`_DISCLOSED_CONDITION_REASON_CODES`, evaluate_path.py,
#: PLAN slice A1) — restated here so the census names the CAUSE and not just
#: the count. Checked against `notice_codes`, not `review_reason_codes`:
#: these ten flags no longer force a review, they name a kept candidate's
#: condition. Only the flags this corpus actually raises are listed; a flag
#: that starts firing without a row here fails
#: `test_every_disclosure_flag_reports_the_walks_it_rewrites` loudly rather
#: than being silently summed into the total. Empty for any flag this corpus
#: raises that HOLDS instead (none today — see EXPECTED_DISCLOSED_REVIEW_FLAGS).
EXPECTED_CONDITION_REASON_FOR_FLAG: dict[str, str] = {
    "ACTIVITY_BOUNDARY": "DISCLOSED_ACTIVITY_BOUNDARY_CONDITION",
    "NOT_CERTAIN": "DISCLOSED_UNCERTAINTY_CONDITION",
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


def _walk_flags(spec: dict[str, Any]) -> tuple[str, ...]:
    """The disclosure flags one fixture carries, as a SET in tuple clothing.

    Order is not meaningful and is not asserted anywhere: both
    ``mapDisclosedReviewFlags`` (fact-mapper.ts) and
    ``VisaOracleEvaluateRequest``'s own ``_canonical_review_flags`` validator
    sort the list, and ``_flag_table_violations`` compares sorted tuples.

    An absent key is the EMPTY tuple and nothing else — the same default
    ``api_models.py::VisaOracleEvaluateRequest`` gives the field on the wire, so
    a fixture without it encodes a walk that raises nothing, not a walk whose
    flags are unknown. ``EXPECTED_DISCLOSED_REVIEW_FLAGS`` pins which walks may
    be in which group, so the default can never quietly absorb a lost flag.
    """

    return tuple(str(flag) for flag in spec.get("disclosed_review_flags", ()))


def _evaluate_walks_with_flags(walks: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The FUNNEL-level census: every walk replayed with the flags its own
    fixture carries, through the same ``_evaluate`` path as above.

    This is the half the applicant lives in. ``_evaluate`` validates the flags
    through ``VisaOracleEvaluateRequest`` before they reach
    ``apply_public_policy_adapters``, so a fixture carrying a name the engine
    does not know is a ValidationError here, never an ignored string.
    """

    return {
        label: _evaluate(
            spec["overrides"],
            label,
            as_of=_AS_OF,
            disclosed_review_flags=_walk_flags(spec),
        )["actual"]
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


def _decide(
    overrides: dict[str, Any], label: str, pack: PackUnderTest | None = None
) -> tuple[Any, Any, Any]:
    """``(raw_decision, compiled, request)``.

    ``_evaluate`` returns the flattened ``actual`` view (codes only), which
    cannot witness ``rule_ids``/``source_refs``. This reuses that module's own
    verified-pack loader and identity provider so the two never diverge on
    which pack, or which instant, is under test.
    """

    pack = _signed_pack() if pack is None else pack
    compiled = pack.compiled
    persona = Persona(
        id=0, label=label, overrides=overrides, expected_state=DecisionState.NEEDS_INPUT
    )
    request = build_persona_request(persona)
    decision = evaluator.evaluate(
        request.applicant_facts(),
        compiled,
        effective_at=pack.as_of,
        observed_at=pack.as_of,
        identity_provider=gold_coverage_eval._offline_identity_provider,
    )
    return decision, compiled, request


def _engine_decision(
    overrides: dict[str, Any], label: str, pack: PackUnderTest | None = None
) -> Any:
    """The RAW ``Decision`` — ``evaluator.evaluate``, no public shaping."""

    decision, _compiled, _request = _decide(overrides, label, pack)
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


def _flag_table_violations(
    walks: dict[str, dict[str, Any]],
    expected: dict[str, tuple[str, ...]] | None = None,
) -> list[str]:
    """The disclosure-flag table, both ways — the shape guard family #3 asks
    for: a pin that only catches a MISSING flag is an UNDER-match, and one
    that only catches an EXTRA flag is an OVER-match.

    A walk carrying flags must be pinned with exactly those flags, and a
    pinned walk that stopped carrying them is a STALE row the curing PR must
    delete — otherwise the table would outlive the layer it describes and go
    on claiming a hold nobody suffers.
    """

    pins = EXPECTED_DISCLOSED_REVIEW_FLAGS if expected is None else expected
    violations: list[str] = []
    for label in sorted(walks):
        carried = _walk_flags(walks[label])
        pinned = pins.get(label, ())
        if tuple(sorted(carried)) != tuple(sorted(pinned)):
            violations.append(
                f"{label}: fixture carries {list(carried)}, table pins {list(pinned)}"
            )
    for label in sorted(set(pins) - set(walks)):
        violations.append(f"{label}: pinned for flags but absent from the corpus")
    return violations


def _scoped_flag_table(*labels: str) -> dict[str, tuple[str, ...]]:
    """``EXPECTED_DISCLOSED_REVIEW_FLAGS`` restricted to ``labels`` — see
    ``_scoped_allowlist`` for why a single-walk assertion must be graded
    against a scoped table and never against the whole one."""

    return {
        label: EXPECTED_DISCLOSED_REVIEW_FLAGS[label]
        for label in labels
        if label in EXPECTED_DISCLOSED_REVIEW_FLAGS
    }


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


def _support_rules_by_product(pack: PackUnderTest | None = None) -> dict[str, tuple[Any, ...]]:
    """``product_code -> the compiled SUPPORT rules that can fire for it``,
    read from the COMPILED highest signed pack at ``_AS_OF``.

    Read from the pack and never from a list in this file on purpose: the
    day a new pack is signed, this set moves by itself and the guard below
    starts demanding a walk for whatever the pack just made supportable.
    A hand-kept list would have to be remembered, and the gap this guard
    exists to close is precisely the one nobody remembered to look for.

    Compiled and effective-filtered rather than read off the raw JSON, on
    the first council round's finding (council round 1, 2026-09-13
    (council/journal.jsonl)). Scanning ``product_version_ids`` in the
    payload gets BOTH directions wrong the moment a pack stops looking like
    today's:

    * a GLOBAL-scope SUPPORT rule carries ``product_version_ids: null`` and
      applies to EVERY product (``compiler.rules_for``), so a payload scan
      would miss it and the guard would stay green over the exact class it
      exists to catch. seq-20 has 6 GLOBAL rules and none of them is a
      SUPPORT — the false green is latent, not present.
    * a payload scan also counts rules and products the evaluator itself
      would skip at ``_AS_OF`` — a rule outside its ``valid_period``, a
      product that is not ACTIVE or outside its own period — which is a
      false RED: the guard would demand a walk naming a product the engine
      cannot emit. Every product in seq-20 is ACTIVE with an open period, so
      this half is latent too.

    Mirroring ``evaluator.evaluate``'s own product selection and
    ``CompiledRulePack.rules_for`` keeps the guard's universe equal to the
    engine's by construction instead of by coincidence.
    """

    pack = _signed_pack() if pack is None else pack
    compiled = pack.compiled
    by_product: dict[str, tuple[Any, ...]] = {}
    for compiled_product in compiled.products:
        if compiled_product.product.status is not VisaProductStatus.ACTIVE:
            continue
        if not evaluator._period_contains(compiled_product.product.valid_period, pack.as_of):
            continue
        support = tuple(
            rule
            for rule in compiled.rules_for(compiled_product, effective_at=pack.as_of)
            # `==`, not `is`: `RuleEffect.type` is the plain string
            # discriminator, and `RuleEffectType` is a `str` Enum, so equality
            # holds for both shapes while identity holds for neither today.
            if rule.effect.type == RuleEffectType.SUPPORT
        )
        if support:
            by_product[compiled_product.product_code] = support
    return by_product


def _support_bearing_product_codes(pack: PackUnderTest | None = None) -> set[str]:
    """The product codes ``_support_rules_by_product`` finds a SUPPORT rule for."""

    return set(_support_rules_by_product(pack))


def _engine_named_products(
    walks: dict[str, dict[str, Any]],
    pack: PackUnderTest | None = None,
) -> dict[str, tuple[str, ...]]:
    """``product_code -> the walks whose ENGINE decision names it``.

    The ENGINE decision, not ``EXPECTED_OUTCOME``'s public one, because the
    question this answers is "can an interview produce facts under which the
    pack supports this product" — a public policy adapter that later abstains
    (the minor privacy hold) is a different layer with a different owner, and
    grading reachability through it would report a product as unreachable
    when the interview reaches it perfectly well.
    """

    named: dict[str, list[str]] = {}
    for label, spec in sorted(walks.items()):
        for candidate in _engine_decision(spec["overrides"], label, pack).candidates:
            named.setdefault(candidate.product_code, []).append(label)
    return {code: tuple(labels) for code, labels in sorted(named.items())}


def _funnel_named_products(
    walks: dict[str, dict[str, Any]],
    pack: PackUnderTest | None = None,
) -> dict[str, tuple[str, ...]]:
    """``product_code -> the walks whose FUNNEL decision names it``.

    The engine decision passed through ``apply_public_policy_adapters`` with
    the disclosure flags the walk's own fixture carries — what the applicant
    is shown. The flagged request is rebuilt field by field exactly as
    ``gold_coverage_eval._evaluate`` rebuilds it (same field-set tripwire), so
    this and the FUNNEL census cannot disagree on what a flag does; unlike
    ``_evaluate`` it takes the pack under test, which is what lets the
    candidate mode ask the applicant-level question at all.
    """

    named: dict[str, list[str]] = {}
    for label, spec in sorted(walks.items()):
        decision, compiled, request = _decide(spec["overrides"], label, pack)
        flags = _walk_flags(spec)
        if flags:
            assert (
                set(VisaOracleEvaluateRequest.model_fields)
                == gold_coverage_eval._REBUILT_REQUEST_FIELDS
            )
            request = VisaOracleEvaluateRequest(
                schema_version=request.schema_version,
                assessment_id=request.assessment_id,
                collected_at=request.collected_at,
                facts=request.facts,
                disclosed_review_flags=flags,  # type: ignore[arg-type]
            )
        public = evaluate_path.apply_public_policy_adapters(
            decision,
            request.applicant_facts(),
            compiled,
            disclosed_review_flags=request.effective_review_flags(),
        )
        for candidate in public.candidates:
            named.setdefault(candidate.product_code, []).append(label)
    return {code: tuple(labels) for code, labels in sorted(named.items())}


def _unreached_support_products(
    named: dict[str, tuple[str, ...]],
    *,
    excused: dict[str, RuledUnreachable] | None = None,
    pack: PackUnderTest | None = None,
) -> list[str]:
    """SUPPORT-bearing products no walk names, minus the ruling rows."""

    excused = UNREACHABLE_BY_RULING if excused is None else excused
    return sorted(_support_bearing_product_codes(pack) - set(named) - set(excused))


def _stale_ruling_rows(
    named: dict[str, tuple[str, ...]],
    *,
    excused: dict[str, RuledUnreachable] | None = None,
) -> list[str]:
    """Ruling rows whose product a walk DOES name — cure the row away."""

    excused = UNREACHABLE_BY_RULING if excused is None else excused
    return sorted(set(excused) & set(named))


def _proves_it_cannot_fire_without(condition: Any, fact: str) -> bool:
    """Whether ``condition`` is PROVABLY unable to evaluate TRUE while ``fact``
    is UNKNOWN.

    One-directional on purpose, and the name says which direction: ``True``
    means proven, ``False`` means NOT PROVEN by this analysis — never "proven
    reachable". Council round 3 (council/journal.jsonl) rejected the earlier name
    (``_condition_cannot_fire_without``) for exactly that confusion: it read
    as a decision procedure, and the caller then turned "my conservative
    analysis could not prove it" into "this route is reachable, delete the
    ruling". The conservative direction is the safe one — an unproven row
    demands re-justification, not a silent pass — but it must not be reported
    as a proof of the opposite.

    Council round 2 (council/journal.jsonl) showed
    why membership in ``CompiledRule.required_facts`` is not this property:
    that set is SYNTACTIC — every fact the AST mentions — so a rule shaped
    ``any(eq(requested_product_code, "BRIDGING"), intersects(purposes, OTHER))``
    lists the forbidden fact and still evaluates TRUE with the fact UNKNOWN.
    The seat reproduced exactly that. A ruling row justified by such a rule
    would be an excuse for a route the funnel can already walk.

    So the test is structural and sound rather than syntactic: under Kleene
    semantics (``ast.py``) an ``all`` node is FALSE if any child is FALSE and
    UNKNOWN if any child is UNKNOWN, so it can never be TRUE when a child is
    not TRUE. A scalar/set leaf on an UNKNOWN fact is UNKNOWN; ``known(fact)``
    on an UNKNOWN fact is FALSE. Either way, a leaf reading the fact anywhere
    on the AND-spine keeps the whole condition away from TRUE.

    ``unknown(fact)`` is the one leaf that is TRUE *because* the fact is
    missing, and is excluded explicitly — a rule that fires ON the absence is
    the opposite of a rule that depends on the presence. Its negation,
    ``not(unknown(fact))``, is accepted: it is ``known(fact)`` spelled the long
    way, FALSE whenever the fact is missing (round 3's own counterexample).
    ``any`` is accepted only when EVERY branch is itself proven — a
    disjunction cannot be TRUE unless some branch is, so if no branch can be,
    neither can it. Anything else returns False, which is not a claim that the
    rule fires without the fact, only that this analysis did not prove it did
    not.
    """

    op = getattr(condition, "op", None)
    if op == "all":
        return any(_proves_it_cannot_fire_without(arg, fact) for arg in condition.args)
    if op == "any":
        return bool(condition.args) and all(
            _proves_it_cannot_fire_without(arg, fact) for arg in condition.args
        )
    if op == "not":
        inner = condition.arg
        return (
            getattr(inner, "op", None) == "unknown"
            and getattr(getattr(inner, "fact", None), "value", None) == fact
        )
    if op == "unknown":
        return False
    referenced = getattr(condition, "fact", None)
    if referenced is None:
        return False
    return getattr(referenced, "value", referenced) == fact


def _ruling_rows_without_a_proven_dependency(
    *,
    excused: dict[str, RuledUnreachable] | None = None,
    pack: PackUnderTest | None = None,
) -> list[str]:
    """Ruling rows carrying a SUPPORT route whose dependency on the forbidden
    fact this analysis cannot prove — either because the route genuinely no
    longer needs the fact, or because it is written in a shape
    ``_proves_it_cannot_fire_without`` does not reason about.

    Both readings demand the same gesture (re-justify the row against the new
    pack, or give the product a walk and delete the row), which is why they
    share a return value — but they are NOT the same claim, and the assertion
    that consumes this says so. This is the half a "does a walk name it?"
    check cannot see: the product is still named by no walk, so the guard and
    the staleness mirror both stay green, while the reason the row was granted
    may have evaporated.
    """

    excused = UNREACHABLE_BY_RULING if excused is None else excused
    support_rules = _support_rules_by_product(pack)
    offenders: list[str] = []
    for code, row in excused.items():
        rules = support_rules.get(code, ())
        if any(not _proves_it_cannot_fire_without(rule.when, row.forbidden_fact) for rule in rules):
            offenders.append(code)
    return sorted(offenders)


@pytest.fixture(scope="module")
def walks() -> dict[str, dict[str, Any]]:
    return _load_walks()


@pytest.fixture(scope="module")
def outcomes(walks: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return _evaluate_walks(walks)


@pytest.fixture(scope="module")
def flagged_outcomes(walks: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return _evaluate_walks_with_flags(walks)


@pytest.fixture(scope="module")
def engine_named(walks: dict[str, dict[str, Any]]) -> dict[str, tuple[str, ...]]:
    return _engine_named_products(walks)


@pytest.fixture(scope="module")
def funnel_named(walks: dict[str, dict[str, Any]]) -> dict[str, tuple[str, ...]]:
    return _funnel_named_products(walks)


@pytest.fixture(scope="module")
def candidate_pack() -> PackUnderTest:
    pack = _candidate_pack()
    if pack is None:
        pytest.skip("no unsigned production source pack sits above the highest signed one")
    return pack


@pytest.fixture(scope="module")
def candidate_engine_named(
    walks: dict[str, dict[str, Any]], candidate_pack: PackUnderTest
) -> dict[str, tuple[str, ...]]:
    return _engine_named_products(walks, candidate_pack)


@pytest.fixture(scope="module")
def candidate_funnel_named(
    walks: dict[str, dict[str, Any]], candidate_pack: PackUnderTest
) -> dict[str, tuple[str, ...]]:
    return _funnel_named_products(walks, candidate_pack)


def test_corpus_is_the_112_real_interview_walks(walks: dict[str, dict[str, Any]]) -> None:
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
    are deliberately out of this PR's scope.

    W-VO-E (THIS PR) adds 10, corpus 84 -> 94, and changes NO existing
    fixture by a single byte (no tree/mapper edit: `git status` showed ten
    new files and no modified one). Every one of the ten answers a question
    the interview ALREADY asks with something other than its FIRST option —
    a visa-free nationality and a 21-day stay, a 45-day stay, MULTIPLE
    entry, business pay from abroad, an offshore investment application,
    that application with the capital figures E28A's rule reads, an
    education sponsor, a vocational level, a remote worker with no
    Indonesian employer/clients/pay/company, and a minor joining a parent.
    Eleven products that carried a SUPPORT rule in the signed pack and were
    named on zero walks are now named; the twelfth (BRIDGING) is
    unreachable by owner ruling — see `UNREACHABLE_BY_RULING` below.

    W-VO-Q (mission SAETTA-VO3) adds 17, corpus 94 -> 111, and DOES change
    existing fixtures: the tree now asks the ten seq-21 qualification facts,
    whose first option is "yes", so every default walk on the `work`,
    INVESTMENT-purpose `invest` and paid-`other` branches gains the new
    questions in `asked` and the facts KNOWN in `overrides`. No existing
    walk's (state, candidates) moves on signed seq-20 — it reads none of the
    ten — which `test_every_walk_ends_in_its_pinned_outcome` proves; on signed
    seq-21 the moves are `_SEQ21_OUTCOME_CHANGES`, every one an added product.
    The new walks are the `capital_market` vehicle's default walk, one seq-21
    product per walk, the honest "no" on each question, and four business
    explorers (item 7: the D12 walk, with and without a sponsor, the default
    and the named dead end).

    E23V-DEFECT (mission seq-22) adds 1, corpus 111 -> 112:
    `offshore/work/sponsor_government/trade_office_only/employer_no`, the
    `trade_office_only` branch's own `work_payer` answered "no" instead of
    the corpus-wide default "yes". No existing fixture changes — `work_payer`
    was already asked on this branch (`FIXED_CATEGORY_QUESTIONS.work`), only
    never answered anything but the default. On signed seq-20 this walk
    dead-ends on the generic cause (`el.e23-employment-support` already
    requires `work.employer_is_indonesian_entity == true`); on the seq-21
    candidate it dead-ends on `PAID_ACTIVITY_WITHOUT_INDONESIAN_SPONSOR`
    instead (`hf.employment-without-indonesian-sponsor` sweeps E23V in) —
    same (state, candidates) pin both sides, see the comment on this walk's
    `EXPECTED_OUTCOME` row for what moved and what did not."""

    assert len(walks) == 112, f"expected 112 interview walks, found {len(walks)}"
    assert sorted(walks) == sorted(EXPECTED_OUTCOME), "corpus and EXPECTED_OUTCOME disagree"
    for label, spec in walks.items():
        assert spec["asked"], f"{label}: walk carries no asked-question history"
        assert spec["overrides"], f"{label}: walk carries no wire facts"


def test_every_walk_ends_in_its_pinned_outcome(outcomes: dict[str, dict[str, Any]]) -> None:
    violations = _outcome_violations(outcomes)
    assert not violations, "interview-walk outcomes moved:\n  " + "\n  ".join(violations)


def test_the_census_pins_the_signed_sequence() -> None:
    """A newly signed pack with no pins must fail HERE, by name — not as a
    wall of "evaluated but not pinned" rows, and never by quietly grading the
    corpus against the previous sequence's answers."""

    assert _SIGNED_SEQUENCE in EXPECTED_OUTCOME_BY_SEQUENCE, (
        f"rulepack-prod-{_SIGNED_SEQUENCE:03d} is the highest signed pack and the "
        "census has no outcome pins for it: add its changes next to "
        "`_SEQ21_OUTCOME_CHANGES`, and its rows to the per-sequence allowlist and "
        "dead-end tables"
    )
    assert _SIGNED_SEQUENCE in WALK_DEAD_END_ALLOWLIST_BY_SEQUENCE
    assert _SIGNED_SEQUENCE in EXPECTED_DEAD_END_FACT_CENSUS_BY_SEQUENCE
    # The sequences share one corpus, so they must pin the same walks.
    assert all(
        sorted(pins) == sorted(_EXPECTED_OUTCOME_ON_SEQ20)
        for pins in EXPECTED_OUTCOME_BY_SEQUENCE.values()
    )
    # Every seq-21 change is an ADDITION: no walk loses a candidate the
    # seq-20 table gave it (the one state change keeps no candidate to lose).
    for label, (_state, candidates) in _SEQ21_OUTCOME_CHANGES.items():
        assert set(_EXPECTED_OUTCOME_ON_SEQ20[label][1]) <= set(candidates), label
    # Same check for seq-22: the employer_no row goes from () to (E23V,),
    # still an addition (it had nothing to lose).
    for label, (_state, candidates) in _SEQ22_OUTCOME_CHANGES.items():
        assert set(_EXPECTED_OUTCOME_ON_SEQ20[label][1]) <= set(candidates), label


def _outcomes_on(
    walks: dict[str, dict[str, Any]], pack: PackUnderTest
) -> dict[str, dict[str, Any]]:
    """``_evaluate_walks`` for a pack handed in rather than selected from disk:
    the same evaluate → ``apply_public_policy_adapters`` path with no flags,
    flattened by the same ``_decision_actual``. The innocence test below
    proves the two paths agree on the signed pack."""

    out: dict[str, dict[str, Any]] = {}
    for label, spec in sorted(walks.items()):
        decision, compiled, request = _decide(spec["overrides"], label, pack)
        public = evaluate_path.apply_public_policy_adapters(
            decision,
            request.applicant_facts(),
            compiled,
            disclosed_review_flags=request.effective_review_flags(),
        )
        out[label] = _decision_actual(public)
    return out


def test_innocence_the_pack_handed_in_replay_is_the_census_replay(
    walks: dict[str, dict[str, Any]],
    outcomes: dict[str, dict[str, Any]],
) -> None:
    """``_outcomes_on`` is only a witness for the candidate if it IS the
    census's own evaluation: on the signed pack the two agree walk by walk."""

    assert _outcomes_on(walks, _signed_pack()) == outcomes


def test_every_walk_ends_in_its_pinned_outcome_on_the_candidate_pack(
    walks: dict[str, dict[str, Any]],
    candidate_pack: PackUnderTest,
) -> None:
    """The next sequence's pins, exercised BEFORE its signature: while an
    unsigned source sits above signed seq-20, the corpus is graded against
    it with that sequence's own table, so those pins are proven on main
    today and not first in the PR that lands the bundle. The candidate is
    the HIGHEST such source — seq-22 today (``_candidate_source_pack_path``);
    when this test was written it was seq-21, which was signed but stopped
    before activation and never entered this repo (``fold_pack_seq22.py``),
    so seq-22 took its place with no code change here. Once the current candidate is
    signed this skips and ``test_every_walk_ends_in_its_pinned_outcome``
    grades the same table against the verified bytes."""

    sequence = candidate_pack.compiled.sequence
    assert sequence in EXPECTED_OUTCOME_BY_SEQUENCE, f"no pins for candidate seq-{sequence}"
    replayed = _outcomes_on(walks, candidate_pack)
    violations = _outcome_violations(replayed, EXPECTED_OUTCOME_BY_SEQUENCE[sequence])
    assert not violations, "candidate-pack outcomes moved:\n  " + "\n  ".join(violations)
    dead_ends = _dead_end_violations(replayed, WALK_DEAD_END_ALLOWLIST_BY_SEQUENCE[sequence])
    assert not dead_ends, "candidate-pack dead ends:\n  " + "\n  ".join(dead_ends)


def test_walk_state_census_is_the_pinned_census_of_the_signed_sequence(
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
    2/15/65. PR-D4c-2 adds 2: 2/15/65 → 2/15/67.

    W-VO-E (THIS PR) adds 10 walks over an 84 → 94 corpus: 9 of them
    SUPPORTED_CANDIDATES (2/15/67 → 2/15/76) and one — the minor walk —
    HUMAN_REVIEW_REQUIRED, the FIRST review-ending walk this census has ever
    pinned. Its cause is named and asserted below: `MINOR_GUARDIAN_PRIVACY_
    REVIEW`, raised by `_apply_minor_privacy_hold` on `derived.is_minor`
    alone. No existing walk moves state OR bytes.

    W-VO-Q (THIS PR) adds 17 walks over a 94 -> 111 corpus. On signed
    seq-20 (1/2/15/76 -> 1/2/16/92) sixteen answer — seq-20 reads none of
    the ten qualification facts — and the seventeenth, the business explorer
    who converts onshore with no investor route, ends NO_SUPPORTED_PATH on
    ``D12_NOT_CONVERTIBLE``. No existing walk moves state. On signed seq-21
    the census is 1/1/16/93: ``offshore/other/paid/sponsor_unsure`` is
    answered by E33B (see ``_SEQ21_OUTCOME_CHANGES``). The literal is kept
    per signed sequence, so the PR that lands the seq-21 bundle moves no pin
    here.

    E23V-DEFECT (mission seq-22) adds 1 walk over a 111 -> 112 corpus:
    ``offshore/work/sponsor_government/trade_office_only/employer_no``. On
    BOTH signed seq-20 and the seq-21 candidate it ends NO_SUPPORTED_PATH
    (16 -> 17), with two different reason codes (see the walk's own
    ``EXPECTED_OUTCOME`` comment) — the (state, candidates) pin does not
    move, so it needs no ``_SEQ21_OUTCOME_CHANGES`` row. No existing walk
    moves.

    THE SEQ-22 FOLD (a previous PR) added no walk — the corpus stayed 112 —
    and cured the defect the walk above is named for:
    ``fold_pack_seq22.py`` scopes ``hf.employment-without-indonesian-
    sponsor`` to ``("E23", "E33B")`` only, so the employer_no walk's pin
    finally MOVED, against the seq-22 candidate (the highest candidate
    source above signed seq-20 today — seq-21 was signed but stopped before
    activation and never entered this repo): SUPPORTED_CANDIDATES [E23V],
    1/1/17/93 -> 1/1/16/94 over the same 112-walk corpus. No other walk
    moved then.

    D23 "OPTION B-STUDIO" (THIS PR, 2026-09-16) redesigns DEFECT 3: the
    HARD_FILTER/EXCLUDE seq-21 added and the first seq-22 fold deleted comes
    back as ``review.e33.below-threshold-studio``, a REQUIRE_REVIEW on the
    SAME two thresholds (see ``fold_pack_seq22.py``'s DEFECT 3 and
    ``_SEQ22_OUTCOME_CHANGES``). The two walks that used to prove the
    deletion cost nothing — ``offshore/invest/{property,bank_deposit}/
    below_threshold`` — now hold on ``SECOND_HOME_BELOW_THRESHOLD_STUDIO``
    instead of answering ``NO_SUPPORTED_PATH``: 1/1/16/94 -> 3/1/14/94 over
    the same 112-walk corpus. No other walk moves; SUPPORTED_CANDIDATES is
    unaffected because neither walk ever named a candidate."""

    census = dict(Counter(outcome["state"] for outcome in outcomes.values()))
    by_sequence = {
        20: {
            "HUMAN_REVIEW_REQUIRED": 1,
            "NEEDS_INPUT": 2,
            "NO_SUPPORTED_PATH": 17,
            "SUPPORTED_CANDIDATES": 92,
        },
        21: {
            "HUMAN_REVIEW_REQUIRED": 1,
            "NEEDS_INPUT": 1,
            "NO_SUPPORTED_PATH": 17,
            "SUPPORTED_CANDIDATES": 93,
        },
        22: {
            "HUMAN_REVIEW_REQUIRED": 3,
            "NEEDS_INPUT": 1,
            "NO_SUPPORTED_PATH": 14,
            "SUPPORTED_CANDIDATES": 94,
        },
    }
    assert census == EXPECTED_STATE_CENSUS == by_sequence[_SIGNED_SEQUENCE]
    assert census["NEEDS_INPUT"] == len(WALK_DEAD_END_ALLOWLIST)
    # NOT a claim about production, and no longer a claim the corpus cannot
    # check. This fixture evaluates every walk WITHOUT its flags, so what it
    # reports is the PACK's own verdict — the ENGINE half. The disclosure arm
    # of `apply_public_policy_adapters` is exercised by the `flagged_outcomes`
    # fixture instead, where the same walks produce 8 holds; the comment that
    # used to stand here said "a regression that adds a disclosure flag passes
    # it invisibly", and `test_the_flagged_census_is_the_funnel_the_applicant_
    # meets` is what stopped that being true.
    #
    # W-VO-E: the zero became a one, and the count became the CAUSE. The minor
    # walk carries NO disclosure flag — it is held by
    # `evaluate_path._apply_minor_privacy_hold`, a different adapter on the
    # same public path — so this is a narrow, deliberate relaxation of the
    # zero-hold invariant with the one permitted cause pinned, not the
    # "strictly stronger" it first claimed to be (council round 1). It is
    # strictly stronger than the `== 1` it could have been: a second held
    # walk, a DIFFERENT walk holding, or the same walk held for another reason
    # all fail here.
    held = {
        label for label, outcome in outcomes.items() if outcome["state"] == "HUMAN_REVIEW_REQUIRED"
    }
    assert PRIVACY_HELD_WALKS == {"offshore/family/PARENT/spNat=IT/minor"}
    assert held == PRIVACY_HELD_WALKS | STUDIO_HELD_WALKS
    walks = _load_walks()
    minor_walk = walks["offshore/family/PARENT/spNat=IT/minor"]
    public = _public_decision(minor_walk["overrides"], "offshore/family/PARENT/spNat=IT/minor")
    assert [reason.code for reason in public.review_reasons] == ["MINOR_GUARDIAN_PRIVACY_REVIEW"]
    # The Studio holds are named by CAUSE too: on seq-22 each of the two walks
    # is held on exactly the one Studio reason, never on a second one.
    for label in sorted(STUDIO_HELD_WALKS):
        studio = _public_decision(walks[label]["overrides"], label)
        assert [reason.code for reason in studio.review_reasons] == [STUDIO_REVIEW_REASON], label
    assert census["NO_SUPPORTED_PATH"] == by_sequence[_SIGNED_SEQUENCE]["NO_SUPPORTED_PATH"]


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
    the PR that adds it.

    W-VO-Q: named per signed sequence — the two rows on seq-20, and on seq-21
    only the retirement row, because the tree's new government-collaboration
    question cures the other (see `WALK_DEAD_END_ALLOWLIST_BY_SEQUENCE`).
    E23V-DEFECT (mission seq-22): unchanged from seq-21 — the walk this fold
    cures answers instead of dead-ending, so it was never a row here to
    remove."""

    assert set(WALK_DEAD_END_ALLOWLIST_BY_SEQUENCE[20]) == {
        "offshore/other/paid/sponsor_unsure",
        "offshore/retirement/undecided/age64/still_unsure",
    }
    assert set(WALK_DEAD_END_ALLOWLIST_BY_SEQUENCE[21]) == {
        "offshore/retirement/undecided/age64/still_unsure",
    }
    assert set(WALK_DEAD_END_ALLOWLIST_BY_SEQUENCE[22]) == {
        "offshore/retirement/undecided/age64/still_unsure",
    }
    assert WALK_DEAD_END_ALLOWLIST is WALK_DEAD_END_ALLOWLIST_BY_SEQUENCE[_SIGNED_SEQUENCE]
    assert len(WALK_DEAD_END_ALLOWLIST_BY_SEQUENCE[20]) == 2


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
    the permanent form of the invariant, with no excuse available.

    Re-anchored a fourth time, by W-VO-Q, onto ``offshore/invest/pt_pma/
    no_route``, because on signed seq-21 the old anchor's premise is false:
    the default ``offshore/invest/pt_pma`` walk now answers the seq-21 route
    questions with their first option ("yes"), so ``el.e28b/d/f.*`` name
    E28B/E28D/E28F without reading ``family.sponsor_confirmed`` at all —
    withdrawing the sponsor answer leaves an answer standing, not a dead end
    (measured: SUPPORTED_CANDIDATES [E28B, E28D, E28F] withdrawn or denied).
    ``no_route`` is the same investor who answers "no" to every route, so the
    route rules are decided FALSE and C2's sponsor premise is again the only
    thing between the walk and a dead end. Measured on seq-20 AND seq-21: the
    withdrawn fact gives NEEDS_INPUT on exactly ``['family.sponsor_confirmed']``,
    the denied fact NO_SUPPORTED_PATH — the shapes above, on both packs."""

    label = "offshore/invest/pt_pma/no_route"
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
    vacuity finding).

    Re-anchored by W-VO-Q onto ``offshore/work/no_government_collaboration``,
    because on signed seq-21 "E23 is the only product whose ELIGIBILITY rules
    cover EMPLOYMENT" is false: E23U, E23V, E33A and E33B cover it too, and
    ``offshore/work`` (sponsor NONE) now answers the government-collaboration
    question "yes", so denying E23's sponsor leaves SUPPORTED_CANDIDATES [E33B]
    — the applicant keeps an answer, exactly as the pack intends. The new
    anchor is the same NONE-sponsored worker answering "no" to that question,
    which is the premise the old sentence stated; measured on seq-20 AND
    seq-21, denying the sponsor lands it on NO_SUPPORTED_PATH with no
    candidate."""

    label = "offshore/work/no_government_collaboration"
    assert walks[label]["overrides"]["sponsor.government_collaboration"] == {
        "status": "KNOWN",
        "value": False,
    }, "the anchor no longer answers the collaboration question 'no' — re-anchor"
    mutated = dict(walks[label]["overrides"])
    mutated["work.indonesian_work_sponsor_confirmed"] = {"status": "KNOWN", "value": False}
    actual = _evaluate(mutated, label, as_of=_AS_OF)["actual"]

    assert actual["state"] == "NO_SUPPORTED_PATH"
    assert actual["candidates"] == []
    assert _outcome_violations({label: actual}, expected=_scoped_expectation(label))
    # ...and the invariant stays SILENT, because losing an answer this way is
    # not a dead end. Scoped, so the silence is about this walk only.
    assert not _dead_end_violations({label: actual}, allowlist=_scoped_allowlist(label))


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
    premise is visibly stale rather than quietly fictional.

    W-VO-Q moved the anchor to ``offshore/invest/pt_pma/no_route``: on signed
    seq-21 the default ``pt_pma`` walk also names E28B/E28D/F off the route
    questions it now answers "yes", so its pinned outcome is no longer the
    bare C2 this row is built on. ``no_route`` answers every route "no" and
    pins SUPPORTED_CANDIDATES [C2] on both sequences."""

    label = "offshore/invest/pt_pma/no_route"
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

    No corpus walk exercised a minor identity when this test was written, and
    the ad-hoc override below is how it proved the point; W-VO-E later added
    `offshore/family/PARENT/spNat=IT/minor`, a real walk on the same facts,
    which is why this test now has a corpus sibling rather than being the only
    witness. Every OTHER family/diaspora
    walk still uses the corpus's default 25-year-old birth date, so
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


# ---------------------------------------------------------------------------
# The disclosure-flag layer (W-VO-H schema half, 2026-09-13)
#
# Until this section landed, every walk was evaluated with
# `disclosed_review_flags = ()` and the census reported 0 HUMAN_REVIEW_REQUIRED
# over a funnel that produces 8 of them. That is cicatrix #2 in its exact
# shape: a green census standing in front of a layer nobody measured.
# ---------------------------------------------------------------------------


def test_the_corpus_carries_the_disclosure_flag_layer(
    walks: dict[str, dict[str, Any]],
) -> None:
    """Every fixture's flags match the pinned table, in both directions.

    The first assertion is the one that makes the omit-when-empty encoding
    safe: if the generator ever stops emitting the field, EVERY walk reads as
    unflagged and the table's 8 rows all go red at once — a loud failure, not
    a census that silently returns to measuring half a request.
    """

    carrying = {label for label, spec in walks.items() if _walk_flags(spec)}
    assert carrying, (
        "no fixture carries `disclosed_review_flags` at all — the generator "
        "stopped emitting the layer; regenerate with "
        "`npm run visa-oracle:walk-corpus -w apps/mouth`"
    )
    assert _flag_table_violations(walks) == []
    assert carrying == set(EXPECTED_DISCLOSED_REVIEW_FLAGS)


def test_guilt_a_walk_that_loses_its_flag_is_caught(
    walks: dict[str, dict[str, Any]],
) -> None:
    """UNDER-match guilt: strip the flag from a fixture and the table must say
    so. Without this, a regression that quietly stops raising a hold — the
    `work_role` shape, which the old census admitted it could not see — would
    pass."""

    label = "offshore/work/sponsor_unsure"
    stripped = copy.deepcopy(walks[label])
    stripped.pop("disclosed_review_flags")

    violations = _flag_table_violations({label: stripped}, _scoped_flag_table(label))
    assert violations == [f"{label}: fixture carries [], table pins ['NOT_CERTAIN']"]


def test_guilt_a_walk_that_gains_a_flag_is_caught(
    walks: dict[str, dict[str, Any]],
) -> None:
    """OVER-match guilt, the symmetric half: a fixture that starts carrying a
    flag nobody pinned must fail too. A new hold is exactly as much of a
    product change as a lost one — it deletes a verdict the pack proved."""

    label = "offshore/tourism"
    fabricated = copy.deepcopy(walks[label])
    fabricated["disclosed_review_flags"] = ["MULTI_PURPOSE_TRIP"]

    violations = _flag_table_violations({label: fabricated}, _scoped_flag_table(label))
    assert violations == [f"{label}: fixture carries ['MULTI_PURPOSE_TRIP'], table pins []"]


def test_the_flagged_census_is_the_funnel_the_applicant_meets(
    outcomes: dict[str, dict[str, Any]],
    flagged_outcomes: dict[str, dict[str, Any]],
) -> None:
    """The two censuses, side by side — and the headline PLAN slice A1
    changed: **zero of the funnel's holds come from the disclosure layer on
    this corpus** (it raises only `ACTIVITY_BOUNDARY`/`NOT_CERTAIN`, and
    neither holds since the 2026-09-13 ruling); the funnel's 3 holds are the
    same 3 the engine already carried — 1 minor-privacy + 2 Studio.

    `EXPECTED_FLAGGED_STATE_CENSUS` is derived, not pinned, so this asserts
    the split property itself: a flagged walk ends HUMAN_REVIEW_REQUIRED only
    if one of its flags is in `evaluate_path.HOLDING_DISCLOSED_FLAGS`,
    otherwise it keeps its engine state exactly (state AND candidates —
    see `test_innocence_an_unflagged_walk_keeps_its_whole_engine_outcome`'s
    sibling assertion inside `test_every_disclosure_flag_reports_the_walks_
    it_rewrites` for the flagged half of that same claim).

    W-VO-E: the "0 human review at engine level" half of the pre-A1 headline
    is still not true. One walk — `offshore/family/PARENT/spNat=IT/minor` —
    raises NO disclosure flag and is still held, by
    `evaluate_path._apply_minor_privacy_hold`, a different adapter on the
    same public path. Subtracting it by NAME keeps this test measuring what
    it was written to measure (the flag layer's own contribution) instead of
    quietly absorbing a second cause into the count.
    """

    engine_census = dict(Counter(actual["state"] for actual in outcomes.values()))
    funnel_census = dict(Counter(actual["state"] for actual in flagged_outcomes.values()))

    print("\nstate                      ENGINE  FUNNEL")
    for state in sorted(set(engine_census) | set(funnel_census)):
        print(f"{state:<26} {engine_census.get(state, 0):>6}  {funnel_census.get(state, 0):>6}")

    assert engine_census == EXPECTED_STATE_CENSUS
    assert funnel_census == EXPECTED_FLAGGED_STATE_CENSUS
    # The minor-privacy hold is named, not counted away: it is the ONLY hold
    # either census may carry that no disclosure flag produced, and it must be
    # the same walk on both sides (the adapter reads `derived.is_minor`, which
    # no flag can change).
    assert PRIVACY_HELD_WALKS == {"offshore/family/PARENT/spNat=IT/minor"}
    for census in (outcomes, flagged_outcomes):
        held_without_a_flag = {
            label
            for label, actual in census.items()
            if actual["state"] == "HUMAN_REVIEW_REQUIRED"
            and label not in EXPECTED_DISCLOSED_REVIEW_FLAGS
        }
        assert held_without_a_flag == PRIVACY_HELD_WALKS | STUDIO_HELD_WALKS
    # The Studio walks raise no disclosure flag either, or the sum below would
    # count them twice.
    assert not (STUDIO_HELD_WALKS & set(EXPECTED_DISCLOSED_REVIEW_FLAGS))
    # No flag this corpus raises is in HOLDING_DISCLOSED_FLAGS (A1), so the
    # disclosure layer contributes zero holds here: the funnel's total is
    # exactly the two non-flag holds. A new corpus walk raising
    # CRIMINAL_RECORD, or a future PR widening the holding set, must grow
    # this sum in the same PR that re-pins EXPECTED_FLAGGED_STATE_CENSUS.
    assert funnel_census["HUMAN_REVIEW_REQUIRED"] == len(PRIVACY_HELD_WALKS) + len(
        STUDIO_HELD_WALKS
    )


def test_innocence_an_unflagged_walk_keeps_its_whole_engine_outcome(
    outcomes: dict[str, dict[str, Any]],
    flagged_outcomes: dict[str, dict[str, Any]],
) -> None:
    """The 103 walks that raise nothing are byte-for-byte the same decision in
    both censuses — not merely the same state, the same candidates, missing
    facts, reason codes and notices. (103 = 111 - 8 since W-VO-Q; 86 = 94 - 8
    before it; it said 76 until council round 4, which is the 84-walk figure
    W-VO-E superseded.)

    This is the innocence half of the guard: supplying flags must change
    NOTHING for a walk that raises none, or the flagged census would be
    measuring the act of passing flags rather than the flags themselves.
    """

    unflagged = sorted(set(outcomes) - set(EXPECTED_DISCLOSED_REVIEW_FLAGS))
    assert len(unflagged) == len(outcomes) - len(EXPECTED_DISCLOSED_REVIEW_FLAGS)
    differences = [label for label in unflagged if flagged_outcomes[label] != outcomes[label]]
    assert differences == []


def test_every_disclosure_flag_reports_the_walks_it_rewrites(
    outcomes: dict[str, dict[str, Any]],
    flagged_outcomes: dict[str, dict[str, Any]],
) -> None:
    """The table Zero needs to rule on `MULTI_PURPOSE_TRIP` and the rest:
    per flag, how many walks it touches, and whether it holds or conditions.

    Since PLAN slice A1, neither flag this corpus raises holds — the pack's
    own state and candidates survive untouched, and a `*_CONDITION` notice
    is the only visible change. Printed on every run (`pytest -s`) and
    asserted, so the number in a PR body is the number the test measured.
    """

    per_flag: dict[str, list[tuple[str, str, str]]] = {}
    for label, flags in EXPECTED_DISCLOSED_REVIEW_FLAGS.items():
        for flag in flags:
            per_flag.setdefault(flag, []).append(
                (label, outcomes[label]["state"], flagged_outcomes[label]["state"])
            )

    print("\nflag | walks touched | engine-state -> funnel-state")
    for flag in sorted(per_flag):
        rows = per_flag[flag]
        transitions = Counter((before, after) for _label, before, after in rows)
        rendered = "; ".join(
            f"{before} -> {after} (x{count})"
            for (before, after), count in sorted(transitions.items())
        )
        print(f"{flag} | {len(rows)} | {rendered}")

    for flag, rows in sorted(per_flag.items()):
        condition_code = EXPECTED_CONDITION_REASON_FOR_FLAG[flag]
        for label, before, after in rows:
            assert after == before, (
                f"{label}: raises {flag}, a non-holding flag, but the funnel "
                f"state ({after}) diverged from the engine state ({before}) — "
                "a conditioning flag may only ADD a notice"
            )
            assert outcomes[label]["candidates"] == flagged_outcomes[label]["candidates"], (
                f"{label}: {flag} changed the candidate set — a conditioning "
                "flag can never create, reorder or remove a candidate"
            )
            assert flagged_outcomes[label]["review_reason_codes"] == [], (
                f"{label}: {flag} is not in HOLDING_DISCLOSED_FLAGS but still "
                "populated review_reason_codes"
            )
            assert condition_code in flagged_outcomes[label]["notice_codes"], (
                f"{label}: rewritten by {flag} without emitting {condition_code}"
            )

    assert {flag: len(rows) for flag, rows in per_flag.items()} == {
        "ACTIVITY_BOUNDARY": 6,
        "NOT_CERTAIN": 2,
    }
    assert sorted(EXPECTED_CONDITION_REASON_FOR_FLAG) == sorted(per_flag), (
        "a flag started (or stopped) firing on this corpus — add or remove its "
        "row in EXPECTED_CONDITION_REASON_FOR_FLAG in the same PR"
    )


def test_innocence_a_fabricated_flag_keeps_a_proven_verdict(
    walks: dict[str, dict[str, Any]],
    outcomes: dict[str, dict[str, Any]],
) -> None:
    """PLAN VISA-ORACLE-DW-20260919 slice A1: a walk the pack answers cleanly
    KEEPS every candidate the moment a non-holding flag is supplied — only a
    named condition is added.

    `offshore/tourism` is SUPPORTED on C1 with no flag. Supply
    `MULTI_PURPOSE_TRIP` — the ordinary answer "my trip has two purposes" —
    and C1 survives. Before A1 this deleted the verdict; the corpus itself
    raises this flag on zero walks, so nothing else in this file would show
    the split. See `test_guilt_the_holding_env_var_restores_a_deleted_verdict`
    for the companion case: the same flag, killswitched back to a hold.
    """

    label = "offshore/tourism"
    assert outcomes[label]["state"] == "SUPPORTED_CANDIDATES"
    assert outcomes[label]["candidates"] == ["C1"]

    conditioned = _evaluate(
        walks[label]["overrides"],
        label,
        as_of=_AS_OF,
        disclosed_review_flags=("MULTI_PURPOSE_TRIP",),
    )["actual"]

    assert conditioned["state"] == "SUPPORTED_CANDIDATES"
    assert conditioned["candidates"] == ["C1"]
    assert conditioned["review_reason_codes"] == []
    assert "DISCLOSED_MULTI_PURPOSE_TRIP_CONDITION" in conditioned["notice_codes"]


def test_guilt_the_holding_env_var_restores_a_deleted_verdict(
    walks: dict[str, dict[str, Any]],
    outcomes: dict[str, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fleet-wide kill switch, exercised against a real corpus walk:
    listing `MULTI_PURPOSE_TRIP` in `VISA_ORACLE_HOLDING_FLAGS` restores the
    pre-A1 hold with no code change — `fly secrets set`, a restart not a
    redeploy."""

    label = "offshore/tourism"
    assert outcomes[label]["state"] == "SUPPORTED_CANDIDATES"
    monkeypatch.setenv(evaluate_path._HOLDING_FLAGS_ENV_VAR, "MULTI_PURPOSE_TRIP")

    held = _evaluate(
        walks[label]["overrides"],
        label,
        as_of=_AS_OF,
        disclosed_review_flags=("MULTI_PURPOSE_TRIP",),
    )["actual"]

    assert held["state"] == "HUMAN_REVIEW_REQUIRED"
    assert held["candidates"] == []
    assert held["review_reason_codes"] == ["DISCLOSED_MULTI_PURPOSE_TRIP_REVIEW"]


def test_the_flagged_rebuild_names_every_field_of_the_wire_model() -> None:
    """The FUNNEL census's one new code path rebuilds ``VisaOracleEvaluateRequest``
    BY HAND, and nothing in the rebuild itself ties it to the model.

    Council round 5 (council/journal.jsonl): a sixth field added to the request model
    would be dropped from every flagged evaluation, and would stay invisible —
    ``test_innocence_an_unflagged_walk_keeps_its_whole_engine_outcome`` cannot
    see it (unflagged walks never enter the rebuild) and the flagged
    assertions cannot either, because ``_apply_disclosed_review_flags``
    overwrites candidates, missing facts, no-path reasons and quotes whatever
    the facts were. So the binding is asserted here, where the red names the
    cause, as well as raised at the rebuild site.
    """

    assert set(VisaOracleEvaluateRequest.model_fields) == set(
        gold_coverage_eval._REBUILT_REQUEST_FIELDS
    )


def test_the_products_the_applicant_is_never_shown_are_pinned_by_cause(
    engine_named: dict[str, tuple[str, ...]],
    funnel_named: dict[str, tuple[str, ...]],
) -> None:
    """The funnel half of the reachability guard, on the SIGNED pack.

    ``test_every_product_the_candidate_pack_adds_is_named_to_the_applicant``
    proves the nine seq-21 products reach the applicant only while seq-21 is
    a candidate, and skips once it is signed. This keeps that property after
    the signature: a product the engine names on some walk but the applicant
    is never shown may only be E31E, held by the minor-privacy adapter.
    Before PLAN slice A1, C6 belonged here too — its one witness
    (``offshore/other/no_paid_activity/medical``) raises ACTIVITY_BOUNDARY,
    which used to rewrite the decision to a hold with candidates emptied. A1
    (owner ruling 2026-09-13) makes ACTIVITY_BOUNDARY a named condition
    instead: C6 now survives at funnel level, with a
    ``DISCLOSED_ACTIVITY_BOUNDARY_CONDITION`` notice attached, so C6 is no
    longer in the gap this test guards. Measured 2026-09-19 (A1) on signed
    seq-22; measured 2026-09-14 on signed seq-20/seq-21 pre-A1."""

    assert sorted(set(engine_named) - set(funnel_named)) == ["E31E"]
    assert engine_named["C6"] == ("offshore/other/no_paid_activity/medical",)
    assert "C6" in funnel_named
    assert set(engine_named["E31E"]) <= PRIVACY_HELD_WALKS


def test_every_support_bearing_product_is_named_by_some_walk(
    engine_named: dict[str, tuple[str, ...]],
) -> None:
    """W-VO-E's binding: a product the signed pack SUPPORTS, that no
    interview walk can name, is a coverage gap no other test in this
    repository can see.

    ``test_gold_coverage_floor.py`` proves the pack can support a product
    when every fact arrives. This file's census proves what the funnel
    answers. NEITHER notices a product that simply never appears: a walk
    cannot lose a candidate it could never gain, so a product unreachable
    through the interview is invisible in every count above — it looks
    exactly like a product nobody happened to qualify for. Measured
    2026-09-13 before this test existed: 12 of the pack's 29 SUPPORT-bearing
    products were in that state, including the digital-nomad and Investor
    KITAS products, and had been for the whole life of the corpus.

    The two halves are read from DIFFERENT sources on purpose — the
    supported set from the signed pack, COMPILED and effective-filtered, the named set by
    replaying the corpus — so neither can be edited into agreement with the
    other. Curing a red here means giving the product a WALK (an applicant
    who answers the questions its rules read), never widening this test.
    """

    unreached = _unreached_support_products(engine_named)
    assert not unreached, (
        "the signed pack supports these products and no interview walk "
        f"names any of them: {unreached}. Add a walk to "
        "`generate-walk-corpus.ts` that answers the facts their rules read, "
        "or — only if an owner ruling forbids collecting one of those facts "
        "— add a row to UNREACHABLE_BY_RULING quoting the ruling."
    )


#: The candidate pack's catalogue: 38 product codes, unchanged since seq-20.
#: Measured 2026-09-14 on rulepack-prod-021.source.json when seq-21 was the
#: candidate; re-measured 2026-09-16 on rulepack-prod-022.source.json, the
#: candidate today (seq-21 was signed but stopped before activation and
#: never entered this repo — see `fold_pack_seq22.py`) — same count, every
#: code still carrying a SUPPORT rule once the nine seq-21/seq-22 products
#: are in force.
CANDIDATE_CATALOGUE_SIZE = 38


def test_every_support_bearing_product_of_the_candidate_pack_is_named_by_some_walk(
    candidate_pack: PackUnderTest,
    candidate_engine_named: dict[str, tuple[str, ...]],
) -> None:
    """W-VO-Q's acceptance, measured rather than asserted: against the
    UNSIGNED candidate — the highest unsigned source above the highest
    signed pack, seq-22 today (seq-21 when this test was written; seq-21 was
    signed but stopped before activation and never entered this repo, see
    `fold_pack_seq22.py`) — every product in the catalogue carries a SUPPORT
    rule, and every one of them is named by at least one interview walk —
    except the one product an owner ruling forbids the funnel to reach
    (``UNREACHABLE_BY_RULING``), which is still accounted for by name.

    The signed default above cannot see this: the candidate's nine new
    SUPPORT rules exist in no signed pack, so a tree that stopped asking
    their facts would stay green there. This mode grades the same corpus
    against the pack that will be signed, which is the only place the ten
    new questions can fail.
    """

    catalogue = {product.product_code for product in candidate_pack.compiled.products}
    assert len(catalogue) == CANDIDATE_CATALOGUE_SIZE
    assert _support_bearing_product_codes(candidate_pack) == catalogue, (
        "the candidate pack no longer gives every catalogue product a SUPPORT rule"
    )
    unreached = _unreached_support_products(candidate_engine_named, pack=candidate_pack)
    assert not unreached, (
        "the candidate pack supports these products and no interview walk names "
        f"any of them: {unreached}. Ask the fact their rule reads (tree.ts/flow.ts) "
        "and give them a walk in `generate-walk-corpus.ts`."
    )
    assert _stale_ruling_rows(candidate_engine_named) == []
    assert set(candidate_engine_named) | set(UNREACHABLE_BY_RULING) == catalogue


def test_the_candidate_ruling_row_still_depends_on_its_forbidden_fact(
    candidate_pack: PackUnderTest,
) -> None:
    """The BRIDGING excuse re-derived from the candidate, not carried over from
    the signed pack: a new sequence is exactly where a free route could appear."""

    assert _ruling_rows_without_a_proven_dependency(pack=candidate_pack) == []
    assert set(UNREACHABLE_BY_RULING) <= _support_bearing_product_codes(candidate_pack)


#: The nine products the candidate pack makes supportable, as the census
#: measures them: named at engine level against the candidate (seq-22 today,
#: seq-21 when first measured — the same nine products, unaffected by
#: seq-22's two cures) and on no walk against the signed pack.
SEQ21_ADDED_PRODUCTS = ("E23U", "E23V", "E28B", "E28C", "E28D", "E28F", "E33A", "E33B", "E33C")


def test_every_product_the_candidate_pack_adds_is_named_to_the_applicant(
    engine_named: dict[str, tuple[str, ...]],
    candidate_engine_named: dict[str, tuple[str, ...]],
    candidate_funnel_named: dict[str, tuple[str, ...]],
) -> None:
    """The engine-level guard above answers "can an interview produce the
    facts"; this answers "does an applicant who gives them SEE the product".
    A walk whose answers also raise a disclosure flag is rewritten to
    HUMAN_REVIEW_REQUIRED with no candidates, so a product whose only witness
    is flagged is reachable on paper and named to nobody.

    That is not hypothetical: E28C's first walk answered the `undecided`
    vehicle, was held by ACTIVITY_BOUNDARY, and passed the engine-level guard
    (council round 1 (council/journal.jsonl)). Scoped to the products seq-21 adds,
    because the signed products' public reach is already pinned walk by walk
    in EXPECTED_OUTCOME and E31E's minor-privacy hold is by design."""

    added = tuple(sorted(set(candidate_engine_named) - set(engine_named)))
    assert added == SEQ21_ADDED_PRODUCTS
    unseen = sorted(set(added) - set(candidate_funnel_named))
    assert not unseen, (
        f"the candidate pack supports {unseen} on some walk, but every such walk "
        "raises a disclosure flag, so no applicant is ever shown them"
    )


def test_guilt_a_seq21_product_whose_only_walk_is_flagged_is_caught(
    walks: dict[str, dict[str, Any]],
    candidate_pack: PackUnderTest,
    candidate_engine_named: dict[str, tuple[str, ...]],
) -> None:
    """Guilt for the test above: give E28C's single witness the
    ACTIVITY_BOUNDARY flag its old `undecided` vehicle raised, and the funnel
    stops naming E28C while the engine still does."""

    (label,) = candidate_engine_named["E28C"]
    held = copy.deepcopy(walks[label])
    held["disclosed_review_flags"] = ["ACTIVITY_BOUNDARY"]
    assert "E28C" in _funnel_named_products({label: walks[label]}, candidate_pack)
    assert "E28C" not in _funnel_named_products({label: held}, candidate_pack)
    assert "E28C" in _engine_named_products({label: held}, candidate_pack)


#: The one qualification fact each seq-21 product's SUPPORT rule adds
#: (FACTS-FOR-THE-TREE.md) — the fact a tree that stopped asking would leave
#: UNKNOWN(NOT_ASKED) on the wire.
SEQ21_QUALIFYING_FACT = {
    "E23U": "sponsor.diplomatic_household",
    "E23V": "sponsor.trade_office",
    "E28B": "investment.establishes_indonesian_company",
    "E28C": "investment.capital_market_only",
    "E28D": "investment.foreign_branch_or_subsidiary",
    "E28F": "investment.ikn_subsidiary",
    "E33A": "sponsor.government_invitation",
    "E33B": "sponsor.government_collaboration",
    "E33C": "sponsor.world_figure_invitation",
}


@pytest.mark.parametrize("product", SEQ21_ADDED_PRODUCTS)
def test_guilt_the_candidate_guard_catches_a_seq21_product_losing_its_walks(
    walks: dict[str, dict[str, Any]],
    candidate_pack: PackUnderTest,
    candidate_engine_named: dict[str, tuple[str, ...]],
    product: str,
) -> None:
    """Guilt, once per product seq-21 made supportable, on the WALKS and not
    on the derived map: every walk that names the product has its qualifying
    fact reset to UNKNOWN(NOT_ASKED) — the wire a tree that stopped asking
    the question would send — and is re-evaluated against the candidate.
    The candidate guard then names exactly that product; the signed guard
    stays silent on the same map, which is why the candidate mode exists."""

    assert sorted(SEQ21_QUALIFYING_FACT) == sorted(SEQ21_ADDED_PRODUCTS)
    witnesses = candidate_engine_named.get(product, ())
    assert witnesses, f"fixture drift: {product} must be named"
    fact = SEQ21_QUALIFYING_FACT[product]
    unasked: dict[str, dict[str, Any]] = {}
    for label in witnesses:
        spec = copy.deepcopy(walks[label])
        assert fact in spec["overrides"], f"{label}: no {fact} on the wire"
        spec["overrides"][fact] = {"status": "UNKNOWN", "reason": "NOT_ASKED"}
        unasked[label] = spec
    renamed = _engine_named_products(unasked, candidate_pack)
    assert product not in renamed
    mutated: dict[str, list[str]] = {
        code: [label for label in labels if label not in unasked]
        for code, labels in candidate_engine_named.items()
    }
    for code, labels in renamed.items():
        mutated.setdefault(code, []).extend(labels)
    named = {code: tuple(labels) for code, labels in mutated.items() if labels}
    assert _unreached_support_products(named, pack=candidate_pack) == [product]
    assert product not in _unreached_support_products(named)


def test_unreachable_by_ruling_holds_only_the_bridging_row() -> None:
    """One row, and it is a ruling. This table is the single place a product
    may be excused from the guard above, so its CONTENTS are pinned: a row
    added without touching this test is not possible."""

    assert set(UNREACHABLE_BY_RULING) == {"BRIDGING"}
    assert UNREACHABLE_BY_RULING["BRIDGING"].forbidden_fact == "intent.requested_product_code"
    assert "never asks which visa" in UNREACHABLE_BY_RULING["BRIDGING"].ruling


def test_every_ruled_unreachable_product_still_depends_on_its_forbidden_fact() -> None:
    """The excuse is re-derived from the pack, not trusted.

    A row says "no walk can name this product because its SUPPORT rules need a
    fact an owner ruling forbids the funnel to collect". That claim is only
    true while EVERY effective SUPPORT route for the product provably cannot
    fire without the fact. The day a signed pack adds a BRIDGING route keyed
    on something the interview does collect, the product becomes reachable —
    and the guard above would stay green anyway, because the excuse subtracts
    the code unconditionally. This test is what turns that into a red (council
    round 1 (council/journal.jsonl)).

    The analysis is conservative (council round 3): it proves dependency, it
    never proves the absence of one, so a red here means "re-justify", not
    "the route is reachable" — the message says which.
    """

    offenders = _ruling_rows_without_a_proven_dependency()
    assert not offenders, (
        "these UNREACHABLE_BY_RULING rows carry a SUPPORT route whose "
        f"dependency on their forbidden fact is no longer provable: {offenders}. "
        "Either the pack gave the product a route that does not need the fact "
        "— give it a walk and delete the row — or the route is written in a "
        "shape this conservative check cannot reason about, in which case "
        "extend the check and say so. Do not widen the excuse."
    )
    # ...and an excuse for a product the pack does not support at all is a
    # typo, not a ruling.
    assert set(UNREACHABLE_BY_RULING) <= _support_bearing_product_codes()


def test_no_unreachable_by_ruling_row_is_stale(
    engine_named: dict[str, tuple[str, ...]],
) -> None:
    """The mirror of the guard: a row whose product a walk DOES name is a
    stale excuse, and stale excuses are how an allowlist outlives the thing
    it was written for. Delete the row instead of leaving it to cover a gap
    that closed."""

    stale = _stale_ruling_rows(engine_named)
    assert not stale, f"UNREACHABLE_BY_RULING rows now reached by a walk: {stale}"


def test_guilt_a_support_bearing_product_no_walk_names_is_caught(
    engine_named: dict[str, tuple[str, ...]],
) -> None:
    """Guilt for the guard: delete the only product-naming this corpus has
    for E33G — exactly what happens when a tree change stops routing to a
    product — and the guard must name E33G.

    E33G is chosen because W-VO-E gave it its first and only walk
    (`offshore/remote/foreign_only`), so dropping it from the named map is
    the faithful simulation of the gap reopening.
    """

    assert "E33G" in engine_named, "fixture drift: E33G must be named by a walk"
    without_e33g = {code: labels for code, labels in engine_named.items() if code != "E33G"}
    assert _unreached_support_products(without_e33g) == ["E33G"]


def test_guilt_a_fabricated_ruling_row_that_is_reachable_is_caught(
    engine_named: dict[str, tuple[str, ...]],
) -> None:
    """Guilt for the staleness mirror: excuse a product the corpus DOES name
    (C1, on 39 of the 94 walks) and the staleness check must catch it, so the
    excuse table can never be used to silence a product that is perfectly
    reachable."""

    fabricated = {
        "C1": RuledUnreachable(
            forbidden_fact="intent.requested_product_code",
            ruling="fabricated row — C1 is named by most of the corpus",
        )
    }
    assert _stale_ruling_rows(engine_named, excused=fabricated) == ["C1"]
    # ...and the guard itself stays silent about C1, which is the half that
    # would hide the fabrication if the mirror above did not exist.
    assert "C1" not in _unreached_support_products(engine_named, excused=fabricated)


def test_guilt_a_ruling_row_whose_product_has_a_free_support_route_is_caught() -> None:
    """Guilt for the fact-dependency check: excuse C6 — a product no ruling
    covers, whose SUPPORT rule (`el.c6.social`) reads `intent.purposes`, never
    `intent.requested_product_code` — and the check must name it.

    C6 stands in for the future BRIDGING route the real row could not see: a
    product excused for a fact its rules do not actually need.
    """

    fabricated = {
        "C6": RuledUnreachable(
            forbidden_fact="intent.requested_product_code",
            ruling="fabricated row — C6's SUPPORT rule reads no such fact",
        )
    }
    assert _ruling_rows_without_a_proven_dependency(excused=fabricated) == ["C6"]


def test_guilt_a_rule_that_only_mentions_the_forbidden_fact_is_not_a_dependency() -> None:
    """Guilt for the SEMANTIC half of the dependency check — the round-2
    council finding, as its own counterexample.

    ``any(eq(requested_product_code, "BRIDGING"), intersects(purposes, OTHER))``
    MENTIONS the forbidden fact, so `required_facts` contains it and a
    membership test would call the ruling row justified. The condition
    nonetheless evaluates TRUE with the fact UNKNOWN, on the OTHER branch —
    verified here against the real evaluator, not asserted. The AND-spine
    test must reject it, and must still accept the conjunction shape every
    real BRIDGING rule uses.
    """

    forbidden = "intent.requested_product_code"
    bypass = ast_module.AnyCondition(
        op="any",
        args=(
            ast_module.EqCondition(
                op="eq", fact=FactPath.INTENT_REQUESTED_PRODUCT_CODE, value="BRIDGING"
            ),
            ast_module.IntersectsCondition(
                op="intersects", fact=FactPath.INTENT_PURPOSES, values=("OTHER",)
            ),
        ),
    )
    snapshot = ast_module.FactSnapshot(
        values={
            FactPath.INTENT_REQUESTED_PRODUCT_CODE: UnknownFact(UnknownReason.NOT_ASKED),
            FactPath.INTENT_PURPOSES: KnownFact(frozenset({"OTHER"})),
        }
    )
    assert forbidden in {str(path) for path in ast_module.collect_fact_paths(bypass)}, (
        "the counterexample must MENTION the fact — that is what makes it a trap"
    )
    assert ast_module.evaluate_condition(bypass, snapshot).truth is TruthValue.TRUE
    assert _proves_it_cannot_fire_without(bypass, forbidden) is False

    # Innocence: the shape the four real BRIDGING rules use is accepted, and
    # the real rules themselves are what the row rests on.
    conjunction = ast_module.AllCondition(op="all", args=(bypass.args[0], bypass.args[1]))
    assert _proves_it_cannot_fire_without(conjunction, forbidden) is True
    for rule in _support_rules_by_product()["BRIDGING"]:
        assert _proves_it_cannot_fire_without(rule.when, forbidden), rule.rule_id
