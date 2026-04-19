import { NextRequest, NextResponse } from "next/server";
import { getPool } from "../../../lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  const pool = await getPool();
  const { rows } = await pool.query(`
    SELECT
      id, ts_utc, endpoint, current_model, proposed_model,
      estimated_monthly_saving_usd::float AS estimated_monthly_saving_usd,
      quality_tradeoff, confidence, spike_flag, status
    FROM llm_cost_recommendations
    WHERE status = 'pending'
    ORDER BY spike_flag DESC, estimated_monthly_saving_usd DESC, ts_utc DESC
    LIMIT 20
  `);
  return NextResponse.json({ rows });
}

export async function PATCH(req: NextRequest) {
  const body = (await req.json()) as { id?: number; status?: string };
  const id = Number(body.id);
  const nextStatus = body.status;
  if (!Number.isFinite(id) || !nextStatus) {
    return NextResponse.json(
      { error: "body must include numeric id and status" },
      { status: 422 },
    );
  }
  if (!["reviewed", "applied", "rejected"].includes(nextStatus)) {
    return NextResponse.json(
      { error: "status must be reviewed|applied|rejected" },
      { status: 422 },
    );
  }

  const pool = await getPool();
  const { rowCount } = await pool.query(
    `UPDATE llm_cost_recommendations
        SET status = $2, reviewed_at = NOW(), reviewed_by = 'local'
      WHERE id = $1`,
    [id, nextStatus],
  );
  if (rowCount === 0) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  return NextResponse.json({ updated: rowCount });
}
