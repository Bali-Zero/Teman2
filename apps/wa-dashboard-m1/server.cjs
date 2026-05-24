#!/usr/bin/env node
"use strict";

const express = require("express");
const { Pool } = require("pg");
const fs = require("fs");
const path = require("path");

const PORT = parseInt(process.env.PORT || "7790", 10);
const HOST = process.env.HOST || "127.0.0.1";

const DATABASE_URL =
  process.env.WA_DASHBOARD_DATABASE_URL ||
  process.env.DATABASE_URL ||
  "postgres://backend_rag_v2:1w32Hrm33npis9rncTVjye3hPEwaVta@127.0.0.1:15432/nuzantara_rag?sslmode=disable";

const ACCOUNTS_JSON =
  process.env.WA_MIRROR_ACCOUNTS_JSON ||
  path.join(process.env.HOME || "/", ".wa-mirror.accounts.json");

const TEAM = (() => {
  try {
    return JSON.parse(fs.readFileSync(ACCOUNTS_JSON, "utf8")).accounts || [];
  } catch (err) {
    console.error(`[wa-dashboard-m1] cannot read ${ACCOUNTS_JSON}: ${err.message}`);
    return [];
  }
})();

const TEAM_PHONES = new Set();
for (const m of TEAM) {
  if (m.e164) TEAM_PHONES.add(m.e164);
}

const pool = new Pool({ connectionString: DATABASE_URL, max: 4, idleTimeoutMillis: 30000 });
pool.on("error", (err) => console.error("[pg-pool-error]", err.message));

const CACHE = { teams: { at: 0, payload: null } };
const CACHE_MS = 5000;

function aliasesForTeamMember(member) {
  const aliases = new Set();
  if (member.e164) {
    aliases.add(member.e164);
    if (member.e164.startsWith("+62821345472")) {
      const suffix = member.e164.slice("+62821345472".length);
      aliases.add(`+628213454772${suffix}`);
      aliases.add(`+6282134547${suffix}`);
    }
  }
  return [...aliases];
}

function isTeamPhone(phone) {
  return !!phone && TEAM_PHONES.has(phone);
}

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
  }));

  for (const member of result.team) {
    const aliases = member.aliases;
    const since = "30 days";

    // Direct conversations
    const directRows = await pool.query(
      `
      WITH base AS (
        SELECT
          NULLIF(counterpart_phone, '') AS direct_phone,
          NULLIF(counterpart_lid, '') AS lid,
          body, media_type, message_date, raw_baileys_event, direction, client_id
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
               MAX(client_id) AS client_id,
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
      SELECT g.conv_key, g.direct_phone, g.client_id, g.n, g.last_at,
             lm.last_body, lm.last_media, lp.pushname,
             cli.full_name AS client_name, cli.company_name, cli.status AS client_status
      FROM grouped g
      LEFT JOIN last_msg lm USING (conv_key)
      LEFT JOIN last_push lp USING (conv_key)
      LEFT JOIN clients cli ON cli.id = g.client_id
      ORDER BY g.last_at DESC NULLS LAST
      LIMIT 200;
      `,
      [aliases],
    );

    // Group conversations
    const groupRows = await pool.query(
      `
      WITH grouped AS (
        SELECT group_jid,
               COALESCE(NULLIF(group_subject_snapshot, ''), group_jid) AS group_label,
               COUNT(*) AS n,
               MAX(message_date) AS last_at
        FROM whatsapp_message_context
        WHERE team_member_phone = ANY($1::text[])
          AND chat_type = 'group'
          AND group_jid IS NOT NULL
          AND message_date >= NOW() - INTERVAL '${since}'
        GROUP BY group_jid, group_subject_snapshot
      ),
      last_msg AS (
        SELECT DISTINCT ON (group_jid)
               group_jid, body AS last_body, media_type AS last_media, sender_phone
        FROM whatsapp_message_context
        WHERE team_member_phone = ANY($1::text[])
          AND chat_type = 'group'
          AND group_jid IS NOT NULL
        ORDER BY group_jid, message_date DESC NULLS LAST
      )
      SELECT g.group_jid, g.group_label, g.n, g.last_at,
             lm.last_body, lm.last_media, lm.sender_phone
      FROM grouped g
      LEFT JOIN last_msg lm USING (group_jid)
      ORDER BY g.last_at DESC NULLS LAST
      LIMIT 200;
      `,
      [aliases],
    );

    const convs = [];
    for (const r of directRows.rows) {
      convs.push({
        kind: "direct",
        counterpart: r.direct_phone || r.conv_key,
        display_name: r.client_name || r.pushname || r.direct_phone || r.conv_key,
        client_id: r.client_id,
        client_status: r.client_status,
        company_name: r.company_name,
        n: parseInt(r.n, 10),
        last_at: r.last_at,
        last_body: r.last_body,
        last_media: r.last_media,
        is_internal: isTeamPhone(r.direct_phone),
      });
    }
    for (const r of groupRows.rows) {
      convs.push({
        kind: "group",
        counterpart: `group:${r.group_jid}`,
        display_name: r.group_label,
        group_jid: r.group_jid,
        sender_phone: r.sender_phone,
        n: parseInt(r.n, 10),
        last_at: r.last_at,
        last_body: r.last_body,
        last_media: r.last_media,
        is_internal: false,
      });
    }
    convs.sort((a, b) => new Date(b.last_at) - new Date(a.last_at));

    result.by_phone[member.phone] = {
      team: member,
      total: convs.reduce((acc, c) => acc + c.n, 0),
      direct_count: convs.filter((c) => c.kind === "direct").length,
      group_count: convs.filter((c) => c.kind === "group").length,
      convs,
    };
  }

  CACHE.teams = { at: Date.now(), payload: result };
  return result;
}

async function fetchThread(memberPhone, convKey) {
  const member = TEAM.find((m) => m.e164 === memberPhone);
  if (!member) throw new Error(`team member not found: ${memberPhone}`);
  const aliases = aliasesForTeamMember(member);

  let where = "";
  let params = [aliases];
  if (convKey.startsWith("group:")) {
    where = `AND chat_type = 'group' AND group_jid = $2`;
    params.push(convKey.slice("group:".length));
  } else if (convKey.startsWith("lid:")) {
    where = `AND counterpart_lid = $2`;
    params.push(convKey.slice("lid:".length));
  } else {
    where = `AND counterpart_phone = $2`;
    params.push(convKey);
  }

  const rows = await pool.query(
    `
    SELECT id, direction, body, media_type, media_mime, message_date,
           sender_phone, sender_push_name_snapshot, group_jid,
           raw_baileys_event->>'pushName' AS pushname
    FROM whatsapp_message_context
    WHERE team_member_phone = ANY($1::text[])
      ${where}
      AND message_date >= NOW() - INTERVAL '30 days'
      AND (
        COALESCE(length(body),0) > 0
        OR media_type IN ('image','document','video','audio','sticker')
      )
    ORDER BY message_date ASC, id ASC
    LIMIT 500;
    `,
    params,
  );
  return rows.rows;
}

const app = express();
app.disable("x-powered-by");

app.use((req, res, next) => {
  res.setHeader("Cache-Control", "no-store");
  next();
});

app.get("/health.json", async (_req, res) => {
  try {
    const r = await pool.query("SELECT 1 AS ok, NOW() AS now");
    res.json({ ok: true, db_now: r.rows[0].now, team_size: TEAM.length, db_url_host: new URL(DATABASE_URL.replace(/^postgres/, "http")).host });
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

app.get("/", (_req, res) => {
  res.sendFile(path.join(__dirname, "viewer.html"));
});

app.listen(PORT, HOST, () => {
  console.log(`[wa-dashboard-m1] listening on http://${HOST}:${PORT}`);
  console.log(`[wa-dashboard-m1] DB: ${DATABASE_URL.replace(/:[^@]+@/, ":***@")}`);
  console.log(`[wa-dashboard-m1] Team size: ${TEAM.length}`);
});
