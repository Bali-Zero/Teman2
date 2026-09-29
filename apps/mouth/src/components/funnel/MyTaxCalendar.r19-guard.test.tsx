import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const root = process.env.MY_TAX_CALENDAR_GUARD_ROOT || process.cwd();
const component = "src/components/funnel/MyTaxCalendar.tsx";
const page = "src/app/(tax-calendar)/tax-calendar/page.tsx";

describe("MyTaxCalendar R19 anchor", () => {
  it("anchors the wizard to the R19 tokens and mounts it on the page", () => {
    const source = readFileSync(resolve(root, component), "utf8");
    const pageSource = readFileSync(resolve(root, page), "utf8");

    expect(source).toContain("var(--r19-copper)");
    expect(source).toContain("var(--r19-wash)");
    expect(source).toContain('borderRadius: "8px"');
    expect(pageSource).toContain("<MyTaxCalendar />");
  });
});
