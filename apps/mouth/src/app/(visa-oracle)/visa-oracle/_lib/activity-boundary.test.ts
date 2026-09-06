import { describe, expect, it } from "vitest";
import {
  ACTIVITY_BOUNDARY_DECIDABLE_ANSWERS,
  mapDisclosedReviewFlags,
  mapOracleFactsToApplicantFacts,
} from "./fact-mapper";
import { flowReducer, initialFlowState, type FlowState } from "./flow";
import { QUESTIONS, type OracleFacts } from "./tree";

/**
 * ACTIVITY_BOUNDARY census — the table this PR narrows, asserted as a TABLE
 * and not as a predicate.
 *
 * Why a census and not "the mapper still compiles": any disclosed flag makes
 * the backend rewrite the decision to HUMAN_REVIEW_REQUIRED with
 * `candidates=()` (`evaluate_path.py::_apply_disclosed_review_flags`), so one
 * over-broad clause silently deletes an answer the signed pack had already
 * proven. Before this PR every `work` interview and every `business`
 * interview carried the flag, because `work_role` and `business_activity` are
 * asked unconditionally in those branches — measured, offshore/work:
 * `SUPPORTED_CANDIDATES [E23]` without the flag, `HUMAN_REVIEW_REQUIRED` with
 * it (research/visa/2026-09-06-visa-oracle-decisiveness-investigation.md
 * §2.1).
 *
 * Every walk below is driven through the REAL `flowReducer`, in the order the
 * real interview asks its questions — a hand-built fact bag could assert a
 * flag set no user can produce.
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

/** The offshore spine every walk below shares (same shape as
 * `flow.test.ts::startOffshore`), through to `review_gate: "none"`. */
function walkFacts(
  category: string,
  tripScope: string,
  branch: readonly (readonly [questionId: string, value: string])[],
): OracleFacts {
  let state = flowReducer(initialFlowState("en"), { type: "ADVANCE" });
  state = answer(state, "in_indonesia", "no");
  state = answer(state, "holds_stay_permit", "no");
  state = answer(state, "overstay_days", "0");
  state = answer(state, "nationalities", "IT");
  state = answer(state, "birth_date", "1990-02-03");
  state = answer(state, "category", category);
  state = answer(state, "trip_scope", tripScope);
  for (const [questionId, value] of branch) {
    state = answer(state, questionId, value);
  }
  state = answer(state, "review_gate", "none");
  return state.facts;
}

interface WalkCase {
  readonly name: string;
  readonly category: string;
  readonly tripScope: string;
  readonly branch: readonly (readonly [questionId: string, value: string])[];
  /** EXACT expected flag array — `mapDisclosedReviewFlags` sorts. */
  readonly flags: readonly string[];
  /** What the row is evidence of. */
  readonly because: string;
}

const WALKS: readonly WalkCase[] = [
  {
    name: "tourism · 30d · single",
    category: "tourism",
    tripScope: "single",
    branch: [
      ["stay_days", "30"],
      ["entry_pattern", "SINGLE"],
    ],
    flags: [],
    because: "no human-context answer in this branch — unchanged by this PR",
  },
  {
    name: "business · meetings · 14d",
    category: "business",
    tripScope: "single",
    branch: [
      ["business_activity", "meetings"],
      ["work_indonesia_compensation", "no"],
      ["stay_days", "14"],
      ["entry_pattern", "SINGLE"],
    ],
    flags: [],
    because:
      "NARROWED: ordinary BUSINESS_MEETINGS conduct the pack decides on purposes + stay_days",
  },
  {
    name: "business · negotiation · 14d",
    category: "business",
    tripScope: "single",
    branch: [
      ["business_activity", "negotiation"],
      ["work_indonesia_compensation", "no"],
      ["stay_days", "14"],
      ["entry_pattern", "SINGLE"],
    ],
    flags: [],
    because: "NARROWED, same reason",
  },
  {
    name: "business · conference · 14d",
    category: "business",
    tripScope: "single",
    branch: [
      ["business_activity", "conference"],
      ["work_indonesia_compensation", "no"],
      ["stay_days", "14"],
      ["entry_pattern", "SINGLE"],
    ],
    flags: [],
    because: "NARROWED, same reason",
  },
  {
    name: "business · training · 14d (still held)",
    category: "business",
    tripScope: "single",
    branch: [
      ["business_activity", "training"],
      ["work_indonesia_compensation", "no"],
      ["stay_days", "14"],
      ["entry_pattern", "SINGLE"],
    ],
    flags: ["ACTIVITY_BOUNDARY"],
    because:
      "KEPT: CL-D12-05 records that no activity.* fact discriminates training from a D12 shape",
  },
  {
    name: "business · other activity · 14d (still held)",
    category: "business",
    tripScope: "single",
    branch: [
      ["business_activity", "other"],
      ["work_indonesia_compensation", "no"],
      ["stay_days", "14"],
      ["entry_pattern", "SINGLE"],
    ],
    flags: ["ACTIVITY_BOUNDARY"],
    because: "KEPT: an unnamed activity is outside the signed vocabulary",
  },
  {
    name: "business · meetings · MULTI-purpose trip",
    category: "business",
    tripScope: "multiple",
    branch: [
      ["business_activity", "meetings"],
      ["work_indonesia_compensation", "no"],
      ["stay_days", "14"],
      ["entry_pattern", "MULTIPLE"],
    ],
    flags: ["MULTI_PURPOSE_TRIP"],
    because:
      "MULTI_PURPOSE_TRIP is out of scope for this PR and must survive the narrowing",
  },
  {
    name: "work · employer confirmed · 365d (the E23 witness)",
    category: "work",
    tripScope: "single",
    branch: [
      ["sponsor_category", "EMPLOYER"],
      ["work_payer", "yes"],
      ["work_indonesia_compensation", "yes"],
      ["work_sponsor_confirmed", "yes"],
      ["work_role", "specialist"],
      ["stay_days", "365"],
    ],
    flags: [],
    because:
      "NARROWED (owner ruling, decision 6): work_role is engine-inert and its flag suppressed E23 for 100% of employment interviews",
  },
  {
    name: "invest · PT PMA · 730d",
    category: "invest",
    tripScope: "single",
    branch: [
      ["sponsor_category", "INVESTMENT"],
      ["investment_vehicle", "pt_pma"],
      ["investment_pt_pma", "yes"],
      ["investment_capital_idr", "1000000000"],
      ["investment_paid_up_capital_idr", "500000000"],
      ["investment_role", "SHAREHOLDER_DIRECTOR"],
      ["stay_days", "730"],
    ],
    flags: [],
    because: "unchanged: pt_pma was already the one decidable vehicle",
  },
  {
    name: "invest · property · 730d (still held)",
    category: "invest",
    tripScope: "single",
    branch: [
      ["sponsor_category", "INVESTMENT"],
      ["investment_vehicle", "property"],
      ["secondhome_property_value_usd", "1200000"],
      ["stay_days", "730"],
    ],
    flags: ["ACTIVITY_BOUNDARY"],
    because:
      "KEPT: a Second Home shape CATEGORY_TO_PURPOSE cannot emit SECOND_HOME for (§6 R3)",
  },
  {
    name: "remote · foreign clients · 365d",
    category: "remote",
    tripScope: "single",
    branch: [
      ["sponsor_category", "NONE"],
      ["remote_clients", "foreign"],
      ["remote_compensation", "no"],
      ["remote_employer_country", "US"],
      ["remote_pt_pma", "no"],
      ["stay_days", "365"],
    ],
    flags: [],
    because:
      "the deleted `remote_income` clause named a question tree.ts does not have — no walk could ever set it",
  },
  {
    name: "family · spouse · registered · 365d",
    category: "family",
    tripScope: "single",
    branch: [
      ["sponsor_category", "INDIVIDUAL"],
      ["family_relation", "SPOUSE"],
      ["marital_status", "MARRIED"],
      ["family_sponsor_nationalities", "ID"],
      ["family_marriage_registered", "yes"],
      ["family_sponsor_confirmed", "yes"],
      ["stay_days", "365"],
    ],
    flags: [],
    because: "no human-context answer in this branch — unchanged",
  },
  {
    name: "retirement · passive income · 365d",
    category: "retirement",
    tripScope: "single",
    branch: [
      ["sponsor_category", "NONE"],
      ["retirement_basis", "passive_income"],
      ["secondhome_passive_income_usd", "3000"],
      ["family_sponsor_confirmed", "yes"],
      ["stay_days", "365"],
    ],
    flags: [],
    because: "unchanged: passive_income is the E33F route the pack decides",
  },
  {
    name: "retirement · property · 365d (still held)",
    category: "retirement",
    tripScope: "single",
    branch: [
      ["sponsor_category", "NONE"],
      ["retirement_basis", "property"],
      ["secondhome_property_value_usd", "1200000"],
      ["stay_days", "365"],
    ],
    flags: ["ACTIVITY_BOUNDARY"],
    because: "KEPT: §6 R3 measured the unflagged answer as a wrong NO_PATH",
  },
  {
    name: "study · postgraduate · 365d",
    category: "study",
    tripScope: "single",
    branch: [
      ["sponsor_category", "EDUCATION"],
      ["study_level", "POSTGRADUATE"],
      ["study_admission_confirmed", "yes"],
      ["study_sponsor_confirmed", "yes"],
      ["stay_days", "365"],
    ],
    flags: [],
    because: "no human-context answer in this branch — unchanged",
  },
  {
    name: "diaspora · former WNI · 365d (still held)",
    category: "diaspora",
    tripScope: "single",
    branch: [
      ["diaspora_connection", "former_wni"],
      ["diaspora_documents", "yes"],
      ["stay_days", "365"],
    ],
    flags: ["ACTIVITY_BOUNDARY"],
    because:
      "KEPT: CATEGORY_TO_PURPOSE emits no purpose for diaspora, so the walk is undecidable until the routing exists",
  },
  {
    name: "other · medical · 30d (still held)",
    category: "other",
    tripScope: "single",
    branch: [
      ["other_purpose", "medical"],
      ["other_paid_activity", "no"],
      ["stay_days", "30"],
      ["entry_pattern", "SINGLE"],
    ],
    flags: ["ACTIVITY_BOUNDARY"],
    because: "KEPT: no answer in the other branch reaches a fact a rule reads",
  },
];

describe("ACTIVITY_BOUNDARY — the walk census", () => {
  it.each(WALKS)("$name", ({ category, tripScope, branch, flags }) => {
    expect(
      mapDisclosedReviewFlags(walkFacts(category, tripScope, branch)),
    ).toEqual([...flags]);
  });

  it("covers all ten interview categories", () => {
    expect(new Set(WALKS.map((walk) => walk.category)).size).toBe(10);
  });

  it("every row states what it is evidence of", () => {
    for (const walk of WALKS) {
      expect(walk.because.length, walk.name).toBeGreaterThan(20);
    }
  });

  it("the freed walks reach the WIRE with no disclosed flag at all", () => {
    // The consumer is the request body `mapOracleFactsToApplicantFacts` POSTs
    // to /visa-oracle/evaluate — asserting the mapper helper alone would not
    // prove the payload changed. `_apply_disclosed_review_flags` keys off
    // exactly this array, so an empty array is the whole difference between
    // "a specialist will review this" and the candidate the pack proved.
    const employmentWalk = WALKS.find((walk) =>
      walk.name.startsWith("work · employer confirmed"),
    );
    expect(employmentWalk).toBeDefined();
    const request = mapOracleFactsToApplicantFacts(
      walkFacts(
        employmentWalk!.category,
        employmentWalk!.tripScope,
        employmentWalk!.branch,
      ),
      {
        assessmentId: "11111111-1111-4111-8111-111111111111",
        collectedAt: new Date("2026-09-06T00:00:00.000Z"),
      },
    );
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
      expect(
        question,
        `${questionId} is not a registered question`,
      ).toBeDefined();
      const optionKeys = new Set(question.options.map((option) => option.key));
      for (const value of decidable) {
        expect(
          optionKeys.has(value),
          `${questionId}: "${value}" is not one of its options`,
        ).toBe(true);
      }
    }
  });

  it("classifies every HUMAN_CONTEXT question — a new one must be filed, not defaulted", () => {
    // The exemptions are the questions that raise a DIFFERENT flag, or none.
    // Adding a HUMAN_CONTEXT question without touching either list fails here,
    // which is the point: the table is the only place this flag is decided.
    const exempt: Readonly<Record<string, string>> = {
      holds_stay_permit: "resolves to a signed fact via mapCurrentStatusExpiry",
      trip_scope: "raises MULTI_PURPOSE_TRIP, not ACTIVITY_BOUNDARY",
      family_sponsor_status_code: "raises AMBIGUOUS_SPONSOR",
      family_sponsor_permit_basis: "raises AMBIGUOUS_SPONSOR",
      work_role:
        "engine-inert HUMAN_CONTEXT; owner ruling 2026-09-06 decision 6 stopped flagging it",
    };
    for (const question of Object.values(QUESTIONS)) {
      if (question.decisionMapping.kind !== "HUMAN_CONTEXT") continue;
      const classified = question.id in table || question.id in exempt;
      expect(
        classified,
        `${question.id} is HUMAN_CONTEXT but is neither in the ACTIVITY_BOUNDARY table nor exempted`,
      ).toBe(true);
    }
  });

  it.each(Object.keys(ACTIVITY_BOUNDARY_DECIDABLE_ANSWERS))(
    "%s: every option is either decidable (no flag) or held (flag) — guilt and innocence per option",
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
    // The direction that matters: an option added to tree.ts later, or a
    // tampered payload, holds instead of slipping through unflagged.
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
    // Both name question ids that do not exist in tree.ts (pinned dead by
    // tree.test.ts, "does not carry the 2 dead legacy nodes"), so their
    // deleted clauses were unreachable code, not a live guard.
    expect(QUESTIONS.tourism_duration).toBeUndefined();
    expect(QUESTIONS.remote_income).toBeUndefined();
    expect(mapDisclosedReviewFlags({ tourism_duration: "short" })).toEqual([]);
    expect(mapDisclosedReviewFlags({ remote_income: "above" })).toEqual([]);
  });

  it("still holds the whole diaspora category, answers or not", () => {
    expect(mapDisclosedReviewFlags({ category: "diaspora" })).toEqual([
      "ACTIVITY_BOUNDARY",
    ]);
    expect(mapDisclosedReviewFlags({ category: "business" })).toEqual([]);
  });
});
