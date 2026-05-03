import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { usePathname } from "next/navigation";
import IntelligenceLayout from "./layout";

vi.mock("next/navigation", () => ({
  usePathname: vi.fn(),
}));

describe("IntelligenceLayout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should hide header on the intelligence homepage", () => {
    vi.mocked(usePathname).mockReturnValue("/intelligence");

    render(
      <IntelligenceLayout>
        <div>Test Content</div>
      </IntelligenceLayout>,
    );

    expect(screen.queryByText("Visa Oracle")).not.toBeInTheDocument();
    expect(screen.queryByText("News Room")).not.toBeInTheDocument();
    expect(screen.queryByText("Article Composer")).not.toBeInTheDocument();
  });

  it("should show header with tabs on sub-pages", () => {
    vi.mocked(usePathname).mockReturnValue("/intelligence/visa-oracle");

    render(
      <IntelligenceLayout>
        <div>Test Content</div>
      </IntelligenceLayout>,
    );

    expect(screen.getByText("Visa Oracle")).toBeInTheDocument();
    expect(screen.getByText("News Room")).toBeInTheDocument();
    expect(screen.getByText("Article Composer")).toBeInTheDocument();
  });

  it('should show "Active" status indicator on sub-pages', () => {
    vi.mocked(usePathname).mockReturnValue("/intelligence/visa-oracle");

    render(
      <IntelligenceLayout>
        <div>Test Content</div>
      </IntelligenceLayout>,
    );

    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("should show back link with aria-label on sub-pages", () => {
    vi.mocked(usePathname).mockReturnValue("/intelligence/visa-oracle");

    render(
      <IntelligenceLayout>
        <div>Test Content</div>
      </IntelligenceLayout>,
    );

    const backLink = screen.getByRole("link", {
      name: "Back to Intelligence Center",
    });
    expect(backLink).toBeInTheDocument();
    expect(backLink).toHaveAttribute("href", "/intelligence");
  });

  it("should render all 3 tabs with correct hrefs", () => {
    vi.mocked(usePathname).mockReturnValue("/intelligence/visa-oracle");

    render(
      <IntelligenceLayout>
        <div>Test Content</div>
      </IntelligenceLayout>,
    );

    const visaOracleLink = screen.getByText("Visa Oracle").closest("a");
    const newsRoomLink = screen.getByText("News Room").closest("a");
    const articleComposerLink = screen
      .getByText("Article Composer")
      .closest("a");

    expect(visaOracleLink).toHaveAttribute("href", "/intelligence/visa-oracle");
    expect(newsRoomLink).toHaveAttribute("href", "/intelligence/news-room");
    expect(articleComposerLink).toHaveAttribute(
      "href",
      "/intelligence/article-composer",
    );
  });

  it("should mark active tab with aria-current=page", () => {
    vi.mocked(usePathname).mockReturnValue("/intelligence/news-room");

    render(
      <IntelligenceLayout>
        <div>Test Content</div>
      </IntelligenceLayout>,
    );

    const newsRoomLink = screen.getByText("News Room").closest("a");
    const visaOracleLink = screen.getByText("Visa Oracle").closest("a");

    expect(newsRoomLink).toHaveAttribute("aria-current", "page");
    expect(visaOracleLink).not.toHaveAttribute("aria-current");
  });

  it("should detect active tab via startsWith (deep paths)", () => {
    vi.mocked(usePathname).mockReturnValue(
      "/intelligence/visa-oracle/some-deep-path",
    );

    render(
      <IntelligenceLayout>
        <div>Test Content</div>
      </IntelligenceLayout>,
    );

    const visaOracleLink = screen.getByText("Visa Oracle").closest("a");
    expect(visaOracleLink).toHaveAttribute("aria-current", "page");
  });

  it("should render children content", () => {
    vi.mocked(usePathname).mockReturnValue("/intelligence/visa-oracle");

    render(
      <IntelligenceLayout>
        <div data-testid="test-child">Test Child Content</div>
      </IntelligenceLayout>,
    );

    expect(screen.getByTestId("test-child")).toBeInTheDocument();
    expect(screen.getByText("Test Child Content")).toBeInTheDocument();
  });

  it("should not have System Pulse tab", () => {
    vi.mocked(usePathname).mockReturnValue("/intelligence/visa-oracle");

    render(
      <IntelligenceLayout>
        <div>Test Content</div>
      </IntelligenceLayout>,
    );

    expect(screen.queryByText("System Pulse")).not.toBeInTheDocument();
  });

  it("should have status indicator with aria-label", () => {
    vi.mocked(usePathname).mockReturnValue("/intelligence/visa-oracle");

    render(
      <IntelligenceLayout>
        <div>Test Content</div>
      </IntelligenceLayout>,
    );

    const statusContainer = screen.getByLabelText(
      "Intelligence services: Active",
    );
    expect(statusContainer).toBeInTheDocument();
  });
});
