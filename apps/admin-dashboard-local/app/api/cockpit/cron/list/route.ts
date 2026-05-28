import { NextResponse } from "next/server";
import { getAllAgenticCronStatus } from "@/lib/cockpit-launchctl";

export const dynamic = "force-dynamic";

export async function GET() {
  const statuses = await getAllAgenticCronStatus();
  const counts = {
    running: statuses.filter((s) => s.state === "running").length,
    waiting: statuses.filter((s) => s.state === "waiting").length,
    not_loaded: statuses.filter((s) => s.state === "not_loaded").length,
    failed: statuses.filter(
      (s) => s.lastExitStatus !== null && s.lastExitStatus !== 0,
    ).length,
  };
  return NextResponse.json({ statuses, counts });
}
