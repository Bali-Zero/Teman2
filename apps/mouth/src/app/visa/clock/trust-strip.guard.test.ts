import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, it, expect } from "vitest";

/**
 * /visa/clock trust strip — only figures we can trace.
 *
 * WHY. The strip read "5,021 visas filed since 2019". No system we run can
 * produce that number: lib/trust-figures.ts records that the CRM starts on
 * 2025-12-22. A precise figure reads as a measured one, which made it a
 * stronger unsourced claim than a rounded "5,000+", on an indexed page.
 *
 * WHAT THIS PROVES. The page source no longer carries that figure or its
 * label, and the visa-type count is computed from the options the form
 * actually offers, so it cannot drift from the select.
 *
 * WHAT IT DOES NOT PROVE. It does not render; `page.test.tsx` does. It does
 * not police other pages.
 */

const src = readFileSync(join(__dirname, "page.tsx"), "utf-8");

describe("visa/clock trust strip", () => {
  it("POSITIVE CONTROL: reads the page that renders the strip", () => {
    expect(src).toContain("<AppTrustStrip");
    expect(src).toContain('label: "checkpoints (D-60 → D-1)"');
  });

  it("GUILT: the unsourced 5,021 / 'visas filed' claim is gone", () => {
    expect(src).not.toMatch(/5[,.]?021/);
    expect(src).not.toMatch(/visas filed/i);
  });

  it("the visa-type count is derived from VISA_OPTIONS, not typed in", () => {
    expect(src).toContain("value: String(VISA_OPTIONS.length)");
  });
});
