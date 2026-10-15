import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// Zero's ruling 2026-10-15 (Q7, standing rule R1 2026-07-17): a visa price is
// ONE all-inclusive amount. Pages that show or govern a visa price must not
// describe it as a Bali Zero fee with government fees billed apart.
const MATCH_RESULT = join(__dirname, "visa", "match", "[hash]", "page.tsx");
const BLOG_TERMS = join(__dirname, "(blog)", "terms", "page.tsx");

const flat = (file: string) => readFileSync(file, "utf8").replace(/\s+/g, " ");

const FEE_SPLIT = [
  /government fees (are )?billed at cost/i,
  /government fees (are )?passed through at cost/i,
  /refund the service fee/i,
  /Bali Zero fee\./,
];

describe("visa price surfaces never split the price", () => {
  it.each([
    ["/visa/match result", MATCH_RESULT],
    ["/terms", BLOG_TERMS],
  ])("%s carries no fee-split sentence", (_label, file) => {
    const text = flat(file);
    for (const pattern of FEE_SPLIT) expect(text).not.toMatch(pattern);
  });

  it("the /visa/match result labels its price all-inclusive", () => {
    expect(flat(MATCH_RESULT)).toMatch(
      /All-inclusive price: government fees and Bali Zero service included\./,
    );
  });

  it("/terms says visa prices are all-inclusive and keeps the refund carve-out", () => {
    const text = flat(BLOG_TERMS);
    expect(text).toMatch(
      /Visa and stay-permit prices are all-inclusive: government fees and the Bali Zero service are included/,
    );
    expect(text).toMatch(/except government fees already paid on your behalf/);
  });
});
