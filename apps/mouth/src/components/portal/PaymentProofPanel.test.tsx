import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  PaymentProof,
  PortalInvoice,
} from "@/lib/api/portal/portal.types";

const { mockUpload } = vi.hoisted(() => ({ mockUpload: vi.fn() }));
vi.mock("@/lib/api", () => ({
  api: { portal: { uploadPaymentProof: mockUpload } },
}));
vi.mock("@/lib/logger", () => ({ logger: { error: vi.fn() } }));

import { PaymentProofPanel } from "./PaymentProofPanel";

const LABEL = "Upload payment proof for INV-202610-00042";
const inv = (payment_proofs?: PaymentProof[]) =>
  ({
    id: 7,
    invoice_number: "INV-202610-00042",
    payment_status: "unpaid",
    payment_proofs,
  }) as PortalInvoice;
const proof = (status: PaymentProof["status"], note?: string) => [
  { id: 1, status, note, created_at: "2026-10-12T00:00:00Z" },
];
const choose = (file: File) =>
  fireEvent.change(screen.getByLabelText(LABEL), {
    target: { files: [file] },
  });
const pdf = new File(["%PDF"], "t.pdf", { type: "application/pdf" });

describe("PaymentProofPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUpload.mockResolvedValue(proof("received")[0]);
  });

  it("renders nothing while the backend does not serve payment_proofs", () => {
    const { container } = render(
      <PaymentProofPanel invoice={inv()} onUploaded={vi.fn()} />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("uploads to the invoice, states the limits, and refreshes billing", async () => {
    const onUploaded = vi.fn();
    render(<PaymentProofPanel invoice={inv([])} onUploaded={onUploaded} />);
    expect(screen.getByText(/10 uploads every 15 minutes/)).toBeTruthy();
    choose(pdf);
    await waitFor(() => expect(onUploaded).toHaveBeenCalledTimes(1));
    expect(mockUpload).toHaveBeenCalledWith(7, pdf);
  });

  it("refuses a type the Vault does not accept, without calling the API", () => {
    render(<PaymentProofPanel invoice={inv([])} onUploaded={vi.fn()} />);
    choose(new File(["x"], "a.exe", { type: "application/x-msdownload" }));
    expect(screen.getByRole("alert").textContent).toMatch(/not accepted/);
    expect(mockUpload).not.toHaveBeenCalled();
  });

  it("a 409 is explained in words", async () => {
    mockUpload.mockRejectedValue(
      Object.assign(new Error(), { statusCode: 409 }),
    );
    render(<PaymentProofPanel invoice={inv([])} onUploaded={vi.fn()} />);
    choose(pdf);
    expect((await screen.findByRole("alert")).textContent).toMatch(
      /less than an hour/,
    );
  });

  it.each([
    ["received", /checking/],
    ["verified", /Payment confirmed/],
  ] as const)("%s: status line, no upload button", (status, re) => {
    render(
      <PaymentProofPanel invoice={inv(proof(status))} onUploaded={vi.fn()} />,
    );
    expect(screen.getByRole("status").textContent).toMatch(re);
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("rejected: shows the reason and allows a new upload", () => {
    render(
      <PaymentProofPanel
        invoice={inv(proof("rejected", "Amount does not match"))}
        onUploaded={vi.fn()}
      />,
    );
    expect(screen.getByText("Reason: Amount does not match")).toBeTruthy();
    expect(screen.getByLabelText(LABEL)).toBeTruthy();
  });
});
