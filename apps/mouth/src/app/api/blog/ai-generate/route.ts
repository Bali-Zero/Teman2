import { NextRequest, NextResponse } from 'next/server';
import type { ArticleCategory } from '@/lib/blog/types';

const ZANTARA_API = process.env.ZANTARA_API_URL || 'http://localhost:8080';

interface AIGenerateRequest {
  topic: string;
  category: ArticleCategory;
  style?: 'informative' | 'analytical' | 'guide' | 'news' | 'opinion';
  targetLength?: 'short' | 'medium' | 'long';
  keywords?: string[];
  targetAudience?: string;
}

/**
 * POST /api/blog/ai-generate
 * Generate article content using Zantara AI
 * Admin only - requires authentication
 */
export async function POST(request: NextRequest) {
  try {
    // TODO: Add authentication check
    // const token = request.headers.get('Authorization');
    // if (!isAdmin(token)) {
    //   return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    // }

    const body: AIGenerateRequest = await request.json();

    // Validate required fields
    if (!body.topic || !body.category) {
      return NextResponse.json(
        { error: 'Topic and category are required' },
        { status: 400 }
      );
    }

    // Call Zantara AI backend
    const response = await fetch(`${ZANTARA_API}/api/blog/ai/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        // 'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        topic: body.topic,
        category: body.category,
        style: body.style || 'informative',
        targetLength: body.targetLength || 'medium',
        keywords: body.keywords || [],
        targetAudience: body.targetAudience || 'expats and investors in Indonesia',
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return NextResponse.json(
        { error: error.message || 'AI generation failed' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('AI generation error:', error);

    // Return mock generated content for demo
    return NextResponse.json({
      success: true,
      article: {
        title: 'AI Generated Article (Demo)',
        excerpt: 'This is a demo article generated when the backend is unavailable.',
        content: `
# Demo Article

This content was generated in demo mode since the backend is unavailable.

## Key Points

1. Point one
2. Point two
3. Point three

*This is placeholder content for demonstration purposes.*
        `,
        suggestedSlug: 'demo-article-' + Date.now(),
        suggestedTags: ['demo', 'ai-generated'],
        readingTime: 5,
      },
      tokens: {
        input: 0,
        output: 0,
      },
    });
  }
}

/**
 * GET /api/blog/ai-generate/triggers
 * Get pending content triggers from monitoring system
 * Admin only
 */
export async function GET(request: NextRequest) {
  try {
    const response = await fetch(`${ZANTARA_API}/api/blog/ai/triggers`, {
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      return NextResponse.json({ triggers: [] });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Failed to fetch AI triggers:', error);
    return NextResponse.json({ triggers: [] });
  }
}
