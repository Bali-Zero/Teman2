import { describe, expect, it, vi } from "vitest";
import { redirect } from "next/navigation";
import LegacyAboutRedirect from "./page";

vi.mock("next/navigation", () => ({
  redirect: vi.fn((destination: string) => {
    throw new Error(`NEXT_REDIRECT:${destination}`);
  }),
}));

describe("legacy About redirect", () => {
  it("temporarily redirects to the canonical About page", () => {
    expect(() => LegacyAboutRedirect()).toThrow("NEXT_REDIRECT:/about");
    expect(redirect).toHaveBeenCalledExactlyOnceWith("/about");
  });
});
