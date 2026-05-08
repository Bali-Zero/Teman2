import { describe, expect, it } from "vitest";

import robots from "./robots";

describe("robots metadata route", () => {
  it("allows public discovery assets while blocking private workspace and API paths", () => {
    const config = robots();
    const rule = Array.isArray(config.rules) ? config.rules[0] : config.rules;

    expect(config.sitemap).toBe("https://balizero.com/sitemap.xml");
    expect(rule.userAgent).toBe("*");
    expect(rule.allow).toEqual([
      "/",
      "/llms.txt",
      "/llms-full.txt",
      "/llms-id.txt",
    ]);
    expect(rule.disallow).toEqual(
      expect.arrayContaining([
        "/dashboard",
        "/clients",
        "/chat",
        "/admin",
        "/api/",
        "/_next/",
      ]),
    );
  });
});
