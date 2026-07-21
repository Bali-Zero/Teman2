import {
  authorize,
  parseRoleAllowlist,
} from "../../../../lib/server/authorization.ts";
import { requireViewer } from "../../../../lib/server/identity.ts";
import { resolvePublishedStoryMedia } from "../../../../lib/server/media.ts";
import { getMagazineBindings } from "../../../../lib/server/runtime-bindings.ts";
import { mediaSecurityHeaders } from "../../../../lib/server/security.ts";

function denied(status: 401 | 404): Response {
  return new Response(null, { status, headers: mediaSecurityHeaders() });
}

export async function GET(
  request: Request,
  context: Readonly<{ params: Promise<Readonly<{ slug: string }>> }>,
): Promise<Response> {
  const bindings = getMagazineBindings();
  try {
    const roles = parseRoleAllowlist(bindings.ROLE_ALLOWLIST_JSON);
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
  const { slug } = await context.params;
  const media = await resolvePublishedStoryMedia(
    bindings.DB,
    bindings.MEDIA,
    slug,
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
