import { protectedPageSecurityHeaders } from "../lib/server/security.ts";

export function secureProtectedHtmlResponse(
  _request: Request,
  response: Response,
): Response {
  const contentType = response.headers.get("content-type") ?? "";
  if (!/^text\/html\b/i.test(contentType)) return response;

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: protectedPageSecurityHeaders(response.headers),
  });
}
