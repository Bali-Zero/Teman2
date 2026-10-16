import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

describe("/tax-calendar canonical points at the tax subdomain", () => {
  const layout = readFileSync(
    join(process.cwd(), "src/app/(tax-calendar)/tax-calendar/layout.tsx"),
    "utf8",
  );

  it("declares alternates.canonical https://tax.balizero.com/", () => {
    expect(layout).toMatch(/canonical:\s*"https:\/\/tax\.balizero\.com\/"/);
  });

  it("does not point the canonical at the root domain", () => {
    expect(layout).not.toMatch(/canonical:\s*"https:\/\/balizero\.com\/?"/);
  });

  it("keeps its title (positive control)", () => {
    expect(layout).toMatch(/title:\s*"Tax Compliance Calendar"/);
  });
});
