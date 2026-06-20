#!/usr/bin/env node
"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");

const DEFAULT_ANALYSIS_DIR = path.join(
  os.homedir(),
  ".codex",
  "wa-captain-analysis",
);
const CACHE_MS = 15000;
const MAX_SECTION_CHARS = 1800;
const MAX_TABLE_TEXT_CHARS = 420;

let CACHE = { at: 0, baseDir: null, payload: null };

function analysisBaseDir() {
  return process.env.WA_CAPTAIN_ANALYSIS_DIR || DEFAULT_ANALYSIS_DIR;
}

function safeJson(line) {
  try {
    return JSON.parse(line);
  } catch {
    return null;
  }
}

function readLatestManifestRows(baseDir) {
  const manifestPath = path.join(baseDir, "manifest.jsonl");
  if (!fs.existsSync(manifestPath)) {
    return { manifestPath, latestRows: [], rawRows: 0, statusCounts: {} };
  }

  const lines = fs
    .readFileSync(manifestPath, "utf8")
    .split(/\r?\n/)
    .filter(Boolean);
  const latest = new Map();
  const statusCounts = {};
  for (const line of lines) {
    const row = safeJson(line);
    if (!row || !row.key) continue;
    latest.set(row.key, row);
  }

  for (const row of latest.values()) {
    const status = row.status || "unknown";
    statusCounts[status] = (statusCounts[status] || 0) + 1;
  }

  return {
    manifestPath,
    latestRows: Array.from(latest.values()),
    rawRows: lines.length,
    statusCounts,
  };
}

function readTextIfExists(filePath) {
  if (!filePath || !fs.existsSync(filePath)) return "";
  const stat = fs.statSync(filePath);
  if (!stat.isFile() || stat.size < 20) return "";
  return fs.readFileSync(filePath, "utf8");
}

function trimText(value, maxChars = MAX_SECTION_CHARS) {
  const text = String(value || "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  if (text.length <= maxChars) return text;
  return `${text.slice(0, maxChars - 1).trim()}…`;
}

function stripCodeFence(text) {
  return String(text || "")
    .replace(/^```(?:text|yaml|yml|json)?\s*/i, "")
    .replace(/\s*```$/i, "")
    .trim();
}

function normalizeHeadingTitle(title) {
  return String(title || "")
    .replace(/\*/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function isKnownAnalysisHeading(title) {
  const normalized = normalizeHeadingTitle(title);
  return /^(tipo|stato|prove|eviden|cosa zantara|next action|prossima|risposta whatsapp|ideal|packet|crm|internal|cosa un dashboard|errore dashboard|deterministico|training label|training labels|gold label)\b/i.test(
    normalized,
  );
}

function parseSections(markdown) {
  const sections = {};
  let current = null;
  let buffer = [];

  const flush = () => {
    if (!current) return;
    const text = trimText(buffer.join("\n"));
    sections[current.number] = {
      number: current.number,
      title: current.title,
      text,
    };
    buffer = [];
  };

  for (const line of String(markdown || "").split(/\r?\n/)) {
    const isMarkdownHeading = /^\s*#{1,6}\s+/.test(line);
    const clean = line
      .trim()
      .replace(/^#{1,6}\s*/, "")
      .replace(/\*\*/g, "")
      .trim();
    const match = clean.match(/^(\d+)\s*[\).]?\s*(.+?)\s*$/);
    if (
      match &&
      Number(match[1]) >= 1 &&
      Number(match[1]) <= 12 &&
      match[2].length <= 90 &&
      (isMarkdownHeading || isKnownAnalysisHeading(match[2]))
    ) {
      flush();
      current = {
        number: Number(match[1]),
        title: match[2].trim(),
      };
      continue;
    }
    if (current) buffer.push(line);
  }
  flush();

  return sections;
}

function findSection(sections, number, titleHints = []) {
  if (sections[number]?.text) return stripCodeFence(sections[number].text);
  const hints = titleHints.map(normalizeHeadingTitle);
  for (const section of Object.values(sections)) {
    const title = normalizeHeadingTitle(section.title);
    if (hints.some((hint) => title.includes(hint)))
      return stripCodeFence(section.text);
  }
  return "";
}

function flagSpecs() {
  return [
    [
      "crm_collision",
      "CRM/thread collision",
      /crm_collision:\s*true|thread_collision:\s*true|actor_collision_detected:\s*true|identity_resolution_needed:\s*true|collisione\s+(forte|alta|reale)|rischio\s+(crm|di collisione)|thread attribution collision|etichettat[oa].*ma/i,
    ],
    [
      "multi_case",
      "Multi-caso",
      /multi[-\s]?cas[oi]|sotto[-\s]?cas[oi]|casi distinti|pratiche diverse|separare.*cas/i,
    ],
    [
      "media_review",
      "Media/artifact review",
      /media senza|allegat[oi].*verific|attachment.*verify|verify.*attachment|artifact_verification|pdf|documento.*verific|foto|immagine|ocr|file.*corretto/i,
    ],
    [
      "pricingtool_required",
      "PricingTool",
      /pricing_required:\s*true|requires_pricing_tool:\s*true|requires.*PricingTool|usare\s+PricingTool|generare.*PricingTool|prezzo.*PricingTool|should_not_invent_price:\s*true/i,
    ],
    [
      "security_credentials",
      "Credenziali/sicurezza",
      /otp|password|pin|credenzial|login|coretax|bank statement|passport|passaporto|ktp|npwp/i,
    ],
    [
      "compliance",
      "Compliance",
      /compliance|oss|bpjs|wlkp|kanim|overstay|kpk|visa|permesso|legal/i,
    ],
    [
      "deadline_or_overstay",
      "Deadline/urgenza",
      /urgent|urgente|scadenza|deadline|expiry|expired|overstay|entro oggi|p0|p1/i,
    ],
    [
      "needs_reply",
      "Needs reply",
      /requires_follow_up:\s*true|needs_reply:\s*true|palla aperta|serve.*rispondere|rispondere.*cliente|follow[-\s]?up.*cliente/i,
    ],
    [
      "reported_done_not_closed",
      "Done non provato",
      /acknowledgement_only|not_proven_completed|non prova|non chiuso|not completed|reported.*done/i,
    ],
    [
      "internal_ops",
      "Internal ops",
      /conversation_type:\s*internal|internal_ops|chat interna|conversazione interna|customer_visible:\s*false|collega interna|liaison/i,
    ],
    [
      "owner_decision",
      "Owner decision",
      /owner[_\s-]?decision|requires_owner|approval_required|decisione owner|approvazione owner|owner deve|owner:/i,
    ],
  ];
}

function detectFlags(fullText) {
  const hits = [];
  for (const [id, label, re] of flagSpecs()) {
    if (re.test(fullText)) hits.push({ id, label });
  }
  return hits;
}

function priorityScore(row, flags, sections) {
  const flagIds = new Set(flags.map((f) => f.id));
  let score = 0;
  if ((row.unread || 0) > 0) score += 35;
  if ((row.n || 0) >= 100) score += 12;
  if ((row.n || 0) >= 40) score += 7;
  if (flagIds.has("deadline_or_overstay")) score += 35;
  if (flagIds.has("security_credentials")) score += 30;
  if (flagIds.has("compliance")) score += 24;
  if (flagIds.has("crm_collision")) score += 20;
  if (flagIds.has("pricingtool_required")) score += 18;
  if (flagIds.has("reported_done_not_closed")) score += 18;
  if (flagIds.has("media_review")) score += 12;
  if (flagIds.has("owner_decision")) score += 10;
  if (flagIds.has("multi_case")) score += 10;
  if (sections.action) score += 6;
  if (sections.ideal_reply) score += 5;
  return score;
}

function caseKindLabel(row) {
  if (row.kind === "group") return "group";
  return "direct";
}

function buildAnalysisItem(row, baseDir) {
  const outputPath = row.outputPath || "";
  const markdown = readTextIfExists(outputPath);
  if (!markdown) return null;

  const parsed = parseSections(markdown);
  const sections = {
    type: findSection(parsed, 1, ["tipo", "attori"]),
    state: findSection(parsed, 2, ["stato reale", "stato"]),
    evidence: findSection(parsed, 3, ["prove", "eviden"]),
    action: findSection(parsed, 4, ["cosa zantara", "next action", "prossima"]),
    ideal_reply: findSection(parsed, 5, ["risposta whatsapp", "ideal"]),
    crm_packet: findSection(parsed, 6, ["packet", "crm", "internal"]),
    deterministic_failure: findSection(parsed, 7, [
      "errore dashboard",
      "deterministico",
      "sbaglierebbe",
    ]),
    training_labels: findSection(parsed, 8, ["training label", "gold label"]),
  };
  const fullText = `${row.label || ""}\n${markdown}`;
  const flags = detectFlags(fullText);
  const stat = fs.statSync(outputPath);

  return {
    key: row.key,
    label: row.label || row.key,
    kind: row.kind || "unknown",
    kind_label: caseKindLabel(row),
    team: row.team || "",
    display: row.display || "",
    n: row.n || 0,
    unread: row.unread || 0,
    last_at: row.last_at || null,
    status: row.status || "unknown",
    analysis_id: path.basename(outputPath, ".md"),
    relative_path: path.relative(baseDir, outputPath),
    output_mtime: stat.mtime.toISOString(),
    flags,
    flag_ids: flags.map((f) => f.id),
    priority_score: priorityScore(row, flags, sections),
    summary: trimText(
      sections.state || sections.type || "",
      MAX_TABLE_TEXT_CHARS,
    ),
    next_action: trimText(sections.action || "", MAX_TABLE_TEXT_CHARS),
    ideal_reply: trimText(sections.ideal_reply || "", MAX_TABLE_TEXT_CHARS),
    sections,
  };
}

function buildRiskCounts(items) {
  const counts = {};
  for (const item of items) {
    for (const id of item.flag_ids || []) {
      counts[id] = (counts[id] || 0) + 1;
    }
  }
  return counts;
}

function buildCategoryCounts(items) {
  const groups = { direct: 0, group: 0, unknown: 0 };
  for (const item of items) {
    groups[item.kind] = (groups[item.kind] || 0) + 1;
  }
  return groups;
}

function buildAnalysisIndexPayload(options = {}) {
  const baseDir = analysisBaseDir();
  const now = Date.now();
  if (
    !options.force &&
    CACHE.payload &&
    CACHE.baseDir === baseDir &&
    now - CACHE.at < CACHE_MS
  ) {
    return CACHE.payload;
  }

  const { manifestPath, latestRows, rawRows, statusCounts } =
    readLatestManifestRows(baseDir);
  const items = latestRows
    .map((row) => buildAnalysisItem(row, baseDir))
    .filter(Boolean)
    .sort((a, b) => {
      if (b.priority_score !== a.priority_score)
        return b.priority_score - a.priority_score;
      return new Date(b.last_at || 0) - new Date(a.last_at || 0);
    });

  const riskCounts = buildRiskCounts(items);
  const categoryCounts = buildCategoryCounts(items);
  const totalFlags = Object.values(riskCounts).reduce(
    (sum, count) => sum + count,
    0,
  );

  const payload = {
    generated_at: new Date().toISOString(),
    exists: fs.existsSync(baseDir),
    base_dir: baseDir,
    manifest_path: manifestPath,
    raw_manifest_rows: rawRows,
    manifest_latest_status: statusCounts,
    analysis_count: items.length,
    valid_count: items.length,
    category_counts: categoryCounts,
    risk_counts: riskCounts,
    total_risk_flags: totalFlags,
    total_cards: {
      gpt55_conversations: String(items.length),
      valid_analyses: String(items.length),
      crm_collisions: String(riskCounts.crm_collision || 0),
      media_reviews: String(riskCounts.media_review || 0),
      pricingtool_required: String(riskCounts.pricingtool_required || 0),
      wa_sends: "0",
      crm_writes: "0",
    },
    filters: flagSpecs()
      .map(([id, label]) => ({
        id,
        label,
        count: riskCounts[id] || 0,
      }))
      .filter((f) => f.count > 0),
    items,
  };

  CACHE = { at: now, baseDir, payload };
  return payload;
}

module.exports = {
  buildAnalysisIndexPayload,
};
