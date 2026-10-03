import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import {
  forbiddenRenderedColour,
  loadR19ColourGuard,
} from "@/test/r19-colour-guard";
import { forbiddenSourceColour } from "@/test/r19-colour-source";
import { MyTaxCalendar } from "./MyTaxCalendar";

const root = process.env.MY_TAX_CALENDAR_GUARD_ROOT || process.cwd();
const component = "src/components/funnel/MyTaxCalendar.tsx";
const page = "src/app/(tax-calendar)/tax-calendar/page.tsx";
// Every file of the route that renders MyTaxCalendar (the page; the layout
// only wraps it).
const sourceFiles = [component, page];

const sampleResponse = {
  obligations: [
    {
      authority: "Directorate General of Taxes",
      frequency: "Monthly",
      id: "monthly-pph",
      name: "Monthly filing",
      reviewed_on: "2026-09-20",
      upcoming_due_dates: [{ due_date: "2026-10-01", period_key: "2026-09" }],
    },
  ],
  withheld_count: 3,
};

function report(findings: { line: number; position: string; text: string }[]) {
  return findings.map((f) => `${f.line} ${f.position} ${f.text}`);
}

describe("MyTaxCalendar R19 anchor", () => {
  it("anchors the wizard to the R19 tokens and mounts it on the page", () => {
    const source = readFileSync(resolve(root, component), "utf8");
    const pageSource = readFileSync(resolve(root, page), "utf8");

    expect(source).toContain("var(--r19-copper)");
    expect(source).toContain("var(--r19-wash)");
    expect(source).toContain('borderRadius: "8px"');
    expect(pageSource).toContain("<MyTaxCalendar />");
  });
});

describe("MyTaxCalendar R19 colour", () => {
  beforeAll(async () => {
    await loadR19ColourGuard();
  });

  afterEach(() => vi.unstubAllGlobals());

  it("renders no literal colour from the first question to the result", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(sampleResponse), {
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    const { container } = render(<MyTaxCalendar />);
    const seen = report(forbiddenRenderedColour(container));
    fireEvent.click(screen.getByLabelText("Individual"));
    await waitFor(() =>
      expect(screen.getByText("Monthly filing")).toBeTruthy(),
    );
    seen.push(...report(forbiddenRenderedColour(container)));
    expect(seen).toEqual([]);
  });

  it("decides no colour by a literal in its source files", () => {
    const seen = sourceFiles.flatMap((file) =>
      report(
        forbiddenSourceColour(file, readFileSync(resolve(root, file), "utf8")),
      ).map((finding) => `${file}:${finding}`),
    );
    expect(seen).toEqual([]);
  });
});
