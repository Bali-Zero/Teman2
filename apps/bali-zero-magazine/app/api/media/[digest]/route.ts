import {
  authorize,
  type RoleAllowlist,
} from "../../../../lib/server/authorization.ts";
import { requireViewer } from "../../../../lib/server/identity.ts";
import { resolvePublishedMedia } from "../../../../lib/server/media.ts";
import { getMagazineBindings } from "../../../../lib/server/runtime-bindings.ts";
import { mediaSecurityHeaders } from "../../../../lib/server/security.ts";

function roleAllowlist(raw: string | undefined): RoleAllowlist {
  if (raw === undefined) throw new TypeError("role allowlist is required");
  const parsed: unknown = JSON.parse(raw);
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed))
    throw new TypeError("invalid role allowlist");
  const candidate = parsed as Partial<RoleAllowlist>;
  return {
    version: candidate.version ?? "",
    analysts: candidate.analysts ?? [],
    operators: candidate.operators ?? [],
  };
}

function denied(status: 401 | 404): Response {
  return new Response(null, { status, headers: mediaSecurityHeaders() });
}

export async function GET(
  request: Request,
  context: Readonly<{ params: Promise<Readonly<{ digest: string }>> }>,
): Promise<Response> {
  const bindings = getMagazineBindings();
  try {
    const roles = roleAllowlist(bindings.ROLE_ALLOWLIST_JSON);
    const viewer = await requireViewer(request.headers, {
      actorKeySecret: bindings.ACTOR_KEY_SECRET ?? "",
      roleAllowlist: roles,
    });
    if (!authorize(viewer, "magazine:read", roles).allowed) return denied(401);
  } catch {
    return denied(401);
  }
  if (bindings.DB === undefined || bindings.MEDIA === undefined)
    return denied(404);
  const { digest } = await context.params;
  const media = await resolvePublishedMedia(
    bindings.DB,
    bindings.MEDIA,
    digest,
  );
  if (media === null) return denied(404);
  const headers = mediaSecurityHeaders({
    "Content-Type": media.mimeType,
    "Content-Length": String(media.bytes.byteLength),
  });
  const body = new ArrayBuffer(media.bytes.byteLength);
  new Uint8Array(body).set(media.bytes);
  return new Response(body, { status: 200, headers });
}
