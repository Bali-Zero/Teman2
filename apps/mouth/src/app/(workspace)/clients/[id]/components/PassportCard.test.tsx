import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PassportCard } from "./PassportCard";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    crm: {
      extractPassportForClient: vi.fn(),
    },
    post: vi.fn(),
    request: vi.fn(),
  },
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
    dismiss: vi.fn(),
  },
}));

const client = {
  id: 42,
  full_name: "Test Client",
  passport_number: null,
  passport_expiry: null,
  date_of_birth: null,
  gender: null,
};

const documents = [
  {
    id: 7,
    document_type: "passport",
    document_category: "personal",
    file_name: "passport.jpg",
    google_drive_file_url: "https://drive.google.com/file/d/drive-file-123/view",
    family_member_id: null,
  },
];

describe("PassportCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      blob: async () => new Blob(["passport image"], { type: "image/jpeg" }),
    } as Response);
    vi.mocked(api.crm.extractPassportForClient).mockResolvedValue({
      success: true,
      confidence: 0.95,
      full_name: null,
      surname: null,
      given_names: null,
      nationality: null,
      date_of_birth: null,
      gender: null,
      passport_number: "A1234567",
      passport_expiry: "2030-01-01",
      issuing_country: null,
      birthplace: null,
      warnings: [],
      message: null,
    });
  });

  it("does not auto-call the deprecated file_id OCR path for existing Drive passports", async () => {
    render(
      <PassportCard
        client={client as any}
        documents={documents as any}
        formatDate={(value) => value}
        onRefresh={vi.fn()}
        clientId={42}
      />,
    );

    await waitFor(() => {
      expect(api.post).not.toHaveBeenCalled();
      expect(api.crm.extractPassportForClient).not.toHaveBeenCalled();
    });
  });

  it("extracts existing Drive passports by sending image_base64 to the enhanced OCR endpoint", async () => {
    const onRefresh = vi.fn();

    render(
      <PassportCard
        client={client as any}
        documents={documents as any}
        formatDate={(value) => value}
        onRefresh={onRefresh}
        clientId={42}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /extract/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith("/api/documents/proxy/drive-file-123");
      expect(api.crm.extractPassportForClient).toHaveBeenCalledWith(
        expect.any(String),
        "image/jpeg",
        42,
      );
      expect(api.post).not.toHaveBeenCalledWith(
        "/api/crm/clients/extract-passport-enhanced",
        expect.objectContaining({ file_id: "drive-file-123" }),
      );
      expect(onRefresh).toHaveBeenCalled();
    });
  });
});
