import { describe, expect, it } from "vitest";
import { mapOracleFactsToApplicantFacts } from "./fact-mapper";
import { getCategoryQuestionIds } from "./flow";
import { translate } from "./i18n";
import { QUESTIONS } from "./tree";

// Bites observer target (scripts/ci/observe_visa_oracle_own_shareholding_question.py):
// the E28A own-shareholding step B interview question.

// Any spelling of the IDR 10 billion threshold: 10,000,000,000 with any
// separator, "10 billion", "10 miliar", "10 M", "Rp 10 miliar". Copy must
// never anchor.
const NAMES_THE_THRESHOLD =
  /(?<!\d)10[\s  ,.]?000[\s  ,.]?000[\s  ,.]?000(?!\d)|(?<!\d)10[\s  ]?(?:billion|miliar|milyar|bn)\b|\bten billion\b|sepuluh miliar/i;

const FACTS_CONTEXT = {
  assessmentId: "00000000-0000-4000-8000-000000000001",
  collectedAt: new Date("2026-10-17T00:00:00.000Z"),
};

describe("E28A step B - the PT PMA investor interview asks the own shareholding", () => {
  it("asks it right after the paid-up capital question, on the pt_pma branch", () => {
    const ids = getCategoryQuestionIds({
      category: "invest",
      investment_vehicle: "pt_pma",
      investment_pt_pma: "yes",
    });
    expect(ids[ids.indexOf("investment_paid_up_capital_idr") + 1]).toBe(
      "investment_own_shareholding_idr",
    );
  });

  it("is a rupiah number with no not-sure option", () => {
    const question = QUESTIONS.investment_own_shareholding_idr;
    expect(question.kind).toBe("number");
    expect(question.notSure).toBeUndefined();
    expect(question.numberInput?.unitI18nKey).toBe("q.unit.idr");
  });

  it("is asked only on the PT PMA investor path", () => {
    const categories = (QUESTIONS.category.options ?? []).map((o) => o.key);
    for (const key of ["invest", "remote", "tourism", "retirement", "study"]) {
      expect(categories, key).toContain(key);
    }
    // `business` reuses the PT PMA commitment questions for an applicant who
    // converts onshore into an investor stay (see the explorer sequence in
    // flow.ts); only after a "yes" on the commitment, never by default.
    expect(getCategoryQuestionIds({ category: "business" })).not.toContain(
      "investment_own_shareholding_idr",
    );
    for (const category of categories.filter(
      (key) => key !== "invest" && key !== "business",
    )) {
      const ids = getCategoryQuestionIds({ category });
      expect(ids, category).not.toEqual(["stay_days"]);
      expect(ids, category).not.toContain("investment_own_shareholding_idr");
    }
    for (const vehicle of [
      "property",
      "bank_deposit",
      "merit",
      "family",
      "undecided",
    ]) {
      const ids = getCategoryQuestionIds({
        category: "invest",
        investment_vehicle: vehicle,
        investment_pt_pma: "yes",
        investment_currency: "idr",
      });
      expect(ids, vehicle).not.toContain("investment_own_shareholding_idr");
    }
    // `capital_market` shares the PT PMA commitment questions (W-VO-Q): the
    // E28A capital figures are asked there too, so the own shareholding is too.
    expect(
      getCategoryQuestionIds({
        category: "invest",
        investment_vehicle: "capital_market",
        investment_pt_pma: "yes",
      }),
    ).toContain("investment_own_shareholding_idr");
    // Innocence: the `pt_pma` vehicle asks its capital questions regardless,
    // but a "no" (or no answer yet) on the commitment never asks the own
    // shareholding; only a "yes" does.
    for (const answered of [{ investment_pt_pma: "no" }, {}] as Record<
      string,
      string
    >[]) {
      expect(
        getCategoryQuestionIds({
          category: "invest",
          investment_vehicle: "pt_pma",
          ...answered,
        }),
      ).not.toContain("investment_own_shareholding_idr");
    }
    // On `capital_market` a "no" on the PT PMA commitment asks for no figure
    // at all (the `pt_pma` vehicle asks its capital questions unconditionally).
    expect(
      getCategoryQuestionIds({
        category: "invest",
        investment_vehicle: "capital_market",
        investment_pt_pma: "no",
      }),
    ).not.toContain("investment_own_shareholding_idr");
  });

  it("maps the answer to the engine fact as a whole-rupiah KNOWN value", () => {
    const wire = mapOracleFactsToApplicantFacts(
      {
        category: "invest",
        investment_own_shareholding_idr: "9999999999",
      },
      FACTS_CONTEXT,
    );
    expect(wire.facts["investment.own_shareholding_idr"]).toEqual({
      status: "KNOWN",
      value: 9_999_999_999,
    });
  });

  it("the neutrality guard catches every spelling of the threshold", () => {
    for (const leak of [
      "10000000000",
      "10,000,000,000",
      "10.000.000.000",
      "10 000 000 000",
      "10 billion",
      "10 miliar",
      "Rp 10 miliar",
      "ten billion",
      "sepuluh miliar",
    ]) {
      expect(leak, leak).toMatch(NAMES_THE_THRESHOLD);
    }
    for (const figure of [
      "2,500,000,000",
      "2,5 miliar",
      "100 billion",
      "1,000,000,000",
    ]) {
      expect(figure, figure).not.toMatch(NAMES_THE_THRESHOLD);
    }
    for (const lang of ["en", "id"] as const) {
      for (const key of [
        "q.investment_own_shareholding_idr",
        "q.investment_own_shareholding_idr.hint",
        "why.investment_own_shareholding_idr",
      ] as const) {
        expect(translate(lang, key), `${lang} ${key}`).not.toMatch(
          NAMES_THE_THRESHOLD,
        );
      }
    }
  });

  it("pins the question and why copy exactly (true before and after the pack reads the figure)", () => {
    expect(translate("en", "q.investment_own_shareholding_idr")).toBe(
      "What is the value of the shares you personally hold in the Indonesian company that will sponsor you, in rupiah?",
    );
    expect(translate("id", "q.investment_own_shareholding_idr")).toBe(
      "Berapa nilai saham yang Anda miliki secara pribadi di perusahaan Indonesia yang akan menjadi penjamin Anda, dalam rupiah?",
    );
    expect(translate("en", "why.investment_own_shareholding_idr")).toBe(
      "The Investor visa looks at the shares you hold yourself in the sponsoring company, not only at the company's capital.",
    );
    expect(translate("id", "why.investment_own_shareholding_idr")).toBe(
      "Visa Investor melihat saham yang Anda miliki sendiri di perusahaan penjamin, tidak hanya modal perusahaan.",
    );
  });
});
