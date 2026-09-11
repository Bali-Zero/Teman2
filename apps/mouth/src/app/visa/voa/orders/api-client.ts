/**
 * Fetch wrapper for the three GARUDA VOA order/checkout operations this lane owns
 * (`products/garuda-voa/contracts/openapi.yaml`):
 *
 *  - `POST /api/visa/voa/orders` (createOrderFromCheck)
 *  - `POST /api/visa/voa/orders/{order_id}/browser-return-observations` (observePaymentBrowserReturn)
 *  - `GET  /api/visa/voa/orders/{order_id}` (getOrderAndPractice)
 *
 * Auth is the contract's `MagicSession` — the same `garuda_session` Secure, HttpOnly
 * cookie `upload/api-client.ts` documents, `Domain` set by the backend's
 * `get_cookie_domain()` (`.balizero.com` in production, `garuda_portal_auth.py`'s
 * `_set_account_session_cookie`) — never sent to a request that goes directly to
 * `nuzantara-rag.fly.dev`. `fetch` sends same-origin cookies by default, so no token
 * handling belongs here, but the base URL MUST stay same-origin `/api` (2026-09-03:
 * `NEXT_PUBLIC_API_URL` pointing at the Fly host directly 401'd the sibling staff
 * lane's cookie-session calls the same way — see `(workspace)/garuda-voa/api-client.ts`).
 */

import type {
  BrowserReturnObservationRequest,
  CreateOrderRequest,
  ErrorResponse,
  OrderCheckout,
  OrderErrorCode,
  OrderView,
} from "./types";

const API_BASE_URL = "/api";

export class GarudaOrderError extends Error {
  constructor(
    public readonly code: OrderErrorCode,
    public readonly retryable: boolean,
    public readonly httpStatus: number,
  ) {
    super(`GarudaOrderError(${code})`);
    this.name = "GarudaOrderError";
  }
}

/** Thrown when a response body can't be parsed as the contract's ErrorResponse or
 * success shape at all — a network-layer or truly unexpected-server failure, distinct
 * from a well-formed error the contract documents. Mirrors `upload/api-client.ts`. */
export class GarudaOrderUnexpectedError extends Error {
  public readonly sourceCause: unknown;

  constructor(
    public readonly httpStatus: number | null,
    cause?: unknown,
  ) {
    super("GarudaOrderUnexpectedError");
    this.name = "GarudaOrderUnexpectedError";
    this.sourceCause = cause;
  }
}

function isErrorResponseShape(body: unknown): body is ErrorResponse {
  return (
    typeof body === "object" &&
    body !== null &&
    "code" in body &&
    "retryable" in body &&
    "message_key" in body
  );
}

async function parseJsonBody(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch (cause) {
    throw new GarudaOrderUnexpectedError(response.status, cause);
  }
}

function throwFromErrorBody(response: Response, body: unknown): never {
  if (isErrorResponseShape(body)) {
    throw new GarudaOrderError(body.code, body.retryable, response.status);
  }
  throw new GarudaOrderUnexpectedError(response.status, body);
}

export interface CreateOrderParams {
  request: CreateOrderRequest;
  idempotencyKey: string;
  signal?: AbortSignal;
}

/** Creates (or, on exact idempotency replay, resumes) one order + checkout session.
 * `review_confirmed` must be the literal `true` the contract's `const` requires — the
 * caller has already run the customer through the upload/review step. */
export async function createOrder({
  request,
  idempotencyKey,
  signal,
}: CreateOrderParams): Promise<OrderCheckout> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/visa/voa/orders`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(request),
      signal,
    });
  } catch (cause) {
    throw new GarudaOrderUnexpectedError(null, cause);
  }

  const body = await parseJsonBody(response);
  if (response.ok) return body as OrderCheckout;
  throwFromErrorBody(response, body);
}

export interface ObservePaymentBrowserReturnParams {
  orderId: string;
  returnNonce: string;
  idempotencyKey: string;
  signal?: AbortSignal;
}

/** Records the non-authoritative OP-07 browser-return observation. Always a 204 (or
 * an error) — never a body, and never proof of payment. Callers must re-fetch
 * `getOrderAndPractice` afterward for the real state; this function itself must never
 * be treated as a payment result. */
export async function observePaymentBrowserReturn({
  orderId,
  returnNonce,
  idempotencyKey,
  signal,
}: ObservePaymentBrowserReturnParams): Promise<void> {
  const request: BrowserReturnObservationRequest = {
    return_nonce: returnNonce,
  };

  let response: Response;
  try {
    response = await fetch(
      `${API_BASE_URL}/visa/voa/orders/${encodeURIComponent(orderId)}/browser-return-observations`,
      {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify(request),
        signal,
      },
    );
  } catch (cause) {
    throw new GarudaOrderUnexpectedError(null, cause);
  }

  if (response.status === 204) return;

  const body = await parseJsonBody(response);
  throwFromErrorBody(response, body);
}

export interface GetOrderAndPracticeParams {
  orderId: string;
  signal?: AbortSignal;
}

/** Reads the authoritative order state + customer-safe practice view. This is the ONLY
 * source of truth for "did the payment succeed" — never the browser-return observation. */
export async function getOrderAndPractice({
  orderId,
  signal,
}: GetOrderAndPracticeParams): Promise<OrderView> {
  let response: Response;
  try {
    response = await fetch(
      `${API_BASE_URL}/visa/voa/orders/${encodeURIComponent(orderId)}`,
      { method: "GET", credentials: "same-origin", signal },
    );
  } catch (cause) {
    throw new GarudaOrderUnexpectedError(null, cause);
  }

  const body = await parseJsonBody(response);
  if (response.ok) return body as OrderView;
  throwFromErrorBody(response, body);
}
