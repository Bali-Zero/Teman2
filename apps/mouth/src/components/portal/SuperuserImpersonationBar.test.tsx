import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SuperuserImpersonationBar } from "./SuperuserImpersonationBar";

const { useAdminImpersonationMock } = vi.hoisted(() => ({
  useAdminImpersonationMock: vi.fn(),
}));

vi.mock("@/contexts/AdminImpersonationContext", () => ({
  useAdminImpersonation: useAdminImpersonationMock,
}));

vi.mock("@/lib/api", () => ({
  api: {
    getToken: vi.fn(() => null),
  },
}));

describe("SuperuserImpersonationBar palette", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [] }),
    });
  });

  it("uses the text-safe copper token for the active client label", () => {
    useAdminImpersonationMock.mockReturnValue({
      isSuperuser: true,
      target: {
        id: 42,
        email: "synthetic@example.com",
        fullName: "Synthetic Client",
      },
      setTarget: vi.fn(),
    });

    render(<SuperuserImpersonationBar />);

    const activeLabel = screen.getByText(/Viewing as: Synthetic Client/i);
    expect(activeLabel).toHaveClass("text-[var(--bz-copper-text)]");
    expect(activeLabel).toHaveClass("bg-[var(--bz-copper)]/10");
    expect(activeLabel).toHaveClass("border-[var(--bz-copper)]");
  });

  it("uses themed surfaces for the search field and results panel", () => {
    useAdminImpersonationMock.mockReturnValue({
      isSuperuser: true,
      target: null,
      setTarget: vi.fn(),
    });

    render(<SuperuserImpersonationBar />);

    const input = screen.getByPlaceholderText("Search client to impersonate…");
    expect(input).toHaveClass("bg-[var(--glass-highlight)]");

    fireEvent.change(input, { target: { value: "sy" } });

    expect(screen.getByText("Searching…").parentElement).toHaveClass(
      "bg-[var(--bz-elevated)]",
    );
  });
});
