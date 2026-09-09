import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import matter from "gray-matter";
import { ArticleBody, safeArticleUrl } from "./ArticleBody";
import { parseArticle } from "./article-model";

describe("article reading surface", () => {
  it("renders owned Markdown headings, lists, sources and tables without executing MDX", () => {
    const { container } = render(<ArticleBody originalUrl="https://balizero.com/business/story" source={'## The context\n\nA **clear** paragraph.\n\n- One item\n\n[Source](https://example.org/source)\n\n| Topic | Note |\n| --- | --- |\n| One | Two |\n\n<script>window.hacked = true</script>'} />);
    expect(screen.getByRole("heading", { level: 2, name: "The context" })).toBeVisible();
    expect(screen.getByRole("listitem")).toHaveTextContent("One item");
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(container.querySelector("script")).toBeNull();
    expect(screen.getByRole("link", { name: "Source" })).toHaveAttribute("href", "https://example.org/source");
  });
  it("translates literal display strings and retains useful notes", () => {
    const source = '<InfoCard title="Summary" items={[{ label: "Topic", value: "Published context", note: "Useful detail", clientId: "PRIVATE_RECORD" }]} />\n\n<AskZantara />';
    const { container } = render(<ArticleBody source={source} originalUrl="https://balizero.com/business/story" />);
    expect(screen.getByText("Published context")).toBeVisible();
    expect(container.querySelector('dt')?.textContent).toBe("Topic");
    expect(container.querySelector('dd')).toHaveTextContent("Published context");
    expect(container.querySelector('dd')).toHaveTextContent("Useful detail");
    expect([...container.querySelectorAll('dt')].map((node) => node.textContent)).not.toEqual(expect.arrayContaining(["Items", "Label", "Value"]));
    expect(container.textContent).not.toContain("PRIVATE_RECORD");
  });
  it("restores all 24 real property sections, substantive prose and comparisons", () => {
    const source = matter(readFileSync(resolve('../mouth/src/content/articles/property/leasehold-vs-freehold.mdx'), 'utf8'));
    const doc = parseArticle(source.content, source.data.title);
    const expected = [...source.content.matchAll(/^#{2,3} (.+)$/gm)].map((match) => match[1]);
    const { container } = render(<ArticleBody source={source.content} document={doc} originalUrl="https://balizero.com/property/leasehold-vs-freehold" />);
    expect(expected).toHaveLength(24);
    expect([...container.querySelectorAll('h2,h3')].map((node) => node.textContent)).toEqual(expected);
    for (const phrase of ["Religious organizations", "Owner may not extend", "When you want to exit a leasehold", "Landowner disputes", "5-year remaining lease", "In prime tourist areas"]) expect(container.textContent).toContain(phrase);
    expect(container.querySelectorAll('table')).toHaveLength(3);
    expect(container.textContent).toContain('IDR 4,000,000,000');
    expect(container.textContent).not.toContain('calculateResult');
  });
  it("retains unsupported public notes and children without private props", () => {
    const {container} = render(<ArticleBody originalUrl="https://balizero.com/business/story" source={'<UnknownFeature title="Summary" clientRecord={{name:"SECRET_RECORD"}} items={[{label:"Topic",value:"Published context"}]} >\n\nBody explanation.\n\n</UnknownFeature>\n\n## After\n\nStill present.'} />);
    expect(container.textContent).toContain("Body explanation.");
    expect(container.textContent).toContain("Still present.");
    expect(container.textContent).not.toContain("SECRET_RECORD");
    expect(container.textContent).toContain("presented as readable article notes");
  });
  it("binds the villa worked example to its exact source and default inputs", () => {
    const source = matter(readFileSync(resolve('../mouth/src/content/articles/property/villa-purchase-bali.mdx'), 'utf8')).content;
    const { container, rerender } = render(<ArticleBody source={source} originalUrl="https://balizero.com/property/villa-purchase-bali" />);
    expect(container.textContent).toContain("IDR 5,350,000,000");
    rerender(<ArticleBody source={source.replace("defaultValue: 5000000000", "defaultValue: 6000000000")} originalUrl="https://balizero.com/property/villa-purchase-bali" />);
    expect(container.textContent).not.toContain("IDR 5,350,000,000");
    expect(container.textContent).toContain("no stored result");
  });
  it("keeps legal consequences, decision explanations and malformed adjacent prose", () => {
    const { container } = render(<ArticleBody originalUrl="https://balizero.com/property/story" source={'<LegalDecoder title="Law" summary="Published summary" sections={[{original:"Rule",impact:"Practical consequence",severity:"high"}]} />\n\n<script>unsafe()\n\n## After\n\nCost <USD 1 million.\n\n###\n\nStill readable.'} />);
    expect(container.textContent).toContain("Practical consequence");
    expect(container.textContent).toContain("Published summary");
    expect(container.textContent).toContain("Cost <USD 1 million.");
    expect(container.textContent).toContain("Still readable.");
    expect(container.textContent).not.toContain("unsafe()");
    expect([...container.querySelectorAll("h2,h3")].map((node) => node.textContent)).toEqual(["After"]);
  });
  it("rejects executable/credential URLs and preserves safe source/anchor links", () => {
    expect(safeArticleUrl("javascript:alert(1)")).toBe("");
    expect(safeArticleUrl("https://user:secret@example.org")).toBe("");
    expect(safeArticleUrl("#context")).toBe("#context");
    expect(safeArticleUrl("/business/story")).toBe("/business/story");
  });
  it("retains the authored email link in the owned spouse KITAS article", () => {
    const source = matter(readFileSync(resolve('../mouth/src/content/articles/immigration/e31b-spouse-dependent-kitas-guide.mdx'), 'utf8')).content;
    render(<ArticleBody source={source} originalUrl="https://balizero.com/visas/e31b-spouse-dependent-kitas-guide" />);
    expect(screen.getByRole("link", { name: "hello@balizero.com" })).toHaveAttribute("href", "mailto:hello@balizero.com");
  });
});
