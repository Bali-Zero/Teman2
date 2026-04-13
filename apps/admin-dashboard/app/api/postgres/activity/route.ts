import { NextResponse } from "next/server";
import { Pool } from "pg";
import { logger } from "@/lib/logger";

export const dynamic = "force-dynamic";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

export async function GET(request: Request) {
  try {
    const client = await pool.connect();
    try {
      // Try fetching from activity_log
      // If table doesn't exist, this will throw, and we can handle it.
      const query = `
        SELECT * FROM activity_log 
        ORDER BY created_at DESC 
        LIMIT 50
      `;
      const result = await client.query(query);
      return NextResponse.json({ activities: result.rows });
    } finally {
      client.release();
    }
  } catch (error) {
    logger.error("Activity Log Error:", error);
    // If table doesn't exist, return empty to avoid breaking UI
    if (error instanceof Error && 'code' in error && (error as { code: string }).code === "42P01") {
      return NextResponse.json({
        activities: [],
        warning: "Table activity_log not found",
      });
    }
    return NextResponse.json({ error: error instanceof Error ? error.message : String(error) }, { status: 500 });
  }
}
