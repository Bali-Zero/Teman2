import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/error-handler";

const mocks = vi.hoisted(() => ({
  apiPost: vi.fn(),
  loggerError: vi.fn(),
  loggerWarn: vi.fn(),
  routerPush: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.routerPush }),
}));

vi.mock("@/lib/api", () => ({
  api: { post: mocks.apiPost },
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({
    error: mocks.toastError,
    success: mocks.toastSuccess,
  }),
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: mocks.loggerError, warn: mocks.loggerWarn },
}));

import LKPMSubmitPage from "./page";

describe("LKPMSubmitPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders a labelled native form and accessible return route", () => {
    render(<LKPMSubmitPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Submit LKPM Data" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Quarter" })).toHaveValue("Q1");
    expect(
      screen.getByRole("spinbutton", { name: /Indonesian Workers/ }),
    ).toHaveAttribute("min", "0");
    expect(
      screen.getByRole("link", { name: "Back to LKPM reports" }),
    ).toHaveAttribute("href", "/portal/lkpm");
    expect(screen.getByRole("button", { name: "Submit Data" })).toHaveAttribute(
      "type",
      "submit",
    );
  });

  it("submits the authenticated-client payload and follows the returned period", async () => {
    mocks.apiPost.mockResolvedValue({
      success: true,
      draft_id: 7,
      quarter: "Q2",
      year: 2026,
      realized_total: 1250000,
    });
    render(<LKPMSubmitPage />);

    fireEvent.change(screen.getByRole("combobox", { name: "Quarter" }), {
      target: { value: "Q2" },
    });
    fireEvent.change(
      screen.getByRole("textbox", { name: "Land Acquisition / Preparation" }),
      {
        target: { value: "1.250.000" },
      },
    );
    fireEvent.change(
      screen.getByRole("spinbutton", { name: /Indonesian Workers/ }),
      {
        target: { value: "3" },
      },
    );
    fireEvent.click(screen.getByRole("button", { name: "Submit Data" }));

    await waitFor(() => {
      expect(mocks.apiPost).toHaveBeenCalledWith(
        "/api/v1/lkpm/submit-data",
        expect.objectContaining({
          client_id: 0,
          quarter: "Q2",
          land: 1250000,
          tki: 3,
        }),
      );
    });
    expect(mocks.toastSuccess).toHaveBeenCalledWith(
      "Data submitted successfully",
      "Draft created for Q2 2026",
    );
    expect(mocks.routerPush).toHaveBeenCalledWith("/portal/lkpm/Q2?year=2026");
  });

  it("keeps the client on the form and shows a safe error when submission fails", async () => {
    const internalError = new Error("synthetic internal detail");
    mocks.apiPost.mockRejectedValue(internalError);
    render(<LKPMSubmitPage />);

    fireEvent.click(screen.getByRole("button", { name: "Submit Data" }));

    await waitFor(() => {
      expect(mocks.toastError).toHaveBeenCalledWith(
        "Submission failed",
        "Please check your data and try again",
      );
    });
    expect(mocks.routerPush).not.toHaveBeenCalled();
    expect(document.body).not.toHaveTextContent("synthetic internal detail");
  });

  it("explains that approved reports are locked without exposing backend detail", async () => {
    mocks.apiPost.mockRejectedValue(
      new ApiError("synthetic backend lifecycle detail", 409),
    );
    render(<LKPMSubmitPage />);

    fireEvent.click(screen.getByRole("button", { name: "Submit Data" }));

    await waitFor(() => {
      expect(mocks.toastError).toHaveBeenCalledWith(
        "Report already locked",
        "Approved or submitted reports cannot be replaced. Contact your Bali Zero team if a correction is needed.",
      );
    });
    expect(document.body).not.toHaveTextContent(
      "synthetic backend lifecycle detail",
    );
    expect(mocks.loggerWarn).toHaveBeenCalledWith(
      "LKPM submission blocked by report lifecycle",
      {
        component: "LKPMSubmitPage",
        action: "submit_locked_report",
      },
    );
    expect(mocks.loggerError).not.toHaveBeenCalled();
    expect(mocks.routerPush).not.toHaveBeenCalled();
  });

  it("switches the form language without changing its native semantics", () => {
    render(<LKPMSubmitPage />);

    fireEvent.click(screen.getByRole("button", { name: "Bahasa" }));

    expect(
      screen.getByRole("heading", { level: 1, name: "Submit Data LKPM" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kirim Data" })).toHaveAttribute(
      "type",
      "submit",
    );
  });
});
