import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/error-handler";

const { mockGetMe, mockReplace, mockRouter } = vi.hoisted(() => {
  const replace = vi.fn();
  return {
    mockGetMe: vi.fn(),
    mockReplace: replace,
    mockRouter: { replace },
  };
});

vi.mock("next/navigation", () => ({
  usePathname: () => "/portal/partner/dashboard",
  useRouter: () => mockRouter,
}));

vi.mock("@/lib/api/partners/partners", () => ({ getMe: mockGetMe }));

import PartnerLayout from "./layout";

describe("PartnerLayout", () => {
  beforeEach(() => {
    mockGetMe.mockReset();
    mockReplace.mockReset();
    window.history.replaceState(
      {},
      "",
      "/portal/partner/dashboard?view=recent",
    );
  });

  it("renders protected content only after the partner role check succeeds", async () => {
    mockGetMe.mockResolvedValue({ id: "partner-1" });
    render(
      <PartnerLayout>
        <div>Partner content</div>
      </PartnerLayout>,
    );

    expect(screen.queryByText("Partner content")).not.toBeInTheDocument();
    expect(await screen.findByText("Partner content")).toBeInTheDocument();
  });

  it("preserves the deep link when the session is unauthenticated", async () => {
    mockGetMe.mockRejectedValue(new ApiError("private backend detail", 401));
    render(<PartnerLayout>Partner content</PartnerLayout>);

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith(
        "/portal/login-upgraded?redirect=%2Fportal%2Fpartner%2Fdashboard%3Fview%3Drecent",
      );
    });
    expect(
      screen.queryByText("private backend detail"),
    ).not.toBeInTheDocument();
  });

  it("shows a truthful account-link state for forbidden partner access", async () => {
    mockGetMe.mockRejectedValue(new ApiError("private link state", 403));
    render(<PartnerLayout>Partner content</PartnerLayout>);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Partner access is unavailable");
    expect(alert).not.toHaveTextContent("private link state");
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("keeps transient outages in place and retries without exposing raw errors", async () => {
    mockGetMe
      .mockRejectedValueOnce(new ApiError("database relation detail", 503))
      .mockResolvedValueOnce({ id: "partner-1" });
    render(<PartnerLayout>Partner content</PartnerLayout>);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "Partner information is temporarily unavailable",
    );
    expect(alert).not.toHaveTextContent("database relation detail");

    fireEvent.click(screen.getByRole("button", { name: "Try Again" }));
    expect(await screen.findByText("Partner content")).toBeInTheDocument();
    expect(mockGetMe).toHaveBeenCalledTimes(2);
    expect(mockReplace).not.toHaveBeenCalled();
  });
});
