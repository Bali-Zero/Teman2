/**
 * GET /api/cockpit/intel-lake/items — read-only recent intel items.
 *
 * Returns latest 30 intel_items. Page renders a table; row click opens
 * canonical_url in a new tab so Antonello reads the source directly.
 */
import { NextResponse } from "next/server";
import { getPool } from "@/app/lib/db";

export const dynamic = "force-dynamic";

interface ItemRow {
  id: string;
  canonical_url: string | null;
  title: string | null;
  source_domain: string | null;
  routing_status: string | null;
  first_seen_at: string | null;
}

export async function GET() {
  try {
    const db = await getPool();
    const { rows } = await db.query<ItemRow>(
      `SELECT id::text,
              canonical_url,
              title,
              source_domain,
              routing_status,
              first_seen_at::text
         FROM intel_items
        ORDER BY first_seen_at DESC NULLS LAST
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
