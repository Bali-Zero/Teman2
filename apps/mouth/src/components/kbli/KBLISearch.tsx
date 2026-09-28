"use client";

import * as React from "react";
import { Search, Loader2, X, AlertTriangle } from "lucide-react";
import {
  apiPmaStatusLabel,
  isApiPmaVerdictVerified,
  kbliApi,
  KBLISearchResult,
} from "@/lib/api/kbli.api";
import { cn } from "@/lib/utils";
import { useRouter } from "next/navigation";
import { logger } from "@/lib/logger";
import { trackKBLISearch } from "@/lib/analytics";
import { searchCodes } from "@/lib/kbli-search";
import {
  lightPmaStatus,
  lightRowsToSearchable,
  loadKbliLightIndex,
  type KBLILightRow,
} from "@/lib/kbli-light-index";
import { RiskBadge } from "./RiskBadge";
import { BaliStatusBadge } from "./BaliStatusBadge";

interface Props {
  navigateOnSubmit?: boolean;
  autoFocus?: boolean;
  className?: string;
  placeholder?: string;
  /** Pre-fill the search input from ?q= URL param (homepage → KBLI deep-link). */
  initialQuery?: string;
  /**
   * One-tap starting points rendered under the input. Clicking one writes the
   * term into the query, which is what actually runs the search — the chips
   * own no state of their own.
   */
  quickFilters?: string[];
}

/** How many instant (index) hits the first frame shows before the API answers. */
const INSTANT_LIMIT = 8;

/**
 * One specimen row — the same shape whether it came from the instant index or
 * from the API. `row` is the build-time index record for the code when the
 * index is loaded; it carries the verified ownership figure, risk and Bali
 * status. `api` is present when the API answered for this code.
 */
interface Specimen {
  code: string;
  row?: KBLILightRow;
  api?: KBLISearchResult;
}

export function KBLISearch({
  navigateOnSubmit = true,
  autoFocus = false,
  className,
  placeholder = "Search KBLI codes (e.g. restaurant, villas, consulting)...",
  initialQuery = "",
  quickFilters,
}: Props) {
  const [query, setQuery] = React.useState(initialQuery);
  const [results, setResults] = React.useState<KBLISearchResult[]>([]);
  // The query the API results above answer — a stale answer never replaces
  // the instant list for a newer query.
  const [answeredQuery, setAnsweredQuery] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(false);
  const [isOpen, setIsOpen] = React.useState(false);
  const [activeIndex, setActiveIndex] = React.useState(-1);
  const [searchError, setSearchError] = React.useState<string | null>(null);
  const [indexRows, setIndexRows] = React.useState<KBLILightRow[] | null>(null);
  const router = useRouter();
  const containerRef = React.useRef<HTMLDivElement>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);
  // useId, not a literal: this component is rendered more than once per page
  // (hero + inline), and two listboxes sharing an id would make every
  // aria-controls / aria-activedescendant reference point at the first one.
  const listboxId = React.useId();
  const optionId = (index: number) => `${listboxId}-option-${index}`;

  // Sync initialQuery on mount only (URL ?q= pre-fill).
  // Not in dep array — intentional: user can freely edit after mount.
  React.useEffect(() => {
    if (initialQuery) setQuery(initialQuery);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // The build-time light index (lib/kbli-light-index.ts). Fetched once; a
  // failure leaves the search API-only, exactly as it was.
  React.useEffect(() => {
    let alive = true;
    loadKbliLightIndex().then((rows) => {
      if (alive && rows) setIndexRows(rows);
    });
    return () => {
      alive = false;
    };
  }, []);

  const searchable = React.useMemo(
    () => (indexRows ? lightRowsToSearchable(indexRows) : null),
    [indexRows],
  );
  const rowByCode = React.useMemo(
    () => new Map((indexRows ?? []).map((row) => [row.c, row])),
    [indexRows],
  );

  const trimmed = query.trim();
  const searchable2 = trimmed.length >= 2 && query.length >= 2;

  // Instant first pass: the unchanged searchCodes over the light index, on
  // every keystroke, no debounce.
  const instant = React.useMemo<Specimen[]>(() => {
    if (!searchable || !searchable2) return [];
    return searchCodes(searchable, trimmed)
      .slice(0, INSTANT_LIMIT)
      .map((hit) => ({
        code: hit.code.code,
        row: rowByCode.get(hit.code.code),
      }));
  }, [searchable, searchable2, trimmed, rowByCode]);

  const apiAnswered = answeredQuery === query && results.length > 0;
  const specimens: Specimen[] = apiAnswered
    ? results.map((api) => ({
        code: api.code,
        api,
        row: rowByCode.get(api.code),
      }))
    : instant;
  const fromIndex = !apiAnswered && instant.length > 0;

  // Focus after hydration instead of via the HTML autofocus attribute. The
  // attribute is present in the server-rendered markup, so the browser focuses
  // the input while parsing and scrolls to it — which skipped the page hero on
  // every first visit. preventScroll keeps the caret without moving the page.
  React.useEffect(() => {
    if (autoFocus) inputRef.current?.focus({ preventScroll: true });
  }, [autoFocus]);

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

  // The instant list opens the dropdown on the keystroke that produced it.
  React.useEffect(() => {
    if (instant.length > 0) {
      setIsOpen(true);
      setActiveIndex(-1);
    }
  }, [instant]);

  // Debounced search — the API refines whatever the index showed.
  React.useEffect(() => {
    if (!query.trim() || query.length < 2) {
      setResults([]);
      setAnsweredQuery(null);
      setSearchError(null);
      setIsOpen(false);
      return;
    }

    const timer = setTimeout(async () => {
      setIsLoading(true);
      setSearchError(null);
      try {
        const data = await kbliApi.search(query);
        setResults(data || []);
        setAnsweredQuery(query);
        setIsOpen(true);
        setActiveIndex(-1);
      } catch (err) {
        logger.error("KBLI search failed:", err as Record<string, unknown>);
        setResults([]);
        setAnsweredQuery(null);

        // ApiClientBase throws Error(error.detail || `HTTP ${status}`).
        // 503 from a gateway/proxy may return non-JSON → detail falls back to
        // "Request failed" (client.ts L353). We treat both as service-down.
        const errMsg = err instanceof Error ? err.message : String(err);
        const isServiceDown =
          errMsg.includes("503") || errMsg.includes("Request failed");

        setSearchError(
          isServiceDown
            ? "Search is temporarily unavailable. Try asking Zantara below!"
            : "Search failed. Please try again.",
        );
        setIsOpen(true); // Keep dropdown open to show error banner

        // Pulse ZantaraFAB to draw attention to the AI fallback
        if (isServiceDown && typeof document !== "undefined") {
          const fab = document.getElementById("zantara-fab");
          if (fab) {
            fab.classList.add("animate-pulse");
            setTimeout(() => fab.classList.remove("animate-pulse"), 3000);
          }
        }
      } finally {
        setIsLoading(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [query]);

  const handleSelect = (code: string) => {
    setIsOpen(false);
    trackKBLISearch(query, specimens.length);
    if (navigateOnSubmit) {
      router.push(`/kbli/${code}`);
    }
  };

  /**
   * Quick chip → the query itself. The debounced effect above sees the new
   * query and runs the same search a typed term would, so there is exactly one
   * search path, not two.
   */
  const handleQuickFilter = (term: string) => {
    setQuery(term);
    setActiveIndex(-1);
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((prev) => Math.min(prev + 1, specimens.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === "Enter") {
      if (activeIndex >= 0 && specimens[activeIndex]) {
        handleSelect(specimens[activeIndex].code);
      } else if (navigateOnSubmit && query.trim()) {
        trackKBLISearch(query, specimens.length);
        router.push(`/kbli?q=${encodeURIComponent(query)}`);
      }
    } else if (e.key === "Escape") {
      setIsOpen(false);
    }
  };

  // With an instant list on screen, a failed API call is not an error the
  // reader needs to act on — the list stays and the footer says where it came
  // from. Without one, the banner shows exactly as before.
  const showError = Boolean(searchError) && specimens.length === 0;

  // The dropdown shows for results OR for the error banner, and the listbox
  // node lives inside it in both cases — so aria-controls resolves whenever
  // aria-expanded is true.
  const isDropdownOpen = isOpen && (specimens.length > 0 || showError);

  return (
    <div ref={containerRef} className={cn("relative w-full", className)}>
      <div className="relative">
        <div className="pointer-events-none absolute left-4 top-1/2 z-10 -translate-y-1/2 text-[var(--kbli-text-primary)]">
          {isLoading && !fromIndex ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : (
            <Search className="h-5 w-5" strokeWidth={1.75} />
          )}
        </div>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => query.length >= 2 && setIsOpen(true)}
          placeholder={placeholder}
          aria-label={placeholder || "Search KBLI"}
          role="combobox"
          aria-expanded={isDropdownOpen}
          aria-controls={listboxId}
          aria-autocomplete="list"
          aria-activedescendant={
            activeIndex >= 0 ? optionId(activeIndex) : undefined
          }
          className={cn(
            "h-[60px] w-full rounded-[var(--r19-radius-control,3px)] border border-[var(--r19-control-border,#7B817F)] bg-[var(--kbli-bg-surface)] pl-12 pr-11 text-[17px] text-[var(--kbli-text-primary)] placeholder:text-[var(--kbli-text-muted)]",
            "shadow-[inset_0_1px_0_#1d2c3b0a] transition-shadow",
            "focus:outline-none focus-visible:outline-[3px] focus-visible:outline-offset-[3px] focus-visible:outline-[var(--kbli-accent)] focus:outline-[3px] focus:outline-offset-[3px] focus:outline-[var(--kbli-accent)]",
          )}
        />
        {query && (
          <button
            type="button"
            aria-label="Clear search"
            onClick={() => {
              setQuery("");
              setResults([]);
            }}
            className="absolute right-2 top-1/2 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full text-[var(--kbli-text-muted)] hover:bg-[var(--kbli-bg-surface-hover)] hover:text-[var(--kbli-text-primary)]"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="sr-only" role="status" aria-live="polite">
        {isDropdownOpen && specimens.length > 0
          ? `${specimens.length} KBLI codes found`
          : ""}
      </div>

      {quickFilters && quickFilters.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-2">
          <span className="mr-1 text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--kbli-text-muted)]">
            Quick:
          </span>
          {quickFilters.map((filter) => (
            <button
              key={filter}
              type="button"
              onClick={() => handleQuickFilter(filter)}
              aria-label={`Search ${filter}`}
              aria-pressed={query === filter}
              className={cn(
                "min-h-[36px] rounded-full border px-3.5 text-[13px] font-medium transition-colors",
                query === filter
                  ? "border-[var(--kbli-text-primary)] bg-[var(--kbli-text-primary)] text-[var(--kbli-bg-surface)]"
                  : "border-[var(--r19-control-border,#7B817F)] bg-transparent text-[var(--kbli-text-primary)] hover:bg-[var(--kbli-bg-surface-hover)]",
              )}
            >
              {filter}
            </button>
          ))}
        </div>
      )}

      {/* Results dropdown — also shown when there is a search error */}
      {isDropdownOpen && (
        <div className="absolute z-50 mt-2 w-full overflow-hidden rounded-[var(--kbli-radius-md)] border border-[var(--kbli-border-hover)] bg-[var(--kbli-bg-surface)] shadow-[0_18px_40px_#1d2c3b24]">
          {/* Error banner — shown above results when search fails */}
          {showError && (
            <div className="flex items-start gap-2 border-b border-[var(--kbli-border)] bg-[var(--kbli-pma-restricted-bg)] px-4 py-3 text-sm">
              <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-[var(--kbli-pma-restricted)]" />
              <span className="text-[var(--kbli-pma-restricted)]">
                {searchError}
              </span>
            </div>
          )}
          <div
            id={listboxId}
            role="listbox"
            aria-label="KBLI search results"
            className="max-h-[min(440px,60vh)] overflow-y-auto overscroll-contain"
          >
            {specimens.map((s, index) => (
              <SpecimenOption
                key={s.code}
                id={optionId(index)}
                specimen={s}
                active={index === activeIndex}
                onSelect={() => handleSelect(s.code)}
                onHover={() => setActiveIndex(index)}
              />
            ))}
          </div>
          <div className="flex items-center justify-between gap-2 whitespace-nowrap border-t border-[var(--kbli-border)] bg-[var(--kbli-bg-base)] px-4 py-2.5 text-[10px] font-semibold uppercase tracking-normal text-[var(--kbli-text-muted)] sm:gap-3 sm:text-[11px] sm:tracking-[0.12em]">
            <span className="min-w-0 truncate tabular-nums">
              {specimens.length} KBLI codes found
            </span>
            <span>
              {fromIndex
                ? searchError
                  ? "Built-in index · live search offline"
                  : "Instant index · refining"
                : "Enter to see all"}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * The specimen card: the code set as a figure (Fraunces, tabular), the
 * English title with the Indonesian one under it, then the measured facts.
 * Ownership shows as a gauge ONLY for a verified verdict with a verified
 * numeric cap (the index carries `f` under exactly that gate); otherwise the
 * API's own label, or "PMA not verified" — never an inferred figure.
 */
function SpecimenOption({
  id,
  specimen,
  active,
  onSelect,
  onHover,
}: {
  id: string;
  specimen: Specimen;
  active: boolean;
  onSelect: () => void;
  onHover: () => void;
}) {
  const { code, row, api } = specimen;
  const titleEn = row?.e ?? api?.title ?? "";
  const titleId = row?.i ?? api?.description ?? "";
  const pmaLabel = api
    ? apiPmaStatusLabel(api)
    : row?.p
      ? `PMA ${lightPmaStatus(row)}`
      : "PMA not verified";
  const pmaVerified = api ? isApiPmaVerdictVerified(api) : Boolean(row?.p);
  const risk = row?.r ?? api?.risk_category;

  return (
    <button
      type="button"
      id={id}
      role="option"
      aria-selected={active}
      onClick={onSelect}
      onMouseEnter={onHover}
      className={cn(
        "grid w-full grid-cols-[4rem_1fr] gap-x-3 border-b border-[var(--kbli-border)] px-4 py-3 text-left last:border-b-0 sm:grid-cols-[5.5rem_1fr]",
        active
          ? "bg-[var(--kbli-bg-surface-hover)] shadow-[inset_3px_0_0_var(--kbli-accent)]"
          : "hover:bg-[var(--kbli-bg-card-hover)]",
      )}
    >
      <span className="kbli-figure pt-0.5 text-[22px] leading-none text-[var(--kbli-text-primary)] sm:text-[24px]">
        {code}
      </span>
      <span className="min-w-0">
        <span className="block text-[15px] font-semibold leading-snug text-[var(--kbli-text-primary)]">
          {titleEn}
        </span>
        {titleId && titleId !== titleEn && (
          <span
            lang="id"
            className="mt-0.5 block truncate text-[13px] text-[var(--kbli-text-secondary)]"
          >
            {titleId}
          </span>
        )}
      </span>
      {/* Facts span the full card width on phones (under the code too), so
          the Bali pill has room for its one line (styles/kbli-theme.css
          .kbli-specimen-bali). */}
      <span className="col-span-2 mt-2 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1.5 sm:col-span-1 sm:col-start-2">
        {typeof row?.f === "number" ? (
          <OwnershipGauge pct={row.f} />
        ) : (
          <span
            className={cn(
              "inline-flex items-center rounded-[3px] border px-1.5 py-0.5 text-[11px] font-medium",
              pmaVerified
                ? "border-[var(--kbli-border-hover)] text-[var(--kbli-text-primary)]"
                : "border-dashed border-[var(--kbli-border-hover)] text-[var(--kbli-text-muted)]",
            )}
          >
            {pmaLabel}
          </span>
        )}
        {risk && (
          <RiskBadge
            riskCategory={risk}
            size="sm"
            verificationPending={row?.rp === 1}
          />
        )}
        {row?.b && (
          <span className="kbli-specimen-bali">
            <BaliStatusBadge
              status={row.b}
              confidence={row.bc}
              needsReview={row.bn === 1}
              pmaStatus={lightPmaStatus(row) ?? "unknown"}
              scope={row.bs}
              size="sm"
            />
          </span>
        )}
      </span>
    </button>
  );
}

/** A measured bar: the verified foreign-ownership ceiling as a share of 100. */
function OwnershipGauge({ pct }: { pct: number }) {
  const clamped = Math.max(0, Math.min(100, pct));
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold tabular-nums text-[var(--kbli-text-primary)]">
      <span
        aria-hidden="true"
        className="relative inline-block h-[6px] w-12 overflow-hidden rounded-[1px] bg-[var(--kbli-bg-secondary)]"
      >
        <span
          className="absolute inset-y-0 left-0 bg-[var(--r19-structure,#233D52)]"
          style={{ width: `${clamped}%` }}
        />
      </span>
      {clamped === 100 ? "Foreign 100%" : `Foreign ≤ ${clamped}%`}
    </span>
  );
}
