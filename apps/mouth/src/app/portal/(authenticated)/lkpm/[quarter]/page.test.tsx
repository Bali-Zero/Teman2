import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const { mockGetLKPMDraft } = vi.hoisted(() => ({
  mockGetLKPMDraft: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ quarter: "Q2-2026" }),
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    portal: {
      getLKPMDraft: mockGetLKPMDraft,
      approveLKPMDraft: vi.fn(),
    },
  },
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

import LKPMQuarterError from "./error";

describe("LKPM quarter page (day edition)", () => {
  it("renders the error state with --state-danger tokens", () => {
    const { container } = render(
      <LKPMQuarterError error={new Error("boom")} reset={() => {}} />,
    );
    const html = container.innerHTML;
    expect(html).toContain("var(--state-danger)");
    expect(html).not.toContain("--neon-rose");
  });

  it("keeps the page free of dark-era raw hexes (drain guard)", () => {
    const raw = readFileSync(join(__dirname, "page.tsx"), "utf8");
    // Comments may document what was drained; judge only code lines.
    const src = raw
      .split("\n")
      .filter(
        (l) =>
          !l.trimStart().startsWith("*") && !l.trimStart().startsWith("//"),
      )
      .join("\n");
    for (const forbidden of [
      "#f87171",
      "#fbbf24",
      "#34d399",
      "rgba(244,63,94",
      "rgba(245,158,11",
      "--neon-rose",
    ]) {
      expect(src.includes(forbidden), `found ${forbidden}`).toBe(false);
    }
  });
});
