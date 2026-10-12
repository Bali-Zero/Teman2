// =============================================================================
// E33E RETIREMENT PRICE GUARD (owner ruling 2026-10-12).
//
// E33E is the 5-year RETIREMENT KITAS (55+). Its Bali Zero price lives in the
// catalogue row `kitas_permits` -> "E33E Second Home Senior (5 Years)" and is
// IDR 45,000,000 all-inclusive. The retirement guide quoted IDR 18M in five
// languages (table row, cost block, "Total 5-Year Cost", comparison card) —
// the number belongs to no E33E row. No article line may state an E33E price
// that is not the catalogue's.
//
// Scope: every article line that names E33E and carries an IDR amount, plus,
// inside retirement-visa-indonesia*.mdx, the lines that label a 5-year price.
// Renewal / extension lines are a different product and are skipped.
// =============================================================================
import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

const ARTICLES_PATH = path.join(process.cwd(), "src/content/articles");
const CATALOGUE_PATH = path.join(
  process.cwd(),
  "../backend-rag/backend/data/bali_zero_official_prices_2026.json",
);
const E33E_ROW = "E33E Second Home Senior (5 Years)";

// family-reunification-indonesia* uses "E33E" as a dependent-child code with a
// price range that is not catalogue-derived; that is a separate, tracked
// defect (E31E is the child code) and not an E33E retirement price claim.
const KNOWN_MISCODED = /^family-reunification-indonesia/;

const RENEWAL =
  /renew|extend|extension|perpanjang|продлен|renouvel|prolong|rinnov|proroga|annual|ежегодн/i;
const FIVE_YEAR_LABEL =
  /5[- ]?year|5 ans|5 anni|5 tahun|5 лет|на 5 лет|за 5 лет|\(5 (years|ans|anni|tahun)\)/i;

/** IDR amounts on a line, normalised to integer rupiah. */
export function idrAmounts(line: string): number[] {
  const out: number[] = [];
  const grouped = "\\d{1,3}(?:[.,\\u00a0 ]\\d{3})+";
  const re = new RegExp(
    `(?:IDR|Rp\\.?)\\s*(${grouped}|\\d+(?:[.,]\\d+)?)(?:\\s*(M|juta|jt|million|millions|milioni|млн)(?![\\p{L}]))?` +
      `|(${grouped}|\\d+(?:[.,]\\d+)?)\\s*(M\\b|juta|jt|million|millions|milioni|млн)?\\s*IDR`,
    "giu",
  );
  for (const m of line.matchAll(re)) {
    const num = m[1] ?? m[3];
    const unit = m[2] ?? m[4];
    if (!num) continue;
    const value = unit
      ? parseFloat(num.replace(",", ".")) * 1_000_000
      : parseInt(num.replace(/[.,  ]/g, ""), 10);
    // A client price is a few million to a few hundred million rupiah; a
    // billion-scale figure ("Rp 5 miliar" property floor) is another claim.
    if (Number.isFinite(value) && value >= 1_000_000 && value < 500_000_000)
      out.push(value);
  }
  return out;
}

function catalogueE33EPrice(): number {
  const cat = JSON.parse(fs.readFileSync(CATALOGUE_PATH, "utf8"));
  const row = cat.services.kitas_permits[E33E_ROW];
  expect(row, `catalogue row ${E33E_ROW}`).toBeTruthy();
  return parseInt(String(row.price).replace(/[^\d]/g, ""), 10);
}

function articleFiles(): { rel: string; file: string }[] {
  const out: { rel: string; file: string }[] = [];
  for (const folder of fs.readdirSync(ARTICLES_PATH)) {
    const dir = path.join(ARTICLES_PATH, folder);
    if (!fs.statSync(dir).isDirectory()) continue;
    for (const f of fs.readdirSync(dir)) {
      if (f.endsWith(".mdx"))
        out.push({ rel: `${folder}/${f}`, file: path.join(dir, f) });
    }
  }
  return out;
}

describe("E33E retirement price (owner ruling 2026-10-12)", () => {
  it("catalogue row is IDR 45,000,000", () => {
    expect(catalogueE33EPrice()).toBe(45_000_000);
  });

  it("idrAmounts reads the shapes the articles use (teeth)", () => {
    expect(idrAmounts("| 5-Year Visa | IDR 18,000,000 |")).toEqual([
      18_000_000,
    ]);
    expect(idrAmounts("| 5 ans | 18 000 000 IDR |")).toEqual([18_000_000]);
    expect(idrAmounts('"Bali Zero Price": "IDR 18M (5 years)",')).toEqual([
      18_000_000,
    ]);
    expect(idrAmounts('"Bali Zero Price": "18 млн IDR (5 лет)",')).toEqual([
      18_000_000,
    ]);
    expect(idrAmounts("| E33E | IDR 45.000.000 |")).toEqual([45_000_000]);
  });

  it("no article states an E33E 5-year price other than the catalogue's", () => {
    const expected = catalogueE33EPrice();
    const offenders: string[] = [];
    for (const { rel, file } of articleFiles()) {
      const base = path.basename(rel);
      if (KNOWN_MISCODED.test(base)) continue;
      const isRetirementGuide = /^retirement-visa-indonesia/.test(base);
      const lines = fs.readFileSync(file, "utf8").split("\n");
      let heading = "";
      lines.forEach((line, i) => {
        if (/^#{1,6}\s/.test(line)) heading = line;
        if (RENEWAL.test(line)) return;
        const names = /E33E/.test(line);
        // Inside the retirement guide a 5-year price line is E33E's when the
        // nearest heading is the E33E section, or when it is a "Bali Zero
        // Price" comparison-card value. The E33F "5-Year Total" (1-year
        // product x 5) sits under an E33F heading and is a different claim.
        const labelled5y =
          isRetirementGuide &&
          FIVE_YEAR_LABEL.test(line) &&
          ((/E33E/.test(heading) && !/E33F/.test(heading)) ||
            /Bali Zero Price/.test(line));
        if (!names && !labelled5y) return;
        for (const amount of idrAmounts(line)) {
          if (amount !== expected) {
            offenders.push(
              `${rel}:${i + 1} states IDR ${amount} (catalogue ${expected})`,
            );
          }
        }
      });
    }
    expect(offenders).toEqual([]);
  });
});
