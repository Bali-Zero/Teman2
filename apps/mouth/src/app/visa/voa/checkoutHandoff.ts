/**
 * Client-side-only handoff of the two `Applicant` fields the upload/review step
 * already collected (`full_name`, `passport_number`) from `upload/{resultId}` to
 * `checkout/{resultId}`. Mirrors `[hash]/page.tsx`'s own `readSubmittedAnswers`
 * pattern (localStorage there, sessionStorage here — this is a same-visit handoff
 * between two steps of one checkout, not a returning-visitor convenience) rather than
 * asking the backend to echo the customer's own answers back, or round-tripping them
 * through the URL (which the product rules forbid for PII-shaped values).
 *
 * `sessionStorage`, not `localStorage`: this data should not outlive the tab/session
 * once the customer is done, and never needs to survive a device switch.
 */

export interface CheckoutHandoffValues {
  full_name?: string;
  passport_number?: string;
}

function key(resultId: string): string {
  return `bz.garuda_voa.checkout_handoff.${resultId}`;
}

export function writeCheckoutHandoff(
  resultId: string,
  values: Record<string, string>,
): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(
      key(resultId),
      JSON.stringify({
        full_name: values.full_name,
        passport_number: values.passport_number,
      }),
    );
  } catch {
    // Best-effort only — checkout still works, it just falls back to asking the
    // customer to re-enter these two fields.
  }
}

export function readCheckoutHandoff(resultId: string): CheckoutHandoffValues {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.sessionStorage.getItem(key(resultId));
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    return {
      full_name:
        typeof parsed.full_name === "string" ? parsed.full_name : undefined,
      passport_number:
        typeof parsed.passport_number === "string"
          ? parsed.passport_number
          : undefined,
    };
  } catch {
    return {};
  }
}
