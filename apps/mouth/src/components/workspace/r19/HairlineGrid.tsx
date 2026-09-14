"use client";

/**
 * `HairlineRow` below owns real event handlers (click/keydown activation,
 * stopPropagation on its action cells) — those closures cannot cross the
 * server/client boundary, so this FILE carries "use client". `HairlineGrid`,
 * `HairlineHead`, `HairlineBody` and `CellStack` do not need it themselves
 * (no state, no hooks, no handlers of their own) and would otherwise stay
 * server-safe — they are only client components because they share this file
 * with `HairlineRow`. See the K1c-bis report for this tradeoff; a future
 * window may split `HairlineRow` into its own file if that boundary starts
 * to matter for a page's bundle.
 */

import React from "react";
import { cn } from "@/lib/utils";
import { COLLAPSE_PX, INK_HEAD_RULE } from "./tokens";

/**
 * The hairline grid: a 44px row with a reserved action column, and a header
 * row that is a SIBLING of the rows container rather than a `<thead>` inside
 * it. That is deliberate — it lets a later window drop a virtualized scroller
 * into the body without a sticky element living inside an absolutely
 * positioned viewport.
 *
 * Both parts share one `--cols` template, passed once to `HairlineGrid`.
 * Below `collapseAt` (default `COLLAPSE_PX`, 1360) the grid can narrow to
 * `colsCollapsed` on its own: pass BOTH `colsCollapsed` and a caller-supplied
 * `id` and this emits one scoped `<style>` tag that sets `--cols` under a
 * media query, hides every `[data-collapse]` cell, and reveals every
 * `[data-collapsed-meta]` cell (see `CellStack`'s `collapsed` prop) — no
 * hooks, so the component stays usable from a server-rendered tree. Passing
 * `colsCollapsed` WITHOUT `id` emits no style at all, because the selector
 * would have nothing to scope to and would collide with every other grid on
 * the page.
 *
 * This is presentation only: sorting, selection and row activation stay with
 * the page that owns the data.
 */
export function HairlineGrid({
  cols,
  colsCollapsed,
  collapseAt = COLLAPSE_PX,
  id,
  children,
  className,
  style,
}: {
  /** A `grid-template-columns` value, e.g. "1.7fr 132px 1fr 92px". */
  cols: string;
  /** A narrower `grid-template-columns` value for widths at/below `collapseAt`. */
  colsCollapsed?: string;
  /** Px width the scoped collapse style switches at. Defaults to `COLLAPSE_PX`. */
  collapseAt?: number;
  /** Caller-supplied, stable id — required for the scoped collapse style to emit. */
  id?: string;
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className={cn("w-full text-[13px]", className)}
      data-hgrid={id}
      style={{ ["--cols" as string]: cols, ...style }}
    >
      {colsCollapsed && id ? (
        <style>{`@media (max-width:${collapseAt}px){[data-hgrid="${id}"]{--cols:${colsCollapsed}}[data-hgrid="${id}"] [data-collapse]{display:none}[data-hgrid="${id}"] [data-collapsed-meta]{display:inline}}`}</style>
      ) : null}
      {children}
    </div>
  );
}

/** The sticky column heads. Give each child its own `<span>`. */
export function HairlineHead({
  children,
  stickyTop,
  className,
}: {
  children: React.ReactNode;
  /**
   * CSS length for `top`. v2 default CHANGES to `var(--bz-header-height,
   * 48px)` (was `calc(... + 44px)`) — the measured fusion render pins the
   * head at the shell header (52/97 in `fusion/MEASURE.md` §6) with the desk
   * strip scrolling away above it, rather than sticking below the strip.
   */
  stickyTop?: string;
  className?: string;
}) {
  return (
    <div
      role="row"
      className={cn(
        "sticky z-10 grid grid-cols-[var(--cols)] bg-[var(--bz-base)]",
        INK_HEAD_RULE,
        "[&>span]:min-w-0 [&>span]:px-2.5 [&>span]:py-2.5",
        "[&>span]:text-[10px] [&>span]:font-[650] [&>span]:uppercase [&>span]:tracking-[0.12em]",
        "[&>span]:leading-[1.25] [&>span]:text-[var(--tx-secondary)] [&>span]:[overflow-wrap:anywhere]",
        className,
      )}
      style={{ top: stickyTop ?? "var(--bz-header-height, 48px)" }}
    >
      {children}
    </div>
  );
}

/** The scrollable body. A virtualized list can replace its children later. */
export function HairlineBody({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={cn("block", className)}>{children}</div>;
}

/**
 * One 44px row. `actions` goes into the reserved last column and appears on
 * hover or focus; `touchAction` is the always-visible 44px fallback for a
 * pointer that cannot hover, because hover is the wrong gate on a tablet —
 * both keep the existing `[@media(hover:none)]` reveal/fallback verbatim,
 * and a 44px menu trigger stays visible under `(hover:none)`; the menu
 * itself (Escape, outside-click, focus restoration) stays page-level.
 *
 * Pass `href` and the WHOLE row activates: `role="link"`, `tabIndex={0}`,
 * `data-href`, a pointer cursor, and `onActivate?.(href)` fires on click, on
 * Enter and on Space (Space also calls `preventDefault()` so the page does
 * not scroll). This is presentation only — the row calls back, the PAGE
 * navigates. Without `href` the row stays a plain, inert div: no role, no
 * tabIndex. The `actions` and `touchAction` cells each stop propagation on
 * click and keydown, so a secondary action never also activates the row.
 */
export function HairlineRow({
  children,
  actions,
  touchAction,
  href,
  onActivate,
  className,
  onClick,
  onKeyDown,
  ...rest
}: React.HTMLAttributes<HTMLDivElement> & {
  children: React.ReactNode;
  actions?: React.ReactNode;
  touchAction?: React.ReactNode;
  /** When given, the row itself becomes activatable. */
  href?: string;
  /** Called with `href` on click/Enter/Space. The PAGE navigates. */
  onActivate?: (href: string) => void;
}) {
  const activate = () => {
    if (href) onActivate?.(href);
  };

  const handleClick = (event: React.MouseEvent<HTMLDivElement>) => {
    onClick?.(event);
    if (href) activate();
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    onKeyDown?.(event);
    if (!href) return;
    if (event.key === "Enter") {
      activate();
    } else if (event.key === " ") {
      event.preventDefault();
      activate();
    }
  };

  const stopPropagation = (event: React.SyntheticEvent) => {
    event.stopPropagation();
  };

  return (
    <div
      role={href ? "link" : undefined}
      tabIndex={href ? 0 : undefined}
      data-href={href}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      className={cn(
        "group/row relative grid min-h-11 grid-cols-[var(--cols)] items-center",
        "border-b border-[var(--bz-border)] hover:bg-[var(--bz-card)]",
        "[&>span]:min-w-0 [&>span]:px-2.5",
        href && "cursor-pointer",
        touchAction ? "[@media(hover:none)]:pr-12" : undefined,
        className,
      )}
      {...rest}
    >
      {children}
      {actions ? (
        <span
          onClick={stopPropagation}
          onKeyDown={stopPropagation}
          className="flex justify-end gap-0.5 opacity-0 transition-opacity duration-100 group-hover/row:opacity-100 group-focus-within/row:opacity-100 [@media(hover:none)]:hidden"
        >
          {actions}
        </span>
      ) : null}
      {touchAction ? (
        <span
          onClick={stopPropagation}
          onKeyDown={stopPropagation}
          className="absolute right-0.5 top-1/2 hidden h-11 w-11 -translate-y-1/2 place-items-center rounded text-[var(--tx-secondary)] [@media(hover:none)]:grid"
        >
          {touchAction}
        </span>
      ) : null}
    </div>
  );
}

/** The primary + secondary pair inside a name cell. */
export function CellStack({
  primary,
  secondary,
  collapsed,
  className,
}: {
  primary: React.ReactNode;
  secondary?: React.ReactNode;
  /**
   * Rendered inside `<span data-collapsed-meta className="hidden">` on the
   * secondary line, so a column that leaves the grid below `collapseAt`
   * reappears here — `HairlineGrid`'s scoped collapse style flips it to
   * `display:inline` under the media query.
   */
  collapsed?: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn("flex min-w-0 flex-col justify-center gap-px", className)}
    >
      <span className="truncate font-semibold">{primary}</span>
      {secondary || collapsed ? (
        <span className="truncate text-[12px] text-[var(--tx-secondary)]">
          {secondary}
          {collapsed ? (
            <span data-collapsed-meta className="hidden">
              {collapsed}
            </span>
          ) : null}
        </span>
      ) : null}
    </span>
  );
}
