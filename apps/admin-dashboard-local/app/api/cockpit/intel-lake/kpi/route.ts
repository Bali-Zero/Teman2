/**
 * GET /api/cockpit/intel-lake/kpi — 4 read-only KPI counters.
 *
 * - items_today: intel_items first_seen_at today (UTC)
 * - outbox_pending: events_outbox intel_lake_event awaiting consume
 * - stuck: intel_items where routing_status = 'needs_review'
 * - nb_pushes_7d: intel_item_nb_pushes in the last 7 days
 */
import { NextResponse } from "next/server";
import { getPool } from "@/app/lib/db";

export const dynamic = "force-dynamic";

async function countSafely(
  pool: Awaited<ReturnType<typeof getPool>>,
  sql: string,
): Promise<number> {
  try {
    const { rows } = await pool.query<{ n: string }>(sql);
    return parseInt(rows[0]?.n ?? "0", 10) || 0;
  } catch {
    // Returning 0 keeps the page rendering even when a sibling migration
    // hasn't been applied locally (e.g. intel_item_nb_pushes absent in a
    // fresh dev DB). Errors surface in the `errors` map for diagnostics.
    return -1;
  }
}

export async function GET() {
  const db = await getPool();
  const errors: Record<string, string> = {};

  const [items_today, outbox_pending, stuck, nb_pushes_7d] = await Promise.all([
    countSafely(
      db,
      `SELECT COUNT(*)::text AS n FROM intel_items
        WHERE first_seen_at::date = CURRENT_DATE`,
    ),
    countSafely(
      db,
      `SELECT COUNT(*)::text AS n FROM events_outbox
        WHERE channel = 'intel_lake_event' AND consumed_at IS NULL`,
    ),
    countSafely(
      db,
      `SELECT COUNT(*)::text AS n FROM intel_items
        WHERE routing_status = 'needs_review'`,
    ),
    countSafely(
      db,
      `SELECT COUNT(*)::text AS n FROM intel_item_nb_pushes
        WHERE pushed_at > NOW() - INTERVAL '7 days'`,
    ),
  ]);

  const out: Record<string, number> = {
    items_today,
    outbox_pending,
    stuck,
    nb_pushes_7d,
  };
  for (const [k, v] of Object.entries(out)) {
    if (v < 0) errors[k] = "query failed (table missing?)";
  }
  return NextResponse.json({ ...out, errors });
}
