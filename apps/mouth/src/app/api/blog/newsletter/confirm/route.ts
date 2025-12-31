import { NextRequest, NextResponse } from 'next/server';

const ZANTARA_API = process.env.ZANTARA_API_URL || 'http://localhost:8080';

/**
 * GET /api/blog/newsletter/confirm
 * Confirm newsletter subscription via email link
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const token = searchParams.get('token');

    if (!token) {
      return NextResponse.redirect(
        new URL('/insights?newsletter=error&message=missing-token', request.url)
      );
    }

    const response = await fetch(
      `${ZANTARA_API}/api/blog/newsletter/confirm?token=${encodeURIComponent(token)}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );

    if (!response.ok) {
      const errorCode = response.status === 404 ? 'invalid-token' : 'confirmation-failed';
      return NextResponse.redirect(
        new URL(`/insights?newsletter=error&message=${errorCode}`, request.url)
      );
    }

    // Redirect to success page
    return NextResponse.redirect(
      new URL('/insights?newsletter=confirmed', request.url)
    );
  } catch (error) {
    console.error('Newsletter confirmation error:', error);
    return NextResponse.redirect(
      new URL('/insights?newsletter=error&message=server-error', request.url)
    );
  }
}
