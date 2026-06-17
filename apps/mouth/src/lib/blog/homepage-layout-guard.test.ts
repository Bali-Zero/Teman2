import { describe, expect, it } from "vitest";
import {
  validateHomepageLayout,
  validateHomepageLayoutFromDisk,
} from "./articles";
import homepageLayout from "@/content/homepage-layout.json";

// Slug-drift guard (Antonello 2026-06-11). The homepage curates hero_*/latest_*
// slugs in homepage-layout.json; (marketing)/page.tsx resolves them with a
// silent `.filter(Boolean)`, and Next.js notFound() returns HTTP 200 — so a
// deleted/renamed slug drops silently with no signal. These tests make that
// drift LOUD. The first three are pure (deterministic fixture); the last one
// validates the REAL layout against the REAL on-disk MDX slug index (offline,
// no network/backend) so a future article rename/delete fails CI.

describe("validateHomepageLayout (pure)", () => {
  const known = ["alpha", "beta", "gamma"];

  it("passes when every curated slug resolves to a real article", () => {
    const layout = {
      _comment: "ignored metadata key",
      hero_main: "alpha",
      hero_2: "beta",
      latest_1: "gamma",
    };
    const result = validateHomepageLayout(layout, known);
    expect(result.ok).toBe(true);
    expect(result.missing).toEqual([]);
    expect(result.checked).toBe(3);
  });

  it("flags a drifted (deleted/renamed) slug with its layout key", () => {
    const layout = {
      hero_main: "alpha",
      hero_2: "deleted-or-renamed-slug",
      latest_1: "gamma",
    };
    const result = validateHomepageLayout(layout, known);
    expect(result.ok).toBe(false);
    expect(result.missing).toEqual([
      { key: "hero_2", slug: "deleted-or-renamed-slug" },
    ]);
    expect(result.checked).toBe(3);
  });

  it("ignores `_`-prefixed metadata keys and empty/non-string values", () => {
    const layout = {
      _comment: "not a slug",
      _note: "also not a slug",
      hero_main: "alpha",
      hero_empty: "",
      hero_bad: 42 as unknown as string,
    };
    const result = validateHomepageLayout(layout, known);
    // Only hero_main is a non-empty string slug key → 1 checked, all resolve.
    expect(result.checked).toBe(1);
    expect(result.ok).toBe(true);
  });
});

describe("homepage-layout.json (real, offline)", () => {
  it("every curated slug resolves to a real on-disk article", async () => {
    // Throws (with the drifted keys/slugs) if any curated slug no longer
    // resolves — that throw is the build/test signal Antonello asked for.
    const result = await validateHomepageLayoutFromDisk(
      homepageLayout as Record<string, unknown>,
    );
    expect(result.ok).toBe(true);
    expect(result.missing).toEqual([]);
    // sanity: the real layout curates several slugs, not zero.
    expect(result.checked).toBeGreaterThan(0);
  });
});
