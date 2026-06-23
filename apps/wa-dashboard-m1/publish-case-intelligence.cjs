#!/usr/bin/env node
"use strict";

const crypto = require("crypto");
const { Pool } = require("pg");
const analysisIndex = require("./analysis-index.cjs");

const DEFAULT_DASHBOARD_URL =
  process.env.WA_DASHBOARD_URL || "http://127.0.0.1:7791";
const DEFAULT_DATABASE_URL =
  process.env.WA_CASE_INTEL_DATABASE_URL ||
  process.env.WA_DASHBOARD_DATABASE_URL ||
  process.env.DATABASE_URL ||
  "";

function parseArgs(argv) {
  const args = {
    dashboardUrl: DEFAULT_DASHBOARD_URL,
    databaseUrl: DEFAULT_DATABASE_URL,
    clientId: null,
    limit: null,
    json: false,
    dryRun: false,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    const next = argv[i + 1];
    if (arg === "--dashboard-url" && next) {
      args.dashboardUrl = next;
      i += 1;
    } else if (arg === "--database-url" && next) {
      args.databaseUrl = next;
      i += 1;
    } else if (arg === "--client-id" && next) {
      args.clientId = Number.parseInt(next, 10);
      i += 1;
    } else if (arg === "--limit" && next) {
      args.limit = Number.parseInt(next, 10);
      i += 1;
    } else if (arg === "--json") {
      args.json = true;
    } else if (arg === "--dry-run") {
      args.dryRun = true;
    } else if (arg === "--help" || arg === "-h") {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  if (args.clientId && args.clientId <= 0) {
    throw new Error("--client-id must be a positive integer");
  }
  if (args.limit && args.limit <= 0) {
    throw new Error("--limit must be a positive integer");
  }
  return args;
}

function printHelp() {
  console.log(`Usage:
  node publish-case-intelligence.cjs [options]

Options:
  --dashboard-url URL   WA dashboard URL with /data.json (default: ${DEFAULT_DASHBOARD_URL})
  --database-url URL    Postgres URL. Defaults to WA_CASE_INTEL_DATABASE_URL, WA_DASHBOARD_DATABASE_URL, DATABASE_URL.
  --client-id ID        Publish only one CRM client.
  --limit N             Publish only first N matched case cards.
  --dry-run             Build payload and print summary without writing.
  --json                Print payload JSON and do not write.`);
}

function compactText(value, maxChars = 900) {
  const text = String(value || "")
    .replace(/\r/g, "")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  if (text.length <= maxChars) return text;
  return `${text.slice(0, maxChars - 1).trim()}…`;
}

function stripTechnicalPacketText(value) {
  const technicalLine =
    /^\s*(?:[-*]\s*)?(?:crm_collision|thread_health|primary_contact|operator_detected|conversation_type|cases|risk|type|intent|urgency|next_action|needs_pricing|pricing_source)\s*:/i;
  const idLine = /^\s*-\s+id\s*:/i;
  return String(value || "")
    .split(/\r?\n/)
    .filter((line) => !technicalLine.test(line) && !idLine.test(line))
    .join("\n")
    .replace(
      /\b(?:crm_collision|thread_health|primary_contact|operator_detected|conversation_type|needs_pricing|pricing_source)\s*:\s*(?:"[^"]*"|[^\n]+)/gi,
      "",
    )
    .trim();
}

function cleanHumanText(value, maxChars = 900) {
  return compactText(stripTechnicalPacketText(value), maxChars)
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\s+([.,;:])/g, "$1")
    .trim();
}

function uniqueBy(items, keyFn) {
  const seen = new Set();
  const out = [];
  for (const item of items) {
    const key = keyFn(item);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
}

function flagIds(flags) {
  return new Set((flags || []).map((flag) => flag.id).filter(Boolean));
}

function humanFlag(flag) {
  const labels = {
    crm_collision: "CRM identity or thread attribution needs human review.",
    multi_case: "The conversation contains multiple distinct cases.",
    media_review: "Attachments or media need to be opened and verified.",
    pricingtool_required:
      "Any price must be checked with PricingTool before replying.",
    security_credentials:
      "Credentials or sensitive documents appear in the thread.",
    compliance: "Compliance or immigration risk is present.",
    deadline_or_overstay:
      "There is a deadline, expiry, travel window, or overstay risk.",
    needs_reply: "The client or operator still needs a reply.",
    reported_done_not_closed:
      "Something was reported as done, but the evidence is not enough to close it.",
    internal_ops:
      "This is internal operations context, not a clean client-facing thread.",
    owner_decision:
      "Owner decision or approval is needed before moving forward.",
  };
  return labels[flag.id] || flag.label || flag.id;
}

function inferCaseStatus(analysis) {
  const ids = flagIds(analysis.flags);
  if (ids.has("owner_decision")) return "blocked";
  if (ids.has("deadline_or_overstay")) return "open";
  if (ids.has("needs_reply")) return "open";
  if (ids.has("reported_done_not_closed")) return "open";
  if (ids.has("media_review")) return "waiting";
  return "open";
}

function inferCaseType(analysis) {
  const ids = flagIds(analysis.flags);
  if (ids.has("internal_ops")) return "internal operations";
  if (ids.has("multi_case")) return "multi-case";
  if (ids.has("crm_collision")) return "CRM review";
  if (ids.has("pricingtool_required")) return "pricing needed";
  if (analysis.kind === "group") return "WhatsApp group case";
  return "WhatsApp case";
}

function buildHumanCrmNote(analysis, conv) {
  const sections = analysis.sections || {};
  const blocks = [];

  const state = cleanHumanText(sections.state || analysis.summary || "", 1200);
  if (state) blocks.push(`Situation\n${state}`);

  const context = [];
  const display = conv.display_name || analysis.display || conv.counterpart;
  if (display) context.push(`Main visible contact/thread: ${display}.`);
  if (conv.assigned_to)
    context.push(`CRM owner currently shown as ${conv.assigned_to}.`);
  if (analysis.kind === "group") {
    context.push(
      "This comes from a WhatsApp group, so actor attribution must be checked before any client-facing action.",
    );
  }
  if (context.length) blocks.push(`Context\n${context.join(" ")}`);

  const attention = uniqueBy((analysis.flags || []).map(humanFlag), (item) =>
    item.toLowerCase(),
  );
  if (attention.length) {
    blocks.push(
      `Attention\n${attention.map((item) => `- ${item}`).join("\n")}`,
    );
  }

  const action = cleanHumanText(
    sections.action || analysis.next_action || "",
    1200,
  );
  if (action) blocks.push(`Next action\n${action}`);

  const idealReply = cleanHumanText(
    sections.ideal_reply || analysis.ideal_reply || "",
    1000,
  );
  if (idealReply) blocks.push(`Ideal reply\n${idealReply}`);

  const evidence = cleanHumanText(sections.evidence || "", 900);
  if (evidence) blocks.push(`Evidence read\n${evidence}`);

  return compactText(blocks.join("\n\n"), 3000);
}

function stableHash(payload) {
  return crypto
    .createHash("sha1")
    .update(JSON.stringify(payload))
    .digest("hex");
}

function toDateOrNull(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

async function fetchOverview(dashboardUrl) {
  const target = new URL("/data.json", dashboardUrl);
  const res = await fetch(target);
  if (!res.ok) throw new Error(`GET ${target.href} returned ${res.status}`);
  return res.json();
}

function buildRows(overview, analysisPayload, options) {
  const analysisByKey = new Map(
    (analysisPayload.items || []).map((item) => [item.key, item]),
  );
  const rows = [];

  for (const [memberPhone, phoneData] of Object.entries(
    overview.by_phone || {},
  )) {
    for (const conv of phoneData?.convs || []) {
      const clientId = Number.parseInt(
        String(
          conv.client_id ||
            conv.sender_client_id ||
            conv.counterpart_client_id ||
            "",
        ),
        10,
      );
      if (!clientId) continue;
      if (options.clientId && clientId !== options.clientId) continue;

      const conversationKey = `${conv.kind || "unknown"}|${memberPhone}|${conv.counterpart}`;
      const analysis = analysisByKey.get(conversationKey);
      if (!analysis) continue;

      const sections = analysis.sections || {};
      const row = {
        client_id: clientId,
        conversation_key: conversationKey,
        member_phone: memberPhone,
        counterpart_key: conv.counterpart || null,
        display_name: conv.display_name || analysis.display || null,
        chat_kind: ["direct", "group"].includes(conv.kind)
          ? conv.kind
          : "unknown",
        case_status: inferCaseStatus(analysis),
        case_type: inferCaseType(analysis),
        source_model: "gpt-5.5",
        reasoning_effort: "xhigh",
        analysis_hash: "",
        analysis_id: analysis.analysis_id || null,
        message_count: Number(analysis.n ?? conv.n ?? 0),
        unread_count: Number(analysis.unread ?? conv.unread_count ?? 0),
        last_message_at: toDateOrNull(analysis.last_at || conv.last_at),
        priority_score: Number(analysis.priority_score || 0),
        flags: analysis.flags || [],
        recap: cleanHumanText(sections.state || analysis.summary || "", 1500),
        next_action: cleanHumanText(
          sections.action || analysis.next_action || "",
          1500,
        ),
        ideal_reply: cleanHumanText(
          sections.ideal_reply || analysis.ideal_reply || "",
          1500,
        ),
        evidence: cleanHumanText(sections.evidence || "", 1500),
        crm_packet: buildHumanCrmNote(analysis, conv),
        raw_sections: {
          ...sections,
          technical_crm_packet_raw: sections.crm_packet || "",
          source_label: analysis.label || "",
          source_display: analysis.display || "",
        },
        analysis_output_path: analysis.relative_path || null,
        generated_at: toDateOrNull(analysis.output_mtime),
      };
      row.analysis_hash = stableHash({
        conversation_key: row.conversation_key,
        analysis_id: row.analysis_id,
        recap: row.recap,
        next_action: row.next_action,
        ideal_reply: row.ideal_reply,
        evidence: row.evidence,
        flags: row.flags,
      });
      rows.push(row);
    }
  }

  const uniqueRows = uniqueBy(
    rows,
    (row) => `${row.client_id}|${row.conversation_key}`,
  ).sort((a, b) => {
    if (b.priority_score !== a.priority_score)
      return b.priority_score - a.priority_score;
    return (
      (b.last_message_at?.getTime() || 0) - (a.last_message_at?.getTime() || 0)
    );
  });

  return options.limit ? uniqueRows.slice(0, options.limit) : uniqueRows;
}

async function publishRows(databaseUrl, rows) {
  const pool = new Pool({
    connectionString: databaseUrl,
    max: 2,
    idleTimeoutMillis: 30000,
  });
  const client = await pool.connect();
  let inserted = 0;
  let updated = 0;

  try {
    await client.query("BEGIN");
    for (const row of rows) {
      const result = await client.query(
        `
        INSERT INTO crm_wa_case_intelligence (
          client_id, conversation_key, member_phone, counterpart_key, display_name,
          chat_kind, case_status, case_type, source_model, reasoning_effort,
          analysis_hash, analysis_id, message_count, unread_count,
          last_message_at, priority_score, flags, recap, next_action,
          ideal_reply, evidence, crm_packet, raw_sections,
          analysis_output_path, generated_at
        ) VALUES (
          $1, $2, $3, $4, $5,
          $6, $7, $8, $9, $10,
          $11, $12, $13, $14,
          $15, $16, $17::jsonb, $18, $19,
          $20, $21, $22, $23::jsonb,
          $24, $25
        )
        ON CONFLICT (client_id, conversation_key) DO UPDATE SET
          member_phone = EXCLUDED.member_phone,
          counterpart_key = EXCLUDED.counterpart_key,
          display_name = EXCLUDED.display_name,
          chat_kind = EXCLUDED.chat_kind,
          case_status = EXCLUDED.case_status,
          case_type = EXCLUDED.case_type,
          source_model = EXCLUDED.source_model,
          reasoning_effort = EXCLUDED.reasoning_effort,
          analysis_hash = EXCLUDED.analysis_hash,
          analysis_id = EXCLUDED.analysis_id,
          message_count = EXCLUDED.message_count,
          unread_count = EXCLUDED.unread_count,
          last_message_at = EXCLUDED.last_message_at,
          priority_score = EXCLUDED.priority_score,
          flags = EXCLUDED.flags,
          recap = EXCLUDED.recap,
          next_action = EXCLUDED.next_action,
          ideal_reply = EXCLUDED.ideal_reply,
          evidence = EXCLUDED.evidence,
          crm_packet = EXCLUDED.crm_packet,
          raw_sections = EXCLUDED.raw_sections,
          analysis_output_path = EXCLUDED.analysis_output_path,
          generated_at = EXCLUDED.generated_at,
          imported_at = NOW(),
          updated_at = NOW()
        RETURNING (xmax = 0) AS inserted
        `,
        [
          row.client_id,
          row.conversation_key,
          row.member_phone,
          row.counterpart_key,
          row.display_name,
          row.chat_kind,
          row.case_status,
          row.case_type,
          row.source_model,
          row.reasoning_effort,
          row.analysis_hash,
          row.analysis_id,
          row.message_count,
          row.unread_count,
          row.last_message_at,
          row.priority_score,
          JSON.stringify(row.flags),
          row.recap,
          row.next_action,
          row.ideal_reply,
          row.evidence,
          row.crm_packet,
          JSON.stringify(row.raw_sections),
          row.analysis_output_path,
          row.generated_at,
        ],
      );
      if (result.rows[0]?.inserted) inserted += 1;
      else updated += 1;
    }
    await client.query("COMMIT");
  } catch (err) {
    await client.query("ROLLBACK");
    throw err;
  } finally {
    client.release();
    await pool.end();
  }

  return { inserted, updated };
}

async function filterRowsWithExistingClients(databaseUrl, rows) {
  if (!rows.length) {
    return {
      rows,
      skippedMissingRows: 0,
      skippedMissingClients: 0,
    };
  }

  const clientIds = uniqueBy(rows, (row) => row.client_id).map(
    (row) => row.client_id,
  );
  const pool = new Pool({
    connectionString: databaseUrl,
    max: 1,
    idleTimeoutMillis: 30000,
  });

  try {
    const result = await pool.query(
      "SELECT id FROM clients WHERE id = ANY($1::bigint[])",
      [clientIds],
    );
    const existingClientIds = new Set(
      result.rows.map((row) => Number(row.id)),
    );
    const validRows = rows.filter((row) =>
      existingClientIds.has(row.client_id),
    );
    const skippedRows = rows.filter(
      (row) => !existingClientIds.has(row.client_id),
    );

    return {
      rows: validRows,
      skippedMissingRows: skippedRows.length,
      skippedMissingClients: new Set(skippedRows.map((row) => row.client_id))
        .size,
    };
  } finally {
    await pool.end();
  }
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const [overview, analysisPayload] = await Promise.all([
    fetchOverview(options.dashboardUrl),
    Promise.resolve(analysisIndex.buildAnalysisIndexPayload({ force: true })),
  ]);
  const rows = buildRows(overview, analysisPayload, options);

  if (options.json) {
    process.stdout.write(
      `${JSON.stringify({ count: rows.length, rows }, null, 2)}\n`,
    );
    return;
  }

  if (options.dryRun || !options.databaseUrl) {
    console.log(
      JSON.stringify(
        {
          mode: options.dryRun ? "dry_run" : "no_database_url",
          dashboard_url: options.dashboardUrl,
          matched_rows: rows.length,
          clients: new Set(rows.map((row) => row.client_id)).size,
          top_cases: rows.slice(0, 8).map((row) => ({
            client_id: row.client_id,
            display_name: row.display_name,
            conversation_key: row.conversation_key,
            case_type: row.case_type,
            priority_score: row.priority_score,
          })),
        },
        null,
        2,
      ),
    );
    return;
  }

  const filtered = await filterRowsWithExistingClients(
    options.databaseUrl,
    rows,
  );
  const result = await publishRows(options.databaseUrl, filtered.rows);
  console.log(
    JSON.stringify(
      {
        mode: "published",
        dashboard_url: options.dashboardUrl,
        matched_rows: rows.length,
        published_rows: filtered.rows.length,
        clients: new Set(filtered.rows.map((row) => row.client_id)).size,
        skipped_missing_client_rows: filtered.skippedMissingRows,
        skipped_missing_clients: filtered.skippedMissingClients,
        inserted: result.inserted,
        updated: result.updated,
      },
      null,
      2,
    ),
  );
}

main().catch((err) => {
  console.error(`[publish-case-intelligence] ${err.stack || err.message}`);
  process.exit(1);
});
