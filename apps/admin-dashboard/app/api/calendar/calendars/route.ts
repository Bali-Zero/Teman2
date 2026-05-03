import { NextResponse } from "next/server";
import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);
const GOG_PATH = "/opt/homebrew/bin/gog";

export async function GET() {
  try {
    const { stdout } = await execAsync(`${GOG_PATH} calendar calendars --json`);
    const data = JSON.parse(stdout || '{"calendars":[]}');
    const calendars = data.calendars || [];

    return NextResponse.json({
      success: true,
      calendars: calendars.map((cal: { id: string; summary: string; accessRole: string }) => ({
        id: cal.id,
        name: cal.summary,
        role: cal.accessRole,
      })),
    });
  } catch (error) {
    console.error("Calendars API error:", error);
    return NextResponse.json(
      { success: false, error: error instanceof Error ? error.message : String(error) },
      { status: 500 },
    );
  }
}
