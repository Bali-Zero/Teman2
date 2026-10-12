import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AddDocumentModal } from "./AddDocumentModal";

const { uploadDocumentBase64, createDocument, toastError } = vi.hoisted(() => ({
  uploadDocumentBase64: vi.fn(),
  createDocument: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: { crm: { uploadDocumentBase64, createDocument } },
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: toastError },
}));

const DOCX =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

function renderModal() {
  const { container } = render(
    <AddDocumentModal
      clientId={12414}
      categories={[]}
      familyMembers={[]}
      clientHasDriveFolder
      onClose={vi.fn()}
      onSave={vi.fn()}
    />,
  );
  const input = container.querySelector(
    'input[type="file"]',
  ) as HTMLInputElement;
  return { input };
}

async function pickAndSave(input: HTMLInputElement, file: File) {
  // applyAccept:false — the test drives handleFileSelect's own check, which
  // is the gate that rejected Word files (the accept attribute is only a
  // picker hint and drag-and-drop bypasses it).
  await userEvent.upload(input, file, { applyAccept: false });
  await userEvent.click(screen.getByRole("button", { name: /save/i }));
}

describe("AddDocumentModal — Word documents (request Surya, 7 Oct)", () => {
  beforeEach(() => {
    uploadDocumentBase64.mockReset();
    uploadDocumentBase64.mockResolvedValue({ success: true });
    toastError.mockReset();
  });

  it("GUILT: a .docx is accepted and uploaded with its own MIME type", async () => {
    const { input } = renderModal();
    await pickAndSave(input, new File(["x"], "surat.docx", { type: DOCX }));
    await waitFor(() => expect(uploadDocumentBase64).toHaveBeenCalled());
    expect(uploadDocumentBase64.mock.calls[0][1]).toMatchObject({
      file_name: "surat.docx",
      mime_type: DOCX,
    });
    expect(toastError).not.toHaveBeenCalledWith(
      "Invalid file type",
      expect.anything(),
    );
  });

  it("GUILT: a legacy .doc is accepted", async () => {
    const { input } = renderModal();
    await pickAndSave(
      input,
      new File(["x"], "lama.doc", { type: "application/msword" }),
    );
    await waitFor(() => expect(uploadDocumentBase64).toHaveBeenCalled());
    expect(uploadDocumentBase64.mock.calls[0][1].mime_type).toBe(
      "application/msword",
    );
  });

  it("GUILT: a .docx whose browser MIME is empty is accepted and sent with the inferred MIME", async () => {
    const { input } = renderModal();
    await pickAndSave(input, new File(["x"], "tanpa-mime.docx", { type: "" }));
    await waitFor(() => expect(uploadDocumentBase64).toHaveBeenCalled());
    expect(uploadDocumentBase64.mock.calls[0][1].mime_type).toBe(DOCX);
  });

  it("INNOCENCE: PDF still uploads exactly as before", async () => {
    const { input } = renderModal();
    await pickAndSave(
      input,
      new File(["x"], "paspor.pdf", { type: "application/pdf" }),
    );
    await waitFor(() => expect(uploadDocumentBase64).toHaveBeenCalled());
    expect(uploadDocumentBase64.mock.calls[0][1].mime_type).toBe(
      "application/pdf",
    );
  });

  it("INNOCENCE: an executable is still refused", async () => {
    const { input } = renderModal();
    await userEvent.upload(
      input,
      new File(["x"], "virus.exe", { type: "application/x-msdownload" }),
      { applyAccept: false },
    );
    expect(toastError).toHaveBeenCalledWith(
      "Invalid file type",
      expect.anything(),
    );
    expect(uploadDocumentBase64).not.toHaveBeenCalled();
  });

  it("the picker hint lists Word", () => {
    const { input } = renderModal();
    expect(input.accept).toContain(".docx");
    expect(input.accept).toContain(".doc");
    expect(screen.getByText(/DOC/)).toBeInTheDocument();
  });
});
