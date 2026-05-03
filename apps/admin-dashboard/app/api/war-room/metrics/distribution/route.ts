import { NextRequest, NextResponse } from "next/server";
import { Pool } from "pg";
import { logger } from "@/lib/logger";

export const dynamic = "force-dynamic";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

const ALLOWED_DAYS = new Set([14, 30, 90]);
const DOMINANCE_ALERT_PCT = 40.0;

export async function GET(request: NextRequest) {
  const daysParam = Number(request.nextUrl.searchParams.get("days") ?? "30");
  const days = ALLOWED_DAYS.has(daysParam) ? daysParam : 30;

  const sql = `
    SELECT COALESCE(register, 'unknown') AS register,
           COUNT(*)::int                 AS post_count
      FROM war_room_posts
     WHERE published_at > NOW() - ($1::int * INTERVAL '1 day')
     GROUP BY 1
     ORDER BY 2 DESC;
  `;
  const client = await pool.connect();
  try {
    const result = await client.query(sql, [days]);
    const total = result.rows.reduce(
      (acc, r) => acc + Number(r.post_count ?? 0),
      0,
    );
    const slices = result.rows.map((r) => {
      const count = Number(r.post_count ?? 0);
      const pct = total > 0 ? (count / total) * 100 : 0;
      return {
        register: r.register,
        post_count: count,
        pct: Number(pct.toFixed(2)),
      };
    });
    const dominant = slices.length > 0 ? slices[0].register : null;
    const alert = slices.some((s) => s.pct > DOMINANCE_ALERT_PCT);
    return NextResponse.json({
      days,
      total_posts: total,
      slices,
      dominant_register: dominant,
      alert,
    });
  } catch (error) {
    logger.error("war_room distribution error", error);
    if (
      error instanceof Error &&
      (error as { code?: string }).code === "42P01"
    ) {
      return NextResponse.json({
        days,
        total_posts: 0,
        slices: [],
        dominant_register: null,
        alert: false,
      });
    }
    return NextResponse.json(
      { days, total_posts: 0, slices: [], error: "internal" },
      { status: 500 },
    );
  } finally {
    client.release();
  }
}
