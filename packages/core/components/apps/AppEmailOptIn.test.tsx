import { fireEvent, render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppEmailOptIn } from "./AppEmailOptIn";

describe("AppEmailOptIn", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("rejects malformed email without contacting the backend", () => {
    const { getByPlaceholderText, getByRole } = render(
      <AppEmailOptIn
        app="visa_clock"
        resultHash="result-1"
        promise="Send me reminders"
      />,
    );

    fireEvent.change(getByPlaceholderText("you@example.com"), {
      target: { value: "invalid" },
    });
    fireEvent.submit(getByRole("button").closest("form")!);

    expect(getByRole("alert").textContent).toContain("doesn't look valid");
    expect(fetch).not.toHaveBeenCalled();
  });

  it("posts the complete subscription contract and renders success", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({ ok: true } as Response);
    const onSubscribed = vi.fn();
    const { getByPlaceholderText, getByRole, getByText } = render(
      <AppEmailOptIn
        app="visa_clock"
        resultHash="result-1"
        promise="Send me reminders"
        payload={{ visa: "E33G" }}
        onSubscribed={onSubscribed}
      />,
    );

    fireEvent.change(getByPlaceholderText("you@example.com"), {
      target: { value: "owner@example.com" },
    });
    fireEvent.click(getByRole("button", { name: "Email me" }));

    await waitFor(() =>
      expect(getByText(/Check your inbox/)).toBeInTheDocument(),
    );
    expect(fetch).toHaveBeenCalledWith(
      "/api/visa/clock/email",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: "owner@example.com",
          app: "visa_clock",
          result_hash: "result-1",
          payload: { visa: "E33G" },
        }),
      }),
    );
    expect(onSubscribed).toHaveBeenCalledWith("owner@example.com");
  });

  it("surfaces backend failures and re-enables retry", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 503,
    } as Response);
    const { getByPlaceholderText, getByRole } = render(
      <AppEmailOptIn
        app="visa_match"
        resultHash="result-2"
        promise="Send me updates"
        endpoint="/custom-subscribe"
      />,
    );

    fireEvent.change(getByPlaceholderText("you@example.com"), {
      target: { value: "owner@example.com" },
    });
    fireEvent.click(getByRole("button", { name: "Email me" }));

    await waitFor(() =>
      expect(getByRole("alert").textContent).toContain("Could not subscribe"),
    );
    expect(fetch).toHaveBeenCalledWith("/custom-subscribe", expect.any(Object));
    expect(getByRole("button", { name: "Email me" })).not.toBeDisabled();
  });
});
