import { resolvePublishedStoryMedia } from "../../../../lib/server/media.ts";
import { getMagazineBindings } from "../../../../lib/server/runtime-bindings.ts";
import { publicMediaSecurityHeaders } from "../../../../lib/server/security.ts";

function denied(status: 404): Response {
  return new Response(null, { status, headers: publicMediaSecurityHeaders() });
}

export async function GET(
  _request: Request,
  context: Readonly<{ params: Promise<Readonly<{ slug: string }>> }>,
): Promise<Response> {
  const bindings = getMagazineBindings();
  if (bindings.DB === undefined || bindings.MEDIA === undefined)
    return denied(404);
  const { slug } = await context.params;
  const media = await resolvePublishedStoryMedia(
    bindings.DB,
    bindings.MEDIA,
    slug,
  );
  if (media === null) return denied(404);
  const headers = publicMediaSecurityHeaders({
    "Content-Type": media.mimeType,
    "Content-Length": String(media.bytes.byteLength),
  });
  const body = new ArrayBuffer(media.bytes.byteLength);
  new Uint8Array(body).set(media.bytes);
  return new Response(body, { status: 200, headers });
}
