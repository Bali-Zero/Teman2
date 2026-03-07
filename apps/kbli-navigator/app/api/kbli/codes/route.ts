import { NextResponse } from "next/server";
import { getAllCodes } from "@/lib/kbli-data";

export async function GET() {
  try {
    const codes = getAllCodes();

    // Validate data integrity
    if (!Array.isArray(codes)) {
      console.error("[API] getAllCodes returned non-array:", typeof codes);
      return NextResponse.json(
        { error: "Internal error: invalid data format" },
        { status: 500 },
      );
    }

    if (codes.length === 0) {
      console.error("[API] getAllCodes returned empty array");
      return NextResponse.json(
        { error: "Internal error: no codes available" },
        { status: 500 },
      );
    }

    return NextResponse.json(codes, {
      headers: {
        "Cache-Control": "public, s-maxage=86400, stale-while-revalidate=3600",
      },
    });
  } catch (error) {
    console.error("[API] Error fetching KBLI codes:", error);

    const errorMessage =
      error instanceof Error ? error.message : "Unknown error";

    return NextResponse.json(
      {
        error: "Failed to load KBLI codes",
        details:
          process.env.NODE_ENV === "development" ? errorMessage : undefined,
      },
      { status: 500 },
    );
  }
}
