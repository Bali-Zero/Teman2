import { describe, expect, it } from "vitest";
import { mapOracleFactsToApplicantFacts } from "./fact-mapper";
import { getCategoryQuestionIds } from "./flow";
import { translate } from "./i18n";
import { QUESTIONS } from "./tree";

// Bites observer target (scripts/ci/observe_visa_oracle_remote_income_question.py):
// the seq-28 step B interview question for the E33G yearly income.

describe("seq-28 step B - the remote interview asks the yearly income", () => {
  it("asks it right after the employer country and before the PT PMA question", () => {
    const ids = getCategoryQuestionIds({ category: "remote" });
    expect(ids[ids.indexOf("remote_employer_country") + 1]).toBe(
      "remote_annual_income_usd",
    );
    expect(ids[ids.indexOf("remote_annual_income_usd") + 1]).toBe(
      "remote_pt_pma",
    );
  });

  it("is a USD-per-year number with no not-sure option", () => {
    const question = QUESTIONS.remote_annual_income_usd;
    expect(question.kind).toBe("number");
    expect(question.notSure).toBeUndefined();
    expect(question.numberInput?.unitI18nKey).toBe("q.unit.usd_year");
  });

  it("is asked on no other category", () => {
    for (const category of ["work", "family", "investment", "study"] as const) {
      expect(getCategoryQuestionIds({ category })).not.toContain(
        "remote_annual_income_usd",
      );
    }
  });

  it("maps the answer to the engine fact and keeps 59999 a known value", () => {
    const wire = mapOracleFactsToApplicantFacts(
      { category: "remote", remote_annual_income_usd: "59999" },
      {
        assessmentId: "00000000-0000-4000-8000-000000000001",
        collectedAt: new Date("2026-10-11T00:00:00.000Z"),
      },
    );
    expect(wire.facts["work.annual_foreign_income_usd"]).toEqual({
      status: "KNOWN",
      value: 59_999,
    });
  });

  it("states the question neutrally in English, without naming a threshold or a source", () => {
    const q = translate("en", "q.remote_annual_income_usd");
    expect(q).toBe("What is your yearly salary or income, in US dollars?");
    expect(translate("en", "q.remote_annual_income_usd.hint")).toContain(
      "US-dollar equivalent",
    );
    for (const key of [
      "q.remote_annual_income_usd",
      "q.remote_annual_income_usd.hint",
      "why.remote_annual_income_usd",
    ] as const) {
      expect(translate("en", key)).not.toMatch(/60[,.]?000/);
      expect(translate("id", key)).not.toMatch(/60[,.]?000/);
    }
    expect(q).not.toMatch(/outside Indonesia/i);
  });

  it("states the question neutrally in Indonesian, with the currency conversion hint", () => {
    expect(translate("id", "q.remote_annual_income_usd")).toBe(
      "Berapa gaji atau penghasilan tahunan Anda, dalam dolar AS?",
    );
    expect(translate("id", "q.remote_annual_income_usd.hint")).toContain(
      "setaranya dalam dolar AS",
    );
  });
});
