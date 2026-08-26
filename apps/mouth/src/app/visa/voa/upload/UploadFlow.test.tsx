import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { UploadFlow } from "./UploadFlow";
import { CHECKLIST_ITEMS } from "./messages";

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

describe("UploadFlow", () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    global.fetch = mockFetch;
    mockFetch.mockReset();
    URL.createObjectURL = vi.fn(() => "blob:mock");
    URL.revokeObjectURL = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders every checklist item and a file input accepting the allowed image types", () => {
    render(<UploadFlow resultId="result-1" />);

    for (const item of CHECKLIST_ITEMS) {
      expect(screen.getByText(item)).toBeInTheDocument();
    }

    const input = screen.getByLabelText(
      "Upload passport photo",
    ) as HTMLInputElement;
    expect(input.getAttribute("accept")).toContain("image/jpeg");
    // No `capture="environment"` (refuter finding, 2026-08-25): that attribute launches
    // the camera directly and hides the OS's native photo-library option — a customer
    // with an existing scan of their passport must be able to pick it, not just shoot a
    // new photo.
    expect(input.hasAttribute("capture")).toBe(false);
  });

  it("hides the checklist once a photo has moved into review", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse(201, {
        document_id: "doc-checklist",
        processing_state: "READY_FOR_REVIEW",
        review_fields: [
          {
            field_path: "full_name",
            value: "JANE DOE",
            confirmation_required: true,
          },
        ],
      }),
    );

    render(<UploadFlow resultId="result-1" />);
    const input = screen.getByLabelText(
      "Upload passport photo",
    ) as HTMLInputElement;
    const file = new File([new Uint8Array(10)], "passport.jpg", {
      type: "image/jpeg",
    });

    await userEvent.upload(input, file);
    await screen.findByDisplayValue("JANE DOE");

    expect(screen.queryByText(CHECKLIST_ITEMS[0])).not.toBeInTheDocument();
  });

  it("never pre-fills a value into a low-confidence field's input", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse(202, {
        document_id: "doc-1",
        processing_state: "LOW_CONFIDENCE",
        uncertain_fields: [
          { field_path: "passport_number", confirmation_required: true },
        ],
      }),
    );

    render(<UploadFlow resultId="result-1" />);
    const input = screen.getByLabelText(
      "Upload passport photo",
    ) as HTMLInputElement;
    const file = new File([new Uint8Array(10)], "passport.jpg", {
      type: "image/jpeg",
    });

    await userEvent.upload(input, file);

    await waitFor(() =>
      expect(
        screen.getByPlaceholderText("Enter this field"),
      ).toBeInTheDocument(),
    );
    const uncertainInput = screen.getByPlaceholderText(
      "Enter this field",
    ) as HTMLInputElement;
    // Load-bearing: the contract's UncertainReviewField carries no value at all — this
    // input must start genuinely empty, never guess at what OCR read with low confidence.
    expect(uncertainInput.value).toBe("");

    const confirmButton = screen.getByRole("button", {
      name: "Confirm and continue",
    });
    expect(confirmButton).toBeDisabled();
  });

  it("pre-fills a ready field's value from review_fields and calls onConfirmed with edits", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse(201, {
        document_id: "doc-2",
        processing_state: "READY_FOR_REVIEW",
        review_fields: [
          {
            field_path: "full_name",
            value: "JANE DOE",
            confirmation_required: true,
          },
        ],
      }),
    );

    const onConfirmed = vi.fn();
    render(<UploadFlow resultId="result-1" onConfirmed={onConfirmed} />);
    const input = screen.getByLabelText(
      "Upload passport photo",
    ) as HTMLInputElement;
    const file = new File([new Uint8Array(10)], "passport.jpg", {
      type: "image/jpeg",
    });

    await userEvent.upload(input, file);

    const fullNameInput = await screen.findByDisplayValue("JANE DOE");
    await userEvent.clear(fullNameInput);
    await userEvent.type(fullNameInput, "JOHN DOE");

    await userEvent.click(
      screen.getByRole("button", { name: "Confirm and continue" }),
    );

    expect(onConfirmed).toHaveBeenCalledWith({ full_name: "JOHN DOE" });
  });
});
