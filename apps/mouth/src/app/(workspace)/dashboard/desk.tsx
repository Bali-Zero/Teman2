"use client";

/**
 * Page-local desk shapes for the kita dashboard — concept-K v2 "TEPAT FORTE"
 * (R19-KITA-20260914/fusion/concept.md §2 "02 Dashboard", render
 * fusion/02-dashboard.html).
 *
 * These are WRAPPERS, not a second visual system. Every value they use is
 * imported from `@/components/workspace/r19` (SERIF, SERIF_SECTION, TABULAR,
 * EYEBROW, StatePill) — nothing here copies a class string out of that module,
 * which is the rule that keeps a restyle a restyle.
 *
 * They exist because the shared module's v1 API cannot yet express three
 * shapes the fusion puts on this page:
 *
 *   1. a 44px KPI numeral whose value is a STRING ("Rp 1.2M", "—", "✓"), where
 *      `Numeral` v1 takes `n: number` and renders `pad2(n)` at 16px;
 *   2. a section head with a rendered ordinal in a fixed left margin;
 *   3. the 4px copper rule down the left edge of the owned queue.
 *
 * The K1 primitives window has announced `Numeral size="kpi|count|ordinal"`,
 * `NumberedList owned/ordinalTone`, `OrdinalMargin` and `LedgerSection` for
 * v2. When those land these wrappers become one-line adapters over them; the
 * page above does not change shape either way.
 *
 * COLOUR LAW (fusion §3, and the module README's four laws):
 *   copper  = the signed-in viewer is the NEXT ACTOR, derived from the viewer
 *             and the record together — never from a raw status, never from a
 *             date. An expiry or a countdown takes `warning`.
 *   slate   = ours / moving      forest = done      muted = waiting / terminal
 *   Colour never travels alone: every tone here is rendered beside a WORD.
 *   Copper is never a fill. There is no red on this page.
 */

import React from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import {
  EYEBROW,
  SERIF,
  SERIF_SECTION,
  TABULAR,
} from "@/components/workspace/r19";

/** The tones a rendered ordinal may take. `you` is ownership, nothing else. */
export type OrdinalTone = "wait" | "you" | "done";

const ORDINAL_TONE: Record<OrdinalTone, string> = {
  wait: "text-[var(--tx-secondary)]",
  you: "text-[var(--bz-copper-text)]",
  done: "text-[var(--state-success)]",
};

/**
 * A Fraunces ordinal in the row's left margin. The label is a ReactNode
 * because the fusion numbers sections `01…07` and marks the rows inside the
 * action margin `A`, `B`, `C` — the letters say "this one is not a position in
 * a list, it is a thing waiting for you".
 */
export function Ordinal({
  label,
  tone = "wait",
  className,
}: {
  label: React.ReactNode;
  tone?: OrdinalTone;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "text-[18px] leading-none tracking-[-0.02em]",
        ORDINAL_TONE[tone],
        className,
      )}
      style={{ ...SERIF, ...TABULAR }}
    >
      {label}
    </span>
  );
}

/**
 * A numbered ledger section: hairline top, a 42px ordinal margin, a Fraunces
 * section title, and an optional right slot for the meta word or the "all →"
 * link.
 *
 * `owned` draws the 4px copper rule down the whole section — the FORTE
 * owned-queue mark. It is the one place on this page copper touches a large
 * surface, and it is a RULE, not a fill.
 */
export function LedgerSection({
  ordinal,
  title,
  meta,
  right,
  owned = false,
  titleId,
  children,
  className,
}: {
  ordinal: React.ReactNode;
  title: React.ReactNode;
  meta?: React.ReactNode;
  right?: React.ReactNode;
  owned?: boolean;
  titleId?: string;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      aria-labelledby={titleId}
      className={cn(
        "border-t border-[var(--bz-border)]",
        owned && "border-l-4 border-l-[var(--bz-copper)] pl-4",
        className,
      )}
    >
      <div className="grid min-h-11 grid-cols-[34px_minmax(0,1fr)_auto] items-center gap-2.5 border-b border-[var(--bz-border)] md:grid-cols-[42px_minmax(0,1fr)_auto]">
        <Ordinal label={ordinal} tone={owned ? "you" : "wait"} />
        <h2
          id={titleId}
          className="min-w-0 truncate text-[19px] leading-[1.2] tracking-[-0.02em] text-[var(--tx-pure)]"
          style={SERIF_SECTION}
        >
          {title}
        </h2>
        <div className="flex items-center gap-3">
          {meta ? (
            <span className="hidden text-[11px] text-[var(--tx-secondary)] md:inline">
              {meta}
            </span>
          ) : null}
          {right}
        </div>
      </div>
      {children}
    </section>
  );
}

/**
 * The recurring unit: a 48px hairline row. Mark, primary/secondary stack, an
 * optional state WORD, an optional tabular trailing value, an optional action.
 *
 * Below 768px the state and trailing columns LEAVE the grid and are re-rendered
 * on the row's secondary line — moved, not hidden. That distinction is the
 * whole point: hiding them would delete the status word and the deadline for
 * every phone reader, and the concept's own 1360 collapse (§2 "03 Clients")
 * relocates a dropped column rather than dropping its content.
 */
export function LedgerRow({
  mark,
  markTone = "wait",
  primary,
  secondary,
  state,
  trailing,
  action,
  className,
}: {
  mark?: React.ReactNode;
  markTone?: OrdinalTone;
  primary: React.ReactNode;
  secondary?: React.ReactNode;
  state?: React.ReactNode;
  trailing?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "grid min-h-12 grid-cols-[34px_minmax(0,1fr)_auto] items-center gap-2.5",
        "border-b border-[var(--bz-border)] py-1.5",
        "hover:bg-[var(--bz-card-hover)] md:grid-cols-[42px_minmax(160px,1.5fr)_minmax(110px,1fr)_minmax(88px,0.7fr)_auto]",
        className,
      )}
    >
      {mark !== undefined ? (
        <Ordinal label={mark} tone={markTone} />
      ) : (
        <span aria-hidden="true" />
      )}
      <div className="min-w-0">
        {/* `span`, not `p`: callers pass block content here — the intelligence
            feed passes an `Eyebrow`, which is itself a `p`, and a nested `p`
            is invalid HTML the browser silently reparents, which showed up as
            a React hydration error in the dev-server render. */}
        <span className="block truncate text-[13px] font-[650] leading-[1.4] text-[var(--tx-pure)]">
          {primary}
        </span>
        {secondary ? (
          <span className="block truncate text-[11px] leading-[1.4] text-[var(--tx-secondary)]">
            {secondary}
          </span>
        ) : null}
        {/* The dropped columns, relocated for a phone. `md:hidden` on the
            wrapper and `hidden md:…` on the grid cells below means exactly one
            copy is in the accessibility tree at any width. */}
        {state || trailing ? (
          <span className="mt-1 flex flex-wrap items-center gap-2 md:hidden">
            {state}
            {trailing ? (
              <span
                className="text-[11px] text-[var(--tx-secondary)]"
                style={TABULAR}
              >
                {trailing}
              </span>
            ) : null}
          </span>
        ) : null}
      </div>
      <div className="hidden justify-self-start md:flex">{state}</div>
      <span
        className="hidden text-[11px] text-[var(--tx-secondary)] md:inline"
        style={TABULAR}
      >
        {trailing}
      </span>
      <div className="flex items-center justify-self-end">{action}</div>
    </div>
  );
}

/**
 * The text link at the end of a ledger row.
 *
 * It is INK by default and copper only with `tone="you"`. The fusion's own
 * render paints every `.text-link` copper, and this is a deliberate, recorded
 * departure from it: §3 lists the places copper may appear — "word, ordinal,
 * outline, stamp, or rule" — and a navigation link is none of them. A page
 * where "View all", "Read" and "Open" are all copper spends the one colour the
 * concept reserves for "you are next" on furniture, which is the same
 * dilution the fusion's own DISPOSITION cured in F3 and F10. Copper here is
 * therefore carried only by the rows inside the action margin.
 *
 * `label` gives the link its accessible NAME. Half a dozen links reading
 * "Open" are indistinguishable in a screen reader's link list, so every caller
 * that repeats a verb must name its destination.
 */
export function DeskLink({
  href,
  children,
  label,
  tone = "ink",
  external = false,
  className,
}: {
  href: string;
  children: React.ReactNode;
  /** The accessible name, when the visible text repeats across rows. */
  label?: string;
  tone?: "ink" | "you";
  external?: boolean;
  className?: string;
}) {
  const style = cn(
    "inline-flex min-h-11 items-center gap-1 whitespace-nowrap text-[12px] font-[650]",
    "hover:underline md:min-h-6",
    tone === "you" ? "text-[var(--bz-copper-text)]" : "text-[var(--tx-pure)]",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--bz-copper)]",
    className,
  );
  if (external) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={label}
        className={style}
      >
        {children}
        <span aria-hidden="true">↗</span>
        <span className="sr-only">(opens in a new tab)</span>
      </a>
    );
  }
  return (
    <Link href={href} aria-label={label} className={style}>
      {children}
      <span aria-hidden="true">→</span>
    </Link>
  );
}

/** The tones a KPI numeral may take. `you` is ownership; `warn` is urgency. */
export type KpiTone = "ink" | "you" | "warn" | "done";

const KPI_TONE: Record<KpiTone, string> = {
  ink: "text-[var(--tx-pure)]",
  you: "text-[var(--bz-copper-text)]",
  warn: "text-[var(--state-warning)]",
  done: "text-[var(--state-success)]",
};

/**
 * The 44px Fraunces numeral — the viewport peak on this page, and the reason
 * the dashboard keeps 44px where the client list drops to 22px (fusion
 * DISPOSITION F4: one peak per viewport).
 */
export function Kpi({
  label,
  value,
  sub,
  tone = "ink",
  href,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  tone?: KpiTone;
  href?: string;
}) {
  const body = (
    <>
      <span className={EYEBROW}>{label}</span>
      <span
        className={cn(
          "my-1.5 block text-[38px] leading-none tracking-[-0.03em] md:text-[44px]",
          KPI_TONE[tone],
        )}
        style={{ ...SERIF, ...TABULAR }}
      >
        {value}
      </span>
      {sub ? (
        <span className="block text-[10px] text-[var(--tx-secondary)]">
          {sub}
        </span>
      ) : null}
    </>
  );
  // Cell separators, matching the fusion's `.metric` rules: a right hairline
  // except on the last cell of each ROW, which is cell 2 on a phone and cell 4
  // on a desk — measured in the dev-server render, where a plain
  // `:not(:last-child)` left a rule hanging on the 390px right edge.
  const box =
    "min-h-[88px] min-w-0 border-[var(--bz-border)] px-4 py-3 md:min-h-24 " +
    "[&:nth-child(odd)]:border-r [&:nth-child(-n+2)]:border-b " +
    "md:[&:nth-child(-n+2)]:border-b-0 md:[&:not(:nth-child(4))]:border-r";
  if (href) {
    return (
      <Link
        href={href}
        className={cn(box, "block hover:bg-[var(--bz-card-hover)]")}
      >
        {body}
      </Link>
    );
  }
  return <div className={box}>{body}</div>;
}

/** The KPI band: a hairline strip of Kpi cells, 2 up on a phone, 4 on a desk. */
export function KpiBand({
  children,
  label,
}: {
  children: React.ReactNode;
  label: string;
}) {
  return (
    <section
      aria-label={label}
      className="grid grid-cols-2 border-y border-[var(--bz-border)] md:grid-cols-4"
    >
      {children}
    </section>
  );
}
