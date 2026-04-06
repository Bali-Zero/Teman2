import { NextRequest, NextResponse } from 'next/server';
import { logger } from '@/lib/logger';

const BACKEND_URL =
  process.env.NUZANTARA_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  'https://nuzantara-rag.fly.dev';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = request.nextUrl;
    const zone_code = searchParams.get('zone_code');
    const limit = searchParams.get('limit') || '10';

    if (!zone_code) {
      return NextResponse.json({ error: 'zone_code is required' }, { status: 400 });
    }

    const params = new URLSearchParams({ zone_code, limit });
    const response = await fetch(`${BACKEND_URL}/api/prime/v2/regulations?${params.toString()}`);

    if (!response.ok) {
      logger.warn('Prime v2 regulations failed', {
        metadata: { status: response.status, zone_code },
      });
      return NextResponse.json({ zone_code, regulations: [], total_found: 0 }, { status: 200 });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    logger.error(
      'Prime v2 regulations API error',
      {},
      error instanceof Error ? error : new Error(String(error))
    );
    return NextResponse.json({ zone_code: '', regulations: [], total_found: 0 }, { status: 200 });
  }
}
