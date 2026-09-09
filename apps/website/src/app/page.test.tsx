import { existsSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import Home from "./page";

vi.mock("../components/HomeJournal", () => ({
  HomeJournal: () => { throw new Promise(() => {}); },
  JournalPending: () => <section id="journal" role="status">Checking the latest published stories…</section>,
}));

describe("homepage integration", () => {
  it("renders company, contact and tools while editorial verification remains pending", () => {
    expect(Home()).not.toBeInstanceOf(Promise);
    render(Home());
    expect(screen.getByRole("status")).toHaveTextContent("Checking the latest");
    expect(document.getElementById("contact")).toBeVisible();
    expect(document.getElementById("tools")).toBeVisible();
    expect(document.getElementById("team")).toBeVisible();
    expect(screen.getByText("Jalan Raya Anyar n.2, Kerobokan, Bali")).toBeVisible();
  });
  it("connects every internal journey to an existing unique destination", async () => {
    const { container } = render(Home());
    const ids = [...container.querySelectorAll("[id]")].map((el) => el.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const link of container.querySelectorAll('a[href^="#"]')) {
      expect(ids).toContain(link.getAttribute("href")!.slice(1));
    }
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    screen.getByRole("main").focus();
    expect(screen.getByRole("main")).toHaveFocus();
  });

  it("ships every referenced portrait and illustration and excludes removed members", async () => {
    const { container } = render(await Home());
    for (const image of container.querySelectorAll("img")) {
      const src = image.getAttribute("src")!;
      expect(src.startsWith("/assets/")).toBe(true);
      expect(existsSync(join(process.cwd(), "public", src))).toBe(true);
    }
    expect(container.textContent).not.toMatch(/Faysha|Fayisha|Sahira/i);
  });
});
