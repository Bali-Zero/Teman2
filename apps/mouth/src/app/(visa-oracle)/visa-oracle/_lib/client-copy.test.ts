import { describe, expect, it } from "vitest";
import {
  GENERIC_NOTICE_CONDITION,
  NOTICE_CONDITION_COPY,
  REVIEW_REASON_COPY,
  SUPPORT_REASON_COPY,
  UNMAPPED_REASON_COPY,
  nextStepsFor,
} from "./engine-adapter";
import { dict } from "./i18n";
import {
  buildClientGuardOutcome,
  buildDegradedHumanReviewOutcome,
  buildNetworkFailureOutcome,
  buildShadowOutcome,
} from "./outcome-fallbacks";
import { buildPreviewOutcome } from "./preview-adapter";
import type { OutcomeState } from "./outcome-view-model";

const STATES: readonly OutcomeState[] = [
  "SUPPORTED_CANDIDATES",
  "NEEDS_INPUT",
  "HUMAN_REVIEW_REQUIRED",
  "NO_SUPPORTED_PATH",
  "TEMPORARILY_UNAVAILABLE",
];

// Words that belong to the engine, not to a client. Indonesian equivalents
// are listed beside their English twin.
const BANNED: readonly RegExp[] = [
  /\bengine\b/i,
  /\bmesin\b/i,
  /\bdisahkan\b/i,
  /fabricat/i,
  /dibuat-buat/i,
  /\bshadow\b/i,
  /\bcandidates?\b/i,
  /\bkandidat\b/i,
  /\bPNBP\b/,
  /verified (decision )?rules/i,
  /decision rules/i,
  /aturan (keputusan )?terverifikasi/i,
  /aturan keputusan/i,
  /\bprovenance\b/i,
  /\b(?:a|the|this|that|safety|client) hold\b/i,
  /\bpenahanan\b/i,
];

// "signed" and "operational" are engine jargon as UI labels but ordinary words
// inside a reason sentence ("a signed Pernyataan Integrasi", "operational
// work"), so they are only banned in the outcome/verdict dictionary entries.
const BANNED_IN_DICT: readonly RegExp[] = [
  /\bsigned\b/i,
  /\boperational\b/i,
  /\boperasional\b/i,
];

function clientStrings(): { where: string; value: string; strict?: boolean }[] {
  const rows: { where: string; value: string; strict?: boolean }[] = [];
  for (const language of ["en", "id"] as const) {
    for (const [key, value] of Object.entries(dict[language])) {
      if (key.startsWith("outcome.") || key.startsWith("verdict.")) {
        rows.push({ where: `${language}:${key}`, value, strict: true });
      }
    }
    for (const state of STATES) {
      for (const step of nextStepsFor(state)) {
        rows.push({
          where: `${language}:nextSteps.${state}.${step.id}`,
          value: `${step.title[language]} ${step.body?.[language] ?? ""}`,
        });
      }
    }
    for (const [name, copy] of Object.entries({
      ...SUPPORT_REASON_COPY,
      ...REVIEW_REASON_COPY,
      ...NOTICE_CONDITION_COPY,
    })) {
      rows.push({ where: `${language}:reason.${name}`, value: copy[language] });
    }
    rows.push(
      { where: `${language}:unmapped`, value: UNMAPPED_REASON_COPY[language] },
      {
        where: `${language}:generic-notice`,
        value: GENERIC_NOTICE_CONDITION[language],
      },
    );
    for (const outcome of [
      buildClientGuardOutcome({ code: "X" }),
      buildNetworkFailureOutcome({ code: "X" }),
      buildShadowOutcome({ code: "X" }),
    ]) {
      rows.push({
        where: `${language}:fallback.${outcome.provenance}`,
        value: outcome.outage.message[language],
      });
    }
  }
  return rows;
}

describe("client-visible copy", () => {
  it("never carries engine jargon in outcome/verdict copy, next steps, reasons or fallbacks", () => {
    const offenders = clientStrings().flatMap(({ where, value, strict }) =>
      [...BANNED, ...(strict ? BANNED_IN_DICT : [])]
        .filter((re) => re.test(value))
        .map((re) => `${where} ~ ${re} :: ${value.slice(0, 80)}`),
    );
    expect(offenders).toEqual([]);
  });

  it("never leaks an internal note into the price or timeline copy", () => {
    for (const language of ["en", "id"] as const) {
      const table = dict[language];
      expect(table["outcome.price_all_inclusive"]).not.toMatch(/split|ever/i);
      expect(table["outcome.price_all_inclusive"]).not.toMatch(/pemisahan/i);
      expect(table["outcome.timeline_pending"]).not.toMatch(
        /unavailable|tidak tersedia|verified|terverifikasi/i,
      );
    }
  });
});

describe("nextStepsFor — one list per outcome state", () => {
  it.each(STATES)(
    "%s carries exactly three distinct, stable-id steps",
    (state) => {
      const steps = nextStepsFor(state);
      expect(steps).toHaveLength(3);
      expect(new Set(steps.map((step) => step.id)).size).toBe(3);
      for (const step of steps) {
        expect(step.id).toMatch(/^[a-z]+(-[a-z]+)*$/);
        expect(step.title.en.length).toBeGreaterThan(0);
        expect(step.title.id.length).toBeGreaterThan(0);
      }
    },
  );

  it("gives every state a different list", () => {
    const lists = new Set(
      STATES.map((state) =>
        nextStepsFor(state)
          .map((step) => step.id)
          .join("|"),
      ),
    );
    expect(lists.size).toBe(STATES.length);
  });

  it("is the single source for the fallbacks and the gold preview baseline", () => {
    expect(buildClientGuardOutcome({ code: "X" }).nextSteps).toBe(
      nextStepsFor("TEMPORARILY_UNAVAILABLE"),
    );
    expect(buildNetworkFailureOutcome({ code: "X" }).nextSteps).toBe(
      nextStepsFor("TEMPORARILY_UNAVAILABLE"),
    );
    expect(buildDegradedHumanReviewOutcome({}).nextSteps).toBe(
      nextStepsFor("HUMAN_REVIEW_REQUIRED"),
    );
    expect(buildPreviewOutcome({}, new Date()).state).toBe(
      "TEMPORARILY_UNAVAILABLE",
    );
  });
});
