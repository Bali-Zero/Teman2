import { NextRequest, NextResponse } from 'next/server';
import { logger } from '@/lib/logger';

const BACKEND_URL =
  process.env.NUZANTARA_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  'https://nuzantara-rag.fly.dev';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = request.nextUrl;
    const client_id = searchParams.get('client_id');

    if (!client_id) {
      return NextResponse.json({ error: 'client_id is required' }, { status: 400 });
    }

    // Forward auth cookie
    const cookieHeader = request.headers.get('cookie') || '';
    const tokenMatch = cookieHeader.match(/nz_access_token=([^;]+)/);
    const token = tokenMatch ? tokenMatch[1] : null;

    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const params = new URLSearchParams({ client_id });
    const response = await fetch(`${BACKEND_URL}/api/prime/v2/portfolio?${params.toString()}`, {
      headers,
    });

    if (response.status === 401 || response.status === 403) {
      return NextResponse.json(
        { client_id: 0, entities: [], risk_concentration: {}, suggestions: [], overall_health: 0 },
        { status: 200 }
      );
    }

    if (!response.ok) {
      logger.warn('Prime v2 portfolio failed', {
        metadata: { status: response.status, client_id },
      });
      return NextResponse.json(
        { client_id: 0, entities: [], risk_concentration: {}, suggestions: [], overall_health: 0 },
        { status: 200 }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    logger.error(
      'Prime v2 portfolio API error',
      {},
      error instanceof Error ? error : new Error(String(error))
    );
    return NextResponse.json(
      { client_id: 0, entities: [], risk_concentration: {}, suggestions: [], overall_health: 0 },
      { status: 200 }
    );
  }
}
