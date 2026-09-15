import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { formatIDR } from "@balizero/core/utils";
import { CheckoutFlow } from "./CheckoutFlow";
import { writeCheckoutHandoff } from "../../checkoutHandoff";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push, replace: mocks.replace }),
}));

// The tracker's own emitFunnelAppEvent posts through the SAME global fetch
// mock the tests below use for /api/visa/voa/orders — mocked here (mirroring
// visa/match's page.test.tsx) so `fetchMock.toHaveBeenCalledTimes(1)` below
// still counts only the orders call, and tracker calls are assertable.
const trackerMocks = vi.hoisted(() => ({
  formSubmitted: vi.fn(),
  formSubmitFailed: vi.fn(),
}));

vi.mock("@balizero/core", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@balizero/core")>();
  return {
    ...actual,
    useFunnelApp: () => ({
      viewed: vi.fn(),
      formSubmitted: trackerMocks.formSubmitted,
      formSubmitFailed: trackerMocks.formSubmitFailed,
    }),
  };
});

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
    trackerMocks.formSubmitted.mockReset();
    trackerMocks.formSubmitFailed.mockReset();
    // jsdom doesn't implement window.location.href assignment navigation; stub it so
    // the redirect-to-provider effect doesn't throw ("Not implemented: navigation").
    // @ts-expect-error -- test-only stub
    delete window.location;
    // @ts-expect-error -- test-only stub
    window.location = { href: "" };
  });

  it("with a missing handoff, renders full_name/passport_number as editable inputs instead of bouncing to upload", () => {
    render(<CheckoutFlow resultId="result-1" paymentsLive={true} />);
    expect(
      screen.queryByRole("link", { name: /go back to upload/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByLabelText(/full name \(as in passport\)/i),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/^passport number$/i)).toBeInTheDocument();
  });

  it("with a missing handoff, submits createOrder with the typed full_name/passport_number", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(201, {
        order_id: "order-1",
        order_state: "awaiting_payment",
        price_idr: 850000,
        checkout_url: "https://pay.example.com/session/abc",
      }),
    );

    const user = userEvent.setup();
    render(<CheckoutFlow resultId="result-1" paymentsLive={true} />);
    await user.type(
      screen.getByLabelText(/full name \(as in passport\)/i),
      "Jane Doe",
    );
    await user.type(screen.getByLabelText(/^passport number$/i), "X1234567");
    await fillAndSubmit(user);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.applicant).toEqual({
      full_name: "Jane Doe",
      email: "customer@example.com",
      phone: "+6281234567890",
      passport_number: "X1234567",
    });
  });

  it("with the handoff present, keeps full_name/passport_number read-only", async () => {
    writeCheckoutHandoff("result-1", {
      full_name: "Jane Doe",
      passport_number: "X1234567",
    });
    render(<CheckoutFlow resultId="result-1" paymentsLive={true} />);

    await screen.findByText("Jane Doe");
    expect(
      screen.queryByLabelText(/full name \(as in passport\)/i),
    ).not.toBeInTheDocument();
  });

  it("never renders a price breakdown — only the single all-inclusive footer line", async () => {
    writeCheckoutHandoff("result-1", {
      full_name: "Jane Doe",
      passport_number: "X1234567",
    });
    render(<CheckoutFlow resultId="result-1" paymentsLive={true} />);

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
    render(<CheckoutFlow resultId="result-1" paymentsLive={true} />);
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

    // Checkout attempt telemetry: field NAMES only (Law 2), never the
    // applicant's own values.
    expect(trackerMocks.formSubmitted).toHaveBeenCalledWith(
      expect.arrayContaining([
        "full_name",
        "email",
        "phone",
        "passport_number",
      ]),
    );
    const wire = JSON.stringify(trackerMocks.formSubmitted.mock.calls);
    expect(wire).not.toContain("Jane Doe");
    expect(wire).not.toContain("customer@example.com");
    expect(wire).not.toContain("X1234567");
  });

  it("a retryable order failure fires formSubmitFailed with endpoint + status, never the applicant", async () => {
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
    render(<CheckoutFlow resultId="result-1" paymentsLive={true} />);
    await screen.findByText(/Jane Doe/i);
    await fillAndSubmit(user);

    await waitFor(() =>
      expect(trackerMocks.formSubmitFailed).toHaveBeenCalledWith(
        "/api/visa/voa/orders",
        503,
      ),
    );
    const wire = JSON.stringify(trackerMocks.formSubmitFailed.mock.calls);
    expect(wire).not.toContain("Jane Doe");
    expect(wire).not.toContain("customer@example.com");
    expect(wire).not.toContain("X1234567");
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
    render(<CheckoutFlow resultId="result-1" paymentsLive={true} />);
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
    render(<CheckoutFlow resultId="result-1" paymentsLive={true} />);
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
    render(<CheckoutFlow resultId="result-1" paymentsLive={true} />);
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
    render(<CheckoutFlow resultId="result-1" paymentsLive={true} />);
    await screen.findByText(/Jane Doe/i);
    await fillAndSubmit(user);

    await screen.findByRole("alert");
    expect(screen.getByRole("alert").textContent).toMatch(
      /payment provider is temporarily unavailable/i,
    );
  });
});

function whatsappTextParam(href: string): string {
  return new URL(href).searchParams.get("text") ?? "";
}

describe("CheckoutFlow — paymentsLive=false (payment activating panel)", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    window.sessionStorage.clear();
  });

  it("renders no order form and never calls createOrder", () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, { verdict: "ACCEPT", price_idr: 850000 }),
    );
    render(<CheckoutFlow resultId="result-12345678" paymentsLive={false} />);

    expect(
      screen.queryByRole("button", { name: /continue to payment/i }),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.every(
        ([url]) => !String(url).includes("/visa/voa/orders"),
      ),
    ).toBe(true);
  });

  it("WhatsApp CTA carries a truncated ref and no PII, even with a handoff on file", async () => {
    writeCheckoutHandoff("result-12345678", {
      full_name: "Jane Doe",
      passport_number: "X1234567",
    });
    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, { verdict: "ACCEPT", price_idr: 850000 }),
    );
    render(<CheckoutFlow resultId="result-12345678" paymentsLive={false} />);

    const link = await screen.findByRole("link", {
      name: /continue on whatsapp/i,
    });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");

    const text = whatsappTextParam(link.getAttribute("href") ?? "");
    expect(text).toContain("ref result-1"); // first 8 chars of "result-12345678"
    expect(text).not.toMatch(/Jane|Doe|X1234567|customer@example\.com|\+62/i);
  });

  it("shows the held all-inclusive price when the eligibility check comes back ACCEPT", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, { verdict: "ACCEPT", price_idr: 850000 }),
    );
    render(<CheckoutFlow resultId="result-12345678" paymentsLive={false} />);

    // formatIDR's id-ID currency formatting inserts a NON-BREAKING space (U+00A0)
    // between "Rp" and the amount — normalize both sides before comparing so this
    // doesn't depend on which whitespace character the ICU data happens to use.
    const priceText = formatIDR(850000).replace(/\s/g, " ");
    await waitFor(() => {
      const bodyText = (document.body.textContent ?? "").replace(/\s/g, " ");
      expect(bodyText).toContain(priceText);
    });
  });

  it("omits the price line — never invents a number — when the eligibility fetch fails", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(404, {}));
    render(<CheckoutFlow resultId="result-12345678" paymentsLive={false} />);

    await screen.findByRole("status");
    expect(screen.queryByText(/all-inclusive\./i)).not.toBeInTheDocument();
    expect(screen.getByRole("status").textContent).toMatch(
      /opens here very soon/i,
    );
  });
});
