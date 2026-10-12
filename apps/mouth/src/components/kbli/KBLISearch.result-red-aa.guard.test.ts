import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The /kbli search dropdown (bg #1c1c1f at 95%) drew two foregrounds in
 * #dc2626: the KBLI code inside each result badge (text-xs bold) and the
 * chevron of the active row. WCAG 2.x contrast, computed against the badge's
 * own red tint over the row (idle / hover / active) and the 5% page bleed of
 * both /kbli themes (#141416, #f4f1ea):
 *   code text  #dc2626: 2.47–3.31  (AA normal text needs 4.5)  → #fca5a5: 6.28–8.43
 *   chevron    #dc2626: 2.58–2.99  (non-text needs 3.0)        → #fca5a5: 6.58–7.62
 * The badge tint and border stay #dc2626 (decorative), and the search input's
 * focus ring is a separate decision (Todoist 6hWhwPgP3qmchHmc).
 *
 * Declared limits: this reads source text; the numbers above come from the
 * hex values in this file, not from a rendered page.
 */
const SRC = readFileSync(join(__dirname, "KBLISearch.tsx"), "utf8");

describe("/kbli search results: red foregrounds meet AA on the dark dropdown", () => {
  it("positive control: the dropdown, the badge tint and the focus ring are still there", () => {
    expect(SRC).toContain("bg-[#1c1c1f]/95");
    expect(SRC).toContain("bg-[#dc2626]/10");
    expect(SRC).toContain("focus:ring-[#dc2626]");
  });

  it("the KBLI code in the result badge uses #fca5a5, not #dc2626", () => {
    expect(SRC).toContain(
      "font-bold text-[#fca5a5] border border-[#dc2626]/20 text-xs",
    );
  });

  it("the active-row chevron uses #fca5a5", () => {
    expect(SRC).toContain(
      'index === activeIndex && "text-[#fca5a5] animate-pulse"',
    );
  });

  it("no foreground text in the file is #dc2626 any more", () => {
    expect(SRC.match(/(?<![a-z:-])text-\[#dc2626\]/g)).toBeNull();
  });
});
