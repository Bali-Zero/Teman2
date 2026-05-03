import { NextRequest, NextResponse } from "next/server";
import { logger } from "@/lib/logger";

const BACKEND_URL =
  process.env.NUZANTARA_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "https://nuzantara-rag.fly.dev";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { lat, lng } = body;

    if (typeof lat !== "number" || typeof lng !== "number") {
      return NextResponse.json(
        { error: "lat and lng required as numbers" },
        { status: 400 },
      );
    }

    const response = await fetch(`${BACKEND_URL}/api/prime/v2/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lat, lng }),
      cache: "no-store",
    });

    if (!response.ok) {
      logger.warn("Prime v2 analyze failed", {
        metadata: { status: response.status, lat, lng },
      });
      return NextResponse.json(
        { error: "upstream analyze failed" },
        { status: 502 },
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    logger.error(
      "Prime v2 analyze proxy error",
      {},
      error instanceof Error ? error : new Error(String(error)),
    );
    return NextResponse.json({ error: "Internal error" }, { status: 500 });
  }
}
