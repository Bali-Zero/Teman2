import { NextResponse } from "next/server";
import { Pool } from "pg";
import { logger } from "@/lib/logger";

export const dynamic = "force-dynamic";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const nodeId = searchParams.get("nodeId");

  if (!nodeId) {
    return NextResponse.json({ error: "nodeId required" }, { status: 400 });
  }

  try {
    const client = await pool.connect();
    try {
      // Find all edges where the node is source OR target
      const query = `
        SELECT e.*, 
               s.name as source_name, 
               t.name as target_name
        FROM kg_edges e
        JOIN kg_nodes s ON e.source_entity_id = s.entity_id
        JOIN kg_nodes t ON e.target_entity_id = t.entity_id
        WHERE e.source_entity_id = $1 OR e.target_entity_id = $1
        LIMIT 100
      `;

      const result = await client.query(query, [nodeId]);
      return NextResponse.json({ edges: result.rows });
    } finally {
      client.release();
    }
  } catch (error) {
    logger.error("NKG Edges Error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : String(error) },
      { status: 500 },
    );
  }
}
