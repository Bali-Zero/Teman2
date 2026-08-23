import { describe, expect, it } from "vitest";
import * as treeRegistry from "./tree";
import {
  QUESTIONS,
  daysRemaining,
  formatIsoDateForDisplay,
  getLane,
  parseIsoDateUtc,
} from "./tree";

describe("tree.ts — interview registry only", () => {
  it("exports no frontend visa catalog or volatile display facts", () => {
    expect("MOCK_CATALOG" in treeRegistry).toBe(false);
    expect("MockVisaCard" in treeRegistry).toBe(false);
  });

  it("every question option has a resolvable i18n key shape", () => {
    for (const question of Object.values(QUESTIONS)) {
      for (const option of question.options) {
        expect(option.labelI18nKey.length).toBeGreaterThan(0);
      }
    }
  });
});

describe("tree.ts — interview decision boundary", () => {
  it("has unique ids that exactly match their registry keys", () => {
    const entries = Object.entries(QUESTIONS);
    expect(new Set(entries.map(([, question]) => question.id)).size).toBe(
      entries.length,
    );
    for (const [key, question] of entries) {
      expect(question.id).toBe(key);
    }
  });

  it("documents every question as an exact fact, review-only, or human context", () => {
    for (const question of Object.values(QUESTIONS)) {
      expect(["FACT", "REVIEW_ONLY", "HUMAN_CONTEXT"]).toContain(
        question.decisionMapping.kind,
      );
      if (question.decisionMapping.kind !== "HUMAN_CONTEXT") {
        expect(question.decisionMapping.factPaths.length).toBeGreaterThan(0);
      }
    }
  });

  it("uses only the verified current-status values read by the production pack", () => {
    expect(QUESTIONS.current_status_code.options.map(({ key }) => key)).toEqual(
      [
        "A1",
        "C1",
        "C2",
        "C6",
        "ITK_FROM_BVK",
        "ITK_FROM_VISIT_C",
        "ITK_FROM_VISIT_D",
        "ITK_PERALIHAN",
        "other",
      ],
    );
    expect(QUESTIONS.current_status_code.kind).toBe("choice");
  });

  it("bounds active overstay at the API-safe 0..36500 range", () => {
    expect(QUESTIONS.overstay_days.numberInput).toMatchObject({
      min: 0,
      max: 36_500,
      step: 1,
    });
  });

  it("keeps free-text sponsor status and legacy buckets outside engine facts", () => {
    expect(QUESTIONS.family_sponsor_status_code.decisionMapping).toEqual({
      kind: "HUMAN_CONTEXT",
    });
    expect(QUESTIONS.other_purpose.decisionMapping.kind).toBe("HUMAN_CONTEXT");
    expect(QUESTIONS.other_purpose.notSure).toEqual({
      mode: "human-review",
    });
  });

  // 2026-08-23: `family_sponsor_permit_basis` shipped as FACT in PR #4650,
  // one increment before this fix — self-declaring a Pasal 33(2) legal
  // category into engine trust, the same defect this file's sibling
  // assertion above exists to prevent. Corrected to mirror
  // `family_sponsor_status_code` exactly. See `mapFamilySponsorPermitBasis`
  // in fact-mapper.ts for the full reasoning.
  it("keeps self-declared sponsor permit basis outside engine facts too", () => {
    expect(QUESTIONS.family_sponsor_permit_basis.decisionMapping).toEqual({
      kind: "HUMAN_CONTEXT",
    });
  });

  it("does not carry the 2 dead legacy nodes (E4 slice — question-registry-audit.md §2)", () => {
    // Both were unreachable in the live graph (flow.ts's dispatch never
    // routed to them from any FIXED_CATEGORY_QUESTIONS or dynamic branch
    // sequence) and are named verbatim, deleted here, in the audit. Guilt:
    // re-adding either id must fail this test.
    expect(
      Object.prototype.hasOwnProperty.call(QUESTIONS, "tourism_duration"),
    ).toBe(false);
    expect(
      Object.prototype.hasOwnProperty.call(QUESTIONS, "remote_income"),
    ).toBe(false);
  });
});

describe("tree.ts — daysRemaining / getLane", () => {
  const today = new Date(Date.UTC(2026, 6, 17)); // 2026-07-17

  it("computes whole-day differences across the UTC boundary", () => {
    expect(daysRemaining("2026-07-17", today)).toBe(0);
    expect(daysRemaining("2026-07-18", today)).toBe(1);
    expect(daysRemaining("2026-07-16", today)).toBe(-1);
  });

  it("returns null when offshore or unanswered", () => {
    expect(getLane({}, today)).toBeNull();
    expect(getLane({ in_indonesia: "no" }, today)).toBeNull();
    expect(
      getLane({ in_indonesia: "unsure", permit_expiry: "2026-07-18" }, today),
    ).toBeNull();
    expect(getLane({ in_indonesia: "yes" }, today)).toBeNull();
  });

  it("routes the four onshore lanes per design doc §4 table", () => {
    expect(
      getLane({ in_indonesia: "yes", permit_expiry: "2026-07-10" }, today),
    ).toBe("expired");
    expect(
      getLane({ in_indonesia: "yes", permit_expiry: "2026-07-18" }, today),
    ).toBe("urgent");
    expect(
      getLane({ in_indonesia: "yes", permit_expiry: "2026-07-19" }, today),
    ).toBe("urgent");
    expect(
      getLane({ in_indonesia: "yes", permit_expiry: "2026-07-22" }, today),
    ).toBe("bridging");
    expect(
      getLane({ in_indonesia: "yes", permit_expiry: "2026-08-10" }, today),
    ).toBe("extend");
    expect(
      getLane({ in_indonesia: "yes", permit_expiry: "2026-12-01" }, today),
    ).toBe("planning");
  });

  it("never routes a 1-2 day case into bridging (R1 adversarial fix, design doc §4)", () => {
    const lane = getLane(
      { in_indonesia: "yes", permit_expiry: "2026-07-19" },
      today,
    );
    expect(lane).not.toBe("bridging");
  });
});

describe("tree.ts — strict date parsing (finding #8, adversarial review 2026-07-17)", () => {
  const today = new Date(Date.UTC(2026, 6, 17));

  it("rejects calendar-invalid dates that would otherwise silently normalize", () => {
    // 2026-02-30 doesn't exist — a naive `new Date(...)` normalizes it to
    // 2026-03-02 instead of rejecting it. parseIsoDateUtc must reject.
    expect(parseIsoDateUtc("2026-02-30")).toBeNull();
    expect(parseIsoDateUtc("2026-13-01")).toBeNull();
    expect(parseIsoDateUtc("not-a-date")).toBeNull();
    expect(parseIsoDateUtc("2026-7-4")).toBeNull(); // not zero-padded — reject, don't guess
  });

  it("accepts a real calendar date and round-trips it", () => {
    expect(parseIsoDateUtc("2026-07-17")).toBe(Date.UTC(2026, 6, 17));
  });

  it("daysRemaining and getLane treat an invalid date as unanswered, never a lane", () => {
    expect(daysRemaining("2026-02-30", today)).toBeNull();
    expect(
      getLane({ in_indonesia: "yes", permit_expiry: "2026-02-30" }, today),
    ).toBeNull();
  });

  it("formatIsoDateForDisplay renders in UTC so a negative-offset viewer never rolls the date back a day", () => {
    // en-GB dateStyle:"medium" — asserting only the day/year survives
    // verbatim (not asserting on the exact locale string format), which is
    // the finding: the calendar day the user TYPED must be the calendar
    // day DISPLAYED, regardless of the viewer's local timezone offset.
    const display = formatIsoDateForDisplay("2026-07-17", "en-GB");
    expect(display).toContain("17");
    expect(display).toContain("2026");
  });

  it("formatIsoDateForDisplay falls back to the raw string on an invalid date rather than throwing", () => {
    expect(formatIsoDateForDisplay("not-a-date", "en-GB")).toBe("not-a-date");
  });
});
