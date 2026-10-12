import { describe, expect, it } from "vitest";
import type { ClientDocument } from "@/lib/api/crm/crm.types";
import { pickCurrentVisa } from "./pickCurrentVisa";

const doc = (
  over: Partial<ClientDocument> & { id: number },
): ClientDocument => ({
  client_id: 1,
  document_type: "kitas",
  document_category: "immigration",
  ...over,
});

describe("pickCurrentVisa — the Overview visa card shows the current permit", () => {
  it("control: among dated documents the farthest expiry wins, even if uploaded earlier", () => {
    const docs = [
      doc({
        id: 1,
        expiry_date: "2028-04-24",
        created_at: "2026-01-10T00:00:00Z",
      }),
      doc({
        id: 2,
        expiry_date: "2027-02-04",
        created_at: "2026-05-01T00:00:00Z",
      }),
    ];
    expect(pickCurrentVisa(docs)?.id).toBe(1);
  });

  it("control: an undated document uploaded BEFORE the dated one does not win", () => {
    const docs = [
      doc({ id: 1, created_at: "2025-01-01T00:00:00Z" }),
      doc({
        id: 2,
        expiry_date: "2027-02-04",
        created_at: "2026-01-10T00:00:00Z",
      }),
    ];
    expect(pickCurrentVisa(docs)?.id).toBe(2);
  });

  it("control: no visa documents -> undefined", () => {
    expect(
      pickCurrentVisa([
        doc({
          id: 1,
          document_type: "passport",
          document_category: "personal",
        }),
      ]),
    ).toBeUndefined();
  });

  it("GUILT (10247 shape): a new KITAS without expiry uploaded after the old visa is the current one", () => {
    const docs = [
      doc({
        id: 41,
        document_type: "visa",
        expiry_date: "2027-02-04",
        created_at: "2026-02-01T00:00:00Z",
      }),
      doc({ id: 7349, created_at: "2026-10-01T00:00:00Z" }),
    ];
    expect(pickCurrentVisa(docs)?.id).toBe(7349);
  });

  it("GUILT: a visa the client removed in the portal (deleted_at) is not shown", () => {
    const docs = [
      doc({
        id: 1,
        expiry_date: "2029-01-01",
        created_at: "2026-01-01T00:00:00Z",
        deleted_at: "2026-09-01T00:00:00Z",
      }),
      doc({
        id: 2,
        expiry_date: "2027-02-04",
        created_at: "2026-01-01T00:00:00Z",
      }),
    ];
    expect(pickCurrentVisa(docs)?.id).toBe(2);
  });

  it("GUILT: an archived visa is not shown", () => {
    const docs = [
      doc({ id: 1, expiry_date: "2029-01-01", is_archived: true }),
      doc({ id: 2, expiry_date: "2027-02-04" }),
    ];
    expect(pickCurrentVisa(docs)?.id).toBe(2);
  });

  it("GUILT: a family member's KITAS is not the client's card", () => {
    const docs = [
      doc({ id: 1, expiry_date: "2029-01-01", family_member_id: 9 }),
      doc({ id: 2, expiry_date: "2027-02-04" }),
    ];
    expect(pickCurrentVisa(docs)?.id).toBe(2);
  });
});
