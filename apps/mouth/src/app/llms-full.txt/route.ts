/**
 * llms-full.txt Route - Complete content export for AI ingestion
 * Generates a single Markdown file with all article content
 * Standard: https://llmstxt.org
 */

import { getAllArticles, getArticleBySlug } from "@/lib/blog/articles";

const baseUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || "https://balizero.com";

function stripMdxComponents(content: string): string {
  // Remove JSX/MDX component tags (InfoCard, ComparisonTable, etc.)
  let cleaned = content
    .replace(/<[A-Z][a-zA-Z]*\s[^>]*\/>/g, "") // self-closing
    .replace(/<[A-Z][a-zA-Z]*\s[^>]*>[\s\S]*?<\/[A-Z][a-zA-Z]*>/g, "") // paired
    .replace(/<[A-Z][a-zA-Z]*>/g, "") // opening without attrs
    .replace(/<\/[A-Z][a-zA-Z]*>/g, ""); // closing

  // Remove import statements
  cleaned = cleaned.replace(/^import\s+.*$/gm, "");

  // Remove export statements (but keep content)
  cleaned = cleaned.replace(/^export\s+default\s+.*$/gm, "");

  // Collapse multiple blank lines
  cleaned = cleaned.replace(/\n{3,}/g, "\n\n");

  return cleaned.trim();
}

export async function GET() {
  const { articles } = await getAllArticles({ limit: 500 });

  const sections: string[] = [];

  sections.push(`# Bali Zero - Complete Content Library`);
  sections.push(`> Generated: ${new Date().toISOString().split("T")[0]}`);
  sections.push(`> Source: ${baseUrl}`);
  sections.push(`> Articles: ${articles.length}`);
  sections.push("");
  sections.push(
    "This file contains the full text of all published articles from Bali Zero, " +
      "a visa, immigration, and business consulting firm in Bali, Indonesia. " +
      "For a structured overview, see /llms.txt",
  );
  sections.push("");
  sections.push("---");
  sections.push("");

  // Group by category
  const byCategory: Record<string, typeof articles> = {};
  for (const article of articles) {
    const cat = article.category;
    if (!byCategory[cat]) byCategory[cat] = [];
    byCategory[cat].push(article);
  }

  for (const [category, catArticles] of Object.entries(byCategory)) {
    sections.push(
      `## ${category.charAt(0).toUpperCase() + category.slice(1).replace("-", " ")}`,
    );
    sections.push("");

    for (const article of catArticles) {
      try {
        const full = await getArticleBySlug(article.category, article.slug);
        if (!full || !full.content) continue;

        const cleanContent = stripMdxComponents(full.content);
        // Skip placeholder articles (very short content)
        if (cleanContent.length < 500) continue;

        sections.push(`### ${full.title}`);
        sections.push(`URL: ${baseUrl}/${full.category}/${full.slug}`);
        sections.push(
          `Published: ${full.publishedAt ? new Date(full.publishedAt).toISOString().split("T")[0] : "Unknown"}`,
        );
        if (full.updatedAt) {
          sections.push(
            `Updated: ${new Date(full.updatedAt).toISOString().split("T")[0]}`,
          );
        }
        sections.push("");
        sections.push(cleanContent);
        sections.push("");
        sections.push("---");
        sections.push("");
      } catch {
        // Skip articles that fail to parse
        continue;
      }
    }
  }

  const body = sections.join("\n");

  return new Response(body, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, max-age=86400, s-maxage=86400",
    },
  });
}
