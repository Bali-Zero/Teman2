import { describe, expect, it } from "vitest";
import type { PortalInvoice } from "@/lib/api/portal/portal.types";
import { paymentProofUploadError, paymentProofView } from "./paymentProof";

const inv = (over: Partial<PortalInvoice>) =>
  ({ id: 1, payment_status: "unpaid", ...over }) as PortalInvoice;
const p = (id: number, status: string, day: number) => ({
  id,
  status: status as "received" | "verified" | "rejected",
  created_at: `2026-10-0${day}T00:00:00Z`,
});

describe("paymentProofView", () => {
  it.each([
    ["field absent (backend not serving) → hidden", inv({}), "hidden"],
    ["served, nothing uploaded → none", inv({ payment_proofs: [] }), "none"],
    [
      "paid with no proof → hidden",
      inv({ payment_proofs: [], payment_status: "paid" }),
      "hidden",
    ],
    [
      "Q1: latest wins over an older verified",
      inv({ payment_proofs: [p(1, "verified", 1), p(2, "rejected", 2)] }),
      "rejected",
    ],
    [
      "Q4: re-upload after rejected is the latest row",
      inv({ payment_proofs: [p(1, "rejected", 1), p(2, "received", 3)] }),
      "received",
    ],
    [
      "same time: higher id wins",
      inv({ payment_proofs: [p(9, "verified", 1), p(5, "rejected", 1)] }),
      "verified",
    ],
  ])("%s", (_, invoice, kind) => {
    expect(paymentProofView(invoice).kind).toBe(kind);
  });
});

describe("paymentProofUploadError", () => {
  it.each([
    [409, /less than an hour/],
    [429, /10 every 15 minutes/],
    [500, /^Upload failed/],
  ])("%s", (statusCode, re) => {
    expect(paymentProofUploadError({ statusCode })).toMatch(re);
  });
});
