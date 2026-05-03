import { NextResponse } from "next/server";
import { getPool } from "../../../lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  const pool = await getPool();
  const { rows } = await pool.query(`
    SELECT
      provider,
      COALESCE(SUM(input_tokens), 0)::bigint  AS input_tokens,
      COALESCE(SUM(output_tokens), 0)::bigint AS output_tokens,
      COUNT(*)                                AS call_count
    FROM llm_cost_events
    WHERE ts_utc >= NOW() - INTERVAL '7 days'
    GROUP BY provider
    ORDER BY input_tokens DESC
  `);
  return NextResponse.json({ rows });
}
