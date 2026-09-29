import { describe, expect, it } from "vitest";

import nextConfig from "../../next.config";

describe("zoning redirect", () => {
  it("permanently redirects the former zoning pitch to property eligibility", async () => {
    expect(nextConfig.redirects).toBeDefined();

    const redirects = await nextConfig.redirects!();

    expect(redirects).toContainEqual({
      source: "/zoning",
      destination: "/property/eligibility",
      permanent: true,
    });
  });
});
