/**
 * Fetch wrapper for the four GARUDA VOA STAFF operations (prefix
 * `/api/visa/voa/staff`, step8-spec.md Deliverable A):
 *
 *  - `GET  /api/visa/voa/staff/practices` (listStaffPractices)
 *  - `GET  /api/visa/voa/staff/practices/{practice_id}` (getStaffPractice)
 *  - `POST /api/visa/voa/staff/practices/{practice_id}/assignment` (assignPractice)
 *  - `POST /api/visa/voa/staff/practices/{practice_id}/transitions` (transitionPractice)
 *
 * Auth: the CRM cookie session (`HybridAuthMiddleware`, see
 * `deps/auth.py::get_current_user`) the rest of the `(workspace)` surface
 * already relies on — same `fetch(..., { credentials: "same-origin" })`
 * pattern used elsewhere. The base URL is deliberately hardcoded same-origin
 * (`lib/api/index.ts`'s `API_BASE_URL = ""`, and the literal `/api/...` fetch
 * in `(workspace)/review/page.tsx`, are the established convention for
 * cookie-session-authenticated `(workspace)` calls): every request MUST go
 * through the Next.js same-origin proxy (`app/api/[...path]/route.ts`),
 * which is also the only place that promotes the `nz_csrf_token` cookie into
 * the `X-CSRF-Token` header for mutating methods. `NEXT_PUBLIC_API_URL`
 * points at the Fly backend host directly in production — using it here sent
 * requests cross-origin, without the proxy's CSRF promotion and without the
 * httpOnly session cookie (scoped to `.balizero.com`, never sent to
 * `nuzantara-rag.fly.dev`), which 401'd every staff call live.
 */

import type {
  AssignPracticeRequest,
  PracticeTransitionRequest,
  PracticeView,
  StaffErrorCode,
  StaffErrorResponse,
  StaffPracticeListResponse,
  StaffPracticeListRow,
  StaffPracticeView,
} from "./types";

const API_BASE_URL = "/api";

export class GarudaStaffError extends Error {
  constructor(
    public readonly code: StaffErrorCode,
    public readonly retryable: boolean,
    public readonly httpStatus: number,
  ) {
    super(`GarudaStaffError(${code})`);
    this.name = "GarudaStaffError";
  }
}

/** Thrown when a response body can't be parsed as the contract's
 * ErrorResponse or success shape at all. Mirrors `orders/api-client.ts`. */
export class GarudaStaffUnexpectedError extends Error {
  public readonly sourceCause: unknown;

  constructor(
    public readonly httpStatus: number | null,
    cause?: unknown,
  ) {
    super("GarudaStaffUnexpectedError");
    this.name = "GarudaStaffUnexpectedError";
    this.sourceCause = cause;
  }
}

function isErrorResponseShape(body: unknown): body is StaffErrorResponse {
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
    throw new GarudaStaffUnexpectedError(response.status, cause);
  }
}

function throwFromErrorBody(response: Response, body: unknown): never {
  if (isErrorResponseShape(body)) {
    throw new GarudaStaffError(body.code, body.retryable, response.status);
  }
  throw new GarudaStaffUnexpectedError(response.status, body);
}

async function fetchJson(url: string, init: RequestInit): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(url, { credentials: "same-origin", ...init });
  } catch (cause) {
    throw new GarudaStaffUnexpectedError(null, cause);
  }
  const body = await parseJsonBody(response);
  if (response.ok) return body;
  throwFromErrorBody(response, body);
}

export interface ListStaffPracticesParams {
  state?: string;
  assigned?: "me" | "all";
  cursor?: string;
  signal?: AbortSignal;
}

export async function listStaffPractices({
  state,
  assigned,
  cursor,
  signal,
}: ListStaffPracticesParams = {}): Promise<StaffPracticeListResponse> {
  const params = new URLSearchParams();
  if (state) params.set("state", state);
  if (assigned) params.set("assigned", assigned);
  if (cursor) params.set("cursor", cursor);
  const qs = params.toString();
  const body = await fetchJson(
    `${API_BASE_URL}/visa/voa/staff/practices${qs ? `?${qs}` : ""}`,
    { method: "GET", signal },
  );
  return body as StaffPracticeListResponse;
}

export async function getStaffPractice(
  practiceId: string,
  signal?: AbortSignal,
): Promise<StaffPracticeView> {
  const body = await fetchJson(
    `${API_BASE_URL}/visa/voa/staff/practices/${encodeURIComponent(practiceId)}`,
    { method: "GET", signal },
  );
  return body as StaffPracticeView;
}

export interface AssignPracticeParams {
  practiceId: string;
  request: AssignPracticeRequest;
  idempotencyKey: string;
  signal?: AbortSignal;
}

/** Admin-only per the contract — a non-admin call is expected to 403
 * ACCESS_DENIED; this client does not pre-check the role, the server does.
 * Returns `StaffPracticeListItem` (openapi.yaml), NOT the full
 * `StaffPracticeView` — no `private_staff_note`/`resume_target` on this
 * response. Callers merge this into an existing detail view, never replace
 * it wholesale (see [practiceId]/page.tsx::handleAssign). */
export async function assignPractice({
  practiceId,
  request,
  idempotencyKey,
  signal,
}: AssignPracticeParams): Promise<StaffPracticeListRow> {
  const body = await fetchJson(
    `${API_BASE_URL}/visa/voa/staff/practices/${encodeURIComponent(practiceId)}/assignment`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(request),
      signal,
    },
  );
  return body as StaffPracticeListRow;
}

export interface TransitionPracticeParams {
  practiceId: string;
  request: PracticeTransitionRequest;
  idempotencyKey: string;
  signal?: AbortSignal;
}

export interface TransitionPracticeResult {
  practice: PracticeView;
  /** True only on an exact-replay 200 that carried the
   * `Idempotency-Replayed` response header — never inferred from the body. */
  replayed: boolean;
}

export async function transitionPractice({
  practiceId,
  request,
  idempotencyKey,
  signal,
}: TransitionPracticeParams): Promise<TransitionPracticeResult> {
  let response: Response;
  try {
    response = await fetch(
      `${API_BASE_URL}/visa/voa/staff/practices/${encodeURIComponent(practiceId)}/transitions`,
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
    throw new GarudaStaffUnexpectedError(null, cause);
  }

  const body = await parseJsonBody(response);
  if (!response.ok) throwFromErrorBody(response, body);
  return {
    practice: body as PracticeView,
    replayed: response.headers.get("Idempotency-Replayed") === "true",
  };
}
