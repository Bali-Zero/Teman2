import { NextResponse } from 'next/server';
import { logger } from '@/lib/logger';

const BACKEND_URL =
  process.env.NUZANTARA_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  'https://nuzantara-rag.fly.dev';

export async function GET() {
  try {
    const url = `${BACKEND_URL}/api/prime/zones-geojson`;
    const response = await fetch(url, {
      headers: { 'Content-Type': 'application/json' },
      next: { revalidate: 3600 }, // Cache for 1 hour
    });

    if (!response.ok) {
      logger.warn('Backend zones-geojson request failed', {
        metadata: { status: response.status },
      });
      return NextResponse.json({ type: 'FeatureCollection', features: [] }, { status: 200 });
    }

    const data = await response.json();
    return NextResponse.json(data, {
      headers: {
        'Cache-Control': 'public, s-maxage=86400, stale-while-revalidate=604800',
      },
    });
  } catch (error) {
    logger.error(
      'Prime zones-geojson API error',
      {},
      error instanceof Error ? error : new Error(String(error))
    );
    return NextResponse.json({ type: 'FeatureCollection', features: [] }, { status: 200 });
  }
}
