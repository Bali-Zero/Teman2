import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The "Official Sources" sidebar of /kbli-explorer was fed by a constant named
 * MOCK_SOURCES that carried enacted dates contradicting the primary sources
 * ("Jan 2025" for PP 28/2025, enacted 5 Jun 2025; "Feb 2025" for Peraturan BPS
 * 7/2025, enacted 17 Dec 2025). SourceCard never rendered the date, so the
 * wrong value was latent: one `{source.date}` away from a public legal claim.
 *
 * Declared limits: this reads the source, it does not render the page.
 */
const PAGE = readFileSync(join(__dirname, "page.tsx"), "utf8");

describe("/kbli-explorer official sources", () => {
  it("positive control: the sidebar section this guard anchors on exists", () => {
    expect(PAGE).toContain("Official Sources");
    expect(PAGE).toContain("OFFICIAL_SOURCES.map(");
  });

  it("no longer names the citation list as mock data", () => {
    expect(PAGE).not.toContain("MOCK_SOURCES");
  });

  it("stores no enacted date for a source, since none is rendered", () => {
    const start = PAGE.indexOf("const OFFICIAL_SOURCES = [");
    const end = PAGE.indexOf("];", start);
    expect(start).toBeGreaterThan(-1);
    expect(PAGE.slice(start, end)).not.toMatch(/\bdate:/);
  });
});
