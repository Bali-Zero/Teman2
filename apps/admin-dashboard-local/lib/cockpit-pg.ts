/**
 * Cockpit PG helpers — read-only by default.
 * Mutations: only cockpit_audit_log + cockpit_intents.
 * NO direct writes to intel_items / war_room_drafts (panel CRITICAL v2 fix).
 */
import { getPool } from "@/app/lib/db";
import { computeAuditHmac } from "./cockpit-audit";

export interface IntelStats {
  unrouted: number;
  routed_recent: number;
  needs_review: number;
  skipped: number;
}

export async function getIntelStats(): Promise<IntelStats> {
  const db = await getPool();
  const { rows } = await db.query<{ routing_status: string; n: string }>(
    `SELECT routing_status, COUNT(*)::text AS n
     FROM intel_items
     WHERE first_seen_at > NOW() - INTERVAL '30 days'
     GROUP BY routing_status`,
  );
  const s: IntelStats = {
    unrouted: 0,
    routed_recent: 0,
    needs_review: 0,
    skipped: 0,
  };
  for (const r of rows) {
    const n = parseInt(r.n, 10);
    if (r.routing_status === "unrouted") s.unrouted = n;
    else if (r.routing_status === "needs_review") s.needs_review = n;
    else if (r.routing_status === "skip") s.skipped = n;
    else s.routed_recent += n;
  }
  return s;
}

export interface AuditInsertParams {
  action: string;
  params: Record<string, unknown>;
  result: "success" | "denied" | "error";
  errorMessage?: string;
}

export async function insertAuditRow(
  hmacSecret: string,
  p: AuditInsertParams,
): Promise<bigint> {
  const db = await getPool();
  const { rows: prev } = await db.query<{ hmac_sha256: string }>(
    `SELECT hmac_sha256 FROM cockpit_audit_log ORDER BY id DESC LIMIT 1`,
  );
  const prevHmac = prev[0]?.hmac_sha256 ?? null;
  const createdAt = new Date().toISOString();
  const hmac = computeAuditHmac(hmacSecret, prevHmac, {
    action: p.action,
    params_json: p.params,
    created_at: createdAt,
    result: p.result,
    error_message: p.errorMessage ?? null,
  });
  const { rows } = await db.query<{ id: string }>(
    `INSERT INTO cockpit_audit_log
       (action, params_json, result, error_message, hmac_sha256, prev_hmac)
     VALUES ($1, $2::jsonb, $3, $4, $5, $6)
     RETURNING id::text`,
    [
      p.action,
      JSON.stringify(p.params),
      p.result,
      p.errorMessage ?? null,
      hmac,
      prevHmac,
    ],
  );
  return BigInt(rows[0].id);
}

export async function createIntent(
  intentType: string,
  params: Record<string, unknown>,
  reason: string,
): Promise<bigint> {
  const db = await getPool();
  const { rows } = await db.query<{ id: string }>(
    `INSERT INTO cockpit_intents (intent_type, params_json, reason)
     VALUES ($1, $2::jsonb, $3)
     RETURNING id::text`,
    [intentType, JSON.stringify(params), reason],
  );
  return BigInt(rows[0].id);
}
