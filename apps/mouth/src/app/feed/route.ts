/**
 * RSS Feed Route - AI-optimized with full content and metadata
 * Generates RSS 2.0 feed with Dublin Core extensions for AI discovery
 * Used by Perplexity, ChatGPT browse, and other AI crawlers
 */

import { getAllArticles } from "@/lib/blog/articles";

const baseUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || "https://balizero.com";

function escapeXml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export async function GET() {
  const { articles } = await getAllArticles({ limit: 500 });

  const items = articles
    .map((article) => {
      const articleUrl = `${baseUrl}/${article.category}/${article.slug}`;
      const pubDate = new Date(article.publishedAt).toUTCString();
      const imageUrl = article.coverImage?.startsWith("http")
        ? article.coverImage
        : `${baseUrl}${article.coverImage}`;

      return `    <item>
      <title>${escapeXml(article.title)}</title>
      <link>${articleUrl}</link>
      <guid isPermaLink="true">${articleUrl}</guid>
      <description>${escapeXml(article.excerpt)}</description>
      <pubDate>${pubDate}</pubDate>
      <dc:creator>${escapeXml(article.author?.name || "Bali Zero Editorial")}</dc:creator>
      <category>${escapeXml(article.category)}</category>
      <media:content url="${escapeXml(imageUrl)}" type="image/jpeg" />
    </item>`;
    })
    .join("\n");

  const feed = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:dc="http://purl.org/dc/elements/1.1/"
  xmlns:content="http://purl.org/rss/1.0/modules/content/"
  xmlns:media="http://search.yahoo.com/mrss/"
  xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Bali Zero - Visa, Business &amp; Immigration Experts</title>
    <link>${baseUrl}</link>
    <description>Expert guides on Indonesia visas, company setup, tax compliance, property investment, and expat life in Bali. Updated 2026 information from Bali Zero.</description>
    <language>en-us</language>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
    <atom:link href="${baseUrl}/feed" rel="self" type="application/rss+xml"/>
    <image>
      <url>${baseUrl}/static/balizero-logo-clean.png</url>
      <title>Bali Zero</title>
      <link>${baseUrl}</link>
    </image>
${items}
  </channel>
</rss>`;

  return new Response(feed, {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      "Cache-Control": "public, max-age=3600, s-maxage=3600",
    },
  });
}
