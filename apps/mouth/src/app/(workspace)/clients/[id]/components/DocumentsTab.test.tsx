import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ClientDocument } from "@/lib/api/crm/crm.types";
import { DocumentsTab } from "./DocumentsTab";
import { getDocumentOpenUrl } from "./utils";

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

const doc = (
  overrides: Partial<ClientDocument> & { id: number },
): ClientDocument => ({
  client_id: 1,
  document_type: "passport",
  document_category: "personal",
  file_name: `doc-${overrides.id}.pdf`,
  ...overrides,
});

const renderTab = (
  documents: ClientDocument[],
  documentsByCategory: Record<string, ClientDocument[]> = {
    personal: documents,
  },
  extra: Partial<{
    onAddClick: () => void;
    onEditClick: (d: ClientDocument) => void;
  }> = {},
) =>
  render(
    <DocumentsTab
      clientId={1}
      documents={documents}
      documentsByCategory={documentsByCategory}
      formatDate={(d) => d}
      onAddClick={extra.onAddClick ?? vi.fn()}
      onEditClick={extra.onEditClick ?? vi.fn()}
    />,
  );

describe("DocumentsTab — grid rows and status pills (GUILT)", () => {
  it("maps each document's real fields to a status pill word", () => {
    const documents = [
      doc({ id: 1, status: "verified", document_category: "personal" }),
      doc({
        id: 2,
        status: "received",
        document_category: "immigration",
        file_name: "form.pdf",
      }),
      doc({
        id: 3,
        document_category: "immigration",
        file_name: "old-visa.pdf",
        expiry_date: "2000-01-01",
      }),
      doc({
        id: 4,
        document_category: "personal",
        file_name: "removed.pdf",
        deleted_at: "2026-09-01",
      }),
    ];
    const documentsByCategory = {
      personal: [documents[0], documents[3]],
      immigration: [documents[1], documents[2]],
    };
    renderTab(documents, documentsByCategory);

    expect(screen.getAllByText("Valid").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Processing").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Expired").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Removed").length).toBeGreaterThan(0);
  });

  it("the category filter narrows the rows and marks the pressed pill", () => {
    const documents = [
      doc({ id: 1, document_category: "personal", file_name: "photo.jpg" }),
      doc({ id: 2, document_category: "immigration", file_name: "visa.pdf" }),
    ];
    const documentsByCategory = {
      personal: [documents[0]],
      immigration: [documents[1]],
    };
    renderTab(documents, documentsByCategory);

    expect(screen.getByText("photo.jpg")).toBeInTheDocument();
    expect(screen.getByText("visa.pdf")).toBeInTheDocument();

    const immigrationPill = screen.getByRole("button", { name: "Immigration" });
    expect(immigrationPill).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(immigrationPill);

    expect(immigrationPill).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("visa.pdf")).toBeInTheDocument();
    expect(screen.queryByText("photo.jpg")).not.toBeInTheDocument();
  });

  it("keeps every existing action reachable by accessible name", () => {
    const documents = [
      doc({
        id: 1,
        document_category: "personal",
        file_name: "IMG_0001.jpeg",
        file_id: "portal-file-1",
        file_url: "https://drive.google.com/file/d/portal-file-1/view",
      }),
    ];
    const onAddClick = vi.fn();
    const onEditClick = vi.fn();
    renderTab(documents, { personal: documents }, { onAddClick, onEditClick });

    const openLink = screen.getByRole("link", { name: "Open IMG_0001.jpeg" });
    expect(openLink).toHaveAttribute(
      "href",
      "/api/documents/proxy/portal-file-1",
    );
    expect(openLink).toHaveAttribute("target", "_blank");
    expect(openLink).toHaveAttribute("rel", "noopener noreferrer");

    const viewLink = screen.getByRole("link", { name: "View IMG_0001.jpeg" });
    expect(viewLink).toHaveAttribute(
      "href",
      "/api/documents/proxy/portal-file-1",
    );

    fireEvent.click(screen.getByRole("button", { name: "Edit IMG_0001.jpeg" }));
    expect(onEditClick).toHaveBeenCalledWith(documents[0]);

    fireEvent.click(screen.getByRole("button", { name: "Add document" }));
    expect(onAddClick).toHaveBeenCalled();
  });

  it("says the file is unavailable when the row has nothing to open", () => {
    renderTab([
      doc({ id: 2, document_category: "personal", file_name: "missing.pdf" }),
    ]);

    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getAllByText("File tidak tersedia").length).toBeGreaterThan(
      0,
    );
    expect(
      screen.getByRole("button", { name: "Edit missing.pdf" }),
    ).toBeInTheDocument();
  });
});

describe("DocumentsTab (INNOCENCE)", () => {
  it("shows the EmptyState sentence and a single action when there are no documents", () => {
    renderTab([], {});

    expect(screen.getByText("No documents on file yet.")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Add document" }),
    ).toBeInTheDocument();
  });

  it("never gives an expired document a red/danger token", () => {
    renderTab([
      doc({
        id: 5,
        document_category: "immigration",
        file_name: "expired-visa.pdf",
        expiry_date: "2000-01-01",
      }),
    ]);

    for (const pill of screen.getAllByText("Expired")) {
      expect(pill.closest("span")?.className ?? "").not.toMatch(/red|danger/i);
    }
  });
});
