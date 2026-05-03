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

  const client = await pool.connect();
  try {
    const [drafts, approved, published, leads] = await Promise.all([
      client.query(
        `SELECT COUNT(*)::int AS n FROM war_room_drafts
         WHERE created_at > NOW() - ($1::int * INTERVAL '1 day');`,
        [days],
      ),
      client.query(
        `SELECT COUNT(*)::int AS n FROM war_room_drafts
         WHERE approved_at IS NOT NULL
           AND approved_at > NOW() - ($1::int * INTERVAL '1 day');`,
        [days],
      ),
      client.query(
        `SELECT COUNT(DISTINCT draft_id)::int AS n FROM war_room_posts
         WHERE published_at > NOW() - ($1::int * INTERVAL '1 day');`,
        [days],
      ),
      client.query(
        `SELECT COUNT(*)::int AS n FROM war_room_leads
         WHERE attributed_at > NOW() - ($1::int * INTERVAL '1 day');`,
        [days],
      ),
    ]);

    return NextResponse.json({
      days,
      stages: [
        { stage: "drafts", count: Number(drafts.rows[0]?.n ?? 0) },
        { stage: "approved", count: Number(approved.rows[0]?.n ?? 0) },
        { stage: "published", count: Number(published.rows[0]?.n ?? 0) },
        { stage: "leads", count: Number(leads.rows[0]?.n ?? 0) },
      ],
    });
  } catch (error) {
    logger.error("war_room funnel error", error);
    if (
      error instanceof Error &&
      (error as { code?: string }).code === "42P01"
    ) {
      return NextResponse.json({
        days,
        stages: [
          { stage: "drafts", count: 0 },
          { stage: "approved", count: 0 },
          { stage: "published", count: 0 },
          { stage: "leads", count: 0 },
        ],
      });
    }
    return NextResponse.json(
      { days, stages: [], error: "internal" },
      { status: 500 },
    );
  } finally {
    client.release();
  }
}
