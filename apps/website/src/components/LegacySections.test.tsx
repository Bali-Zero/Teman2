import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import AboutPage from "../app/about/page";
import { Footer } from "./Footer";
import { Reviews } from "./Reviews";
import { ZantaraEntry } from "./ZantaraEntry";

describe("legacy section journeys", () => {
  it("keeps review attribution on its public source without inventing testimonials", () => {
    render(<Reviews />);
    expect(
      screen.getByRole("link", { name: /Google Reviews/ }),
    ).toHaveAttribute("href", "https://maps.app.goo.gl/whiMUTNchcDR5naz8");
    expect(screen.queryByRole("blockquote")).not.toBeInTheDocument();
    expect(
      screen.getByText("Opens the public Google profile"),
    ).toBeInTheDocument();
  });

  it("makes About reachable locally and uses homepage anchors from inner pages", () => {
    render(<Footer />);
    expect(screen.getByRole("link", { name: "Our story" })).toHaveAttribute(
      "href",
      "/about",
    );
    expect(screen.getByRole("link", { name: "Our tools" })).toHaveAttribute(
      "href",
      "/#tools",
    );
    expect(screen.getByRole("link", { name: "E-VOA" })).toHaveAttribute(
      "href",
      "/#evoa",
    );
    expect(
      screen.queryByRole("link", { name: /Telegram/i }),
    ).not.toBeInTheDocument();
  });

  it("provides the company story, existing founders and next steps", () => {
    render(<AboutPage />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(
      screen.getByRole("heading", { name: "A clearer way to get started." }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Meet our team/ })).toHaveAttribute(
      "href",
      "/team",
    );
    expect(
      screen.getByRole("link", { name: /Read the Journal/ }),
    ).toHaveAttribute("href", "/news");
  });

  it("opens an honest assistant state with usable contacts and returns focus on close", async () => {
    const user = userEvent.setup();
    render(<ZantaraEntry />);
    const panel = document.querySelector("dialog")!;
    const open = vi.fn(() => panel.setAttribute("open", ""));
    const close = vi.fn(() => {
      panel.removeAttribute("open");
      fireEvent(panel, new Event("close"));
    });
    panel.showModal = open;
    panel.close = close;
    const trigger = screen.getByRole("button", { name: "Zantara" });
    await user.click(trigger);
    expect(open).toHaveBeenCalledOnce();
    expect(screen.getByRole("dialog", { name: "Zantara" })).toBeInTheDocument();
    expect(
      screen.getByText("Chat unavailable in this preview"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Continue on WhatsApp/ }),
    ).toHaveAttribute(
      "href",
      expect.stringContaining("https://wa.me/628213454721?text="),
    );
    await user.click(screen.getByRole("button", { name: "Close Zantara" }));
    expect(close).toHaveBeenCalledOnce();
    expect(trigger).toHaveFocus();
  });
});
