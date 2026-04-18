import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("@/lib/api", () => ({
  api: {
    post: vi.fn(),
  },
}));

vi.mock("@/lib/logger", () => ({
  logger: {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

import { api } from "@/lib/api";
import { SecuritySettings } from "./SecuritySettings";

describe("SecuritySettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders password + 2FA placeholders and revoke button", () => {
    render(<SecuritySettings />);
    expect(
      screen.getByRole("heading", { name: /^Password$/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /^Two-factor authentication$/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /log out all other sessions/i }),
    ).toBeInTheDocument();
  });

  it("calls /api/auth/revoke-all on click and shows success status", async () => {
    vi.mocked(api.post).mockResolvedValue({ success: true } as never);
    render(<SecuritySettings />);

    fireEvent.click(
      screen.getByRole("button", { name: /log out all other sessions/i }),
    );

    await waitFor(() =>
      expect(vi.mocked(api.post)).toHaveBeenCalledWith(
        "/api/auth/revoke-all",
        {},
      ),
    );
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(
        /all other sessions revoked/i,
      ),
    );
  });

  it("surfaces error status when the API call fails", async () => {
    vi.mocked(api.post).mockRejectedValue(new Error("HTTP 500"));
    render(<SecuritySettings />);

    fireEvent.click(
      screen.getByRole("button", { name: /log out all other sessions/i }),
    );

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        /unable to revoke sessions/i,
      ),
    );
  });
});
