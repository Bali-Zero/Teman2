import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ContactHandoff } from "./ContactHandoff";
import { navigateToHandoff } from "../lib/destinations/lead-handoff";

vi.mock("../lib/destinations/lead-handoff", async (original) => ({
  ...await original<typeof import("../lib/destinations/lead-handoff")>(),
  navigateToHandoff: vi.fn(),
}));

afterEach(() => { vi.clearAllMocks(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

describe("ContactHandoff", () => {
  it("renders an immediately usable contextual link without submitting on mount", () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    render(<ContactHandoff topic="tax" sourcePage="/services/tax">Talk about tax</ContactHandoff>);
    const href = screen.getByRole("link", { name: "Talk about tax" }).getAttribute("href")!;
    expect(new URL(href).searchParams.get("text")).toContain("tax and accounting (from /services/tax)");
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("captures, measures and navigates exactly once even under duplicate activation", async () => {
    let respond!: (response: Response) => void;
    const fetcher = vi.fn<typeof fetch>().mockImplementation(() => new Promise((resolve) => { respond = resolve; }));
    const consumer = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    vi.stubGlobal("gtag", consumer);
    vi.stubEnv("NEXT_PUBLIC_WEBSITE_LEAD_ANALYTICS_ENABLED", "true");
    render(<ContactHandoff topic="company" sourcePage="/services/company-setup" analyticsConsent>Talk about business</ContactHandoff>);
    const link = screen.getByRole("link", { name: "Talk about business" });
    fireEvent.click(link);
    fireEvent.click(link);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(link).toHaveAttribute("aria-busy", "true");
    await act(async () => { respond(Response.json({ whatsapp_url: "https://wa.me/628213454721?text=Company%20enquiry" }, { status: 201 })); });
    fireEvent.click(link);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(consumer).toHaveBeenCalledTimes(1);
    expect(consumer.mock.calls[0][2]).toMatchObject({ topic: "company", captured: true, source_page: "/services/company-setup" });
    expect(navigateToHandoff).toHaveBeenCalledExactlyOnceWith("https://wa.me/628213454721?text=Company%20enquiry");
  });

  it("opens the direct fallback by keyboard when capture is unavailable and does not measure without consent", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(Response.json({ available: false }, { status: 503 }));
    const consumer = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    vi.stubGlobal("gtag", consumer);
    vi.stubEnv("NEXT_PUBLIC_WEBSITE_LEAD_ANALYTICS_ENABLED", "true");
    render(<ContactHandoff topic="evoa" sourcePage="/contact?private=discarded">Plan arrival</ContactHandoff>);
    const link = screen.getByRole("link", { name: "Plan arrival" });
    link.focus();
    await userEvent.setup().keyboard("{Enter}");
    await waitFor(() => expect(navigateToHandoff).toHaveBeenCalledExactlyOnceWith(link.getAttribute("href")));
    expect(JSON.parse(fetcher.mock.calls[0][1]?.body as string)).toEqual({ topic: "evoa", sourcePage: "/contact" });
    expect(consumer).not.toHaveBeenCalled();
  });

  it("blocks a malformed returned redirect and measures only the unconfirmed fallback", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(Response.json({ whatsapp_url: "https://evil.example" }, { status: 201 })));
    const consumer = vi.fn();
    vi.stubGlobal("gtag", consumer);
    vi.stubEnv("NEXT_PUBLIC_WEBSITE_LEAD_ANALYTICS_ENABLED", "true");
    render(<ContactHandoff topic="portal" analyticsConsent>Portal help</ContactHandoff>);
    const link = screen.getByRole("link", { name: "Portal help" });
    fireEvent.click(link);
    await waitFor(() => expect(navigateToHandoff).toHaveBeenCalledExactlyOnceWith(link.getAttribute("href")));
    expect(consumer).toHaveBeenCalledTimes(1);
    expect(consumer.mock.calls[0][2].captured).toBe(false);
  });

  it("preserves native modified-click behavior without capture", () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    render(<ContactHandoff topic="general">Contact</ContactHandoff>);
    const link = screen.getByRole("link", { name: "Contact" });
    link.addEventListener("click", (event) => event.preventDefault());
    fireEvent.click(link, { ctrlKey: true });
    expect(fetcher).not.toHaveBeenCalled();
    expect(navigateToHandoff).not.toHaveBeenCalled();
  });

  it("allows a new intentional handoff after returning from WhatsApp through browser history", async () => {
    const fetcher = vi.fn<typeof fetch>().mockImplementation(async () => Response.json({ available: false }, { status: 503 }));
    vi.stubGlobal("fetch", fetcher);
    render(<ContactHandoff topic="general">Contact</ContactHandoff>);
    const link = screen.getByRole("link", { name: "Contact" });
    fireEvent.click(link);
    await waitFor(() => expect(navigateToHandoff).toHaveBeenCalledTimes(1));
    fireEvent(window, new PageTransitionEvent("pageshow", { persisted: true }));
    expect(link).toHaveAttribute("aria-busy", "false");
    fireEvent.click(link);
    await waitFor(() => expect(navigateToHandoff).toHaveBeenCalledTimes(2));
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
