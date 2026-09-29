import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MyTaxCalendar } from "./MyTaxCalendar";

const root = process.env.MY_TAX_CALENDAR_GUARD_ROOT || process.cwd();
const sourceFile = "src/components/funnel/MyTaxCalendar.tsx";

const forbiddenClass = (token: string) => {
  const base = token.slice(token.lastIndexOf(":") + 1).replace(/^!|!$/g, "");
  return (
    /^!?(bg-gradient|bg-linear)-/.test(base) ||
    /^!?(bg|text|border|from|via|to|ring|fill|stroke)-(slate|gray|zinc|neutral|stone|sky|blue|cyan|teal|emerald|green|lime|yellow|amber|orange|red|rose|pink|fuchsia|purple|violet|indigo)-\d+(\/\d+)?$/.test(
      base,
    ) ||
    /^!?(text|bg|border)-white/.test(base) ||
    /^!?bg-black/.test(base) ||
    /^!?opacity-\d+/.test(base) ||
    /^!?(font-black|font-extrabold)$/.test(base) ||
    /\[[^\]]*(#|rgb\(|rgba\(|hsl\(|hsla\(|gradient|white|black|opacity)[^\]]*\]/i.test(
      base,
    )
  );
};

describe("MyTaxCalendar R19 guard", () => {
  afterEach(() => vi.useRealTimers());

  it("uses only R19-safe rendered classes and inline styles", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-29T00:00:00.000Z"));
    const { container } = render(<MyTaxCalendar />);

    for (const element of container.querySelectorAll("*")) {
      for (const token of (element.getAttribute("class") ?? "")
        .split(/\s+/)
        .filter(Boolean)) {
        expect(forbiddenClass(token), `forbidden class: ${token}`).toBe(false);
      }
      const style = (element.getAttribute("style") ?? "").replace(
        /var\([^)]*\)/g,
        "",
      );
      expect(style, `forbidden inline style: ${style}`).not.toMatch(
        /gradient|backdrop-?filter|rgb\(|rgba\(|#[0-9a-f]{3,8}\b|(?<![\w-])(white|black)(?![\w-])|!important|opacity\s*:/i,
      );
    }
  });

  it("keeps literal colours and filters out of source", () => {
    const source = readFileSync(resolve(root, sourceFile), "utf8").replace(
      /var\([^)]*\)/g,
      "",
    );
    expect(source, "literal colour").not.toMatch(/#[0-9a-f]{3,8}\b/i);
    expect(source, "backdrop filter").not.toMatch(/backdrop-?filter/i);
    expect(source, "important rule").not.toMatch(/!important/i);
  });

  it("anchors the wizard to the R19 tokens", () => {
    const source = readFileSync(resolve(root, sourceFile), "utf8");
    expect(source).toContain("var(--r19-copper)");
    expect(source).toContain("var(--r19-wash)");
    expect(source).toContain('borderRadius: "8px"');
  });
});
