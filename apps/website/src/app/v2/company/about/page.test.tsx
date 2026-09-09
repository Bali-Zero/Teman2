import { describe, expect, it, vi } from "vitest";
import { permanentRedirect } from "next/navigation";
import LegacyAboutRedirect from "./page";

vi.mock("next/navigation", () => ({
  permanentRedirect: vi.fn((destination: string) => {
    throw new Error(`NEXT_PERMANENT_REDIRECT:${destination}`);
  }),
}));

describe("legacy About redirect", () => {
  it("permanently redirects to the canonical About page", () => {
    expect(() => LegacyAboutRedirect()).toThrow(
      "NEXT_PERMANENT_REDIRECT:/about",
    );
    expect(permanentRedirect).toHaveBeenCalledExactlyOnceWith("/about");
  });
});
