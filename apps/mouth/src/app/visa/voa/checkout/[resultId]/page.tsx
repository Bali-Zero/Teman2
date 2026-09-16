import { isGarudaPaymentsLive } from "../../flag";
import { CheckoutFlow } from "./CheckoutFlow";

/**
 * `/visa/voa/checkout/{resultId}` — customer-facing checkout step (L4 part 3).
 * `resultId` is the same opaque eligibility-check id `upload/{resultId}` uses.
 *
 * A server component so `isGarudaPaymentsLive()` is read fresh per request (the layout's
 * `export const dynamic = "force-dynamic"` already forces this route to render at request
 * time, not build time) — see flag.ts's own docblock on why this read must happen at call
 * time and never be hoisted.
 */
export default async function CheckoutPage({
  params,
}: {
  params: Promise<{ resultId: string }>;
}) {
  const { resultId } = await params;
  return (
    <CheckoutFlow resultId={resultId} paymentsLive={isGarudaPaymentsLive()} />
  );
}
