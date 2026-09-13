import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

/**
 * Retired-door guard (W-VO-C, 2026-09-13).
 *
 * RULING Zero 2026-08-25: «Due porte: 301 → `/visa-oracle` subito». The defect
 * was not "a redirect is missing" but the shape it took for nineteen days: two
 * doors answering 200 and indexable, while the funnel carrying the signed
 * RulePack was the one search engines cannot see.
 *
 * THE FIRST ATTEMPT AT THIS FIX ALSO ANSWERED 200, and that is why the STATUS
 * CODE is asserted here rather than the mere existence of a redirect. A page
 * whose body is `permanentRedirect("/visa-oracle")` is statically prerendered by
 * Next 16 into a 41KB HTML document; `next start` then answers
 * `HTTP/1.1 200 OK` with `x-nextjs-prerender: 1` and no `location:` header, and
 * the redirect fires only client-side after hydration. Measured on PR #6401,
 * which was withdrawn for it. Every other check was green on that version —
 * typecheck, vitest, eslint, the Vercel preview deploy — because nothing in this
 * repo's PR gate probes an HTTP status.
 *
 * Guilt AND innocence: the handlers must answer 308 to /visa-oracle, and no
 * page component may exist behind them for the redirect to be wrapped around.
 */

import { GET as visaGET } from "./route";
import { GET as matchGET } from "./match/route";

const VISA_DIR = path.dirname(fileURLToPath(import.meta.url));

const DOORS = [
  { url: "https://balizero.com/visa", handler: visaGET, name: "/visa" },
  {
    url: "https://balizero.com/visa/match",
    handler: matchGET,
    name: "/visa/match",
  },
] as const;

describe("retired visa doors — guilt", () => {
  for (const door of DOORS) {
    it(`${door.name} answers a PERMANENT redirect, not a 200`, () => {
      const res = door.handler(new Request(door.url));
      // 308, never 200: a 200 is what the withdrawn first attempt shipped.
      expect(res.status).toBe(308);
      expect(res.headers.get("location")).toBe(
        "https://balizero.com/visa-oracle",
      );
    });

    it(`${door.name} keeps the visitor's origin (no hard-coded host)`, () => {
      const res = door.handler(
        new Request(`https://preview.example.com${new URL(door.url).pathname}`),
      );
      expect(res.headers.get("location")).toBe(
        "https://preview.example.com/visa-oracle",
      );
    });
  }
});

describe("retired visa doors — innocence", () => {
  it("no page component survives behind either redirect", () => {
    expect(fs.existsSync(path.join(VISA_DIR, "page.tsx"))).toBe(false);
    expect(fs.existsSync(path.join(VISA_DIR, "match", "page.tsx"))).toBe(false);
  });

  it("the handlers carry no quiz and no data path", () => {
    for (const file of ["route.ts", path.join("match", "route.ts")]) {
      const source = fs.readFileSync(path.join(VISA_DIR, file), "utf8");
      expect(source).not.toContain("use client");
      for (const legacy of [
        "AppWizard",
        "AppFrame",
        "AppBranchSelector",
        "useFunnelApp",
        "fetch(",
      ]) {
        expect(source).not.toContain(legacy);
      }
    }
  });

  it("leaves the shared result route in place (deep links still resolve)", () => {
    // /visa/match/[hash] is a different segment and is NOT retired: a result
    // link already shared with a visitor must still open.
    expect(
      fs.existsSync(path.join(VISA_DIR, "match", "[hash]", "page.tsx")),
    ).toBe(true);
  });
});
