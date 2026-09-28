import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { metadata } from "./layout";

// Next.js merges `openGraph` shallowly, so the route must restate every key
// the root layout sets. The root key sets are read from the root layout's
// source (its module pulls next/font, which vitest cannot load).
function rootOpenGraphKeys(): { og: string[]; image: string[] } {
  const src = readFileSync(join(__dirname, "../../layout.tsx"), "utf8");
  const block = src.slice(src.indexOf("  openGraph: {"));
  const og = block.slice(0, block.indexOf("\n  },"));
  const image = og.slice(og.indexOf("images: ["));
  const keys = (text: string, indent: number) =>
    [...text.matchAll(new RegExp(`^ {${indent}}(\\w+):`, "gm"))].map(
      (m) => m[1],
    );
  return { og: keys(og, 4), image: keys(image, 8) };
}

describe("Property Check metadata", () => {
  it("restates every openGraph and image key the root layout sets", () => {
    const root = rootOpenGraphKeys();
    expect(root.og).toContain("images");
    expect(root.image).toContain("url");

    const og = metadata.openGraph as Record<string, unknown>;
    const [image] = og.images as Record<string, unknown>[];
    expect(Object.keys(og)).toEqual(expect.arrayContaining(root.og));
    expect(Object.keys(image)).toEqual(expect.arrayContaining(root.image));
    expect(og.url).toBe("https://balizero.com/property/eligibility");
    expect(image.url).toBe("https://balizero.com/static/og-image.jpg");
  });
});
