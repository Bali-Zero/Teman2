#!/usr/bin/env node
"use strict";

const express = require("express");
const { Pool } = require("pg");
const fs = require("fs");
const path = require("path");

const PORT = parseInt(process.env.PORT || "7790", 10);
const HOST = process.env.HOST || "0.0.0.0"; // bind also Tailnet (parity with wa-viewer:7777)

const DATABASE_URL =
  process.env.WA_DASHBOARD_DATABASE_URL ||
  process.env.DATABASE_URL ||
  "postgres://backend_rag_v2:1w32Hrm33npis9rncTVjye3hPEwaVta@127.0.0.1:15432/nuzantara_rag?sslmode=disable";

const ACCOUNTS_JSON =
  process.env.WA_MIRROR_ACCOUNTS_JSON ||
  path.join(process.env.HOME || "/", ".wa-mirror.accounts.json");

const MEDIA_ROOT = process.env.WA_MIRROR_MEDIA_ROOT || "/Users/nuzantara/wa-mirror-media";
const TEAM_AVATAR_DIR = process.env.WA_TEAM_AVATAR_DIR || "/Users/nuzantara/Desktop/nuzantara/apps/mouth/public/static/team";

const TEAM = (() => {
  try {
    return JSON.parse(fs.readFileSync(ACCOUNTS_JSON, "utf8")).accounts || [];
  } catch (err) {
    console.error(`[wa-dashboard-m1] cannot read ${ACCOUNTS_JSON}: ${err.message}`);
    return [];
  }
})();

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
function cleanName(name) {
  if (!name) return null;
  const s = String(name).trim();
  if (!s) return null;
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
  result.team = TEAM.map((m) => ({
    name: m.name,
    phone: m.e164,
    label: m.label || "BZ",
    role: m.role || "team",
    aliases: aliasesForTeamMember(m),
    avatar_url: TEAM_AVATAR_FILES[m.e164] ? `/team-avatar/${encodeURIComponent(m.name.toLowerCase())}` : null,
  }));

  for (const member of result.team) {
    const aliases = member.aliases;
    const since = "30 days";

    const [directRows, groupRows, sessionInfo] = await Promise.all([
      pool.query(
        `
      WITH base AS (
        SELECT
          NULLIF(counterpart_phone, '') AS direct_phone,
          NULLIF(counterpart_lid, '') AS lid,
          body, media_type, message_date, raw_baileys_event, direction, client_id,
          attention_priority, attention_resolved_at
        FROM whatsapp_message_context
        WHERE team_member_phone = ANY($1::text[])
          AND chat_type = 'direct'
          AND message_date >= NOW() - INTERVAL '${since}'
          AND (
            (counterpart_phone IS NOT NULL AND counterpart_phone <> '')
            OR (counterpart_lid IS NOT NULL AND counterpart_lid <> '')
          )
          AND (
            COALESCE(length(body),0) > 0
            OR media_type IN ('image','document','video','audio','sticker')
          )
      ),
      keyed AS (
        SELECT base.*,
               COALESCE(direct_phone, 'lid:' || lid) AS conv_key
        FROM base
      ),
      grouped AS (
        SELECT conv_key,
               MAX(direct_phone) AS direct_phone,
               MAX(lid) AS lid,
               MAX(client_id) AS client_id,
               MAX(attention_priority) FILTER (WHERE attention_resolved_at IS NULL) AS attention_priority,
               COUNT(*) AS n,
               MAX(message_date) AS last_at
        FROM keyed
        GROUP BY conv_key
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
      SELECT g.conv_key, g.direct_phone, g.lid, g.client_id, g.n, g.last_at,
             g.attention_priority,
             lm.last_body, lm.last_media, lp.pushname,
             COALESCE(cli_id.full_name, cli_phone.full_name) AS client_name,
             COALESCE(cli_id.company_name, cli_phone.company_name) AS company_name,
             COALESCE(cli_id.status, cli_phone.status) AS client_status,
             COALESCE(cli_id.id, cli_phone.id) AS resolved_client_id,
             COALESCE(cli_id.assigned_to, cli_phone.assigned_to) AS assigned_to,
             COALESCE(cli_id.tax_consultant, cli_phone.tax_consultant) AS tax_consultant,
             COALESCE(cli_id.strategic_recap, cli_phone.strategic_recap) AS strategic_recap,
             COALESCE(cli_id.strategic_recap_source, cli_phone.strategic_recap_source) AS strategic_recap_source,
             COALESCE(cli_id.avatar_url, cli_phone.avatar_url) AS avatar_url,
             wc.name AS wa_contact_name,
             wc.business_name AS wa_business_name
      FROM grouped g
      LEFT JOIN last_msg lm USING (conv_key)
      LEFT JOIN last_push lp USING (conv_key)
      LEFT JOIN clients cli_id
        ON cli_id.id = g.client_id AND cli_id.deleted_at IS NULL
      LEFT JOIN clients cli_phone
        ON cli_phone.deleted_at IS NULL
       AND g.direct_phone IS NOT NULL
       AND (
         cli_phone.phone_normalized = regexp_replace(g.direct_phone, '\\D', '', 'g')
         OR cli_phone.phone = g.direct_phone
         OR cli_phone.whatsapp = g.direct_phone
       )
      LEFT JOIN whatsapp_contacts wc
        ON g.direct_phone IS NOT NULL
       AND wc.phone_normalized = regexp_replace(g.direct_phone, '\\D', '', 'g')
      ORDER BY g.last_at DESC NULLS LAST
      LIMIT 200;
      `,
        [aliases],
      ),
      pool.query(
        `
      WITH grouped AS (
        SELECT group_jid,
               COALESCE(NULLIF(group_subject_snapshot, ''), group_jid) AS group_label,
               COUNT(*) AS n,
               MAX(message_date) AS last_at,
               MAX(attention_priority) FILTER (WHERE attention_resolved_at IS NULL) AS attention_priority
        FROM whatsapp_message_context
        WHERE team_member_phone = ANY($1::text[])
          AND chat_type = 'group'
          AND group_jid IS NOT NULL
          AND message_date >= NOW() - INTERVAL '${since}'
        GROUP BY group_jid, group_subject_snapshot
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
      SELECT g.group_jid, g.group_label, g.n, g.last_at, g.attention_priority,
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
      // Display name with priority: CRM > WA business > WA contact > pushName > phone
      const crmName = cleanName(r.client_name);
      const businessName = cleanName(r.wa_business_name);
      const waName = cleanName(r.wa_contact_name);
      const push = cleanName(r.pushname);

      let display = crmName;
      if (display && r.company_name) display = `${crmName} · ${r.company_name}`;
      if (!display) display = businessName || waName || push || r.direct_phone || r.conv_key;
      const isInternal = isTeamPhone(r.direct_phone);
      const isLid = !r.direct_phone && r.lid;
      let tag;
      if (isInternal) { tag = "internal"; internalCount++; }
      else if (crmName) { tag = "crm"; crmMatched++; }
      else if (push || waName || businessName) tag = "prospect";
      else if (isLid) { tag = "lid"; unresolvedLids++; }
      else tag = "unknown";

      if (r.attention_priority === "HIGH") attentionHigh++;
      else if (r.attention_priority === "MEDIUM") attentionMedium++;

      convs.push({
        kind: "direct",
        counterpart: r.direct_phone || r.conv_key,
        display_name: display,
        crm_match: !!crmName,
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
        last_at: r.last_at,
        last_body: r.last_body,
        last_media: r.last_media,
        is_internal: isInternal,
        is_legacy_lid: !!isLid,
        tag,
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
        last_at: r.last_at,
        last_body: r.last_body,
        last_media: r.last_media,
        is_internal: false,
        tag: "group",
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
      attention: { high: attentionHigh, medium: attentionMedium }, // Feature #7
      convs,
    };
  }

  CACHE.teams = { at: Date.now(), payload: result };
  return result;
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
    where = `AND m.counterpart_phone = $2`;
    params.push(convKey);
  }

  const rows = await pool.query(
    `
    SELECT m.id, m.direction, m.body, m.media_type, m.media_mime, m.media_url,
           m.media_stored_path, m.message_date,
           m.sender_phone, m.sender_push_name_snapshot, m.group_jid,
           m.counterpart_phone, m.counterpart_lid,
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
    LEFT JOIN clients cli_s
      ON cli_s.deleted_at IS NULL
     AND m.sender_phone IS NOT NULL
     AND (
       cli_s.phone_normalized = regexp_replace(m.sender_phone, '\\D', '', 'g')
       OR cli_s.phone = m.sender_phone
       OR cli_s.whatsapp = m.sender_phone
     )
    LEFT JOIN clients cli_c
      ON cli_c.deleted_at IS NULL
     AND m.counterpart_phone IS NOT NULL
     AND (
       cli_c.phone_normalized = regexp_replace(m.counterpart_phone, '\\D', '', 'g')
       OR cli_c.phone = m.counterpart_phone
       OR cli_c.whatsapp = m.counterpart_phone
     )
    LEFT JOIN whatsapp_contacts wc_s
      ON m.sender_phone IS NOT NULL
     AND wc_s.phone_normalized = regexp_replace(m.sender_phone, '\\D', '', 'g')
    LEFT JOIN whatsapp_contacts wc_c
      ON m.counterpart_phone IS NOT NULL
     AND wc_c.phone_normalized = regexp_replace(m.counterpart_phone, '\\D', '', 'g')
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
  return rows.rows.map((r) => ({
    ...r,
    sender_display:
      cleanName(r.sender_crm_name) ||
      cleanName(r.sender_wa_business_name) ||
      cleanName(r.sender_wa_contact_name) ||
      cleanName(r.pushname) ||
      r.sender_phone,
  }));
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

app.get("/thread.json", async (req, res) => {
  const memberPhone = req.query.member;
  const convKey = req.query.conv;
  if (!memberPhone || !convKey) {
    return res.status(400).json({ error: "missing member or conv" });
  }
  try {
    const rows = await fetchThread(memberPhone, convKey);
    res.json({ member: memberPhone, conv: convKey, count: rows.length, messages: rows });
  } catch (err) {
    console.error("[thread.json]", err);
    res.status(500).json({ error: err.message });
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
    if (a.includes("drive.google.com")) {
      const idMatch = a.match(/\/d\/([a-zA-Z0-9_-]+)/);
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

app.get("/", (_req, res) => {
  res.sendFile(path.join(__dirname, "viewer.html"));
});

app.listen(PORT, HOST, () => {
  console.log(`[wa-dashboard-m1] listening on http://${HOST}:${PORT}`);
  console.log(`[wa-dashboard-m1] DB: ${DATABASE_URL.replace(/:[^@]+@/, ":***@")}`);
  console.log(`[wa-dashboard-m1] Team size: ${TEAM.length} | Media root: ${MEDIA_ROOT}`);
});
