'use client';

import { useState, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Search, X } from 'lucide-react';

interface KBLISearchProps {
  navigateOnSubmit?: boolean;
  placeholder?: string;
  autoFocus?: boolean;
  initialQuery?: string;
}

export function KBLISearch({
  navigateOnSubmit = true,
  placeholder = "Search by code, name, or activity — e.g. 'restaurant', '56101', 'villa rental'",
  autoFocus = false,
  initialQuery = '',
}: KBLISearchProps) {
  const [query, setQuery] = useState(initialQuery);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  const handleSearch = useCallback(
    (q: string) => {
      const trimmed = q.trim();
      if (!trimmed) return;
      if (navigateOnSubmit) {
        router.push(`/kbli/search?q=${encodeURIComponent(trimmed)}`);
      }
    },
    [navigateOnSubmit, router]
  );

  const handleClear = useCallback(() => {
    setQuery('');
    inputRef.current?.focus();
  }, []);

  return (
    <div className="relative w-full">
      <div className="relative">
        <Search
          className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-[var(--foreground-muted)]"
          aria-hidden
        />
        <input
          ref={inputRef}
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && query.trim()) handleSearch(query);
            if (e.key === 'Escape') handleClear();
          }}
          placeholder={placeholder}
          autoFocus={autoFocus}
          className="w-full rounded-2xl border border-[#d4845a]/30 bg-[#1c1c1e]
                     py-4 pl-12 pr-12 text-white placeholder-zinc-400
                     outline-none transition-all duration-300
                     hover:border-[#d4845a]/60 hover:shadow-[0_0_20px_rgba(212,132,90,0.1)]
                     focus:border-[#d4845a]/80 focus:bg-[#202022] focus:animate-pulse-glow"
          aria-label="Search KBLI codes"
        />
        {query && (
          <button
            onClick={handleClear}
            className="absolute right-4 top-1/2 -translate-y-1/2 text-[var(--foreground-muted)] hover:text-[var(--foreground)]"
            aria-label="Clear search"
            type="button"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}
