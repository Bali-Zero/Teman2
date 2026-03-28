import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import {
  BaliZeroPaymentsWorkbench,
  baliZeroPaymentsFixture,
} from "./BaliZeroPaymentsWorkbench";

describe("BaliZeroPaymentsWorkbench", () => {
  it("renders default invoice and linked practice details", () => {
    render(<BaliZeroPaymentsWorkbench {...baliZeroPaymentsFixture} />);

    expect(
      screen.getByRole("heading", { name: "INV-2026-017" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Next milestone: Akta notaris booking/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Atlas Advisory · Company Setup · Waiting payment/i),
    ).toBeInTheDocument();
  });

  it("switches invoice context and exposes the correct event trail", async () => {
    const user = userEvent.setup();

    render(<BaliZeroPaymentsWorkbench {...baliZeroPaymentsFixture} />);

    await user.click(
      screen.getByRole("button", {
        name: /INV-2026-021/i,
      }),
    );

    expect(
      screen.getByText(/Next milestone: Biometric appointment/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Sofia Marchetti · Immigration · Documents approved/i),
    ).toBeInTheDocument();
    expect(screen.getByText("Partial payment captured")).toBeInTheDocument();
  });

  it("creates a payment link with the selected invoice and method", async () => {
    const user = userEvent.setup();
    const onCreatePaymentLink = vi.fn();

    render(
      <BaliZeroPaymentsWorkbench
        {...baliZeroPaymentsFixture}
        onCreatePaymentLink={onCreatePaymentLink}
      />,
    );

    await user.click(
      screen.getByRole("button", {
        name: /E-wallet collection/i,
      }),
    );
    await user.click(screen.getByRole("button", { name: /Generate link/i }));

    expect(onCreatePaymentLink).toHaveBeenCalledWith({
      invoiceId: "invoice-01",
      practiceId: "practice-pt-pma-01",
      paymentMethodId: "pm-wallet",
    });
  });
});
