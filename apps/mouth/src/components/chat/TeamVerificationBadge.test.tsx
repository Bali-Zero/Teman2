import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { TeamVerificationBadge } from "./TeamVerificationBadge";

// Mock useChatLocale
vi.mock("@/hooks/useChatLocale", () => ({
  useChatLocale: vi.fn(() => "en"),
}));

import { useChatLocale } from "@/hooks/useChatLocale";

describe("TeamVerificationBadge", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when status is not_needed", () => {
    const { container } = render(<TeamVerificationBadge status="not_needed" />);
    expect(container.firstChild).toBeNull();
  });

  it("renders consulting state in English", () => {
    vi.mocked(useChatLocale).mockReturnValue("en");
    render(<TeamVerificationBadge status="consulting" domainLabel="Legal" />);
    expect(screen.getByText(/Our Legal specialists are verifying/i)).toBeDefined();
  });

  it("renders verified state in Italian", () => {
    vi.mocked(useChatLocale).mockReturnValue("it");
    render(<TeamVerificationBadge status="verified" domainLabel="Legal" />);
    expect(screen.getByText(/Verificato dal team Legal/i)).toBeDefined();
  });

  it("renders verified state in Indonesian", () => {
    vi.mocked(useChatLocale).mockReturnValue("id");
    render(<TeamVerificationBadge status="verified" domainLabel="Imigrasi" />);
    expect(screen.getByText(/Diverifikasi oleh tim Imigrasi/i)).toBeDefined();
  });

  it("applies aria-expanded based on isExpanded prop", () => {
    const { rerender } = render(
      <TeamVerificationBadge
        status="verified"
        domainLabel="Legal"
        onToggleCitations={() => {}}
        isExpanded={false}
      />
    );
    const button = screen.getByRole("button");
    expect(button.getAttribute("aria-expanded")).toBe("false");

    rerender(
      <TeamVerificationBadge
        status="verified"
        domainLabel="Legal"
        onToggleCitations={() => {}}
        isExpanded={true}
      />
    );
    expect(button.getAttribute("aria-expanded")).toBe("true");
  });
});
