import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CheckoutFlow } from "./CheckoutFlow";
import { writeCheckoutHandoff } from "../../checkoutHandoff";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push, replace: mocks.replace }),
}));

const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;

function jsonResponse(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/email/i), "customer@example.com");
  await user.type(screen.getByLabelText(/phone/i), "+6281234567890");
  await user.click(
    screen.getByRole("button", { name: /continue to payment/i }),
  );
}

describe("CheckoutFlow", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    window.sessionStorage.clear();
    mocks.push.mockReset();
    mocks.replace.mockReset();
    // jsdom doesn't implement window.location.href assignment navigation; stub it so
    // the redirect-to-provider effect doesn't throw ("Not implemented: navigation").
    // @ts-expect-error -- test-only stub
    delete window.location;
    // @ts-expect-error -- test-only stub
    window.location = { href: "" };
  });

  it("blocks checkout and points back to upload when the handoff is missing", () => {
    render(<CheckoutFlow resultId="result-1" />);
    expect(
      screen.getByRole("link", { name: /go back to upload/i }),
    ).toHaveAttribute("href", "/visa/voa/upload/result-1");
  });

  it("never renders a price breakdown — only the single all-inclusive footer line", async () => {
    writeCheckoutHandoff("result-1", {
      full_name: "Jane Doe",
      passport_number: "X1234567",
    });
    render(<CheckoutFlow resultId="result-1" />);

    await screen.findByText(/Jane Doe/i);

    const bodyText = document.body.textContent ?? "";
    expect(bodyText).not.toMatch(/PNBP/i);
    expect(bodyText).not.toMatch(/government fee[:\s]/i);
    expect(bodyText).not.toMatch(/service fee/i);
    expect(bodyText).toMatch(/never billed separately from this figure/i);
  });

  it("sends an Idempotency-Key header and the confirmed applicant on submit", async () => {
    writeCheckoutHandoff("result-1", {
      full_name: "Jane Doe",
      passport_number: "X1234567",
    });
    fetchMock.mockResolvedValueOnce(
      jsonResponse(201, {
        order_id: "order-1",
        order_state: "awaiting_payment",
        price_idr: 850000,
        checkout_url: "https://pay.example.com/session/abc",
      }),
    );

    const user = userEvent.setup();
    render(<CheckoutFlow resultId="result-1" />);
    await screen.findByText(/Jane Doe/i);
    await fillAndSubmit(user);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/visa/voa/orders");
    expect(init.method).toBe("POST");
    const headers = init.headers as Record<string, string>;
    expect(headers["Idempotency-Key"]).toBeTruthy();
    const body = JSON.parse(init.body as string);
    expect(body).toEqual({
      result_id: "result-1",
      applicant: {
        full_name: "Jane Doe",
        email: "customer@example.com",
        phone: "+6281234567890",
        passport_number: "X1234567",
      },
      review_confirmed: true,
    });
  });

  it("redirects the browser to checkout_url on a fresh awaiting_payment order — never renders success itself", async () => {
    writeCheckoutHandoff("result-1", {
      full_name: "Jane Doe",
      passport_number: "X1234567",
    });
    fetchMock.mockResolvedValueOnce(
      jsonResponse(201, {
        order_id: "order-1",
        order_state: "awaiting_payment",
        price_idr: 850000,
        checkout_url: "https://pay.example.com/session/abc",
      }),
    );

    const user = userEvent.setup();
    render(<CheckoutFlow resultId="result-1" />);
    await screen.findByText(/Jane Doe/i);
    await fillAndSubmit(user);

    await waitFor(() =>
      expect(window.location.href).toBe("https://pay.example.com/session/abc"),
    );
    // Never a router.push to a "success"/tracker route while handing off to the
    // provider — the tracker is reached only via the provider's own return trip.
    expect(mocks.push).not.toHaveBeenCalled();
    expect(mocks.replace).not.toHaveBeenCalled();
    expect(screen.queryByText(/success/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/paid/i)).not.toBeInTheDocument();
  });

  it("forwards a replayed already-paid order straight to the tracker instead of showing a payment button", async () => {
    writeCheckoutHandoff("result-1", {
      full_name: "Jane Doe",
      passport_number: "X1234567",
    });
    fetchMock.mockResolvedValueOnce(
      jsonResponse(201, {
        order_id: "order-1",
        order_state: "paid",
        price_idr: 850000,
        checkout_url: null,
      }),
    );

    const user = userEvent.setup();
    render(<CheckoutFlow resultId="result-1" />);
    await screen.findByText(/Jane Doe/i);
    await fillAndSubmit(user);

    await waitFor(() =>
      expect(mocks.replace).toHaveBeenCalledWith("/visa/voa/orders/order-1"),
    );
  });

  it("never places the applicant's email or passport number into a URL", async () => {
    writeCheckoutHandoff("result-1", {
      full_name: "Jane Doe",
      passport_number: "X1234567",
    });
    fetchMock.mockResolvedValueOnce(
      jsonResponse(201, {
        order_id: "order-1",
        order_state: "awaiting_payment",
        price_idr: 850000,
        checkout_url: "https://pay.example.com/session/abc",
      }),
    );

    const user = userEvent.setup();
    render(<CheckoutFlow resultId="result-1" />);
    await screen.findByText(/Jane Doe/i);
    await fillAndSubmit(user);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).not.toContain("customer@example.com");
    expect(url).not.toContain("X1234567");
    expect(url).not.toContain("Jane");
  });

  it("shows the server's error copy and lets the customer retry on a retryable failure", async () => {
    writeCheckoutHandoff("result-1", {
      full_name: "Jane Doe",
      passport_number: "X1234567",
    });
    fetchMock.mockResolvedValueOnce(
      jsonResponse(503, {
        code: "PAYMENT_PROVIDER_UNAVAILABLE",
        retryable: true,
        message_key: "garuda_voa.error.payment_provider_unavailable",
      }),
    );

    const user = userEvent.setup();
    render(<CheckoutFlow resultId="result-1" />);
    await screen.findByText(/Jane Doe/i);
    await fillAndSubmit(user);

    await screen.findByRole("alert");
    expect(screen.getByRole("alert").textContent).toMatch(
      /payment provider is temporarily unavailable/i,
    );
  });
});
