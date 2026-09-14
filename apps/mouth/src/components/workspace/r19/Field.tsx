import React from "react";
import { cn } from "@/lib/utils";
import { EYEBROW, FIELD } from "./tokens";

/**
 * A labelled field on a single control boundary, copper on focus. The boundary
 * reads --line-control rather than the hairline, because a hairline under a
 * control fails SC 1.4.11's 3:1.
 *
 * The label is a real `<label htmlFor>`; the caller owns the id, the value and
 * every input attribute, so nothing here can silently change an input's type,
 * inputMode or name.
 */
export const Field = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement> & {
    id: string;
    label: React.ReactNode;
    hint?: React.ReactNode;
    wrapperClassName?: string;
  }
>(function Field(
  { id, label, hint, wrapperClassName, className, ...rest },
  ref,
) {
  return (
    <div className={cn("flex flex-col gap-1", wrapperClassName)}>
      <label htmlFor={id} className={EYEBROW}>
        {label}
      </label>
      <input id={id} ref={ref} className={cn(FIELD, className)} {...rest} />
      {hint ? (
        <span className="text-[12px] text-[var(--tx-secondary)]">{hint}</span>
      ) : null}
    </div>
  );
});
