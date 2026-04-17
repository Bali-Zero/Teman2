"use client";

import * as React from "react";
import { Search, Loader2, X, ChevronRight } from "lucide-react";
import { kbliApi, KBLISearchResult } from "@/lib/api/kbli.api";
import { cn } from "@/lib/utils";
import { useRouter } from "next/navigation";
import { logger } from "@/lib/logger";
import { trackKBLISearch } from "@/lib/analytics";

interface Props {
  navigateOnSubmit?: boolean;
  autoFocus?: boolean;
  className?: string;
  placeholder?: string;
}

export function KBLISearch({
  navigateOnSubmit = true,
  autoFocus = false,
  className,
  placeholder = "Search KBLI codes (e.g. restaurant, villas, consulting)...",
}: Props) {
  const [query, setQuery] = React.useState("");
  const [results, setResults] = React.useState<KBLISearchResult[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);
  const [isOpen, setIsOpen] = React.useState(false);
  const [activeIndex, setActiveIndex] = React.useState(-1);
  const router = useRouter();
  const containerRef = React.useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Debounced search
  React.useEffect(() => {
    if (!query.trim() || query.length < 2) {
      setResults([]);
      setIsOpen(false);
      return;
    }

    const timer = setTimeout(async () => {
      setIsLoading(true);
      try {
        const data = await kbliApi.search(query);
        setResults(data || []);
        setIsOpen(true);
        setActiveIndex(-1);
      } catch (err) {
        logger.error("KBLI search failed:", err as Record<string, unknown>);
        setResults([]);
      } finally {
        setIsLoading(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [query]);

  const handleSelect = (code: string) => {
    setIsOpen(false);
    trackKBLISearch(query, results.length);
    if (navigateOnSubmit) {
      router.push(`/kbli/${code}`);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((prev) => Math.min(prev + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === "Enter") {
      if (activeIndex >= 0 && results[activeIndex]) {
        handleSelect(results[activeIndex].code);
      } else if (navigateOnSubmit && query.trim()) {
        trackKBLISearch(query, results.length);
        router.push(`/kbli?q=${encodeURIComponent(query)}`);
      }
    } else if (e.key === "Escape") {
      setIsOpen(false);
    }
  };

  return (
    <div ref={containerRef} className={cn("relative w-full", className)}>
      <div className="relative group">
        <div className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-500 group-focus-within:text-zinc-300 transition-colors">
          {isLoading ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Search className="w-5 h-5" />
          )}
        </div>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => query.length >= 2 && setIsOpen(true)}
          placeholder={placeholder}
          aria-label={placeholder || "Search KBLI"}
          autoFocus={autoFocus}
          className={cn(
            "w-full pl-12 pr-10 py-4 bg-white/[0.04] backdrop-blur-xl border border-white/[0.08] rounded-2xl text-white placeholder-zinc-500",
            "shadow-[0_4px_20px_rgba(0,0,0,0.3),inset_0_1px_0_rgba(255,255,255,0.04)]",
            "focus:outline-none focus:ring-2 focus:ring-[#dc2626]/20 focus:border-white/[0.15] transition-all text-lg",
          )}
        />
        {query && (
          <button
            onClick={() => {
              setQuery("");
              setResults([]);
            }}
            className="absolute right-4 top-1/2 -translate-y-1/2 p-1 rounded-full hover:bg-white/[0.08] text-zinc-500"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Results dropdown */}
      {isOpen && results.length > 0 && (
        <div className="absolute z-50 w-full mt-2 bg-[#1c1c1f]/95 backdrop-blur-2xl border border-white/[0.08] rounded-xl shadow-[0_16px_48px_rgba(0,0,0,0.5)] overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="max-h-[400px] overflow-y-auto">
            {results.map((result, index) => (
              <button
                key={result.code}
                onClick={() => handleSelect(result.code)}
                onMouseEnter={() => setActiveIndex(index)}
                className={cn(
                  "w-full flex items-start gap-4 px-4 py-3 text-left transition-all duration-200",
                  index === activeIndex
                    ? "bg-white/[0.06]"
                    : "hover:bg-white/[0.04]",
                )}
              >
                <div className="flex-shrink-0 w-12 h-12 bg-[#dc2626]/10 rounded-lg flex items-center justify-center font-bold text-[#dc2626] border border-[#dc2626]/20 text-xs">
                  {result.code}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold truncate text-white">
                    {result.title}
                  </div>
                  <div className="text-sm text-zinc-400 line-clamp-1">
                    {result.description}
                  </div>
                  <div className="flex gap-2 mt-1">
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-medium">
                      {result.pma_status}
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 font-medium">
                      {result.risk_category}
                    </span>
                  </div>
                </div>
                <ChevronRight
                  className={cn(
                    "w-4 h-4 self-center text-zinc-600",
                    index === activeIndex && "text-[#dc2626] animate-pulse",
                  )}
                />
              </button>
            ))}
          </div>
          <div className="p-3 bg-white/[0.02] border-t border-white/[0.06] flex justify-between items-center text-[10px] text-zinc-500 uppercase tracking-widest font-bold">
            <span>{results.length} KBLI codes found</span>
            <span className="flex items-center gap-1">
              Press{" "}
              <kbd className="bg-white/[0.06] px-1.5 py-0.5 rounded border border-white/[0.1] text-zinc-400">
                ENTER
              </kbd>{" "}
              to see all
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
