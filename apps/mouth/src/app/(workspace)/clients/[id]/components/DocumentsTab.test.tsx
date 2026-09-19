import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ClientDocument } from "@/lib/api/crm/crm.types";
import { StatePill } from "@/components/workspace/r19";
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
  it("pill words come only from deleted_at/status — Removed/Valid/Processing/Rejected — and none of them is copper", () => {
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
    const { container } = renderTab(documents, documentsByCategory);

    expect(screen.getAllByText("Valid").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Processing").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Rejected").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Removed").length).toBeGreaterThan(0);
    // This fixture is the one that actually renders all four pills — the
    // "no copper" claim only means something proven against a row that
    // HAS a pill (R3-audit.md §6: the old fixture had none, so the
    // assertion passed vacuously).
    expect(container.innerHTML).not.toContain("--bz-copper-text");
  });

  it("a document that EXISTS but has no status is never labelled 'Missing'", () => {
    renderTab([
      doc({ id: 5, document_category: "personal", file_name: "untyped.pdf" }),
    ]);
    expect(screen.queryByText("Missing")).not.toBeInTheDocument();
  });

  it("the status pill never carries the Expired/Expiring word", () => {
    renderTab([
      doc({
        id: 6,
        document_category: "immigration",
        file_name: "expiring-visa.pdf",
        expiry_date: daysFromNow(10),
      }),
    ]);
    // Exact match: post-fix, "Expired"/"Expiring" only ever appear as PART of
    // the Expires-cell countdown ("⏰ 10d left"), never as a pill's whole text.
    // This fixture has no `status`/`deleted_at`, so it renders NO pill at
    // all (`documentStatusPill` → `null`) — the copper claim belongs on the
    // multi-pill fixture above, where a pill actually exists to check
    // (R3-audit.md §6).
    expect(screen.queryByText("Expired")).not.toBeInTheDocument();
    expect(screen.queryByText("Expiring")).not.toBeInTheDocument();
  });

  it("sanity: the copper-detector pattern actually catches copper — proves the assertion above is not vacuous", () => {
    // R3-audit.md §6, round 2: a string literal asserting it contains a
    // substring of itself is a tautology and proves nothing about the
    // product. This instead renders r19's OWN `you` tone (`tokens.ts:107`,
    // `PILL_TONE.you`) — the structurally-unreachable copper case this
    // component never emits (§6) — and proves the exact token the negative
    // assertions above search for is what a REAL copper pill's className
    // actually contains. Same constant, `--bz-copper-text`, in both tests.
    const { container } = render(<StatePill tone="you" label="You" />);
    expect(container.innerHTML).toContain("--bz-copper-text");
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

  describe("the 90-day window is pinned at the exact boundary (R3-audit.md §3)", () => {
    // Fake timers freeze "now" so `Math.ceil` on the day arithmetic lands on
    // an exact integer — with a real clock the previous fixtures (80 in,
    // 200 out) left the 91–199 band unsampled, so a drift to 90→180 or
    // 90→85 passed with every test green. These two fail on EITHER move.
    beforeEach(() => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date("2026-01-01T00:00:00.000Z"));
    });
    afterEach(() => {
      vi.useRealTimers();
    });

    it("GUILT: exactly 90 days out still carries the countdown, in warning", () => {
      renderTab([
        doc({
          id: 20,
          document_category: "immigration",
          file_name: "edge-in.pdf",
          expiry_date: daysFromNow(90),
        }),
      ]);
      const countdowns = screen.getAllByText(/left/);
      expect(countdowns.length).toBeGreaterThan(0);
      for (const el of countdowns) {
        expect(el.getAttribute("style") ?? "").toContain("--state-warning");
      }
    });

    it("INNOCENCE: 91 days out is a plain date — no countdown, no warning token", () => {
      const { container } = renderTab([
        doc({
          id: 21,
          document_category: "immigration",
          file_name: "edge-out.pdf",
          expiry_date: daysFromNow(91),
        }),
      ]);
      expect(screen.queryByText(/left/)).not.toBeInTheDocument();
      expect(container.innerHTML).not.toContain("--state-warning");
    });

    it("GUILT: the aggregate counts an exactly-90-day document — same expiryCountdown fn", () => {
      renderTab([
        doc({
          id: 22,
          document_category: "immigration",
          file_name: "agg-in.pdf",
          expiry_date: daysFromNow(90),
        }),
      ]);
      expect(screen.getByText("1 expiring soon")).toBeInTheDocument();
    });

    it("INNOCENCE: the aggregate excludes a 91-day document", () => {
      renderTab([
        doc({
          id: 23,
          document_category: "immigration",
          file_name: "agg-out.pdf",
          expiry_date: daysFromNow(91),
        }),
      ]);
      expect(screen.queryByText(/expiring soon/)).not.toBeInTheDocument();
    });
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
      /state-danger|neon-purple|#ff0000/i, // token-lint-ok: negative assertion — the hex is what must NOT render
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

describe("DocumentsTab — per-category doc count + expiring count (R3-audit.md §2.2/§2.3)", () => {
  it("GUILT: the category filter pill carries its own doc count and expiring-soon count, computed with expiryCountdown", () => {
    const documents = [
      doc({
        id: 24,
        document_category: "immigration",
        file_name: "a.pdf",
        expiry_date: daysFromNow(10),
      }),
      doc({
        id: 25,
        document_category: "immigration",
        file_name: "b.pdf",
        expiry_date: daysFromNow(200),
      }),
      doc({ id: 26, document_category: "personal", file_name: "c.pdf" }),
    ];
    const documentsByCategory = {
      immigration: [documents[0], documents[1]],
      personal: [documents[2]],
    };
    renderTab(documents, documentsByCategory);

    // 2 docs total in "immigration", 1 of them expiring within 90 days —
    // readable off the pill without clicking it (old grouped-header view,
    // origin/main before this restyle, showed both simultaneously per group).
    expect(
      screen.getByRole("button", { name: "Immigration · 2 · 1 soon" }),
    ).toBeInTheDocument();
    // "personal" has 1 doc, none expiring — no "soon" suffix.
    expect(
      screen.getByRole("button", { name: "Personal · 1" }),
    ).toBeInTheDocument();
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

    const immigrationPill = screen.getByRole("button", {
      name: "Immigration · 1",
    });
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

    // INNOCENCE (R3-audit.md §5, restoring T-OLD:96): a row that HAS a file
    // must never show the "unavailable" fallback — the symmetric side of
    // the guilt case below, which only proved the fallback appears when
    // the file is missing, never that it stays away when it isn't.
    expect(screen.queryByText("File tidak tersedia")).not.toBeInTheDocument();
  });

  it("shows the document type on the secondary line even when file_name is present (R3-audit.md §2.1)", () => {
    renderTab([
      doc({
        id: 27,
        document_type: "id_card",
        document_category: "personal",
        file_name: "IMG_0001.jpeg",
      }),
    ]);
    // GUILT: the old component read `document_type` on every row regardless
    // of `file_name`; the name alone ("IMG_0001.jpeg") does not say what the
    // document IS. Category ("Personal") does not substitute for type
    // either — it covers passport, visa, KITAS, sponsor letter, ERP alike.
    expect(screen.getByText("IMG_0001.jpeg")).toBeInTheDocument();
    expect(screen.getAllByText(/Id Card/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Personal/).length).toBeGreaterThan(0);
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

  it("shows the EmptyState sentence, its old hint (R3-audit.md §2.4), and a single action when there are no documents", () => {
    renderTab([], {});

    expect(screen.getByText("No documents on file yet.")).toBeInTheDocument();
    // Verbatim from the old component (`OLD:128-130`) — the only line that
    // told a new operator WHAT to upload.
    expect(
      screen.getByText("Upload passport, visa, or company documents"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Add document" }),
    ).toBeInTheDocument();
  });
});
