import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { assistantContactContext } from "../lib/destinations/contact-context";
import { ContactOptions } from "./ContactOptions";

const originalUrl = window.location.href;
const originalState: unknown = window.history.state;
afterEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState(originalState, "", originalUrl);
});

describe("contact topic continuity", () => {
  it("lets the assistant read a changed topic with the original safe source", async () => {
    const routerState = { retainedRouterState: "synthetic" };
    window.history.replaceState(routerState, "", "/contact?topic=tax&from=team&private=discarded#discarded");
    render(<ContactOptions initialTopic="tax" sourcePage="/team" />);

    await userEvent.setup().selectOptions(screen.getByRole("combobox"), "property");

    const nextUrl = new URL(window.location.href);
    expect(assistantContactContext(nextUrl)).toEqual({ topic: "property", source: "/team" });
    expect([...nextUrl.searchParams.entries()]).toEqual([["topic", "property"], ["from", "/team"]]);
    expect(nextUrl.hash).toBe("");
    expect(window.history.state).toEqual(routerState);
    const href = screen.getByRole("link", { name: /Continue on WhatsApp/ }).getAttribute("href")!;
    expect(new URL(href).searchParams.get("text")).toContain("property due diligence (from /team)");
  });

  it.each(["/", "/about", "/services/immigration", "/services/company-setup", "/services/tax", "/services/property", "/contact"])("keeps the exact allowed source %s when the topic changes", async (source) => {
    window.history.replaceState(null, "", `/contact?topic=general&from=${encodeURIComponent(source)}`);
    render(<ContactOptions initialTopic="general" sourcePage={source} />);
    await userEvent.setup().selectOptions(screen.getByRole("combobox"), "property");
    expect(assistantContactContext(new URL(window.location.href))).toEqual({ topic: "property", source });
  });

  it("updates the Home contact controls without changing Home navigation or query", async () => {
    window.history.replaceState(null, "", "/?campaign=retained#contact");
    const before = window.location.href;
    const replaceState = vi.spyOn(window.history, "replaceState");
    render(<ContactOptions initialTopic="general" sourcePage="/" />);
    await userEvent.setup().selectOptions(screen.getByRole("combobox"), "property");
    expect(window.location.href).toBe(before);
    expect(replaceState).not.toHaveBeenCalled();
    const href = screen.getByRole("link", { name: /Continue on WhatsApp/ }).getAttribute("href")!;
    expect(new URL(href).searchParams.get("text")).toContain("property due diligence (from /)");
  });
});
