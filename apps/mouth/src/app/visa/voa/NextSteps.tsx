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
function steps(hasDeadline: boolean): { n: string; text: string }[] {
  return [
    {
      n: "1",
      text: "Upload a photo of your passport page. We check it can actually be read before anything else happens.",
    },
    {
      n: "2",
      text: "Pay once, the price shown above. Nothing further is collected at the counter.",
    },
    {
      n: "3",
      text: hasDeadline
        ? "We prepare and file your application at the office the date above is published by."
        : "We prepare and file your application at the office that publishes your filing deadline.",
    },
    {
      n: "4",
      text: "You follow it like a parcel, and the result reaches the email you gave us.",
    },
  ];
}

function limits(hasDeadline: boolean): string[] {
  return [
    "The decision is Immigration's, not ours. We prepare your application and file it correctly — we do not approve it, and nobody who says otherwise can.",
    hasDeadline
      ? "We do not quote a processing time. The date above is the counter's published filing deadline, which is a different thing and the only one we can stand behind."
      : "We do not quote a processing time. We confirm the counter's published filing deadline before you pay, and that date is a different thing from a processing time — it is the only one we can stand behind.",
    hasDeadline
      ? "That date is scoped to one office. If you end up filing somewhere else, tell us and we will confirm yours before you rely on it."
      : "A published deadline is scoped to one office. Tell us where you plan to file and we will confirm yours before you rely on it.",
  ];
}

export function NextSteps({
  handoffHref,
  hasDeadline,
}: {
  handoffHref: string;
  hasDeadline: boolean;
}) {
  return (
    <section
      className="voa-next"
      aria-labelledby="voa-next-heading voa-next-limits-heading"
    >
      <h2 className="voa-next__heading" id="voa-next-heading">
        What happens next
      </h2>
      <ol aria-labelledby="voa-next-heading" className="voa-next__steps">
        {steps(hasDeadline).map((s) => (
          <li className="voa-next__step" key={s.n}>
            <span className="voa-next__n" aria-hidden="true">
              {s.n}
            </span>
            <span>{s.text}</span>
          </li>
        ))}
      </ol>

      <h2
        className="voa-next__heading voa-next__heading--limits"
        id="voa-next-limits-heading"
      >
        What we cannot promise
      </h2>
      <ul
        aria-labelledby="voa-next-limits-heading"
        className="voa-next__limits"
      >
        {limits(hasDeadline).map((l) => (
          <li className="voa-next__limit" key={l.slice(0, 24)}>
            {l}
          </li>
        ))}
      </ul>

      <a
        className="voa-next__ask"
        href={handoffHref}
        target="_blank"
        rel="noopener noreferrer"
      >
        Ask us anything before you pay
      </a>
    </section>
  );
}
