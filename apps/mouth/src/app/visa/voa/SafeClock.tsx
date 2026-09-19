"use client";

import { useEffect, useState } from "react";

/**
 * GARUDA VOA — the published filing deadline, rendered as the hero of the
 * ACCEPT screen instead of a clause inside a subtitle.
 *
 * WHAT THIS DATE IS, and the two rules that shape every line below.
 *
 * 1. It is a CIVIL CALENDAR DAY in Asia/Makassar, never a UTC instant
 *    (`contracts/openapi.yaml`
 *    `AcceptedEligibilityResult.published_filing_deadline`, `x-civil-timezone:
 *    Asia/Makassar`). The contract states the trap in writing at
 *    `openapi.yaml:1227` — in `entry_date`'s description, which is where the
 *    sentence lives and NOT in the deadline's own, as the first version of
 *    this docblock claimed: "A client that derives this from a local `Date` in
 *    another zone reintroduces it here" — the defect
 *    `civil_clock.py::garuda_today` exists to prevent on the server. So "today" here is WITA's today, resolved
 *    through `Intl` with an explicit `timeZone`, and the deadline string is
 *    formatted with `timeZone: "UTC"` so a date-only ISO renders as the day
 *    it was written rather than sliding a day west. A visitor reading this
 *    page in Honolulu and one reading it in Denpasar must see the same
 *    number of days, because the counter they are both filing at is the same
 *    counter.
 *
 * 2. It is SCOPED TO ONE OFFICE. The same contract paragraph: "a surface may
 *    display this date only when the filing office is known to be Ngurah Rai;
 *    otherwise it suppresses the date and routes to WhatsApp" — and the
 *    intake collects no office at all. The office is therefore named in the
 *    copy on every branch, and the handoff line below is not decoration: it
 *    is the "otherwise" half of that sentence.
 *
 * The internal name of this mechanism, and every internal checkpoint that is
 * not this one date, stay out of the rendered strings —
 * `voa-copy.guard.test.ts` §2 enforces exactly that and this file is added to
 * its corpus in the same change.
 */

const WITA = "Asia/Makassar";

/** Four states, four visual identities. `passed` renders no countdown at all. */
export type SafeClockState = "ample" | "soon" | "today" | "passed";

const WITA_DAY = new Intl.DateTimeFormat("en-CA", {
  timeZone: WITA,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

/**
 * WITA's current civil day as `YYYY-MM-DD`.
 *
 * Built from `formatToParts` rather than the formatted string: `en-CA` yields
 * ISO order on every ICU build we have measured, but the locale is a hint and
 * the part names are the contract. Reading the parts makes the order ours.
 */
export function witaCivilDay(now: Date): string {
  const part: Record<string, string> = {};
  for (const p of WITA_DAY.formatToParts(now)) part[p.type] = p.value;
  return `${part.year}-${part.month}-${part.day}`;
}

/**
 * Whole civil days from `fromDay` to `toDay`, both `YYYY-MM-DD`.
 *
 * Both ends are pinned to UTC midnight before subtracting, so the result is
 * an exact integer count of calendar days with no zone or DST term in it —
 * the arithmetic never touches a local clock. Returns `null` on a string this
 * function cannot read, so a caller renders nothing rather than a number it
 * invented.
 */
export function civilDaysBetween(
  fromDay: string,
  toDay: string,
): number | null {
  const a = /^(\d{4})-(\d{2})-(\d{2})$/.exec(fromDay);
  const b = /^(\d{4})-(\d{2})-(\d{2})$/.exec(toDay);
  if (!a || !b) return null;
  const at = Date.UTC(Number(a[1]), Number(a[2]) - 1, Number(a[3]));
  const bt = Date.UTC(Number(b[1]), Number(b[2]) - 1, Number(b[3]));
  if (Number.isNaN(at) || Number.isNaN(bt)) return null;
  return Math.round((bt - at) / 86_400_000);
}

/** Days from WITA-today to the deadline. Negative once the day has passed. */
export function safeClockDaysLeft(deadline: string, now: Date): number | null {
  return civilDaysBetween(witaCivilDay(now), deadline);
}

export function safeClockState(daysLeft: number): SafeClockState {
  if (daysLeft < 0) return "passed";
  if (daysLeft === 0) return "today";
  if (daysLeft <= 3) return "soon";
  return "ample";
}

/**
 * A date-only ISO formatted as the day it was written.
 *
 * `timeZone: "UTC"` is load-bearing, not boilerplate: `new Date("2026-09-08")`
 * is UTC midnight, and the shared `formatDate` helper in
 * `@balizero/core/utils` renders it in the RUNTIME's zone — which turns the
 * Bali counter's 8 September into 7 September for every visitor west of
 * Greenwich. That helper is right for the timestamps it was written for and
 * wrong for a civil day, which is why this one is here instead.
 */
const DEADLINE_DAY = new Intl.DateTimeFormat("en-GB", {
  timeZone: "UTC",
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
});

export function formatCivilDay(day: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(day);
  if (!m) return day;
  return DEADLINE_DAY.format(
    new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]))),
  );
}

/**
 * Re-reads WITA's civil day on a cadence, and re-renders only when it CHANGES.
 *
 * A deadline measured in whole days does not need a per-second tick, and a
 * digit that flickers every second is a claim of precision this number does
 * not have. What it does need is to stop being stale: a visitor who leaves
 * the tab open across WITA midnight, or lands mid-flight and wakes the tab
 * hours later, must not read yesterday's count. Hence a coarse poll plus a
 * `visibilitychange` read — no midnight offset arithmetic, so there is no DST
 * or zone-shift term to get wrong.
 */
const POLL_MS = 60_000;

export function useWitaCivilDay(frozen?: Date): string {
  const [day, setDay] = useState(() => witaCivilDay(frozen ?? new Date()));

  // A frozen clock stays frozen. Without this guard the effect below would
  // immediately overwrite the seam with the real `new Date()`, so every test
  // would silently assert against today instead of the date it named — the
  // test seam would exist and prove nothing.
  const isFrozen = frozen !== undefined;

  useEffect(() => {
    if (isFrozen) return;
    const read = () => setDay(witaCivilDay(new Date()));
    const id = window.setInterval(read, POLL_MS);
    document.addEventListener("visibilitychange", read);
    read();
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", read);
    };
  }, [isFrozen]);

  return day;
}

/**
 * The hero itself.
 *
 * STATE IDENTITY (mandate accent 4: every state its own colour, never two in
 * one). The number is always `--bz-data` — that token's declared job in
 * `globals.css` is "prices/dates/order-reference text" at 11.60:1, and this
 * is a date. What separates the states is the RULE beside it plus the WORD,
 * and the three live states take three different tokens:
 *
 *   ample  (4+ days) --state-info      calm, nothing is being asked of you yet
 *   soon   (1-3)     --state-warning
 *   today  (0)       --bz-status-mark  the one red on this surface, and used
 *                                      strictly inside its own contract: a
 *                                      non-text marker (a rule, never a fill,
 *                                      never text), max one per viewport,
 *                                      always paired with the word.
 *   passed           no clock at all
 *
 * `--state-danger` is deliberately NOT one of them: it resolves to the same
 * #c46a52 as `--bz-copper-text` on this theme, and copper on this surface
 * means ownership — the person who holds your case — not a status. Two states
 * in one colour is the thing this mapping exists to avoid, and a state that
 * is indistinguishable from an unrelated meaning is the same defect wearing a
 * different name.
 *
 * `passed` renders no countdown deliberately, mirroring the overstay branch
 * of `/visa/clock/[hash]` rather than inventing a second doctrine: a page
 * that counts down to a day that is gone is not "zero days left", it is a
 * different situation, and the number would mislead. What happens next
 * depends on facts this funnel never asked for, so it hands over to a person
 * and states no consequence of its own.
 */

/**
 * `ample` and `soon` used to share this string, which left the 3px rule as
 * their only differentiator — and `--state-info` and `--state-warning`
 * composite to rgb(162,171,176) and rgb(198,175,150), **1.11:1** apart. Two
 * states in one identity, which is the exact thing accent 4 forbids, shipped
 * under a test that only compared class NAMES. The words differ now, the rule
 * widths differ, and `voa-clock-states.guard.test.ts` measures all three on
 * the CSS and the DOM rather than on the class suffix.
 */
const STATE_WORD: Record<Exclude<SafeClockState, "passed">, string> = {
  ample: "days to file",
  soon: "days left to file",
  today: "Today",
};

export interface SafeClockHeroProps {
  /** `published_filing_deadline` — a civil day in Asia/Makassar, `YYYY-MM-DD`. */
  deadline: string;
  /** Test seam. Production always reads the real clock. */
  now?: Date;
  /** Rendered under the clock; the caller owns the WhatsApp link it builds. */
  handoffHref: string;
}

export function SafeClockHero({
  deadline,
  now,
  handoffHref,
}: SafeClockHeroProps) {
  const today = useWitaCivilDay(now);
  const daysLeft = civilDaysBetween(today, deadline);

  // An unreadable deadline is not a zero — render nothing rather than a number
  // this component made up. The caller's own subtitle still carries the case.
  if (daysLeft === null) return null;

  const state = safeClockState(daysLeft);
  const day = formatCivilDay(deadline);

  if (state === "passed") {
    return (
      <section
        className="voa-clock voa-clock--passed"
        aria-label="Filing deadline"
      >
        <p className="voa-clock__word">
          The published filing day at Ngurah Rai for this check has passed.
        </p>
        <p className="voa-clock__date">It was {day}.</p>
        <p className="voa-clock__note">
          A consultant can tell you what your options are from here — it depends
          on details this form never asked for.
        </p>
        <ClockHandoff href={handoffHref} label="Message the visa desk" />
      </section>
    );
  }

  const plural = daysLeft === 1 ? "day left to file" : STATE_WORD[state];

  return (
    <section
      className={`voa-clock voa-clock--${state}`}
      aria-label="Filing deadline"
    >
      {state === "today" ? (
        <p className="voa-clock__word voa-clock__word--lead">Today</p>
      ) : (
        <p className="voa-clock__count">
          <span className="voa-clock__num">{daysLeft}</span>
          <span className="voa-clock__unit">{plural}</span>
        </p>
      )}
      <p className="voa-clock__date">
        {state === "today"
          ? `is the last published filing day at Ngurah Rai — ${day}.`
          : `${day} at Ngurah Rai — the counter's published deadline.`}
      </p>
      <p className="voa-clock__note">
        {
          "This is the one date we publish, and it is the one Ngurah Rai publishes. Filing at another office runs on that office's own deadline."
        }
      </p>
      <ClockHandoff href={handoffHref} label="Filing somewhere else?" />
    </section>
  );
}

/**
 * The handoff is its OWN control, below the prose, never a link inside it.
 *
 * The first version reached the 48px thumb floor with
 * `display: inline-flex; min-height: 48px` on an `<a>` sitting mid-sentence.
 * Measured on the promoted build at 390px, that broke the paragraph into three
 * fragments — "…runs on that office's own" / "deadline — tell us where you're
 * filing and" / "we'll confirm yours." — because a 48px-tall inline-flex box
 * cannot sit on a 1.5-line-height text line. Every unit test passed; only the
 * rendered page showed it. A tap target and a sentence want different boxes,
 * and the honest resolution is to stop asking one element to be both.
 */
function ClockHandoff({ href, label }: { href: string; label: string }) {
  return (
    <a
      className="voa-clock__handoff"
      href={href}
      target="_blank"
      rel="noopener noreferrer"
    >
      {label}
    </a>
  );
}
