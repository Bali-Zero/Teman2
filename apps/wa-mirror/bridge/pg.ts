// pg.ts — thin Postgres wrapper for wa-mirror.
// Uses node-postgres `pg` driver. Single shared pool across the daemon
// because each Baileys session writes a small amount of data (one row per
// message + one heartbeat update per minute), well below pool saturation.

import pg from "pg";
import type { PoolConfig, QueryResult } from "pg";

import { normalizePhone, phoneSearchVariants } from "./phone.js";

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
  const variants = phoneSearchVariants(phoneRaw);
  if (variants.length === 0) return null;
  // Match strategies (most → least specific):
  //   1. exact phone_normalized
  //   2. exact whatsapp (digit-stripped)
  //   3. exact phone (digit-stripped)
  // Indonesian numbers may be stored as 0812..., 62812..., or +62812...
  // The variant array covers canonical E.164, digit-only, and local 08...
  // forms without dropping prospects when no row matches.
  const sql = `
    SELECT id FROM clients
    WHERE COALESCE(phone_normalized, '') = ANY($1::text[])
       OR COALESCE(whatsapp, '') = ANY($1::text[])
       OR COALESCE(phone, '') = ANY($1::text[])
       OR regexp_replace(COALESCE(phone_normalized, ''), '\\D', '', 'g') = ANY($1::text[])
       OR regexp_replace(COALESCE(whatsapp, ''),         '\\D', '', 'g') = ANY($1::text[])
       OR regexp_replace(COALESCE(phone, ''),            '\\D', '', 'g') = ANY($1::text[])
    LIMIT 1
  `;
  const res = await query<{ id: number }>(sql, [variants]);
  return res.rowCount && res.rowCount > 0 ? res.rows[0].id : null;
}

export async function findOpenPracticeForClient(
  clientId: number
): Promise<number | null> {
  const res = await query<{ id: number }>(
    `SELECT id
       FROM practices
      WHERE client_id = $1
        AND COALESCE(status, '') NOT IN (
          'completed', 'cancelled', 'canceled', 'rejected', 'archived'
        )
      ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST, id DESC
      LIMIT 1`,
    [clientId]
  );
  return res.rowCount && res.rowCount > 0 ? res.rows[0].id : null;
}

export async function touchWhatsAppContact(opts: {
  phone: string;
  name: string;
}): Promise<void> {
  const canonical = normalizePhone(opts.phone);
  if (!canonical) return;
  await query(
    `INSERT INTO whatsapp_contacts
       (phone, phone_normalized, name, contact_type, imported_from, last_message_at, total_messages)
     VALUES ($1, $2, $3, 'client', 'wa_mirror', NOW(), 1)
     ON CONFLICT (phone) DO UPDATE
       SET phone_normalized = EXCLUDED.phone_normalized,
           last_message_at = NOW(),
           total_messages = whatsapp_contacts.total_messages + 1,
           updated_at = NOW()`,
    [canonical, canonical.replace(/[^\d]/g, ""), opts.name.slice(0, 255)]
  );
}
