import { NextResponse } from "next/server";
import { getPool } from "../../../lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  const pool = await getPool();
  const { rows } = await pool.query(`
    SELECT
      COALESCE(SUM(CASE WHEN ts_utc >= CURRENT_DATE THEN cost_usd ELSE 0 END), 0) AS today_usd,
      COALESCE(SUM(CASE WHEN ts_utc >= NOW() - INTERVAL '7 days'  THEN cost_usd ELSE 0 END), 0) AS last_7d_usd,
      COALESCE(SUM(CASE WHEN ts_utc >= NOW() - INTERVAL '30 days' THEN cost_usd ELSE 0 END), 0) AS last_30d_usd
    FROM llm_cost_events
  `);
  return NextResponse.json(rows[0]);
}
