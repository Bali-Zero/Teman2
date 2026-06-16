"use strict";

// wa-dashboard-m1 — Team Quality Metrics module
// ------------------------------------------------------------------
// Pro-bound: reads/writes ONLY the local nuzantara_dev Postgres (same pool
// as server.cjs). No PII leaves the box — output is aggregate counts/latencies.
//
// Attribution key = team_member_phone + aliasesForTeamMember() (parity with
// fetchOverview in server.cjs), NOT team_member_email. Using email would
// produce numbers that do not reconcile with the conversations columns.
//
// Schema versioning (metrics_schema_version) guards trend comparability:
// when a metric formula changes (e.g. backlog 55%→25% rewrite), bump the
// version so history queries compare only same-version rows. (cicatrix #9
// state-schema drift.)
// ------------------------------------------------------------------

const METRICS_SCHEMA_VERSION = 1;
const DEFAULT_WINDOW_DAYS = 30;
const LIVE_CACHE_MS = 60_000; // metrics move slowly; protect the DB

// in-module cache keyed by windowDays
const LIVE_CACHE = new Map();

function intOr(v, fallback) {
  const n = parseInt(v, 10);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

async function ensureMetricsSchema(pool) {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS wa_team_daily_metrics (
      id                     BIGSERIAL PRIMARY KEY,
      snapshot_date          DATE        NOT NULL,
      metrics_schema_version INTEGER     NOT NULL,
      team_member_phone      TEXT        NOT NULL,
      team_member_name       TEXT,
      window_days            INTEGER     NOT NULL DEFAULT 30,
      msgs_total             INTEGER     NOT NULL DEFAULT 0,
      msgs_in                INTEGER     NOT NULL DEFAULT 0,
      msgs_out               INTEGER     NOT NULL DEFAULT 0,
      clients                INTEGER     NOT NULL DEFAULT 0,
      active_days            INTEGER     NOT NULL DEFAULT 0,
      avg_out_chars          INTEGER,
      pct_afterhours         NUMERIC(5,1),
      resp_median_min        NUMERIC(8,1),
      resp_p90_min           NUMERIC(8,1),
      pct_under5min          NUMERIC(5,1),
      n_replies              INTEGER     NOT NULL DEFAULT 0,
      backlog_threads        INTEGER     NOT NULL DEFAULT 0,
      backlog_ball_team      INTEGER     NOT NULL DEFAULT 0,
      backlog_stale24h       INTEGER     NOT NULL DEFAULT 0,
      grp_msgs               INTEGER     NOT NULL DEFAULT 0,
      computed_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE (snapshot_date, metrics_schema_version, team_member_phone)
    );
    CREATE INDEX IF NOT EXISTS idx_wa_team_daily_metrics_lookup
      ON wa_team_daily_metrics (team_member_phone, snapshot_date DESC);
  `);
}

// --- Per-member aggregation (3 parallel queries; member fixed → partition by counterpart) ---
async function aggregateForMember(pool, aliases, windowDays) {
  const since = `${intOr(windowDays, DEFAULT_WINDOW_DAYS)} days`;

  const [volRow, respRow, backlogRow, grpRow] = await Promise.all([
    // (A) volume / coverage / length / after-hours — DIRECT chats
    pool.query(
      `
      WITH base AS (
        SELECT direction, message_date,
               COALESCE(NULLIF(body,''), NULLIF(message_text,'')) AS txt,
               counterpart_phone AS cp
        FROM whatsapp_message_context
        WHERE team_member_phone = ANY($1::text[])
          AND chat_type = 'direct'
          AND message_date >= NOW() - INTERVAL '${since}'
      )
      SELECT
        count(*)                                              AS msgs_total,
        count(*) FILTER (WHERE direction='inbound')           AS msgs_in,
        count(*) FILTER (WHERE direction='outbound')          AS msgs_out,
        count(DISTINCT cp) FILTER (WHERE cp IS NOT NULL)      AS clients,
        count(DISTINCT (message_date AT TIME ZONE 'Asia/Makassar')::date) AS active_days,
        round(avg(length(txt)) FILTER (WHERE direction='outbound'))::int  AS avg_out_chars,
        round(100.0 * count(*) FILTER (WHERE direction='outbound'
              AND (EXTRACT(HOUR FROM message_date AT TIME ZONE 'Asia/Makassar') < 8
                OR EXTRACT(HOUR FROM message_date AT TIME ZONE 'Asia/Makassar') >= 18))
              / NULLIF(count(*) FILTER (WHERE direction='outbound'),0), 1) AS pct_afterhours
      FROM base
      `,
      [aliases],
    ),
    // (B) response latency — outbound after client inbound, same thread, 0..12h
    pool.query(
      `
      WITH base AS (
        SELECT counterpart_phone AS cp, direction, message_date
        FROM whatsapp_message_context
        WHERE team_member_phone = ANY($1::text[])
          AND chat_type = 'direct'
          AND message_date >= NOW() - INTERVAL '${since}'
      ),
      seq AS (
        SELECT cp, direction, message_date,
               LAG(direction)    OVER w AS prev_dir,
               LAG(message_date) OVER w AS prev_ts
        FROM base WINDOW w AS (PARTITION BY cp ORDER BY message_date)
      ),
      resp AS (
        SELECT EXTRACT(EPOCH FROM (message_date - prev_ts)) AS lat_s
        FROM seq
        WHERE direction='outbound' AND prev_dir='inbound'
          AND (message_date - prev_ts) BETWEEN INTERVAL '0 second' AND INTERVAL '12 hours'
      )
      SELECT
        count(*)                                                        AS n_replies,
        round((percentile_cont(0.5) WITHIN GROUP (ORDER BY lat_s)/60)::numeric, 1) AS resp_median_min,
        round((percentile_cont(0.9) WITHIN GROUP (ORDER BY lat_s)/60)::numeric, 1) AS resp_p90_min,
        round(100.0 * count(*) FILTER (WHERE lat_s <= 300)
              / NULLIF(count(*),0), 1)                                  AS pct_under5min
      FROM resp
      `,
      [aliases],
    ),
    // (C) backlog — last message in a direct thread is INBOUND (ball with team); stale >24h
    pool.query(
      `
      WITH base AS (
        SELECT counterpart_phone AS cp, direction, message_date
        FROM whatsapp_message_context
        WHERE team_member_phone = ANY($1::text[])
          AND chat_type = 'direct'
          AND counterpart_phone IS NOT NULL AND counterpart_phone <> ''
          AND message_date >= NOW() - INTERVAL '${since}'
      ),
      last_per_thread AS (
        SELECT DISTINCT ON (cp) cp, direction, message_date
        FROM base
        ORDER BY cp, message_date DESC
      )
      SELECT
        count(*)                                                       AS backlog_threads,
        count(*) FILTER (WHERE direction='inbound')                    AS backlog_ball_team,
        count(*) FILTER (WHERE direction='inbound'
              AND message_date < NOW() - INTERVAL '24 hours')          AS backlog_stale24h
      FROM last_per_thread
      `,
      [aliases],
    ),
    // (D) group-chat volume
    pool.query(
      `
      SELECT count(*) AS grp_msgs
      FROM whatsapp_message_context
      WHERE team_member_phone = ANY($1::text[])
        AND chat_type = 'group'
        AND message_date >= NOW() - INTERVAL '${since}'
      `,
      [aliases],
    ),
  ]);

  const v = volRow.rows[0] || {};
  const r = respRow.rows[0] || {};
  const b = backlogRow.rows[0] || {};
  const g = grpRow.rows[0] || {};

  const numOrNull = (x) => (x === null || x === undefined ? null : Number(x));
  const intVal = (x) => parseInt(x || 0, 10);

  return {
    msgs_total: intVal(v.msgs_total),
    msgs_in: intVal(v.msgs_in),
    msgs_out: intVal(v.msgs_out),
    clients: intVal(v.clients),
    active_days: intVal(v.active_days),
    avg_out_chars: v.avg_out_chars === null ? null : intVal(v.avg_out_chars),
    pct_afterhours: numOrNull(v.pct_afterhours),
    n_replies: intVal(r.n_replies),
    resp_median_min: numOrNull(r.resp_median_min),
    resp_p90_min: numOrNull(r.resp_p90_min),
    pct_under5min: numOrNull(r.pct_under5min),
    backlog_threads: intVal(b.backlog_threads),
    backlog_ball_team: intVal(b.backlog_ball_team),
    backlog_stale24h: intVal(b.backlog_stale24h),
    grp_msgs: intVal(g.grp_msgs),
  };
}

// --- Live metrics for the whole team (cached) ---
// team: array of {name, e164, ...}; aliasesFor: (member)=>string[]; hideNames: Set<string>
async function fetchLiveMetrics(pool, team, aliasesFor, hideNames, windowDays) {
  const wd = intOr(windowDays, DEFAULT_WINDOW_DAYS);
  const cacheKey = `w${wd}`;
  const cached = LIVE_CACHE.get(cacheKey);
  if (cached && Date.now() - cached.at < LIVE_CACHE_MS) return cached.payload;

  const members = team.filter((m) => m && m.e164 && !(hideNames && hideNames.has(m.name)));
  const rows = await Promise.all(
    members.map(async (m) => {
      const agg = await aggregateForMember(pool, aliasesFor(m), wd);
      return {
        team_member_phone: m.e164,
        team_member_name: m.full_name || m.name,
        ...agg,
      };
    }),
  );
  // rank by total volume desc (stable, informative for triage)
  rows.sort((a, b) => b.msgs_total - a.msgs_total);

  const payload = {
    generated_at: new Date().toISOString(),
    metrics_schema_version: METRICS_SCHEMA_VERSION,
    window_days: wd,
    operators: rows,
  };
  LIVE_CACHE.set(cacheKey, { at: Date.now(), payload });
  return payload;
}

// --- Compute today's snapshot and UPSERT into the rollup table (heartbeat) ---
async function computeAndStoreRollup(pool, team, aliasesFor, hideNames, windowDays) {
  const wd = intOr(windowDays, DEFAULT_WINDOW_DAYS);
  // bypass cache for the authoritative nightly snapshot
  LIVE_CACHE.delete(`w${wd}`);
  const live = await fetchLiveMetrics(pool, team, aliasesFor, hideNames, wd);

  let written = 0;
  for (const op of live.operators) {
    await pool.query(
      `
      INSERT INTO wa_team_daily_metrics
        (snapshot_date, metrics_schema_version, team_member_phone, team_member_name,
         window_days, msgs_total, msgs_in, msgs_out, clients, active_days, avg_out_chars,
         pct_afterhours, resp_median_min, resp_p90_min, pct_under5min, n_replies,
         backlog_threads, backlog_ball_team, backlog_stale24h, grp_msgs, computed_at)
      VALUES
        ((NOW() AT TIME ZONE 'Asia/Makassar')::date, $1, $2, $3,
         $4, $5, $6, $7, $8, $9, $10,
         $11, $12, $13, $14, $15,
         $16, $17, $18, $19, NOW())
      ON CONFLICT (snapshot_date, metrics_schema_version, team_member_phone)
      DO UPDATE SET
        team_member_name = EXCLUDED.team_member_name,
        window_days      = EXCLUDED.window_days,
        msgs_total       = EXCLUDED.msgs_total,
        msgs_in          = EXCLUDED.msgs_in,
        msgs_out         = EXCLUDED.msgs_out,
        clients          = EXCLUDED.clients,
        active_days      = EXCLUDED.active_days,
        avg_out_chars    = EXCLUDED.avg_out_chars,
        pct_afterhours   = EXCLUDED.pct_afterhours,
        resp_median_min  = EXCLUDED.resp_median_min,
        resp_p90_min     = EXCLUDED.resp_p90_min,
        pct_under5min    = EXCLUDED.pct_under5min,
        n_replies        = EXCLUDED.n_replies,
        backlog_threads  = EXCLUDED.backlog_threads,
        backlog_ball_team= EXCLUDED.backlog_ball_team,
        backlog_stale24h = EXCLUDED.backlog_stale24h,
        grp_msgs         = EXCLUDED.grp_msgs,
        computed_at      = NOW()
      `,
      [
        METRICS_SCHEMA_VERSION, op.team_member_phone, op.team_member_name,
        wd, op.msgs_total, op.msgs_in, op.msgs_out, op.clients, op.active_days, op.avg_out_chars,
        op.pct_afterhours, op.resp_median_min, op.resp_p90_min, op.pct_under5min, op.n_replies,
        op.backlog_threads, op.backlog_ball_team, op.backlog_stale24h, op.grp_msgs,
      ],
    );
    written += 1;
  }

  return {
    ok: true,
    snapshot_date: live.generated_at.slice(0, 10),
    metrics_schema_version: METRICS_SCHEMA_VERSION,
    window_days: wd,
    rows_written: written,
    computed_at: new Date().toISOString(),
  };
}

// --- Historical trend (for sparklines / delta vs prior period) ---
async function fetchHistory(pool, { days = 90, schemaVersion = METRICS_SCHEMA_VERSION } = {}) {
  const r = await pool.query(
    `
    SELECT snapshot_date, team_member_phone, team_member_name,
           msgs_total, msgs_in, msgs_out, clients, active_days, avg_out_chars,
           pct_afterhours, resp_median_min, resp_p90_min, pct_under5min, n_replies,
           backlog_threads, backlog_ball_team, backlog_stale24h, grp_msgs, computed_at
    FROM wa_team_daily_metrics
    WHERE metrics_schema_version = $1
      AND snapshot_date >= ((NOW() AT TIME ZONE 'Asia/Makassar')::date - ($2::int))
    ORDER BY snapshot_date ASC, team_member_phone ASC
    `,
    [schemaVersion, intOr(days, 90)],
  );
  return {
    metrics_schema_version: schemaVersion,
    days: intOr(days, 90),
    rows: r.rows,
  };
}

module.exports = {
  METRICS_SCHEMA_VERSION,
  ensureMetricsSchema,
  fetchLiveMetrics,
  computeAndStoreRollup,
  fetchHistory,
};
