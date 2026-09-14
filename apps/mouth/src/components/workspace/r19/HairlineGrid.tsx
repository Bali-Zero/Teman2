import React from "react";
import { cn } from "@/lib/utils";

/**
 * The hairline grid: a 44px row with a reserved action column, and a header
 * row that is a SIBLING of the rows container rather than a `<thead>` inside
 * it. That is deliberate — it lets a later window drop a virtualized scroller
 * into the body without a sticky element living inside an absolutely
 * positioned viewport.
 *
 * Both parts share one `--cols` template, passed once to `HairlineGrid`.
 * Callers narrow it below 1360px with their own media query and move the
 * dropped columns onto the row's second line.
 *
 * This is presentation only: sorting, selection and row activation stay with
 * the page that owns the data.
 */
export function HairlineGrid({
  cols,
  children,
  className,
  style,
}: {
  /** A `grid-template-columns` value, e.g. "1.7fr 132px 1fr 92px". */
  cols: string;
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className={cn("w-full text-[13px]", className)}
      style={{ ["--cols" as string]: cols, ...style }}
    >
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
  /** CSS length for `top`; defaults to the header plus the desk strip. */
  stickyTop?: string;
  className?: string;
}) {
  return (
    <div
      role="row"
      className={cn(
        "sticky z-10 grid grid-cols-[var(--cols)] border-b border-[var(--line-control)] bg-[var(--bz-base)]",
        "[&>span]:min-w-0 [&>span]:px-2.5 [&>span]:py-2.5",
        "[&>span]:text-[10px] [&>span]:font-[650] [&>span]:uppercase [&>span]:tracking-[0.12em]",
        "[&>span]:leading-[1.25] [&>span]:text-[var(--tx-secondary)] [&>span]:[overflow-wrap:anywhere]",
        className,
      )}
      style={{ top: stickyTop ?? "calc(var(--bz-header-height, 48px) + 44px)" }}
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
 * pointer that cannot hover, because hover is the wrong gate on a tablet.
 */
export function HairlineRow({
  children,
  actions,
  touchAction,
  className,
  ...rest
}: React.HTMLAttributes<HTMLDivElement> & {
  children: React.ReactNode;
  actions?: React.ReactNode;
  touchAction?: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "group/row relative grid min-h-11 grid-cols-[var(--cols)] items-center",
        "border-b border-[var(--bz-border)] hover:bg-[var(--bz-card)]",
        "[&>span]:min-w-0 [&>span]:px-2.5",
        touchAction ? "[@media(hover:none)]:pr-12" : undefined,
        className,
      )}
      {...rest}
    >
      {children}
      {actions ? (
        <span className="flex justify-end gap-0.5 opacity-0 transition-opacity duration-100 group-hover/row:opacity-100 group-focus-within/row:opacity-100 [@media(hover:none)]:hidden">
          {actions}
        </span>
      ) : null}
      {touchAction ? (
        <span className="absolute right-0.5 top-1/2 hidden h-11 w-11 -translate-y-1/2 place-items-center rounded text-[var(--tx-secondary)] [@media(hover:none)]:grid">
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
  className,
}: {
  primary: React.ReactNode;
  secondary?: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn("flex min-w-0 flex-col justify-center gap-px", className)}
    >
      <span className="truncate font-semibold">{primary}</span>
      {secondary ? (
        <span className="truncate text-[12px] text-[var(--tx-secondary)]">
          {secondary}
        </span>
      ) : null}
    </span>
  );
}
