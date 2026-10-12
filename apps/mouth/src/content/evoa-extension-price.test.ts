// =============================================================================
// E-VOA GUIDE — Bali Zero VOA / VOA-extension prices must match the catalogue.
//
// WHY THIS EXISTS. Owner ruling 2026-10-12 (Zero): the e-VOA guide quoted a
// Bali Zero VOA extension of IDR 2,300,000 and a VOA assistance fee of
// IDR 1,500,000 in five languages, while the catalogue SSOT
// (`bali_zero_official_prices_2026.json`, `single_entry_visas`) prices the
// B1 VOA at 750.000 and its +30-day extension at 850.000, government fee
// included. The C1/C2 "60 days + 4 extensions" bundles (8.5M / 13.9M) were not
// derivable from catalogue rows and were deleted rather than re-invented.
//
// WHAT IT PINS. (1) every language of the e-VOA guide states the catalogue VOA
// and extension prices; (2) no line of the e-VOA guide carries the stale
// 2,300,000 / 13,900,000 figures; (3) no article anywhere pairs
// "Bali Zero" + a VOA extension on one line with 2,300,000.
// The expected numbers come from the JSON, not from this file.
// =============================================================================

import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

const ARTICLES_PATH = path.join(process.cwd(), "src/content/articles");
const CATALOGUE_PATH = path.join(
  process.cwd(),
  "../backend-rag/backend/data/bali_zero_official_prices_2026.json",
);

/** "850.000 IDR" -> 850000 */
function idr(price: string): number {
  return Number(price.replace(/[^0-9]/g, ""));
}

function loadCatalogue() {
  const raw = JSON.parse(fs.readFileSync(CATALOGUE_PATH, "utf8"));
  const visas = raw.services.single_entry_visas;
  return {
    voa: idr(visas["B1 Visa on Arrival (VOA)"].price),
    extension: idr(visas["B1 Visa on Arrival Extension"].price),
  };
}

/** Every digit run, separators stripped, so 2,300,000 / 2.300.000 / "2 300 000" collide. */
function amounts(line: string): number[] {
  const out: number[] = [];
  for (const m of line.matchAll(/\d{1,3}(?:[ .,  ]\d{3})+|\d+/g)) {
    out.push(Number(m[0].replace(/[^0-9]/g, "")));
  }
  return out;
}

function walk(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) return walk(p);
    return e.name.endsWith(".mdx") ? [p] : [];
  });
}

const ALL = walk(ARTICLES_PATH);
const EVOA = ALL.filter((f) =>
  path.basename(f).startsWith("e-voa-electronic-visa-on-arrival-guide"),
);

describe("e-VOA guide Bali Zero prices follow the catalogue", () => {
  const cat = loadCatalogue();

  it("catalogue still prices the VOA at 750k and its extension at 850k", () => {
    expect(cat.voa).toBe(750000);
    expect(cat.extension).toBe(850000);
  });

  it("finds the guide in all five languages", () => {
    expect(EVOA.length).toBe(5);
  });

  it.each(EVOA.map((f) => [path.basename(f), f]))(
    "%s states the catalogue VOA and extension prices and no stale bundle",
    (_name, file) => {
      const lines = fs.readFileSync(file as string, "utf8").split("\n");
      const all = lines.flatMap(amounts);
      expect(all).toContain(cat.voa);
      expect(all).toContain(cat.extension);
      for (const stale of [2300000, 13900000]) {
        const hit = lines.find(
          (l) => amounts(l).includes(stale) && !/3[ .,]?600[ .,]?000/.test(l),
        );
        expect(hit, `stale ${stale} in ${_name}`).toBeUndefined();
      }
    },
  );

  it("no article line pairs Bali Zero + a VOA extension with 2,300,000", () => {
    const offenders: string[] = [];
    for (const file of ALL) {
      fs.readFileSync(file, "utf8")
        .split("\n")
        .forEach((line, i) => {
          if (
            /bali zero/i.test(line) &&
            /(voa|visa on arrival)/i.test(line) &&
            /(extension|extend|proroga|perpanjangan|prolongation|продлен)/i.test(
              line,
            ) &&
            amounts(line).includes(2300000)
          ) {
            offenders.push(`${path.relative(ARTICLES_PATH, file)}:${i + 1}`);
          }
        });
    }
    expect(offenders).toEqual([]);
  });
});
