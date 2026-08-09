import { describe, expect, it } from "vitest";

import PortalMetadataLayout, { metadata } from "./layout";

describe("portal metadata boundary", () => {
  it("keeps every portal route out of search indexes and marketing canonicals", () => {
    expect(metadata.title).toEqual({
      default: "Client Portal",
      template: "%s | Bali Zero",
    });
    expect(metadata.robots).toEqual({ index: false, follow: false });
    expect(metadata.alternates).toEqual({ canonical: null });
    expect(metadata.openGraph).toBeNull();
    expect(metadata.twitter).toBeNull();
  });

  it("renders the nested portal route unchanged", () => {
    expect(PortalMetadataLayout({ children: "portal child" })).toBe(
      "portal child",
    );
  });
});
