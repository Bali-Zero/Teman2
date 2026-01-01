import { NextRequest, NextResponse } from 'next/server';

const ZANTARA_API = process.env.ZANTARA_API_URL || 'http://localhost:8080';

interface RouteParams {
  params: Promise<{
    category: string;
    slug: string;
  }>;
}

/**
 * POST /api/blog/articles/[category]/[slug]/views
 * Track article view
 */
export async function POST(request: NextRequest, { params }: RouteParams) {
  try {
    const { category, slug } = await params;

    // Get visitor info from headers
    const userAgent = request.headers.get('user-agent') || '';
    const referer = request.headers.get('referer') || '';
    const forwarded = request.headers.get('x-forwarded-for');
    const ip = forwarded ? forwarded.split(',')[0].trim() : 'unknown';

    // Call backend to track view
    const response = await fetch(
      `${ZANTARA_API}/api/blog/articles/${category}/${slug}/views`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          userAgent,
          referer,
          ip: hashIP(ip), // Hash for privacy
          timestamp: new Date().toISOString(),
        }),
      }
    );

    if (!response.ok) {
      // Silent fail for view tracking
      console.error('Failed to track view:', response.status);
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('View tracking error:', error);
    // Silent fail - don't disrupt user experience
    return NextResponse.json({ success: true });
  }
}

/**
 * GET /api/blog/articles/[category]/[slug]/views
 * Get article view count
 */
export async function GET(request: NextRequest, { params }: RouteParams) {
  try {
    const { category, slug } = await params;

    const response = await fetch(
      `${ZANTARA_API}/api/blog/articles/${category}/${slug}/views`,
      {
        headers: {
          'Content-Type': 'application/json',
        },
        next: { revalidate: 60 }, // Cache for 1 minute
      }
    );

    if (!response.ok) {
      return NextResponse.json({ views: 0 });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Failed to fetch view count:', error);
    return NextResponse.json({ views: 0 });
  }
}

// Simple hash function for IP privacy
function hashIP(ip: string): string {
  let hash = 0;
  for (let i = 0; i < ip.length; i++) {
    const char = ip.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return hash.toString(16);
}
