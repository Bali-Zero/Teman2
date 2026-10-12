import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The process detail "Expiry Date" countdown stopped at months: a document
 * valid ~9 more years rendered "111mo left" in the workspace. Client cards
 * (PassportCard, VisaCard, ImmigrationTab, FamilyTab) already use
 * `formatLongSpan` ("9y 1mo"); this page still divided by 30 and stopped.
 *
 * Declared limits: this reads source text; `formatLongSpan` itself is covered
 * by lib/utils/format-date tests. Age labels ("mo ago") are out of scope.
 */
const text = readFileSync(join(__dirname, "page.tsx"), "utf8");

describe("process detail expiry countdown uses years + months past a year", () => {
  it('positive control: page still renders a "d left" countdown', () => {
    expect(text).toMatch(/d left`/);
  });

  it("formats long spans with formatLongSpan", () => {
    expect(text).toMatch(/\$\{formatLongSpan\(daysLeft\)\} left`/);
  });

  it('has no months-only "/ 30)}mo left" shape', () => {
    expect(text).not.toMatch(/\/ 30\)\}mo left/);
  });
});
