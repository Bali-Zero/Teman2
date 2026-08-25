/**
 * Hand-written types mirroring the FROZEN GARUDA VOA contract
 * (`products/garuda-voa/contracts/openapi.yaml`) for the three order/checkout/tracker
 * operations this lane calls: `createOrderFromCheck`, `observePaymentBrowserReturn`,
 * `getOrderAndPractice`.
 *
 * Hand-written for the same reason `upload/types.ts` is (see that file's header): the
 * OpenAPI -> generated-TS-client toolchain isn't wired in yet (ASSEMBLY-LINE.md backlog
 * #4). This is a direct transcription of the contract, not an invention — check both
 * before changing either.
 */

export interface Applicant {
  full_name: string;
  email: string;
  phone: string;
  passport_number: string;
}

export interface CreateOrderRequest {
  result_id: string;
  applicant: Applicant;
  review_confirmed: true;
}

/** openapi.yaml `OrderState` — the full lifecycle, including terminal states an order
 * created before the customer's tab reconnects may already be in. */
export type OrderState =
  "created" | "awaiting_payment" | "paid" | "failed" | "expired" | "refunded";

export interface OrderCheckout {
  order_id: string;
  /** `created` is deliberately absent from the contract's enum here — see
   * openapi.yaml's 2026-08-25 amendment comment on this field. Never hardcode
   * `awaiting_payment` as the only possible value this response can carry. */
  order_state: Exclude<OrderState, "created">;
  price_idr: number;
  /** Required-and-nullable by design (contract comment): null means there is nothing
   * to pay right now (order moved past payment, or terminal) — never treat a missing
   * key as "nothing to pay" via `undefined`, always read the literal `null`. */
  checkout_url: string | null;
}

export interface BrowserReturnObservationRequest {
  return_nonce: string;
}

export type PracticeState =
  | "Received"
  | "In review"
  | "Blocked"
  | "Submitted"
  | "Approved"
  | "Rejected"
  | "Delivered";

export interface PracticeView {
  practice_id: string;
  state: PracticeState;
  /** Customer-safe copy KEY (`garuda_voa.practice.*`), never rendered prose — the
   * contract has no closed catalog of actual key values yet, so this lane humanizes
   * the key itself rather than inventing a lookup table that would silently drift
   * (see orders/messages.ts `humanizePracticeKey`). */
  customer_reason_key?: string;
  required_action_key?: string;
  artifact_available: boolean;
}

export interface OrderView {
  order_id: string;
  order_state: OrderState;
  price_idr: number;
  /** Non-authoritative OP-07 browser-return observation. Can NEVER by itself justify
   * rendering a paid/success state — only `order_state === "paid"` can. */
  browser_observation: "browser_not_returned" | "browser_return_observed";
  practice: PracticeView | null;
}

/** Closed error catalog — union of every `x-error-codes` list across the three
 * operations this lane calls (createOrderFromCheck, observePaymentBrowserReturn,
 * getOrderAndPractice). An unlisted code from the network is still handled (see
 * api-client.ts) but treated as a generic retryable failure. */
export type OrderErrorCode =
  | "IDEMPOTENCY_KEY_REQUIRED"
  | "SESSION_REQUIRED"
  | "GARUDA_PUBLIC_DISABLED"
  | "RESULT_NOT_FOUND"
  | "ORDER_NOT_FOUND"
  | "IDEMPOTENCY_CONFLICT"
  | "ORDER_NOT_READY"
  | "INVALID_STATE_TRANSITION"
  | "INVALID_REQUEST"
  | "RATE_LIMITED"
  | "PERSISTENCE_POLICY_UNAVAILABLE"
  | "PRICE_UNRESOLVABLE"
  | "PAYMENT_PROVIDER_UNAVAILABLE"
  | "SERVICE_UNAVAILABLE"
  | "INTERNAL_ERROR";

export interface ErrorResponse {
  code: OrderErrorCode;
  retryable: boolean;
  message_key: string;
}
