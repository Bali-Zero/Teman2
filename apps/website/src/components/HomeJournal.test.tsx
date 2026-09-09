import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { connection } from "next/server";
import { loadJournalFeed } from "../lib/server/journal-feed";
import { HomeJournal, JournalPending } from "./HomeJournal";

vi.mock("next/server", () => ({ connection: vi.fn(async () => {}) }));
vi.mock("../lib/server/journal-feed", () => ({ loadJournalFeed: vi.fn(async () => ({ status: "empty", articles: [], rejected: 0 })) }));

describe("request-time editorial island", () => {
  beforeEach(() => vi.clearAllMocks());
  it("waits for a real request before reading publication status", async () => {
    let release!: () => void;
    vi.mocked(connection).mockImplementationOnce(() => new Promise<void>((resolve) => { release = resolve; }));
    const pending = HomeJournal();
    expect(loadJournalFeed).not.toHaveBeenCalled();
    release();
    await pending;
    expect(loadJournalFeed).toHaveBeenCalledExactlyOnceWith({ home: true });
  });
  it("renders only the fresh verified feed, including an empty publication", async () => {
    const node = await HomeJournal();
    expect(node.props.articles).toEqual([]);
    expect(node.props.status).toBe("empty");
    expect(node.props.fixture).toBe(false);
  });
  it("offers an honest pending state and a separate Journal route", () => {
    render(<JournalPending />);
    expect(screen.getByRole("status")).toHaveTextContent("Checking the latest published stories");
    expect(screen.getByRole("link", { name: /Explore the Journal/ })).toHaveAttribute("href", "/journal");
    expect(document.getElementById("journal")).toHaveAttribute("aria-busy", "true");
  });
});
