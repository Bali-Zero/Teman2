/**
 * GET /api/cockpit/cron/list — agentic cron status snapshot.
 *
 * Read-only: launchctl print for each of 35 allowlisted labels. Returns
 * total + running count for the Home tile "Global Pulse".
 */
import { NextResponse } from "next/server";
import { getAllAgenticCronStatus } from "@/lib/cockpit-launchctl";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const rows = await getAllAgenticCronStatus();
    const running = rows.filter((r) => r.state === "running").length;
    const waiting = rows.filter((r) => r.state === "waiting").length;
    const notLoaded = rows.filter((r) => r.state === "not_loaded").length;
    return NextResponse.json({
      total: rows.length,
      running,
      waiting,
      not_loaded: notLoaded,
      items: rows,
    });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
