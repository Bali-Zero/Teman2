import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  forbiddenClassToken,
  forbiddenInlineStyle,
  forbiddenSourceColour,
} from "@/test/r19-colour-guard";
import { MyTaxCalendar } from "./MyTaxCalendar";

const root = process.env.MY_TAX_CALENDAR_GUARD_ROOT || process.cwd();
const component = "src/components/funnel/MyTaxCalendar.tsx";
const page = "src/app/(tax-calendar)/tax-calendar/page.tsx";
const layout = "src/app/(tax-calendar)/tax-calendar/layout.tsx";

describe("MyTaxCalendar R19 guard", () => {
  it("uses only R19-safe rendered classes and inline styles", () => {
    const { container } = render(<MyTaxCalendar />);

    for (const element of container.querySelectorAll("*")) {
      const classes = (element.getAttribute("class") ?? "").split(/\s+/);
      for (const token of classes.filter(Boolean)) {
        expect(forbiddenClassToken(token), `forbidden class: ${token}`).toBe(
          false,
        );
      }

      const style = element.getAttribute("style") ?? "";
      expect(
        forbiddenInlineStyle(style),
        `forbidden inline style: ${style}`,
      ).toBeNull();
    }
  });

  it("keeps colour and depth effects out of the source files", () => {
    for (const file of [component, page, layout]) {
      const source = readFileSync(resolve(root, file), "utf8");
      expect(
        forbiddenSourceColour(source),
        `literal colour or backdrop effect in ${file}`,
      ).toBeNull();
    }
  });

  it("anchors the wizard to the R19 tokens and mounts it on the page", () => {
    const source = readFileSync(resolve(root, component), "utf8");
    const pageSource = readFileSync(resolve(root, page), "utf8");

    expect(source).toContain("var(--r19-copper)");
    expect(source).toContain("var(--r19-wash)");
    expect(source).toContain('borderRadius: "8px"');
    expect(pageSource).toContain("<MyTaxCalendar />");
  });
});
