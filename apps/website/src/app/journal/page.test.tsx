import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import JournalPage, { metadata } from "./page";

vi.mock("next/server", () => ({ connection: vi.fn(async () => {}) }));
vi.mock("../../lib/server/journal-feed", () => ({ loadJournalFeed: vi.fn(async () => ({ status: "empty", articles: [], rejected: 0 })) }));

describe("/journal", () => {
  it("renders one editorial index heading with no local article route", async () => {
    render(await JournalPage({}));

    expect(
      screen.getByRole("heading", { level: 1, name: "The Bali Zero Journal" }),
    ).toBeInTheDocument();
    for (const link of screen.queryAllByRole("link")) {
      const href = link.getAttribute("href") ?? "";
      expect(href.startsWith("/journal/")).toBe(false);
    }
  });

  it("describes the Magazine publication index", () => {
    expect(metadata.title).toBe("The Bali Zero Journal");
    expect(metadata.description).toMatch(/Bali Zero Journal/i);
  });
});
