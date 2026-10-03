import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { articleHref } from "./article-href";

describe("articleHref", () => {
  it("is /<category>/<slug>, the only routed article URL", () => {
    expect(articleHref({ category: "business", slug: "kbli-2025-oss" })).toBe(
      "/business/kbli-2025-oss",
    );
  });
});

// Class guard: `/news/<slug>` and `/news/<category>/<slug>` are not article
// routes (measured live: 404 / a 200 "Page not found" soft-404). No template
// literal in the app may build an article href under /news/.
describe("no article href is built under /news/", () => {
  const SRC = path.resolve(__dirname, "..", "..");

  function walk(dir: string, out: string[] = []): string[] {
    for (const name of readdirSync(dir)) {
      const full = path.join(dir, name);
      if (statSync(full).isDirectory()) walk(full, out);
      else if (/\.(ts|tsx)$/.test(name) && !/\.test\.(ts|tsx)$/.test(name))
        out.push(full);
    }
    return out;
  }

  it("finds none in src/", () => {
    const offenders = walk(SRC)
      .filter((f) => /`\/news\/\$\{[^`]*slug/.test(readFileSync(f, "utf8")))
      .map((f) => path.relative(SRC, f));
    expect(offenders).toEqual([]);
  });
});
