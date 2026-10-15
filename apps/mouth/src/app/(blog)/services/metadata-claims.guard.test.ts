import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

describe("/services layout metadata makes no pricing claim", () => {
  const layout = readFileSync(
    join(process.cwd(), "src/app/(blog)/services/layout.tsx"),
    "utf8",
  );

  it("states no IDR price", () => {
    expect(layout).not.toMatch(/IDR\s*\d/);
  });

  it("does not promise transparent pricing", () => {
    expect(layout).not.toMatch(/transparent pricing/i);
  });

  it("keeps its self canonical (positive control)", () => {
    expect(layout).toMatch(/canonical:\s*"https:\/\/balizero\.com\/services"/);
  });
});
