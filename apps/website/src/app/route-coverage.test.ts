import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { describe, expect, it, vi } from "vitest";

vi.mock("../lib/server/public-catalog", () => ({
  loadPublicCatalog: vi.fn(async () => []),
}));

import sitemap from "./sitemap";

const appDir = path.join(process.cwd(), "src", "app");

function pageFiles(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) pageFiles(full, acc);
    else if (entry.name === "page.tsx") acc.push(full);
  }
  return acc;
}

/** noindex may be declared on the page or on any ancestor layout. */
function declaresNoIndex(pageFile: string): boolean {
  let dir = path.dirname(pageFile);
  if (/index:\s*false/.test(readFileSync(pageFile, "utf8"))) return true;
  while (dir.startsWith(appDir)) {
    const layout = path.join(dir, "layout.tsx");
    try {
      if (/index:\s*false/.test(readFileSync(layout, "utf8"))) return true;
    } catch {
      // no layout at this level
    }
    if (dir === appDir) break;
    dir = path.dirname(dir);
  }
  return false;
}

const isRedirectOnly = (file: string): boolean =>
  /permanentRedirect\(|redirect\(/.test(readFileSync(file, "utf8"));

const routeOf = (file: string): string =>
  "/" +
  path
    .relative(appDir, path.dirname(file))
    .split(path.sep)
    .filter(Boolean)
    .join("/");

/**
 * The guard the cutover did not have: every rendered route must be either
 * PUBLISHED (in the sitemap) or DELIBERATELY HIDDEN (noindex). Without it, a
 * private route added next week is indexable by default and every existing
 * test stays green — nothing enumerates the filesystem.
 */
describe("every route is either published or deliberately hidden", () => {
  it("leaves no page unaccounted for", async () => {
    vi.stubEnv("WEBSITE_PUBLIC_ORIGIN", "https://balizero.com");
    const published = new Set(
      (await sitemap()).map((entry) => new URL(entry.url).pathname),
    );

    const pages = pageFiles(appDir);
    const unaccounted = pages.filter((file) => {
      const route = routeOf(file);
      if (route.includes("[")) return false; // generated from data, not a literal path
      if (isRedirectOnly(file)) return false; // answers 308, never rendered
      if (declaresNoIndex(file)) return false;
      return !published.has(route === "/" ? "/" : route);
    });

    expect(unaccounted.map((file) => routeOf(file))).toEqual([]);
    // Guilt control: an empty walk would satisfy the assertion above.
    expect(pages.length).toBeGreaterThan(40);
  });
});
