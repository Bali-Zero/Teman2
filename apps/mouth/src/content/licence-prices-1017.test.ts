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
const ALCOHOL_LABEL =
  /alcohol|alkohol|minuman beralkohol|golongan|NPBBKC|SKPL|алкогол|alcool|alcolici/i;
// The retired A+B+C price, in full ("15,000,000", "15 000 000") or short ("15 million").
const RETIRED_ALCOHOL =
  /(?<![\d.,])15(?:[.,\u00a0\u202f ]000){2}(?!\d)|(?<![\d.,])15\s+(?:million|juta|млн)(?![A-Za-z])/i;

/**
 * Two independent rules, either one is a violation:
 *  1. on an NPBBKC line every amount must be one of {4M, 10M, 12M}; a short
 *     "15M"-style amount is never allowed there (it cannot be checked);
 *  2. any alcohol-licence line (label in any locale, NPBBKC or not) carrying
 *     the retired 15M figure.
 * Rule 2 alone dropped "any other amount is wrong" (5M on an NPBBKC row).
 */
export function alcoholViolation(line: string): boolean {
  if (/NPBBKC/.test(line)) {
    if ([...line.matchAll(SHORT)].length > 0) return true;
    if (fullAmounts(line).some((n) => !ALCOHOL_OK.has(n))) return true;
  }
  return ALCOHOL_LABEL.test(line) && RETIRED_ALCOHOL.test(line);
}

/** PIRT carries no Bali Zero price at all. */
export function onRequestViolation(line: string): boolean {
  return /\bPIRT\b/.test(line) && hasAmount(line);
}

/** An SLHS label may have its quoted price on the following non-empty line. */
export function slhsViolation(line: string, nextNonEmpty = ""): boolean {
  return (
    /\bSLHS\b/.test(line) &&
    (hasAmount(line) ||
      (!nextNonEmpty.trimStart().startsWith("|") && hasAmount(nextNonEmpty)))
  );
}

/** Halal figures that were Bali Zero / unattributed quotes and are retired. */
const RETIRED_HALAL =
  /5[.,   ]000[.,   ]000\s*[-–]\s*8[.,   ]000[.,   ]000|(?<![\d.,])5\s?[-–]\s?8\s?(?:M\b|juta\b|million\b)|(?<![\d.,])0\s?[-–]\s?50\s?(?:M\b|juta\b|million\b|milioni\b|миллион\w*)|(?<![\d.,])5\s?[-–]\s?25\s?(?:M\b|juta\b|million\b|milioni\b|миллион\w*)|1\s?[-–]\s?8M\b/;
export function halalViolation(line: string, file = ""): boolean {
  // The "Cost:" / "costs (IDR 0-50M)" lines of a halal article do not repeat
  // the word "halal", so inside a halal-named file every line is in scope.
  const inScope = !file || /halal/i.test(file) || /halal|халял/i.test(line);
  return inScope && RETIRED_HALAL.test(line);
}

/** A KITAP + MERP bundle (or a "+ MERP" add-on) prices the KITAP, which stays. */
const MERP_BUNDLE = /\+\s*MERP/i;

/**
 * MERP price lines: rows, cost lines and renewal lines, never the KITAP bundle.
 * Two rules, either one is a violation:
 *  1. the original line rules (table row whose FIRST cell names MERP/STM with an
 *     amount; "Cost:" lines; MERP renewal lines; USD budget lines are exempt);
 *  2. a MERP label followed, on the same line, by a colon or pipe and an
 *     amount: "- MERP (Multiple Re-entry): IDR 1,000,000",
 *     "MERP 1 Anno: IDR 4.000.000", "1x MERP (1 tahun): Rp 4.000.000".
 */
export function merpViolation(line: string): boolean {
  return merpLineRule(line) || merpLabelRule(line);
}

function merpLineRule(line: string): boolean {
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

function merpLabelRule(line: string): boolean {
  if (MERP_BUNDLE.test(line) || /KITAP/.test(line)) return false;
  if (line.trimStart().startsWith("|")) {
    // Table row: a SHORT cell that is a MERP label (any column, not only the
    // first) followed by a priced cell. A long cell is a sentence ("Compare
    // single ERP total with MERP quote"), not a price label.
    const cells = line.split("|").slice(1, -1);
    return cells.some(
      (cell, i) =>
        cell.trim().length <= 30 &&
        /\bMERP\b/.test(cell) &&
        cells
          .slice(i + 1)
          .some((c) => /\b(?:IDR|Rp)\b/.test(c) && hasAmount(c)),
    );
  }
  const m = /\bMERP\b[^:|\n]{0,40}:/.exec(line);
  if (!m) return false;
  return (
    /\b(?:IDR|Rp)\b/.test(line) && hasAmount(line.slice(m.index + m[0].length))
  );
}

/**
 * The ONE exemption from the MERP rules. exit-reentry-permits keeps a row with
 * the government's own MERP fee range (`| MERP | IDR 800K-1M | On request | On
 * request |`: fee column = the state's PNBP range, the Bali Zero service and
 * total columns = on request). Both MERP rules fire on that row by design (first
 * cell is MERP, it carries an amount), so without this exemption the restored
 * government-fee fact could not stay. It is exact: the range is the only figure
 * allowed, and every other column must say "on request".
 */
export function governmentMerpFact(line: string): boolean {
  return (
    /^\|\s*MERP\s*\|/.test(line) &&
    /(?:IDR\s*800K-1M|800K-1M\s*IDR|800\s*тыс\.\s*-\s*1\s*млн\s*IDR)/.test(
      line,
    ) &&
    /(?:On request|Atas permintaan|Su richiesta|Sur demande|По запросу)/.test(
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

/**
 * One line, with what the line checks need around it: the next non-empty line
 * (an SLHS label keeps its price on the line after) and a scope name (a halal
 * article file, or the URL of the llms section the line sits in).
 */
type Unit = { at: string; text: string; next: string; scope: string };

function unitsOf(
  fileLines: string[],
  at: (i: number) => string,
  scopeOf: (i: number) => string,
): Unit[] {
  const out: Unit[] = new Array(fileLines.length);
  let next = "";
  for (let i = fileLines.length - 1; i >= 0; i--) {
    out[i] = { at: at(i), text: fileLines[i], next, scope: scopeOf(i) };
    if (fileLines[i].trim()) next = fileLines[i];
  }
  return out;
}

const articleUnits = files.flatMap((f) => {
  const rel = path.relative(ARTICLES, f);
  return unitsOf(
    fs.readFileSync(f, "utf8").split("\n"),
    (i) => `${rel}:${i + 1}`,
    () => rel,
  );
});

// What LLM crawlers read: the committed exports of every article. Each line
// is scoped by the URL of its section, so a halal section's "Cost:" lines are
// in scope for the halal rule.
const PUBLIC = path.join(ROOT, "public");
const LLMS_EXPORTS = ["llms-full.txt", "llms-id.txt"];
const llmsUnits = LLMS_EXPORTS.flatMap((name) => {
  const all = fs.readFileSync(path.join(PUBLIC, name), "utf8").split("\n");
  const scopes: string[] = new Array(all.length);
  let url = "";
  all.forEach((text, i) => {
    if (text.startsWith("URL: ")) url = text.slice(5);
    scopes[i] = url;
  });
  return unitsOf(
    all,
    (i) => `public/${name}:${i + 1}`,
    (i) => scopes[i],
  );
});

const everyUnit = [...articleUnits, ...llmsUnits];

describe("guards are not vacuous (guilt: the retired lines fail)", () => {
  it("old alcohol, SLHS, PIRT, halal and MERP lines are caught", () => {
    expect(
      alcoholViolation(
        "Bali Zero provides this alcohol licence for IDR 15,000,000.",
      ),
    ).toBe(true);
    expect(alcoholViolation("| Izin Alkohol (A+B+C) | 15.000.000 |")).toBe(
      true,
    );
    expect(alcoholViolation("licence alcool pour **15 000 000 IDR**")).toBe(
      true,
    );
    // the original NPBBKC fixtures, kept verbatim
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
    // any other amount on an NPBBKC line is wrong, not only the retired 15M
    expect(alcoholViolation("| NPBBKC (Golongan A) | IDR 5,000,000 |")).toBe(
      true,
    );
    expect(alcoholViolation("NPBBKC Golongan A + B + C: IDR 15M")).toBe(true);
    expect(slhsViolation("SLHS", "IDR 9–25 million")).toBe(true);
    expect(slhsViolation("assistance for **IDR 9,000,000**, SLHS")).toBe(true);
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
    expect(merpViolation("- MERP (Multiple Re-entry): IDR 1,000,000")).toBe(
      true,
    );
    // the three original MERP guilt fixtures, kept verbatim
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
    // label forms found in the llms exports
    expect(merpViolation("MERP 1 Anno: IDR 4.000.000")).toBe(true);
    expect(
      merpViolation(
        "| **5+ trips**               | 1-Year MERP                | IDR 4,000K (flat)                |",
      ),
    ).toBe(true);
    expect(merpViolation("- MERP d'1 An : IDR 4 000 000")).toBe(true);
    expect(merpViolation("- 1x MERP (1 tahun): Rp 4.000.000")).toBe(true);
    expect(
      merpViolation("- MERP (Multiple Re-entry): IDR 4,000,000-5,000,000"),
    ).toBe(true);
    expect(exitPermitViolation('        Cost: "IDR 1-1.5M",')).toBe(true);
    expect(halalViolation("IDR 5-8M")).toBe(true);
    expect(halalViolation("5–8 juta")).toBe(true);
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
      slhsViolation("| SLHS | Hygiene Sanitation Certificate |", "On request"),
    ).toBe(false);
    expect(
      slhsViolation("| SLHS | Hygiene Sanitation Certificate | On request |"),
    ).toBe(false);
    expect(
      alcoholViolation(
        "| NPBBKC Golongan B + C | IDR 10,000,000 | 4-8 weeks |",
      ),
    ).toBe(false);
    expect(halalViolation("Processing takes 5-8 months.")).toBe(false);
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
    expect(merpViolation("| KITAP + MERP | IDR 33,000,000 |")).toBe(false);
    expect(merpViolation("KITAP + MERP 1 Anno: IDR 33.000.000")).toBe(false);
    // a comparison sentence in a table cell is not a MERP price label
    expect(
      merpViolation(
        "| **3-4 trips**              | Compare single ERP total with MERP quote | IDR 2,400K - 3,200K (single ERPs) |",
      ),
    ).toBe(false);
    expect(merpViolation("SERP: IDR 300,000")).toBe(false);
    // the government-fee row is the only exempt MERP row, and only as-is
    expect(
      merpViolation("| MERP | IDR 800K-1M | On request | On request |"),
    ).toBe(true);
    expect(
      governmentMerpFact("| MERP | IDR 800K-1M | On request | On request |"),
    ).toBe(true);
    expect(
      governmentMerpFact("| MERP | IDR 1,000,000 | On request | On request |"),
    ).toBe(false);
    expect(governmentMerpFact("| MERP | IDR 800K-1M | IDR 4,000,000 |")).toBe(
      false,
    );
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
  it("scans the corpus and both llms exports", () => {
    expect(files.length).toBeGreaterThan(100);
    for (const name of LLMS_EXPORTS)
      expect(
        llmsUnits.filter((u) => u.at.startsWith(`public/${name}:`)).length,
      ).toBeGreaterThan(1000);
  });

  it("NPBBKC lines quote only 4M / 10M / 12M (A / B+C / A+B+C), never 15M", () => {
    const hits = everyUnit
      .filter((u) => alcoholViolation(u.text))
      .map((u) => u.at);
    expect(hits).toEqual([]);
  });

  it("no article or llms export carries a Bali Zero price for SLHS or PIRT", () => {
    const hits = everyUnit
      .filter(
        (u) => onRequestViolation(u.text) || slhsViolation(u.text, u.next),
      )
      .map((u) => u.at);
    expect(hits).toEqual([]);
  });

  it("the retired halal quotes (5-8M, 0-50M, 5-25M, 1-8M) are gone", () => {
    const hits = everyUnit
      .filter((u) => halalViolation(u.text, u.scope))
      .map((u) => u.at);
    expect(hits).toEqual([]);
  });

  it("no standalone MERP price carries an amount", () => {
    const hits = everyUnit
      .filter((u) => merpViolation(u.text) && !governmentMerpFact(u.text))
      .map((u) => u.at);
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
          (/^\|\s*MERP\s*\|/.test(l.text) &&
            hasAmount(l.text) &&
            !governmentMerpFact(l.text)) ||
          (/MERP/.test(l.text) &&
            /(?:biaya|costo|prezzo|harga)/i.test(l.text) &&
            !/\bERP\b.*\d/.test(l.text) &&
            hasAmount(l.text)),
      )
      .map((l) => l.at);
    expect(hits).toEqual([]);
  });
});
