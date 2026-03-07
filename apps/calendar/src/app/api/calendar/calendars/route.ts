import { NextResponse } from "next/server";
import { listCalendars } from "@/lib/google-calendar";

export async function GET() {
  try {
    const calendars = await listCalendars();

    return NextResponse.json({ success: true, calendars });
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "Failed to fetch calendars";
    return NextResponse.json(
      { success: false, error: message },
      { status: 500 },
    );
  }
}
