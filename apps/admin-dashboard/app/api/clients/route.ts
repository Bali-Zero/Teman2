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
  const requestedPage = Number(searchParams.get("page") ?? "1");
  // `parseInt("abc")` is NaN, and NaN survives Math.max — it would reach pg as
  // the OFFSET bind and 500 the route.
  const page = Number.isFinite(requestedPage)
    ? Math.max(1, Math.floor(requestedPage))
    : 1;
  const limit = 100;
  const offset = (page - 1) * limit;

  // `x-admin-email` is stamped by middleware.ts from the verified JWT, which
  // strips any inbound copy first. Never read a header the caller can set:
  // this one decides whether the response is the whole client book or one
  // person's assignments.
  const authUser = request.headers.get("x-admin-email") ?? "";
  const hasFullAccess = FULL_ACCESS_USERS.includes(authUser);

  // An absent identity must match NOTHING — not the rows whose assignee happens
  // to be nothing. Measured against prod: `assigned_to = ''` is 5 real clients,
  // so scoping an empty caller by equality showed exactly the unassigned book.
  // Small (local dev is the only path that reaches here without an identity) but
  // it is a disclosure nobody chose, and it made "scopes to nobody" false.
  if (!hasFullAccess && authUser === "") {
    return NextResponse.json({ rows: [], page, limit });
  }

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
    // The detail goes to the log, not to the caller — a pg error string can
    // carry the connection target and column names.
    logger.error("Clients query error:", error);
    return NextResponse.json(
      { error: "clients query failed" },
      { status: 500 },
    );
  }
}
