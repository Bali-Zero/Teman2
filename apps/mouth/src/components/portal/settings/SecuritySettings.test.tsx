import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: replaceMock,
  }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    post: vi.fn(),
    clearToken: vi.fn(),
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
    replaceMock.mockClear();
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
      screen.getByRole("button", { name: /log out all sessions/i }),
    ).toBeInTheDocument();
  });

  it("revokes every session, clears local auth, and redirects to sign in", async () => {
    vi.mocked(api.post).mockResolvedValue({ success: true } as never);
    render(<SecuritySettings />);

    fireEvent.click(
      screen.getByRole("button", { name: /log out all sessions/i }),
    );

    await waitFor(() =>
      expect(vi.mocked(api.post)).toHaveBeenCalledWith(
        "/api/auth/revoke-all",
        {},
      ),
    );
    await waitFor(() =>
      expect(vi.mocked(api.clearToken)).toHaveBeenCalledOnce(),
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      /all sessions revoked/i,
    );
    expect(replaceMock).toHaveBeenCalledWith("/portal/login-upgraded");
  });

  it("surfaces error status when the API call fails", async () => {
    vi.mocked(api.post).mockRejectedValue(new Error("HTTP 500"));
    render(<SecuritySettings />);

    fireEvent.click(
      screen.getByRole("button", { name: /log out all sessions/i }),
    );

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        /unable to revoke sessions/i,
      ),
    );
    expect(vi.mocked(api.clearToken)).not.toHaveBeenCalled();
    expect(replaceMock).not.toHaveBeenCalled();
  });
});
