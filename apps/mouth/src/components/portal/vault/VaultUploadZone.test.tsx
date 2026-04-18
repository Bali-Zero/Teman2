import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

// Mock useVaultUpload — control its returned state per test.
const mockUpload = vi.fn();
const mockReset = vi.fn();
let mockState: { status: string; [k: string]: unknown } = { status: "idle" };

vi.mock("@/hooks/useVaultUpload", () => ({
  useVaultUpload: () => ({
    state: mockState,
    upload: mockUpload,
    reset: mockReset,
  }),
}));

import { VaultUploadZone } from "./VaultUploadZone";

describe("VaultUploadZone", () => {
  beforeEach(() => {
    mockUpload.mockReset();
    mockReset.mockReset();
    mockState = { status: "idle" };
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
    expect(mockUpload.mock.calls[0][1]).toEqual({ practiceId: 42 });
  });

  it("renders error state when upload state is error", () => {
    mockState = { status: "error", message: "Upload failed (413)" };
    render(<VaultUploadZone />);
    expect(screen.getByRole("alert")).toHaveTextContent(/Upload failed/i);
  });

  it("renders done state with uploaded filename", () => {
    mockState = {
      status: "done",
      file: { name: "ok.pdf" },
      processing: { virus_clean: true },
    };
    render(<VaultUploadZone />);
    expect(screen.getByRole("status")).toHaveTextContent(/Uploaded: ok\.pdf/i);
  });
});
