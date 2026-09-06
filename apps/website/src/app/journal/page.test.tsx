import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import JournalPage, { metadata } from "./page";

describe("/journal", () => {
  it("renders one editorial index heading with no local article route", () => {
    render(<JournalPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "The Bali Zero Journal" }),
    ).toBeInTheDocument();
    for (const link of screen.queryAllByRole("link")) {
      const href = link.getAttribute("href") ?? "";
      expect(href.startsWith("/journal/")).toBe(false);
    }
  });

  it("describes the route as a verified index", () => {
    expect(metadata.title).toBe("The Bali Zero Journal");
    expect(metadata.description).toMatch(/verified index/i);
  });
});
