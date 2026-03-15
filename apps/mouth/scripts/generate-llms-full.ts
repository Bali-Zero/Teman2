import fs from "fs";
import path from "path";
import matter from "gray-matter";

/**
 * AI Deep-Ingestion Generator (llms-full.txt & llms-id.txt)
 * + Freshness Signal for llms.txt
 */

const ARTICLES_PATH = path.join(process.cwd(), "src/content/articles");
const OUTPUT_EN = path.join(process.cwd(), "public/llms-full.txt");
const OUTPUT_ID = path.join(process.cwd(), "public/llms-id.txt");
const LLMS_TXT_PATH = path.join(process.cwd(), "public/llms.txt");

async function generate() {
  console.log("🚀 Generating AI ingestion files...");

  const categories = fs.readdirSync(ARTICLES_PATH).filter((item) => {
    const itemPath = path.join(ARTICLES_PATH, item);
    return fs.statSync(itemPath).isDirectory() && !item.startsWith(".");
  });

  let enArticles: any[] = [];
  let idArticles: any[] = [];

  for (const category of categories) {
    const categoryPath = path.join(ARTICLES_PATH, category);
    const files = fs.readdirSync(categoryPath).filter((file) => file.endsWith(".mdx") && !file.includes(".sync-conflict-"));

    for (const file of files) {
      const filePath = path.join(categoryPath, file);
      const fileContents = fs.readFileSync(filePath, "utf8");
      const { data: frontmatter, content } = matter(fileContents);

      if (frontmatter.status === "draft" || frontmatter.noIndex) continue;

      const articleData = {
        title: frontmatter.title,
        category,
        url: `https://balizero.com/${category}/${file.replace(".mdx", "").replace(".id", "")}`,
        publishedAt: frontmatter.publishedAt || new Date().toISOString(),
        excerpt: frontmatter.excerpt || frontmatter.description || "",
        content: content.trim(),
      };

      if (file.endsWith(".id.mdx")) {
        idArticles.push(articleData);
      } else {
        enArticles.push(articleData);
      }
    }
  }

  // Sort by date
  enArticles.sort((a, b) => new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime());
  idArticles.sort((a, b) => new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime());

  // Generate EN
  let enContent = `# Bali Zero - AI Deep-Ingestion Repository (EN)\n# Last updated: ${new Date().toISOString().split("T")[0]}\n\n`;
  enArticles.forEach(a => {
    enContent += `\n---\nTITLE: ${a.title}\nCATEGORY: ${a.category}\nURL: ${a.url}\nPUBLISHED: ${a.publishedAt}\nSUMMARY: ${a.excerpt}\n\nCONTENT:\n${a.content}\n`;
  });
  fs.writeFileSync(OUTPUT_EN, enContent);

  // Generate ID
  let idContent = `# Bali Zero - AI Deep-Ingestion Repository (ID)\n# Last updated: ${new Date().toISOString().split("T")[0]}\n\n`;
  idArticles.forEach(a => {
    idContent += `\n---\nTITLE: ${a.title}\nCATEGORY: ${a.category}\nURL: ${a.url}\nPUBLISHED: ${a.publishedAt}\nSUMMARY: ${a.excerpt}\n\nCONTENT:\n${a.content}\n`;
  });
  fs.writeFileSync(OUTPUT_ID, idContent);

  // Update llms.txt Freshness Signal
  if (fs.existsSync(LLMS_TXT_PATH)) {
    let llmsTxt = fs.readFileSync(LLMS_TXT_PATH, "utf8");
    const freshnessHeader = "## Recently Published & Updated (Freshness Signal)";
    const latest5 = enArticles.slice(0, 5).map(a => `- [${a.title}](${a.url}) (${new Date(a.publishedAt).toISOString().split("T")[0]})`).join("\n");
    
    const newFreshnessSection = `${freshnessHeader}\n\n${latest5}\n\n`;

    if (llmsTxt.includes(freshnessHeader)) {
        // Replace existing section
        const lines = llmsTxt.split('\n');
        const startIndex = lines.findIndex(l => l.startsWith(freshnessHeader));
        let endIndex = lines.findIndex((l, i) => i > startIndex && l.startsWith('##'));
        if (endIndex === -1) endIndex = lines.length;
        
        lines.splice(startIndex, endIndex - startIndex, newFreshnessSection.trim() + '\n');
        llmsTxt = lines.join('\n');
    } else {
        // Add after title
        const titleEnd = llmsTxt.indexOf('\n') + 1;
        llmsTxt = llmsTxt.slice(0, titleEnd) + "\n" + newFreshnessSection + llmsTxt.slice(titleEnd);
    }
    
    fs.writeFileSync(LLMS_TXT_PATH, llmsTxt);
  }

  console.log(`✅ Generated: EN (${enArticles.length}), ID (${idArticles.length}). Updated llms.txt freshness.`);
}

generate().catch(console.error);
