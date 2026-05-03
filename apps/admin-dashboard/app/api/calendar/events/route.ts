import { NextRequest, NextResponse } from "next/server";
import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);

const GOG_PATH = "/opt/homebrew/bin/gog";
const TEAM_CALENDAR_ID =
  "ec0863e7c14ac6bf414ec23e2aab81960ecb26823c6a8f397c664fc64901d617@group.calendar.google.com";

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const calendarId = searchParams.get("calendarId") || TEAM_CALENDAR_ID;
    const days = searchParams.get("days") || "30";
    const max = searchParams.get("max") || "50";

    const { stdout } = await execAsync(
      `${GOG_PATH} calendar events "${calendarId}" --days ${days} --max ${max} --json`,
    );

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

    console.error("Calendar API error:", error);
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

    let cmd = `${GOG_PATH} calendar create "${calendarId}" --summary "${summary}" --from "${from}" --to "${to}"`;

    if (description) cmd += ` --description "${description}"`;
    if (location) cmd += ` --location "${location}"`;
    if (attendees) cmd += ` --attendees "${attendees}"`;
    if (withMeet) cmd += ` --with-meet`;

    cmd += " --json";

    const { stdout } = await execAsync(cmd);
    const event = JSON.parse(stdout || "{}");

    return NextResponse.json({ success: true, event });
  } catch (error) {
    console.error("Calendar create error:", error);
    return NextResponse.json(
      { success: false, error: error instanceof Error ? error.message : String(error) },
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

    await execAsync(
      `${GOG_PATH} calendar delete "${calendarId}" "${eventId}" --force`,
    );

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Calendar delete error:", error);
    return NextResponse.json(
      { success: false, error: error instanceof Error ? error.message : String(error) },
      { status: 500 },
    );
  }
}
