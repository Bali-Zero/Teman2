/**
 * Licence prices owner-ruled 2026-10-17 (Zero). Articles quoted figures that
 * Bali Zero does not sell at that price, in five languages:
 *   - alcohol licence (NPBBKC): IDR 4M (Golongan A only), 10M (B + C only),
 *     12M (A + B + C); the old A+B+C figure was 15M;
 *   - SLHS, halal certification and PIRT: no Bali Zero price, "on request";
 *   - standalone MERP: not a priced item (KITAP + MERP bundles are, and stay).
 *
 * Line-based on purpose: each rule reads one article line, the way a client
 * reads it, so a stale figure in any locale names its own file:line.
 */
import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..", "..");
const ARTICLES = path.join(ROOT, "src", "content", "articles");

function walk(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    return e.isDirectory() ? walk(p) : p.endsWith(".mdx") ? [p] : [];
  });
}

// "4,000,000" / "4.000.000" / "4 000 000" (nbsp, narrow nbsp or space)
const FULL = /(?<![\d.,])\d{1,3}(?:[.,   ]\d{3}){2,}(?!\d)/g;
// "15M" / "800K-1M" / "10-15 million" / "5 juta" / "5 млн"
const SHORT =
  /(?<![\d.,])\d+(?:[.,]\d+)?(?:\s?[–-]\s?\d+(?:[.,]\d+)?)?\s?(?:K|M|rb|jt|juta|million|millions|milioni|miliun|млн|тыс\.?|миллион\w*)(?![A-Za-z])/g;

const digitsOf = (s: string) => Number(s.replace(/\D/g, ""));
const fullAmounts = (line: string) =>
  [...line.matchAll(FULL)].map((m) => digitsOf(m[0]));
const hasAmount = (line: string) =>
  fullAmounts(line).length > 0 || [...line.matchAll(SHORT)].length > 0;

const ALCOHOL_OK = new Set([4_000_000, 10_000_000, 12_000_000]);

/** NPBBKC line: every amount is one of the three owner-ruled prices. */
export function alcoholViolation(line: string): boolean {
  if (!/NPBBKC/.test(line)) return false;
  if ([...line.matchAll(SHORT)].length > 0) return true;
  return fullAmounts(line).some((n) => !ALCOHOL_OK.has(n));
}

/** SLHS / PIRT carry no Bali Zero price at all. */
export function onRequestViolation(line: string): boolean {
  return /\b(SLHS|PIRT)\b/.test(line) && hasAmount(line);
}

/** Halal figures that were Bali Zero / unattributed quotes and are retired. */
const RETIRED_HALAL =
  /5[.,   ]000[.,   ]000\s*[-–]\s*8[.,   ]000[.,   ]000|(?<![\d.,])5\s?[-–]\s?8\s?(?:M|juta|million)|(?<![\d.,])0\s?[-–]\s?50\s?(?:M\b|juta|million|milioni|миллион)|(?<![\d.,])5\s?[-–]\s?25\s?(?:M\b|juta|million|milioni|миллион)|1\s?[-–]\s?8M/i;
export function halalViolation(line: string, file = ""): boolean {
  // The "Cost:" / "costs (IDR 0-50M)" lines of a halal article do not repeat
  // the word "halal", so inside a halal-named file every line is in scope.
  const inScope = /halal/i.test(file) || /halal|халял/i.test(line);
  return inScope && RETIRED_HALAL.test(line);
}

/** MERP price lines: rows, cost cards and renewal lines, never the KITAP bundle. */
export function merpViolation(line: string): boolean {
  if (/KITAP/.test(line) || !/MERP|STM/.test(line) || !hasAmount(line))
    return false;
  // "(includes MERP)" prices the KITAP bundle, which stays.
  if (
    /(?:includes?|termasuk|inclut|incluso|включа\w*)\s+(?:the\s+|il\s+)?MERP|MERP\s+(?:included|inclus)/i.test(
      line,
    )
  )
    return false;
  if (line.trimStart().startsWith("|")) {
    const first = line.split("|")[1] ?? "";
    return /MERP|STM/.test(first);
  }
  if (!/IDR|Rp/.test(line)) return false; // USD budget lines are not a MERP fee
  return (
    /\b(?:Cost|Costo|Coût|Biaya|Стоимость)\b\s*:/.test(line) ||
    /MERP renewal|Perpanjangan MERP|Renouvellement du MERP|Продление MERP/.test(
      line,
    )
  );
}

/** exit-reentry-permits: MERP cost cards / rows / FAQ must not carry an amount. */
export function exitPermitViolation(line: string): boolean {
  if (!hasAmount(line)) return false;
  if (/^\s*Cost: "/.test(line)) return /MERP/.test(line) || /1/.test(line);
  return false;
}

const files = walk(ARTICLES);
const lines = files.flatMap((f) =>
  fs
    .readFileSync(f, "utf8")
    .split("\n")
    .map((text, i) => ({ at: `${path.relative(ARTICLES, f)}:${i + 1}`, text })),
);

describe("guards are not vacuous (guilt: the retired lines fail)", () => {
  it("old alcohol, SLHS, PIRT, halal and MERP lines are caught", () => {
    expect(
      alcoholViolation(
        "Bali Zero provides this service for IDR 15,000,000. NPBBKC",
      ),
    ).toBe(true);
    expect(
      alcoholViolation(
        "| NPBBKC Alcohol License (A+B+C) | 15.000.000 | 4-8 sett. |",
      ),
    ).toBe(true);
    expect(alcoholViolation("licence NPBBKC pour **15 000 000 IDR**")).toBe(
      true,
    );
    expect(onRequestViolation("assistance for **IDR 9,000,000**, SLHS")).toBe(
      true,
    );
    expect(
      onRequestViolation(
        "| PIRT (Home Industry Food) | 500,000 - 1,000,000 | 2-4 weeks |",
      ),
    ).toBe(true);
    expect(
      halalViolation(
        "the complete halal certification service costs IDR 5,000,000 - 8,000,000.",
      ),
    ).toBe(true);
    expect(
      halalViolation(
        "4. **Cost:** IDR 0-50 million (small businesses often subsidized)",
        "business/kbli-2025-halal-certification-fnb.mdx",
      ),
    ).toBe(true);
    expect(
      halalViolation(
        "costs (IDR 0-50M), and the Bali restaurant implications",
        "business/kbli-2025-halal-certification-fnb.fr.mdx",
      ),
    ).toBe(true);
    expect(
      halalViolation(
        "- Halal Certification: IDR 5–25 million depending on menu complexity",
      ),
    ).toBe(true);
    expect(
      merpViolation(
        "| MERP/STM          | IDR 1,000,000 | Immigration | Re-entry permit |",
      ),
    ).toBe(true);
    expect(merpViolation("- Cost: IDR 1,000,000 for new MERP")).toBe(true);
    expect(
      merpViolation(
        "**MERP renewal**: Every 5 years, approximately IDR 10,000,000 - 15,000,000",
      ),
    ).toBe(true);
    expect(exitPermitViolation('        Cost: "IDR 1-1.5M",')).toBe(true);
  });

  it("the ruled prices, on-request wording and KITAP bundles pass", () => {
    expect(
      alcoholViolation("| NPBBKC (Golongan A only) | 4,000,000 | 4-8 weeks |"),
    ).toBe(false);
    expect(
      alcoholViolation("NPBBKC Golongan A + B + C **IDR 12,000,000**"),
    ).toBe(false);
    expect(
      alcoholViolation(
        "licence NPBBKC : 4 000 000 IDR ; 10 000 000 IDR ; 12 000 000 IDR",
      ),
    ).toBe(false);
    expect(
      onRequestViolation(
        "| SLHS | Hygiene Sanitation Certificate | On request |",
      ),
    ).toBe(false);
    expect(halalViolation("SIHALAL registration | Free")).toBe(false);
    expect(
      halalViolation(
        "| Large business  | > 50 billion       | 15 - 50 million+ |",
        "business/kbli-2025-halal-certification-fnb.mdx",
      ),
    ).toBe(false);
    expect(
      merpViolation("**Cost:** IDR 33,000,000 per dependent (includes MERP)."),
    ).toBe(false);
    expect(
      merpViolation("| **KITAP + MERP** (after 5 years) | IDR 45,000,000 |"),
    ).toBe(false);
    expect(merpViolation("| STM/MERP (re-entry permit) | On request |")).toBe(
      false,
    );
    expect(
      merpViolation(
        "Single ERP costs IDR 800,000 per trip. The MERP price is quoted on request.",
      ),
    ).toBe(false);
  });
});

describe("licence prices follow the 2026-10-17 owner ruling", () => {
  it("scans the corpus", () => {
    expect(files.length).toBeGreaterThan(100);
  });

  it("NPBBKC lines quote only 4M / 10M / 12M (A / B+C / A+B+C), never 15M", () => {
    const hits = lines.filter((l) => alcoholViolation(l.text)).map((l) => l.at);
    expect(hits).toEqual([]);
  });

  it("no article carries a Bali Zero price for SLHS or PIRT", () => {
    const hits = lines
      .filter((l) => onRequestViolation(l.text))
      .map((l) => l.at);
    expect(hits).toEqual([]);
  });

  it("the retired halal quotes (5-8M, 0-50M, 5-25M, 1-8M) are gone", () => {
    const hits = lines
      .filter((l) => halalViolation(l.text, l.at))
      .map((l) => l.at);
    expect(hits).toEqual([]);
  });

  it("no standalone MERP row, cost line or renewal line carries an amount", () => {
    const hits = lines.filter((l) => merpViolation(l.text)).map((l) => l.at);
    expect(hits).toEqual([]);
  });

  it("exit-reentry-permits cost cards, cost row and FAQ carry no MERP amount", () => {
    const hits = lines
      .filter((l) =>
        /^immigration\/exit-reentry-permits(\.\w\w)?\.mdx/.test(l.at),
      )
      .filter(
        (l) =>
          exitPermitViolation(l.text) ||
          (/^\|\s*(Cost|Biaya|Costo|Coût|Стоимость)\s*\|/.test(l.text) &&
            hasAmount(l.text)) ||
          (/^\|\s*MERP\s*\|/.test(l.text) && hasAmount(l.text)) ||
          (/MERP/.test(l.text) &&
            /(?:biaya|costo|prezzo|harga)/i.test(l.text) &&
            !/\bERP\b.*\d/.test(l.text) &&
            hasAmount(l.text)),
      )
      .map((l) => l.at);
    expect(hits).toEqual([]);
  });
});
