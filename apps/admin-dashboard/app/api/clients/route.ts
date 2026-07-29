import { NextResponse } from "next/server";
import { Pool } from "pg";
import { logger } from "@/lib/logger";

export const dynamic = "force-dynamic";

const pool = new Pool({ connectionString: process.env.DATABASE_URL });

const SAFE_COLUMNS = [
  "id",
  "full_name",
  "email",
  "phone",
  "status",
  "assigned_to",
  "created_at",
].join(", ");

const FULL_ACCESS_USERS = [
  "zero@balizero.com",
  "antonellosiano@balizero.com",
  "asya@balizero.com",
];

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const page = Math.max(1, parseInt(searchParams.get("page") ?? "1", 10));
  const limit = 100;
  const offset = (page - 1) * limit;

  const authUser = request.headers.get("x-user-email") ?? "";
  const hasFullAccess = FULL_ACCESS_USERS.includes(authUser);

  try {
    const client = await pool.connect();
    try {
      const query = hasFullAccess
        ? `SELECT ${SAFE_COLUMNS} FROM clients WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT $1 OFFSET $2`
        : `SELECT ${SAFE_COLUMNS} FROM clients WHERE deleted_at IS NULL AND assigned_to = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3`;
      const params = hasFullAccess
        ? [limit, offset]
        : [authUser, limit, offset];

      const result = await client.query(query, params);
      return NextResponse.json({ rows: result.rows, page, limit });
    } finally {
      client.release();
    }
  } catch (error) {
    logger.error("Clients query error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : String(error) },
      { status: 500 },
    );
  }
}
