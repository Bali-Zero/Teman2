import { describe, expect, it } from "vitest";
import { evaluate, filterCandidates, pathsRemaining } from "./mock-engine";
import type { OracleFacts } from "./tree";

const CLEAN_REVIEW = { review_gate: "none" };

function factsFor(overrides: OracleFacts): OracleFacts {
  return { ...overrides };
}

describe("mock-engine — determinism", () => {
  it("same facts always produce the same result", () => {
    const facts = factsFor({
      in_indonesia: "no",
      category: "work",
      work_payer: "yes",
      ...CLEAN_REVIEW,
    });
    const a = evaluate(facts);
    const b = evaluate({ ...facts });
    expect(a).toEqual(b);
  });

  it("pathsRemaining narrows monotonically as facts accumulate", () => {
    const step1 = pathsRemaining({});
    const step2 = pathsRemaining({ category: "work" });
    const step3 = pathsRemaining({ category: "work", work_payer: "no" });
    expect(step2).toBeLessThanOrEqual(step1);
    expect(step3).toBeLessThanOrEqual(step2);
  });
});

describe("mock-engine — all five RecommendState values are reachable", () => {
  it("NEEDS_INPUT mid-interview", () => {
    const result = evaluate(factsFor({ in_indonesia: "no" }));
    expect(result.state).toBe("NEEDS_INPUT");
  });

  it("SUPPORTED_CANDIDATES on a clean work lane", () => {
    const result = evaluate(
      factsFor({
        in_indonesia: "no",
        category: "work",
        work_payer: "yes",
        ...CLEAN_REVIEW,
      }),
    );
    expect(result.state).toBe("SUPPORTED_CANDIDATES");
    expect(result.candidates.length).toBeGreaterThan(0);
    expect(result.candidates.some((c) => c.code === "E23")).toBe(true);
  });

  it("HUMAN_REVIEW_REQUIRED when the review gate is flagged", () => {
    const result = evaluate(
      factsFor({
        in_indonesia: "no",
        category: "work",
        work_payer: "yes",
        review_gate: "flagged",
      }),
    );
    expect(result.state).toBe("HUMAN_REVIEW_REQUIRED");
    expect(result.candidates).toEqual([]);
  });

  it("HUMAN_REVIEW_REQUIRED for the 7 non-behavioral categories (honest routing)", () => {
    const result = evaluate(
      factsFor({ in_indonesia: "no", category: "family", ...CLEAN_REVIEW }),
    );
    expect(result.state).toBe("HUMAN_REVIEW_REQUIRED");
  });

  it("HUMAN_REVIEW_REQUIRED on an urgent onshore lane, before the category is even chosen", () => {
    const today = new Date(Date.UTC(2026, 6, 17));
    const result = evaluate(
      factsFor({ in_indonesia: "yes", permit_expiry: "2026-07-18" }),
      today,
    );
    expect(result.state).toBe("HUMAN_REVIEW_REQUIRED");
  });

  it("NO_SUPPORTED_PATH when work category has no Indonesian payer, with alternatives offered", () => {
    const result = evaluate(
      factsFor({
        in_indonesia: "no",
        category: "work",
        work_payer: "no",
        ...CLEAN_REVIEW,
      }),
    );
    expect(result.state).toBe("NO_SUPPORTED_PATH");
    expect(result.candidates).toEqual([]);
    expect(result.alternativeCategories?.length).toBeGreaterThan(0);
  });

  it("TEMPORARILY_UNAVAILABLE for an extended tourism stay (honest limitation, no invented dates)", () => {
    const result = evaluate(
      factsFor({
        in_indonesia: "no",
        category: "tourism",
        tourism_duration: "extended",
        ...CLEAN_REVIEW,
      }),
    );
    expect(result.state).toBe("TEMPORARILY_UNAVAILABLE");
  });
});

describe("mock-engine — skip-with-assumption (NotSure)", () => {
  it("records a visible assumption when a conservative-branch question is skipped", () => {
    const result = evaluate(
      factsFor({
        in_indonesia: "no",
        category: "tourism",
        tourism_duration: "unsure",
        ...CLEAN_REVIEW,
      }),
    );
    expect(result.assumptions).toEqual([{ questionId: "tourism_duration" }]);
    // conservative branch resolves to "short" — still reaches a decision.
    expect(result.state).toBe("SUPPORTED_CANDIDATES");
  });

  it("load-bearing rule: never guess on money/payer/clients — 'unsure' forces human review", () => {
    const payer = evaluate(
      factsFor({
        in_indonesia: "no",
        category: "work",
        work_payer: "unsure",
        ...CLEAN_REVIEW,
      }),
    );
    expect(payer.state).toBe("HUMAN_REVIEW_REQUIRED");
    expect(payer.assumptions).toEqual([{ questionId: "work_payer" }]);

    const clients = evaluate(
      factsFor({
        in_indonesia: "no",
        category: "remote",
        remote_clients: "unsure",
        remote_income: "above",
        ...CLEAN_REVIEW,
      }),
    );
    expect(clients.state).toBe("HUMAN_REVIEW_REQUIRED");

    const income = evaluate(
      factsFor({
        in_indonesia: "no",
        category: "remote",
        remote_clients: "foreign",
        remote_income: "unsure",
        ...CLEAN_REVIEW,
      }),
    );
    expect(income.state).toBe("HUMAN_REVIEW_REQUIRED");
  });
});

describe("mock-engine — review gate forces review, never a candidate", () => {
  it("any flagged review item overrides an otherwise-supported path", () => {
    const clean = evaluate(
      factsFor({
        in_indonesia: "no",
        category: "work",
        work_payer: "yes",
        review_gate: "none",
      }),
    );
    expect(clean.state).toBe("SUPPORTED_CANDIDATES");

    const flagged = evaluate(
      factsFor({
        in_indonesia: "no",
        category: "work",
        work_payer: "yes",
        review_gate: "flagged",
      }),
    );
    expect(flagged.state).toBe("HUMAN_REVIEW_REQUIRED");
    expect(flagged.candidates).toEqual([]);
  });
});

describe("mock-engine — soft downgrade, not exclusion", () => {
  it("remote income below the floor downgrades E33G instead of excluding it", () => {
    const result = evaluate(
      factsFor({
        in_indonesia: "no",
        category: "remote",
        remote_clients: "foreign",
        remote_income: "below",
        ...CLEAN_REVIEW,
      }),
    );
    expect(result.state).toBe("SUPPORTED_CANDIDATES");
    const e33g = result.candidates.find((c) => c.code === "E33G");
    expect(e33g?.eligibility).toBe("conditional");
  });
});

describe("mock-engine — filterCandidates", () => {
  it("never excludes a card on an unanswered fact", () => {
    const all = filterCandidates({});
    expect(all.length).toBe(pathsRemaining({}));
  });
});

describe("mock-engine — in_indonesia normalization (finding #2, adversarial review 2026-07-17)", () => {
  it("an unsure in_indonesia resolves to the SAME onshore requirement as a literal 'yes' — never silently skips permit_expiry", () => {
    const literalYesIncomplete = evaluate(
      factsFor({
        in_indonesia: "yes",
        category: "tourism",
        tourism_duration: "short",
        ...CLEAN_REVIEW,
      }),
    );
    const unsureIncomplete = evaluate(
      factsFor({
        in_indonesia: "unsure",
        category: "tourism",
        tourism_duration: "short",
        ...CLEAN_REVIEW,
      }),
    );
    // Both are missing permit_expiry (required once resolved onshore) —
    // before the fix, the "unsure" case's raw `!== "yes"` check silently
    // skipped that requirement and could reach SUPPORTED_CANDIDATES.
    expect(literalYesIncomplete.state).toBe("NEEDS_INPUT");
    expect(unsureIncomplete.state).toBe("NEEDS_INPUT");
  });

  it("with permit_expiry answered, unsure in_indonesia reaches a decision exactly like a literal 'yes'", () => {
    const today = new Date(Date.UTC(2026, 6, 17));
    const result = evaluate(
      factsFor({
        in_indonesia: "unsure",
        permit_expiry: "2026-12-01",
        category: "tourism",
        tourism_duration: "short",
        ...CLEAN_REVIEW,
      }),
      today,
    );
    expect(result.state).toBe("SUPPORTED_CANDIDATES");
  });
});

describe("mock-engine — lane-gated candidates (finding #3, adversarial review 2026-07-17)", () => {
  const today = new Date(Date.UTC(2026, 6, 17)); // 2026-07-17

  it("Bridging Visa is absent outside the 'bridging' lane (planning: 60+ days out)", () => {
    const result = filterCandidates(
      factsFor({ in_indonesia: "yes", permit_expiry: "2026-12-01" }),
      today,
    );
    expect(result.some((c) => c.code === "BRIDGING")).toBe(false);
  });

  it("Bridging Visa is present and ranked first in the 'bridging' lane (3-7 days out)", () => {
    const result = evaluate(
      factsFor({
        in_indonesia: "yes",
        permit_expiry: "2026-07-22", // 5 days out — bridging lane per tree.test.ts table
        category: "tourism",
        tourism_duration: "short",
        ...CLEAN_REVIEW,
      }),
      today,
    );
    expect(result.state).toBe("SUPPORTED_CANDIDATES");
    expect(result.candidates[0]?.code).toBe("BRIDGING");
  });

  it("offshore facts never admit Bridging Visa (lane is null, but requiredFacts.in_indonesia already excludes it)", () => {
    const result = filterCandidates(factsFor({ in_indonesia: "no" }));
    expect(result.some((c) => c.code === "BRIDGING")).toBe(false);
  });
});

describe("mock-engine — review-gate CSV values (finding #5, adversarial review 2026-07-17)", () => {
  it("exactly 'none' is clean; any other value (including a multi-item CSV) forces review", () => {
    const clean = evaluate(
      factsFor({
        in_indonesia: "no",
        category: "work",
        work_payer: "yes",
        review_gate: "none",
      }),
    );
    expect(clean.state).toBe("SUPPORTED_CANDIDATES");

    const csvFlagged = evaluate(
      factsFor({
        in_indonesia: "no",
        category: "work",
        work_payer: "yes",
        review_gate: "criminal_record,health_flag",
      }),
    );
    expect(csvFlagged.state).toBe("HUMAN_REVIEW_REQUIRED");
    expect(csvFlagged.candidates).toEqual([]);

    const singleItemFlagged = evaluate(
      factsFor({
        in_indonesia: "no",
        category: "work",
        work_payer: "yes",
        review_gate: "not_certain",
      }),
    );
    expect(singleItemFlagged.state).toBe("HUMAN_REVIEW_REQUIRED");
  });
});

describe("mock-engine — E33G reachable 'likely-not' on mixed clients (finding #14, adversarial review 2026-07-17)", () => {
  it("mixed clients downgrades E33G to likely-not instead of excluding it from candidates", () => {
    const result = evaluate(
      factsFor({
        in_indonesia: "no",
        category: "remote",
        remote_clients: "mixed",
        remote_income: "above",
        ...CLEAN_REVIEW,
      }),
    );
    expect(result.state).toBe("SUPPORTED_CANDIDATES");
    const e33g = result.candidates.find((c) => c.code === "E33G");
    expect(e33g).toBeDefined();
    expect(e33g?.eligibility).toBe("likely-not");
  });

  it("indonesian-employed clients still hard-excludes E33G (a different lane entirely)", () => {
    const result = filterCandidates(
      factsFor({
        in_indonesia: "no",
        category: "remote",
        remote_clients: "indonesian",
      }),
    );
    expect(result.some((c) => c.code === "E33G")).toBe(false);
  });
});
