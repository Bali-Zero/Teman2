import { NextResponse } from "next/server";
import { Pool } from "pg";
import { logger } from "@/lib/logger";

export const dynamic = "force-dynamic";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const table = searchParams.get("table");
  const page = parseInt(searchParams.get("page") || "1", 10);
  const limit = 100;
  const offset = (page - 1) * limit;

  if (!table) {
    return NextResponse.json(
      { error: "Table parameter required" },
      { status: 400 },
    );
  }

  try {
    const client = await pool.connect();
    try {
      const checkTable = await client.query(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = $1",
        [table],
      );

      if (checkTable.rowCount === 0) {
        return NextResponse.json({ error: "Invalid table" }, { status: 400 });
      }

      const dataQuery = `SELECT * FROM "${table}" LIMIT $1 OFFSET $2`;
      const dataResult = await client.query(dataQuery, [limit, offset]);

      return NextResponse.json({
        rows: dataResult.rows,
        page,
        limit,
      });
    } finally {
      client.release();
    }
  } catch (error) {
    logger.error("Query Error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : String(error) },
      { status: 500 },
    );
  }
}
