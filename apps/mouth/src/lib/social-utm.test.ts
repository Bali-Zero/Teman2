import { describe, it, expect } from "vitest";
import { buildSocialCTA } from "./social-utm";

describe("buildSocialCTA", () => {
  it("builds a URL with all 4 required UTM params for instagram", () => {
    const url = buildSocialCTA({
      baseUrl: "https://visa.balizero.com/",
      channel: "instagram",
      contentId: "post-20260422-kitas",
      campaign: "kitas-apr26",
    });
    expect(url).toContain("utm_source=instagram");
    expect(url).toContain("utm_medium=social");
    expect(url).toContain("utm_campaign=kitas-apr26");
    expect(url).toContain("utm_content=post-20260422-kitas");
    expect(url).not.toContain("undefined");
    expect(url).not.toContain("?&");
  });

  it("maps newsletter to medium=email", () => {
    const url = buildSocialCTA({
      baseUrl: "https://balizero.com/pricing",
      channel: "newsletter",
      contentId: "nl-20260422",
      campaign: "monthly-digest",
    });
    expect(url).toContain("utm_medium=email");
    expect(url).not.toContain("utm_medium=social");
  });

  it("maps blog/podcast/quora/reddit to medium=referral", () => {
    for (const channel of ["blog", "podcast", "quora", "reddit"] as const) {
      const url = buildSocialCTA({
        baseUrl: "https://x.com/",
        channel,
        contentId: "c1",
        campaign: "c1",
      });
      expect(url).toContain("utm_medium=referral");
    }
  });

  it("rejects empty contentId", () => {
    expect(() =>
      buildSocialCTA({
        baseUrl: "https://x.com/",
        channel: "instagram",
        contentId: "",
        campaign: "ok",
      }),
    ).toThrow(/contentId is required/);
  });

  it("rejects empty campaign", () => {
    expect(() =>
      buildSocialCTA({
        baseUrl: "https://x.com/",
        channel: "instagram",
        contentId: "ok",
        campaign: "  ",
      }),
    ).toThrow(/campaign is required/);
  });

  it("rejects missing baseUrl", () => {
    expect(() =>
      buildSocialCTA({
        baseUrl: "",
        channel: "instagram",
        contentId: "a",
        campaign: "b",
      }),
    ).toThrow(/baseUrl is required/);
  });

  it("preserves existing query params in baseUrl", () => {
    const url = buildSocialCTA({
      baseUrl: "https://visa.balizero.com/?ref=existing",
      channel: "linkedin",
      contentId: "li-001",
      campaign: "oct26",
    });
    expect(url).toContain("ref=existing");
    expect(url).toContain("utm_source=linkedin");
  });

  it("appends utm_term when provided", () => {
    const url = buildSocialCTA({
      baseUrl: "https://visa.balizero.com/",
      channel: "tiktok",
      contentId: "tt-001",
      campaign: "kitas-apr26",
      term: "retirement-visa",
    });
    expect(url).toContain("utm_term=retirement-visa");
  });
});
