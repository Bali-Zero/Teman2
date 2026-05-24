import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { NLMCitationPanel } from "./NLMCitationPanel";

// Mock useChatLocale
vi.mock("@/hooks/useChatLocale", () => ({
  useChatLocale: vi.fn(() => "en"),
}));

import { useChatLocale } from "@/hooks/useChatLocale";

describe("NLMCitationPanel", () => {
  const mockCitations = [
    {
      source_file: "test_file.pdf",
      section: "Section 1",
      excerpt: "Test excerpt",
      page: 1,
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders localized title in English", () => {
    vi.mocked(useChatLocale).mockReturnValue("en");
    render(
      <NLMCitationPanel
        citations={mockCitations}
        domainLabel="Legal"
        expanded={false}
        onToggle={() => {}}
      />
    );
    expect(screen.getByText(/Official Sources — Legal/i)).toBeDefined();
  });

  it("renders localized title in Italian", () => {
    vi.mocked(useChatLocale).mockReturnValue("it");
    render(
      <NLMCitationPanel
        citations={mockCitations}
        domainLabel="Legal"
        expanded={false}
        onToggle={() => {}}
      />
    );
    expect(screen.getByText(/Fonti ufficiali — Legal/i)).toBeDefined();
  });

  it("calls onToggle when header is clicked", () => {
    const onToggle = vi.fn();
    render(
      <NLMCitationPanel
        citations={mockCitations}
        domainLabel="Legal"
        expanded={false}
        onToggle={onToggle}
      />
    );
    fireEvent.click(screen.getByRole("button"));
    expect(onToggle).toHaveBeenCalled();
  });

  it("has correct aria-expanded attribute", () => {
    const { rerender } = render(
      <NLMCitationPanel
        citations={mockCitations}
        domainLabel="Legal"
        expanded={false}
        onToggle={() => {}}
      />
    );
    expect(screen.getByRole("button").getAttribute("aria-expanded")).toBe("false");

    rerender(
      <NLMCitationPanel
        citations={mockCitations}
        domainLabel="Legal"
        expanded={true}
        onToggle={() => {}}
      />
    );
    expect(screen.getByRole("button").getAttribute("aria-expanded")).toBe("true");
  });
});
