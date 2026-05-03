import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

const useMeMock = vi.fn();
vi.mock("@/hooks/useMe", () => ({
  useMe: () => useMeMock(),
}));

import { AccountSettings } from "./AccountSettings";

describe("AccountSettings", () => {
  beforeEach(() => {
    useMeMock.mockReset();
  });

  it("renders loading state", () => {
    useMeMock.mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: true,
    });
    render(<AccountSettings />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders error state when hook exposes error", () => {
    useMeMock.mockReturnValue({
      data: undefined,
      error: new Error("boom"),
      isLoading: false,
    });
    render(<AccountSettings />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      /unable to load profile/i,
    );
  });

  it("renders profile fields on success", () => {
    useMeMock.mockReturnValue({
      data: {
        id: "u_1",
        email: "zero@balizero.com",
        name: "Zero",
        role: "admin",
        language: "en",
        timezone: "Asia/Bali",
      },
      error: undefined,
      isLoading: false,
    });
    render(<AccountSettings />);
    expect(screen.getByText("Zero")).toBeInTheDocument();
    expect(screen.getByText("zero@balizero.com")).toBeInTheDocument();
    expect(screen.getByText("admin")).toBeInTheDocument();
    expect(screen.getByText("Asia/Bali")).toBeInTheDocument();
  });
});
