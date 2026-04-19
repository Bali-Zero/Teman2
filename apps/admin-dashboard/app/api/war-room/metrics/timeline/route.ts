import { NextRequest, NextResponse } from "next/server";
import { Pool } from "pg";
import { logger } from "@/lib/logger";

export const dynamic = "force-dynamic";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

const ALLOWED_DAYS = new Set([14, 30, 90]);

export async function GET(request: NextRequest) {
  const daysParam = Number(request.nextUrl.searchParams.get("days") ?? "14");
  const days = ALLOWED_DAYS.has(daysParam) ? daysParam : 14;

  const sql = `
    SELECT DATE(published_at AT TIME ZONE 'UTC') AS day,
           COALESCE(register, 'unknown')          AS register,
           COUNT(*)::int                          AS post_count
      FROM war_room_posts
     WHERE published_at > NOW() - ($1::int * INTERVAL '1 day')
     GROUP BY 1, 2
     ORDER BY 1 ASC, 2 ASC;
  `;
  const client = await pool.connect();
  try {
    const result = await client.query(sql, [days]);
    return NextResponse.json({
      days,
      buckets: result.rows.map((r) => ({
        day:
          r.day instanceof Date
            ? r.day.toISOString().slice(0, 10)
            : String(r.day),
        register: r.register,
        post_count: Number(r.post_count ?? 0),
      })),
    });
  } catch (error) {
    logger.error("war_room timeline error", error);
    // 42P01 = relation does not exist — return empty for pre-migration envs
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
