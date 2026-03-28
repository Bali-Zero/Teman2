'use client';

import { Suspense, useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'next/navigation';
import { KBLISearch } from '@/components/kbli/KBLISearch';
import { KBLIFilters } from '@/components/kbli/KBLIFilters';
import { KBLICard } from '@/components/kbli/KBLICard';
import { KBLIBreadcrumb } from '@/components/kbli/KBLIBreadcrumb';
import type { KBLICode, KBLISearchResult, KBLIPmaStatus } from '@/lib/kbli-types';
import { searchCodes } from '@/lib/kbli-search';
function SearchContent() {
  const searchParams = useSearchParams();
  const query = searchParams.get('q') ?? '';

  const [allCodes, setAllCodes] = useState<KBLICode[]>([]);
  const [pmaFilter, setPmaFilter] = useState<string | null>(null);
  const [transitionFilter, setTransitionFilter] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetch('/api/kbli/codes')
      .then((r) => r.json())
      .then((data: KBLICode[] | { error?: string }) => {
        // Validate response is an array
        if (Array.isArray(data)) {
          setAllCodes(data);
        } else {
          console.error('API returned non-array data:', data);
          setAllCodes([]);
        }
        setLoaded(true);
      })
      .catch((err) => {
        console.error('Failed to fetch codes:', err);
        setAllCodes([]);
        setLoaded(true);
      });
  }, []);

  // Filter + search
  const filteredCodes = useMemo(() => {
    // Guard: ensure allCodes is an array
    if (!Array.isArray(allCodes)) return [];

    let codes = allCodes;
    if (pmaFilter) {
      codes = codes.filter((c) => c.pma.status === pmaFilter);
    }
    if (transitionFilter) {
      codes = codes.filter((c) => c.transition.mappingStatus === transitionFilter);
    }
    return codes;
  }, [allCodes, pmaFilter, transitionFilter]);

  const results: KBLISearchResult[] = useMemo(() => {
    if (!query.trim() || filteredCodes.length === 0) return [];
    return searchCodes(filteredCodes, query, {
      pmaStatus: pmaFilter as KBLIPmaStatus | undefined,
    });
  }, [query, filteredCodes, pmaFilter]);

  const filterCounts = useMemo(() => {
    if (allCodes.length === 0) return undefined;

    const source = query.trim() ? results.map((r) => r.code) : allCodes;
    const pma = { all: source.length, open: 0, restricted: 0, closed: 0 };
    const transition = { new: 0, merged: 0, renamed: 0 };

    for (const code of source) {
      if (code.pma.status === 'open') pma.open++;
      else if (code.pma.status === 'restricted') pma.restricted++;
      else pma.closed++;

      const m = code.transition.mappingStatus;
      if (m === 'BPS_ONLY') transition.new++;
      else if (m === 'MATCH_CON_AGGREGAZIONE') transition.merged++;
      else if (m === 'CODICE_RINUMERATO') transition.renamed++;
    }

    return { pma, transition };
  }, [allCodes, results, query]);

  const breadcrumbs = [
    { label: 'KBLI Navigator', href: '/kbli' },
    { label: query ? `Search: ${query}` : 'Search' },
  ];

  return (
    <div className="space-y-6">
      <KBLIBreadcrumb items={breadcrumbs} />
      <KBLISearch initialQuery={query} autoFocus />
      <KBLIFilters
        pmaFilter={pmaFilter}
        transitionFilter={transitionFilter}
        onPMAChange={setPmaFilter}
        onTransitionChange={setTransitionFilter}
        counts={filterCounts}
      />

      {!loaded ? (
        <p className="text-center text-sm text-[var(--foreground-muted)]">Loading codes...</p>
      ) : !query.trim() ? (
        <p className="text-center text-sm text-[var(--foreground-muted)]">
          Enter a search term above to find KBLI codes.
        </p>
      ) : results.length === 0 ? (
        <div className="py-12 text-center">
          <p className="text-lg text-[var(--foreground-secondary)]">
            No results for &quot;{query}&quot;
          </p>
          <p className="mt-2 text-sm text-[var(--foreground-muted)]">
            Try a different search term, a 5-digit code, or browse by sector.
          </p>
        </div>
      ) : (
        <>
          <p
            className="text-sm text-[var(--foreground-muted)]"
            aria-live="polite"
            aria-atomic="true"
          >
            {results.length} result{results.length !== 1 ? 's' : ''} for &quot;
            {query}&quot;
          </p>
          <div
            className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
            aria-label={`Search results for ${query}`}
          >
            {results.map((r) => (
              <KBLICard key={r.code.code} code={r.code} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export default function KBLISearchPage() {
  return (
    <Suspense
      fallback={
        <p className="py-12 text-center text-sm text-[var(--foreground-muted)]">Loading...</p>
      }
    >
      <SearchContent />
    </Suspense>
  );
}
