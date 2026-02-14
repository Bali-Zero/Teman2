import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Building2, FileText, AlertCircle, CheckCircle, ArrowRight } from 'lucide-react';
import { logger } from '@/lib/logger';

/**
 * KBLI Code Landing Page (SEO-optimized)
 *
 * Dynamic route: /kbli/[code]
 * Example: /kbli/56101 → Restaurant business classification
 *
 * SEO Features:
 * - Dynamic metadata with KBLI-specific title/description
 * - JSON-LD structured data (DefinedTerm + BreadcrumbList)
 * - Internal linking to related services
 * - FAQ schema (future enhancement)
 * - Mobile-optimized content
 *
 * Data source: Backend API endpoint GET /api/v1/kbli/{code}
 */

interface KBLIData {
  code: string;
  title_id: string;
  title_en: string;
  description: string;
  category: string;
  section: string;
  risk_level?: string;
  pma_status?: string;
  required_licenses?: string[];
  capital_requirement?: string;
}

/**
 * Fetch KBLI data directly from backend
 * Using absolute URL to avoid CORS/auth issues
 */
async function getKBLIData(code: string): Promise<KBLIData | null> {
  try {
    const response = await fetch(`https://nuzantara-rag.fly.dev/api/v1/kbli-notebook/inspect/${code}`, {
      next: { revalidate: 86400 }, // Cache for 24 hours (KBLI codes rarely change)
      cache: 'force-cache', // Aggressive caching
    });

    if (!response.ok) {
      return null;
    }

    const data = await response.json();

    // Transform backend response to match our interface
    return {
      code: data.kode_kbli || code,
      title_id: data.judul || `KBLI ${code}`,
      title_en: data.title_en || data.judul || `KBLI ${code}`,
      description: data.content || data.description || '',
      category: data.kategori || data.category || 'Business',
      section: data.sektor || data.section || '',
      risk_level: data.kategori_risiko,
      pma_status: data.pma_status,
      required_licenses: data.required_licenses,
      capital_requirement: data.capital_requirement,
    };
  } catch (error) {
    logger.error(`[KBLI] Failed to fetch data for code ${code}`, { error });
    return null;
  }
}

/**
 * Generate metadata for SEO
 */
export async function generateMetadata({
  params,
}: {
  params: { code: string };
}): Promise<Metadata> {
  const data = await getKBLIData(params.code);

  if (!data) {
    return {
      title: `KBLI ${params.code} - Business Classification Code`,
      description: `Information about Indonesian business classification code (KBLI) ${params.code}.`,
    };
  }

  const title = `KBLI ${data.code}: ${data.title_en} - Indonesia Business Classification`;
  const description = `Complete guide to KBLI ${data.code} (${data.title_en}). Requirements, licenses, capital, and PMA status for ${data.category} businesses in Indonesia.`;

  return {
    title,
    description,
    keywords: [
      `kbli ${data.code}`,
      data.title_en.toLowerCase(),
      data.title_id.toLowerCase(),
      'kbli indonesia',
      'business classification',
      'pt pma',
      'company setup indonesia',
      data.category.toLowerCase(),
    ],
    openGraph: {
      title,
      description,
      type: 'article',
      url: `https://balizero.com/kbli/${data.code}`,
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
    },
  };
}

/**
 * Generate JSON-LD structured data
 */
function generateStructuredData(data: KBLIData, code: string) {
  // DefinedTerm schema for KBLI code
  const definedTerm = {
    '@context': 'https://schema.org',
    '@type': 'DefinedTerm',
    name: `KBLI ${data.code}`,
    description: data.description,
    inDefinedTermSet: 'https://kbli.data.go.id/',
    termCode: data.code,
  };

  // BreadcrumbList schema
  const breadcrumbs = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      {
        '@type': 'ListItem',
        position: 1,
        name: 'Home',
        item: 'https://balizero.com',
      },
      {
        '@type': 'ListItem',
        position: 2,
        name: 'KBLI Explorer',
        item: 'https://balizero.com/kbli-explorer',
      },
      {
        '@type': 'ListItem',
        position: 3,
        name: `KBLI ${data.code}`,
        item: `https://balizero.com/kbli/${code}`,
      },
    ],
  };

  return { definedTerm, breadcrumbs };
}

/**
 * Get risk level badge color
 */
function getRiskBadgeColor(level?: string): string {
  if (!level) return 'bg-gray-100 text-gray-700';

  const normalized = level.toLowerCase();
  if (normalized.includes('rendah') || normalized.includes('low')) {
    return 'bg-green-100 text-green-700';
  }
  if (normalized.includes('sedang') || normalized.includes('medium')) {
    return 'bg-yellow-100 text-yellow-700';
  }
  if (normalized.includes('tinggi') || normalized.includes('high')) {
    return 'bg-red-100 text-red-700';
  }
  return 'bg-gray-100 text-gray-700';
}

/**
 * Get PMA status badge
 */
function getPMABadge(status?: string) {
  if (!status) return null;

  const normalized = status.toLowerCase();
  const isAllowed = normalized.includes('diizinkan') || normalized.includes('allowed');
  const isProhibited = normalized.includes('dilarang') || normalized.includes('prohibited');

  if (isAllowed) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-3 py-1 text-sm font-medium text-green-700">
        <CheckCircle className="h-4 w-4" />
        PMA Allowed
      </span>
    );
  }

  if (isProhibited) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-3 py-1 text-sm font-medium text-red-700">
        <AlertCircle className="h-4 w-4" />
        PMA Prohibited
      </span>
    );
  }

  return (
    <span className="rounded-full bg-gray-100 px-3 py-1 text-sm font-medium text-gray-700">
      {status}
    </span>
  );
}

import KBLICodePageClient from './client-page';

export default function KBLICodePage({ params }: { params: { code: string } }) {
  // Use client-side rendering for reliable data fetching
  return (
    <>
      <KBLICodePageClient code={params.code} />
      <div className="hidden mx-auto min-h-screen max-w-4xl px-4 py-12 sm:px-6 lg:px-8">
        {/* Breadcrumb */}
        <nav className="mb-8 flex items-center gap-2 text-sm text-muted-foreground">
          <Link href="/" className="hover:text-foreground">
            Home
          </Link>
          <span>/</span>
          <Link href="/kbli-explorer" className="hover:text-foreground">
            KBLI Explorer
          </Link>
          <span>/</span>
          <span className="text-foreground">KBLI {data.code}</span>
        </nav>

        {/* Header */}
        <div className="mb-12">
          <div className="mb-4 flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
              <Building2 className="h-6 w-6 text-primary" />
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">KBLI Code</p>
              <h1 className="text-4xl font-bold tracking-tight">{data.code}</h1>
            </div>
          </div>

          <h2 className="mb-4 text-2xl font-semibold text-foreground">{data.title_en}</h2>
          {data.title_id !== data.title_en && (
            <p className="text-lg text-muted-foreground">{data.title_id}</p>
          )}
        </div>

        {/* Badges */}
        <div className="mb-8 flex flex-wrap gap-3">
          <span className="rounded-full bg-blue-100 px-4 py-1.5 text-sm font-medium text-blue-700">
            {data.category}
          </span>
          {data.section && (
            <span className="rounded-full bg-purple-100 px-4 py-1.5 text-sm font-medium text-purple-700">
              {data.section}
            </span>
          )}
          {data.risk_level && (
            <span className={`rounded-full px-4 py-1.5 text-sm font-medium ${getRiskBadgeColor(data.risk_level)}`}>
              {data.risk_level}
            </span>
          )}
          {getPMABadge(data.pma_status)}
        </div>

        {/* Description */}
        <div className="prose prose-lg mb-12 max-w-none">
          <h3 className="text-xl font-semibold">Description</h3>
          <p className="text-muted-foreground">{data.description}</p>
        </div>

        {/* Requirements Section */}
        {(data.required_licenses || data.capital_requirement) && (
          <div className="mb-12 rounded-lg border bg-card p-6">
            <h3 className="mb-4 text-xl font-semibold">Requirements</h3>

            {data.capital_requirement && (
              <div className="mb-4">
                <p className="text-sm font-medium text-muted-foreground">Minimum Capital</p>
                <p className="text-lg font-semibold">{data.capital_requirement}</p>
              </div>
            )}

            {data.required_licenses && data.required_licenses.length > 0 && (
              <div>
                <p className="mb-2 text-sm font-medium text-muted-foreground">Required Licenses</p>
                <ul className="space-y-2">
                  {data.required_licenses.map((license, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <FileText className="mt-0.5 h-4 w-4 text-muted-foreground" />
                      <span className="text-sm">{license}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* CTA Section */}
        <div className="mb-12 rounded-xl bg-gradient-to-r from-primary/10 to-primary/5 p-8">
          <h3 className="mb-2 text-2xl font-bold">Need Help Setting Up Your Business?</h3>
          <p className="mb-6 text-muted-foreground">
            Our experts can guide you through the complete PT PMA setup process, including KBLI selection,
            licensing, and compliance.
          </p>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Link
              href="/services/company"
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-6 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              Company Setup Services
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/contact"
              className="inline-flex items-center justify-center gap-2 rounded-lg border bg-background px-6 py-3 text-sm font-medium hover:bg-accent"
            >
              Contact Our Team
            </Link>
          </div>
        </div>

        {/* Related Links */}
        <div className="border-t pt-8">
          <h3 className="mb-4 text-lg font-semibold">Related Resources</h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <Link
              href="/kbli-explorer"
              className="flex items-center gap-3 rounded-lg border p-4 hover:bg-accent"
            >
              <Building2 className="h-5 w-5 text-primary" />
              <div>
                <p className="font-medium">KBLI Explorer</p>
                <p className="text-sm text-muted-foreground">Search all business codes</p>
              </div>
            </Link>
            <Link
              href="/services/company"
              className="flex items-center gap-3 rounded-lg border p-4 hover:bg-accent"
            >
              <FileText className="h-5 w-5 text-primary" />
              <div>
                <p className="font-medium">PT PMA Setup</p>
                <p className="text-sm text-muted-foreground">Company registration guide</p>
              </div>
            </Link>
          </div>
        </div>

        {/* Back button */}
        <div className="mt-12">
          <Link
            href="/kbli-explorer"
            className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to KBLI Explorer
          </Link>
        </div>
      </div>
    </>
  );
}
