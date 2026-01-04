import { NextRequest, NextResponse } from 'next/server';
import { serialize } from 'next-mdx-remote/serialize';
import remarkGfm from 'remark-gfm';
import type { Article } from '@/lib/blog/types';
import { getArticleBySlug } from '@/lib/blog/articles';

interface RouteParams {
  params: Promise<{
    category: string;
    slug: string;
  }>;
}

/**
 * Strip import statements from MDX content
 * These are handled by the component mapping, not runtime imports
 */
function stripImports(content: string): string {
  // Remove import statements (single and multi-line)
  return content
    .replace(/^import\s+[\s\S]*?from\s+['"][^'"]+['"];?\s*$/gm, '')
    .replace(/^import\s*{[\s\S]*?}\s*from\s*['"][^'"]+['"];?\s*$/gm, '')
    .trim();
}

/**
 * GET /api/blog/articles/[category]/[slug]
 * Get a single article by category and slug from local MDX files
 */
export async function GET(request: NextRequest, { params }: RouteParams) {
  try {
    const { category, slug } = await params;

    // Read article from local MDX files
    const article = await getArticleBySlug(category, slug);

    if (article) {
      // Strip import statements and serialize MDX content
      const cleanContent = stripImports(article.content);

      try {
        // Try to serialize MDX
        const mdxSource = await serialize(cleanContent, {
          mdxOptions: {
            remarkPlugins: [remarkGfm],
            development: process.env.NODE_ENV === 'development',
          },
        });

        return NextResponse.json({
          ...article,
          mdxSource, // Serialized MDX for client-side rendering
        });
      } catch (mdxError) {
        console.error('MDX serialization failed, falling back to raw content:', mdxError);
        // Fallback: return article without mdxSource (will render as plain text)
        return NextResponse.json({
          ...article,
          mdxSource: null,
          content: cleanContent, // Return cleaned content (imports stripped)
        });
      }
    }

    // Fallback to mock article for demo
    const mockArticle = getMockArticle(category, slug);
    if (mockArticle) {
      return NextResponse.json(mockArticle);
    }

    return NextResponse.json(
      { error: 'Article not found' },
      { status: 404 }
    );
  } catch (error) {
    console.error('Failed to fetch article:', error);

    // Try mock data as fallback
    const { category, slug } = await params;
    const mockArticle = getMockArticle(category, slug);
    if (mockArticle) {
      return NextResponse.json(mockArticle);
    }

    return NextResponse.json(
      { error: 'Failed to fetch article' },
      { status: 500 }
    );
  }
}

/**
 * PATCH /api/blog/articles/[category]/[slug]
 * Update an article - Not implemented for static MDX files
 */
export async function PATCH(_request: NextRequest, { params }: RouteParams) {
  const { category, slug } = await params;
  return NextResponse.json(
    { error: `Article updates not supported. Edit MDX file directly: src/content/articles/${category}/${slug}.mdx` },
    { status: 501 }
  );
}

/**
 * DELETE /api/blog/articles/[category]/[slug]
 * Delete an article - Not implemented for static MDX files
 */
export async function DELETE(_request: NextRequest, { params }: RouteParams) {
  const { category, slug } = await params;
  return NextResponse.json(
    { error: `Article deletion not supported. Delete MDX file directly: src/content/articles/${category}/${slug}.mdx` },
    { status: 501 }
  );
}

// Mock article for demo/development
function getMockArticle(category: string, slug: string): Article | null {
  const mockArticles: Record<string, Article> = {
    'immigration/golden-visa-revolution': {
      id: '1',
      slug: 'golden-visa-revolution',
      title: "The Golden Visa Revolution: Indonesia's $350K Bet on Global Talent",
      excerpt: 'Indonesia launches its Golden Visa program, offering 5-10 year stays for investors and high-net-worth individuals.',
      content: `
# The Golden Visa Revolution

Indonesia has officially launched its highly anticipated **Golden Visa** program, marking a significant shift in the nation's approach to attracting global talent and investment.

## What is the Golden Visa?

The Golden Visa is a special residency permit that allows high-net-worth individuals and investors to stay in Indonesia for **5 to 10 years** without the need for regular visa renewals.

### Investment Requirements

| Tier | Investment | Duration | Benefits |
|------|------------|----------|----------|
| Tier 1 | $350,000+ | 5 years | Full residency, work permit |
| Tier 2 | $1,000,000+ | 10 years | Full residency, work permit, fast-track citizenship |

## Key Benefits

1. **Extended Stay** - No more 60-day visa runs
2. **Work Authorization** - Legal permission to work in Indonesia
3. **Family Inclusion** - Spouse and children included
4. **Property Rights** - Enhanced property ownership options
5. **Tax Benefits** - Potential tax advantages for investors

## Application Process

The application process is streamlined through the Immigration Directorate General:

\`\`\`
1. Submit initial application online
2. Provide proof of investment/net worth
3. Complete background check
4. Attend interview (if required)
5. Receive Golden Visa
\`\`\`

## Impact on Bali's Economy

This program is expected to bring:

- **Increased foreign investment** in local businesses
- **Growth in property sector** as more foreigners can invest
- **Job creation** through new business ventures
- **Knowledge transfer** from global talent

## Expert Opinion

> "The Golden Visa represents Indonesia's commitment to becoming a global hub for innovation and investment. We expect to see significant interest from entrepreneurs, retirees, and digital nomads alike."
>
> — Immigration Expert

## Conclusion

The Golden Visa program positions Indonesia, and particularly Bali, as a premier destination for those seeking long-term residency in Southeast Asia. With its combination of lifestyle benefits and investment opportunities, it's likely to attract significant interest from global citizens.

---

*Have questions about the Golden Visa? [Contact our team](/contact) for a free consultation.*
      `,
      coverImage: '/images/blog/golden-visa.jpg',
      category: 'immigration',
      tags: ['golden-visa', 'investment', 'residency', 'indonesia'],
      author: {
        id: 'zantara-ai',
        name: 'Zantara AI',
        avatar: '/images/zantara-avatar.png',
        role: 'AI Research Assistant',
        isAI: true,
      },
      publishedAt: new Date('2024-12-20'),
      updatedAt: new Date('2024-12-20'),
      readingTime: 12,
      viewCount: 15420,
      featured: true,
      trending: true,
      aiGenerated: true,
      status: 'published',
      seoTitle: "Golden Visa Indonesia 2026: Complete Guide | Bali Zero",
      seoDescription: "Everything you need to know about Indonesia's Golden Visa program. Investment requirements, benefits, and application process explained.",
      relatedArticleIds: ['oss-2-complete-guide', 'kitas-application-2026'],
      coverImageAlt: 'Golden Visa Indonesia program',
      createdAt: new Date('2024-12-20'),
      shareCount: 234,
      likeCount: 89,
      commentCount: 12,
      locale: 'en',
    },
    'business/oss-2-complete-guide': {
      id: '2',
      slug: 'oss-2-complete-guide',
      title: 'OSS 2.0: The Complete Guide to Indonesia Business Licensing',
      excerpt: 'Everything you need to know about the Online Single Submission system for company registration.',
      content: `
# OSS 2.0: Complete Guide

The **Online Single Submission (OSS)** system is Indonesia's integrated business licensing platform. Version 2.0, also known as OSS-RBA (Risk-Based Approach), has streamlined the process significantly.

## What is OSS?

OSS is a single-window system that allows businesses to:

- Register their company
- Obtain business licenses
- Get required permits
- All in one integrated platform

## The Risk-Based Approach

Under OSS-RBA, businesses are classified by risk level:

### Low Risk
- Simple registration
- Immediate NIB (Business Identification Number)
- No additional permits required

### Medium-Low Risk
- Standard registration
- Self-declaration compliance
- Minimal documentation

### Medium-High Risk
- Verification required
- Technical standards compliance
- Inspections may be needed

### High Risk
- Full verification
- Pre-operational inspections
- Ongoing compliance monitoring

## Step-by-Step Registration

1. **Create OSS Account**
2. **Complete Company Profile**
3. **Select KBLI Codes**
4. **Submit Required Documents**
5. **Receive NIB**
6. **Obtain Sector-Specific Permits**

## Common KBLI Codes for Foreigners

| Code | Description | Risk Level |
|------|-------------|------------|
| 62011 | Software Development | Low |
| 70201 | Business Consulting | Low |
| 73100 | Advertising | Medium-Low |
| 68110 | Real Estate Agency | Medium-High |

## Timeline

- Low Risk: 1-3 days
- Medium Risk: 1-2 weeks
- High Risk: 1-3 months

---

*Need help with OSS registration? [Contact us](/contact) for professional assistance.*
      `,
      coverImage: '/images/blog/oss-guide.jpg',
      category: 'business',
      tags: ['oss', 'business-license', 'pt-pma', 'indonesia'],
      author: {
        id: '1',
        name: 'Legal Team',
        avatar: '/images/team/legal.jpg',
        role: 'Legal Advisor',
        isAI: false,
      },
      publishedAt: new Date('2024-12-18'),
      updatedAt: new Date('2024-12-18'),
      readingTime: 15,
      viewCount: 8932,
      featured: false,
      trending: true,
      aiGenerated: false,
      status: 'published',
      seoTitle: "OSS 2.0 Guide: Indonesia Business License System | Bali Zero",
      seoDescription: "Complete guide to Indonesia's OSS 2.0 system. Learn how to register your business, obtain licenses, and navigate KBLI codes.",
      relatedArticleIds: ['golden-visa-revolution', 'tax-deadlines-2026'],
      coverImageAlt: 'OSS 2.0 Business Licensing Indonesia',
      createdAt: new Date('2024-12-18'),
      shareCount: 156,
      likeCount: 67,
      commentCount: 8,
      locale: 'en',
    },
    'tax-legal/tax-deadlines-2026': {
      id: '3',
      slug: 'tax-deadlines-2026',
      title: 'Tax Deadlines 2026: What Every Expat in Indonesia Needs to Know',
      excerpt: 'Key dates and obligations for personal and corporate tax filings. Coretax system now fully operational.',
      content: `
# Tax Deadlines 2026

Stay compliant with Indonesia's tax requirements. The new **Coretax** system is now fully operational for all filings.

## Personal Tax (PPh 21)

| Deadline | Obligation |
|----------|------------|
| Monthly (10th) | Employer withholding deposit |
| Monthly (20th) | Monthly tax report (SPT Masa) via Coretax |
| March 31, 2026 | Annual personal tax return |

## Corporate Tax (PPh 25/29)

| Deadline | Obligation |
|----------|------------|
| Monthly (15th) | Installment payment |
| April 30, 2026 | Annual corporate tax return |

## VAT (PPN) - Now 12%

- Monthly reporting by the end of the following month
- Payment by the 15th of the following month
- **Note:** VAT increased to 12% as of January 2025

## Key Changes for 2026

1. **Coretax Integration** - All filings now through the new system
2. **VAT at 12%** - Full implementation from 2025
3. **NIK as NPWP** - National ID now serves as tax number
4. **Digital Services Tax** - Expanded to include more platforms
5. **Carbon Tax** - Wider industry coverage

## Penalties for Late Filing

- 2% per month for late payment
- IDR 100,000 - 1,000,000 for late reporting
- Additional penalties for intentional non-compliance

---

*Need tax assistance? [Schedule a consultation](/contact) with our tax experts.*
      `,
      coverImage: '/images/blog/tax-calendar.jpg',
      category: 'tax-legal',
      tags: ['tax', 'deadlines', 'compliance', 'indonesia', 'coretax'],
      author: {
        id: 'zantara-ai',
        name: 'Zantara AI',
        avatar: '/images/zantara-avatar.png',
        role: 'AI Research Assistant',
        isAI: true,
      },
      publishedAt: new Date('2025-12-28'),
      updatedAt: new Date('2025-12-28'),
      readingTime: 8,
      viewCount: 6234,
      featured: false,
      trending: true,
      aiGenerated: true,
      status: 'published',
      seoTitle: "Indonesia Tax Deadlines 2026: Expat Guide | Bali Zero",
      seoDescription: "Complete 2026 tax calendar for expats in Indonesia. Personal, corporate, and VAT deadlines with Coretax integration.",
      relatedArticleIds: ['oss-2-complete-guide', 'golden-visa-revolution'],
      coverImageAlt: 'Indonesia Tax Calendar 2026',
      createdAt: new Date('2025-12-28'),
      shareCount: 89,
      likeCount: 45,
      commentCount: 5,
      locale: 'en',
    },
  };

  const key = `${category}/${slug}`;
  return mockArticles[key] || null;
}
