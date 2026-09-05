import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { OrderTracker } from "./OrderTracker";
import type { OrderState, OrderView } from "./types";

const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;

function jsonResponse(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

function order(overrides: Partial<OrderView>): OrderView {
  return {
    order_id: "order-1",
    order_state: "awaiting_payment",
    price_idr: 850000,
    browser_observation: "browser_not_returned",
    practice: null,
    ...overrides,
  };
}

describe("OrderTracker", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.useRealTimers();
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("never renders a price breakdown — only the single all-inclusive footer line", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, order({})));
    render(<OrderTracker orderId="order-1" />);

    await screen.findByText(/Rp/);

    const bodyText = document.body.textContent ?? "";
    expect(bodyText).not.toMatch(/PNBP/i);
    expect(bodyText).not.toMatch(/government fee[:\s]/i);
    expect(bodyText).toMatch(/never billed separately from this figure/i);
  });

  it.each<OrderState>([
    "created",
    "awaiting_payment",
    "paid",
    "failed",
    "expired",
    "refunded",
  ])(
    "labels the amount using the authoritative %s order state",
    async (state) => {
      fetchMock.mockResolvedValue(
        jsonResponse(200, order({ order_state: state })),
      );
      render(<OrderTracker orderId="order-1" />);

      await screen.findByText(/Rp/);
      expect(
        screen.getByText(state === "paid" ? "Total paid" : "Order total"),
      ).toBeInTheDocument();
      if (state !== "paid") {
        expect(screen.queryByText("Total paid")).not.toBeInTheDocument();
      }
    },
  );

  it("never claims paid/success from a browser-return observation alone", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        200,
        order({
          order_state: "awaiting_payment",
          browser_observation: "browser_return_observed",
        }),
      ),
    );
    render(<OrderTracker orderId="order-1" />);

    await screen.findByText(/confirming your payment/i);
    expect(screen.queryByText("Total paid")).not.toBeInTheDocument();
    // "Payment confirmed" appears only as a pending step LABEL (ParcelSteps) here —
    // the claim this test guards against is a stated confirmation, never the label.
    expect(
      screen.queryByText(/here's where your application stands/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/your visa has been delivered/i),
    ).not.toBeInTheDocument();
  });

  it("renders the delivery panel only when order_state is paid AND practice.state is Delivered", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        200,
        order({
          order_state: "paid",
          browser_observation: "browser_return_observed",
          practice: {
            practice_id: "practice-1",
            state: "Delivered",
            artifact_available: true,
          },
        }),
      ),
    );
    render(<OrderTracker orderId="order-1" />);

    await screen.findByLabelText(/visa delivered/i);
    expect(
      screen.getByText(/your visa on arrival has been delivered/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /continue on whatsapp/i }),
    ).toBeInTheDocument();
  });

  it("shows delivery when an approved practice advances while the page stays open", async () => {
    vi.useFakeTimers();
    const approved = order({
      order_state: "paid",
      practice: {
        practice_id: "practice-1",
        state: "Approved",
        artifact_available: false,
      },
    });
    const delivered = order({
      order_state: "paid",
      practice: {
        practice_id: "practice-1",
        state: "Delivered",
        artifact_available: true,
      },
    });
    fetchMock
      .mockResolvedValueOnce(jsonResponse(200, approved))
      .mockResolvedValue(jsonResponse(200, delivered));
    render(<OrderTracker orderId="order-1" />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.getByText("Total paid")).toBeInTheDocument();
    expect(screen.queryByLabelText(/visa delivered/i)).not.toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(screen.getByLabelText(/visa delivered/i)).toBeInTheDocument();
  });

  it.each(["failed", "expired"] as const)(
    "offers payment verification for %s without claiming no money was charged",
    async (state) => {
      // OP-F05 keeps the terminal state even after a valid late paid webhook.
      // OrderView therefore cannot establish whether the customer was charged.
      fetchMock.mockResolvedValue(
        jsonResponse(200, order({ order_state: state })),
      );
      render(<OrderTracker orderId="order-1" />);

      await screen.findByText(/Rp/);
      expect(document.body.textContent).not.toMatch(
        /nothing was charged|no payment was taken|didn't go through/i,
      );
      expect(
        screen.getByText(/verify your payment status before you try again/i),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: /continue on whatsapp/i }),
      ).toBeInTheDocument();
    },
  );

  it("shows a WhatsApp route when the practice is Blocked", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        200,
        order({
          order_state: "paid",
          practice: {
            practice_id: "practice-1",
            state: "Blocked",
            required_action_key: "garuda_voa.action.resubmit_passport_photo",
            artifact_available: false,
          },
        }),
      ),
    );
    render(<OrderTracker orderId="order-1" />);

    await screen.findByText(/we need something from you/i);
    expect(screen.getByText(/resubmit passport photo/i)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /continue on whatsapp/i }),
    ).toBeInTheDocument();
  });

  it("never places order data into a rendered link's URL beyond the opaque order id it was given", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, order({})));
    render(<OrderTracker orderId="order-1" />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toBe("/api/visa/voa/orders/order-1");
  });
});
