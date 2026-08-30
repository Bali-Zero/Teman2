#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const requestedLocale = process.argv[2] ?? "en";
const locales = {
  en: {
    lang: "en",
    sourceSuffix: "",
    outputSuffix: "",
    documentTitle: "Bali Zero - Setup Team Villa Operator Architecture",
    coverEyebrow: "BALI ZERO <span class=\"sep\">·</span> INTERNAL OPERATING DOSSIER",
    tagline: "Powered by humans, fueled by a thinking engine.",
    coverTitle: "VILLA OPERATOR<br>ARCHITECTURE",
    coverSubtitle: "PMA restrictions · Perseroan Perorangan · Tax flows",
    coverDescription: "A decision manual for a lawful Bali villa owner-operator model under the targeted 2026 PMA restrictions. Includes KBLI gates, principal-agent revenue logic, unit economics, authority questions and a 30-day go/no-go pilot.",
    coverDisclaimer: "Decision status: pre-clearance. No structure moves before the written gates are closed.",
    cutoff: "CUT-OFF · 31 AUG 2026",
    briefEyebrow: "SETUP TEAM OPERATING BRIEF",
    decisionBoard: "DECISION BOARD",
    lead: "This dossier is designed for case setup, pre-clearance and go/no-go control. It does not assign internal roles. It gives the team one shared decision standard: the legal principal, operational substance, money flow, tax record and property permit chain must tell the same story.",
    statuses: [
      ["BASELINE", "Owner-led villa with one lawful principal and one merchant-of-record chain.", false],
      ["CONDITIONAL", "Disclosed 55203/55901 management only after written authority confirmation.", false],
      ["NO-GO", "Paper operator, hidden foreign control, nominee economics or residual sweep.", true],
    ],
    decisions: [
      ["Run one brownfield pilot only after written pre-clearance.", false],
      ["Use the owner-led model as the baseline architecture.", false],
      ["Do not use 55203 through a lessee or sublessee until <em>pemilik</em> is answered in writing.", true],
      ["Keep guest contract, OTA, bank, receipt, refund, PBJT and accounting on the same principal.", false],
      ["Require real WNI control, capital, risk, books and beneficial-ownership substance.", false],
      ["Clear coordinates, zoning, KKPR, PBG, SLF and tourism requirements before entity design.", false],
      ["Treat PP 20/2026 at 0.5% as tax treatment, never as a business licence.", false],
      ["In a true management model, principal books guest gross and PBJT; manager books fee only.", false],
      ["Give every rent, service, loan, royalty or commission lane independent substance and a benchmark.", false],
      ["Protect investors through reporting, audit and valid security - never operating control.", false],
      ["Reject shared OTP, foreign bank control, fixed nominee fee and automatic residual sweep.", true],
      ["No incorporation, OTA migration, guest collection or launch before a signed go/no-go.", true],
    ],
    evidenceEyebrow: "EVIDENCE REGISTER",
    primarySources: "PRIMARY SOURCES",
    sourceLead: "The dossier uses the following legal, government and authority-facing source locations. The operative test remains the primary text and the live OSS record for the exact entity, KBLI and property.",
    headerDoc: "Villa Operator Architecture · Setup Team",
    pageLabel: "p.",
    internalUse: "Internal use",
    continuation: "CONTINUED",
    decisionSection: "DECISION BOARD",
    dossierSection: "FULL DOSSIER",
    defaultSection: "OPERATING DOSSIER",
  },
  id: {
    lang: "id",
    sourceSuffix: ".id",
    outputSuffix: "_ID",
    documentTitle: "Bali Zero - Arsitektur Operator Villa - Setup Team",
    coverEyebrow: "BALI ZERO <span class=\"sep\">·</span> DOSSIER OPERASIONAL INTERNAL",
    tagline: "Digerakkan manusia, ditenagai mesin berpikir.",
    coverTitle: "ARSITEKTUR<br>OPERATOR VILLA",
    coverSubtitle: "Pembatasan PMA · Perseroan Perorangan · Arus pajak",
    coverDescription: "Panduan keputusan untuk model pemilik-operator villa Bali yang sah di bawah pembatasan PMA tertarget tahun 2026. Mencakup gate KBLI, logika pendapatan prinsipal-agen, unit economics, pertanyaan kepada otoritas, dan pilot go/no-go selama 30 hari.",
    coverDisclaimer: "Status keputusan: pra-klirens. Tidak ada struktur yang dijalankan sebelum seluruh gate tertulis ditutup.",
    cutoff: "BATAS DATA · 31 AGU 2026",
    briefEyebrow: "RINGKASAN OPERASIONAL SETUP TEAM",
    decisionBoard: "PAPAN KEPUTUSAN",
    lead: "Dossier ini dirancang untuk setup kasus, pra-klirens, dan kontrol go/no-go. Dossier ini tidak menetapkan pembagian peran internal. Tim menggunakan satu standar keputusan bersama: prinsipal hukum, substansi operasional, arus uang, catatan pajak, dan rangkaian izin properti harus menceritakan hal yang sama.",
    statuses: [
      ["DASAR", "Villa yang dipimpin pemilik dengan satu prinsipal sah dan satu rantai merchant of record.", false],
      ["BERSYARAT", "Manajemen 55203/55901 yang diungkapkan hanya setelah konfirmasi tertulis dari otoritas.", false],
      ["TIDAK LAYAK", "Operator di atas kertas, kontrol asing tersembunyi, ekonomi nominee, atau penyapuan laba residual.", true],
    ],
    decisions: [
      ["Jalankan hanya satu pilot brownfield setelah pra-klirens tertulis.", false],
      ["Gunakan model yang dipimpin pemilik sebagai arsitektur dasar.", false],
      ["Jangan gunakan 55203 melalui penyewa atau subpenyewa sebelum arti <em>pemilik</em> dijawab tertulis.", true],
      ["Pertahankan kontrak tamu, OTA, bank, tanda terima, refund, PBJT, dan pembukuan pada prinsipal yang sama.", false],
      ["Wajibkan kontrol, modal, risiko, pembukuan, dan substansi beneficial ownership WNI yang nyata.", false],
      ["Pastikan koordinat, zonasi, KKPR, PBG, SLF, dan persyaratan pariwisata sebelum mendesain entitas.", false],
      ["Perlakukan tarif 0,5% dalam PP 20/2026 sebagai perlakuan pajak, bukan izin usaha.", false],
      ["Dalam model manajemen nyata, prinsipal membukukan pendapatan bruto tamu dan PBJT; manajer hanya membukukan fee.", false],
      ["Berikan substansi independen dan benchmark pada setiap jalur sewa, jasa, pinjaman, royalti, atau komisi.", false],
      ["Lindungi investor melalui pelaporan, audit, dan jaminan yang sah - bukan kontrol operasional.", false],
      ["Tolak OTP bersama, kontrol bank oleh pihak asing, fee nominee tetap, dan penyapuan laba residual otomatis.", true],
      ["Tidak ada pendirian entitas, migrasi OTA, penerimaan uang tamu, atau peluncuran sebelum go/no-go ditandatangani.", true],
    ],
    evidenceEyebrow: "REGISTER BUKTI",
    primarySources: "SUMBER PRIMER",
    sourceLead: "Dossier ini menggunakan lokasi sumber hukum, pemerintah, dan sumber yang ditujukan kepada otoritas berikut. Pengujian operasional tetap mengacu pada teks primer dan catatan OSS live untuk entitas, KBLI, dan properti yang tepat.",
    headerDoc: "Arsitektur Operator Villa · Setup Team",
    pageLabel: "hal.",
    internalUse: "Penggunaan internal",
    continuation: "LANJUTAN",
    decisionSection: "PAPAN KEPUTUSAN",
    dossierSection: "DOSSIER LENGKAP",
    defaultSection: "DOSSIER OPERASIONAL",
  },
  it: {
    lang: "it",
    sourceSuffix: ".it",
    outputSuffix: "_IT",
    documentTitle: "Bali Zero - Architettura Operatore Villa - Setup Team",
    coverEyebrow: "BALI ZERO <span class=\"sep\">·</span> DOSSIER OPERATIVO INTERNO",
    tagline: "Guidato da persone, alimentato da un motore pensante.",
    coverTitle: "ARCHITETTURA<br>OPERATORE VILLA",
    coverSubtitle: "Restrizioni PMA · Perseroan Perorangan · Flussi fiscali",
    coverDescription: "Manuale decisionale per un modello legittimo di proprietario-operatore di villa a Bali nell'ambito delle restrizioni PMA mirate del 2026. Include gate KBLI, logica dei ricavi principal-agent, unit economics, domande alle autorità e un pilot go/no-go di 30 giorni.",
    coverDisclaimer: "Stato decisionale: pre-clearance. Nessuna struttura procede finché tutti i gate scritti non sono chiusi.",
    cutoff: "DATI AL · 31 AGO 2026",
    briefEyebrow: "BRIEF OPERATIVO DEL SETUP TEAM",
    decisionBoard: "QUADRO DECISIONALE",
    lead: "Questo dossier è concepito per il setup del caso, la pre-clearance e il controllo go/no-go. Non assegna ruoli interni. Offre al team un unico standard decisionale condiviso: il principal legale, la sostanza operativa, il flusso di denaro, le registrazioni fiscali e la catena dei permessi immobiliari devono raccontare la stessa storia.",
    statuses: [
      ["BASE", "Villa guidata dal proprietario con un unico principal legittimo e una sola catena merchant of record.", false],
      ["CONDIZIONALE", "Gestione 55203/55901 dichiarata, solo dopo conferma scritta delle autorità.", false],
      ["STOP", "Operatore di facciata, controllo straniero occulto, economia nominee o drenaggio dell'utile residuo.", true],
    ],
    decisions: [
      ["Avviare un solo pilot brownfield dopo la pre-clearance scritta.", false],
      ["Usare il modello guidato dal proprietario come architettura di base.", false],
      ["Non usare il 55203 tramite locatario o sublocatario finché <em>pemilik</em> non riceve risposta scritta.", true],
      ["Mantenere contratto con l'ospite, OTA, banca, ricevuta, rimborso, PBJT e contabilità sullo stesso principal.", false],
      ["Richiedere controllo, capitale, rischio, libri contabili e sostanza di beneficial ownership WNI reali.", false],
      ["Verificare coordinate, zoning, KKPR, PBG, SLF e requisiti turistici prima di progettare l'entità.", false],
      ["Trattare lo 0,5% del PP 20/2026 come regime fiscale, mai come licenza commerciale.", false],
      ["In un vero modello di gestione, il principal contabilizza ricavi lordi degli ospiti e PBJT; il manager solo la fee.", false],
      ["Dare sostanza indipendente e benchmark a ogni flusso di affitto, servizio, prestito, royalty o commissione.", false],
      ["Proteggere gli investitori con reporting, audit e garanzie valide - mai con controllo operativo.", false],
      ["Rifiutare OTP condivisi, controllo straniero del conto, fee nominee fissa e sweep automatico dell'utile residuo.", true],
      ["Nessuna costituzione, migrazione OTA, incasso dagli ospiti o lancio prima di un go/no-go firmato.", true],
    ],
    evidenceEyebrow: "REGISTRO DELLE EVIDENZE",
    primarySources: "FONTI PRIMARIE",
    sourceLead: "Il dossier utilizza le seguenti fonti giuridiche, governative e destinate al confronto con le autorità. Il test operativo resta il testo primario e il record OSS live per l'entità, il KBLI e l'immobile specifici.",
    headerDoc: "Architettura Operatore Villa · Setup Team",
    pageLabel: "pag.",
    internalUse: "Uso interno",
    continuation: "CONTINUA",
    decisionSection: "QUADRO DECISIONALE",
    dossierSection: "DOSSIER COMPLETO",
    defaultSection: "DOSSIER OPERATIVO",
  },
};
const locale = locales[requestedLocale];
if (!locale) throw new Error(`Unsupported locale: ${requestedLocale}. Use en, id or it.`);

const sourcePath = path.join(repoRoot, `research/property/2026-08-31-bali-villa-operator-architecture${locale.sourceSuffix}.md`);
const cssPath = path.join(repoRoot, "skills/bali-zero-brand/surfaces/internal-print-a4/_template.css");
const outputDir = path.join(repoRoot, "output/pdf");
const htmlDir = path.join(outputDir, "source");
const outputBasename = `Bali_Zero_Setup_Team_Villa_Operator_Architecture${locale.outputSuffix}`;
const htmlPath = path.join(htmlDir, `${outputBasename}.html`);
const pdfPath = path.join(outputDir, `${outputBasename}.pdf`);

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
const statusesHtml = locale.statuses
  .map(([label, description, stop]) => `<div class="status-card${stop ? " stop" : ""}"><strong>${label}</strong><span>${description}</span></div>`)
  .join("\n");
const decisionCardsHtml = locale.decisions
  .map(([description, stop], index) => `<div class="decision-card${stop ? " stop" : ""}"><span class="number">${String(index + 1).padStart(2, "0")}</span><p>${description}</p></div>`)
  .join("\n");
const paginationLabels = JSON.stringify({
  headerDoc: locale.headerDoc,
  pageLabel: locale.pageLabel,
  internalUse: locale.internalUse,
  tagline: locale.tagline,
  continuation: locale.continuation,
  decisionSection: locale.decisionSection,
  dossierSection: locale.dossierSection,
  defaultSection: locale.defaultSection,
});

const documentHtml = `<!DOCTYPE html>
<html lang="${locale.lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${locale.documentTitle}</title>
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
      <div class="cover-eyebrow">${locale.coverEyebrow}</div>
      <div class="cover-tagline">${locale.tagline}</div>
    </div>
  </div>
  <div class="cover-title-block">
    <h1 class="cover-title">${locale.coverTitle}</h1>
    <div class="cover-subtitle">${locale.coverSubtitle}</div>
    <div class="cover-rule"></div>
    <p class="cover-description">${locale.coverDescription}</p>
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
      <div class="cover-footer-disclaimer">${locale.coverDisclaimer}</div>
    </div>
    <div class="cover-footer-right">${locale.cutoff}</div>
  </div>
</section>

<div id="pages"></div>

<main id="source-content" class="doc-content">
  <section data-manual-page="decision-board">
    <div class="eyebrow">${locale.briefEyebrow}</div>
    <h2>${locale.decisionBoard}</h2>
    <div class="team-line">ADIT · SURYA · ARI · KRISNA</div>
    <p class="lead">${locale.lead}</p>
    <div class="status-row">
      ${statusesHtml}
    </div>
    <div class="decision-grid">
      ${decisionCardsHtml}
    </div>
  </section>
  <section data-dossier-content>
    ${dossierHtml}
  </section>
  <section data-sources>
    <div class="eyebrow">${locale.evidenceEyebrow}</div>
    <h2>${locale.primarySources}</h2>
    <p class="lead">${locale.sourceLead}</p>
    <ol class="source-list">${sourcesHtml}</ol>
  </section>
</main>

<script>
(() => {
  const labels = ${paginationLabels};
  const pagesRoot = document.getElementById("pages");
  const sourceRoot = document.getElementById("source-content");
  let pageNumber = 0;
  let currentPage = null;
  let currentBody = null;
  let currentSection = labels.defaultSection;

  function makePage(sectionLabel = currentSection) {
    pageNumber += 1;
    const page = document.createElement("section");
    page.className = "page";
    page.innerHTML = [
      '<div class="page-header">',
      '  <div class="page-header-logo bz-logo-image"></div>',
      '  <div class="page-header-titles">',
      '    <div class="page-header-brand">BALI ZERO</div>',
      '    <div class="page-header-doc">' + labels.headerDoc + '</div>',
      '  </div>',
      '  <div class="page-header-num">' + labels.pageLabel + ' ' + String(pageNumber).padStart(2, "0") + '</div>',
      '</div>',
      '<div class="page-body" data-section="' + sectionLabel.replace(/"/g, "&quot;") + '"></div>',
      '<div class="page-footer">',
      '  <div>balizero.com <span style="margin: 0 4mm;">·</span> ' + labels.internalUse + '</div>',
      '  <div class="page-footer-right">' + labels.tagline + '</div>',
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
    label.textContent = currentSection + " · " + labels.continuation;
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
    makePage(labels.decisionSection);
    for (let index = 0; index < entries.length; index += 1) {
      const { type, node } = entries[index];
      if (type === "manual") {
        for (const child of Array.from(node.children)) appendNode(child);
        makePage(labels.dossierSection);
        continue;
      }

      if (node.matches?.("h2")) {
        currentSection = node.textContent.trim().toUpperCase();
        const used = usedRatio();
        const nextEntry = entries[index + 1];
        const opensTable = nextEntry?.type === "content" && nextEntry.node.matches?.("table");
        if (currentBody.children.length && (used > 0.72 || opensTable)) makePage(currentSection);
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
