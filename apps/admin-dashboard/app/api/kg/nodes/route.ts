import { NextResponse } from "next/server";
import { Pool } from "pg";
import { logger } from "@/lib/logger";

export const dynamic = "force-dynamic";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const search = searchParams.get("search") || "";
  const limit = 50;

  try {
    const client = await pool.connect();
    try {
      let query = `SELECT * FROM kg_nodes ORDER BY created_at DESC LIMIT $1`;
      let params: (string | number)[] = [limit];

      if (search) {
        query = `
          SELECT * FROM kg_nodes 
          WHERE name ILIKE $2 OR description ILIKE $2
          ORDER BY created_at DESC LIMIT $1
        `;
        params = [limit, `%${search}%`];
      }

      const result = await client.query(query, params);
      return NextResponse.json({ nodes: result.rows });
    } finally {
      client.release();
    }
  } catch (error) {
    logger.error("NKG Nodes Error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : String(error) },
      { status: 500 },
    );
  }
}
