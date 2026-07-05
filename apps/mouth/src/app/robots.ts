import type { MetadataRoute } from "next";

// In robots.txt semantics a crawler obeys ONLY the most specific matching
// user-agent group — specific groups REPLACE the `*` group, they do not
// inherit from it. Every named group below must therefore carry the full
// disallow list, or that crawler is silently allowed into /api/, /dashboard
// and the rest of the workspace (crawl-budget bleed — GSC clean-window
// investigation 2026-07-03).
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
        allow: ["/", "/llms.txt", "/llms-full.txt", "/llms-id.txt"],
        disallow: DISALLOW,
      },
      {
        userAgent: "Bingbot",
        allow: ["/"],
        disallow: DISALLOW,
        crawlDelay: 1,
      },
      // ── AI crawlers — explicitly welcome (on public content) ──
      {
        userAgent: ["GPTBot", "OAI-SearchBot"],
        allow: ["/"],
        disallow: DISALLOW,
        crawlDelay: 2,
      },
      {
        userAgent: "ChatGPT-User",
        allow: ["/"],
        disallow: DISALLOW,
      },
      {
        userAgent: ["ClaudeBot", "anthropic-ai"],
        allow: ["/"],
        disallow: DISALLOW,
        crawlDelay: 2,
      },
      {
        userAgent: "Claude-User",
        allow: ["/"],
        disallow: DISALLOW,
      },
      {
        userAgent: "PerplexityBot",
        allow: ["/"],
        disallow: DISALLOW,
        crawlDelay: 2,
      },
      {
        userAgent: "Google-Extended",
        allow: ["/"],
        disallow: DISALLOW,
      },
      {
        userAgent: ["Applebot-Extended", "Amazonbot", "YouBot", "Bytespider"],
        allow: ["/"],
        disallow: DISALLOW,
        crawlDelay: 2,
      },
      {
        userAgent: ["FacebookBot", "Meta-ExternalAgent", "CCBot", "cohere-ai"],
        allow: ["/"],
        disallow: DISALLOW,
      },
    ],
    sitemap: "https://balizero.com/sitemap.xml",
  };
}
