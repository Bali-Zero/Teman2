import { NextRequest, NextResponse } from 'next/server';
import { logger } from '@/lib/logger';

const BACKEND_URL =
  process.env.NUZANTARA_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  'https://nuzantara-rag.fly.dev';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Forward auth cookie
    const cookieHeader = request.headers.get('cookie') || '';
    const tokenMatch = cookieHeader.match(/nz_access_token=([^;]+)/);
    const token = tokenMatch ? tokenMatch[1] : null;

    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${BACKEND_URL}/api/prime/v2/proposal`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    logger.error(
      'Prime v2 proposal create error',
      {},
      error instanceof Error ? error : new Error(String(error))
    );
    return NextResponse.json({ error: 'Internal error' }, { status: 500 });
  }
}
