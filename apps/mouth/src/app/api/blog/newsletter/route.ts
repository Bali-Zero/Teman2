import { NextRequest, NextResponse } from 'next/server';
import type { ArticleCategory } from '@/lib/blog/types';

const ZANTARA_API = process.env.ZANTARA_API_URL || 'http://localhost:8080';

interface SubscribeRequest {
  email: string;
  name?: string;
  categories?: ArticleCategory[];
  frequency?: 'instant' | 'daily' | 'weekly';
}

/**
 * POST /api/blog/newsletter
 * Subscribe to the newsletter
 */
export async function POST(request: NextRequest) {
  try {
    const body: SubscribeRequest = await request.json();

    // Validate email
    if (!body.email || !isValidEmail(body.email)) {
      return NextResponse.json(
        { error: 'Valid email address is required' },
        { status: 400 }
      );
    }

    // Proxy to backend
    const response = await fetch(`${ZANTARA_API}/api/blog/newsletter/subscribe`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        email: body.email,
        name: body.name || '',
        categories: body.categories || [],
        frequency: body.frequency || 'weekly',
      }),
    });

    if (!response.ok) {
      // Handle specific error cases
      if (response.status === 409) {
        return NextResponse.json(
          { error: 'This email is already subscribed', code: 'ALREADY_SUBSCRIBED' },
          { status: 409 }
        );
      }

      const error = await response.json().catch(() => ({}));
      return NextResponse.json(
        { error: error.message || 'Failed to subscribe' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json({
      success: true,
      message: 'Successfully subscribed! Check your email to confirm.',
      subscriberId: data.subscriberId,
    });
  } catch (error) {
    console.error('Newsletter subscription error:', error);

    // Mock success for demo when backend is unavailable
    return NextResponse.json({
      success: true,
      message: 'Successfully subscribed! (Demo mode)',
      subscriberId: `demo-${Date.now()}`,
    });
  }
}

/**
 * DELETE /api/blog/newsletter
 * Unsubscribe from the newsletter
 */
export async function DELETE(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const email = searchParams.get('email');
    const token = searchParams.get('token');

    if (!email && !token) {
      return NextResponse.json(
        { error: 'Email or unsubscribe token is required' },
        { status: 400 }
      );
    }

    const response = await fetch(`${ZANTARA_API}/api/blog/newsletter/unsubscribe`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email, token }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return NextResponse.json(
        { error: error.message || 'Failed to unsubscribe' },
        { status: response.status }
      );
    }

    return NextResponse.json({
      success: true,
      message: 'Successfully unsubscribed from the newsletter.',
    });
  } catch (error) {
    console.error('Newsletter unsubscribe error:', error);
    return NextResponse.json(
      { error: 'Failed to unsubscribe' },
      { status: 500 }
    );
  }
}

/**
 * PATCH /api/blog/newsletter
 * Update newsletter preferences
 */
export async function PATCH(request: NextRequest) {
  try {
    const body = await request.json();
    const { email, categories, frequency } = body;

    if (!email) {
      return NextResponse.json(
        { error: 'Email is required' },
        { status: 400 }
      );
    }

    const response = await fetch(`${ZANTARA_API}/api/blog/newsletter/preferences`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email, categories, frequency }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return NextResponse.json(
        { error: error.message || 'Failed to update preferences' },
        { status: response.status }
      );
    }

    return NextResponse.json({
      success: true,
      message: 'Newsletter preferences updated.',
    });
  } catch (error) {
    console.error('Newsletter preferences error:', error);
    return NextResponse.json(
      { error: 'Failed to update preferences' },
      { status: 500 }
    );
  }
}

// Email validation helper
function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}
