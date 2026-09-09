import { describe, expect, it, vi } from "vitest";
import { permanentRedirect } from "next/navigation";
import Page from "./page";

vi.mock("next/navigation", () => ({
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
  redirect: vi.fn((destination: string) => {
    throw new Error(`NEXT_TEMPORARY_REDIRECT:${destination}`);
  }),
  permanentRedirect: vi.fn((destination: string) => {
    throw new Error(`NEXT_PERMANENT_REDIRECT:${destination}`);
  }),
}));

describe("legacy KBLI Navigator redirect", () => {
  it("permanently redirects a retained path and preserves query values", async () => {
    await expect(
      Page({
        params: Promise.resolve({ retainedPath: ["sectors", "A"] }),
        searchParams: Promise.resolve({ q: "food", lang: ["en", "id"] }),
      }),
    ).rejects.toThrow(
      "NEXT_PERMANENT_REDIRECT:/kbli/sectors/A?q=food&lang=en&lang=id",
    );
    expect(permanentRedirect).toHaveBeenCalledExactlyOnceWith(
      "/kbli/sectors/A?q=food&lang=en&lang=id",
    );
  });
});
