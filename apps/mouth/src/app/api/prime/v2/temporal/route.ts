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
    const period = searchParams.get('period') || '6m';
    const granularity = searchParams.get('granularity') || 'weekly';

    if (!zone_code) {
      return NextResponse.json({ error: 'zone_code is required' }, { status: 400 });
    }

    // Forward auth cookie
    const cookieHeader = request.headers.get('cookie') || '';
    const tokenMatch = cookieHeader.match(/nz_access_token=([^;]+)/);
    const token = tokenMatch ? tokenMatch[1] : null;

    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const params = new URLSearchParams({ zone_code, period, granularity });
    const response = await fetch(`${BACKEND_URL}/api/prime/v2/temporal?${params.toString()}`, {
      headers,
    });

    if (!response.ok) {
      logger.warn('Prime v2 temporal failed', {
        metadata: { status: response.status, zone_code },
      });
      return NextResponse.json(
        { zone_code, buckets: [], trend: 'stable', total_activity: 0 },
        { status: 200 }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    logger.error(
      'Prime v2 temporal API error',
      {},
      error instanceof Error ? error : new Error(String(error))
    );
    return NextResponse.json(
      { zone_code: '', buckets: [], trend: 'stable', total_activity: 0 },
      { status: 200 }
    );
  }
}
