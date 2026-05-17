/**
 * GET /api/cockpit/wr2/drafts — read-only WR2 drafts list.
 *
 * Returns latest 30 war_room_drafts. MVP exposes no mutations; the page
 * filters client-side by status (dropdown).
 */
import { NextResponse } from "next/server";
import { getPool } from "@/app/lib/db";

export const dynamic = "force-dynamic";

interface DraftRow {
  id: string;
  topic: string | null;
  status: string | null;
  register: string | null;
  updated_at: string | null;
  lease_owner: string | null;
}

export async function GET() {
  try {
    const db = await getPool();
    // Schema note: the column is `tone_register` (per migrations_v2), alias
    // to `register` in the API contract for the UI table.
    const { rows } = await db.query<DraftRow>(
      `SELECT id::text,
              topic,
              status,
              tone_register AS register,
              updated_at::text,
              lease_owner
         FROM war_room_drafts
        ORDER BY updated_at DESC NULLS LAST
        LIMIT 30`,
    );
    return NextResponse.json({ count: rows.length, items: rows });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      { count: 0, items: [], error: msg },
      { status: 500 },
    );
  }
}
