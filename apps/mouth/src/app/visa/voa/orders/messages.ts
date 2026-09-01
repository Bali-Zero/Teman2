/**
 * Customer-facing copy keyed by the contract's closed `OrderErrorCode` catalog
 * (see types.ts). Same convention as `upload/messages.ts`: `COPY` is typed
 * `Record<OrderErrorCode, string>`, so adding a code to the union without a matching
 * entry here fails the BUILD, not a runtime lookup.
 */

import type { OrderErrorCode } from "./types";

const COPY: Record<OrderErrorCode, string> = {
  IDEMPOTENCY_KEY_REQUIRED:
    "Something went wrong preparing that request. Please try again.",
  SESSION_REQUIRED:
    "Your session has expired. Please sign in again to continue.",
  GARUDA_PUBLIC_DISABLED:
    "This isn't available right now. Please try again later.",
  RESULT_NOT_FOUND:
    "We couldn't find your application. Please start again from your check result.",
  ORDER_NOT_FOUND:
    "We couldn't find this order. Please check the link or start again.",
  IDEMPOTENCY_CONFLICT:
    "That didn't match your previous attempt. Please reload and try again.",
  ORDER_NOT_READY:
    "Your application isn't ready to check out yet. Please confirm your document details first.",
  INVALID_STATE_TRANSITION:
    "This order has already moved on. Reload the page to see its current state.",
  INVALID_REQUEST: "We couldn't process that request. Please try again.",
  RATE_LIMITED: "Too many attempts. Please wait a moment and try again.",
  PERSISTENCE_POLICY_UNAVAILABLE:
    "Checkout is temporarily unavailable. Please try again in a moment.",
  PRICE_UNRESOLVABLE:
    "We couldn't confirm your price right now. Please try again shortly.",
  PAYMENT_PROVIDER_UNAVAILABLE:
    "Our payment provider is temporarily unavailable. Please try again shortly.",
  SERVICE_UNAVAILABLE:
    "Something went wrong on our end. Please try again in a moment.",
  INTERNAL_ERROR: "Something went wrong on our end. Please try again.",
};

const GENERIC_NETWORK_ERROR =
  "We couldn't reach the server. Check your connection and try again.";

export function messageFor(code: OrderErrorCode): string {
  return COPY[code];
}

export function messageForUnknownCode(code: string): string {
  return code in COPY ? COPY[code as OrderErrorCode] : GENERIC_NETWORK_ERROR;
}

/**
 * The contract's `customer_reason_key` / `required_action_key` fields are documented
 * as a closed vocabulary (`^garuda_voa\.practice\.[a-z0-9_]+$` /
 * `^garuda_voa\.action\.[a-z0-9_]+$`), but no catalog of the actual key VALUES exists
 * anywhere in this repo yet (checked `products/garuda-voa/**`,
 * `apps/backend-rag/backend/services/garuda_flow/**` — nothing defines them). Building
 * a lookup table here would be a second, unsourced catalog exactly like the one
 * `openapi.yaml`'s own 2026-08-25 amendment comment warns against: a contract/lane
 * pair where reality has more values than either side wrote down, silently drifting the
 * moment the backend adds one. Instead: strip the namespace prefix and humanize the
 * remainder, same fallback pattern `UploadFlow.tsx::fieldLabel` already uses for an
 * unrecognized `field_path`. If a real catalog lands, this is the one function to swap.
 */
export function humanizePracticeKey(key: string): string {
  const withoutPrefix = key.replace(/^garuda_voa\.(practice|action)\./, "");
  const words = withoutPrefix.replace(/_/g, " ").trim();
  if (!words) return key;
  return words.charAt(0).toUpperCase() + words.slice(1);
}
