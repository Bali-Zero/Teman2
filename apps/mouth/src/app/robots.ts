import type { MetadataRoute } from "next";

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
      {
        userAgent: "*",
        allow: ["/", "/llms.txt", "/llms-full.txt", "/llms-id.txt"],
        disallow: DISALLOW,
      },
      {
        userAgent: "Googlebot",
        allow: ["/"],
        crawlDelay: 1,
      },
      {
        userAgent: "Bingbot",
        allow: ["/"],
        crawlDelay: 1,
      },
      // ── AI crawlers — explicitly welcome ──────────────
      {
        userAgent: ["GPTBot", "OAI-SearchBot"],
        allow: ["/"],
        crawlDelay: 2,
      },
      {
        userAgent: "ChatGPT-User",
        allow: ["/"],
      },
      {
        userAgent: ["ClaudeBot", "anthropic-ai"],
        allow: ["/"],
        crawlDelay: 2,
      },
      {
        userAgent: "Claude-User",
        allow: ["/"],
      },
      {
        userAgent: "PerplexityBot",
        allow: ["/"],
        crawlDelay: 2,
      },
      {
        userAgent: "Google-Extended",
        allow: ["/"],
      },
      {
        userAgent: ["Applebot-Extended", "Amazonbot", "YouBot", "Bytespider"],
        allow: ["/"],
        crawlDelay: 2,
      },
      {
        userAgent: ["FacebookBot", "Meta-ExternalAgent", "CCBot", "cohere-ai"],
        allow: ["/"],
      },
    ],
    sitemap: "https://balizero.com/sitemap.xml",
  };
}
