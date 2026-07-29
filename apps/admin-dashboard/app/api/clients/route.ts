import { NextResponse } from "next/server";
import { Pool } from "pg";
import { logger } from "@/lib/logger";

export const dynamic = "force-dynamic";

const pool = new Pool({ connectionString: process.env.DATABASE_URL });

/**
 * Why this route exists: `/clients` used to read `/api/postgres/query?table=clients`,
 * which is `SELECT * FROM "<table>"` — every column of every row, soft-deleted rows
 * included. This route is the narrow replacement: an explicit column allow-list, the
 * `deleted_at` filter, and parameterised values.
 *
 * WHERE THE ACCESS BOUNDARY ACTUALLY IS: `middleware.ts`. It runs on every path
 * including `/api/*`, verifies the `nz_access_token` JWT, and requires
 * `role ∈ {admin, super_admin, owner}`. Anyone who reaches this handler is already
 * an admin — there is no second, finer principal available here.
 *
 * The first draft of this route tried to be finer anyway: it read
 * `request.headers.get("x-user-email")` and, for anyone not in a hardcoded
 * full-access list, scoped the query to `assigned_to = <that email>`. Measured, that
 * was worse than nothing on both counts:
 *   - NOBODY SETS THAT HEADER. It appeared exactly once in the whole app — in the
 *     line that read it. The middleware sets `x-admin-email`, and it sets it on the
 *     RESPONSE (`res.headers.set`), which a route handler never sees. So `authUser`
 *     was always `""`, the query was always `assigned_to = ''`, and the clients page
 *     returned ZERO ROWS in every environment, production and local dev alike.
 *   - It was a control in name only. An inbound header is caller-supplied, so had it
 *     ever been non-empty it would have been spoofable — and `/api/postgres/query`
 *     still sits next door serving the same table unfiltered to the same admins.
 *
 * A predicate that is permanently false is not access control; it is an outage
 * wearing the costume of one. So the per-user scope is gone, deliberately. If a
 * per-assignee view is wanted, it belongs where a real principal exists (the CRM in
 * `kita`), not in an admin-only DB inspector.
 */
const SAFE_COLUMNS = [
  "id",
  "full_name",
  "email",
  "phone",
  "status",
  "assigned_to",
  "created_at",
].join(", ");

const PAGE_SIZE = 100;

export interface ClientsQuery {
  text: string;
  values: number[];
  page: number;
  limit: number;
}

/**
 * Pure so it can be asserted without a database. It takes ONLY the page — there is
 * deliberately no principal parameter, which is what makes "an unset header empties
 * the page" unrepresentable rather than merely fixed.
 *
 * `parseInt("abc")` is NaN and `Math.max(1, NaN)` is NaN, which would reach pg as a
 * NaN OFFSET; hence the finite check rather than a bare `Math.max`.
 */
export function buildClientsQuery(rawPage: string | null): ClientsQuery {
  const parsed = Number.parseInt(rawPage ?? "1", 10);
  const page = Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
  const offset = (page - 1) * PAGE_SIZE;

  return {
    text: `SELECT ${SAFE_COLUMNS} FROM clients WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT $1 OFFSET $2`,
    values: [PAGE_SIZE, offset],
    page,
    limit: PAGE_SIZE,
  };
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const { text, values, page, limit } = buildClientsQuery(
    searchParams.get("page"),
  );

  try {
    const client = await pool.connect();
    try {
      const result = await client.query(text, values);
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
