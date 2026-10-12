import { describe, expect, it } from "vitest";
import {
  GENERIC_NOTICE_CONDITION,
  NOTICE_CONDITION_COPY,
  REVIEW_REASON_COPY,
  REVIEW_REASON_ELEMENTS,
  SUPPORT_REASON_COPY,
  UNMAPPED_REASON_COPY,
  nextStepsFor,
} from "./engine-adapter";
import { buildDegradedHumanReviewOutcome } from "./outcome-fallbacks";
import type { LocalizedText } from "./outcome-view-model";

// An advisor is OFFERED, never promised. The tool cannot see whether an
// advisor will answer, what they will conclude, or when; a sentence that says
// "we confirm", "a person reviews your case" or "our team comes back to you"
// commits a person who has not been engaged. The phrase that stays true is
// "an advisor can ...".
const PROMISE: readonly RegExp[] = [
  /\bwe (confirm|check|verify|review|work out)\b/i,
  /\bour (team|advisors?) (reviews?|confirms?|tells?|comes?|verifies|checks)\b/i,
  /\bcomes? back to you\b/i,
  /\bcontinues? from here\b/i,
  /\breviews (your|it|this)\b/i,
  /\ba person reviews\b/i,
  /\b(advisor|consultant|specialist) (reviews|confirms|checks|verifies|decides|reads|continues|will)\b/i,
  /\bconfirmed by a bali zero advisor\b/i,
  /\bkami (memastikan|memeriksa|memverifikasi|mengonfirmasi|meninjau)/i,
  /\btim kami (akan|meninjau|memastikan)/i,
  /\bkonsultan (bali zero )?(akan|melanjutkan|memastikan|meninjau|memeriksa)/i,
  /\bspesialis (meninjau|membaca)/i,
  /\bdipastikan oleh konsultan\b/i,
  /\bditinjau oleh seseorang\b/i,
  /\bkasus anda ditinjau\b/i,
];

// Second Home (E33) sentences belong to the E33 lane; they carry the same
// template and are rewritten there, not here.
const E33_OWNED = /^E33/;

function offenders(rows: [string, LocalizedText][]): string[] {
  const found: string[] = [];
  for (const [where, copy] of rows) {
    for (const language of ["en", "id"] as const) {
      for (const re of PROMISE) {
        if (re.test(copy[language])) found.push(`${where}:${language} ~ ${re}`);
      }
    }
  }
  return found;
}

function table(
  name: string,
  record: Record<string, LocalizedText>,
): [string, LocalizedText][] {
  return Object.entries(record)
    .filter(([code]) => !E33_OWNED.test(code))
    .map(([code, copy]) => [`${name}.${code}`, copy]);
}

describe("the advisor is offered, never promised", () => {
  it("next steps for every state", () => {
    const rows: [string, LocalizedText][] = [];
    for (const state of [
      "SUPPORTED_CANDIDATES",
      "NEEDS_INPUT",
      "HUMAN_REVIEW_REQUIRED",
      "NO_SUPPORTED_PATH",
      "TEMPORARILY_UNAVAILABLE",
    ] as const) {
      for (const step of nextStepsFor(state)) {
        rows.push([`nextSteps.${state}.${step.id}`, step.title]);
      }
    }
    expect(offenders(rows)).toEqual([]);
  });

  it("support and review reason sentences", () => {
    expect(
      offenders([
        ...table("SUPPORT_REASON_COPY", SUPPORT_REASON_COPY),
        ...table("REVIEW_REASON_COPY", REVIEW_REASON_COPY),
        ["UNMAPPED_REASON_COPY", UNMAPPED_REASON_COPY],
      ]),
    ).toEqual([]);
  });

  it("review reason elements (rule / checked / prepare / handling)", () => {
    const rows: [string, LocalizedText][] = [];
    for (const [code, elements] of Object.entries(REVIEW_REASON_ELEMENTS)) {
      if (!elements) continue;
      for (const part of ["rule", "checked", "prepare", "handling"] as const) {
        rows.push([`REVIEW_REASON_ELEMENTS.${code}.${part}`, elements[part]]);
      }
    }
    expect(offenders(rows)).toEqual([]);
  });

  it("notice conditions, the generic notice and the degraded review reason", () => {
    const degraded = buildDegradedHumanReviewOutcome({}).reviewReasons[0];
    expect(
      offenders([
        ...table("NOTICE_CONDITION_COPY", NOTICE_CONDITION_COPY),
        ["GENERIC_NOTICE_CONDITION", GENERIC_NOTICE_CONDITION],
        ["DEGRADED_REVIEW_REASON", degraded.message],
      ]),
    ).toEqual([]);
  });

  it("the guard is guilty on the sentences it replaced", () => {
    const old: LocalizedText[] = [
      {
        en: "Send it to a Bali Zero advisor on WhatsApp: we confirm the documents, the timing and the quote.",
        id: "Kirim ke konsultan Bali Zero lewat WhatsApp: kami memastikan dokumen, jadwal, dan penawarannya.",
      },
      {
        en: "A Bali Zero consultant continues from here with an adult present.",
        id: "Konsultan Bali Zero melanjutkan dari sini.",
      },
      {
        en: "A specialist reviews this before we confirm a path, and our team comes back to you.",
        id: "Seorang spesialis meninjau hal ini, dan tim kami akan mengabari Anda.",
      },
      {
        en: "A Bali Zero advisor will review your full case by hand.",
        id: "Konsultan Bali Zero akan meninjau kasus Anda secara lengkap.",
      },
      {
        en: "The price for this path is confirmed by a Bali Zero advisor.",
        id: "Harga jalur ini dipastikan oleh konsultan Bali Zero.",
      },
    ];
    for (const copy of old) {
      expect(offenders([["old", copy]]).length).toBeGreaterThan(0);
    }
  });
});

describe("the supported next step", () => {
  it("names what an advisor can go over as an offer, in EN and ID", () => {
    const step = nextStepsFor("SUPPORTED_CANDIDATES").find(
      (item) => item.id === "send-to-advisor",
    );
    expect(step?.title.en).toMatch(/advisor can go over the documents/);
    expect(step?.title.id).toMatch(/konsultan dapat membahas dokumen/);
  });
});
