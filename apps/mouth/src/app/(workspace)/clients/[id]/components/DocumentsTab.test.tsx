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

/** ISO date string `n` days from "now" — used only to land a fixture inside
 * or outside the 90-day urgency window without pinning an exact day count
 * (which `Math.ceil` against a bare date can round either side of `n`
 * depending on the wall-clock time this test happens to run at). */
const daysFromNow = (n: number): string =>
  new Date(Date.now() + n * 86400000).toISOString().slice(0, 10);

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

describe("DocumentsTab — status pill is strictly deleted_at/status (GUILT)", () => {
  it("pill words come only from deleted_at/status — Removed/Valid/Processing/Rejected", () => {
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
        status: "rejected",
        document_category: "immigration",
        file_name: "rejected.pdf",
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
    expect(screen.getAllByText("Rejected").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Removed").length).toBeGreaterThan(0);
  });

  it("a document that EXISTS but has no status is never labelled 'Missing'", () => {
    renderTab([
      doc({ id: 5, document_category: "personal", file_name: "untyped.pdf" }),
    ]);
    expect(screen.queryByText("Missing")).not.toBeInTheDocument();
  });

  it("the status pill never carries the Expired/Expiring word or the copper tone", () => {
    const { container } = renderTab([
      doc({
        id: 6,
        document_category: "immigration",
        file_name: "expiring-visa.pdf",
        expiry_date: daysFromNow(10),
      }),
    ]);
    // Exact match: post-fix, "Expired"/"Expiring" only ever appear as PART of
    // the Expires-cell countdown ("⏰ 10d left"), never as a pill's whole text.
    expect(screen.queryByText("Expired")).not.toBeInTheDocument();
    expect(screen.queryByText("Expiring")).not.toBeInTheDocument();
    expect(container.innerHTML).not.toContain("--bz-copper-text");
  });
});

describe("DocumentsTab — urgency lives on the Expires cell, never the pill", () => {
  it("GUILT: a document expiring within 90 days shows the warning treatment + countdown", () => {
    renderTab([
      doc({
        id: 7,
        document_category: "immigration",
        file_name: "soon.pdf",
        expiry_date: daysFromNow(60),
      }),
    ]);
    const countdowns = screen.getAllByText(/left/);
    expect(countdowns.length).toBeGreaterThan(0);
    for (const el of countdowns) {
      expect(el.getAttribute("style") ?? "").toContain("--state-warning");
    }
  });

  it("GUILT: an already-expired document reads 'Expired Nd ago'", () => {
    renderTab([
      doc({
        id: 8,
        document_category: "immigration",
        file_name: "lapsed.pdf",
        expiry_date: "2000-01-01",
      }),
    ]);
    expect(screen.getAllByText(/Expired \d+d ago/).length).toBeGreaterThan(0);
  });

  it("GUILT: verified AND expiring together show BOTH the Valid pill and the countdown", () => {
    renderTab([
      doc({
        id: 9,
        status: "verified",
        document_category: "immigration",
        file_name: "verified-soon.pdf",
        expiry_date: daysFromNow(10),
      }),
    ]);
    expect(screen.getAllByText("Valid").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/left/).length).toBeGreaterThan(0);
  });

  it("INNOCENCE: a document expiring in 200 days has a plain date cell", () => {
    const { container } = renderTab([
      doc({
        id: 10,
        document_category: "immigration",
        file_name: "far.pdf",
        expiry_date: daysFromNow(200),
      }),
    ]);
    expect(screen.queryByText(/left/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Expired/)).not.toBeInTheDocument();
    expect(screen.queryByText("Expires today")).not.toBeInTheDocument();
    expect(container.innerHTML).not.toContain("--state-warning");
  });

  it("never gives an expiring/expired document a red/danger token", () => {
    const { container } = renderTab([
      doc({
        id: 11,
        document_category: "immigration",
        file_name: "expired.pdf",
        expiry_date: "2000-01-01",
      }),
    ]);
    expect(container.innerHTML).not.toMatch(
      /state-danger|neon-purple|#ff0000/i,
    );
  });
});

describe("DocumentsTab — aggregate expiring-soon summary", () => {
  it("GUILT: counts documents within the 90-day window across all categories", () => {
    const documents = [
      doc({
        id: 12,
        document_category: "personal",
        file_name: "a.pdf",
        expiry_date: daysFromNow(10),
      }),
      doc({
        id: 13,
        document_category: "immigration",
        file_name: "b.pdf",
        expiry_date: daysFromNow(80),
      }),
      doc({
        id: 14,
        document_category: "immigration",
        file_name: "c.pdf",
        expiry_date: daysFromNow(200),
      }),
    ];
    const documentsByCategory = {
      personal: [documents[0]],
      immigration: [documents[1], documents[2]],
    };
    renderTab(documents, documentsByCategory);
    expect(screen.getByText("2 expiring soon")).toBeInTheDocument();
  });
});

describe("DocumentsTab — removed-document restore window", () => {
  it("GUILT: shows the restore-window line with the real deleted_at date", () => {
    renderTab([
      doc({
        id: 15,
        document_category: "personal",
        file_name: "removed.pdf",
        deleted_at: "2026-09-01",
      }),
    ]);
    expect(
      screen.getByText(
        "Removed by the client on 2026-09-01 — restorable by them for 30 days",
      ),
    ).toBeInTheDocument();
  });
});

describe("DocumentsTab — grid/filter/actions (kept)", () => {
  it("the category filter narrows the rows and marks the pressed pill", () => {
    const documents = [
      doc({ id: 16, document_category: "personal", file_name: "photo.jpg" }),
      doc({ id: 17, document_category: "immigration", file_name: "visa.pdf" }),
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
        id: 18,
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
      doc({ id: 19, document_category: "personal", file_name: "missing.pdf" }),
    ]);

    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getAllByText("File tidak tersedia").length).toBeGreaterThan(
      0,
    );
    expect(
      screen.getByRole("button", { name: "Edit missing.pdf" }),
    ).toBeInTheDocument();
  });

  it("shows the EmptyState sentence and a single action when there are no documents", () => {
    renderTab([], {});

    expect(screen.getByText("No documents on file yet.")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Add document" }),
    ).toBeInTheDocument();
  });
});
