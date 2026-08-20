import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

/**
 * Findability guard for the visa funnel (2026-07-28).
 *
 * TRAUMA: `/visa/voa` shipped on 2026-07-27 — engine, public route, wizard,
 * result page, 107 backend tests — and spent a full day LIVE AND UNREACHABLE:
 * zero inbound links anywhere in `src/`, and absent from this sitemap, which
 * listed its four siblings. Everything about the page worked; nobody could
 * arrive at it. Nothing failed, because nothing was watching for the absence.
 *
 * So this test enumerates the funnel's real static routes from the filesystem
 * and demands each one be either listed in the sitemap or named in
 * INTENTIONALLY_UNLISTED with a reason. A new funnel page fails this test
 * until someone makes that choice deliberately — the point is not to force
 * every page into the sitemap, it is to make omission a decision instead of
 * an oversight.
 *
 * Dynamic `[hash]` result routes are excluded structurally (they are one
 * visitor's ephemeral answer, and they canonicalise to their funnel entry —
 * see visa/voa/layout.tsx), and the innocence case below pins that they never
 * leak into the sitemap.
 */

// Heavy data sources — this test is about route coverage, not content.
// Each of these is consumed inside a try/catch in sitemap.ts, so an empty
// result exercises the static/visa branches without touching the corpus.
vi.mock("@/lib/blog/articles", () => ({
  getAllArticles: vi.fn(async () => []),
  getNoIndexSlugs: vi.fn(async () => []),
}));
vi.mock("@/lib/kbli-data.server", () => ({
  getAllCodes: vi.fn(() => []),
  getSections: vi.fn(() => []),
}));
vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}));

import sitemap from "./sitemap";

const APP_DIR = path.dirname(fileURLToPath(import.meta.url));
const VISA_DIR = path.join(APP_DIR, "visa");
const BASE = "https://balizero.com";

/**
 * Routes that exist under /visa but deliberately stay out of the sitemap.
 * Add here ONLY with a reason — an entry without one is a silent omission
 * wearing a permission slip.
 */
const INTENTIONALLY_UNLISTED: Record<string, string> = {
  "/visa/privacy": "legal boilerplate, no search intent to serve",
  "/visa/terms": "legal boilerplate, no search intent to serve",
};

/** Static (non-dynamic) route paths under /visa, derived from the tree. */
function staticVisaRoutes(): string[] {
  const out: string[] = [];
  const walk = (dir: string, urlPath: string) => {
    if (fs.existsSync(path.join(dir, "page.tsx"))) out.push(urlPath);
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      // `[hash]` / `[...slug]` — dynamic, never enumerable in a sitemap
      if (entry.name.startsWith("[")) continue;
      walk(path.join(dir, entry.name), `${urlPath}/${entry.name}`);
    }
  };
  walk(VISA_DIR, "/visa");
  return out.sort();
}

describe("sitemap — visa funnel findability", () => {
  it("has a route tree to check (the probe can produce a positive)", () => {
    // Guard against the empty-set failure mode: a walk that finds nothing
    // would make every assertion below vacuously true.
    const routes = staticVisaRoutes();
    expect(routes.length).toBeGreaterThanOrEqual(4);
    expect(routes).toContain("/visa/voa");
  });

  it("lists every static visa route, or names it as deliberately unlisted", async () => {
    const urls = new Set((await sitemap()).map((e) => e.url));
    const missing = staticVisaRoutes().filter(
      (r) => !urls.has(`${BASE}${r}`) && !(r in INTENTIONALLY_UNLISTED),
    );
    expect(missing).toEqual([]);
  });

  it("lists /visa/voa specifically (the route this guard was born from)", async () => {
    const urls = (await sitemap()).map((e) => e.url);
    expect(urls).toContain(`${BASE}/visa/voa`);
  });

  it("lists the localized second-home routes (it/id, 2026-08-20)", async () => {
    // /visa/second-home/[locale] is a dynamic segment, excluded structurally
    // from staticVisaRoutes()'s walk (see comment above) — so this is the
    // only guard that would catch these two URLs missing from the sitemap.
    const urls = (await sitemap()).map((e) => e.url);
    expect(urls).toContain(`${BASE}/visa/second-home/it`);
    expect(urls).toContain(`${BASE}/visa/second-home/id`);
  });

  it("does NOT list per-visitor result pages", async () => {
    const urls = (await sitemap()).map((e) => e.url);
    const leaked = urls.filter((u) =>
      /\/visa\/(voa|match|clock)\/[^/]+$/.test(u),
    );
    expect(leaked).toEqual([]);
  });

  it("does not list a route that was deliberately excluded (innocence)", async () => {
    const urls = new Set((await sitemap()).map((e) => e.url));
    for (const excluded of Object.keys(INTENTIONALLY_UNLISTED)) {
      expect(urls.has(`${BASE}${excluded}`)).toBe(false);
    }
  });
});
