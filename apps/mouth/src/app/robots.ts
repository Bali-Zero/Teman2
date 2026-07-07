import type { MetadataRoute } from "next";

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

export default function robots(): MetadataRoute.Robots {
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
