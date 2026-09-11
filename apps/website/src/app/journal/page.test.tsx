import { describe, expect, it, vi } from "vitest";
import { permanentRedirect } from "next/navigation";
import JournalRedirect from "./page";

vi.mock("next/navigation", () => ({
  permanentRedirect: vi.fn((destination: string) => {
    throw new Error(`NEXT_PERMANENT_REDIRECT:${destination}`);
  }),
}));

describe("legacy Journal redirect", () => {
  it("permanently redirects to News while preserving supported query values", async () => {
    await expect(
      JournalRedirect({
        searchParams: Promise.resolve({
          category: "taxes",
          q: "company tax",
          page: "2",
          utm_source: "newsletter",
          gclid: "abc123",
          ignored: "private",
        }),
      }),
    ).rejects.toThrow(
      "NEXT_PERMANENT_REDIRECT:/news?category=taxes&q=company+tax&page=2&utm_source=newsletter&gclid=abc123",
    );
    expect(permanentRedirect).toHaveBeenCalledExactlyOnceWith(
      "/news?category=taxes&q=company+tax&page=2&utm_source=newsletter&gclid=abc123",
    );
  });
});
