"use client";

import * as React from "react";
import type { CSSProperties } from "react";
import { Info } from "lucide-react";
import type { ServicePackage } from "@/data/services_data";
import {
  buildVisaLedger,
  rowCells,
  type LedgerChapter,
  type LedgerListFamily,
  type LedgerMatrixFamily,
  type LedgerMatrixRow,
} from "@/data/visa-price-ledger";

/*
 * The public visa price list, read as a ledger instead of a wall of cards:
 * five chapters (short stays, multiple entry, KITAS, KITAP, paperwork), a
 * sticky chapter index, and inside each chapter either a matrix (one service,
 * its Offshore / Onshore / Extension or 1-2-5-year variants as columns) or a
 * plain list of lines. Prices are never computed here: `renderPrice` is the
 * same PricingTool-backed resolver ServicePricing uses for its cards, and the
 * details dialog is ServicePricing's too (`onPick` hands it the row).
 *
 * Every priced cell keeps the `public-service-price-card` contract the e2e
 * suite reads (data-pricing-category / data-pricing-key, the exact figure in
 * its text, a "More Details" trigger), so the page's price surface is still
 * one element per catalogue row.
 */

interface VisaPriceLedgerProps {
  packages: ServicePackage[];
  renderPrice: (pkg: ServicePackage) => React.ReactNode;
  onPick: (pkg: ServicePackage, trigger: HTMLButtonElement) => void;
}

const CHAPTER_PREFIX = "chapter-";

const MATRIX_COLUMNS: Record<number, string> = {
  2: "md:grid-cols-[minmax(0,1.6fr)_repeat(2,minmax(0,1fr))]",
  3: "md:grid-cols-[minmax(0,1.6fr)_repeat(3,minmax(0,1fr))]",
  4: "md:grid-cols-[minmax(0,1.6fr)_repeat(4,minmax(0,1fr))]",
};

const EYEBROW: CSSProperties = {
  fontSize: "11px",
  letterSpacing: "0.22em",
  textTransform: "uppercase",
  color: "var(--text-tertiary)",
};

const SERIF: CSSProperties = { fontFamily: "var(--font-serif)" };

/** A catalogue duration/validity such as "1 year", "6 months", "12 months". */
const DURATION = /^\d+\s+(?:day|days|month|months|year|years)$/i;

/** The duration every priced cell of a row agrees on; nothing when the
 *  columns themselves are durations (1 / 2 / 5 years) or the cells differ. */
function rowValidity(cells: (ServicePackage | null)[]): string | undefined {
  const found = cells
    .filter((cell): cell is ServicePackage => cell !== null)
    .map(
      (cell) =>
        cell.features.find((feature) => DURATION.test(feature.trim())) ?? null,
    );
  if (found.length === 0 || found.some((hit) => hit === null)) return undefined;
  return new Set(found).size === 1 ? (found[0] as string) : undefined;
}

function useActiveChapter(chapters: LedgerChapter[]): string | null {
  const [active, setActive] = React.useState<string | null>(
    chapters[0]?.id ?? null,
  );
  React.useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;
    const sections = chapters
      .map((chapter) => document.getElementById(CHAPTER_PREFIX + chapter.id))
      .filter((el): el is HTMLElement => el !== null);
    const intersecting = new Set<string>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const id = entry.target.id.slice(CHAPTER_PREFIX.length);
          if (entry.isIntersecting) intersecting.add(id);
          else intersecting.delete(id);
        }
        const first = chapters.find((chapter) => intersecting.has(chapter.id));
        if (first) setActive(first.id);
      },
      { rootMargin: "-20% 0px -55% 0px" },
    );
    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, [chapters]);
  return active;
}

function DetailsButton({
  pkg,
  onPick,
}: {
  pkg: ServicePackage;
  onPick: VisaPriceLedgerProps["onPick"];
}) {
  return (
    <button
      type="button"
      aria-label={`More Details: ${pkg.name}`}
      aria-haspopup="dialog"
      onClick={(event) => onPick(pkg, event.currentTarget)}
      className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[var(--border-subtle)] text-[var(--text-secondary)] transition-colors hover:border-[var(--r19-copper)] hover:text-[var(--r19-copper)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--r19-copper)]"
    >
      <Info className="h-4 w-4" aria-hidden="true" />
    </button>
  );
}

function PopularTag() {
  return (
    <span
      className="rounded-full px-2 py-0.5 align-middle"
      style={{
        ...EYEBROW,
        fontSize: "10px",
        letterSpacing: "0.14em",
        color: "var(--r19-copper)",
        border: "1px solid var(--r19-copper)",
      }}
    >
      Most requested
    </span>
  );
}

function ListFamily({
  family,
  renderPrice,
  onPick,
}: {
  family: LedgerListFamily;
  renderPrice: VisaPriceLedgerProps["renderPrice"];
  onPick: VisaPriceLedgerProps["onPick"];
}) {
  return (
    <div>
      <h4 className="mb-2" style={EYEBROW}>
        {family.name}
      </h4>
      <ul
        className="divide-y"
        style={{
          borderTop: "1px solid var(--border-subtle)",
          borderBottom: "1px solid var(--border-subtle)",
          borderColor: "var(--border-subtle)",
        }}
      >
        {family.items.map((pkg) => (
          <li
            key={pkg.livePriceKey ?? pkg.name}
            data-testid="public-service-price-card"
            data-pricing-category={pkg.livePriceCategory}
            data-pricing-key={pkg.livePriceKey}
            className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 py-3 transition-colors hover:bg-[var(--r19-active-bg)]"
          >
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className="text-[17px] leading-tight"
                  style={{ ...SERIF, color: "var(--text-primary)" }}
                >
                  {pkg.name}
                </span>
                {pkg.popular && <PopularTag />}
              </div>
              {pkg.description && (
                <p
                  className="mt-0.5 line-clamp-1 text-[13px]"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {pkg.description}
                </p>
              )}
            </div>
            <div className="flex items-center justify-end gap-3">
              <span className="text-right tabular-nums">
                {renderPrice(pkg)}
              </span>
              <DetailsButton pkg={pkg} onPick={onPick} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function MatrixFamily({
  family,
  renderPrice,
  onPick,
}: {
  family: LedgerMatrixFamily;
  renderPrice: VisaPriceLedgerProps["renderPrice"];
  onPick: VisaPriceLedgerProps["onPick"];
}) {
  const columns = MATRIX_COLUMNS[family.columns.length] ?? MATRIX_COLUMNS[3];
  const headingId = `family-${family.id}`;
  return (
    <section aria-labelledby={headingId}>
      <div
        className={`items-end gap-x-6 pb-2 md:grid ${columns}`}
        style={{ borderBottom: "1px solid var(--border-subtle)" }}
      >
        <h4 id={headingId} style={EYEBROW}>
          {family.name}
        </h4>
        {family.columns.map((column) => (
          <div
            key={column}
            aria-hidden="true"
            className="hidden text-right md:block"
            style={EYEBROW}
          >
            {column}
          </div>
        ))}
      </div>
      {family.rows.map((row) => {
        const validity = row.variants ? undefined : rowValidity(rowCells(row));
        const popular = rowCells(row).some((cell) => cell?.popular);
        const head = (
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className="text-[17px] leading-tight"
                style={{ ...SERIF, color: "var(--text-primary)" }}
              >
                {row.name}
              </span>
              {popular && <PopularTag />}
            </div>
            {validity && (
              <p
                className="mt-0.5 text-[13px]"
                style={{ color: "var(--text-secondary)" }}
              >
                {validity}
              </p>
            )}
          </div>
        );
        if (row.variants) {
          return (
            <div
              key={row.name}
              className="py-4"
              style={{ borderBottom: "1px solid var(--border-subtle)" }}
            >
              {head}
              {row.variants.map((variant) => (
                <div
                  key={variant.label}
                  className={`mt-3 grid grid-cols-1 gap-x-6 gap-y-2 md:items-center ${columns}`}
                >
                  <div
                    className="text-[13px] md:pl-4"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {variant.label}
                  </div>
                  <Cells
                    family={family}
                    cells={variant.cells}
                    renderPrice={renderPrice}
                    onPick={onPick}
                  />
                </div>
              ))}
            </div>
          );
        }
        return (
          <div
            key={row.name}
            className={`grid grid-cols-1 gap-x-6 gap-y-2 py-4 md:items-center ${columns}`}
            style={{ borderBottom: "1px solid var(--border-subtle)" }}
          >
            {head}
            <Cells
              family={family}
              cells={row.cells}
              renderPrice={renderPrice}
              onPick={onPick}
            />
          </div>
        );
      })}
    </section>
  );
}

function Cells({
  family,
  cells,
  renderPrice,
  onPick,
}: {
  family: LedgerMatrixFamily;
  cells: LedgerMatrixRow["cells"];
  renderPrice: VisaPriceLedgerProps["renderPrice"];
  onPick: VisaPriceLedgerProps["onPick"];
}) {
  return (
    <>
      {cells.map((cell, index) =>
        cell ? (
          <div
            key={family.columns[index]}
            data-testid="public-service-price-card"
            data-pricing-category={cell.livePriceCategory}
            data-pricing-key={cell.livePriceKey}
            className="flex items-center justify-between gap-3 md:justify-end"
          >
            <span className="md:sr-only" style={EYEBROW}>
              {family.columns[index]}
            </span>
            <span className="text-right tabular-nums">{renderPrice(cell)}</span>
            <DetailsButton pkg={cell} onPick={onPick} />
          </div>
        ) : (
          <div
            key={family.columns[index]}
            aria-hidden="true"
            className="hidden justify-end md:flex"
            style={{ color: "var(--text-tertiary)" }}
          >
            &mdash;
          </div>
        ),
      )}
    </>
  );
}

function ChapterIndex({
  chapters,
  active,
}: {
  chapters: LedgerChapter[];
  active: string | null;
}) {
  const link = (chapter: LedgerChapter, current: boolean) => (
    <a
      key={chapter.id}
      href={`#${CHAPTER_PREFIX}${chapter.id}`}
      aria-current={current ? "location" : undefined}
      className={`flex items-baseline gap-3 whitespace-nowrap rounded-md px-3 py-2 text-[14px] transition-colors hover:text-[var(--r19-copper)] ${
        current
          ? "bg-[var(--r19-active-bg)] text-[var(--text-primary)] shadow-[inset_2px_0_0_var(--r19-copper)]"
          : "text-[var(--text-secondary)]"
      }`}
    >
      <span
        className="w-6 text-[15px]"
        style={{ ...SERIF, color: "var(--r19-copper)" }}
      >
        {chapter.numeral}
      </span>
      <span>{chapter.title}</span>
      <span className="ml-auto pl-3 text-[12px] tabular-nums" style={EYEBROW}>
        {chapter.count}
      </span>
    </a>
  );
  return (
    <>
      <nav
        aria-label="Price list chapters"
        className="hidden lg:col-span-3 lg:block"
      >
        <div className="sticky top-28 space-y-1">
          <p className="mb-3 px-3" style={EYEBROW}>
            Chapters
          </p>
          {chapters.map((chapter) => link(chapter, chapter.id === active))}
        </div>
      </nav>
      <nav
        aria-label="Price list chapters"
        className="sticky z-10 -mx-6 flex gap-1 overflow-x-auto px-6 py-2 lg:hidden"
        style={{
          top: "var(--public-header-height, 56px)",
          background: "var(--surface-base)",
          borderBottom: "1px solid var(--border-subtle)",
        }}
      >
        {chapters.map((chapter) => link(chapter, chapter.id === active))}
      </nav>
    </>
  );
}

export default function VisaPriceLedger({
  packages,
  renderPrice,
  onPick,
}: VisaPriceLedgerProps) {
  const ledger = React.useMemo(() => buildVisaLedger(packages), [packages]);
  const active = useActiveChapter(ledger.chapters);

  return (
    <div data-testid="visa-price-ledger">
      <p
        className="mb-10 max-w-[60ch] text-[16px] leading-relaxed"
        style={{ color: "var(--text-secondary)" }}
      >
        <span className="tabular-nums">{ledger.total}</span> services in{" "}
        {ledger.chapters.length} chapters. One all-inclusive figure for each,
        read from the Bali Zero price list.
      </p>

      <div className="grid grid-cols-1 gap-10 lg:grid-cols-12">
        <ChapterIndex chapters={ledger.chapters} active={active} />

        <div className="space-y-16 lg:col-span-9">
          {ledger.chapters.map((chapter, index) => {
            const band = index % 2 === 1;
            return (
              <section
                key={chapter.id}
                id={CHAPTER_PREFIX + chapter.id}
                aria-labelledby={`${CHAPTER_PREFIX}${chapter.id}-title`}
                className={band ? "rounded-2xl px-6 py-8 md:px-10" : ""}
                style={{
                  scrollMarginTop:
                    "calc(var(--public-header-height, 56px) + 72px)",
                  background: band ? "var(--r19-wash)" : "transparent",
                }}
              >
                <header
                  className="mb-8 flex items-start gap-5 pb-5"
                  style={{ borderBottom: "1px solid var(--border-strong)" }}
                >
                  <span
                    aria-hidden="true"
                    className="leading-none"
                    style={{
                      ...SERIF,
                      fontSize: "clamp(40px, 5vw, 56px)",
                      color: "var(--r19-copper)",
                    }}
                  >
                    {chapter.numeral}
                  </span>
                  <div className="min-w-0 flex-1">
                    <h3
                      id={`${CHAPTER_PREFIX}${chapter.id}-title`}
                      className="tracking-tight"
                      style={{
                        ...SERIF,
                        fontWeight: 500,
                        fontSize: "clamp(22px, 2.4vw, 30px)",
                        lineHeight: 1.1,
                        color: "var(--text-primary)",
                      }}
                    >
                      {chapter.title}
                    </h3>
                    <p
                      className="mt-1 text-[15px]"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      {chapter.lede}
                    </p>
                  </div>
                  <span
                    className="hidden shrink-0 pt-2 tabular-nums sm:block"
                    style={EYEBROW}
                  >
                    {chapter.count} services
                  </span>
                </header>

                <div className="space-y-10">
                  {chapter.families.map((family) =>
                    family.kind === "matrix" ? (
                      <MatrixFamily
                        key={family.id}
                        family={family}
                        renderPrice={renderPrice}
                        onPick={onPick}
                      />
                    ) : (
                      <ListFamily
                        key={family.id}
                        family={family}
                        renderPrice={renderPrice}
                        onPick={onPick}
                      />
                    ),
                  )}
                </div>
              </section>
            );
          })}
        </div>
      </div>
    </div>
  );
}
