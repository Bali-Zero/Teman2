import { NextResponse } from "next/server";
import { getPool } from "../../../lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  const pool = await getPool();
  const { rows } = await pool.query(`
    SELECT
      DATE(ts_utc)                    AS day,
      provider,
      COALESCE(SUM(cost_usd), 0)::float AS cost_usd
    FROM llm_cost_events
    WHERE ts_utc >= NOW() - INTERVAL '30 days'
    GROUP BY day, provider
    ORDER BY day ASC
  `);
  return NextResponse.json({ rows });
}
