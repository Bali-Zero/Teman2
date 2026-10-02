import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import {
  forbiddenCssModule,
  forbiddenRenderedColour,
  loadR19ColourGuard,
} from "@/test/r19-colour-guard";
import { forbiddenSourceColour } from "@/test/r19-colour-source";
import { TaxCalendarBody } from "./TaxCalendarBody";

vi.mock("@/lib/analytics", () => ({
  trackTaxDashboardViewed: vi.fn(),
}));

// The override lets the verification command run this same test against a
// temporary, restored copy without mutating the working tree.
const root = process.env.TAX_CALENDAR_GUARD_ROOT || process.cwd();
const sourceFiles = [
  "src/components/funnel/TaxCalendarBody.tsx",
  "src/app/(tax-calendar)/tax-calendar/layout.tsx",
  "src/app/(tax-calendar)/tax-calendar/page.tsx",
];
const cssModule =
  "src/app/(tax-calendar)/tax-calendar/r19-funnel-frame.module.css";

const deadlines = [
  {
    id: "pph25",
    kind: "PPh" as const,
    title: "PPh 25",
    date: "2026-05-15T00:00:00Z",
    description: "Monthly.",
  },
  {
    id: "ppn",
    kind: "PPN" as const,
    title: "PPN",
    date: "2026-05-31T00:00:00Z",
    description: "SPT Masa.",
  },
  {
    id: "pb1",
    kind: "PB1" as const,
    title: "PB1",
    date: "2026-05-10T00:00:00Z",
    regency: "Badung",
    description: "Hotel tax.",
  },
];

function report(findings: { line: number; position: string; text: string }[]) {
  return findings.map((f) => `${f.line} ${f.position} ${f.text}`);
}

describe("TaxCalendarBody R19 anchor", () => {
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

describe("TaxCalendarBody R19 colour", () => {
  beforeAll(async () => {
    await loadR19ColourGuard();
  });

  it("renders no literal colour in any tab or regency state", () => {
    const { container } = render(
      <TaxCalendarBody deadlines={deadlines} regencies={["Badung"]} />,
    );
    const seen = report(forbiddenRenderedColour(container));
    for (const tab of ["PPh", "PPN", "LKPM", "PB1", "ALL"]) {
      fireEvent.click(screen.getByRole("button", { name: tab }));
      seen.push(...report(forbiddenRenderedColour(container)));
    }
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "Badung" },
    });
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

  it("decides no colour by a literal in its route-scoped css module", () => {
    const css = readFileSync(resolve(root, cssModule), "utf8");
    expect(report(forbiddenCssModule(css))).toEqual([]);
  });
});
