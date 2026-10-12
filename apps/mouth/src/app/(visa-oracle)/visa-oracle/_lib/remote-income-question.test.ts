import { describe, expect, it } from "vitest";
import { mapOracleFactsToApplicantFacts } from "./fact-mapper";
import { getCategoryQuestionIds } from "./flow";
import { translate } from "./i18n";
import { QUESTIONS } from "./tree";

// Bites observer target (scripts/ci/observe_visa_oracle_remote_income_question.py):
// the seq-28 step B interview question for the E33G yearly income.

// Any spelling of the 60,000 USD threshold: digits with a separator or a thin/
// no-break space, 60k, 60 thousand, 60 ribu, or the number in words (EN/ID).
// Copy must never anchor.
const NAMES_THE_THRESHOLD =
  /60[\s\u00a0\u202f,.]?000|60[\s\u00a0\u202f]?k\b|(?<!\d)60[\s\u00a0\u202f]?(?:thousand|ribu)|sixty|enam puluh/i;

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
    const categories = (QUESTIONS.category.options ?? []).map((o) => o.key);
    // A silently shrunk list must fail: every category the gate named is here.
    for (const key of [
      "remote",
      "tourism",
      "business",
      "retirement",
      "second_home",
      "diaspora",
      "other",
      "work",
      "family",
      "invest",
      "study",
    ]) {
      expect(categories, key).toContain(key);
    }
    for (const category of categories.filter((key) => key !== "remote")) {
      const ids = getCategoryQuestionIds({ category });
      // An unknown key falls back to ["stay_days"]: a misspelt key must not pass.
      expect(ids, category).not.toEqual(["stay_days"]);
      expect(ids.length, category).toBeGreaterThan(0);
      expect(ids, category).not.toContain("remote_annual_income_usd");
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

  it("the neutrality guard catches every spelling of the threshold, and passes the real copy", () => {
    for (const leak of [
      "at least 60000",
      "60,000",
      "60.000",
      "60 000",
      "60k",
      "sixty thousand",
      "enam puluh ribu",
    ]) {
      expect(leak, leak).toMatch(NAMES_THE_THRESHOLD);
    }
    for (const lang of ["en", "id"] as const) {
      for (const key of [
        "q.remote_annual_income_usd",
        "q.remote_annual_income_usd.hint",
        "why.remote_annual_income_usd",
      ] as const) {
        expect(translate(lang, key), `${lang} ${key}`).not.toMatch(
          NAMES_THE_THRESHOLD,
        );
      }
    }
  });

  it("the threshold regex matches every spelling and no unrelated figure", () => {
    for (const spelling of [
      "60,000",
      "60.000",
      "60 000",
      "60\u00a0000",
      "60\u202f000",
      "60000",
      "60k",
      "sixty",
      "enam puluh",
      "60 thousand",
      "60 ribu",
      "60ribu",
      "60 Thousand",
      "60 RIBU",
    ]) {
      expect(spelling, spelling).toMatch(NAMES_THE_THRESHOLD);
    }
    for (const figure of [
      "6,000",
      "600",
      "160 days",
      "160 ribu",
      "16 thousand",
    ]) {
      expect(figure, figure).not.toMatch(NAMES_THE_THRESHOLD);
    }
  });

  it("pins the why-copy exactly, true before and after seq-28, with no figure", () => {
    expect(translate("en", "why.remote_annual_income_usd")).toBe(
      "The remote-worker visa (E33G) has a yearly income requirement. The amount is used exactly as you enter it.",
    );
    expect(translate("id", "why.remote_annual_income_usd")).toBe(
      "Visa pekerja jarak jauh (E33G) memiliki persyaratan penghasilan tahunan. Jumlah ini digunakan persis seperti yang Anda masukkan.",
    );
  });

  it("states the question neutrally in English, without naming a threshold or a source", () => {
    const q = translate("en", "q.remote_annual_income_usd");
    expect(q).toBe("What is your yearly salary or income, in US dollars?");
    expect(translate("en", "q.remote_annual_income_usd.hint")).toBe(
      "Enter the yearly amount in whole US dollars. If you are paid in another currency, enter its US-dollar equivalent.",
    );
    expect(q).not.toMatch(/outside Indonesia/i);
  });

  it("states the question neutrally in Indonesian, with the currency conversion hint", () => {
    expect(translate("id", "q.remote_annual_income_usd")).toBe(
      "Berapa gaji atau penghasilan tahunan Anda, dalam dolar AS?",
    );
    expect(translate("id", "q.remote_annual_income_usd.hint")).toBe(
      "Masukkan jumlah tahunan dalam dolar AS (angka bulat). Jika Anda dibayar dalam mata uang lain, masukkan nilai setaranya dalam dolar AS.",
    );
  });
});
