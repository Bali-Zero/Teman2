import React from "react";
import { DESK_PILL, DESK_PILL_ON } from "./deskStrip";

export interface StatChip {
  key: string;
  content: React.ReactNode;
  onClick?: () => void;
  className?: string;
  style?: React.CSSProperties;
  title?: string;
  ariaLabel?: string;
  /**
   * Only meaningful for `variant="desk"`, and only on a chip that has an
   * `onClick`: a chip that can be pressed reports whether it IS pressed. It
   * becomes `aria-pressed` on the button, so the state reaches a screen reader
   * and not only an eye.
   */
  pressed?: boolean;
}

export interface StatChipsProps {
  items: Array<StatChip | false | null | undefined>;
  className?: string;
  chipClassName?: string;
  /**
   * `"desk"` is the R19 strip: square 44px outline pills, and a pressed one
   * filled with a ✓ in front of its label. Opt-in — the default branch is
   * byte-identical to what shipped, so no page changes until it asks.
   */
  variant?: "default" | "desk";
}

/**
 * Row of stat / quick-filter pills shared by workspace list pages. Chips with
 * an `onClick` render as buttons, the rest as static spans. Falsy items are
 * skipped (allows inline `cond && {…}`); per-chip `className` is appended to
 * the shared `chipClassName` base.
 */
export function StatChips({
  items,
  className = "flex flex-wrap gap-2 text-xs",
  chipClassName = "flex items-center gap-1 px-2.5 py-1 rounded-full",
  variant = "default",
}: StatChipsProps) {
  const desk = variant === "desk";
  const wrapper = desk
    ? className === "flex flex-wrap gap-2 text-xs"
      ? "flex flex-wrap items-center gap-1.5"
      : className
    : className;
  return (
    <div className={wrapper}>
      {items
        .filter((item): item is StatChip => Boolean(item))
        .map((item) => {
          const base = desk
            ? item.pressed
              ? DESK_PILL_ON
              : DESK_PILL
            : chipClassName;
          const cls = item.className ? `${base} ${item.className}` : base;
          return item.onClick ? (
            <button
              key={item.key}
              type="button"
              onClick={item.onClick}
              className={cls}
              style={desk ? undefined : item.style}
              title={item.title}
              aria-label={item.ariaLabel}
              aria-pressed={
                desk && item.pressed !== undefined ? item.pressed : undefined
              }
            >
              {desk && item.pressed && (
                // The tick is what survives greyscale, a colour-blind eye and
                // a screen reader that ignores background-color.
                <span aria-hidden="true" className="font-[800]">
                  ✓
                </span>
              )}
              {item.content}
            </button>
          ) : (
            <span
              key={item.key}
              className={cls}
              style={desk ? undefined : item.style}
              title={item.title}
              aria-label={item.ariaLabel}
            >
              {item.content}
            </span>
          );
        })}
    </div>
  );
}
