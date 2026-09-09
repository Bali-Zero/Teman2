import { readFileSync } from "node:fs";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { parseArticle, type ComponentNode, type ReadingNode } from "./article-model";
import { ArticleInteraction } from "./ArticleInteraction";
import { checklistData, decisionData } from "./interaction-data";
const url = "https://balizero.com/property/leasehold-vs-freehold";
const source = readFileSync("../mouth/src/content/articles/property/leasehold-vs-freehold.mdx", "utf8");
function find(nodes: ReadingNode[]): ComponentNode | undefined { for (const node of nodes) if (node.kind === "component") { if (node.name === "DecisionTree") return node; const nested = find(node.children); if (nested) return nested; } }
const props = find(parseArticle(source).nodes)!.props;
function mount(): void { render(<ArticleInteraction name="DecisionTree" props={props} articleTitle="Leasehold vs Freehold" articleUrl={url} />); }
describe("authored property decision guide", () => {
  it("edits an earlier answer and discards dependent answers", () => {
    mount(); fireEvent.click(screen.getByRole("button", { name: /Yes, I have Indonesian residence permit/ }));
    fireEvent.click(screen.getByRole("button", { name: /Long-term/ }));
    fireEvent.click(screen.getByRole("button", { name: /Edit answer 1:/ }));
    expect(screen.getByRole("heading", { name: "Do you have KITAS or KITAP?" })).toBeVisible();
    expect(screen.queryByText("Long-term (5+ years)")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /No, I don't have KITAS/ }));
    expect(screen.getByRole("heading", { name: "Leasehold Only" })).toBeVisible();
    expect(screen.queryByRole("button", { name: /Edit answer 2:/ })).not.toBeInTheDocument();
  });
  it("reaches the no-residence result, explains the selected path, then resets", () => {
    mount(); fireEvent.click(screen.getByRole("button", { name: /No, I don't have KITAS/ }));
    expect(screen.getByRole("heading", { name: "Leasehold Only" })).toBeVisible();
    expect(screen.getByText("Your route")).toBeVisible();
    expect(decodeURIComponent(screen.getByRole("link", { name: /Discuss this article outcome/ }).getAttribute("href")!)).toContain(url);
    fireEvent.click(screen.getByRole("button", { name: "Start again" }));
    expect(screen.getByRole("heading", { name: "Do you have KITAS or KITAP?" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Start again" })).toBeDisabled();
  });
  it("takes long-term and flexible alternatives with Previous preserving the earlier answer", () => {
    mount(); fireEvent.click(screen.getByRole("button", { name: /Yes, I have Indonesian residence permit/ }));
    fireEvent.click(screen.getByRole("button", { name: /Long-term/ }));
    expect(screen.getByRole("heading", { name: "Consider Hak Pakai" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /Previous question/ }));
    expect(screen.getByRole("heading", { name: /How long do you plan/ })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /Uncertain/ }));
    expect(screen.getByRole("heading", { name: "Leasehold May Be Easier" })).toBeVisible();
    expect(screen.queryByText("Long-term (5+ years)")).not.toBeInTheDocument();
  });
  it("rejects dangling transitions, duplicate nodes, cycles and incomplete results", () => {
    expect(decisionData(props)).not.toBeNull();
    for (const nodes of [ [{ id: "start", question: "Q", options: [{ label: "A", next: "missing" }] }], [{ id: "start", question: "Q", options: [{ label: "A", next: "start" }] }], [{ id: "start", isResult: true, result: { title: "Incomplete" } }], [{ id: "x" }, { id: "x" }]]) expect(decisionData({ nodes })).toBeNull();
  });
});
describe("checklist", () => {
  it("restores the exact selection with Undo reset and invalidates undo after a new change", () => {
    render(<ArticleInteraction name="Checklist" articleTitle="Test" articleUrl={url} props={{ title: "Preparation", items: [{ text: "First step", group: "Documents" }, { text: "Second step", group: "Documents" }] }} />);
    const items = screen.getAllByRole("checkbox"); fireEvent.click(items[1]);
    fireEvent.click(screen.getByRole("button", { name: "Reset checklist" }));
    fireEvent.click(screen.getByRole("button", { name: "Undo reset" }));
    expect(items[0]).not.toBeChecked(); expect(items[1]).toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "Reset checklist" })); fireEvent.click(items[0]);
    expect(screen.queryByRole("button", { name: "Undo reset" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Documents/ })).toBeVisible();
  });
  it("preserves legacy labels, details and required state; counts and resets checked items", () => {
    render(<ArticleInteraction name="Checklist" articleTitle="Test" articleUrl={url} props={{ title: "Preparation", items: [{ text: "First step", description: "Explanation from source.", subItems: ["Detail from source"], required: true }, { label: "Second step", group: "Documents", category: "Identity" }] }} />);
    expect(screen.getByRole("button", { name: "Reset checklist" })).toBeDisabled();
    const items = screen.getAllByRole("checkbox"); items.forEach((item) => fireEvent.click(item));
    expect(screen.getByRole("status")).toHaveTextContent("2 of 2 complete · Checklist complete");
    expect(screen.getByText("Explanation from source. Detail from source")).toBeVisible();
    expect(screen.getByText("Documents / Identity")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Reset checklist" }));
    items.forEach((item) => expect(item).not.toBeChecked());
    expect(screen.getByRole("progressbar")).toHaveAttribute("value", "0");
  });
  it("does not fabricate missing items", () => {
    expect(checklistData({ items: [{ label: "Valid" }, {}] })).toBeNull();
    render(<ArticleInteraction name="Checklist" articleTitle="Test" articleUrl={url} props={{ title: "Incomplete" }} />);
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
  });
});
