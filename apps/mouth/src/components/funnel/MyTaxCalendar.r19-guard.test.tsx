import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  forbiddenClassToken,
  forbiddenInlineStyle,
  forbiddenSourceColour,
} from "@/test/r19-colour-guard";
import { MyTaxCalendar } from "./MyTaxCalendar";

const root = process.env.MY_TAX_CALENDAR_GUARD_ROOT || process.cwd();
const sourceFile = "src/components/funnel/MyTaxCalendar.tsx";

function expectR19Safe(container: HTMLElement) {
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
}

describe("MyTaxCalendar R19 guard", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the first step and the result with R19-safe styles only", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            obligations: [
              {
                authority: "Directorate General of Taxes",
                frequency: "monthly",
                id: "pph21_payment",
                legal_source: "Cleared source",
                name: "PPh 21 payment",
                reviewed_on: "2026-09-20",
                upcoming_due_dates: [
                  { due_date: "2026-10-15", period_key: "2026-09" },
                  { due_date: "2026-11-15", period_key: "2026-10" },
                ],
              },
            ],
            withheld_count: 2,
          }),
          { headers: { "Content-Type": "application/json" }, status: 200 },
        ),
      ),
    );
    const { container } = render(<MyTaxCalendar />);
    expectR19Safe(container);

    fireEvent.click(screen.getByLabelText("Individual"));
    await screen.findByText("PPh 21 payment");
    expectR19Safe(container);
  });

  it("keeps colour and depth effects out of the source", () => {
    const source = readFileSync(resolve(root, sourceFile), "utf8");
    expect(
      forbiddenSourceColour(source),
      "literal colour or backdrop effect",
    ).toBeNull();
  });

  it("anchors the wizard to the R19 tokens", () => {
    const source = readFileSync(resolve(root, sourceFile), "utf8");
    expect(source).toContain("var(--r19-copper)");
    expect(source).toContain("var(--r19-wash)");
    expect(source).toContain('borderRadius: "8px"');
  });
});
