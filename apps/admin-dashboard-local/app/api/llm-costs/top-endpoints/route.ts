import { NextResponse } from "next/server";
import { getPool } from "../../../lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  const pool = await getPool();
  const { rows } = await pool.query(`
    SELECT
      COALESCE(endpoint, 'unknown') AS endpoint,
      COUNT(*)                      AS call_count,
      COALESCE(SUM(cost_usd), 0)::float AS total_cost_usd
    FROM llm_cost_events
    WHERE ts_utc >= NOW() - INTERVAL '7 days'
    GROUP BY endpoint
    ORDER BY total_cost_usd DESC
    LIMIT 10
  `);
  return NextResponse.json({ rows });
}
