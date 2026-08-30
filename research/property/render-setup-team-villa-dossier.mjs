#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const sourcePath = path.join(repoRoot, "research/property/2026-08-31-bali-villa-operator-architecture.md");
const cssPath = path.join(repoRoot, "skills/bali-zero-brand/surfaces/internal-print-a4/_template.css");
const outputDir = path.join(repoRoot, "output/pdf");
const htmlDir = path.join(outputDir, "source");
const htmlPath = path.join(htmlDir, "Bali_Zero_Setup_Team_Villa_Operator_Architecture.html");
const pdfPath = path.join(outputDir, "Bali_Zero_Setup_Team_Villa_Operator_Architecture.pdf");

const runtimeModules = process.env.CODEX_RUNTIME_NODE_MODULES;
if (!runtimeModules) {
  throw new Error("Set CODEX_RUNTIME_NODE_MODULES to the bundled Codex node_modules path.");
}
const { marked } = await import(pathToFileURL(path.join(runtimeModules, "marked/lib/marked.esm.js")).href);

const raw = fs.readFileSync(sourcePath, "utf8");
const frontmatter = raw.match(/^---\n([\s\S]*?)\n---\n/);
if (!frontmatter) throw new Error("Expected YAML frontmatter in dossier source.");

const sourceUrls = frontmatter[1]
  .split("\n")
  .filter((line) => /^\s+- https?:\/\//.test(line))
  .map((line) => line.replace(/^\s+-\s+/, "").trim());

let markdownBody = raw.slice(frontmatter[0].length);
markdownBody = markdownBody.replace(/^# .+\n+/, "");
markdownBody = markdownBody
  .replace(/[–—]/g, "-")
  .replace(/→/g, "->")
  .replace(/☐/g, "[ ]")
  .replace(/☒/g, "[x]")
  .replace(/✓/g, "PASS")
  .replace(/⚠/g, "WARNING");

marked.setOptions({ gfm: true, breaks: false });
const dossierHtml = marked.parse(markdownBody);
const sourcesHtml = sourceUrls
  .map((url, index) => `<li><span class="source-index">${String(index + 1).padStart(2, "0")}</span><a href="${url}">${url}</a></li>`)
  .join("\n");

const documentHtml = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bali Zero - Setup Team Villa Operator Architecture</title>
<link rel="stylesheet" href="${pathToFileURL(cssPath).href}">
<style>
  .page { height: 297mm; max-height: 297mm; overflow: hidden; }
  .page-body { height: 224mm; overflow: hidden; position: relative; }
  .page-body > :first-child { margin-top: 0; }
  .doc-content { display: none; }
  .doc-content h2,
  .page-body h2 {
    font-size: 19pt;
    font-weight: 500;
    line-height: 1.15;
    letter-spacing: -0.01em;
    text-transform: uppercase;
    color: var(--bz-text-body);
    margin: 0 0 4mm 0;
    padding-bottom: 2.5mm;
    border-bottom: 1px solid var(--bz-gold);
    page-break-after: avoid;
  }
  .page-body h3 {
    text-transform: uppercase;
    margin-top: 4.5mm;
  }
  .page-body h4 {
    font-size: 9.5pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--bz-text-body);
    margin: 4mm 0 1.5mm;
    page-break-after: avoid;
  }
  .page-body blockquote {
    margin: 4mm 0 5mm;
    padding: 4mm 5mm;
    border-left: 3px solid var(--bz-gold);
    background: var(--bz-bg-callout);
    font-size: 11pt;
    font-weight: 600;
    line-height: 1.45;
  }
  .page-body blockquote p { margin: 0; }
  .page-body a { color: var(--bz-text-body); text-decoration-color: var(--bz-gold); }
  .page-body table.long-table { font-size: 7.5pt; }
  .page-body table.long-table th,
  .page-body table.long-table td { padding: 1.7mm 2mm; line-height: 1.28; }
  .page-body table.medium-table { font-size: 8.2pt; }
  .page-body table.medium-table th,
  .page-body table.medium-table td { padding: 2mm 2.4mm; line-height: 1.32; }
  .page-body ul.task-list { list-style: none; padding-left: 0; }
  .page-body ol:not(.source-list) { padding-left: 8mm; }
  .page-body input[type="checkbox"] { display: none; }
  .task-box {
    display: inline-block;
    width: 3.2mm;
    height: 3.2mm;
    border: 1px solid var(--bz-text-secondary);
    margin-right: 2mm;
    vertical-align: -0.45mm;
  }
  .task-box.checked { background: var(--bz-gold); border-color: var(--bz-gold); }
  .continuation-label {
    color: var(--bz-gold);
    font-size: 7.5pt;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin: 0 0 3mm;
  }
  .keep-group { display: flow-root; }
  .keep-group > :first-child { margin-top: 0; }
  .decision-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 2.2mm;
    margin-top: 2.5mm;
  }
  .decision-card {
    border-left: 3px solid var(--bz-gold);
    background: var(--bz-bg-callout);
    padding: 2.3mm 3mm;
    min-height: 17.5mm;
  }
  .decision-card.stop { border-left-color: var(--bz-red); background: var(--bz-bg-callout-red); }
  .decision-card .number {
    display: block;
    color: var(--bz-gold);
    font-size: 8pt;
    font-weight: 800;
    letter-spacing: 0.1em;
    margin-bottom: 1mm;
  }
  .decision-card.stop .number { color: var(--bz-red); }
  .decision-card p { font-size: 8.1pt; line-height: 1.28; margin: 0; }
  .team-line {
    color: var(--bz-gold);
    font-size: 12pt;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin: 0 0 5mm;
  }
  .status-row { display: flex; gap: 3mm; margin: 3mm 0 3.5mm; }
  .status-card {
    flex: 1;
    border-top: 3px solid var(--bz-gold);
    background: var(--bz-bg-callout);
    padding: 2.5mm;
  }
  .status-card.stop { border-top-color: var(--bz-red); background: var(--bz-bg-callout-red); }
  .status-card strong {
    display: block;
    font-size: 8pt;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 1mm;
  }
  .status-card span { display: block; font-size: 8.4pt; line-height: 1.35; }
  .source-list { list-style: none; padding-left: 0; margin: 0; }
  .source-list li {
    display: grid;
    grid-template-columns: 9mm 1fr;
    gap: 2mm;
    margin: 0 0 2.2mm;
    font-family: "SF Mono", Monaco, "Courier New", monospace;
    font-size: 7.2pt;
    line-height: 1.35;
    overflow-wrap: anywhere;
  }
  .source-index { color: var(--bz-gold); font-weight: 700; }
  .source-list a { color: var(--bz-text-secondary); text-decoration: none; }
  .cover-audience {
    margin-top: 5mm;
    color: var(--bz-text-light);
    font-size: 10pt;
    font-weight: 600;
    letter-spacing: 0.09em;
    text-transform: uppercase;
  }
</style>
</head>
<body>
<section class="cover">
  <div class="cover-header">
    <div class="cover-logo bz-logo-image"></div>
    <div class="cover-header-text">
      <div class="cover-eyebrow">BALI ZERO <span class="sep">·</span> INTERNAL OPERATING DOSSIER</div>
      <div class="cover-tagline">Powered by humans, fueled by a thinking engine.</div>
    </div>
  </div>
  <div class="cover-title-block">
    <h1 class="cover-title">VILLA OPERATOR<br>ARCHITECTURE</h1>
    <div class="cover-subtitle">PMA restrictions · Perseroan Perorangan · Tax flows</div>
    <div class="cover-rule"></div>
    <p class="cover-description">A decision manual for a lawful Bali villa owner-operator model under the targeted 2026 PMA restrictions. Includes KBLI gates, principal-agent revenue logic, unit economics, authority questions and a 30-day go/no-go pilot.</p>
    <div class="cover-audience">SETUP TEAM · ADIT · SURYA · ARI · KRISNA</div>
    <div class="cover-chips">
      <span class="cover-chip">KBLI 55203 / 55901</span>
      <span class="cover-chip">PP 20/2026</span>
      <span class="cover-chip">PBJT · PPh 23/26</span>
    </div>
  </div>
  <div class="cover-footer">
    <div>
      <div class="cover-footer-left">balizero.com <span class="sep">·</span> Kuta / Canggu / Denpasar</div>
      <div class="cover-footer-disclaimer">Decision status: pre-clearance. No structure moves before the written gates are closed.</div>
    </div>
    <div class="cover-footer-right">CUT-OFF · 31 AUG 2026</div>
  </div>
</section>

<div id="pages"></div>

<main id="source-content" class="doc-content">
  <section data-manual-page="decision-board">
    <div class="eyebrow">SETUP TEAM OPERATING BRIEF</div>
    <h2>DECISION BOARD</h2>
    <div class="team-line">ADIT · SURYA · ARI · KRISNA</div>
    <p class="lead">This dossier is designed for case setup, pre-clearance and go/no-go control. It does not assign internal roles. It gives the team one shared decision standard: the legal principal, operational substance, money flow, tax record and property permit chain must tell the same story.</p>
    <div class="status-row">
      <div class="status-card"><strong>BASELINE</strong><span>Owner-led villa with one lawful principal and one merchant-of-record chain.</span></div>
      <div class="status-card"><strong>CONDITIONAL</strong><span>Disclosed 55203/55901 management only after written authority confirmation.</span></div>
      <div class="status-card stop"><strong>NO-GO</strong><span>Paper operator, hidden foreign control, nominee economics or residual sweep.</span></div>
    </div>
    <div class="decision-grid">
      <div class="decision-card"><span class="number">01</span><p>Run one brownfield pilot only after written pre-clearance.</p></div>
      <div class="decision-card"><span class="number">02</span><p>Use the owner-led model as the baseline architecture.</p></div>
      <div class="decision-card stop"><span class="number">03</span><p>Do not use 55203 through a lessee or sublessee until <em>pemilik</em> is answered in writing.</p></div>
      <div class="decision-card"><span class="number">04</span><p>Keep guest contract, OTA, bank, receipt, refund, PBJT and accounting on the same principal.</p></div>
      <div class="decision-card"><span class="number">05</span><p>Require real WNI control, capital, risk, books and beneficial-ownership substance.</p></div>
      <div class="decision-card"><span class="number">06</span><p>Clear coordinates, zoning, KKPR, PBG, SLF and tourism requirements before entity design.</p></div>
      <div class="decision-card"><span class="number">07</span><p>Treat PP 20/2026 at 0.5% as tax treatment, never as a business licence.</p></div>
      <div class="decision-card"><span class="number">08</span><p>In a true management model, principal books guest gross and PBJT; manager books fee only.</p></div>
      <div class="decision-card"><span class="number">09</span><p>Give every rent, service, loan, royalty or commission lane independent substance and a benchmark.</p></div>
      <div class="decision-card"><span class="number">10</span><p>Protect investors through reporting, audit and valid security - never operating control.</p></div>
      <div class="decision-card stop"><span class="number">11</span><p>Reject shared OTP, foreign bank control, fixed nominee fee and automatic residual sweep.</p></div>
      <div class="decision-card stop"><span class="number">12</span><p>No incorporation, OTA migration, guest collection or launch before a signed go/no-go.</p></div>
    </div>
  </section>
  <section data-dossier-content>
    ${dossierHtml}
  </section>
  <section data-sources>
    <div class="eyebrow">EVIDENCE REGISTER</div>
    <h2>PRIMARY SOURCES</h2>
    <p class="lead">The dossier uses the following legal, government and authority-facing source locations. The operative test remains the primary text and the live OSS record for the exact entity, KBLI and property.</p>
    <ol class="source-list">${sourcesHtml}</ol>
  </section>
</main>

<script>
(() => {
  const pagesRoot = document.getElementById("pages");
  const sourceRoot = document.getElementById("source-content");
  let pageNumber = 0;
  let currentPage = null;
  let currentBody = null;
  let currentSection = "OPERATING DOSSIER";

  function makePage(sectionLabel = currentSection) {
    pageNumber += 1;
    const page = document.createElement("section");
    page.className = "page";
    page.innerHTML = [
      '<div class="page-header">',
      '  <div class="page-header-logo bz-logo-image"></div>',
      '  <div class="page-header-titles">',
      '    <div class="page-header-brand">BALI ZERO</div>',
      '    <div class="page-header-doc">Villa Operator Architecture · Setup Team</div>',
      '  </div>',
      '  <div class="page-header-num">hal. ' + String(pageNumber).padStart(2, "0") + '</div>',
      '</div>',
      '<div class="page-body" data-section="' + sectionLabel.replace(/"/g, "&quot;") + '"></div>',
      '<div class="page-footer">',
      '  <div>balizero.com <span style="margin: 0 4mm;">·</span> Penggunaan internal</div>',
      '  <div class="page-footer-right">Powered by humans, fueled by a thinking engine.</div>',
      '</div>',
    ].join("");
    pagesRoot.appendChild(page);
    currentPage = page;
    currentBody = page.querySelector(".page-body");
    return currentBody;
  }

  function overflows(body = currentBody) {
    return body.scrollHeight > body.clientHeight + 1;
  }

  function usedRatio(body = currentBody) {
    if (!body || !body.lastElementChild) return 0;
    const bodyTop = body.getBoundingClientRect().top;
    const contentBottom = body.lastElementChild.getBoundingClientRect().bottom;
    return Math.max(0, contentBottom - bodyTop) / body.clientHeight;
  }

  function normalizeNode(node) {
    const clone = node.cloneNode(true);
    if (clone.matches?.("table")) {
      const rows = clone.querySelectorAll("tbody tr").length;
      if (rows >= 11) clone.classList.add("long-table");
      else if (rows >= 8) clone.classList.add("medium-table");
    }
    clone.querySelectorAll?.('input[type="checkbox"]').forEach((input) => {
      const box = document.createElement("span");
      box.className = "task-box" + (input.checked ? " checked" : "");
      input.replaceWith(box);
    });
    return clone;
  }

  function addContinuation() {
    if (!currentSection) return;
    const label = document.createElement("div");
    label.className = "continuation-label";
    label.textContent = currentSection + " · CONTINUED";
    currentBody.appendChild(label);
  }

  function splitList(node) {
    const items = Array.from(node.children);
    let list = node.cloneNode(false);
    currentBody.appendChild(list);
    for (const item of items) {
      const itemClone = normalizeNode(item);
      list.appendChild(itemClone);
      if (overflows()) {
        list.removeChild(itemClone);
        makePage();
        addContinuation();
        list = node.cloneNode(false);
        currentBody.appendChild(list);
        list.appendChild(itemClone);
      }
    }
  }

  function splitTable(node) {
    const head = node.querySelector("thead");
    const rows = Array.from(node.querySelectorAll("tbody > tr"));
    const makeTable = () => {
      const table = node.cloneNode(false);
      if (head) table.appendChild(head.cloneNode(true));
      const body = document.createElement("tbody");
      table.appendChild(body);
      currentBody.appendChild(table);
      return { table, body };
    };
    let parts = makeTable();
    for (const row of rows) {
      const rowClone = row.cloneNode(true);
      parts.body.appendChild(rowClone);
      if (overflows()) {
        parts.body.removeChild(rowClone);
        makePage();
        addContinuation();
        parts = makeTable();
        parts.body.appendChild(rowClone);
      }
    }
  }

  function splitParagraph(node) {
    const words = node.textContent.trim().split(/\s+/);
    let paragraph = node.cloneNode(false);
    currentBody.appendChild(paragraph);
    let buffer = [];
    for (const word of words) {
      buffer.push(word);
      paragraph.textContent = buffer.join(" ");
      if (overflows()) {
        buffer.pop();
        paragraph.textContent = buffer.join(" ");
        makePage();
        addContinuation();
        paragraph = node.cloneNode(false);
        currentBody.appendChild(paragraph);
        buffer = [word];
        paragraph.textContent = word;
      }
    }
  }

  function appendNode(node) {
    const clone = normalizeNode(node);
    currentBody.appendChild(clone);
    if (!overflows()) return;
    currentBody.removeChild(clone);

    if (currentBody.children.length > 0) {
      makePage();
      addContinuation();
    }

    const fresh = normalizeNode(node);
    currentBody.appendChild(fresh);
    if (!overflows()) return;
    currentBody.removeChild(fresh);

    if (node.matches?.("ul, ol")) splitList(node);
    else if (node.matches?.("table")) splitTable(node);
    else if (node.matches?.("p")) splitParagraph(node);
    else currentBody.appendChild(fresh);
  }

  function flattenSections() {
    const nodes = [];
    for (const section of Array.from(sourceRoot.children)) {
      if (section.hasAttribute("data-manual-page")) {
        nodes.push({ type: "manual", node: section });
        continue;
      }
      for (const child of Array.from(section.children)) nodes.push({ type: "content", node: child });
    }
    return nodes;
  }

  function shouldKeepWithNext(node) {
    if (node.matches?.(".eyebrow, h2, h3, h4")) return true;
    return node.matches?.("p") && /:\s*$/.test(node.textContent.trim());
  }

  function keepSequence(entries, index) {
    const node = entries[index]?.node;
    const next = entries[index + 1];
    const afterNext = entries[index + 2];
    if (!node || next?.type !== "content") return [node].filter(Boolean);

    if (node.matches?.(".eyebrow") && next.node.matches?.("h2")) {
      const sequence = [node, next.node];
      if (afterNext?.type === "content" && afterNext.node.matches?.("p")) sequence.push(afterNext.node);
      return sequence;
    }

    if (node.matches?.("h2") && next.node.matches?.("h3, h4")) {
      const sequence = [node, next.node];
      if (afterNext?.type === "content" && !afterNext.node.matches?.("table")) sequence.push(afterNext.node);
      return sequence;
    }

    return shouldKeepWithNext(node) ? [node, next.node] : [node];
  }

  function appendKeepGroup(nodes) {
    if (nodes.length < 2 || nodes.slice(1).some((node) => node.matches?.("table"))) return false;
    const group = document.createElement("div");
    group.className = "keep-group";
    group.append(...nodes.map((node) => normalizeNode(node)));
    currentBody.appendChild(group);
    if (!overflows()) return true;

    group.remove();
    if (currentBody.children.length === 0) return false;
    makePage(currentSection);
    currentBody.appendChild(group);
    if (!overflows()) return true;

    group.remove();
    return false;
  }

  function paginate() {
    const entries = flattenSections();
    makePage("DECISION BOARD");
    for (let index = 0; index < entries.length; index += 1) {
      const { type, node } = entries[index];
      if (type === "manual") {
        for (const child of Array.from(node.children)) appendNode(child);
        makePage("FULL DOSSIER");
        continue;
      }

      if (node.matches?.("h2")) {
        currentSection = node.textContent.trim().toUpperCase();
        const used = usedRatio();
        if (currentBody.children.length && used > 0.72) makePage(currentSection);
      } else if (node.matches?.("h3, h4") && usedRatio() > 0.84) {
        makePage(currentSection);
      }

      const sequence = keepSequence(entries, index);
      const groupedH2 = sequence.find((entryNode) => entryNode.matches?.("h2"));
      if (groupedH2) currentSection = groupedH2.textContent.trim().toUpperCase();
      if (appendKeepGroup(sequence)) {
        index += sequence.length - 1;
        continue;
      }
      appendNode(node);
    }

    if (currentBody && currentBody.children.length === 0) {
      currentPage.remove();
      pageNumber -= 1;
    }
    document.body.dataset.paginated = "true";
    document.body.dataset.pageCount = String(pageNumber + 1);
  }

  window.addEventListener("load", async () => {
    await document.fonts.ready;
    paginate();
  });
})();
</script>
</body>
</html>`;

fs.mkdirSync(htmlDir, { recursive: true });
fs.writeFileSync(htmlPath, documentHtml, "utf8");
fs.mkdirSync(outputDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 1600 } });
await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "networkidle" });
await page.waitForFunction(() => document.body.dataset.paginated === "true");
const diagnostics = await page.evaluate(() => ({
  logicalPages: Number(document.body.dataset.pageCount),
  overflowPages: Array.from(document.querySelectorAll(".page-body"))
    .map((body, index) => ({ index: index + 1, scroll: body.scrollHeight, client: body.clientHeight }))
    .filter((entry) => entry.scroll > entry.client + 1),
  emptyPages: Array.from(document.querySelectorAll(".page-body"))
    .map((body, index) => ({ index: index + 1, text: body.textContent.trim() }))
    .filter((entry) => entry.text.length === 0)
    .map((entry) => entry.index),
}));

if (diagnostics.overflowPages.length || diagnostics.emptyPages.length) {
  await browser.close();
  throw new Error(`Pagination QA failed: ${JSON.stringify(diagnostics)}`);
}

await page.pdf({
  path: pdfPath,
  format: "A4",
  printBackground: true,
  preferCSSPageSize: true,
  margin: { top: "0", right: "0", bottom: "0", left: "0" },
  tagged: true,
  outline: true,
});
await browser.close();

console.log(JSON.stringify({ sourcePath, htmlPath, pdfPath, ...diagnostics }, null, 2));
