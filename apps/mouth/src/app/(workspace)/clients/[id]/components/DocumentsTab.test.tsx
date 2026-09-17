import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ClientDocument } from "@/lib/api/crm/crm.types";
import { DocumentsTab } from "./DocumentsTab";
import { getDocumentOpenUrl } from "./utils";

vi.mock("./AiSummaryCard", () => ({ AiSummaryCard: () => null }));

describe("getDocumentOpenUrl", () => {
  it("prefers file_id over any URL on the row", () => {
    expect(
      getDocumentOpenUrl({
        file_id: "portal-file-1",
        google_drive_file_url: "https://drive.google.com/file/d/other-id/view",
        file_url: "https://drive.google.com/file/d/third-id/view",
      }),
    ).toBe("/api/documents/proxy/portal-file-1");
  });

  it("opens a portal upload that has file_id + file_url but no google_drive_file_url", () => {
    expect(
      getDocumentOpenUrl({
        file_id: "portal-file-1",
        file_url: "https://drive.google.com/file/d/portal-file-1/view",
        google_drive_file_url: null,
      }),
    ).toBe("/api/documents/proxy/portal-file-1");
  });

  it("uses file_id when file_url is not a Drive URL", () => {
    expect(
      getDocumentOpenUrl({
        file_id: "portal-file-1",
        file_url: "https://kita.balizero.com/api/portal/documents/42/download",
      }),
    ).toBe("/api/documents/proxy/portal-file-1");
  });

  it("does not mine an id out of a non-Drive URL", () => {
    expect(
      getDocumentOpenUrl({
        file_id: null,
        file_url: "https://example.com/uploads/d/not-a-drive-id?id=nope",
      }),
    ).toBeNull();
  });

  it("falls back to the id inside a Drive URL", () => {
    expect(
      getDocumentOpenUrl({
        google_drive_file_url: "https://drive.google.com/open?id=legacy-id",
      }),
    ).toBe("/api/documents/proxy/legacy-id");
  });

  it("returns null when the row carries no file", () => {
    expect(getDocumentOpenUrl({})).toBeNull();
  });
});

const renderTab = (documents: ClientDocument[]) =>
  render(
    <DocumentsTab
      clientId={1}
      documents={documents}
      documentsByCategory={{ personal: documents }}
      formatDate={(d) => d}
      onAddClick={vi.fn()}
      onEditClick={vi.fn()}
    />,
  );

describe("DocumentsTab document row", () => {
  it("links the file name and View to the proxy in a new tab", () => {
    renderTab([
      {
        id: 1,
        client_id: 1,
        document_type: "photo",
        document_category: "personal",
        file_name: "IMG_0001.jpeg",
        file_id: "portal-file-1",
        file_url: "https://drive.google.com/file/d/portal-file-1/view",
      },
    ]);

    for (const name of ["Open IMG_0001.jpeg", "View IMG_0001.jpeg"]) {
      const link = screen.getByRole("link", { name });
      expect(link).toHaveAttribute(
        "href",
        "/api/documents/proxy/portal-file-1",
      );
      expect(link).toHaveAttribute("target", "_blank");
      expect(link).toHaveAttribute("rel", "noopener noreferrer");
    }
    expect(screen.queryByText("File tidak tersedia")).not.toBeInTheDocument();
  });

  it("says the file is unavailable when the row has nothing to open", () => {
    renderTab([
      {
        id: 2,
        client_id: 1,
        document_type: "photo",
        document_category: "personal",
        file_name: "missing.pdf",
      },
    ]);

    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByText("File tidak tersedia")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
  });
});
