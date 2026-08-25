import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import OrderReturnPage from "./page";

const mocks = vi.hoisted(() => ({
  useParams: vi.fn(),
  useSearchParams: vi.fn(),
  replace: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: mocks.useParams,
  useSearchParams: mocks.useSearchParams,
  useRouter: () => ({ replace: mocks.replace }),
}));

const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;

describe("OrderReturnPage — browser return is an observation, not a truth", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    mocks.replace.mockReset();
    mocks.useParams.mockReturnValue({ orderId: "order-1" });
  });

  it("never renders a success/paid state, even when the observation call succeeds (204)", async () => {
    mocks.useSearchParams.mockReturnValue(
      new URLSearchParams({ return_nonce: "a".repeat(20) }),
    );
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 204,
      json: async () => ({}),
    });

    render(<OrderReturnPage />);

    await waitFor(() =>
      expect(mocks.replace).toHaveBeenCalledWith("/visa/voa/orders/order-1"),
    );
    expect(screen.queryByText(/success/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/you're eligible/i)).not.toBeInTheDocument();
    expect(document.body.textContent ?? "").not.toMatch(/\bpaid\b/i);
  });

  it("still forwards to the tracker (never shows success) when the observation call errors", async () => {
    mocks.useSearchParams.mockReturnValue(
      new URLSearchParams({ return_nonce: "a".repeat(20) }),
    );
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 503,
      json: async () => ({
        code: "SERVICE_UNAVAILABLE",
        retryable: true,
        message_key: "garuda_voa.error.service_unavailable",
      }),
    });

    render(<OrderReturnPage />);

    await waitFor(() =>
      expect(mocks.replace).toHaveBeenCalledWith("/visa/voa/orders/order-1"),
    );
    expect(document.body.textContent ?? "").not.toMatch(/\bpaid\b/i);
  });

  it("posts the return_nonce as the request body, never as a query string on the API call", async () => {
    mocks.useSearchParams.mockReturnValue(
      new URLSearchParams({ return_nonce: "a".repeat(20) }),
    );
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 204,
      json: async () => ({}),
    });

    render(<OrderReturnPage />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(
      "/api/visa/voa/orders/order-1/browser-return-observations",
    );
    expect(url).not.toContain("a".repeat(20));
    expect(JSON.parse(init.body as string)).toEqual({
      return_nonce: "a".repeat(20),
    });
  });

  it("forwards straight to the tracker without calling the API when no return_nonce is present", async () => {
    mocks.useSearchParams.mockReturnValue(new URLSearchParams());

    render(<OrderReturnPage />);

    await waitFor(() =>
      expect(mocks.replace).toHaveBeenCalledWith("/visa/voa/orders/order-1"),
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
