import React from "react";
import { cn } from "@/lib/utils";
import { COPPER_RULE, EYEBROW, SERIF } from "./tokens";

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
 * The 56x3 copper rule, the eyebrow, the Fraunces headline, the subtitle.
 * This is where the copper rule lives on every kita page, which is why the
 * masthead is never removed.
 */
export function Masthead({
  eyebrow,
  title,
  subtitle,
  right,
  className,
  headingClassName,
}: {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  right?: React.ReactNode;
  className?: string;
  headingClassName?: string;
}) {
  return (
    <section className={cn("flex items-start gap-4", className)}>
      <div className="min-w-0 flex-1">
        <div aria-hidden="true" className={cn("mb-4", COPPER_RULE)} />
        {eyebrow ? <Eyebrow className="mb-2">{eyebrow}</Eyebrow> : null}
        <h1
          className={cn(
            "text-[26px] leading-[1.06] tracking-[-0.03em] text-[var(--tx-pure)] md:text-[30px]",
            headingClassName,
          )}
          style={SERIF}
        >
          {title}
        </h1>
        {subtitle ? (
          <p className="mt-2 text-[13px] text-[var(--tx-secondary)]">
            {subtitle}
          </p>
        ) : null}
      </div>
      {right ? (
        <div className="flex shrink-0 items-center gap-2">{right}</div>
      ) : null}
    </section>
  );
}
