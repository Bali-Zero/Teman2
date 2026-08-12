import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

/**
 * DATA-COHERENCE QUARANTINE — THESE ARE FALSE CLAIMS STILL SERVED TO CLIENTS.
 *
 * `whatChanged` in canonical and gold can assert KBLI-2020 ancestry that the
 * same record's official BPS ancestor set does not support. This test does not
 * rewrite or hide that prose: the content cure belongs in a follow-up compiler
 * lane such as `cure_whatchanged_corroborated_predecessor.py`. The exact
 * 2026-08-12 populations below are pinned so every class can only shrink; any
 * intentional cure must ratchet the corresponding number downward.
 */

const REPO_ROOT = path.resolve(process.cwd(), "../..");
const CANONICAL_PATH = path.join(
  REPO_ROOT,
  "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json",
);
const GOLD_PATH = path.join(REPO_ROOT, "apps/mouth/data/kbli-gold-all.json");

interface CanonicalRecord {
  kode_kbli_2025: string;
  bps_2020_ancestors?: { codes?: string[] } | null;
  intel_2026?: { whatChanged?: string } | null;
}

interface CanonicalDataset {
  data: CanonicalRecord[];
}

interface GoldRecord {
  whatChanged?: string;
}

const ANCESTRY_ASSERTION =
  /(?:Direct 1:1 match|Previous code\(s\)|Renumbered from|Merged from)/i;

const POSITIVE_ANCESTRY_SENTENCE =
  /(?:Previous code\(s\)|Previous KBLI 2020 sources|Renumbered from|Merged from|Merges KBLI 2020|Consolidated from|Aggregated from|aggregated from|absorbs KBLI 2020|Inherits part of the old KBLI 2020|previously aggregated under KBLI 2020|data merged from KBLI 2020|split out from the unified KBLI 2020|under a single code: KBLI 2020)/i;

const RETRACTED_ANCESTRY_SENTENCE =
  /(?:not supported|unconfirmed|false .*narrative|not \d{5}|do not .*number-intuitions)/i;

function bpsCodes(record: CanonicalRecord): Set<string> {
  return new Set(record.bps_2020_ancestors?.codes ?? []);
}

function namedAncestryCodes(text: string, currentCode: string): Set<string> {
  const named = new Set<string>();

  for (const sentence of text.split(/(?<=[.!?])\s+/)) {
    if (
      !POSITIVE_ANCESTRY_SENTENCE.test(sentence) ||
      RETRACTED_ANCESTRY_SENTENCE.test(sentence)
    ) {
      continue;
    }

    const ancestryMarker = sentence.search(
      /(?:KBLI[- ]?2020|Previous code\(s\)|Previous KBLI 2020 sources)/i,
    );

    for (const match of sentence.matchAll(/\b\d{5}\b/g)) {
      const code = match[0];
      const offset = match.index ?? 0;
      const before = sentence.slice(0, offset);
      const after = sentence.slice(offset + code.length);
      const renumberedBeforeMarker = new RegExp(
        `Renumbered from\\s+${code}\\s+in KBLI 2020`,
        "i",
      ).test(sentence);

      if (code === currentCode) continue;
      if (offset < ancestryMarker && !renumberedBeforeMarker) continue;
      if (/KBLI 2025[^.]{0,80}$/.test(before)) continue;
      if (/^\s*(?:\([^)]*\))?\s*(?:is|was|now|instead)/i.test(after)) {
        continue;
      }
      named.add(code);
    }
  }

  return named;
}

function contradictionCounts(
  canonical: CanonicalRecord[],
  textFor: (record: CanonicalRecord) => string,
): { noBpsButClaimsAncestry: number; namedCodeOutsideBps: number } {
  let noBpsButClaimsAncestry = 0;
  let namedCodeOutsideBps = 0;

  for (const record of canonical) {
    const text = textFor(record);
    if (!text) continue;
    const officialAncestors = bpsCodes(record);

    if (officialAncestors.size === 0 && ANCESTRY_ASSERTION.test(text)) {
      noBpsButClaimsAncestry += 1;
    }

    const unsupported = [
      ...namedAncestryCodes(text, record.kode_kbli_2025),
    ].filter((code) => !officialAncestors.has(code));
    if (unsupported.length > 0) namedCodeOutsideBps += 1;
  }

  return { noBpsButClaimsAncestry, namedCodeOutsideBps };
}

function tsxFiles(root: string): string[] {
  const files: string[] = [];
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name === ".next") continue;
    const absolute = path.join(root, entry.name);
    if (entry.isDirectory()) files.push(...tsxFiles(absolute));
    else if (entry.name.endsWith(".tsx") && !entry.name.includes(".test.")) {
      files.push(absolute);
    }
  }
  return files;
}

describe("KBLI whatChanged data-coherence guardian", () => {
  it("pins the four known false-claim populations at their measured 2026-08-12 counts", () => {
    const canonical = (
      JSON.parse(fs.readFileSync(CANONICAL_PATH, "utf8")) as CanonicalDataset
    ).data;
    const gold = JSON.parse(fs.readFileSync(GOLD_PATH, "utf8")) as Record<
      string,
      GoldRecord
    >;

    expect(
      contradictionCounts(
        canonical,
        (record) => record.intel_2026?.whatChanged ?? "",
      ),
    ).toEqual({
      noBpsButClaimsAncestry: 58,
      namedCodeOutsideBps: 21,
    });
    expect(
      contradictionCounts(
        canonical,
        (record) => gold[record.kode_kbli_2025]?.whatChanged ?? "",
      ),
    ).toEqual({
      noBpsButClaimsAncestry: 10,
      namedCodeOutsideBps: 57,
    });
  });

  it("binds every whatChanged TSX render reference to the three audited sites", () => {
    const srcRoot = path.join(REPO_ROOT, "apps/mouth/src");
    const references = tsxFiles(srcRoot)
      .flatMap((file) => {
        const source = fs.readFileSync(file, "utf8");
        return [...source.matchAll(/\bwhatChanged\b/g)].map(() =>
          path.relative(REPO_ROOT, file),
        );
      })
      .sort();

    // page.tsx has the gold render plus the intel guard+render; Inspector has
    // the third render site. A new reference is unaudited and must turn red.
    expect(references).toEqual([
      "apps/mouth/src/app/kbli-explorer/components/KBLIInspector.tsx",
      "apps/mouth/src/app/kbli/[code]/page.tsx",
      "apps/mouth/src/app/kbli/[code]/page.tsx",
      "apps/mouth/src/app/kbli/[code]/page.tsx",
    ]);
  });
});
