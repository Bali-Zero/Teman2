import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

/**
 * Deliberate-publication guard for the visa funnel (2026-07-28).
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
 * Dynamic `[hash]` result routes are excluded structurally. GARUDA VOA is now
 * an internal-only admin tool; its old public route remains a 404 tombstone
 * and is deliberately excluded below so it cannot regain search discovery by
 * accident.
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
import { GET as getVoaTombstone } from "./visa/voa/route";
import { GET as getVoaResultTombstone } from "./visa/voa/[hash]/route";

const APP_DIR = path.dirname(fileURLToPath(import.meta.url));
const VISA_DIR = path.join(APP_DIR, "visa");
// `(visa-oracle)` is a Next.js route GROUP — it contributes nothing to the
// URL, unlike `/visa` above, so walks starting here must anchor the URL
// prefix at "/visa-oracle" directly, not at the group's directory name.
const VISA_ORACLE_DIR = path.join(APP_DIR, "(visa-oracle)", "visa-oracle");
const PUBLIC_API_SCHEMA = path.join(APP_DIR, "..", "lib", "api", "schema.d.ts");
const LOCALES_DIR = path.join(APP_DIR, "..", "i18n", "locales");
const BASE = "https://balizero.com";

/**
 * Routes that exist under /visa but deliberately stay out of the sitemap.
 * Add here ONLY with a reason — an entry without one is a silent omission
 * wearing a permission slip.
 */
const INTENTIONALLY_UNLISTED: Record<string, string> = {
  "/visa/privacy": "legal boilerplate, no search intent to serve",
  "/visa/terms": "legal boilerplate, no search intent to serve",
  "/visa/voa":
    "retired public route; GARUDA VOA is an internal-only admin tool",
  "/visa":
    "retired public route (Owner ruling #4, 2026-08-25); 301s to " +
    "/visa-oracle in next.config.ts",
  "/visa/match":
    "retired public route (Owner ruling #4, 2026-08-25); 301s to " +
    "/visa-oracle in next.config.ts",
};

/**
 * Every static route under /visa-oracle is deliberately unlisted: the engine
 * is SHADOW (verdicts are not authoritative) and DPIA §8 is unsigned (#4591,
 * 2026-08-23) — the layout's `robots: { index: false, follow: false }` is
 * what keeps it out of search, and a sitemap entry would fight that directly.
 * Ratification conditions are recorded in apps/mouth/src/app/(visa-oracle)/
 * visa-oracle/layout.tsx; when they are met, both that noindex AND this
 * exclusion need to move together, not just one of them.
 */
const INTENTIONALLY_UNLISTED_VISA_ORACLE: Record<string, string> = {
  "/visa-oracle": "SHADOW engine, DPIA §8 unsigned — see #4591",
  "/visa-oracle/privacy": "policy for a SHADOW/unratified tool — see #4591",
  "/visa-oracle/unlock":
    "internal team-only PIN gate, reached by URL, never linked publicly",
};

/** Static (non-dynamic) route paths under `dir`, URL-rooted at `urlPrefix`. */
function staticRoutesUnder(dir: string, urlPrefix: string): string[] {
  const out: string[] = [];
  const walk = (currentDir: string, urlPath: string) => {
    if (
      fs.existsSync(path.join(currentDir, "page.tsx")) ||
      fs.existsSync(path.join(currentDir, "route.ts"))
    ) {
      out.push(urlPath);
    }
    for (const entry of fs.readdirSync(currentDir, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      // `[hash]` / `[...slug]` — dynamic, never enumerable in a sitemap
      if (entry.name.startsWith("[")) continue;
      walk(path.join(currentDir, entry.name), `${urlPath}/${entry.name}`);
    }
  };
  walk(dir, urlPrefix);
  return out.sort();
}

/** Static (non-dynamic) route paths under /visa, derived from the tree. */
function staticVisaRoutes(): string[] {
  return staticRoutesUnder(VISA_DIR, "/visa");
}

/** Static (non-dynamic) route paths under /visa-oracle, derived from the tree. */
function staticVisaOracleRoutes(): string[] {
  return staticRoutesUnder(VISA_ORACLE_DIR, "/visa-oracle");
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

  it("does not list the retired public GARUDA VOA route", async () => {
    const urls = (await sitemap()).map((e) => e.url);
    expect(urls).not.toContain(`${BASE}/visa/voa`);
  });

  it("keeps both retired GARUDA public pages as real 404 route handlers", async () => {
    expect(fs.existsSync(path.join(VISA_DIR, "voa", "page.tsx"))).toBe(false);
    expect(
      fs.existsSync(path.join(VISA_DIR, "voa", "[hash]", "page.tsx")),
    ).toBe(false);
    const entry = fs.readFileSync(
      path.join(VISA_DIR, "voa", "route.ts"),
      "utf8",
    );
    const result = fs.readFileSync(
      path.join(VISA_DIR, "voa", "[hash]", "route.ts"),
      "utf8",
    );
    expect(entry).toContain('dynamic = "force-dynamic"');
    expect(result).toContain('dynamic = "force-dynamic"');
    expect(`${entry}\n${result}`).not.toContain("AppShareBar");
    expect(`${entry}\n${result}`).not.toContain("/api/visa/voa");

    for (const response of [getVoaTombstone(), getVoaResultTombstone()]) {
      expect(response.status).toBe(404);
      expect(response.headers.get("cache-control")).toContain("no-store");
      expect(response.headers.get("x-robots-tag")).toBe("noindex, nofollow");
      expect(await response.text()).toBe("Not Found\n");
    }
  });

  it("has no canonical, OpenGraph, or indexable metadata for GARUDA", () => {
    const layout = fs.readFileSync(
      path.join(VISA_DIR, "voa", "layout.tsx"),
      "utf8",
    );
    expect(layout).not.toContain("canonical");
    expect(layout).not.toContain("openGraph");
    expect(layout).toContain("index: false");
    expect(layout).toContain("follow: false");
  });

  it("has no public inbound link to GARUDA from the visa landing page", () => {
    const landing = fs.readFileSync(path.join(VISA_DIR, "page.tsx"), "utf8");
    expect(landing).not.toContain('href="/visa/voa"');
  });

  it("keeps GARUDA out of the checked-in public API client contract", () => {
    const schema = fs.readFileSync(PUBLIC_API_SCHEMA, "utf8");
    for (const retiredMarker of [
      '"/api/visa/voa"',
      '"/api/visa/voa/{hash}"',
      "VoaRequest",
      "VoaResponse",
      'CaseType: "issuance" | "extension"',
      "backend__services__garuda_flow__intake__Purpose",
      "submit_voa_api_visa_voa_post",
      "get_voa_api_visa_voa__hash__get",
    ]) {
      expect(schema).not.toContain(retiredMarker);
    }

    const publicSource = schema.match(
      /PublicLeadSource:[\s\S]*?;\n\s+\/\*\*/,
    )?.[0];
    expect(publicSource).toBeDefined();
    expect(publicSource).not.toContain('"garuda_voa"');
  });

  it("removes retired GARUDA copy from every translated public bundle", () => {
    for (const locale of ["en", "id", "it"]) {
      const raw = fs.readFileSync(
        path.join(LOCALES_DIR, `${locale}.json`),
        "utf8",
      );
      const messages = JSON.parse(raw) as Record<string, unknown>;
      expect(messages).not.toHaveProperty("garudaVoa");
      expect(raw).not.toContain('"garudaVoa"');
    }
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

describe("sitemap — visa-oracle stays out of the sitemap while noindex (#4591)", () => {
  it("has a route tree to check (the probe can produce a positive)", () => {
    // Guard against the empty-set failure mode: a walk that finds nothing
    // would make every assertion below vacuously true.
    const routes = staticVisaOracleRoutes();
    expect(routes.length).toBeGreaterThanOrEqual(1);
    expect(routes).toContain("/visa-oracle");
  });

  it("lists every static visa-oracle route, or names it as deliberately unlisted", async () => {
    const urls = new Set((await sitemap()).map((e) => e.url));
    const missing = staticVisaOracleRoutes().filter(
      (r) =>
        !urls.has(`${BASE}${r}`) && !(r in INTENTIONALLY_UNLISTED_VISA_ORACLE),
    );
    expect(missing).toEqual([]);
  });

  it("does not list any visa-oracle route (innocence — a future accidental add fails here)", async () => {
    const urls = new Set((await sitemap()).map((e) => e.url));
    for (const excluded of Object.keys(INTENTIONALLY_UNLISTED_VISA_ORACLE)) {
      expect(urls.has(`${BASE}${excluded}`)).toBe(false);
    }
  });
});
