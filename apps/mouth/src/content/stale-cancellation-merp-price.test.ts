// =============================================================================
// STALE PRICES — the KITAS cancellation bundle and the standalone MERP are not
// quoted in articles.
//
// WHY THIS EXISTS. Owner ruling 2026-10-12 (Zero): the articles stated a Bali
// Zero "IDR 3.5M" KITAS cancellation bundle (RPTKA + IMTA + Wajib Lapor) and a
// standalone MERP price of IDR 4,000,000 (4-5M for 1-2 years), in five
// languages. Neither is a catalogue row of its own: the catalogue
// (`bali_zero_official_prices_2026.json`, `other_process`) prices EPO at 700.000
// and the single ERP at 800.000, and bundles the MERP into the KITAP (UU
// 63/2024, no separate fee). Zero ruled the two figures deleted, not replaced.
//
// WHAT IT PINS. (1) the catalogue rows the articles still rely on (EPO, ERP)
// are unchanged; (2) no article line pairs MERP with a 4M-family amount;
// (3) no article line pairs a cancellation context (RPTKA/IMTA/Wajib Lapor/
// Bali Zero + cancel) with a 3.5M-family amount.
// =============================================================================

import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

const ARTICLES_PATH = path.join(process.cwd(), "src/content/articles");
const CATALOGUE_PATH = path.join(
  process.cwd(),
  "../backend-rag/backend/data/bali_zero_official_prices_2026.json",
);

function walk(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) return walk(p);
    return e.name.endsWith(".mdx") ? [p] : [];
  });
}

/** 4,000,000 / 4.000.000 / "4 000 000" / 4M / 4-5M / 4-5 million / 4 млн ... */
const MERP_PRICE =
  /(?<![\d.,])(?:4[.,   ]000[.,   ]000|4(?:[–-]5)? ?(?:M\b|million|millions|milioni|milion|juta|jt|млн|миллион))/i;

/** 3,500,000 / 3.500.000 / "3 500 000" / 3.5M / 3,5 juta / 3,5 млн ... */
const CANCELLATION_PRICE =
  /(?<![\d.,])(?:3[.,   ]500[.,   ]000|3[.,]5 ?(?:M\b|million|millions|milioni|milion|juta|jt|млн))/i;
const CANCELLATION_CONTEXT =
  /(cancel|annul|pembatal|cancell|аннул|отмен|annull)/i;
const BUNDLE_CONTEXT = /(RPTKA|IMTA|Wajib Lapor|Bali Zero|KITAS)/i;

const ALL = walk(ARTICLES_PATH);

describe("articles do not quote the cancellation bundle or the standalone MERP", () => {
  it("catalogue still carries the EPO and ERP rows the articles rely on", () => {
    const raw = JSON.parse(fs.readFileSync(CATALOGUE_PATH, "utf8"));
    const proc = raw.services.other_process;
    const digits = (s: string) => Number(s.replace(/[^0-9]/g, ""));
    expect(digits(proc["EPO (Exit Permit Only)"].price)).toBe(700000);
    expect(digits(proc["ERP (Exit Re-entry Permit)"].price)).toBe(800000);
  });

  it("scans the corpus", () => {
    expect(ALL.length).toBeGreaterThan(100);
  });

  it("no line pairs MERP with a 4M-family amount", () => {
    const offenders: string[] = [];
    for (const file of ALL) {
      fs.readFileSync(file, "utf8")
        .split("\n")
        .forEach((line, i) => {
          if (/MERP/.test(line) && MERP_PRICE.test(line)) {
            offenders.push(`${path.relative(ARTICLES_PATH, file)}:${i + 1}`);
          }
        });
    }
    expect(offenders).toEqual([]);
  });

  it("no line pairs a KITAS cancellation context with a 3.5M-family amount", () => {
    const offenders: string[] = [];
    for (const file of ALL) {
      fs.readFileSync(file, "utf8")
        .split("\n")
        .forEach((line, i) => {
          if (
            CANCELLATION_PRICE.test(line) &&
            CANCELLATION_CONTEXT.test(line) &&
            BUNDLE_CONTEXT.test(line)
          ) {
            offenders.push(`${path.relative(ARTICLES_PATH, file)}:${i + 1}`);
          }
        });
    }
    expect(offenders).toEqual([]);
  });
});
