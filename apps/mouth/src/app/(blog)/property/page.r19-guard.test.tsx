import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import PropertyPage from "./page";

const FORBIDDEN_CLASS =
  /(^|[\s"'`])(bg-gradient-|text-white\b|bg-black\b|border-white\/|bg-white\/|font-black\b|font-extrabold\b|(sky|blue|cyan|teal|emerald|green|lime|amber|orange|red|rose|pink|fuchsia|purple|violet|indigo)-\d{2,3})/;

const pageSource = readFileSync(
  resolve(process.cwd(), "src/app/(blog)/property/page.tsx"),
  "utf8",
);

describe("/property — R19 guard", () => {
  it("renders with no forbidden legacy color utility", () => {
    const { container } = render(<PropertyPage />);
    const elements = container.querySelectorAll("*");

    expect(elements.length).toBeGreaterThan(0);

    for (const element of Array.from(elements)) {
      const className = element.getAttribute("class") ?? "";
      expect(
        className,
        `forbidden class on <${element.tagName}>: "${className}"`,
      ).not.toMatch(FORBIDDEN_CLASS);
    }
  });

  it("keeps literal hex colors inside var() fallbacks only", () => {
    const sourceWithoutVarFallbacks = pageSource.replace(/var\([^)]*\)/g, "");

    expect(sourceWithoutVarFallbacks).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});
