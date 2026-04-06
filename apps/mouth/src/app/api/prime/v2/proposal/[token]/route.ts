import { NextRequest, NextResponse } from 'next/server';
import { logger } from '@/lib/logger';

const BACKEND_URL =
  process.env.NUZANTARA_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  'https://nuzantara-rag.fly.dev';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ token: string }> }
) {
  try {
    const { token } = await params;

    const response = await fetch(`${BACKEND_URL}/api/prime/v2/proposal/${token}`);

    if (!response.ok) {
      logger.warn('Prime v2 proposal fetch failed', {
        metadata: { status: response.status },
      });
      return NextResponse.json({ error: 'not_found' }, { status: 200 });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    logger.error(
      'Prime v2 proposal fetch error',
      {},
      error instanceof Error ? error : new Error(String(error))
    );
    return NextResponse.json({ error: 'Internal error' }, { status: 200 });
  }
}
