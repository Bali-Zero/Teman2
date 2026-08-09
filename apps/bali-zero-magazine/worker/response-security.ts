import {
  protectedPageSecurityHeaders,
  publicPageSecurityHeaders,
} from "../lib/server/security.ts";

export function secureProtectedHtmlResponse(
  request: Request,
  response: Response,
): Response {
  const contentType = response.headers.get("content-type") ?? "";
  if (!/^text\/html\b/i.test(contentType)) return response;
  const pathname = new URL(request.url).pathname;
  const internal =
    pathname === "/research" ||
    pathname.startsWith("/research/") ||
    pathname === "/operations" ||
    pathname.startsWith("/operations/");
  const headers = internal
    ? protectedPageSecurityHeaders(response.headers)
    : publicPageSecurityHeaders(response.headers);

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}
