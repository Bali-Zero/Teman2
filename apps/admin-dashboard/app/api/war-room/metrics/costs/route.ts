import { NextRequest, NextResponse } from "next/server";
import { Pool } from "pg";
import { logger } from "@/lib/logger";

export const dynamic = "force-dynamic";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

const ALLOWED_DAYS = new Set([14, 30, 90]);

interface CostRow {
  draft_id: string;
  topic: string;
  total_usd: number;
  by_type: Record<string, number>;
}

export async function GET(request: NextRequest) {
  const daysParam = Number(request.nextUrl.searchParams.get("days") ?? "30");
  const days = ALLOWED_DAYS.has(daysParam) ? daysParam : 30;
  const limitParam = Number(request.nextUrl.searchParams.get("limit") ?? "50");
  const limit = Math.max(
    1,
    Math.min(200, Number.isFinite(limitParam) ? limitParam : 50),
  );

  const sql = `
    WITH totals AS (
      SELECT c.draft_id,
             SUM(c.cost_usd) AS total_usd
        FROM war_room_costs c
       WHERE c.occurred_at > NOW() - ($1::int * INTERVAL '1 day')
         AND c.draft_id IS NOT NULL
       GROUP BY c.draft_id
       ORDER BY total_usd DESC
       LIMIT $2::int
    ),
    by_type AS (
      SELECT c.draft_id, c.cost_type, SUM(c.cost_usd) AS t
        FROM war_room_costs c
       WHERE c.draft_id IN (SELECT draft_id FROM totals)
       GROUP BY 1, 2
    )
    SELECT t.draft_id,
           d.topic,
           t.total_usd,
           JSONB_OBJECT_AGG(b.cost_type, b.t)
             FILTER (WHERE b.cost_type IS NOT NULL) AS by_type
      FROM totals t
      LEFT JOIN war_room_drafts d ON d.id = t.draft_id
      LEFT JOIN by_type b         ON b.draft_id = t.draft_id
     GROUP BY t.draft_id, d.topic, t.total_usd
     ORDER BY t.total_usd DESC;
  `;
  const client = await pool.connect();
  try {
    const result = await client.query(sql, [days, limit]);
    const rows: CostRow[] = result.rows.map((r) => {
      const rawByType = r.by_type as Record<string, unknown> | null;
      const byType: Record<string, number> = {};
      if (rawByType && typeof rawByType === "object") {
        for (const [k, v] of Object.entries(rawByType)) {
          byType[k] = Number(v ?? 0);
        }
      }
      return {
        draft_id: String(r.draft_id),
        topic: r.topic ?? "",
        total_usd: Number(r.total_usd ?? 0),
        by_type: byType,
      };
    });
    const grandTotal = rows.reduce((acc, row) => acc + row.total_usd, 0);
    return NextResponse.json({
      days,
      limit,
      rows,
      grand_total_usd: Number(grandTotal.toFixed(4)),
    });
  } catch (error) {
    logger.error("war_room costs error", error);
    if (
      error instanceof Error &&
      (error as { code?: string }).code === "42P01"
    ) {
      return NextResponse.json({ days, limit, rows: [], grand_total_usd: 0 });
    }
    return NextResponse.json(
      { days, limit, rows: [], grand_total_usd: 0, error: "internal" },
      { status: 500 },
    );
  } finally {
    client.release();
  }
}
