import { NextResponse } from "next/server";
import { Pool } from "pg";
import { logger } from "@/lib/logger";

export const dynamic = "force-dynamic";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

export async function GET() {
  try {
    const client = await pool.connect();
    try {
      const result = await client.query(`
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
      `);

      const tablesWithCounts = await Promise.all(
        result.rows.map(async (row) => {
          const countResult = await client.query(
            `SELECT count(*) FROM "${row.table_name}"`,
          );
          return {
            name: row.table_name,
            count: parseInt(countResult.rows[0].count, 10),
          };
        }),
      );

      return NextResponse.json({ tables: tablesWithCounts });
    } finally {
      client.release();
    }
  } catch (error) {
    logger.error("Postgres Error:", error);
    return NextResponse.json({ error: error instanceof Error ? error.message : String(error) }, { status: 500 });
  }
}
