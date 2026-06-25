#!/usr/bin/env node
"use strict";

const express = require("express");
const { Pool } = require("pg");
const fs = require("fs");
const path = require("path");
const metrics = require("./metrics.cjs");
const {
  actionBucketForRow,
  buildDirectActionSummary,
  buildQwenBatchGateSummary,
  buildQwenKnownBenchmarkSummary,
  buildQwenPlacementPreviewSummary,
  parserBucketForRow,
  workspaceBucketForDocType,
} = require("./intake-buckets.cjs");

const PORT = parseInt(process.env.PORT || "7790", 10);
const HOST = process.env.HOST || "0.0.0.0"; // bind also Tailnet (parity with wa-viewer:7777)

const DATABASE_URL =
  process.env.WA_DASHBOARD_DATABASE_URL ||
  process.env.DATABASE_URL;
if (!DATABASE_URL) {
  console.error("FATAL: WA_DASHBOARD_DATABASE_URL or DATABASE_URL must be set");
  process.exit(74);
}

const ACCOUNTS_JSON =
  process.env.WA_MIRROR_ACCOUNTS_JSON ||
  path.join(process.env.HOME || "/", ".wa-mirror.accounts.json");

const MEDIA_ROOT = process.env.WA_MIRROR_MEDIA_ROOT || "/Users/nuzantara/wa-mirror-media";
const TEAM_AVATAR_DIR = process.env.WA_TEAM_AVATAR_DIR || "/Users/nuzantara/Desktop/nuzantara/apps/mouth/public/static/team";
const QWEN_GATE_SNAPSHOT =
  process.env.INTAKE_QWEN_GATE_SNAPSHOT || "/tmp/intake-qwen-gate-snapshot.json";

// Team members hidden from views (parity with conversations columns; Law-2 perimeter).
const HIDE_TEAM_NAMES = new Set(
  (process.env.HIDE_TEAM_NAMES || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean),
);

const TEAM = (() => {
  try {
    const raw = JSON.parse(fs.readFileSync(ACCOUNTS_JSON, "utf8")).accounts || [];
    // Drop entries with empty e164 — they are placeholders (e.g. Subhi pre-onboarding)
    return raw.filter((m) => m && typeof m.e164 === "string" && m.e164.length > 0);
  } catch (err) {
    console.error(`[wa-dashboard-m1] cannot read ${ACCOUNTS_JSON}: ${err.message}`);
    return [];
  }
})();

// Map phone → TEAM entry, used by contactKindColor lookup
const TEAM_BY_PHONE = new Map();
for (const m of TEAM) {
  if (m.e164) TEAM_BY_PHONE.set(m.e164, m);
}

function readQwenGateSnapshot() {
  try {
    return JSON.parse(fs.readFileSync(QWEN_GATE_SNAPSHOT, "utf8"));
  } catch (_err) {
    return null;
  }
}

// === Contact kind/color taxonomy (2026-05-26 naming + color coding) ===
// 5 categories with WCAG AA+ contrast on both light (#ffffff/#efeae2) and dark backgrounds.
const KIND_COLORS = {
  zero:           "#fbbf24",   // gold        — Antonello (board)
  team_balizero:  "#06b6d4",   // cyan        — Bali Zero staff
  team_bayu:      "#3b82f6",   // vivid blue  — Bayu Santera partner staff
  client:         "#10b981",   // green       — in CRM clients table
  prospect:       "#a855f7",   // purple      — phone seen, no CRM match
};

function contactKindColor(account, isInClients) {
  if (account?.kind === "zero") {
    return { kind: "zero", color: KIND_COLORS.zero, label: "ZERO" };
  }
  if (account?.kind === "team") {
    if (account.company === "Bayu Santera") {
      return { kind: "team_bayu", color: KIND_COLORS.team_bayu, label: "TEAM·BS" };
    }
    return { kind: "team_balizero", color: KIND_COLORS.team_balizero, label: "TEAM·BZ" };
  }
  if (isInClients) {
    return { kind: "client", color: KIND_COLORS.client, label: "CLIENT" };
  }
  return { kind: "prospect", color: KIND_COLORS.prospect, label: "PROSPECT" };
}

// Build team→avatar map from disk
const TEAM_AVATAR_FILES = {};
try {
  if (fs.existsSync(TEAM_AVATAR_DIR)) {
    const files = fs.readdirSync(TEAM_AVATAR_DIR);
    for (const m of TEAM) {
      const lower = m.name.toLowerCase();
      const candidates = files.filter((f) => f.toLowerCase().startsWith(lower + "."));
      if (candidates.length) {
        TEAM_AVATAR_FILES[m.e164] = path.join(TEAM_AVATAR_DIR, candidates[0]);
      }
    }
  }
} catch (err) {
  console.warn(`[wa-dashboard-m1] team avatar load failed: ${err.message}`);
}

const TEAM_PHONES = new Set();
for (const m of TEAM) {
  if (m.e164) TEAM_PHONES.add(m.e164);
}

const INTERNAL_NAME_PATTERNS = [
  /^bali\s*zero/i,
  /^bz\s*halo/i,
  /^halo\s*bz/i,
  /^bali\s*zero\s*halo/i,
  /^bz\b/i,
  /^zantara/i,
];
function isInternalName(name) {
  if (!name) return false;
  return INTERNAL_NAME_PATTERNS.some((re) => re.test(String(name).trim()));
}
// Reject junk auto-names like "wa:+628...", "Lead +628...", bare digits.
// Real human names never start with "wa:" or "Lead " followed by digits.
const JUNK_NAME_PATTERNS = [
  /^wa:\+?[0-9]+$/i,
  /^lead\s*\+?[0-9]+$/i,
  /^\+?[0-9]{8,}$/,
];
function cleanName(name) {
  if (!name) return null;
  const s = String(name).trim();
  if (!s) return null;
  if (JUNK_NAME_PATTERNS.some((re) => re.test(s))) return null;
  return s.replace(/\s+/g, " ");
}

const pool = new Pool({ connectionString: DATABASE_URL, max: 6, idleTimeoutMillis: 30000 });
pool.on("error", (err) => console.error("[pg-pool-error]", err.message));

const CACHE = { teams: { at: 0, payload: null } };
const CACHE_MS = 5000;

function aliasesForTeamMember(member) {
  const aliases = new Set();
  if (member.e164) {
    aliases.add(member.e164);
    // Bali Zero halo team phones single-7 vs double-7 (Baileys legacy)
    // single-7 example: +628213454725 (13 digits)
    // double-7 example: +6282134547725 (14 digits, extra "7" after +6282134547)
    // single-7  +628213454725 (13 chars) → double-7  +6282134547725 (14 chars)
    // insert "7" at position 11 (after "+6282134547")
    if (member.e164.startsWith("+6282134547") && member.e164.length === 13) {
      const doubleSeven = member.e164.slice(0, 11) + "7" + member.e164.slice(11);
      aliases.add(doubleSeven);
    }
  }
  return [...aliases];
}

function isTeamPhone(phone) {
  return !!phone && TEAM_PHONES.has(phone);
}

// === Bridge health introspection (Feature #2: Bridge health pill) ===
function bridgeHealthFor(memberName) {
  const lower = memberName.toLowerCase();
  const pidFile = `/tmp/wa-mirror-pids/${lower}.pid`;
  const logFile = `/tmp/wa-mirror-logs/${lower}.log`;
  let pid = null;
  let alive = false;
  let needsQr = false;
  let logTail = null;
  try {
    if (fs.existsSync(pidFile)) {
      pid = parseInt(fs.readFileSync(pidFile, "utf8").trim(), 10);
      if (pid) {
        try {
          process.kill(pid, 0);
          alive = true;
        } catch {
          alive = false;
        }
      }
    }
    if (fs.existsSync(logFile)) {
      const data = fs.readFileSync(logFile, "utf8");
      const lines = data.trim().split("\n");
      logTail = lines.slice(-3).join(" | ").slice(-400);
      if (/QR salvato|QR code|please scan|needs.*qr/i.test(data.slice(-4000))) {
        needsQr = true;
      }
    }
  } catch {}
  let runtime;
  if (alive) runtime = "running";
  else if (needsQr) runtime = "needs_qr";
  else runtime = "stopped";
  return { pid, runtime_status: runtime, log_tail: logTail };
}

async function teamSessionFor(member) {
  const aliases = aliasesForTeamMember(member);
  const r = await pool.query(
    `
    SELECT status, connected_at, last_seen_at, disconnected_at, disconnect_reason,
           messages_logged, messages_filtered
    FROM whatsapp_team_sessions
    WHERE team_member_phone = ANY($1::text[])
       OR phone_normalized = ANY($2::text[])
    ORDER BY (status = 'connected') DESC, updated_at DESC NULLS LAST
    LIMIT 1
    `,
    [aliases, aliases.map((a) => a.replace(/\D/g, ""))],
  );
  return r.rows[0] || null;
}

// === MAIN overview query ===
async function fetchOverview() {
  if (CACHE.teams.payload && Date.now() - CACHE.teams.at < CACHE_MS) {
    return CACHE.teams.payload;
  }

  const result = { generated_at: new Date().toISOString(), team: [], by_phone: {} };
  result.team = TEAM.map((m) => {
    const kindInfo = contactKindColor(m, false);
    return {
      name: m.name,
      full_name: m.full_name || m.name,
      phone: m.e164,
      label: m.label || "BZ",
      role: m.role || "team",
      // 2026-05-26 naming + color coding
      company: m.company || "Bali Zero",
      department: m.department || "setup",
      kind: m.kind || "team",
      contact_kind: kindInfo.kind,
      contact_color: kindInfo.color,
      contact_label: kindInfo.label,
      aliases: aliasesForTeamMember(m),
      avatar_url: TEAM_AVATAR_FILES[m.e164] ? `/team-avatar/${encodeURIComponent(m.name.toLowerCase())}` : null,
    };
  });

  // P1 fix 2026-05-26: serial for-loop → Promise.all(.map()) parallelize cross-member.
  // Each member's payload is keyed by member.phone in result.by_phone (no shared state,
  // safe to parallelize). Reduces refresh latency from N×roundtrip to 1×roundtrip
  // for the slowest member.
  await Promise.all(result.team.map(async (member) => {
    const aliases = member.aliases;
    const since = "30 days";

    const [directRows, groupRows, sessionInfo] = await Promise.all([
      pool.query(
        `
      WITH base AS (
        SELECT
          NULLIF(m.counterpart_phone, '') AS direct_phone,
          NULLIF(m.counterpart_lid, '') AS lid,
          lpr.resolved_phone AS lid_resolved_phone,
          -- 2026-05-26 fix #2: extract pushname from whatsapp_lid_phone_map for this team member's view
          -- (lid map is per-team-member; same lid can have different pushname across team members per cicatrix LID collision)
          lpm.pushname AS lid_pushname,
          m.body, m.media_type, m.message_date, m.raw_baileys_event, m.direction, m.client_id,
          m.attention_priority, m.attention_resolved_at
        FROM whatsapp_message_context m
        LEFT JOIN wa_lid_phone_resolution lpr ON lpr.counterpart_lid = m.counterpart_lid
        LEFT JOIN whatsapp_lid_phone_map lpm
          ON lpm.lid = m.counterpart_lid
         AND lpm.team_member_phone = m.team_member_phone
        WHERE m.team_member_phone = ANY($1::text[])
          AND m.chat_type = 'direct'
          AND m.message_date >= NOW() - INTERVAL '${since}'
          AND (
            (m.counterpart_phone IS NOT NULL AND m.counterpart_phone <> '')
            OR (m.counterpart_lid IS NOT NULL AND m.counterpart_lid <> '')
          )
          AND (
            COALESCE(length(m.body),0) > 0
            OR m.media_type IN ('image','document','video','audio','sticker')
          )
      ),
      keyed AS (
        SELECT base.*,
               -- conv_key normalizes: phone > resolved_phone > lid:xxx
               COALESCE(direct_phone, lid_resolved_phone, 'lid:' || lid) AS conv_key,
               -- effective phone for CRM lookup (real or resolved)
               COALESCE(direct_phone, lid_resolved_phone) AS effective_phone
        FROM base
      ),
      last_outbound AS (
        SELECT conv_key, MAX(message_date) AS last_outbound_at
        FROM keyed
        WHERE direction = 'outbound'
        GROUP BY conv_key
      ),
      grouped AS (
        SELECT k.conv_key,
               MAX(COALESCE(k.direct_phone, k.effective_phone)) AS direct_phone,
               MAX(k.lid) AS lid,
               MAX(k.lid_pushname) AS lid_pushname,
               MAX(k.effective_phone) AS effective_phone,
               MAX(k.client_id) AS client_id,
               MAX(k.attention_priority) FILTER (WHERE k.attention_resolved_at IS NULL) AS attention_priority,
               COUNT(*) AS n,
               MAX(k.message_date) AS last_at,
               COUNT(*) FILTER (
                 WHERE k.direction = 'inbound'
                   AND k.message_date > COALESCE(lo.last_outbound_at, 'epoch'::timestamptz)
               ) AS unread_count
        FROM keyed k
        LEFT JOIN last_outbound lo USING (conv_key)
        GROUP BY k.conv_key
      ),
      last_msg AS (
        SELECT DISTINCT ON (conv_key) conv_key, body AS last_body, media_type AS last_media
        FROM keyed
        ORDER BY conv_key, message_date DESC NULLS LAST
      ),
      last_push AS (
        SELECT DISTINCT ON (conv_key)
               conv_key, raw_baileys_event->>'pushName' AS pushname
        FROM keyed
        WHERE direction = 'inbound' AND raw_baileys_event->>'pushName' IS NOT NULL
        ORDER BY conv_key, message_date DESC NULLS LAST
      )
      SELECT g.conv_key, g.direct_phone, g.lid, g.lid_pushname, g.client_id, g.n, g.last_at,
             g.attention_priority, g.unread_count,
             lm.last_body, lm.last_media, lp.pushname,
             COALESCE(cli_id.full_name, cli_phone.full_name, cli_archived.full_name) AS client_name,
             COALESCE(cli_id.company_name, cli_phone.company_name, cli_archived.company_name) AS company_name,
             COALESCE(cli_id.status, cli_phone.status, cli_archived.status) AS client_status,
             COALESCE(cli_id.id, cli_phone.id, cli_archived.id) AS resolved_client_id,
             COALESCE(cli_id.assigned_to, cli_phone.assigned_to, cli_archived.assigned_to) AS assigned_to,
             COALESCE(cli_id.tax_consultant, cli_phone.tax_consultant, cli_archived.tax_consultant) AS tax_consultant,
             COALESCE(cli_id.strategic_recap, cli_phone.strategic_recap, cli_archived.strategic_recap) AS strategic_recap,
             COALESCE(cli_id.strategic_recap_source, cli_phone.strategic_recap_source, cli_archived.strategic_recap_source) AS strategic_recap_source,
             COALESCE(cli_id.avatar_url, cli_phone.avatar_url, cli_archived.avatar_url) AS avatar_url,
             -- crm_archived = true se match SOLO via cli_archived (alive lookup failed)
             (cli_id.id IS NULL AND cli_phone.id IS NULL AND cli_archived.id IS NOT NULL) AS crm_archived,
             cli_archived.deleted_at AS archived_at,
             wc.name AS wa_contact_name,
             wc.business_name AS wa_business_name
      FROM grouped g
      LEFT JOIN last_msg lm USING (conv_key)
      LEFT JOIN last_push lp USING (conv_key)
      LEFT JOIN clients cli_id
        ON cli_id.id = g.client_id AND cli_id.deleted_at IS NULL
      LEFT JOIN clients cli_phone
        ON cli_phone.deleted_at IS NULL
       AND COALESCE(g.effective_phone, g.direct_phone) IS NOT NULL
       AND (
         cli_phone.phone_normalized = regexp_replace(COALESCE(g.effective_phone, g.direct_phone), '\\D', '', 'g')
         OR cli_phone.phone = COALESCE(g.effective_phone, g.direct_phone)
         OR cli_phone.whatsapp = COALESCE(g.effective_phone, g.direct_phone)
       )
      -- Fallback: soft-deleted clients still talking on WA (cicatrix marzo-2026 7733-purge ghosts)
      LEFT JOIN LATERAL (
        SELECT id, full_name, company_name, status, assigned_to, tax_consultant,
               strategic_recap, strategic_recap_source, avatar_url, deleted_at
        FROM clients
        WHERE deleted_at IS NOT NULL
          AND COALESCE(g.effective_phone, g.direct_phone) IS NOT NULL
          AND (
            phone_normalized = regexp_replace(COALESCE(g.effective_phone, g.direct_phone), '\\D', '', 'g')
            OR phone = COALESCE(g.effective_phone, g.direct_phone)
            OR whatsapp = COALESCE(g.effective_phone, g.direct_phone)
          )
        ORDER BY deleted_at DESC
        LIMIT 1
      ) cli_archived ON cli_id.id IS NULL AND cli_phone.id IS NULL
      LEFT JOIN whatsapp_contacts wc
        ON COALESCE(g.effective_phone, g.direct_phone) IS NOT NULL
       AND wc.phone_normalized = regexp_replace(COALESCE(g.effective_phone, g.direct_phone), '\\D', '', 'g')
      ORDER BY g.last_at DESC NULLS LAST
      LIMIT 200;
      `,
        [aliases],
      ),
      pool.query(
        `
      WITH base AS (
        SELECT group_jid,
               COALESCE(NULLIF(group_subject_snapshot, ''), group_jid) AS group_label,
               direction, message_date, attention_priority, attention_resolved_at
        FROM whatsapp_message_context
        WHERE team_member_phone = ANY($1::text[])
          AND chat_type = 'group'
          AND group_jid IS NOT NULL
          AND message_date >= NOW() - INTERVAL '${since}'
      ),
      last_outbound AS (
        SELECT group_jid, MAX(message_date) AS last_outbound_at
        FROM base
        WHERE direction = 'outbound'
        GROUP BY group_jid
      ),
      grouped AS (
        SELECT b.group_jid,
               MAX(b.group_label) AS group_label,
               COUNT(*) AS n,
               MAX(b.message_date) AS last_at,
               MAX(b.attention_priority) FILTER (WHERE b.attention_resolved_at IS NULL) AS attention_priority,
               COUNT(*) FILTER (
                 WHERE b.direction = 'inbound'
                   AND b.message_date > COALESCE(lo.last_outbound_at, 'epoch'::timestamptz)
               ) AS unread_count
        FROM base b
        LEFT JOIN last_outbound lo USING (group_jid)
        GROUP BY b.group_jid
      ),
      last_msg AS (
        SELECT DISTINCT ON (group_jid)
               group_jid, body AS last_body, media_type AS last_media, sender_phone,
               raw_baileys_event->>'pushName' AS sender_pushname
        FROM whatsapp_message_context
        WHERE team_member_phone = ANY($1::text[])
          AND chat_type = 'group'
          AND group_jid IS NOT NULL
        ORDER BY group_jid, message_date DESC NULLS LAST
      )
      SELECT g.group_jid, g.group_label, g.n, g.last_at, g.attention_priority, g.unread_count,
             lm.last_body, lm.last_media, lm.sender_phone, lm.sender_pushname,
             cli.full_name AS sender_crm_name,
             cli.company_name AS sender_company,
             cli.strategic_recap AS sender_strategic_recap,
             cli.avatar_url AS sender_avatar_url,
             wc.name AS sender_wa_contact_name
      FROM grouped g
      LEFT JOIN last_msg lm USING (group_jid)
      LEFT JOIN clients cli
        ON cli.deleted_at IS NULL
       AND lm.sender_phone IS NOT NULL
       AND (
         cli.phone_normalized = regexp_replace(lm.sender_phone, '\\D', '', 'g')
         OR cli.phone = lm.sender_phone
         OR cli.whatsapp = lm.sender_phone
       )
      LEFT JOIN whatsapp_contacts wc
        ON lm.sender_phone IS NOT NULL
       AND wc.phone_normalized = regexp_replace(lm.sender_phone, '\\D', '', 'g')
      ORDER BY g.last_at DESC NULLS LAST
      LIMIT 200;
      `,
        [aliases],
      ),
      teamSessionFor(member),
    ]);

    const bridge = bridgeHealthFor(member.name);

    // === Build convs array ===
    const convs = [];
    let attentionHigh = 0;
    let attentionMedium = 0;
    let crmMatched = 0;
    let unresolvedLids = 0;
    let internalCount = 0;

    for (const r of directRows.rows) {
      // Display name with priority: CRM > TEAM > WA business > WA contact > raw-message pushName > lid_phone_map pushname > phone
      const crmName = cleanName(r.client_name);
      const businessName = cleanName(r.wa_business_name);
      const waName = cleanName(r.wa_contact_name);
      const push = cleanName(r.pushname);
      // 2026-05-26 fix #2: pushname from whatsapp_lid_phone_map (for LID-only conv where Baileys raw event has no pushName)
      const lidPush = cleanName(r.lid_pushname);

      // 2026-05-26 lookup TEAM roster FIRST so internal counterpart resolves to display name
      const teamMatch = r.direct_phone ? TEAM_BY_PHONE.get(r.direct_phone) : null;
      const teamName = teamMatch ? (teamMatch.full_name || teamMatch.name) : null;

      let display = crmName || teamName;
      if (display && crmName && r.company_name) display = `${crmName} · ${r.company_name}`;
      if (!display) display = businessName || waName || push || lidPush || r.direct_phone || r.conv_key;
      const isInternal = isTeamPhone(r.direct_phone);
      const isLid = !r.direct_phone && r.lid;
      const isCrmArchived = !!r.crm_archived;
      let tag;
      if (isInternal) { tag = "internal"; internalCount++; }
      else if (crmName && !isCrmArchived) { tag = "crm"; crmMatched++; }
      else if (crmName && isCrmArchived) { tag = "crm-archived"; }
      else if (push || waName || businessName || lidPush) tag = "prospect";
      else if (isLid) { tag = "lid"; unresolvedLids++; }
      else tag = "unknown";

      // 2026-05-26 naming + color coding: contactKindColor over counterpart
      // Hierarchy: ZERO > TEAM·BZ > TEAM·BS > CLIENT > PROSPECT
      const isInClients = !!crmName; // active or archived CRM match counts
      const kindInfo = contactKindColor(teamMatch, isInClients);

      if (r.attention_priority === "HIGH") attentionHigh++;
      else if (r.attention_priority === "MEDIUM") attentionMedium++;

      convs.push({
        kind: "direct",
        counterpart: r.direct_phone || r.conv_key,
        display_name: display,
        crm_match: !!crmName,
        crm_archived: isCrmArchived,
        archived_at: r.archived_at,
        client_id: r.resolved_client_id || r.client_id,
        client_status: r.client_status,
        assigned_to: r.assigned_to,
        tax_consultant: r.tax_consultant,
        strategic_recap: r.strategic_recap,
        strategic_recap_source: r.strategic_recap_source,
        avatar_url: r.avatar_url,
        company_name: r.company_name,
        wa_contact_name: waName,
        wa_business_name: businessName,
        pushname: push,
        attention_priority: r.attention_priority,
        n: parseInt(r.n, 10),
        unread_count: parseInt(r.unread_count || 0, 10),
        last_at: r.last_at,
        last_body: r.last_body,
        last_media: r.last_media,
        is_internal: isInternal,
        is_legacy_lid: !!isLid,
        tag,
        // 2026-05-26 naming + color coding
        contact_kind: kindInfo.kind,
        contact_color: kindInfo.color,
        contact_label: kindInfo.label,
        contact_company: teamMatch?.company || null,
        contact_department: teamMatch?.department || null,
      });
    }
    for (const r of groupRows.rows) {
      const senderName = cleanName(r.sender_crm_name) || cleanName(r.sender_wa_contact_name) || cleanName(r.sender_pushname);
      const groupLabel = r.group_label && !r.group_label.endsWith("@g.us")
        ? r.group_label
        : (senderName
            ? `Gruppo ${senderName}${r.sender_company ? " (" + r.sender_company + ")" : ""}`
            : r.group_label);
      if (r.attention_priority === "HIGH") attentionHigh++;
      else if (r.attention_priority === "MEDIUM") attentionMedium++;

      // 2026-05-26 group kind/color reflects LAST sender (most informative for triage)
      const groupTeamMatch = r.sender_phone ? TEAM_BY_PHONE.get(r.sender_phone) : null;
      const groupIsInClients = !!r.sender_crm_name;
      const groupKindInfo = contactKindColor(groupTeamMatch, groupIsInClients);

      convs.push({
        kind: "group",
        counterpart: `group:${r.group_jid}`,
        display_name: groupLabel,
        group_jid: r.group_jid,
        sender_phone: r.sender_phone,
        sender_crm_name: cleanName(r.sender_crm_name),
        sender_wa_contact_name: cleanName(r.sender_wa_contact_name),
        sender_company: r.sender_company,
        sender_strategic_recap: r.sender_strategic_recap,
        sender_avatar_url: r.sender_avatar_url,
        crm_match: !!r.sender_crm_name,
        attention_priority: r.attention_priority,
        n: parseInt(r.n, 10),
        unread_count: parseInt(r.unread_count || 0, 10),
        last_at: r.last_at,
        last_body: r.last_body,
        last_media: r.last_media,
        is_internal: false,
        tag: "group",
        // 2026-05-26 naming + color coding
        contact_kind: groupKindInfo.kind,
        contact_color: groupKindInfo.color,
        contact_label: groupKindInfo.label,
        contact_company: groupTeamMatch?.company || null,
        contact_department: groupTeamMatch?.department || null,
      });
    }
    convs.sort((a, b) => new Date(b.last_at) - new Date(a.last_at));

    // True raw count from DB (not conv-aggregated, single source of truth)
    const rawCountRow = await pool.query(
      `
      SELECT
        COUNT(*) AS msgs_total,
        COUNT(*) FILTER (WHERE chat_type='direct') AS msgs_direct,
        COUNT(*) FILTER (WHERE chat_type='group')  AS msgs_group,
        COUNT(*) FILTER (WHERE chat_type='direct' AND counterpart_phone IS NULL AND counterpart_lid IS NOT NULL) AS msgs_lid_only,
        COUNT(*) FILTER (WHERE media_type IN ('image','document','video','audio','sticker')) AS msgs_media
      FROM whatsapp_message_context
      WHERE team_member_phone = ANY($1::text[])
        AND message_date >= NOW() - INTERVAL '${since}'
      `,
      [aliases],
    );
    const counts = rawCountRow.rows[0] || {};

    const unreadTotal = convs.reduce((sum, c) => sum + (c.unread_count || 0), 0);
    const unreadConvs = convs.filter((c) => (c.unread_count || 0) > 0).length;
    const archivedCount = convs.filter((c) => c.crm_archived).length;

    result.by_phone[member.phone] = {
      team: member,
      bridge,                    // Feature #2 (health pill)
      session: sessionInfo,      // messages_logged / messages_filtered / connected_at
      total: parseInt(counts.msgs_total || 0, 10),
      msgs_direct: parseInt(counts.msgs_direct || 0, 10),
      msgs_group: parseInt(counts.msgs_group || 0, 10),
      msgs_lid_only: parseInt(counts.msgs_lid_only || 0, 10),
      msgs_media: parseInt(counts.msgs_media || 0, 10),
      direct_count: convs.filter((c) => c.kind === "direct").length,
      group_count: convs.filter((c) => c.kind === "group").length,
      crm_count: crmMatched,
      internal_count: internalCount,
      unresolved_lids: unresolvedLids,
      unread_total: unreadTotal,         // Feature: unread badge (col 1 team pill)
      unread_convs: unreadConvs,
      archived_count: archivedCount,     // Feature: ghost CRM clients still talking on WA

      attention: { high: attentionHigh, medium: attentionMedium }, // Feature #7
      convs,
    };
  }));

  CACHE.teams = { at: Date.now(), payload: result };
  return result;
}

async function fetchIntakeSummary() {
  const [queueRows, groupKindRows, directRows, routingRows] = await Promise.all([
    pool.query(
      `
      WITH docs AS (
        SELECT
          CASE
            WHEN q.source_context->>'chat_type' = 'direct' THEN 'direct'
            WHEN q.source_context->>'chat_type' = 'group' THEN 'group'
            ELSE 'unknown'
          END AS scope,
          q.status,
          COALESCE(q.stage_output->'classify'->>'doc_type', 'unknown') AS doc_type,
          CASE
            WHEN COALESCE(q.stage_output->'classify'->>'type_confidence', '') ~ '^[0-9]+(\\.[0-9]+)?$'
            THEN (q.stage_output->'classify'->>'type_confidence')::numeric
            ELSE 0
          END AS type_confidence,
          COALESCE((
            SELECT SUM(length(
              CASE
                WHEN jsonb_typeof(page.value) = 'object' THEN COALESCE(page.value->>'text', page.value->>'ocr_text', '')
                WHEN jsonb_typeof(page.value) = 'string' THEN trim(both '"' from page.value::text)
                ELSE ''
              END
            ))
            FROM jsonb_array_elements(
              CASE
                WHEN jsonb_typeof(q.stage_output->'classify'->'ocr_text_per_page') = 'array'
                THEN q.stage_output->'classify'->'ocr_text_per_page'
                ELSE '[]'::jsonb
              END
            ) AS page(value)
          ), 0) AS ocr_chars,
          q.sender_phone,
          q.client_id_hint,
          q.source_context
        FROM intake_queue q
        WHERE q.source = 'whatsapp'
          AND q.source_ref LIKE 'wa-mirror:%'
      )
      SELECT
        COUNT(*) AS total,
        COUNT(*) FILTER (WHERE scope='direct') AS direct_docs,
        COUNT(*) FILTER (WHERE scope='group') AS group_docs,
        COUNT(*) FILTER (WHERE scope='unknown') AS unknown_context_docs,
        COUNT(*) FILTER (WHERE status='done') AS done_docs,
        COUNT(*) FILTER (WHERE status='dead') AS dead_docs,
        COUNT(*) FILTER (WHERE scope='direct' AND doc_type <> 'unknown') AS direct_known_docs,
        COUNT(*) FILTER (WHERE scope='direct' AND doc_type = 'unknown') AS direct_unknown_docs,
        COUNT(*) FILTER (WHERE scope='direct' AND doc_type <> 'unknown' AND type_confidence >= 0.70) AS direct_high_conf_docs,
        COUNT(*) FILTER (WHERE scope='direct' AND doc_type <> 'unknown' AND type_confidence < 0.70) AS direct_low_conf_known_docs,
        COUNT(*) FILTER (WHERE scope='direct' AND doc_type = 'unknown' AND ocr_chars = 0) AS direct_unknown_ocr_empty,
        COUNT(*) FILTER (WHERE scope='direct' AND doc_type = 'unknown' AND ocr_chars > 0) AS direct_unknown_ocr_text,
        COUNT(*) FILTER (WHERE source_context <> '{}'::jsonb) AS with_source_context,
        COUNT(*) FILTER (WHERE scope='group' AND sender_phone IS NOT NULL) AS group_unsafe_sender_phone,
        COUNT(*) FILTER (WHERE scope='group' AND client_id_hint IS NOT NULL) AS group_unsafe_client_hint
      FROM docs
      `,
    ),
    pool.query(
      `
      WITH group_docs AS (
        SELECT
          w.group_jid,
          COUNT(*) AS docs,
          COUNT(*) FILTER (WHERE q.status='done') AS done_docs,
          COUNT(*) FILTER (WHERE q.status='dead') AS dead_docs,
          BOOL_OR(q.sender_phone IS NOT NULL) AS has_unsafe_sender_phone,
          BOOL_OR(q.client_id_hint IS NOT NULL) AS has_unsafe_client_hint,
          COUNT(DISTINCT w.sender_phone) FILTER (WHERE COALESCE(w.sender_phone,'') <> '') AS distinct_senders,
          COUNT(DISTINCT w.team_member_phone) FILTER (WHERE COALESCE(w.team_member_phone,'') <> '') AS team_accounts_seen
        FROM intake_queue q
        JOIN whatsapp_message_context w
          ON q.source_ref = 'wa-mirror:' || w.baileys_message_id
        WHERE q.source = 'whatsapp'
          AND q.source_ref LIKE 'wa-mirror:%'
          AND (w.chat_type = 'group' OR w.group_jid IS NOT NULL)
        GROUP BY w.group_jid
      ),
      classified AS (
        SELECT *,
          CASE
            WHEN team_accounts_seen >= 3 AND distinct_senders <= 3 THEN 'team_coordination_likely'
            WHEN distinct_senders <= 2 THEN 'small_client_group_likely'
            WHEN distinct_senders BETWEEN 3 AND 6 THEN 'multi_party_case_likely'
            ELSE 'large_or_broadcast_group'
          END AS inferred_group_kind
        FROM group_docs
      )
      SELECT inferred_group_kind,
             COUNT(*) AS groups,
             SUM(docs) AS docs,
             SUM(done_docs) AS done_docs,
             SUM(dead_docs) AS dead_docs,
             SUM(CASE WHEN has_unsafe_sender_phone THEN 1 ELSE 0 END) AS unsafe_sender_groups,
             SUM(CASE WHEN has_unsafe_client_hint THEN 1 ELSE 0 END) AS unsafe_hint_groups,
             percentile_disc(0.5) WITHIN GROUP (ORDER BY docs) AS median_docs_per_group,
             MAX(docs) AS max_docs_per_group
      FROM classified
      GROUP BY inferred_group_kind
      ORDER BY docs DESC
      `,
    ),
    pool.query(
      `
      WITH latest AS (
        SELECT DISTINCT ON (queue_id)
               queue_id,
               status AS proposal_status,
               entity_resolution->>'decision' AS entity_decision
        FROM document_routing_proposal
        ORDER BY queue_id, created_at DESC, id DESC
      ),
      direct_docs AS (
        SELECT
          q.id,
          q.status AS queue_status,
          COALESCE(q.stage_output->'classify'->>'doc_type', 'unknown') AS doc_type,
          CASE
            WHEN COALESCE(q.stage_output->'classify'->>'type_confidence', '') ~ '^[0-9]+(\\.[0-9]+)?$'
            THEN (q.stage_output->'classify'->>'type_confidence')::numeric
            ELSE 0
          END AS type_confidence,
          COALESCE((q.stage_output ? 'extract') AND NOT COALESCE((q.stage_output->'extract'->>'stub')::boolean, false), false) AS extracted_non_stub,
          COALESCE((q.stage_output ? 'route') AND NOT COALESCE((q.stage_output->'route'->>'stub')::boolean, false), false) AS routed_non_stub,
          COALESCE((
            SELECT SUM(length(
              CASE
                WHEN jsonb_typeof(page.value) = 'object' THEN COALESCE(page.value->>'text', page.value->>'ocr_text', '')
                WHEN jsonb_typeof(page.value) = 'string' THEN trim(both '"' from page.value::text)
                ELSE ''
              END
            ))
            FROM jsonb_array_elements(
              CASE
                WHEN jsonb_typeof(q.stage_output->'classify'->'ocr_text_per_page') = 'array'
                THEN q.stage_output->'classify'->'ocr_text_per_page'
                ELSE '[]'::jsonb
              END
            ) AS page(value)
          ), 0) AS ocr_chars,
          COALESCE(l.proposal_status, 'NO_PROPOSAL') AS proposal_status,
          COALESCE(l.entity_decision, 'NO_PROPOSAL') AS entity_decision,
          w.media_type
        FROM intake_queue q
        JOIN whatsapp_message_context w
          ON q.source_ref = 'wa-mirror:' || w.baileys_message_id
        LEFT JOIN latest l ON l.queue_id = q.id
        WHERE q.source = 'whatsapp'
          AND q.source_ref LIKE 'wa-mirror:%'
          AND NOT (w.chat_type = 'group' OR w.group_jid IS NOT NULL)
      )
      SELECT *
      FROM direct_docs
      `,
    ),
    pool.query(
      `
      WITH latest AS (
        SELECT DISTINCT ON (queue_id)
               queue_id,
               status AS proposal_status,
               entity_resolution->>'decision' AS entity_decision
        FROM document_routing_proposal
        ORDER BY queue_id, created_at DESC, id DESC
      )
      SELECT COALESCE(l.entity_decision, 'NO_PROPOSAL') AS entity_decision,
             COALESCE(l.proposal_status, 'NO_PROPOSAL') AS proposal_status,
             COUNT(*) AS docs
      FROM intake_queue q
      JOIN whatsapp_message_context w
        ON q.source_ref = 'wa-mirror:' || w.baileys_message_id
      LEFT JOIN latest l ON l.queue_id = q.id
      WHERE q.source = 'whatsapp'
        AND q.source_ref LIKE 'wa-mirror:%'
        AND NOT (w.chat_type = 'group' OR w.group_jid IS NOT NULL)
      GROUP BY 1,2
      ORDER BY docs DESC
      `,
    ),
  ]);

  const queue = queueRows.rows[0] || {};
  const docTypeMap = new Map();
  const parserMap = new Map();
  const actionMap = new Map();
  const workspaceMap = new Map();
  for (const row of directRows.rows) {
    const docType = row.doc_type || "unknown";
    const workspaceBucket = workspaceBucketForDocType(docType);
    const parserBucket = parserBucketForRow(row);
    const actionBucket = actionBucketForRow(row);
    const docKey = `${docType}|${workspaceBucket}`;
    const existingDoc = docTypeMap.get(docKey) || {
      doc_type: docType,
      workspace_bucket: workspaceBucket,
      docs: 0,
      high_confidence: 0,
      extracted_non_stub: 0,
      routed_non_stub: 0,
    };
    existingDoc.docs += 1;
    if (Number(row.type_confidence || 0) >= 0.7) existingDoc.high_confidence += 1;
    if (row.extracted_non_stub) existingDoc.extracted_non_stub += 1;
    if (row.routed_non_stub) existingDoc.routed_non_stub += 1;
    docTypeMap.set(docKey, existingDoc);

    parserMap.set(parserBucket, (parserMap.get(parserBucket) || 0) + 1);
    actionMap.set(actionBucket, (actionMap.get(actionBucket) || 0) + 1);
    workspaceMap.set(workspaceBucket, (workspaceMap.get(workspaceBucket) || 0) + 1);
  }

  const directActions = [...actionMap.entries()]
    .map(([bucket, docs]) => ({ bucket, docs }))
    .sort((a, b) => b.docs - a.docs);
  const directActionSummary = buildDirectActionSummary(directActions);
  const qwenGateSnapshot = readQwenGateSnapshot();
  const toInt = (v) => parseInt(v || 0, 10);
  return {
    generated_at: new Date().toISOString(),
    pii_policy: "aggregate_only_no_raw_phone_no_raw_group_subject_no_raw_ocr",
    source: "intake_queue + whatsapp_message_context",
    queue: {
      total: toInt(queue.total),
      direct_docs: toInt(queue.direct_docs),
      group_docs: toInt(queue.group_docs),
      unknown_context_docs: toInt(queue.unknown_context_docs),
      done_docs: toInt(queue.done_docs),
      dead_docs: toInt(queue.dead_docs),
      direct_known_docs: toInt(queue.direct_known_docs),
      direct_unknown_docs: toInt(queue.direct_unknown_docs),
      direct_high_conf_docs: toInt(queue.direct_high_conf_docs),
      direct_low_conf_known_docs: toInt(queue.direct_low_conf_known_docs),
      direct_unknown_ocr_empty: toInt(queue.direct_unknown_ocr_empty),
      direct_unknown_ocr_text: toInt(queue.direct_unknown_ocr_text),
      with_source_context: toInt(queue.with_source_context),
      group_unsafe_sender_phone: toInt(queue.group_unsafe_sender_phone),
      group_unsafe_client_hint: toInt(queue.group_unsafe_client_hint),
    },
    group_kinds: groupKindRows.rows.map((r) => ({
      inferred_group_kind: r.inferred_group_kind,
      groups: toInt(r.groups),
      docs: toInt(r.docs),
      done_docs: toInt(r.done_docs),
      dead_docs: toInt(r.dead_docs),
      unsafe_sender_groups: toInt(r.unsafe_sender_groups),
      unsafe_hint_groups: toInt(r.unsafe_hint_groups),
      median_docs_per_group: toInt(r.median_docs_per_group),
      max_docs_per_group: toInt(r.max_docs_per_group),
    })),
    direct_parser: [...parserMap.entries()]
      .map(([bucket, docs]) => ({ bucket, docs }))
      .sort((a, b) => b.docs - a.docs),
    direct_actions: directActions,
    direct_action_summary: directActionSummary,
    qwen_batch_gate: buildQwenBatchGateSummary(directActionSummary, qwenGateSnapshot),
    qwen_known_benchmark_gate: buildQwenKnownBenchmarkSummary(qwenGateSnapshot),
    qwen_placement_preview: buildQwenPlacementPreviewSummary(qwenGateSnapshot),
    workspace_buckets: [...workspaceMap.entries()]
      .map(([bucket, docs]) => ({ bucket, docs }))
      .sort((a, b) => b.docs - a.docs),
    direct_doc_types: [...docTypeMap.values()]
      .sort((a, b) => b.docs - a.docs)
      .slice(0, 30),
    direct_routing: routingRows.rows.map((r) => ({
      entity_decision: r.entity_decision,
      proposal_status: r.proposal_status,
      docs: toInt(r.docs),
    })),
  };
}

// === Thread query (Feature #4 wa_contact_name fallback in messages) ===
async function fetchThread(memberPhone, convKey) {
  const member = TEAM.find((m) => m.e164 === memberPhone);
  if (!member) throw new Error(`team member not found: ${memberPhone}`);
  const aliases = aliasesForTeamMember(member);

  let where = "";
  let params = [aliases];
  if (convKey.startsWith("group:")) {
    where = `AND m.chat_type = 'group' AND m.group_jid = $2`;
    params.push(convKey.slice("group:".length));
  } else if (convKey.startsWith("lid:")) {
    where = `AND m.counterpart_lid = $2`;
    params.push(convKey.slice("lid:".length));
  } else {
    // convKey is a phone — match either direct phone OR LID that resolves to it
    where = `AND (
      m.counterpart_phone = $2
      OR m.counterpart_lid IN (
        SELECT counterpart_lid FROM wa_lid_phone_resolution WHERE resolved_phone = $2
      )
    )`;
    params.push(convKey);
  }

  const rows = await pool.query(
    `
    SELECT m.id, m.direction, m.body, m.media_type, m.media_mime, m.media_url,
           m.media_stored_path, m.message_date,
           m.sender_phone, m.sender_push_name_snapshot, m.group_jid,
           m.counterpart_phone, m.counterpart_lid,
           lpr_c.resolved_phone AS counterpart_resolved_phone,
           lpr_s.resolved_phone AS sender_resolved_phone,
           m.attention_priority, m.attention_reason, m.attention_resolved_at,
           m.raw_baileys_event->>'pushName' AS pushname,
           cli_s.id AS sender_client_id,
           cli_s.full_name AS sender_crm_name,
           cli_s.company_name AS sender_company,
           cli_c.id AS counterpart_client_id,
           cli_c.full_name AS counterpart_crm_name,
           cli_c.company_name AS counterpart_company,
           wc_s.name AS sender_wa_contact_name,
           wc_s.business_name AS sender_wa_business_name,
           wc_c.name AS counterpart_wa_contact_name,
           wc_c.business_name AS counterpart_wa_business_name
    FROM whatsapp_message_context m
    LEFT JOIN wa_lid_phone_resolution lpr_c
      ON lpr_c.counterpart_lid = m.counterpart_lid
    LEFT JOIN wa_lid_phone_resolution lpr_s
      ON lpr_s.counterpart_lid = m.sender_lid
    LEFT JOIN clients cli_s
      ON cli_s.deleted_at IS NULL
     AND COALESCE(m.sender_phone, lpr_s.resolved_phone) IS NOT NULL
     AND (
       cli_s.phone_normalized = regexp_replace(COALESCE(m.sender_phone, lpr_s.resolved_phone), '\\D', '', 'g')
       OR cli_s.phone = COALESCE(m.sender_phone, lpr_s.resolved_phone)
       OR cli_s.whatsapp = COALESCE(m.sender_phone, lpr_s.resolved_phone)
     )
    LEFT JOIN clients cli_c
      ON cli_c.deleted_at IS NULL
     AND COALESCE(m.counterpart_phone, lpr_c.resolved_phone) IS NOT NULL
     AND (
       cli_c.phone_normalized = regexp_replace(COALESCE(m.counterpart_phone, lpr_c.resolved_phone), '\\D', '', 'g')
       OR cli_c.phone = COALESCE(m.counterpart_phone, lpr_c.resolved_phone)
       OR cli_c.whatsapp = COALESCE(m.counterpart_phone, lpr_c.resolved_phone)
     )
    LEFT JOIN whatsapp_contacts wc_s
      ON COALESCE(m.sender_phone, lpr_s.resolved_phone) IS NOT NULL
     AND wc_s.phone_normalized = regexp_replace(COALESCE(m.sender_phone, lpr_s.resolved_phone), '\\D', '', 'g')
    LEFT JOIN whatsapp_contacts wc_c
      ON COALESCE(m.counterpart_phone, lpr_c.resolved_phone) IS NOT NULL
     AND wc_c.phone_normalized = regexp_replace(COALESCE(m.counterpart_phone, lpr_c.resolved_phone), '\\D', '', 'g')
    WHERE m.team_member_phone = ANY($1::text[])
      ${where}
      AND m.message_date >= NOW() - INTERVAL '30 days'
      AND (
        COALESCE(length(m.body),0) > 0
        OR m.media_type IN ('image','document','video','audio','sticker')
      )
    ORDER BY m.message_date ASC, m.id ASC
    LIMIT 500;
    `,
    params,
  );
  return rows.rows.map((r) => {
    const effectivePhone = r.sender_phone || r.sender_resolved_phone;
    const formatted = effectivePhone ? `📱 ${effectivePhone}` : null;
    return {
      ...r,
      sender_display:
        cleanName(r.sender_crm_name) ||
        cleanName(r.sender_wa_business_name) ||
        cleanName(r.sender_wa_contact_name) ||
        cleanName(r.pushname) ||
        formatted,
      counterpart_resolved: r.counterpart_phone || r.counterpart_resolved_phone,
    };
  });
}

// === Client lookup with smart-recap (Feature #11) ===
async function fetchClientCard(clientId) {
  const r = await pool.query(
    `
    SELECT id, full_name, company_name, phone, whatsapp, status, assigned_to,
           tax_consultant, strategic_recap, strategic_recap_source,
           strategic_recap_updated_at, ai_summary, nationality, lead_source,
           service_interest, custom_fields, created_at, last_interaction_date,
           google_drive_folder_id
    FROM clients
    WHERE id = $1 AND deleted_at IS NULL
    `,
    [clientId],
  );
  return r.rows[0] || null;
}

// === Express app ===
const app = express();
app.disable("x-powered-by");

app.use((req, res, next) => {
  res.setHeader("Cache-Control", "no-store");
  next();
});

app.get("/health.json", async (_req, res) => {
  try {
    const r = await pool.query("SELECT 1 AS ok, NOW() AS now");
    res.json({
      ok: true,
      db_now: r.rows[0].now,
      team_size: TEAM.length,
      db_url_host: new URL(DATABASE_URL.replace(/^postgres/, "http")).host,
    });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
});

app.get("/data.json", async (_req, res) => {
  try {
    const payload = await fetchOverview();
    res.json(payload);
  } catch (err) {
    console.error("[data.json]", err);
    res.status(500).json({ error: err.message });
  }
});

app.get("/intake-summary.json", async (_req, res) => {
  try {
    const payload = await fetchIntakeSummary();
    res.json(payload);
  } catch (err) {
    console.error("[intake-summary.json]", err);
    res.status(500).json({ error: "intake summary query failed" });
  }
});

app.get("/thread.json", async (req, res) => {
  const memberPhone = typeof req.query.member === "string" ? req.query.member : "";
  const convKey = typeof req.query.conv === "string" ? req.query.conv : "";
  if (!memberPhone || !convKey) {
    return res.status(400).json({ error: "missing member or conv" });
  }
  try {
    const rows = await fetchThread(memberPhone, convKey);
    res.json({ member: memberPhone, conv: convKey, count: rows.length, messages: rows });
  } catch (err) {
    console.error("[thread.json] error", { code: err.code, name: err.name });
    res.status(500).json({ error: "thread query failed" });
  }
});

app.get("/client.json", async (req, res) => {
  const cid = parseInt(req.query.id, 10);
  if (!cid) return res.status(400).json({ error: "missing id" });
  try {
    const row = await fetchClientCard(cid);
    if (!row) return res.status(404).json({ error: "not found" });
    res.json(row);
  } catch (err) {
    console.error("[client.json]", err);
    res.status(500).json({ error: err.message });
  }
});

// === Media inline (Feature #9) ===
const MIME_BY_EXT = {
  ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
  ".gif": "image/gif", ".webp": "image/webp", ".pdf": "application/pdf",
  ".mp4": "video/mp4", ".webm": "video/webm", ".m4a": "audio/mp4",
  ".ogg": "audio/ogg", ".mp3": "audio/mpeg", ".opus": "audio/opus",
};
app.get("/media", (req, res) => {
  const p = req.query.path;
  if (!p || typeof p !== "string") return res.status(400).send("missing path");
  const resolved = path.resolve(p);
  if (!resolved.startsWith(MEDIA_ROOT + "/")) return res.status(403).send("forbidden");
  if (!fs.existsSync(resolved)) return res.status(404).send("not found");
  const ext = path.extname(resolved).toLowerCase();
  const mime = MIME_BY_EXT[ext] || "application/octet-stream";
  res.setHeader("Content-Type", mime);
  res.setHeader("Cache-Control", "private, max-age=300");
  res.setHeader(
    "Content-Disposition",
    mime === "application/pdf" || mime.startsWith("image/") || mime.startsWith("video/") || mime.startsWith("audio/")
      ? "inline"
      : `inline; filename="${path.basename(resolved)}"`,
  );
  fs.createReadStream(resolved).pipe(res);
});

// Team avatar — serve disk file mapped by lowercased team name
app.get("/team-avatar/:name", (req, res) => {
  const name = String(req.params.name || "").toLowerCase().replace(/[^a-z0-9_-]/g, "");
  const member = TEAM.find((m) => m.name.toLowerCase() === name);
  if (!member) return res.status(404).send("no team");
  const file = TEAM_AVATAR_FILES[member.e164];
  if (!file || !fs.existsSync(file)) return res.status(404).send("no avatar");
  const ext = path.extname(file).toLowerCase();
  res.setHeader("Content-Type", MIME_BY_EXT[ext] || "image/png");
  res.setHeader("Cache-Control", "private, max-age=3600");
  fs.createReadStream(file).pipe(res);
});

// Client avatar — handles base64 data URIs + drive URLs + http URLs
app.get("/client-avatar/:id", async (req, res) => {
  const cid = parseInt(req.params.id, 10);
  if (!cid) return res.status(400).send("bad id");
  try {
    const r = await pool.query(`SELECT avatar_url FROM clients WHERE id = $1 AND deleted_at IS NULL`, [cid]);
    const a = r.rows[0]?.avatar_url;
    if (!a) return res.status(404).send("no avatar");
    if (a.startsWith("data:")) {
      const m = a.match(/^data:([^;]+);base64,(.+)$/);
      if (!m) return res.status(415).send("bad data uri");
      res.setHeader("Content-Type", m[1]);
      res.setHeader("Cache-Control", "private, max-age=3600");
      return res.end(Buffer.from(m[2], "base64"));
    }
    // Google Drive view URLs → not directly streamable, fallback redirect
    let parsedUrl = null;
    try { parsedUrl = new URL(a); } catch { /* not a URL */ }
    if (parsedUrl && parsedUrl.hostname === "drive.google.com") {
      const idMatch = parsedUrl.pathname.match(/\/d\/([a-zA-Z0-9_-]+)/);
      if (idMatch) {
        // Use thumbnail endpoint (works for public files)
        return res.redirect(`https://drive.google.com/thumbnail?id=${idMatch[1]}&sz=w200`);
      }
    }
    if (a.startsWith("http")) return res.redirect(a);
    res.status(415).send("unsupported");
  } catch (err) {
    console.error("[client-avatar]", err);
    res.status(500).send(err.message);
  }
});

// Refresh LID resolution map (cron-able): POST /lid-refresh
app.post("/lid-refresh", async (_req, res) => {
  try {
    await pool.query("REFRESH MATERIALIZED VIEW CONCURRENTLY wa_lid_phone_resolution");
    const r = await pool.query("SELECT COUNT(*) AS n FROM wa_lid_phone_resolution");
    CACHE.teams = { at: 0, payload: null };
    res.json({ ok: true, resolved_lids: parseInt(r.rows[0].n, 10) });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
});

app.get("/lid-stats", async (_req, res) => {
  try {
    const r = await pool.query(`
      SELECT
        (SELECT COUNT(*) FROM wa_lid_phone_resolution) AS resolved_total,
        (SELECT COUNT(DISTINCT counterpart_lid) FROM whatsapp_message_context
         WHERE counterpart_lid IS NOT NULL AND counterpart_phone IS NULL) AS total_lid_only,
        (SELECT computed_at FROM wa_lid_phone_resolution ORDER BY computed_at DESC LIMIT 1) AS computed_at
    `);
    res.json(r.rows[0]);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// === Team Quality Metrics (quality tab) ===
// Live aggregate metrics per operator. Attribution by team_member_phone + aliases
// (parity with fetchOverview). Aggregate-only output — no PII leaves the box.
app.get("/metrics.json", async (req, res) => {
  try {
    const windowDays = parseInt(req.query.window, 10) || 30;
    const payload = await metrics.fetchLiveMetrics(pool, TEAM, aliasesForTeamMember, HIDE_TEAM_NAMES, windowDays);
    res.json(payload);
  } catch (err) {
    console.error("[metrics.json]", err);
    res.status(500).json({ error: err.message });
  }
});

// Historical rollup trend (sparklines / delta vs prior period).
app.get("/metrics-history.json", async (req, res) => {
  try {
    const days = parseInt(req.query.days, 10) || 90;
    const payload = await metrics.fetchHistory(pool, { days });
    res.json(payload);
  } catch (err) {
    console.error("[metrics-history.json]", err);
    res.status(500).json({ error: err.message });
  }
});

// Compute + persist today's snapshot (scheduled daily; idempotent UPSERT per day).
// Heartbeat: returns rows_written + computed_at so the scheduler proves real liveness.
app.post("/metrics-rollup", async (req, res) => {
  try {
    const windowDays = parseInt(req.query.window, 10) || 30;
    const result = await metrics.computeAndStoreRollup(pool, TEAM, aliasesForTeamMember, HIDE_TEAM_NAMES, windowDays);
    res.json(result);
  } catch (err) {
    console.error("[metrics-rollup]", err);
    res.status(500).json({ ok: false, error: err.message });
  }
});

app.get("/", (_req, res) => {
  res.sendFile(path.join(__dirname, "viewer.html"));
});

app.listen(PORT, HOST, () => {
  console.log(`[wa-dashboard-m1] listening on http://${HOST}:${PORT}`);
  console.log(`[wa-dashboard-m1] DB: ${DATABASE_URL.replace(/:[^@]+@/, ":***@")}`);
  console.log(`[wa-dashboard-m1] Team size: ${TEAM.length} | Media root: ${MEDIA_ROOT}`);
  // Ensure the team-quality rollup table exists (idempotent, local DB).
  metrics.ensureMetricsSchema(pool)
    .then(() => console.log("[wa-dashboard-m1] wa_team_daily_metrics schema ready"))
    .catch((err) => console.error("[wa-dashboard-m1] metrics schema init failed:", err.message));
});
