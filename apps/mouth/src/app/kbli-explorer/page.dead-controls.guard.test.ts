import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The /kbli-explorer sidebar served four controls that looked clickable and
 * did nothing: two "Quick Access" buttons with no handler (Recent Searches,
 * Browse by Sector), and two `cursor-pointer` divs with no handler (each
 * "Official Sources" card and the assistant footer). Measured at 9282d24513.
 *
 * Declared limits: this reads page.tsx only, by regex over JSX opening tags.
 * It does not render, so a handler attached by spread props would read as
 * missing, and controls in ./components are not covered.
 */
const PAGE = readFileSync(join(__dirname, "page.tsx"), "utf8");
const OPEN_TAGS = [...PAGE.matchAll(/<(button|div)\b([^>]*?)>/gs)].map((m) => ({
  tag: m[1],
  attrs: m[2],
}));

describe("/kbli-explorer has no dead controls", () => {
  it("positive control: the scan reaches buttons that do have a handler", () => {
    const handled = OPEN_TAGS.filter(
      (t) => t.tag === "button" && t.attrs.includes("onClick"),
    );
    expect(handled.length).toBeGreaterThan(5);
  });

  it("every <button> has an onClick or is a submit button", () => {
    const dead = OPEN_TAGS.filter(
      (t) =>
        t.tag === "button" &&
        !t.attrs.includes("onClick") &&
        !t.attrs.includes('type="submit"'),
    );
    expect(dead).toEqual([]);
  });

  it("no <div> shows a pointer cursor without an onClick", () => {
    const fake = OPEN_TAGS.filter(
      (t) =>
        t.tag === "div" &&
        t.attrs.includes("cursor-pointer") &&
        !t.attrs.includes("onClick"),
    );
    expect(fake).toEqual([]);
  });

  it("the removed Quick Access labels stay gone", () => {
    expect(PAGE).not.toContain("Recent Searches");
    expect(PAGE).not.toContain("Browse by Sector");
  });
});
