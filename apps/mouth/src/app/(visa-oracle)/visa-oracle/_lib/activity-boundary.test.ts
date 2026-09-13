import { describe, expect, it } from "vitest";
import {
  ACTIVITY_BOUNDARY_DECIDABLE_ANSWERS,
  mapDisclosedReviewFlags,
  mapOracleFactsToApplicantFacts,
} from "./fact-mapper";
import { flowReducer, initialFlowState, type FlowState } from "./flow";
import { QUESTIONS, type OracleFacts } from "./tree";

/**
 * ACTIVITY_BOUNDARY census — the narrowed table asserted as a TABLE, not a
 * predicate, because a disclosed flag is terminal: the backend rewrites the
 * decision to HUMAN_REVIEW_REQUIRED with `candidates=()`, so one over-broad
 * clause deletes an answer the pack had already proven (offshore/work,
 * measured: `SUPPORTED_CANDIDATES [E23]` without the flag,
 * `HUMAN_REVIEW_REQUIRED` with it — spec §2.1). Every walk is driven through
 * the REAL `flowReducer`; a hand-built fact bag could assert a flag set no
 * user can produce. Rows cover every branch carrying a human-context answer,
 * plus tourism, which stands for the branches that carry none.
 */

function answer(
  state: FlowState,
  questionId: string,
  value: string,
): FlowState {
  expect(state.history[state.history.length - 1]).toEqual({
    kind: "question",
    questionId,
  });
  return flowReducer(state, { type: "ANSWER", questionId, value });
}

/** The offshore spine every walk shares (same shape as
 * `flow.test.ts::startOffshore`), through to `review_gate: "none"`. */
function walkFacts(walk: WalkCase): OracleFacts {
  let state = flowReducer(initialFlowState("en"), { type: "ADVANCE" });
  state = answer(state, "in_indonesia", "no");
  state = answer(state, "holds_stay_permit", "no");
  state = answer(state, "overstay_days", "0");
  state = answer(state, "nationalities", "IT");
  state = answer(state, "birth_date", "1990-02-03");
  state = answer(state, "category", walk.category);
  state = answer(state, "trip_scope", walk.tripScope);
  for (const [questionId, value] of walk.branch) {
    state = answer(state, questionId, value);
  }
  return answer(state, "review_gate", "none").facts;
}

interface WalkCase {
  /** `name` carries the verdict this row is evidence of. */
  readonly name: string;
  readonly category: string;
  readonly tripScope: string;
  readonly branch: readonly (readonly [questionId: string, value: string])[];
  /** EXACT expected flags — `mapDisclosedReviewFlags` sorts. */
  readonly flags: readonly string[];
}

const WALKS: readonly WalkCase[] = [
  {
    name: "tourism · 30d — no human-context answer, unchanged",
    category: "tourism",
    tripScope: "single",
    branch: [
      ["stay_days", "30"],
      ["entry_pattern", "SINGLE"],
    ],
    flags: [],
  },
  {
    name: "business · meetings — FREED: conduct the pack decides on purposes + stay_days",
    category: "business",
    tripScope: "single",
    branch: [
      ["business_activity", "meetings"],
      ["work_indonesia_compensation", "no"],
      ["stay_days", "14"],
      ["entry_pattern", "SINGLE"],
    ],
    flags: [],
  },
  {
    name: "business · training — HELD: CL-D12-05, no activity.* fact discriminates it",
    category: "business",
    tripScope: "single",
    branch: [
      ["business_activity", "training"],
      ["work_indonesia_compensation", "no"],
      ["stay_days", "14"],
      ["entry_pattern", "SINGLE"],
    ],
    flags: ["ACTIVITY_BOUNDARY"],
  },
  {
    name: "business · meetings · multi-purpose — MULTI_PURPOSE_TRIP survives the narrowing",
    category: "business",
    tripScope: "multiple",
    branch: [
      ["business_activity", "meetings"],
      ["work_indonesia_compensation", "no"],
      ["stay_days", "14"],
      ["entry_pattern", "MULTIPLE"],
    ],
    flags: ["MULTI_PURPOSE_TRIP"],
  },
  {
    name: "work · employer confirmed — FREED (decision 6): the E23 witness",
    category: "work",
    tripScope: "single",
    branch: [
      ["sponsor_category", "EMPLOYER"],
      ["work_payer", "yes"],
      ["work_indonesia_compensation", "yes"],
      ["work_sponsor_confirmed", "yes"],
      // `work_role` used to sit here. It is gone from the flow as of
      // 2026-09-06 (owner ruling 6, shipped on main), so driving the REAL
      // reducer through it now fails — the row is re-anchored to the live
      // sequence, not weakened.
      ["stay_days", "365"],
    ],
    flags: [],
  },
  {
    name: "remote · foreign clients — the deleted remote_income clause named no real question",
    category: "remote",
    tripScope: "single",
    branch: [
      ["sponsor_category", "NONE"],
      ["remote_clients", "foreign"],
      ["remote_compensation", "no"],
      // `work_payer` (work.employer_is_indonesian_entity) was inserted into
      // the remote branch by #5855. "no" is the answer a foreign-client
      // remote worker gives; it is a FACT question, so it adds no flag.
      ["work_payer", "no"],
      ["remote_employer_country", "US"],
      ["remote_pt_pma", "no"],
      ["stay_days", "365"],
    ],
    flags: [],
  },
  {
    // Released (PR-D3, D3-1): `investment_vehicle=property` now routes to
    // Second Home and `mapPurposes` emits SECOND_HOME alone, so neither
    // `family_sponsor_confirmed` nor `wants_onshore_conversion` is asked any
    // more — no E33 rule reads either fact. Was "HELD" under §6 R3; see
    // fact-mapper.ts's `ACTIVITY_BOUNDARY_DECIDABLE_ANSWERS` comment.
    name: "invest · property — FREED (D3-1): routes to Second Home, SECOND_HOME alone",
    category: "invest",
    tripScope: "single",
    branch: [
      ["sponsor_category", "INVESTMENT"],
      ["investment_vehicle", "property"],
      ["secondhome_property_value_usd", "1200000"],
      ["stay_days", "730"],
    ],
    flags: [],
  },
  {
    name: "invest · bank_deposit — FREED (D3-1): routes to Second Home, SECOND_HOME alone",
    category: "invest",
    tripScope: "single",
    branch: [
      ["sponsor_category", "INVESTMENT"],
      ["investment_vehicle", "bank_deposit"],
      ["secondhome_deposit_usd", "150000"],
      ["secondhome_state_bank", "yes"],
      ["secondhome_own_name", "yes"],
      ["stay_days", "730"],
    ],
    flags: [],
  },
  {
    name: "retirement · property — FREED (PR-D3, D3-3): family_sponsor_confirmed is now asked as a fallback, curing the §6 R3 defect this HELD",
    category: "retirement",
    tripScope: "single",
    branch: [
      ["sponsor_category", "NONE"],
      ["retirement_basis", "property"],
      ["secondhome_property_value_usd", "1200000"],
      ["secondhome_passive_income_usd", "5000"],
      ["family_sponsor_confirmed", "yes"],
      ["stay_days", "365"],
    ],
    flags: [],
  },
  {
    // NARROW-2 (owner ruling SHWEB-20260911, 2026-09-12): `el.e33f.
    // retirement` (rulepack-prod-020) decides SUPPORT off
    // `secondhome.passive_monthly_income_usd >= 3000` and `family.
    // sponsor_confirmed == true` alone — it never reads `retirement_basis`
    // at all — so the table was UNDER-inclusive: it deleted a real,
    // deterministic engine answer regardless of which one it was.
    // CORRECTED 2026-09-12 (D3-C/C2): this fixture is the YOUNG identity
    // (age 25, `YOUNG_APPLICANT_BIRTH_DATE`), and at 25 the answer is
    // NO_SUPPORTED_PATH — `hf.e33f.age-below-55` excludes E33F before
    // `el.e33f.retirement` is ever reached. SUPPORTED E33F is reached only
    // by the SAME branch replayed at age 64 in the backend corpus
    // (`offshore/retirement/family_sponsor/age64`,
    // `test_interview_walk_census.py`'s `EXPECTED_OUTCOME`); the walk at
    // this age (`offshore/retirement/family_sponsor`) is pinned
    // NO_SUPPORTED_PATH there. What NARROW-2 actually fixed is age-blind:
    // `mapDisclosedReviewFlags` never sees `birth_date`, so the flag was
    // deleting whichever real verdict the engine reached — a proven
    // NO_SUPPORTED_PATH at 25, a proven SUPPORTED E33F at 64 — for a fact
    // (`retirement_basis`) neither verdict depends on.
    name: "retirement · family_sponsor — FREED (NARROW-2): el.e33f.retirement never reads retirement_basis",
    category: "retirement",
    tripScope: "single",
    branch: [
      ["sponsor_category", "NONE"],
      ["retirement_basis", "family_sponsor"],
      ["secondhome_passive_income_usd", "5000"],
      ["family_sponsor_confirmed", "yes"],
      ["stay_days", "365"],
    ],
    flags: [],
  },
  {
    // NAME CORRECTED 2026-09-08, RELEASED SAME DAY. This row used to read
    // "HELD: CATEGORY_TO_PURPOSE emits no purpose for it", and that rationale
    // died when #5855 — merged into this very branch — added
    // `diaspora: "FAMILY"` to CATEGORY_TO_PURPOSE (fact-mapper.ts): the path
    // was no longer unreachable, so the flag was no longer harmless.
    //
    // MEASURED against production 2026-09-07, `disclosed_review_flags=[]`: all
    // 15 diaspora walks of the corpus return SUPPORTED_CANDIDATES with real
    // candidates (C1 + E31A/E31C/E31F/E31G by relation). Holding on the mere
    // presence of `diaspora_connection`/`diaspora_documents` was deleting
    // proven candidates for 100% of diaspora traffic — the exact pathology
    // this file's own docstring names. The owner ruled: automatic. This walk
    // (`former_wni`) is now FREED — the pack decides it on its own.
    //
    // `dual` (Indonesian dual citizenship) stays HELD, deliberately: it is the
    // one diaspora status the owner named as a legitimate human-review case,
    // and no corpus walk exercises it — see the second row below, which
    // certifies the exception on the same live branch.
    name: "diaspora · former_wni — FREED: the pack decides it on its own",
    category: "diaspora",
    tripScope: "single",
    branch: [
      ["diaspora_connection", "former_wni"],
      ["diaspora_documents", "yes"],
      // #5855 turned the single dead-end diaspora walk into a full family
      // branch — the sponsor is now interviewed properly instead of the
      // interview stopping. Re-anchored to that live sequence.
      ["sponsor_category", "FAMILY"],
      ["family_relation", "SPOUSE"],
      ["marital_status", "MARRIED"],
      ["family_sponsor_nationalities", "ID"],
      ["family_marriage_registered", "yes"],
      ["family_sponsor_confirmed", "yes"],
      ["stay_days", "365"],
    ],
    flags: [],
  },
  {
    name: "diaspora · dual — HELD: Indonesian dual citizenship, no corpus walk exercises it",
    category: "diaspora",
    tripScope: "single",
    branch: [
      ["diaspora_connection", "dual"],
      ["diaspora_documents", "yes"],
      ["sponsor_category", "FAMILY"],
      ["family_relation", "SPOUSE"],
      ["marital_status", "MARRIED"],
      ["family_sponsor_nationalities", "ID"],
      ["family_marriage_registered", "yes"],
      ["family_sponsor_confirmed", "yes"],
      ["stay_days", "365"],
    ],
    flags: ["ACTIVITY_BOUNDARY"],
  },
  {
    // NARROW-1 (owner ruling SHWEB-20260911, 2026-09-12): a foreign sponsor
    // used to raise AMBIGUOUS_SPONSOR for every relation, on the mere
    // presence of `family_sponsor_status_code`/`family_sponsor_permit_
    // basis`. `el.c1.tourism-family` (rulepack-prod-020) reads no sponsor
    // fact at all, so this deleted a verdict the flag could never affect —
    // the OVER-match this narrowing exists to cure. SPOUSE stands for
    // PARENT/CHILD/SIBLING/DEPENDENT/OTHER too: none of their pack products
    // gate on the sponsor fact with a real (non-NO_EFFECT) effect.
    name: "family · SPOUSE, foreign sponsor — FREED (NARROW-1): el.c1.tourism-family reads no sponsor fact",
    category: "family",
    tripScope: "single",
    branch: [
      ["sponsor_category", "FAMILY"],
      ["family_relation", "SPOUSE"],
      ["marital_status", "MARRIED"],
      ["family_sponsor_nationalities", "IT"],
      ["family_sponsor_status_code", "E23"],
      ["family_sponsor_permit_basis", "EXPERT"],
      ["family_marriage_registered", "yes"],
      ["family_sponsor_confirmed", "yes"],
      ["stay_days", "121"],
    ],
    flags: [],
  },
  {
    // D3-4's hold (STEPCHILD held on the sponsor's own KITAS/KITAP) was
    // REMOVED (owner ruling SHWEB-20260911, 2026-09-13, fresh grader
    // review): no pack requirement for the sponsor's own permit exists for
    // E31D (Permenkumham 11/2024 Pasal 33 ayat (2) huruf h names none for
    // E31D, unlike its E31E neighbour; Pasal 193 makes E31D's guarantor a
    // WNI, who cannot hold a KITAS/KITAP). The question itself is gone
    // (tree.ts), so this walk now FREES — same shape as the SPOUSE walk
    // above.
    name: "family · STEPCHILD, foreign sponsor — FREED (D3-4 hold removed): no pack rule reads the sponsor's own permit for E31D",
    category: "family",
    tripScope: "single",
    branch: [
      ["sponsor_category", "FAMILY"],
      ["family_relation", "STEPCHILD"],
      ["marital_status", "SINGLE"],
      ["family_sponsor_nationalities", "IT"],
      ["family_sponsor_status_code", "E23"],
      ["family_sponsor_permit_basis", "EXPERT"],
      ["family_stepchild_marriage_certificate_confirmed", "yes"],
      ["family_stepchild_birth_certificate_confirmed", "yes"],
      ["family_sponsor_confirmed", "yes"],
      ["stay_days", "121"],
    ],
    flags: [],
  },
  {
    name: "other · medical — HELD: no answer here reaches a fact a rule reads",
    category: "other",
    tripScope: "single",
    branch: [
      ["other_purpose", "medical"],
      ["other_paid_activity", "no"],
      // Inserted into the `other` branch by #5855.
      ["family_sponsor_confirmed", "yes"],
      ["stay_days", "30"],
      ["entry_pattern", "SINGLE"],
    ],
    flags: ["ACTIVITY_BOUNDARY"],
  },
  {
    // D3-2 changes the ENGINE-level route (`other_paid_activity=yes` now
    // asks the two employment facts `el.e23-employment-support` reads and
    // `mapPurposes` emits EMPLOYMENT alone), but `other_purpose` still holds
    // on the 7 values D4a did not release (spec: "holds on the
    // `other_purpose` values stay until each value is mapped") — so this
    // walk still holds, on the value `other_paid_activity` no longer
    // contributes to. `disclosed_review_flags` is a boundary flag, not a
    // per-cause list: removing one undecidable answer cannot un-hold a walk
    // that another undecidable answer already holds. Uses `medical`, not
    // `transit`: D4a (owner ruling SHWEB-20260911) released `transit` —
    // `mapPurposes` now maps it to a real, pack-decided purpose — so it can
    // no longer stand in for "an undecidable other_purpose value" here.
    // `sponsor_category` (PR-D4d) is now asked between `other_paid_activity`
    // and `work_payer` on this branch — the value is incidental to this
    // row's own concern (`other_purpose`'s hold), so `NONE` (the question's
    // first option) is used, same as the neutral rows above.
    name: "other · paid activity yes — engine reroutes to employment; other_purpose still holds",
    category: "other",
    tripScope: "single",
    branch: [
      ["other_purpose", "medical"],
      ["other_paid_activity", "yes"],
      ["sponsor_category", "NONE"],
      ["work_payer", "yes"],
      ["work_sponsor_confirmed", "yes"],
      ["stay_days", "30"],
      ["entry_pattern", "SINGLE"],
    ],
    flags: ["ACTIVITY_BOUNDARY"],
  },
];

describe("ACTIVITY_BOUNDARY — the walk census", () => {
  it.each(WALKS)("$name", (walk) => {
    expect(mapDisclosedReviewFlags(walkFacts(walk))).toEqual([...walk.flags]);
  });

  it("the freed employment walk reaches the WIRE with no disclosed flag", () => {
    // The consumer is the request body `mapOracleFactsToApplicantFacts` POSTs
    // to /visa-oracle/evaluate; `_apply_disclosed_review_flags` keys off
    // exactly this array, so an empty array is the whole difference between
    // "a specialist will review this" and the candidate the pack proved.
    const walk = WALKS.find((row) => row.category === "work");
    expect(walk).toBeDefined();
    const request = mapOracleFactsToApplicantFacts(walkFacts(walk!), {
      assessmentId: "11111111-1111-4111-8111-111111111111",
      collectedAt: new Date("2026-09-06T00:00:00.000Z"),
    });
    expect(request.disclosed_review_flags).toEqual([]);
  });
});

describe("ACTIVITY_BOUNDARY — the decision table itself", () => {
  const table = ACTIVITY_BOUNDARY_DECIDABLE_ANSWERS as Readonly<
    Record<string, readonly string[]>
  >;

  it("names only real questions, and only real option keys of those questions", () => {
    for (const [questionId, decidable] of Object.entries(table)) {
      const question = QUESTIONS[questionId];
      expect(question, `${questionId} is not registered`).toBeDefined();
      const keys = new Set(question.options.map((option) => option.key));
      for (const value of decidable) {
        expect(keys.has(value), `${questionId}: "${value}" is no option`).toBe(
          true,
        );
      }
    }
  });

  it("classifies every HUMAN_CONTEXT question — a new one must be filed, not defaulted", () => {
    const exempt: Readonly<Record<string, string>> = {
      holds_stay_permit: "routes to a signed fact, not to this flag",
      trip_scope: "raises MULTI_PURPOSE_TRIP",
      family_sponsor_status_code: "raises AMBIGUOUS_SPONSOR",
      family_sponsor_permit_basis: "raises AMBIGUOUS_SPONSOR",
      work_role: "engine-inert; owner ruling 2026-09-06 decision 6",
      // Engine-inert routing label added by #5855: it only chooses WHICH
      // evidence question follows, and the engine reads that evidence
      // (`secondhome.qualifying_property_value_usd` /
      // `secondhome.bank_deposit_usd`), never this label. Holding on it would
      // be raising the flag "for the mere fact that a question was answered",
      // which the table's own contract forbids. Not a judgement call:
      // MEASURED against production on 2026-09-07, `offshore/second_home/
      // property` returns SUPPORTED_CANDIDATES [E33] — classifying `property`
      // as undecidable would delete an E33 the signed pack had proven.
      secondhome_basis:
        "engine-inert routing label; the evidence carries the fact",
      // D3-3 (PR-D3): same shape as `secondhome_basis` above — this only
      // selects which evidence questions follow (`getCategoryQuestionIds`,
      // flow.ts); the engine reads that evidence, never this label.
      retirement_undecided_basis:
        "engine-inert routing label; the evidence carries the fact",
      // PR-D4c-2: same shape as `secondhome_basis`/`retirement_undecided_basis`
      // above — this only selects which amount question follows
      // (`investment_capital_idr` or `investment_amount_usd`,
      // `getCategoryQuestionIds` in flow.ts); the evidence question itself
      // carries the fact a rule could ever read, never this label.
      investment_currency:
        "engine-inert routing label; the evidence carries the fact",
    };
    for (const question of Object.values(QUESTIONS)) {
      if (question.decisionMapping.kind !== "HUMAN_CONTEXT") continue;
      expect(
        question.id in table || question.id in exempt,
        `${question.id} is HUMAN_CONTEXT but neither classified nor exempted`,
      ).toBe(true);
    }
  });

  it.each(Object.keys(ACTIVITY_BOUNDARY_DECIDABLE_ANSWERS))(
    "%s: every option either decides (no flag) or holds (flag)",
    (questionId) => {
      const decidable = new Set(table[questionId]);
      for (const option of QUESTIONS[questionId].options) {
        const flags = mapDisclosedReviewFlags({ [questionId]: option.key });
        expect(
          flags.includes("ACTIVITY_BOUNDARY"),
          `${questionId}=${option.key}`,
        ).toBe(!decidable.has(option.key));
      }
    },
  );

  it("fails CLOSED on an answer the table does not know", () => {
    // An option added to tree.ts later, or a tampered payload, must hold.
    expect(
      mapDisclosedReviewFlags({ business_activity: "acquiring-a-bank" }),
    ).toEqual(["ACTIVITY_BOUNDARY"]);
    expect(mapDisclosedReviewFlags({ retirement_basis: "unsure" })).toEqual([
      "ACTIVITY_BOUNDARY",
      "NOT_CERTAIN",
    ]);
  });

  it("never holds on a question it does not classify", () => {
    expect(mapDisclosedReviewFlags({ work_role: "executive" })).toEqual([]);
    // Both name question ids absent from tree.ts (pinned by tree.test.ts,
    // "does not carry the 2 dead legacy nodes"): unreachable code, not guards.
    expect(QUESTIONS.tourism_duration).toBeUndefined();
    expect(QUESTIONS.remote_income).toBeUndefined();
    expect(mapDisclosedReviewFlags({ tourism_duration: "short" })).toEqual([]);
    expect(mapDisclosedReviewFlags({ remote_income: "above" })).toEqual([]);
  });

  it("no longer holds on the bare category — released 2026-09-08, per-answer table governs now", () => {
    // The blanket `facts.category === "diaspora"` clause is gone: a diaspora
    // walk with no `diaspora_connection`/`diaspora_documents` answer yet
    // raises nothing, exactly like every other category — the table above,
    // not the category label, decides.
    expect(mapDisclosedReviewFlags({ category: "diaspora" })).toEqual([]);
    expect(mapDisclosedReviewFlags({ category: "business" })).toEqual([]);
  });
});
