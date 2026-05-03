import { NextRequest, NextResponse } from "next/server";
import { Pool } from "pg";
import { logger } from "@/lib/logger";

export const dynamic = "force-dynamic";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

const ALLOWED_DAYS = new Set([14, 30, 90]);

export async function GET(request: NextRequest) {
  const daysParam = Number(request.nextUrl.searchParams.get("days") ?? "30");
  const days = ALLOWED_DAYS.has(daysParam) ? daysParam : 30;

  const sql = `
    SELECT COALESCE(p.register, 'unknown') AS register,
           m.metric_name,
           AVG(m.value)::float             AS avg_value,
           COUNT(*)::int                   AS sample_count
      FROM war_room_metrics m
      JOIN war_room_posts p ON p.id = m.post_id
     WHERE m.collected_at > NOW() - ($1::int * INTERVAL '1 day')
     GROUP BY 1, 2
     ORDER BY 1 ASC, 2 ASC;
  `;
  const client = await pool.connect();
  try {
    const result = await client.query(sql, [days]);
    return NextResponse.json({
      days,
      cells: result.rows.map((r) => ({
        register: r.register,
        metric_name: r.metric_name,
        avg_value: Number(r.avg_value ?? 0),
        sample_count: Number(r.sample_count ?? 0),
      })),
    });
  } catch (error) {
    logger.error("war_room heatmap error", error);
    if (
      error instanceof Error &&
      (error as { code?: string }).code === "42P01"
    ) {
      return NextResponse.json({ days, cells: [] });
    }
    return NextResponse.json(
      { days, cells: [], error: "internal" },
      { status: 500 },
    );
  } finally {
    client.release();
  }
}
