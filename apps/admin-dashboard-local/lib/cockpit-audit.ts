/**
 * Cockpit audit log with HMAC-SHA-256 chain.
 * Each row hmac = HMAC(secret, prev_hmac || JSON(row)).
 * Panel finding 4-LLM v2 MEDIUM: audit log must be immutable.
 */
import { createHmac } from "node:crypto";

export interface AuditRow {
  id?: bigint;
  action: string;
  params_json: Record<string, unknown>;
  created_at: string;
  result: "success" | "denied" | "error";
  error_message?: string | null;
  prev_hmac?: string | null;
  hmac_sha256?: string;
}

function serializeForHmac(row: AuditRow): string {
  return JSON.stringify({
    action: row.action,
    params_json: row.params_json,
    created_at: row.created_at,
    result: row.result,
    error_message: row.error_message ?? null,
  });
}

export function computeAuditHmac(
  secret: string,
  prevHmac: string | null,
  row: AuditRow,
): string {
  const payload = (prevHmac ?? "") + serializeForHmac(row);
  return createHmac("sha256", secret).update(payload).digest("hex");
}

export interface ChainVerification {
  valid: boolean;
  tamperedAt?: bigint;
}

export function verifyAuditChain(
  secret: string,
  rows: AuditRow[],
): ChainVerification {
  let prev: string | null = null;
  for (const row of rows) {
    if (computeAuditHmac(secret, prev, row) !== row.hmac_sha256) {
      return { valid: false, tamperedAt: row.id };
    }
    prev = row.hmac_sha256 ?? null;
  }
  return { valid: true };
}

export function readHmacSecret(): string | null {
  return process.env.COCKPIT_HMAC_KEY || null;
}
