import { NextResponse } from "next/server";
import { Pool } from "pg";
import { logger } from "@/lib/logger";

export const dynamic = "force-dynamic";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const userId = searchParams.get("userId");
  const search = searchParams.get("search");

  try {
    const client = await pool.connect();
    try {
      if (userId) {
        // Note: In production, users are stored in 'team_members' or 'clients'
        // 'user_facts' likely references these via UUID.
        const factsQuery = `SELECT * FROM user_facts WHERE user_id = $1 ORDER BY learned_at DESC`;
        const memoriesQuery = `SELECT * FROM episodic_memories WHERE user_id = $1 ORDER BY created_at DESC LIMIT 50`;
        // Try getting user from team_members first
        const userQuery = `SELECT id, email, name as full_name, created_at FROM team_members WHERE id = $1`;

        const [userRes, factsRes, memoriesRes] = await Promise.all([
          client.query(userQuery, [userId]),
          client.query(factsQuery, [userId]),
          client.query(memoriesQuery, [userId]),
        ]);

        return NextResponse.json({
          user: userRes.rows[0],
          facts: factsRes.rows,
          memories: memoriesRes.rows,
        });
      } else {
        // List users from team_members
        let query = `SELECT id, email, name as full_name, created_at FROM team_members ORDER BY created_at DESC LIMIT 50`;
        let params: (string | number)[] = [];

        if (search) {
          query = `SELECT id, email, name as full_name, created_at FROM team_members WHERE email ILIKE $1 OR name ILIKE $1 ORDER BY created_at DESC LIMIT 50`;
          params = [`%${search}%`];
        }

        const result = await client.query(query, params);
        return NextResponse.json({ users: result.rows });
      }
    } finally {
      client.release();
    }
  } catch (error) {
    logger.error("User Context Error:", error);
    // Handle missing tables gracefully
    const pgError = error as { code?: string };
    if (pgError.code === "42P01") {
      return NextResponse.json({
        users: [],
        warning: "User tables not found or schema mismatch",
      });
    }
    return NextResponse.json(
      { error: error instanceof Error ? error.message : String(error) },
      { status: 500 },
    );
  }
}
