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
      ["work_role", "specialist"],
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
      ["remote_employer_country", "US"],
      ["remote_pt_pma", "no"],
      ["stay_days", "365"],
    ],
    flags: [],
  },
  {
    name: "invest · property — HELD: a Second Home shape no purpose can be emitted for (§6 R3)",
    category: "invest",
    tripScope: "single",
    branch: [
      ["sponsor_category", "INVESTMENT"],
      ["investment_vehicle", "property"],
      ["secondhome_property_value_usd", "1200000"],
      ["stay_days", "730"],
    ],
    flags: ["ACTIVITY_BOUNDARY"],
  },
  {
    name: "retirement · property — HELD: §6 R3 measured the unflagged answer as a wrong NO_PATH",
    category: "retirement",
    tripScope: "single",
    branch: [
      ["sponsor_category", "NONE"],
      ["retirement_basis", "property"],
      ["secondhome_property_value_usd", "1200000"],
      ["stay_days", "365"],
    ],
    flags: ["ACTIVITY_BOUNDARY"],
  },
  {
    name: "diaspora — HELD: CATEGORY_TO_PURPOSE emits no purpose for it",
    category: "diaspora",
    tripScope: "single",
    branch: [
      ["diaspora_connection", "former_wni"],
      ["diaspora_documents", "yes"],
      ["stay_days", "365"],
    ],
    flags: ["ACTIVITY_BOUNDARY"],
  },
  {
    name: "other · medical — HELD: no answer here reaches a fact a rule reads",
    category: "other",
    tripScope: "single",
    branch: [
      ["other_purpose", "medical"],
      ["other_paid_activity", "no"],
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

  it("still holds the whole diaspora category, answers or not", () => {
    expect(mapDisclosedReviewFlags({ category: "diaspora" })).toEqual([
      "ACTIVITY_BOUNDARY",
    ]);
    expect(mapDisclosedReviewFlags({ category: "business" })).toEqual([]);
  });
});
