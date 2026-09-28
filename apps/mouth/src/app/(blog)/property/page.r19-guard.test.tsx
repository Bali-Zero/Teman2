import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import PropertyPage from "./page";

const PALETTE =
  "sky|blue|cyan|teal|emerald|green|lime|amber|orange|red|rose|pink|fuchsia|purple|violet|indigo";

// Matched per class token after stripping variant prefixes (hover:, md:, …),
// so `hover:bg-white/10` is judged as `bg-white/10`.
const FORBIDDEN_UTILITY = [
  /^bg-gradient-/,
  new RegExp(
    `^(bg|text|border|from|via|to|ring|fill|stroke)-(${PALETTE})-\\d+`,
  ),
  /^text-white(\/\d+)?$/,
  /^bg-black(\/\d+)?$/,
  /^bg-white(\/\d+)?$/,
  /^border-white(\/\d+)?$/,
  /^font-(black|extrabold)$/,
];

// The R19 page paints through classes only: an inline style may reference
// var(--…), never a literal colour, a gradient or a backdrop filter. jsdom
// serialises hex to rgb(), so rgb( covers literal hex too.
const FORBIDDEN_IN_STYLE = [
  /gradient/i,
  /backdrop-filter/i,
  /rgba?\(/i,
  /#[0-9a-f]{3,8}\b/i,
  /\b(white|black)\b/i,
];

const pageSource = readFileSync(
  resolve(process.cwd(), "src/app/(blog)/property/page.tsx"),
  "utf8",
);

function forbiddenHits(container: HTMLElement): string[] {
  const hits: string[] = [];
  container.querySelectorAll("[class],[style]").forEach((el) => {
    for (const token of (el.getAttribute("class") ?? "").split(/\s+/)) {
      const utility = token.slice(token.lastIndexOf(":") + 1);
      if (FORBIDDEN_UTILITY.some((re) => re.test(utility))) {
        hits.push(`class <${el.tagName}> ${token}`);
      }
    }
    const style = el.getAttribute("style") ?? "";
    const styleWithoutVars = style.replace(/var\([^)]*\)/g, "");
    for (const re of FORBIDDEN_IN_STYLE) {
      if (re.test(styleWithoutVars))
        hits.push(`style <${el.tagName}> ${style}`);
    }
  });
  return hits;
}

describe("/property — R19 guard", () => {
  it("renders no legacy colour utility (variants included) and no literal colour in inline styles", () => {
    const { container } = render(<PropertyPage />);
    expect(container.querySelectorAll("*").length).toBeGreaterThan(0);
    expect(forbiddenHits(container)).toEqual([]);
  });

  it("keeps literal hex colours in the source inside var() fallbacks only", () => {
    const sourceWithoutVarFallbacks = pageSource.replace(/var\([^)]*\)/g, "");
    expect(sourceWithoutVarFallbacks).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});
