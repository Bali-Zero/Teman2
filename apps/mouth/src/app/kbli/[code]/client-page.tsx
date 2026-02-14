'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Building2, FileText, AlertCircle, CheckCircle, ArrowRight } from 'lucide-react';

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
  const isAllowed = normalized.includes('diizinkan') || normalized.includes('allowed') || normalized.includes('terbuka');
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

export default function KBLICodePageClient({ code }: { code: string }) {
  const [data, setData] = useState<KBLIData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    async function fetchData() {
      try {
        const response = await fetch(`https://nuzantara-rag.fly.dev/api/v1/kbli-notebook/inspect/${code}`);

        if (!response.ok) {
          setError(true);
          return;
        }

        const json = await response.json();

        // Transform backend response
        setData({
          code: json.kode_kbli || code,
          title_id: json.judul || `KBLI ${code}`,
          title_en: json.title_en || json.judul || `KBLI ${code}`,
          description: json.content || json.description || '',
          category: json.kategori || json.category || 'Business',
          section: json.sektor || json.section || '',
          risk_level: json.kategori_risiko,
          pma_status: json.pma_status,
          required_licenses: json.required_licenses,
          capital_requirement: json.capital_requirement,
        });
      } catch (err) {
        console.error('Failed to fetch KBLI data:', err);
        setError(true);
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [code]);

  if (loading) {
    return (
      <div className="mx-auto min-h-screen max-w-4xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="flex items-center justify-center">
          <div className="text-center">
            <div className="mb-4 text-xl font-semibold">Loading KBLI {code}...</div>
            <div className="text-muted-foreground">Fetching business classification data</div>
          </div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="mx-auto min-h-screen max-w-4xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="text-center">
          <h1 className="mb-4 text-4xl font-bold">KBLI Code Not Found</h1>
          <p className="mb-8 text-muted-foreground">
            The KBLI code {code} could not be found or loaded.
          </p>
          <Link
            href="/kbli-explorer"
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-6 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to KBLI Explorer
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto min-h-screen max-w-4xl px-4 py-12 sm:px-6 lg:px-8">
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
  );
}
