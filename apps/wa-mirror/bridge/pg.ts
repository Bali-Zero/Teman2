// pg.ts — thin asyncpg-equivalent wrapper for wa-mirror.
// Uses node-postgres `pg` driver. Single shared pool across the daemon
// because each Baileys session writes a small amount of data (one row per
// message + one heartbeat update per minute), well below pool saturation.

import pg from "pg";
import type { PoolConfig, QueryResult } from "pg";

let _pool: pg.Pool | null = null;

export function getPool(): pg.Pool {
  if (_pool !== null) return _pool;
  const connectionString = process.env.WA_MIRROR_DATABASE_URL ?? process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error(
      "wa-mirror: WA_MIRROR_DATABASE_URL or DATABASE_URL must be set."
    );
  }
  const config: PoolConfig = {
    connectionString,
    max: Number(process.env.WA_MIRROR_PG_MAX_CONN ?? 5),
    idleTimeoutMillis: 30_000,
    connectionTimeoutMillis: 5_000,
    application_name: "wa-mirror",
  };
  _pool = new pg.Pool(config);
  _pool.on("error", (err) => {
    // node-postgres emits idle client errors; never crash the daemon.
    // eslint-disable-next-line no-console
    console.error("[wa-mirror.pg] idle client error:", err.message);
  });
  return _pool;
}

export async function query<T extends pg.QueryResultRow = pg.QueryResultRow>(
  sql: string,
  params: unknown[] = []
): Promise<QueryResult<T>> {
  const pool = getPool();
  return pool.query<T>(sql, params);
}

export async function closePool(): Promise<void> {
  if (_pool !== null) {
    const pool = _pool;
    _pool = null;
    await pool.end();
  }
}

/**
 * Look up a client by their WhatsApp phone number (any common format).
 * Returns the client id if found, null otherwise.
 *
 * The clients table maintains `phone_normalized` as the canonical form;
 * we also fall back to `whatsapp` and raw `phone` for safety. All
 * comparisons strip non-digits before matching.
 */
export async function findClientByPhone(
  phoneRaw: string
): Promise<number | null> {
  const normalized = phoneRaw.replace(/[^\d]/g, "");
  if (normalized.length < 8) return null;
  // Match strategies (most → least specific):
  //   1. exact phone_normalized
  //   2. exact whatsapp (digit-stripped)
  //   3. exact phone (digit-stripped)
  // Indonesian numbers may be stored as 0812..., 62812..., or +62812...
  // The digit-stripped form removes the ambiguity.
  const sql = `
    SELECT id FROM clients
    WHERE regexp_replace(COALESCE(phone_normalized, ''), '\\D', '', 'g') = $1
       OR regexp_replace(COALESCE(whatsapp, ''),         '\\D', '', 'g') = $1
       OR regexp_replace(COALESCE(phone, ''),            '\\D', '', 'g') = $1
    LIMIT 1
  `;
  const res = await query<{ id: number }>(sql, [normalized]);
  return res.rowCount && res.rowCount > 0 ? res.rows[0].id : null;
}
