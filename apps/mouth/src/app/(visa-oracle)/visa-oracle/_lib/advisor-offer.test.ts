import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  GENERIC_NOTICE_CONDITION,
  GENERIC_REVIEW_REASON,
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
  // An obligation laid on the advisor is no more an offer than a promise is:
  // "an advisor needs to confirm it" commits a person who has not been engaged.
  /\b(advisor|consultant|specialist) needs? to\b/i,
  /\bneeds? to be (confirmed|reviewed|checked|verified) by (a |an )?(bali zero )?(advisor|consultant)/i,
  /\bneeds? a (fresh )?(check|review) by (a |an )?(bali zero )?(advisor|consultant)/i,
  /\bkonsultan (bali zero )?perlu\b/i,
  /\bperlu (diperiksa ulang|dikonfirmasi|ditinjau|diverifikasi) oleh konsultan/i,
  /\b(memerlukan|diperlukan) (peninjauan|konfirmasi|pemeriksaan)[^.]{0,80}oleh konsultan/i,
  // "needs a Bali Zero advisor's judgment" makes the advisor's judgment a
  // precondition, the same obligation in a possessive.
  /\bneeds? an? (bali zero )?(advisor|consultant)'s\b/i,
  /\bmemerlukan (penilaian|pertimbangan|keputusan) (dari )?konsultan/i,
];

// EXEMPTION, stated openly: Second Home (E33*) keys are skipped by name. Their
// sentences belong to Track C (the E33 lane) and still carry the old promise
// template ("We confirm", "We review", "We work out", "We check"); they are
// rewritten there, not in this PR. Every claim below is therefore "every
// non-E33 code", never "every visa code".
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

describe("the advisor is offered, never promised (every non-E33 code; E33 is Track C)", () => {
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
    for (const codes of [["A1"], ["BRIDGING"], ["BRIDGING", "B1"]]) {
      for (const step of nextStepsFor("SUPPORTED_CANDIDATES", {
        productCodes: codes,
      })) {
        rows.push([`nextSteps.${codes.join("+")}.${step.id}`, step.title]);
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
        ["GENERIC_REVIEW_REASON", GENERIC_REVIEW_REASON],
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

  it("the guard is guilty on an advisor made an obligation, not an offer", () => {
    const obligations: LocalizedText[] = [
      {
        en: "so a Bali Zero advisor needs to confirm it before a path can be confirmed.",
        id: "sehingga konsultan Bali Zero perlu memastikannya sebelum jalur dapat dikonfirmasi.",
      },
      {
        en: "One of the official sources behind this result needs a fresh check by a Bali Zero advisor before the result can stand.",
        id: "Salah satu sumber resmi di balik hasil ini perlu diperiksa ulang oleh konsultan Bali Zero sebelum hasilnya dapat dipakai.",
      },
      {
        en: "a Bali Zero advisor needs to review the details before any path can be confirmed.",
        id: "dan memerlukan peninjauan detail oleh konsultan Bali Zero sebelum jalur apa pun dapat dikonfirmasi.",
      },
      {
        en: "x",
        id: "diperlukan konfirmasi oleh konsultan Bali Zero mengenai status mana yang benar.",
      },
      {
        en: "Some of your answers need a Bali Zero advisor's judgment before we can confirm a path.",
        id: "Beberapa jawaban Anda memerlukan penilaian dari konsultan Bali Zero sebelum kami dapat mengonfirmasi jalur.",
      },
    ];
    for (const copy of obligations) {
      expect(offenders([["obligation", copy]]).length).toBeGreaterThan(0);
    }
  });
});

// The Playwright specs pin copy word for word, and nothing in the unit suite
// ran them: two of them still expected the old promises after the adapter
// moved on. A spec that pins a promise sentence is a spec that fails the day
// the sentence is cured, so the specs are scanned like any other copy table.
// The one allow-listed literal is the disclaimer paragraph that lives in
// i18n.ts (tree lane, named in the PR body as a follow-up).
describe("the Playwright specs pin no promise sentence", () => {
  const e2eDir = path.resolve(__dirname, "../../../../../e2e");
  const TREE_LANE_DISCLAIMER =
    "a Bali Zero advisor reviews your case before any path is confirmed";

  function literals(source: string): string[] {
    return source.match(/"(?:[^"\\\n]|\\.)*"|`(?:[^`\\]|\\.)*`/g) ?? [];
  }

  it("no visa-oracle e2e string literal carries a promise or an obligation", () => {
    const files = readdirSync(e2eDir).filter((name) =>
      /^visa-.*\.spec\.ts$/.test(name),
    );
    expect(files.length).toBeGreaterThan(0);
    const found: string[] = [];
    for (const name of files) {
      const source = readFileSync(path.join(e2eDir, name), "utf8");
      for (const literal of literals(source)) {
        if (literal.includes(TREE_LANE_DISCLAIMER)) continue;
        for (const re of PROMISE) {
          if (re.test(literal))
            found.push(`${name} ~ ${re}: ${literal.slice(0, 60)}`);
        }
      }
    }
    expect(found).toEqual([]);
  });
});

describe("the advisor is offered no more than the rules and Imigrasi support", () => {
  const blacklist = NOTICE_CONDITION_COPY.DISCLOSED_BLACKLIST_ENTRY_CONDITION;

  it("the blacklist notice names the disclosure without stating a legal effect or an advisor lookup the rule pack does not hold", () => {
    // UU 6/2011 Pasal 42 says the visa application is REJECTED for someone on
    // the penangkalan list, and immigration officers keep that list. Neither
    // the rule pack nor imigrasi.go.id says an applicant is barred from
    // SUBMITTING, nor that an advisor can look the entry up with Ditjen
    // Imigrasi. The notice may say what the person flagged and offer to go
    // over it, and nothing about the ban's effect or the advisor's reach.
    expect(blacklist.en).not.toMatch(
      /stops any application|filed|lifted|verify your status|Ditjen/i,
    );
    expect(blacklist.id).not.toMatch(
      /tidak dapat diproses|dicabut|memverifikasi status|Ditjen/i,
    );
    expect(blacklist.en).toMatch(/advisor can go over/i);
    expect(blacklist.id).toMatch(/konsultan Bali Zero dapat membahas/i);
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
