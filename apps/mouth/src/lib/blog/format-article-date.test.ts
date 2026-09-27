import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { BLOG_TIME_ZONE, formatArticleDate } from "./format-article-date";

// The article date must render identically on the server (Vercel runs in UTC)
// and in the reader's browser (Asia/Makassar for the Bali audience). The
// formatter therefore pins an explicit zone and never reads the process one.
// Run `TZ=UTC npx vitest run <this file>` to prove it: the WITA answers below
// hold under every process TZ, whereas a local-time formatter fails them.
describe("formatArticleDate", () => {
  it("pins the business zone to WITA (Asia/Makassar)", () => {
    expect(BLOG_TIME_ZONE).toBe("Asia/Makassar");
  });

  it("rolls a late-evening UTC timestamp forward to the WITA calendar day", () => {
    // 2026-01-03 20:00Z is 2026-01-04 04:00 in Bali — the exact QA repro
    // (SSR "Jan 3, 2026" vs client "Jan 4, 2026", React hydration #418).
    expect(formatArticleDate("2026-01-03T20:00:00Z")).toBe("Jan 4, 2026");
  });

  it("keeps a timestamp that is still the same WITA day on that day", () => {
    // 2026-01-04 15:30Z is 2026-01-04 23:30 in Bali — a UTC+8..+14 process
    // zone would wrongly print Jan 5.
    expect(formatArticleDate("2026-01-04T15:30:00Z")).toBe("Jan 4, 2026");
  });

  it("accepts Date and epoch-millisecond inputs identically to ISO strings", () => {
    const iso = "2026-01-03T20:00:00Z";
    expect(formatArticleDate(new Date(iso))).toBe("Jan 4, 2026");
    expect(formatArticleDate(Date.parse(iso))).toBe("Jan 4, 2026");
  });

  it("formats across a year boundary in WITA, not UTC", () => {
    // 2025-12-31 17:00Z is 2026-01-01 01:00 in Bali.
    expect(formatArticleDate("2025-12-31T17:00:00Z")).toBe("Jan 1, 2026");
  });

  it("returns an empty string for missing or unparseable input", () => {
    expect(formatArticleDate(null)).toBe("");
    expect(formatArticleDate(undefined)).toBe("");
    expect(formatArticleDate("")).toBe("");
    expect(formatArticleDate("not-a-date")).toBe("");
  });
});

// Class guard: the public blog / news / article / journal display paths must
// go through the helper. A bare `toLocaleDateString`, `toLocaleTimeString` or
// date-fns `format` reads the process zone, so the same page hydrates to a
// different day on the server than in the browser.
describe("blog/news/article date rendering is zone-pinned", () => {
  const SRC = path.resolve(__dirname, "..", "..");
  const ROOTS = [
    "app/(blog)",
    "app/v2/news",
    "app/v2/_components",
    "components/blog",
  ];

  function walk(dir: string, out: string[] = []): string[] {
    for (const name of readdirSync(dir)) {
      const full = path.join(dir, name);
      if (statSync(full).isDirectory()) walk(full, out);
      else if (/\.(ts|tsx)$/.test(name) && !/\.test\.(ts|tsx)$/.test(name))
        out.push(full);
    }
    return out;
  }

  const files = ROOTS.flatMap((r) => walk(path.join(SRC, r)));

  it("scans a non-trivial set of files", () => {
    expect(files.length).toBeGreaterThan(20);
  });

  it.each(files.map((f) => [path.relative(SRC, f), f]))(
    "%s has no zone-dependent date formatting",
    (_rel, file) => {
      const source = readFileSync(file, "utf8");
      expect(source).not.toMatch(/\.toLocaleDateString\(/);
      expect(source).not.toMatch(/\.toLocaleTimeString\(/);
      expect(source).not.toMatch(
        /import\s*\{[^}]*\bformat\b[^}]*\}\s*from\s*["']date-fns["']/,
      );
    },
  );
});
