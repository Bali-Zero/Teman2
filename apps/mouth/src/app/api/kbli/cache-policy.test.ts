import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const PUBLIC_KBLI_ROUTES = [
  "src/app/api/kbli/gold/route.ts",
  "src/app/api/kbli/gold/[code]/route.ts",
  "src/app/api/og/kbli/[code]/route.tsx",
];

describe("KBLI disclosure route cache policy", () => {
  it.each(PUBLIC_KBLI_ROUTES)("keeps %s non-cacheable", (route) => {
    const source = readFileSync(join(process.cwd(), route), "utf8");

    expect(source).toContain('"Cache-Control": "no-store"');
    expect(source).not.toMatch(/s-maxage|stale-while-revalidate|immutable/);
  });
});
