/**
 * Detect the "the proposal already left the claimable state" 409, so a retry
 * after a transient blip (whose write already committed) is shown as an
 * informational refresh, NOT a red "action failed" error.
 *
 * The backend guard (shared by approve AND reject) raises HTTP 409 with
 * detail=`Proposal must be review_claimed (status=<actual>).`; the api client
 * surfaces that detail verbatim into Error.message. We anchor on the stable
 * "must be review_claimed" phrase, then branch on the terminal status:
 *   - status=routed   → the document was already approved & filed.
 *   - status=rejected → the proposal was already rejected.
 * Any other status (e.g. review_pending) or a different error (network/500,
 * "Claim lease expired", etc.) returns null and stays on the normal error path.
 *
 * Lives in its own module (not page.tsx): Next.js App Router rejects any
 * non-reserved named export from a `page.tsx` ("does not match the required
 * types of a Next.js Page"), which fails the production `next build`.
 */
export function classifyResolvedDecideError(
  message: string | undefined | null,
): "already_filed" | "already_rejected" | null {
  if (!message || !message.includes("must be review_claimed")) return null;
  if (message.includes("status=routed")) return "already_filed";
  if (message.includes("status=rejected")) return "already_rejected";
  return null;
}
