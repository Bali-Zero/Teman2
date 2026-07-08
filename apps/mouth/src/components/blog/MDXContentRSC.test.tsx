import fs from "node:fs";
import path from "node:path";
import { renderToString } from "react-dom/server";
import matter from "gray-matter";
import { describe, expect, it } from "vitest";

import { renderMDXBody } from "./MDXContentRSC";

function stripImports(content: string): string {
  return content
    .replace(/^import\s+[\s\S]*?from\s+['"][^'"]+['"];?\s*$/gm, "")
    .replace(/^import\s*{[\s\S]*?}\s*from\s*['"][^'"]+['"];?\s*$/gm, "")
    .trim();
}

const strataTitleArticles = [
  "src/content/articles/property/strata-title-explained.mdx",
  "src/content/articles/property/strata-title-explained.fr.mdx",
  "src/content/articles/property/strata-title-explained.id.mdx",
  "src/content/articles/property/strata-title-explained.it.mdx",
  "src/content/articles/property/strata-title-explained.ru.mdx",
];

describe("renderMDXBody", () => {
  it("server-renders the driving license article interactive MDX body", async () => {
    const articlePath = path.join(
      process.cwd(),
      "src/content/articles/lifestyle/driving-license-foreigners.mdx",
    );
    const articleFile = fs.readFileSync(articlePath, "utf8");
    const { content } = matter(articleFile);

    const mdxBody = await renderMDXBody(stripImports(content));

    const html = renderToString(<>{mdxBody}</>);

    expect(html).toContain("Driving License for Foreigners in Indonesia 2026");
    expect(html).toContain("How long are you staying in Indonesia?");
    expect(html).toContain("Prepare Documents");
    expect(html).not.toContain("Decision tree unavailable");
    expect(html).not.toContain("Journey map unavailable");
  });

  it.each(strataTitleArticles)(
    "server-renders the strata title article interactive MDX body: %s",
    async (article) => {
      const articlePath = path.join(process.cwd(), article);
      const articleFile = fs.readFileSync(articlePath, "utf8");
      const { content } = matter(articleFile);

      const mdxBody = await renderMDXBody(stripImports(content));

      const html = renderToString(<>{mdxBody}</>);

      expect(html).toContain("PPJB vs SHMSRS");
    },
  );
});
