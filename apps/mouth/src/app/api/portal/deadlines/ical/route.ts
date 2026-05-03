/**
 * Portal deadlines iCal export.
 *
 * Fetches /api/portal/dashboard/summary from the backend (forwarding the
 * client's nz_access_token cookie) and streams the upcoming deadlines back
 * as a .ics attachment. Same pattern as /api/tax-calendar/ical.
 */

import { NextRequest, NextResponse } from "next/server";
import { toIcalString } from "@balizero/core/utils";

function getBackendUrl(): string {
  const raw =
    process.env.NUZANTARA_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "https://nuzantara-rag.fly.dev";
  return raw.replace(/\/+$/, "").replace(/\/api$/, "");
}

interface SummaryDeadline {
  id: string;
  label: string;
  due_date: string | null;
  kind: string | null;
}

export async function GET(req: NextRequest): Promise<NextResponse> {
  const jwt = req.cookies.get("nz_access_token")?.value;
  if (!jwt) {
    return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  }

  const upstream = await fetch(
    `${getBackendUrl()}/api/portal/dashboard/summary`,
    {
      headers: { Authorization: `Bearer ${jwt}` },
      cache: "no-store",
    },
  );
  if (!upstream.ok) {
    return NextResponse.json(
      { error: "upstream_failed", status: upstream.status },
      { status: upstream.status },
    );
  }
  const data = (await upstream.json()) as {
    upcoming_deadlines?: SummaryDeadline[];
  };
  const deadlines = data.upcoming_deadlines ?? [];

  const ics = toIcalString(
    deadlines
      .filter((d): d is SummaryDeadline & { due_date: string } =>
        Boolean(d.due_date),
      )
      .map((d) => {
        const start = new Date(d.due_date);
        return {
          uid: `balizero-portal-${d.id}@balizero.com`,
          summary: d.label,
          start,
          end: new Date(start.getTime() + 86_400_000),
          description: d.kind ?? "",
        };
      }),
    { prodId: "BaliZero//Portal//EN" },
  );

  return new NextResponse(ics, {
    headers: {
      "Content-Type": "text/calendar; charset=utf-8",
      "Content-Disposition": 'attachment; filename="balizero-deadlines.ics"',
    },
  });
}
