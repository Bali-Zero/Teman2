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
    SELECT reason, COUNT(*)::int AS n
      FROM war_room_rejections
     WHERE rejected_at > NOW() - ($1::int * INTERVAL '1 day')
     GROUP BY reason
     ORDER BY n DESC;
  `;
  const client = await pool.connect();
  try {
    const result = await client.query(sql, [days]);
    return NextResponse.json({
      days,
      buckets: result.rows.map((r) => ({
        reason: r.reason,
        count: Number(r.n ?? 0),
      })),
    });
  } catch (error) {
    logger.error("war_room rejections error", error);
    if (
      error instanceof Error &&
      (error as { code?: string }).code === "42P01"
    ) {
      return NextResponse.json({ days, buckets: [] });
    }
    return NextResponse.json(
      { days, buckets: [], error: "internal" },
      { status: 500 },
    );
  } finally {
    client.release();
  }
}
