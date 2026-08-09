import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

// Mock useVaultUpload — control its returned state per test.
const mockUpload = vi.fn();
const mockReset = vi.fn();
const mockRetry = vi.fn();
let mockState: { status: string; [k: string]: unknown } = { status: "idle" };
let mockCanRetry = false;

vi.mock("@/hooks/useVaultUpload", () => ({
  useVaultUpload: () => ({
    state: mockState,
    upload: mockUpload,
    reset: mockReset,
    retry: mockRetry,
    canRetry: mockCanRetry,
  }),
}));

import { VaultUploadZone } from "./VaultUploadZone";

describe("VaultUploadZone", () => {
  beforeEach(() => {
    mockUpload.mockReset();
    mockReset.mockReset();
    mockRetry.mockReset();
    mockState = { status: "idle" };
    mockCanRetry = false;
  });

  it("toggles drag-over state on drag events", () => {
    render(<VaultUploadZone />);
    const zone = screen.getByTestId("vault-upload-zone");
    expect(zone.getAttribute("data-drag-over")).toBe("false");

    fireEvent.dragOver(zone);
    expect(zone.getAttribute("data-drag-over")).toBe("true");

    fireEvent.dragLeave(zone);
    expect(zone.getAttribute("data-drag-over")).toBe("false");
  });

  it("calls upload() when file input changes", () => {
    render(<VaultUploadZone practiceId={42} />);
    const input = screen.getByLabelText(
      "Choose file to upload",
    ) as HTMLInputElement;
    const file = new File(["x"], "a.pdf", { type: "application/pdf" });
    Object.defineProperty(input, "files", { value: [file] });
    fireEvent.change(input);
    expect(mockUpload).toHaveBeenCalledTimes(1);
    expect(mockUpload.mock.calls[0][0]).toBe(file);
    // FASE 5: purpose is now part of the upload options (empty when untouched).
    expect(mockUpload.mock.calls[0][1]).toEqual({
      practiceId: 42,
      purpose: "",
    });
  });

  it("advertises exactly the formats and cap enforced by the backend", () => {
    render(<VaultUploadZone />);
    const input = screen.getByLabelText(
      "Choose file to upload",
    ) as HTMLInputElement;
    expect(input).toHaveAttribute("accept", ".pdf,.jpg,.jpeg,.png,.docx");
    expect(input).toHaveAttribute("aria-describedby", "vault-upload-formats");
    expect(
      screen.getByText("PDF, JPG, PNG, or DOCX up to 10 MB"),
    ).toBeInTheDocument();
  });

  it("forwards the typed purpose to upload()", () => {
    render(<VaultUploadZone practiceId={42} />);
    const purposeInput = screen.getByLabelText(
      /what is this document for/i,
    ) as HTMLInputElement;
    fireEvent.change(purposeInput, {
      target: { value: "Passport for KITAS renewal" },
    });
    const input = screen.getByLabelText(
      "Choose file to upload",
    ) as HTMLInputElement;
    const file = new File(["x"], "a.pdf", { type: "application/pdf" });
    Object.defineProperty(input, "files", { value: [file] });
    fireEvent.change(input);
    expect(mockUpload.mock.calls[0][1]).toEqual({
      practiceId: 42,
      purpose: "Passport for KITAS renewal",
    });
  });

  it("renders error state when upload state is error", () => {
    mockState = { status: "error", message: "Upload failed (413)" };
    render(<VaultUploadZone />);
    expect(screen.getByRole("alert")).toHaveTextContent(/Upload failed/i);
    expect(
      screen.queryByRole("button", { name: "Retry upload" }),
    ).not.toBeInTheDocument();
  });

  it("retries the retained upload from a retryable error", () => {
    mockState = { status: "error", message: "Network error" };
    mockCanRetry = true;
    render(<VaultUploadZone />);

    fireEvent.click(screen.getByRole("button", { name: "Retry upload" }));

    expect(mockRetry).toHaveBeenCalledTimes(1);
  });

  it("renders done state with uploaded filename", () => {
    mockState = {
      status: "done",
      file: { name: "ok.pdf" },
    };
    render(<VaultUploadZone />);
    expect(screen.getByRole("status")).toHaveTextContent(/Uploaded: ok\.pdf/i);
  });
});
