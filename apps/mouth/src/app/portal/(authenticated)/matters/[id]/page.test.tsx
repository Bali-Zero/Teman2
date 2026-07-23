import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { mockUseParams, mockUsePortalMatter } = vi.hoisted(() => ({
  mockUseParams: vi.fn(),
  mockUsePortalMatter: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: mockUseParams,
}));

vi.mock("@/hooks", () => ({
  usePortalMatter: mockUsePortalMatter,
}));

vi.mock("@/components/portal", () => ({
  PortalBackButton: ({ label }: { label?: string }) => (
    <a href="/portal/matters">{label ?? "Back"}</a>
  ),
}));

import PortalMatterDetailPage from "./page";

describe("PortalMatterDetailPage", () => {
  it("renders approved client-safe intelligence without raw source details", () => {
    mockUseParams.mockReturnValue({ id: "9" });
    mockUsePortalMatter.mockReturnValue({
      data: {
        id: 9,
        title: "Company Setup",
        type: "company",
        progress: 60,
        pending_docs: ["Company registry"],
        next_deadline: null,
        next_step: "Review filing date",
        status_label: "In progress",
        description: "We are working on this now.",
        approved_intelligence: {
          available: true,
          status: "approved",
          company_name: "PT Safe Client Story",
          summary: "The company profile is approved for client review.",
          last_reviewed_at: "2026-05-17T00:00:00+00:00",
          facts: [
            {
              category: "identity",
              label: "Company status",
              detail: "The company profile is approved for client review.",
              confidence: "confirmed",
            },
          ],
          missing_items: ["Upload the current company registry."],
          next_steps: ["Confirm the next filing date."],
        },
      },
      isLoading: false,
      isError: false,
      error: null,
    });

    render(<PortalMatterDetailPage />);

    expect(screen.getByText("Company Setup")).toBeInTheDocument();
    expect(screen.getByText("Approved Intelligence")).toBeInTheDocument();
    expect(screen.getByText("PT Safe Client Story")).toBeInTheDocument();
    expect(
      screen.getAllByText("The company profile is approved for client review."),
    ).toHaveLength(2);
    expect(
      screen.getByText("Upload the current company registry."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Confirm the next filing date."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/drive\.google\.com/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/\bKG\b|\bOCR\b|source_file_ids/i),
    ).not.toBeInTheDocument();
  });

  it("renders a pending state when no approved intelligence is available", () => {
    mockUseParams.mockReturnValue({ id: "10" });
    mockUsePortalMatter.mockReturnValue({
      data: {
        id: 10,
        title: "Visa Renewal",
        type: "visa",
        progress: 30,
        pending_docs: [],
        next_deadline: null,
        next_step: null,
        status_label: "Waiting for documents",
        description: "We are waiting for the documents listed below.",
        approved_intelligence: {
          available: false,
          status: "pending",
          company_name: null,
          summary: null,
          last_reviewed_at: null,
          facts: [],
          missing_items: [],
          next_steps: [],
        },
      },
      isLoading: false,
      isError: false,
      error: null,
    });

    render(<PortalMatterDetailPage />);

    expect(screen.getByText("Visa Renewal")).toBeInTheDocument();
    expect(screen.getByText("No approved summary yet")).toBeInTheDocument();
  });

  it("uses semantic day-theme tokens (WS3), never dark hardcoded colors", () => {
    mockUseParams.mockReturnValue({ id: "9" });
    mockUsePortalMatter.mockReturnValue({
      data: {
        id: 9,
        title: "Company Setup",
        type: "company",
        progress: 60,
        pending_docs: ["Company registry"],
        next_deadline: null,
        next_step: "Review filing date",
        status_label: "In progress",
        description: "We are working on this now.",
        approved_intelligence: {
          available: true,
          status: "approved",
          company_name: "PT Safe Client Story",
          summary: "The company profile is approved for client review.",
          last_reviewed_at: "2026-05-17T00:00:00+00:00",
          facts: [
            {
              category: "identity",
              label: "Company status",
              detail: "The company profile is approved for client review.",
              confidence: "confirmed",
            },
          ],
          missing_items: [],
          next_steps: [],
        },
      },
      isLoading: false,
      isError: false,
      error: null,
    });

    const { container } = render(<PortalMatterDetailPage />);

    // Day masthead: serif headline in --tx-pure, no white-on-paper gradient.
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading.style.fontFamily).toBe("var(--font-serif)");
    expect(heading.className).toContain("text-[var(--tx-pure)]");
    expect(container.querySelector(".lux-text-gradient")).toBeNull();

    // Panels sit on the warm-paper card surface + hairline border (was
    // hardcoded dark rgba(30,30,35,0.7) / rgba(255,255,255,0.05)).
    const panels = container.querySelectorAll("section, aside");
    const panelStyles = Array.from(panels).map(
      (el) => (el as HTMLElement).style.background,
    );
    expect(panelStyles).toContain("var(--bz-card)");
    expect(container.innerHTML).not.toContain("rgba(30,30,35");
    expect(container.innerHTML).not.toContain("rgba(255,255,255,0.05)");

    // Status/approval badges read --state-success (was emerald-300/500,
    // 1.6–2.2:1 on paper).
    const badges = container.querySelectorAll('[class*="--state-success"]');
    expect(badges.length).toBeGreaterThanOrEqual(2);
    expect(container.innerHTML).not.toContain("text-emerald-300");
    expect(container.innerHTML).not.toContain("bg-emerald-500/10");

    // Drain guard: no hardcoded hex colors anywhere in the page output.
    expect(container.innerHTML).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});
