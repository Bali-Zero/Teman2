import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TaxCalendarBody } from "./TaxCalendarBody";

// The override lets the verification command run this same guard against a
// temporary, restored HEAD copy without mutating the working tree.
const root = process.env.TAX_CALENDAR_GUARD_ROOT || process.cwd();
const sourceFiles = [
  "src/components/funnel/TaxCalendarBody.tsx",
  "src/app/(tax-calendar)/tax-calendar/layout.tsx",
  "src/app/(tax-calendar)/tax-calendar/page.tsx",
];

const forbiddenClass = (token: string) => {
  const base = token.slice(token.lastIndexOf(":") + 1).replace(/^!|!$/g, "");
  return (
    /^(bg-gradient|bg-linear)-/.test(base) ||
    /^(bg|text|border|from|via|to|ring|fill|stroke)-(slate|gray|zinc|neutral|stone|sky|blue|cyan|teal|emerald|green|lime|yellow|amber|orange|red|rose|pink|fuchsia|purple|violet|indigo)-\d+(\/\d+)?$/.test(
      base,
    ) ||
    /^(text|bg|border)-white/.test(base) ||
    /^bg-black/.test(base) ||
    /^(font-black|font-extrabold)$/.test(base) ||
    /\[[^\]]*(#|rgb\(|rgba\(|hsl\(|hsla\(|gradient|white|black)[^\]]*\]/i.test(
      base,
    )
  );
};

describe("TaxCalendarBody R19 guard", () => {
  afterEach(() => vi.useRealTimers());

  it("uses only R19-safe rendered classes and inline styles", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-29T00:00:00.000Z"));
    const { container } = render(
      <TaxCalendarBody
        deadlines={[
          {
            date: "2026-10-15T00:00:00.000Z",
            description: "Monthly tax payment.",
            id: "pph-25",
            kind: "PPh",
            title: "PPh 25 monthly",
          },
        ]}
        regencies={["Badung"]}
      />,
    );

    for (const element of container.querySelectorAll("*")) {
      const classes = (element.getAttribute("class") ?? "").split(/\s+/);
      for (const token of classes.filter(Boolean)) {
        expect(forbiddenClass(token), `forbidden class: ${token}`).toBe(false);
      }

      const style = (element.getAttribute("style") ?? "").replace(
        /var\([^)]*\)/g,
        "",
      );
      expect(style, `forbidden inline style: ${style}`).not.toMatch(
        /gradient|backdrop-filter|rgb\(|rgba\(|#[0-9a-f]{3,8}\b|(?<![\w-])(white|black)(?![\w-])/i,
      );
    }
  });

  it("keeps literal colours inside CSS variable fallbacks only", () => {
    for (const file of sourceFiles) {
      const source = readFileSync(resolve(root, file), "utf8").replace(
        /var\([^)]*\)/g,
        "",
      );
      expect(source, `literal colour in ${file}`).not.toMatch(
        /#[0-9a-f]{3,8}\b/i,
      );
      // jsdom drops the -webkit- prefixed property, so the render scan cannot see it.
      expect(source, `backdrop filter in ${file}`).not.toMatch(
        /backdrop-?filter/i,
      );
    }
  });

  it("anchors the calendar to the R19 presentation contract", () => {
    const body = readFileSync(resolve(root, sourceFiles[0]), "utf8");
    const layout = readFileSync(resolve(root, sourceFiles[1]), "utf8");
    const page = readFileSync(resolve(root, sourceFiles[2]), "utf8");

    expect(body).toContain("var(--r19-copper)");
    expect(body).toContain("var(--r19-wash)");
    expect(body).toContain('borderRadius: "8px"');
    expect(layout).toContain("<R19Presentation force>");
    expect(layout).toContain('variant="paper"');
    expect(page).toContain("className={styles.scope}");
  });
});
