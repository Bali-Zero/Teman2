import type { Permission, Viewer } from "./authorization.ts";
import { authorize } from "./authorization.ts";
import { requireViewer } from "./identity.ts";
import { currentResearchRoleAllowlist } from "./research-http.ts";
import { getMagazineBindings } from "./runtime-bindings.ts";
import { privateNoStoreHeaders } from "./security.ts";

export class OperationsHttpError extends Error {
  readonly status: 400 | 401 | 403 | 404 | 409;
  readonly code: string;

  constructor(status: 400 | 401 | 403 | 404 | 409, code: string) {
    super(code);
    this.status = status;
    this.code = code;
  }
}

export async function authorizeOperationsRequest(
  request: Request,
  permission: Permission,
): Promise<Viewer> {
  const bindings = getMagazineBindings();
  const allowlist = currentResearchRoleAllowlist();
  const viewer = await requireViewer(request.headers, {
    actorKeySecret: bindings.ACTOR_KEY_SECRET ?? "",
    roleAllowlist: allowlist,
  });
  if (!authorize(viewer, permission, allowlist).allowed)
    throw new OperationsHttpError(403, "forbidden");
  return viewer;
}

export function operationsJson(value: unknown, status = 200): Response {
  return Response.json(value, { status, headers: privateNoStoreHeaders() });
}

export function operationsFailure(error: unknown): Response {
  if (error instanceof OperationsHttpError)
    return operationsJson({ ok: false, error: error.code }, error.status);
  if (error instanceof TypeError)
    return operationsJson({ ok: false, error: "invalid_request" }, 400);
  const message = error instanceof Error ? error.message : "";
  return operationsJson(
    {
      ok: false,
      error: message.includes("authorization")
        ? "authorization_revoked"
        : message.includes("idempotency")
          ? "idempotency_conflict"
          : "conflict",
    },
    message.includes("authorization") ? 403 : 409,
  );
}
