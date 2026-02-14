import { NextRequest, NextResponse } from 'next/server';

/**
 * KBLI API Proxy Route
 *
 * Proxies KBLI data requests to the backend API.
 * This ensures reliable server-side fetching during Next.js builds.
 *
 * Route: GET /api/kbli/[code]
 * Backend: https://nuzantara-rag.fly.dev/api/v1/kbli-notebook/inspect/[code]
 */

const BACKEND_URL = 'https://nuzantara-rag.fly.dev';

export async function GET(
  request: NextRequest,
  { params }: { params: { code: string } }
) {
  const { code } = params;

  try {
    // Fetch from backend with timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10s timeout

    const response = await fetch(
      `${BACKEND_URL}/api/v1/kbli-notebook/inspect/${code}`,
      {
        signal: controller.signal,
        headers: {
          'Accept': 'application/json',
        },
      }
    );

    clearTimeout(timeoutId);

    if (!response.ok) {
      return NextResponse.json(
        { error: `Backend returned ${response.status}` },
        { status: response.status }
      );
    }

    const data = await response.json();

    // Return with cache headers
    return NextResponse.json(data, {
      headers: {
        'Cache-Control': 'public, s-maxage=86400, stale-while-revalidate=43200',
      },
    });
  } catch (error: any) {
    console.error(`[KBLI API] Failed to fetch code ${code}:`, error);

    if (error.name === 'AbortError') {
      return NextResponse.json(
        { error: 'Backend timeout' },
        { status: 504 }
      );
    }

    return NextResponse.json(
      { error: 'Failed to fetch KBLI data' },
      { status: 500 }
    );
  }
}
