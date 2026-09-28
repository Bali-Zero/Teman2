import { describe, expect, it } from "vitest";

import { metadata } from "./layout";

describe("Property Check metadata", () => {
  it("restates the share-preview fields the root openGraph would otherwise lose", () => {
    const og = metadata.openGraph as Record<string, unknown>;
    expect(og.type).toBe("website");
    expect(og.url).toBe("https://balizero.com/property/eligibility");
    expect(og.siteName).toBe("Bali Zero");
    expect(og.images).toEqual([
      expect.objectContaining({
        url: "https://balizero.com/static/og-image.jpg",
      }),
    ]);
  });
});
