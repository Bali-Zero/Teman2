import {
  buildDeclineEducation,
  primaryDeclineCode,
  type DeclineCode,
  type EligibilitySubmission,
} from "./declineEducation";

/**
 * Bite-proof for owner decision 5 / constraint 5b: "A DECLINE is positively
 * educational, never rejecting." These tests are written to actually fail if
 * the taboo phrase creeps back in, or if a new DeclineCode ships without a
 * mapping — not just to describe the intended shape.
 */

const ALL_CODES: DeclineCode[] = [
  "NATIONALITY_NOT_ELIGIBLE",
  "PURPOSE_NOT_ELIGIBLE",
  "GROUP_CASE",
  "PASSPORT_TYPE",
  "PASSPORT_VALIDITY",
  "NOT_SELF_PAY",
  "FEEDBACK_REQUIRED",
  "URGENT_CASE",
  "SPECIAL_PASSPORT",
  "PRIOR_ISSUE",
  "ELIGIBILITY_UNCONFIRMED",
  "FASTLANE_REQUEST",
  "EXPIRY_UNKNOWN",
  "EXPIRES_TOO_SOON",
  "EXTENSION_ALREADY_USED",
  "ARRIVAL_TOO_SOON",
  "ARRIVAL_DATE_UNCONFIRMED",
  "ARRIVAL_TOO_FAR",
  "EXTENSION_EXCEEDS_MAX_STAY",
];

const baseAnswers: EligibilitySubmission = {
  case_type: "issuance",
  nationality: "USA",
  purpose: "business-meeting",
  travellers: 1,
  self_pay: true,
  extension_already_used: false,
};

describe("buildDeclineEducation — every engine code is covered", () => {
  it.each(ALL_CODES)(
    "%s produces a full 4-part education, no taboo phrase",
    (code) => {
      const edu = buildDeclineEducation(code, baseAnswers);
      expect(edu.mirror.length).toBeGreaterThan(0);
      expect(edu.forbids.length).toBeGreaterThan(0);
      expect(edu.alternative.length).toBeGreaterThan(0);
      expect(["oracle", "whatsapp"]).toContain(edu.routeKind);

      // Bite: mutate the taboo phrase in — this assertion must catch it.
      const rejectingShapes = [
        /not for you/i,
        /you are not eligible for anything/i,
      ];
      for (const re of rejectingShapes) {
        expect(edu.forbids).not.toMatch(re);
        expect(edu.mirror).not.toMatch(re);
        expect(edu.alternative).not.toMatch(re);
      }
    },
  );
});

describe("buildDeclineEducation — mirror uses the customer's OWN answer, not a generic line", () => {
  it("PURPOSE_NOT_ELIGIBLE names the actual submitted purpose", () => {
    const edu = buildDeclineEducation("PURPOSE_NOT_ELIGIBLE", {
      ...baseAnswers,
      purpose: "business-meeting",
    });
    expect(edu.mirror).toContain("business meeting");

    const eduFamily = buildDeclineEducation("PURPOSE_NOT_ELIGIBLE", {
      ...baseAnswers,
      purpose: "family",
    });
    expect(eduFamily.mirror).toContain("visiting family");
    // Bite: the two must actually differ — a hardcoded string would pass the
    // "contains" checks above with the wrong purpose baked in.
    expect(edu.mirror).not.toEqual(eduFamily.mirror);
  });

  it("NATIONALITY_NOT_ELIGIBLE names the actual submitted nationality", () => {
    const edu = buildDeclineEducation("NATIONALITY_NOT_ELIGIBLE", {
      ...baseAnswers,
      nationality: "XYZ",
    });
    expect(edu.mirror).toContain("XYZ");
  });

  it("GROUP_CASE names the actual traveller count", () => {
    const edu = buildDeclineEducation("GROUP_CASE", {
      ...baseAnswers,
      travellers: 4,
    });
    expect(edu.mirror).toContain("4");
  });
});

describe("buildDeclineEducation — never names a specific alternative visa product", () => {
  it("the alternative text never contains a visa product code (e.g. B211, E33, KITAS)", () => {
    const banned = /\bB211\b|\bE33\b|\bKITAS\b|\bC1\b|\bC7\b/i;
    for (const code of ALL_CODES) {
      const edu = buildDeclineEducation(code, baseAnswers);
      expect(edu.alternative).not.toMatch(banned);
    }
  });
});

describe("primaryDeclineCode", () => {
  it("returns the first code and null on empty", () => {
    expect(primaryDeclineCode(["GROUP_CASE", "NOT_SELF_PAY"])).toBe(
      "GROUP_CASE",
    );
    expect(primaryDeclineCode([])).toBeNull();
  });
});
