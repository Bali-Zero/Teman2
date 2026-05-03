/**
 * IndexNow API Route - Push-based indexing for search engines
 * Notifies Bing, Yandex, and other IndexNow-compatible engines of content updates
 * Reduces AI citation delay from 14-28 days to <7 days
 *
 * Usage: POST /api/indexnow with { urls: ["/business/my-article"] }
 * Auth: Requires INDEXNOW_SECRET env var matching Authorization header
 */

import { NextRequest, NextResponse } from "next/server";

const INDEXNOW_KEY = "2633309a0003ec408c59ec48c952604f";
const BASE_URL = process.env.NEXT_PUBLIC_PUBLIC_URL || "https://balizero.com";
const INDEXNOW_SECRET = process.env.INDEXNOW_SECRET;

export async function POST(request: NextRequest) {
  // Simple auth check - only allow from internal/admin calls
  if (INDEXNOW_SECRET) {
    const auth = request.headers.get("authorization");
    if (auth !== `Bearer ${INDEXNOW_SECRET}`) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
  }

  try {
    const { urls } = await request.json();

    if (!Array.isArray(urls) || urls.length === 0) {
      return NextResponse.json(
        { error: "urls array required" },
        { status: 400 },
      );
    }

    // Normalize URLs to absolute
    const absoluteUrls = urls.map((url: string) =>
      url.startsWith("http")
        ? url
        : `${BASE_URL}${url.startsWith("/") ? "" : "/"}${url}`,
    );

    // Submit to IndexNow (Bing endpoint - shared with Yandex, Seznam, etc.)
    const response = await fetch("https://api.indexnow.org/indexnow", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        host: new URL(BASE_URL).hostname,
        key: INDEXNOW_KEY,
        keyLocation: `${BASE_URL}/${INDEXNOW_KEY}.txt`,
        urlList: absoluteUrls.slice(0, 10000), // IndexNow limit
      }),
    });

    return NextResponse.json({
      submitted: absoluteUrls.length,
      status: response.status,
      ok: response.ok,
    });
  } catch (error) {
    return NextResponse.json(
      { error: "Failed to submit to IndexNow" },
      { status: 500 },
    );
  }
}
