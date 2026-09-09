import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { ServicePrice } from "./ServicePrice";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("requests the exact price only after the visitor activates the control", async () => {
  const fetch = vi.fn().mockResolvedValue(Response.json({ available: true, price: "123.456 IDR", verifiedOn: "2026-09-08" }));
  vi.stubGlobal("fetch", fetch);
  render(<ServicePrice serviceKey="Exact (Service)" name="Example service" />);
  expect(fetch).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Check current price for Example service" }));
  expect(fetch).toHaveBeenCalledWith("/api/service-price?key=Exact%20(Service)", expect.objectContaining({ cache: "no-store" }));
  expect(await screen.findByRole("status")).toHaveTextContent("123.456 IDR");
  expect(screen.getByText("2026-09-08")).toHaveAttribute("dateTime", "2026-09-08");
});

it("provides a retry and quote fallback after an unavailable response", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ available: false }, { status: 503 })));
  render(<ServicePrice serviceKey="Example" name="Example" />);
  await userEvent.click(screen.getByRole("button"));
  expect(await screen.findByRole("status")).toHaveTextContent("Price unavailable. Request a quote.");
  expect(screen.getByRole("button")).toHaveTextContent("Try price again");
});
