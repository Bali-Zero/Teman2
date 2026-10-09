import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PassportScanSection } from "./PassportScanSection";

const { extractPassportPreview } = vi.hoisted(() => ({
  extractPassportPreview: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: { crm: { extractPassportPreview } },
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn(), debug: vi.fn() },
}));

/**
 * New Client > Scan Passport must take a PDF, not only JPG/PNG: staff
 * receive most passports as PDF scans (request 9 Oct). The OCR endpoint
 * already receives PDFs from the client page PassportCard
 * (extractPassportForClient with mime "application/pdf"), so this screen
 * only has to stop refusing them and pass the real mime on.
 *
 * Declared limits: jsdom, no real OCR; the backend call is mocked and only
 * its arguments are checked.
 */

function fileInput(): HTMLInputElement {
  const input = document.querySelector<HTMLInputElement>('input[type="file"]');
  if (!input) throw new Error("file input not rendered");
  return input;
}

const OCR_OK = {
  success: true,
  confidence: 0.95,
  full_name: "Test Person",
  nationality: null,
  date_of_birth: "1990-01-01",
  gender: "M",
  passport_number: "X1234567",
  passport_expiry: "2030-01-01",
  warnings: [],
};

describe("PassportScanSection — PDF passports", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    extractPassportPreview.mockResolvedValue(OCR_OK);
  });

  it("positive control: the upload zone and its file input render", () => {
    render(
      <PassportScanSection onFieldsConfirmed={vi.fn()} onDiscarded={vi.fn()} />,
    );
    expect(fileInput()).toBeInTheDocument();
    expect(screen.getByText(/JPG, PNG/)).toBeInTheDocument();
  });

  it("GUILT: the file picker offers PDF and the hint says so", () => {
    render(
      <PassportScanSection onFieldsConfirmed={vi.fn()} onDiscarded={vi.fn()} />,
    );
    expect(fileInput().accept).toContain("application/pdf");
    expect(screen.getByText(/JPG, PNG, PDF/)).toBeInTheDocument();
  });

  it("GUILT: a PDF reaches consent and the OCR call carries application/pdf", async () => {
    const onFieldsConfirmed = vi.fn();
    render(
      <PassportScanSection
        onFieldsConfirmed={onFieldsConfirmed}
        onDiscarded={vi.fn()}
      />,
    );
    const pdf = new File(["%PDF-1.4 passport"], "passport.pdf", {
      type: "application/pdf",
    });
    await userEvent.upload(fileInput(), pdf);

    expect(
      await screen.findByText("AI Processing Consent"),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() => expect(extractPassportPreview).toHaveBeenCalled());
    expect(extractPassportPreview.mock.calls[0][1]).toBe("application/pdf");

    await userEvent.click(
      await screen.findByRole("button", { name: "Apply selected" }),
    );
    expect(onFieldsConfirmed).toHaveBeenCalledTimes(1);
    expect(onFieldsConfirmed.mock.calls[0][2]).toBe("application/pdf");
  });

  it("INNOCENCE: a JPG still goes through with image/jpeg", async () => {
    const onFieldsConfirmed = vi.fn();
    render(
      <PassportScanSection
        onFieldsConfirmed={onFieldsConfirmed}
        onDiscarded={vi.fn()}
      />,
    );
    const jpg = new File(["jpeg-bytes"], "passport.jpg", {
      type: "image/jpeg",
    });
    await userEvent.upload(fileInput(), jpg);
    await userEvent.click(
      await screen.findByRole("button", { name: "Continue" }),
    );
    await waitFor(() => expect(extractPassportPreview).toHaveBeenCalled());
    expect(extractPassportPreview.mock.calls[0][1]).toBe("image/jpeg");
    await userEvent.click(
      await screen.findByRole("button", { name: "Apply selected" }),
    );
    expect(onFieldsConfirmed.mock.calls[0][2]).toBe("image/jpeg");
  });

  it("INNOCENCE: a Word file is still refused, and the message names PDF", async () => {
    render(
      <PassportScanSection onFieldsConfirmed={vi.fn()} onDiscarded={vi.fn()} />,
    );
    const user = userEvent.setup({ applyAccept: false });
    const docx = new File(["word"], "passport.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });
    await user.upload(fileInput(), docx);
    expect(
      await screen.findByText("Only JPG, PNG and PDF files are supported."),
    ).toBeInTheDocument();
    expect(extractPassportPreview).not.toHaveBeenCalled();
  });
});
