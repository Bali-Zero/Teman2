import { describe, expect, it } from "vitest";

import { getAllCodes, getCode } from "./kbli-data";
import { getGoldCodes, getGoldContent } from "./kbli-data.server";
import type { KBLIPmaInfo } from "./kbli-types";

// =============================================================================
// This guard exists because certified editorial text has repeatedly told
// foreign investors a restricted code is "open" — /kbli/47111 said "fully
// open to 100% PMA" on a code that was not, /kbli/95220's pullQuote read
// "National openness remains real" on a 0% Koperasi/UMKM-allocated record,
// /kbli/41020 headlined "Clearly Open at Scale" on a 0% code. Every one of
// those was caught by a human reading the page, not by a test. This file is
// the test.
// =============================================================================

/**
 * Known openness-claim SHAPES, matched case-insensitively. This is a ratchet
 * against phrasing this repo has actually shipped by mistake at least once —
 * NOT a proof of absence. SAETTA-20260915 W-H PR-3c (gate-6593) de-certified
 * 12 canonicalIntel + 6 mouthGold entries whose prose claimed an openness
 * their own tuple denied, and it found several of those by human/semantic
 * review of paraphrases a regex sweep like this one would not have caught on
 * its own (see kbli-editorial-certification.test.ts). New phrasing always
 * needs a human read; this only re-catches the shapes already seen.
 */
export const OPENNESS_CLAIM_PATTERNS: { name: string; re: RegExp }[] = [
  { name: "fully-open", re: /fully open/gi },
  {
    name: "100-pct-foreign",
    re: /100%\s*(?:foreign|pma|foreign[- ]owned|foreign ownership)/gi,
  },
  { name: "open-to-100-pct", re: /open to (?:up to )?100%/gi },
  { name: "genuinely-open", re: /genuinely open/gi },
  { name: "national-openness", re: /national openness/gi },
  { name: "clearly-open", re: /clearly open/gi },
  { name: "fully-foreign-owned", re: /fully foreign[- ]owned/gi },
  {
    name: "no-local-partner-required",
    re: /no local (?:indonesian )?partner (?:is )?required/gi,
  },
  { name: "wholly-foreign-owned", re: /wholly foreign[- ]owned/gi },
  { name: "open-to-foreign-investment", re: /open to foreign investment/gi },
  { name: "open-to-pma", re: /\bopen to (?:a )?(?:PT )?PMA\b/gi },
];

/** A match is not a claim if one of these sits immediately before it. */
const NEGATION_WINDOW_CHARS = 20;
const NEGATION_IMMEDIATELY_BEFORE =
  /\b(?:not|never|isn't|is not|cannot be|can't be)\s+(?:a\s+|an\s+)?$/i;

/**
 * "open to foreign investment" alone is not a claim when the SAME sentence
 * immediately qualifies it with its own cap — "open to foreign investment up
 * to 49%" is a correct description of a 49%-capped code, not a false one.
 */
const CAP_FOLLOWUP_WINDOW_CHARS = 40;
const CAP_FOLLOWUP_QUALIFIER = /(up to \d+%|capped|maximum|\bmax\b)/i;

/** A code is "capped" unless its tuple is exactly fully open. */
function isFullyOpenPma(
  pma: Pick<
    KBLIPmaInfo,
    "status" | "capVerified" | "maxForeign" | "capSpecial"
  >,
): boolean {
  return (
    pma.status === "open" &&
    pma.capVerified === true &&
    pma.maxForeign === 100 &&
    !pma.capSpecial
  );
}

/** Recursively collect every non-empty string field, keyed by a dotted/bracketed path. */
function walkStringFields(
  value: unknown,
  prefix: string,
  out: Record<string, string>,
): void {
  if (typeof value === "string") {
    if (value.trim().length > 0) out[prefix] = value;
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) =>
      walkStringFields(item, `${prefix}[${index}]`, out),
    );
    return;
  }
  if (value !== null && typeof value === "object") {
    for (const [key, nested] of Object.entries(
      value as Record<string, unknown>,
    )) {
      walkStringFields(nested, prefix ? `${prefix}.${key}` : key, out);
    }
  }
}

export interface OpennessFinding {
  code: string;
  fieldPath: string;
  pattern: string;
  match: string;
  context: string;
}

/**
 * Scan every text field of a code's served content for an openness claim
 * that its own PMA tuple denies. Fully-open codes are never scanned — a
 * "fully open to 100%" sentence on a genuinely 100%-open code is true, not a
 * finding.
 */
function findOpennessClaims(
  code: string,
  pma: Pick<
    KBLIPmaInfo,
    "status" | "capVerified" | "maxForeign" | "capSpecial"
  >,
  texts: Record<string, string>,
): OpennessFinding[] {
  if (isFullyOpenPma(pma)) return [];

  const findings: OpennessFinding[] = [];
  for (const [fieldPath, text] of Object.entries(texts)) {
    for (const { name, re } of OPENNESS_CLAIM_PATTERNS) {
      re.lastIndex = 0;
      let match: RegExpExecArray | null;
      while ((match = re.exec(text)) !== null) {
        const start = match.index;
        const matched = match[0];
        const precedingWindow = text.slice(
          Math.max(0, start - NEGATION_WINDOW_CHARS),
          start,
        );
        if (NEGATION_IMMEDIATELY_BEFORE.test(precedingWindow)) {
          if (matched.length === 0) re.lastIndex++;
          continue;
        }
        if (name === "open-to-foreign-investment") {
          const followingWindow = text.slice(
            start + matched.length,
            start + matched.length + CAP_FOLLOWUP_WINDOW_CHARS,
          );
          if (CAP_FOLLOWUP_QUALIFIER.test(followingWindow)) {
            if (matched.length === 0) re.lastIndex++;
            continue;
          }
        }
        findings.push({
          code,
          fieldPath,
          pattern: name,
          match: matched,
          context: text.slice(
            Math.max(0, start - 40),
            Math.min(text.length, start + matched.length + 40),
          ),
        });
        if (matched.length === 0) re.lastIndex++;
      }
    }
  }
  return findings;
}

/**
 * Human-reviewed (code, fieldPath) pairs whose text mechanically matches an
 * OPENNESS_CLAIM_PATTERNS shape but is, on read, NOT a false openness claim.
 * Each entry is a negation the adjacency window cannot see (a form it does not
 * list, or one that FOLLOWS the phrase) or an "open to PMA" statement that is
 * true on a capped code because the same text states the cap.
 *
 * This list must track the live corpus, not a snapshot of it: an entry whose
 * text no longer matches ANY pattern is stale, and the dedicated test below
 * fails naming it, rather than silently keeping a rule that governs nothing.
 */
const REVIEWED_TRUE_TEXT: Record<string, string> = {
  "50126:intel_2026.editorial.body":
    "\"...capped at 49%, rather than being fully open.\" correctly states the cap denies full openness; 'rather than' is a negation construction outside the adjacent forms this scanner checks.",
  "50126:intel_2026.whatYouNeed":
    '"...so a fully foreign-owned PMA cannot hold this code directly" — the negation follows the phrase, which an adjacency window cannot see (Dux read, 2026-09-16).',
  "51101:intel_2026.editorial.headline":
    '"Scheduled Commercial Air Transport Is Open to PMA in Bali" — true on a 49% cap: a PT PMA may enter as a minority-foreign company; the body states the 49% ceiling (reviewed in W-H PR-3c, SAETTA-20260915).',
};

// -----------------------------------------------------------------------------
// Corpus collection — mirrors kbli-editorial-certification.test.ts's loaders.
// -----------------------------------------------------------------------------

interface ScannedGroup {
  code: string;
  source: "intel" | "gold";
  pma: KBLIPmaInfo;
  fields: Record<string, string>;
}

function collectCertifiedGroups(): ScannedGroup[] {
  const groups: ScannedGroup[] = [];

  for (const record of getAllCodes().filter((c) => c.intel_2026)) {
    const fields: Record<string, string> = {};
    walkStringFields(record.intel_2026, "intel_2026", fields);
    groups.push({
      code: record.code,
      source: "intel",
      pma: record.pma,
      fields,
    });
  }

  for (const code of getGoldCodes()) {
    const gold = getGoldContent(code);
    const record = getCode(code);
    if (!gold || !record) continue;
    const fields: Record<string, string> = {};
    walkStringFields(gold, "", fields);
    groups.push({ code, source: "gold", pma: record.pma, fields });
  }

  return groups;
}

function pmaFixture(overrides: Partial<KBLIPmaInfo> = {}): KBLIPmaInfo {
  return {
    status: "restricted",
    maxForeign: 49,
    condition: null,
    isPriority: false,
    note: null,
    source: null,
    verificationStatus: "located",
    officialBasis: "fixture",
    sourceVintage: "2026-01-01",
    capSpecial: false,
    capVerified: true,
    routeTo: null,
    citation: null,
    ...overrides,
  };
}

describe("KBLI certified-openness guard", () => {
  const groups = collectCertifiedGroups();
  const intelGroups = groups.filter((g) => g.source === "intel");
  const goldGroups = groups.filter((g) => g.source === "gold");

  it("actually walks the corpus — a vacuous pass is impossible", () => {
    // Pinned against getAllCodes()/getGoldCodes() 2026-09-16 — the same
    // numbers kbli-editorial-certification.test.ts pins (36/8 since #6640) for the served
    // certified partitions. A drift here means the certified corpus itself
    // changed shape; re-run the scanner before touching this number.
    expect(intelGroups).toHaveLength(36);
    expect(goldGroups).toHaveLength(8);

    const totalFieldsScanned = groups.reduce(
      (sum, g) => sum + Object.keys(g.fields).length,
      0,
    );
    // Pinned 2026-09-16 after #6640 de-certified canonicalIntel 47221:
    // 796 intel_2026 string fields (36 codes, including the nested
    // `editorial` block) + 52 gold string fields (8 codes).
    expect(totalFieldsScanned).toBe(848);
  });

  it("flags every certified openness claim not already human-reviewed", () => {
    const unresolved: string[] = [];
    for (const group of groups) {
      for (const finding of findOpennessClaims(
        group.code,
        group.pma,
        group.fields,
      )) {
        const key = `${finding.code}:${finding.fieldPath}`;
        if (key in REVIEWED_TRUE_TEXT) continue;
        unresolved.push(
          `${key} [${finding.pattern}] "${finding.match}" :: ...${finding.context}...`,
        );
      }
    }
    expect(unresolved, `\n${unresolved.join("\n")}`).toEqual([]);
  });

  it("fails a REVIEWED_TRUE_TEXT entry whose text no longer matches any pattern", () => {
    const fieldsByKey = new Map<string, ScannedGroup>();
    for (const group of groups) {
      for (const fieldPath of Object.keys(group.fields)) {
        fieldsByKey.set(`${group.code}:${fieldPath}`, group);
      }
    }

    for (const key of Object.keys(REVIEWED_TRUE_TEXT)) {
      const group = fieldsByKey.get(key);
      expect(
        group,
        `${key}: no such (code, fieldPath) in the live corpus anymore`,
      ).toBeDefined();
      const [code, ...pathParts] = key.split(":");
      const fieldPath = pathParts.join(":");
      const text = group!.fields[fieldPath];
      const findings = findOpennessClaims(code, group!.pma, {
        [fieldPath]: text,
      });
      expect(
        findings.length,
        `stale allowlist entry ${key}: its text no longer matches any pattern`,
      ).toBeGreaterThan(0);
    }
  });
});

describe("KBLI certified-openness guard — GUILT (fires on a contradicting claim)", () => {
  it("flags an injected 'fully open to 100%' claim on a real capped code", () => {
    const record = getCode("50113")!;
    expect(record.pma.status).toBe("restricted");
    expect(record.pma.maxForeign).toBe(49);

    const fields: Record<string, string> = {};
    walkStringFields(record.intel_2026, "intel_2026", fields);
    const targetPath = "intel_2026.whatYouNeed";
    fields[targetPath] =
      `${fields[targetPath]} This activity is fully open to 100% foreign ownership.`;

    const findings = findOpennessClaims("50113", record.pma, fields);
    expect(findings.some((f) => f.fieldPath === targetPath)).toBe(true);
  });

  it("flags an injected 'open to PT PMA' claim on a 0%-cap tuple", () => {
    const findings = findOpennessClaims(
      "00000",
      pmaFixture({ status: "closed", maxForeign: 0 }),
      { headline: "This Activity Is Open to PT PMA Investors" },
    );
    expect(findings.map((f) => f.pattern)).toEqual(["open-to-pma"]);
  });

  it("flags an injected 'No local partner required.' claim", () => {
    const record = getCode("50113")!;
    const fields: Record<string, string> = {};
    walkStringFields(record.intel_2026, "intel_2026", fields);
    const targetPath = "intel_2026.editorial.standfirst";
    fields[targetPath] = `${fields[targetPath]} No local partner required.`;

    const findings = findOpennessClaims("50113", record.pma, fields);
    expect(
      findings.some(
        (f) =>
          f.fieldPath === targetPath &&
          f.pattern === "no-local-partner-required",
      ),
    ).toBe(true);
  });

  it("flags 'Clearly open at scale' on a synthetic 0%-cap tuple", () => {
    const zeroCapPma = pmaFixture({ status: "closed", maxForeign: 0 });
    const findings = findOpennessClaims("00000", zeroCapPma, {
      headline: "Clearly Open at Scale",
    });
    expect(findings).toHaveLength(1);
    expect(findings[0]).toMatchObject({
      fieldPath: "headline",
      pattern: "clearly-open",
    });
  });
});

describe("KBLI certified-openness guard — INNOCENCE (stays quiet on true text)", () => {
  it("does not flag an article-carrying negation ('not a fully …', 'cannot be wholly …')", () => {
    const findings = findOpennessClaims("00000", pmaFixture(), {
      body: "It is not a fully foreign-owned operation, and a PMA cannot be wholly foreign-owned here.",
    });
    expect(findings).toEqual([]);
  });

  it("does not flag a negation immediately before the phrase", () => {
    const findings = findOpennessClaims("50113", pmaFixture(), {
      injected: "This is NOT fully open.",
    });
    expect(findings).toEqual([]);
  });

  it("does not scan a genuinely fully-open tuple at all", () => {
    const fullyOpenPma = pmaFixture({
      status: "open",
      maxForeign: 100,
      capSpecial: false,
    });
    const findings = findOpennessClaims("00001", fullyOpenPma, {
      headline: "This activity is fully open to 100% foreign ownership.",
    });
    expect(findings).toEqual([]);
  });

  it("does not flag an open-to-foreign-investment claim immediately qualified by its own cap", () => {
    const findings = findOpennessClaims(
      "50113",
      pmaFixture({ maxForeign: 49 }),
      {
        injected: "This sector is open to foreign investment up to 49%.",
      },
    );
    expect(findings).toEqual([]);
  });
});
