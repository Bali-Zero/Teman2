import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

// The override lets the verification command run this same test against a
// temporary, restored copy without mutating the working tree.
const root = process.env.TAX_CALENDAR_GUARD_ROOT || process.cwd();
const sourceFiles = [
  "src/components/funnel/TaxCalendarBody.tsx",
  "src/app/(tax-calendar)/tax-calendar/layout.tsx",
  "src/app/(tax-calendar)/tax-calendar/page.tsx",
];

describe("TaxCalendarBody R19 anchor", () => {
  it("anchors the calendar to the R19 presentation contract", () => {
    const body = readFileSync(resolve(root, sourceFiles[0]), "utf8");
    const layout = readFileSync(resolve(root, sourceFiles[1]), "utf8");
    const page = readFileSync(resolve(root, sourceFiles[2]), "utf8");

    expect(body).toContain("var(--r19-copper)");
    expect(body).toContain("var(--r19-wash)");
    expect(body).toContain('borderRadius: "8px"');
    expect(layout).toContain("<R19Presentation force>");
    expect(layout).toContain('variant="paper"');
    expect(page).toContain("className={styles.scope}");
  });
});
