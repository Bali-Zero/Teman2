import { describe, expect, it } from "vitest";
import { CATEGORY_KEYS, getLane, QUESTIONS, type OracleFacts } from "./tree";
import {
  INTERVIEW_SNAPSHOT_SCHEMA_VERSION,
  computeNextNode,
  createInterviewSnapshot,
  flowReducer,
  getCategoryQuestionIds,
  getTreeSteps,
  initialFlowState,
  isEditableTreeStep,
  restoreInterviewSnapshot,
  type FlowState,
} from "./flow";

function reduce(
  state: FlowState,
  action: Parameters<typeof flowReducer>[1],
): FlowState {
  return flowReducer(state, action);
}

function expectQuestion(state: FlowState, questionId: string): void {
  expect(state.history[state.history.length - 1]).toEqual({
    kind: "question",
    questionId,
  });
}

function answer(
  state: FlowState,
  questionId: string,
  value: string,
): FlowState {
  expectQuestion(state, questionId);
  return reduce(state, { type: "ANSWER", questionId, value });
}

function startOffshore(category?: string): FlowState {
  let state = initialFlowState("en");
  state = reduce(state, { type: "ADVANCE" });
  state = answer(state, "in_indonesia", "no");
  // Offshore now asks a single permit-status gate question before
  // converging (fixed 2026-08-24, D12 offshore-reachability P0, then
  // re-fixed same day after a funnel-cost review — see `computeNextNode`'s
  // `in_indonesia`/`holds_stay_permit` cases). "no" here converges
  // straight to `overstay_days` with no further questions (the fact
  // resolves from this answer alone via `fact-mapper.ts`'s synthesized
  // `NO_STAY_PERMIT`) — preserved here to keep every downstream test's
  // original intent (none of them are about permit status).
  state = answer(state, "holds_stay_permit", "no");
  state = answer(state, "overstay_days", "0");
  state = answer(state, "nationalities", "IT");
  state = answer(state, "birth_date", "1990-02-03");
  if (category) state = answer(state, "category", category);
  return state;
}

const CATEGORY_CASES: ReadonlyArray<{
  category: (typeof CATEGORY_KEYS)[number];
  branch: readonly [questionId: string, value: string][];
}> = [
  {
    category: "tourism",
    branch: [
      ["stay_days", "30"],
      ["entry_pattern", "SINGLE"],
    ],
  },
  {
    category: "business",
    branch: [
      ["business_activity", "meetings"],
      ["work_indonesia_compensation", "no"],
      ["stay_days", "14"],
      ["entry_pattern", "SINGLE"],
    ],
  },
  {
    category: "work",
    branch: [
      ["sponsor_category", "EMPLOYER"],
      ["work_payer", "yes"],
      ["work_indonesia_compensation", "yes"],
      ["work_sponsor_confirmed", "yes"],
      ["work_role", "specialist"],
      ["stay_days", "365"],
    ],
  },
  {
    category: "invest",
    branch: [
      ["sponsor_category", "INVESTMENT"],
      ["investment_vehicle", "pt_pma"],
      ["investment_product_code", "STANDARD"],
      ["investment_pt_pma", "yes"],
      ["investment_capital_idr", "1000000000"],
      ["investment_paid_up_capital_idr", "500000000"],
      ["investment_role", "SHAREHOLDER_DIRECTOR"],
      ["stay_days", "730"],
    ],
  },
  {
    category: "remote",
    branch: [
      ["sponsor_category", "NONE"],
      ["remote_clients", "foreign"],
      ["remote_compensation", "no"],
      ["remote_employer_country", "US"],
      ["remote_pt_pma", "no"],
      ["stay_days", "365"],
    ],
  },
  {
    category: "family",
    branch: [
      ["sponsor_category", "INDIVIDUAL"],
      ["family_relation", "SPOUSE"],
      ["marital_status", "MARRIED"],
      ["family_sponsor_nationalities", "ID"],
      ["family_marriage_registered", "yes"],
      ["family_sponsor_confirmed", "yes"],
      ["stay_days", "365"],
    ],
  },
  {
    category: "retirement",
    branch: [
      ["sponsor_category", "NONE"],
      ["retirement_basis", "passive_income"],
      ["secondhome_passive_income_usd", "3000"],
      ["family_sponsor_confirmed", "yes"],
      ["stay_days", "365"],
    ],
  },
  {
    category: "study",
    branch: [
      ["sponsor_category", "EDUCATION"],
      ["study_level", "POSTGRADUATE"],
      ["study_admission_confirmed", "yes"],
      ["study_sponsor_confirmed", "yes"],
      ["stay_days", "365"],
    ],
  },
  {
    category: "diaspora",
    branch: [
      ["diaspora_connection", "former_wni"],
      ["diaspora_documents", "yes"],
      ["stay_days", "365"],
    ],
  },
  {
    category: "other",
    branch: [
      ["other_purpose", "medical"],
      ["other_paid_activity", "no"],
      ["stay_days", "30"],
      ["entry_pattern", "SINGLE"],
    ],
  },
];

describe("the ten behavioral interview branches", () => {
  it.each(CATEGORY_CASES)(
    "$category reaches review and confirmation without a dead end",
    ({ category, branch }) => {
      let state = startOffshore(category);
      state = answer(state, "trip_scope", "single");
      for (const [questionId, value] of branch) {
        state = answer(state, questionId, value);
      }
      expectQuestion(state, "review_gate");
      state = answer(state, "review_gate", "none");
      expect(state.history[state.history.length - 1]).toEqual({
        kind: "confirmation",
      });
      state = reduce(state, { type: "ADVANCE" });
      expect(state.history[state.history.length - 1]).toEqual({
        kind: "verdict",
      });
    },
  );

  it("covers exactly the ten category keys", () => {
    expect(CATEGORY_CASES.map(({ category }) => category)).toEqual(
      CATEGORY_KEYS,
    );
  });

  it("uses only registered questions in every branch", () => {
    for (const { category, branch } of CATEGORY_CASES) {
      const facts = Object.fromEntries(branch) as OracleFacts;
      const ids = getCategoryQuestionIds({ ...facts, category });
      expect(ids.every((id) => QUESTIONS[id] !== undefined)).toBe(true);
    }
  });
});

describe("retirement evidence branches", () => {
  it.each([
    [
      "bank_deposit",
      [
        "sponsor_category",
        "retirement_basis",
        "secondhome_deposit_usd",
        "secondhome_state_bank",
        "secondhome_own_name",
        "secondhome_passive_income_usd",
        "stay_days",
      ],
    ],
    [
      "passive_income",
      [
        "sponsor_category",
        "retirement_basis",
        "secondhome_passive_income_usd",
        "family_sponsor_confirmed",
        "stay_days",
      ],
    ],
    [
      "family_sponsor",
      [
        "sponsor_category",
        "retirement_basis",
        "secondhome_passive_income_usd",
        "family_sponsor_confirmed",
        "stay_days",
      ],
    ],
  ] as const)(
    "%s collects every fact needed before review",
    (retirementBasis, expectedQuestionIds) => {
      expect(
        getCategoryQuestionIds({
          category: "retirement",
          retirement_basis: retirementBasis,
        }),
      ).toEqual(expectedQuestionIds);
    },
  );

  it.each([
    {
      basis: "bank_deposit",
      answers: [
        ["secondhome_deposit_usd", "100000"],
        ["secondhome_state_bank", "yes"],
        ["secondhome_own_name", "yes"],
        ["secondhome_passive_income_usd", "3000"],
        ["stay_days", "365"],
      ],
    },
    {
      basis: "passive_income",
      answers: [
        ["secondhome_passive_income_usd", "3000"],
        ["family_sponsor_confirmed", "yes"],
        ["stay_days", "365"],
      ],
    },
    {
      basis: "family_sponsor",
      answers: [
        ["secondhome_passive_income_usd", "3000"],
        ["family_sponsor_confirmed", "yes"],
        ["stay_days", "365"],
      ],
    },
  ] as const)(
    "$basis reaches the review gate without a dead end",
    ({ basis, answers }) => {
      let state = startOffshore("retirement");
      state = answer(state, "trip_scope", "single");
      state = answer(state, "sponsor_category", "NONE");
      state = answer(state, "retirement_basis", basis);
      for (const [questionId, value] of answers) {
        state = answer(state, questionId, value);
      }
      expectQuestion(state, "review_gate");
    },
  );

  it("prunes deposit evidence when the retirement basis changes", () => {
    let state = startOffshore("retirement");
    state = answer(state, "trip_scope", "single");
    state = answer(state, "sponsor_category", "NONE");
    state = answer(state, "retirement_basis", "bank_deposit");
    state = answer(state, "secondhome_deposit_usd", "100000");
    state = answer(state, "secondhome_state_bank", "yes");
    state = answer(state, "secondhome_own_name", "yes");
    state = answer(state, "secondhome_passive_income_usd", "3000");

    state = reduce(state, {
      type: "EDIT",
      questionId: "retirement_basis",
    });
    state = answer(state, "retirement_basis", "family_sponsor");

    expect(state.facts.secondhome_deposit_usd).toBeUndefined();
    expect(state.facts.secondhome_state_bank).toBeUndefined();
    expect(state.facts.secondhome_own_name).toBeUndefined();
    expect(state.facts.secondhome_passive_income_usd).toBeUndefined();
    expectQuestion(state, "secondhome_passive_income_usd");
  });
});

describe("onshore/offshore canonical fact collection", () => {
  it("collects exact onshore status, active overstay and application channel", () => {
    let state = initialFlowState("en");
    state = reduce(state, { type: "ADVANCE" });
    state = answer(state, "in_indonesia", "yes");
    state = answer(state, "permit_expiry", "2026-09-01");
    state = answer(state, "holds_stay_permit", "no");
    state = answer(state, "current_status_code", "C1");
    state = answer(state, "overstay_days", "0");
    state = answer(state, "wants_onshore_conversion", "yes");
    state = answer(state, "application_channel", "ONSHORE_CONVERSION");
    expectQuestion(state, "nationalities");
    expect(state.facts).toMatchObject({
      current_status_code: "C1",
      overstay_days: "0",
      wants_onshore_conversion: "yes",
      application_channel: "ONSHORE_CONVERSION",
    });
  });

  it("offshore + holds a permit: gates on holds_stay_permit first, then asks the full chain, then converges", () => {
    // Fixed 2026-08-24 (D12 offshore-reachability P0, then re-fixed same
    // day after a funnel-cost review): before the P0 fix, "no" skipped
    // straight to overstay_days, so an offshore applicant's
    // current-status/permit facts could never be collected — including
    // the exact person the D12 owner ruling names (someone abroad holding
    // an unlapsed KITAS). The first fix mirrored the onshore order
    // unconditionally (permit_expiry asked before knowing whether the
    // applicant even holds a permit); this version gates on
    // holds_stay_permit FIRST for offshore instead, to avoid paying the
    // full chain for applicants who don't hold one (see the sibling test
    // below). wants_onshore_conversion/application_channel remain
    // onshore-only, unchanged by this fix.
    let state = initialFlowState("en");
    state = reduce(state, { type: "ADVANCE" });
    state = answer(state, "in_indonesia", "no");
    expectQuestion(state, "holds_stay_permit");
    state = answer(state, "holds_stay_permit", "yes");
    expectQuestion(state, "permit_expiry");
    state = answer(state, "permit_expiry", "2026-09-01");
    expectQuestion(state, "stay_permit_code");
    state = answer(state, "stay_permit_code", "E28A");
    expectQuestion(state, "overstay_days");
    state = answer(state, "overstay_days", "0");
    expectQuestion(state, "nationalities");
    expect(state.facts.stay_permit_code).toBe("E28A");
    expect(state.facts.application_channel).toBeUndefined();
  });

  it("offshore + no permit: converges on overstay_days after exactly one gate question, no code/expiry asked", () => {
    // The funnel-cost half of the same 2026-08-24 fix: an offshore
    // applicant who does not hold a permit pays exactly ONE extra
    // question (holds_stay_permit itself), not the full 3-question
    // chain — permit_expiry/stay_permit_code/current_status_code are
    // never reached at all. Reachability of
    // derived.has_active_stay_permit from this path (the synthesized
    // NO_STAY_PERMIT sentinel resolving to a definite False) is proven
    // at the backend in fact-mapper.test.ts and
    // test_d12_active_stay_permit_exclusion.py, not here — this test
    // only proves the frontend never asks the redundant questions.
    let state = initialFlowState("en");
    state = reduce(state, { type: "ADVANCE" });
    state = answer(state, "in_indonesia", "no");
    expectQuestion(state, "holds_stay_permit");
    state = answer(state, "holds_stay_permit", "no");
    expectQuestion(state, "overstay_days");
    state = answer(state, "overstay_days", "0");
    expectQuestion(state, "nationalities");
    expect(state.facts.permit_expiry).toBeUndefined();
    expect(state.facts.stay_permit_code).toBeUndefined();
    expect(state.facts.current_status_code).toBeUndefined();
    expect(state.facts.application_channel).toBeUndefined();
  });

  it("records unknown current status without substituting a code", () => {
    let state = initialFlowState("en");
    state = reduce(state, { type: "ADVANCE" });
    state = answer(state, "in_indonesia", "yes");
    state = answer(state, "permit_expiry", "2026-09-01");
    state = answer(state, "holds_stay_permit", "no");
    expectQuestion(state, "current_status_code");
    state = reduce(state, { type: "SKIP", questionId: "current_status_code" });
    expect(state.facts.current_status_code).toBe("unsure");
    expectQuestion(state, "overstay_days");
  });

  it.each([
    [0, "urgent"],
    [1, "urgent"],
    [2, "urgent"],
    [60, "extend"],
    [61, "planning"],
  ] as const)("keeps %i permit days in the %s display lane", (days, lane) => {
    const today = new Date(2026, 6, 17, 12);
    const expiry = new Date(2026, 6, 17 + days, 12);
    const iso = `${expiry.getFullYear()}-${String(expiry.getMonth() + 1).padStart(2, "0")}-${String(expiry.getDate()).padStart(2, "0")}`;
    expect(getLane({ in_indonesia: "yes", permit_expiry: iso }, today)).toBe(
      lane,
    );
  });

  it("never derives active overstay days from an expired permit date", () => {
    const next = computeNextNode(
      { kind: "question", questionId: "permit_expiry" },
      { in_indonesia: "yes", permit_expiry: "2020-01-01" },
    );
    // permit_expiry always advances to the holds_stay_permit gate now
    // (never straight to overstay_days) — an expired date does not
    // short-circuit the interview into treating the applicant as already
    // out of status without asking what they currently hold.
    expect(next).toEqual({
      kind: "question",
      questionId: "holds_stay_permit",
    });
  });
});

describe("renewal_paid gating (F4, 2026-08-24 owner ruling)", () => {
  it("is reached for an onshore expired-permit path", () => {
    let state = initialFlowState("en");
    state = reduce(state, { type: "ADVANCE" });
    state = answer(state, "in_indonesia", "yes");
    state = answer(state, "permit_expiry", "2020-01-01");
    state = answer(state, "holds_stay_permit", "yes");
    state = answer(state, "stay_permit_code", "E28A");
    expectQuestion(state, "renewal_paid");
    state = answer(state, "renewal_paid", "yes");
    expectQuestion(state, "overstay_days");
    expect(state.facts.renewal_paid).toBe("yes");
  });

  it("is reached for an onshore not-sure-expiry path", () => {
    let state = initialFlowState("en");
    state = reduce(state, { type: "ADVANCE" });
    state = answer(state, "in_indonesia", "yes");
    state = answer(state, "permit_expiry", "unsure");
    state = answer(state, "holds_stay_permit", "yes");
    state = answer(state, "stay_permit_code", "E28A");
    expectQuestion(state, "renewal_paid");
  });

  it("is reached for an offshore expired-permit path", () => {
    let state = initialFlowState("en");
    state = reduce(state, { type: "ADVANCE" });
    state = answer(state, "in_indonesia", "no");
    state = answer(state, "holds_stay_permit", "yes");
    state = answer(state, "permit_expiry", "2020-01-01");
    state = answer(state, "stay_permit_code", "E28A");
    expectQuestion(state, "renewal_paid");
  });

  it("is NOT reached for a known-current permit (onshore)", () => {
    const next = computeNextNode(
      { kind: "question", questionId: "stay_permit_code" },
      {
        in_indonesia: "yes",
        permit_expiry: "2099-01-01",
        holds_stay_permit: "yes",
        stay_permit_code: "E28A",
      },
      new Date(2026, 7, 24),
    );
    expect(next).toEqual({ kind: "question", questionId: "overstay_days" });
  });

  it("is NOT reached when no stay permit is held (current_status_code branch never routes here)", () => {
    const next = computeNextNode(
      { kind: "question", questionId: "current_status_code" },
      {
        in_indonesia: "yes",
        permit_expiry: "2020-01-01",
        holds_stay_permit: "no",
        current_status_code: "C1",
      },
      new Date(2026, 7, 24),
    );
    expect(next).toEqual({ kind: "question", questionId: "overstay_days" });
  });
});

/**
 * `wants_onshore_conversion` and `application_channel` describe the SAME
 * real-world fact from two angles. Left uncross-checked, `false` +
 * `ONSHORE_CONVERSION` disarms the safety-critical hard filter
 * `hf.d12-onshore-conversion-excluded` (which reads only
 * `process.wants_onshore_conversion`) while the channel that actually
 * describes the applicant's real intent sits unread by every rule in the
 * pack — D12 got recommended as if the applicant were applying from
 * offshore. `channelConflictsWithOnshoreIntent` in flow.ts is the fix:
 * the reducer refuses to record a contradictory `application_channel`
 * answer at all, rather than deriving or silently overwriting either fact.
 */
describe("wants_onshore_conversion / application_channel cross-validation (2026-08-23)", () => {
  function reachApplicationChannel(wantsOnshoreConversion: string): FlowState {
    let state = initialFlowState("en");
    state = reduce(state, { type: "ADVANCE" });
    state = answer(state, "in_indonesia", "yes");
    state = answer(state, "permit_expiry", "2026-09-01");
    state = answer(state, "holds_stay_permit", "no");
    state = answer(state, "current_status_code", "C1");
    state = answer(state, "overstay_days", "0");
    state = answer(state, "wants_onshore_conversion", wantsOnshoreConversion);
    expectQuestion(state, "application_channel");
    return state;
  }

  /**
   * The FULL cross product, enumerated rather than sampled: 3
   * `wants_onshore_conversion` values × 4 `application_channel` values =
   * 12 combinations, 3 of them contradictory. Sampling risks the exact
   * failure mode a guard like this can hide — a widened check (here,
   * `yes + OFFSHORE` was added beyond the originally-measured leak) is
   * precisely where a false positive on an honest, coherent answer would
   * live undetected. Every one of the other 9 is asserted to pass, not
   * merely a representative few.
   */
  const WANTS_VALUES = ["yes", "no", "unsure"] as const;
  const CHANNEL_VALUES = [
    "OFFSHORE",
    "ONSHORE_CONVERSION",
    "STATUS_BRIDGING",
    "unsure",
  ] as const;
  const BLOCKED_PAIRS = new Set([
    "no|ONSHORE_CONVERSION",
    "no|STATUS_BRIDGING",
    "yes|OFFSHORE",
  ]);
  const FULL_CROSS_PRODUCT = WANTS_VALUES.flatMap((wants) =>
    CHANNEL_VALUES.map(
      (channel) =>
        [wants, channel, BLOCKED_PAIRS.has(`${wants}|${channel}`)] as const,
    ),
  );

  it("the cross product table itself covers exactly 12 combinations, 3 blocked and 9 passing", () => {
    expect(FULL_CROSS_PRODUCT).toHaveLength(12);
    expect(FULL_CROSS_PRODUCT.filter(([, , blocked]) => blocked)).toHaveLength(
      3,
    );
    expect(FULL_CROSS_PRODUCT.filter(([, , blocked]) => !blocked)).toHaveLength(
      9,
    );
  });

  it.each(FULL_CROSS_PRODUCT)(
    "wants_onshore_conversion=%s + application_channel=%s -> blocked=%s",
    (wants, channel, shouldBlock) => {
      const before = reachApplicationChannel(wants);
      const after = reduce(before, {
        type: "ANSWER",
        questionId: "application_channel",
        value: channel,
      });
      if (shouldBlock) {
        // GUILT: still parked on the same question, the fact never
        // recorded, neither answer touched or overwritten.
        expectQuestion(after, "application_channel");
        expect(after.facts.application_channel).toBeUndefined();
        expect(after.facts.wants_onshore_conversion).toBe(wants);
        expect(after.blockedAnswer).toEqual({
          questionId: "application_channel",
          conflictsWithQuestionId: "wants_onshore_conversion",
        });
      } else {
        // INNOCENCE: advances untouched, both facts recorded exactly as
        // answered, no block set.
        expectQuestion(after, "nationalities");
        expect(after.facts.wants_onshore_conversion).toBe(wants);
        expect(after.facts.application_channel).toBe(channel);
        expect(after.blockedAnswer).toBeNull();
      }
    },
  );

  describe("guilt: every contradictory pair is blocked", () => {
    it("the exact measured production leak never reaches facts: false + ONSHORE_CONVERSION", () => {
      const before = reachApplicationChannel("no");
      const after = reduce(before, {
        type: "ANSWER",
        questionId: "application_channel",
        value: "ONSHORE_CONVERSION",
      });
      expect(after.facts.application_channel).toBeUndefined();
      expect(after.facts.wants_onshore_conversion).toBe("no");
      expectQuestion(after, "application_channel");
    });

    it("picking a different, coherent channel after a blocked attempt clears the block and advances", () => {
      const blocked = reduce(reachApplicationChannel("no"), {
        type: "ANSWER",
        questionId: "application_channel",
        value: "ONSHORE_CONVERSION",
      });
      expect(blocked.blockedAnswer).not.toBeNull();

      const recovered = answer(blocked, "application_channel", "OFFSHORE");
      expect(recovered.blockedAnswer).toBeNull();
      expect(recovered.facts.application_channel).toBe("OFFSHORE");
      expectQuestion(recovered, "nationalities");
    });

    it("going Back to correct wants_onshore_conversion instead also clears the block", () => {
      const blocked = reduce(reachApplicationChannel("no"), {
        type: "ANSWER",
        questionId: "application_channel",
        value: "ONSHORE_CONVERSION",
      });
      const backed = reduce(blocked, { type: "BACK" });
      expect(backed.blockedAnswer).toBeNull();
      expectQuestion(backed, "wants_onshore_conversion");
    });
  });

  describe("innocence: 'unsure' on either side is never treated as a conflict", () => {
    it("an unsure wants_onshore_conversion accepts any application_channel", () => {
      const before = reachApplicationChannel("unsure");
      const after = answer(before, "application_channel", "ONSHORE_CONVERSION");
      expectQuestion(after, "nationalities");
      expect(after.facts.wants_onshore_conversion).toBe("unsure");
      expect(after.facts.application_channel).toBe("ONSHORE_CONVERSION");
      expect(after.blockedAnswer).toBeNull();
    });

    it("skipping application_channel (unsure) is accepted regardless of wants_onshore_conversion", () => {
      const before = reachApplicationChannel("no");
      const after = reduce(before, {
        type: "SKIP",
        questionId: "application_channel",
      });
      expectQuestion(after, "nationalities");
      expect(after.facts.application_channel).toBe("unsure");
      expect(after.blockedAnswer).toBeNull();
    });
  });

  it("innocence: in_indonesia=no skips both questions entirely — no false trigger", () => {
    const state = startOffshore();
    expect(state.facts.wants_onshore_conversion).toBeUndefined();
    expect(state.facts.application_channel).toBeUndefined();
    expect(state.blockedAnswer).toBeNull();
  });
});

describe("seq-10 companion: the marriage question fires for PARENT-relation family interviews", () => {
  // Kimi refuter finding 1 (2026-08-19): E31C's engine rules require the
  // PARENTS' registered marriage, but this question only fired for SPOUSE —
  // every PARENT-relation interview shipped `family.marriage_registered`
  // UNKNOWN by construction, so the seq-10 HARD_FILTER would dead-end those
  // applicants in NEEDS_INPUT with no way to ever answer the question.
  it("asks family_marriage_registered when the sponsor is a parent", () => {
    const ids = getCategoryQuestionIds({
      category: "family",
      family_relation: "PARENT",
    } as OracleFacts);
    expect(ids).toContain("family_marriage_registered");
  });

  it("still asks it for SPOUSE, and not for CHILD (innocence)", () => {
    expect(
      getCategoryQuestionIds({
        category: "family",
        family_relation: "SPOUSE",
      } as OracleFacts),
    ).toContain("family_marriage_registered");
    expect(
      getCategoryQuestionIds({
        category: "family",
        family_relation: "CHILD",
      } as OracleFacts),
    ).not.toContain("family_marriage_registered");
  });
});

describe("2026-08-23 owner ruling: family_sponsor_permit_basis rides the same condition as family_sponsor_status_code", () => {
  it("guilt: asks it when the sponsor's nationalities exclude ID", () => {
    const ids = getCategoryQuestionIds({
      category: "family",
      family_sponsor_nationalities: "US",
    } as OracleFacts);
    expect(ids).toContain("family_sponsor_status_code");
    expect(ids).toContain("family_sponsor_permit_basis");
  });

  it("innocence: does not ask it when the sponsor is Indonesian", () => {
    const ids = getCategoryQuestionIds({
      category: "family",
      family_sponsor_nationalities: "ID",
    } as OracleFacts);
    expect(ids).not.toContain("family_sponsor_status_code");
    expect(ids).not.toContain("family_sponsor_permit_basis");
  });

  it("innocence: does not ask it before the nationalities question is answered", () => {
    const ids = getCategoryQuestionIds({
      category: "family",
    } as OracleFacts);
    expect(ids).not.toContain("family_sponsor_permit_basis");
  });
});

describe("2026-08-23 owner ruling: stepchild evidence questions fire only for family_relation=STEPCHILD", () => {
  // research/visa/2026-08-15-gold-family-refuter.md diagnosed E31D's rules
  // as reducible to bare `intent.purposes ∩ FAMILY` — the interview never
  // had a way to collect either evidence fact this ruling names.
  it("guilt: asks both evidence questions for STEPCHILD", () => {
    const ids = getCategoryQuestionIds({
      category: "family",
      family_relation: "STEPCHILD",
    } as OracleFacts);
    expect(ids).toContain("family_stepchild_marriage_certificate_confirmed");
    expect(ids).toContain("family_stepchild_birth_certificate_confirmed");
  });

  it("innocence: asks neither for SPOUSE, PARENT or CHILD", () => {
    for (const relation of ["SPOUSE", "PARENT", "CHILD"] as const) {
      const ids = getCategoryQuestionIds({
        category: "family",
        family_relation: relation,
      } as OracleFacts);
      expect(ids).not.toContain(
        "family_stepchild_marriage_certificate_confirmed",
      );
      expect(ids).not.toContain("family_stepchild_birth_certificate_confirmed");
    }
  });
});

describe("V1/E28 (2026-08-24): investment_product_code is askable for every invest vehicle", () => {
  // The mandate's disease: intent.requested_product_code was hard-coded
  // NOT_ASKED in fact-mapper.ts, so no interview path could ever reach
  // E28B/C/D/F (each product's sole rule keys on this exact fact). This
  // asserts the fix by the REAL path a user walks — getCategoryQuestionIds —
  // never by inspecting the mapper alone (acceptance item 1).
  it.each([
    "pt_pma",
    "property",
    "bank_deposit",
    "merit",
    "family",
    "undecided",
  ])(
    "is asked right after investment_vehicle for every vehicle branch (%s), including the non-PT-PMA ones E28C needs",
    (vehicle) => {
      const ids = getCategoryQuestionIds({
        category: "invest",
        investment_vehicle: vehicle,
      } as OracleFacts);
      const vehicleIdx = ids.indexOf("investment_vehicle");
      expect(vehicleIdx).toBeGreaterThanOrEqual(0);
      expect(ids[vehicleIdx + 1]).toBe("investment_product_code");
    },
  );

  it("is asked even before the vehicle is chosen (undefined branch)", () => {
    const ids = getCategoryQuestionIds({ category: "invest" } as OracleFacts);
    expect(ids).toContain("investment_product_code");
  });

  it("is never reachable through a non-invest category", () => {
    for (const category of CATEGORY_KEYS) {
      if (category === "invest") continue;
      const ids = getCategoryQuestionIds({ category } as OracleFacts);
      expect(ids).not.toContain("investment_product_code");
    }
  });
});

describe("V1/E33 (2026-08-25): sponsor-gated E33A/B/C question reachability", () => {
  it.each(["GOVERNMENT", "NONE"])(
    "investment_product_code_govt is asked on the invest branch when sponsor_category is %s",
    (sponsorCategory) => {
      const ids = getCategoryQuestionIds({
        category: "invest",
        sponsor_category: sponsorCategory,
      } as OracleFacts);
      expect(ids).toContain("investment_product_code_govt");
    },
  );

  it.each(["INDIVIDUAL", "EMPLOYER", "EDUCATION", "INVESTMENT", undefined])(
    "investment_product_code_govt is never asked on the invest branch when sponsor_category is %s",
    (sponsorCategory) => {
      const ids = getCategoryQuestionIds({
        category: "invest",
        ...(sponsorCategory === undefined
          ? {}
          : { sponsor_category: sponsorCategory }),
      } as OracleFacts);
      expect(ids).not.toContain("investment_product_code_govt");
    },
  );

  it("employment_product_code_govt is asked on the work branch if and only if sponsor_category is GOVERNMENT", () => {
    for (const sponsorCategory of [
      "NONE",
      "INDIVIDUAL",
      "EMPLOYER",
      "EDUCATION",
      "INVESTMENT",
      "GOVERNMENT",
    ]) {
      const ids = getCategoryQuestionIds({
        category: "work",
        sponsor_category: sponsorCategory,
      } as OracleFacts);
      if (sponsorCategory === "GOVERNMENT") {
        expect(ids).toContain("employment_product_code_govt");
      } else {
        expect(ids).not.toContain("employment_product_code_govt");
      }
    }
  });

  it("employment_product_code_none is asked on the work branch if and only if sponsor_category is NONE", () => {
    for (const sponsorCategory of [
      "NONE",
      "INDIVIDUAL",
      "EMPLOYER",
      "EDUCATION",
      "INVESTMENT",
      "GOVERNMENT",
    ]) {
      const ids = getCategoryQuestionIds({
        category: "work",
        sponsor_category: sponsorCategory,
      } as OracleFacts);
      if (sponsorCategory === "NONE") {
        expect(ids).toContain("employment_product_code_none");
      } else {
        expect(ids).not.toContain("employment_product_code_none");
      }
    }
  });

  it("employment_product_code_govt and employment_product_code_none are never both present (mutual exclusivity by construction)", () => {
    for (const sponsorCategory of [
      "NONE",
      "INDIVIDUAL",
      "EMPLOYER",
      "EDUCATION",
      "INVESTMENT",
      "GOVERNMENT",
      undefined,
    ]) {
      const ids = getCategoryQuestionIds({
        category: "work",
        ...(sponsorCategory === undefined
          ? {}
          : { sponsor_category: sponsorCategory }),
      } as OracleFacts);
      const hasGovt = ids.includes("employment_product_code_govt");
      const hasNone = ids.includes("employment_product_code_none");
      expect(hasGovt && hasNone).toBe(false);
    }
  });
});

describe("editing, pruning and branch projection", () => {
  it("editing category removes stale descendants from the abandoned branch", () => {
    let state = startOffshore("work");
    state = answer(state, "trip_scope", "single");
    state = answer(state, "sponsor_category", "EMPLOYER");
    state = answer(state, "work_payer", "yes");
    state = answer(state, "work_indonesia_compensation", "yes");
    expect(state.facts.work_payer).toBe("yes");

    state = reduce(state, { type: "EDIT", questionId: "category" });
    state = answer(state, "category", "tourism");
    expect(state.facts.sponsor_category).toBeUndefined();
    expect(state.facts.work_payer).toBeUndefined();
    expect(state.facts.work_indonesia_compensation).toBeUndefined();
    expectQuestion(state, "trip_scope");
  });

  it("editing in_indonesia prunes stale answers and re-enters the (now shared, differently-ordered) permit-status chain", () => {
    // Renamed and updated 2026-08-24 (D12 offshore-reachability P0 fix,
    // then re-fixed same day after a funnel-cost review): the fact is no
    // longer onshore-only-reachable — both branches can reach it now —
    // but the OFFSHORE order gates on holds_stay_permit first (funnel-cost
    // minimization: a "no" answer converges immediately, see the
    // dedicated tests above), so switching to "no" re-enters a
    // differently-shaped chain, not the identical onshore one.
    // application_channel remains genuinely onshore-only (only reachable
    // after wants_onshore_conversion, which stays gated on
    // in_indonesia==="yes"), so it is still correctly pruned and
    // unreachable here.
    let state = initialFlowState("en");
    state = reduce(state, { type: "ADVANCE" });
    state = answer(state, "in_indonesia", "yes");
    state = answer(state, "permit_expiry", "2026-09-01");
    state = answer(state, "holds_stay_permit", "no");
    state = answer(state, "current_status_code", "C1");
    state = answer(state, "overstay_days", "0");
    state = answer(state, "wants_onshore_conversion", "yes");
    state = answer(state, "application_channel", "STATUS_BRIDGING");

    state = reduce(state, { type: "EDIT", questionId: "in_indonesia" });
    state = answer(state, "in_indonesia", "no");
    expect(state.facts.permit_expiry).toBeUndefined();
    expect(state.facts.current_status_code).toBeUndefined();
    expect(state.facts.application_channel).toBeUndefined();
    expectQuestion(state, "holds_stay_permit");

    // Prove the chain is genuinely reachable now, not just present in
    // history — answer it through to convergence via BOTH offshore
    // sub-branches are covered by the dedicated tests above; here, prove
    // re-entry specifically converges correctly on the "no" path.
    state = answer(state, "holds_stay_permit", "no");
    expectQuestion(state, "overstay_days");
    expect(state.facts.permit_expiry).toBeUndefined();
    expect(state.facts.current_status_code).toBeUndefined();
    expect(state.facts.application_channel).toBeUndefined();
  });

  it("back is a real history step and prunes the removed answer", () => {
    let state = startOffshore("tourism");
    expectQuestion(state, "trip_scope");
    state = reduce(state, { type: "BACK" });
    expectQuestion(state, "category");
    expect(state.facts.category).toBe("tourism");
    state = reduce(state, { type: "BACK" });
    expectQuestion(state, "birth_date");
    expect(state.facts.category).toBeUndefined();
  });

  it("category leaves describe interview branches, with one selected", () => {
    const before = getTreeSteps(
      { kind: "question", questionId: "category" },
      { in_indonesia: "no", overstay_days: "0" },
    );
    expect(
      before.categoryLeaves?.every((leaf) => leaf.status === "pending"),
    ).toBe(true);
    const after = getTreeSteps(
      { kind: "question", questionId: "trip_scope" },
      { in_indonesia: "no", overstay_days: "0", category: "study" },
    );
    expect(
      after.categoryLeaves?.filter((leaf) => leaf.status === "done"),
    ).toEqual([{ key: "study", status: "done" }]);
  });

  it("GUILT: answering category with 'Not sure?' still projects the live question into the trunk", () => {
    // Reproduces the live defect (measured on balizero.com/visa-oracle,
    // Indonesian interface, "Berapa hari Anda berencana tinggal?" step):
    // the category question has `notSure: { mode: "human-review" }`
    // (tree.ts), so a real interview can leave `facts.category === "unsure"`
    // via flowReducer's SKIP action — not a synthetic value. Before the fix,
    // `behavioralSteps` bailed to `[]` whenever `category` wasn't a real
    // `CategoryKey`, so the live node ("stay_days") was absent from
    // `getTreeSteps`'s `order` array, `currentIdx` came back -1, and EVERY
    // trunk step — including ones already answered — read "pending". That
    // is what emptied the sr-only nav `<ol>` entirely (not a missing
    // translation: `getTreeSteps` never takes a language).
    let state = startOffshore();
    expectQuestion(state, "category");
    state = reduce(state, { type: "SKIP", questionId: "category" });
    expect(state.facts.category).toBe("unsure");
    state = answer(state, "trip_scope", "single");
    expectQuestion(state, "stay_days");

    const { trunk } = getTreeSteps(
      state.history[state.history.length - 1],
      state.facts,
    );
    const stayDays = trunk.find((s) => s.id === "stay_days");
    expect(stayDays).toEqual({
      id: "stay_days",
      labelI18nKey: "tree.stay_days",
      status: "current",
    });
    // Every step already answered on the way here must read "done", not
    // "pending" — the whole-nav-blank symptom was every step (not just
    // "stay_days") losing its real status because `currentIdx` was -1.
    const alreadyAnswered = ["framing", "in_indonesia", "overstay_days"];
    for (const id of alreadyAnswered) {
      expect(trunk.find((s) => s.id === id)?.status).not.toBe("pending");
    }
    expect(trunk.find((s) => s.id === "category")?.status).toBe("done");
  });

  it("INNOCENCE: a real category's trunk projection is unaffected by the 'unsure' fix", () => {
    // Same shape as the CATEGORY_CASES branches above (tourism: stay_days
    // then entry_pattern) — pins that delegating `behavioralSteps` straight
    // to `getCategoryQuestionIds` did not change anything for an actual
    // `CategoryKey`, only for the "unsure" fallback it previously mishandled.
    let state = startOffshore("tourism");
    state = answer(state, "trip_scope", "single");
    expectQuestion(state, "stay_days");

    const { trunk } = getTreeSteps(
      state.history[state.history.length - 1],
      state.facts,
    );
    expect(trunk.find((s) => s.id === "stay_days")).toEqual({
      id: "stay_days",
      labelI18nKey: "tree.stay_days",
      status: "current",
    });
    expect(trunk.find((s) => s.id === "category")?.status).toBe("done");
    expect(trunk.find((s) => s.id === "entry_pattern")?.status).toBe("pending");
  });

  it("only completed question steps are editable", () => {
    expect(
      isEditableTreeStep({
        id: "nationalities",
        labelI18nKey: "tree.nationalities",
        status: "done",
      }),
    ).toBe(true);
    expect(
      isEditableTreeStep({
        id: "confirmation",
        labelI18nKey: "tree.confirmation",
        status: "done",
      }),
    ).toBe(false);
  });
});

describe("resume snapshot validation", () => {
  it("replays date-sensitive routing against the snapshot's OWN save-time, not the resume-time wall clock (P1, 2026-08-24)", () => {
    // Reproduces the exact scenario from the adversarial grade on this PR:
    // save while the permit is still current (the renewal_paid gate skips,
    // history reaches past `overstay_days`), then resume after the permit
    // has since expired in real wall-clock time. Before this fix, replay
    // recomputed `shouldAskRenewalPaid` against the RESUME-time clock,
    // diverged from the saved `overstay_days` next-node, and truncated
    // history right there — silently dropping the already-answered
    // `overstay_days` fact even though nothing about the saved answers was
    // ever invalid.
    let state = initialFlowState("en");
    state = reduce(state, { type: "ADVANCE" });
    state = answer(state, "in_indonesia", "yes");
    state = answer(state, "permit_expiry", "2026-09-01");
    state = answer(state, "holds_stay_permit", "yes");
    state = answer(state, "stay_permit_code", "E28A");
    // At save-time (2026-08-24) the permit is still 8 days from expiry, so
    // the gate skips `renewal_paid` and goes straight to `overstay_days`.
    expectQuestion(state, "overstay_days");
    state = answer(state, "overstay_days", "0");
    expectQuestion(state, "wants_onshore_conversion");
    expect(state.facts.overstay_days).toBe("0");

    const snapshot = createInterviewSnapshot(
      state,
      new Date("2026-08-24T00:00:00Z"),
    );

    // Resume 22 days later: the permit is now expired in real wall-clock
    // time — this is the moment the bug's clock (`restoreToday`) reads.
    const restored = restoreInterviewSnapshot(
      snapshot,
      "en",
      new Date("2026-09-15T00:00:00Z"),
    );

    expect(restored?.history).toEqual(state.history);
    expect(restored?.facts).toEqual(state.facts);
    expect(restored?.facts.overstay_days).toBe("0");
  });

  it("serializes language-neutral facts and restores in a different language", () => {
    const state = startOffshore("tourism");
    const snapshot = createInterviewSnapshot(
      state,
      new Date("2026-08-03T00:00:00Z"),
    );
    expect(JSON.stringify(snapshot)).not.toContain('"en"');
    const restored = restoreInterviewSnapshot(snapshot, "id");
    expect(restored?.language).toBe("id");
    expect(restored?.facts).toEqual(state.facts);
  });

  it("rejects an unknown schema version", () => {
    expect(
      restoreInterviewSnapshot({
        schemaVersion: INTERVIEW_SNAPSHOT_SCHEMA_VERSION + 1,
        attempt: 0,
        history: [{ kind: "framing" }],
        facts: {},
        updatedAtIso: "2026-08-03T00:00:00Z",
      }),
    ).toBeNull();
  });

  it("fails closed on a typo status code instead of treating it as KNOWN", () => {
    const snapshot = {
      schemaVersion: INTERVIEW_SNAPSHOT_SCHEMA_VERSION,
      attempt: 0,
      updatedAtIso: "2026-08-03T00:00:00Z",
      history: [
        { kind: "framing" },
        { kind: "question", questionId: "in_indonesia" },
        { kind: "question", questionId: "permit_expiry" },
        { kind: "question", questionId: "holds_stay_permit" },
        { kind: "question", questionId: "current_status_code" },
        { kind: "question", questionId: "overstay_days" },
      ],
      facts: {
        in_indonesia: "yes",
        permit_expiry: "2026-09-01",
        holds_stay_permit: "no",
        current_status_code: "C22",
      },
    };
    const restored = restoreInterviewSnapshot(snapshot);
    expect(restored?.history[restored.history.length - 1]).toEqual({
      kind: "question",
      questionId: "current_status_code",
    });
    expect(restored?.facts.current_status_code).toBeUndefined();
  });

  it("invalidates the legacy composite overstay/blacklist value", () => {
    let state = startOffshore("tourism");
    state = answer(state, "trip_scope", "single");
    state = answer(state, "stay_days", "30");
    state = answer(state, "entry_pattern", "SINGLE");
    const snapshot = createInterviewSnapshot(state);
    const legacy = {
      ...snapshot,
      history: [...snapshot.history, { kind: "confirmation" as const }],
      facts: {
        ...snapshot.facts,
        review_gate: "overstay_or_blacklist",
      },
    };
    const restored = restoreInterviewSnapshot(legacy);
    expect(restored?.history[restored.history.length - 1]).toEqual({
      kind: "question",
      questionId: "review_gate",
    });
    expect(restored?.facts.review_gate).toBeUndefined();
  });

  it("rejects non-canonical country-code sets and out-of-range integers", () => {
    const state = startOffshore();
    const snapshot = createInterviewSnapshot(state);
    const badCountry = {
      ...snapshot,
      facts: { ...snapshot.facts, nationalities: "US,IT" },
    };
    expect(
      restoreInterviewSnapshot(badCountry)?.facts.nationalities,
    ).toBeUndefined();

    const unknownCountry = {
      ...snapshot,
      facts: { ...snapshot.facts, nationalities: "ZZ" },
    };
    expect(
      restoreInterviewSnapshot(unknownCountry)?.facts.nationalities,
    ).toBeUndefined();

    const tooManyCountries = {
      ...snapshot,
      facts: { ...snapshot.facts, nationalities: "AU,FR,ID,IT,US" },
    };
    expect(
      restoreInterviewSnapshot(tooManyCountries)?.facts.nationalities,
    ).toBeUndefined();

    const onshoreHistory = [
      { kind: "framing" as const },
      { kind: "question" as const, questionId: "in_indonesia" },
      { kind: "question" as const, questionId: "permit_expiry" },
      { kind: "question" as const, questionId: "holds_stay_permit" },
      { kind: "question" as const, questionId: "current_status_code" },
      { kind: "question" as const, questionId: "overstay_days" },
      { kind: "question" as const, questionId: "wants_onshore_conversion" },
    ];
    const badOverstay = {
      schemaVersion: INTERVIEW_SNAPSHOT_SCHEMA_VERSION,
      attempt: 0,
      updatedAtIso: "2026-08-03T00:00:00Z",
      history: onshoreHistory,
      facts: {
        in_indonesia: "yes",
        permit_expiry: "2026-09-01",
        holds_stay_permit: "no",
        current_status_code: "C1",
        overstay_days: "36501",
      },
    };
    const restored = restoreInterviewSnapshot(badOverstay);
    expect(restored?.history[restored.history.length - 1]).toEqual({
      kind: "question",
      questionId: "overstay_days",
    });
    expect(restored?.facts.overstay_days).toBeUndefined();
  });

  it("fails closed (returns null, never throws) on a pre-deletion snapshot paused on either dead node (E4 slice)", () => {
    // Guilt: a snapshot from before this cleanup could have `history`
    // ending on `tourism_duration`/`remote_income` (a real user paused an
    // interview there pre-deploy). Both ids are gone from QUESTIONS now —
    // `isOracleNode`'s hasOwnProperty guard must reject the whole snapshot,
    // not throw and not silently accept an unknown node.
    const base = {
      schemaVersion: INTERVIEW_SNAPSHOT_SCHEMA_VERSION,
      attempt: 0,
      updatedAtIso: "2026-08-03T00:00:00Z",
      facts: {},
    };
    for (const deadId of ["tourism_duration", "remote_income"]) {
      const snapshot = {
        ...base,
        history: [
          { kind: "framing" as const },
          { kind: "question" as const, questionId: deadId },
        ],
      };
      expect(() => restoreInterviewSnapshot(snapshot)).not.toThrow();
      expect(restoreInterviewSnapshot(snapshot)).toBeNull();
    }
  });
});

describe("dead-node cleanup — E4 slice (question-registry-audit.md §2)", () => {
  it("no live category sequence (fixed or dynamic) ever names a dead node", () => {
    // Innocence: the full behavioral graph reachable from every category
    // (fixed sequences + every dynamic branch combination already exercised
    // by "the ten behavioral interview branches" above) never mentions
    // either id — proving their removal from tree.ts/flow.ts changed
    // nothing about any LIVE path.
    const deadIds = new Set(["tourism_duration", "remote_income"]);
    for (const category of CATEGORY_KEYS) {
      for (const facts of [
        { category },
        { category, investment_vehicle: "pt_pma" },
        { category, investment_vehicle: "property" },
        { category, investment_vehicle: "bank_deposit" },
        { category, retirement_basis: "bank_deposit" },
        { category, retirement_basis: "property" },
        { category, retirement_basis: "passive_income" },
        { category, retirement_basis: "family_sponsor" },
        { category, family_relation: "SPOUSE" },
        { category, family_sponsor_nationalities: "US" },
        { category, family_sponsor_nationalities: "ID" },
      ] as OracleFacts[]) {
        for (const id of getCategoryQuestionIds(facts)) {
          expect(deadIds.has(id)).toBe(false);
        }
      }
    }
  });

  it("computeNextNode never routes any live transition into a dead node", () => {
    // Guilt: if either id were re-wired into a live sequence, this would
    // catch it via the ten-branch happy paths above already asserting
    // exact next-question ids at every step — this test additionally pins
    // that `tourism_duration`/`remote_income` are absent from every fixed
    // sequence's declared ids.
    const fixedIds = CATEGORY_KEYS.flatMap((category) =>
      getCategoryQuestionIds({ category }),
    );
    expect(fixedIds).not.toContain("tourism_duration");
    expect(fixedIds).not.toContain("remote_income");
  });
});

describe("attempt and verdict navigation", () => {
  it("increments attempt only on a true restart", () => {
    let state = startOffshore("tourism");
    const attempt = state.attempt;
    state = reduce(state, { type: "EDIT", questionId: "category" });
    expect(state.attempt).toBe(attempt);
    state = reduce(state, { type: "RESTART" });
    expect(state.attempt).toBe(attempt + 1);
    expect(state.facts).toEqual({});
  });

  it("SELECT_CATEGORY reuses the interview and prunes the prior branch", () => {
    let state = startOffshore("work");
    state = answer(state, "trip_scope", "single");
    state = answer(state, "sponsor_category", "EMPLOYER");
    state = answer(state, "work_payer", "yes");
    state = reduce(state, { type: "SELECT_CATEGORY", category: "study" });
    expect(state.facts.category).toBe("study");
    expect(state.facts.sponsor_category).toBeUndefined();
    expect(state.facts.work_payer).toBeUndefined();
    expectQuestion(state, "trip_scope");
  });
});
