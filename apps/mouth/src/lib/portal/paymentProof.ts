import type {
  PaymentProof,
  PortalInvoice,
} from "@/lib/api/portal/portal.types";

/**
 * What the portal shows for one invoice's payment proof (spec
 * docs/specs/payment-proof-upload.md; Q1–Q5 as answered in the 7 Oct email):
 * Q1 the LATEST proof decides (created_at, then id); Q2 never `paid_date`;
 * Q4 a re-upload after `rejected` is a new, later row.
 * `hidden` = backend not serving `payment_proofs`, or paid with no proof.
 */
export type PaymentProofView =
  | { kind: "hidden" }
  | { kind: "none" }
  | { kind: "received"; proof: PaymentProof }
  | { kind: "verified"; proof: PaymentProof }
  | { kind: "rejected"; proof: PaymentProof };

const time = (value: string) => Date.parse(value) || 0;

export function latestPaymentProof(
  proofs: PaymentProof[],
): PaymentProof | undefined {
  return proofs.reduce<PaymentProof | undefined>((best, p) => {
    if (!best) return p;
    const diff = time(p.created_at) - time(best.created_at);
    return diff > 0 || (diff === 0 && p.id > best.id) ? p : best;
  }, undefined);
}

export function paymentProofView(invoice: PortalInvoice): PaymentProofView {
  const proofs = invoice.payment_proofs;
  if (!Array.isArray(proofs)) return { kind: "hidden" };
  const latest = latestPaymentProof(proofs);
  if (!latest) {
    return invoice.payment_status === "paid"
      ? { kind: "hidden" }
      : { kind: "none" };
  }
  return { kind: latest.status, proof: latest };
}

/** Sentence for a failed upload, by HTTP status (spec §b limits). */
export function paymentProofUploadError(err: unknown): string {
  const status = (err as { statusCode?: unknown } | null)?.statusCode;
  if (status === 409) {
    return "You uploaded a file with this name less than an hour ago. Rename the file or wait, then try again.";
  }
  if (status === 429) {
    return "Too many uploads in a short time (limit: 10 every 15 minutes). Please try again later.";
  }
  return "Upload failed. Please try again, or send the proof to your account manager through Chat.";
}
