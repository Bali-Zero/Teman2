import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import NewsPage, { metadata } from "./page";

vi.mock("next/server", () => ({ connection: vi.fn(async () => {}) }));
vi.mock("../../lib/server/journal-feed", () => ({
  loadJournalFeed: vi.fn(async () => ({
    status: "empty",
    articles: [],
    rejected: 0,
  })),
}));

describe("public News index", () => {
  it("renders the Journal presentation at its canonical route", async () => {
    render(await NewsPage({}));

    expect(
      screen.getByRole("heading", { level: 1, name: "The Bali Zero Journal" }),
    ).toBeInTheDocument();
  });

  it("publishes a self-canonical title and description", () => {
    expect(metadata).toMatchObject({
      title: "The Bali Zero Journal | Bali Zero",
      alternates: { canonical: "/news" },
    });
    expect(metadata.description).toMatch(/Bali Zero Journal/i);
  });
});
