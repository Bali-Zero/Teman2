import { globSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { createHash } from "node:crypto";
import matter from "gray-matter";
import { renderToStaticMarkup } from "react-dom/server";
import { toString } from "mdast-util-to-string";
import { expect, it } from "vitest";
import { ArticleBody } from "./ArticleBody";
import { parseArticle, markdownParser, type ReadingNode } from "./article-model";
import { supportedArticleComponents, publicComponentData } from "./ArticleComponents";

const normalized = (text: string): string => text.replace(/\s+/g, " ").trim();

function sourceHeadings(source: string, title: string): string[] {
  const headings: string[] = [];
  let fence = "";
  for (const line of source.split("\n")) {
    const block = line.replace(/^(?:\s{0,3}> ?)+/, "");
    const marker = /^\s{0,3}(`{3,}|~{3,})/.exec(block);
    if (marker) { if (!fence) fence = marker[1]; else if (marker[1][0] === fence[0] && marker[1].length >= fence.length) fence = ""; continue; }
    if (fence) continue;
    const match = /^\s{0,3}(#{1,3})\s+(.+)$/.exec(block);
    if (!match) continue;
    const text = normalized(toString(markdownParser.parse(block)));
    if (text && (match[1].length !== 1 || text !== normalized(title))) headings.push(text);
  }
  return headings;
}

// Explicit audit: ARTICLE_CORPUS_REPORT=/absolute/path/report.json npm test -- ArticleCorpus
// A local source inventory is distinct from the published HTTP catalog. Neither
// a heading check nor these SSR comparisons prove factual or visual correctness.
it.skipIf(!process.env.ARTICLE_CORPUS_REPORT)("audits every available owned MDX source and its server-rendered projection", () => {
  const root = resolve("../mouth/src/content/articles");
  const files = process.env.ARTICLE_PUBLIC_SOURCES ? [] : globSync("**/*.mdx", { cwd: root }).sort();
  const sources: { path: string; raw: string; content: string; title: string }[] = files.map((path) => {
    const raw = readFileSync(resolve(root, path), "utf8"), parsed = matter(raw);
    return { path, raw, content: parsed.content, title: typeof parsed.data.title === "string" ? parsed.data.title : "" };
  });
  if (process.env.ARTICLE_PUBLIC_SOURCES) {
    const publicSources = JSON.parse(readFileSync(process.env.ARTICLE_PUBLIC_SOURCES, "utf8")) as { rows: { approved: boolean; category: string; slug: string; content: string; title: string }[] };
    for (const row of publicSources.rows.filter((row) => row.approved)) sources.push({ path: `${row.category}/${row.slug}`, raw: row.content, content: row.content, title: row.title });
  }
  const rows: Record<string, unknown>[] = [];
  const componentCounts: Record<string, number> = {}, propCounts: Record<string, Record<string, number>> = {};
  const element = document.createElement("div");
  for (const { path, raw, content, title } of sources) {
    try {
      const parsed = parseArticle(content, title);
      const expected = sourceHeadings(content, title);
      element.innerHTML = renderToStaticMarkup(<ArticleBody source={content} document={parsed} originalUrl={`https://balizero.com/${path.replace(/\.mdx$/, "")}`} title={title} />);
      const actual = [...element.querySelectorAll("h2[id],h3[id]")].map((node) => normalized(node.textContent ?? ""));
      const renderedText = normalized(element.textContent ?? "");
      const components: { name: string; offset: number; issues: string[]; excludedProps: string[]; formula?: string }[] = [];
      const missingMarkdown: number[] = [];
      function scan(nodes: ReadingNode[]): void {
        for (const node of nodes) {
          if (node.kind === "markdown") {
            for (const child of node.tree.children) {
              // Inline markup can create distinct DOM text boundaries. Each
              // AST leaf remains independently traceable, including list/table cells.
              const visit = (part: typeof child): void => {
                if (part.type === "text" && !renderedText.includes(normalized(part.value))) missingMarkdown.push(part.position?.start.offset ?? node.offset);
                if ("children" in part) part.children.forEach((item) => visit(item as typeof child));
              }; visit(child);
            }
          } else {
            componentCounts[node.name] = (componentCounts[node.name] ?? 0) + 1;
            propCounts[node.name] ??= {};
            for (const key of Object.keys(node.props)) propCounts[node.name][key] = (propCounts[node.name][key] ?? 0) + 1;
            const projected = publicComponentData(node.props) as Record<string, unknown>;
            components.push({ name: node.name, offset: node.offset, issues: node.issues, excludedProps: Object.keys(node.props).filter((key) => !(key in projected)), ...(node.expressionDigests.calculateResult ? { formula: node.expressionDigests.calculateResult } : {}) });
            scan(node.children);
          }
        }
      }
      scan(parsed.nodes);
      rows.push({ path, sha256: createHash("sha256").update(raw).digest("hex"), sourceHeadings: expected.length, renderedHeadings: actual.length,
        headingsMatch: JSON.stringify(expected) === JSON.stringify(actual), ...(JSON.stringify(expected) !== JSON.stringify(actual) ? { expected, actual } : {}),
        missingMarkdown, components, parserIssues: parsed.issues });
    } catch (error) { rows.push({ path, inaccessible: error instanceof Error ? error.message : "Unreadable source" }); }
  }
  const report = { checkedAt: new Date().toISOString(), root, sources: files.length,
    inaccessible: rows.filter((row) => row.inaccessible), headingMismatches: rows.filter((row) => row.headingsMatch === false).map((row) => row.path),
    markdownMismatches: rows.filter((row) => Array.isArray(row.missingMarkdown) && row.missingMarkdown.length).map((row) => row.path),
    componentCounts, unsupported: Object.keys(componentCounts).filter((name) => !supportedArticleComponents.has(name)), propCounts, rows };
  writeFileSync(process.env.ARTICLE_CORPUS_REPORT!, JSON.stringify(report, null, 2));
  report.sources = sources.length;
  writeFileSync(process.env.ARTICLE_CORPUS_REPORT!, JSON.stringify(report, null, 2));
  expect(sources.length).toBeGreaterThan(0);
  expect(report.inaccessible).toEqual([]);
  expect(report.headingMismatches).toEqual([]);
  expect(report.markdownMismatches).toEqual([]);
}, 300000);
