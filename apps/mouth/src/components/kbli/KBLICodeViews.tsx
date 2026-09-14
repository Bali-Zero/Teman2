"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { LayoutGrid, List, Table2 } from "lucide-react";
import type { KBLIPanelDetail } from "@/lib/kbli-panel-detail";
import {
  DEFAULT_VERIFIED,
  DEFAULT_VIEW,
  readViewParams,
  viewParamsHref,
  writeViewParams,
  type KBLIVerifiedFilter,
  type KBLIViewType,
} from "@/lib/kbli-view-params";
import { ProvenanceBadge } from "./ProvenanceBadge";

/**
 * The sector code list, with the two controls that decide WHICH codes are shown
 * and HOW they are drawn. Used by both sector surfaces — the off-canvas panel
 * and the full page — so a filter means the same thing on either.
 *
 * ── Why the cards arrive as a ReactNode ───────────────────────────────────────
 * `cards` is the SERVER-rendered grid of KBLICard, handed down untouched. The
 * card is a Server Component reading the full KBLICode (editorial, per-scale
 * licensing, Bali L4), and re-implementing it here from the projection would
 * create a second card that disagrees with the first about disclosure — the
 * exact failure the intercepting-route design exists to prevent.
 *
 * So the cards view is not filtered by re-rendering: the server wraps each card
 * in a `[data-kbli-verified]` element and this component sets
 * `data-kbli-verified-filter` on the container, which a CSS rule in
 * styles/kbli-theme.css reads. Filtering is then a style recalculation with no
 * React work, no second data path, and no card markup owned twice.
 *
 * The table and list views ARE rendered here, from `items` — the same
 * projection the drill-down already uses, so they cost no extra payload.
 *
 * ── Layout stability ─────────────────────────────────────────────────────────
 * The toolbar sits above the scrolling content and has a fixed height, so
 * switching views never moves the controls under the pointer that is clicking
 * them. The result count lives in the toolbar for the same reason: it changes
 * text, never its box.
 */

const VERIFIED_OPTIONS: { value: KBLIVerifiedFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "verified", label: "Verified" },
  { value: "unverified", label: "Unverified" },
];

const VIEW_OPTIONS: {
  value: KBLIViewType;
  label: string;
  Icon: typeof LayoutGrid;
}[] = [
  { value: "table", label: "Table", Icon: Table2 },
  { value: "cards", label: "Cards", Icon: LayoutGrid },
  { value: "list", label: "List", Icon: List },
];

function matches(item: KBLIPanelDetail, filter: KBLIVerifiedFilter): boolean {
  if (filter === "all") return true;
  const verified = item.provenanceState === "verified";
  return filter === "verified" ? verified : !verified;
}

/**
 * A segmented control that is a real radio group: arrow keys move AND select,
 * Home/End jump to the ends, and exactly one button is in the tab order
 * (roving tabindex) so Tab leaves the group rather than walking through it —
 * the behaviour the WAI-ARIA radio group pattern specifies.
 */
function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
  testId,
}: {
  label: string;
  value: T;
  options: { value: T; label: string; Icon?: typeof LayoutGrid }[];
  onChange: (next: T) => void;
  testId: string;
}) {
  const groupId = useId();
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  const move = (delta: number) => {
    const index = options.findIndex((o) => o.value === value);
    const next =
      options[(index + delta + options.length) % options.length]!.value;
    onChange(next);
    refs.current[next]?.focus();
  };

  const onKeyDown = (event: React.KeyboardEvent) => {
    switch (event.key) {
      case "ArrowRight":
      case "ArrowDown":
        event.preventDefault();
        move(1);
        break;
      case "ArrowLeft":
      case "ArrowUp":
        event.preventDefault();
        move(-1);
        break;
      case "Home":
        event.preventDefault();
        onChange(options[0]!.value);
        refs.current[options[0]!.value]?.focus();
        break;
      case "End": {
        const last = options[options.length - 1]!.value;
        event.preventDefault();
        onChange(last);
        refs.current[last]?.focus();
        break;
      }
    }
  };

  return (
    <div className="flex min-w-0 items-center gap-2">
      <span
        id={groupId}
        className="shrink-0 text-[10px] font-bold uppercase tracking-[0.12em] text-zinc-500"
      >
        {label}
      </span>
      <div
        role="radiogroup"
        aria-labelledby={groupId}
        data-testid={testId}
        onKeyDown={onKeyDown}
        className="inline-flex shrink-0 gap-0.5 rounded-full border border-white/[0.08] bg-white/[0.03] p-0.5 backdrop-blur-md"
      >
        {options.map((option) => {
          const active = option.value === value;
          return (
            <button
              key={option.value}
              ref={(node) => {
                refs.current[option.value] = node;
              }}
              type="button"
              role="radio"
              aria-checked={active}
              tabIndex={active ? 0 : -1}
              onClick={() => onChange(option.value)}
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-medium transition-all
                          focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--kbli-accent)] ${
                            active
                              ? "border border-white/[0.14] bg-white/[0.10] text-white"
                              : "border border-transparent text-zinc-400 hover:bg-white/[0.06] hover:text-white"
                          }`}
            >
              {option.Icon ? <option.Icon size={12} aria-hidden /> : null}
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** The badge is drawn for a verified code only — an unverified one carries no
 *  claim to make. ProvenanceBadge's wording is its own and is not restated. */
function VerifiedMark({ item }: { item: KBLIPanelDetail }) {
  if (item.provenanceState !== "verified") return null;
  return <ProvenanceBadge state="verified" size="sm" />;
}

export function KBLICodeViews({
  items,
  cards,
}: {
  /** Ordered projections — the same list the cards were rendered from. */
  items: KBLIPanelDetail[];
  /** Server-rendered KBLICard grid, each card under a [data-kbli-verified]. */
  cards: React.ReactNode;
}) {
  const [verified, setVerified] =
    useState<KBLIVerifiedFilter>(DEFAULT_VERIFIED);
  const [view, setView] = useState<KBLIViewType>(DEFAULT_VIEW);

  // Both surfaces are prerendered, so the query string cannot be read on the
  // server: the first paint is always the default view and the URL is applied
  // after mount. Same shape as the panel's own `?code=` handling.
  useEffect(() => {
    const params = readViewParams(window.location.search);
    setVerified(params.verified);
    setView(params.view);
  }, []);

  const commit = useCallback(
    (next: { verified: KBLIVerifiedFilter; view: KBLIViewType }) => {
      setVerified(next.verified);
      setView(next.view);
      writeViewParams(
        viewParamsHref(window.location.pathname + window.location.search, next),
      );
    },
    [],
  );

  const shown = items.filter((item) => matches(item, verified));
  const verifiedCount = items.filter(
    (i) => i.provenanceState === "verified",
  ).length;
  const counts: Record<KBLIVerifiedFilter, number> = {
    all: items.length,
    verified: verifiedCount,
    unverified: items.length - verifiedCount,
  };

  return (
    <div>
      <div
        data-testid="kbli-code-views-toolbar"
        className="mb-4 flex flex-wrap items-center gap-x-5 gap-y-3"
      >
        <Segmented
          label="Verified status"
          value={verified}
          testId="kbli-verified-filter"
          options={VERIFIED_OPTIONS.map((o) => ({
            ...o,
            label: `${o.label} (${counts[o.value]})`,
          }))}
          onChange={(next) => commit({ verified: next, view })}
        />
        <Segmented
          label="View type"
          value={view}
          testId="kbli-view-type"
          options={VIEW_OPTIONS}
          onChange={(next) => commit({ verified, view: next })}
        />
        <p
          aria-live="polite"
          data-testid="kbli-code-views-count"
          className="text-xs text-zinc-500"
        >
          {shown.length} of {items.length}{" "}
          {items.length === 1 ? "code" : "codes"}
        </p>
      </div>

      {shown.length === 0 ? (
        <div
          data-testid="kbli-code-views-empty"
          className="rounded-2xl border border-white/[0.06] bg-white/[0.02] px-5 py-10 text-center"
        >
          <p className="text-sm font-semibold text-white">
            No codes match this filter
          </p>
          <p className="mt-1 text-xs text-zinc-500">
            This section has no{" "}
            {verified === "verified" ? "verified" : "unverified"} codes. Switch
            back to All to see all {items.length}.
          </p>
        </div>
      ) : (
        <>
          {/* Cards stay mounted and are filtered by CSS — see the note above.
              `hidden` rather than unmounting keeps the server grid intact. */}
          <div
            data-kbli-verified-filter={verified}
            hidden={view !== "cards"}
            data-testid="kbli-code-views-cards"
          >
            {cards}
          </div>

          {view === "table" && (
            <div
              className="overflow-x-auto rounded-xl border border-white/[0.06]"
              data-testid="kbli-code-views-table"
            >
              <table className="w-full min-w-[560px] border-collapse text-left text-sm">
                <thead className="sticky top-0 z-10 bg-[#1c1c1f]">
                  <tr className="text-[10px] uppercase tracking-[0.12em] text-zinc-500">
                    <th scope="col" className="px-3 py-2 font-bold">
                      Kode
                    </th>
                    <th scope="col" className="px-3 py-2 font-bold">
                      Judul
                    </th>
                    <th scope="col" className="px-3 py-2 font-bold">
                      Kategori
                    </th>
                    <th scope="col" className="px-3 py-2 font-bold">
                      Status
                    </th>
                    <th scope="col" className="px-3 py-2 font-bold">
                      Aksi
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((item, index) => (
                    <tr
                      key={item.code}
                      className={`border-t border-white/[0.06] align-top ${
                        index % 2 === 1 ? "bg-white/[0.02]" : ""
                      }`}
                    >
                      <td className="whitespace-nowrap px-3 py-2 font-mono text-xs font-bold tabular-nums text-[var(--kbli-accent)]">
                        {item.code}
                      </td>
                      <td className="px-3 py-2">
                        <span className="text-white">{item.titleEn}</span>
                        <span className="block text-xs text-zinc-500">
                          {item.titleId}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 text-xs text-zinc-400">
                        {item.riskCategory ?? "—"}
                      </td>
                      <td className="px-3 py-2">
                        {item.provenanceState === "verified" ? (
                          <VerifiedMark item={item} />
                        ) : (
                          <span className="text-xs text-zinc-500">
                            Unverified
                          </span>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-3 py-2">
                        <a
                          href={`/kbli/${item.code}`}
                          className="text-xs font-semibold text-[var(--kbli-accent)] underline-offset-2 hover:underline
                                     focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--kbli-accent)]"
                        >
                          View
                          <span className="sr-only">
                            {" "}
                            {item.code} {item.titleEn}
                          </span>
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {view === "list" && (
            <ul
              className="divide-y divide-white/[0.06]"
              data-testid="kbli-code-views-list"
            >
              {shown.map((item) => (
                <li key={item.code}>
                  <a
                    href={`/kbli/${item.code}`}
                    className="flex items-center justify-between gap-3 py-2.5 transition-colors hover:bg-white/[0.03]
                               focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--kbli-accent)]"
                  >
                    <span className="flex min-w-0 items-baseline gap-2.5">
                      <span className="shrink-0 font-mono text-xs font-bold tabular-nums text-[var(--kbli-accent)]">
                        {item.code}
                      </span>
                      <span className="truncate text-sm text-white">
                        {item.titleEn}
                      </span>
                    </span>
                    <span className="shrink-0">
                      <VerifiedMark item={item} />
                    </span>
                  </a>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
