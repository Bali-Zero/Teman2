import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Contact } from "./Contact";
import ContactPage from "../app/contact/page";

describe("contact journeys", () => {
  it("provides verified office information and an accessible contextual handoff", async () => {
    const user = userEvent.setup();
    render(<Contact />);
    expect(screen.getByText("Jalan Raya Anyar n.2, Kerobokan, Bali")).toBeVisible();
    expect(screen.getByText(/Monday–Friday, 09:00–17:00 WITA/)).toBeVisible();
    expect(screen.getByText(/Office visits by appointment/)).toBeVisible();
    await user.selectOptions(screen.getByRole("combobox", { name: /What would you/ }), "tax");
    const href = screen.getByRole("link", { name: /Continue on WhatsApp/ }).getAttribute("href")!;
    expect(new URL(href).searchParams.get("text")).toContain("tax and accounting (from /)");
    expect(new URL(screen.getByRole("link", { name: /Write an email/ }).getAttribute("href")!).searchParams.get("subject")).toContain("Tax & accounting");
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("retains the team topic and offers existing-client recovery", async () => {
    render(await ContactPage({ searchParams: Promise.resolve({ topic: "portal", from: "team" }) }));
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("combobox")).toHaveValue("portal");
    expect(new URL(screen.getByRole("link", { name: /Continue on WhatsApp/ }).getAttribute("href")!).searchParams.get("text")).toContain("(from /team)");
    expect(screen.getByRole("link", { name: /Open my client portal/ })).toHaveAttribute("href", "https://my.balizero.com/");
  });

  it("does not echo arbitrary topics, array values or source text from the URL", async () => {
    const { container } = render(await ContactPage({ searchParams: Promise.resolve({ topic: ["untrusted-input"], from: "https://untrusted.example/person" }) }));
    expect(screen.getByRole("combobox")).toHaveValue("general");
    expect(container.innerHTML).not.toContain("untrusted");
    expect(new URL(screen.getByRole("link", { name: /Continue on WhatsApp/ }).getAttribute("href")!).searchParams.get("text")).toContain("(from /contact)");
  });
});
