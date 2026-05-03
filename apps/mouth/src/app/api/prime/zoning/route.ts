import { NextRequest, NextResponse } from "next/server";
import { logger } from "@/lib/logger";

const BACKEND_URL =
  process.env.NUZANTARA_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "https://nuzantara-rag.fly.dev";

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const lat = searchParams.get("lat");
  const lng = searchParams.get("lng");

  if (!lat || !lng) {
    return NextResponse.json(
      { error: "lat and lng query params required" },
      { status: 400 },
    );
  }

  const latNum = parseFloat(lat);
  const lngNum = parseFloat(lng);

  if (isNaN(latNum) || isNaN(lngNum)) {
    return NextResponse.json(
      { error: "lat and lng must be valid numbers" },
      { status: 400 },
    );
  }

  try {
    const url = `${BACKEND_URL}/api/prime/zoning?lat=${latNum}&lng=${lngNum}`;
    const response = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      next: { revalidate: 0 },
    });

    if (!response.ok) {
      logger.warn("Backend zoning request failed", {
        metadata: { status: response.status, lat: latNum, lng: lngNum },
      });
      return NextResponse.json(
        { error: "Zoning data unavailable", status: "outside_coverage" },
        { status: 200 },
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    logger.error(
      "Prime zoning API error",
      { metadata: { lat: latNum, lng: lngNum } },
      error instanceof Error ? error : new Error(String(error)),
    );
    return NextResponse.json(
      { error: "Internal error", status: "outside_coverage" },
      { status: 200 },
    );
  }
}
