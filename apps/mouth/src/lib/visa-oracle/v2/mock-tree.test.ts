import { describe, expect, it } from "vitest";

import {
  CATEGORIES,
  Q0_EXPIRY_DATE,
  Q0_IN_INDONESIA,
  Q1_CATEGORY,
  RW_DURATION,
  RW_INCOME_BAND,
  RW_WHO_PAYS,
  answer,
  computeLane,
  createInterview,
  nextQuestion,
  pathsRemaining,
  resolveOutcome,
  skip,
} from "./mock-tree";
import type { InterviewState } from "./types";

describe("computeLane", () => {
  it("routes an already-expired stay permit to overstay-help", () => {
    expect(computeLane(-5)).toBe("overstay-help");
    expect(computeLane(0)).toBe("overstay-help");
  });

  it("routes 1-2 days remaining to urgent-review (never bridging)", () => {
    expect(computeLane(1)).toBe("urgent-review");
    expect(computeLane(2)).toBe("urgent-review");
  });

  it("routes 3-7 days remaining to bridging-urgent", () => {
    expect(computeLane(3)).toBe("bridging-urgent");
    expect(computeLane(7)).toBe("bridging-urgent");
  });

  it("routes 8-60 days remaining to extend-convert", () => {
    expect(computeLane(8)).toBe("extend-convert");
    expect(computeLane(60)).toBe("extend-convert");
  });

  it("routes 61+ days remaining to plan", () => {
    expect(computeLane(61)).toBe("plan");
  });
});

describe("answer — local-time date lane routing (Codex sol review F1 regression)", () => {
  it("routes a date exactly 7 LOCAL days ahead to bridging-urgent, regardless of the hour of `today`", () => {
    // Reviewer's exact bug report: at 00:30 UTC+8, an expiry seven local
    // days away was counted as eight days by a UTC-based `today` and
    // mis-routed to extend-convert instead of bridging-urgent. Local-time
    // day-counting must be invariant to the WALL-CLOCK HOUR of `today` —
    // only the local calendar day matters. `new Date(y, m, d, h, min)`
    // constructs a genuinely local Date in the test runner's own
    // timezone, so this exercises the same local/UTC divergence class of
    // bug the report describes, independent of which timezone CI runs in.
    for (const hour of [0, 0.5, 6, 12, 18, 23.98]) {
      const wholeHour = Math.floor(hour);
      const minute = Math.round((hour - wholeHour) * 60);
      const today = new Date(2026, 6, 17, wholeHour, minute);

      let state = createInterview();
      state = answer(state, Q0_IN_INDONESIA.id, "yes", today);
      state = answer(state, Q0_EXPIRY_DATE.id, "2026-07-24", today);

      expect(state.lane).toBe("bridging-urgent");
    }
  });

  it("draws the bridging-urgent/extend-convert boundary at exactly 7 vs 8 local days, using local Date construction throughout", () => {
    const today = new Date(2026, 6, 17, 0, 30); // 00:30 local, the report's exact repro hour
    let s7 = createInterview();
    s7 = answer(s7, Q0_IN_INDONESIA.id, "yes", today);
    s7 = answer(s7, Q0_EXPIRY_DATE.id, "2026-07-24", today); // 7 local days ahead
    expect(s7.lane).toBe("bridging-urgent");

    let s8 = createInterview();
    s8 = answer(s8, Q0_IN_INDONESIA.id, "yes", today);
    s8 = answer(s8, Q0_EXPIRY_DATE.id, "2026-07-25", today); // 8 local days ahead
    expect(s8.lane).toBe("extend-convert");
  });
});

describe("answer — fail-closed on ISO-shaped-but-invalid dates (Codex sol review F2 regression)", () => {
  it("'2026-99-99' does not advance state, sets a validationError, and never reaches computeLane", () => {
    const s0 = createInterview();
    const s1 = answer(s0, Q0_IN_INDONESIA.id, "yes");
    const s2 = answer(s1, Q0_EXPIRY_DATE.id, "2026-99-99");

    expect(s2.answers[Q0_EXPIRY_DATE.id]).toBeUndefined();
    expect(s2.lane).toBeUndefined();
    expect(s2.validationError).toEqual({
      qid: Q0_EXPIRY_DATE.id,
      message: expect.any(Object),
    });
    // Unchanged: still parked on the date question, not advanced to category.
    expect(nextQuestion(s2)?.id).toBe(Q0_EXPIRY_DATE.id);
  });

  it("'2026-02-30' (February has no 30th) does not advance state and sets a validationError", () => {
    const s0 = createInterview();
    const s1 = answer(s0, Q0_IN_INDONESIA.id, "yes");
    const s2 = answer(s1, Q0_EXPIRY_DATE.id, "2026-02-30");

    expect(s2.answers[Q0_EXPIRY_DATE.id]).toBeUndefined();
    expect(s2.lane).toBeUndefined();
    expect(s2.validationError?.qid).toBe(Q0_EXPIRY_DATE.id);
  });

  it("clears a prior validationError on the next successfully-processed answer", () => {
    const today = new Date(2026, 6, 17, 12, 0);
    const s0 = createInterview();
    const s1 = answer(s0, Q0_IN_INDONESIA.id, "yes", today);
    const s2 = answer(s1, Q0_EXPIRY_DATE.id, "2026-99-99", today);
    expect(s2.validationError).toBeDefined();

    const s3 = answer(s2, Q0_EXPIRY_DATE.id, "2026-08-01", today);
    expect(s3.validationError).toBeUndefined();
    expect(s3.lane).toBeDefined();
    expect(s3.answers[Q0_EXPIRY_DATE.id]).toBe("2026-08-01");
  });

  it("still accepts the 'unknown' skip sentinel (not a calendar date, but not user-typed garbage either)", () => {
    const s0 = createInterview();
    const s1 = answer(s0, Q0_IN_INDONESIA.id, "yes");
    const s2 = skip(s1, Q0_EXPIRY_DATE.id);
    expect(s2.validationError).toBeUndefined();
    expect(s2.lane).toBe("urgent-review");
  });
});

describe("nextQuestion + answer — offshore walkthrough", () => {
  it("routes the 'no' branch straight to category selection, skipping the date question", () => {
    const s0 = createInterview();
    expect(nextQuestion(s0)?.id).toBe(Q0_IN_INDONESIA.id);

    const s1 = answer(s0, Q0_IN_INDONESIA.id, "no");
    expect(nextQuestion(s1)?.id).toBe(Q1_CATEGORY.id);
  });

  it("routes the 'yes' branch through the expiry-date question before category", () => {
    // Fixed `today` (F1) — removes wall-clock flakiness from this test.
    const today = new Date(2026, 6, 17, 12, 0);
    const s0 = createInterview();
    const s1 = answer(s0, Q0_IN_INDONESIA.id, "yes", today);
    expect(nextQuestion(s1)?.id).toBe(Q0_EXPIRY_DATE.id);

    const s2 = answer(s1, Q0_EXPIRY_DATE.id, "2026-08-01", today);
    expect(nextQuestion(s2)?.id).toBe(Q1_CATEGORY.id);
    expect(s2.lane).toBeDefined();
  });

  it("terminates (nextQuestion === null) for every non-remote-worker category", () => {
    for (const category of CATEGORIES) {
      if (category.key === "remote-worker") continue;
      const s0 = createInterview();
      const s1 = answer(s0, Q0_IN_INDONESIA.id, "no");
      const s2 = answer(s1, Q1_CATEGORY.id, category.key);
      expect(nextQuestion(s2)).toBeNull();
    }
  });

  it("walks the full remote-worker sub-tree before terminating", () => {
    const s0 = createInterview();
    const s1 = answer(s0, Q0_IN_INDONESIA.id, "no");
    const s2 = answer(s1, Q1_CATEGORY.id, "remote-worker");
    expect(nextQuestion(s2)?.id).toBe(RW_WHO_PAYS.id);

    const s3 = answer(s2, RW_WHO_PAYS.id, "foreign-clients");
    expect(nextQuestion(s3)?.id).toBe(RW_INCOME_BAND.id);

    const s4 = answer(s3, RW_INCOME_BAND.id, "above-floor");
    expect(nextQuestion(s4)?.id).toBe(RW_DURATION.id);

    const s5 = answer(s4, RW_DURATION.id, "long-term");
    expect(nextQuestion(s5)).toBeNull();
  });
});

describe("pathsRemaining — monotonicity", () => {
  it("never increases across a full played-through remote-worker interview", () => {
    let state = createInterview();
    const counts: number[] = [pathsRemaining(state)];

    state = answer(state, Q0_IN_INDONESIA.id, "no");
    counts.push(pathsRemaining(state));

    state = answer(state, Q1_CATEGORY.id, "remote-worker");
    counts.push(pathsRemaining(state));

    state = answer(state, RW_WHO_PAYS.id, "foreign-clients");
    counts.push(pathsRemaining(state));

    state = answer(state, RW_INCOME_BAND.id, "above-floor");
    counts.push(pathsRemaining(state));

    state = answer(state, RW_DURATION.id, "long-term");
    counts.push(pathsRemaining(state));

    for (let i = 1; i < counts.length; i += 1) {
      expect(counts[i]).toBeLessThanOrEqual(counts[i - 1]);
    }
    // Strictly narrows at the category/payer/income steps specifically.
    expect(counts[0]).toBe(13);
    expect(counts).toEqual([13, 13, 4, 2, 1, 1]);
  });

  it("never increases across a non-remote-worker walkthrough", () => {
    let state = createInterview();
    const before = pathsRemaining(state);
    state = answer(state, Q0_IN_INDONESIA.id, "no");
    state = answer(state, Q1_CATEGORY.id, "study");
    const after = pathsRemaining(state);
    expect(after).toBeLessThanOrEqual(before);
    expect(after).toBe(1);
  });
});

describe("skip — records the assumption", () => {
  it("records a dated assumption when skipping the expiry-date question, and resolves the conservative lane", () => {
    const s0 = createInterview();
    const s1 = answer(s0, Q0_IN_INDONESIA.id, "yes");
    const s2 = skip(s1, Q0_EXPIRY_DATE.id);

    expect(s2.answers[Q0_EXPIRY_DATE.id]).toBe("unknown");
    expect(s2.assumptions).toContainEqual({
      qid: Q0_EXPIRY_DATE.id,
      assumedKey: "unknown",
    });
    expect(s2.lane).toBe("urgent-review");
  });

  it("records the conservative duration assumption for the remote-worker tree", () => {
    let state = createInterview();
    state = answer(state, Q0_IN_INDONESIA.id, "no");
    state = answer(state, Q1_CATEGORY.id, "remote-worker");
    state = answer(state, RW_WHO_PAYS.id, "foreign-clients");
    state = answer(state, RW_INCOME_BAND.id, "above-floor");
    state = skip(state, RW_DURATION.id);

    expect(state.answers[RW_DURATION.id]).toBe("short-term");
    expect(state.assumptions).toContainEqual({
      qid: RW_DURATION.id,
      assumedKey: "short-term",
    });
  });

  it("is a no-op on a question without a skipAssumption (e.g. category)", () => {
    const s0 = createInterview();
    const s1 = answer(s0, Q0_IN_INDONESIA.id, "no");
    const s2 = skip(s1, Q1_CATEGORY.id);
    expect(s2).toEqual(s1);
  });
});

describe("answer — immutability", () => {
  it("never mutates the input state, its answers map, or its assumptions array", () => {
    const original: InterviewState = createInterview();
    const originalAnswersRef = original.answers;
    const originalAssumptionsRef = original.assumptions;
    const snapshotAnswers = { ...original.answers };
    const snapshotAssumptions = [...original.assumptions];

    const next = answer(original, Q0_IN_INDONESIA.id, "yes");

    expect(original.answers).toEqual(snapshotAnswers);
    expect(original.assumptions).toEqual(snapshotAssumptions);
    expect(original.answers).toBe(originalAnswersRef);
    expect(original.assumptions).toBe(originalAssumptionsRef);
    expect(next).not.toBe(original);
    expect(next.answers).not.toBe(original.answers);
    expect(next.answers[Q0_IN_INDONESIA.id]).toBe("yes");
    expect(original.answers[Q0_IN_INDONESIA.id]).toBeUndefined();
  });
});

describe("resolveOutcome — mock pricing shape (owner ruling R1)", () => {
  function collectOutcomes() {
    const outcomes = [];

    for (const category of CATEGORIES) {
      if (category.key === "remote-worker") continue;
      let state = createInterview();
      state = answer(state, Q0_IN_INDONESIA.id, "no");
      state = answer(state, Q1_CATEGORY.id, category.key);
      outcomes.push(resolveOutcome(state));
    }

    for (const payer of RW_WHO_PAYS.options) {
      for (const income of RW_INCOME_BAND.options) {
        for (const duration of RW_DURATION.options) {
          let state = createInterview();
          state = answer(state, Q0_IN_INDONESIA.id, "no");
          state = answer(state, Q1_CATEGORY.id, "remote-worker");
          state = answer(state, RW_WHO_PAYS.id, payer.key);
          state = answer(state, RW_INCOME_BAND.id, income.key);
          state = answer(state, RW_DURATION.id, duration.key);
          outcomes.push(resolveOutcome(state));
        }
      }
    }

    return outcomes;
  }

  it("produces at least one SUPPORTED_CANDIDATES outcome with mock candidates", () => {
    const outcomes = collectOutcomes();
    const withCandidates = outcomes.filter(
      (o) => o && o.candidates && o.candidates.length > 0,
    );
    expect(withCandidates.length).toBeGreaterThan(0);
  });

  it("every candidate in every outcome carries exactly one mock all-inclusive price, never a fee/PNBP/official split field", () => {
    const outcomes = collectOutcomes();
    let candidatesChecked = 0;

    for (const outcome of outcomes) {
      if (!outcome?.candidates) continue;
      for (const candidate of outcome.candidates) {
        candidatesChecked += 1;
        expect(candidate.priceAllInclusive.mock).toBe(true);
        expect(typeof candidate.priceAllInclusive.amountIDR).toBe("number");

        const keys = Object.keys(candidate);
        const forbidden = keys.filter((k) => /fee|pnbp|official/i.test(k));
        expect(forbidden).toEqual([]);

        const priceKeys = Object.keys(candidate.priceAllInclusive);
        const forbiddenPriceKeys = priceKeys.filter((k) =>
          /fee|pnbp|official/i.test(k),
        );
        expect(forbiddenPriceKeys).toEqual([]);
      }
    }

    expect(candidatesChecked).toBeGreaterThan(0);
  });
});
