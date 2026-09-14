import React from "react";
import { cn } from "@/lib/utils";
import {
  COPPER_RULE,
  EYEBROW,
  MASTHEAD_H1,
  MASTHEAD_SUB,
  SERIF,
} from "./tokens";

/** 10px/650/.14em uppercase label. Above a masthead, a strip or a section. */
export function Eyebrow({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <p className={cn(EYEBROW, className)}>{children}</p>;
}

/**
 * The 96×4 copper rule, the copper eyebrow, the 40/42 Fraunces headline, the
 * sentence, and the `actions` the page supplies. This is where the copper
 * rule lives on every kita page, which is why the masthead is never removed.
 *
 * v2 renamed the props (`subtitle` → `sub`, `right` → `actions`) — the
 * module had zero importers on origin/main when this shipped, so the rename
 * is free. `actions` holds the page's own buttons: the PRIMARY action is a
 * forest button, the SECONDARY an ink outline — the masthead supplies no
 * button styling of its own.
 */
export function Masthead({
  eyebrow,
  title,
  sub,
  actions,
  className,
  headingClassName,
}: {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  sub?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
  headingClassName?: string;
}) {
  return (
    <section
      className={cn(
        "flex flex-col items-start gap-3 mb-3.5",
        "md:mb-5 md:flex-row md:items-end md:gap-[18px]",
        className,
      )}
    >
      <div className="min-w-0 flex-1">
        <div aria-hidden="true" className={cn("mb-[11px]", COPPER_RULE)} />
        {eyebrow ? (
          <Eyebrow className="mb-2 text-[var(--bz-copper-text)]">
            {eyebrow}
          </Eyebrow>
        ) : null}
        <h1 className={cn(MASTHEAD_H1, headingClassName)} style={SERIF}>
          {title}
        </h1>
        {sub ? <p className={MASTHEAD_SUB}>{sub}</p> : null}
      </div>
      {actions ? (
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {actions}
        </div>
      ) : null}
    </section>
  );
}
