import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { RequiredDocument } from "@/lib/types/required-documents";

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: apiMock,
}));

import { useRequiredDocuments } from "./useRequiredDocuments";

const existingDocument: RequiredDocument = {
  id: 10,
  practice_id: 771,
  document_type: "passport",
  document_label: "Passport",
  description: "Valid passport copy",
  is_required: true,
  uploaded_by_client: false,
  uploaded_file_id: null,
  uploaded_at: null,
  client_notes: null,
  team_member_notes: null,
  status: "pending",
  created_at: "2026-07-27T12:00:00Z",
  updated_at: "2026-07-27T12:00:00Z",
};

describe("useRequiredDocuments", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMock.get.mockResolvedValue([existingDocument]);
  });

  it("shows a newly added document from the mutation response even when a refetch would be stale", async () => {
    const addedDocument: RequiredDocument = {
      ...existingDocument,
      id: 11,
      document_type: "photo",
      document_label: "Recent photo",
    };
    apiMock.post.mockResolvedValue(addedDocument);

    const { result } = renderHook(() =>
      useRequiredDocuments({ practiceId: 771 }),
    );

    await waitFor(() =>
      expect(result.current.documents).toEqual([existingDocument]),
    );

    await act(async () => {
      await result.current.addDocument({
        document_type: "photo",
        document_label: "Recent photo",
      });
    });

    expect(result.current.documents).toEqual([existingDocument, addedDocument]);
  });

  it("shows an updated document from the mutation response even when a refetch would be stale", async () => {
    const updatedDocument: RequiredDocument = {
      ...existingDocument,
      status: "verified",
      team_member_notes: "Checked",
      updated_at: "2026-07-27T12:05:00Z",
    };
    apiMock.patch.mockResolvedValue(updatedDocument);

    const { result } = renderHook(() =>
      useRequiredDocuments({ practiceId: 771 }),
    );

    await waitFor(() =>
      expect(result.current.documents).toEqual([existingDocument]),
    );

    await act(async () => {
      await result.current.updateDocument(existingDocument.id, {
        status: "verified",
        team_member_notes: "Checked",
      });
    });

    expect(result.current.documents).toEqual([updatedDocument]);
  });

  it("removes a deleted document immediately without depending on a refetch", async () => {
    apiMock.delete.mockResolvedValue(undefined);

    const { result } = renderHook(() =>
      useRequiredDocuments({ practiceId: 771 }),
    );

    await waitFor(() =>
      expect(result.current.documents).toEqual([existingDocument]),
    );

    await act(async () => {
      await result.current.deleteDocument(existingDocument.id);
    });

    expect(result.current.documents).toEqual([]);
  });
});
