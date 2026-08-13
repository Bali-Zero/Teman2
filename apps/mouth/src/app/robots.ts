import { headers } from "next/headers";
import type { MetadataRoute } from "next";
import { normalizeHostname } from "@/lib/hostname";

// In robots.txt semantics a crawler obeys ONLY the most specific matching
// user-agent group — specific groups REPLACE the `*` group, they do not
// inherit from it. Every named group below must therefore carry the full
// disallow list, or that crawler is silently allowed into /api/, /dashboard
// and the rest of the workspace (crawl-budget bleed — GSC clean-window
// investigation 2026-07-03).
// /_next/ stays disallowed (build manifests, data routes), but the static
// assets and the image optimizer MUST stay crawlable: search-engine renderers
// fetch CSS/JS/images to evaluate the page, and robots-blocked resources
// degrade rendering (red-team finding 2026-07-05). Longest-match wins, so
// these allows beat the /_next/ disallow for exactly the asset paths.
const ALLOW = ["/", "/_next/static/", "/_next/image"];

const DISALLOW = [
  // Tag-filtered listing URLs (`/insights?tag=`, `/?tag=`) are duplicate-content
  // parameter pages that nothing on the site actually consumes (no searchParams
  // reader). They are pure crawl-budget waste — and the 2026-07-21 leak turned
  // them into `/insights?tag=<raw-LLM-reasoning>` URLs Google indexed. Block the
  // param outright; canonical content lives at the un-parametrised path.
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
  "/api/",
  "/_next/",
];

// Hosts that serve the internal app surface. These must never be crawled:
// the pages sit behind login, so what leaks is the subdomain's existence
// and its route structure, not content.
//
// This is a CRAWL block, not an index block, and the difference is
// load-bearing: a URL disallowed here can still appear in results as a bare
// URL, because the crawler never fetches it and so never sees a noindex.
// Measured on the live surface 2026-08-13, `GET /` as Googlebot:
//   zantara → X-Robots-Tag: noindex, nofollow   (shipped in #4106)
//   kita    → absent (307 to /login)
//   my      → absent (307 to /portal/login)
//   prime   → absent (200, proxy.ts returns from the prime rewrite before
//             the header is set)
// So for kita/my/prime this file is currently the ONLY protection and the
// block is strictly better than nothing. For zantara the two layers do
// interact — the noindex has been live for a day, and blocking the crawl
// stops Google re-reading it — which is why the open question is whether
// anything from these hosts is in the index at all. That is a Search Console
// measurement, not a code question; until it is answered, do not "tidy" this
// by adding a noindex header to the other three and calling it layered.
// #4153 closed zantara only, because that was what the instruction named.
// The census afterwards found the same hole on three more hosts: kita, my and
// prime all answered `/api/health` with 200 and served this file's public
// rules verbatim — one deployment, four internal front doors, one of them
// closed. They match what proxy.ts already classifies as non-public:
// isAppDomain (kita + prime) and isPortalDomain (my).
//
// visa.balizero.com and tax.balizero.com are served by this same deployment
// and are deliberately NOT here: both are public marketing surfaces (measured
// 2026-08-13 — they answer /api/health 200 like the internal hosts do, so
// "same deployment" is not what decides this; being publicly marketed is).
// Adding either would de-index a funnel we pay to rank.
const INTERNAL_HOSTS = new Set([
  "zantara.balizero.com",
  "www.zantara.balizero.com",
  "kita.balizero.com",
  "www.kita.balizero.com",
  "my.balizero.com",
  "www.my.balizero.com",
  "prime.balizero.com",
  "www.prime.balizero.com",
]);

export default async function robots(): Promise<MetadataRoute.Robots> {
  const host = normalizeHostname((await headers()).get("host") ?? "");

  if (INTERNAL_HOSTS.has(host)) {
    return {
      rules: [{ userAgent: "*", disallow: "/" }],
    };
  }

  return {
    rules: [
      // ── Standard crawlers ─────────────────────────────
      // Googlebot intentionally has no dedicated group: it falls back to `*`
      // (Google ignores crawl-delay, so a specific group bought nothing and
      // cost us the disallow list).
      {
        userAgent: "*",
        allow: [...ALLOW, "/llms.txt", "/llms-full.txt", "/llms-id.txt"],
        disallow: DISALLOW,
      },
      {
        userAgent: "Bingbot",
        allow: ALLOW,
        disallow: DISALLOW,
        crawlDelay: 1,
      },
      // ── AI crawlers — explicitly welcome (on public content) ──
      {
        userAgent: ["GPTBot", "OAI-SearchBot"],
        allow: ALLOW,
        disallow: DISALLOW,
        crawlDelay: 2,
      },
      {
        userAgent: "ChatGPT-User",
        allow: ALLOW,
        disallow: DISALLOW,
      },
      {
        userAgent: ["ClaudeBot", "anthropic-ai"],
        allow: ALLOW,
        disallow: DISALLOW,
        crawlDelay: 2,
      },
      {
        userAgent: "Claude-User",
        allow: ALLOW,
        disallow: DISALLOW,
      },
      {
        userAgent: "PerplexityBot",
        allow: ALLOW,
        disallow: DISALLOW,
        crawlDelay: 2,
      },
      {
        userAgent: "Google-Extended",
        allow: ALLOW,
        disallow: DISALLOW,
      },
      {
        userAgent: ["Applebot-Extended", "Amazonbot", "YouBot", "Bytespider"],
        allow: ALLOW,
        disallow: DISALLOW,
        crawlDelay: 2,
      },
      {
        userAgent: ["FacebookBot", "Meta-ExternalAgent", "CCBot", "cohere-ai"],
        allow: ALLOW,
        disallow: DISALLOW,
      },
    ],
    sitemap: "https://balizero.com/sitemap.xml",
  };
}
