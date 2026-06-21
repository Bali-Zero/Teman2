"use strict";

// wa-dashboard-m1 — Local Zantara training/shadow artifact index
// ------------------------------------------------------------------
// Pro-bound and read-only. This module scans only safe Markdown summaries
// under research/personal/wa-corpus and never exposes raw JSONL/SQLite rows,
// message text, phone numbers, or case identifiers.
// ------------------------------------------------------------------

const fs = require("fs");
const path = require("path");

const DEFAULT_CORPUS_DIR = path.resolve(
  __dirname,
  "../../research/personal/wa-corpus",
);
const SUMMARY_RE = /_summary\.md$/i;
const MAX_DEPTH = 5;
const MAX_FILES = 700;
const MAX_SUMMARY_BYTES = 256 * 1024;
const CACHE_MS = 15_000;

let CACHE = { at: 0, payload: null };

const CATEGORY_RULES = [
  {
    id: "client_academy",
    label: "Client Captain Academy",
    tone: "green",
    re: /client[-_]?captain.*academy|client_captain_academy/i,
  },
  {
    id: "client_shadow",
    label: "Client Captain Shadow",
    tone: "blue",
    re: /client[-_]?captain[-_]?shadow|client_captain_shadow/i,
  },
  {
    id: "team_shadow",
    label: "Team Captain Shadow",
    tone: "cyan",
    re: /team[-_]?captain[-_]?shadow|team_captain_shadow/i,
  },
  {
    id: "owner_shadow",
    label: "Owner Captain Shadow",
    tone: "gold",
    re: /owner[-_]?captain[-_]?shadow|owner_captain_shadow/i,
  },
  {
    id: "owner_decision",
    label: "Owner Decision Chain",
    tone: "violet",
    re: /owner[-_]?decision|owner_decision|approval|approve|reject|ledger|work[-_]?order|decision[-_]?packs|decision[-_]?inbox/i,
  },
  {
    id: "operator_ops",
    label: "Operator Ops",
    tone: "orange",
    re: /operator|next[-_]?best|case[-_]?closure|case[-_]?memory|case[-_]?timeline|evidence[-_]?gap|war[-_]?room/i,
  },
  {
    id: "corpus_analysis",
    label: "Corpus Analysis",
    tone: "slate",
    re: /analysis|allowed_|classification|registry|review|full[-_]?corpus|gold[-_]?signals|drive[-_]?import|manifest/i,
  },
];

const IMPORTANT_METRICS = [
  "training_examples",
  "replay_scenarios",
  "shadow_drafts",
  "owner_approval_items",
  "owner_decision_packs",
  "owner_briefs",
  "operator_packets",
  "review_items",
  "intake_items",
  "awaiting_owner_decision",
  "captured_decisions",
  "team_findings",
  "owner_findings",
  "source_cases",
  "depth_layers",
  "p1_count",
  "whatsapp_sends",
  "crm_mutations",
  "human_approval_required",
];

function corpusDir() {
  return process.env.WA_TRAINING_CORPUS_DIR || DEFAULT_CORPUS_DIR;
}

function metricKey(label) {
  return String(label || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function displayNumber(value) {
  if (value == null || value === "") return "—";
  if (typeof value === "number") return value.toLocaleString("it-IT");
  const s = String(value).trim();
  const numeric = s.replace(/,/g, "");
  if (/^-?\d+(\.\d+)?$/.test(numeric)) {
    return Number(numeric).toLocaleString("it-IT");
  }
  return s;
}

function numericValue(value) {
  if (value == null) return null;
  const s = String(value).trim().replace(/,/g, "");
  if (!/^-?\d+(\.\d+)?%?$/.test(s)) return null;
  return Number(s.replace(/%/g, ""));
}

function cleanBullet(line) {
  return String(line || "")
    .replace(/^\s*[-*]\s+/, "")
    .replace(/`/g, "")
    .trim();
}

function markdownSections(text) {
  const sections = [];
  let current = null;
  for (const line of String(text || "").split(/\r?\n/)) {
    const heading = line.match(/^##\s+(.+?)\s*$/);
    if (heading) {
      if (current) sections.push(current);
      current = { title: heading[1].trim(), body: [] };
      continue;
    }
    if (current) current.body.push(line);
  }
  if (current) sections.push(current);
  return sections.map((section) => ({
    ...section,
    body: section.body.join("\n").trim(),
  }));
}

function sectionText(text, heading) {
  const wanted = String(heading || "")
    .trim()
    .toLowerCase();
  const found = markdownSections(text).find(
    (section) => section.title.toLowerCase() === wanted,
  );
  return found ? found.body : "";
}

function parseTableRows(section) {
  const rows = [];
  for (const raw of String(section || "").split(/\r?\n/)) {
    const line = raw.trim();
    if (!line.startsWith("|") || !line.endsWith("|")) continue;
    const cells = line
      .slice(1, -1)
      .split("|")
      .map((cell) => cell.trim());
    if (cells.length < 2) continue;
    if (/^-{2,}:?$/.test(cells[0].replace(/\s/g, ""))) continue;
    if (/^(metric|value)$/i.test(cells[0]) && /^(value|count)$/i.test(cells[1]))
      continue;
    rows.push({ label: cells[0], value: cells[1] });
  }
  return rows;
}

function parseTables(text) {
  const tables = {};
  for (const section of markdownSections(text)) {
    const rows = parseTableRows(section.body);
    if (rows.length) tables[section.title] = rows;
  }
  return tables;
}

function categorize(relativePath, title) {
  const haystack = `${relativePath} ${title}`;
  for (const rule of CATEGORY_RULES) {
    if (rule.re.test(haystack)) {
      return { id: rule.id, label: rule.label, tone: rule.tone };
    }
  }
  return { id: "other", label: "Other Training Artifacts", tone: "slate" };
}

function safeStat(file) {
  try {
    return fs.statSync(file);
  } catch {
    return null;
  }
}

function scanSummaryFiles(baseDir, dir, depth, acc) {
  if (depth > MAX_DEPTH || acc.length >= MAX_FILES) return;
  let entries = [];
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }
  entries.sort((a, b) => a.name.localeCompare(b.name));
  for (const entry of entries) {
    if (acc.length >= MAX_FILES) return;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      scanSummaryFiles(baseDir, full, depth + 1, acc);
      continue;
    }
    if (entry.isFile() && SUMMARY_RE.test(entry.name)) {
      const rel = path.relative(baseDir, full);
      acc.push({ full, rel });
    }
  }
}

function parseSummaryText(text, relativePath, stat) {
  const title =
    (text.match(/^#\s+(.+?)\s*$/m) || [])[1] || path.basename(relativePath);
  const generatedAt =
    (text.match(/^Generated UTC:\s*`?([^`\n]+)`?/im) || [])[1] ||
    (text.match(/^Generated(?: at)?:\s*`?([^`\n]+)`?/im) || [])[1] ||
    null;

  const tables = parseTables(text);
  const counts = {};
  for (const row of tables.Counts || []) {
    counts[metricKey(row.label)] = row.value;
  }

  const privacyBullets = sectionText(text, "Privacy Mode")
    .split(/\r?\n/)
    .filter((line) => /^\s*[-*]\s+/.test(line))
    .slice(0, 6)
    .map(cleanBullet);
  const contractBullets = sectionText(text, "Execution Contract")
    .split(/\r?\n/)
    .filter((line) => /^\s*[-*]\s+/.test(line))
    .slice(0, 8)
    .map(cleanBullet);

  const category = categorize(relativePath, title);
  const keyMetrics = IMPORTANT_METRICS.filter((key) => counts[key] != null)
    .slice(0, 8)
    .map((key) => ({
      key,
      label: key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      value: counts[key],
      display_value: displayNumber(counts[key]),
    }));

  if (!keyMetrics.length) {
    for (const row of (tables.Counts || []).slice(0, 5)) {
      keyMetrics.push({
        key: metricKey(row.label),
        label: row.label,
        value: row.value,
        display_value: displayNumber(row.value),
      });
    }
  }

  return {
    title: title.trim(),
    relative_path: relativePath,
    category_id: category.id,
    category_label: category.label,
    category_tone: category.tone,
    generated_at: generatedAt,
    mtime: stat ? stat.mtime.toISOString() : null,
    counts,
    key_metrics: keyMetrics,
    privacy: privacyBullets,
    execution_contract: contractBullets,
  };
}

function aggregateTotals(artifacts) {
  const totals = {};
  for (const artifact of artifacts) {
    for (const [key, value] of Object.entries(artifact.counts || {})) {
      const n = numericValue(value);
      if (n == null) continue;
      totals[key] = (totals[key] || 0) + n;
    }
  }
  return totals;
}

function buildCategories(artifacts) {
  const byId = new Map();
  for (const artifact of artifacts) {
    if (!byId.has(artifact.category_id)) {
      byId.set(artifact.category_id, {
        id: artifact.category_id,
        label: artifact.category_label,
        tone: artifact.category_tone,
        count: 0,
        latest_generated_at: null,
        latest_mtime: null,
        top_metrics: {},
      });
    }
    const group = byId.get(artifact.category_id);
    group.count += 1;
    if (
      artifact.generated_at &&
      (!group.latest_generated_at ||
        artifact.generated_at > group.latest_generated_at)
    ) {
      group.latest_generated_at = artifact.generated_at;
    }
    if (
      artifact.mtime &&
      (!group.latest_mtime || artifact.mtime > group.latest_mtime)
    ) {
      group.latest_mtime = artifact.mtime;
    }
    for (const metric of artifact.key_metrics.slice(0, 4)) {
      if (group.top_metrics[metric.key] == null)
        group.top_metrics[metric.key] = metric.display_value;
    }
  }
  return [...byId.values()].sort((a, b) => {
    const ar = CATEGORY_RULES.findIndex((r) => r.id === a.id);
    const br = CATEGORY_RULES.findIndex((r) => r.id === b.id);
    return (
      (ar === -1 ? 99 : ar) - (br === -1 ? 99 : br) ||
      a.label.localeCompare(b.label)
    );
  });
}

function buildTrainingPayload(options = {}) {
  const baseDir = options.baseDir || corpusDir();
  const now = Date.now();
  if (
    !options.noCache &&
    CACHE.payload &&
    Date.now() - CACHE.at < CACHE_MS &&
    CACHE.payload.base_dir === baseDir
  ) {
    return CACHE.payload;
  }

  const files = [];
  const exists = fs.existsSync(baseDir);
  if (exists) scanSummaryFiles(baseDir, baseDir, 0, files);

  const artifacts = [];
  const errors = [];
  for (const file of files) {
    try {
      const stat = safeStat(file.full);
      const raw = fs
        .readFileSync(file.full, "utf8")
        .slice(0, MAX_SUMMARY_BYTES);
      artifacts.push(parseSummaryText(raw, file.rel, stat));
    } catch (err) {
      errors.push({ relative_path: file.rel, error: err.message });
    }
  }

  artifacts.sort((a, b) => {
    const at = a.generated_at || a.mtime || "";
    const bt = b.generated_at || b.mtime || "";
    return (
      bt.localeCompare(at) || a.relative_path.localeCompare(b.relative_path)
    );
  });

  const totals = aggregateTotals(artifacts);
  const payload = {
    generated_at: new Date().toISOString(),
    base_dir: baseDir,
    exists,
    artifact_count: artifacts.length,
    summary_limit: MAX_FILES,
    latest_generated_at:
      artifacts.find((a) => a.generated_at)?.generated_at || null,
    totals,
    total_cards: {
      training_examples: displayNumber(totals.training_examples || 0),
      replay_scenarios: displayNumber(totals.replay_scenarios || 0),
      shadow_drafts: displayNumber(totals.shadow_drafts || 0),
      owner_queue: displayNumber(
        totals.awaiting_owner_decision || totals.owner_approval_items || 0,
      ),
      whatsapp_sends: displayNumber(totals.whatsapp_sends || 0),
      crm_mutations: displayNumber(totals.crm_mutations || 0),
    },
    categories: buildCategories(artifacts),
    artifacts,
    errors,
    contract: {
      local_only: true,
      read_only: true,
      raw_artifacts_exposed: false,
      source: "Markdown summaries only",
    },
    elapsed_ms: Date.now() - now,
  };
  CACHE = { at: Date.now(), payload };
  return payload;
}

module.exports = {
  buildTrainingPayload,
  parseSummaryText,
  metricKey,
};
