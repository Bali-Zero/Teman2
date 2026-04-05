import { NextRequest, NextResponse } from 'next/server';
import { logger } from '@/lib/logger';

const BACKEND_URL =
  process.env.NUZANTARA_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  'https://nuzantara-rag.fly.dev';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { lat, lng } = body;

    if (lat === undefined || lng === undefined) {
      return NextResponse.json({ error: 'lat and lng required in request body' }, { status: 400 });
    }

    const response = await fetch(`${BACKEND_URL}/api/prime/v2/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lat, lng }),
    });

    if (!response.ok) {
      logger.warn('Prime v2 resolve failed', {
        metadata: { status: response.status, lat, lng },
      });
      return NextResponse.json(
        { status: 'outside_coverage', error: 'Zone data unavailable' },
        { status: 200 }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    logger.error(
      'Prime v2 resolve API error',
      {},
      error instanceof Error ? error : new Error(String(error))
    );
    return NextResponse.json({ status: 'error', error: 'Internal error' }, { status: 200 });
  }
}
