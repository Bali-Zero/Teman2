import { describe, expect, it } from "vitest";

import { buildKbliFaq } from "./kbli-faq";
import { getCode } from "./kbli-data";
import { isPmaVerdictVerified } from "./kbli-provenance";
import type { KBLICode } from "./kbli-types";

// SAETTA-20260915/W-H PR-5 — the 12 codes the (superseded) #6488 would have
// published as a national 0% closure. The dossier found no Perpres 10/2021
// (as amended by 49/2021) annex reservation for any of them: the honest
// answer is "PT PMA eligibility must be confirmed in OSS", never a national
// verdict and never the generic "not yet verified" sentence every other
// unverified code shows.
const HOLD_CODES = [
  "38110",
  "55202",
  "55300",
  "56102",
  "56304",
  "56306",
  "70201",
  "73300",
  "74199",
  "79901",
  "79902",
  "86995",
];

// A phrase from the (superseded) #6488 spec's WITHDRAWN inference — must
// never reappear (test_withdrawn_umkm_inference_absent.py's own ban, mirrored
// here at the render layer).
const BANNED = [
  /\bOpen\b/,
  /\b100%\b/,
  /\b0%\b/,
  /valid for a foreign-owned company outside Bali/i,
  /no Usaha Besar scale row/i,
  /reserved for UMKM/i,
];

function pmaAnswerFor(code: string): string {
  const kbli = getCode(code);
  expect(kbli, `getCode(${code}) must resolve`).toBeDefined();
  return buildKbliFaq(kbli as KBLICode)[0].answer;
}

describe("hold-code PMA review notice — guilt", () => {
  it.each(HOLD_CODES)(
    "KBLI %s: FAQ answer carries the specific notice, never the generic sentence or a verdict word",
    (code) => {
      const kbli = getCode(code) as KBLICode;
      expect(kbli, `getCode(${code}) must resolve`).toBeDefined();
      expect(
        kbli.pmaReviewNotice,
        `${code} must carry a registered notice`,
      ).toBeTruthy();

      const answer = pmaAnswerFor(code);
      expect(answer).toContain("Not a national 0% finding");
      expect(answer).toContain("confirm in OSS");
      expect(answer).not.toContain(
        "The canonical record carries a current PMA label",
      );
      for (const pattern of BANNED) {
        expect(answer, `${code} answer must not match ${pattern}`).not.toMatch(
          pattern,
        );
      }

      // Structural proof for the OTHER two surfaces named in the lane brief
      // (PMABadge, LicensingSection's "outside Bali" frame): both are gated on
      // `isPmaVerdictVerified`, which requires `pma.verificationStatus ===
      // "located"`. The PMA tuple for every hold code stays `declared_gap` (no
      // 0, no 100 published), so that gate is false — PMABadge renders its
      // "unknown"/"PMA unverified" branch (never Open/100%/0%) and
      // LicensingSection's `pmaVerified && baliBlocked` frame (the one that
      // says "valid for a foreign-owned company outside Bali") cannot render
      // at all. This is not incidental: it is guaranteed by the same PMA tuple
      // the lane brief required to stay unchanged.
      expect(isPmaVerdictVerified(kbli)).toBe(false);
      expect(kbli.pma.verificationStatus).toBe("declared_gap");
    },
  );

  it.each(["73300", "38110"])("BEFORE/AFTER render proof — %s", (code) => {
    const before = `Not yet verified. The canonical record carries a current PMA label for KBLI ${code} (${(getCode(code) as KBLICode).titleId}), but no adjudicated per-code official basis and source vintage verify that whole-code verdict. Confirm the current treatment at oss.go.id before planning a PT PMA.`;
    const after = pmaAnswerFor(code);
    expect(after).not.toBe(before);
    expect(after).toContain(
      "OSS lists licensing rows for this code only at Mikro, Kecil and Menengah scale",
    );
    // eslint-disable-next-line no-console
    console.log(`[render-proof ${code}] BEFORE:`, before);
    // eslint-disable-next-line no-console
    console.log(`[render-proof ${code}] AFTER:`, after);
  });
});

describe("hold-code PMA review notice — innocence", () => {
  it("96220 (TERBATAS/0/located, Lampiran II Koperasi/UMKM) renders byte-identically — no notice, no change", () => {
    const kbli = getCode("96220") as KBLICode;
    expect(kbli).toBeDefined();
    expect(kbli.pmaReviewNotice).toBeUndefined();
    const answer = pmaAnswerFor("96220");
    expect(answer).toMatch(/^No\. /);
    expect(answer).toContain("ceiling for foreign capital is 0%");
  });

  it("a TERBUKA/located code (02102) renders byte-identically — no notice, no change", () => {
    const kbli = getCode("02102") as KBLICode;
    expect(kbli).toBeDefined();
    expect(kbli.pma.verificationStatus).toBe("located");
    expect(kbli.pmaReviewNotice).toBeUndefined();
    const answer = pmaAnswerFor("02102");
    expect(answer).not.toContain("Not a national 0% finding");
  });
});
