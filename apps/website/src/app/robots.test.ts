import { afterEach, describe, expect, it, vi } from "vitest";
import robots from "./robots";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("environment-bound robots policy", () => {
  it("blocks every crawler and omits the sitemap in preview", () => {
    vi.stubEnv("WEBSITE_PUBLIC_ORIGIN", "");

    expect(robots()).toEqual({
      rules: { userAgent: "*", disallow: "/" },
    });
  });

  it("allows public content while protecting production-only paths", () => {
    vi.stubEnv("WEBSITE_PUBLIC_ORIGIN", "https://www.example.com/");

    expect(robots()).toEqual({
      rules: {
        userAgent: "*",
        allow: [
          "/",
          "/_next/static/",
          "/_next/image",
          "/llms.txt",
          "/llms-full.txt",
          "/llms-id.txt",
        ],
        disallow: [
          "/api/",
          "/_next/",
          "/*?tag=",
          "/*&tag=",
          "/dashboard",
          "/clients",
          "/chat",
          "/settings",
          "/analytics",
          "/intelligence",
          "/whatsapp",
          "/email",
          "/documents",
          "/knowledge",
          "/cases",
          "/omnichannel",
          "/admin",
          "/login",
          "/portal/login",
          "/portal/login-upgraded",
          "/legacy/",
          "/visa-oracle/unlock",
        ],
      },
      sitemap: "https://www.example.com/sitemap.xml",
    });
  });
});
