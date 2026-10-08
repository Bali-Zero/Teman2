/**
 * Guard — the Overview passport card shows the client's CURRENT passport.
 *
 * The card used to take the first passport row of the profile list. That list
 * is ordered by category/type, not by date, and on the client profile it keeps
 * passports the client removed from the portal vault (deleted_at set — the
 * profile keeps them for the "Removed" pill and the 30-day restore window).
 * So a removed or older passport could be the one shown, downloaded, OCR'd or
 * deleted from the card.
 *
 * Rule: own passport only (no family member), not removed by the client, not
 * archived, newest upload first (created_at, then id).
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ClientDocument } from "@/lib/api/crm/crm.types";
import { PassportCard } from "./PassportCard";
import { pickCurrentPassport } from "./utils";

vi.mock("@/lib/api", () => ({
  api: {
    crm: { extractPassportForClient: vi.fn() },
    post: vi.fn(),
    request: vi.fn(),
  },
}));
vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
    dismiss: vi.fn(),
  }),
}));

const doc = (over: Partial<ClientDocument>): ClientDocument =>
  ({
    client_id: 42,
    document_type: "passport",
    document_category: "personal",
    file_name: "passport.jpg",
    google_drive_file_url: "https://drive.google.com/file/d/f/view",
    family_member_id: undefined,
    ...over,
  }) as ClientDocument;

describe("pickCurrentPassport", () => {
  it("GUILT: skips a passport the client removed in the portal, even when it is listed first", () => {
    const removed = doc({ id: 1, deleted_at: "2026-10-01T00:00:00Z" });
    const live = doc({ id: 2 });
    expect(pickCurrentPassport([removed, live])?.id).toBe(2);
  });

  it("GUILT: picks the newest upload, not the first row of the list", () => {
    const older = doc({ id: 10, created_at: "2024-01-05T00:00:00Z" });
    const newer = doc({ id: 11, created_at: "2026-09-30T00:00:00Z" });
    expect(pickCurrentPassport([older, newer])?.id).toBe(11);
  });

  it("skips archived passports and family members' passports", () => {
    const archived = doc({
      id: 20,
      is_archived: true,
      created_at: "2026-10-01T00:00:00Z",
    });
    const family = doc({
      id: 21,
      family_member_id: 5,
      created_at: "2026-10-02T00:00:00Z",
    });
    const own = doc({ id: 22, created_at: "2025-01-01T00:00:00Z" });
    expect(pickCurrentPassport([archived, family, own])?.id).toBe(22);
  });

  it("innocence: one passport is returned as is; no passport is undefined", () => {
    const only = doc({ id: 30 });
    expect(pickCurrentPassport([only])).toBe(only);
    expect(
      pickCurrentPassport([doc({ id: 31, document_type: "kitas" })]),
    ).toBeUndefined();
    expect(pickCurrentPassport([])).toBeUndefined();
  });

  it("without dates, the higher id (later insert) wins", () => {
    expect(pickCurrentPassport([doc({ id: 40 }), doc({ id: 41 })])?.id).toBe(
      41,
    );
  });
});

describe("PassportCard uses the current passport", () => {
  const renderCard = (documents: ClientDocument[]) =>
    render(
      <PassportCard
        client={{ id: 42, full_name: "T", passport_expiry: null } as never}
        documents={documents}
        formatDate={(v) => v}
        onRefresh={vi.fn()}
        clientId={42}
      />,
    );

  it("positive control: a live PDF passport renders as 'PDF Document'", () => {
    renderCard([doc({ id: 50, file_name: "old.pdf" })]);
    expect(screen.getByText("PDF Document")).toBeTruthy();
  });

  it("GUILT: a removed PDF listed first does not replace the live JPG passport", () => {
    renderCard([
      doc({ id: 50, file_name: "old.pdf", deleted_at: "2026-10-01T00:00:00Z" }),
      doc({ id: 51, file_name: "new.jpg" }),
    ]);
    expect(screen.queryByText("PDF Document")).toBeNull();
  });
});
