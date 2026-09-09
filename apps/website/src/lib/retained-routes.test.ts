import { afterEach, describe, expect, it, vi } from "vitest";
import { publishedEditionHref, retainedPath } from "./retained-routes";
import { retainedImage } from "./retained-assets";
import {
  retainedApiUnavailable,
  retainedHandoff,
} from "./server/retained-handoff";
import {
  legacyOriginForHeaders,
  resolveLegacyOrigin,
} from "./server/legacy-origin";
import { readEditorialJson } from "./server/public-catalog";
import { decodePublicArticle } from "./server/public-editorial";
import {
  safeArticleImage,
  safeArticleUrl,
} from "../components/journal/article-urls";
import { headers } from "next/headers";
import nextConfig from "../../next.config";

vi.mock("next/headers", () => ({
  headers: vi.fn(async () => new Headers({ host: "localhost:3100" })),
}));
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.mocked(headers).mockResolvedValue(new Headers({ host: "localhost:3100" }));
});

const known = [
  "/visa",
  "/visa/privacy",
  "/visa/terms",
  "/visa/match",
  "/visa/match/result_1",
  "/visa/clock",
  "/visa/clock/result_1",
  "/visa/voa",
  "/visa/voa/result_1",
  "/visa/voa/upload/result_1",
  "/visa/voa/checkout/result_1",
  "/visa/voa/orders/order_1",
  "/visa/voa/orders/order_1/return",
  "/visa/voa/auth",
  "/visa/voa/auth/continue",
  "/visa/second-home",
  "/visa/second-home/it",
  "/visa/second-home/id",
  "/visa/second-home/studio",
  "/visa-oracle",
  "/visa-oracle/privacy",
  "/visa-oracle/unlock",
  "/kbli",
  "/kbli/56101",
  "/kbli/builder",
  "/kbli/decoder",
  "/kbli/sectors",
  "/kbli/sectors/food-beverage",
  "/kbli-explorer",
  "/tax-calendar",
  "/taxes/gap",
  "/property/eligibility",
  "/privacy",
  "/terms",
  "/v2/privacy",
  "/v2/terms",
  "/v2/cookies",
  "/v2/company/press",
  "/v2/company/careers",
  "/feed",
  "/book",
  "/book/introduction",
  "/prime",
  "/prime/proposal/result_1",
  "/zoning",
];

describe("explicit retained route inventory", () => {
  it("covers every public retained family and preserves valid result identifiers", () => {
    for (const path of known) expect(retainedPath(path), path).toBe(path);
  });
  it("normalizes only evidenced aliases", () => {
    for (const [from, to] of [
      ["/kbli-navigator/56101", "/kbli/56101"],
      ["/visa-v2", "/visa-oracle"],
      ["/tax/gap", "/taxes/gap"],
      ["/visa/second-home-e33", "/visa/second-home"],
      ["/visa/", "/visa"],
    ])
      expect(retainedPath(from)).toBe(to);
  });
  it("permits explicit secure continuation from native visa results without admitting operations", () => {
    expect(retainedPath("/legacy/visa/voa")).toBe("/visa/voa");
    expect(retainedPath("/legacy/prime")).toBe("/prime");
    for (const product of ["voa", "clock", "match"]) {
      expect(retainedPath(`/legacy/visa/${product}/result_1`)).toBe(
        `/visa/${product}/result_1`,
      );
    }
    for (const path of [
      "/legacy/visa/voa/upload/ref",
      "/legacy/visa/clock/ref/delete",
      "/legacy/visa/match/ref?token=private",
    ])
      expect(retainedPath(path)).toBeNull();
  });
  it("preserves published underscore article identities without admitting path syntax", () => {
    const slug = "news_20260907_173053_1e7fa0d1";
    expect(retainedPath(`/legacy/business/${slug}`)).toBe(`/business/${slug}`);
    expect(publishedEditionHref(`https://balizero.com/business/${slug}`)).toBe(
      `/legacy/business/${slug}`,
    );
    for (const suffix of [
      "a_../secret",
      "a_%2fsecret",
      "a_\\secret",
      "a_?draft=1",
      "a_#fragment",
      "_",
      "_leading",
    ]) {
      expect(retainedPath(`/legacy/business/${suffix}`)).toBeNull();
    }
  });
  it("rejects invented families, invalid IDs, encoded traversal and arbitrary nested operations", () => {
    for (const path of [
      "/visa/result",
      "/sh",
      "/result",
      "/visa/second-home/de",
      "/visa/clock/a/delete",
      "/kbli/1234",
      "/api/private",
      "/legacy/news/admin",
      "/legacy/portal/record",
      "/visa/%2e%2e/portal",
      "/visa//clock",
      "/visa/clock/a%2Fb",
    ])
      expect(retainedPath(path), path).toBeNull();
  });
  it("localizes article-to-tool URLs, preserving result and planning context", () => {
    expect(
      safeArticleUrl(
        "https://balizero.com/visa/second-home/studio?source=article#p=abc",
      ),
    ).toBe("/visa/second-home/studio?source=article#p=abc");
    expect(
      safeArticleUrl("https://balizero.com/visa/clock/result_1?source=guide"),
    ).toBe("/visa/clock/result_1?source=guide");
    expect(
      publishedEditionHref(
        "https://balizero.com/property/leasehold-vs-freehold?lang=it#context",
      ),
    ).toBe("/legacy/property/leasehold-vs-freehold?lang=it#context");
    expect(
      publishedEditionHref(
        "https://foreign.invalid/property/leasehold-vs-freehold",
      ),
    ).toBe("/legacy/news");
  });
  it("maps only evidenced v2 and locale-prefix aliases into current local routes", async () => {
    const redirects = await nextConfig.redirects!();
    for (const [source, destination] of [
      ["/v2", "/"],
      ["/v2/news", "/news"],
      ["/visa/second-home-e33", "/visa/second-home"],
      ["/id/taxes/freelancer-tax-guide", "/taxes/freelancer-tax-guide?lang=id"],
      [
        "/it/tax-for-freelancers-indonesia-2026",
        "/taxes/freelancer-tax-guide?lang=it",
      ],
    ])
      expect(redirects).toContainEqual({
        source,
        destination,
        permanent: true,
      });
    expect(redirects.every((entry) => entry.permanent)).toBe(true);
    expect(
      redirects.every(
        (entry) =>
          entry.destination.startsWith("/") && !entry.source.includes(":path*"),
      ),
    ).toBe(true);
  });
  it("does not attach a global X-Robots-Tag header", async () => {
    const configuredHeaders = nextConfig.headers
      ? await nextConfig.headers()
      : [];
    expect(
      configuredHeaders.some((entry) =>
        entry.headers.some(
          (header) => header.key.toLowerCase() === "x-robots-tag",
        ),
      ),
    ).toBe(false);
  });
});

describe("independent owner boundary", () => {
  it("allows default apex only from local preview", () => {
    expect(resolveLegacyOrigin(["localhost:3100", "127.0.0.1:3100"])).toBe(
      "https://balizero.com",
    );
    for (const host of [
      "balizero.com",
      "www.balizero.com",
      "new-public.example",
      "preview.vercel.app",
    ])
      expect(resolveLegacyOrigin([host]), host).toBeNull();
  });
  it("requires explicit independent legacy and public origins on any public host", () => {
    expect(
      resolveLegacyOrigin(["new-public.example"], {
        legacyOrigin: "https://legacy.example",
      }),
    ).toBeNull();
    expect(
      resolveLegacyOrigin(["new-public.example"], {
        legacyOrigin: "https://legacy.example",
        publicOrigin: "https://new-public.example",
      }),
    ).toBe("https://legacy.example");
    expect(
      resolveLegacyOrigin(["internal-host"], {
        legacyOrigin: "https://new-public.example",
        publicOrigin: "https://new-public.example",
      }),
    ).toBeNull();
  });
  it("rejects canonical aliases and known mouth host redirects", () => {
    for (const legacyOrigin of [
      "https://www.balizero.com",
      "https://balizero.com.",
      "https://visa.balizero.com",
      "https://tax.balizero.com",
      "https://my.balizero.com",
      "https://kita.balizero.com",
      "https://zantara.balizero.com",
      "https://prime.balizero.com",
    ]) {
      expect(
        resolveLegacyOrigin(["balizero.com"], {
          legacyOrigin,
          publicOrigin: "https://balizero.com",
        }),
        legacyOrigin,
      ).toBeNull();
    }
  });
  it("rejects unsafe configured URLs and missing request origin", () => {
    for (const legacyOrigin of [
      "http://legacy.example",
      "https://user:pass@legacy.example",
      "https://legacy.example/api",
      "https://legacy.example?url=x",
      "https://legacy.example#x",
      "https://localhost",
      "https://legacy.example:8080",
      "not a URL",
    ])
      expect(
        resolveLegacyOrigin(["localhost"], { legacyOrigin }),
        legacyOrigin,
      ).toBeNull();
    expect(resolveLegacyOrigin([])).toBeNull();
  });
  it("checks forwarded and actual request hosts instead of trusting loopback behind a proxy", () => {
    expect(
      legacyOriginForHeaders(
        new Headers({
          host: "localhost:3100",
          "x-forwarded-host": "balizero.com",
        }),
        "http://localhost:3100/visa",
      ),
    ).toBeNull();
    vi.stubEnv("WEBSITE_PUBLIC_ORIGIN", "https://new-public.example");
    vi.stubEnv("WEBSITE_LEGACY_ORIGIN", "https://legacy.example");
    expect(
      legacyOriginForHeaders(
        new Headers({
          host: "internal",
          "x-forwarded-host": "new-public.example, legacy.example",
        }),
      ),
    ).toBeNull();
  });
  it("preserves query, results and fragments in a no-store/no-referrer 307", () => {
    const response = retainedHandoff(
      new Request(
        "http://localhost:3100/visa/second-home/studio?source=guide&source=home#p=synthetic",
      ),
    );
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "https://balizero.com/visa/second-home/studio?source=guide&source=home#p=synthetic",
    );
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(response.headers.get("referrer-policy")).toBe("no-referrer");
    expect(response.headers.has("set-cookie")).toBe(false);
  });
  it("fails closed with a useful token-free page and never sends requests", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const response = retainedHandoff(
      new Request(
        "https://balizero.com/visa/voa/auth?magic_token=SYNTHETIC_PRIVATE_TOKEN&result_id=fixture",
      ),
    );
    expect(response.status).toBe(503);
    const body = await response.text();
    expect(body).toContain('href="/contact"');
    expect(body).not.toMatch(
      /SYNTHETIC_PRIVATE_TOKEN|magic_token|result_id|analytics|<script/,
    );
    expect(response.headers.has("location")).toBe(false);
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("does not submit POST payloads or use arbitrary fallback catchalls", () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const response = retainedHandoff(
      new Request("http://localhost:3100/visa/voa/auth/exchange", {
        method: "POST",
        body: "SYNTHETIC_BODY",
      }),
    );
    expect(response.status).toBe(405);
    expect(response.headers.get("allow")).toBe("GET, HEAD");
    expect(
      retainedHandoff(
        new Request("http://localhost:3100/visa/private/operation"),
      ).status,
    ).toBe(404);
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("keeps known product APIs unavailable on marketing, with unknown operations 404", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    for (const path of [
      "/api/visa/clock/fixture",
      "/api/visa/voa/orders/fixture/browser-return-observations",
      "/api/visa/voa/eligibility-checks/fixture/documents",
      "/api/property/analyze",
      "/api/v1/visa-oracle/chat",
      "/api/tax-calendar/ical",
      "/api/blog/newsletter/confirm",
    ]) {
      const request = new Request(`http://localhost:3100${path}`, {
        method: "POST",
        body: "SYNTHETIC_BODY",
      });
      const response = retainedApiUnavailable(request);
      expect(response.status, path).toBe(503);
      expect(request.bodyUsed).toBe(false);
      expect(await response.json()).toMatchObject({
        code: "PRODUCT_OWNER_REQUIRED",
      });
    }
    expect(
      retainedApiUnavailable(
        new Request("http://localhost:3100/api/admin/delete"),
      ).status,
    ).toBe(404);
    expect(
      await retainedApiUnavailable(
        new Request("http://localhost:3100/api/visa/clock", { method: "HEAD" }),
      ).text(),
    ).toBe("");
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("refuses same-host editorial reads even after a public hostname change", async () => {
    vi.stubEnv("WEBSITE_PUBLIC_ORIGIN", "https://new-public.example");
    vi.stubEnv("WEBSITE_LEGACY_ORIGIN", "https://new-public.example");
    vi.mocked(headers).mockResolvedValue(
      new Headers({ host: "new-public.example" }),
    );
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    await expect(readEditorialJson("/api/blog/articles")).rejects.toThrow(
      "Independent editorial owner unavailable",
    );
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("never follows an upstream redirect back into the public application", async () => {
    const fetcher = vi.fn(async (_input: string, init: RequestInit) => {
      expect(init.redirect).toBe("error");
      throw new TypeError("Upstream redirect rejected by fetch");
    });
    vi.stubGlobal("fetch", fetcher);
    await expect(readEditorialJson("/api/blog/articles")).rejects.toThrow(
      "Upstream redirect rejected",
    );
    expect(fetcher).toHaveBeenCalledOnce();
  });
});

describe("retained published assets", () => {
  it("preserves source evidence while using the guarded local asset route", () => {
    expect(retainedImage("https://balizero.com/static/news/story.jpg")).toEqual(
      {
        src: "/legacy/static/news/story.jpg",
        sourceSrc: "https://balizero.com/static/news/story.jpg",
      },
    );
    expect(safeArticleImage("/static/insights/property/villa.jpg")).toBe(
      "/legacy/static/insights/property/villa.jpg",
    );
    expect(safeArticleImage("/static/blog/kitas-guide.jpg")).toBe(
      "/legacy/static/blog/kitas-guide.jpg",
    );
    expect(
      retainedHandoff(
        new Request("http://localhost:3100/legacy/static/news/story.jpg"),
      ).headers.get("location"),
    ).toBe("https://balizero.com/static/news/story.jpg");
  });
  it("rejects non-image operations, foreign hosts, traversal, encoded segments and request context", () => {
    for (const value of [
      "https://foreign.invalid/static/news/story.jpg",
      "/static/news/../story.jpg",
      "/static/news/%2e%2e/story.jpg",
      "/static/news/..%2Fstory.jpg",
      "/static/news/story.svg",
      "/static/news/script.js",
      "/static/private/story.jpg",
      "/static/news/story.jpg?token=fixture",
      "/static/news/story.jpg#fragment",
    ])
      expect(retainedImage(value), value).toBeNull();
    expect(
      retainedHandoff(
        new Request(
          "http://localhost:3100/legacy/static/news/story.jpg?token=fixture",
        ),
      ).status,
    ).toBe(404);
  });
  it("fails safely on the future public host and keeps articles readable without invalid images", () => {
    expect(
      retainedHandoff(
        new Request("https://balizero.com/legacy/static/news/story.jpg"),
      ).status,
    ).toBe(503);
    const result = decodePublicArticle(
      {
        category: "business",
        slug: "published-story",
        status: "published",
        noIndex: false,
        title: "Published story",
        content: "Owned body.",
        publishedAt: "2026-01-02",
        coverImage: "/static/news/script.js",
      },
      "business",
      "published-story",
    );
    expect(result?.metadata.image).toBeNull();
    expect(result?.markdown).toBe("Owned body.");
  });
});
