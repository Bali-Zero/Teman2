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
 * v2 names the sentence `sub` and the slot `actions`. It ALSO still accepts
 * v1's `subtitle` and `right`, and that is not politeness: PR #6512 (K2a) put
 * the kita dashboard on this module between this window's base sha and the
 * branch it actually shipped from, so a rename here is a breaking change for
 * a page window K1c-bis is forbidden to edit. The v1 spellings stay until the
 * K2 desk window migrates its own page; a new caller should write `sub` and
 * `actions`, and `r19.test.tsx` pins both spellings so neither can rot.
 *
 * `actions` holds the page's own buttons: the PRIMARY action is a forest
 * button, the SECONDARY an ink outline — the masthead supplies no button
 * styling of its own.
 */
export function Masthead({
  eyebrow,
  title,
  sub,
  subtitle,
  actions,
  right,
  className,
  headingClassName,
}: {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  sub?: React.ReactNode;
  /** v1 spelling of `sub`. Accepted for the K2a dashboard; prefer `sub`. */
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  /** v1 spelling of `actions`. Accepted for the K2a dashboard; prefer `actions`. */
  right?: React.ReactNode;
  className?: string;
  headingClassName?: string;
}) {
  const sentence = sub ?? subtitle;
  const slot = actions ?? right;
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
        {sentence ? <p className={MASTHEAD_SUB}>{sentence}</p> : null}
      </div>
      {slot ? (
        <div className="flex shrink-0 flex-wrap items-center gap-2">{slot}</div>
      ) : null}
    </section>
  );
}
