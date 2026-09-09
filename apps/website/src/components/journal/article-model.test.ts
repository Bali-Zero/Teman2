import { describe, expect, it } from "vitest";
import { literalData, parseArticle } from "./article-model";

describe("inert article projection", () => {
  it("decodes data, never executable syntax", () => {
    expect(literalData("[{title: 'Text', value: -2, yes: true, empty: null}]" )).toEqual([{title: "Text", value: -2, yes: true, empty: null}]);
    for (const source of ["process.exit()", "({get x(){ return 1 }})", "{...secret}", "()=>1", "globalThis.x=1", "`hello ${secret}`", "{__proto__: {a:1}}", "{x:1,x:2}", "[1,,2]", "1; alert(1)"]) expect(() => literalData(source), source).toThrow();
  });
  it("balances paired and self-closing siblings with complete Markdown sections", () => {
    const doc = parseArticle('<InfoCard title="Note">\nA paragraph.\n</InfoCard>\n\n## One\n\n- Keep this\n\n<Calculator fields={[]} calculateResult={() => ({n: 4})} />\n\n### Two\n\nEnd.');
    expect(doc.headings.map((h) => h.text)).toEqual(["One", "Two"]);
    expect(JSON.stringify(doc)).toContain("Keep this");
    expect(doc.nodes.filter((node) => node.kind === "component").map((node) => node.name)).toEqual(["InfoCard", "Calculator"]);
  });
  it("removes only complete imports and keeps neighboring prose", () => {
    const doc = parseArticle('import { A,\nB } from "dangerous";\nProse directly afterward.\n\n## Next\nText');
    expect(JSON.stringify(doc.nodes)).not.toContain("dangerous");
    expect(JSON.stringify(doc.nodes)).toContain("Prose directly afterward.");
    expect(doc.headings).toHaveLength(1);
  });
  it("recovers incomplete attributes before the next heading", () => {
    for (const bad of ['<InfoCard title="unfinished', '<Calculator fields={[{ value: 4', '<Widget thing={oops']) {
      const doc = parseArticle(`${bad}\n\n## Recovery\n\nImportant text.`);
      expect(doc.headings.map((h) => h.text), bad).toEqual(["Recovery"]);
      expect(JSON.stringify(doc)).toContain("Important text.");
    }
  });
  it("protects fenced and inline examples, stable duplicate IDs, and a repeated title", () => {
    const doc = parseArticle('# Title\n\n## Same\n\n`<InfoCard />`\n\n```mdx\n<Widget />\n```\n\n## Same', 'Title');
    expect(doc.headings.map((h) => h.id)).toEqual(["same", "same-2"]);
    expect(doc.nodes.every((node) => node.kind === "markdown")).toBe(true);
  });
  it("excludes source expressions and comments without executing them", () => {
    const doc = parseArticle('Start\n\n{/* private implementation */}\n{globalThis.hacked = true}\n\n## End');
    expect(JSON.stringify(doc)).not.toContain("private implementation");
    expect(JSON.stringify(doc)).not.toContain("globalThis");
    expect(doc.headings[0].text).toBe("End");
  });
  it("reserves emitted heading IDs including natural numeric suffixes and deep headings", () => {
    const doc = parseArticle('## Same\n\n## Same\n\n## Same 2\n\n#### Same\n\n##### Same 4\n\n###### Same\n\n## Same');
    expect(doc.headingIds).toEqual(["same", "same-2", "same-2-2", "same-3", "same-4", "same-5", "same-6"]);
    expect(doc.headings.map((heading) => heading.id)).toEqual(["same", "same-2", "same-2-2", "same-6"]);
  });
  it("recovers a known malformed literal attribute without discarding the following checklist", () => {
    const doc = parseArticle('<Checklist title="Before signing" description: "Verify documents" items={[{label:"Check letter",required:true}]} />\n\n## Next');
    expect(doc.nodes[0]).toMatchObject({ kind: "component", props: { description: "Verify documents", items: [{label: "Check letter", required: true}] } });
    expect(doc.headings.map((heading) => heading.text)).toEqual(["Next"]);
  });
});
