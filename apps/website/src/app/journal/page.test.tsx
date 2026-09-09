import { describe, expect, it, vi } from "vitest";
import { redirect } from "next/navigation";
import JournalRedirect from "./page";

vi.mock("next/navigation", () => ({
  redirect: vi.fn((destination: string) => {
    throw new Error(`NEXT_REDIRECT:${destination}`);
  }),
}));

describe("legacy Journal redirect", () => {
  it("temporarily redirects to News while preserving supported query values", async () => {
    await expect(
      JournalRedirect({
        searchParams: Promise.resolve({
          category: "taxes",
          q: "company tax",
          page: "2",
          ignored: "private",
        }),
      }),
    ).rejects.toThrow(
      "NEXT_REDIRECT:/news?category=taxes&q=company+tax&page=2",
    );
    expect(redirect).toHaveBeenCalledExactlyOnceWith(
      "/news?category=taxes&q=company+tax&page=2",
    );
  });
});
