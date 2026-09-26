import { describe, expect, it } from "vitest";
import type { ArticleListItem } from "@/lib/blog/types";
import { selectJournalArticles } from "./adapter";

function story(slug: string, date = "2026-09-25T02:00:00Z"): ArticleListItem {
  return {
    slug,
    title: "Synthetic story",
    category: "business",
    coverImage: "/static/blog/bali-skyline.jpg",
    publishedAt: new Date(date),
  } as ArticleListItem;
}
describe("R19 Journal existing-reader adapter", () => {
  it("honours pinned slots and fills missing ones without duplicate stories", () => {
    const rows = selectJournalArticles(
      [story("new"), story("pinned"), story("other")],
      { hero_main: "pinned", hero_2: "gone", latest_1: "pinned" },
    );
    expect(rows.map((row) => row.slug)).toEqual(["pinned", "new", "other"]);
  });
  it("preserves canonical article routes and supplied images", () => {
    const [row] = selectJournalArticles([story("example")], {});
    expect(row.localHref).toBe("/business/example");
    expect(row.image?.src).toBe("/static/blog/bali-skyline.jpg");
  });
  it("does not invent dates or stories", () => {
    expect(selectJournalArticles([], {})).toEqual([]);
    expect(
      selectJournalArticles([story("invalid", "invalid")], {})[0].date,
    ).toBeNull();
  });
  it("skips an unknown category without hiding healthy articles or consuming a slot", () => {
    const invalid = {
      ...story("malformed"),
      category: "unknown-category",
    } as unknown as ArticleListItem;
    const rows = selectJournalArticles(
      [invalid, story("healthy")],
      { hero_main: "malformed" },
      1,
    );
    expect(rows.map((row) => row.slug)).toEqual(["healthy"]);
    expect(rows[0].destinationStatus).toBe("available");
  });
  it("caps the visible edition after deduplication", () => {
    expect(
      selectJournalArticles(
        Array.from({ length: 12 }, (_, i) => story("story-" + i)),
        {},
        7,
      ),
    ).toHaveLength(7);
  });
});
