"use client";

import { useVoaLocale } from "./useVoaLocale";
import { voaCopy, type VoaCopyKey } from "./voa-copy";

/**
 * GARUDA VOA — what happens next, and what we do not promise.
 *
 * The mandate's third accent, and the hardest one to build honestly: a
 * purchase funnel earns trust by being specific about the thing it does and
 * explicit about the thing it cannot do. Everything below is derivable from a
 * surface that exists in this repo — no step is aspirational:
 *
 *   1. upload      `visa/voa/upload/[resultId]`, and `UploadFlow`'s own
 *                  `unreadable` branch is why "we check it can be read" is a
 *                  real step and not a reassurance
 *   2. pay once    `checkout/[resultId]`, one all-inclusive `price_idr`
 *   3. we file     at the office the verdict's `published_filing_deadline` is
 *                  scoped to (`openapi.yaml` `x-published-by-office`)
 *   4. you follow  `orders/[orderId]`, the parcel tracker, and `DeliveredPanel`
 *                  states delivery goes to the email on file
 *
 * WHAT IS DELIBERATELY ABSENT. No processing time, anywhere, in any form — the
 * corner's banned-claims list forbids "dijamin 24 jam" and this repo has
 * already retired one unmeasured response-time promise from another surface
 * (`TrustBand`'s docblock records it). No approval likelihood, no count of
 * cases handled, no named consultant: practice assignment routes through
 * `assign_lead`, but that wiring is an OPEN ledger row — nothing constructs
 * the adapter yet — so naming a person who will own the file would be a
 * promise the system cannot currently keep. What is said instead is what the
 * system does today.
 *
 * The "cannot promise" half is not a disclaimer in small print. It is the part
 * a copycat will not write, which is exactly why it belongs at the same weight
 * as the rest.
 */

/**
 * THE DATE ABOVE MAY NOT BE ABOVE. `[hash]/page.tsx` renders `SafeClockHero`
 * only when the verdict carries a `published_filing_deadline`; without one the
 * page's own subtitle already says "We'll confirm your exact filing deadline
 * before you pay". Copy that points at a hero which did not render is the
 * quietest way a funnel starts lying, so the two date-bearing sentences have a
 * second form and the caller passes which one is true.
 */
function stepKeys(hasDeadline: boolean): { n: string; key: VoaCopyKey }[] {
  return [
    { n: "1", key: "next.step1" },
    { n: "2", key: "next.step2" },
    { n: "3", key: hasDeadline ? "next.step3" : "next.step3.noDeadline" },
    { n: "4", key: "next.step4" },
  ];
}

function limitKeys(hasDeadline: boolean): VoaCopyKey[] {
  return [
    "next.limit1",
    hasDeadline ? "next.limit2" : "next.limit2.noDeadline",
    hasDeadline ? "next.limit3" : "next.limit3.noDeadline",
  ];
}

export function NextSteps({
  handoffHref,
  hasDeadline,
}: {
  handoffHref: string;
  hasDeadline: boolean;
}) {
  const t = voaCopy(useVoaLocale());

  return (
    <section
      className="voa-next"
      aria-labelledby="voa-next-heading voa-next-limits-heading"
    >
      <h2 className="voa-next__heading" id="voa-next-heading">
        {t("next.heading")}
      </h2>
      <ol aria-labelledby="voa-next-heading" className="voa-next__steps">
        {stepKeys(hasDeadline).map((s) => (
          <li className="voa-next__step" key={s.n}>
            <span className="voa-next__n" aria-hidden="true">
              {s.n}
            </span>
            <span>{t(s.key)}</span>
          </li>
        ))}
      </ol>

      <h2
        className="voa-next__heading voa-next__heading--limits"
        id="voa-next-limits-heading"
      >
        {t("next.limits.heading")}
      </h2>
      <ul
        aria-labelledby="voa-next-limits-heading"
        className="voa-next__limits"
      >
        {limitKeys(hasDeadline).map((key) => (
          <li className="voa-next__limit" key={key}>
            {t(key)}
          </li>
        ))}
      </ul>

      <a
        className="voa-next__ask"
        href={handoffHref}
        target="_blank"
        rel="noopener noreferrer"
      >
        {t("next.ask")}
      </a>
    </section>
  );
}
