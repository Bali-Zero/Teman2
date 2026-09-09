import { parse, parseExpressionAt, type Node as JsNode } from "acorn";
import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkGfm from "remark-gfm";
import { toString } from "mdast-util-to-string";
import type { Root, RootContent } from "mdast";
import { createHash } from "node:crypto";

export type Data = string | number | boolean | null | Data[] | { [key: string]: Data };
export type ReadingNode = { kind: "markdown"; source: string; offset: number; tree: Root; inlineGlossaries?: Record<string, ComponentNode> } | ComponentNode;
export interface ComponentNode {
  kind: "component"; name: string; props: Record<string, Data>; children: ReadingNode[];
  offset: number; end: number; issues: string[]; expressionDigests: Record<string, string>;
}
export interface Heading { id: string; text: string; depth: number }
export interface ReadingDocument { nodes: ReadingNode[]; headings: Heading[]; headingIds: string[]; issues: { offset: number; reason: string }[] }
export const markdownParser = unified().use(remarkParse).use(remarkGfm);

/** A data decoder, NOT an interpreter. No calls, member access, templates with
 * expressions, spreads, getters, assignments, imports or functions are accepted. */
export function literalData(source: string): Data {
  const ast = parseExpressionAt(source, 0, { ecmaVersion: "latest" });
  if (source.slice(ast.end).trim()) throw new Error("Expression is not literal data");
  let budget = 10000;
  function read(raw: JsNode, depth: number): Data {
    if (--budget < 0 || depth > 24) throw new Error("Literal data exceeds limits");
    const node = raw as JsNode & Record<string, unknown>;
    if (node.type === "Literal" && (node.value === null || typeof node.value === "string" || typeof node.value === "boolean" || typeof node.value === "number" && Number.isFinite(node.value))) return node.value as Data;
    if (node.type === "UnaryExpression" && node.operator === "-" && (node.argument as JsNode).type === "Literal") {
      const value = read(node.argument as JsNode, depth + 1);
      if (typeof value === "number") return -value;
    }
    if (node.type === "ArrayExpression") return (node.elements as JsNode[]).map((child) => { if (!child) throw new Error("Sparse data"); return read(child, depth + 1); });
    if (node.type === "ObjectExpression") {
      const result: Record<string, Data> = Object.create(null);
      for (const rawProp of node.properties as JsNode[]) {
        const prop = rawProp as JsNode & Record<string, unknown>;
        if (prop.type !== "Property" || prop.kind !== "init" || prop.method || prop.computed || prop.shorthand) throw new Error("Non-data property");
        const keyNode = prop.key as JsNode & { name?: string; value?: unknown };
        const key = keyNode.type === "Identifier" ? keyNode.name : keyNode.value;
        if (typeof key !== "string" || ["__proto__", "prototype", "constructor"].includes(key) || Object.hasOwn(result, key)) throw new Error("Unsafe or duplicate key");
        result[key] = read(prop.value as JsNode, depth + 1);
      }
      return result;
    }
    throw new Error("Executable expression excluded");
  }
  return read(ast, 0);
}

// Balanced lexical boundaries prevent a paired opener consuming a later />.
// An incomplete tag stops before a Markdown heading and recovers its siblings.
function delimitedEnd(source: string, start: number, opening: string, closing: string): number {
  let depth = 0, quote = "", lineComment = false, blockComment = false;
  for (let index = start; index < source.length; index++) {
    const char = source[index], next = source[index + 1];
    if (char === "\n" && /^#{1,6}\s/.test(source.slice(index + 1))) return -1;
    if (lineComment) { if (char === "\n") lineComment = false; continue; }
    if (blockComment) { if (char === "*" && next === "/") { blockComment = false; index++; } continue; }
    if (quote) { if (char === "\\") index++; else if (char === quote) quote = ""; continue; }
    if (char === '"' || char === "'" || char === "`") { quote = char; continue; }
    if (char === "/" && next === "/") { lineComment = true; index++; continue; }
    if (char === "/" && next === "*") { blockComment = true; index++; continue; }
    if (char === opening) depth++;
    if (char === closing && --depth === 0) return index + 1;
  }
  return -1;
}

interface Tag { name: string; close: boolean; selfClosing: boolean; props: Record<string, Data>; issues: string[]; end: number; expressionDigests: Record<string, string> }
function readTag(source: string, start: number): Tag | null {
  const match = /^<(\/)?([A-Za-z][\w.:-]*)(?=[\s/>])/.exec(source.slice(start));
  if (!match) return null;
  // A monetary comparison such as "<USD 1 million" is prose, not JSX.
  if (/^\s+\d/.test(source.slice(start + match[0].length))) return null;
  const result: Tag = { name: match[2], close: !!match[1], selfClosing: false, props: Object.create(null), issues: [], end: start, expressionDigests: {} };
  let index = start + match[0].length;
  const seen = new Set<string>();
  const malformed = (): Tag => ({ ...result, end: source.indexOf("\n", start) < 0 ? source.length : source.indexOf("\n", start), selfClosing: true, issues: [...result.issues, "Incomplete component; following text preserved"] });
  while (index < source.length) {
    while (/\s/.test(source[index] ?? "") && index < source.length) index++;
    if (/^#{1,6}\s/.test(source.slice(index))) return malformed();
    if (source[index] === ">" || source.slice(index, index + 2) === "/>") {
      result.selfClosing = source[index] === "/";
      result.end = index + (result.selfClosing ? 2 : 1);
      return result;
    }
    if (source[index] === "{") {
      const end = delimitedEnd(source, index, "{", "}");
      if (end < 0) return malformed();
      result.issues.push("Spread attributes excluded"); index = end; continue;
    }
    const attribute = /^[\w:-]+/.exec(source.slice(index));
    if (!attribute) return malformed();
    const rawKey = attribute[0]; index += rawKey.length;
    // Some owned sources use a JSON-style colon for a quoted JSX attribute.
    // Recover that literal value explicitly instead of losing every later prop.
    const colon = rawKey.endsWith(":");
    const key = colon ? rawKey.slice(0, -1) : rawKey;
    if (colon) result.issues.push(`Recovered colon attribute ${key}`);
    while (/\s/.test(source[index] ?? "") && index < source.length) index++;
    let value: Data = true;
    if (source[index] === "=" || colon) {
      if (!colon) index++;
      while (/\s/.test(source[index] ?? "") && index < source.length) index++;
      const begin = index;
      if (source[index] === "{") {
        const end = delimitedEnd(source, index, "{", "}");
        if (end < 0) return malformed();
        index = end;
        try { value = literalData(source.slice(begin + 1, end - 1)); }
        catch { result.issues.push(`Non-literal ${key} excluded`); result.expressionDigests[key] = createHash("sha256").update(source.slice(begin + 1, end - 1).trim()).digest("hex"); continue; }
      } else if (source[index] === '"' || source[index] === "'") {
        const quote = source[index++];
        while (index < source.length && source[index] !== quote) {
          if (source[index] === "\n" && /^#{1,6}\s/.test(source.slice(index + 1))) return malformed();
          if (source[index] === "\\") index++; index++;
        }
        if (index >= source.length) return malformed();
        index++;
        // JSX strings are text, not JS expressions. Acorn decodes escaped strings.
        try { value = literalData(source.slice(begin, index)); }
        catch { value = source.slice(begin + 1, index - 1); }
      } else { result.issues.push(`Invalid ${key} excluded`); while (index < source.length && !/[\s>]/.test(source[index])) index++; continue; }
    }
    if (/^on/i.test(key) || ["__proto__", "prototype", "constructor", "dangerouslySetInnerHTML", "style"].includes(key)) { result.issues.push(`Unsafe ${key} excluded`); continue; }
    if (seen.has(key)) { delete result.props[key]; result.issues.push(`Duplicate ${key} excluded`); continue; }
    seen.add(key);
    result.props[key] = value;
  }
  return malformed();
}

function visit(node: Root | RootContent, fn: (node: RootContent) => void): void {
  if (node.type !== "root") fn(node);
  if ("children" in node) for (const child of node.children) visit(child as RootContent, fn);
}

/** Rejoin only inline glossary terms with their surrounding Markdown. Block
 * components remain separate. Build from accepted chunks, never from a whole
 * source range that could reintroduce an excluded import or expression. */
function inlineGlossaries(nodes: ReadingNode[], source: string): ReadingNode[] {
  const result: ReadingNode[] = [], group: ReadingNode[] = [];
  const isInline = (node: ComponentNode): boolean => node.name === "GlossaryTerm" && !node.issues.length &&
    !!(source.slice(source.lastIndexOf("\n", node.offset - 1) + 1, node.offset).trim() ||
      source.slice(node.end, source.indexOf("\n", node.end) < 0 ? source.length : source.indexOf("\n", node.end)).trim());
  const flush = (): void => {
    if (!group.some((node) => node.kind === "component")) { result.push(...group); group.length = 0; return; }
    const glossary: Record<string, ComponentNode> = {};
    let text = "", previousEnd = group[0].offset;
    for (const node of group) {
      const gap = source.slice(previousEnd, node.offset);
      text += gap.trim() ? "\n\n" : gap;
      if (node.kind === "markdown") { text += node.source; previousEnd = node.offset + node.source.length; }
      else {
        let marker = `bz-inline-glossary-${node.offset}`;
        while (source.includes(marker)) marker += "-term";
        glossary[marker] = node; text += marker; previousEnd = node.end;
      }
    }
    const tree = markdownParser.parse(text);
    function replace(parent: Root | RootContent, linked = false): void {
      if (!("children" in parent)) return;
      parent.children = parent.children.flatMap((child) => {
        if (child.type !== "text") { replace(child as RootContent, linked || child.type === "link" || child.type === "linkReference"); return [child]; }
        const pieces: RootContent[] = [];
        let remaining = child.value;
        while (remaining) {
          const next = Object.keys(glossary).map((marker) => ({ marker, at: remaining.indexOf(marker) })).filter(({ at }) => at >= 0).sort((a, b) => a.at - b.at)[0];
          if (!next) { pieces.push({ type: "text", value: remaining }); break; }
          if (next.at) pieces.push({ type: "text", value: remaining.slice(0, next.at) });
          const node = glossary[next.marker];
          const label = node.children.map((part) => part.kind === "markdown" ? toString(part.tree) : "").join("") || dataText(node.props.term);
          pieces.push({ type: "emphasis", children: [{ type: "text", value: label }], data: { hName: "span", hProperties: { id: `${linked ? "linked-" : ""}${next.marker}` } } });
          remaining = remaining.slice(next.at + next.marker.length);
        }
        return pieces;
      }) as typeof parent.children;
    }
    replace(tree);
    result.push({ kind: "markdown", source: text, offset: group[0].offset, tree, inlineGlossaries: glossary });
    group.length = 0;
  };
  for (const node of nodes) {
    if (node.kind === "component") node.children = inlineGlossaries(node.children, source);
    if (node.kind === "markdown" || isInline(node)) group.push(node);
    else { flush(); result.push(node); }
  }
  flush(); return result;
}

export function headingId(text: string, used: Map<string, number>): string {
  const base = text.toLowerCase().normalize("NFKC").replace(/[^\p{L}\p{N}\s-]/gu, "").trim().replace(/\s+/g, "-") || "section";
  let occurrence = (used.get(base) ?? 0) + 1;
  let id = occurrence === 1 ? base : `${base}-${occurrence}`;
  while (used.has(id)) id = `${base}-${++occurrence}`;
  used.set(base, occurrence);
  used.set(id, used.get(id) ?? 1);
  return id;
}

/** Tolerant MDX projection: Markdown AST + a balanced component tree. It does
 * not compile MDX, resolve imports, execute expressions or spread source props. */
export function parseArticle(source: string, title?: string): ReadingDocument {
  const document: ReadingDocument = { nodes: [], headings: [], headingIds: [], issues: [] };
  const stack: ComponentNode[] = [];
  const children = (): ReadingNode[] => stack.at(-1)?.children ?? document.nodes;
  const used = new Map<string, number>();
  const protections: { start: number; end: number }[] = [];
  visit(markdownParser.parse(source), (node) => {
    if (node.type === "code" || node.type === "inlineCode") protections.push({ start: node.position!.start.offset!, end: node.position!.end.offset! });
  });
  let protection = 0, textStart = 0, index = 0;
  const flush = (end: number): void => {
    const text = source.slice(textStart, end);
    if (!text.trim()) return;
    const tree = markdownParser.parse(text);
    children().push({ kind: "markdown", source: text, offset: textStart, tree });
  };
  const recordHeadings = (tree: Root, offset: number): void => {
    visit(tree, (node) => {
      if (node.type !== "heading") return;
      const label = toString(node);
      if (!label.trim()) { node.data = { hName: "span", hProperties: { hidden: true } }; document.issues.push({ offset: offset + (node.position?.start.offset ?? 0), reason: "Empty source heading excluded from navigation" }); return; }
      if (node.depth === 1 && title && label.trim() === title.trim()) { node.data = { hName: "span", hProperties: { hidden: true, "data-repeated-title": true } }; return; }
      const depth = node.depth === 1 ? 2 : node.depth;
      const id = headingId(label, used);
      document.headingIds.push(id);
      node.depth = depth;
      node.data = { hProperties: { id, tabIndex: -1 } };
      if (depth <= 3) document.headings.push({ id, text: label, depth });
    });
  };
  while (index < source.length) {
    while (protections[protection]?.end <= index) protection++;
    if (protections[protection]?.start <= index) { index = protections[protection].end; continue; }
    // Parse one complete ESM statement, without loading it. Do not consume
    // adjacent prose just because an import lacks a following blank line.
    if ((index === 0 || source[index - 1] === "\n") && /^(?:import|export)\s/.test(source.slice(index))) {
      let end = index, statementEnd = -1;
      for (let line = 0; line < 100 && end < source.length; line++) {
        end = source.indexOf("\n", end + 1); if (end < 0) end = source.length;
        const candidate = source.slice(index, end);
        if (/\n\s*\n|\n#{1,6}\s/.test(candidate)) break;
        try {
          const program = parse(candidate, { sourceType: "module", ecmaVersion: "latest" });
          if (program.body.length === 1 && /^(Import|Export)/.test(program.body[0].type)) statementEnd = end;
          break;
        } catch { /* Continue a multiline declaration, never evaluate. */ }
      }
      if (statementEnd >= 0) {
        flush(index); document.issues.push({ offset: index, reason: "ESM excluded; never loaded" });
        index = statementEnd; textStart = index; continue;
      }
    }
    // MDX comments carry no reader content. An expression stays inert and is
    // represented explicitly, without exposing its executable source.
    if (source[index] === "{") {
      const end = delimitedEnd(source, index, "{", "}");
      if (end > index) {
        const expression = source.slice(index + 1, end - 1).trim();
        const comment = expression.startsWith("/*") && expression.endsWith("*/");
        let executable = false;
        try { const ast = parseExpressionAt(expression, 0, { ecmaVersion: "latest" }); executable = !expression.slice(ast.end).trim(); } catch { /* Ordinary braces stay as text. */ }
        if (comment || executable) {
          flush(index);
          if (!comment) children().push({ kind: "component", name: "Expression", props: {}, children: [], offset: index, end, issues: ["Inline expression excluded"], expressionDigests: {} });
          index = end; textStart = end; continue;
        }
      }
    }
    const tag = source[index] === "<" ? readTag(source, index) : null;
    if (!tag) { index++; continue; }
    flush(index);
    if (!tag.close && ["script", "style", "object", "embed"].includes(tag.name)) {
      const close = source.indexOf(`</${tag.name}>`, tag.end);
      const nextHeading = source.slice(tag.end).search(/\n#{1,6}\s/);
      const boundary = nextHeading < 0 ? source.length : tag.end + nextHeading;
      const end = close >= 0 && close < boundary ? close + tag.name.length + 3 : Math.min(boundary, source.indexOf("\n", tag.end) < 0 ? source.length : source.indexOf("\n", tag.end));
      children().push({ kind: "component", name: tag.name, props: {}, children: [], offset: index, end, issues: ["Executable embed excluded"], expressionDigests: {} });
      index = end; textStart = end; continue;
    }
    if (tag.close) {
      const matching = stack.findLastIndex((node) => node.name === tag.name);
      if (matching < 0) document.issues.push({ offset: index, reason: `Unmatched closing ${tag.name}` });
      else {
        for (const node of stack.splice(matching)) { node.end = tag.end; if (node.name !== tag.name) node.issues.push("Unclosed nested component"); }
      }
    } else {
      const node: ComponentNode = { kind: "component", name: tag.name, props: tag.props, children: [], offset: index, end: tag.end, issues: tag.issues, expressionDigests: tag.expressionDigests };
      children().push(node);
      if (!tag.selfClosing && !["img", "br", "hr", "input", "source"].includes(tag.name)) stack.push(node);
    }
    index = tag.end; textStart = index;
  }
  flush(source.length);
  for (const node of stack) { node.end = source.length; node.issues.push("Unclosed component; remaining text preserved"); }
  document.nodes = inlineGlossaries(document.nodes, source);
  const headings = (nodes: ReadingNode[]): void => {
    for (const node of nodes) {
      if (node.kind === "markdown") recordHeadings(node.tree, node.offset);
      else headings(node.children);
    }
  };
  headings(document.nodes);
  return document;
}

export const isDataRecord = (value: Data | undefined): value is Record<string, Data> => value !== null && typeof value === "object" && !Array.isArray(value);
export const dataText = (value: Data | undefined): string => typeof value === "string" ? value : "";
export const dataRows = (value: Data | undefined): Record<string, Data>[] => Array.isArray(value) ? value.filter(isDataRecord) : [];
