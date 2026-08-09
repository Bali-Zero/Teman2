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

const productionArticleRegressions = [
  "src/content/articles/business/export-import-business-guide.mdx",
  "src/content/articles/business/ota-data-crackdown-bali-2026.mdx",
  "src/content/articles/business/capital-requirements-guide.mdx",
  "src/content/articles/business/restaurant-business-guide.mdx",
  "src/content/articles/business/business-licenses-overview.mdx",
  "src/content/articles/business/contracts-indonesian-law.mdx",
  "src/content/articles/business/due-diligence-indonesia.mdx",
  "src/content/articles/business/labor-law-guide.mdx",
  "src/content/articles/business/manufacturing-business-guide.mdx",
  "src/content/articles/business/hiring-indonesian-employees.mdx",
  "src/content/articles/immigration/airport-procedures.mdx",
  "src/content/articles/immigration/golden-visa-indonesia-complete-guide.mdx",
  "src/content/articles/property/property-investment-guide.mdx",
  "src/content/articles/property/villa-investment-guide.mdx",
  "src/content/articles/business/pt-pma-first-year-compliance.mdx",
  "src/content/articles/business/pt-pma-registration-guide.mdx",
  "src/content/articles/digital-nomad/freelancing-legally-indonesia.mdx",
  "src/content/articles/tax/freelancer-tax-guide.mdx",
  "src/content/articles/business/bali-2026-eco-luxury-villas-and-the-new-american-expat-playbook.id.mdx",
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

  it("server-renders legacy calculator MDX without client function props", async () => {
    const articlePath = path.join(
      process.cwd(),
      "src/content/articles/property/rental-income-tax.mdx",
    );
    const articleFile = fs.readFileSync(articlePath, "utf8");
    const { content } = matter(articleFile);

    const mdxBody = await renderMDXBody(stripImports(content));

    const html = renderToString(<>{mdxBody}</>);

    expect(html).toContain("Rental Income Tax Calculator");
    expect(html).toContain("Annual Tax (10%)");
    expect(html).toContain('data-mdx-calculator-rsc="true"');
    expect(html).not.toContain("calculateResult");
    expect(html).not.toContain("Functions cannot be passed");
  });

  it("server-renders tax takeaway MDX that uses KeyTakeaway children", async () => {
    const articlePath = path.join(
      process.cwd(),
      "src/content/articles/tax/ppn-12-percent-increase-2026.mdx",
    );
    const articleFile = fs.readFileSync(articlePath, "utf8");
    const { content } = matter(articleFile);

    const mdxBody = await renderMDXBody(stripImports(content));

    const html = renderToString(<>{mdxBody}</>);

    expect(html).toContain("Indonesia PPN/VAT Rate 2026");
    expect(html).toContain("Key Takeaways");
    expect(html).toContain("PPN raised to 12%");
    expect(html).not.toContain("Cannot read properties of undefined");
  });

  it.each(productionArticleRegressions)(
    "server-renders an article observed failing in production: %s",
    async (article) => {
      const articlePath = path.join(process.cwd(), article);
      const articleFile = fs.readFileSync(articlePath, "utf8");
      const { content } = matter(articleFile);

      const mdxBody = await renderMDXBody(stripImports(content));
      const html = renderToString(<>{mdxBody}</>);

      expect(html).toContain("mdx-content");
    },
  );
});
