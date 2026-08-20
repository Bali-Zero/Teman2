import { NextRequest, NextResponse } from "next/server";
import { execFile } from "child_process";
import { promisify } from "util";

import { logger } from "@/lib/logger";

// execFile (not exec) — argv is passed as an array straight to the binary,
// never through a shell. calendarId/days/max/summary/etc. are user-provided
// (query params or JSON body); with `exec` + a template string they could
// break out of the intended argument via shell metacharacters (CodeQL
// js/command-line-injection #2311/#2312/#2313, 2026-08-21). execFile makes
// that class of injection structurally impossible — each array element
// becomes exactly one argv token, no matter what characters it contains.
const execFileAsync = promisify(execFile);

const GOG_PATH = "/opt/homebrew/bin/gog";
const TEAM_CALENDAR_ID =
  "ec0863e7c14ac6bf414ec23e2aab81960ecb26823c6a8f397c664fc64901d617@group.calendar.google.com";

// Argument-injection guard (argv flag smuggling — CodeQL follow-up, 2026-08-21).
// execFile stops shell metacharacter injection (no shell is ever spawned), but
// it does NOT stop a value that starts with `-`/`--` from being read as a FLAG
// by gog's own parser once it lands in argv (gog is built on alecthomas/kong,
// which — like effectively every CLI-parsing library — recognizes a `-`-led
// token as a flag candidate regardless of which array slot it occupies). A
// calendarId of `--upload-file=/etc/passwd` or an eventId of `--force` carries
// no shell risk but could still be reinterpreted by gog itself. Defense: allow-
// list every field to the shape it MUST have, never a blocklist of "dangerous"
// characters — and reject anything starting with `-`, which none of these
// fields ever legitimately do.
const CALENDAR_ID_RE =
  /^(?:primary|[A-Za-z0-9](?:[A-Za-z0-9._%+-]*[A-Za-z0-9])?@[A-Za-z0-9.-]+\.[A-Za-z]{2,})$/;
const DIGITS_RE = /^\d{1,4}$/;
const EVENT_ID_RE = /^[A-Za-z0-9][A-Za-z0-9_-]{0,1023}$/;
const ISO_DATETIME_RE =
  /^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2}|[+-]\d{4})?)?$/;

function badRequest(field: string): NextResponse {
  return NextResponse.json(
    { success: false, error: `Invalid ${field}` },
    { status: 400 },
  );
}

// Free-text fields (summary/description/location/attendees): no fixed shape,
// but a legitimate value never begins with `-` and has a sane length cap.
function isSafeFreeText(value: string, maxLen: number): boolean {
  return value.length > 0 && value.length <= maxLen && !value.startsWith("-");
}

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const calendarId = searchParams.get("calendarId") || TEAM_CALENDAR_ID;
    const days = searchParams.get("days") || "30";
    const max = searchParams.get("max") || "50";

    if (!CALENDAR_ID_RE.test(calendarId)) return badRequest("calendarId");
    if (!DIGITS_RE.test(days)) return badRequest("days");
    if (!DIGITS_RE.test(max)) return badRequest("max");

    const { stdout } = await execFileAsync(GOG_PATH, [
      "calendar",
      "events",
      calendarId,
      "--days",
      days,
      "--max",
      max,
      "--json",
    ]);

    const data = JSON.parse(stdout || '{"events":[]}');
    interface CalendarEvent {
      id: string;
      summary: string;
      start?: { dateTime?: string; date?: string };
      end?: { dateTime?: string; date?: string };
      description?: string;
      location?: string;
      hangoutLink?: string;
      attendees?: { email: string }[];
    }

    const events = (data.events || data || []).map((evt: CalendarEvent) => ({
      id: evt.id,
      summary: evt.summary,
      start: evt.start?.dateTime || evt.start?.date,
      end: evt.end?.dateTime || evt.end?.date,
      description: evt.description,
      location: evt.location,
      hangoutLink: evt.hangoutLink,
      attendees: evt.attendees?.map((a) => a.email),
    }));

    return NextResponse.json({
      success: true,
      events,
      calendarId,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    // If no events, return empty array
    if (message?.includes("No events")) {
      return NextResponse.json({
        success: true,
        events: [],
        calendarId: TEAM_CALENDAR_ID,
      });
    }

    logger.error("Calendar API error:", error);
    return NextResponse.json(
      { success: false, error: message },
      { status: 500 },
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const {
      summary,
      from,
      to,
      description,
      location,
      attendees,
      withMeet,
      calendarId = TEAM_CALENDAR_ID,
    } = body;

    if (!summary || !from || !to) {
      return NextResponse.json(
        { success: false, error: "summary, from, and to are required" },
        { status: 400 },
      );
    }

    const calId = String(calendarId);
    const summaryStr = String(summary);
    const fromStr = String(from);
    const toStr = String(to);

    if (!CALENDAR_ID_RE.test(calId)) return badRequest("calendarId");
    if (!isSafeFreeText(summaryStr, 500)) return badRequest("summary");
    if (!ISO_DATETIME_RE.test(fromStr)) return badRequest("from");
    if (!ISO_DATETIME_RE.test(toStr)) return badRequest("to");
    if (description && !isSafeFreeText(String(description), 5000)) {
      return badRequest("description");
    }
    if (location && !isSafeFreeText(String(location), 500)) {
      return badRequest("location");
    }
    if (attendees && !isSafeFreeText(String(attendees), 2000)) {
      return badRequest("attendees");
    }

    const args = [
      "calendar",
      "create",
      calId,
      "--summary",
      summaryStr,
      "--from",
      fromStr,
      "--to",
      toStr,
    ];

    if (description) args.push("--description", String(description));
    if (location) args.push("--location", String(location));
    if (attendees) args.push("--attendees", String(attendees));
    if (withMeet) args.push("--with-meet");

    args.push("--json");

    const { stdout } = await execFileAsync(GOG_PATH, args);
    const event = JSON.parse(stdout || "{}");

    return NextResponse.json({ success: true, event });
  } catch (error) {
    logger.error("Calendar create error:", error);
    return NextResponse.json(
      {
        success: false,
        error: error instanceof Error ? error.message : String(error),
      },
      { status: 500 },
    );
  }
}

export async function DELETE(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const eventId = searchParams.get("eventId");
    const calendarId = searchParams.get("calendarId") || TEAM_CALENDAR_ID;

    if (!eventId) {
      return NextResponse.json(
        { success: false, error: "eventId is required" },
        { status: 400 },
      );
    }

    if (!CALENDAR_ID_RE.test(calendarId)) return badRequest("calendarId");
    if (!EVENT_ID_RE.test(eventId)) return badRequest("eventId");

    await execFileAsync(GOG_PATH, [
      "calendar",
      "delete",
      calendarId,
      eventId,
      "--force",
    ]);

    return NextResponse.json({ success: true });
  } catch (error) {
    logger.error("Calendar delete error:", error);
    return NextResponse.json(
      {
        success: false,
        error: error instanceof Error ? error.message : String(error),
      },
      { status: 500 },
    );
  }
}
