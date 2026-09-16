import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { describe, expect, it } from "vitest";
import { CATEGORY_KEYS, getLane, QUESTIONS, type OracleFacts } from "./tree";
import { translate, type I18nKey } from "./i18n";
// The walk corpus' own default-answer convention, reused so a test that drives
// the interview forward answers exactly what the committed fixtures answer.
import { answerFor } from "../../../../../scripts/visa-oracle/generate-walk-corpus";
import {
  D12_MAX_STAY_DAYS,
  INTERVIEW_SNAPSHOT_SCHEMA_VERSION,
  computeNextNode,
  createInterviewSnapshot,
  flowReducer,
  followUpPrerequisitesMet,
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

/** `today` is optional and defaults to undefined, so every existing caller is
 * unchanged. Pass it ONLY on a transition whose next node depends on a date
 * comparison — `shouldAskRenewalPaid` is the one that does. The reducer
 * forwards it to `computeNextNode` (flow.ts), so this is the clock the engine
 * actually READS; freezing anything else would leave the forward build on the
 * real wall clock, which is precisely how the two fixtures below went off. */
function answer(
  state: FlowState,
  questionId: string,
  value: string,
  today?: Date,
): FlowState {
  expectQuestion(state, questionId);
  return reduce(state, { type: "ANSWER", questionId, value, today });
}

/** The date the two date-sensitive tests below were WRITTEN on. Their fixture
 * `permit_expiry: "2026-09-01"` was picked as "8 days out" from here, so the
 * `renewal_paid` gate skipped and the chain reached `overstay_days`. Judged
 * against the real wall clock that stopped being true at 00:00 UTC on
 * 2026-09-02, and both went red with no code change behind them. The sibling
 * `renewal_paid gating` block never had this fault: its fixtures are
 * 2020-01-01 and 2099-01-01, far enough out on both sides that no clock
 * reaches them. Those tests are deliberately left alone. */
const PERMIT_STILL_CURRENT = new Date("2026-08-24T00:00:00Z");

function startOffshore(category?: string): FlowState {
  let state = initialFlowState("en");
  state = reduce(state, { type: "ADVANCE" });
  state = answer(state, "in_indonesia", "no");
  // Offshore now asks a single permit-status gate question before
  // converging (fixed 2026-08-24, D12 offshore-reachability P0, then
  // re-fixed same day after a funnel-cost review — see `computeNextNode`'s
  // `in_indonesia`/`holds_stay_permit` cases). "no" here converges
  // straight to `nationalities` with no further questions (the fact
  // resolves from this answer alone via `fact-mapper.ts`'s synthesized
  // `NO_STAY_PERMIT`) — preserved here to keep every downstream test's
  // original intent (none of them are about permit status). D19
  // (2026-09-16): `overstay_days` itself is no longer asked offshore at
  // all, so it is not answered here either — `flow.test.ts`'s dedicated
  // D19 describe block below covers that skip directly.
  state = answer(state, "holds_stay_permit", "no");
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
      ["stay_days", "365"],
    ],
  },
  {
    category: "invest",
    branch: [
      ["sponsor_category", "INVESTMENT"],
      ["investment_vehicle", "pt_pma"],
      ["investment_pt_pma", "yes"],
      ["investment_capital_idr", "1000000000"],
      ["investment_paid_up_capital_idr", "500000000"],
      ["investment_role", "SHAREHOLDER_DIRECTOR"],
      ["investment_establishes_company", "yes"],
      ["investment_foreign_branch", "no"],
      ["investment_ikn_subsidiary", "no"],
      ["investment_meets_threshold", "yes"],
      ["family_sponsor_confirmed", "no"],
      // `startOffshore` drives every CATEGORY_CASES walk, so the invest
      // branch's offshore-only `wants_onshore_conversion` is asked here.
      ["wants_onshore_conversion", "no"],
      ["stay_days", "730"],
    ],
  },
  {
    category: "remote",
    branch: [
      ["sponsor_category", "NONE"],
      ["remote_clients", "foreign"],
      ["remote_compensation", "no"],
      ["work_payer", "no"],
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
    category: "second_home",
    branch: [
      ["secondhome_basis", "property"],
      ["secondhome_property_value_usd", "2000000"],
      ["stay_days", "1825"],
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
      // Diaspora now serves the FAMILY question set verbatim (owner
      // ruling 4) — `getCategoryQuestionIds` composes the two
      // diaspora-context questions with `familyQuestionIds`.
      ["sponsor_category", "INDIVIDUAL"],
      ["family_relation", "PARENT"],
      ["marital_status", "MARRIED"],
      ["family_sponsor_nationalities", "ID"],
      ["family_marriage_registered", "yes"],
      ["family_sponsor_confirmed", "yes"],
      ["stay_days", "365"],
    ],
  },
  {
    category: "other",
    branch: [
      ["other_purpose", "medical"],
      ["other_paid_activity", "no"],
      ["family_sponsor_confirmed", "yes"],
      ["stay_days", "30"],
      ["entry_pattern", "SINGLE"],
    ],
  },
];

describe("the eleven behavioral interview branches", () => {
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

  it("covers exactly the eleven category keys", () => {
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
        "family_sponsor_confirmed",
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
        ["family_sponsor_confirmed", "yes"],
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
    // onshore-only, unchanged by this fix. D19 (2026-09-16): the chain no
    // longer stops at `overstay_days` either — offshore converges straight
    // on `nationalities` (see the dedicated D19 describe block below).
    let state = initialFlowState("en");
    state = reduce(state, { type: "ADVANCE" });
    state = answer(state, "in_indonesia", "no");
    expectQuestion(state, "holds_stay_permit");
    state = answer(state, "holds_stay_permit", "yes");
    expectQuestion(state, "permit_expiry");
    state = answer(state, "permit_expiry", "2026-09-01");
    expectQuestion(state, "stay_permit_code");
    state = answer(state, "stay_permit_code", "E28A", PERMIT_STILL_CURRENT);
    expectQuestion(state, "nationalities");
    expect(state.facts.stay_permit_code).toBe("E28A");
    expect(state.facts.overstay_days).toBeUndefined();
    expect(state.facts.application_channel).toBeUndefined();
  });

  it("offshore + no permit: converges on nationalities after exactly one gate question, no code/expiry/overstay asked", () => {
    // The funnel-cost half of the same 2026-08-24 fix: an offshore
    // applicant who does not hold a permit pays exactly ONE extra
    // question (holds_stay_permit itself), not the full 3-question
    // chain — permit_expiry/stay_permit_code/current_status_code are
    // never reached at all. Reachability of
    // derived.has_active_stay_permit from this path (the synthesized
    // NO_STAY_PERMIT sentinel resolving to a definite False) is proven
    // at the backend in fact-mapper.test.ts and
    // test_d12_active_stay_permit_exclusion.py, not here — this test
    // only proves the frontend never asks the redundant questions. D19
    // (2026-09-16): `overstay_days` joins that redundant-question list —
    // you cannot overstay while outside Indonesia, so it is never shown.
    let state = initialFlowState("en");
    state = reduce(state, { type: "ADVANCE" });
    state = answer(state, "in_indonesia", "no");
    expectQuestion(state, "holds_stay_permit");
    state = answer(state, "holds_stay_permit", "no");
    expectQuestion(state, "nationalities");
    expect(state.facts.permit_expiry).toBeUndefined();
    expect(state.facts.stay_permit_code).toBeUndefined();
    expect(state.facts.current_status_code).toBeUndefined();
    expect(state.facts.overstay_days).toBeUndefined();
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

describe("D19 — offshore never asks overstay_days (owner ruling, Zero, 2026-09-16)", () => {
  // "You cannot be overstaying in Indonesia while you are outside it." Every
  // offshore transition that used to lead into `overstay_days` now leads
  // straight to `nationalities` instead; onshore is untouched.
  it("guilt: holds_stay_permit='no' chain converges on nationalities, not overstay_days", () => {
    expect(
      computeNextNode(
        { kind: "question", questionId: "holds_stay_permit" },
        { in_indonesia: "no", holds_stay_permit: "no" },
      ),
    ).toEqual({ kind: "question", questionId: "nationalities" });
  });

  it("guilt: holds_stay_permit='yes' chain, current permit (no renewal_paid gate), converges on nationalities", () => {
    expect(
      computeNextNode(
        { kind: "question", questionId: "stay_permit_code" },
        {
          in_indonesia: "no",
          holds_stay_permit: "yes",
          permit_expiry: "2099-01-01",
          stay_permit_code: "E28A",
        },
        new Date(2026, 7, 24),
      ),
    ).toEqual({ kind: "question", questionId: "nationalities" });
  });

  it("guilt: holds_stay_permit='yes' chain, expired permit (renewal_paid gate fires), still converges on nationalities after it", () => {
    expect(
      computeNextNode(
        { kind: "question", questionId: "renewal_paid" },
        {
          in_indonesia: "no",
          holds_stay_permit: "yes",
          permit_expiry: "2020-01-01",
          stay_permit_code: "E28A",
          renewal_paid: "yes",
        },
      ),
    ).toEqual({ kind: "question", questionId: "nationalities" });
  });

  it("innocence: onshore holds_stay_permit='no' chain still asks overstay_days, unchanged", () => {
    expect(
      computeNextNode(
        { kind: "question", questionId: "current_status_code" },
        {
          in_indonesia: "yes",
          holds_stay_permit: "no",
          current_status_code: "C1",
        },
      ),
    ).toEqual({ kind: "question", questionId: "overstay_days" });
  });

  it("innocence: onshore holds_stay_permit='yes' chain still asks overstay_days, unchanged", () => {
    expect(
      computeNextNode(
        { kind: "question", questionId: "stay_permit_code" },
        {
          in_indonesia: "yes",
          holds_stay_permit: "yes",
          permit_expiry: "2099-01-01",
          stay_permit_code: "E28A",
        },
        new Date(2026, 7, 24),
      ),
    ).toEqual({ kind: "question", questionId: "overstay_days" });
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

describe("editing, pruning and branch projection", () => {
  // `study_level` is a REGISTERED question that this tourism interview never
  // asked (was `work_role`, deleted from the registry 2026-09-06 — an
  // unregistered id no longer exercises the "registered but off-path"
  // half of this assertion). `unknown-question` covers the unregistered
  // half.
  it.each(["study_level", "unknown-question"])(
    "EDIT resets an absent target %s without retaining the previous interview",
    (questionId) => {
      const state: FlowState = {
        ...startOffshore("tourism"),
        language: "id",
        attempt: 7,
        blockedAnswer: {
          questionId: "application_channel",
          conflictsWithQuestionId: "wants_onshore_conversion",
        },
      };
      expect(state.history).not.toContainEqual({
        kind: "question",
        questionId,
      });
      const next = reduce(state, { type: "EDIT", questionId });
      expect(next).toEqual({
        language: "id",
        attempt: 8,
        history: [{ kind: "framing" }],
        facts: {},
        blockedAnswer: null,
        pendingFollowUp: null,
      });
    },
  );

  it("EDIT keeps the current visited question in the same attempt", () => {
    const state: FlowState = {
      ...startOffshore("tourism"),
      language: "id",
      attempt: 7,
    };
    expectQuestion(state, "trip_scope");
    expect(reduce(state, { type: "EDIT", questionId: "trip_scope" })).toEqual(
      state,
    );
  });

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
    // re-entry specifically converges correctly on the "no" path. D19
    // (2026-09-16): that convergence point is `nationalities`, not
    // `overstay_days` — offshore never asks it at all, so the stale "0"
    // answered onshore above must be pruned away, not carried over.
    state = answer(state, "holds_stay_permit", "no");
    expectQuestion(state, "nationalities");
    expect(state.facts.permit_expiry).toBeUndefined();
    expect(state.facts.current_status_code).toBeUndefined();
    expect(state.facts.application_channel).toBeUndefined();
    expect(state.facts.overstay_days).toBeUndefined();
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
      { in_indonesia: "no" },
    );
    expect(
      before.categoryLeaves?.every((leaf) => leaf.status === "pending"),
    ).toBe(true);
    const after = getTreeSteps(
      { kind: "question", questionId: "trip_scope" },
      { in_indonesia: "no", category: "study" },
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
    // `overstay_days` is not one of these any more (D19, 2026-09-16):
    // offshore's trunk never includes it at all, so `holds_stay_permit` —
    // the actual offshore gate question `startOffshore` answers — replaces
    // it here.
    const alreadyAnswered = ["framing", "in_indonesia", "holds_stay_permit"];
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
    state = answer(state, "stay_permit_code", "E28A", PERMIT_STILL_CURRENT);
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

// ────────────────────────────────────────────────────────────────────────
// 2026-09-06 decisiveness wave (PR-3): the +1 questions that supply the
// facts the engine still asks for, and the follow-up loop that asks a
// modelled-but-unasked question instead of rendering a dead row.
// ────────────────────────────────────────────────────────────────────────

describe("PR-3 · wants_onshore_conversion is asked OFFSHORE in the invest branch only", () => {
  it("guilt: the offshore invest branch asks it exactly once, immediately before stay_days", () => {
    const ids = getCategoryQuestionIds({
      category: "invest",
      investment_vehicle: "pt_pma",
      in_indonesia: "no",
    });
    expect(ids.filter((id) => id === "wants_onshore_conversion")).toHaveLength(
      1,
    );
    expect(ids[ids.indexOf("wants_onshore_conversion") + 1]).toBe("stay_days");
  });

  it("innocence: the ONSHORE invest branch does not repeat the spine question", () => {
    // Onshore, `computeNextNode`'s `overstay_days` case already routes
    // through it — asking again in the branch would be a duplicate node.
    const ids = getCategoryQuestionIds({
      category: "invest",
      investment_vehicle: "pt_pma",
      in_indonesia: "yes",
    });
    expect(ids).not.toContain("wants_onshore_conversion");
  });

  it("innocence: no other category asks it, onshore or offshore", () => {
    for (const category of CATEGORY_KEYS) {
      if (category === "invest") continue;
      for (const inIndonesia of ["yes", "no"]) {
        expect(
          getCategoryQuestionIds({ category, in_indonesia: inIndonesia }),
        ).not.toContain("wants_onshore_conversion");
      }
    }
  });

  it("guilt: answering it offshore continues the invest branch, never the onshore spine", () => {
    // The regression this guards: `computeNextNode` matches by question id
    // BEFORE falling through to the category sequence, so the offshore
    // occurrence used to route to `application_channel` — an onshore-only
    // question the applicant had already skipped past.
    const facts: OracleFacts = {
      in_indonesia: "no",
      category: "invest",
      investment_vehicle: "pt_pma",
    };
    expect(
      computeNextNode(
        { kind: "question", questionId: "wants_onshore_conversion" },
        facts,
      ),
    ).toEqual({ kind: "question", questionId: "stay_days" });
  });

  it("innocence: the onshore spine still routes it to application_channel", () => {
    expect(
      computeNextNode(
        { kind: "question", questionId: "wants_onshore_conversion" },
        { in_indonesia: "yes", category: "invest" },
      ),
    ).toEqual({ kind: "question", questionId: "application_channel" });
  });
});

describe("PR-3 · family_sponsor_confirmed reaches the invest and other branches", () => {
  it.each(["invest", "other", "family", "retirement", "diaspora"] as const)(
    "guilt: %s asks it exactly once",
    (category) => {
      const ids = getCategoryQuestionIds({
        category,
        investment_vehicle: "pt_pma",
        retirement_basis: "passive_income",
      });
      expect(
        ids.filter((id) => id === "family_sponsor_confirmed"),
      ).toHaveLength(1);
    },
  );

  it("innocence: the branches whose covering rules do not read it are untouched", () => {
    for (const category of ["tourism", "business", "work", "study"] as const) {
      expect(getCategoryQuestionIds({ category })).not.toContain(
        "family_sponsor_confirmed",
      );
    }
  });
});

describe("PR-3 · work_payer reaches the remote branch", () => {
  it("guilt: remote asks it exactly once, right before the employer country", () => {
    const ids = getCategoryQuestionIds({ category: "remote" });
    expect(ids.filter((id) => id === "work_payer")).toHaveLength(1);
    expect(ids[ids.indexOf("work_payer") + 1]).toBe("remote_employer_country");
  });

  it("innocence: work still asks it once and no third branch picked it up", () => {
    expect(
      getCategoryQuestionIds({ category: "work" }).filter(
        (id) => id === "work_payer",
      ),
    ).toHaveLength(1);
    const others = CATEGORY_KEYS.filter(
      (category) => category !== "work" && category !== "remote",
    );
    for (const category of others) {
      expect(getCategoryQuestionIds({ category })).not.toContain("work_payer");
    }
  });
});

describe("PR-3 · work_role is gone from every live sequence (owner ruling 6)", () => {
  it("guilt: no category sequence names it and the registry has no entry", () => {
    for (const category of CATEGORY_KEYS) {
      expect(getCategoryQuestionIds({ category })).not.toContain("work_role");
    }
    expect(Object.prototype.hasOwnProperty.call(QUESTIONS, "work_role")).toBe(
      false,
    );
  });

  it("innocence: the work branch still collects every fact E23 reads", () => {
    // `el.e23-employment-support` requires `intent.purposes`,
    // `work.employer_is_indonesian_entity` and
    // `work.indonesian_work_sponsor_confirmed` — deleting the role
    // question must not have taken any of them with it.
    const ids = getCategoryQuestionIds({ category: "work" });
    expect(ids).toContain("work_payer");
    expect(ids).toContain("work_sponsor_confirmed");
    expect(ids).toContain("work_indonesia_compensation");
  });
});

describe("PR-3 · the second_home branch (owner ruling 3)", () => {
  it("guilt: each basis serves exactly the evidence its E33 support rule reads", () => {
    expect(
      getCategoryQuestionIds({
        category: "second_home",
        secondhome_basis: "property",
      }),
    ).toEqual([
      "secondhome_basis",
      "secondhome_property_value_usd",
      "stay_days",
    ]);
    expect(
      getCategoryQuestionIds({
        category: "second_home",
        secondhome_basis: "bank_deposit",
      }),
    ).toEqual([
      "secondhome_basis",
      "secondhome_deposit_usd",
      "secondhome_state_bank",
      "secondhome_own_name",
      "stay_days",
    ]);
  });

  it("innocence: before the basis is answered no evidence question is asked", () => {
    expect(getCategoryQuestionIds({ category: "second_home" })).toEqual([
      "secondhome_basis",
      "stay_days",
    ]);
  });

  it("innocence: the retirement branch is unchanged by the new tile", () => {
    expect(
      getCategoryQuestionIds({
        category: "retirement",
        retirement_basis: "property",
      }),
    ).toEqual([
      "sponsor_category",
      "retirement_basis",
      "secondhome_property_value_usd",
      // Added (PR-D3, D3-3): `property` now asks the same E33F fallback
      // pair every other retirement basis does — see flow.ts.
      "secondhome_passive_income_usd",
      "family_sponsor_confirmed",
      "stay_days",
    ]);
  });
});

describe("PR-3 · diaspora serves the FAMILY question set (owner ruling 4)", () => {
  it("guilt: the diaspora sequence is its two context questions plus the family branch verbatim", () => {
    const facts: OracleFacts = {
      family_relation: "PARENT",
      family_sponsor_nationalities: "ID",
    };
    expect(getCategoryQuestionIds({ ...facts, category: "diaspora" })).toEqual([
      "diaspora_connection",
      "diaspora_documents",
      ...getCategoryQuestionIds({ ...facts, category: "family" }),
    ]);
  });

  it("guilt: a diaspora STEPCHILD interview reaches the stepchild evidence questions", () => {
    const ids = getCategoryQuestionIds({
      category: "diaspora",
      family_relation: "STEPCHILD",
    });
    expect(ids).toContain("family_stepchild_marriage_certificate_confirmed");
    expect(ids).toContain("family_stepchild_birth_certificate_confirmed");
  });

  it("innocence: the family tile keeps its own sequence, with no diaspora questions", () => {
    const ids = getCategoryQuestionIds({ category: "family" });
    expect(ids).not.toContain("diaspora_connection");
    expect(ids).not.toContain("diaspora_documents");
    expect(ids[0]).toBe("sponsor_category");
  });
});

describe("PR-3 · ASK_FOLLOW_UP appends, and never destroys the interview", () => {
  function atVerdict(): FlowState {
    let state = startOffshore("tourism");
    state = answer(state, "trip_scope", "single");
    state = answer(state, "stay_days", "30");
    state = answer(state, "entry_pattern", "SINGLE");
    state = answer(state, "review_gate", "none");
    state = reduce(state, { type: "ADVANCE" });
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "verdict",
    });
    return state;
  }

  it("guilt: appends the never-asked question and keeps every fact already answered", () => {
    const before = atVerdict();
    const after = reduce(before, {
      type: "ASK_FOLLOW_UP",
      questionId: "study_level",
    });
    expect(after.history).toEqual([
      ...before.history,
      { kind: "question", questionId: "study_level" },
    ]);
    expect(after.facts).toEqual(before.facts);
    expect(after.attempt).toBe(before.attempt);
    expect(after.pendingFollowUp).toBe("study_level");
  });

  it("guilt: EDIT on the same absent target would have wiped the interview — the contrast is the point", () => {
    const before = atVerdict();
    const wiped = reduce(before, { type: "EDIT", questionId: "study_level" });
    expect(wiped.facts).toEqual({});
    expect(wiped.attempt).toBe(before.attempt + 1);
  });

  it("guilt: answering the follow-up returns to the verdict, never into another branch's sequence", () => {
    let state = reduce(atVerdict(), {
      type: "ASK_FOLLOW_UP",
      questionId: "study_level",
    });
    state = reduce(state, {
      type: "ANSWER",
      questionId: "study_level",
      value: "POSTGRADUATE",
    });
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "verdict",
    });
    expect(state.facts.study_level).toBe("POSTGRADUATE");
    expect(state.facts.stay_days).toBe("30");
    expect(state.pendingFollowUp).toBeNull();
  });

  it("guilt: SKIP on the follow-up also returns to the verdict, recording the unsure sentinel", () => {
    let state = reduce(atVerdict(), {
      type: "ASK_FOLLOW_UP",
      questionId: "study_level",
    });
    state = reduce(state, { type: "SKIP", questionId: "study_level" });
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "verdict",
    });
    expect(state.facts.study_level).toBe("unsure");
  });

  it("innocence: an unregistered id is a no-op, not a reset", () => {
    const before = atVerdict();
    expect(
      reduce(before, { type: "ASK_FOLLOW_UP", questionId: "not-a-question" }),
    ).toBe(before);
  });

  it("innocence: an ALREADY-ASKED question is a no-op — reopening it is EDIT's job", () => {
    const before = atVerdict();
    expect(
      reduce(before, { type: "ASK_FOLLOW_UP", questionId: "stay_days" }),
    ).toBe(before);
  });

  it("innocence: BACK from a follow-up returns to the verdict and clears the pending marker", () => {
    const before = atVerdict();
    const asked = reduce(before, {
      type: "ASK_FOLLOW_UP",
      questionId: "study_level",
    });
    const back = reduce(asked, { type: "BACK" });
    expect(back.history).toEqual(before.history);
    expect(back.facts).toEqual(before.facts);
    expect(back.pendingFollowUp).toBeNull();
  });

  // `pendingFollowUp` is cleared by BACK, so an applicant who answers the
  // follow-up, steps BACK onto it and answers again holds no pending id.
  // Routing that second answer by question id would drop them into
  // `review_gate` — the interview they had already finished, re-opened.
  it("guilt: re-answering a follow-up after BACK still returns to the verdict, not review_gate", () => {
    let state = reduce(atVerdict(), {
      type: "ASK_FOLLOW_UP",
      questionId: "study_level",
    });
    state = reduce(state, {
      type: "ANSWER",
      questionId: "study_level",
      value: "POSTGRADUATE",
    });
    state = reduce(state, { type: "BACK" });
    expectQuestion(state, "study_level");
    expect(state.pendingFollowUp).toBeNull();
    state = reduce(state, {
      type: "ANSWER",
      questionId: "study_level",
      value: "UNDERGRADUATE",
    });
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "verdict",
    });
    expect(state.facts.study_level).toBe("UNDERGRADUATE");
  });

  it("innocence: an ordinary in-sequence answer is unaffected by the follow-up machinery", () => {
    let state = startOffshore("tourism");
    state = answer(state, "trip_scope", "single");
    state = answer(state, "stay_days", "30");
    expectQuestion(state, "entry_pattern");
    expect(state.pendingFollowUp).toBeNull();
  });
});

// W-VO-Q (mission SAETTA-VO3): the ten seq-21 qualification questions are
// asked only where the rule that reads each one can match — the sponsor
// premise its `sponsor.type` names, on a branch whose purpose the rule
// covers (`rulepack-prod-021.source.json`, FACTS-FOR-THE-TREE.md).
describe("seq-21 qualification questions — asked only where their rule can match", () => {
  const SPONSOR_QUESTIONS = [
    "sponsor_government_invitation",
    "sponsor_government_collaboration",
    "sponsor_world_figure_invitation",
    "sponsor_diplomatic_household",
    "sponsor_trade_office",
  ];
  const ROUTE_QUESTIONS = [
    "investment_establishes_company",
    "investment_capital_market_only",
    "investment_foreign_branch",
    "investment_ikn_subsidiary",
    "investment_meets_threshold",
  ];
  const TEN = [...SPONSOR_QUESTIONS, ...ROUTE_QUESTIONS];
  const SPONSORS = QUESTIONS.sponsor_category.options.map(({ key }) => key);
  const asked = (facts: OracleFacts) =>
    TEN.filter((id) => getCategoryQuestionIds(facts).includes(id));

  it("gives each of the ten a process-rail label in both languages", () => {
    // Found in the browser, not by a test: the rail rendered the raw key
    // `tree.investment_establishes_company` until these labels existed.
    for (const id of TEN) {
      for (const lang of ["en", "id"] as const) {
        expect(translate(lang, `tree.${id}` as I18nKey)).not.toBe(`tree.${id}`);
        expect(translate(lang, `q.${id}` as I18nKey)).not.toBe(`q.${id}`);
        expect(translate(lang, `why.${id}` as I18nKey)).not.toBe(`why.${id}`);
      }
    }
  });

  it("registers all ten as yes/no FACT questions with no Not-sure affordance", () => {
    for (const id of TEN) {
      const question = QUESTIONS[id];
      expect(question.options.map(({ key }) => key)).toEqual(["yes", "no"]);
      expect(question.decisionMapping.kind).toBe("FACT");
      expect(question.notSure).toBeUndefined();
    }
  });

  it.each([
    ["GOVERNMENT", ["sponsor_government_invitation", "sponsor_trade_office"]],
    ["INDIVIDUAL", ["sponsor_diplomatic_household"]],
    ["NONE", ["sponsor_government_collaboration"]],
    ["EMPLOYER", []],
    ["EDUCATION", []],
    ["INVESTMENT", []],
    ["unsure", []],
  ])(
    "an EMPLOYMENT branch with sponsor %s asks exactly %j",
    (sponsor, expected) => {
      expect(asked({ category: "work", sponsor_category: sponsor })).toEqual(
        expected,
      );
      expect(
        asked({
          category: "other",
          other_paid_activity: "yes",
          sponsor_category: sponsor,
        }),
      ).toEqual(expected);
    },
  );

  it("guilt: no category outside work, paid other and invest ever asks one, whatever the sponsor", () => {
    const quiet = CATEGORY_KEYS.filter(
      (category) => category !== "work" && category !== "invest",
    );
    for (const category of quiet) {
      for (const sponsor_category of SPONSORS) {
        const facts: OracleFacts = { category, sponsor_category };
        expect(asked(facts)).toEqual([]);
        expect(asked({ ...facts, other_paid_activity: "no" })).toEqual([]);
      }
    }
  });

  it("a Second Home vehicle asks none of the ten, even with a government sponsor", () => {
    for (const investment_vehicle of ["property", "bank_deposit"]) {
      expect(
        asked({
          category: "invest",
          sponsor_category: "GOVERNMENT",
          investment_vehicle,
          investment_establishes_company: "yes",
        }),
      ).toEqual([]);
    }
  });

  it("the world-figure question needs an INVESTMENT vehicle AND a government sponsor", () => {
    const base = { category: "invest", investment_vehicle: "pt_pma" };
    expect(
      asked({ ...base, sponsor_category: "GOVERNMENT" }).includes(
        "sponsor_world_figure_invitation",
      ),
    ).toBe(true);
    for (const sponsor_category of SPONSORS.filter((s) => s !== "GOVERNMENT")) {
      expect(asked({ ...base, sponsor_category })).not.toContain(
        "sponsor_world_figure_invitation",
      );
    }
  });

  it.each([
    [
      { investment_establishes_company: "yes" },
      [
        "investment_establishes_company",
        "investment_foreign_branch",
        "investment_ikn_subsidiary",
        "investment_meets_threshold",
      ],
    ],
    [
      {
        investment_establishes_company: "no",
        investment_foreign_branch: "no",
        investment_capital_market_only: "yes",
      },
      [
        "investment_establishes_company",
        "investment_capital_market_only",
        "investment_foreign_branch",
        "investment_meets_threshold",
      ],
    ],
    [
      {
        investment_establishes_company: "no",
        investment_foreign_branch: "no",
        investment_capital_market_only: "no",
      },
      [
        "investment_establishes_company",
        "investment_capital_market_only",
        "investment_foreign_branch",
      ],
    ],
    // A stale IKN "yes" left behind by an edit to "no company" is never
    // re-asked and never read: its question is off the sequence, and
    // fact-mapper.ts sends the fact KNOWN(false) on the company answer.
    [
      {
        investment_establishes_company: "no",
        investment_foreign_branch: "no",
        investment_ikn_subsidiary: "yes",
        investment_capital_market_only: "no",
      },
      [
        "investment_establishes_company",
        "investment_capital_market_only",
        "investment_foreign_branch",
      ],
    ],
    [{}, ["investment_establishes_company", "investment_foreign_branch"]],
  ])("investment routes for %j are %j", (routeAnswers, expected) => {
    expect(
      asked({
        category: "invest",
        sponsor_category: "NONE",
        investment_vehicle: "merit",
        ...routeAnswers,
      }),
    ).toEqual(expected);
  });

  it("the capital-market vehicle keeps INVESTMENT and asks the same route questions", () => {
    expect(
      asked({
        category: "invest",
        sponsor_category: "NONE",
        investment_vehicle: "capital_market",
        investment_establishes_company: "no",
        investment_capital_market_only: "yes",
      }),
    ).toEqual([
      "investment_establishes_company",
      "investment_capital_market_only",
      "investment_foreign_branch",
      "investment_meets_threshold",
    ]);
  });

  /**
   * Council round 3 (council/journal.jsonl), on `el.e28c.capital-market`
   * (seq-21): its premises are `INVESTMENT` + `investment.capital_market_only`
   * + `investment.meets_published_threshold` — there is NO
   * "and no company is being established" conjunct. So if a stale
   * `investment_capital_market_only = "yes"` survived an edit back to "yes, I
   * am establishing a company", `fact-mapper.ts` would send it KNOWN(true) and
   * the engine would hand the same applicant E28B ("establishing a company")
   * and E28C ("capital market ONLY, without establishing a company") at once —
   * two answers that contradict each other.
   *
   * It cannot survive, and this is the measurement rather than the argument:
   * `EDIT` truncates history AT its target and `pruneFacts` then drops every
   * fact whose question is no longer in that history. The mapper reads
   * `state.facts`, so the fact it cannot see is the fact it cannot send.
   * The mirror case — a stale `investment_ikn_subsidiary` — is covered above
   * by the route table AND by an explicit KNOWN(false) in the mapper; this one
   * needs no mapper rule because the answer itself is gone.
   */
  it("innocence: an edit back to 'I am establishing a company' erases the stale capital-market answer", () => {
    const answers: Record<string, string> = {
      in_indonesia: "no",
      holds_stay_permit: "no",
      trip_scope: "single",
      category: "invest",
      sponsor_category: "NONE",
      investment_vehicle: "merit",
      investment_establishes_company: "no",
      investment_capital_market_only: "yes",
      investment_foreign_branch: "no",
      investment_meets_threshold: "yes",
    };
    /** Answer whatever question is on screen until `stopAt` is reached, using
     * the corpus generator's own default (first option / fixed synthetic
     * value) for every question this test has no opinion about. Bounded, so a
     * routing bug is a red here and never a hung suite. */
    const driveTo = (start: FlowState, stopAt: string): FlowState => {
      let state = start;
      for (let step = 0; step < 40; step += 1) {
        const head = state.history[state.history.length - 1];
        if (head.kind !== "question") break;
        if (head.questionId === stopAt) return state;
        state = answer(
          state,
          head.questionId,
          answerFor(head.questionId, answers),
        );
      }
      throw new Error(
        `never reached ${stopAt}; asked ${state.history
          .filter((n) => n.kind === "question")
          .map((n) => (n as { questionId: string }).questionId)
          .join(", ")}`,
      );
    };

    let state = initialFlowState("en");
    state = reduce(state, { type: "ADVANCE" });
    state = driveTo(state, "investment_meets_threshold");
    expect(state.facts.investment_capital_market_only).toBe("yes");
    expect(state.facts.investment_establishes_company).toBe("no");

    state = reduce(state, {
      type: "EDIT",
      questionId: "investment_establishes_company",
    });
    state = answer(state, "investment_establishes_company", "yes");

    expect(state.facts.investment_capital_market_only).toBeUndefined();
    expect(
      getCategoryQuestionIds(state.facts).includes(
        "investment_capital_market_only",
      ),
    ).toBe(false);
  });

  it("walks a government-invited employee through both sponsor questions to the verdict", () => {
    let state = startOffshore("work");
    state = answer(state, "trip_scope", "single");
    state = answer(state, "sponsor_category", "GOVERNMENT");
    expectQuestion(state, "sponsor_government_invitation");
    state = answer(state, "sponsor_government_invitation", "yes");
    expectQuestion(state, "sponsor_trade_office");
    state = answer(state, "sponsor_trade_office", "no");
    expectQuestion(state, "work_payer");
  });
});

// W-VO-Q, coverage report §B2 rows 16–17: the two corpus walks that still end
// NEEDS_INPUT at engine level. The doctrine (COMMON-ADD §B, Zero 2026-09-13)
// allows NEEDS_INPUT only as "the missing fact, re-asked by the tree" — so
// what must hold is that the interview CAN ask each blocking fact again, not
// that the walk hides it. Row 16 (`unsure` on the work sponsor) asks it in its
// own history; row 17 (`still_unsure` retirement basis) reaches it as a
// follow-up, the same question the family branch asks.
describe("§B2 rows 16–17 — the blocking fact is one the tree re-asks", () => {
  it("row 16: offshore/other/paid/sponsor_unsure asks work_sponsor_confirmed on its own walk", () => {
    const facts: OracleFacts = {
      in_indonesia: "no",
      holds_stay_permit: "no",
      category: "other",
      other_paid_activity: "yes",
      sponsor_category: "NONE",
      work_payer: "yes",
    };
    expect(getCategoryQuestionIds(facts)).toContain("work_sponsor_confirmed");
    expect(QUESTIONS.work_sponsor_confirmed.decisionMapping).toEqual({
      kind: "FACT",
      factPaths: ["work.indonesian_work_sponsor_confirmed"],
    });
  });

  it("row 17: offshore/retirement/undecided/age64/still_unsure can follow up on family_sponsor_confirmed", () => {
    const facts: OracleFacts = {
      in_indonesia: "no",
      holds_stay_permit: "no",
      category: "retirement",
      retirement_basis: "undecided",
      retirement_undecided_basis: "still_unsure",
    };
    expect(getCategoryQuestionIds(facts)).not.toContain(
      "family_sponsor_confirmed",
    );
    expect(followUpPrerequisitesMet("family_sponsor_confirmed", facts)).toBe(
      true,
    );
  });
});

// W-VO-Q item 7 (owner ruling 2026-09-14): the business visitor exploring
// whether to invest or open a business. INVESTMENT purpose (`mapPurposes`),
// so the explorer is asked what `el.d12-*` and `el.c2.business` read, and —
// only when the conversion answer excludes D12 — what the investor products
// read, so the engine is never left asking for a fact the walk skipped.
describe("business explorer — the D12 sequence", () => {
  const explorer: OracleFacts = {
    in_indonesia: "no",
    category: "business",
    business_activity: "exploring",
  };

  it("offshore, asks the sponsor and the conversion question, then the stay, and nothing a business meeting reads", () => {
    expect(getCategoryQuestionIds(explorer)).toEqual([
      "business_activity",
      "family_sponsor_confirmed",
      "wants_onshore_conversion",
      "stay_days",
    ]);
    expect(
      getCategoryQuestionIds({ ...explorer, wants_onshore_conversion: "no" }),
    ).toEqual([
      "business_activity",
      "family_sponsor_confirmed",
      "wants_onshore_conversion",
      "stay_days",
    ]);
  });

  it("onshore, never asks the conversion question twice (the spine already did)", () => {
    expect(
      getCategoryQuestionIds({
        ...explorer,
        in_indonesia: "yes",
        wants_onshore_conversion: "no",
      }),
    ).toEqual(["business_activity", "family_sponsor_confirmed", "stay_days"]);
  });

  const INVESTOR_FACTS_AFTER_THE_STAY = [
    "business_activity",
    "family_sponsor_confirmed",
    "wants_onshore_conversion",
    "stay_days",
    "sponsor_category",
    "investment_pt_pma",
    "investment_establishes_company",
    "investment_foreign_branch",
  ];

  it("a conversion yes asks the investor facts after the stay: sponsor, PT PMA commitment, routes", () => {
    expect(
      getCategoryQuestionIds({ ...explorer, wants_onshore_conversion: "yes" }),
    ).toEqual(INVESTOR_FACTS_AFTER_THE_STAY);
    const committed = getCategoryQuestionIds({
      ...explorer,
      wants_onshore_conversion: "yes",
      sponsor_category: "GOVERNMENT",
      investment_pt_pma: "yes",
      investment_establishes_company: "yes",
    });
    expect(committed).toEqual([
      "business_activity",
      "family_sponsor_confirmed",
      "wants_onshore_conversion",
      "stay_days",
      "sponsor_category",
      "sponsor_world_figure_invitation",
      "investment_pt_pma",
      "investment_capital_idr",
      "investment_paid_up_capital_idr",
      "investment_role",
      "investment_establishes_company",
      "investment_foreign_branch",
      "investment_ikn_subsidiary",
      "investment_meets_threshold",
    ]);
  });

  it("a stay beyond D12's own bound asks the investor facts too; a stay inside it does not", () => {
    const noConversion = { ...explorer, wants_onshore_conversion: "no" };
    expect(
      getCategoryQuestionIds({
        ...noConversion,
        stay_days: String(D12_MAX_STAY_DAYS + 1),
      }),
    ).toEqual(INVESTOR_FACTS_AFTER_THE_STAY);
    expect(
      getCategoryQuestionIds({
        ...noConversion,
        stay_days: String(D12_MAX_STAY_DAYS),
      }),
    ).toEqual([
      "business_activity",
      "family_sponsor_confirmed",
      "wants_onshore_conversion",
      "stay_days",
    ]);
  });

  /** The SIGNED pack and the CANDIDATE source pack are resolved SEPARATELY,
   * and the constant must equal BOTH bounds.
   *
   * Reading only "the highest sequence on disk" was an under-match (council
   * round 6, council/journal.jsonl): a future window could move the bound in
   * an unsigned source pack AND in this constant together, leave the signed
   * pack — the one production actually evaluates — at the old bound, and this
   * test would still be green while the live interview asked the investor
   * questions at the wrong day count. Measured when the finding was taken:
   * sequences 1-19 carry `lte 180`, sequence 20 (signed, in force) and
   * sequence 21 (source, candidate) both carry `lte 360`, so the two agree
   * today and this assertion is a pin, not a widening. If they ever disagree,
   * the constant cannot satisfy both and the red names which side moved. */
  it("D12_MAX_STAY_DAYS is the stay bound of el.d12-multi-entry-support in BOTH the highest signed pack and the highest source pack", () => {
    const packs = path.resolve(
      path.dirname(fileURLToPath(import.meta.url)),
      "../../../../../../backend-rag/backend/services/visa_engine/contracts/packs",
    );
    type Pack = { sequence: number; rules: Array<Record<string, unknown>> };
    const highest: Record<"signed" | "source", Pack | null> = {
      signed: null,
      source: null,
    };
    for (const name of fs.readdirSync(packs)) {
      const match = /^rulepack-prod-\d+\.(signed|source)\.json$/.exec(name);
      if (!match) continue;
      const kind = match[1] as "signed" | "source";
      const raw = JSON.parse(fs.readFileSync(path.join(packs, name), "utf-8"));
      const payload = (raw.payload ?? raw) as {
        sequence?: number;
        rules?: Array<Record<string, unknown>>;
      };
      if (typeof payload.sequence !== "number" || !payload.rules) continue;
      const best = highest[kind];
      if (best === null || payload.sequence > best.sequence) {
        highest[kind] = { sequence: payload.sequence, rules: payload.rules };
      }
    }
    const stayBound = (pack: Pack | null): unknown => {
      const rule = pack?.rules.find(
        (r) => r.rule_id === "el.d12-multi-entry-support",
      ) as { when: { args: Array<Record<string, unknown>> } } | undefined;
      return rule?.when.args.find(
        (arg) => arg.op === "lte" && arg.fact === "intent.stay_days",
      )?.value;
    };
    // Both lanes must be present: an empty one would make its assertion
    // vacuously true against `undefined`, which is the failure shape this
    // test exists to refuse.
    expect(highest.signed?.sequence ?? 0).toBeGreaterThanOrEqual(20);
    expect(highest.source?.sequence ?? 0).toBeGreaterThanOrEqual(20);
    expect(stayBound(highest.signed)).toBe(D12_MAX_STAY_DAYS);
    expect(stayBound(highest.source)).toBe(D12_MAX_STAY_DAYS);
  });

  it("the capital-market vehicle asks the PT PMA commitment, and the capital questions only after a yes", () => {
    const base: OracleFacts = {
      category: "invest",
      sponsor_category: "NONE",
      investment_vehicle: "capital_market",
    };
    const ids = getCategoryQuestionIds(base);
    expect(ids).toContain("investment_pt_pma");
    expect(ids).not.toContain("investment_capital_idr");
    expect(
      getCategoryQuestionIds({ ...base, investment_pt_pma: "yes" }),
    ).toEqual(
      expect.arrayContaining([
        "investment_capital_idr",
        "investment_paid_up_capital_idr",
        "investment_role",
      ]),
    );
  });

  it("guilt: every other business answer keeps the meetings sequence", () => {
    for (const { key } of QUESTIONS.business_activity.options) {
      if (key === "exploring") continue;
      expect(
        getCategoryQuestionIds({
          ...explorer,
          business_activity: key,
          wants_onshore_conversion: "yes",
        }),
      ).toEqual([
        "business_activity",
        "work_indonesia_compensation",
        "stay_days",
        "entry_pattern",
      ]);
    }
  });

  it("walks an offshore explorer to the verdict through the real reducer", () => {
    let state = startOffshore("business");
    state = answer(state, "trip_scope", "single");
    state = answer(state, "business_activity", "exploring");
    state = answer(state, "family_sponsor_confirmed", "no");
    state = answer(state, "wants_onshore_conversion", "no");
    state = answer(state, "stay_days", "90");
    expectQuestion(state, "review_gate");
  });
});
