import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * GARUDA VOA — copy guard over the six purchase screens (DELIBERA fase 2 §(d),
 * lane S5). This scans SOURCE, not rendered output — same convention as
 * `voa-r19.contract.test.ts` and `(workspace)/__tests__/desk-no-red.guard.test.ts`
 * — because the closed banned-claims list and the Safe Clock rule bind every
 * string a customer could read, whichever branch renders it, and a source
 * scan catches a literal the day it is typed rather than the day a specific
 * component happens to mount it.
 *
 * Six screens, by file (DELIBERA (d)): wizard, verdict-ACCEPT/DECLINE, upload,
 * checkout, tracker, magic-link. `declineEducation.ts` is included because it
 * is the DECLINE screen's own copy table (`buildDeclineEducation`), not a
 * separate surface — the mirror/forbids/alternative strings it returns are
 * exactly what the DECLINE screen renders.
 *
 * WHAT THIS GUARD DOES NOT SEE, stated so its green is never read as more
 * than it measures (cicatrix family #3 discipline): it does not evaluate
 * "fast" used without a qualifier, or "the government requires..." followed
 * by an internal precaution — both phrasing traps in the skill's closed list
 * that depend on surrounding sentence context a regex cannot judge without
 * convicting legitimate prose (this file's own `sourcesOf`-style corpus
 * already uses "fast-track" and "fast-lane" as internal/service nouns, never
 * as an unqualified client promise). Those two traps stay a human review
 * item; the skill (`garuda-voa/SKILL.md` step 4) is the enforcement path
 * for them.
 */

const VOA_DIR = join(__dirname); // apps/mouth/src/app/visa/voa

/** The six purchase screens plus their copy tables, per DELIBERA (d). */
const SCREEN_FILES = [
  "page.tsx", // wizard
  // The wizard's copy MOVED here (EN/ID dictionary, 2026-09-20). Scanning
  // the screen alone would now measure an empty room: a banned claim typed
  // into either language column reaches the customer through `page.tsx`
  // exactly as a literal used to. A guard that changes what it reads and
  // does not follow the thing it guards is cicatrix family #3 — the
  // assertion survives in name while its subject has left.
  "voa-copy.ts",
  "SafeClock.tsx", // the published-deadline hero the verdict screen renders
  "NextSteps.tsx", // "what happens next" / "what we cannot promise"
  "[hash]/page.tsx", // verdict ACCEPT/DECLINE
  "upload/[resultId]/page.tsx",
  "upload/UploadFlow.tsx",
  "upload/messages.ts",
  "checkout/[resultId]/page.tsx",
  "checkout/[resultId]/CheckoutFlow.tsx",
  "orders/[orderId]/page.tsx",
  "orders/[orderId]/return/page.tsx",
  "orders/OrderTracker.tsx",
  "orders/messages.ts",
  "auth/continue/page.tsx", // magic link consumed/expired
].map((rel) => join(VOA_DIR, rel));

/** The DECLINE screen's copy table lives one directory tree over. */
const DECLINE_EDUCATION_FILE = join(
  VOA_DIR,
  "..",
  "..",
  "..",
  "components",
  "garuda",
  "declineEducation.ts",
);

const ALL_FILES = [...SCREEN_FILES, DECLINE_EDUCATION_FILE];

/**
 * Code lines only, comments stripped — a docstring naming "GARUDA VOA" in a
 * file header, or explaining why a rule exists, is PROSE for maintainers, not
 * copy a customer reads. Same block-comment state machine as
 * `desk-no-red.guard.test.ts::codeLines`, reused here rather than
 * reimplemented differently, because a second, slightly different comment
 * stripper is exactly the kind of drift that convicts innocent prose one file
 * and misses guilty paint in another.
 */
function codeLines(file: string): Array<{ n: number; text: string }> {
  const out: Array<{ n: number; text: string }> = [];
  let inBlock = false;
  readFileSync(file, "utf8")
    .split("\n")
    .forEach((text, i) => {
      const t = text.trimStart();
      const opensBlock = /\/\*/.test(text);
      const closesBlock = /\*\//.test(text);
      if (inBlock) {
        if (closesBlock) inBlock = false;
        return;
      }
      if (opensBlock && !closesBlock) {
        inBlock = true;
        return;
      }
      if (
        t.startsWith("//") ||
        t.startsWith("*") ||
        t.startsWith("/*") ||
        t.startsWith("{/*")
      ) {
        return;
      }
      out.push({ n: i + 1, text });
    });
  return out;
}

function bodyOf(file: string): Array<{ n: number; text: string }> {
  return codeLines(file);
}

// ---------------------------------------------------------------------------
// 1. The closed banned-claims list (garuda-voa/reference/banned-claims.md) —
//    8 rows, Bahasa and English forms, plus the two phrasing traps that are
//    mechanically checkable ("usually approved"-style, "nothing to worry"-
//    style). No fourth outcome, no rewording that rescues a hit.
// ---------------------------------------------------------------------------
const BANNED_CLAIMS: Array<{
  label: string;
  re: RegExp;
  /** A preceding negator acquits — see `convicts` below for why, and why only here. */
  negationFlips?: boolean;
}> = [
  {
    label: "official partner / mitra resmi",
    re: /mitra resmi|reseller pertama|official (?:immigration |imigrasi )?partner/i,
  },
  {
    label: "guaranteed in 24 hours",
    re: /dijamin 24 jam|guaranteed (?:in |within )?24[- ]hours?/i,
  },
  {
    label: "approval guaranteed",
    re: /persetujuan dijamin|(?:approval|approved) guaranteed|guaranteed approval/i,
  },
  {
    label: "fully online extension",
    re: /perpanjangan sepenuhnya online|(?:fully|entirely|completely) online extension/i,
  },
  {
    label: "without biometrics",
    re: /tanpa biometrik|without biometrics?|no biometrics? (?:required|needed)/i,
  },
  {
    label: "zero overstay risk",
    re: /risiko overstay nol|zero overstay risk|no overstay risk/i,
  },
  {
    label: "remote work on a B1",
    re: /kerja jarak jauh dengan b1|(?:remote work|work remotely) on (?:a |the )?b1/i,
  },
  {
    label: "second/automatic extension",
    re: /automatic extension|second extension|extends? (?:again|a second time|twice)|perpanjangan (?:otomatis|kedua)|diperpanjang (?:otomatis|dua kali|lagi|untuk kedua kali(?:nya)?)|memperpanjang (?:lagi|dua kali|untuk kedua kali(?:nya)?)/i,
    negationFlips: true,
  },
  {
    label: "trap: approval-guarantee-as-statistic",
    re: /usually approved|practically always(?: approved)?|never had a rejection|never been rejected|biasanya disetujui|hampir selalu disetujui|(?:tidak|belum) pernah ditolak/i,
  },
  {
    label: "trap: false all-handled promise",
    re: /nothing to worry about|we handle everything|zero stress|semua(?:nya)? kami urus|kami urus semua(?:nya)?|tidak perlu khawatir|bebas repot|tanpa stres/i,
  },
];

/**
 * A negator BEFORE the hit turns ONE of these rules into the truth this funnel
 * has to be able to tell. The Visa on Arrival may be extended once, so
 * "tidak dapat diperpanjang untuk kedua kali" is the honest sentence and
 * convicting it would forbid the rule the screen exists to explain — the
 * over-match half of cicatrix family #3, introduced by the very fix that
 * closes the under-match half.
 *
 * Only `negationFlips` rows get this reading. In the other two the negation IS
 * the claim ("belum pernah ditolak", "tidak perlu khawatir"), and treating a
 * negator as innocence would gut the rule instead of scoping it.
 */
const NEGATOR_RE = /\b(?:tidak|tak|bukan|belum|cannot|never)\b/i;

function convicts(rule: (typeof BANNED_CLAIMS)[number], text: string): boolean {
  const hit = rule.re.exec(text);
  if (!hit) return false;
  if (!rule.negationFlips) return true;
  return !NEGATOR_RE.test(text.slice(0, hit.index));
}

// ---------------------------------------------------------------------------
// 2. Safe Clock — only D-7 (published_filing_deadline) may reach a client.
//    D-14/D-10/D-3/D-1 and the internal name "Safe Clock" itself never do.
// ---------------------------------------------------------------------------
const SAFE_CLOCK_LEAK_RE = /D-14|D-10|D-3\b|D-1\b|Safe Clock/i;

// ---------------------------------------------------------------------------
// 3. Bahasa term set — VOA, eVOA, KITAS, PT PMA stay verbatim (correct case)
//    wherever they appear in PROSE; never a lowercase paraphrase of the same
//    term. None of these terms is required to appear (this funnel spells out
//    "Visa on Arrival" in full and never uses the bare acronym in copy today
//    — verified against the current corpus below) — the guard only binds
//    the term the day someone types it, so it does not convict a screen for
//    a term it doesn't use.
//
//    Excluded by construction, not by accident: a route path segment
//    (`/visa/voa/...`, always preceded by `/`) and a kebab-case DOM id/
//    htmlFor (`voa-email`, `voa-checkout-full-name`, always followed by `-`)
//    are not prose a customer reads — they are code, and this corpus is full
//    of both legitimately. Convicting them would be guard-over-match
//    (cicatrix family #3); the lookbehind/lookahead below excludes exactly
//    those two shapes and no other.
// ---------------------------------------------------------------------------
const BAHASA_TERMS = ["VOA", "eVOA", "KITAS", "PT PMA"] as const;
const LOWERCASE_PARAPHRASE_RE: Record<(typeof BAHASA_TERMS)[number], RegExp> = {
  VOA: /(?<!\/)\bvoa\b(?!-)/,
  eVOA: /(?<!\/)\bevoa\b(?!-)/,
  KITAS: /(?<!\/)\bkitas\b(?!-)/,
  "PT PMA": /\bpt pma\b/,
};

// ---------------------------------------------------------------------------
// 4. No emoji. Scoped to the astral emoji blocks (U+1F000-U+1FFFF) only —
//    NOT the BMP arrow/dingbat/geometric ranges, because this corpus already
//    and legitimately uses "→" (CTA arrows) and "✓ ● ○" (OrderTracker's
//    parcel-tracker rail, named explicitly in design-A-claude.md §1) — those
//    are typographic glyphs, not emoji, and convicting them would be
//    guard-over-match (cicatrix family #3).
// ---------------------------------------------------------------------------
const EMOJI_RE = /[\u{1F000}-\u{1FFFF}]/u;

// ---------------------------------------------------------------------------
// 5. No price literal. Prices come only from `price_idr` via PricingTool —
//    never a hardcoded amount. Requires a currency marker directly followed
//    by digits, so it does not convict the `formatIDR`/`price_idr`
//    identifiers (no digit follows "IDR" in either spelling).
// ---------------------------------------------------------------------------
const PRICE_LITERAL_RE = /\b(Rp|IDR)[ \t]?[0-9][0-9.,]*/;

describe("voa-copy.guard — the six purchase screens carry no banned claim", () => {
  it("has screens to scan", () => {
    expect(ALL_FILES.length).toBeGreaterThan(0);
    for (const f of ALL_FILES) {
      expect(() => readFileSync(f, "utf8"), f).not.toThrow();
    }
  });

  it("is GUILTY when a banned claim is inserted (guilt control)", () => {
    const injected = 'const x = "we are the official partner for Imigrasi";';
    const hit = BANNED_CLAIMS.find((rule) => convicts(rule, injected));
    expect(hit?.label).toBe("official partner / mitra resmi");
  });

  it("is INNOCENT on ordinary consultant/process prose (innocence control)", () => {
    const clean =
      "A consultant can fast-track the same case by hand, on WhatsApp.";
    for (const rule of BANNED_CLAIMS) {
      expect(convicts(rule, clean)).toBe(false);
    }
  });

  for (const file of ALL_FILES) {
    const rel = file.includes("declineEducation")
      ? "components/garuda/declineEducation.ts"
      : file.slice(VOA_DIR.length + 1);

    it(`${rel} — zero banned claims`, () => {
      const offences: string[] = [];
      for (const { n, text } of bodyOf(file)) {
        for (const rule of BANNED_CLAIMS) {
          if (convicts(rule, text))
            offences.push(`${n}: ${rule.label} — ${text.trim()}`);
        }
      }
      expect(offences).toEqual([]);
    });

    it(`${rel} — never D-14/D-10/D-3/D-1, never "Safe Clock"`, () => {
      const offences: string[] = [];
      for (const { n, text } of bodyOf(file)) {
        if (SAFE_CLOCK_LEAK_RE.test(text))
          offences.push(`${n}: ${text.trim()}`);
      }
      expect(offences).toEqual([]);
    });

    it(`${rel} — no emoji`, () => {
      const offences: string[] = [];
      for (const { n, text } of bodyOf(file)) {
        if (EMOJI_RE.test(text)) offences.push(`${n}: ${text.trim()}`);
      }
      expect(offences).toEqual([]);
    });

    it(`${rel} — no price literal (prices come only from price_idr)`, () => {
      const offences: string[] = [];
      for (const { n, text } of bodyOf(file)) {
        if (PRICE_LITERAL_RE.test(text)) offences.push(`${n}: ${text.trim()}`);
      }
      expect(offences).toEqual([]);
    });

    it(`${rel} — Bahasa term set stays verbatim, never a lowercase paraphrase`, () => {
      const offences: string[] = [];
      for (const { n, text } of bodyOf(file)) {
        for (const term of BAHASA_TERMS) {
          if (LOWERCASE_PARAPHRASE_RE[term].test(text)) {
            offences.push(`${n}: lowercase "${term}" — ${text.trim()}`);
          }
        }
      }
      expect(offences).toEqual([]);
    });
  }
});

// ---------------------------------------------------------------------------
// The three rules that knew only English.
//
// Until #6948 this corpus had no Indonesian column, so "the guard reads both
// languages" was true of the FILE and false of three of its ten rules: the
// EN/ID dictionary could carry `perpanjangan otomatis`, `biasanya disetujui`
// or `semua kami urus` and every screen test would still be green. That is
// family #3 UNDER-match, found by the on-disk gate on #6948 and closed here.
//
// Each form below is convicted individually rather than as one blob: a row
// that matches "some Bahasa somewhere" tells a future reader nothing about
// which spelling it actually knows.
// ---------------------------------------------------------------------------
describe("voa-copy.guard — the Bahasa forms of the three English-only rules", () => {
  const GUILTY_BAHASA: Array<[string, string]> = [
    ["Perpanjangan otomatis setelah 30 hari.", "second/automatic extension"],
    ["Anda mendapat perpanjangan kedua.", "second/automatic extension"],
    ["Visa ini diperpanjang otomatis.", "second/automatic extension"],
    ["Bisa diperpanjang dua kali.", "second/automatic extension"],
    [
      "Anda dapat memperpanjang lagi tahun depan.",
      "second/automatic extension",
    ],
    [
      "Permohonan seperti ini biasanya disetujui.",
      "trap: approval-guarantee-as-statistic",
    ],
    [
      "Hampir selalu disetujui oleh Imigrasi.",
      "trap: approval-guarantee-as-statistic",
    ],
    [
      "Klien kami belum pernah ditolak.",
      "trap: approval-guarantee-as-statistic",
    ],
    ["Semua kami urus untuk Anda.", "trap: false all-handled promise"],
    ["Kami urus semuanya.", "trap: false all-handled promise"],
    ["Tidak perlu khawatir soal dokumen.", "trap: false all-handled promise"],
    ["Proses bebas repot.", "trap: false all-handled promise"],
  ];

  for (const [sentence, label] of GUILTY_BAHASA) {
    it(`convicts: ${sentence}`, () => {
      const hit = BANNED_CLAIMS.find((rule) => convicts(rule, sentence));
      expect(hit?.label).toBe(label);
    });
  }

  /**
   * INNOCENCE, and it is the half that costs something to get right. These
   * sentences are what the funnel must be free to say — including the one
   * that states the extension limit, which is the rule the DECLINE screen
   * exists to explain.
   */
  const INNOCENT_BAHASA = [
    "Visa on Arrival ini tidak dapat diperpanjang untuk kedua kali.",
    "Visa on Arrival tidak bisa diperpanjang lagi setelah perpanjangan pertama.",
    "Memperpanjang Visa on Arrival yang sudah saya miliki",
    "Saya sudah pernah memperpanjang Visa on Arrival ini satu kali",
    "Kami belum dapat memeriksa kelayakan saat ini. Silakan coba lagi.",
    "Meja visa kami menjawab di WhatsApp.",
  ];

  for (const sentence of INNOCENT_BAHASA) {
    it(`acquits: ${sentence}`, () => {
      const hit = BANNED_CLAIMS.find((rule) => convicts(rule, sentence));
      expect(hit?.label ?? null).toBeNull();
    });
  }

  /**
   * The negation reading is a real mechanism, not a decorative flag: with it
   * off, the honest sentence about the extension limit is convicted. This is
   * what keeps the innocence rows above from being green-by-absence.
   */
  it("negationFlips is what acquits the honest extension sentence", () => {
    const honest =
      "Visa on Arrival ini tidak dapat diperpanjang untuk kedua kali.";
    const rule = BANNED_CLAIMS.find(
      (r) => r.label === "second/automatic extension",
    );
    expect(rule).toBeTruthy();
    expect(convicts(rule!, honest)).toBe(false);
    expect(convicts({ ...rule!, negationFlips: false }, honest)).toBe(true);
  });

  /**
   * And the flag is scoped: the other two rules must stay convicting even
   * though their own claims contain a negator. Reading "belum pernah ditolak"
   * as innocent would have deleted the rule while leaving its name in place.
   */
  it("the negation reading does not leak into the other two rules", () => {
    for (const label of [
      "trap: approval-guarantee-as-statistic",
      "trap: false all-handled promise",
    ]) {
      const rule = BANNED_CLAIMS.find((r) => r.label === label);
      expect(rule?.negationFlips ?? false).toBe(false);
    }
    expect(
      BANNED_CLAIMS.some((rule) =>
        convicts(rule, "Klien kami belum pernah ditolak."),
      ),
    ).toBe(true);
  });
});
