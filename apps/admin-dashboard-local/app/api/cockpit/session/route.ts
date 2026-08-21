import { NextRequest, NextResponse } from "next/server";
import { isAllowedCockpitHost } from "@/lib/cockpit-host";
import { hasValidCockpitSession } from "@/lib/cockpit-session";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  if (!isAllowedCockpitHost(request.headers.get("host"))) {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }
  if (!(await hasValidCockpitSession(request))) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  return NextResponse.json(
    { authenticated: true },
    {
      headers: {
        "cache-control": "no-store, max-age=0",
        "x-robots-tag": "noindex, nofollow, noarchive",
      },
    },
  );
}
