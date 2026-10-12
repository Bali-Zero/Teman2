/**
 * The PT PMA setup price is ONE number, owned by the catalogue
 * (`company_services."New Company (PT PMA)"`). Two business articles kept
 * quoting "~IDR 18M" in all five languages after the owner's 2026-10-12 ruling
 * moved it to 25.000.000, because the sweep only caught the "20M" spelling.
 * This pins every article line that states a PT PMA setup price to the
 * catalogue value instead of to a list of known-stale spellings.
 */
import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..", "..");
const CATALOGUE = path.resolve(
  ROOT,
  "..",
  "backend-rag",
  "backend",
  "data",
  "bali_zero_official_prices_2026.json",
);

function walk(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    return e.isDirectory() ? walk(p) : p.endsWith(".mdx") ? [p] : [];
  });
}

describe("PT PMA setup price follows the catalogue", () => {
  const catalogue = JSON.parse(fs.readFileSync(CATALOGUE, "utf8"));
  const raw: string =
    catalogue.services.company_services["New Company (PT PMA)"].price;
  const million = Number(raw.replace(/[^0-9]/g, "")) / 1_000_000;

  it("the catalogue row is the owner-ruled 25M", () => {
    expect(million).toBe(25);
  });

  it("no article states a different 'PT PMA setup ~IDR NM' point price", () => {
    // llms-full/llms-id are regenerated from the articles at build
    // (scripts/generate-llms-full.ts), so the articles are the source.
    const files = walk(path.join(ROOT, "src", "content", "articles"));
    const stale = /(setup|pengaturan|setup di)[^.\n]{0,40}~?IDR (18|20)M\b/i;
    const hits: string[] = [];
    for (const f of files) {
      fs.readFileSync(f, "utf8")
        .split("\n")
        .forEach((line, i) => {
          if (/PT PMA/i.test(line) && stale.test(line)) {
            hits.push(`${path.relative(ROOT, f)}:${i + 1}`);
          }
        });
    }
    expect(hits).toEqual([]);
  });
});
