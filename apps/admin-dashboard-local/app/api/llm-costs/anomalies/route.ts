import { NextResponse } from "next/server";
import { getPool } from "../../../lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  const pool = await getPool();
  const { rows } = await pool.query(`
    SELECT
      id, ts_utc, endpoint, current_model, proposed_model,
      estimated_monthly_saving_usd::float AS estimated_monthly_saving_usd,
      confidence
    FROM llm_cost_recommendations
    WHERE spike_flag = TRUE
      AND status = 'pending'
    ORDER BY ts_utc DESC
    LIMIT 10
  `);
  return NextResponse.json({ rows });
}
