import robots from "./robots";

/**
 * Guilt-and-innocence corpus for the per-host robots.txt guard (#4153).
 *
 * TRAUMA: this file serves /robots.txt for every host on the deployment, and
 * for months it answered `Allow: /` on the internal app subdomains — the
 * public site's rules, verbatim, on surfaces that sit behind login. #4153
 * added a host guard and closed one of the four; it shipped with no test at
 * all, so nothing held either half of the contract in place.
 *
 * A host guard has two ways to be wrong and they are opposite:
 *   - guilt failure   → an internal host is served the crawlable ruleset
 *   - innocence failure → the public site gets `Disallow: /`, which is an
 *     SEO outage in the shape of a one-line diff
 *
 * The innocence half is the load-bearing one here. INTERNAL_HOSTS is a list
 * that will keep growing, and the day someone reaches for a pattern instead
 * of an exact host ("*.balizero.com", `endsWith`, a regex) this is what
 * refuses the change.
 */

const mockHeaders = vi.fn();
vi.mock("next/headers", () => ({
  headers: () => mockHeaders(),
}));

function withHost(host: string) {
  mockHeaders.mockReturnValue(new Headers({ host }));
}

const INTERNAL = [
  "zantara.balizero.com",
  "www.zantara.balizero.com",
  "kita.balizero.com",
  "www.kita.balizero.com",
  "my.balizero.com",
  "www.my.balizero.com",
  "prime.balizero.com",
  "www.prime.balizero.com",
];

// Served by the same deployment, must stay crawlable. visa/tax are public
// funnels we pay to rank; balizero.com is the marketing site itself.
// proxy.ts::matchesDomain treats the `www.` variant of a public domain as
// public too, so the corpus carries both forms: a single stray `www.` entry
// slipped into INTERNAL_HOSTS would otherwise de-index a funnel with every
// test still green.
const PUBLIC = [
  "balizero.com",
  "www.balizero.com",
  "visa.balizero.com",
  "www.visa.balizero.com",
  "tax.balizero.com",
  "www.tax.balizero.com",
  "mo.balizero.com",
];

beforeEach(() => {
  mockHeaders.mockReset();
});

describe("robots.txt — guilt: internal hosts are fully disallowed", () => {
  it.each(INTERNAL)("%s gets a single blanket Disallow", async (host) => {
    withHost(host);
    const result = await robots();
    const rules = Array.isArray(result.rules) ? result.rules : [result.rules];

    expect(rules).toHaveLength(1);
    expect(rules[0].userAgent).toBe("*");
    expect(rules[0].disallow).toBe("/");
    // An `allow` alongside `disallow: "/"` would re-open the host by
    // longest-match, which is exactly how this file's public ruleset works.
    expect(rules[0].allow).toBeUndefined();
    expect(result.sitemap).toBeUndefined();
  });

  it("normalises the host before matching — case, trailing dot, port", async () => {
    for (const host of [
      "ZANTARA.balizero.com",
      "zantara.balizero.com.",
      "zantara.balizero.com:443",
      "  kita.balizero.com  ",
    ]) {
      withHost(host);
      const result = await robots();
      const rules = Array.isArray(result.rules) ? result.rules : [result.rules];
      // If this fails, read the host in the loop above — normalisation dropped it.
      expect([host, rules[0].disallow]).toEqual([host, "/"]);
    }
  });
});

describe("robots.txt — innocence: public hosts keep the full ruleset", () => {
  it.each(PUBLIC)("%s is unchanged by the guard", async (host) => {
    withHost(host);
    const result = await robots();
    const rules = Array.isArray(result.rules) ? result.rules : [result.rules];

    // The public output is the multi-group ruleset (named crawler groups),
    // not the one-line internal answer.
    expect(rules.length).toBeGreaterThan(1);

    const star = rules.find((r) => r.userAgent === "*");
    expect(star).toBeDefined();
    expect(star?.allow).toContain("/");
    expect(star?.allow).toContain("/_next/static/");
    expect(star?.disallow).toContain("/dashboard");
    expect(star?.disallow).toContain("/api/");
    expect(result.sitemap).toBe("https://balizero.com/sitemap.xml");
  });

  it("an unknown or missing host falls through to the public rules", async () => {
    for (const host of ["", "localhost:3000", "mouth.vercel.app"]) {
      withHost(host);
      const result = await robots();
      const rules = Array.isArray(result.rules) ? result.rules : [result.rules];
      // A length of 1 here means the host was swallowed by INTERNAL_HOSTS.
      expect([host, rules.length > 1]).toEqual([host, true]);
    }
  });
});
