import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MobileNav } from "./MobileNav";

vi.mock("@balizero/core/analytics", () => ({ trackFunnelEvent: vi.fn() }));
vi.mock("@balizero/core/auth", () => ({
  getOrCreateSessionId: () => "test-session",
}));

vi.stubGlobal(
  "matchMedia",
  vi.fn(() => ({
    matches: false,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })),
);
afterEach(cleanup);
const items = [{ label: "Services", href: "#services" }];

describe("MobileNav keyboard navigation", () => {
  it("keeps the closed drawer out of the accessibility tree", () => {
    render(<MobileNav items={items} funnel="home" />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Services" }),
    ).not.toBeInTheDocument();
  });

  it("moves focus inside, closes on Escape, and restores trigger focus", async () => {
    render(<MobileNav items={items} funnel="home" />);
    const trigger = screen.getByRole("button", { name: "Open menu" });
    trigger.focus();
    fireEvent.click(trigger);
    const dialog = await screen.findByRole("dialog", {
      name: "Navigation menu",
    });
    await waitFor(() =>
      expect(dialog.contains(document.activeElement)).toBe(true),
    );
    fireEvent.keyDown(document.activeElement!, { key: "Escape" });
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    await waitFor(() => expect(trigger).toHaveFocus());
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });

  it("keeps Tab and Shift+Tab inside the open drawer", async () => {
    render(<MobileNav items={items} funnel="home" />);
    fireEvent.click(screen.getByRole("button", { name: "Open menu" }));
    const first = await screen.findByRole("button", { name: "Close menu" });
    const last = screen.getByRole("link", { name: "Login" });
    last.focus();
    fireEvent.keyDown(last, { key: "Tab" });
    expect(first).toHaveFocus();
    fireEvent.keyDown(first, { key: "Tab", shiftKey: true });
    expect(last).toHaveFocus();
  });

  it("closes when a navigation destination is selected", async () => {
    render(<MobileNav items={items} funnel="home" />);
    fireEvent.click(screen.getByRole("button", { name: "Open menu" }));
    fireEvent.click(await screen.findByRole("link", { name: "Services" }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
  });
});
