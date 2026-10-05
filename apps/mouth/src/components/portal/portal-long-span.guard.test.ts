import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Portal countdown chips stopped at months: a passport valid ~9 more years
 * rendered "111mo left" on my.balizero.com (reported by Pak Adit). The
 * workspace already moved to `formatLongSpan` ("9y 3mo"); the three portal
 * call sites below still divided by 30 and stopped there.
 *
 * Declared limits: this reads source text; `formatLongSpan` itself is covered
 * by lib/utils/format-date.test.ts.
 */
const SRC = join(__dirname, "..", "..");
const FILES = [
  "app/portal/(authenticated)/profile/page.tsx",
  "app/portal/(authenticated)/visa/page.tsx",
  "components/portal/CountdownChip.tsx",
];

describe("portal countdown chips use years + months past a year", () => {
  for (const rel of FILES) {
    const text = readFileSync(join(SRC, rel), "utf8");

    it(`positive control: ${rel} still renders a "left" countdown`, () => {
      expect(text).toMatch(/d left`/);
    });

    it(`${rel} formats long spans with formatLongSpan`, () => {
      expect(text).toMatch(/\$\{formatLongSpan\([^)]*\)\} left`/);
    });

    it(`${rel} has no months-only "/ 30)}mo left" shape`, () => {
      expect(text).not.toMatch(/\/ 30\)\}mo left/);
    });
  }
});
