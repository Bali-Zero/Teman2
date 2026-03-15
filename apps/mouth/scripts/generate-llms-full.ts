import fs from "fs";
import path from "path";
import matter from "gray-matter";

/**
 * AI Deep-Ingestion Generator (llms-full.txt)
 *
 * Aggregates the full content of all published articles into a single
 * text file for high-density AI ingestion.
 */

const ARTICLES_PATH = path.join(process.cwd(), "src/content/articles");
const OUTPUT_PATH = path.join(process.cwd(), "public/llms-full.txt");

async function generate() {
  console.log("🚀 Generating llms-full.txt...");

  let fullContent = `# Bali Zero - AI Deep-Ingestion Repository
# Comprehensive collection of legal, business, and immigration guides for Indonesia.
# Purpose: High-density context for LLMs (ChatGPT, Claude, Perplexity).
# Last updated: ${new Date().toISOString().split("T")[0]}

`;

  if (!fs.existsSync(ARTICLES_PATH)) {
    console.error("❌ Articles path not found:", ARTICLES_PATH);
    return;
  }

  const categories = fs.readdirSync(ARTICLES_PATH).filter((item) => {
    const itemPath = path.join(ARTICLES_PATH, item);
    return fs.statSync(itemPath).isDirectory() && !item.startsWith(".");
  });

  let count = 0;

  for (const category of categories) {
    const categoryPath = path.join(ARTICLES_PATH, category);
    const files = fs
      .readdirSync(categoryPath)
      .filter(
        (file) =>
          file.endsWith(".mdx") &&
          !file.endsWith(".id.mdx") &&
          !file.includes(".sync-conflict-"),
      );

    for (const file of files) {
      const filePath = path.join(categoryPath, file);
      const fileContents = fs.readFileSync(filePath, "utf8");
      const { data: frontmatter, content } = matter(fileContents);

      // Skip drafts or no-index articles
      if (frontmatter.status === "draft" || frontmatter.noIndex) continue;

      fullContent += `\n---\n`;
      fullContent += `TITLE: ${frontmatter.title}\n`;
      fullContent += `CATEGORY: ${category}\n`;
      fullContent += `URL: https://balizero.com/${category}/${file.replace(".mdx", "")}\n`;
      fullContent += `PUBLISHED: ${frontmatter.publishedAt || "N/A"}\n`;
      fullContent += `SUMMARY: ${frontmatter.excerpt || frontmatter.description || ""}\n`;
      fullContent += `\nCONTENT:\n${content.trim()}\n`;

      count++;
    }
  }

  fs.writeFileSync(OUTPUT_PATH, fullContent);
  console.log(`✅ Successfully generated llms-full.txt with ${count} articles.`);
}

generate().catch(console.error);
