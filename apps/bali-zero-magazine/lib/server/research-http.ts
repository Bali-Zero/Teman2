import type { Permission, RoleAllowlist, Viewer } from "./authorization.ts";
import { authorize, validateRoleAllowlist } from "./authorization.ts";
import { requireViewer } from "./identity.ts";
import type { ResearchJobView } from "./research-repository.ts";
import { getMagazineBindings } from "./runtime-bindings.ts";
import { privateNoStoreHeaders } from "./security.ts";

export function currentResearchRoleAllowlist(): RoleAllowlist {
  const raw = getMagazineBindings().ROLE_ALLOWLIST_JSON;
  if (raw === undefined) throw new TypeError("role allowlist is required");
  const value: unknown = JSON.parse(raw);
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError("invalid role allowlist");
  }
  const record = value as Record<string, unknown>;
  if (
    Object.keys(record).sort().join(",") !== "analysts,operators,version" ||
    typeof record.version !== "string" ||
    !Array.isArray(record.analysts) ||
    !Array.isArray(record.operators)
  ) {
    throw new TypeError("invalid role allowlist");
  }
  const current = {
    version: record.version,
    analysts: record.analysts as readonly string[],
    operators: record.operators as readonly string[],
  };
  validateRoleAllowlist(current);
  return current;
}

export async function authorizeResearchRequest(
  request: Request,
  permission: Permission,
): Promise<Viewer> {
  const bindings = getMagazineBindings();
  const current = currentResearchRoleAllowlist();
  const viewer = await requireViewer(request.headers, {
    actorKeySecret: bindings.ACTOR_KEY_SECRET ?? "",
    roleAllowlist: current,
  });
  if (!authorize(viewer, permission, current).allowed) {
    throw new ResearchHttpError(403, "forbidden");
  }
  return viewer;
}

export function requireSameOriginMutation(request: Request): void {
  let origin: string;
  try {
    origin = new URL(request.url).origin;
  } catch {
    throw new ResearchHttpError(403, "forbidden");
  }
  if (
    request.headers.get("origin") !== origin ||
    request.headers.get("x-magazine-csrf") !== "1"
  ) {
    throw new ResearchHttpError(403, "forbidden");
  }
}

export async function readClosedJson(
  request: Request,
  maximumBytes = 32_768,
): Promise<unknown> {
  if (request.headers.get("content-type") !== "application/json") {
    throw new ResearchHttpError(400, "invalid_request");
  }
  const raw = await request.text();
  if (new TextEncoder().encode(raw).byteLength > maximumBytes) {
    throw new ResearchHttpError(400, "invalid_request");
  }
  try {
    return JSON.parse(raw) as unknown;
  } catch {
    throw new ResearchHttpError(400, "invalid_request");
  }
}

export class ResearchHttpError extends Error {
  readonly status: 400 | 401 | 403 | 404 | 409;
  readonly code: string;

  constructor(status: 400 | 401 | 403 | 404 | 409, code: string) {
    super(code);
    this.status = status;
    this.code = code;
  }
}

export function publicResearchJob(job: ResearchJobView) {
  const result =
    job.result === null
      ? null
      : {
          schema_version: job.result.schema_version,
          job_id: job.result.job_id,
          mode: job.result.mode,
          status: job.result.status,
          completed_at: job.result.completed_at,
          summary: job.result.summary,
          claims: job.result.claims,
          failure: job.result.failure,
        };
  return {
    job_id: job.job_id,
    mode: job.mode,
    request: job.request,
    status: job.status,
    created_at: job.created_at,
    expires_at: job.expires_at,
    completed_at: job.completed_at,
    result,
  };
}

export function researchJson(value: unknown, status = 200): Response {
  return Response.json(value, {
    status,
    headers: privateNoStoreHeaders(),
  });
}

export function researchFailure(error: unknown): Response {
  if (error instanceof ResearchHttpError) {
    return researchJson({ ok: false, error: error.code }, error.status);
  }
  if (error instanceof TypeError) {
    return researchJson({ ok: false, error: "invalid_request" }, 400);
  }
  return researchJson({ ok: false, error: "conflict" }, 409);
}
